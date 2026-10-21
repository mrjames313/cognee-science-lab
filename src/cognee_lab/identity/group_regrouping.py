"""Captured group split with explicit review; no automatic Describe."""

import json
from .captured_chunks import bind_chunks, fresh_mention_id
from .models import IdentitySource
from .occurrence_fixture import BEFORE
from .validation import IntentError, text_digest

AFTER = (
    "Helios controller (HC) regulates plasma heating, and the controller adjusts "
    "coil current.\n\nDuring calibration, it limits oscillations.\n"
)
# Each old occurrence, in order, maps to its [new group, new index] pair.
REGROUPING = {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}


def describe_split(old, before, chunks):
    if (
        old.revision != 1
        or before != BEFORE
        or set(old.mention_groups) != set(REGROUPING)
    ):
        raise IntentError(
            "fixture_scope", "Group split requires doc01 of a fresh chunked-fixture"
        )
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(AFTER)
    payload["producers"]["regrouping_review"] = dict(
        method="captured_fixture",
        implementation="stage6-captured-group-split",
        version="0.1",
        configuration={"policy": "explicit-paragraph-regrouping-v1"},
        run_id=None,
    )
    resolution = old.mention_resolutions["r01"]
    retired = payload["mention_groups"].pop("g01")["entity_id"]
    payload["entity_constructions"].pop(retired)
    payload["mention_resolutions"].pop("r01")
    start = AFTER.index("plasma")
    payload["mention_groups"]["g02"]["occurrences"][0].update(
        start=start, end=start + len("plasma")
    )
    for key, rid, name, start in [
        ("g04", "r04", "the controller", AFTER.index("the controller")),
        ("g05", "r05", "it", AFTER.index(" it limits") + 1),
    ]:
        mid = str(fresh_mention_id(old.identity_data_id, key))
        payload["entity_constructions"][mid] = dict(
            name=name, description=f"Captured separate local reference group {key}."
        )
        payload["mention_groups"][key] = dict(
            entity_id=mid,
            document_ref=old.original_input_ref,
            occurrences=[dict(start=start, end=start + len(name), text=name)],
            chunk_refs=["chunk01"],
            input_refs=[old.original_input_ref],
            producer_ref="regrouping_review",
        )
        payload["mention_resolutions"][rid] = dict(
            group_ref=key,
            status="accepted",
            target_entity_id=str(resolution.target_entity_id),
            input_refs=list(resolution.input_refs),
            producer_ref="regrouping_review",
            explanation=None,
        )
    for record in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["producer_ref"] = "regrouping_review"
    bind_chunks(payload, AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))
