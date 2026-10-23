"""Saved records another source may cite, and what a citation pins.

One registry maps each citable record type to where its records live in a
description and what of a record a citation pins (its fingerprint).
Admission, validation and withholding read records only through it, so
another record type is one more entry. Today the citable records are
decisions: mention resolutions and variant assignments.

A fingerprint is a record's reviewed fields, never who reviewed it or what
it read (`ATTRIBUTION_FIELDS`): a re-confirm keeps it and an in-place
replacement changes it. A resolution's fingerprint also names its group's
mention UUID. Mention UUIDs are revision-scoped and never reused, so a
resolution key and group key that come back later with the same target
fingerprint differently.
"""

from collections.abc import Callable
from typing import NamedTuple

from .models import IdentitySource, SavedRecordInput
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
    """Where one record type lives in a description (its attribute) and the
    fields a citation of one of its records pins."""

    field: str
    fingerprint: Callable[[IdentitySource, str], dict]


def resolution_fingerprint(description, key) -> dict:
    record = description.mention_resolutions[key]
    group = description.mention_groups[record.group_ref]
    return dict(
        reviewed_decisions({key: record})[key], group_entity_id=str(group.entity_id)
    )


def variant_fingerprint(description, key) -> dict:
    return reviewed_decisions({key: description.variant_assignments[key]})[key]


REGISTRY: dict[str, RecordKind] = {
    "mention_resolution": RecordKind("mention_resolutions", resolution_fingerprint),
    "variant_assignment": RecordKind("variant_assignments", variant_fingerprint),
}


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
