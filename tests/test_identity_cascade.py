"""The erasure cascade on rows that a failed attempt or a retired upstream
leaves: what the cascade still removes, and that it converges."""

import dataclasses

import pytest

from cascade_worlds import cascade_rows
from chain_worlds import identity, row_of
from cognee_lab.identity import erasure
from cognee_lab.identity.retirement import source_ids

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


@pytest.mark.parametrize("upstream_state", ["withdrawn", "failed_withdrawal"])
def test_a_failed_removal_whose_upstream_retired_leaves_the_cascade(upstream_state):
    """The records s2's failed removal cites are bound by no removal any
    more: s1 is withdrawn, or its withdrawal failed. s2 leaves the cascade,
    as a citer of a withdrawn intermediate does, and every reader of the
    cascade answers instead of raising."""
    state = "withdrawn" if upstream_state == "withdrawn" else "failed"
    rows = saved_level_two_removal(state)
    if upstream_state == "failed_withdrawal":
        s1 = by_label(rows, "s1")
        rows = replaced(
            rows,
            "s1",
            dataclasses.replace(s1, plan=dict(operation="identity_withdraw")),
        )
    tomb = rows[0].tombstone
    assert erasure.cascade(rows, source_ids(tomb), ()) == ()
    assert erasure.unfinished(tomb, rows) == []
    assert erasure.remaining(tomb, rows).dependents == ()
    assert [i.dependents for i in erasure.under_way(rows)] == [()]
    erasure.refuse_retiring_inputs(by_label(rows, "s2").description, rows)
