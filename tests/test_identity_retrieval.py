"""Query seed selection must not depend on vector payload layout or lucky rank."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cognee_lab.identity.retrieve import select_seed_entities
from cognee_lab.identity.settled import SearchRefused, SearchRequest, SearchScope


@pytest.mark.parametrize("payload", [None, {"text": "HC"}, {"name": "wrong"}])
async def test_explicit_name_beats_higher_ranked_fact_target(payload):
    nodes = {
        "oscillations": {"type": "Entity", "name": "oscillations"},
        "hc": {"type": "Entity", "name": "HC"},
        "mention": {"type": "Entity", "name": "HC"},
    }
    graph = SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get))
    candidates = [
        SimpleNamespace(id=key, payload=payload)
        for key in ["oscillations", "mention", "hc", "hc"]
    ]
    assert await select_seed_entities(
        graph, candidates, {"mention"}, "What does HC limit?", allowed=set(nodes)
    ) == {"hc"}
    assert [call.args[0] for call in graph.get_node.await_args_list] == [
        "oscillations",
        "hc",
    ]


async def test_fallback_skips_stale_and_non_entity_vector_entries():
    nodes = {
        "chunk": {"type": "DocumentChunk", "name": "HC"},
        "a": {"type": "Entity", "name": "Helios controller"},
        "b": {"type": "Entity", "name": "Other device"},
    }
    graph = SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get))
    candidates = [SimpleNamespace(id=key) for key in ["missing", "chunk", "a", "b"]]
    assert await select_seed_entities(
        graph, candidates, set(), "regulation?", allowed={"a", "b"}
    ) == {"a"}


async def test_no_eligible_candidate_returns_no_seed():
    graph = SimpleNamespace(get_node=AsyncMock(return_value=None))
    assert (
        await select_seed_entities(
            graph, [SimpleNamespace(id="missing")], set(), "HC", allowed={"missing"}
        )
        == set()
    )


@pytest.mark.parametrize(
    "ranked, query, seeds",
    [
        (["aurora", "helios"], "What does Aurora controller limit?", set()),
        (["aurora", "helios"], "limits?", set()),
        (["aurora", "helios"], "What does Helios controller limit?", {"helios"}),
        (["helios", "aurora"], "limits?", {"helios"}),
        (["mention", "helios", "aurora"], "limits?", {"helios"}),
    ],
)
async def test_an_entity_no_served_source_constructs_never_seeds(ranked, query, seeds):
    """Another dataset's Entity shares Entity_name (probe E5). It is never a
    seed, and when it ranks first no lab Entity takes its place: a query
    about another dataset's Entity returns no lab fact."""
    nodes = {
        "aurora": {"type": "Entity", "name": "Aurora controller"},
        "helios": {"type": "Entity", "name": "Helios controller"},
        "mention": {"type": "Entity", "name": "The controller"},
    }
    graph = SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get))
    candidates = [SimpleNamespace(id=key) for key in ranked]
    assert (
        await select_seed_entities(
            graph, candidates, {"mention"}, query, allowed={"helios"}
        )
        == seeds
    )


def _settled(monkeypatch, outcomes):
    """retrieve_settled over a retrieve that raises or returns `outcomes` in
    turn, and the limit of each read it made."""
    from cognee_lab.identity import settled as module

    reads = []

    async def fake(publisher, dataset_id, query, *, limit):
        reads.append(limit)
        outcome = outcomes[len(reads) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(module, "retrieve", fake)
    return module.retrieve_settled, reads


@pytest.mark.parametrize("code", ["retrieval_changed", "stale_attempt"])
async def test_a_writer_during_the_read_gets_one_more_read(monkeypatch, code):
    from cognee_lab.identity.validation import IntentError

    settled, reads = _settled(
        monkeypatch, [IntentError(code, "changed"), dict(facts=["f"])]
    )
    found = await settled(None, "d1", "q", SearchRequest.parse(), limit=3)
    assert found == dict(
        mode="semantic", scope="identity", dataset_id="d1", facts=["f"]
    )
    # Cognee's search history stores the result as str(list).
    assert repr(found["mode"]) == "'semantic'"
    assert reads == [3, 3]


@pytest.mark.parametrize("code", ["retrieval_changed", "stale_attempt"])
async def test_a_second_change_fails_the_search(monkeypatch, code):
    from cognee_lab.identity.validation import IntentError

    settled, reads = _settled(
        monkeypatch, [IntentError(code, "first"), IntentError(code, "second")]
    )
    with pytest.raises(IntentError, match="second"):
        await settled(None, "d1", "q", SearchRequest.parse())
    assert len(reads) == 2


async def test_another_failure_is_not_read_again(monkeypatch):
    from cognee_lab.identity.validation import IntentError

    settled, reads = _settled(monkeypatch, [IntentError("ledger_format", "old")])
    with pytest.raises(IntentError, match="old"):
        await settled(None, "d1", "q", SearchRequest.parse())
    assert len(reads) == 1


@pytest.mark.parametrize(
    "scope, mode, code",
    [
        ("identity_and_unattributed", None, "scope_not_built"),
        (None, "source_aware", "mode_not_built"),
        ("everything", None, "config_invalid"),
    ],
)
def test_a_request_refuses_what_is_not_built(scope, mode, code):
    """However it is made: parsed from CLI values, from a search's
    retriever_specific_config, or constructed directly."""
    given = {k: v for k, v in dict(scope=scope, mode=mode).items() if v is not None}
    for make in (
        lambda: SearchRequest.parse(scope, mode),
        lambda: SearchRequest.from_config(given),
        lambda: SearchRequest(**given),
    ):
        with pytest.raises(SearchRefused) as refused:
            make()
        assert refused.value.code == code


def test_a_config_key_that_is_not_a_request_field_is_invalid():
    with pytest.raises(SearchRefused) as refused:
        SearchRequest.from_config(dict(scope="identity", top_k=3))
    assert refused.value.code == "config_invalid"
    assert SearchRequest.from_config(None) == SearchRequest()


def test_a_request_defaults_to_scope_identity_and_mode_semantic():
    request = SearchRequest.parse()
    assert (request.scope, request.mode) == ("identity", "semantic")
    assert request == SearchRequest.parse(SearchScope.IDENTITY, "semantic")


def test_capability_check_sees_through_transparent_engine_handle():
    from cognee.infrastructure.databases.graph.graph_db_interface import (
        GraphDBInterface,
    )
    from cognee_lab.identity.native import require_graph_methods
    from cognee_lab.identity.validation import IntentError

    class Unsupported(GraphDBInterface):
        pass

    class Handle:
        @property
        def __class__(self):
            return Unsupported

    with pytest.raises(IntentError, match="remove_node_source_refs"):
        require_graph_methods(Handle(), ["remove_node_source_refs"])

    class Supported(Unsupported):
        async def remove_node_source_refs(self, *args):
            pass

    class SupportedHandle:
        @property
        def __class__(self):
            return Supported

    require_graph_methods(SupportedHandle(), ["remove_node_source_refs"])


@pytest.mark.parametrize("writer_completes", [False, True])
async def test_a_writer_between_the_read_and_the_fail_gets_a_second_read(
    monkeypatch, source_payload, writer_completes
):
    """Spec review R5 through a real RecordStore: retrieval reads a current
    row, finds its own input failed, and a writer begins on the source
    before RecordStore.fail runs. The fail raises stale_attempt and records
    nothing, and the second read serves the rows the writer left."""
    import json

    from test_identity_storage import PUBLISH_INTENT, memory_store

    from cognee_lab.identity import retrieve as module
    from cognee_lab.identity.models import IdentitySource
    from cognee_lab.identity.settled import retrieve_settled
    from cognee_lab.identity.validation import IntentError

    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = memory_store()
    await store.initialize()
    await store.complete(
        source, await store.begin(source, expected_revision=0, plan={})
    )
    publisher = SimpleNamespace(
        records=store,
        withholdings=SimpleNamespace(rows=AsyncMock(return_value=[])),
        vector=SimpleNamespace(has_collection=AsyncMock(return_value=False)),
    )
    writers = []

    async def drift(publisher, source, reader):
        if writers:
            return {}
        writers.append(
            await store.begin(
                source,
                expected_revision=1,
                plan=dict(PUBLISH_INTENT),
                method="reconcile",
            )
        )
        if writer_completes:
            await store.complete(source, writers[0])
        raise IntentError("source_missing", "own chunks are gone")

    monkeypatch.setattr(module, "live_drift", drift)
    found = await retrieve_settled(
        publisher, source.dataset_id, "q", SearchRequest.parse()
    )
    (row,) = await store.rows(source.dataset_id)
    assert await store.events(source.dataset_id) == []
    assert row.attempt == writers[0]
    if writer_completes:
        assert row.state == "current"
        assert found["unavailable_sources"] == []
    else:
        assert row.state == "pending"
        assert found["unavailable_sources"] == [
            dict(
                identity_data_id=str(source.identity_data_id),
                assignment_id=None,
                reason="publication_pending",
                recovery_event_id=None,
            )
        ]
