import json

from .captured_chunks import bind_chunks
from .models import IdentitySource
from .occurrence_fixture import BEFORE
from .validation import IntentError, fresh_mention_id, text_digest

SPLIT_AFTER = (
    "Helios controller (HC) regulates plasma heating, and the controller adjusts "
    "coil current.\n\nDuring calibration, it limits oscillations.\n"
)
SPLIT_REGROUPING = {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}


def describe_split(old, before, chunks):
    if (
        old.revision != 1
        or before != BEFORE
        or set(old.mention_groups) != set(SPLIT_REGROUPING)
    ):
        raise IntentError(
            "fixture_scope", "Group split requires doc01 of a fresh chunked-fixture"
        )
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(SPLIT_AFTER)
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
    start = SPLIT_AFTER.index("plasma")
    payload["mention_groups"]["g02"]["occurrences"][0].update(
        start=start, end=start + len("plasma")
    )
    for key, rid, name, start in [
        ("g04", "r04", "the controller", SPLIT_AFTER.index("the controller")),
        ("g05", "r05", "it", SPLIT_AFTER.index(" it limits") + 1),
    ]:
        mid = str(fresh_mention_id(old.identity_data_id, payload["revision"], key))
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
    bind_chunks(payload, SPLIT_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


COMBINE_AFTER = (
    "Helios controller (HC) regulates plasma heating, the controller adjusts coil "
    "current, and during calibration it limits oscillations.\n"
)
COMBINE_REGROUPING = {
    "g04": [["g06", 0]],
    "g05": [["g06", 1]],
    "g02": [["g02", 0]],
}


def describe_combination(old, before, chunks):
    split = old.producers.get("regrouping_review")
    if (
        old.revision != 2
        or before != SPLIT_AFTER
        or set(old.mention_groups) != set(COMBINE_REGROUPING)
        or split is None
        or split.implementation != "stage6-captured-group-split"
    ):
        raise IntentError(
            "fixture_scope", "Group combination requires doc01 produced by split-group"
        )
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(
        COMBINE_AFTER
    )
    payload["producers"]["combination_review"] = dict(
        method="captured_fixture",
        implementation="stage6-captured-group-combination",
        version="0.1",
        configuration={"policy": "explicit-paragraph-combination-v1"},
        run_id=None,
    )
    resolution = old.mention_resolutions["r04"]
    for key, rid in [("g04", "r04"), ("g05", "r05")]:
        retired = payload["mention_groups"].pop(key)["entity_id"]
        payload["entity_constructions"].pop(retired)
        payload["mention_resolutions"].pop(rid)
    start = COMBINE_AFTER.index("plasma")
    payload["mention_groups"]["g02"]["occurrences"][0].update(
        start=start, end=start + len("plasma")
    )
    mid = str(fresh_mention_id(old.identity_data_id, payload["revision"], "g06"))
    payload["entity_constructions"][mid] = dict(
        name="the controller; it",
        description="Captured paragraph-local reference group g06.",
    )
    occurrences = [
        dict(start=start, end=start + len(text), text=text)
        for text, start in [
            ("the controller", COMBINE_AFTER.index("the controller")),
            ("it", COMBINE_AFTER.index(" it limits") + 1),
        ]
    ]
    payload["mention_groups"]["g06"] = dict(
        entity_id=mid,
        document_ref=old.original_input_ref,
        occurrences=occurrences,
        chunk_refs=["chunk01"],
        input_refs=[old.original_input_ref],
        producer_ref="combination_review",
    )
    payload["mention_resolutions"]["r06"] = dict(
        group_ref="g06",
        status="accepted",
        target_entity_id=str(resolution.target_entity_id),
        input_refs=list(resolution.input_refs),
        producer_ref="combination_review",
        explanation=None,
    )
    for record in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["producer_ref"] = "combination_review"
    bind_chunks(payload, COMBINE_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))
