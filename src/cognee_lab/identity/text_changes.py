"""Bounded whole-document text replacement through native Cognee interfaces."""

from dataclasses import dataclass

from .admission import (
    OccurrenceMap,
    admit,
    check_absent_from_graph,
    identity_map,
    occurrence,
    parse_occurrence_map,
)
from .models import ChunkInput, IdentitySource, SourceTextInput
from .validation import IntentError, map_chunks


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


def indices(reviewed, groups, valid):
    """A saved old-mode map: every old group, each with a list of valid ints."""
    if (
        not isinstance(reviewed, dict)
        or set(reviewed) != set(groups)
        or not all(
            isinstance(v, list)
            and all(type(i) is int for i in v)
            and valid(v, groups[k])
            for k, v in reviewed.items()
        )
    ):
        raise IntentError("recovery_plan", "Saved occurrence map is malformed")
    return reviewed


def from_retention(reviewed, groups):
    kept = indices(
        reviewed,
        groups,
        lambda v, n: v == sorted(set(v)) and all(0 <= i < n for i in v),
    )
    return {
        k: [[k, kept[k].index(i)] if i in kept[k] else None for i in range(n)]
        for k, n in groups.items()
    }


def from_continuity(reviewed, groups):
    moved = indices(
        reviewed, groups, lambda v, n: len(v) == n and all(i >= 0 for i in v)
    )
    return {k: [[k, j] for j in moved[k]] for k in groups}


def from_regrouping(reviewed, groups):
    if not isinstance(reviewed, dict) or set(reviewed) != set(groups):
        raise IntentError("recovery_plan", "Saved occurrence map is malformed")
    return reviewed


# Plans saved before 2026-10-21 hold at most one of these old-mode maps, or
# none for a prefix shift. Delete this reader once no kept root holds a plan
# without `occurrence_map`.
LEGACY_READERS = {
    "occurrence_retention": from_retention,
    "occurrence_continuity": from_continuity,
    "occurrence_regrouping": from_regrouping,
}


def legacy_occurrence_map(old, saved):
    """The general map that states the same edit as a saved old-mode map."""
    chosen = [f for f in LEGACY_READERS if saved.get(f) is not None]
    if len(chosen) > 1:
        raise IntentError("recovery_plan", "Saved plan selects more than one mode")
    if not chosen:
        return identity_map(old)
    groups = {k: len(g.occurrences) for k, g in old.mention_groups.items()}
    raw = LEGACY_READERS[chosen[0]](saved[chosen[0]], groups)
    try:
        return parse_occurrence_map(raw)
    except IntentError:
        raise IntentError("recovery_plan", "Saved occurrence map is malformed")


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
        """Read the text change a plan saved, converting an old-mode map
        against the plan's previous description."""
        saved = dict(plan["text_change"])
        legacy = {f: saved.pop(f) for f in LEGACY_READERS if f in saved}
        if "occurrence_map" not in saved:
            old = IdentitySource.model_validate_json(plan["previous_description"])
            saved["occurrence_map"] = legacy_occurrence_map(old, legacy)
        elif any(v is not None for v in legacy.values()):
            raise IntentError("recovery_plan", "Saved plan mixes map formats")
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
        from cognee.infrastructure.databases.provenance.markers import (
            stores_provenance_in_graph,
        )
        from cognee.infrastructure.databases.unified import get_unified_engine

        fate = admit(
            old,
            source,
            self.previous_text,
            self.text,
            self.occurrence_map,
            first_attempt=not retry,
        )
        if not retry:
            await check_absent_from_graph(publisher.graph, old, source, fate)
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
