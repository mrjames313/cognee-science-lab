import json

from .captured_chunks import COMBINATION, SPLIT, bind_chunks
from .models import IdentitySource
from .captured_revision import (
    begin_revision,
    declare_group,
    occurrence,
    require_root,
    retire_group,
    stamp_producer,
)
from .validation import IntentError

SPLIT_AFTER = (
    "Helios controller (HC) regulates plasma heating, and the controller adjusts "
    "coil current.\n\nDuring calibration, it limits oscillations.\n"
)
SPLIT_MAP = {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}
SPLIT_FRESH = (
    ("g04", "r04", "the controller", None),
    ("g05", "r05", "it", " it limits"),
)
COMBINE_AFTER = (
    "Helios controller (HC) regulates plasma heating, the controller adjusts coil "
    "current, and during calibration it limits oscillations.\n"
)
COMBINE_MAP = {
    "g04": [["g06", 0]],
    "g05": [["g06", 1]],
    "g02": [["g02", 0]],
}


def place_plasma(payload, after):
    start = after.index("plasma")
    payload["mention_groups"]["g02"]["occurrences"][0].update(
        start=start, end=start + len("plasma")
    )


def describe_split(old, before, chunks):
    require_root(
        old,
        before,
        set(SPLIT_MAP),
        "Group split requires doc01 of a fresh chunked-fixture",
    )
    ref = "regrouping_review"
    payload = begin_revision(
        old,
        SPLIT_AFTER,
        ref,
        SPLIT,
        "explicit-paragraph-regrouping-v1",
    )
    target = old.mention_resolutions["r01"].target_entity_id
    retire_group(payload, "g01")
    place_plasma(payload, SPLIT_AFTER)
    for key, rid, text, anchor in SPLIT_FRESH:
        declare_group(
            payload,
            old,
            key,
            rid,
            text,
            f"Captured separate local reference group {key}.",
            [occurrence(SPLIT_AFTER, text, anchor)],
            ref,
            status="accepted",
            target=target,
        )
    stamp_producer(payload, ref)
    bind_chunks(payload, SPLIT_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_combination(old, before, chunks):
    split = old.producers.get("regrouping_review")
    if (
        old.revision != 2
        or before != SPLIT_AFTER
        or set(old.mention_groups) != set(COMBINE_MAP)
        or split is None
        or split.implementation != SPLIT
    ):
        raise IntentError(
            "fixture_scope", "Group combination requires doc01 produced by split-group"
        )
    ref = "combination_review"
    payload = begin_revision(
        old,
        COMBINE_AFTER,
        ref,
        COMBINATION,
        "explicit-paragraph-combination-v1",
    )
    target = old.mention_resolutions["r04"].target_entity_id
    retire_group(payload, "g04")
    retire_group(payload, "g05")
    place_plasma(payload, COMBINE_AFTER)
    declare_group(
        payload,
        old,
        "g06",
        "r06",
        "the controller; it",
        "Captured paragraph-local reference group g06.",
        [
            occurrence(COMBINE_AFTER, "the controller"),
            occurrence(COMBINE_AFTER, "it", " it limits"),
        ],
        ref,
        status="accepted",
        target=target,
    )
    stamp_producer(payload, ref)
    bind_chunks(payload, COMBINE_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))
