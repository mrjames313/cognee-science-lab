import json
from copy import deepcopy
from uuid import uuid4

import pytest

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.replace import unchanged_occurrences, retained_contributions
from cognee_lab.identity.revisions import corrected
from cognee_lab.identity.storage import RecordStore
from cognee_lab.identity.validation import IntentError


def test_captured_correction_preserves_occurrence_and_fact_anchors(source_payload):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    new = corrected(old)
    unchanged_occurrences(old, new)
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


def test_replacement_declines_text_and_group_changes(source_payload):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    changed = deepcopy(source_payload)
    changed["inputs"]["doc01"]["text_sha256"] = "0" * 64
    new = IdentitySource.model_validate_json(json.dumps(changed))
    with pytest.raises(IntentError, match="remain unchanged"):
        unchanged_occurrences(old, new)
    changed = deepcopy(source_payload)
    changed["mention_groups"]["g01"]["entity_id"] = str(uuid4())
    changed["entity_constructions"][changed["mention_groups"]["g01"]["entity_id"]] = {
        "name": "other",
        "description": "new group",
    }
    new = IdentitySource.model_validate_json(json.dumps(changed))
    with pytest.raises(IntentError, match="remain unchanged"):
        unchanged_occurrences(old, new)


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
