"""The cascade half of the chain check: a forget down chains of citations.

On every acyclic citation graph of up to four sources (chain_worlds.py),
with s0 forgotten and every other source ok, blocked, drifted or reconciled
(cascade_worlds.py), it checks:

- The cascade. The impact a dry run reports lists each dependent at its
  level with the decisions it loses and the removed records it cites, as
  the oracle states them, and its token tells apart any two different
  cascades.
- Order and resume. Writing the removal revisions as `finish_dependents`
  does (the first one `erasure.ready` lets write, in the cascade's order),
  admission admits each one (a removal in place through the erasure-retry
  chain check); after each write the cascade read from the rows again plans
  the same revisions for the rest; what is left at the end is what waits
  for a blocked removal.
- A retired upstream. Before a removal below level 1 is written, the same
  removal saved by a failed attempt resumes at its level, and once every
  source whose records it cites withdraws, it leaves the cascade and no
  reader of the cascade raises.
- The inductive gate. Admission refuses (`erasure_unbound`) a removal below
  level 1 before the removals above it are written, and one below a
  removal that was written out of order.
- Shrink only. While the forget is pending, and after each removal is
  written, every new citation of a record that the fence, the record
  checks and the cycle check admit leaves the cascade's removals inside
  the ones the confirmed token covers.

The code under test is erasure.cascade, erasure.remaining, the token,
erasure.ready, erasure_rules.bound_removals and erasure_of through
admission.admit and check_retry_chain, and erasure.refuse_retiring_inputs.
Nothing is replaced.

    uv run python support/chain_check.py   # runs both halves
"""

import dataclasses
from collections import Counter
from contextlib import contextmanager
from itertools import product
from types import MappingProxyType

from cascade_worlds import (
    CASCADE_STATES,
    FORGOTTEN,
    cascade_oracle,
    cascade_rows,
    new_citation,
    pending_row,
)
from chain_worlds import LABELS, TEXT, acyclic, graphs, row_of
from cognee_lab.identity import (
    dependency,
    erasure,
    erasure_rules,
    records,
    retirement,
    withholding,
)
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
    rows, or None when it admits it. A removal in place of a failed
    attempt's saved revision is an erasure retry, which begin checks."""
    old = step.row.description
    erasures = erasure_rules.erasures_of(rows, old)
    try:
        if step.description.revision == old.revision:
            erasure_rules.check_retry_chain(
                [old, step.description], erasures, step.row.verified_revision
            )
        else:
            admit(
                old, step.description, TEXT, TEXT, identity_map(old), erasures=erasures
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


def shrinks(rows, confirmed, impact_of):
    """Each admitted new citation leaves the removals inside `confirmed`.
    Yields the citations that widen them."""
    current = {r.source: r for r in rows if r.state == "current"}
    for row in rows:
        if row.state != "current":
            continue
        for cited, decision in product(sorted(current), ("d", "v")):
            target = current[cited].description
            if cited == row.source or decision not in records.record_keys(target):
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


def retired_upstream(rows, step, ids, tomb):
    """Disagreements when `step`, a removal below level 1 whose upstream is
    written, fails after it began, and then every source whose records it
    cites withdraws: the failed removal resumes at its level while they
    stay, and leaves the cascade once they withdraw, with no reader of the
    cascade raising."""
    source = step.row.source
    operation = "identity_replace" if step.row.state == "current" else None
    failed = dataclasses.replace(
        row_of(step.description, "ok"),
        state="failed",
        verified_revision=step.row.verified_revision,
        plan=dict(operation=operation or step.row.plan["operation"]),
    )
    after = [failed if r.source == source else r for r in rows]
    resumed = next(
        (s for s in erasure.cascade(after, ids, ()) if s.row.source == source), None
    )
    if resumed is None or resumed.impact is not None or resumed.level != step.level:
        return [("failed removal resumes", source)]
    upstream = {r.identity_data_id for r in step.cited_records}
    retired = [
        dataclasses.replace(r, state="withdrawn") if r.source in upstream else r
        for r in after
    ]
    try:
        left = {s.row.source for s in erasure.cascade(retired, ids, ())}
        erasure.unfinished(tomb, retired)
        list(erasure.under_way(retired))
        try:
            erasure.refuse_retiring_inputs(failed.description, retired)
        except IntentError:
            pass
    except Exception as exc:
        return [("upstream retired", source, type(exc).__name__)]
    return [("upstream retired", source)] if source in left else []


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
        writable, _ = erasure.ready(steps)
        if not writable:
            break
        step = writable[0]
        if step.level > 1:
            failures += retired_upstream(rows, step, ids, tomb)
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


def removes_before_served(row, cited):
    """A removal in place of a failed attempt takes the revision before as
    the last that served its records, even when that revision was served."""
    found = _removes(row, cited)
    if row.state == "current" or erasure.blocked(row):
        return found
    return frozenset(r._replace(last_revision=row.revision - 1) for r in found)


def unbound_retries(removals, known=MappingProxyType({})):
    """A removal binds even when a record it cites is removed by no
    removal at all, as a retry whose upstream retired."""
    removed = set(known).union(*(removes for _, removes in removals.values()))
    return _levels(
        {k: (cited & removed, removes) for k, (cited, removes) in removals.items()},
        known,
    )


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


_citations = dependency.citations
_cascade = erasure.cascade
_removes = erasure.removes
_levels = erasure_rules.levels
# Each mutant: its replacement and every (module, name) that binds the
# original, so callers that imported it see the mutant too.
MUTANTS = {
    "one_level_cascade": (
        one_level,
        [
            (m, "citations")
            for m in (dependency, erasure, erasure_rules, retirement, withholding)
        ],
    ),
    "cascade_out_of_order": (by_source, [(erasure, "cascade")]),
    "bound_without_induction": (
        without_induction,
        [(erasure, "bound_removals"), (erasure_rules, "bound_removals")],
    ),
    "level_one_fence": (level_one_fence, [(erasure, "removed_records")]),
    "removed_before_served": (removes_before_served, [(erasure, "removes")]),
    "unbound_retries": (
        unbound_retries,
        [(erasure, "levels"), (erasure_rules, "levels")],
    ),
    "removed_any_fingerprint": (any_fingerprint, [(records.RemovedRecord, "reads")]),
}


@contextmanager
def patched(name):
    replacement, bindings = MUTANTS[name]
    originals = [
        (owner, attribute, getattr(owner, attribute)) for owner, attribute in bindings
    ]
    for owner, attribute, _ in originals:
        setattr(owner, attribute, replacement)
    try:
        yield
    finally:
        for owner, attribute, original in originals:
            setattr(owner, attribute, original)


def run_mutants(count=4, states=("ok", "drifted", "reconciled")):
    caught = {}
    for name in MUTANTS:
        with patched(name):
            _, failures = search(count, states, first=True)
        caught[name] = failures[0] if failures else None
    return caught
