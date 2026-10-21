import json
from dataclasses import asdict
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

import pytest

from test_identity_occurrences import example
from cognee_lab.identity.captured_chunks import (
    FACT_GROUPS,
    FACT_TEXT,
    captured_facts,
    fact_chunks,
)
from cognee_lab.identity.group_regrouping import AFTER, REGROUPING, describe_split
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.multisource import fixture_id
from cognee_lab.identity.occurrence_fixture import BEFORE
from cognee_lab.identity.text_changes import (
    TextChange,
    admit_occurrence_regrouping,
    admit_remap,
    classify_regrouping,
)
from cognee_lab.identity.validation import IntentError, validate_inputs


def split(payload):
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=AFTER,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return old, chunk, describe_split(old, BEFORE, [chunk])


def admit(old, source, mapping=REGROUPING):
    return admit_remap(old, source, BEFORE, AFTER, occurrence_regrouping=mapping)


def rebuilt(intended, mutate):
    payload = intended.model_dump(mode="json")
    mutate(payload)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def test_reviewed_split_into_fresh_groups(source_payload):
    old, chunk, intended = split(source_payload)
    plan = admit(old, intended)
    assert (plan.continuing, plan.retired, plan.fresh) == (
        {"g02"},
        {"g01"},
        {"g04", "g05"},
    )
    assert list(intended.mention_groups) == ["g02", "g04", "g05"]
    assert intended.mention_groups["g02"] == old.mention_groups["g02"].model_copy(
        update=dict(producer_ref="regrouping_review")
    )
    retired = old.mention_groups["g01"].entity_id
    assert retired not in intended.entity_constructions
    assert "r01" not in intended.mention_resolutions
    target = old.mention_resolutions["r01"].target_entity_id
    for key, rid in [("g04", "r04"), ("g05", "r05")]:
        group = intended.mention_groups[key]
        assert group.entity_id not in old.entity_constructions
        assert group.entity_id == uuid5(old.identity_data_id, f"mention:{key}")
        assert intended.mention_resolutions[rid].group_ref == key
        assert intended.mention_resolutions[rid].target_entity_id == target
    payload = intended.model_dump(mode="json")
    for assignment in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        assignment["input_refs"] = ["doc01"]
    checked = IdentitySource.model_validate_json(json.dumps(payload))
    await validate_inputs(
        checked, texts={"doc01": AFTER}, chunks={str(chunk.id): chunk}, graph=None
    )
    # The fact is regenerated for the group that holds it now; g04 gets none.
    assert dict(captured_facts(intended)) == dict.fromkeys(FACT_GROUPS, FACT_TEXT)
    assert fact_chunks(intended, [chunk], group_key="g05") == [chunk]
    assert fact_chunks(intended, [chunk], group_key="g01") == []
    with pytest.raises(IntentError, match="prefix insertion"):
        admit_remap(old, intended, BEFORE, AFTER)
    # The map is durable recovery intent, under its own named mode.
    change = TextChange(BEFORE, AFTER, occurrence_regrouping=REGROUPING)
    assert TextChange(**json.loads(json.dumps(asdict(change)))) == change


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        {"g01": [["g04", 0], ["g05", 0]]},
        {**REGROUPING, "extra": []},
        {"g01": [["g04", 0]], "g02": [["g02", 0]]},
        {"g01": [["g04", 0], ["g04", 0]], "g02": [["g02", 0]]},
        {"g01": [["g04", 0], ["g05", 1]], "g02": [["g02", 0]]},
        {"g01": [["g04", 0], ["g06", 0]], "g02": [["g02", 0]]},
        {"g01": [["g04", 0], ["g05", 0]], "g02": [["g04", 0]]},
        {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 1]]},
        {"g01": [["g04"], ["g05", 0]], "g02": [["g02", 0]]},
        {"g01": [["g04", 0, 0], ["g05", 0]], "g02": [["g02", 0]]},
        {"g01": [["g04", True], ["g05", 0]], "g02": [["g02", 0]]},
        {"g01": [[4, 0], ["g05", 0]], "g02": [["g02", 0]]},
        {"g01": [("g04", 0), ("g05", 0)], "g02": [["g02", 0]]},
        {"g01": "g04,g05", "g02": [["g02", 0]]},
        {"g01": [["g04", 0], ["g05", 0]], "g02": []},
    ],
)
def test_split_refuses_incomplete_or_false_maps(source_payload, mapping):
    old, _, intended = split(source_payload)
    with pytest.raises(IntentError):
        admit(old, intended, mapping)


def test_split_refuses_a_map_that_swaps_occurrence_text(source_payload):
    old, _, intended = split(source_payload)
    swapped = {"g01": [["g05", 0], ["g04", 0]], "g02": [["g02", 0]]}
    with pytest.raises(IntentError, match="text differs"):
        admit(old, intended, swapped)


def test_a_group_continues_only_when_it_alone_receives_its_occurrences(
    source_payload,
):
    old, _, intended = split(source_payload)
    plan = classify_regrouping(old, intended, REGROUPING)
    assert plan.images["g01"] == [("g04", 0), ("g05", 0)]
    # Identity map over the old shape: nothing retires, so nothing regroups.
    identity = {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]}
    nothing = classify_regrouping(old, old, identity)
    assert nothing.retired == nothing.fresh == frozenset()
    with pytest.raises(IntentError, match="regroups at least one"):
        admit_occurrence_regrouping(old, old, BEFORE, AFTER, identity)
    # g01 keeps its key but loses an occurrence to g05: it retires, g01 is fresh.
    kept_key = {"g01": [["g01", 0], ["g05", 0]], "g02": [["g02", 0]]}

    def reshape(p):
        p["mention_groups"]["g01"] = p["mention_groups"].pop("g04")
        p["mention_resolutions"]["r04"]["group_ref"] = "g01"

    plan = classify_regrouping(old, rebuilt(intended, reshape), kept_key)
    assert (plan.continuing, plan.retired, plan.fresh) == (
        {"g02"},
        {"g01"},
        {"g01", "g05"},
    )


@pytest.mark.parametrize(
    "mutation, code",
    [
        ("continuing_uuid", "occurrence_changed"),
        ("fresh_reuses_old_uuid", "incompatible_group"),
        ("missing_resolution", "not_admitted"),
        ("reused_assignment_id", "not_admitted"),
        ("retarget_continuing", "not_admitted"),
        ("continuing_recipe", "not_admitted"),
        ("retired_recipe_kept", "not_admitted"),
        ("bad_span", "occurrence_changed"),
        ("variant_changed", "not_admitted"),
    ],
)
def test_split_rejects_hidden_semantic_and_representation_changes(
    source_payload, mutation, code
):
    old, _, intended = split(source_payload)
    retired = str(old.mention_groups["g01"].entity_id)
    p = intended.model_dump(mode="json")
    if mutation == "continuing_uuid":
        mid = str(uuid4())
        old_id = p["mention_groups"]["g02"]["entity_id"]
        p["entity_constructions"][mid] = p["entity_constructions"].pop(old_id)
        p["mention_groups"]["g02"]["entity_id"] = mid
    elif mutation == "fresh_reuses_old_uuid":
        fresh = p["mention_groups"]["g04"]["entity_id"]
        p["entity_constructions"].pop(fresh)
        p["entity_constructions"][retired] = dict(name="x", description="y")
        p["mention_groups"]["g04"]["entity_id"] = retired
    elif mutation == "missing_resolution":
        p["mention_resolutions"].pop("r05")
    elif mutation == "reused_assignment_id":
        p["mention_resolutions"]["r01"] = p["mention_resolutions"].pop("r04")
    elif mutation == "retarget_continuing":
        p["mention_resolutions"]["r02"] = dict(
            p["mention_resolutions"]["r05"], group_ref="g02"
        )
        p["mention_resolutions"]["r05"]["group_ref"] = "g05"
    elif mutation == "continuing_recipe":
        p["entity_constructions"][p["mention_groups"]["g02"]["entity_id"]][
            "description"
        ] = "changed"
    elif mutation == "retired_recipe_kept":
        p["entity_constructions"][retired] = dict(name="x", description="y")
    elif mutation == "bad_span":
        p["mention_groups"]["g05"]["occurrences"][0]["start"] += 1
        p["mention_groups"]["g05"]["occurrences"][0]["end"] += 1
    else:
        p["variant_assignments"]["v01"]["applicability"] = dict(kind="corpus")
    changed = IdentitySource.model_validate_json(json.dumps(p))
    with pytest.raises(IntentError) as refusal:
        admit(old, changed)
    assert refusal.value.code == code


def test_regrouping_is_separate_from_the_other_modes(source_payload):
    old, _, intended = split(source_payload)
    with pytest.raises(IntentError, match="Select one"):
        admit_remap(
            old,
            intended,
            BEFORE,
            AFTER,
            {"g01": [0, 1], "g02": [0]},
            None,
            REGROUPING,
        )
    with pytest.raises(IntentError, match="Select one"):
        admit_remap(
            old, intended, BEFORE, AFTER, None, {"g01": [0, 1], "g02": [0]}, REGROUPING
        )


async def test_fresh_group_cannot_reuse_an_existing_graph_uuid(source_payload):
    old, _, intended = split(source_payload)

    class Graph:
        async def get_node(self, key):
            return {"id": key, "type": "Entity"}

    publisher = SimpleNamespace(graph=Graph())
    change = TextChange(BEFORE, AFTER, occurrence_regrouping=REGROUPING)
    with pytest.raises(IntentError, match="already exists"):
        await change.preflight(publisher, old, intended, {}, {}, None, retry=False)


def test_the_split_fixture_ids_follow_the_saved_source(source_payload):
    old, _, intended = split(source_payload)
    assert old.identity_data_id == UUID("718efce2-4251-5f6f-8318-417bb4dd3525")
    assert intended.mention_groups["g04"].entity_id == UUID(
        "7b93ccfe-fe9d-5126-b484-1b1c5eb39f6e"
    )
    assert intended.mention_groups["g05"].entity_id == UUID(
        "e6307cfe-012a-53c4-abf7-30dc1d8d904d"
    )
    assert fixture_id("doc01:singleton") in map(str, intended.entity_constructions)
