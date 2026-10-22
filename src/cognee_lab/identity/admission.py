"""Admission of a reviewed text change: what the new description may claim.

One map states the edit. For each old occurrence, in order, it gives the new
occurrence it became, or None if it was removed; a new occurrence that nothing
maps to is an addition. The rules are stated over occurrences and groups, never
over kinds of edit, so removal, addition, split, combination, a prefix shift
and their mixtures are particular maps. Functions below follow the order in
which `admit` applies them.
"""

from dataclasses import dataclass
from typing import NamedTuple

from .models import ChunkInput, CorpusObjectInput, SourceTextInput
from .validation import IntentError, fresh_mention_id, text_digest


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
    """Admit any reviewed mix of kept, removed, added and regrouped occurrences.

    Only a first attempt chooses fresh UUIDs; a retry completes a saved plan,
    which may predate the revision-scoped rule.
    """
    check_source_identity(old, source, before, after)
    check_changed_text(before, after)
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
    check_continuing_decisions(old, source, fate)
    check_variants_unchanged(old, source)
    check_fresh_resolution_ids(old, source, fate)
    check_one_resolution_per_fresh_group(source, fate)
    check_recipes(old, source, fate)
    check_no_span_variants(source)
    return fate


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


def check_changed_text(before, after):
    if not before or not after or before == after:
        raise IntentError("not_admitted", "A text change requires changed text")


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


def check_continuing_decisions(old, source, fate):
    if reviewed_decisions(resolutions_of(source, fate.continuing)) != (
        reviewed_decisions(resolutions_of(old, fate.continuing))
    ):
        raise IntentError(
            "not_admitted", "A continuing group keeps its reviewed resolutions"
        )


def check_variants_unchanged(old, source):
    if reviewed_decisions(source.variant_assignments) != reviewed_decisions(
        old.variant_assignments
    ):
        raise IntentError("not_admitted", "Variant assignments stay unchanged")


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


def check_recipes(old, source, fate):
    retired = {old.mention_groups[k].entity_id for k in fate.retired}
    recipes = {
        eid: recipe
        for eid, recipe in old.entity_constructions.items()
        if eid not in retired
    }
    for key in fate.fresh:
        eid = source.mention_groups[key].entity_id
        recipes[eid] = source.entity_constructions[eid]
    if source.entity_constructions != recipes:
        raise IntentError(
            "not_admitted",
            "Recipes are the old ones, minus the retired groups', plus the fresh groups'",
        )


def check_no_span_variants(source):
    if any(
        v.applicability.kind == "text_spans"
        for v in source.variant_assignments.values()
    ):
        raise IntentError(
            "not_admitted", "Span-scoped variants require explicit scope remapping"
        )
