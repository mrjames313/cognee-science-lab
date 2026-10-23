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


@pytest.mark.asyncio
async def test_forget_guard_recovery_and_readd_at_the_next_revision(source_payload):
    source_payload["dataset_id"] = str(uuid4())
    for item in source_payload["inputs"].values():
        if "dataset_id" in item:
            item["dataset_id"] = source_payload["dataset_id"]
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = RecordStore()
    await store.initialize()
    attempt = await store.begin(source, expected_revision=0, plan={})
    await store.complete(source, attempt)
    plan = {"operation": "identity_forget"}
    with pytest.raises(IntentError, match="durable forget plan"):
        await store.begin(source, expected_revision=1, plan={}, method="forget")
    attempt = await store.begin(source, expected_revision=1, plan=plan, method="forget")
    await store.fail(source, attempt, "forget_document", IntentError("injected", "x"))
    with pytest.raises(IntentError, match="Retry the failed forget"):
        await store.begin(source, expected_revision=1, plan={}, method="reconcile")
    with pytest.raises(IntentError, match="Retry the failed forget"):
        await store.begin(source, expected_revision=1, plan=plan, method="withdraw")
    attempt = await store.begin(source, expected_revision=1, plan=plan, method="forget")
    await store.complete(source, attempt, state="forgotten")
    row = (await store.rows(source.dataset_id))[0]
    assert row["state"] == "forgotten"
    assert row["revision"] == 1 and row["verified_revision"] == 1
    assert IdentitySource.model_validate_json(row["description"]) == source
    assert (await store.events(source.dataset_id))[0]["outcome"] == "forgotten"
    for method in ("reconcile", "withdraw", "forget", "replace"):
        with pytest.raises(IntentError, match="Forgotten source"):
            await store.begin(source, expected_revision=1, plan=plan, method=method)
    with pytest.raises(IntentError, match="next revision"):
        await store.begin(source, expected_revision=1, plan={}, method="publish")
    readded = source.model_copy(update={"revision": 2})
    attempt = await store.begin(readded, expected_revision=1, plan={})
    await store.complete(readded, attempt)
    row = (await store.rows(source.dataset_id))[0]
    assert row["state"] == "current"
    assert row["revision"] == 2 and row["verified_revision"] == 2

    # Forget takes a current source only: a failed first publication must be
    # reconciled or withdrawn, and a withdrawn source stays withdrawn.
    partial = source.model_copy(update={"identity_data_id": uuid4()})
    attempt = await store.begin(partial, expected_revision=0, plan={})
    await store.fail(partial, attempt, "nodes", IntentError("injected", "partial"))
    with pytest.raises(IntentError, match="Forget a current source"):
        await store.begin(partial, expected_revision=1, plan=plan, method="forget")
    attempt = await store.begin(
        partial,
        expected_revision=1,
        plan={"operation": "identity_withdraw"},
        method="withdraw",
    )
    await store.complete(partial, attempt, state="withdrawn")
    with pytest.raises(IntentError, match="Withdrawn source"):
        await store.begin(partial, expected_revision=1, plan=plan, method="forget")
    with pytest.raises(IntentError, match="advance it through replacement"):
        await store.begin(
            source.model_copy(update={"revision": 3}), expected_revision=2, plan={}
        )


def memory_store():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    return RecordStore(async_sessionmaker(engine, expire_on_commit=False))


async def free_reservation(store):
    """A person clears an abandoned writer's reservation by hand."""
    from sqlalchemy import update

    from cognee_lab.identity.storage import Writer

    async with store.session_factory() as session:
        await session.execute(update(Writer).values(owner=None))
        await session.commit()


PUBLISH = {"operation": "identity_publish"}
WITHDRAW = {"operation": "identity_withdraw"}
FORGET = {"operation": "identity_forget"}


async def reach(store, source, row):
    """Drive a fresh store to one row state through the calls that make it."""
    if row == "none":
        return
    attempt = await store.begin(source, expected_revision=0, plan=dict(PUBLISH))
    if row == "pending":
        return await free_reservation(store)
    if row == "failed publish":
        return await store.fail(source, attempt, "nodes", IntentError("x", "x"))
    await store.complete(source, attempt)
    if row == "current":
        return
    if row == "failed replace":
        nxt = source.model_copy(update={"revision": 2})
        plan = dict(
            operation="identity_replace", previous_description=source.model_dump_json()
        )
        attempt = await store.begin(
            nxt, expected_revision=1, plan=plan, method="replace"
        )
        return await store.fail(nxt, attempt, "replace_saved", IntentError("x", "x"))
    method, plan, done = {
        "withdrawn": ("withdraw", WITHDRAW, "withdrawn"),
        "failed withdraw": ("withdraw", WITHDRAW, None),
        "forgotten": ("forget", FORGET, "forgotten"),
        "failed forget": ("forget", FORGET, None),
    }[row]
    attempt = await store.begin(
        source, expected_revision=1, plan=dict(plan), method=method
    )
    if done:
        return await store.complete(source, attempt, state=done)
    await store.fail(source, attempt, "stage", IntentError("x", "x"))


def caller_arguments(method, row):
    """The begin() arguments that the method's caller builds from one read of
    the row: a re-add or a new replacement takes the next revision, the rest
    the saved one, and a retry keeps the saved plan."""
    if row is None:
        return 1, 0, {"operation": f"identity_{method}"}
    operation = row["plan"].get("operation")
    if method == "publish":
        return row["revision"] + 1, row["revision"], dict(PUBLISH)
    retry = row["state"] == "failed" and operation == "identity_replace"
    if method == "replace" and not retry:
        plan = dict(
            operation="identity_replace", previous_description=row["description"]
        )
        return row["revision"] + 1, row["revision"], plan
    keep = {
        "reconcile": PUBLISH,
        "replace": row["plan"],
        "withdraw": (
            row["plan"]
            if row["state"] != "withdrawn" and operation == "identity_withdraw"
            else WITHDRAW
        ),
        "forget": (
            row["plan"]
            if row["state"] == "failed" and operation == "identity_forget"
            else FORGET
        ),
    }[method]
    return row["revision"], row["revision"], dict(keep)


METHODS = ("publish", "reconcile", "replace", "withdraw", "forget")
# Row state and saved plan -> what begin() answers each method's caller.
TRANSITIONS = {
    "none": ("accepted", "accepted", "source_missing", "accepted", "source_missing"),
    "pending": ("pending_attempt",) * 5,
    "current": ("recovery_choice", "accepted", "accepted", "accepted", "accepted"),
    "withdrawn": ("withdrawn_source",) * 3 + ("accepted", "withdrawn_source"),
    "forgotten": ("accepted",) + ("forgotten_source",) * 4,
    "failed publish": (
        "recovery_choice",
        "accepted",
        "recovery_choice",
        "accepted",
        "forget_state",
    ),
    "failed replace": ("recovery_choice",) * 2
    + ("accepted",)
    + ("recovery_choice",) * 2,
    "failed withdraw": ("recovery_choice",) * 3 + ("accepted", "recovery_choice"),
    "failed forget": ("recovery_choice",) * 4 + ("accepted",),
}


@pytest.mark.parametrize(
    "row,method,expected",
    [
        (row, method, code)
        for row, codes in TRANSITIONS.items()
        for method, code in zip(METHODS, codes, strict=True)
    ],
)
async def test_begin_transition_matrix(source_payload, row, method, expected):
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = memory_store()
    await store.initialize()
    await reach(store, source, row)
    saved = next(iter(await store.rows()), None)
    if saved is not None:
        source = IdentitySource.model_validate_json(saved["description"])
    revision, expected_revision, plan = caller_arguments(method, saved)
    try:
        await store.begin(
            source.model_copy(update={"revision": revision}),
            expected_revision=expected_revision,
            plan=plan,
            method=method,
        )
        answer = "accepted"
    except IntentError as refused:
        answer = refused.code
    assert answer == expected
