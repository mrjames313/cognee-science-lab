"""The erasure cascade on rows that a failed attempt or a retired upstream
leaves: what the cascade still removes, and that it converges."""

import dataclasses

import pytest

from cascade_worlds import cascade_rows
from chain_worlds import identity, row_of
from cognee_lab.identity import erasure
from cognee_lab.identity.erasure_rules import check_retry_chain, erasures_of
from cognee_lab.identity.retirement import source_ids
from cognee_lab.identity.validation import IntentError

# s0 is forgotten; s1 cites it and s2 cites s1.
CHAIN = {"s0": set(), "s1": {"s0"}, "s2": {"s1"}}


def rows_of(**states):
    return cascade_rows(CHAIN, {"s1": "ok", "s2": "ok", **states})


def replaced(rows, label, row):
    return [row if r.source == str(identity(label)) else r for r in rows]


def by_label(rows, label):
    return next(r for r in rows if r.source == str(identity(label)))


def test_a_failed_reconcile_of_a_served_row_keeps_its_citers_in_the_cascade():
    """s1 was served at revision 1, which s2 cites; its reconcile at the
    same revision failed. Its removal applies in place, and the records it
    removes were served at revision 1, so s2 is still a level-2 dependent."""
    rows = rows_of()
    s1 = by_label(rows, "s1")
    failed = dataclasses.replace(
        s1, state="failed", plan=dict(operation="identity_publish")
    )
    rows = replaced(rows, "s1", failed)
    found = erasure.remaining(rows[0].tombstone, rows)
    assert [(d.identity_data_id, d.level) for d in found.dependents] == [
        (str(identity("s1")), 1),
        (str(identity("s2")), 2),
    ]
    assert {r.last_revision for r in found.dependents[0].removed_records} == {1}


def test_a_first_publication_that_failed_was_never_served():
    rows = rows_of()
    s1 = by_label(rows, "s1")
    failed = dataclasses.replace(
        s1, state="failed", verified_revision=0, plan=dict(operation="identity_publish")
    )
    rows = replaced(rows, "s1", failed)
    (s1_impact,) = erasure.remaining(rows[0].tombstone, rows).dependents
    assert {r.last_revision for r in s1_impact.removed_records} == {0}


def saved_level_two_removal(upstream_state):
    """s1's removal is written; s2's removal revision failed, so s2 holds
    it as a failed replacement; then s1 goes to `upstream_state`."""
    rows = rows_of()
    ids = source_ids(rows[0].tombstone)
    s1_step, s2_step = erasure.cascade(rows, ids, ())
    rows = replaced(rows, "s1", row_of(s1_step.description, "ok"))
    failed = dataclasses.replace(
        row_of(s2_step.description, "ok"),
        state="failed",
        verified_revision=s2_step.row.revision,
        plan=dict(operation="identity_replace"),
    )
    rows = replaced(rows, "s2", failed)
    (retry,) = erasure.cascade(rows, ids, ())
    assert retry.row.source == str(identity("s2")) and retry.level == 2
    s1 = by_label(rows, "s1")
    return replaced(rows, "s1", dataclasses.replace(s1, state=upstream_state))


def test_a_failed_removal_whose_upstream_withdrew_leaves_the_cascade():
    """The records s2's failed removal cites are bound by no removal any
    more: s1 is withdrawn. s2 leaves the cascade, as a citer of a withdrawn
    intermediate does, and every reader of the cascade answers instead of
    raising."""
    rows = saved_level_two_removal("withdrawn")
    tomb = rows[0].tombstone
    assert erasure.cascade(rows, source_ids(tomb), ()) == ()
    assert erasure.unfinished(tomb, rows) == []
    assert erasure.remaining(tomb, rows).dependents == ()
    assert [i.dependents for i in erasure.under_way(rows)] == [()]
    erasure.refuse_retiring_inputs(by_label(rows, "s2").description, rows)


def test_a_failed_removal_stays_while_its_upstream_withdrawal_fails():
    """s1's withdrawal failed after its removal was written: the removal was
    served, so it still binds, and s2's failed removal resumes at level 2."""
    rows = saved_level_two_removal("failed")
    s1 = by_label(rows, "s1")
    rows = replaced(
        rows, "s1", dataclasses.replace(s1, plan=dict(operation="identity_withdraw"))
    )
    (retry,) = erasure.cascade(rows, source_ids(rows[0].tombstone), ())
    assert (retry.row.source, retry.level) == (str(identity("s2")), 2)
    assert erasure.ready([retry]) == ([retry], [])


LONG_CHAIN = {"s0": set(), "s1": {"s0"}, "s2": {"s1"}, "s3": {"s2"}}


def two_levels_written():
    """s1's and s2's removals are written; s3's is still to write."""
    rows = cascade_rows(LONG_CHAIN, {"s1": "ok", "s2": "ok", "s3": "ok"})
    ids = source_ids(rows[0].tombstone)
    for _ in range(2):
        step = erasure.cascade(rows, ids, ())[0]
        rows = [
            row_of(step.description, "ok") if r.source == step.row.source else r
            for r in rows
        ]
    return rows, ids


@pytest.mark.parametrize("operation", ["identity_publish", "identity_withdraw"])
def test_a_failed_attempt_on_a_written_intermediate_keeps_the_citers_below(operation):
    """s1's removal was written and served; then a reconcile at the same
    revision, or a withdrawal, failed. The removal still binds, so s3 is
    still a level-3 dependent and the forget is not finished, and s1 is not
    a removal to write again."""
    rows, ids = two_levels_written()
    s1 = by_label(rows, "s1")
    rows = replaced(
        rows,
        "s1",
        dataclasses.replace(s1, state="failed", plan=dict(operation=operation)),
    )
    steps = erasure.cascade(rows, ids, ())
    assert [(s.row.source, s.level) for s in steps] == [(str(identity("s3")), 3)]
    assert erasure.unfinished(rows[0].tombstone, rows) == [by_label(rows, "s3")]


def test_a_failed_removal_in_place_of_a_served_revision_resumes():
    """s1 was served at revision 1 and a reconcile there failed; its removal
    then failed in place, superseding the served description (an erasure
    retry). The saved removal was never served, so it is still a removal
    to write at level 1, with s2 below it."""
    rows = rows_of(s1="reconciled")
    step, _ = erasure.cascade(rows, source_ids(rows[0].tombstone), ())
    failed = dataclasses.replace(
        row_of(step.description, "ok"),
        state="failed",
        plan=dict(
            operation="identity_publish",
            erased_from=[step.row.description.model_dump_json()],
        ),
    )
    rows = replaced(rows, "s1", failed)
    steps = erasure.cascade(rows, source_ids(rows[0].tombstone), ())
    assert [(s.row.source, s.level, s.impact is None) for s in steps] == [
        (str(identity("s1")), 1, True),
        (str(identity("s2")), 2, False),
    ]


def test_a_source_holding_a_removal_retires_only_once_the_cascade_finishes():
    """s1 and s2 hold written removals and s3's is still to write: neither
    may be withdrawn or forgotten until it is. The forgotten source itself
    holds none, and a source that holds no removal is never refused."""
    rows, ids = two_levels_written()
    for label in ("s1", "s2"):
        with pytest.raises(IntentError) as refused:
            erasure.refuse_unfinished_cascade(by_label(rows, label).description, rows)
        assert refused.value.code == "cascade_unfinished"
        assert refused.value.details["unfinished"] == [str(identity("s3"))]
    erasure.refuse_unfinished_cascade(by_label(rows, "s3").description, rows)
    (step,) = erasure.cascade(rows, ids, ())
    rows = replaced(rows, "s3", row_of(step.description, "ok"))
    for label in ("s1", "s2", "s3"):
        erasure.refuse_unfinished_cascade(by_label(rows, label).description, rows)


def removal_listing(description, key, last):
    """The removal revision with its producer's removed records relisted as
    last served at `last`."""
    producer = description.producers[key]
    config = producer.model_dump(mode="json")
    for record in config["configuration"]["removed_records"]:
        record["last_revision"] = last
    return description.model_copy(
        update=dict(
            producers={
                **description.producers,
                key: type(producer).model_validate(config),
            }
        )
    )


def test_a_new_removal_in_place_lists_exactly_the_served_revision():
    """s1 was served at revision 1, which s2 pins, and a reconcile there
    failed. A removal in place that lists its records as last served at
    revision 0 would leave s2 out of the cascade: it is refused when new in
    a begin, and tolerated only as a step an earlier begin admitted."""
    rows = rows_of(s1="reconciled")
    step, _ = erasure.cascade(rows, source_ids(rows[0].tombstone), ())
    saved = step.row.description
    (key,) = set(step.description.producers) - set(saved.producers)
    erasures = erasures_of(rows, saved)
    check_retry_chain([saved, step.description], erasures, 1, saved)
    forged = removal_listing(step.description, key, 0)
    with pytest.raises(IntentError) as refused:
        check_retry_chain([saved, forged], erasures, 1, saved)
    assert refused.value.code == "erasure_incomplete"
    check_retry_chain([saved, forged], erasures, 1, forged)


def failed_leaf_removal():
    """s1's removal is written; s2's removal revision failed and was never
    served, so s2's own saved removal is the only unfinished link."""
    rows = rows_of()
    ids = source_ids(rows[0].tombstone)
    step = erasure.cascade(rows, ids, ())[0]
    rows = replaced(rows, "s1", row_of(step.description, "ok"))
    (step,) = erasure.cascade(rows, ids, ())
    failed = dataclasses.replace(
        row_of(step.description, "ok"),
        state="failed",
        verified_revision=step.row.revision,
        plan=dict(operation="identity_replace"),
    )
    return replaced(rows, "s2", failed)


def test_a_failed_removal_whose_own_link_is_all_that_is_left_may_retire():
    """Withdrawing or forgetting s2 frees no other source, so it is not
    refused; withdrawing s1 would free s2's failed removal, so it is."""
    rows = failed_leaf_removal()
    assert erasure.unfinished(rows[0].tombstone, rows) == [by_label(rows, "s2")]
    erasure.refuse_unfinished_cascade(by_label(rows, "s2").description, rows)
    with pytest.raises(IntentError) as refused:
        erasure.refuse_unfinished_cascade(by_label(rows, "s1").description, rows)
    assert refused.value.code == "cascade_unfinished"

