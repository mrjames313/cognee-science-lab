"""The eight properties support/ledger_check.py checks after every step.

Each property is a generator over one Step: the model's record of writers
and sources before and after the step, what RecordStore showed before and
after, and how the store answered. It yields a message for each break. The
docstring of each property states it; .claude/skills/identity-ledger/
reference.md gives the harm of each break and the code that keeps it.
"""

import json
from dataclasses import dataclass
from itertools import pairwise

from ledger_model import (
    CONTENT_FREE_PLAN,
    ERASURE_STEPS,
    METHODS,
    Begin,
    Finish,
    Op,
    Plan,
    Reject,
    Repeat,
    World,
    canonical,
    canonical_tombstone,
    removal,
    saved_json,
    scrubbed,
    variant_of,
)

ACCEPTED, REFUSED, HANDLED = "accepted", "refused", "handled"


@dataclass(frozen=True)
class Observation:
    rows: dict  # source index -> PublicationRow from RecordStore.rows()
    events: dict  # source index -> list of event details
    owner: str | None


def served(row):
    # storage.py PublicationRow.is_served, the retrieval eligibility test. The test in
    # tests/test_identity_ledger_check.py fails if that condition changes.
    return (
        row is not None
        and row.state == "current"
        and row.revision == row.verified_revision
    )


@dataclass(frozen=True)
class Step:
    model_before: World
    model_after: World
    obs_before: Observation
    obs_after: Observation
    op: Op
    result: str
    recovery: dict  # source -> why its failed row did not recover, or None

    @property
    def accepted(self):
        return self.result == ACCEPTED


def op_source(step):
    match step.op:
        case Begin() | Reject():
            return step.op.source
        case Finish():
            return step.model_before.writers[step.op.writer].holds.source
        case Repeat():
            return step.model_before.writers[step.op.writer].last.attempt.source
    return None


def step_kind(op):
    match op:
        case Begin():
            return op.method
        case Finish():
            return "complete" if op.stage is None else "fail"
    return type(op).__name__.lower()


def unresolved(events):
    return [e for e in events if e.get("resolved_at") is None]


def p1_withheld_until_complete(step):
    """A source is served exactly when its last accepted attempt completed as
    current, and then at that attempt's revision and description. A completed
    withdrawal or forget leaves the row in that state."""
    for s, ghost in enumerate(step.model_after.sources):
        row = step.obs_after.rows.get(s)
        if served(row) != (ghost.outcome == "current"):
            yield (
                f"S{s + 1} served={served(row)} but its last attempt is {ghost.outcome}"
            )
        if ghost.outcome == "current" and (
            row.revision != ghost.revision
            or saved_json(row) != canonical(s, ghost.revision, ghost.variant)
        ):
            yield f"S{s + 1} served a description other than the completed one"
        if ghost.outcome in ("withdrawn", "forgotten") and row.state != ghost.outcome:
            yield f"S{s + 1} {ghost.outcome} completed but the row is {row.state}"


def p2_independent_sources(step):
    """A step on one source leaves every other source's row and events alone."""
    touched = op_source(step)
    before, after = step.obs_before, step.obs_after
    for s in range(len(step.model_after.sources)):
        if s != touched and (
            before.rows.get(s) != after.rows.get(s)
            or before.events[s] != after.events[s]
        ):
            yield f"step {step.op.label!r} changed S{s + 1}"


def p3_stale_calls_refused(step):
    """A refused call changes nothing. begin() with an expected revision other
    than the saved one is refused. An acknowledgement for an attempt that ended
    or that a later begin() replaced, or for a description other than the one
    begun, is refused."""
    op, before = step.op, step.model_before
    if step.result == REFUSED and step.obs_before != step.obs_after:
        yield "a refused call changed the ledger"
    if step.accepted and isinstance(op, Repeat | Reject):
        if isinstance(op, Reject):
            kind, attempt = "fail", before.sources[op.source].served.attempt
        else:
            ack = before.writers[op.writer].last
            kind, attempt = ack.kind, ack.attempt.id
        touched = op_source(step)
        if kind == "complete" or attempt != before.sources[touched].attempt:
            yield (
                f"stale {kind} accepted for S{touched + 1}: the attempt "
                "already ended or a later begin() replaced it"
            )
    if isinstance(op, Begin) and step.accepted:
        prior = step.obs_before.rows.get(op.source)
        actual = prior.revision if prior else 0
        if op.expected != actual:
            yield (
                f"begin with expected_revision={op.expected} accepted at saved "
                f"revision {actual}"
            )
    if isinstance(op, Finish) and op.alt and step.accepted:
        yield "a completion for a description other than the one begun was accepted"


def p4_one_writer(step):
    """At most one attempt is open, and the reservation names exactly it."""
    open_attempts = [w.holds.id for w in step.model_after.writers if w.holds]
    if len(open_attempts) > 1:
        yield "two writers hold open attempts at once"
    if step.obs_after.owner != (open_attempts[0] if open_attempts else None):
        names = step.model_after.names
        yield (
            f"reservation owner={names.get(step.obs_after.owner, step.obs_after.owner)}"
            f" but open attempts={[names[a] for a in open_attempts]}"
        )


def p5_explicit_forward_recovery(step):
    """Revisions move forward one at a time, only the method that owns a saved
    intent resumes it, and each failure has one recovery event that only its
    completion resolves. No step deletes an event or changes a resolved
    event."""
    op, before, after = step.op, step.obs_before, step.obs_after
    completing = isinstance(op, Finish) and op.stage is None and step.accepted
    forgetting = completing and (
        step.model_after.sources[op_source(step)].outcome == "forgotten"
    )
    for s in range(len(step.model_after.sources)):
        old, new = before.rows.get(s), after.rows.get(s)
        if old and (new is None or new.revision < old.revision):
            yield f"S{s + 1} revision went back"
        open_events = unresolved(after.events[s])
        state = new.state if new else None
        allowed = {"failed": (1,), "pending": (0, 1)}.get(state, (0,))
        if len(open_events) not in allowed:
            yield f"S{s + 1} is {state} with {len(open_events)} unresolved recovery events"
        now_by_id = {e["recovery_event_id"]: e for e in after.events[s]}
        for e in before.events[s]:
            now = now_by_id.get(e["recovery_event_id"])
            if now is None:
                yield f"S{s + 1} recovery event deleted by {op.label!r}"
            elif e.get("resolved_at") is not None and now != e:
                # The one exception: completing a forget drops the messages
                # of the forgotten source's events, resolved ones included.
                if not (forgetting and s == op_source(step) and now == scrubbed(e)):
                    yield f"S{s + 1} resolved recovery event changed by {op.label!r}"
            elif (
                e.get("resolved_at") is None
                and now.get("resolved_at") is not None
                and not completing
            ):
                yield f"S{s + 1} recovery event resolved by {op.label!r}"
    if completing:
        attempt = step.model_before.writers[op.writer].holds
        done = METHODS[attempt.method].done_state
        was_open = {
            e["recovery_event_id"] for e in unresolved(before.events[attempt.source])
        }
        for e in after.events[attempt.source]:
            if e["recovery_event_id"] not in was_open:
                continue
            if e.get("resolving_attempt") != attempt.id:
                yield "a completion did not resolve the open event"
            elif e.get("outcome") != ("restored" if done == "current" else done):
                yield f"a completion as {done} recorded outcome {e.get('outcome')!r}"
            elif e.get("recovery_attempts") and (
                e["recovery_attempts"][-1].get("outcome") != "verified"
            ):
                yield "a completion did not mark its recovery attempt verified"
    if isinstance(op, Begin) and step.accepted:
        yield from begin_rules(op, before.rows.get(op.source))


def begin_rules(op, prior):
    method = METHODS[op.method]
    state = prior.state if prior else None
    actual = prior.revision if prior else 0
    if op.revision != actual + method.begins.get(state, 0):
        yield f"begin moved S{op.source + 1} from revision {actual} to {op.revision} through {op.method}"
    if method.requires_plan and op.plan.operation != method.recovers:
        yield f"{op.method} began with a {op.plan.operation} plan"
    if prior is None:
        return
    saved = Plan.of(op.source, prior.plan)
    if op.revision == actual:
        prior_variant = variant_of(op.source, saved_json(prior))
        same = op.variant == prior_variant
        superseding = (
            state == "failed"
            and method.supersedes
            and saved.operation == method.recovers
        )
        if not same and not (
            superseding and op.plan.erased == (*saved.erased, prior_variant)
        ):
            yield f"begin changed S{op.source + 1}'s description at saved revision {actual}"
        if superseding and same and op.plan.erased != saved.erased:
            yield f"{op.method} retry changed the saved plan's erased"
        chain = (*op.plan.erased, op.variant)
        if op.plan.erased and any(
            step not in ERASURE_STEPS for step in pairwise(chain)
        ):
            yield f"{op.method} began an erasure retry whose steps {chain} are not each the erasure removal"
        if (
            superseding
            and not same
            and op.variant != removal(actual, prior.verified_revision)
        ):
            yield f"{op.method} began an erasure removal that lists r01 as last served at another revision than S{op.source + 1}'s verified {prior.verified_revision}"
    erases = method.erases_row(state, saved.operation)
    if not (state in method.begins or method.owns(state, saved.operation) or erases):
        yield f"{op.method} began on a {state} {saved.operation} row"
    owners = {m.name for m in METHODS.values() if m.owns(state, saved.operation)}
    if owners and op.method not in owners and not erases:
        yield f"{state} {saved.operation} row resumed through {op.method}"
    if state == "failed" and method.owns(state, saved.operation):
        for name in method.preserved_on_retry:
            if getattr(op.plan, name) != getattr(saved, name):
                yield f"{op.method} retry changed the saved plan's {name}"


def p6_failed_rows_recoverable(step):
    """From a failed row and a free reservation, the method that owns the saved
    plan, called with the saved arguments, is accepted and completes."""
    for s, why in sorted(step.recovery.items()):
        if why:
            yield f"S{s + 1} failed row did not recover: {why}"


def p7_forgotten_rows_hold_no_content(step):
    """A forgotten row holds no description content: its description is the
    tombstone of the description its forget began, its plan keeps only
    identifiers, with no edge property, and no recovery event of the source
    keeps a message. forget.py builds the tombstone, with the UUIDs of the
    source's earlier forgotten lives; the checker passes Tombstone.of, whose
    carry is empty because the model's descriptions share their UUIDs."""
    for s, ghost in enumerate(step.model_after.sources):
        row = step.obs_after.rows.get(s)
        if row is None or row.state != "forgotten":
            continue
        if saved_json(row) != canonical_tombstone(s, ghost.revision, ghost.variant):
            yield f"S{s + 1} is forgotten but its description is not its tombstone"
        if set(row.plan) - CONTENT_FREE_PLAN or any(
            "properties" in e for e in row.plan.get("edges", [])
        ):
            yield f"S{s + 1} is forgotten but its plan keeps {sorted(row.plan)}"
        for e in step.obs_after.events[s]:
            if e != scrubbed(e):
                yield f"S{s + 1} is forgotten but a recovery event keeps its message"


def p8_tombstone_kept_until_next_forget(step):
    """A source that lives again keeps the tombstone its last forget left
    (`last_tombstone`), from the re-add's begin until its next forget, for
    that forget to carry; a forgotten row holds none beside its own."""
    for s, after in step.obs_after.rows.items():
        before = step.obs_before.rows.get(s)
        if after.state == "forgotten" or before is None:
            kept = None
        elif before.state == "forgotten":
            kept = before.tombstone
        else:
            kept = before.last_tombstone
        if after.last_tombstone != kept:
            yield (
                f"S{s + 1} {after.state} row holds last_tombstone "
                f"{'none' if after.last_tombstone is None else after.last_tombstone.revision}, "
                f"not {'none' if kept is None else kept.revision}"
            )


PROPERTIES = [
    p1_withheld_until_complete,
    p2_independent_sources,
    p3_stale_calls_refused,
    p4_one_writer,
    p5_explicit_forward_recovery,
    p6_failed_rows_recoverable,
    p7_forgotten_rows_hold_no_content,
    p8_tombstone_kept_until_next_forget,
]


def first_violation(step):
    for prop in PROPERTIES:
        message = next(prop(step), None)
        if message:
            return prop.__name__[:2].upper(), message
    return None
