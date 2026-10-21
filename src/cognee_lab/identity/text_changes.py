"""Bounded whole-document text replacement through native Cognee interfaces."""

from dataclasses import dataclass

from .models import ChunkInput, CorpusObjectInput, SourceTextInput
from .validation import IntentError, fresh_mention_id, map_chunks, text_digest


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


def admit_remap(
    old,
    source,
    before,
    after,
    occurrence_retention=None,
    occurrence_continuity=None,
    occurrence_regrouping=None,
):
    """The caller supplies reviewed decisions; this check does not infer identity.

    Default: a prefix insertion with exact uniform offsets. The optional
    retention manifest admits explicit reviewed occurrence removal instead;
    continuity admits additions with explicit old-to-new occurrence indices;
    regrouping admits splits and combinations with explicit old-to-new
    group/occurrence pairs. These modes do not match text or reconsider
    identity semantics.
    """
    modes = [
        m
        for m in (occurrence_retention, occurrence_continuity, occurrence_regrouping)
        if m is not None
    ]
    if len(modes) > 1:
        raise IntentError("not_admitted", "Select one occurrence transition mode")
    if not modes and (not before or not after.endswith(before) or after == before):
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
    if occurrence_regrouping is not None:
        return admit_occurrence_regrouping(
            old, source, before, after, occurrence_regrouping
        )
    if occurrence_continuity is not None:
        return admit_occurrence_addition(
            old, source, before, after, occurrence_continuity
        )
    if occurrence_retention is not None:
        return admit_occurrence_removal(
            old, source, before, after, occurrence_retention
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


def reviewed_decisions(values):
    """Decision content that must survive a reviewed change; attribution may differ."""
    return {
        k: {
            f: v
            for f, v in item.model_dump(mode="json").items()
            if f not in {"producer_ref", "input_refs", "explanation"}
        }
        for k, item in values.items()
    }


def admit_occurrence_removal(old, source, before, after, retention):
    """Validate explicit reviewed continuity; never infer matches from text.

    Every old group maps to ordered zero-based occurrence indices to retain.
    Empty lists explicitly retire groups. New positions are supplied in the
    intended source and checked against the new document, independently of
    identity judgment. This slice preserves the surviving assignment semantics.
    """
    if not before or not after or before == after:
        raise IntentError("not_admitted", "Occurrence removal requires changed text")
    if not isinstance(retention, dict) or set(retention) != set(old.mention_groups):
        raise IntentError("occurrence_changed", "Declare retention for every old group")
    kept = set()
    retired_entities = set()
    for key, previous in old.mention_groups.items():
        indices = retention[key]
        if (
            not isinstance(indices, list)
            or any(
                type(i) is not int or not 0 <= i < len(previous.occurrences)
                for i in indices
            )
            or indices != sorted(set(indices))
        ):
            raise IntentError(
                "occurrence_changed",
                "Retained indices must be unique, ordered old occurrence indices",
            )
        # Check the previous slices too: fingerprints alone do not validate spans.
        for o in previous.occurrences:
            if before[o.start : o.end] != o.text:
                raise IntentError(
                    "occurrence_changed", "Previous occurrence does not match text"
                )
        if not indices:
            retired_entities.add(previous.entity_id)
            continue
        kept.add(key)
        current = source.mention_groups.get(key)
        if (
            current is None
            or current.entity_id != previous.entity_id
            or current.document_ref != previous.document_ref
            or [o.text for o in current.occurrences]
            != [previous.occurrences[i].text for i in indices]
            or any(after[o.start : o.end] != o.text for o in current.occurrences)
        ):
            raise IntentError(
                "occurrence_changed",
                "Supply exact reviewed surviving occurrences with stable group UUIDs",
            )
    if set(source.mention_groups) != kept:
        raise IntentError(
            "occurrence_changed", "Only explicitly continuing groups may remain"
        )
    if not any(
        len(retention[k]) < len(g.occurrences) for k, g in old.mention_groups.items()
    ):
        raise IntentError(
            "not_admitted", "This reviewed slice removes at least one occurrence"
        )

    expected_resolutions = {
        k: r for k, r in old.mention_resolutions.items() if r.group_ref in kept
    }
    if (
        reviewed_decisions(source.mention_resolutions)
        != reviewed_decisions(expected_resolutions)
        or reviewed_decisions(source.variant_assignments)
        != reviewed_decisions(old.variant_assignments)
        or source.entity_constructions
        != {
            k: v
            for k, v in old.entity_constructions.items()
            if k not in retired_entities
        }
        or any(
            v.applicability.kind == "text_spans"
            for v in source.variant_assignments.values()
        )
    ):
        raise IntentError(
            "not_admitted",
            "Preserve continuing decisions and recipes; retire only empty-group declarations",
        )
    return None  # An arbitrary reviewed removal has no single global offset shift.


def admit_occurrence_addition(old, source, before, after, continuity):
    """Map every old occurrence to its reviewed index in the new group.

    Unmapped new indices are additions. No removals, regrouping, retargeting,
    recipe changes or new reusable identities are admitted by this mode.
    Positions and identity judgments are supplied, never inferred from text.
    """
    if not before or not after or before == after:
        raise IntentError("not_admitted", "Occurrence addition requires changed text")
    if not isinstance(continuity, dict) or set(continuity) != set(old.mention_groups):
        raise IntentError(
            "occurrence_changed", "Declare continuity for every old group"
        )
    if not set(old.mention_groups) <= set(source.mention_groups):
        raise IntentError("occurrence_changed", "Addition cannot retire old groups")
    added = False
    for key, previous in old.mention_groups.items():
        current = source.mention_groups[key]
        indices = continuity[key]
        if (
            not isinstance(indices, list)
            or len(indices) != len(previous.occurrences)
            or any(
                type(i) is not int or not 0 <= i < len(current.occurrences)
                for i in indices
            )
            or indices != sorted(set(indices))
            or current.entity_id != previous.entity_id
            or current.document_ref != previous.document_ref
        ):
            raise IntentError(
                "occurrence_changed",
                "Preserve all old occurrences and group UUIDs with ordered new indices",
            )
        for occurrence, index in zip(previous.occurrences, indices, strict=True):
            if (
                before[occurrence.start : occurrence.end] != occurrence.text
                or current.occurrences[index].text != occurrence.text
            ):
                raise IntentError(
                    "occurrence_changed",
                    "Continuing occurrence text differs from reviewed mapping",
                )
        added |= len(current.occurrences) > len(previous.occurrences)
    new_groups = set(source.mention_groups) - set(old.mention_groups)
    for key in new_groups:
        if source.mention_groups[key].entity_id in old.entity_constructions:
            raise IntentError(
                "incompatible_group", "A new group requires a fresh Entity UUID"
            )
    for group in source.mention_groups.values():
        if any(after[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed",
                "New occurrence does not match its exact document slice",
            )

    continuing = {
        k: r
        for k, r in source.mention_resolutions.items()
        if r.group_ref not in new_groups
    }
    new_resolutions = {
        k: r for k, r in source.mention_resolutions.items() if r.group_ref in new_groups
    }
    expected_recipes = dict(old.entity_constructions)
    for key in new_groups:
        eid = source.mention_groups[key].entity_id
        expected_recipes[eid] = source.entity_constructions[eid]
    if (
        reviewed_decisions(continuing) != reviewed_decisions(old.mention_resolutions)
        or reviewed_decisions(source.variant_assignments)
        != reviewed_decisions(old.variant_assignments)
        or set(new_resolutions)
        & (set(old.mention_resolutions) | set(old.variant_assignments))
        or {r.group_ref for r in new_resolutions.values()} != new_groups
        or source.entity_constructions != expected_recipes
        or any(
            v.applicability.kind == "text_spans"
            for v in source.variant_assignments.values()
        )
    ):
        raise IntentError(
            "not_admitted",
            "Preserve existing decisions and recipes; declare each new group's resolution",
        )
    if not added and not new_groups:
        raise IntentError(
            "not_admitted", "This reviewed slice adds at least one occurrence"
        )
    return None


@dataclass(frozen=True)
class Regrouping:
    """An explicit old-to-new occurrence map, classified by group key."""

    images: dict[str, list[tuple[str, int]]]
    continuing: frozenset[str]
    retired: frozenset[str]
    fresh: frozenset[str]


def classify_regrouping(old, source, regrouping):
    """Partition old and new group keys from the reviewed occurrence map.

    A group continues only when every old occurrence lands, in order, on its
    own key and nothing else lands there. Every other old group retires and
    every other new group is fresh.
    """
    if not isinstance(regrouping, dict) or set(regrouping) != set(old.mention_groups):
        raise IntentError(
            "occurrence_changed", "Declare regrouping for every old group"
        )
    images = {}
    for key, previous in old.mention_groups.items():
        pairs = regrouping[key]
        if (
            not isinstance(pairs, list)
            or len(pairs) != len(previous.occurrences)
            or any(
                not isinstance(p, list)
                or len(p) != 2
                or not isinstance(p[0], str)
                or type(p[1]) is not int
                for p in pairs
            )
        ):
            raise IntentError(
                "occurrence_changed",
                "Map each old occurrence, in order, to one [group, index] pair",
            )
        images[key] = [tuple(p) for p in pairs]
    targets = [t for pairs in images.values() for t in pairs]
    current = {
        (key, i)
        for key, group in source.mention_groups.items()
        for i in range(len(group.occurrences))
    }
    if len(targets) != len(set(targets)) or set(targets) != current:
        raise IntentError(
            "occurrence_changed",
            "Every old occurrence maps once and every new occurrence has one origin",
        )
    continuing = frozenset(
        key
        for key, pairs in images.items()
        if key in source.mention_groups
        and pairs == [(key, i) for i in range(len(pairs))]
        and len(source.mention_groups[key].occurrences) == len(pairs)
    )
    return Regrouping(
        images=images,
        continuing=continuing,
        retired=frozenset(old.mention_groups) - continuing,
        fresh=frozenset(source.mention_groups) - continuing,
    )


def admit_occurrence_regrouping(old, source, before, after, regrouping):
    """Admit a reviewed split or combination with fresh resulting groups.

    Facts are regenerated for the new groups, never transferred. Positions,
    groups and resolutions are supplied, never inferred from text.
    """
    if not before or not after or before == after:
        raise IntentError("not_admitted", "Occurrence regrouping requires changed text")
    plan = classify_regrouping(old, source, regrouping)
    if not plan.retired:
        raise IntentError(
            "not_admitted", "This reviewed slice regroups at least one group"
        )
    for key, previous in old.mention_groups.items():
        for occurrence, (target, index) in zip(
            previous.occurrences, plan.images[key], strict=True
        ):
            if (
                before[occurrence.start : occurrence.end] != occurrence.text
                or source.mention_groups[target].occurrences[index].text
                != occurrence.text
            ):
                raise IntentError(
                    "occurrence_changed",
                    "Regrouped occurrence text differs from reviewed mapping",
                )
    for group in source.mention_groups.values():
        if any(after[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed",
                "New occurrence does not match its exact document slice",
            )
    for key in plan.continuing:
        previous, current = old.mention_groups[key], source.mention_groups[key]
        if (current.entity_id, current.document_ref) != (
            previous.entity_id,
            previous.document_ref,
        ):
            raise IntentError(
                "occurrence_changed", "A continuing group keeps its Entity UUID"
            )
    for key in plan.fresh:
        entity_id = source.mention_groups[key].entity_id
        if entity_id in old.entity_constructions:
            raise IntentError(
                "incompatible_group", "A fresh group requires a fresh Entity UUID"
            )
        # Retired UUIDs are not in old, so only a derived ID keeps one from returning.
        if entity_id != fresh_mention_id(old.identity_data_id, key):
            raise IntentError(
                "incompatible_group",
                "A fresh group's Entity UUID derives from its source and group key",
            )
    kept = {
        k: r
        for k, r in source.mention_resolutions.items()
        if r.group_ref in plan.continuing
    }
    declared = {
        k: r for k, r in source.mention_resolutions.items() if r.group_ref in plan.fresh
    }
    retired_entities = {old.mention_groups[k].entity_id for k in plan.retired}
    expected_recipes = {
        eid: recipe
        for eid, recipe in old.entity_constructions.items()
        if eid not in retired_entities
    }
    for key in plan.fresh:
        eid = source.mention_groups[key].entity_id
        expected_recipes[eid] = source.entity_constructions[eid]
    if (
        reviewed_decisions(kept)
        != reviewed_decisions(
            {
                k: r
                for k, r in old.mention_resolutions.items()
                if r.group_ref in plan.continuing
            }
        )
        or reviewed_decisions(source.variant_assignments)
        != reviewed_decisions(old.variant_assignments)
        or set(declared) & (set(old.mention_resolutions) | set(old.variant_assignments))
        or len(declared) != len(plan.fresh)
        or {r.group_ref for r in declared.values()} != plan.fresh
        or source.entity_constructions != expected_recipes
        or any(
            v.applicability.kind == "text_spans"
            for v in source.variant_assignments.values()
        )
    ):
        raise IntentError(
            "not_admitted",
            "Retire the old groups' decisions and recipes; declare one resolution per fresh group",
        )
    return plan


@dataclass(frozen=True)
class TextChange:
    previous_text: str
    text: str
    chunk_budget: int = 512
    occurrence_retention: dict[str, list[int]] | None = None
    occurrence_continuity: dict[str, list[int]] | None = None
    occurrence_regrouping: dict[str, list[list[str | int]]] | None = None

    async def preflight(self, publisher, old, source, texts, chunks, ctx, *, retry):
        from cognee.infrastructure.databases.provenance.markers import (
            stores_provenance_in_graph,
        )
        from cognee.infrastructure.databases.unified import get_unified_engine

        admitted = admit_remap(
            old,
            source,
            self.previous_text,
            self.text,
            self.occurrence_retention,
            self.occurrence_continuity,
            self.occurrence_regrouping,
        )
        if self.occurrence_regrouping is not None:
            fresh = admitted.fresh
        elif self.occurrence_continuity is not None:
            fresh = set(source.mention_groups) - set(old.mention_groups)
        else:
            fresh = set()
        if not retry:
            for key in fresh:
                if (
                    await publisher.graph.get_node(
                        str(source.mention_groups[key].entity_id)
                    )
                    is not None
                ):
                    raise IntentError(
                        "incompatible_group",
                        "New mention Entity UUID already exists in the graph",
                    )
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
