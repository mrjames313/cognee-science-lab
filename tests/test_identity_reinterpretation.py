"""Changed interpretation: g01 retires and a fresh g03 takes the new meaning."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_identity_additions import addition
from test_identity_occurrences import example
from test_identity_revisions import Graph
from cognee_lab.identity.admission import GroupFate
from cognee_lab.identity.captured_chunks import (
    ADDED_FACT_TEXT,
    FACT_TEXT,
    captured_facts,
    fact_chunks,
    lineage_groups,
    retired_facts,
    retired_mentions,
)
from cognee_lab.identity.captured_text import BEFORE
from cognee_lab.identity.kind_change import describe_to_mention
from cognee_lab.identity.models import Accepted, IdentitySource, Unresolved
from cognee_lab.identity.reinterpretation import (
    NEW_ENTITY_AFTER,
    REINTERPRETATION_MAP,
    UNRESOLVED_AFTER,
    describe_new_entity,
    describe_unresolved,
)
from cognee_lab.identity.replace import admit_replacement
from cognee_lab.identity.text_changes import TextChange
from cognee_lab.identity.validation import (
    IntentError,
    fresh_entity_id,
    fresh_mention_id,
)

CASES = {
    "new_entity": (NEW_ENTITY_AFTER, describe_new_entity, "the backup controller", 97),
    "unresolved": (UNRESOLVED_AFTER, describe_unresolved, "A controller", 88),
}


def reinterpreted(payload, case):
    after, describe, mention, it_start = CASES[case]
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=after,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return old, chunk, describe(old, BEFORE, [chunk]), after, mention, it_start


async def admit_case(old, source, after, mapping=REINTERPRETATION_MAP, graph=None):
    change = TextChange(BEFORE, after, mapping)
    return await admit_replacement(
        graph or Graph(), old, source, {"doc01": after}, change, retry=False
    )


@pytest.mark.parametrize("case", CASES)
async def test_g01_retires_and_a_fresh_g03_takes_the_new_mention_and_it(
    source_payload, case
):
    old, chunk, intended, after, mention, it_start = reinterpreted(source_payload, case)
    fate = await admit_case(old, intended, after)
    assert fate == GroupFate(frozenset({"g02"}), frozenset({"g01"}), frozenset({"g03"}))
    g03 = intended.mention_groups["g03"]
    start = after.index(mention)
    assert [o.model_dump() for o in g03.occurrences] == [
        dict(start=start, end=start + len(mention), text=mention),
        dict(start=it_start, end=it_start + 2, text="it"),
    ]
    assert g03.entity_id == fresh_mention_id(old.identity_data_id, 2, "g03")
    assert "g01" not in intended.mention_groups and "r01" not in (
        intended.mention_resolutions
    )
    assert old.mention_groups["g01"].entity_id not in intended.entity_constructions
    plasma = intended.mention_groups["g02"], old.mention_groups["g02"]
    assert (plasma[0].entity_id, plasma[0].occurrences) == (
        plasma[1].entity_id,
        plasma[1].occurrences,
    )
    assert set(intended.variant_assignments) == {"v01"}
    assert intended.variant_assignments["v01"].target_entity_id == (
        old.variant_assignments["v01"].target_entity_id
    )
    assert dict(captured_facts(intended)) == {"g03": FACT_TEXT}
    assert dict(retired_facts(intended)) == {"g01": FACT_TEXT}
    assert set(retired_mentions(intended)) == {"g01"}
    assert fact_chunks(intended, [chunk], group_key="g03") == [chunk]


async def test_the_new_entity_is_a_derived_reusable_entity_that_r03_names(
    source_payload,
):
    old, _, intended, after, _, _ = reinterpreted(source_payload, "new_entity")
    backup = fresh_entity_id(old.identity_data_id, 2, "r03")
    decision = intended.mention_resolutions["r03"]
    assert isinstance(decision, Accepted) and decision.target_entity_id == backup
    assert intended.entity_constructions[backup].name == "Backup controller"
    assert backup not in old.entity_constructions
    helios = old.inputs["existing_A"].entity_id
    assert helios in intended.entity_constructions
    await admit_case(old, intended, after, graph=Graph())
    with pytest.raises(IntentError) as refused:
        await admit_case(old, intended, after, graph=Graph({str(backup)}))
    assert refused.value.code == "entity_uuid_in_graph"


async def test_the_unresolved_case_declares_no_new_entity(source_payload):
    old, _, intended, after, _, _ = reinterpreted(source_payload, "unresolved")
    assert isinstance(intended.mention_resolutions["r03"], Unresolved)
    assert set(intended.entity_constructions) - set(old.entity_constructions) == {
        intended.mention_groups["g03"].entity_id
    }
    await admit_case(old, intended, after)


async def test_a_new_entity_that_is_not_derived_is_refused(source_payload):
    old, _, intended, after, _, _ = reinterpreted(source_payload, "new_entity")
    payload = intended.model_dump(mode="json")
    derived = payload["mention_resolutions"]["r03"]["target_entity_id"]
    other = str(uuid4())
    payload["entity_constructions"][other] = payload["entity_constructions"].pop(
        derived
    )
    payload["mention_resolutions"]["r03"]["target_entity_id"] = other
    wrong = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="derives from its source") as refused:
        await admit_case(old, wrong, after)
    assert refused.value.code == "entity_uuid_not_derived"


async def test_a_retired_key_that_returns_with_a_new_meaning_is_refused(
    source_payload,
):
    old, _, intended, after, _, _ = reinterpreted(source_payload, "unresolved")
    payload = json.loads(
        intended.model_dump_json().replace('"g03"', '"g01"').replace('"r03"', '"r01"')
    )
    wrong = IdentitySource.model_validate_json(json.dumps(payload))
    mapping = {"g01": [None, ["g01", 1]], "g02": [["g02", 0]]}
    with pytest.raises(IntentError, match="key that no old group used") as refused:
        await admit_case(old, wrong, after, mapping)
    assert refused.value.code == "fresh_key_reused"


async def test_a_continuing_group_may_not_change_its_decision_in_a_text_edit(
    source_payload,
):
    old, _, intended, after, _, _ = reinterpreted(source_payload, "unresolved")
    payload = intended.model_dump(mode="json")
    fresh = payload["mention_groups"].pop("g03")
    payload["mention_resolutions"].pop("r03")
    payload["entity_constructions"].pop(fresh["entity_id"])
    kept = old.mention_groups["g01"].entity_id
    payload["entity_constructions"][str(kept)] = old.entity_constructions[
        kept
    ].model_dump()
    payload["mention_groups"]["g01"] = dict(
        fresh, entity_id=str(kept), occurrences=fresh["occurrences"][1:]
    )
    payload["mention_resolutions"]["r01"] = dict(
        group_ref="g01",
        status="unresolved",
        input_refs=["doc01"],
        producer_ref=fresh["producer_ref"],
        explanation=None,
    )
    changed = IdentitySource.model_validate_json(json.dumps(payload))
    mapping = {"g01": [None, ["g01", 0]], "g02": [["g02", 0]]}
    with pytest.raises(IntentError, match="keeps its reviewed decision") as refused:
        await admit_case(old, changed, after, mapping)
    assert refused.value.code == "continuing_decision_changed"


@pytest.mark.parametrize("describe", [describe_new_entity, describe_unresolved])
def test_the_describers_refuse_any_root_but_a_fresh_doc01(source_payload, describe):
    old, chunk, intended, _, _, _ = reinterpreted(source_payload, "new_entity")
    with pytest.raises(IntentError) as refused:
        describe(intended, NEW_ENTITY_AFTER, [chunk])
    assert refused.value.code == "fixture_scope"
    with pytest.raises(IntentError) as refused:
        describe(old, NEW_ENTITY_AFTER, [chunk])
    assert refused.value.code == "fixture_scope"


def test_a_group_key_reads_the_entry_of_the_sources_own_lineage(source_payload):
    facts = {}
    old, _, intended, _, _, _ = reinterpreted(source_payload, "new_entity")
    facts["reinterpretation"] = lineage_groups(intended)["g03"].fact
    _, chunk, added = addition(source_payload)
    facts["addition"] = lineage_groups(added)["g03"].fact
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=BEFORE,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    facts["kind change"] = lineage_groups(describe_to_mention(old, BEFORE, [chunk]))[
        "g03"
    ].fact
    assert facts == {
        "reinterpretation": FACT_TEXT,
        "addition": ADDED_FACT_TEXT,
        "kind change": None,
    }
    assert "g03" not in lineage_groups(old)
