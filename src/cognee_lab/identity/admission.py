"""Admission of a reviewed replacement: what the new description may claim.

One map states the edit. For each old occurrence, in order, it gives the new
occurrence it became, or None if it was removed; a new occurrence that nothing
maps to is an addition. The rules are stated over occurrences and groups, never
over kinds of edit, so removal, addition, split, combination, a prefix shift,
a correction with unchanged text and their mixtures are particular maps.
Whether the text changed decides three rules: with unchanged text every mapped
occurrence keeps its span and a continuing group may change its decision in
place; with changed text span-scoped variants are refused. Functions below
follow the order in which `admit` applies them. `check_absent_from_graph` is
the one rule that reads the graph: on a first attempt no UUID the revision
introduces may be a node yet, so the caller runs it after `admit`.
"""

from dataclasses import dataclass
from typing import NamedTuple

from .models import Accepted, ChunkInput, CorpusObjectInput, SourceTextInput
from .validation import IntentError, fresh_entity_id, fresh_mention_id, text_digest


class OccurrenceRef(NamedTuple):
    group: str
    index: int


OccurrenceMap = dict[str, tuple[OccurrenceRef | None, ...]]


def parse_occurrence_map(raw) -> OccurrenceMap:
    """Parse a map from JSON or code into typed references."""
    if not isinstance(raw, dict) or not all(isinstance(k, str) for k in raw):
        raise IntentError("occurrence_changed", "An occurrence map is keyed by group")
    parsed = {}
    for key, entries in raw.items():
        if not isinstance(entries, (list, tuple)):
            raise IntentError(
                "occurrence_changed", "Map each old occurrence, in order, once"
            )
        refs = []
        for entry in entries:
            if entry is None:
                refs.append(None)
            elif (
                isinstance(entry, (list, tuple))
                and len(entry) == 2
                and isinstance(entry[0], str)
                and type(entry[1]) is int
            ):
                refs.append(OccurrenceRef(*entry))
            else:
                raise IntentError(
                    "occurrence_changed",
                    "Map an old occurrence to null or one [group, index] pair",
                )
        parsed[key] = tuple(refs)
    return parsed


def identity_map(source) -> OccurrenceMap:
    """Every occurrence stays where it is, as in a prefix insertion."""
    return {
        k: tuple(OccurrenceRef(k, i) for i in range(len(g.occurrences)))
        for k, g in source.mention_groups.items()
    }


@dataclass(frozen=True)
class GroupFate:
    continuing: frozenset[str]
    retired: frozenset[str]
    fresh: frozenset[str]


@dataclass(frozen=True)
class Origin:
    """One mapped old occurrence: where it was and where it is now."""

    old: OccurrenceRef
    new: OccurrenceRef


def admit(old, source, before, after, occurrence_map, *, first_attempt=True):
    """Admit any reviewed mix of kept, removed, added and regrouped occurrences,
    with changed or unchanged text.

    Only a first attempt chooses new UUIDs; a retry completes a saved plan,
    which may predate the derivation rules.
    """
    text_changed = before != after
    check_text_present(before, after)
    check_source_identity(old, source, before, after)
    check_next_revision(old, source)
    origins = map_origins(old, occurrence_map)
    check_old_slices(old, before)
    check_targets_exist(source, origins)
    check_single_origin(origins)
    check_same_text(old, source, origins)
    if not text_changed:
        check_same_spans(old, source, origins)
    check_new_slices(source, after)
    fate = group_fate(old, source, origins)
    check_fresh_keys(old, fate.fresh)
    check_unused_entity_ids(old, source, fate.fresh)
    if first_attempt:
        check_revision_scoped_ids(old, source, fate.fresh)
    check_continuing_resolutions(old, source, fate)
    check_fresh_resolution_ids(old, source, fate)
    check_one_resolution_per_fresh_group(source, fate)
    check_mention_recipes(old, source, fate)
    check_reusable_recipes(old, source)
    if first_attempt:
        check_derived_entity_ids(old, source)
    check_scoped_variants(old, source)
    check_new_variant_keys(old, source)
    if text_changed:
        check_continuing_decisions(old, source, fate)
        check_no_span_variants(source)
    return fate


def check_text_present(before, after):
    if not before or not after:
        raise IntentError("empty_text", "A replacement keeps a non-empty text")


def check_source_identity(old, source, before, after):
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


def check_next_revision(old, source):
    if source.revision != old.revision + 1:
        raise IntentError(
            "not_admitted", "A group change advances exactly one revision"
        )


def map_origins(old, occurrence_map: OccurrenceMap):
    if set(occurrence_map) != set(old.mention_groups):
        raise IntentError("occurrence_changed", "Map every old group")
    origins = []
    for key, previous in old.mention_groups.items():
        refs = occurrence_map[key]
        if len(refs) != len(previous.occurrences):
            raise IntentError(
                "occurrence_changed", "Map each old occurrence, in order, once"
            )
        origins += [
            Origin(OccurrenceRef(key, i), ref) for i, ref in enumerate(refs) if ref
        ]
    return origins


def check_old_slices(old, before):
    for group in old.mention_groups.values():
        if any(before[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed", "Previous occurrence does not match text"
            )


def check_targets_exist(source, origins):
    for o in origins:
        group = source.mention_groups.get(o.new.group)
        if group is None or not 0 <= o.new.index < len(group.occurrences):
            raise IntentError(
                "occurrence_changed", "Mapped occurrence is not in the new source"
            )


def check_single_origin(origins):
    if len({o.new for o in origins}) != len(origins):
        raise IntentError(
            "occurrence_changed", "A new occurrence has at most one origin"
        )


def occurrence(description, ref):
    return description.mention_groups[ref.group].occurrences[ref.index]


def check_same_text(old, source, origins):
    for o in origins:
        if occurrence(source, o.new).text != occurrence(old, o.old).text:
            raise IntentError(
                "occurrence_changed",
                "Mapped occurrence text differs from the old occurrence",
            )


def check_same_spans(old, source, origins):
    """With unchanged text nothing re-marks the document, so a mapped
    occurrence stays at its span even when another has the same text."""
    for o in origins:
        previous, current = occurrence(old, o.old), occurrence(source, o.new)
        if (current.start, current.end) != (previous.start, previous.end):
            raise IntentError(
                "occurrence_moved",
                "With unchanged text a mapped occurrence keeps its start and end",
            )


def check_new_slices(source, after):
    for group in source.mention_groups.values():
        if any(after[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed",
                "New occurrence does not match its exact document slice",
            )


def same_identity(old, source, key):
    previous, current = old.mention_groups[key], source.mention_groups[key]
    return (current.entity_id, current.document_ref) == (
        previous.entity_id,
        previous.document_ref,
    )


def fed_only_by_itself(key, feeders):
    return feeders.get(key) == {key}


def lands_only_in_itself(key, landings):
    return landings.get(key, set()) <= {key}


def group_fate(old, source, origins):
    """Strict continuation: an old group continues only into the new group with
    its key and UUID that receives all of its surviving occurrences, at least
    one, and none from another old group. Order within a group may change."""
    feeders, landings = {}, {}
    for o in origins:
        feeders.setdefault(o.new.group, set()).add(o.old.group)
        landings.setdefault(o.old.group, set()).add(o.new.group)
    continuing = frozenset(
        key
        for key in old.mention_groups
        if key in source.mention_groups
        and same_identity(old, source, key)
        and fed_only_by_itself(key, feeders)
        and lands_only_in_itself(key, landings)
    )
    return GroupFate(
        continuing=continuing,
        retired=frozenset(old.mention_groups) - continuing,
        fresh=frozenset(source.mention_groups) - continuing,
    )


def check_fresh_keys(old, fresh):
    if fresh & set(old.mention_groups):
        raise IntentError(
            "fresh_key_reused", "A fresh group needs a key that no old group used"
        )


def check_unused_entity_ids(old, source, fresh):
    for key in fresh:
        if source.mention_groups[key].entity_id in old.entity_constructions:
            raise IntentError(
                "fresh_uuid_reused", "A fresh group requires a fresh Entity UUID"
            )


def check_revision_scoped_ids(old, source, fresh):
    """A fresh group's UUID is derived from its source, new revision and key.

    The record store advances one revision per step and refuses a changed
    description at a used revision, so no (source, revision, key) repeats and a
    retired key that returns gets a different UUID.
    """
    for key in fresh:
        entity_id = source.mention_groups[key].entity_id
        if entity_id != fresh_mention_id(old.identity_data_id, source.revision, key):
            raise IntentError(
                "fresh_uuid_not_derived",
                "A fresh group's Entity UUID derives from its source, revision and group key",
            )


ATTRIBUTION_FIELDS = frozenset({"producer_ref", "input_refs", "explanation"})


def reviewed_decisions(values):
    return {
        k: {
            f: v
            for f, v in item.model_dump(mode="json").items()
            if f not in ATTRIBUTION_FIELDS
        }
        for k, item in values.items()
    }


def resolutions_of(description, groups):
    return {
        k: r
        for k, r in description.mention_resolutions.items()
        if r.group_ref in groups
    }


def check_continuing_resolutions(old, source, fate):
    """A continuing group keeps its resolution record: the same key, for the
    same group."""
    previous = resolutions_of(old, fate.continuing)
    current = resolutions_of(source, fate.continuing)
    if {k: r.group_ref for k, r in previous.items()} != {
        k: r.group_ref for k, r in current.items()
    }:
        raise IntentError(
            "continuing_resolution_changed",
            "A continuing group keeps its resolution record",
        )


def check_continuing_decisions(old, source, fate):
    """With changed text a continuing group keeps its reviewed decision,
    because a changed meaning in a text edit is a fresh group. With unchanged
    text the decision may change in place, so `admit` skips this rule."""
    previous = resolutions_of(old, fate.continuing)
    current = resolutions_of(source, fate.continuing)
    if reviewed_decisions(current) != reviewed_decisions(previous):
        raise IntentError(
            "continuing_decision_changed",
            "A continuing group keeps its reviewed decision when the text changes",
        )


def check_fresh_resolution_ids(old, source, fate):
    used = set(old.mention_resolutions) | set(old.variant_assignments)
    if set(resolutions_of(source, fate.fresh)) & used:
        raise IntentError(
            "not_admitted",
            "A fresh resolution needs an ID no old resolution or assignment used",
        )


def check_one_resolution_per_fresh_group(source, fate):
    # The model allows at most one resolution per group, so this needs at least one.
    declared = {r.group_ref for r in resolutions_of(source, fate.fresh).values()}
    if declared != fate.fresh:
        raise IntentError(
            "not_admitted", "Declare exactly one resolution per fresh group"
        )


def check_mention_recipes(old, source, fate):
    """Mention recipes are the old ones, minus the retired groups', plus the
    fresh groups'. The model supplies each fresh group's recipe, and the fresh
    UUID rules keep it distinct, so this checks the continuing and retired."""
    for key in fate.continuing:
        eid = old.mention_groups[key].entity_id
        if source.entity_constructions[eid] != old.entity_constructions[eid]:
            raise IntentError(
                "mention_recipe_changed",
                "A continuing group keeps its mention recipe",
            )
    for key in fate.retired:
        if old.mention_groups[key].entity_id in source.entity_constructions:
            raise IntentError(
                "mention_recipe_changed",
                "A retired group's mention recipe is dropped",
            )


def reusable_recipes(description):
    mentions = {g.entity_id for g in description.mention_groups.values()}
    return {
        eid: recipe
        for eid, recipe in description.entity_constructions.items()
        if eid not in mentions
    }


def check_reusable_recipes(old, source):
    """A reusable recipe may be added or dropped in any edit; a retained one is
    unchanged."""
    previous, current = reusable_recipes(old), reusable_recipes(source)
    if any(current[eid] != previous[eid] for eid in set(previous) & set(current)):
        raise IntentError(
            "reusable_recipe_changed", "A retained reusable recipe stays unchanged"
        )


def referenced_corpus_ids(source):
    """Existing Entities that a resolution or variant reads through a corpus
    input. Only an input listed in some input_refs reaches validate_inputs,
    which proves the Entity exists in the graph with the recorded hash."""
    listed = set()
    for record in [
        *source.mention_resolutions.values(),
        *source.variant_assignments.values(),
    ]:
        listed.update(record.input_refs)
    return {
        i.entity_id
        for key, i in source.inputs.items()
        if key in listed and isinstance(i, CorpusObjectInput)
    }


def new_reusable_ids(old, source):
    """Reusable Entities this revision creates: added recipes that no listed
    corpus input names as an existing Entity."""
    return (
        set(reusable_recipes(source))
        - set(old.entity_constructions)
        - referenced_corpus_ids(source)
    )


def naming_keys(source, entity_id):
    """Keys of the resolutions and variants that name an Entity."""
    return {
        k
        for k, r in source.mention_resolutions.items()
        if isinstance(r, Accepted) and r.target_entity_id == entity_id
    } | {
        k
        for k, v in source.variant_assignments.items()
        if entity_id in (v.source_entity_id, v.target_entity_id)
    }


def check_derived_entity_ids(old, source):
    """A new reusable Entity's UUID derives from the source, the new revision
    and the key of a resolution or variant that names it."""
    for eid in new_reusable_ids(old, source):
        derived = {
            fresh_entity_id(old.identity_data_id, source.revision, k)
            for k in naming_keys(source, eid)
        }
        if eid not in derived:
            raise IntentError(
                "entity_uuid_not_derived",
                "A new reusable Entity's UUID derives from its source, revision and the key of a resolution or variant that names it",
            )


FIXED_SCOPES = frozenset({"corpus", "text_spans"})


def scoped_variants(description, kinds):
    return {
        k: v
        for k, v in description.variant_assignments.items()
        if v.applicability.kind in kinds
    }


def check_scoped_variants(old, source):
    """Document-scoped variants may be added, dropped or retargeted. Corpus-
    and span-scoped ones reach beyond this edit, so they stay unchanged."""
    if reviewed_decisions(scoped_variants(source, FIXED_SCOPES)) != (
        reviewed_decisions(scoped_variants(old, FIXED_SCOPES))
    ):
        raise IntentError(
            "variant_changed",
            "Corpus- and span-scoped variant assignments stay unchanged",
        )


def check_new_variant_keys(old, source):
    added = set(source.variant_assignments) - set(old.variant_assignments)
    if added & set(old.mention_resolutions):
        raise IntentError(
            "variant_key_reused", "A new variant key is not an old resolution key"
        )


def check_no_span_variants(source):
    if any(
        v.applicability.kind == "text_spans"
        for v in source.variant_assignments.values()
    ):
        raise IntentError(
            "span_variant_in_text_edit",
            "Span-scoped variants require explicit scope remapping",
        )


async def check_absent_from_graph(graph, old, source, fate):
    """On a first attempt, no UUID this revision introduces is a graph node yet."""
    probes = [
        (
            source.mention_groups[key].entity_id,
            "fresh_uuid_in_graph",
            "New mention Entity UUID already exists in the graph",
        )
        for key in sorted(fate.fresh)
    ] + [
        (
            eid,
            "entity_uuid_in_graph",
            "New reusable Entity UUID already exists in the graph",
        )
        for eid in sorted(new_reusable_ids(old, source))
    ]
    for entity_id, code, message in probes:
        if await graph.get_node(str(entity_id)) is not None:
            raise IntentError(code, message)


def entity_ids_named(source):
    """Every Entity UUID a description names: its recipes, its accepted
    targets, its variant endpoints and its corpus inputs."""
    named = set(source.entity_constructions)
    named.update(
        r.target_entity_id
        for r in source.mention_resolutions.values()
        if isinstance(r, Accepted)
    )
    for v in source.variant_assignments.values():
        named.update((v.source_entity_id, v.target_entity_id))
    named.update(
        i.entity_id for i in source.inputs.values() if isinstance(i, CorpusObjectInput)
    )
    return named


def check_removed_entity_ids(source, removed):
    """A re-add does not bring back an Entity the forget removed. An old
    recipe does not authorize recreating a retired object under its UUID."""
    if removed & entity_ids_named(source):
        raise IntentError(
            "forgotten_uuid_reused",
            "A re-add does not recreate an Entity UUID the forget removed",
        )


def replacement_entity_id(identity_data_id, revision, removed_id):
    """The UUID a re-add gives the replacement of a removed Entity that no
    resolution or variant names."""
    return fresh_entity_id(identity_data_id, revision, f"replaces:{removed_id}")


def check_readd_entity_ids(forgotten, source, removed):
    """A new reusable Entity in a re-add derives from the key of a resolution
    or variant that names it, as in any revision. Only an Entity nothing
    names replaces a removed one by that Entity's UUID."""
    replacements = {
        replacement_entity_id(forgotten.identity_data_id, source.revision, r)
        for r in removed
    }
    for eid in new_reusable_ids(forgotten, source):
        keys = naming_keys(source, eid)
        allowed = {
            fresh_entity_id(forgotten.identity_data_id, source.revision, k)
            for k in keys
        }
        if eid not in (allowed if keys else replacements):
            raise IntentError(
                "entity_uuid_not_derived",
                "A re-added reusable Entity's UUID derives from a key that names it; only an Entity nothing names derives from the removed Entity it replaces",
            )


async def admit_readd(graph, forgotten, source, removed):
    """A re-add after forget publishes the same identity source and document
    at the next revision. Every group is fresh: its UUID derives from the new
    revision, repeats nothing the forgotten revision used, and is not in the
    graph. No Entity in `removed`, the ones the forget took away, returns; a
    reusable one is replaced by a derived UUID: from a key that names it, or
    from the removed UUID when nothing names it."""
    from .storage import READD_REVISION

    old_doc = forgotten.inputs[forgotten.original_input_ref]
    doc = source.inputs[source.original_input_ref]
    if (source.dataset_id, source.identity_data_id, doc.data_id) != (
        forgotten.dataset_id,
        forgotten.identity_data_id,
        old_doc.data_id,
    ):
        raise IntentError(
            "source_changed", "Re-add the forgotten identity source and its document"
        )
    if source.revision != forgotten.revision + 1:
        raise IntentError(*READD_REVISION)
    fresh = frozenset(source.mention_groups)
    check_unused_entity_ids(forgotten, source, fresh)
    check_revision_scoped_ids(forgotten, source, fresh)
    check_removed_entity_ids(source, removed)
    check_readd_entity_ids(forgotten, source, removed)
    fate = GroupFate(frozenset(), frozenset(forgotten.mention_groups), fresh)
    await check_absent_from_graph(graph, forgotten, source, fate)
