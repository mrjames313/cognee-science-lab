import json
from dataclasses import asdict
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_identity_occurrences import example
from cognee_lab.identity.captured_chunks import (
    ADDED_FACT_TEXT,
    FACT_TEXT,
    captured_facts,
    fact_chunks,
    retired_mentions,
)
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.multisource import fixture_id
from cognee_lab.identity.occurrence_addition import (
    AFTER,
    BEFORE,
    CONTINUITY,
    describe_addition,
)
from cognee_lab.identity.text_changes import TextChange, admit_remap
from cognee_lab.identity.validation import IntentError, validate_inputs


def addition(payload):
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=AFTER,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return old, chunk, describe_addition(old, BEFORE, [chunk])


def admit(old, source, mapping=CONTINUITY):
    return admit_remap(old, source, BEFORE, AFTER, occurrence_continuity=mapping)


async def test_reviewed_continuation_and_same_text_new_group(source_payload):
    old, chunk, intended = addition(source_payload)
    assert admit(old, intended).fresh == {"g03"}
    assert len(intended.mention_groups["g01"].occurrences) == 3
    assert (
        intended.mention_groups["g01"].entity_id == old.mention_groups["g01"].entity_id
    )
    g = intended.mention_groups["g03"]
    assert g.entity_id not in old.entity_constructions
    assert g.occurrences[0].text == intended.mention_groups["g01"].occurrences[-1].text
    assert (
        intended.mention_resolutions["r03"].target_entity_id
        == old.mention_resolutions["r01"].target_entity_id
    )
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
    assert fact_chunks(
        intended, [chunk], group_key="g03", fact_text=ADDED_FACT_TEXT
    ) == [chunk]
    assert dict(captured_facts(intended)) == {
        "g01": FACT_TEXT,
        "g03": ADDED_FACT_TEXT,
    }
    assert retired_mentions(intended) == {}
    with pytest.raises(IntentError, match="prefix insertion"):
        admit_remap(old, intended, BEFORE, AFTER)
    # Manifest is durable recovery intent, including its separately named mode.
    change = TextChange(BEFORE, AFTER, occurrence_continuity=CONTINUITY)
    assert TextChange(**json.loads(json.dumps(asdict(change)))) == change


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        {"g01": [0, 1]},
        {"g01": [0, 1], "g02": [0], "extra": []},
        {"g01": [0], "g02": [0]},
        {"g01": [0, 0], "g02": [0]},
        {"g01": [1, 0], "g02": [0]},
        {"g01": [True, 1], "g02": [0]},
        {"g01": [-1, 1], "g02": [0]},
        {"g01": [0, 3], "g02": [0]},
        {"g01": [1, 2], "g02": [0]},
        {"g01": "0,1", "g02": [0]},
    ],
)
def test_addition_refuses_incomplete_or_false_continuity(source_payload, mapping):
    old, _, intended = addition(source_payload)
    with pytest.raises(IntentError):
        admit(old, intended, mapping)


@pytest.mark.parametrize(
    "mutation",
    [
        "retarget",
        "recipe",
        "missing_resolution",
        "reused_assignment",
        "new_uuid_reused",
        "bad_span",
        "retire_group",
        "change_uuid",
    ],
)
def test_addition_rejects_hidden_semantic_and_representation_changes(
    source_payload, mutation
):
    old, _, intended = addition(source_payload)
    p = intended.model_dump(mode="json")
    if mutation == "retarget":
        p["mention_resolutions"]["r01"]["target_entity_id"] = p["variant_assignments"][
            "v01"
        ]["source_entity_id"]
    elif mutation == "recipe":
        p["entity_constructions"][str(old.mention_groups["g01"].entity_id)][
            "description"
        ] = "changed"
    elif mutation == "missing_resolution":
        p["mention_resolutions"].pop("r03")
    elif mutation == "reused_assignment":
        p["mention_resolutions"]["r01"] = p["mention_resolutions"].pop("r03")
    elif mutation == "new_uuid_reused":
        mid = p["mention_groups"]["g03"]["entity_id"]
        p["entity_constructions"].pop(mid)
        p["mention_groups"]["g03"]["entity_id"] = fixture_id("doc01:singleton")
    elif mutation == "bad_span":
        p["mention_groups"]["g03"]["occurrences"][0]["start"] += 1
        p["mention_groups"]["g03"]["occurrences"][0]["end"] += 1
    elif mutation == "retire_group":
        p["mention_groups"].pop("g02")
        p["mention_resolutions"].pop("r02")
    else:
        mid = str(uuid4())
        p["entity_constructions"][mid] = p["entity_constructions"].pop(
            p["mention_groups"]["g01"]["entity_id"]
        )
        p["mention_groups"]["g01"]["entity_id"] = mid
    changed = IdentitySource.model_validate_json(json.dumps(p))
    with pytest.raises(IntentError):
        admit(old, changed)


def test_additions_are_separate_from_removal_mode(source_payload):
    old, _, intended = addition(source_payload)
    with pytest.raises(IntentError, match="Select one"):
        admit_remap(
            old, intended, BEFORE, AFTER, {"g01": [0, 1], "g02": [0]}, CONTINUITY
        )
    p = intended.model_dump(mode="json")
    mid = p["mention_groups"].pop("g03")["entity_id"]
    p["entity_constructions"].pop(mid)
    p["mention_resolutions"].pop("r03")
    p["mention_groups"]["g01"]["occurrences"].pop()
    no_addition = IdentitySource.model_validate_json(json.dumps(p))
    with pytest.raises(IntentError, match="adds at least one"):
        admit(old, no_addition)


async def test_new_group_cannot_reuse_an_existing_graph_uuid(source_payload):
    old, _, intended = addition(source_payload)

    class Graph:
        async def get_node(self, key):
            return {"id": key, "type": "Entity"}

    publisher = SimpleNamespace(graph=Graph())
    change = TextChange(BEFORE, AFTER, occurrence_continuity=CONTINUITY)
    with pytest.raises(IntentError, match="already exists"):
        await change.preflight(publisher, old, intended, {}, {}, None, retry=False)
