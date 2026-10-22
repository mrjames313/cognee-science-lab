"""Captured changed interpretation on doc01: a text edit changes what g01 refers to.

A changed meaning in a text edit is a fresh group, never a continuing group
with a new decision. g01 retires, a fresh group (g07 or g08) holds the new
mention and the carried-over `it`, and the fact is generated again from it.
Each case has its own key, so a group key names one captured group. The
reviewer wrote both texts and both maps; the process infers nothing.
"""

import json

from .captured_chunks import REINTERPRET_ENTITY, REINTERPRET_UNRESOLVED, bind_chunks
from .captured_revision import (
    begin_revision,
    declare_group,
    occurrence,
    require_fresh_doc01,
    retire_group,
    stamp_producer,
)
from .models import Accepted, IdentitySource, Unresolved
from .validation import fresh_entity_id

NEW_ENTITY_AFTER = (
    "Helios controller (HC) regulates plasma heating, the backup controller adjusts "
    "coil current, and it limits oscillations.\n"
)
UNRESOLVED_AFTER = (
    "Helios controller (HC) regulates plasma heating. A controller adjusts "
    "coil current, and it limits oscillations.\n"
)
# g01's `the controller` is removed and g01's `it` moves to the fresh group,
# which also gains the new mention as an addition. g02 continues in place.
ENTITY_MAP = {"g01": [None, ["g07", 1]], "g02": [["g02", 0]]}
UNRESOLVED_MAP = {"g01": [None, ["g08", 1]], "g02": [["g02", 0]]}
SCOPE = "Changed interpretation requires doc01 of a fresh chunked-fixture"
POLICY = "explicit-changed-interpretation-v1"
REF = "interpretation_review"


def describe_new_entity(old, before, chunks):
    """g07 resolves to a new reusable Backup controller, derived from r07."""
    require_fresh_doc01(old, before, {"g01", "g02"}, SCOPE)
    payload = begin_revision(old, NEW_ENTITY_AFTER, REF, REINTERPRET_ENTITY, POLICY)
    backup = fresh_entity_id(old.identity_data_id, payload["revision"], "r07")
    payload["entity_constructions"][str(backup)] = dict(
        name="Backup controller",
        description="Captured reusable backup controller identity.",
    )
    retire_group(payload, "g01")
    declare_group(
        payload,
        old,
        "g07",
        "r07",
        "the backup controller; it",
        "Captured replacement local reference group g07.",
        [
            occurrence(NEW_ENTITY_AFTER, "the backup controller"),
            occurrence(NEW_ENTITY_AFTER, "it", " it limits"),
        ],
        Accepted(
            status="accepted",
            group_ref="g07",
            input_refs=[old.original_input_ref],
            producer_ref=REF,
            target_entity_id=backup,
        ),
        REF,
    )
    stamp_producer(payload, REF)
    bind_chunks(payload, NEW_ENTITY_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_unresolved(old, before, chunks):
    """g08 is unresolved: the reviewer does not say what `A controller` is."""
    require_fresh_doc01(old, before, {"g01", "g02"}, SCOPE)
    payload = begin_revision(old, UNRESOLVED_AFTER, REF, REINTERPRET_UNRESOLVED, POLICY)
    retire_group(payload, "g01")
    declare_group(
        payload,
        old,
        "g08",
        "r08",
        "A controller; it",
        "Captured replacement local reference group g08.",
        [
            occurrence(UNRESOLVED_AFTER, "A controller"),
            occurrence(UNRESOLVED_AFTER, "it", " it limits"),
        ],
        Unresolved(
            status="unresolved",
            group_ref="g08",
            input_refs=[old.original_input_ref],
            producer_ref=REF,
        ),
        REF,
    )
    stamp_producer(payload, REF)
    bind_chunks(payload, UNRESOLVED_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


UNRESOLVED_QUERIES = {"helios_controller": "What does Helios controller limit?"}
ENTITY_QUERIES = {
    **UNRESOLVED_QUERIES,
    "backup_controller": "What does Backup controller limit?",
}
