"""Captured additions with explicit group continuity; no automatic Describe."""

import json

from .captured_chunks import bind_chunks
from .captured_text import BEFORE
from .models import IdentitySource
from .validation import IntentError, fresh_mention_id, text_digest

FIRST = " During startup, the controller remains active.\n\n"
SECOND = "After calibration, the controller limits oscillations.\n"
BASE = BEFORE.rstrip("\n")
AFTER = BASE + FIRST + SECOND
CONTINUITY = {"g01": [0, 1], "g02": [0]}


def describe_addition(old, before, chunks):
    if (
        old.revision != 1
        or before != BEFORE
        or set(old.mention_groups) != set(CONTINUITY)
    ):
        raise IntentError(
            "fixture_scope",
            "Occurrence addition requires doc01 of a fresh chunked-fixture",
        )
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(AFTER)
    payload["producers"]["addition_review"] = dict(
        method="captured_fixture",
        implementation="stage6-captured-occurrence-addition",
        version="0.1",
        configuration={"policy": "explicit-continuity-and-new-group-v1"},
        run_id=None,
    )
    start = len(BASE) + len(" During startup, ")
    payload["mention_groups"]["g01"]["occurrences"].append(
        dict(start=start, end=start + len("the controller"), text="the controller")
    )
    # A separate local group deliberately has the same surface text. Its UUID
    # comes from a saved source, revision and group key, never the surface name or offsets.
    mid = str(fresh_mention_id(old.identity_data_id, payload["revision"], "g03"))
    start = len(BASE) + len(FIRST) + len("After calibration, ")
    payload["entity_constructions"][mid] = dict(
        name="the controller",
        description="Captured separate local reference group g03.",
    )
    payload["mention_groups"]["g03"] = dict(
        entity_id=mid,
        document_ref=old.original_input_ref,
        occurrences=[
            dict(start=start, end=start + len("the controller"), text="the controller")
        ],
        chunk_refs=["chunk01"],
        input_refs=[old.original_input_ref],
        producer_ref="addition_review",
    )
    payload["mention_resolutions"]["r03"] = dict(
        group_ref="g03",
        status="accepted",
        target_entity_id=str(old.mention_resolutions["r01"].target_entity_id),
        input_refs=list(old.mention_resolutions["r01"].input_refs),
        producer_ref="addition_review",
        explanation=None,
    )
    for record in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["producer_ref"] = "addition_review"
    bind_chunks(payload, AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))
