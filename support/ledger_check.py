"""Bounded exhaustive check of the identity publication ledger (RecordStore).

Drives the real RecordStore in src/cognee_lab/identity/storage.py on a fresh
in-memory SQLite store through every sequence of ledger operations up to
--depth, and checks six properties after every step. See
.claude/skills/identity-ledger/SKILL.md for the properties, bounds and scope.

    uv run python support/ledger_check.py
    uv run python support/ledger_check.py --depth 6
    uv run python support/ledger_check.py --depth 8 --skip-probability 0.5 --seed 2
    uv run python support/ledger_check.py --replay "W1 publish S1 rev=1 expect=0 plan=publish; W1 complete"
    uv run python support/ledger_check.py --mutants
"""

import argparse
import asyncio
import copy
import json
import multiprocessing
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from cognee_lab.identity.validation import IntentError
from ledger_model import (
    DATASET,
    METHODS,
    Ack,
    Attempt,
    Begin,
    Crash,
    Finish,
    FORGOTTEN_AT,
    VARIANT_TAGS,
    Ghost,
    Plan,
    Reject,
    Repeat,
    Served,
    World,
    Writer,
    background,
    candidates,
    description,
    completion,
    other,
    source_id,
    saved_json,
    variant_of,
    view_of,
)
from ledger_mutants import DEEP_MUTANTS, MUTANTS, load_storage
from ledger_properties import (
    ACCEPTED,
    HANDLED,
    REFUSED,
    Observation,
    Step,
    first_violation,
    step_kind,
    unresolved,
)

LOCK_SCOPE = "shared-identity-publication"
DEFAULT_DEPTH = 5


async def call(awaitable):
    """Run one RecordStore call; return (accepted, value or refusal code)."""
    try:
        return True, await awaitable
    except IntentError as exc:
        return False, exc.code


class Unreadable(Exception):
    """rows() refused the store after a step: a forgotten row kept content,
    or another row holds no description."""


class Harness:
    def __init__(self, storage):
        self.storage = storage
        self.engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        self.store = storage.RecordStore(
            async_sessionmaker(self.engine, expire_on_commit=False)
        )
        self.tables = storage.Base.metadata.sorted_tables

    async def forget_background(self):
        """Every sequence starts with the background source forgotten, as
        forget leaves it: an erasure retry needs a forgotten source. Written
        to the table directly, so a break in the store cannot stop it."""
        from cognee_lab.identity.models import Tombstone

        source = background()
        async with self.engine.begin() as conn:
            await conn.execute(
                insert(self.storage.Publication),
                dict(
                    dataset=DATASET,
                    source=str(source.identity_data_id),
                    revision=1,
                    verified_revision=1,
                    state="forgotten",
                    attempt="background",
                    description=Tombstone.of(
                        source, forgotten_at=FORGOTTEN_AT
                    ).model_dump_json(),
                    plan=json.dumps(dict(operation="identity_forget", revision=1)),
                ),
            )

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
        try:
            rows = {
                index[r.source]: r
                for r in await self.store.rows(DATASET)
                if r.source in index
            }
        except IntentError as exc:
            # rows() refuses a forgotten row that is not a tombstone, and any
            # other row whose description does not parse.
            raise Unreadable(exc.code, str(exc)) from exc
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

    async def fail_attempt(self, world, writer, attempt, stage, source):
        ok, _ = await call(
            self.store.fail(
                source,
                attempt.id,
                stage,
                IntentError("injected_failure", f"ledger_check {stage}"),
                origin="ledger_check",
            )
        )
        if ok:
            world.sources[attempt.source].outcome = "failed"
            writer.holds, writer.last = None, Ack("fail", attempt, stage)
        else:
            # The caller raises recovery_record_failed and keeps the reservation.
            writer.stuck = True
        return HANDLED if ok else REFUSED

    async def apply(self, world, op):
        """Apply op the way its caller drives RecordStore.

        Returns ACCEPTED, REFUSED (the call raised and the caller stops), or
        HANDLED (the call raised and the caller recorded a failure instead).
        """
        match op:
            case Begin():
                ok, value = await call(
                    self.store.begin(
                        description(op.source, op.revision, op.variant),
                        expected_revision=op.expected,
                        plan=op.plan.as_dict(op.source),
                        method=op.method,
                        origin="ledger_check",
                    )
                )
                if not ok:
                    return REFUSED
                writer, ghost = world.writers[op.writer], world.sources[op.source]
                writer.begun += 1
                world.names[value] = f"W{op.writer + 1}#{writer.begun}"
                writer.holds = Attempt(
                    value,
                    op.source,
                    op.revision,
                    op.variant,
                    op.method,
                    ghost.outcome == "failed",
                )
                ghost.outcome, ghost.revision = "open", op.revision
                ghost.variant, ghost.attempt = op.variant, value
                return ACCEPTED
            case Finish(stage=None):
                writer = world.writers[op.writer]
                attempt = writer.holds
                method = METHODS[attempt.method]
                source = description(
                    attempt.source,
                    attempt.revision,
                    other(attempt.variant) if op.alt else attempt.variant,
                )
                if method.asserts_pending:
                    ok, _ = await call(self.store.assert_pending(source, attempt.id))
                    if not ok:
                        if method.on_assert_refused is None:
                            writer.stuck = True
                            return REFUSED
                        return await self.fail_attempt(
                            world, writer, attempt, method.on_assert_refused, source
                        )
                ok, _ = await call(
                    self.store.complete(
                        source,
                        attempt.id,
                        state=method.done_state,
                        **completion(method, attempt),
                    )
                )
                if not ok:
                    return await self.fail_attempt(
                        world, writer, attempt, method.ack_stage, source
                    )
                self.completed(world, attempt, method.done_state)
                writer.holds = None
                writer.last = Ack("complete", attempt, method.done_state)
                return ACCEPTED
            case Finish():
                writer = world.writers[op.writer]
                attempt = writer.holds
                source = description(attempt.source, attempt.revision, attempt.variant)
                result = await self.fail_attempt(
                    world, writer, attempt, op.stage, source
                )
                return ACCEPTED if result == HANDLED else REFUSED
            case Crash():
                world.writers[op.writer].stuck = True
                return ACCEPTED
            case Repeat():
                kind, attempt, detail = world.writers[op.writer].last
                source = description(attempt.source, attempt.revision, attempt.variant)
                if kind == "complete":
                    # A duplicated finish runs the whole path again: the guard
                    # before graph writes, then complete(). If the guard lets an
                    # ended attempt through, its graph writes would start.
                    if METHODS[attempt.method].asserts_pending:
                        ok, _ = await call(
                            self.store.assert_pending(source, attempt.id)
                        )
                        if ok:
                            return ACCEPTED
                    ok, _ = await call(
                        self.store.complete(
                            source,
                            attempt.id,
                            state=detail,
                            **completion(METHODS[attempt.method], attempt),
                        )
                    )
                    if ok:
                        self.completed(world, attempt, detail)
                    return ACCEPTED if ok else REFUSED
                ok, _ = await call(
                    self.store.fail(
                        source,
                        attempt.id,
                        detail,
                        IntentError("injected_failure", "repeated"),
                        origin="ledger_check",
                    )
                )
                if ok:
                    world.sources[attempt.source].outcome = "failed"
                return ACCEPTED if ok else REFUSED
            case Reject():
                attempt, revision = world.sources[op.source].served
                # retrieve.py passes the description it read; fail() uses only
                # its ids, revision and inputs, which every variant shares.
                ok, _ = await call(
                    self.store.fail(
                        description(op.source, revision),
                        attempt,
                        "retrieval_validation",
                        IntentError("generated_source_changed", "ledger_check reject"),
                    )
                )
                if ok:
                    world.sources[op.source].outcome = "failed"
                return ACCEPTED if ok else REFUSED

    @staticmethod
    def completed(world, attempt, state):
        ghost = world.sources[attempt.source]
        ghost.outcome = state
        if state == "current":
            ghost.served = Served(attempt.id, attempt.revision)

    async def recover(self, s, row):
        """Run the explicit recovery for a failed row; say why it did not complete.

        The method that resumes the saved plan begins with the saved revision,
        description and plan, then completes. The store is restored after.
        """
        view = view_of(s, row)
        method = next(m for m in METHODS.values() if m.recovers == view.plan.operation)
        source = description(s, view.revision, view.variant)
        snap = await self.snapshot()
        ok, value = await call(
            self.store.begin(
                source,
                expected_revision=view.revision,
                plan=view.plan.as_dict(s),
                method=method.name,
                origin="ledger_check",
            )
        )
        why = None if ok else f"{method.name} begin refused ({value})"
        if ok and method.asserts_pending:
            ok, code = await call(self.store.assert_pending(source, value))
            why = None if ok else f"assert_pending refused ({code})"
        if ok:
            ok, code = await call(
                self.store.complete(
                    source,
                    value,
                    state=method.done_state,
                    **completion(
                        method,
                        Attempt(
                            value, s, view.revision, view.variant, method.name, True
                        ),
                    ),
                )
            )
            why = None if ok else f"complete refused ({code})"
        await self.restore(snap)
        return why


# A pass that never reaches one of these says nothing about it, so the run is
# INCONCLUSIVE: row states, accepted calls of each step kind, a publish
# accepted on a forgotten row (the re-add), an erasure retry that superseded a
# failed replacement's description and one that superseded a failed
# publication's, and a failed row that completed as current again.
REACHABLE = (
    "row current",
    "row failed",
    "row withdrawn",
    "row forgotten",
    "row pending",
    *(f"accepted {m}" for m in METHODS),
    "accepted readd",
    "forget withdrawn",
    "forget failed publish",
    "erasure retry replace",
    "erasure retry reconcile",
    "accepted complete",
    "accepted fail",
    "accepted crash",
    "accepted repeat",
    "accepted reject",
    "recovered",
)


def tally(reached, step):
    for row in step.obs_after.rows.values():
        reached[f"row {row.state}"] += 1
    if not step.accepted:
        return
    reached[f"accepted {step_kind(step.op)}"] += 1
    if isinstance(step.op, Begin) and step.op.method == "publish":
        prior = step.obs_before.rows.get(step.op.source)
        if prior and prior.state == "forgotten":
            reached["accepted readd"] += 1
    if isinstance(step.op, Begin) and step.op.method == "forget":
        prior = step.obs_before.rows.get(step.op.source)
        if prior and prior.state == "withdrawn":
            reached["forget withdrawn"] += 1
        if prior and prior.state == "failed":
            if prior.plan["operation"] == "identity_publish":
                reached["forget failed publish"] += 1
    if isinstance(step.op, Begin) and step.op.plan.erased:
        prior = Plan.of(step.op.source, step.obs_before.rows[step.op.source].plan)
        if step.op.plan.erased != prior.erased:
            reached[f"erasure retry {step.op.method}"] += 1
    if isinstance(step.op, Finish) and step.op.stage is None:
        attempt = step.model_before.writers[step.op.writer].holds
        if attempt.from_failed and METHODS[attempt.method].done_state == "current":
            reached["recovered"] += 1


@dataclass(frozen=True)
class Config:
    depth: int = DEFAULT_DEPTH
    sources: int = 2
    writers: int = 2
    skip_probability: float = 0.0
    seed: int = 0
    mutant: str | None = None
    replay: tuple[str, ...] | None = None


@dataclass
class Failure:
    prop: str
    message: str
    sequence: list
    before: str
    after: str


@dataclass
class Result:
    config: Config
    nodes: int = 0
    skipped: int = 0
    noops: int = 0
    sequences: int = 0
    seconds: float = 0.0
    reached: Counter = field(default_factory=Counter)
    failure: Failure | None = None
    trace: list = field(default_factory=list)  # --replay: state after each step

    @property
    def missing(self):
        return [k for k in REACHABLE if not self.reached[k]]

    @property
    def verdict(self):
        if self.failure:
            return "FAIL"
        # A search that never reached an outcome in REACHABLE checked no step
        # that leads to it, so its pass is not evidence. A replay checks only
        # its own steps and makes no claim about coverage.
        if self.config.replay is None and self.missing:
            return "INCONCLUSIVE"
        return "PASS"


class NotACandidate(Exception):
    pass


def render(world, obs):
    names = world.names
    lines = []
    for s in sorted(range(len(world.sources))):
        row = obs.rows.get(s)
        if row is None:
            lines.append(f"S{s + 1}: no row")
            continue
        events = obs.events[s]
        resolvers = sorted(
            names.get(e["resolving_attempt"], "?")
            for e in events
            if e.get("resolving_attempt")
        )
        lines.append(
            f"S{s + 1}: r{row.revision}"
            + VARIANT_TAGS[variant_of(s, saved_json(row))]
            + f"/{row.state}/verified={row.verified_revision}"
            f"/plan={Plan.of(s, row.plan).tag}/attempt={names.get(row.attempt, '?')}"
            f" events={len(events)} unresolved={len(unresolved(events))}"
            f" resolved_by={resolvers}"
        )
    owner = names.get(obs.owner, obs.owner) if obs.owner else "free"
    return "; ".join(lines) + f"; reservation={owner}"


async def check_ledger(config: Config) -> Result:
    harness = Harness(load_storage(config.mutant))
    await harness.store.initialize()
    await harness.forget_background()
    rng = random.Random(config.seed)
    result = Result(config)
    replay = config.replay
    depth = len(replay) if replay is not None else config.depth
    world = World(
        [Writer() for _ in range(config.writers)],
        [Ghost() for _ in range(config.sources)],
    )
    started = time.perf_counter()

    async def explore(world, before, path):
        result.nodes += 1
        if len(path) == depth:
            result.sequences += 1
            return
        ops = candidates(world)
        if replay is not None:
            ops = [op for op in ops if op.label == replay[len(path)]]
            if not ops:
                raise NotACandidate(
                    f"step {len(path) + 1} {replay[len(path)]!r} is not a "
                    f"candidate after: {'; '.join(path) or '(start)'}"
                )
        snap, dirty, explored = None, False, 0
        for op in ops:
            if config.skip_probability and rng.random() < config.skip_probability:
                result.skipped += 1
                continue
            if snap is None:
                snap = await harness.snapshot()
            elif dirty:
                await harness.restore(snap)
            explored += 1
            child = copy.deepcopy(world)
            outcome = await harness.apply(child, op)
            if outcome == REFUSED and await harness.snapshot() == snap:
                # Same tables, same observation: skip the rows()/events() reads.
                after = before
            else:
                try:
                    after = await harness.observe(config.sources)
                except Unreadable as exc:
                    # A forgotten row that is not a tombstone breaks P7; any
                    # other row that holds no description breaks P1.
                    result.failure = Failure(
                        "P7" if exc.args[0] == "forgotten_format" else "P1",
                        f"rows() refused the store: {exc.args[1]}",
                        [*path, op.label],
                        render(world, before),
                        "unreadable",
                    )
                    return
            for s, ghost in enumerate(child.sources):
                view = (
                    ghost.views[-1]
                    if after is before
                    else view_of(s, after.rows.get(s))
                )
                if view != ghost.views[-1]:
                    ghost.views.append(view)
            noop = child == world and after == before
            recovery = {}
            if not noop and after.owner is None:
                for s, row in after.rows.items():
                    if row.state == "failed":
                        recovery[s] = await harness.recover(s, row)
            step = Step(world, child, before, after, op, outcome, recovery)
            tally(result.reached, step)
            steps = [*path, op.label]
            if replay is not None:
                result.trace.append(render(child, after))
            violation = first_violation(step)
            if violation:
                result.failure = Failure(
                    *violation, steps, render(world, before), render(child, after)
                )
                return
            if noop:
                result.noops += 1
            if noop and replay is None:
                # Every sequence after this step is a sequence after its
                # parent, which this search already covers. A replay goes on,
                # because its later steps run only on this path.
                result.nodes += 1
                result.sequences += 1
                dirty = False
                continue
            dirty = True
            await explore(child, after, steps)
            if result.failure:
                return
        if not explored:
            result.sequences += 1

    try:
        await explore(world, await harness.observe(config.sources), [])
    finally:
        await harness.engine.dispose()
    result.seconds = time.perf_counter() - started
    return result


def removals(sequence):
    """Every sequence with one contiguous run of steps removed, shortest first.

    A begin and its finish only leave together, so single steps are not enough.
    """
    n = len(sequence)
    for size in range(n - 1, 0, -1):
        for i in range(n - size + 1):
            yield tuple(sequence[:i] + sequence[i + size :])


async def shrink(config: Config, failure: Failure) -> Failure:
    """Replay shorter copies of a failing sequence until no contiguous run of
    steps can be removed with the replay still failing the same property."""
    shorter = True
    while shorter:
        shorter = False
        for trial in removals(failure.sequence):
            try:
                run = await check_ledger(
                    replace(config, replay=trial, skip_probability=0.0)
                )
            except NotACandidate:
                continue
            if run.failure and run.failure.prop == failure.prop:
                failure, shorter = run.failure, True
                break
    return failure


async def run_and_shrink(config: Config) -> Result:
    result = await check_ledger(config)
    if result.failure and config.replay is None:
        result.failure = await shrink(config, result.failure)
    return result


def run_one(config: Config, minimal=True) -> Result:
    return asyncio.run(run_and_shrink(config) if minimal else check_ledger(config))


def run_all(configs, minimal=True) -> list[Result]:
    """Run independent checks in parallel processes, in order.

    Each check waits on aiosqlite's thread for most of its time, so separate
    processes finish a batch in about the time of its slowest check.
    """
    spawn = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(mp_context=spawn) as pool:
        return list(pool.map(run_one, configs, [minimal] * len(configs)))


def caught_as(result):
    """The property that caught a mutant, INCONCLUSIVE, or None if it survived."""
    if result.failure:
        return result.failure.prop
    return "INCONCLUSIVE" if result.verdict == "INCONCLUSIVE" else None


def report(result: Result) -> str:
    c = result.config
    if c.replay is not None:
        mode = "replay"
    elif c.skip_probability:
        mode = f"sampled (P={c.skip_probability}, seed={c.seed})"
    else:
        mode = "verified within bound" if result.verdict == "PASS" else "exhaustive"
    lines = [
        f"{result.verdict} {mode}: depth={len(c.replay) if c.replay else c.depth} "
        f"sources={c.sources} writers={c.writers}"
        + (f" mutant={c.mutant}" if c.mutant else ""),
        f"nodes={result.nodes} skipped={result.skipped} noops={result.noops} "
        f"sequences={result.sequences} seconds={result.seconds:.2f}",
        "reached: "
        + " ".join(f"{k.replace(' ', ':')}={result.reached[k]}" for k in REACHABLE),
    ]
    if result.verdict == "INCONCLUSIVE":
        lines.append("never reached: " + ", ".join(result.missing))
    for i, (label, state) in enumerate(zip(c.replay or (), result.trace), 1):
        lines.append(f"  {i}. {label}\n     {state}")
    f = result.failure
    if f is None:
        return "\n".join(lines)
    rerun = (
        "uv run python support/ledger_check.py "
        f"--sources {c.sources} --writers {c.writers} "
        + (f"--mutant {c.mutant} " if c.mutant else "")
        + f"--replay {'; '.join(f.sequence)!r}"
    )
    lines += [
        f"{f.prop}: {f.message}",
        (
            f"replayed sequence ({len(f.sequence)} steps):"
            if c.replay
            else f"minimal failing sequence ({len(f.sequence)} steps, no run of "
            f"steps removable; search depth {c.depth}, P={c.skip_probability}, "
            f"seed={c.seed}):"
        ),
        *(f"  {i}. {label}" for i, label in enumerate(f.sequence, 1)),
        f"before last step: {f.before}",
        f"after last step: {f.after}",
        f"rerun: {rerun}",
    ]
    return "\n".join(lines)


def parse(argv):
    defaults = Config()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--depth", type=int, default=defaults.depth)
    parser.add_argument("--sources", type=int, choices=[1, 2], default=defaults.sources)
    parser.add_argument("--writers", type=int, choices=[1, 2], default=defaults.writers)
    parser.add_argument("--skip-probability", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--replay", help="'; '-separated step labels from a failure report"
    )
    parser.add_argument("--mutant", choices=sorted(MUTANTS | DEEP_MUTANTS))
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
    if args.replay and args.skip_probability:
        parser.error(
            "--replay runs every step it names; it takes no --skip-probability"
        )
    return args


def main(argv=None):
    args = parse(argv)
    config = Config(
        depth=args.depth,
        sources=args.sources,
        writers=args.writers,
        skip_probability=args.skip_probability,
        seed=args.seed,
        mutant=args.mutant,
        replay=(
            tuple(s.strip() for s in args.replay.split(";")) if args.replay else None
        ),
    )
    if args.mutants:
        wrong = []
        results = run_all([replace(config, mutant=name) for name in MUTANTS])
        for (name, mutant), result in zip(MUTANTS.items(), results):
            got = caught_as(result)
            line = f"{name}: expected {mutant.prop}, "
            if result.failure:
                line += (
                    f"caught {got} in {len(result.failure.sequence)} steps: "
                    + "; ".join(result.failure.sequence)
                )
            else:
                line += f"{got or 'MISSED'} ({result.nodes} nodes)"
            print(line)
            if got != mutant.prop:
                wrong.append(name)
        if wrong:
            print("not caught by the named property: " + ", ".join(wrong))
        return 1 if wrong else 0
    try:
        result = run_one(config)
    except NotACandidate as exc:
        raise SystemExit(str(exc))
    print(report(result))
    return {"FAIL": 1, "INCONCLUSIVE": 2, "PASS": 0}[result.verdict]


if __name__ == "__main__":
    sys.exit(main())
