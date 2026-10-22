import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from cognee_lab.identity.admission import GroupFate
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.replace import admit_replacement, retained_contributions
from cognee_lab.identity.revisions import corrected
from cognee_lab.identity.storage import RecordStore
from cognee_lab.identity.validation import (
    IntentError,
    fresh_entity_id,
    fresh_mention_id,
)

TEXT = (Path(__file__).parent / "fixtures/identity/source.txt").read_text()


class Graph:
    def __init__(self, present=()):
        self.present = set(present)

    async def get_node(self, key):
        return {"id": key} if key in self.present else None


async def correct(old, new, texts={"doc01": TEXT}, present=(), *, retry=False):
    """Admit a replacement without a text change through the entry point
    `replace` uses."""
    return await admit_replacement(Graph(present), old, new, texts, None, retry=retry)


async def test_captured_correction_preserves_occurrence_and_fact_anchors(
    source_payload,
):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    new = corrected(old)
    fate = await correct(old, new)
    assert fate == GroupFate({"g01"}, frozenset(), frozenset())
    assert new.revision == 2
    assert new.identity_data_id == old.identity_data_id
    assert new.mention_groups == old.mention_groups
    assert (
        new.mention_groups["g01"].producer_ref == old.mention_groups["g01"].producer_ref
    )
    assert new.mention_resolutions["r01"].producer_ref == "correction"
    assert new.producers["fixture"] == old.producers["fixture"]
    assert (
        new.mention_resolutions["r01"].target_entity_id
        != old.mention_resolutions["r01"].target_entity_id
    )
    assert new.mention_resolutions["r01"].target_entity_id == fresh_entity_id(
        old.identity_data_id, 2, "r01"
    )


async def test_a_correction_may_not_name_an_underived_new_entity_on_a_first_attempt(
    source_payload,
):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    payload = corrected(old).model_dump(mode="json")
    derived = payload["mention_resolutions"]["r01"]["target_entity_id"]
    other = str(uuid4())
    payload["entity_constructions"][other] = payload["entity_constructions"].pop(
        derived
    )
    payload["mention_resolutions"]["r01"]["target_entity_id"] = other
    payload["variant_assignments"]["v01"]["target_entity_id"] = other
    saved = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="derives from its source") as refused:
        await correct(old, saved)
    assert refused.value.code == "entity_uuid_not_derived"
    retried = await correct(old, saved, retry=True)
    assert retried.continuing == {"g01"}


def test_retirement_preserves_independent_payload_and_requires_its_owner(
    source_payload,
):
    from cognee.infrastructure.databases.provenance import make_source_ref_key
    from cognee_lab.identity.publish import identity_edges

    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    own = identity_edges(source)[-1][-1]
    foreign = dict(own, identity_data_id=str(uuid4()))
    refs = [
        make_source_ref_key(source.dataset_id, source.identity_data_id),
        make_source_ref_key(source.dataset_id, foreign["identity_data_id"]),
    ]
    assert retained_contributions(source, [own, foreign], [], refs) == [foreign]
    with pytest.raises(IntentError, match="no native owner"):
        retained_contributions(source, [own, foreign], [], refs[:1])


async def test_a_correction_may_not_name_a_new_entity_the_graph_already_holds(
    source_payload,
):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    new = corrected(old)
    present = {str(new.mention_resolutions["r01"].target_entity_id)}
    with pytest.raises(IntentError, match="already exists") as refused:
        await correct(old, new, present=present)
    assert refused.value.code == "entity_uuid_in_graph"
    retried = await correct(old, new, present=present, retry=True)
    assert retried.continuing == {"g01"}


async def test_a_correction_declines_changed_text_and_needs_a_rebuild_for_new_groups(
    source_payload,
):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    changed = deepcopy(source_payload)
    changed["revision"] = 2
    changed["inputs"]["doc01"]["text_sha256"] = "0" * 64
    new = IdentitySource.model_validate_json(json.dumps(changed))
    with pytest.raises(IntentError, match="fingerprints disagree") as refused:
        await correct(old, new)
    assert refused.value.code == "source_changed"
    with pytest.raises(IntentError, match="text is missing") as refused:
        await correct(old, new, texts={})
    assert refused.value.code == "source_changed"
    changed = deepcopy(source_payload)
    changed["revision"] = 2
    fresh = str(fresh_mention_id(old.identity_data_id, 2, "g03"))
    changed["entity_constructions"][fresh] = dict(name="HC", description="new group")
    changed["mention_groups"]["g03"] = dict(
        changed["mention_groups"]["g01"],
        entity_id=fresh,
        occurrences=[dict(start=19, end=21, text="HC")],
    )
    changed["mention_resolutions"]["r03"] = dict(
        changed["mention_resolutions"]["r01"], group_ref="g03"
    )
    new = IdentitySource.model_validate_json(json.dumps(changed))
    with pytest.raises(IntentError, match="requires a text change") as refused:
        await correct(old, new)
    assert refused.value.code == "rebuild_required"


async def test_saved_replacement_is_guarded_and_retried_without_new_intent(
    source_payload,
):
    source_payload["dataset_id"] = str(uuid4())
    for item in source_payload["inputs"].values():
        if "dataset_id" in item:
            item["dataset_id"] = source_payload["dataset_id"]
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    intended = corrected(old)
    store = RecordStore()
    await store.initialize()
    attempt = await store.begin(old, expected_revision=0, plan={})
    await store.complete(old, attempt)
    with pytest.raises(IntentError, match="replacement"):
        await store.begin(intended, expected_revision=1, plan={})
    attempt = await store.begin(
        intended,
        expected_revision=1,
        method="replace",
        plan={
            "operation": "identity_replace",
            "previous_description": old.model_dump_json(),
        },
    )
    row = (await store.rows(old.dataset_id))[0]
    assert (
        row["revision"] == 2
        and row["verified_revision"] == 1
        and row["state"] == "pending"
    )
    await store.assert_pending(intended, attempt)
    with pytest.raises(IntentError, match="pending intent"):
        await store.assert_pending(old, attempt)
    event = await store.fail(
        intended, attempt, "replace_saved", IntentError("injected", "stopped")
    )
    with pytest.raises(IntentError, match="retirement plan"):
        await store.begin(
            intended,
            expected_revision=2,
            method="replace",
            plan={"operation": "identity_replace"},
        )
    with pytest.raises(IntentError, match="replacement plan"):
        await store.begin(intended, expected_revision=2, method="reconcile", plan={})
    with pytest.raises(IntentError, match="Saved revision changed"):
        await store.begin(intended, expected_revision=1, method="replace", plan={})
    retry = await store.begin(
        intended, expected_revision=2, method="replace", plan=row["plan"]
    )
    await store.complete(intended, retry)
    row = (await store.rows(old.dataset_id))[0]
    assert (
        row["revision"] == row["verified_revision"] == 2 and row["state"] == "current"
    )
    incidents = await store.events(old.dataset_id)
    assert incidents[0]["recovery_event_id"] == event and incidents[0]["resolved_at"]


async def test_a_correction_may_not_move_an_occurrence_to_another_span_with_the_same_text(
    source_payload,
):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    payload = corrected(old).model_dump(mode="json")
    inside_limits = TEXT.index("limits") + 3
    assert TEXT[inside_limits : inside_limits + 2] == "it"
    payload["mention_groups"]["g01"]["occurrences"][1].update(
        start=inside_limits, end=inside_limits + 2
    )
    moved = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="keeps its start and end") as refused:
        await correct(old, moved)
    assert refused.value.code == "occurrence_moved"


async def test_a_correction_may_not_add_an_occurrence_without_a_rebuild(
    source_payload,
):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    payload = corrected(old).model_dump(mode="json")
    inside_limits = TEXT.index("limits") + 3
    payload["mention_groups"]["g01"]["occurrences"].append(
        dict(start=inside_limits, end=inside_limits + 2, text="it")
    )
    added = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="requires a text change") as refused:
        await correct(old, added)
    assert refused.value.code == "rebuild_required"


@pytest.mark.parametrize("listed", ["record", "group", "none"])
async def test_a_corpus_input_exempts_an_entity_only_when_a_record_lists_it(
    source_payload, listed
):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    payload = corrected(old).model_dump(mode="json")
    existing = str(uuid4())
    payload["entity_constructions"][existing] = dict(name="HC", description="known")
    payload["inputs"]["existing_Z"] = dict(
        source_payload["inputs"]["existing_A"], entity_id=existing
    )
    payload["variant_assignments"]["v02"] = dict(
        payload["variant_assignments"]["v01"],
        target_entity_id=existing,
        input_refs=["doc01", "existing_Z"] if listed == "record" else ["doc01"],
    )
    if listed == "group":
        # Input validation also checks a group's inputs, but only a decision
        # that names the Entity may exempt it from derivation.
        payload["mention_groups"]["g01"]["input_refs"].append("existing_Z")
    new = IdentitySource.model_validate_json(json.dumps(payload))
    if listed == "record":
        fate = await correct(old, new, present={existing})
        assert fate.continuing == {"g01"}
    else:
        with pytest.raises(IntentError, match="derives from its source") as refused:
            await correct(old, new)
        assert refused.value.code == "entity_uuid_not_derived"
