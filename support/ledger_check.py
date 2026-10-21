"""Bounded exhaustive check of the identity publication ledger (RecordStore).

Drives the real RecordStore in src/cognee_lab/identity/storage.py on a fresh
in-memory SQLite store through every sequence of ledger operations up to
--depth, and checks five properties after every step. See
.claude/skills/identity-ledger/SKILL.md for the properties, bounds and scope.

    uv run python support/ledger_check.py
    uv run python support/ledger_check.py --depth 7
    uv run python support/ledger_check.py --depth 9 --skip-probability 0.5 --seed 2
    uv run python support/ledger_check.py --replay "W1 publish S1 rev=1 expect=0; W1 complete"
    uv run python support/ledger_check.py --mutants
"""

import argparse
import asyncio
import copy
import json
import random
import sys
import time
import types
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import cognee_lab.identity.storage as real_storage
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.validation import IntentError

REPO = Path(__file__).resolve().parents[1]
STORAGE_PATH = REPO / "src/cognee_lab/identity/storage.py"
FIXTURE = REPO / "tests/fixtures/identity/cognee_identity_source_example.json"
LOCK_SCOPE = "shared-identity-publication"
DEFAULT_DEPTH = 5

# The stage each caller records when an injected fault stops its store work
# (publish.py:373, replace.py:345, withdraw.py:121). storage.py copies the
# stage into the recovery event and never branches on it, so one stage per
# method covers every fault the caller can inject.
FAIL_STAGE = {
    "publish": "nodes",
    "reconcile": "nodes",
    "replace": "replace_saved",
    "withdraw": "withdraw_contributions",
}
# The stage each caller records when complete() or assert_pending() refuses.
ACK_STAGE = {
    "publish": "verification",
    "reconcile": "verification",
    "replace": "verification",
    "withdraw": "withdraw_verification",
}

# Scratch breaks of storage.py: name -> (old text, new text, property the
# break must violate). --mutants applies each to an in-memory copy of the file.
MUTANTS = {
    "begin-keeps-state": (
        'row.revision, row.state, row.attempt = source.revision, "pending", attempt',
        'row.revision, row.state, row.attempt = (source.revision, row.state or "pending", attempt)',
        "P1",
    ),
    "complete-skips-verified-revision": (
        '        if state == "current":\n'
        '            values["verified_revision"] = source.revision\n',
        "",
        "P1",
    ),
    "fail-keeps-state": ('            row.state = "failed"\n', "", "P1"),
    "begin-links-every-source": (
        "                            RecoveryEvent.dataset == dataset,\n"
        "                            RecoveryEvent.source == sid,\n"
        "                        )\n"
        "                    )\n"
        "                )\n"
        "                .scalars()\n"
        "                .all()\n"
        "            )\n"
        "            for event in events:",
        "                            RecoveryEvent.dataset == dataset,\n"
        "                        )\n"
        "                    )\n"
        "                )\n"
        "                .scalars()\n"
        "                .all()\n"
        "            )\n"
        "            for event in events:",
        "P2",
    ),
    "complete-resolves-every-source": (
        "                        RecoveryEvent.dataset == dataset, RecoveryEvent.source == sid\n",
        "                        RecoveryEvent.dataset == dataset\n",
        "P2",
    ),
    "no-stale-revision-guard": (
        "            if actual_revision != expected_revision:\n"
        '                raise IntentError("stale_revision", "Saved revision changed")\n',
        "",
        "P3",
    ),
    "complete-ignores-attempt": (
        "                    Publication.attempt == attempt,\n"
        '                    Publication.state == "pending",\n',
        "",
        "P3",
    ),
    "fail-ignores-attempt": (
        "            if row is None or row.attempt != attempt:",
        "            if row is None:",
        "P3",
    ),
    "no-writer-reservation": (
        "            if locked.rowcount != 1:",
        "            if False:",
        "P4",
    ),
    "complete-keeps-reservation": (
        "            await session.execute(\n"
        "                update(Writer)\n"
        "                .where(\n"
        '                    Writer.dataset == "shared-identity-publication",\n'
        "                    Writer.owner == attempt,\n"
        "                )\n"
        "                .values(owner=None)\n"
        "            )\n"
        "            for event in (",
        "            for event in (",
        "P4",
    ),
    "fail-always-new-event": (
        "            event = await session.get(RecoveryEvent, event_id)\n"
        "            if event is None:\n",
        "            event = await session.get(RecoveryEvent, event_id)\n"
        "            if False:\n",
        "P5",
    ),
    "no-replace-recovery-choice": (
        '                and json.loads(row.plan).get("operation") == "identity_replace"\n'
        '                and method != "replace"\n',
        '                and json.loads(row.plan).get("operation") == "identity_replace"\n'
        '                and method not in {"replace", "reconcile"}\n',
        "P5",
    ),
    "no-withdrawn-guard": (
        '            if row and row.state == "withdrawn" and method != "withdraw":',
        "            if False:",
        "P5",
    ),
}


ACCEPTED, REFUSED, HANDLED = "accepted", "refused", "handled"


def verdict(ok):
    return ACCEPTED if ok else REFUSED


class Violation(Exception):
    def __init__(self, prop, message):
        self.prop = prop
        super().__init__(f"{prop}: {message}")


@cache
def fixture():
    return json.loads(FIXTURE.read_text())


DATASET = fixture()["dataset_id"]


def source_id(s):
    return str(uuid5(NAMESPACE_URL, f"ledger-check-source:{s}"))


@cache
def src(s, revision):
    """The saved description of source s at a revision; one per (s, revision)."""
    payload = dict(fixture(), identity_data_id=source_id(s), revision=revision)
    return IdentitySource.model_validate_json(json.dumps(payload))


def publish_plan(revision):
    # publish.py:289-297. The ledger reads only "operation" from it.
    return dict(operation="identity_publish", revision=revision, runtime_profile={})


def replace_plan(s, revision):
    # replace.py:126-131 for a current row at `revision`.
    return dict(
        operation="identity_replace",
        revision=revision + 1,
        previous_description=src(s, revision).model_dump_json(),
        runtime_profile={},
    )


def withdraw_plan(revision):
    # withdraw.py:60-83 when the saved plan is not a withdrawal.
    return dict(operation="identity_withdraw", revision=revision, runtime_profile={})


@dataclass
class Attempt:
    id: str
    source: int
    revision: int
    method: str


@dataclass
class Writer:
    holds: Attempt | None = None
    stuck: bool = False
    # The last call that ended an attempt: ("complete", attempt, state) or
    # ("fail", attempt, stage). Repeat resends it.
    last: tuple | None = None


@dataclass
class Ghost:
    """What the checker knows happened to one source, independent of the store."""

    outcome: str | None = None  # None, open, current, withdrawn, failed
    revision: int = 0
    attempt: str | None = None  # the last attempt begin() accepted
    # Every distinct row this source had on the path, as a caller could have
    # read it: None (no row) or (revision, state, plan). Callers read the row
    # and call begin() later, so any earlier read can reach begin().
    views: list = field(default_factory=lambda: [None])
    # The attempt and revision of the last row seen current (for Reject).
    served: tuple | None = None


@dataclass
class World:
    writers: list
    sources: list


@dataclass(frozen=True)
class Begin:
    writer: int
    source: int
    method: str
    expected: int
    revision: int
    plan: dict = field(compare=False, hash=False)

    @property
    def label(self):
        return (
            f"W{self.writer + 1} {self.method} S{self.source + 1} "
            f"rev={self.revision} expect={self.expected}"
        )


@dataclass(frozen=True)
class Finish:
    """A held attempt's store work ends: stage None succeeds, else it fails there."""

    writer: int
    stage: str | None

    @property
    def label(self):
        return f"W{self.writer + 1} " + (
            "complete" if self.stage is None else f"fail@{self.stage}"
        )


@dataclass(frozen=True)
class Crash:
    """The writer process dies holding its attempt; nothing is released."""

    writer: int

    @property
    def label(self):
        return f"W{self.writer + 1} crash"


@dataclass(frozen=True)
class Repeat:
    """A duplicated or delayed copy of the writer's last complete() or fail()."""

    writer: int

    @property
    def label(self):
        return f"W{self.writer + 1} repeat"


@dataclass(frozen=True)
class Reject:
    """retrieve.py:88-91 fails a row it read as current but could not validate."""

    source: int

    @property
    def label(self):
        return f"reject S{self.source + 1}"


@dataclass(frozen=True)
class Observation:
    rows: dict  # source index -> row dict from RecordStore.rows()
    events: dict  # source index -> list of event details
    owner: str | None


def served(row):
    # retrieve.py:21, the retrieval eligibility test.
    return (
        row is not None
        and row["state"] == "current"
        and row["revision"] == row["verified_revision"]
    )


def view_of(row):
    if row is None:
        return None
    return (row["revision"], row["state"], row["plan"])


def intents(w, s, view):
    """Begin calls the callers build from one read of the row (view).

    The callers' own pre-checks (publish.py:274-282, replace.py:88-125,
    withdraw.py:42-45) are skipped on purpose: they read the row without the
    reservation, so begin() is the guard that must hold on its own.
    """
    if view is None:
        return [Begin(w, s, "publish", 0, 1, publish_plan(1))]
    revision, state, plan = view
    ops = [
        Begin(w, s, "reconcile", revision, revision, publish_plan(revision)),
        Begin(w, s, "replace", revision, revision + 1, replace_plan(s, revision)),
    ]
    if plan.get("operation") == "identity_replace":  # replace.py:100-118
        ops.append(Begin(w, s, "replace", revision, revision, dict(plan)))
    reuse = state != "withdrawn" and plan.get("operation") == "identity_withdraw"
    ops.append(
        Begin(
            w,
            s,
            "withdraw",
            revision,
            revision,
            dict(plan) if reuse else withdraw_plan(revision),
        )
    )
    return ops


def candidates(world):
    # Writers that never began and sources that never had a row are
    # interchangeable, so only the first of each kind starts anything.
    fresh_writer = next((w for w, x in enumerate(world.writers) if x == Writer()), None)
    fresh_source = next(
        (s for s, g in enumerate(world.sources) if g.views == [None]), None
    )
    ops = []
    for w, writer in enumerate(world.writers):
        if writer.stuck:
            continue
        if writer.holds is not None:
            ops.append(Finish(w, None))
            ops.append(Finish(w, FAIL_STAGE[writer.holds.method]))
            ops.append(Crash(w))
            continue
        if writer == Writer() and w != fresh_writer:
            continue
        seen = set()
        for s, ghost in enumerate(world.sources):
            if ghost.views == [None] and s != fresh_source:
                continue
            for view in reversed(ghost.views):
                for op in intents(w, s, view):
                    if op.label not in seen:
                        seen.add(op.label)
                        ops.append(op)
        if writer.last is not None:
            ops.append(Repeat(w))
    for s, ghost in enumerate(world.sources):
        if ghost.served is not None:
            ops.append(Reject(s))
    return ops


class Harness:
    def __init__(self, storage):
        self.storage = storage
        self.engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        self.store = storage.RecordStore(
            async_sessionmaker(self.engine, expire_on_commit=False)
        )
        self.tables = storage.Base.metadata.sorted_tables

    async def snapshot(self):
        async with self.engine.connect() as conn:
            return {
                t.name: [r._asdict() for r in (await conn.execute(select(t))).all()]
                for t in self.tables
            }

    async def restore(self, snap):
        async with self.engine.begin() as conn:
            for t in self.tables:
                await conn.execute(delete(t))
            for t in self.tables:
                if snap[t.name]:
                    await conn.execute(insert(t), snap[t.name])

    async def observe(self, sources):
        index = {source_id(s): s for s in range(sources)}
        rows = {index[r["source"]]: r for r in await self.store.rows(DATASET)}
        events = {s: [] for s in range(sources)}
        for e in await self.store.events(DATASET):
            events[index[e["identity_data_id"]]].append(e)
        async with self.engine.connect() as conn:
            owner = (
                await conn.execute(
                    select(self.storage.Writer.owner).where(
                        self.storage.Writer.dataset == LOCK_SCOPE
                    )
                )
            ).scalar_one_or_none()
        return Observation(rows, events, owner)

    async def call(self, name, *args, **kwargs):
        """Run one RecordStore call; return (accepted, value or refusal code)."""
        try:
            return True, await getattr(self.store, name)(*args, **kwargs)
        except IntentError as exc:
            return False, exc.code

    async def fail_attempt(self, world, writer, attempt, stage):
        ok, _ = await self.call(
            "fail",
            src(attempt.source, attempt.revision),
            attempt.id,
            stage,
            IntentError("injected_failure", f"ledger_check {stage}"),
            origin="ledger_check",
        )
        if ok:
            world.sources[attempt.source].outcome = "failed"
            writer.holds, writer.last = None, ("fail", attempt, stage)
        else:
            # The caller raises recovery_record_failed and keeps the reservation.
            writer.stuck = True
        return ok

    async def apply(self, world, op):
        """Apply op the way its caller drives RecordStore.

        Returns ACCEPTED, REFUSED (the call raised and the caller stops), or
        HANDLED (the call raised and the caller recorded a failure instead).
        """
        match op:
            case Begin():
                ok, value = await self.call(
                    "begin",
                    src(op.source, op.revision),
                    expected_revision=op.expected,
                    plan=copy.deepcopy(op.plan),
                    method=op.method,
                    origin="ledger_check",
                )
                if ok:
                    world.writers[op.writer].holds = Attempt(
                        value, op.source, op.revision, op.method
                    )
                    ghost = world.sources[op.source]
                    ghost.outcome, ghost.revision = "open", op.revision
                    ghost.attempt = value
                return verdict(ok)
            case Finish(stage=None):
                writer = world.writers[op.writer]
                attempt = writer.holds
                source = src(attempt.source, attempt.revision)
                if attempt.method != "withdraw":
                    ok, _ = await self.call("assert_pending", source, attempt.id)
                    if not ok:
                        if attempt.method == "replace":
                            await self.fail_attempt(
                                world, writer, attempt, "replacement_publish"
                            )
                            return HANDLED
                        # publish.py:340 runs before its try block.
                        writer.stuck = True
                        return REFUSED
                state = "withdrawn" if attempt.method == "withdraw" else "current"
                ok, _ = await self.call("complete", source, attempt.id, state=state)
                if not ok:
                    await self.fail_attempt(
                        world, writer, attempt, ACK_STAGE[attempt.method]
                    )
                    return HANDLED
                self.completed(world, attempt, state)
                writer.holds, writer.last = None, ("complete", attempt, state)
                return ACCEPTED
            case Finish():
                writer = world.writers[op.writer]
                return verdict(
                    await self.fail_attempt(world, writer, writer.holds, op.stage)
                )
            case Crash():
                world.writers[op.writer].stuck = True
                return ACCEPTED
            case Repeat():
                kind, attempt, detail = world.writers[op.writer].last
                source = src(attempt.source, attempt.revision)
                if kind == "complete":
                    ok, _ = await self.call(
                        "complete", source, attempt.id, state=detail
                    )
                    if ok:
                        self.completed(world, attempt, detail)
                    return verdict(ok)
                ok, _ = await self.call(
                    "fail",
                    source,
                    attempt.id,
                    detail,
                    IntentError("injected_failure", "repeated"),
                    origin="ledger_check",
                )
                if ok:
                    world.sources[attempt.source].outcome = "failed"
                return verdict(ok)
            case Reject():
                attempt, revision = world.sources[op.source].served
                ok, _ = await self.call(
                    "fail",
                    src(op.source, revision),
                    attempt,
                    "retrieval_validation",
                    IntentError("generated_source_changed", "ledger_check reject"),
                )
                if ok:
                    world.sources[op.source].outcome = "failed"
                return verdict(ok)

    @staticmethod
    def completed(world, attempt, state):
        ghost = world.sources[attempt.source]
        ghost.outcome = state
        if state == "current":
            ghost.served = (attempt.id, attempt.revision)


def op_source(world_before, op):
    match op:
        case Begin() | Reject():
            return op.source
        case Finish():
            return world_before.writers[op.writer].holds.source
        case Repeat():
            return world_before.writers[op.writer].last[1].source
    return None


def last_attempt(world, op):
    return world.writers[op.writer].last[1].id


def unresolved(events):
    return [e for e in events if e.get("resolved_at") is None]


def check(world_before, world, before, after, op, result):
    """Raise Violation if the step broke a property. See the skill for P1-P5."""
    touched = op_source(world_before, op)

    # P1: a source is served exactly when its last accepted attempt completed
    # as current, and then at that attempt's revision and description.
    for s, ghost in enumerate(world.sources):
        row = after.rows.get(s)
        if served(row) != (ghost.outcome == "current"):
            raise Violation(
                "P1",
                f"S{s + 1} served={served(row)} but its last attempt is "
                f"{ghost.outcome}; row={brief(row)}",
            )
        if ghost.outcome == "current" and (
            row["revision"] != ghost.revision
            or json.loads(row["description"])
            != json.loads(src(s, ghost.revision).model_dump_json())
        ):
            raise Violation(
                "P1", f"S{s + 1} served a description other than the completed one"
            )
        if ghost.outcome == "withdrawn" and row["state"] != "withdrawn":
            raise Violation("P1", f"S{s + 1} withdrawal completed but row={brief(row)}")

    # P2: a step on one source leaves every other source's row and events alone.
    for s in range(len(world.sources)):
        if s != touched and (
            before.rows.get(s) != after.rows.get(s)
            or before.events[s] != after.events[s]
        ):
            raise Violation("P2", f"step {op.label!r} changed S{s + 1}")

    # P3: a refused call changes nothing; begin() with an expected revision
    # other than the saved one is refused; an acknowledgement for an attempt
    # that already ended, or that a later begin() replaced, is refused.
    accepted = result == ACCEPTED
    if result == REFUSED and before != after:
        raise Violation("P3", "a refused call changed the ledger")
    if accepted and isinstance(op, Repeat | Reject):
        kind, attempt = (
            ("fail", world_before.sources[op.source].served[0])
            if isinstance(op, Reject)
            else (
                world_before.writers[op.writer].last[0],
                last_attempt(world_before, op),
            )
        )
        latest = world_before.sources[touched].attempt
        if kind == "complete" or attempt != latest:
            raise Violation(
                "P3",
                f"stale {kind} accepted for S{touched + 1}: the attempt "
                "already ended or a later begin() replaced it",
            )
    if isinstance(op, Begin) and accepted:
        actual = before.rows.get(op.source, {}).get("revision", 0)
        if op.expected != actual:
            raise Violation(
                "P3",
                f"begin with expected_revision={op.expected} accepted at saved "
                f"revision {actual}",
            )

    # P4: at most one attempt is open, and the reservation names exactly it.
    open_attempts = [w.holds.id for w in world.writers if w.holds is not None]
    if len(open_attempts) > 1:
        raise Violation("P4", "two writers hold open attempts at once")
    if after.owner != (open_attempts[0] if open_attempts else None):
        raise Violation(
            "P4",
            f"reservation owner={after.owner} but open attempts={open_attempts}",
        )

    # P5: recovery is explicit and forward: revisions never go back, a failed
    # replacement or withdrawal resumes only through the same method, each
    # failed row has exactly one open recovery event, and only a completion
    # resolves it, once.
    for s in range(len(world.sources)):
        old, new = before.rows.get(s), after.rows.get(s)
        if old and (new is None or new["revision"] < old["revision"]):
            raise Violation(
                "P5", f"S{s + 1} revision went back: {brief(old)} -> {brief(new)}"
            )
        open_events = unresolved(after.events[s])
        state = new["state"] if new else None
        allowed = {"failed": (1,), "pending": (0, 1)}.get(state, (0,))
        if len(open_events) not in allowed:
            raise Violation(
                "P5",
                f"S{s + 1} is {state} with {len(open_events)} unresolved recovery events",
            )
        now_by_id = {e["recovery_event_id"]: e for e in after.events[s]}
        for e in before.events[s]:
            if e.get("resolved_at") is not None and (
                now_by_id.get(e["recovery_event_id"], {}).get("resolved_at")
                != e["resolved_at"]
            ):
                raise Violation("P5", f"S{s + 1} resolved recovery event reopened")
    if isinstance(op, Begin) and accepted:
        prior = before.rows.get(op.source)
        actual = prior["revision"] if prior else 0
        advance = (prior is None and op.method == "publish") or (
            prior is not None and prior["state"] == "current" and op.method == "replace"
        )
        if op.revision != actual + (1 if advance else 0):
            raise Violation(
                "P5",
                f"begin moved S{op.source + 1} from revision {actual} to "
                f"{op.revision} through {op.method}",
            )
    if isinstance(op, Begin) and accepted and op.source in before.rows:
        prior = before.rows[op.source]
        need = {
            "identity_replace": "replace",
            "identity_withdraw": "withdraw",
        }.get(prior["plan"].get("operation"))
        if prior["state"] == "failed" and need and op.method != need:
            raise Violation(
                "P5",
                f"failed {prior['plan']['operation']} resumed through {op.method}",
            )
        if prior["state"] == "withdrawn" and op.method != "withdraw":
            raise Violation("P5", f"withdrawn source restarted through {op.method}")
    if accepted and isinstance(op, Finish) and op.stage is None:
        attempt = world_before.writers[op.writer].holds
        was_open = {
            e["recovery_event_id"] for e in unresolved(before.events[attempt.source])
        }
        for e in after.events[attempt.source]:
            if (
                e["recovery_event_id"] in was_open
                and e.get("resolving_attempt") != attempt.id
            ):
                raise Violation("P5", "a completion did not resolve the open event")


def brief(row):
    if row is None:
        return "none"
    return (
        f"r{row['revision']}/{row['state']}/verified={row['verified_revision']}"
        f"/{row['plan'].get('operation')}"
    )


@dataclass
class Run:
    depth: int
    sources: int
    writers: int
    skip_probability: float = 0.0
    seed: int = 0
    replay: list | None = None
    mutant: str | None = None
    nodes: int = 0
    skipped: int = 0
    noops: int = 0
    sequences: int = 0
    seconds: float = 0.0
    failure: dict | None = None


def load_storage(mutant):
    if mutant is None:
        return real_storage
    old, new, _ = MUTANTS[mutant]
    text = STORAGE_PATH.read_text()
    if text.count(old) != 1:
        raise SystemExit(
            f"mutant {mutant} no longer matches storage.py exactly once; "
            "update it in support/ledger_check.py MUTANTS"
        )
    module = types.ModuleType(f"cognee_lab.identity._ledger_mutant_{mutant}")
    module.__package__ = "cognee_lab.identity"
    sys.modules[module.__name__] = module
    exec(compile(text.replace(old, new), str(STORAGE_PATH), "exec"), module.__dict__)
    return module


async def check_ledger(run: Run) -> Run:
    harness = Harness(load_storage(run.mutant))
    await harness.store.initialize()
    rng = random.Random(run.seed)
    world = World(
        [Writer() for _ in range(run.writers)], [Ghost() for _ in range(run.sources)]
    )
    started = time.perf_counter()

    async def explore(world, before, path):
        run.nodes += 1
        if len(path) == run.depth:
            run.sequences += 1
            return
        ops = candidates(world)
        if run.replay is not None:
            if len(path) == len(run.replay):
                run.sequences += 1
                return
            ops = [op for op in ops if op.label == run.replay[len(path)]]
            if not ops:
                raise SystemExit(
                    f"step {len(path) + 1} {run.replay[len(path)]!r} is not a "
                    f"candidate after: {'; '.join(path) or '(start)'}"
                )
        snap, dirty, explored = None, False, 0
        for op in ops:
            if run.skip_probability and rng.random() < run.skip_probability:
                run.skipped += 1
                continue
            if snap is None:
                snap = await harness.snapshot()
            elif dirty:
                await harness.restore(snap)
            explored += 1
            child = copy.deepcopy(world)
            result = await harness.apply(child, op)
            after = await harness.observe(run.sources)
            for s, ghost in enumerate(child.sources):
                view = view_of(after.rows.get(s))
                if view != ghost.views[-1]:
                    ghost.views.append(view)
            steps = [*path, op.label]
            try:
                check(world, child, before, after, op, result)
            except Violation as exc:
                run.failure = dict(
                    property=exc.prop,
                    message=str(exc),
                    sequence=steps,
                    before={f"S{s + 1}": brief(r) for s, r in before.rows.items()},
                    after={f"S{s + 1}": brief(r) for s, r in after.rows.items()},
                )
                return
            if child == world and after == before:
                # Nothing changed, so every sequence after this step is a
                # sequence after its parent, which this search already covers.
                run.noops += 1
                run.nodes += 1
                run.sequences += 1
                dirty = False
                continue
            dirty = True
            await explore(child, after, steps)
            if run.failure:
                return
        if not explored:
            run.sequences += 1

    await explore(world, await harness.observe(run.sources), [])
    run.seconds = time.perf_counter() - started
    await harness.engine.dispose()
    return run


def report(run: Run) -> str:
    if run.replay is not None:
        mode = "replay"
    elif run.skip_probability:
        mode = f"sampled (P={run.skip_probability}, seed={run.seed})"
    else:
        mode = "verified within bound" if not run.failure else "exhaustive"
    verdict = "FAIL" if run.failure else "INCONCLUSIVE" if run.nodes == 1 else "PASS"
    head = (
        f"{verdict} {mode}: depth={run.depth} "
        f"sources={run.sources} writers={run.writers}"
        + (f" mutant={run.mutant}" if run.mutant else "")
        + f"\nnodes={run.nodes} skipped={run.skipped} noops={run.noops} "
        f"sequences={run.sequences} seconds={run.seconds:.2f}"
    )
    if not run.failure:
        return head
    f = run.failure
    steps = "\n".join(f"  {i}. {label}" for i, label in enumerate(f["sequence"], 1))
    rerun = (
        "uv run python support/ledger_check.py "
        f"--sources {run.sources} --writers {run.writers} "
        + (f"--mutant {run.mutant} " if run.mutant else "")
        + f"--replay {'; '.join(f['sequence'])!r}"
    )
    return (
        f"{head}\n{f['message']}\nshortest failing sequence ({len(f['sequence'])} "
        f"steps; search depth {run.depth}, P={run.skip_probability}, "
        f"seed={run.seed}):\n{steps}\n"
        f"rows before last step: {f['before']}\nrows after last step: {f['after']}\n"
        f"rerun: {rerun}"
    )


def shrink(run: Run) -> Run:
    """Search shallower bounds so a failure is reported at its shortest length."""
    while run.failure and len(run.failure["sequence"]) > 1:
        shorter = asyncio.run(
            check_ledger(
                Run(
                    depth=len(run.failure["sequence"]) - 1,
                    sources=run.sources,
                    writers=run.writers,
                    mutant=run.mutant,
                )
            )
        )
        if not shorter.failure:
            break
        run.failure = shorter.failure
    return run


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--sources", type=int, choices=[1, 2], default=2)
    parser.add_argument("--writers", type=int, choices=[1, 2], default=2)
    parser.add_argument("--skip-probability", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--replay", help="'; '-separated step labels from a failure report"
    )
    parser.add_argument("--mutant", choices=sorted(MUTANTS))
    parser.add_argument(
        "--mutants",
        action="store_true",
        help="run every scratch break of storage.py and report which were caught",
    )
    args = parser.parse_args(argv)
    if not 0 <= args.skip_probability < 1:
        parser.error("--skip-probability must satisfy 0 <= P < 1")
    if args.depth < 1:
        parser.error("--depth must be at least 1")
    return args


def main(argv=None):
    args = parse(argv)
    base = dict(
        depth=args.depth,
        sources=args.sources,
        writers=args.writers,
        skip_probability=args.skip_probability,
        seed=args.seed,
    )
    if args.mutants:
        missed = []
        for name, (_, _, prop) in MUTANTS.items():
            run = shrink(asyncio.run(check_ledger(Run(**base, mutant=name))))
            got = run.failure["property"] if run.failure else None
            print(
                f"{name}: expected {prop}, "
                + (
                    f"caught {got} in {len(run.failure['sequence'])} steps: "
                    + "; ".join(run.failure["sequence"])
                    if got
                    else f"MISSED ({run.nodes} nodes)"
                )
            )
            if got is None:
                missed.append(name)
        return 1 if missed else 0
    replay = [s.strip() for s in args.replay.split(";")] if args.replay else None
    if replay:
        base["depth"] = len(replay)
    run = asyncio.run(check_ledger(Run(**base, replay=replay, mutant=args.mutant)))
    if replay is None:
        run = shrink(run)
    print(report(run))
    # Skipping every first step checks nothing, which is not a pass.
    return 1 if run.failure else 2 if run.nodes == 1 else 0


if __name__ == "__main__":
    sys.exit(main())
