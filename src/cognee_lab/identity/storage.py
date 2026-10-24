"""Portable project bookkeeping through Cognee's configured relational sessions."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Literal, NamedTuple
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import Integer, String, Text, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .erasure_rules import check_retry_chain, erasures_of
from .models import IdentitySource, Tombstone
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
    # On a source that lives again: the tombstone its last forget left, set
    # by the re-add's begin and kept until the next forget, which carries
    # its UUIDs into the new tombstone (forget.py). None on a forgotten row.
    last_tombstone: Mapped[str | None] = mapped_column(Text, nullable=True)


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
# What a forgotten row's plan keeps: identifiers, refs and file locations.
# Every edge property goes, since a fact or chunk edge quotes the document.
FORGOTTEN_PLAN_FIELDS = (
    "operation",
    "revision",
    "origin",
    "method",
    "original_data_id",
    "stored_files",
    "chunk_ids",
    "identity_edges",
    "entities",
    "edges",
)
FORGOTTEN_EDGE_FIELDS = ("source", "target", "relation", "refs")


def scrubbed_plan(plan: dict) -> dict:
    """A forget plan as its forgotten row keeps it, by whitelist."""
    kept = {k: plan[k] for k in FORGOTTEN_PLAN_FIELDS if k in plan}
    if "edges" in kept:
        kept["edges"] = [
            {k: e[k] for k in FORGOTTEN_EDGE_FIELDS if k in e} for e in kept["edges"]
        ]
    return kept


def scrubbed_event(info: dict) -> dict:
    """A recovery event of a forgotten source: an error message can quote
    content, so it goes; ids, stage, codes and attempts stay."""
    info = dict(info)
    if "message" in info:
        info["message"] = None
    if "recovery_attempts" in info:
        info["recovery_attempts"] = [
            dict(a, message=None) if "message" in a else a
            for a in info["recovery_attempts"]
        ]
    return info


FailedAttempt = Literal["publish", "replace", "text_change", "withdraw", "forget"]


@dataclass(frozen=True)
class PublicationRow:
    """One saved publication, as RecordStore.rows() and row() read it, parsed
    once: a forgotten row holds its tombstone and no description, every
    other row its description and no tombstone. A forgotten row from before
    tombstones is refused here. `last_tombstone` is the tombstone the
    source's last forget left, on a row re-added since; a forgotten row's
    own tombstone already carries it."""

    dataset: str
    source: str
    revision: int
    verified_revision: int
    state: str
    attempt: str
    description: IdentitySource | None
    tombstone: Tombstone | None
    plan: dict
    last_tombstone: Tombstone | None = None

    @classmethod
    def of(cls, record: Publication) -> "PublicationRow":
        description = tombstone = None
        if record.state == "forgotten":
            tombstone = saved_tombstone(record.description)
        else:
            try:
                description = IdentitySource.model_validate_json(record.description)
            except ValueError:
                raise IntentError(*DESCRIPTION_FORMAT) from None
        return cls(
            dataset=record.dataset,
            source=record.source,
            revision=record.revision,
            verified_revision=record.verified_revision,
            state=record.state,
            attempt=record.attempt,
            description=description,
            tombstone=tombstone,
            plan=json.loads(record.plan),
            last_tombstone=(
                saved_tombstone(record.last_tombstone)
                if record.last_tombstone
                else None
            ),
        )

    def record(self) -> dict:
        """The row as the fixture reports print it: the description column
        as stored, a tombstone for a forgotten row."""
        return dict(
            dataset=self.dataset,
            source=self.source,
            revision=self.revision,
            verified_revision=self.verified_revision,
            state=self.state,
            attempt=self.attempt,
            description=(self.description or self.tombstone).model_dump_json(),
            plan=self.plan,
        )

    @property
    def operation(self) -> str | None:
        """The saved plan's operation: the intent in flight, or the last one."""
        return self.plan.get("operation")

    @property
    def is_retired(self) -> bool:
        return self.state in RETIRED_STATES

    @property
    def is_served(self) -> bool:
        """The retrieval eligibility test. support/ledger_properties.py
        copies it as served()."""
        return self.state == "current" and self.revision == self.verified_revision

    @property
    def resumed_by(self) -> str | None:
        """The method that alone resumes this row's saved plan, if it failed."""
        return cell_for(self).owner

    @property
    def failed_attempt(self) -> FailedAttempt | None:
        """The attempt a failed row saved, None on any other row: a
        publication (a first one, a reconcile or a re-add), or the attempt of
        the one method that resumes it, with a replacement that carries a
        text change told apart."""
        if self.state != "failed":
            return None
        if self.resumed_by == "replace" and self.plan.get("text_change"):
            return "text_change"
        return self.resumed_by or "publish"


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
STRAY_ERASURE = Refusal(
    "recovery_plan", "Only a retry of a failed attempt names superseded revisions"
)
PUBLICATION_PLAN = Refusal("recovery_plan", "Reconcile requires a publication plan")
PRESERVE_PUBLICATION = Refusal(
    "recovery_plan", "Preserve the saved publication's superseded revisions"
)
PRESERVE_REPLACEMENT = Refusal(
    "recovery_plan", "Preserve the saved replacement retirement plan"
)
FORGET_STATE = Refusal(
    "forget_state",
    "Forget a current, withdrawn or failed-publication source, or retry its failed forget",
)
DESCRIPTION_FORMAT = Refusal(
    "description_format",
    "A saved row that is not forgotten holds an identity description",
)
OLD_FORGOTTEN_ROW = Refusal(
    "forgotten_format",
    "A forgotten row in an older format is not read; regenerate this development root",
)
OLD_LEDGER = Refusal(
    "ledger_format",
    "This root's ledger lacks columns this version reads; regenerate this development root",
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
    # A failed publication: a first one, a reconcile or a re-add.
    ("failed", None): lineage_row({"reconcile": 0, "withdraw": 0, "forget": 0}),
    ("failed", "identity_withdraw"): owned("withdraw", FAILED_WITHDRAWAL),
    ("failed", "identity_forget"): owned("forget", FAILED_FORGET),
    ("failed", "identity_replace"): owned("replace", FAILED_REPLACEMENT),
    ("withdrawn", None): Transition(
        {"withdraw": 0, "forget": 0}, otherwise=WITHDRAWN_SOURCE
    ),
    ("forgotten", None): Transition(
        {"publish": 1}, otherwise=FORGOTTEN_SOURCE, sequence=READD_REVISION
    ),
}


ERASED_FROM = "erased_from"


class RequiredPlan(NamedTuple):
    operation: str  # the plan operation begin() requires
    refusal: Refusal  # for a plan of any other operation
    # On a row the table neither admits nor refuses it on, and for a retry
    # of a failed row whose plan differs in a preserved field.
    off_row: Refusal
    preserved: tuple[str, ...] = ()  # plan fields a retry keeps
    # A retry may instead add the saved description to its plan's
    # `erased_from`, and then begins with another description at the saved
    # revision: an erasure retry (erasure_rules.check_retry_chain).
    supersedes: bool = False


REQUIRED_PLANS = {
    # A replacement retry keeps what the failed attempt planned to retire,
    # and the saved revisions earlier erasure retries superseded.
    "replace": RequiredPlan(
        "identity_replace",
        REPLACEMENT_PLAN,
        PRESERVE_REPLACEMENT,
        preserved=("previous_description", "text_change", ERASED_FROM),
        supersedes=True,
    ),
    # A reconcile of a failed publication keeps the saved revisions erasure
    # retries superseded, or supersedes the saved one (Publisher.superseded).
    "reconcile": RequiredPlan(
        "identity_publish",
        PUBLICATION_PLAN,
        PRESERVE_PUBLICATION,
        preserved=(ERASED_FROM,),
        supersedes=True,
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


def erased_from(plan: dict) -> list[IdentitySource]:
    """The saved descriptions a plan says erasure retries superseded."""
    return [IdentitySource.model_validate_json(d) for d in plan.get(ERASED_FROM, [])]


def superseding_plan(row, source) -> dict:
    """The `erased_from` a retry of this failed row plans with `source`: the
    saved list, with the saved description added when `source` is another
    one (an erasure retry, which supersedes it). Empty when the list is."""
    erased = list(row.plan.get(ERASED_FROM, []))
    if source != row.description:
        erased.append(row.description.model_dump_json())
    return {ERASED_FROM: erased} if erased else {}


def erasure_chain(row, method, plan) -> list[IdentitySource]:
    """The superseded descriptions a retry of this failed row names, which
    begin() checks as an erasure-retry chain against every saved row; empty
    for any other begin."""
    required = REQUIRED_PLANS.get(method)
    if required and required.supersedes and row and row.state == "failed":
        return erased_from(plan)
    return []


def admissible(row, method, plan, source, rows=()) -> Refusal | None:
    """The refusal begin() gives `method` with this plan and description on
    this saved row (None: no row), or None when it may begin. `rows` are
    every saved row, which bind an erasure retry to the forgets it erases.
    begin() checks the expected revision before."""
    cell = cell_for(row)
    actual = row.revision if row else 0
    revision = source.revision
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
    retry = bool(required and row and row.state == "failed")
    superseding = False
    if retry:
        changed = {f for f in required.preserved if plan.get(f) != row.plan.get(f)}
        # erased_from: preserved, or the saved list plus the saved description.
        superseding = (
            required.supersedes
            and changed == {ERASED_FROM}
            and erased_from(plan) == erased_from(superseding_plan(row, source))
        )
        if changed and not superseding:
            return required.off_row
    elif plan.get(ERASED_FROM):
        return STRAY_ERASURE
    if not row or revision != actual:
        return None if revision == actual + 1 else NEW_REVISION
    if not superseding and source != row.description:
        return REVISION_REUSE
    if chain := erasure_chain(row, method, plan):
        try:
            check_retry_chain([*chain, source], erasures_of(rows, source))
        except IntentError as refused:
            return Refusal(refused.code, str(refused))
    return None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def saved_tombstone(text: str) -> Tombstone:
    """A saved tombstone; one from before tombstones or in an older format
    is refused."""
    try:
        return Tombstone.model_validate_json(text)
    except ValueError:
        raise IntentError(*OLD_FORGOTTEN_ROW) from None


def saved_columns(connection) -> dict[str, set[str]]:
    """The columns each ledger table has in the store, which create_all
    does not add to a table made by an older version."""
    found = inspect(connection)
    return {
        t.name: {c["name"] for c in found.get_columns(t.name)}
        for t in Base.metadata.sorted_tables
    }


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
            saved = await connection.run_sync(saved_columns)
            await session.commit()
        if any(
            set(t.columns.keys()) - saved[t.name] for t in Base.metadata.sorted_tables
        ):
            raise IntentError(*OLD_LEDGER)

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
            or row.description != source
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
            rows = []
            if erasure_chain(saved, method, plan):
                found = (await session.execute(select(Publication))).scalars().all()
                rows = [PublicationRow.of(r) for r in found]
            if refusal := admissible(saved, method, plan, source, rows):
                raise IntentError(*refusal)
            payload = source.model_dump_json()
            if row is None:
                row = Publication(dataset=dataset, source=sid, verified_revision=0)
                session.add(row)
            elif row.state == "forgotten":
                row.last_tombstone = row.description
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

    async def complete(self, source, attempt, *, state="current", tombstone=None):
        """Acknowledge the pending attempt. A forget completes with the
        source's tombstone, which replaces its description and its
        `last_tombstone` in the same transaction (forget.py builds it to
        carry that one); its plan keeps only identifiers, and every recovery
        event of the source loses its message."""
        if state not in {"current", "withdrawn", "forgotten"}:
            raise ValueError("Unsupported completion state")
        if (state == "forgotten") != (tombstone is not None):
            raise ValueError("A forget, and only a forget, completes with a tombstone")
        dataset, sid = str(source.dataset_id), str(source.identity_data_id)
        values = {"state": state}
        if state == "current":
            values["verified_revision"] = source.revision
        if tombstone is not None:
            if (str(tombstone.dataset_id), str(tombstone.identity_data_id)) != (
                dataset,
                sid,
            ) or tombstone.revision != source.revision:
                raise ValueError("The tombstone names another source or revision")
            values.update(description=tombstone.model_dump_json(), last_tombstone=None)
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
            if tombstone is not None:
                row = await session.get(Publication, (dataset, sid))
                row.plan = encode(scrubbed_plan(json.loads(row.plan)))
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
                if tombstone is not None:
                    info = scrubbed_event(info)
                event.details = encode(info)
            await session.commit()
