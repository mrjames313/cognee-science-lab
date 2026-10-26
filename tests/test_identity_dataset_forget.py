"""The dataset forget without Cognee's stores: the order readers come in,
the rows a later step sees, which step a fault stage fails, when a repair
goes on past a waiting dependent, and, with a fake forget, where a
confirmed run stops."""

import json
from uuid import uuid4

import pytest

from cognee_lab.identity.dataset_forget import (
    CLEANUP_FAULT,
    order,
    reads,
    repaired_later,
    simulated,
    step_fault,
)
from cognee_lab.identity.retirement import retired_sources
from cognee_lab.identity.validation import IntentError
from test_identity_forget import reader_of, row_of, source_of


def builder_of(payload, entity, *, cites=None):
    """Another source that builds `entity` and, given `cites`, reads that
    Entity as a corpus input."""
    source = reader_of(payload, entity_id=cites) if cites else reader_of(payload)
    changed = json.loads(source.model_dump_json())
    changed["entity_constructions"][str(entity)] = dict(
        name=f"built {entity}", description="Built by this source."
    )
    return source_of(changed)


def test_readers_come_before_what_they_read(source_payload):
    doc01 = row_of(source_of(source_payload))
    by_text = row_of(reader_of(source_payload, text=True))
    unrelated = row_of(reader_of(source_payload))
    assert reads(by_text, doc01) and not reads(doc01, by_text)
    ordered = order([doc01, unrelated, by_text])
    assert ordered.index(by_text) < ordered.index(doc01)
    assert set(r.source for r in ordered) == {
        doc01.source,
        by_text.source,
        unrelated.source,
    }


def test_an_entity_the_reader_builds_itself_is_not_a_read(source_payload):
    """doc01 cites the borrowed controller and builds it too, so another
    builder of it is not what doc01 reads."""
    doc01 = source_of(source_payload)
    controller = next(
        i.entity_id for i in doc01.inputs.values() if i.kind == "corpus_object"
    )
    other = row_of(builder_of(source_payload, controller))
    assert not reads(row_of(doc01), other)


def test_a_cycle_is_broken_by_identity(source_payload):
    a, b = uuid4(), uuid4()
    first = row_of(builder_of(source_payload, a, cites=b))
    second = row_of(builder_of(source_payload, b, cites=a))
    assert reads(first, second) and reads(second, first)
    ordered = order([second, first])
    assert [r.source for r in ordered] == sorted([first.source, second.source])


def test_a_later_step_sees_the_earlier_ones_forgotten(source_payload):
    doc01 = row_of(source_of(source_payload))
    reader = row_of(reader_of(source_payload, text=True))
    later = simulated([doc01, reader], {reader.source})
    assert [r.state for r in later] == ["current", "forgotten"]
    assert later[1].description is None
    assert (reader.dataset, reader.source) in retired_sources(later)


def test_a_fault_stage_fails_the_first_or_last_step():
    assert [step_fault("first:forget_identity", n, 3) for n in range(3)] == [
        "forget_identity",
        None,
        None,
    ]
    assert [step_fault("last:forget_document", n, 3) for n in range(3)] == [
        None,
        None,
        "forget_document",
    ]
    assert step_fault(CLEANUP_FAULT, 0, 3) is None
    assert step_fault(None, 0, 3) is None


def outcome(*waiting, code="dependent_unfinished"):
    return dict(dependents_waiting=list(waiting), dependents_failed=dict(code=code))


def test_a_repair_goes_on_past_a_dependent_a_later_step_erases():
    gone = dict(identity_data_id="b", missing=["chunks"])
    pending = dict(identity_data_id="b", missing=None)
    assert repaired_later(outcome(gone), {"b"})
    assert not repaired_later(outcome(gone), {"c"})
    assert not repaired_later(outcome(pending), {"b"})


def test_a_repair_stops_at_a_removal_that_raised():
    """A removal revision write that raises leaves nothing waiting, or a
    waiting list beside another code: neither is a repair."""
    gone = dict(identity_data_id="b", missing=["chunks"])
    assert not repaired_later(outcome(code="verify_survivor"), {"b"})
    assert not repaired_later(outcome(), {"b"})
    assert not repaired_later(outcome(gone, code="injected_failure"), {"b"})


async def test_a_simulated_forget_reads_as_a_real_one(source_payload):
    """`simulated` stands in for the row a forget leaves, for the impact a
    later step sees: it must agree with a real forgotten row on every field
    that impact reads."""
    from cognee_lab.identity.models import Tombstone
    from test_identity_storage import memory_store

    source = source_of(source_payload)
    store = memory_store()
    await store.initialize()
    attempt = await store.begin(source, expected_revision=0, plan={})
    await store.complete(source, attempt)
    (saved,) = await store.rows()
    doc = source.inputs[source.original_input_ref]
    plan = dict(operation="identity_forget", original_data_id=str(doc.data_id))
    attempt = await store.begin(source, expected_revision=1, plan=plan, method="forget")
    tombstone = Tombstone.of(source, forgotten_at="now")
    await store.complete(source, attempt, state="forgotten", tombstone=tombstone)
    (real,) = await store.rows()
    (fake,) = simulated([saved], {saved.source})
    assert (fake.state, fake.description, fake.is_retired) == (
        real.state,
        real.description,
        real.is_retired,
    )
    assert retired_sources([fake]) == retired_sources([real])


def ledger(*sources):
    """Saved rows a fake forget turns into tombstones."""
    from types import SimpleNamespace

    return [
        SimpleNamespace(
            source=s, state="current", revision=1, tombstone=None, description=s
        )
        for s in sources
    ]


SEED, LATE = str(uuid4()), str(uuid4())


def faked(monkeypatch, rows, outcomes, present):
    """A publisher over `rows`, a dry run that lists each as a step and the
    seed as other Data, and a forget that returns the next of `outcomes`."""
    from types import SimpleNamespace

    from cognee.modules.users import methods

    from cognee_lab.identity import dataset_forget, forget

    report = dict(
        pending=[],
        token="t",
        dataset_id=str(uuid4()),
        sources=[
            dict(label=r.source, identity_data_id=r.source, order=n)
            for n, r in enumerate(rows)
        ],
        other_data=[dict(data_id=SEED, name="seed")],
        orphan_name_points=[],
    )
    called, deleted = [], []

    async def dry_run(publisher, root):
        return report

    async def forget_one(publisher, selected, **_):
        called.append(selected)
        row = next(r for r in rows if r.source == selected)
        row.state, row.tombstone = "forgotten", SimpleNamespace()
        return dict(dependents_revised=[], **outcomes.pop(0))

    async def nothing(*_args, **_kwargs):
        return {}

    async def deleting(dataset, data_id, locations, user):
        deleted.append(str(data_id))
        present.pop(str(data_id), None)

    async def listing(dataset):
        return present

    async def rows_now(dataset=None):
        return list(rows)

    monkeypatch.setattr(dataset_forget, "dry_run", dry_run)
    monkeypatch.setattr(dataset_forget, "plan_for", nothing)
    monkeypatch.setattr(
        dataset_forget, "impact", lambda *_: SimpleNamespace(token="step")
    )
    monkeypatch.setattr(dataset_forget, "unfinished", lambda *_: [])
    monkeypatch.setattr(dataset_forget, "lab_data", lambda rows: set())
    monkeypatch.setattr(dataset_forget, "stored_files", nothing)
    monkeypatch.setattr(dataset_forget, "delete_data", deleting)
    monkeypatch.setattr(dataset_forget, "dataset_data", listing)
    monkeypatch.setattr(dataset_forget, "sweep_orphans", lambda *_: nothing())
    monkeypatch.setattr(forget, "forget", forget_one)
    monkeypatch.setattr(methods, "get_default_user", nothing)
    publisher = SimpleNamespace(records=SimpleNamespace(rows=rows_now))
    return publisher, called, deleted


async def test_a_dataset_forget_stops_at_a_removal_that_raised(monkeypatch):
    from cognee_lab.identity.dataset_forget import forget_dataset

    rows = ledger("a", "b")
    failure = dict(code="verify_survivor", message="lost")
    outcomes = [dict(dependents_waiting=[], dependents_failed=failure)]
    publisher, called, deleted = faked(monkeypatch, rows, outcomes, {})
    result = await forget_dataset(publisher, None, confirm="t")
    assert called == ["a"] and deleted == []
    assert result["dependents_failed"] == failure
    assert [f["identity_data_id"] for f in result["forgotten"]] == ["a"]


async def test_a_dataset_forget_refuses_data_its_dry_run_did_not_list(monkeypatch):
    from cognee_lab.identity.dataset_forget import forget_dataset

    rows = ledger("a")
    outcomes = [dict(dependents_waiting=[], dependents_failed=None)]
    present = {SEED: "seed", LATE: "added after the dry run"}
    publisher, called, deleted = faked(monkeypatch, rows, outcomes, present)
    with pytest.raises(IntentError) as refused:
        await forget_dataset(publisher, None, confirm="t")
    assert refused.value.code == "impact_changed"
    assert refused.value.details["unlisted_data"] == [LATE]
    assert called == ["a"] and deleted == [SEED]
