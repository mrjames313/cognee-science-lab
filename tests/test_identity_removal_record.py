"""The removal record in the ledger: every Entity UUID a lab operation
removed, appended once and kept through every later operation, and what a
ledger from before the record gains from its tombstones."""

import json
from uuid import UUID, uuid4

from sqlalchemy import text

from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.retirement import record_removals
from test_identity_storage import FORGET_INTENT, PUBLISH_INTENT, memory_store

HELIOS = UUID("8b4bff50-907b-56b6-bc80-3b0a7018714a")


def source_of(payload):
    return IdentitySource.model_validate_json(json.dumps(payload))


class Graph:
    def __init__(self, *present):
        self.present = {str(p) for p in present}

    async def get_node_delete_data(self, node_ids):
        return {i: object() for i in node_ids if i in self.present}


async def published(store, source):
    attempt = await store.begin(source, expected_revision=0, plan=PUBLISH_INTENT)
    await store.complete(source, attempt)


async def test_a_removal_is_kept_once_through_later_operations(source_payload):
    store = memory_store()
    await store.initialize()
    source = source_of(source_payload)
    await published(store, source)
    plan = dict(operation="identity_replace", retired_entities={str(HELIOS): {}})
    await record_removals(Graph(), store, source, plan)
    kept = str(uuid4())
    plan["retired_entities"][kept] = {}
    await record_removals(Graph(kept), store, source, plan)
    attempt = await store.begin(
        source, expected_revision=1, plan=dict(FORGET_INTENT), method="forget"
    )
    await store.complete(
        source,
        attempt,
        state="forgotten",
        tombstone=Tombstone.of(source, forgotten_at="now"),
    )
    forget = dict(operation="identity_forget", entities={})
    forget["entities"][str(HELIOS)] = dict(type="Entity", refs=[])
    await record_removals(Graph(), store, source, forget)
    assert await store.removed() == {HELIOS: "identity_replace"}


async def test_an_older_ledger_gains_what_its_tombstones_prove_removed(
    source_payload,
):
    """A forget's removed Entities and its mention Entities."""
    store = memory_store()
    await store.initialize()
    source = source_of(source_payload)
    await published(store, source)
    attempt = await store.begin(
        source, expected_revision=1, plan=dict(FORGET_INTENT), method="forget"
    )
    tombstone = Tombstone.of(source, forgotten_at="now", removed_entity_ids=[HELIOS])
    await store.complete(source, attempt, state="forgotten", tombstone=tombstone)
    async with store.session_factory() as session:
        await session.execute(text("DROP TABLE lab_identity_removed_entities"))
        await session.commit()
    await store.initialize()
    expected = {HELIOS, *tombstone.all_mention_ids}
    assert await store.removed() == dict.fromkeys(expected, "identity_forget")


async def forgotten_store(source, removed=()):
    """A store whose one source is forgotten, with Helios removed."""
    store = memory_store()
    await store.initialize()
    await published(store, source)
    attempt = await store.begin(
        source, expected_revision=1, plan=dict(FORGET_INTENT), method="forget"
    )
    tombstone = Tombstone.of(source, forgotten_at="now", removed_entity_ids=removed)
    await store.complete(source, attempt, state="forgotten", tombstone=tombstone)
    return store, tombstone


async def test_a_root_from_main_with_a_served_entity_list_still_opens(
    source_payload,
):
    """Tombstones saved on main since 614703d list `served_entity_ids`;
    this code no longer reads them, but opens the root and fills the
    removal record from such a tombstone."""
    source = source_of(source_payload)
    store, tombstone = await forgotten_store(source, [HELIOS])
    saved = dict(
        json.loads(tombstone.model_dump_json()), served_entity_ids=[str(uuid4())]
    )
    async with store.session_factory() as session:
        await session.execute(text("DROP TABLE lab_identity_removed_entities"))
        await session.execute(
            text("UPDATE lab_identity_publications SET description = :d"),
            dict(d=json.dumps(saved)),
        )
        await session.commit()
    await store.initialize()
    [row] = await store.rows()
    assert row.tombstone == tombstone
    assert HELIOS in await store.removed()


async def test_every_initialize_fills_what_a_crashed_fill_left_out(source_payload):
    """A fill that stopped after the table was made is finished by the next
    initialize; one already recorded keeps its first entry."""
    source = source_of(source_payload)
    store, tombstone = await forgotten_store(source, [HELIOS])
    async with store.session_factory() as session:
        await session.execute(text("DELETE FROM lab_identity_removed_entities"))
        await session.commit()
    await store.record_removed(
        [HELIOS], dataset=uuid4(), source=uuid4(), operation="identity_replace"
    )
    await store.initialize()
    expected = dict.fromkeys(tombstone.all_mention_ids, "identity_forget")
    assert await store.removed() == {**expected, HELIOS: "identity_replace"}


async def test_concurrent_records_of_one_entity_keep_one_entry(source_payload):
    """Two writers recording the same UUIDs at once, as two initializes
    filling one older ledger do, both succeed."""
    import asyncio

    store = memory_store()
    await store.initialize()
    ids = [uuid4() for _ in range(20)]

    async def record(operation):
        await store.record_removed(
            ids, dataset=uuid4(), source=uuid4(), operation=operation
        )

    await asyncio.gather(record("identity_forget"), record("identity_replace"))
    assert set(await store.removed()) == set(ids)
