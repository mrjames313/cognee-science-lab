import json

from .captured_chunks import COMBINATION, SPLIT, bind_chunks
from .captured_text import BEFORE
from .models import IdentitySource
from .validation import IntentError, fresh_mention_id, text_digest

SPLIT_AFTER = (
    "Helios controller (HC) regulates plasma heating, and the controller adjusts "
    "coil current.\n\nDuring calibration, it limits oscillations.\n"
)
SPLIT_REGROUPING = {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}
SPLIT_FRESH = (
    ("g04", "r04", "the controller", None),
    ("g05", "r05", "it", " it limits"),
)
COMBINE_AFTER = (
    "Helios controller (HC) regulates plasma heating, the controller adjusts coil "
    "current, and during calibration it limits oscillations.\n"
)
COMBINE_REGROUPING = {
    "g04": [["g06", 0]],
    "g05": [["g06", 1]],
    "g02": [["g02", 0]],
}


def begin_revision(old, after, ref, implementation, policy):
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(after)
    payload["producers"][ref] = dict(
        method="captured_fixture",
        implementation=implementation,
        version="0.1",
        configuration={"policy": policy},
        run_id=None,
    )
    return payload


def retire_group(payload, key):
    entity_id = payload["mention_groups"].pop(key)["entity_id"]
    payload["entity_constructions"].pop(entity_id)
    payload["mention_resolutions"] = {
        k: r for k, r in payload["mention_resolutions"].items() if r["group_ref"] != key
    }


def place_plasma(payload, after):
    start = after.index("plasma")
    payload["mention_groups"]["g02"]["occurrences"][0].update(
        start=start, end=start + len("plasma")
    )


def occurrence(after, text, anchor=None):
    anchor = anchor or text
    start = after.index(anchor) + anchor.index(text)
    return dict(start=start, end=start + len(text), text=text)


def declare_group(
    payload, old, key, rid, name, description, occurrences, resolution, ref
):
    entity_id = str(fresh_mention_id(old.identity_data_id, payload["revision"], key))
    payload["entity_constructions"][entity_id] = dict(
        name=name, description=description
    )
    payload["mention_groups"][key] = dict(
        entity_id=entity_id,
        document_ref=old.original_input_ref,
        occurrences=occurrences,
        chunk_refs=["chunk01"],
        input_refs=[old.original_input_ref],
        producer_ref=ref,
    )
    payload["mention_resolutions"][rid] = dict(
        group_ref=key,
        status="accepted",
        target_entity_id=str(resolution.target_entity_id),
        input_refs=list(resolution.input_refs),
        producer_ref=ref,
        explanation=None,
    )


def stamp_producer(payload, ref):
    for record in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["producer_ref"] = ref


def describe_split(old, before, chunks):
    if (
        old.revision != 1
        or before != BEFORE
        or set(old.mention_groups) != set(SPLIT_REGROUPING)
    ):
        raise IntentError(
            "fixture_scope", "Group split requires doc01 of a fresh chunked-fixture"
        )
    ref = "regrouping_review"
    payload = begin_revision(
        old,
        SPLIT_AFTER,
        ref,
        SPLIT,
        "explicit-paragraph-regrouping-v1",
    )
    resolution = old.mention_resolutions["r01"]
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
            resolution,
            ref,
        )
    stamp_producer(payload, ref)
    bind_chunks(payload, SPLIT_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_combination(old, before, chunks):
    split = old.producers.get("regrouping_review")
    if (
        old.revision != 2
        or before != SPLIT_AFTER
        or set(old.mention_groups) != set(COMBINE_REGROUPING)
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
    resolution = old.mention_resolutions["r04"]
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
        resolution,
        ref,
    )
    stamp_producer(payload, ref)
    bind_chunks(payload, COMBINE_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))
