"""The model that support/ledger_check.py drives RecordStore with.

Descriptions, plans, the steps a caller can take, the Method table and the
checker's own record of writers and sources. Nothing here touches the store.
"""

import hashlib
import json
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Callable, Literal, NamedTuple
from uuid import NAMESPACE_URL, uuid5

from cognee_lab.identity.models import IdentitySource

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/identity/cognee_identity_source_example.json"


@cache
def fixture():
    return json.loads(FIXTURE.read_text())


DATASET = fixture()["dataset_id"]
# asdict(TextChange) as replace.py saves it in plan["text_change"].
TEXT_CHANGE = dict(
    previous_text="ledger_check text",
    text="Revision note: ledger_check text",
    occurrence_map={"g01": [["g01", 0], ["g01", 1]]},
    chunk_budget=512,
)
TEXT_REGROUP = dict(
    TEXT_CHANGE,
    occurrence_map={"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]},
)
TEXT_CHANGES = dict(text=TEXT_CHANGE, regroup=TEXT_REGROUP)
TEXT_PLANS = (None, *TEXT_CHANGES)


def source_id(s):
    return str(uuid5(NAMESPACE_URL, f"ledger-check-source:{s}"))


@cache
def description(s, revision, variant=0):
    """The description of source s at a revision.

    Variant 1 changes the original text digest. No caller saves it; it is the
    changed description that begin() must refuse at a saved revision.
    """
    payload = json.loads(json.dumps(fixture()))
    payload.update(identity_data_id=source_id(s), revision=revision)
    if variant:
        text = payload["inputs"][payload["original_input_ref"]]
        text["text_sha256"] = hashlib.sha256(b"changed text").hexdigest()
    return IdentitySource.model_validate_json(json.dumps(payload))


@cache
def canonical(s, revision, variant):
    return json.loads(description(s, revision, variant).model_dump_json())


def variant_of(s, saved):
    """Which variant a saved description (a parsed JSON dict) is."""
    for variant in (0, 1):
        if saved == canonical(s, saved["revision"], variant):
            return variant
    raise ValueError(f"S{s + 1} saved a description the checker never sent")


@dataclass(frozen=True)
class Plan:
    """A plan a caller saves, reduced to the fields storage.py reads.

    Publisher._publish, replace() in replace.py, withdraw() in withdraw.py and
    forget() in forget.py.
    """

    operation: Literal["publish", "replace", "withdraw", "forget"]
    revision: int
    previous: tuple[int, int] | None = None  # (revision, variant) it replaces
    change: Literal["text", "regroup"] | None = None

    @property
    def tag(self):
        if self.operation != "replace":
            return self.operation
        revision, variant = self.previous
        kind = self.change or "replace"
        return f"{kind}<r{revision}" + ("alt" if variant else "")

    def as_dict(self, s):
        plan = dict(
            operation=f"identity_{self.operation}",
            revision=self.revision,
            runtime_profile={},
        )
        if self.previous is not None:
            plan["previous_description"] = description(
                s, *self.previous
            ).model_dump_json()
        if self.change:
            plan["text_change"] = dict(TEXT_CHANGES[self.change])
        return plan

    @classmethod
    def of(cls, s, saved):
        previous = None
        if "previous_description" in saved:
            old = json.loads(saved["previous_description"])
            previous = (old["revision"], variant_of(s, old))
        change = saved.get("text_change")
        kind = None
        if change is not None:
            kind = next((k for k, v in TEXT_CHANGES.items() if v == change), None)
            if kind is None:
                raise ValueError(f"S{s + 1} saved a text_change the checker never sent")
        return cls(
            saved["operation"].removeprefix("identity_"),
            saved["revision"],
            previous,
            kind,
        )


class View(NamedTuple):
    """One row as a caller read it from RecordStore.rows()."""

    revision: int
    state: str
    plan: Plan
    variant: int


def view_of(s, row):
    if row is None:
        return None
    return View(
        row.revision,
        row.state,
        Plan.of(s, row.plan),
        variant_of(s, json.loads(row.description)),
    )


@dataclass(frozen=True)
class Begin:
    writer: int
    source: int
    method: str
    expected: int
    revision: int
    plan: Plan
    variant: int = 0

    @property
    def label(self):
        return (
            f"W{self.writer + 1} {self.method} S{self.source + 1} "
            f"rev={self.revision} expect={self.expected} plan={self.plan.tag}"
            + (" desc=alt" if self.variant else "")
        )


@dataclass(frozen=True)
class Finish:
    """A held attempt's store work ends: stage None succeeds, else it fails there.

    alt=True acknowledges work for a description other than the one begun,
    which assert_pending() exists to refuse.
    """

    writer: int
    stage: str | None
    alt: bool = False

    @property
    def label(self):
        if self.stage is not None:
            return f"W{self.writer + 1} fail@{self.stage}"
        return f"W{self.writer + 1} complete" + (" desc=alt" if self.alt else "")


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
    """valid_sources() in retrieve.py fails a current row it could not validate."""

    source: int

    @property
    def label(self):
        return f"reject S{self.source + 1}"


Op = Begin | Finish | Crash | Repeat | Reject


def publish_intents(w, s, view):
    if view is None:
        return [
            Begin(w, s, "publish", 0, 1, Plan("publish", 1)),
            Begin(w, s, "publish", 0, 2, Plan("publish", 2)),
        ]
    # A re-add after forget: Publisher.readd with the saved revision as the
    # guard and the next revision as the description. Refused on other rows.
    r, v = view.revision, view.variant
    return [
        Begin(w, s, "publish", r, r + 1, Plan("publish", r + 1)),
        Begin(w, s, "publish", r, r, Plan("publish", r), v),
    ]


def reconcile_intents(w, s, view):
    if view is None:
        return []
    r, v = view.revision, view.variant
    return [
        Begin(w, s, "reconcile", r, r, Plan("publish", r), v),
        Begin(w, s, "reconcile", r, r, Plan("publish", r), 1 - v),
        Begin(w, s, "reconcile", r, r + 1, Plan("publish", r + 1)),
    ]


def replace_intents(w, s, view):
    if view is None:
        return []
    r, v = view.revision, view.variant
    ops = [
        Begin(w, s, "replace", r, r + 1, Plan("replace", r + 1, (r, v), change))
        for change in TEXT_PLANS
    ]
    ops += [
        Begin(w, s, "replace", r, r + 2, Plan("replace", r + 2, (r, v))),
        Begin(w, s, "replace", r, r + 1, Plan("publish", r + 1)),
    ]
    saved = view.plan
    if saved.operation == "replace":  # the retry branch of replace()
        prior, prior_variant = saved.previous
        ops += [
            Begin(w, s, "replace", r, r, saved, v),
            Begin(w, s, "replace", r, r, saved, 1 - v),
            *[
                Begin(w, s, "replace", r, r, replace(saved, change=change), v)
                for change in TEXT_PLANS
                if change != saved.change
            ],
            Begin(
                w,
                s,
                "replace",
                r,
                r,
                replace(saved, previous=(prior, 1 - prior_variant)),
                v,
            ),
        ]
    return ops


def withdraw_intents(w, s, view):
    if view is None:
        return []
    r, v = view.revision, view.variant
    reuse = view.state != "withdrawn" and view.plan.operation == "withdraw"
    plan = view.plan if reuse else Plan("withdraw", r)  # as withdraw() chooses
    return [
        Begin(w, s, "withdraw", r, r, plan, v),
        Begin(w, s, "withdraw", r, r, plan, 1 - v),
        Begin(w, s, "withdraw", r, r + 1, Plan("withdraw", r + 1)),
    ]


def forget_intents(w, s, view):
    if view is None:
        # forget() refuses a missing row itself; begin() must refuse it too.
        return [Begin(w, s, "forget", 0, 1, Plan("forget", 1))]
    r, v = view.revision, view.variant
    reuse = view.state == "failed" and view.plan.operation == "forget"
    plan = view.plan if reuse else Plan("forget", r)  # as forget() chooses
    return [
        Begin(w, s, "forget", r, r, plan, v),
        Begin(w, s, "forget", r, r, plan, 1 - v),
        Begin(w, s, "forget", r, r + 1, Plan("forget", r + 1)),
        Begin(w, s, "forget", r, r, Plan("publish", r), v),
    ]


@dataclass(frozen=True)
class Method:
    """How one caller drives RecordStore, and which rows only it may resume.

    Harness.apply(), candidates() and the P5 and P6 rules read this table and
    nothing else about methods. The Begin label (method, source, revisions,
    plan tag, description) is the dedupe key in candidates() and the --replay
    key. Every step touches at most one source today (op_source() in
    ledger_check.py).
    """

    name: str
    # Begin calls the caller builds from one read of the row (None: no row).
    # The caller's own pre-checks are skipped on purpose: they read the row
    # without the reservation, so begin() must hold on its own. Each list
    # also holds arguments that begin() must refuse.
    intents: Callable[[int, int, View | None], list[Begin]]
    done_state: str  # complete(state=...)
    asserts_pending: bool  # assert_pending() before complete()
    # The stage fail() records when assert_pending() refuses, or None when the
    # caller raises with the reservation held (Publisher._apply_pending calls
    # assert_pending() before its try block).
    on_assert_refused: str | None
    # The stage fail() records for an injected fault. storage.py copies the
    # stage into the event and never branches on it, so one stage covers
    # every fault the caller can inject.
    fail_stage: str
    ack_stage: str  # the stage fail() records when complete() refuses
    # Row states (None: no row) it may begin on, each with its revision step:
    # 0 at the saved revision, 1 at the next. A "failed" entry covers only the
    # failed rows that no other method owns. A failed row whose saved plan
    # this method owns needs no entry: owns() admits it at step 0.
    begins: dict[str | None, int]
    recovers: str | None  # P6: the saved plan operation it resumes
    owns_recovery: bool  # a failed row with the `recovers` plan resumes only here
    owns_terminal: str | None  # a row in this terminal state begins only here
    requires_plan: bool  # begin() must carry a plan of the `recovers` operation
    preserved_on_retry: tuple[str, ...]  # Plan fields a retry keeps

    def __post_init__(self):
        assert self.recovers or not self.requires_plan, (
            f"{self.name}: requires_plan names the `recovers` operation, "
            "so it needs one"
        )

    def owns(self, state, operation):
        """Only this method may begin on a row in this state and saved plan."""
        return state == self.owns_terminal or (
            state == "failed" and self.owns_recovery and operation == self.recovers
        )


METHODS = {
    m.name: m
    for m in (
        Method(  # Publisher.publish (a first publication) and Publisher.readd
            name="publish",
            intents=publish_intents,
            done_state="current",
            asserts_pending=True,
            on_assert_refused=None,
            fail_stage="nodes",
            ack_stage="verification",
            begins={None: 1, "forgotten": 1},
            recovers=None,
            owns_recovery=False,
            owns_terminal="forgotten",
            requires_plan=False,
            preserved_on_retry=(),
        ),
        Method(  # Publisher.reconcile; the reconcile CLI
            name="reconcile",
            intents=reconcile_intents,
            done_state="current",
            asserts_pending=True,
            on_assert_refused=None,
            fail_stage="nodes",
            ack_stage="verification",
            begins={"current": 0, "failed": 0},
            recovers="publish",
            owns_recovery=False,
            owns_terminal=None,
            requires_plan=False,
            preserved_on_retry=(),
        ),
        Method(  # replace(); revisions.replace_one, text_fixture.maintain_one
            name="replace",
            intents=replace_intents,
            done_state="current",
            asserts_pending=True,
            on_assert_refused="replacement_publish",
            fail_stage="replace_saved",
            ack_stage="verification",
            begins={"current": 1},
            recovers="replace",
            owns_recovery=True,
            owns_terminal=None,
            requires_plan=True,
            preserved_on_retry=("previous", "change"),
        ),
        Method(  # withdraw()
            name="withdraw",
            intents=withdraw_intents,
            done_state="withdrawn",
            asserts_pending=False,
            on_assert_refused=None,
            fail_stage="withdraw_contributions",
            ack_stage="withdraw_verification",
            begins={"current": 0, "failed": 0, "withdrawn": 0},
            recovers="withdraw",
            owns_recovery=True,
            owns_terminal="withdrawn",
            requires_plan=False,
            preserved_on_retry=(),
        ),
        Method(  # forget()
            name="forget",
            intents=forget_intents,
            done_state="forgotten",
            asserts_pending=False,
            on_assert_refused=None,
            fail_stage="forget_contributions",
            ack_stage="forget_verification",
            begins={"current": 0},
            recovers="forget",
            owns_recovery=True,
            owns_terminal=None,
            requires_plan=True,
            preserved_on_retry=(),
        ),
    )
}


@dataclass
class Attempt:
    id: str
    source: int
    revision: int
    variant: int
    method: str
    from_failed: bool  # begun on a failed row


class Ack(NamedTuple):
    """The last call that ended an attempt. Repeat resends it."""

    kind: Literal["complete", "fail"]
    attempt: Attempt
    detail: str  # the completion state or the failure stage


class Served(NamedTuple):
    """The attempt and revision of the row a reader last saw current."""

    attempt: str
    revision: int


Outcome = Literal["open", "current", "withdrawn", "forgotten", "failed"] | None


@dataclass
class Writer:
    holds: Attempt | None = None
    stuck: bool = False
    last: Ack | None = None
    begun: int = 0


@dataclass
class Ghost:
    """What the checker knows happened to one source, independent of the store."""

    outcome: Outcome = None
    revision: int = 0
    variant: int = 0
    attempt: str | None = None  # the last attempt begin() accepted
    # Every distinct row this source had on the path, as a caller could have
    # read it. Callers read the row and call begin() later, so any earlier
    # read can reach begin().
    views: list = field(default_factory=lambda: [None])
    served: Served | None = None


@dataclass
class World:
    writers: list
    sources: list
    names: dict = field(default_factory=dict)  # attempt id -> "W1#2"


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
            if METHODS[writer.holds.method].asserts_pending:
                ops.append(Finish(w, None, alt=True))
            ops.append(Finish(w, METHODS[writer.holds.method].fail_stage))
            ops.append(Crash(w))
            continue
        if writer == Writer() and w != fresh_writer:
            continue
        seen = set()
        for s, ghost in enumerate(world.sources):
            if ghost.views == [None] and s != fresh_source:
                continue
            for view in reversed(ghost.views):
                for method in METHODS.values():
                    for op in method.intents(w, s, view):
                        if op.label not in seen:
                            seen.add(op.label)
                            ops.append(op)
        if writer.last is not None:
            ops.append(Repeat(w))
    for s, ghost in enumerate(world.sources):
        if ghost.served is not None:
            ops.append(Reject(s))
    return ops
