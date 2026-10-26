"""The lab's add, cognify and remember over Cognee's own pipeline.

`add` registers an original document and its identity description. `cognify`
runs Cognee's standard Tasks under the pipeline name `cognify_pipeline`, so
Cognee builds the document and its chunks, then one lab Task publishes the
description once per document over the whole chunk set. `remember` is `add`
then `cognify`.

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

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .models import ChunkInput, IdentitySource
from .validation import IntentError

# Cognee batches the chunks it hands each Task. One batch larger than any
# document gives the lab Task the document's whole chunk set at once.
WHOLE_DOCUMENT = 1_000_000


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
    chunks: list
    dataset_id: UUID


@dataclass(frozen=True)
class Semantics:
    """How the lab Task writes and checks the semantic facts of a source:
    `write(publisher, source, chunks, original_ctx)` and `verify(...)` with
    the same arguments. Captured fixture facts are the only extractor until
    step 6."""

    write: Callable[..., Awaitable[None]]
    verify: Callable[..., Awaitable[None]]


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

    from .fixture import context_for
    from .registered import stamp
    from .text_changes import chunk_text

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
    """The budget to chunk a saved source's original with: the one its
    native chunks record, or `default` when they are gone (a failed first
    publication, whose chunks `cognify` writes again)."""
    from .captured_chunks import recorded_budget

    for chunk_id in described_chunks(source):
        if await graph.get_node(chunk_id) is not None:
            return await recorded_budget(source, graph)
    return default


async def cognify(
    publisher,
    sources: Sequence[IdentitySource],
    *,
    semantics: Semantics,
    chunk_budget: int = 512,
    fault_stage: str | None = None,
    origin: str = "runtime",
):
    """Chunk each source's original with Cognee's standard Tasks and publish
    the source in a lab Task: a first publication when it has no row, else a
    reconcile, which finishes a failed publication or verifies a current
    one. A lab failure is recorded in the ledger, the run still completes,
    and the failure is raised after the run."""
    from cognee.modules.pipelines.operations.pipeline import run_pipeline
    from cognee.modules.pipelines.tasks.task import Task
    from cognee.tasks.documents import classify_documents, extract_chunks_from_documents
    from cognee.tasks.storage import add_data_points

    from .fixture import context_for
    from .registered import read_texts, stamp
    from .text_changes import chunk_text

    if len({s.dataset_id for s in sources}) != 1:
        raise IntentError("dataset_scope", "cognify takes sources of one dataset")
    by_original, budgets = {}, set()
    for source in sources:
        data_id = source.inputs[source.original_input_ref].data_id
        if await publisher.records.row(source) is not None:
            # Chunking again would hide a copy deleted outside the lab.
            await publisher.refuse_natively_deleted(source)
        original = await context_for(data_id)
        text = (await read_texts(source))[source.original_input_ref]
        budget = await chunk_budget_of(source, publisher.graph, chunk_budget)
        planned = await chunk_text(text, original, budget)
        if {str(c.id) for c in planned} != described_chunks(source):
            raise IntentError(
                "chunk_policy",
                "The native chunks of the original differ from the description's",
            )
        by_original[data_id] = (source, original)
        budgets.add(budget)
    if len(budgets) != 1:
        raise IntentError("chunk_policy", "cognify takes one chunk budget per run")
    failures = []

    async def identity_publish(chunks, ctx=None):
        source, original = by_original[ctx.data_item.id]
        # Stamp once the native chunks are written, whatever the lab outcome:
        # a regular run writes no stamp of its own.
        await stamp(original.data_item.id, source.dataset_id)
        try:
            await publish_one(
                publisher, source, chunks, original, semantics, fault_stage, origin
            )
        except Exception as exc:
            failures.append(exc)
        return chunks

    async for _ in run_pipeline(
        tasks=[
            Task(classify_documents, needs_llm=False),
            Task(
                extract_chunks_from_documents,
                max_chunk_size=budgets.pop(),
                needs_llm=False,
            ),
            Task(
                add_data_points,
                task_config={"batch_size": WHOLE_DOCUMENT},
                needs_llm=False,
            ),
            Task(
                identity_publish,
                task_config={"batch_size": WHOLE_DOCUMENT},
                needs_llm=False,
            ),
        ],
        data=[original.data_item for _, original in by_original.values()],
        datasets=[sources[0].dataset_id],
        user=next(iter(by_original.values()))[1].user,
        pipeline_name="cognify_pipeline",
        incremental_loading=False,
        rollback_handler=None,
        skip_connection_test=True,
    ):
        pass
    if failures:
        raise failures[0]


async def publish_one(
    publisher, source, chunks, original, semantics, fault_stage, origin
):
    """The lab Task's work on one document, with contexts of its own: the
    identity Data's for the identity writes and the original's for the
    facts, neither carrying the run's ID."""
    from .fixture import context_for
    from .registered import read_texts

    if {str(c.id) for c in chunks} != described_chunks(source):
        raise IntentError(
            "chunk_mapping", "The lab Task did not receive the whole chunk set"
        )
    row = await publisher.records.row(source)
    method = publisher.publish if row is None else publisher.reconcile
    await method(
        source,
        texts=await read_texts(source),
        chunks={str(c.id): c for c in chunks},
        ctx=await context_for(source.identity_data_id),
        origin="test/fault_injection" if fault_stage else origin,
        fault_stage=fault_stage,
        semantic_writer=lambda: semantics.write(publisher, source, chunks, original),
        verify_semantics=lambda: semantics.verify(publisher, source, chunks, original),
    )


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
        [source],
        semantics=semantics,
        chunk_budget=chunk_budget,
        fault_stage=fault_stage,
        origin=origin,
    )
    return source
