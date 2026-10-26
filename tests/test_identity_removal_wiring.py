"""Each lab operation that deletes records what it removed in the removal
record, through its own code, before a later begin overwrites the plan
that listed it. The ledger is a real RecordStore; the graph and Cognee's
deletes stand in, and a stand-in delete removes the nodes it is given."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.validation import IntentError
from test_identity_forget import FORGET_GRAPH_METHODS
from test_identity_outside_deletion import HELIOS, admit, renamed
from test_identity_readd_outside_deletion import (
    co_owner,
    dropped_helios,
    readd_writes,
    without_input,
)
from test_identity_storage import PUBLISH_INTENT, memory_store

UNUSED = {
    *FORGET_GRAPH_METHODS,
    "find_nodes_by_source_ref",
    "find_edges_by_source_ref",
}


def source_of(payload):
    return IdentitySource.model_validate_json(json.dumps(payload))


def at_revision(source, revision):
    return source.model_copy(update={"revision": revision})


class Graph:
    """The nodes still present, and those of them the source owns; the
    stand-in deletes remove from it."""

    def __init__(self, *present, owned=()):
        self.present = {str(p) for p in (*present, *owned)}
        self.owned = {str(o) for o in owned}

    def delete(self, ids):
        self.present -= {str(i) for i in ids}

    async def get_node(self, node_id):
        return {"type": "Entity"} if str(node_id) in self.present else None

    async def get_node_delete_data(self, node_ids):
        node = SimpleNamespace(
            source_ref_keys=[], node_type="Entity", indexed_fields=[]
        )
        return {i: node for i in node_ids if str(i) in self.present}

    async def find_nodes_by_source_ref(self, _):
        return sorted(self.owned & self.present)

    async def find_edges_by_source_ref(self, _):
        return []

    async def get_edge_delete_data(self, _):
        return {}

    async def unused(self, *_):
        return None

    locals().update(dict.fromkeys(UNUSED - set(locals()), unused))


def entity_plan(operation, *entities):
    return dict(
        operation=operation,
        entities={str(e): dict(type="Entity", refs=[]) for e in entities},
    )


async def ledger():
    records = memory_store()
    await records.initialize()
    return records


async def publish(records, source):
    attempt = await records.begin(
        source, expected_revision=source.revision - 1, plan=PUBLISH_INTENT
    )
    await records.complete(source, attempt)


async def failed_first(records, source, plan):
    attempt = await records.begin(
        source, expected_revision=source.revision - 1, plan=plan
    )
    await records.fail(source, attempt, "nodes", "injected")


async def failed_replacement(records, previous, source, retired=()):
    """`source` replaced `previous` and failed, planning to retire
    `retired`."""
    await publish(records, previous)
    plan = dict(
        operation="identity_replace",
        revision=source.revision,
        previous_description=previous.model_dump_json(),
        retired_entities={str(e): {} for e in retired},
    )
    attempt = await records.begin(
        source, expected_revision=previous.revision, plan=plan, method="replace"
    )
    await records.fail(source, attempt, "replace_saved", "injected")


@pytest.fixture
def forgetting(monkeypatch):
    """forget() with its Cognee deletes and checks stood in: the plan from
    the graph names `owned` and `kept`, and the native delete removes
    `owned`; another source still owns `kept`."""
    import cognee.modules.users.methods as users
    from cognee_lab.identity import forget as module

    async def nothing(*_, **__):
        return None

    state = SimpleNamespace(owned=(), kept=(), graph=None)

    async def plan_of(_, source):
        doc = source.inputs[source.original_input_ref]
        files = {str(doc.data_id): [], str(source.identity_data_id): []}
        return dict(
            entity_plan("identity_forget", *state.owned, *state.kept),
            revision=source.revision,
            original_data_id=str(doc.data_id),
            stored_files=files,
        )

    async def delete_data(*_, **__):
        state.graph.delete(state.owned)

    for name in ("withdraw_contributions", "clear_withholdings", "verify_forgotten"):
        monkeypatch.setattr(module, name, nothing)
    monkeypatch.setattr(module, "delete_data", delete_data)
    monkeypatch.setattr(module, "forget_plan", plan_of)
    monkeypatch.setattr(module, "contribution_triples", lambda _: [])
    monkeypatch.setattr(users, "get_default_user", nothing)

    async def run(records, graph, source, owned=(), kept=()):
        state.owned, state.kept, state.graph = tuple(owned), tuple(kept), graph
        publisher = SimpleNamespace(graph=graph, records=records)
        return await module.forget(publisher, source, expected_revision=source.revision)

    return run


async def readd_begin(records, source):
    """The re-add's begin, which replaces the forgotten row's plan."""
    await records.begin(
        at_revision(source, source.revision + 1),
        expected_revision=source.revision,
        plan=PUBLISH_INTENT,
    )


async def test_forget_records_what_its_delete_removed(source_payload, forgetting):
    records = await ledger()
    source = source_of(source_payload)
    await publish(records, source)
    owned, kept = uuid4(), uuid4()
    await forgetting(records, Graph(owned, kept), source, owned=(owned,), kept=(kept,))
    await readd_begin(records, source)
    assert await records.removed() == {owned: "identity_forget"}


@pytest.mark.parametrize("operation", ["publish", "replace"])
async def test_forget_records_a_failed_attempt_removals_before_its_begin(
    source_payload, forgetting, operation
):
    """A failed publication's erasure retry, or a failed replacement,
    retired Entities its own retry would record; the forget's begin
    replaces that plan, so the forget records them first."""
    records = await ledger()
    source = source_of(source_payload)
    retired = uuid4()
    if operation == "publish":
        plan = dict(operation="identity_publish", retired_entities={str(retired): {}})
        await failed_first(records, source, plan)
    else:
        await failed_replacement(
            records, source, at_revision(source, 2), retired=(retired,)
        )
        source = at_revision(source, 2)
    await forgetting(records, Graph(), source)
    await readd_begin(records, source)
    assert await records.removed() == {retired: f"identity_{operation}"}


async def test_a_failed_replacement_that_would_rebuild_a_removed_entity_is_forgotten(
    source_payload, forgetting
):
    """The review's steps: C's replacement adds a recipe of Helios and fails
    before it writes; A's forget removes Helios. C's retry is refused, with
    forget and re-add as the remedy; the forget begins on the failed
    replacement, and C's re-add builds Helios under a derived UUID."""
    records = await ledger()
    a = without_input(source_payload)
    c = without_input(json.loads(co_owner(renamed(source_payload)).model_dump_json()))
    c_v1 = at_revision(dropped_helios(json.loads(c.model_dump_json())), 1)
    c_v2 = at_revision(c, 2)
    await failed_replacement(records, c_v1, c_v2)
    await publish(records, a)
    graph = Graph(HELIOS)
    await forgetting(records, graph, a, owned=(HELIOS,))
    assert await records.removed() == {HELIOS: "identity_forget"}

    with pytest.raises(IntentError) as refused:
        await admit(await records.rows(), c_v2, removed=await records.removed())
    assert refused.value.code == "entity_recreation"
    assert "Forget this source and re-add it" in str(refused.value)

    owned = uuid4()
    graph.present.add(str(owned))
    await forgetting(records, graph, c_v2, owned=(owned,))
    row = await records.row(c_v2)
    assert row.state == "forgotten" and row.revision == 2
    readded = await readd_writes(
        await records.rows(), row.tombstone, c_v2, await records.removed()
    )
    assert str(HELIOS) not in readded.model_dump_json()
    target = readded.mention_resolutions["r01"].target_entity_id
    assert readded.entity_constructions[target].name == "Helios controller"


@pytest.fixture
def withdrawing(monkeypatch):
    """withdraw() with Cognee's owner delete and its checks stood in: the
    delete removes the source's refs, and every node it owned alone."""
    from cognee.infrastructure.databases.unified import unified_store_engine
    from cognee_lab.identity import withdraw as module

    async def nothing(*_, **__):
        return None

    for name in (
        "withdraw_contributions",
        "verify_no_contributions",
        "verify_survivors",
    ):
        monkeypatch.setattr(module, name, nothing)

    class Engine:
        def __init__(self, graph, *_):
            self.graph = graph

        async def delete_by_source_ref(self, _):
            gone = self.graph.owned - self.graph.shared
            self.graph.delete(gone)
            self.graph.owned = set()
            return SimpleNamespace(deleted_node_ids=sorted(gone))

    monkeypatch.setattr(unified_store_engine, "UnifiedStoreEngine", Engine)

    async def run(records, graph, source, shared=()):
        graph.shared = {str(s) for s in shared}
        publisher = SimpleNamespace(
            graph=graph, vector=None, records=records, runtime_profile={}
        )
        return await module.withdraw(
            publisher, source, expected_revision=source.revision
        )

    return run


async def test_withdraw_records_what_its_delete_removed(source_payload, withdrawing):
    records = await ledger()
    source = source_of(source_payload)
    await publish(records, source)
    alone, shared = uuid4(), uuid4()
    graph = Graph(owned=(alone, shared))
    await withdrawing(records, graph, source, shared=(shared,))
    await readd_begin_after_forget(records, source)
    assert await records.removed() == {alone: "identity_withdraw"}


async def test_withdraw_records_a_failed_publication_removals_before_its_begin(
    source_payload, withdrawing
):
    records = await ledger()
    source = source_of(source_payload)
    retired = uuid4()
    plan = dict(operation="identity_publish", retired_entities={str(retired): {}})
    await failed_first(records, source, plan)
    await withdrawing(records, Graph(), source)
    assert await records.removed() == {retired: "identity_publish"}


async def readd_begin_after_forget(records, source):
    """A forget, then the re-add's begin: two plans over the withdrawal's."""
    from cognee_lab.identity.models import Tombstone

    attempt = await records.begin(
        source,
        expected_revision=source.revision,
        plan=dict(operation="identity_forget"),
        method="forget",
    )
    tombstone = Tombstone.of(source, forgotten_at="now")
    await records.complete(source, attempt, state="forgotten", tombstone=tombstone)
    await readd_begin(records, source)


@pytest.fixture
def retiring(monkeypatch):
    """A replacement's or an erasure retry's retirement with its graph
    writes stood in: the plan retires `retired`, and the retirement deletes
    what no other source owns. The publication's own writes stand in too:
    `_apply_pending` runs the retirement, then completes."""
    from cognee_lab.identity import publish, replace
    from cognee_lab.identity import storage

    async def nothing(*_, **__):
        return None

    state = SimpleNamespace(retired=(), shared=(), registered=None)

    async def plan_retirement(graph, plan, olds, source):
        plan.setdefault("retired_entities", {}).update(
            {str(e): {} for e in state.retired}
        )

    async def retire(graph, vector, source, plan):
        graph.delete(set(plan["retired_entities"]) - {str(e) for e in state.shared})

    async def apply_pending(self, source, *, attempt, after_write=None, **_):
        if after_write is not None:
            await after_write()
        await self.records.complete(source, attempt)

    async def read_registered(_):
        return state.registered

    async def write_registered(source, _):
        state.registered = source

    for name in ("admit_replacement", "verify_retired"):
        monkeypatch.setattr(replace, name, nothing)
    monkeypatch.setattr(replace, "plan_retirement", plan_retirement)
    monkeypatch.setattr(replace, "retire", retire)
    monkeypatch.setattr(replace, "read_registered", read_registered)
    monkeypatch.setattr(replace, "write_registered", write_registered)
    # The erasure chain's own rules are the ledger checker's.
    for module in (replace, storage):
        monkeypatch.setattr(module, "check_retry_chain", lambda *_: None)

    async def preflight(*_, **__):
        return SimpleNamespace(entities={}, edges=[])

    monkeypatch.setattr(publish.Publisher, "preflight", preflight)
    monkeypatch.setattr(publish.Publisher, "_apply_pending", apply_pending)
    return state


async def publisher_over(records, graph):
    from cognee_lab.identity.publish import Publisher

    publisher = Publisher(graph, None, records)
    await publisher.withholdings.initialize()
    return publisher


async def test_replace_records_what_its_retirement_removed(source_payload, retiring):
    from cognee_lab.identity.replace import replace

    records = await ledger()
    source = source_of(source_payload)
    await publish(records, source)
    alone, shared = uuid4(), uuid4()
    retiring.retired, retiring.shared, retiring.registered = (
        (alone, shared),
        (shared,),
        source,
    )
    publisher = await publisher_over(records, Graph(alone, shared))
    following = at_revision(source, 2)
    await replace(
        publisher, following, texts={}, chunks=[], ctx=None, expected_revision=1
    )
    await readd_begin_after_forget(records, following)
    assert await records.removed() == {alone: "identity_replace"}


async def test_an_erasure_retry_records_what_its_retirement_removed(
    source_payload, retiring
):
    """A failed publication's reconcile with another description at the
    saved revision supersedes it, and retires what it wrote."""
    records = await ledger()
    source = source_of(source_payload)
    await failed_first(records, source, PUBLISH_INTENT)
    removal = without_input(json.loads(source.model_dump_json()))
    written = uuid4()
    retiring.retired = (written,)
    publisher = await publisher_over(records, Graph(written))
    await publisher._publish(
        removal, {}, [], None, expected_revision=1, method="reconcile"
    )
    await readd_begin_after_forget(records, removal)
    assert await records.removed() == {written: "identity_publish"}
