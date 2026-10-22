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
    require_root,
    retire_group,
    stamp_producer,
)
from .models import IdentitySource
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


def reinterpret(
    old, before, chunks, *, after, mention, key, rid, producer, backup=None
):
    """g01 retires. Fresh group `key` holds `mention` and the carried-over `it`.

    With a `backup` name, the group resolves to a new reusable Entity of that
    name. Its UUID derives from the resolution key `rid`. Without one, the
    group is unresolved.
    """
    require_root(old, before, {"g01", "g02"}, SCOPE)
    payload = begin_revision(old, after, REF, producer, POLICY)
    target = None
    if backup:
        target = fresh_entity_id(old.identity_data_id, payload["revision"], rid)
        payload["entity_constructions"][str(target)] = dict(
            name=backup, description="Captured reusable backup controller identity."
        )
    retire_group(payload, "g01")
    declare_group(
        payload,
        old,
        key,
        rid,
        f"{mention}; it",
        f"Captured replacement local reference group {key}.",
        [occurrence(after, mention), occurrence(after, "it", " it limits")],
        REF,
        status="accepted" if backup else "unresolved",
        target=target,
    )
    stamp_producer(payload, REF)
    bind_chunks(payload, after, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_new_entity(old, before, chunks):
    return reinterpret(
        old,
        before,
        chunks,
        after=NEW_ENTITY_AFTER,
        mention="the backup controller",
        key="g07",
        rid="r07",
        producer=REINTERPRET_ENTITY,
        backup="Backup controller",
    )


def describe_unresolved(old, before, chunks):
    return reinterpret(
        old,
        before,
        chunks,
        after=UNRESOLVED_AFTER,
        mention="A controller",
        key="g08",
        rid="r08",
        producer=REINTERPRET_UNRESOLVED,
    )


UNRESOLVED_QUERIES = {"helios_controller": "What does Helios controller limit?"}
ENTITY_QUERIES = {
    **UNRESOLVED_QUERIES,
    "backup_controller": "What does Backup controller limit?",
}
