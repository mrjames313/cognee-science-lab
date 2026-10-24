"""Saved records another source may cite, and what a citation pins.

One registry maps each citable record type to where its records live in a
description and what of a record a citation pins (its fingerprint).
Admission, validation, withholding and erasure read records only through
it, so another record type is one more entry. Today the citable records are
decisions: mention resolutions and variant assignments.

A fingerprint is a record's reviewed fields, never who reviewed it or what
it read (`ATTRIBUTION_FIELDS`): a re-confirm keeps it and an in-place
replacement changes it. A resolution's fingerprint also names its group's
mention UUID. Mention UUIDs are revision-scoped and never reused, so a
resolution key and group key that come back later with the same target
fingerprint differently.

An erasure removes a record that cites what a forget took away, and a
reviewer removes or unresolves one whose input changed or went, through
one helper (`apply_removal`, by `RecordKind.removed`). A removed record is
named with the fingerprint it had and the last served revision that held
it (`RemovedRecord`), so a citation made before the removal matches it and
a later one does not.
"""

from collections.abc import Callable, Collection, Mapping
from typing import NamedTuple, Protocol, get_args
from uuid import UUID

from .models import (
    Accepted,
    DecisionBase,
    IdentitySource,
    RecordType,
    SavedRecordInput,
    Unresolved,
    Variant,
)
from .digests import object_digest

ATTRIBUTION_FIELDS = frozenset({"producer_ref", "input_refs", "explanation"})


def reviewed_decisions(values):
    """Each decision's fields apart from its attribution."""
    return {
        k: {
            f: v
            for f, v in item.model_dump(mode="json").items()
            if f not in ATTRIBUTION_FIELDS
        }
        for k, item in values.items()
    }


Record = DecisionBase | Variant


class CitesInputs(Protocol):
    """A part of a description that cites inputs by key, as a group does."""

    input_refs: list[str]


# Each input key a removal changes: its new key, or None when it goes.
RefMap = Mapping[str, str | None]


class RecordKind(NamedTuple):
    """One citable record type: everything the chain logic asks of it, so
    no other module names a record type's fields.

    - `field`: the description attribute that holds its records, by key.
    - `fingerprint`: what a citation of a record pins, given its source and
      key.
    - `inputs`: the input keys a record cites directly, given its source and
      key.
    - `names`: the Entities a record names, given its source and key.
    - `held`: whether a record is withheld, given its source's entries of
      the withheld-decision set, its source and its key.
    - `removed`: what a removal leaves of a record, given its source, its
      key, the input ref map (`rewired`), the removal producer's key and an
      explanation: the record after the removal, or None when the removal
      drops it.
    - `outcome`: the name of what a removal leaves (`unresolved`,
      `dropped`).
    - `stripped`: the other parts of a description that hold the inputs of
      the given records of this type, by field, rewired by the ref map.
    - `unlinked`: the mention Entities whose facts lose their identity link
      when a record is removed, given its source and key."""

    field: str
    fingerprint: Callable[[IdentitySource, str], dict]
    inputs: Callable[[IdentitySource, str], frozenset[str]]
    names: Callable[[IdentitySource, str], frozenset[UUID]]
    held: Callable[[Mapping[str, object], IdentitySource, str], bool]
    removed: Callable[[IdentitySource, str, RefMap, str, str | None], Record | None]
    outcome: str
    stripped: Callable[
        [IdentitySource, Collection[str], RefMap], dict[str, dict[str, CitesInputs]]
    ]
    unlinked: Callable[[IdentitySource, str], frozenset[UUID]]


def resolution_fingerprint(description, key) -> dict:
    record = description.mention_resolutions[key]
    group = description.mention_groups[record.group_ref]
    return dict(
        reviewed_decisions({key: record})[key], group_entity_id=str(group.entity_id)
    )


def variant_fingerprint(description, key) -> dict:
    return reviewed_decisions({key: description.variant_assignments[key]})[key]


def resolution_inputs(description, key) -> frozenset[str]:
    """A resolution is one unit with its group, so it cites the group's
    inputs too."""
    decision = description.mention_resolutions[key]
    group = description.mention_groups[decision.group_ref]
    return frozenset([*decision.input_refs, *group.input_refs])


def variant_inputs(description, key) -> frozenset[str]:
    """A variant cites its scope's document too."""
    variant = description.variant_assignments[key]
    scope = getattr(variant.applicability, "document_ref", None)
    return frozenset([*variant.input_refs, *([scope] if scope else [])])


def resolution_names(description, key) -> frozenset[UUID]:
    """An accepted resolution names its target; an unresolved one nothing."""
    decision = description.mention_resolutions[key]
    if isinstance(decision, Accepted):
        return frozenset([decision.target_entity_id])
    return frozenset()


def variant_names(description, key) -> frozenset[UUID]:
    variant = description.variant_assignments[key]
    return frozenset([variant.source_entity_id, variant.target_entity_id])


def decision_held(entries, description, key) -> bool:
    """A decision is withheld when the withheld-decision set holds its key."""
    return key in entries


def rewired(refs, ref_map: RefMap, fallback):
    """Input refs with each key of `ref_map` replaced by its new key, or
    dropped when it maps to None; the original document when nothing else
    remains."""
    kept = [ref_map.get(k, k) for k in refs]
    return [k for k in kept if k is not None] or [fallback]


def resolution_removed(description, key, ref_map, producer, explanation):
    """A removed resolution stays, unresolved in place under the removal
    producer, with its inputs rewired."""
    was = description.mention_resolutions[key]
    return Unresolved(
        group_ref=was.group_ref,
        status="unresolved",
        input_refs=rewired(was.input_refs, ref_map, description.original_input_ref),
        producer_ref=producer,
        explanation=explanation,
    )


def variant_removed(description, key, ref_map, producer, explanation):
    """A removed variant is dropped."""
    return None


def groups_stripped(description, keys, ref_map) -> dict[str, dict[str, CitesInputs]]:
    """The group of each given resolution, which its inputs include, with
    its inputs rewired. Another resolution's group keeps what it cites."""
    fallback = description.original_input_ref
    groups = {
        description.mention_resolutions[k].group_ref
        for k in keys
        if k in description.mention_resolutions
    }
    return dict(
        mention_groups={
            k: g.model_copy(
                update=dict(input_refs=rewired(g.input_refs, ref_map, fallback))
            )
            for k, g in description.mention_groups.items()
            if k in groups
        }
    )


def nothing_stripped(description, keys, ref_map) -> dict[str, dict[str, CitesInputs]]:
    return {}


def resolution_unlinked(description, key) -> frozenset[UUID]:
    """An accepted resolution linked its group's mention to an Entity."""
    decision = description.mention_resolutions[key]
    if not isinstance(decision, Accepted):
        return frozenset()
    return frozenset([description.mention_groups[decision.group_ref].entity_id])


def nothing_unlinked(description, key) -> frozenset[UUID]:
    return frozenset()


REGISTRY: dict[str, RecordKind] = {
    "mention_resolution": RecordKind(
        field="mention_resolutions",
        fingerprint=resolution_fingerprint,
        inputs=resolution_inputs,
        names=resolution_names,
        held=decision_held,
        removed=resolution_removed,
        outcome="unresolved",
        stripped=groups_stripped,
        unlinked=resolution_unlinked,
    ),
    "variant_assignment": RecordKind(
        field="variant_assignments",
        fingerprint=variant_fingerprint,
        inputs=variant_inputs,
        names=variant_names,
        held=decision_held,
        removed=variant_removed,
        outcome="dropped",
        stripped=nothing_stripped,
        unlinked=nothing_unlinked,
    ),
}
if set(get_args(RecordType)) != REGISTRY.keys():
    raise TypeError("models.RecordType and records.REGISTRY name different types")


def apply_removal(
    payload, source, keys, ref_map: RefMap, producer_key, explanation=None
):
    """Remove each record in `keys` from `payload`, a JSON dump of `source`,
    as its record type says (`RecordKind.removed`), and rewire the parts
    that hold those records' inputs (`RecordKind.stripped`) by `ref_map`.
    Other records and their parts keep citing what they cite. An erasure
    maps each erased input to None; a reviewer maps an input that changed
    to its new key and one that went or that it drops to None. The caller
    adds the new inputs and the producer."""
    for key in sorted(keys):
        kind = REGISTRY[record_type_of(source, key)]
        record = kind.removed(source, key, ref_map, producer_key, explanation)
        if record is None:
            payload[kind.field].pop(key)
        else:
            payload[kind.field][key] = record.model_dump(mode="json", exclude_none=True)
    for kind in REGISTRY.values():
        for field, parts in kind.stripped(source, keys, ref_map).items():
            for part_key, part in parts.items():
                payload[field][part_key] = part.model_dump(mode="json")


def drops(description, key) -> bool:
    """Whether a removal drops the record (`RecordKind.outcome`), as it
    drops a variant, rather than keep it in place."""
    return REGISTRY[record_type_of(description, key)].outcome == "dropped"


def record_inputs(source) -> dict[str, frozenset[str]]:
    """The input keys each record cites directly, by its key, as its record
    type says (`RecordKind.inputs`)."""
    return {
        key: kind.inputs(source, key)
        for kind in REGISTRY.values()
        for key in getattr(source, kind.field)
    }


def naming(description, key) -> frozenset[UUID]:
    """The Entities one record names, as its record type says
    (`RecordKind.names`)."""
    return REGISTRY[record_type_of(description, key)].names(description, key)


def record_digest(description, record_type, record_id) -> str | None:
    """The fingerprint digest of one record, or None when the description
    has no record of that type under that key."""
    kind = REGISTRY[record_type]
    if record_id not in getattr(description, kind.field):
        return None
    return object_digest(
        dict(kind.fingerprint(description, record_id), record_type=record_type)
    )


def record_type_of(description, record_id) -> str | None:
    """The type whose records hold this key: record keys are unique within a
    source across every type."""
    return next(
        (
            t
            for t, kind in REGISTRY.items()
            if record_id in getattr(description, kind.field)
        ),
        None,
    )


def record_keys(description) -> list[str]:
    """Every record key of the description, of every type."""
    return [k for kind in REGISTRY.values() for k in getattr(description, kind.field)]


def cited_row(rows, item: SavedRecordInput):
    """The ledger row of the source a citation names, or None."""
    return next(
        (
            r
            for r in rows
            if (r.dataset, r.source)
            == (str(item.dataset_id), str(item.identity_data_id))
        ),
        None,
    )


def saved_records(description) -> dict[str, SavedRecordInput]:
    """The description's saved-record inputs, by key."""
    return {
        k: i for k, i in description.inputs.items() if isinstance(i, SavedRecordInput)
    }


def citation(description, record_id) -> dict:
    """The saved-record input that cites one record of `description` as it
    is now."""
    record_type = record_type_of(description, record_id)
    if record_type is None:
        raise KeyError(record_id)
    return dict(
        kind="saved_record",
        dataset_id=str(description.dataset_id),
        identity_data_id=str(description.identity_data_id),
        record_type=record_type,
        record_id=record_id,
        representation_revision=description.revision,
        content_sha256=record_digest(description, record_type, record_id),
    )


class RemovedRecord(NamedTuple):
    """A record an erasure removed or will remove: its source, type and key,
    the fingerprint it had, and the last served revision of its source
    that held it. A citation reads it when it pins that fingerprint at that
    revision or before (`reads`); a citation made after the removal reads
    the record
    as it is now, even when it comes back with the same fingerprint."""

    identity_data_id: str
    record_type: str
    record_id: str
    content_sha256: str
    last_revision: int

    @classmethod
    def of(cls, description, record_id, served: int) -> "RemovedRecord":
        """The record as `description` holds it, before its removal.
        `served` is the last revision of its source that the ledger
        verified (`PublicationRow.verified_revision`): a citation pins a
        served record, so no citation pins one at a later revision. A
        removal in place of a failed attempt's saved revision (an erasure
        retry) holds a record last served at the revision before, or at the
        same revision when a reconcile of a served row failed. A re-add's
        failed attempt still carries the verified revision of the source's
        forgotten life, which no record of the new life was served at.
        Listing it is harmless: the forget's cascade removed every citation
        of that life before the re-add was admitted
        (Publisher.admit_readd waits for it), and a new citation needs a
        served row, so none pins a revision that old."""
        record_type = record_type_of(description, record_id)
        return cls(
            str(description.identity_data_id),
            record_type,
            record_id,
            record_digest(description, record_type, record_id),
            min(description.revision, served),
        )

    @classmethod
    def parse(cls, value: dict) -> "RemovedRecord":
        """One from a removal producer's configuration; KeyError, TypeError
        or ValueError when it is malformed."""
        found = cls(**value)
        if found.record_type not in REGISTRY or not isinstance(
            found.last_revision, int
        ):
            raise ValueError(value)
        return found

    def reads(self, item: SavedRecordInput) -> bool:
        """Whether a citation reads this record as it was before removal."""
        return (
            names_record(item, self.identity_data_id, self.record_id)
            and (item.record_type, item.content_sha256)
            == (self.record_type, self.content_sha256)
            and item.representation_revision <= self.last_revision
        )


def names_record(item: SavedRecordInput, identity_data_id: str, record_id) -> bool:
    """Whether a citation names this record key of this source. A key names
    one record in a source across every type, so a citation of the key
    reads whatever record the source holds under it; its fingerprint and
    pinned revision say which one it read (`RemovedRecord.reads`)."""
    return (str(item.identity_data_id), item.record_id) == (
        identity_data_id,
        record_id,
    )
