"""Portable project bookkeeping through Cognee's configured relational sessions."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import NamedTuple
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import Integer, String, Text, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import IdentitySource
from .validation import IntentError


class Base(DeclarativeBase):
    pass


class Publication(Base):
    __tablename__ = "lab_identity_publications"
    dataset: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    verified_revision: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(16))
    attempt: Mapped[str] = mapped_column(String(36))
    description: Mapped[str] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(Text)


class Writer(Base):
    __tablename__ = "lab_identity_writers"
    dataset: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(36), nullable=True)


class RecoveryEvent(Base):
    __tablename__ = "lab_identity_recovery_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset: Mapped[str] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(36))
    attempt: Mapped[str] = mapped_column(String(36))
    details: Mapped[str] = mapped_column(Text)


RETIRED_STATES = frozenset({"withdrawn", "forgotten"})


@dataclass(frozen=True)
class PublicationRow:
    """One saved publication, as RecordStore.rows() and row() read it."""

    dataset: str
    source: str
    revision: int
    verified_revision: int
    state: str
    attempt: str
    description: str
    plan: dict

    @classmethod
    def of(cls, record: Publication) -> "PublicationRow":
        return cls(
            dataset=record.dataset,
            source=record.source,
            revision=record.revision,
            verified_revision=record.verified_revision,
            state=record.state,
            attempt=record.attempt,
            description=record.description,
            plan=json.loads(record.plan),
        )

    @property
    def operation(self) -> str | None:
        """The saved plan's operation: the intent in flight, or the last one."""
        return self.plan.get("operation")

    @property
    def is_retired(self) -> bool:
        return self.state in RETIRED_STATES

    @property
    def resumed_by(self) -> str | None:
        """The method that alone resumes this row's saved plan, if it failed."""
        return cell_for(self).owner


class Refusal(NamedTuple):
    """A guard's diagnostic code and message: raise IntentError(*refusal)."""

    code: str
    message: str


STALE_REVISION = Refusal("stale_revision", "Saved revision changed")
PENDING = Refusal("pending_attempt", "Inspect abandoned pending publication explicitly")
WITHDRAWN_SOURCE = Refusal(
    "withdrawn_source", "Withdrawn source requires explicit new publication intent"
)
FORGOTTEN_SOURCE = Refusal(
    "forgotten_source",
    "Forgotten source accepts only a new publication at the next revision",
)
SAVED_LINEAGE = Refusal(
    "recovery_choice", "Reconcile a saved revision, or advance it through replacement"
)
FAILED_WITHDRAWAL = Refusal("recovery_choice", "Retry the failed withdrawal explicitly")
FAILED_FORGET = Refusal("recovery_choice", "Retry the failed forget explicitly")
FAILED_REPLACEMENT = Refusal(
    "recovery_choice", "Reconcile the saved replacement plan explicitly"
)
ADVANCE_THROUGH_REPLACEMENT = Refusal(
    "recovery_choice", "Advance a current revision through replacement"
)
REPLACEMENT_MISSING = Refusal(
    "source_missing", "Replacement requires an existing publication"
)
FORGET_MISSING = Refusal("source_missing", "Forget requires an existing publication")
REPLACEMENT_PLAN = Refusal(
    "recovery_plan", "Replacement requires a durable replacement plan"
)
FORGET_PLAN = Refusal("recovery_plan", "Forget requires a durable forget plan")
PRESERVE_REPLACEMENT = Refusal(
    "recovery_plan", "Preserve the saved replacement retirement plan"
)
FORGET_STATE = Refusal(
    "forget_state", "Forget a current source, or retry its failed forget"
)
NEW_REVISION = Refusal(
    "revision_sequence", "New description must advance exactly one revision"
)
READD_REVISION = Refusal(
    "revision_sequence", "Re-add a forgotten source at exactly the next revision"
)
REPLACEMENT_REVISION = Refusal(
    "revision_sequence", "Replacement must advance exactly one revision"
)
REVISION_REUSE = Refusal(
    "revision_reuse", "Changed description requires a new revision"
)


class Transition(NamedTuple):
    """What one saved row lets each method begin.

    `admits` maps a method to its revision step: 0 resumes the saved revision,
    1 takes the next. `refuses` turns a method away before any argument is
    read, and `otherwise` turns away every other method that `admits` lacks.
    A method in none of them meets its own row refusal (REQUIRED_PLANS) after
    its plan check. `sequence` refuses a step-1 method at any revision but the
    next; on a missing row begin()'s final check gives that refusal. `owner`
    is the one method that resumes a failed row's saved plan.
    """

    admits: Mapping[str, int]
    refuses: Mapping[str, Refusal] = MappingProxyType({})
    otherwise: Refusal | None = None
    sequence: Refusal | None = None
    owner: str | None = None


def lineage_row(admits, otherwise=None, sequence=None, owner=None):
    """A saved row other than a forgotten one: a publish would restart it."""
    return Transition(admits, {"publish": SAVED_LINEAGE}, otherwise, sequence, owner)


def owned(method, otherwise):
    """A failed row whose saved plan only `method` resumes."""
    return lineage_row({method: 0}, otherwise, owner=method)


# Keyed by (row state, saved plan operation); a row with no entry for its
# plan operation takes its state's entry with None.
TRANSITIONS = {
    (None, None): Transition(
        {"publish": 1, "reconcile": 1, "withdraw": 1},
        {"replace": REPLACEMENT_MISSING, "forget": FORGET_MISSING},
    ),
    ("pending", None): Transition({}, otherwise=PENDING),
    ("current", None): lineage_row(
        {"reconcile": 0, "replace": 1, "withdraw": 0, "forget": 0},
        sequence=REPLACEMENT_REVISION,
    ),
    ("failed", None): lineage_row({"reconcile": 0, "withdraw": 0}),
    ("failed", "identity_withdraw"): owned("withdraw", FAILED_WITHDRAWAL),
    ("failed", "identity_forget"): owned("forget", FAILED_FORGET),
    ("failed", "identity_replace"): owned("replace", FAILED_REPLACEMENT),
    ("withdrawn", None): Transition({"withdraw": 0}, otherwise=WITHDRAWN_SOURCE),
    ("forgotten", None): Transition(
        {"publish": 1}, otherwise=FORGOTTEN_SOURCE, sequence=READD_REVISION
    ),
}


class RequiredPlan(NamedTuple):
    operation: str  # the plan operation begin() requires
    refusal: Refusal  # for a plan of any other operation
    # On a row the table neither admits nor refuses it on, and for a retry
    # of a failed row whose plan differs in a preserved field.
    off_row: Refusal
    preserved: tuple[str, ...] = ()  # plan fields a retry keeps


REQUIRED_PLANS = {
    # A replacement retry keeps what the failed attempt planned to retire.
    "replace": RequiredPlan(
        "identity_replace",
        REPLACEMENT_PLAN,
        PRESERVE_REPLACEMENT,
        preserved=("previous_description", "text_change"),
    ),
    "forget": RequiredPlan("identity_forget", FORGET_PLAN, FORGET_STATE),
}


def cell_for(row: PublicationRow | None) -> Transition:
    """The TRANSITIONS entry that governs this saved row (None: no row)."""
    if row is None:
        return TRANSITIONS[None, None]
    for key in ((row.state, row.operation), (row.state, None)):
        if key in TRANSITIONS:
            return TRANSITIONS[key]
    raise IntentError("unknown_state", f"Saved row state {row.state!r} is unknown")


def admissible(row, method, plan, revision) -> Refusal | None:
    """The refusal begin() gives `method` with this plan and description
    revision on this saved row (None: no row), or None when it may begin.
    begin() checks the expected revision before and, after, the description
    at the saved revision and that any advance takes exactly the next one."""
    cell = cell_for(row)
    actual = row.revision if row else 0
    step = cell.admits.get(method)
    if step is None and (refusal := cell.refuses.get(method, cell.otherwise)):
        return refusal
    if row and step != 1 and revision != actual:
        return ADVANCE_THROUGH_REPLACEMENT
    required = REQUIRED_PLANS.get(method)
    if required and plan.get("operation") != required.operation:
        return required.refusal
    if step is None:
        return required.off_row
    if step == 1 and revision != actual + 1 and cell.sequence:
        return cell.sequence
    if required and row and row.state == "failed":
        if any(plan.get(f) != row.plan.get(f) for f in required.preserved):
            return required.off_row
    return None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


class RecordStore:
    def __init__(self, session_factory=None):
        if session_factory is None:
            from cognee.infrastructure.databases.relational import get_relational_engine

            session_factory = get_relational_engine().get_async_session
        self.session_factory = session_factory

    async def initialize(self):
        async with self.session_factory() as session:
            connection = await session.connection()
            await connection.run_sync(Base.metadata.create_all)
            await session.commit()

    async def rows(self, dataset=None) -> list[PublicationRow]:
        async with self.session_factory() as session:
            statement = select(Publication)
            if dataset is not None:
                statement = statement.where(Publication.dataset == str(dataset))
            rows = (await session.execute(statement)).scalars().all()
            return [PublicationRow.of(r) for r in rows]

    async def row(self, source) -> PublicationRow | None:
        """The publication row of one identity source, or None."""
        dataset, sid = str(source.dataset_id), str(source.identity_data_id)
        return next((r for r in await self.rows(dataset) if r.source == sid), None)

    async def events(self, dataset):
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(RecoveryEvent).where(
                            RecoveryEvent.dataset == str(dataset)
                        )
                    )
                )
                .scalars()
                .all()
            )
            return [json.loads(r.details) for r in rows]

    async def assert_pending(self, source, attempt):
        row = await self.row(source)
        if (
            row is None
            or row.state != "pending"
            or row.attempt != attempt
            or IdentitySource.model_validate_json(row.description) != source
        ):
            raise IntentError(
                "stale_attempt", "Graph write does not match saved pending intent"
            )

    async def begin(
        self,
        source: IdentitySource,
        *,
        expected_revision: int,
        plan: dict,
        method="publish",
        origin="runtime",
    ) -> str:
        dataset, sid = str(source.dataset_id), str(source.identity_data_id)
        # Serialize project writers across datasets in shared physical storage.
        # Native writers outside this coordinator are not covered by this lock.
        lock_scope = "shared-identity-publication"
        async with self.session_factory() as session:
            if await session.get(Writer, lock_scope) is None:
                session.add(Writer(dataset=lock_scope, owner=None))
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
        attempt = str(uuid4())
        async with self.session_factory() as session:
            locked = await session.execute(
                update(Writer)
                .where(Writer.dataset == lock_scope, Writer.owner.is_(None))
                .values(owner=attempt)
            )
            if locked.rowcount != 1:
                raise IntentError(
                    "writer_busy", "Dataset has an active/abandoned project writer"
                )
            row = await session.get(Publication, (dataset, sid))
            actual_revision = row.revision if row else 0
            if actual_revision != expected_revision:
                raise IntentError(*STALE_REVISION)
            saved = PublicationRow.of(row) if row else None
            if refusal := admissible(saved, method, plan, source.revision):
                raise IntentError(*refusal)
            payload = source.model_dump_json()
            if row and source.revision == actual_revision:
                if json.loads(payload) != json.loads(row.description):
                    raise IntentError(*REVISION_REUSE)
            elif source.revision != actual_revision + 1:
                raise IntentError(*NEW_REVISION)
            if row is None:
                row = Publication(dataset=dataset, source=sid, verified_revision=0)
                session.add(row)
            row.revision, row.state, row.attempt = source.revision, "pending", attempt
            row.description, row.plan = payload, encode(plan)
            # Recovery attempts are diagnostic links, not new incidents.
            events = (
                (
                    await session.execute(
                        select(RecoveryEvent).where(
                            RecoveryEvent.dataset == dataset,
                            RecoveryEvent.source == sid,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for event in events:
                info = json.loads(event.details)
                if info.get("resolved_at") is None:
                    info.setdefault("recovery_attempts", []).append(
                        {"attempt_id": attempt, "method": method, "started_at": now()}
                    )
                    event.details = encode(info)
            plan.update(origin=origin, method=method)
            row.plan = encode(plan)
            await session.commit()
        return attempt

    async def fail(self, source, attempt, stage, error, *, origin=None) -> str:
        dataset, sid = str(source.dataset_id), str(source.identity_data_id)
        event_id = str(uuid5(NAMESPACE_URL, f"lab-recovery:{dataset}:{sid}:{attempt}"))
        async with self.session_factory() as session:
            row = await session.get(Publication, (dataset, sid))
            if row is None or row.attempt != attempt:
                raise IntentError("stale_attempt", "Failure belongs to another attempt")
            row.state = "failed"
            event = await session.get(RecoveryEvent, event_id)
            if event is None:
                prior = (
                    (
                        await session.execute(
                            select(RecoveryEvent).where(
                                RecoveryEvent.dataset == dataset,
                                RecoveryEvent.source == sid,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for candidate in prior:
                    details = json.loads(candidate.details)
                    if details.get("resolved_at") is None and any(
                        a["attempt_id"] == attempt
                        for a in details.get("recovery_attempts", [])
                    ):
                        event, event_id = candidate, candidate.id
                        break
            info = (
                json.loads(event.details)
                if event
                else {
                    "recovery_event_id": event_id,
                    "dataset_id": dataset,
                    "identity_data_id": sid,
                    "original_data_id": str(
                        source.inputs[source.original_input_ref].data_id
                    ),
                    "attempt_id": attempt,
                    "intended_revision": source.revision,
                    "last_verified_revision": row.verified_revision,
                    "first_detected_at": now(),
                    "origin": origin or json.loads(row.plan).get("origin", "runtime"),
                    "runtime_profile": json.loads(row.plan).get("runtime_profile", {}),
                    "operation": json.loads(row.plan).get("method", "publish"),
                    "integration_version": "stage6-m3-replacement",
                    "resolved_at": None,
                }
            )
            failure = dict(
                stage=stage,
                reason_code=getattr(error, "code", type(error).__name__),
                message=str(error)[:800],
            )
            info["last_observed_at"] = now()
            if info["attempt_id"] == attempt:
                info.update(failure)
            else:
                for recovery in info.get("recovery_attempts", []):
                    if recovery["attempt_id"] == attempt:
                        recovery.update(failure, outcome="failed", finished_at=now())
            if event is None:
                session.add(
                    RecoveryEvent(
                        id=event_id,
                        dataset=dataset,
                        source=sid,
                        attempt=attempt,
                        details=encode(info),
                    )
                )
            else:
                event.details = encode(info)
            await session.execute(
                update(Writer)
                .where(
                    Writer.dataset == "shared-identity-publication",
                    Writer.owner == attempt,
                )
                .values(owner=None)
            )
            await session.commit()
        return event_id

    async def complete(self, source, attempt, *, state="current"):
        if state not in {"current", "withdrawn", "forgotten"}:
            raise ValueError("Unsupported completion state")
        dataset, sid = str(source.dataset_id), str(source.identity_data_id)
        values = {"state": state}
        if state == "current":
            values["verified_revision"] = source.revision
        async with self.session_factory() as session:
            result = await session.execute(
                update(Publication)
                .where(
                    Publication.dataset == dataset,
                    Publication.source == sid,
                    Publication.revision == source.revision,
                    Publication.attempt == attempt,
                    Publication.state == "pending",
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise IntentError(
                    "stale_attempt", "Cannot acknowledge stale/nonpending attempt"
                )
            await session.execute(
                update(Writer)
                .where(
                    Writer.dataset == "shared-identity-publication",
                    Writer.owner == attempt,
                )
                .values(owner=None)
            )
            for event in (
                await session.execute(
                    select(RecoveryEvent).where(
                        RecoveryEvent.dataset == dataset, RecoveryEvent.source == sid
                    )
                )
            ).scalars():
                info = json.loads(event.details)
                if info.get("resolved_at") is None:
                    info.update(
                        resolved_at=now(),
                        resolving_attempt=attempt,
                        resolving_revision=source.revision,
                        outcome="restored" if state == "current" else state,
                    )
                    if info.get("recovery_attempts"):
                        info["recovery_attempts"][-1]["outcome"] = "verified"
                    event.details = encode(info)
            await session.commit()
