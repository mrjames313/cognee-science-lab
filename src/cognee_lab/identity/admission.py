"""Admission of a reviewed text change: what the new description may claim."""

from dataclasses import dataclass

from .models import ChunkInput, CorpusObjectInput, SourceTextInput
from .validation import IntentError, fresh_mention_id, text_digest


@dataclass(frozen=True)
class Admission:
    fresh: frozenset[str] = frozenset()


def admit_remap(
    old,
    source,
    before,
    after,
    occurrence_retention=None,
    occurrence_continuity=None,
    occurrence_regrouping=None,
):
    kind, reviewed = select_mode(
        occurrence_retention=occurrence_retention,
        occurrence_continuity=occurrence_continuity,
        occurrence_regrouping=occurrence_regrouping,
    )
    check_source_identity(old, source, before, after)
    return ADMITTERS[kind](old, source, before, after, reviewed)


def admit_general(old, source, before, after, occurrence_map, *, first_attempt=True):
    check_source_identity(old, source, before, after)
    return admit_occurrence_map(
        old, source, before, after, occurrence_map, first_attempt
    )


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


def admit_prefix_shift(old, source, before, after, _):
    if not before or not after.endswith(before) or after == before:
        raise IntentError(
            "not_admitted", "Text slice requires a nonempty prefix insertion"
        )
    delta = len(after) - len(before)
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
    if (
        reviewed_decisions({**old.mention_resolutions, **old.variant_assignments})
        != reviewed_decisions(
            {**source.mention_resolutions, **source.variant_assignments}
        )
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
    return Admission()


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


def check_unused_entity_ids(old, source, fresh):
    for key in fresh:
        if source.mention_groups[key].entity_id in old.entity_constructions:
            raise IntentError(
                "incompatible_group", "A fresh group requires a fresh Entity UUID"
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
                "incompatible_group",
                "A fresh group's Entity UUID derives from its source, revision and group key",
            )


def check_new_slices(source, after):
    for group in source.mention_groups.values():
        if any(after[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed",
                "New occurrence does not match its exact document slice",
            )


def check_carryover(old, source, continuing, fresh):
    kept = {
        k: r for k, r in source.mention_resolutions.items() if r.group_ref in continuing
    }
    declared = {
        k: r for k, r in source.mention_resolutions.items() if r.group_ref in fresh
    }
    carried = {
        k: r for k, r in old.mention_resolutions.items() if r.group_ref in continuing
    }
    retired = {
        g.entity_id for k, g in old.mention_groups.items() if k not in continuing
    }
    recipes = {
        eid: recipe
        for eid, recipe in old.entity_constructions.items()
        if eid not in retired
    }
    for key in fresh:
        eid = source.mention_groups[key].entity_id
        recipes[eid] = source.entity_constructions[eid]
    if reviewed_decisions(kept) != reviewed_decisions(carried):
        raise IntentError(
            "not_admitted", "A continuing group keeps its reviewed resolutions"
        )
    if len(kept) + len(declared) != len(source.mention_resolutions):
        raise IntentError(
            "not_admitted", "Every resolution belongs to a continuing or fresh group"
        )
    if reviewed_decisions(source.variant_assignments) != reviewed_decisions(
        old.variant_assignments
    ):
        raise IntentError("not_admitted", "Variant assignments stay unchanged")
    if set(declared) & (set(old.mention_resolutions) | set(old.variant_assignments)):
        raise IntentError(
            "not_admitted",
            "A fresh resolution needs an ID no old resolution or assignment used",
        )
    if len(declared) != len(fresh) or {r.group_ref for r in declared.values()} != fresh:
        raise IntentError(
            "not_admitted", "Declare exactly one resolution per fresh group"
        )
    if source.entity_constructions != recipes:
        raise IntentError(
            "not_admitted",
            "Recipes are the old ones, minus the retired groups', plus the fresh groups'",
        )
    if any(
        v.applicability.kind == "text_spans"
        for v in source.variant_assignments.values()
    ):
        raise IntentError(
            "not_admitted", "Span-scoped variants require explicit scope remapping"
        )


def check_next_revision(old, source):
    if source.revision != old.revision + 1:
        raise IntentError(
            "not_admitted", "A group change advances exactly one revision"
        )


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
            continue
        kept.add(key)
        current = source.mention_groups.get(key)
        if (
            current is None
            or current.entity_id != previous.entity_id
            or current.document_ref != previous.document_ref
            or [o.text for o in current.occurrences]
            != [previous.occurrences[i].text for i in indices]
        ):
            raise IntentError(
                "occurrence_changed",
                "Supply exact reviewed surviving occurrences with stable group UUIDs",
            )
    if set(source.mention_groups) != kept:
        raise IntentError(
            "occurrence_changed", "Only explicitly continuing groups may remain"
        )
    check_new_slices(source, after)
    if not any(
        len(retention[k]) < len(g.occurrences) for k, g in old.mention_groups.items()
    ):
        raise IntentError(
            "not_admitted", "This reviewed slice removes at least one occurrence"
        )
    check_carryover(old, source, kept, frozenset())
    return Admission()


def admit_occurrence_addition(old, source, before, after, continuity):
    """Map every old occurrence to its reviewed index in the new group.

    Unmapped new indices are additions. No removals, regrouping, retargeting,
    recipe changes or new reusable identities are admitted by this mode.
    Positions and identity judgments are supplied, never inferred from text.
    """
    if not before or not after or before == after:
        raise IntentError("not_admitted", "Occurrence addition requires changed text")
    check_next_revision(old, source)
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
    new_groups = frozenset(source.mention_groups) - set(old.mention_groups)
    check_unused_entity_ids(old, source, new_groups)
    check_new_slices(source, after)
    check_carryover(old, source, set(old.mention_groups), new_groups)
    if not added and not new_groups:
        raise IntentError(
            "not_admitted", "This reviewed slice adds at least one occurrence"
        )
    return Admission(new_groups)


@dataclass(frozen=True)
class Regrouping:
    images: dict[str, list[tuple[str, int]]]
    continuing: frozenset[str]
    retired: frozenset[str]
    fresh: frozenset[str]


def classify_regrouping(old, source, regrouping):
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
    fresh = frozenset(source.mention_groups) - continuing
    if fresh & set(old.mention_groups):
        raise IntentError(
            "incompatible_group",
            "A fresh group needs a key that no old group used",
        )
    return Regrouping(
        images=images,
        continuing=continuing,
        retired=frozenset(old.mention_groups) - continuing,
        fresh=fresh,
    )


def admit_occurrence_regrouping(old, source, before, after, regrouping):
    if not before or not after or before == after:
        raise IntentError("not_admitted", "Occurrence regrouping requires changed text")
    plan = classify_regrouping(old, source, regrouping)
    if not plan.retired:
        raise IntentError(
            "not_admitted", "This reviewed slice regroups at least one group"
        )
    check_next_revision(old, source)
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
    check_new_slices(source, after)
    for key in plan.continuing:
        previous, current = old.mention_groups[key], source.mention_groups[key]
        if (current.entity_id, current.document_ref) != (
            previous.entity_id,
            previous.document_ref,
        ):
            raise IntentError(
                "occurrence_changed", "A continuing group keeps its Entity UUID"
            )
    check_unused_entity_ids(old, source, plan.fresh)
    check_carryover(old, source, plan.continuing, plan.fresh)
    return Admission(plan.fresh)


ADMITTERS = {
    "prefix": admit_prefix_shift,
    "retention": admit_occurrence_removal,
    "continuity": admit_occurrence_addition,
    "regrouping": admit_occurrence_regrouping,
}


MODE_FIELDS = (
    ("retention", "occurrence_retention"),
    ("continuity", "occurrence_continuity"),
    ("regrouping", "occurrence_regrouping"),
)


def select_mode(**fields):
    chosen = [
        (kind, fields[field])
        for kind, field in MODE_FIELDS
        if fields[field] is not None
    ]
    if len(chosen) > 1:
        raise IntentError("not_admitted", "Select one occurrence transition mode")
    return chosen[0] if chosen else ("prefix", None)


@dataclass(frozen=True)
class GroupFate:
    continuing: frozenset[str]
    retired: frozenset[str]
    fresh: frozenset[str]


@dataclass(frozen=True)
class Origin:
    """One mapped old occurrence: where it was and where it is now."""

    old_key: str
    old_index: int
    new_key: str
    new_index: int


def parse_occurrence_map(old, occurrence_map):
    if not isinstance(occurrence_map, dict) or set(occurrence_map) != set(
        old.mention_groups
    ):
        raise IntentError("occurrence_changed", "Map every old group")
    origins = []
    for key, previous in old.mention_groups.items():
        entries = occurrence_map[key]
        if not isinstance(entries, list) or len(entries) != len(previous.occurrences):
            raise IntentError(
                "occurrence_changed", "Map each old occurrence, in order, once"
            )
        for index, entry in enumerate(entries):
            if entry is None:
                continue
            if (
                not isinstance(entry, list)
                or len(entry) != 2
                or not isinstance(entry[0], str)
                or type(entry[1]) is not int
            ):
                raise IntentError(
                    "occurrence_changed",
                    "Map an old occurrence to null or one [group, index] pair",
                )
            origins.append(Origin(key, index, *entry))
    return origins


def check_old_slices(old, before):
    for group in old.mention_groups.values():
        if any(before[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed", "Previous occurrence does not match text"
            )


def check_targets_exist(source, origins):
    for o in origins:
        group = source.mention_groups.get(o.new_key)
        if group is None or not 0 <= o.new_index < len(group.occurrences):
            raise IntentError(
                "occurrence_changed", "Mapped occurrence is not in the new source"
            )


def check_single_origin(origins):
    targets = [(o.new_key, o.new_index) for o in origins]
    if len(set(targets)) != len(targets):
        raise IntentError(
            "occurrence_changed", "A new occurrence has at most one origin"
        )


def check_same_text(old, source, origins):
    for o in origins:
        before = old.mention_groups[o.old_key].occurrences[o.old_index].text
        if source.mention_groups[o.new_key].occurrences[o.new_index].text != before:
            raise IntentError(
                "occurrence_changed",
                "Mapped occurrence text differs from the old occurrence",
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
        feeders.setdefault(o.new_key, set()).add(o.old_key)
        landings.setdefault(o.old_key, set()).add(o.new_key)
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
            "incompatible_group", "A fresh group needs a key that no old group used"
        )


def admit_occurrence_map(old, source, before, after, occurrence_map, first_attempt):
    """Admit any reviewed mix of kept, removed, added and regrouped occurrences.

    Rules are stated over occurrences and groups, never over kinds of edit, so
    removal, addition, split, combination and their mixtures are particular
    maps. Only a first attempt chooses fresh UUIDs; a retry completes a saved
    plan, which may predate the revision-scoped rule.
    """
    if not before or not after or before == after:
        raise IntentError("not_admitted", "A text change requires changed text")
    check_next_revision(old, source)
    origins = parse_occurrence_map(old, occurrence_map)
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
    check_carryover(old, source, fate.continuing, fate.fresh)
    return fate


def to_occurrence_map(old, kind, reviewed):
    """Write an old-mode map as the general map that states the same edit."""
    groups = {k: len(g.occurrences) for k, g in old.mention_groups.items()}
    if kind == "prefix":
        return {k: [[k, i] for i in range(n)] for k, n in groups.items()}
    if kind == "retention":
        return {
            k: [
                [k, reviewed[k].index(i)] if i in reviewed[k] else None
                for i in range(n)
            ]
            for k, n in groups.items()
        }
    if kind == "continuity":
        return {k: [[k, j] for j in reviewed[k]] for k in groups}
    return {k: [list(pair) for pair in reviewed[k]] for k in groups}
