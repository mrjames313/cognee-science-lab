"""The removal record: every Entity UUID a lab operation removed from the
graph, appended once and never changed or deleted. A removed Entity UUID is
never reused (the user's decision of 2026-10-26), so a publication refuses
to rebuild one (`admission.check_no_removed_recipes`) and a re-add derives
a new UUID for it. `RecordStore` keeps the record beside the ledger."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import String, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# The plan operation of the attempt whose delete removed an Entity.
RemovalOperation = Literal[
    "identity_publish", "identity_replace", "identity_withdraw", "identity_forget"
]


class Base(DeclarativeBase):
    pass


class RemovedEntity(Base):
    __tablename__ = "lab_identity_removed_entities"
    entity: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset: Mapped[str] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(36))
    operation: Mapped[str] = mapped_column(String(32))
    recorded_at: Mapped[str] = mapped_column(String(40))


INSERTS = dict(sqlite=sqlite.insert, postgresql=postgresql.insert)


class RemovalRecord:
    """The record's methods, which `RecordStore` mixes in over its
    sessions."""

    async def removed(self) -> dict[UUID, RemovalOperation]:
        """Every Entity UUID a lab operation removed, with the plan
        operation that removed it."""
        async with self.session_factory() as session:
            found = (await session.execute(select(RemovedEntity))).scalars().all()
            return {UUID(r.entity): r.operation for r in found}

    async def record_removed(
        self, entity_ids, *, dataset, source, operation: RemovalOperation
    ):
        """Append each Entity UUID not yet recorded; one already recorded
        keeps its first entry, also against a concurrent writer, so a retry
        or a second fill records nothing twice. `dataset` and `source` name
        the source whose attempt removed them."""
        ids = sorted({str(e) for e in entity_ids})
        if not ids:
            return
        at = datetime.now(timezone.utc).isoformat()
        async with self.session_factory() as session:
            connection = await session.connection()
            insert = INSERTS[connection.dialect.name](RemovedEntity)
            await session.execute(
                insert.on_conflict_do_nothing(index_elements=["entity"]),
                [
                    dict(
                        entity=e,
                        dataset=str(dataset),
                        source=str(source),
                        operation=operation,
                        recorded_at=at,
                    )
                    for e in ids
                ],
            )
            await session.commit()

    async def record_tombstone_removals(self):
        """What the tombstones prove a forget removed: each one's removed
        Entities and the mention Entities of every forgotten life.
        `RecordStore.initialize` runs it every time, so a ledger from before
        the record, or a fill a crash cut short, gains them; it records
        nothing twice. A replacement's retirement or a withdrawal's delete
        that an older ledger completed is not derivable: its plan is
        overwritten or names a candidate the graph may still hold, so a
        re-add treats such an Entity as one no lab record accounts for."""
        for row in await self.rows():
            for tombstone in (row.tombstone, row.last_tombstone):
                if tombstone is None:
                    continue
                ids = set(tombstone.removed_entity_ids) | set(tombstone.all_mention_ids)
                await self.record_removed(
                    ids,
                    dataset=row.dataset,
                    source=row.source,
                    operation="identity_forget",
                )
