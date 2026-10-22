"""Admission of a reviewed replacement: what the new description may claim.

One map states the edit. For each old occurrence, in order, it gives the new
occurrence it became, or None if it was removed; a new occurrence that nothing
maps to is an addition. The rules are stated over occurrences and groups, never
over kinds of edit, so removal, addition, split, combination, a prefix shift,
a correction with unchanged text and their mixtures are particular maps.
Whether the text changed decides only two rules: a continuing group may change
its decision in place when the text is unchanged, and span-scoped variants are
refused when it changed. Functions below follow the order in which `admit`
applies them.
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
    check_text_present(before, after)
    check_source_identity(old, source, before, after)
    check_next_revision(old, source)
    origins = map_origins(old, occurrence_map)
    check_old_slices(old, before)
    check_targets_exist(source, origins)
    check_single_origin(origins)
    check_same_text(old, source, origins)
    check_new_slices(source, after)
    fate = group_fate(old, source, origins)
    check_fresh_keys(old, fate.fresh)
    check_unused_entity_ids(old, source, fate.fresh)
    if first_attempt:
        check_revision_scoped_ids(old, source, fate.fresh)
    text_changed = before != after
    check_continuing_decisions(old, source, fate, text_changed)
    check_fresh_resolution_ids(old, source, fate)
    check_one_resolution_per_fresh_group(source, fate)
    check_mention_recipes(old, source, fate)
    check_reusable_recipes(old, source)
    if first_attempt:
        check_derived_entity_ids(old, source)
    check_scoped_variants(old, source)
    check_new_variant_keys(old, source)
    if text_changed:
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


def check_continuing_decisions(old, source, fate, text_changed):
    """A continuing group keeps its resolution record. With changed text it
    also keeps the reviewed decision, because a changed meaning in a text edit
    is a fresh group; with unchanged text the decision may change in place."""
    previous = resolutions_of(old, fate.continuing)
    current = resolutions_of(source, fate.continuing)
    if {k: r.group_ref for k, r in previous.items()} != {
        k: r.group_ref for k, r in current.items()
    } or (text_changed and reviewed_decisions(current) != reviewed_decisions(previous)):
        raise IntentError(
            "continuing_decision_changed",
            "A continuing group keeps its resolution record, and its reviewed decision when the text changes",
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


def new_reusable_ids(old, source):
    """Reusable Entities this revision creates: added recipes that no corpus
    input names as an existing Entity."""
    existing = {
        i.entity_id for i in source.inputs.values() if isinstance(i, CorpusObjectInput)
    }
    return set(reusable_recipes(source)) - set(old.entity_constructions) - existing


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
            "not_admitted", "Span-scoped variants require explicit scope remapping"
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
