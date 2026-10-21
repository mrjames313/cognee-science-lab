import json
from dataclasses import asdict
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from test_identity_occurrences import example
from cognee_lab.identity.captured_chunks import (
    FACT_TEXT,
    captured_facts,
    fact_chunks,
    retired_facts,
    retired_mentions,
)
from cognee_lab.identity.group_regrouping import (
    COMBINE_AFTER,
    COMBINE_REGROUPING,
    SPLIT_AFTER,
    SPLIT_REGROUPING,
    describe_combination,
    describe_split,
)
from cognee_lab.identity.captured_chunks import bind_chunks
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.multisource import fixture_id
from cognee_lab.identity.occurrence_fixture import BEFORE
from cognee_lab.identity.text_changes import (
    TextChange,
    admit_occurrence_regrouping,
    admit_remap,
    classify_regrouping,
)
from cognee_lab.identity.validation import (
    IntentError,
    fresh_mention_id,
    text_digest,
    validate_inputs,
)


def split(payload):
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=SPLIT_AFTER,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return old, chunk, describe_split(old, BEFORE, [chunk])


def admit(old, source, mapping=SPLIT_REGROUPING):
    return admit_remap(old, source, BEFORE, SPLIT_AFTER, occurrence_regrouping=mapping)


def rebuilt(intended, mutate):
    payload = intended.model_dump(mode="json")
    mutate(payload)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def test_reviewed_split_into_fresh_groups(source_payload):
    old, chunk, intended = split(source_payload)
    assert admit(old, intended).fresh == {"g04", "g05"}
    plan = classify_regrouping(old, intended, SPLIT_REGROUPING)
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
        assert group.entity_id == fresh_mention_id(old.identity_data_id, 2, key)
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
        checked, texts={"doc01": SPLIT_AFTER}, chunks={str(chunk.id): chunk}, graph=None
    )
    assert dict(captured_facts(intended)) == {"g05": FACT_TEXT}
    assert dict(retired_facts(intended)) == {"g01": FACT_TEXT}
    assert set(retired_mentions(intended)) == {"g01"}
    assert fact_chunks(intended, [chunk], group_key="g05") == [chunk]
    assert fact_chunks(intended, [chunk], group_key="g01") == []
    with pytest.raises(IntentError, match="prefix insertion"):
        admit_remap(old, intended, BEFORE, SPLIT_AFTER)
    change = TextChange(BEFORE, SPLIT_AFTER, occurrence_regrouping=SPLIT_REGROUPING)
    assert TextChange(**json.loads(json.dumps(asdict(change)))) == change


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        {"g01": [["g04", 0], ["g05", 0]]},
        {**SPLIT_REGROUPING, "extra": []},
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
    plan = classify_regrouping(old, intended, SPLIT_REGROUPING)
    assert plan.images["g01"] == [("g04", 0), ("g05", 0)]
    identity = {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]}
    nothing = classify_regrouping(old, old, identity)
    assert nothing.retired == nothing.fresh == frozenset()
    with pytest.raises(IntentError, match="regroups at least one"):
        admit_occurrence_regrouping(old, old, BEFORE, SPLIT_AFTER, identity)
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
        ("fresh_uuid_not_derived", "incompatible_group"),
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
    elif mutation == "fresh_uuid_not_derived":
        fresh = p["mention_groups"]["g04"]["entity_id"]
        mid = str(uuid4())
        p["entity_constructions"][mid] = p["entity_constructions"].pop(fresh)
        p["mention_groups"]["g04"]["entity_id"] = mid
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
            SPLIT_AFTER,
            {"g01": [0, 1], "g02": [0]},
            None,
            SPLIT_REGROUPING,
        )
    with pytest.raises(IntentError, match="Select one"):
        admit_remap(
            old,
            intended,
            BEFORE,
            SPLIT_AFTER,
            None,
            {"g01": [0, 1], "g02": [0]},
            SPLIT_REGROUPING,
        )


async def test_fresh_group_cannot_reuse_an_existing_graph_uuid(source_payload):
    old, _, intended = split(source_payload)

    class Graph:
        async def get_node(self, key):
            return {"id": key, "type": "Entity"}

    publisher = SimpleNamespace(graph=Graph())
    change = TextChange(BEFORE, SPLIT_AFTER, occurrence_regrouping=SPLIT_REGROUPING)
    with pytest.raises(IntentError, match="already exists"):
        await change.preflight(publisher, old, intended, {}, {}, None, retry=False)


def test_the_split_fixture_ids_follow_the_saved_source(source_payload):
    old, _, intended = split(source_payload)
    assert old.identity_data_id == UUID("718efce2-4251-5f6f-8318-417bb4dd3525")
    assert intended.mention_groups["g04"].entity_id == UUID(
        "b584813e-92d6-5eb4-b330-cbb0414866cf"
    )
    assert intended.mention_groups["g05"].entity_id == UUID(
        "2de73cc9-c7ff-5e83-b1e7-a189bedb1d37"
    )
    assert fixture_id("doc01:singleton") in map(str, intended.entity_constructions)


def combine(payload):
    _, split_chunk, split_source = split(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=COMBINE_AFTER,
        is_part_of=split_chunk.is_part_of,
    )
    return split_source, chunk, describe_combination(split_source, SPLIT_AFTER, [chunk])


def admit_combination(old, source, mapping=COMBINE_REGROUPING):
    return admit_remap(
        old, source, SPLIT_AFTER, COMBINE_AFTER, occurrence_regrouping=mapping
    )


async def test_reviewed_combination_into_one_fresh_group(source_payload):
    old, chunk, intended = combine(source_payload)
    assert admit_combination(old, intended).fresh == {"g06"}
    plan = classify_regrouping(old, intended, COMBINE_REGROUPING)
    assert (plan.continuing, plan.retired, plan.fresh) == (
        {"g02"},
        {"g04", "g05"},
        {"g06"},
    )
    assert list(intended.mention_groups) == ["g02", "g06"]
    assert intended.revision == 3
    g06 = intended.mention_groups["g06"]
    assert g06.entity_id == UUID("da6e1b3e-2e1e-570b-893d-9fe8996abe83")
    assert g06.entity_id == fresh_mention_id(old.identity_data_id, 3, "g06")
    assert [(o.start, o.end, o.text) for o in g06.occurrences] == [
        (49, 63, "the controller"),
        (109, 111, "it"),
    ]
    assert COMBINE_AFTER[109:111] == "it" and COMBINE_AFTER[49:63] == "the controller"
    recipe = intended.entity_constructions[g06.entity_id]
    assert recipe.name == "the controller; it"
    resolution = intended.mention_resolutions["r06"]
    assert resolution.group_ref == "g06" and resolution.status == "accepted"
    assert resolution.target_entity_id == UUID("8b4bff50-907b-56b6-bc80-3b0a7018714a")
    assert set(intended.mention_resolutions) == {"r02", "r06"}
    for key in ("g04", "g05"):
        assert old.mention_groups[key].entity_id not in intended.entity_constructions
    for rid in ("r04", "r05"):
        assert rid not in intended.mention_resolutions
    assert [(o.start, o.end) for o in intended.mention_groups["g02"].occurrences] == [
        (33, 39)
    ]
    assert intended.mention_groups["g02"].entity_id == (
        old.mention_groups["g02"].entity_id
    )
    assert "g01" not in intended.mention_groups
    assert g06.entity_id != UUID("233cb019-3986-5864-88bc-91f334a64372")
    assert dict(captured_facts(intended)) == {"g06": FACT_TEXT}
    assert dict(retired_facts(intended)) == {"g01": FACT_TEXT, "g05": FACT_TEXT}
    assert fact_chunks(intended, [chunk], group_key="g06") == [chunk]
    for gone in ("g01", "g05"):
        assert fact_chunks(intended, [chunk], group_key=gone) == []
    assert set(retired_mentions(intended)) == {"g01", "g04", "g05"}
    assert retired_mentions(intended)["g05"] == old.mention_groups["g05"].entity_id
    payload = intended.model_dump(mode="json")
    for assignment in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        assignment["input_refs"] = ["doc01"]
    checked = IdentitySource.model_validate_json(json.dumps(payload))
    await validate_inputs(
        checked,
        texts={"doc01": COMBINE_AFTER},
        chunks={str(chunk.id): chunk},
        graph=None,
    )
    change = TextChange(
        SPLIT_AFTER, COMBINE_AFTER, occurrence_regrouping=COMBINE_REGROUPING
    )
    assert TextChange(**json.loads(json.dumps(asdict(change)))) == change


def test_combination_needs_the_saved_split_output(source_payload):
    old, chunk, _ = split(source_payload)
    with pytest.raises(IntentError) as refusal:
        describe_combination(old, SPLIT_AFTER, [chunk])
    assert refusal.value.code == "fixture_scope"
    original, _, _ = example(source_payload)
    with pytest.raises(IntentError) as refusal:
        describe_combination(original, BEFORE, [chunk])
    assert refusal.value.code == "fixture_scope"
    unsplit = old.model_copy(update=dict(producers={}))
    with pytest.raises(IntentError) as refusal:
        describe_combination(unsplit, SPLIT_AFTER, [chunk])
    assert refusal.value.code == "fixture_scope"
    with pytest.raises(IntentError) as refusal:
        describe_combination(old, BEFORE, [chunk])
    assert refusal.value.code == "fixture_scope"


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        {"g04": [["g06", 0]], "g02": [["g02", 0]]},
        {**COMBINE_REGROUPING, "g01": []},
        {"g04": [["g06", 0]], "g05": [], "g02": [["g02", 0]]},
        {"g04": [["g06", 0]], "g05": [["g06", 0]], "g02": [["g02", 0]]},
        {"g04": [["g06", 0]], "g05": [["g05", 0]], "g02": [["g02", 0]]},
        {"g04": [["g06", 0], ["g06", 1]], "g05": [], "g02": [["g02", 0]]},
        {"g04": [["g06", 0]], "g05": [["g06", 2]], "g02": [["g02", 0]]},
        {"g04": [["g06", 0]], "g05": [["g06", 1]], "g02": [["g06", 0]]},
        {"g04": [["g06", 0]], "g05": [["g06", 1]], "g02": [["g02", 1]]},
        {"g04": [["g06", 0]], "g05": [["g07", 1]], "g02": [["g02", 0]]},
    ],
)
def test_combination_refuses_incomplete_or_false_maps(source_payload, mapping):
    old, _, intended = combine(source_payload)
    with pytest.raises(IntentError):
        admit_combination(old, intended, mapping)


def test_combination_refuses_a_map_that_swaps_occurrence_text(source_payload):
    old, _, intended = combine(source_payload)
    swapped = {"g04": [["g06", 1]], "g05": [["g06", 0]], "g02": [["g02", 0]]}
    with pytest.raises(IntentError, match="text differs"):
        admit_combination(old, intended, swapped)


def test_combination_refuses_a_group_that_takes_only_part_of_the_merge(source_payload):
    old, _, intended = combine(source_payload)

    def drop_it(p):
        p["mention_groups"]["g06"]["occurrences"].pop()

    with pytest.raises(IntentError, match="origin"):
        admit_combination(old, rebuilt(intended, drop_it))


@pytest.mark.parametrize(
    "mutation, code",
    [
        ("reuses_g04_uuid", "incompatible_group"),
        ("reuses_g05_uuid", "incompatible_group"),
        ("reuses_g01_uuid", "incompatible_group"),
        ("not_derived_uuid", "incompatible_group"),
        ("missing_resolution", "not_admitted"),
        ("reused_assignment_id", "not_admitted"),
        ("retired_recipe_kept", "not_admitted"),
        ("continuing_recipe", "not_admitted"),
        ("retarget_continuing", "not_admitted"),
        ("bad_span", "occurrence_changed"),
        ("variant_changed", "not_admitted"),
    ],
)
def test_combination_rejects_hidden_semantic_and_representation_changes(
    source_payload, mutation, code
):
    old, _, intended = combine(source_payload)
    g01 = "233cb019-3986-5864-88bc-91f334a64372"
    p = intended.model_dump(mode="json")
    fresh = p["mention_groups"]["g06"]["entity_id"]

    def adopt(mid):
        p["entity_constructions"][mid] = p["entity_constructions"].pop(fresh)
        p["mention_groups"]["g06"]["entity_id"] = mid

    if mutation == "reuses_g04_uuid":
        adopt(str(old.mention_groups["g04"].entity_id))
    elif mutation == "reuses_g05_uuid":
        adopt(str(old.mention_groups["g05"].entity_id))
    elif mutation == "reuses_g01_uuid":
        adopt(g01)
    elif mutation == "not_derived_uuid":
        adopt(str(uuid4()))
    elif mutation == "missing_resolution":
        p["mention_resolutions"].pop("r06")
    elif mutation == "reused_assignment_id":
        p["mention_resolutions"]["r04"] = p["mention_resolutions"].pop("r06")
    elif mutation == "retired_recipe_kept":
        retired = str(old.mention_groups["g05"].entity_id)
        p["entity_constructions"][retired] = dict(name="x", description="y")
    elif mutation == "continuing_recipe":
        p["entity_constructions"][p["mention_groups"]["g02"]["entity_id"]][
            "description"
        ] = "changed"
    elif mutation == "retarget_continuing":
        p["mention_resolutions"]["r02"] = dict(
            p["mention_resolutions"]["r06"], group_ref="g02"
        )
    elif mutation == "bad_span":
        p["mention_groups"]["g06"]["occurrences"][1]["start"] += 1
        p["mention_groups"]["g06"]["occurrences"][1]["end"] += 1
    else:
        p["variant_assignments"]["v01"]["applicability"] = dict(kind="corpus")
    changed = IdentitySource.model_validate_json(json.dumps(p))
    with pytest.raises(IntentError) as refusal:
        admit_combination(old, changed)
    assert refusal.value.code == code


def test_the_combination_fixture_ids_follow_the_saved_source(source_payload):
    old, _, intended = combine(source_payload)
    assert intended.mention_groups["g06"].entity_id == UUID(
        "da6e1b3e-2e1e-570b-893d-9fe8996abe83"
    )
    assert fixture_id("doc01:singleton") in map(str, intended.entity_constructions)


def resplit(combined, chunk, ids):
    p = combined.model_dump(mode="json")
    p["revision"] = 4
    p["inputs"]["doc01"]["text_sha256"] = text_digest(SPLIT_AFTER)
    resolution = p["mention_resolutions"].pop("r06")
    p["entity_constructions"].pop(p["mention_groups"].pop("g06")["entity_id"])
    plasma = SPLIT_AFTER.index("plasma")
    p["mention_groups"]["g02"]["occurrences"][0].update(
        start=plasma, end=plasma + len("plasma")
    )
    for key, rid, text, start in [
        ("g04", "r04", "the controller", SPLIT_AFTER.index("the controller")),
        ("g05", "r05", "it", SPLIT_AFTER.index(" it limits") + 1),
    ]:
        mid = str(ids[key])
        p["entity_constructions"][mid] = dict(name=text, description=key)
        p["mention_groups"][key] = dict(
            entity_id=mid,
            document_ref="doc01",
            occurrences=[dict(start=start, end=start + len(text), text=text)],
            chunk_refs=["chunk01"],
            input_refs=["doc01"],
            producer_ref="regrouping_review",
        )
        p["mention_resolutions"][rid] = dict(resolution, group_ref=key)
    bind_chunks(p, SPLIT_AFTER, [chunk])
    return IdentitySource.model_validate_json(json.dumps(p))


def test_a_returning_group_key_cannot_reuse_a_retired_uuid(source_payload):
    _, chunk, split_source = split(source_payload)
    _, _, combined = combine(source_payload)
    rev2 = {k: split_source.mention_groups[k].entity_id for k in ("g04", "g05")}
    again = {"g06": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}

    def admit_again(source):
        return admit_remap(
            combined, source, COMBINE_AFTER, SPLIT_AFTER, occurrence_regrouping=again
        )

    with pytest.raises(IntentError) as refusal:
        admit_again(resplit(combined, chunk, rev2))
    assert refusal.value.code == "incompatible_group"
    derived = {k: fresh_mention_id(combined.identity_data_id, 4, k) for k in rev2}
    admit_again(resplit(combined, chunk, derived))
    assert all(derived[k] != rev2[k] for k in rev2)
