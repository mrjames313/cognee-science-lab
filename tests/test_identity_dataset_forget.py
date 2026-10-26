"""The dataset forget's pure parts, without a store: the order readers
come in, the rows a later step sees, which step a fault stage fails, and
when a repair goes on past a waiting dependent."""

import json
from uuid import uuid4

from cognee_lab.identity.dataset_forget import (
    CLEANUP_FAULT,
    order,
    reads,
    repaired_later,
    simulated,
    step_fault,
)
from cognee_lab.identity.retirement import retired_sources
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
