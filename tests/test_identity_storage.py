import json
from uuid import uuid4

import pytest

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.storage import RecordStore
from cognee_lab.identity.validation import IntentError


@pytest.mark.asyncio
async def test_guard_failure_event_and_explicit_reconciliation(source_payload):
    source_payload["dataset_id"] = str(uuid4())
    for value in source_payload["inputs"].values():
        if "dataset_id" in value:
            value["dataset_id"] = source_payload["dataset_id"]
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = RecordStore()
    await store.initialize()
    first = await store.begin(source, expected_revision=0, plan={}, origin="test")
    assert (await store.rows(source.dataset_id))[0]["state"] == "pending"
    with pytest.raises(IntentError, match="writer"):
        await store.begin(source, expected_revision=1, plan={})
    event = await store.fail(
        source, first, "nodes", IntentError("injected", "test failure"), origin="test"
    )
    await store.fail(
        source, first, "nodes", IntentError("injected", "observed again"), origin="test"
    )
    assert len(await store.events(source.dataset_id)) == 1
    with pytest.raises(IntentError, match="revision changed"):
        await store.begin(source, expected_revision=0, plan={})
    second = await store.begin(
        source, expected_revision=1, plan={}, method="reconcile", origin="test"
    )
    same_event = await store.fail(
        source,
        second,
        "verification",
        IntentError("injected", "recovery failed"),
        origin="test",
    )
    assert same_event == event
    assert len(await store.events(source.dataset_id)) == 1
    second = await store.begin(
        source, expected_revision=1, plan={}, method="reconcile", origin="test"
    )
    with pytest.raises(IntentError, match="stale"):
        await store.complete(source, first)
    await store.complete(source, second)
    row = (await store.rows(source.dataset_id))[0]
    assert row["state"] == "current" and row["verified_revision"] == 1
    records = await store.events(source.dataset_id)
    assert records[0]["recovery_event_id"] == event
    assert records[0]["resolved_at"] is not None
    assert records[0]["recovery_attempts"][-1]["attempt_id"] == second


@pytest.mark.asyncio
async def test_withdrawal_guard_and_completion(source_payload):
    source_payload["dataset_id"] = str(uuid4())
    for item in source_payload["inputs"].values():
        if "dataset_id" in item:
            item["dataset_id"] = source_payload["dataset_id"]
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = RecordStore()
    await store.initialize()
    attempt = await store.begin(source, expected_revision=0, plan={})
    await store.complete(source, attempt)
    plan = {"operation": "identity_withdraw"}
    attempt = await store.begin(
        source, expected_revision=1, plan=plan, method="withdraw"
    )
    await store.fail(
        source, attempt, "withdraw_owners", IntentError("injected", "stopped")
    )
    with pytest.raises(IntentError, match="Retry the failed withdrawal"):
        await store.begin(source, expected_revision=1, plan={}, method="reconcile")
    attempt = await store.begin(
        source, expected_revision=1, plan=plan, method="withdraw"
    )
    await store.complete(source, attempt, state="withdrawn")
    row = (await store.rows(source.dataset_id))[0]
    assert row["state"] == "withdrawn" and row["verified_revision"] == 1
    assert (await store.events(source.dataset_id))[0]["outcome"] == "withdrawn"
    with pytest.raises(IntentError, match="Withdrawn source"):
        await store.begin(source, expected_revision=1, plan={}, method="reconcile")
    with pytest.raises(IntentError, match="Saved revision changed"):
        await store.begin(source, expected_revision=0, plan=plan, method="withdraw")

    # Retiring a publication that never completed must not claim that its
    # intended revision was ever successfully published.
    partial = source.model_copy(update={"identity_data_id": uuid4()})
    attempt = await store.begin(partial, expected_revision=0, plan={})
    await store.fail(partial, attempt, "nodes", IntentError("injected", "partial"))
    attempt = await store.begin(
        partial, expected_revision=1, plan=plan, method="withdraw"
    )
    await store.complete(partial, attempt, state="withdrawn")
    row = next(
        r
        for r in await store.rows(partial.dataset_id)
        if r["source"] == str(partial.identity_data_id)
    )
    assert row["state"] == "withdrawn" and row["verified_revision"] == 0
