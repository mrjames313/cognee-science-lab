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

from .models import IdentitySource
from .validation import IntentError

if TYPE_CHECKING:
    from cognee.modules.chunking.models import DocumentChunk

    from .admission import OccurrenceMap
    from .entry import Semantics


@dataclass(frozen=True)
class EditDraft:
    """What an edit describer reads: the current description, the
    registered text, the new text and the new text's native chunks."""

    old: IdentitySource
    previous_text: str
    text: str
    chunks: list[DocumentChunk]


EditDescriber = Callable[[EditDraft], tuple[IdentitySource, "OccurrenceMap"]]


async def update(
    publisher,
    source: IdentitySource,
    text: str,
    *,
    describe_edit: EditDescriber | None,
    expected_revision: int,
    semantics: Semantics | None,
    fault_stage: str | None = None,
    origin: str = "runtime",
) -> IdentitySource:
    """Replace the original of `source` with `text` and publish the next
    revision that `describe_edit` gives, with its occurrence map, from the
    new text's in-memory native chunks (`replace_text`). Cognee rebuilds
    the whole document; the identity revision is admitted against the
    occurrence map. Refused without a describer: no lab edit guesses a
    description. Returns the published revision."""
    from .captured_chunks import recorded_budget
    from .registered import context_for
    from .native_chunks import chunk_text
    from .text_changes import TextChange, original_context, read_original

    if describe_edit is None:
        raise IntentError(
            "describer_missing",
            "A lab update needs a describer for the edited description",
        )
    # The budget is read from the native chunks, which may be what is gone.
    await publisher.refuse_natively_deleted(source)
    ctx = await context_for(source.identity_data_id)
    previous_text = await read_original(source, ctx)
    budget = await recorded_budget(source, publisher.graph)
    chunks = await chunk_text(text, await original_context(source, ctx), budget)
    intended, occurrence_map = describe_edit(
        EditDraft(source, previous_text, text, chunks)
    )
    await replace_text(
        publisher,
        intended,
        TextChange(previous_text, text, occurrence_map, budget),
        expected_revision=expected_revision,
        semantics=semantics,
        fault_stage=fault_stage,
        origin=origin,
    )
    return intended


def rebuild_hooks(semantics, publisher, source, chunks, ctx) -> dict:
    """The publisher's `semantic_writer` and `verify_semantics` for a text
    change: `semantics` over the rebuilt chunks, which the text change puts
    in `chunks`, with the original's context as it is then; checks of
    nothing for a source with no captured facts."""
    from .text_changes import original_context

    async def write():
        if semantics is not None:
            await semantics.write(
                publisher,
                source,
                list(chunks.values()),
                await original_context(source, ctx),
            )

    async def verify():
        if semantics is not None:
            await semantics.verify(
                publisher,
                source,
                list(chunks.values()),
                await original_context(source, ctx),
            )

    return dict(semantic_writer=write, verify_semantics=verify)


async def replace_text(
    publisher,
    intended: IdentitySource,
    change,
    *,
    expected_revision: int,
    semantics: Semantics | None,
    fault_stage: str | None = None,
    origin: str = "runtime",
):
    """Publish `intended` with its text change (`TextChange`) in one lab
    Task, run by Cognee's `run_pipeline` under the pipeline name
    `cognify_pipeline` over the original. The Task calls the publisher's
    `replace`, which begins the attempt, forgets the original's memory,
    registers the new text and rebuilds the chunks with the standard Tasks
    (`build_chunks`), then publishes. `update` calls this for a new edit,
    and `reconcile` for a failed one with the text change its plan saved.
    A lab failure is recorded in the ledger, the run still completes, and
    the failure is raised after the run."""
    from cognee.modules.pipelines.operations.pipeline import run_pipeline
    from cognee.modules.pipelines.tasks.task import Task

    from .registered import context_for, read_texts
    from .native_chunks import chunk_text
    from .text_changes import original_context

    generated = await context_for(intended.identity_data_id)
    original = await original_context(intended, generated)
    chunks = {
        str(c.id): c
        for c in await chunk_text(change.text, original, change.chunk_budget)
    }
    failures = []

    async def identity_update(items, ctx=None):
        """Replace the source with the identity Data's context, which
        carries no run ID, never the run's."""
        try:
            await publisher.replace(
                intended,
                texts=await read_texts(
                    intended, known={intended.original_input_ref: change.text}
                ),
                chunks=chunks,
                ctx=generated,
                expected_revision=expected_revision,
                text_change=change,
                origin="test/fault_injection" if fault_stage else origin,
                fault_stage=fault_stage,
                **rebuild_hooks(semantics, publisher, intended, chunks, generated),
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
