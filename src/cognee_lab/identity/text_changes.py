"""Bounded whole-document text replacement through native Cognee interfaces."""

from dataclasses import dataclass

from .models import ChunkInput, CorpusObjectInput, SourceTextInput
from .validation import IntentError, map_chunks, text_digest


def reject_dependents(old, rows):
    from .models import IdentitySource

    doc = old.inputs[old.original_input_ref]
    for row in rows:
        if (row["source"], row["dataset"]) == (
            str(old.identity_data_id),
            str(old.dataset_id),
        ):
            continue
        if row["state"] == "withdrawn":
            continue
        other = IdentitySource.model_validate_json(row["description"])
        if any(
            isinstance(i, SourceTextInput) and i.data_id == doc.data_id
            for i in other.inputs.values()
        ):
            raise IntentError(
                "dependent_source",
                "Another saved identity source depends on the edited text; reconsideration is required",
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


def admit_remap(old, source, before, after):
    """The caller supplies reviewed decisions; this check does not infer identity.

    First slice: a prefix insertion, stable groups and occurrence texts, all
    offsets shifted by the exact Unicode prefix length. Arbitrary edits and
    grouping changes require a later Describe/reconsideration implementation.
    """
    if not before or not after.endswith(before) or after == before:
        raise IntentError(
            "not_admitted", "Text slice requires a nonempty prefix insertion"
        )
    delta = len(after) - len(before)
    key = old.original_input_ref
    if (source.dataset_id, source.identity_data_id, source.original_input_ref) != (
        old.dataset_id,
        old.identity_data_id,
        key,
    ):
        raise IntentError(
            "not_admitted", "Text replacement must preserve source identity"
        )
    for value in [old, source]:
        if any(
            not isinstance(i, (SourceTextInput, ChunkInput, CorpusObjectInput))
            for i in value.inputs.values()
        ):
            raise IntentError(
                "not_admitted",
                "This text slice does not remap span/record dependencies",
            )
        if [k for k, i in value.inputs.items() if isinstance(i, SourceTextInput)] != [
            key
        ]:
            raise IntentError(
                "not_admitted", "Text slice replaces exactly one original"
            )
    a, b = old.inputs[key], source.inputs[key]
    if a.data_id != b.data_id or a.dataset_id != b.dataset_id:
        raise IntentError("not_admitted", "Original Data identity must remain stable")
    if text_digest(before) != a.text_sha256 or text_digest(after) != b.text_sha256:
        raise IntentError(
            "source_changed", "Saved text transition fingerprints disagree"
        )
    if set(old.mention_groups) != set(source.mention_groups):
        raise IntentError("not_admitted", "This slice preserves group membership")
    for name, previous in old.mention_groups.items():
        current = source.mention_groups[name]
        expected = [
            dict(start=o.start + delta, end=o.end + delta, text=o.text)
            for o in previous.occurrences
        ]
        if (
            current.entity_id != previous.entity_id
            or current.document_ref != previous.document_ref
            or [o.model_dump() for o in current.occurrences] != expected
        ):
            raise IntentError(
                "occurrence_changed",
                "Supply exact shifted occurrences with stable group UUIDs",
            )

    # Reusing a local fact is admitted only for unchanged assignment semantics.
    # Captured producer attribution may change after a fresh review of context.
    def decisions(value):
        return {
            name: {
                k: v
                for k, v in item.model_dump(mode="json").items()
                if k not in {"producer_ref", "input_refs", "explanation"}
            }
            for name, item in {
                **value.mention_resolutions,
                **value.variant_assignments,
            }.items()
        }

    if (
        decisions(old) != decisions(source)
        or old.entity_constructions != source.entity_constructions
    ):
        raise IntentError(
            "not_admitted",
            "Text slice requires unchanged reviewed assignments and recipes",
        )
    if any(
        v.applicability.kind == "text_spans"
        for v in source.variant_assignments.values()
    ):
        raise IntentError(
            "not_admitted", "Span-scoped variants require explicit scope remapping"
        )
    return delta


@dataclass(frozen=True)
class TextChange:
    previous_text: str
    text: str
    chunk_budget: int = 512

    async def preflight(self, publisher, old, source, texts, chunks, ctx, *, retry):
        from cognee.infrastructure.databases.provenance.markers import (
            stores_provenance_in_graph,
        )
        from cognee.infrastructure.databases.unified import get_unified_engine

        admit_remap(old, source, self.previous_text, self.text)
        if not 1 <= self.chunk_budget <= 4096:
            raise IntentError("not_admitted", "Invalid captured chunk budget")
        if texts != {source.original_input_ref: self.text}:
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
        # Refuse dependencies we cannot yet reconsider; do not silently invalidate them.
        reject_dependents(old, await publisher.records.rows())
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
        from .registered import write_text

        # Repeat preconditions under the durable project writer reservation.
        reject_dependents(old, await publisher.records.rows())
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
