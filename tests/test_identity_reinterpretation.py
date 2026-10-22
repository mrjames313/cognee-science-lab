"""Changed interpretation: g01 retires and a fresh group takes the new meaning."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_identity_occurrences import example
from test_identity_revisions import Graph
from cognee_lab.identity.admission import GroupFate
from cognee_lab.identity.captured_chunks import (
    FACT_TEXT,
    captured_facts,
    fact_chunks,
    retired_facts,
    retired_mentions,
)
from cognee_lab.identity.captured_text import BEFORE
from cognee_lab.identity.models import Accepted, IdentitySource, Unresolved
from cognee_lab.identity.reinterpretation import (
    ENTITY_MAP,
    NEW_ENTITY_AFTER,
    UNRESOLVED_AFTER,
    UNRESOLVED_MAP,
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
    "new_entity": SimpleNamespace(
        after=NEW_ENTITY_AFTER,
        describe=describe_new_entity,
        mention="the backup controller",
        key="g07",
        rid="r07",
        mapping=ENTITY_MAP,
    ),
    "unresolved": SimpleNamespace(
        after=UNRESOLVED_AFTER,
        describe=describe_unresolved,
        mention="A controller",
        key="g08",
        rid="r08",
        mapping=UNRESOLVED_MAP,
    ),
}


def reinterpreted(payload, case):
    """The old source, the chunk, the described source and the case's facts."""
    spec = CASES[case]
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=spec.after,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return SimpleNamespace(
        old=old,
        chunk=chunk,
        intended=spec.describe(old, BEFORE, [chunk]),
        **vars(spec),
    )


async def admit_case(r, source=None, mapping=None, graph=None):
    change = TextChange(BEFORE, r.after, mapping or r.mapping)
    return await admit_replacement(
        graph or Graph(),
        r.old,
        source or r.intended,
        {"doc01": r.after},
        change,
        retry=False,
    )


@pytest.mark.parametrize("case", CASES)
async def test_g01_retires_and_a_fresh_group_takes_the_new_mention_and_it(
    source_payload, case
):
    r = reinterpreted(source_payload, case)
    fate = await admit_case(r)
    assert fate == GroupFate(frozenset({"g02"}), frozenset({"g01"}), frozenset({r.key}))
    mention = r.after.index(r.mention)
    it = r.after.index(" it limits") + 1
    fresh = r.intended.mention_groups[r.key]
    assert [o.model_dump() for o in fresh.occurrences] == [
        dict(start=mention, end=mention + len(r.mention), text=r.mention),
        dict(start=it, end=it + 2, text="it"),
    ]
    assert fresh.entity_id == fresh_mention_id(r.old.identity_data_id, 2, r.key)
    assert "g01" not in r.intended.mention_groups and "r01" not in (
        r.intended.mention_resolutions
    )
    assert r.old.mention_groups["g01"].entity_id not in r.intended.entity_constructions
    plasma = r.intended.mention_groups["g02"], r.old.mention_groups["g02"]
    assert (plasma[0].entity_id, plasma[0].occurrences) == (
        plasma[1].entity_id,
        plasma[1].occurrences,
    )
    assert set(r.intended.variant_assignments) == {"v01"}
    assert r.intended.variant_assignments["v01"].target_entity_id == (
        r.old.variant_assignments["v01"].target_entity_id
    )
    assert dict(captured_facts(r.intended)) == {r.key: FACT_TEXT}
    assert dict(retired_facts(r.intended)) == {"g01": FACT_TEXT}
    assert set(retired_mentions(r.intended)) == {"g01"}
    assert fact_chunks(r.intended, [r.chunk], group_key=r.key) == [r.chunk]


async def test_the_new_entity_is_a_derived_reusable_entity_that_r07_names(
    source_payload,
):
    r = reinterpreted(source_payload, "new_entity")
    backup = fresh_entity_id(r.old.identity_data_id, 2, "r07")
    decision = r.intended.mention_resolutions["r07"]
    assert isinstance(decision, Accepted) and decision.target_entity_id == backup
    assert r.intended.entity_constructions[backup].name == "Backup controller"
    assert backup not in r.old.entity_constructions
    helios = r.old.inputs["existing_A"].entity_id
    assert helios in r.intended.entity_constructions
    await admit_case(r)
    with pytest.raises(IntentError) as refused:
        await admit_case(r, graph=Graph({str(backup)}))
    assert refused.value.code == "entity_uuid_in_graph"


async def test_the_unresolved_case_declares_no_new_entity(source_payload):
    r = reinterpreted(source_payload, "unresolved")
    assert isinstance(r.intended.mention_resolutions["r08"], Unresolved)
    assert set(r.intended.entity_constructions) - set(r.old.entity_constructions) == {
        r.intended.mention_groups["g08"].entity_id
    }
    await admit_case(r)


async def test_a_new_entity_that_is_not_derived_is_refused(source_payload):
    r = reinterpreted(source_payload, "new_entity")
    payload = r.intended.model_dump(mode="json")
    derived = payload["mention_resolutions"]["r07"]["target_entity_id"]
    other = str(uuid4())
    payload["entity_constructions"][other] = payload["entity_constructions"].pop(
        derived
    )
    payload["mention_resolutions"]["r07"]["target_entity_id"] = other
    wrong = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="derives from its source") as refused:
        await admit_case(r, wrong)
    assert refused.value.code == "entity_uuid_not_derived"


async def test_a_retired_key_that_returns_with_a_new_meaning_is_refused(
    source_payload,
):
    r = reinterpreted(source_payload, "unresolved")
    payload = json.loads(
        r.intended.model_dump_json().replace('"g08"', '"g01"').replace('"r08"', '"r01"')
    )
    wrong = IdentitySource.model_validate_json(json.dumps(payload))
    mapping = {"g01": [None, ["g01", 1]], "g02": [["g02", 0]]}
    with pytest.raises(IntentError, match="key that no old group used") as refused:
        await admit_case(r, wrong, mapping)
    assert refused.value.code == "fresh_key_reused"


async def test_a_continuing_group_may_not_change_its_decision_in_a_text_edit(
    source_payload,
):
    r = reinterpreted(source_payload, "unresolved")
    payload = r.intended.model_dump(mode="json")
    fresh = payload["mention_groups"].pop("g08")
    payload["mention_resolutions"].pop("r08")
    payload["entity_constructions"].pop(fresh["entity_id"])
    kept = r.old.mention_groups["g01"].entity_id
    payload["entity_constructions"][str(kept)] = r.old.entity_constructions[
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
        await admit_case(r, changed, mapping)
    assert refused.value.code == "continuing_decision_changed"


@pytest.mark.parametrize("describe", [describe_new_entity, describe_unresolved])
def test_the_describers_refuse_any_root_but_a_fresh_doc01(source_payload, describe):
    r = reinterpreted(source_payload, "new_entity")
    with pytest.raises(IntentError) as refused:
        describe(r.intended, NEW_ENTITY_AFTER, [r.chunk])
    assert refused.value.code == "fixture_scope"
    with pytest.raises(IntentError) as refused:
        describe(r.old, NEW_ENTITY_AFTER, [r.chunk])
    assert refused.value.code == "fixture_scope"
