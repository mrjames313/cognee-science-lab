"""Bounded whole-document text replacement through native Cognee interfaces."""

from dataclasses import dataclass, fields

from .admission import OccurrenceMap, identity_map, occurrence, parse_occurrence_map
from .models import ChunkInput
from .validation import IntentError, map_chunks


async def reject_sole_owned_readers(publisher, old, source):
    """A text edit does not wait for the sources that read the edited text:
    the edit withholds their affected decisions (withholding.py). One case
    stays refused. The edit drops a reusable recipe that only this source
    owns, so the Entity leaves the graph, while another source reads that
    Entity as a corpus object."""
    from uuid import UUID

    from .validation import reusable_recipes
    from .retirement import dependents, owned_by

    dropped = sorted(
        str(e) for e in set(reusable_recipes(old)) - set(reusable_recipes(source))
    )
    if not dropped:
        return
    owners = await publisher.graph.get_node_delete_data(dropped)
    own = owned_by(old, document=True)
    sole = frozenset(
        UUID(key)
        for key, node in owners.items()
        if all(own(ref) for ref in node.source_ref_keys)
    )
    found = [
        d
        for d in dependents(old, await publisher.records.rows(), sole)
        if d["kind"] == "corpus_object"
    ]
    if found:
        raise IntentError(
            "dependent_source",
            "Another saved identity source reads an Entity that only the edited source owns and the edit drops; reconsider that source first",
            details=dict(dependents=found),
        )


async def reject_unsafe_cascades(publisher, source):
    """Refuse an ownership inconsistency before native endpoint deletion."""
    from cognee.infrastructure.databases.provenance import parse_source_ref_key
    from .native import edge_metadata, fact_neighborhood

    doc = source.inputs[source.original_input_ref]

    def selected(ref):
        try:
            parsed = parse_source_ref_key(ref)
            return (
                parsed.dataset_id == source.dataset_id and parsed.data_id == doc.data_id
            )
        except ValueError:
            return False

    refs = await publisher.graph.find_node_source_refs_by_dataset(
        str(source.dataset_id)
    )
    for node_id, owners in refs.items():
        if not owners or not all(selected(ref) for ref in owners):
            continue
        edges, limited = await fact_neighborhood(publisher.graph, node_id, 1000)
        if limited:
            raise IntentError(
                "removal_check_limited",
                "Endpoint removal safety check reached its neighborhood limit",
            )
        for a, b, relation, _ in edges:
            edge = await edge_metadata(publisher.graph, a, b, relation)
            if edge and any(not selected(ref) for ref in edge.source_ref_keys):
                raise IntentError(
                    "ownership_gap",
                    "Removing an unretained endpoint would cascade into another owner's edge; repair native ownership first",
                )


async def original_context(source, ctx):
    from cognee.modules.data.methods.get_data import get_data
    from cognee.modules.pipelines.models import PipelineContext

    doc = source.inputs[source.original_input_ref]
    data = await get_data(ctx.user.id, doc.data_id, source.dataset_id)
    if data is None:
        raise IntentError("source_missing", "Original Data item is missing")
    return PipelineContext(
        user=ctx.user,
        dataset=ctx.dataset,
        data_item=data,
        pipeline_name="identity_text_replacement",
    )


async def read_original(source, ctx):
    from cognee.infrastructure.files.utils.open_data_file import open_data_file
    from cognee.modules.ingestion.data_types import TextData

    original = await original_context(source, ctx)
    async with open_data_file(
        original.data_item.raw_data_location, mode="r", encoding="utf-8"
    ) as f:
        text = f.read()
    if (
        TextData(text).get_metadata()["content_hash"]
        != original.data_item.raw_content_hash
    ):
        raise IntentError(
            "source_changed", "Original text and native raw hash disagree"
        )
    return text


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


@dataclass(frozen=True)
class TextChange:
    previous_text: str
    text: str
    occurrence_map: OccurrenceMap
    chunk_budget: int = 512

    def __post_init__(self):
        parsed = parse_occurrence_map(self.occurrence_map)
        object.__setattr__(self, "occurrence_map", parsed)

    @classmethod
    def from_plan(cls, plan):
        """Read the text change a plan saved. Only plans with the general
        `occurrence_map` are read; the roots that hold older plans are history."""
        saved = plan["text_change"]
        if "occurrence_map" not in saved or set(saved) - {f.name for f in fields(cls)}:
            raise IntentError(
                "recovery_plan",
                "Saved text change predates the general occurrence map; this root is history and its plan cannot be resumed",
            )
        return cls(**saved)

    def prefix_shift(self, old, source):
        """The offset every occurrence moved by, when the text only gained a
        prefix and every occurrence kept its group, index and relative place."""
        delta = len(self.text) - len(self.previous_text)
        if not self.text.endswith(self.previous_text) or self.occurrence_map != (
            identity_map(source)
        ):
            return None
        refs = [r for refs in self.occurrence_map.values() for r in refs]
        if any(
            occurrence(source, r).start != occurrence(old, r).start + delta
            for r in refs
        ):
            return None
        return delta

    async def preflight(self, publisher, old, source, texts, chunks, ctx, *, retry):
        """Text, chunk and capability checks. `replace` admits the change
        before calling this."""
        from cognee.infrastructure.databases.provenance.markers import (
            stores_provenance_in_graph,
        )
        from cognee.infrastructure.databases.unified import get_unified_engine

        if not 1 <= self.chunk_budget <= 4096:
            raise IntentError("not_admitted", "Invalid captured chunk budget")
        # Other documents' texts come from read_texts; only this one changes.
        if texts.get(source.original_input_ref) != self.text:
            raise IntentError(
                "source_changed", "Supplied text differs from saved transition"
            )
        unified = await get_unified_engine()
        if (
            not unified.supports_graph_provenance_delete()
            or not await stores_provenance_in_graph(publisher.graph)
        ):
            raise IntentError(
                "unsupported_capability",
                "Text replacement requires native graph provenance deletion",
            )
        actual = await read_original(old, ctx)
        if actual not in (
            (self.previous_text, self.text) if retry else (self.previous_text,)
        ):
            raise IntentError(
                "source_changed",
                "Original text matches neither admitted transition state",
            )
        original = await original_context(old, ctx)
        projected = await chunk_text(self.text, original, self.chunk_budget)
        signature = lambda values: [
            (str(c.id), c.chunk_index, c.text)
            for c in sorted(values, key=lambda c: c.chunk_index)
        ]
        if signature(projected) != signature(chunks.values()):
            raise IntentError(
                "chunk_mapping", "Prepared chunks differ from native rechunking"
            )
        declared = {
            str(i.chunk_id) for i in source.inputs.values() if isinstance(i, ChunkInput)
        }
        if declared != set(chunks):
            raise IntentError(
                "chunk_mapping", "Describe must supply the complete new chunk mapping"
            )
        await reject_sole_owned_readers(publisher, old, source)
        await reject_unsafe_cascades(publisher, old)
        if not retry:
            old_chunks = await chunk_text(
                self.previous_text, original, self.chunk_budget
            )
            await publisher.preflight(
                old,
                {old.original_input_ref: self.previous_text},
                {str(c.id): c for c in old_chunks},
                ctx,
            )

    async def apply(self, publisher, old, source, chunks, ctx, boundary):
        from cognee import forget
        from cognee.tasks.storage import add_data_points
        from .registered import stamp, write_text

        # Repeat preconditions under the durable project writer reservation.
        await reject_sole_owned_readers(publisher, old, source)
        await reject_unsafe_cascades(publisher, old)
        actual = await read_original(old, ctx)
        if actual not in (self.previous_text, self.text):
            raise IntentError(
                "source_changed", "Original text changed during replacement"
            )
        doc = old.inputs[old.original_input_ref]
        await forget(
            data_id=doc.data_id,
            dataset_id=old.dataset_id,
            user=ctx.user,
            memory_only=True,
        )
        # write_text stamps again; this covers a failure before it.
        await stamp(doc.data_id, old.dataset_id)
        await boundary("text_removed")
        original = await original_context(old, ctx)
        await write_text(self.text, original, doc.data_id)
        if await read_original(source, ctx) != self.text:
            raise IntentError(
                "source_changed", "Registered original differs from intended text"
            )
        await boundary("text_registered")
        # Recreate the native Document/DocumentChunk structures and their indexes.
        # The supplied chunks were obtained from the native chunker before writes.
        rebuilt = await chunk_text(self.text, original, self.chunk_budget)
        if {str(c.id): c.text for c in rebuilt} != {
            k: c.text for k, c in chunks.items()
        }:
            raise IntentError("chunk_mapping", "Native chunks changed after ingestion")
        chunks.clear()
        chunks.update({str(c.id): c for c in rebuilt})
        await add_data_points(rebuilt, ctx=original)
        await boundary("text_chunks")

    async def verify(self, publisher, old, source, chunks):
        old_ids = {
            str(i.chunk_id) for i in old.inputs.values() if isinstance(i, ChunkInput)
        }
        for chunk_id in old_ids - set(chunks):
            if await publisher.graph.get_node(chunk_id) is not None:
                raise IntentError("stale_chunk", "Retired chunk remains in graph")
            if await publisher.vector.retrieve("DocumentChunk_text", [chunk_id]):
                raise IntentError(
                    "stale_chunk", "Retired chunk remains in vector index"
                )
        mapping = map_chunks(self.text, list(chunks.values()))
        for key, item in source.inputs.items():
            if isinstance(item, ChunkInput) and mapping[str(item.chunk_id)] != (
                item.start,
                item.end,
            ):
                raise IntentError(
                    "chunk_mapping", "New chunk mapping failed verification"
                )
