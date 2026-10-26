"""The lab's update over Cognee's own pipeline.

`update` edits a published source's original: one lab Task under
`cognify_pipeline` replaces the text, rebuilds the chunks with Cognee's
standard Tasks and publishes the next revision (`replace_text`). Like the
lab Task of `cognify` (entry.py), it writes with contexts of its own, never
the run's, and the run passes no rollback handler.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .entry import semantic_hooks
from .models import IdentitySource

if TYPE_CHECKING:
    from cognee.modules.chunking.models import DocumentChunk
    from cognee.modules.pipelines.models import PipelineContext

    from .admission import OccurrenceMap
    from .entry import Semantics
    from .text_changes import TextChange


@dataclass(frozen=True)
class EditDraft:
    """What an edit describer reads: the current description, the
    registered text, the new text and the new text's native chunks."""

    old: IdentitySource
    previous_text: str
    text: str
    chunks: list[DocumentChunk]


EditDescriber = Callable[[EditDraft], IdentitySource]


class NoFacts:
    """The semantics of a source with no captured facts. A text change
    still names a writer and a verifier (`replace`); these write and check
    nothing."""

    async def write(self, *_):
        pass

    async def verify(self, *_):
        pass


async def update(
    publisher,
    source: IdentitySource,
    text: str,
    occurrence_map: OccurrenceMap,
    *,
    describe_edit: EditDescriber,
    expected_revision: int,
    semantics: Semantics | None,
    fault_stage: str | None = None,
    origin: str = "runtime",
) -> IdentitySource:
    """Replace the original of `source` with `text` and publish the next
    revision that `describe_edit` gives from the new text's in-memory
    native chunks, admitted against `occurrence_map`. Cognee rebuilds the
    whole document. Returns the published revision."""
    from .captured_chunks import recorded_budget
    from .native_chunks import chunk_text
    from .registered import context_for
    from .text_changes import TextChange, original_context, read_original

    # The budget is read from the native chunks, which may be what is gone.
    await publisher.refuse_natively_deleted(source)
    generated = await context_for(source.identity_data_id)
    previous_text = await read_original(source, generated)
    budget = await recorded_budget(source, publisher.graph)
    original = await original_context(source, generated)
    chunks = await chunk_text(text, original, budget)
    intended = describe_edit(EditDraft(source, previous_text, text, chunks))
    await _replace(
        publisher,
        intended,
        TextChange(previous_text, text, occurrence_map, budget),
        chunks,
        generated,
        original,
        expected_revision=expected_revision,
        semantics=semantics,
        fault_stage=fault_stage,
        origin=origin,
    )
    return intended


async def replace_text(
    publisher,
    intended: IdentitySource,
    change: TextChange,
    *,
    expected_revision: int,
    semantics: Semantics | None,
    fault_stage: str | None = None,
    origin: str = "runtime",
):
    """Publish `intended` with its text change: `reconcile` of a failed
    edit, with the text change its plan saved, and a forget's erasure retry
    of one."""
    from .native_chunks import chunk_text
    from .registered import context_for
    from .text_changes import original_context

    generated = await context_for(intended.identity_data_id)
    original = await original_context(intended, generated)
    await _replace(
        publisher,
        intended,
        change,
        await chunk_text(change.text, original, change.chunk_budget),
        generated,
        original,
        expected_revision=expected_revision,
        semantics=semantics,
        fault_stage=fault_stage,
        origin=origin,
    )


async def _replace(
    publisher,
    intended: IdentitySource,
    change: TextChange,
    chunks: list[DocumentChunk],
    generated: PipelineContext,
    original: PipelineContext,
    *,
    expected_revision: int,
    semantics: Semantics | None,
    fault_stage: str | None,
    origin: str,
):
    """Publish `intended` with its text change in one lab Task, run by
    Cognee's `run_pipeline` under the pipeline name `cognify_pipeline` over
    the original. `chunks` are the new text's in-memory native chunks. The
    Task calls the publisher's `replace` with the identity Data's context
    (`generated`), which carries no run ID. `replace` begins the attempt,
    forgets the original's memory, registers the new text and rebuilds the
    chunks with the standard Tasks (`build_chunks`), then publishes. A lab
    failure is recorded in the ledger, the run still completes, and the
    failure is raised after the run."""
    from cognee.modules.pipelines.operations.pipeline import run_pipeline
    from cognee.modules.pipelines.tasks.task import Task

    from .registered import read_texts
    from .text_changes import original_context

    # The text change puts the rebuilt chunks here.
    by_id = {str(c.id): c for c in chunks}
    failures = []

    async def identity_update(items, ctx=None):
        try:
            await publisher.replace(
                intended,
                texts=await read_texts(
                    intended, known={intended.original_input_ref: change.text}
                ),
                chunks=by_id,
                ctx=generated,
                expected_revision=expected_revision,
                text_change=change,
                origin="test/fault_injection" if fault_stage else origin,
                fault_stage=fault_stage,
                **semantic_hooks(
                    semantics or NoFacts(),
                    publisher,
                    intended,
                    lambda: list(by_id.values()),
                    lambda: original_context(intended, generated),
                ),
            )
        except Exception as exc:
            failures.append(exc)
        return items

    async for _ in run_pipeline(
        tasks=[Task(identity_update, needs_llm=False)],
        data=[original.data_item],
        datasets=[intended.dataset_id],
        user=original.user,
        pipeline_name="cognify_pipeline",
        incremental_loading=False,
        rollback_handler=None,
        skip_connection_test=True,
    ):
        pass
    if failures:
        (failure,) = failures
        raise failure
