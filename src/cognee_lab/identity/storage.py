"""Portable project bookkeeping through Cognee's configured relational sessions."""

import json
from datetime import datetime, timezone
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


FORGOTTEN_SOURCE = (
    "Forgotten source accepts only a new publication at the next revision"
)
FAILED_FORGET = "Retry the failed forget explicitly"
FAILED_REPLACEMENT = "Reconcile the saved replacement plan explicitly"
FORGET_STATE = "Forget a current source, or retry its failed forget"
READD_REVISION = "Re-add a forgotten source at exactly the next revision"
STALE_REVISION = "Saved revision changed"


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

    async def rows(self, dataset=None):
        async with self.session_factory() as session:
            statement = select(Publication)
            if dataset is not None:
                statement = statement.where(Publication.dataset == str(dataset))
            rows = (await session.execute(statement)).scalars().all()
            return [
                dict(
                    dataset=r.dataset,
                    source=r.source,
                    revision=r.revision,
                    verified_revision=r.verified_revision,
                    state=r.state,
                    attempt=r.attempt,
                    description=r.description,
                    plan=json.loads(r.plan),
                )
                for r in rows
            ]

    async def row(self, source):
        """The publication row of one identity source, or None."""
        dataset, sid = str(source.dataset_id), str(source.identity_data_id)
        return next((r for r in await self.rows(dataset) if r["source"] == sid), None)

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
            or row["state"] != "pending"
            or row["attempt"] != attempt
            or IdentitySource.model_validate_json(row["description"]) != source
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
                raise IntentError("stale_revision", STALE_REVISION)
            if row and row.state == "pending":
                raise IntentError(
                    "pending_attempt",
                    "Inspect abandoned pending publication explicitly",
                )
            if row and row.state == "withdrawn" and method != "withdraw":
                raise IntentError(
                    "withdrawn_source",
                    "Withdrawn source requires explicit new publication intent",
                )
            if row and row.state == "forgotten" and method != "publish":
                raise IntentError("forgotten_source", FORGOTTEN_SOURCE)
            if method == "publish" and row:
                # A publication starts a lineage: from no row, or again after forget.
                if row.state != "forgotten":
                    raise IntentError(
                        "recovery_choice",
                        "Reconcile a saved revision, or advance it through replacement",
                    )
                if source.revision != actual_revision + 1:
                    raise IntentError("revision_sequence", READD_REVISION)
            if (
                row
                and row.state == "failed"
                and json.loads(row.plan).get("operation") == "identity_withdraw"
                and method != "withdraw"
            ):
                raise IntentError(
                    "recovery_choice", "Retry the failed withdrawal explicitly"
                )
            if (
                row
                and row.state == "failed"
                and json.loads(row.plan).get("operation") == "identity_forget"
                and method != "forget"
            ):
                raise IntentError("recovery_choice", FAILED_FORGET)
            if (
                row
                and row.state == "failed"
                and json.loads(row.plan).get("operation") == "identity_replace"
                and method != "replace"
            ):
                raise IntentError("recovery_choice", FAILED_REPLACEMENT)
            if row and source.revision != actual_revision:
                if not (
                    (method == "replace" and row.state == "current")
                    or method == "publish"
                ):
                    raise IntentError(
                        "recovery_choice",
                        "Advance a current revision through replacement",
                    )
            if method == "replace" and row is None:
                raise IntentError(
                    "source_missing", "Replacement requires an existing publication"
                )
            if method == "forget":
                if row is None:
                    raise IntentError(
                        "source_missing", "Forget requires an existing publication"
                    )
                if plan.get("operation") != "identity_forget":
                    raise IntentError(
                        "recovery_plan", "Forget requires a durable forget plan"
                    )
                if not (
                    row.state == "current"
                    or json.loads(row.plan).get("operation") == "identity_forget"
                ):
                    raise IntentError("forget_state", FORGET_STATE)
            if method == "replace" and row is not None:
                prior_plan = json.loads(row.plan)
                if plan.get("operation") != "identity_replace":
                    raise IntentError(
                        "recovery_plan",
                        "Replacement requires a durable replacement plan",
                    )
                if row.state == "current" and source.revision != actual_revision + 1:
                    raise IntentError(
                        "revision_sequence",
                        "Replacement must advance exactly one revision",
                    )
                if row.state == "failed" and (
                    prior_plan.get("operation") != "identity_replace"
                    or plan.get("previous_description")
                    != prior_plan.get("previous_description")
                    or plan.get("text_change") != prior_plan.get("text_change")
                ):
                    raise IntentError(
                        "recovery_plan",
                        "Preserve the saved replacement retirement plan",
                    )
            payload = source.model_dump_json()
            if row and source.revision == actual_revision:
                if json.loads(payload) != json.loads(row.description):
                    raise IntentError(
                        "revision_reuse", "Changed description requires a new revision"
                    )
            elif source.revision != actual_revision + 1:
                raise IntentError(
                    "revision_sequence",
                    "New description must advance exactly one revision",
                )
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
