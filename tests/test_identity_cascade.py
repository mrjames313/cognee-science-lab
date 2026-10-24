"""The erasure cascade on rows that a failed attempt or a retired upstream
leaves: what the cascade still removes, and that it converges."""

import dataclasses

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
