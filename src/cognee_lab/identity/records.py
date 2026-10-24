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

An erasure removes a record that cites what a forget took away
(`RecordKind.removed`). A removed record is named with the fingerprint it
had and the last revision that held it (`RemovedRecord`), so a citation
made before the removal matches it and a later one does not.
"""

from collections.abc import Callable, Mapping
from typing import NamedTuple, get_args

from .models import IdentitySource, RecordType, SavedRecordInput, Unresolved
from .validation import object_digest

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


class RecordKind(NamedTuple):
    """Where one record type lives in a description (its attribute), the
    fields a citation of one of its records pins, whether one of its
    records is withheld, given its source's withheld decisions (entries of
    the withheld-decision set), its source and its key, and what an
    erasure leaves of a record (`removed`: the record after the removal, or
    None when the removal drops it), given its source, its key, the erased
    input keys and the removal producer's key."""

    field: str
    fingerprint: Callable[[IdentitySource, str], dict]
    held: Callable[[Mapping[str, object], IdentitySource, str], bool]
    removed: Callable[[IdentitySource, str, set[str], str], object | None]


def resolution_fingerprint(description, key) -> dict:
    record = description.mention_resolutions[key]
    group = description.mention_groups[record.group_ref]
    return dict(
        reviewed_decisions({key: record})[key], group_entity_id=str(group.entity_id)
    )


def variant_fingerprint(description, key) -> dict:
    return reviewed_decisions({key: description.variant_assignments[key]})[key]


def decision_held(entries, description, key) -> bool:
    """A decision is withheld when the withheld-decision set holds its key."""
    return key in entries


def without_erased(refs, erased, fallback):
    """Input refs with the erased keys stripped; the original document when
    nothing else remains."""
    return [k for k in refs if k not in erased] or [fallback]


def resolution_removed(description, key, erased, producer):
    """A removed resolution stays, unresolved in place under the removal
    producer, with the erased inputs stripped."""
    was = description.mention_resolutions[key]
    return Unresolved(
        group_ref=was.group_ref,
        status="unresolved",
        input_refs=without_erased(
            was.input_refs, erased, description.original_input_ref
        ),
        producer_ref=producer,
    )


def variant_removed(description, key, erased, producer):
    """A removed variant is dropped."""
    return None


REGISTRY: dict[str, RecordKind] = {
    "mention_resolution": RecordKind(
        "mention_resolutions", resolution_fingerprint, decision_held, resolution_removed
    ),
    "variant_assignment": RecordKind(
        "variant_assignments", variant_fingerprint, decision_held, variant_removed
    ),
}
if set(get_args(RecordType)) != REGISTRY.keys():
    raise TypeError("models.RecordType and records.REGISTRY name different types")


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
    the fingerprint it had, and the last revision of its source that held
    it. A citation reads it when it pins that fingerprint at that revision
    or before (`reads`); a citation made after the removal reads the record
    as it is now, even when it comes back with the same fingerprint."""

    identity_data_id: str
    record_type: str
    record_id: str
    content_sha256: str
    last_revision: int

    @classmethod
    def of(cls, description, record_id, *, in_place=False) -> "RemovedRecord":
        """The record as `description` holds it, before its removal. A
        removal in place of a failed attempt's saved revision (an erasure
        retry) removes a record no citation could pin at that revision,
        which was never served, so the last revision that held it for a
        citer is the one before."""
        record_type = record_type_of(description, record_id)
        return cls(
            str(description.identity_data_id),
            record_type,
            record_id,
            record_digest(description, record_type, record_id),
            description.revision - 1 if in_place else description.revision,
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
            str(item.identity_data_id),
            item.record_type,
            item.record_id,
            item.content_sha256,
        ) == (
            self.identity_data_id,
            self.record_type,
            self.record_id,
            self.content_sha256,
        ) and item.representation_revision <= self.last_revision
