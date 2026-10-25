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
- A failed removal. Before each removal is written, the same removal
  saved by a failed attempt: below level 1 it resumes at its level, and
  once every source whose records it cites withdraws, it leaves the
  cascade and no reader of the cascade raises.
- A failed attempt on a written removal. After each write, a reconcile at
  the written revision or a withdrawal that fails leaves the cascade
  planning the same revisions for the rest.
- Retiring mid-cascade. In both shapes above, a withdrawal or forget of a
  source is refused (`cascade_unfinished`) exactly when the source holds a
  removal and retiring it would change what the cascade still does to any
  other source: which sources are left, or what any of their removals
  removes or cites. A source whose own failed removal is all that is left
  may retire.
- A rejected retry. A removal below level 1 that completed, then lost
  every source whose records it cites to a withdrawal, then was rejected
  at retrieval, is admitted again with its saved removal: in place through
  the erasure-retry chain check, at the next revision through admission.
  So is every removal of a finished cascade rejected after s0 was
  re-added.
- The served revision. A removal in place that lists its records as last
  served at another revision than the ledger verified is refused.
- The inductive gate. Admission refuses (`erasure_unbound`) a removal below
  level 1 before the removals above it are written, and one below a
  removal that was written out of order.
- Shrink only. While the forget is pending, and after each removal is
  written, every new citation of a record that the fence, the record
  checks and the cycle check admit leaves the cascade's removals inside
  the ones the confirmed token covers.
- No stale citation. Once the cascade finishes, with no retirement or
  after any withdrawal the fence allows while a removal is left to write,
  no live source cites a record the forget took away or a removal dropped
  or changed, by the fingerprint it pins. The removed records come from
  the descriptions before and after, not from `cascade`. The withdrawals
  are tried before each write, not once: on 2026-10-25 a single try on the
  initial rows also caught skip_citers_of_withdrawn but saved no time (four
  sources, three runs each: 292 s per search trying before each write,
  297 s trying once), since this check took about 4% of a profiled
  three-source search.

The code under test is erasure.cascade, erasure.remaining, the token,
erasure.ready, erasure_rules.bound_removals and erasure_of through
admission.admit and check_retry_chain, erasure.refuse_retiring_inputs and
erasure.refuse_unfinished_cascade. Nothing is replaced.

    uv run python support/chain_check.py   # runs both halves
"""

import dataclasses
import sys
from collections import Counter
from contextlib import contextmanager
from itertools import pairwise, product
from types import MappingProxyType

from cascade_worlds import (
    CASCADE_STATES,
    FORGOTTEN,
    cascade_oracle,
    cascade_rows,
    described,
    new_citation,
    pending_row,
    readded,
)
from chain_worlds import LABELS, TEXT, acyclic, graphs, row_of
from cognee_lab.identity import (
    dependency,
    erasure,
    erasure_rules,
    records,
)
from cognee_lab.identity.admission import admit, identity_map
from cognee_lab.identity.chains import (
    check_citation_cycles,
    check_record_citations,
    new_citations,
)
from cognee_lab.identity.retirement import source_ids
from cognee_lab.identity.storage import PublicationRow
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
                [old, step.description], erasures, step.row.verified_revision, old
            )
        else:
            admit(
                old, step.description, TEXT, TEXT, identity_map(old), erasures=erasures
            )
    except IntentError as exc:
        return exc.code
    return None


def relisted(step, last):
    """`step` with its removal producer's records relisted as last served
    at `last`."""
    description = step.description
    (key,) = set(description.producers) - set(step.row.description.producers)
    producer = description.producers[key]
    config = producer.model_dump(mode="json")
    for record in config["configuration"]["removed_records"]:
        record["last_revision"] = last
    producers = {**description.producers, key: type(producer).model_validate(config)}
    return step._replace(
        description=description.model_copy(update=dict(producers=producers))
    )


def misdated(rows, steps):
    """Disagreements when a removal in place that admission admits lists
    its records as last served one revision before the ledger verified."""
    return [
        ("served revision", step.row.source)
        for step in steps
        if step.impact is not None
        and step.description.revision == step.row.revision
        and step.impact.removed_records
        and refusal(rows, step) is None
        and refusal(rows, relisted(step, step.row.verified_revision - 1))
        != "erasure_incomplete"
    ]


def holds_removal(row) -> bool:
    return row.description is not None and any(
        p.implementation == erasure_rules.ERASURE_IMPLEMENTATION
        for p in row.description.producers.values()
    )


def failed_after_written(rows, step, ids, tomb):
    """Disagreements once `step` is written: a failed reconcile at its
    revision, or a failed withdrawal, changes nothing the cascade plans for
    the rest, and a withdrawal or forget is refused as
    `retire_disagreements` states."""
    failures = []
    plan = {
        (s.row.source, s.level, s.description.model_dump_json())
        for s in erasure.cascade(rows, ids, ())
    }
    source = step.row.source
    for operation in ("identity_publish", "identity_withdraw"):
        row = next(r for r in rows if r.source == source)
        failed = dataclasses.replace(
            row, state="failed", plan=dict(operation=operation)
        )
        after = [failed if r.source == source else r for r in rows]
        found = {
            (s.row.source, s.level, s.description.model_dump_json())
            for s in erasure.cascade(after, ids, ())
        }
        if found != plan:
            failures.append(("written then failed", source, operation))
    return failures + retire_disagreements(rows, tomb, "retire while unfinished")


def withdrawn(rows, sources):
    return [
        dataclasses.replace(r, state="withdrawn") if r.source in sources else r
        for r in rows
    ]


def reach(rows, ids, own):
    """What the forget's cascade still does to each source but `own`: the
    records its removal removes and the removed records it cites."""
    found = {}
    for step in erasure.cascade(rows, ids, ()):
        if step.row.source == own:
            continue
        removes = (
            step.impact.removed_records
            if step.impact is not None
            else erasure.removal_of(step.row, ids).removed_records
        )
        found[step.row.source] = (frozenset(removes), step.cited_records)
    return found


def retire_disagreements(rows, tomb, check):
    """Disagreements over withdrawing or forgetting each saved source: it
    is refused (`cascade_unfinished`) exactly when it holds a removal and
    retiring it would change what the forget's cascade still does to any
    other source (`reach`)."""
    failures = []
    ids = source_ids(tomb)
    for row in rows:
        if row.description is None:
            continue
        after = withdrawn(rows, {row.source})
        changes = reach(rows, ids, row.source) != reach(after, ids, row.source)
        try:
            erasure.refuse_unfinished_cascade(row.description, rows)
            refused = False
        except IntentError as exc:
            refused = exc.code == "cascade_unfinished"
        if refused != (holds_removal(row) and changes):
            failures.append((check, row.source, refused))
    return failures


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


def failed_step(rows, step):
    """`step`'s removal saved by an attempt that failed after it began, and
    the rows with it."""
    if step.row.state == "current":
        plan = dict(operation="identity_replace")
    else:
        plan = dict(
            operation=step.row.plan["operation"],
            erased_from=[step.row.description.model_dump_json()],
        )
    failed = dataclasses.replace(
        row_of(step.description, "ok"),
        state="failed",
        verified_revision=step.row.verified_revision,
        plan=plan,
    )
    return failed, [failed if r.source == failed.source else r for r in rows]


def retired_upstream(rows, step, ids, tomb):
    """Disagreements when `step`, a removal whose upstream is written,
    fails after it began: a withdrawal or forget is refused as
    `retire_disagreements` states, and below level 1, once every source
    whose records it cites withdraws, the failed removal leaves the
    cascade, after resuming at its level while they stay, with no reader
    of the cascade raising."""
    source = step.row.source
    failed, after = failed_step(rows, step)
    failures = retire_disagreements(after, tomb, "retire a failed removal")
    if step.level == 1:
        return failures
    resumed = next(
        (s for s in erasure.cascade(after, ids, ()) if s.row.source == source), None
    )
    if resumed is None or resumed.impact is not None or resumed.level != step.level:
        return failures + [("failed removal resumes", source)]
    retired = withdrawn(after, {r.identity_data_id for r in step.cited_records})
    try:
        left = {s.row.source for s in erasure.cascade(retired, ids, ())}
        erasure.unfinished(tomb, retired)
        list(erasure.under_way(retired))
        try:
            erasure.refuse_retiring_inputs(failed.description, retired)
        except IntentError:
            pass
    except Exception as exc:
        return failures + [("upstream retired", source, type(exc).__name__)]
    return failures + ([("upstream retired", source)] if source in left else [])


def retry_refusal(step, rows):
    """The code admission refuses the retry of `step`'s removal with, once
    it completed and retrieval rejected it, in `rows` (which hold that
    rejected row), or None when it admits it. A removal in place is an
    erasure retry, which begin checks; one at the next revision is a
    replacement's retry, which admission checks."""
    old, removal = step.row.description, step.description
    row = next(r for r in rows if r.source == step.row.source)
    erasures = erasure_rules.erasures_of(rows, removal)
    try:
        if removal.revision == old.revision:
            erasure_rules.check_retry_chain(
                [old, removal], erasures, row.verified_revision, removal
            )
        else:
            admit(
                old,
                removal,
                TEXT,
                TEXT,
                identity_map(old),
                first_attempt=False,
                erasures=erasures,
            )
    except IntentError as exc:
        return exc.code
    return None


def rejected(rows, step):
    """`rows` with `step`'s removal completed and then rejected at
    retrieval."""
    row = dataclasses.replace(row_of(step.description, "ok"), state="failed")
    return [row if r.source == row.source else r for r in rows]


def rejected_after_upstream_retired(rows, step):
    """Disagreements when `step`, a removal below level 1, completed, every
    source whose records it cites withdrew, and retrieval then rejected
    it: the retry with the saved removal is admitted, since its first
    attempt found what it cites bound."""
    if step.level == 1:
        return []
    after = withdrawn(
        rejected(rows, step), {r.identity_data_id for r in step.cited_records}
    )
    if code := retry_refusal(step, after):
        return [("rejected after upstream retired", step.row.source, code)]
    return []


def rejected_after_readd(rows, planned):
    """Disagreements once the cascade finished and s0 was re-added, which
    moves its tombstone to the row's last tombstone, when retrieval then
    rejects a removal: its retry with the saved removal is admitted, since
    the forget it names is s0's last."""
    failures = []
    for step in planned:
        if code := retry_refusal(step, readded(rejected(rows, step))):
            failures.append(("rejected after re-add", step.row.source, code))
    return failures


def fingerprints(description) -> set:
    """(source, key, digest) of each record a description holds."""
    return {
        (
            str(description.identity_data_id),
            key,
            records.record_digest(
                description, records.record_type_of(description, key), key
            ),
        )
        for key in records.record_keys(description)
    }


def removed_since(start, rows) -> set:
    """(source, key, digest) of each record of `start`, the descriptions
    before the forget, that `rows` no longer hold with that digest: every
    record of the forgotten source, and each record a removal dropped or
    changed. A withdrawn source keeps its description, so its records do
    not count as removed."""
    now = set().union(*(fingerprints(r.description) for r in rows if r.description))
    return set().union(*(fingerprints(d) for d in start)) - now


def stale_citations(start, rows) -> list:
    """(source, record, cited) for each citation a live source makes of a
    record removed since `start`, by the digest it pins."""
    removed = removed_since(start, rows)
    found = []
    for row in rows:
        if row.description is None or row.is_retired:
            continue
        saved = records.saved_records(row.description)
        for key, inputs in records.record_inputs(row.description).items():
            for ref in sorted(inputs & saved.keys()):
                item = saved[ref]
                cited = (str(item.identity_data_id), item.record_id)
                if (*cited, item.content_sha256) in removed:
                    found.append((row.source, key, cited))
    return found


def finished(rows, ids):
    """`rows` once every removal the cascade lets write is written, in its
    order, or None when a removal still waits."""
    while True:
        writable, _ = erasure.ready(erasure.cascade(rows, ids, ()))
        if not writable:
            break
        rows = written(rows, writable[0])
    return None if erasure.cascade(rows, ids, ()) else rows


def stale_after_withdrawal(start, rows, ids):
    """Disagreements when each source the fence lets withdraw now does, and
    the cascade then finishes: a live source still cites a removed
    record."""
    failures = []
    for row in rows:
        if row.description is None or row.is_retired:
            continue
        try:
            erasure.refuse_unfinished_cascade(row.description, rows)
        except IntentError:
            continue
        done = finished(withdrawn(rows, {row.source}), ids)
        if done is not None and (stale := stale_citations(start, done)):
            failures.append(("stale after withdrawal", row.source, stale[0]))
    return failures


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
    start = [described(FORGOTTEN, graph[FORGOTTEN])] + [
        r.description for r in rows if r.description is not None
    ]
    failures += misdated(rows, planned.values())
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
        failures += stale_after_withdrawal(start, rows, ids)
        step = writable[0]
        failures += retired_upstream(rows, step, ids, tomb)
        failures += rejected_after_upstream_retired(rows, step)
        if (code := refusal(rows, step)) is not None:
            failures.append(("write in order", step.row.source, code))
            break
        rows = written(rows, step)
        failures += failed_after_written(rows, step, ids, tomb)
    left = {s.row.source for s in erasure.cascade(rows, ids, ())}
    if left != waiting:
        failures.append(("waiting", left))
    if not left:
        failures += rejected_after_readd(rows, planned.values())
        failures += [("stale citation", *c) for c in stale_citations(start, rows)]
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


def written_only_current(self):
    """Only a current row's removal is written: a failed attempt on a
    written removal frees the citers below it."""
    return self.state == "current"


def served_despite_supersede(self):
    """A failed row verified at its revision holds what was served, even
    after an erasure retry superseded that description."""
    return self.state == "current" or self.verified_revision >= self.revision


def retire_anytime(source, rows):
    """Withdrawing or forgetting a source that holds a removal is never
    refused."""


def retire_blocked_by_own_removal(source, rows):
    """A source holding a removal is refused while anything is left, even
    when its own failed removal is all that is left."""
    tomb = next(r.tombstone for r in rows if r.tombstone)
    holds = any(erasure_rules.is_removal_producer(p) for p in source.producers.values())
    if holds and erasure.unfinished(tomb, rows):
        raise IntentError("cascade_unfinished", "")


def retire_by_ids(source, rows):
    """A source holding a removal is refused only when retiring it would
    drop another source from what is left, not when it would shrink what
    another source's removal removes or cites."""
    tomb = next(r.tombstone for r in rows if r.tombstone)
    own = str(source.identity_data_id)
    holds = any(erasure_rules.is_removal_producer(p) for p in source.producers.values())
    left = {r.source for r in erasure.unfinished(tomb, rows)} - {own}
    kept = {r.source for r in erasure.unfinished(tomb, withdrawn(rows, {own}))}
    if holds and left - kept:
        raise IntentError("cascade_unfinished", "")


def forget_only_live(old, source, erasures, **options):
    """A removal may name only a forget whose source is still forgotten,
    also on a retry after the source was re-added."""
    return _erasure_of(old, source, erasures._replace(earlier={}), **options)


def bind_every_step(chain, erasures, served, saved):
    """Every step of a retry chain must cite records bound now, also a step
    an earlier begin admitted."""
    for i, (before, after) in enumerate(pairwise(chain)):
        new = i == len(chain) - 2 and after != saved
        last = frozenset({served} if new else {served, after.revision - 1})
        _check_erasure_retry(before, after, erasures, last)


def bind_on_retry(old, source, erasures, **options):
    """A retry's saved removal must cite records bound now, as a first
    attempt's must."""
    return _erasure_of(old, source, erasures)


def skip_citers_of_withdrawn(rows, ids, removed, token=None):
    """A dependent that cites a withdrawn source leaves the cascade, though
    it still cites a record the forget removed."""
    withdrawn_ids = {r.source for r in rows if r.state == "withdrawn"}

    def cites_withdrawn(description):
        return any(
            str(i.identity_data_id) in withdrawn_ids
            for i in records.saved_records(description).values()
        )

    return tuple(
        s
        for s in _cascade(rows, ids, removed, token)
        if not cites_withdrawn(s.row.description)
    )


def served_or_before(chain, erasures, served, saved):
    """Every step of a retry chain may list the revision before the served
    one, also the step new in this begin."""
    for before, after in pairwise(chain):
        _check_erasure_retry(
            before, after, erasures, frozenset({served, after.revision - 1})
        )


_citations = dependency.citations
_cascade = erasure.cascade
_removes = erasure.removes
_levels = erasure_rules.levels
_check_erasure_retry = erasure_rules.check_erasure_retry
_erasure_of = erasure_rules.erasure_of
# Each mutant: its replacement and the (owner, name) of the original. Every
# other binding of the original in a cognee_lab.identity module, which a
# caller imported by name, is patched too (`patched`).
MUTANTS = {
    "one_level_cascade": (one_level, (dependency, "citations")),
    "cascade_out_of_order": (by_source, (erasure, "cascade")),
    "bound_without_induction": (without_induction, (erasure_rules, "bound_removals")),
    "level_one_fence": (level_one_fence, (erasure, "removed_records")),
    "removed_before_served": (removes_before_served, (erasure, "removes")),
    "unbound_retries": (unbound_retries, (erasure_rules, "levels")),
    "removed_any_fingerprint": (any_fingerprint, (records.RemovedRecord, "reads")),
    "written_only_current": (
        property(written_only_current),
        (PublicationRow, "holds_served"),
    ),
    "served_despite_supersede": (
        property(served_despite_supersede),
        (PublicationRow, "holds_served"),
    ),
    "retire_anytime": (retire_anytime, (erasure, "refuse_unfinished_cascade")),
    "retire_blocked_by_own_removal": (
        retire_blocked_by_own_removal,
        (erasure, "refuse_unfinished_cascade"),
    ),
    "retire_by_ids": (retire_by_ids, (erasure, "refuse_unfinished_cascade")),
    "served_or_before": (served_or_before, (erasure_rules, "check_retry_chain")),
    "bind_every_step": (bind_every_step, (erasure_rules, "check_retry_chain")),
    "bind_on_retry": (bind_on_retry, (erasure_rules, "erasure_of")),
    "forget_only_live": (forget_only_live, (erasure_rules, "erasure_of")),
    "skip_citers_of_withdrawn": (skip_citers_of_withdrawn, (erasure, "cascade")),
}


def bindings(owner, attribute):
    """`(owner, attribute)` and every module-level name in a
    cognee_lab.identity module bound to the same object."""
    original = (
        vars(owner)[attribute] if isinstance(owner, type) else getattr(owner, attribute)
    )
    found = [(owner, attribute, original)]
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith("cognee_lab.identity"):
            continue
        for key, value in list(vars(module).items()):
            if value is original and (module, key) != (owner, attribute):
                found.append((module, key, original))
    return found


@contextmanager
def patched(name):
    replacement, (owner, attribute) = MUTANTS[name]
    originals = bindings(owner, attribute)
    for target, key, _ in originals:
        setattr(target, key, replacement)
    try:
        yield
    finally:
        for target, key, original in originals:
            setattr(target, key, original)


def run_mutants(count=4, states=("ok", "drifted", "reconciled")):
    caught = {}
    for name in MUTANTS:
        with patched(name):
            _, failures = search(count, states, first=True)
        caught[name] = failures[0] if failures else None
    return caught
