import dataclasses
import itertools
import json
from uuid import uuid4

import pytest

from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.storage import (
    TRANSITIONS,
    PublicationRow,
    RecordStore,
    Refusal,
    admissible,
)
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
    assert (await store.rows(source.dataset_id))[0].state == "pending"
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
        source,
        expected_revision=1,
        plan=dict(PUBLISH_INTENT),
        method="reconcile",
        origin="test",
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
        source,
        expected_revision=1,
        plan=dict(PUBLISH_INTENT),
        method="reconcile",
        origin="test",
    )
    with pytest.raises(IntentError, match="stale"):
        await store.complete(source, first)
    await store.complete(source, second)
    row = (await store.rows(source.dataset_id))[0]
    assert row.state == "current" and row.verified_revision == 1
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
        await store.begin(
            source, expected_revision=1, plan=dict(PUBLISH_INTENT), method="reconcile"
        )
    attempt = await store.begin(
        source, expected_revision=1, plan=plan, method="withdraw"
    )
    await store.complete(source, attempt, state="withdrawn")
    row = (await store.rows(source.dataset_id))[0]
    assert row.state == "withdrawn" and row.verified_revision == 1
    assert (await store.events(source.dataset_id))[0]["outcome"] == "withdrawn"
    with pytest.raises(IntentError, match="Withdrawn source"):
        await store.begin(
            source, expected_revision=1, plan=dict(PUBLISH_INTENT), method="reconcile"
        )
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
        if r.source == str(partial.identity_data_id)
    )
    assert row.state == "withdrawn" and row.verified_revision == 0


def tombstone_of(source):
    return Tombstone.of(source, forgotten_at="2026-10-23T00:00:00+00:00")


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
    plan = {
        "operation": "identity_forget",
        "original_data_id": "x",
        "edges": [
            dict(
                source="a",
                target="b",
                relation="is_part_of",
                refs=["r"],
                properties={"edge_text": "The first words of the document"},
            )
        ],
        "runtime_profile": {"cognee_version": "1.6.2"},
    }
    with pytest.raises(IntentError, match="durable forget plan"):
        await store.begin(source, expected_revision=1, plan={}, method="forget")
    attempt = await store.begin(source, expected_revision=1, plan=plan, method="forget")
    await store.fail(
        source, attempt, "forget_document", IntentError("injected", "quotes text")
    )
    with pytest.raises(IntentError, match="Retry the failed forget"):
        await store.begin(
            source, expected_revision=1, plan=dict(PUBLISH_INTENT), method="reconcile"
        )
    with pytest.raises(IntentError, match="Retry the failed forget"):
        await store.begin(source, expected_revision=1, plan=plan, method="withdraw")
    attempt = await store.begin(source, expected_revision=1, plan=plan, method="forget")
    with pytest.raises(ValueError, match="tombstone"):
        await store.complete(source, attempt, state="forgotten")
    await store.complete(
        source, attempt, state="forgotten", tombstone=tombstone_of(source)
    )
    row = (await store.rows(source.dataset_id))[0]
    assert row.state == "forgotten"
    assert row.revision == 1 and row.verified_revision == 1
    assert row.tombstone == tombstone_of(source)
    assert row.description is None
    assert "The controller" not in row.tombstone.model_dump_json()
    assert row.plan == {
        "operation": "identity_forget",
        "original_data_id": "x",
        "edges": [dict(source="a", target="b", relation="is_part_of", refs=["r"])],
        "origin": "runtime",
        "method": "forget",
    }
    (event,) = await store.events(source.dataset_id)
    assert event["outcome"] == "forgotten" and event["message"] is None
    assert event["reason_code"] == "injected" and event["stage"] == "forget_document"
    for method in ("reconcile", "withdraw", "forget", "replace"):
        with pytest.raises(IntentError, match="Forgotten source"):
            await store.begin(source, expected_revision=1, plan=plan, method=method)
    with pytest.raises(IntentError, match="next revision"):
        await store.begin(source, expected_revision=1, plan={}, method="publish")
    readded = source.model_copy(update={"revision": 2})
    attempt = await store.begin(readded, expected_revision=1, plan={})
    await store.complete(readded, attempt)
    row = (await store.rows(source.dataset_id))[0]
    assert row.state == "current"
    assert row.revision == 2 and row.verified_revision == 2

    # Any source can be forgotten: one whose first publication failed, and a
    # withdrawn one.
    for prior in ("failed", "withdrawn"):
        other = source.model_copy(update={"identity_data_id": uuid4()})
        attempt = await store.begin(other, expected_revision=0, plan={})
        if prior == "failed":
            await store.fail(other, attempt, "nodes", IntentError("x", "partial"))
        else:
            await store.complete(other, attempt)
            attempt = await store.begin(
                other,
                expected_revision=1,
                plan={"operation": "identity_withdraw"},
                method="withdraw",
            )
            await store.complete(other, attempt, state="withdrawn")
        attempt = await store.begin(
            other, expected_revision=1, plan=plan, method="forget"
        )
        await store.complete(
            other, attempt, state="forgotten", tombstone=tombstone_of(other)
        )
    with pytest.raises(IntentError, match="advance it through replacement"):
        await store.begin(
            source.model_copy(update={"revision": 3}), expected_revision=2, plan={}
        )


@pytest.mark.asyncio
async def test_a_forgotten_row_from_before_tombstones_is_refused(source_payload):
    """A forgotten row that still holds its description is an old format;
    rows() refuses it rather than read content a tombstone would drop."""
    from sqlalchemy import update

    from cognee_lab.identity.storage import Publication

    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = memory_store()
    await store.initialize()
    attempt = await store.begin(source, expected_revision=0, plan={})
    await store.complete(source, attempt)
    async with store.session_factory() as session:
        await session.execute(update(Publication).values(state="forgotten"))
        await session.commit()
    with pytest.raises(IntentError) as refused:
        await store.rows()
    assert refused.value.code == "forgotten_format"


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


PUBLISH_INTENT = {"operation": "identity_publish"}
WITHDRAW_INTENT = {"operation": "identity_withdraw"}
FORGET_INTENT = {"operation": "identity_forget"}


async def reach(store, source, row):
    """Drive a fresh store to one row state through the calls that make it."""
    if row == "none":
        return
    attempt = await store.begin(source, expected_revision=0, plan=dict(PUBLISH_INTENT))
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
        "withdrawn": ("withdraw", WITHDRAW_INTENT, "withdrawn"),
        "failed withdraw": ("withdraw", WITHDRAW_INTENT, None),
        "forgotten": ("forget", FORGET_INTENT, "forgotten"),
        "failed forget": ("forget", FORGET_INTENT, None),
    }[row]
    attempt = await store.begin(
        source, expected_revision=1, plan=dict(plan), method=method
    )
    if done == "forgotten":
        return await store.complete(
            source, attempt, state=done, tombstone=tombstone_of(source)
        )
    if done:
        return await store.complete(source, attempt, state=done)
    await store.fail(source, attempt, "stage", IntentError("x", "x"))


def caller_arguments(method, row):
    """The begin() arguments that the method's caller builds from one read of
    the row: a re-add or a new replacement takes the next revision, the rest
    the saved one, and a retry keeps the saved plan. It restates the callers'
    retry choice on its own on purpose, rather than reading resumed_by."""
    if row is None:
        operation = "publish" if method == "reconcile" else method
        return 1, 0, {"operation": f"identity_{operation}"}
    operation = row.operation
    if method == "publish":
        return row.revision + 1, row.revision, dict(PUBLISH_INTENT)
    retry = row.state == "failed" and operation == "identity_replace"
    if method == "replace" and not retry:
        plan = dict(
            operation="identity_replace",
            previous_description=(row.description or row.tombstone).model_dump_json(),
        )
        return row.revision + 1, row.revision, plan
    keep = {
        "reconcile": PUBLISH_INTENT,
        "replace": row.plan,
        "withdraw": (
            row.plan
            if row.state != "withdrawn" and operation == "identity_withdraw"
            else WITHDRAW_INTENT
        ),
        "forget": (
            row.plan
            if row.state == "failed" and operation == "identity_forget"
            else FORGET_INTENT
        ),
    }[method]
    return row.revision, row.revision, dict(keep)


# Each answer is written out rather than read from storage.py, so a changed
# refusal message fails here. None: begin() accepts the call.
LINEAGE = (
    "recovery_choice",
    "Reconcile a saved revision, or advance it through replacement",
)
PENDING_ROW = ("pending_attempt", "Inspect abandoned pending publication explicitly")
WITHDRAWN_ROW = (
    "withdrawn_source",
    "Withdrawn source requires explicit new publication intent",
)
FORGOTTEN_ROW = (
    "forgotten_source",
    "Forgotten source accepts only a new publication at the next revision",
)
RETRY_WITHDRAWAL = ("recovery_choice", "Retry the failed withdrawal explicitly")
RETRY_FORGET = ("recovery_choice", "Retry the failed forget explicitly")
RETRY_REPLACEMENT = (
    "recovery_choice",
    "Reconcile the saved replacement plan explicitly",
)
# Row state and saved plan -> what begin() answers each method's caller.
BEGIN_MATRIX = {
    "none": {
        "publish": None,
        "reconcile": None,
        "replace": ("source_missing", "Replacement requires an existing publication"),
        "withdraw": None,
        "forget": ("source_missing", "Forget requires an existing publication"),
    },
    "pending": dict.fromkeys(
        ("publish", "reconcile", "replace", "withdraw", "forget"), PENDING_ROW
    ),
    "current": {
        "publish": LINEAGE,
        "reconcile": None,
        "replace": None,
        "withdraw": None,
        "forget": None,
    },
    "withdrawn": {
        "publish": WITHDRAWN_ROW,
        "reconcile": WITHDRAWN_ROW,
        "replace": WITHDRAWN_ROW,
        "withdraw": None,
        "forget": None,
    },
    "forgotten": {
        "publish": None,
        "reconcile": FORGOTTEN_ROW,
        "replace": FORGOTTEN_ROW,
        "withdraw": FORGOTTEN_ROW,
        "forget": FORGOTTEN_ROW,
    },
    "failed publish": {
        "publish": LINEAGE,
        "reconcile": None,
        "replace": (
            "recovery_choice",
            "Advance a current revision through replacement",
        ),
        "withdraw": None,
        "forget": None,
    },
    "failed replace": {
        "publish": LINEAGE,
        "reconcile": RETRY_REPLACEMENT,
        "replace": None,
        "withdraw": RETRY_REPLACEMENT,
        "forget": RETRY_REPLACEMENT,
    },
    "failed withdraw": {
        "publish": LINEAGE,
        "reconcile": RETRY_WITHDRAWAL,
        "replace": RETRY_WITHDRAWAL,
        "withdraw": None,
        "forget": RETRY_WITHDRAWAL,
    },
    "failed forget": {
        "publish": LINEAGE,
        "reconcile": RETRY_FORGET,
        "replace": RETRY_FORGET,
        "withdraw": RETRY_FORGET,
        "forget": None,
    },
}


@pytest.mark.parametrize(
    "row,method,expected",
    [
        (row, method, answer)
        for row, answers in BEGIN_MATRIX.items()
        for method, answer in answers.items()
    ],
)
async def test_begin_transition_matrix(source_payload, row, method, expected):
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = memory_store()
    await store.initialize()
    await reach(store, source, row)
    saved = next(iter(await store.rows()), None)
    if saved is not None and saved.state != "forgotten":
        source = saved.description
    revision, expected_revision, plan = caller_arguments(method, saved)
    try:
        await store.begin(
            source.model_copy(update={"revision": revision}),
            expected_revision=expected_revision,
            plan=plan,
            method=method,
        )
        answer = None
    except IntentError as refused:
        answer = (refused.code, str(refused))
    assert answer == expected


def table_rows():
    """A saved row for each TRANSITIONS entry (None: no row), at revision 2."""
    for state, operation in TRANSITIONS:
        if state is None:
            yield None
            continue
        yield PublicationRow(
            dataset="d",
            source="s",
            revision=2,
            verified_revision=2,
            state=state,
            attempt="a",
            description=None,
            tombstone=None,
            plan={"operation": operation} if operation else {},
        )


@pytest.mark.parametrize("row", list(table_rows()))
def test_every_table_entry_answers_every_method(row, source_payload):
    """admissible() answers each (entry, method) pair with a Refusal or None,
    whatever the plan and revision, so no pair falls through the table."""
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    methods = ("publish", "reconcile", "replace", "withdraw", "forget")
    plans = [{}, *({"operation": f"identity_{m}"} for m in methods)]
    for method, plan, revision in itertools.product(methods, plans, range(1, 5)):
        described = source.model_copy(update={"revision": revision})
        answer = admissible(row, method, plan, described)
        assert answer is None or isinstance(answer, Refusal), (method, plan)


def test_step_one_entries_hold_the_next_revision():
    """Every entry for a saved row that admits a method at the next revision
    names the refusal for any other revision. The missing-row entry takes
    begin()'s final check, which refuses every revision but 1."""
    for (state, _), cell in TRANSITIONS.items():
        if state is not None and 1 in cell.admits.values():
            assert cell.sequence is not None, state
    assert set(TRANSITIONS[None, None].admits.values()) == {1}


def test_owned_entries_admit_only_their_owner():
    for (state, operation), cell in TRANSITIONS.items():
        if cell.owner:
            assert state == "failed" and operation
            assert dict(cell.admits) == {cell.owner: 0}


def test_unknown_row_state_is_refused_clearly(source_payload):
    row = next(r for r in table_rows() if r and r.state == "current")
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    with pytest.raises(IntentError, match="unknown"):
        admissible(dataclasses.replace(row, state="archived"), "reconcile", {}, source)
