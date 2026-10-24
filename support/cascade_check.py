"""The cascade half of the chain check: a forget down chains of citations.

On every acyclic citation graph of up to four sources (chain_worlds.py),
with s0 forgotten and every other source ok, blocked or drifted
(cascade_worlds.py), it checks:

- The cascade. The impact a dry run reports lists each dependent at its
  level with the decisions it loses and the removed records it cites, as
  the oracle states them, and its token tells apart any two different
  cascades.
- Order and resume. Writing the removal revisions as `finish_dependents`
  does (the first one that waits for nothing, in the cascade's order),
  admission admits each one; after each write the cascade read from the
  rows again plans the same revisions for the rest; what is left at the end
  is what waits for a blocked removal.
- The inductive gate. Admission refuses (`erasure_unbound`) a removal below
  level 1 before the removals above it are written, and one below a
  removal that was written out of order.
- Shrink only. While the forget is pending, and after each removal is
  written, every new citation of a record that the fence, the record
  checks and the cycle check admit leaves the cascade's removals inside
  the ones the confirmed token covers.

The code under test is erasure.cascade, erasure.remaining, the token,
erasure_rules.bound_removals and erasure_of through admission.admit, and
erasure.refuse_retiring_inputs. Nothing is replaced.

    uv run python support/chain_check.py   # runs both halves
"""

from collections import Counter
from contextlib import contextmanager
from itertools import product

from cascade_worlds import (
    CASCADE_STATES,
    FORGOTTEN,
    cascade_oracle,
    cascade_rows,
    new_citation,
    pending_row,
)
from chain_worlds import LABELS, TEXT, acyclic, graphs, row_of
from cognee_lab.identity import erasure, erasure_rules, records
from cognee_lab.identity.admission import admit, identity_map
from cognee_lab.identity.chains import (
    check_citation_cycles,
    check_record_citations,
    new_citations,
)
from cognee_lab.identity.retirement import source_ids
from cognee_lab.identity.validation import IntentError


def refusal(rows, step):
    """The code admission refuses this removal revision with, given the
    rows, or None when it admits it."""
    old = step.row.description
    try:
        admit(
            old,
            step.description,
            TEXT,
            TEXT,
            identity_map(old),
            erasures=erasure_rules.erasures_of(rows, old),
        )
    except IntentError as exc:
        return exc.code
    return None


def written(rows, step):
    return [
        row_of(step.description, "ok") if r.source == step.row.source else r
        for r in rows
    ]


def plan_of(found):
    return {
        d.identity_data_id: (
            d.level,
            frozenset(r.assignment for r in d.decisions),
            frozenset((r.identity_data_id, r.record_id) for r in d.cited_records),
        )
        for d in found.dependents
    }


def removals(found):
    """(source, key) of each record the impact's removals remove."""
    return {
        (r.identity_data_id, r.record_id)
        for d in found.dependents
        for r in d.removed_records
    }


def next_step(steps):
    """The first removal revision that waits for nothing, as
    finish_dependents picks it."""
    held = set()
    for step in steps:
        behind = {r.identity_data_id for r in step.cited_records} & held
        if erasure.blocked(step.row) or behind:
            held.add(step.row.source)
            continue
        return step
    return None


def shrinks(rows, confirmed, impact_of):
    """Each admitted new citation leaves the removals inside `confirmed`.
    Yields the citations that widen them."""
    current = {r.source: r for r in rows if r.state == "current"}
    for row in rows:
        if row.state != "current":
            continue
        for cited, decision in product(sorted(current), ("d", "v")):
            target = current[cited].description
            if cited == row.source or decision not in {
                *target.mention_resolutions,
                *target.variant_assignments,
            }:
                continue
            candidate = new_citation(row.description, target, decision)
            try:
                erasure.refuse_retiring_inputs(candidate, rows)
                check_record_citations(candidate, rows, new_citations(candidate, row))
                check_citation_cycles(candidate, rows)
            except IntentError:
                continue
            after = [
                row_of(candidate, "ok") if r.source == row.source else r for r in rows
            ]
            if not removals(impact_of(after)) <= confirmed:
                yield (row.source, cited, decision)


def check_world(graph, states, tokens, *, shrink):
    """Every disagreement in one world, as (check, detail)."""
    failures = []
    rows = cascade_rows(graph, states)
    tomb = rows[0].tombstone
    ids = source_ids(tomb)
    want, waiting = cascade_oracle(graph, states)
    found = erasure.remaining(tomb, rows)
    got = plan_of(found)
    if got != want:
        failures.append(("impact", got))
    signature = tuple(sorted(got.items()))
    if tokens.setdefault(found.token, signature) != signature:
        failures.append(("token", found.token))
    planned = {s.row.source: s for s in erasure.cascade(rows, ids, ())}
    for step in planned.values():
        if step.level > 1 and not erasure.blocked(step.row):
            if refusal(rows, step) != "erasure_unbound":
                failures.append(("gate before its upstream", step.row.source))
    early = rows
    for step in planned.values():
        if step.level == 2 and not erasure.blocked(step.row):
            early = written(early, step)
    for step in planned.values():
        if step.level == 3 and not erasure.blocked(step.row):
            if refusal(early, step) != "erasure_unbound":
                failures.append(("gate below an unbound removal", step.row.source))
    confirmed = removals(found)
    if shrink:
        pending = cascade_rows(graph, states, pending_row)
        source, plan = pending[0].description, pending[0].plan
        before = removals(erasure.impact(source, plan, pending))
        if before != confirmed:
            failures.append(("pending impact", before))
        for widened in shrinks(
            pending, confirmed, lambda r: erasure.impact(source, plan, r)
        ):
            failures.append(("shrink while pending", widened))
    while True:
        steps = erasure.cascade(rows, ids, ())
        for step in steps:
            first = planned.get(step.row.source)
            if first is None or step.description != first.description:
                failures.append(("resume", step.row.source))
        if shrink:
            for widened in shrinks(
                rows, confirmed, lambda r: erasure.remaining(tomb, r)
            ):
                failures.append(("shrink", widened))
        step = next_step(steps)
        if step is None:
            break
        if (code := refusal(rows, step)) is not None:
            failures.append(("write in order", step.row.source, code))
            break
        rows = written(rows, step)
    left = {s.row.source for s in erasure.cascade(rows, ids, ())}
    if left != waiting:
        failures.append(("waiting", left))
    return failures


def search(count, states=CASCADE_STATES, shrink=True, first=False):
    """Every disagreement on every world of up to `count` sources; with
    `first`, only the first one found."""
    labels = LABELS[:count]
    others = [label for label in labels if label != FORGOTTEN]
    tally, failures, tokens = Counter(), [], {}
    for graph in graphs(labels):
        if not acyclic(graph):
            continue
        for chosen in product(states, repeat=len(others)):
            world = dict(zip(others, chosen))
            tally["cascade worlds"] += 1
            levels = max(
                (v[0] for v in cascade_oracle(graph, world)[0].values()), default=0
            )
            tally[f"cascade depth {levels}"] += 1
            for failure in check_world(graph, world, tokens, shrink=shrink):
                failures.append((graph, world, failure))
            if first and failures:
                return tally, failures
    return tally, failures


def one_level(reader, target):
    """The cascade stops at level 1: a removed record reads as nothing."""
    return _citations(reader, target._replace(records=frozenset()))


def by_source(rows, ids, removed, token=None):
    """The removal revisions in source order, not level order."""
    steps = _cascade(rows, ids, removed, token)
    return tuple(sorted(steps, key=lambda s: s.row.source))


def without_induction(rows, document, entities):
    """Every written removal binds, whether or not the records it cites
    are bound."""
    found = {}
    for claim in erasure_rules.written_claims(rows, document, entities):
        found.update(dict.fromkeys(claim.removed_records, 1))
    return found


def level_one_fence(found):
    """The fence knows only the level-1 removals."""
    return {r for d in found.dependents if d.level == 1 for r in d.removed_records}


def any_fingerprint(self, item):
    """A removed record reads every citation of its key, at any
    fingerprint."""
    return (str(item.identity_data_id), item.record_id) == (
        self.identity_data_id,
        self.record_id,
    ) and item.representation_revision <= self.last_revision


_citations = erasure.citations
_cascade = erasure.cascade
MUTANTS = {
    "one_level_cascade": (erasure, "citations", one_level),
    "cascade_out_of_order": (erasure, "cascade", by_source),
    "bound_without_induction": (erasure_rules, "bound_removals", without_induction),
    "level_one_fence": (erasure, "removed_records", level_one_fence),
    "removed_any_fingerprint": (records.RemovedRecord, "reads", any_fingerprint),
}


@contextmanager
def patched(name):
    owner, attribute, replacement = MUTANTS[name]
    original = getattr(owner, attribute)
    setattr(owner, attribute, replacement)
    try:
        yield
    finally:
        setattr(owner, attribute, original)


def run_mutants(count=4, states=("ok", "drifted")):
    caught = {}
    for name in MUTANTS:
        with patched(name):
            _, failures = search(count, states, first=True)
        caught[name] = failures[0] if failures else None
    return caught
