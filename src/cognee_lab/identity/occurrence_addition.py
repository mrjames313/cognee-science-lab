"""Captured additions with explicit group continuity; no automatic Describe."""

import json

from .captured_chunks import ADDITION, bind_chunks
from .captured_text import BEFORE
from .models import IdentitySource
from .captured_revision import (
    begin_revision,
    declare_group,
    occurrence,
    require_root,
    stamp_producer,
)

FIRST = " During startup, the controller remains active.\n\n"
SECOND = "After calibration, the controller limits oscillations.\n"
BASE = BEFORE.rstrip("\n")
AFTER = BASE + FIRST + SECOND
# g01 keeps both occurrences and gains a third; g02 is unchanged; g03 is fresh.
ADDITION_MAP = {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]}


def describe_addition(old, before, chunks):
    require_root(
        old,
        before,
        set(ADDITION_MAP),
        "Occurrence addition requires doc01 of a fresh chunked-fixture",
    )
    payload = begin_revision(
        old,
        AFTER,
        "addition_review",
        ADDITION,
        "explicit-continuity-and-new-group-v1",
    )
    payload["mention_groups"]["g01"]["occurrences"].append(
        occurrence(AFTER, "the controller", "the controller remains")
    )
    # A separate local group deliberately has the same surface text. Its UUID
    # comes from a saved source, revision and group key, never the surface
    # name or offsets.
    declare_group(
        payload,
        old,
        "g03",
        "r03",
        "the controller",
        "Captured separate local reference group g03.",
        [occurrence(AFTER, "the controller", "the controller limits")],
        "addition_review",
        status="accepted",
        target=old.mention_resolutions["r01"].target_entity_id,
    )
    stamp_producer(payload, "addition_review")
    bind_chunks(payload, AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))
