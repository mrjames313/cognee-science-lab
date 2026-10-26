"""The native chunks of an original document, built with Cognee's own
chunker: in memory before any write (`chunk_text`), or written by Cognee's
standard Tasks (`standard_tasks`, `build_chunks`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cognee.modules.chunking.models import DocumentChunk
    from cognee.modules.pipelines.models import PipelineContext

# Cognee batches the chunks it hands each Task. One batch larger than any
# document gives the lab Task the document's whole chunk set at once.
WHOLE_DOCUMENT = 1_000_000


async def chunk_text(text, ctx, budget=512):
    """Run the native chunker in memory before any destructive write."""
    from cognee.modules.chunking.TextChunker import TextChunker
    from cognee.modules.data.processing.document_types import TextDocument

    async def get_text():
        yield text

    doc = TextDocument(
        id=ctx.data_item.id,
        name=ctx.data_item.name,
        raw_data_location=ctx.data_item.raw_data_location,
        external_metadata=None,
    )
    return [
        c
        async for c in TextChunker(doc, get_text=get_text, max_chunk_size=budget).read()
    ]


def standard_tasks(budget: int) -> list:
    """Cognee's standard Tasks that build a document and its chunks:
    `classify_documents`, `extract_chunks_from_documents` and
    `add_data_points`, the last over the whole chunk set at once."""
    from cognee.modules.pipelines.tasks.task import Task
    from cognee.tasks.documents import classify_documents, extract_chunks_from_documents
    from cognee.tasks.storage import add_data_points

    return [
        Task(classify_documents, needs_llm=False),
        Task(extract_chunks_from_documents, max_chunk_size=budget, needs_llm=False),
        Task(
            add_data_points,
            task_config={"batch_size": WHOLE_DOCUMENT},
            needs_llm=False,
        ),
    ]


async def build_chunks(original: PipelineContext, budget: int) -> list[DocumentChunk]:
    """Run the standard Tasks over the registered original, outside any
    pipeline run, with `original`, the lab's context. It carries no run ID,
    so a rollback or a startup recovery of the run that called this never
    finds the chunks, and a resumed edit need not chunk again."""
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base

    return [
        chunk
        async for batch in run_tasks_base(
            standard_tasks(budget), [original.data_item], original.user, original
        )
        for chunk in batch
    ]
