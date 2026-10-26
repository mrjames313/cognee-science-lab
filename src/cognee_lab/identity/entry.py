"""The lab's add, cognify and remember over Cognee's own pipeline.

`add` registers an original document and its identity description. `cognify`
runs Cognee's standard Tasks under the pipeline name `cognify_pipeline`, so
Cognee builds the document and its chunks, then one lab Task publishes the
description once per document over the whole chunk set. `remember` is `add`
then `cognify`; `remember_in_order` does both for each source of a root.
`update` (entry_update.py) edits a published source's original.

The lab Task never writes with the pipeline's context. Its writes carry no
pipeline run ID, so Cognee's rollback and its startup recovery of an
abandoned run can only ever reach the native document and chunks. The run
passes no rollback handler, so a failed run keeps even those, and the
ledger, not a rollback, decides what happens next (forward recovery through
`reconcile`).

A plain `cognee.cognify`, `cognee.remember` or `cognee.update` bypasses the
identity layer. The lab stamps every file it manages as cognified so a plain
`cognee.cognify` skips them; see docs/stage6_identity_standard_entry_points.md
for the gaps in that protection.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from .models import ChunkInput, IdentitySource
from .validation import IntentError

if TYPE_CHECKING:
    from cognee.modules.chunking.models import DocumentChunk
    from cognee.modules.pipelines.models import PipelineContext

    from .publish import Publisher


@dataclass(frozen=True)
class Original:
    """An original document to register: its file and its Data ID."""

    path: Path
    data_id: UUID


@dataclass(frozen=True)
class Draft:
    """What a describer reads: the registered text, its native chunks and the
    dataset they belong to."""

    text: str
    chunks: list[DocumentChunk]
    dataset_id: UUID


class Semantics(Protocol):
    """How the lab Task writes and checks the semantic facts of a source,
    with the original's context. Captured fixture facts are the only
    extractor until step 6."""

    async def write(
        self,
        publisher: Publisher,
        source: IdentitySource,
        chunks: list[DocumentChunk],
        original: PipelineContext,
    ) -> None: ...

    async def verify(
        self,
        publisher: Publisher,
        source: IdentitySource,
        chunks: list[DocumentChunk],
        original: PipelineContext,
    ) -> None: ...


async def add(
    dataset_name: str,
    original: Original,
    *,
    describe: Callable[[Draft], IdentitySource],
    identity_path: Path,
    chunk_budget: int = 512,
) -> IdentitySource:
    """Register `original`, describe it from its in-memory native chunks
    (`describe`), and register the description at `identity_path`. The
    description is stamped as cognified at once; the original only once
    `cognify` has chunked it, so a plain `cognee.cognify` in between would
    still extract the original."""
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem

    from .registered import context_for, stamp
    from .native_chunks import chunk_text

    await cognee.add(
        DataItem(data=str(original.path), data_id=original.data_id),
        dataset_name=dataset_name,
        skip_connection_test=True,
    )
    ctx = await context_for(original.data_id)
    text = original.path.read_text()
    chunks = await chunk_text(text, ctx, chunk_budget)
    source = describe(Draft(text, chunks, ctx.dataset.id))
    identity_path.write_text(source.model_dump_json(indent=2) + "\n")
    await cognee.add(
        DataItem(data=str(identity_path), data_id=source.identity_data_id),
        dataset_name=dataset_name,
        skip_connection_test=True,
    )
    await stamp(source.identity_data_id, source.dataset_id)
    return source


def described_chunks(source) -> set[str]:
    return {
        str(item.chunk_id)
        for item in source.inputs.values()
        if isinstance(item, ChunkInput)
        and item.document_ref == source.original_input_ref
    }


async def chunk_budget_of(source, graph, default: int) -> int:
    """The budget to chunk a source's original with: the one its native
    chunks record, or `default` before its first `cognify` writes them."""
    from .captured_chunks import recorded_budget

    for chunk_id in described_chunks(source):
        if await graph.get_node(chunk_id) is not None:
            return await recorded_budget(source, graph)
    return default


def semantic_hooks(semantics, publisher, source, chunks, original) -> dict:
    """The publisher's `semantic_writer` and `verify_semantics` for
    `semantics` over the source's chunks, with the original's context; None
    for both when the source has no captured facts."""
    if semantics is None:
        return dict(semantic_writer=None, verify_semantics=None)
    return dict(
        semantic_writer=lambda: semantics.write(publisher, source, chunks, original),
        verify_semantics=lambda: semantics.verify(publisher, source, chunks, original),
    )


async def cognify(
    publisher,
    source: IdentitySource,
    *,
    semantics: Semantics | None,
    chunk_budget: int = 512,
    expected_revision: int | None = None,
    fault_stage: str | None = None,
    origin: str = "runtime",
):
    """Chunk the source's original with Cognee's standard Tasks and publish
    the source in a lab Task: a first publication when it has no row, a
    re-add at `expected_revision` when its row is forgotten, else a
    reconcile, which finishes a failed publication or verifies a current
    one. `semantics` is None for a source with no captured facts. A lab
    failure is recorded in the ledger, the run still completes, and the
    failure is raised after the run.

    One source per run: Cognee runs the items of one run concurrently, and
    a root's sources publish in order (`remember_in_order`)."""
    from cognee.modules.pipelines.operations.pipeline import run_pipeline
    from cognee.modules.pipelines.tasks.task import Task

    from .native_chunks import WHOLE_DOCUMENT, chunk_text, standard_tasks
    from .registered import context_for, read_texts, stamp

    if await publisher.records.row(source) is not None:
        # Chunking again would hide a copy deleted outside the lab.
        await publisher.refuse_natively_deleted(source)
    original = await context_for(source.inputs[source.original_input_ref].data_id)
    text = (await read_texts(source))[source.original_input_ref]
    budget = await chunk_budget_of(source, publisher.graph, chunk_budget)
    planned = await chunk_text(text, original, budget)
    if {str(c.id) for c in planned} != described_chunks(source):
        raise IntentError(
            "chunk_policy",
            "The native chunks of the original differ from the description's",
        )
    failures = []

    async def identity_publish(chunks, ctx=None):
        """Publish the source over its whole chunk set, with contexts of its
        own: the identity Data's for the identity writes and the original's
        for the facts, neither carrying the run's ID."""
        # Stamp once the native chunks are written, whatever the lab outcome:
        # a regular run writes no stamp of its own.
        await stamp(original.data_item.id, source.dataset_id)
        try:
            if {str(c.id) for c in chunks} != described_chunks(source):
                raise IntentError(
                    "chunk_mapping", "The lab Task did not receive the whole chunk set"
                )
            row = await publisher.records.row(source)
            if row is None:
                method = publisher.publish
            elif row.tombstone is not None:
                method = partial(publisher.readd, expected_revision=expected_revision)
            else:
                method = publisher.reconcile
            await method(
                source,
                texts=await read_texts(source),
                chunks={str(c.id): c for c in chunks},
                ctx=await context_for(source.identity_data_id),
                origin="test/fault_injection" if fault_stage else origin,
                fault_stage=fault_stage,
                **semantic_hooks(semantics, publisher, source, chunks, original),
            )
        except Exception as exc:
            failures.append(exc)
        return chunks

    async for _ in run_pipeline(
        tasks=[
            *standard_tasks(budget),
            Task(
                identity_publish,
                task_config={"batch_size": WHOLE_DOCUMENT},
                needs_llm=False,
            ),
        ],
        data=[original.data_item],
        datasets=[source.dataset_id],
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


async def remember(
    publisher,
    dataset_name: str,
    original: Original,
    *,
    describe: Callable[[Draft], IdentitySource],
    identity_path: Path,
    semantics: Semantics,
    chunk_budget: int = 512,
    fault_stage: str | None = None,
    origin: str = "runtime",
):
    """`add`, then `cognify` of the one new source. It never runs Cognee's
    improve step."""
    source = await add(
        dataset_name,
        original,
        describe=describe,
        identity_path=identity_path,
        chunk_budget=chunk_budget,
    )
    await cognify(
        publisher,
        source,
        semantics=semantics,
        chunk_budget=chunk_budget,
        fault_stage=fault_stage,
        origin=origin,
    )
    return source


AddSource = Callable[[Mapping[str, IdentitySource]], Awaitable[IdentitySource]]


async def remember_in_order(
    publisher,
    adds: Mapping[str, AddSource],
    *,
    semantics: Callable[[str], Semantics | None],
    chunk_budget: int = 512,
    fault: tuple[str, str] | None = None,
    origin: str = "runtime",
) -> dict[str, IdentitySource]:
    """Add, then `cognify`, each source of a root in publication order, by
    label. Each `add` registers its source and returns its description; it
    reads only the descriptions before it, which it is given. `semantics`
    gives a label's semantics, and `fault` a label and the stage at which
    its publication fails.

    A later source may cite an earlier one's published decisions, so a
    failure stops the run before the next source is added: no source after
    a failed one is registered, so none is left unstamped for a plain
    `cognee.cognify` to extract."""
    done: dict[str, IdentitySource] = {}
    for label, add in adds.items():
        done[label] = await add(dict(done))
        await cognify(
            publisher,
            done[label],
            semantics=semantics(label),
            chunk_budget=chunk_budget,
            fault_stage=fault[1] if fault and fault[0] == label else None,
            origin=origin,
        )
    return done
