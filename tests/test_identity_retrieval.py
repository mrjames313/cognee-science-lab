"""Query seed selection must not depend on vector payload layout or lucky rank."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cognee_lab.identity.retrieve import select_seed_entities


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
        graph, candidates, {"oscillations", "hc"}, "What does HC limit?"
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
    allowed = {"missing", "chunk", "a", "b"}
    assert await select_seed_entities(graph, candidates, allowed, "regulation?") == {
        "a"
    }


async def test_no_eligible_candidate_returns_no_seed():
    graph = SimpleNamespace(get_node=AsyncMock(return_value=None))
    assert (
        await select_seed_entities(
            graph, [SimpleNamespace(id="missing")], {"missing"}, "HC"
        )
        == set()
    )


@pytest.mark.parametrize("query", ["What does Aurora controller limit?", "limits?"])
async def test_an_entity_no_served_source_constructs_never_seeds(query):
    """Another dataset's Entity shares Entity_name (probe E5): neither its
    exact name nor its vector rank makes it a seed."""
    nodes = {
        "aurora": {"type": "Entity", "name": "Aurora controller"},
        "helios": {"type": "Entity", "name": "Helios controller"},
    }
    graph = SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get))
    candidates = [SimpleNamespace(id="aurora"), SimpleNamespace(id="helios")]
    assert await select_seed_entities(graph, candidates, {"helios"}, query) == {
        "helios"
    }


def _settled(monkeypatch, outcomes):
    """retrieve_settled over a retrieve that raises or returns `outcomes` in
    turn, and the limit of each read it made."""
    from cognee_lab.identity import retrieve as module

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
    found = await settled(None, "d1", "q", limit=3)
    assert found == dict(
        mode="semantic", scope="identity", dataset_id="d1", facts=["f"]
    )
    assert reads == [3, 3]


@pytest.mark.parametrize("code", ["retrieval_changed", "stale_attempt"])
async def test_a_second_change_fails_the_search(monkeypatch, code):
    from cognee_lab.identity.validation import IntentError

    settled, reads = _settled(
        monkeypatch, [IntentError(code, "first"), IntentError(code, "second")]
    )
    with pytest.raises(IntentError, match="second"):
        await settled(None, "d1", "q")
    assert len(reads) == 2


async def test_another_failure_is_not_read_again(monkeypatch):
    from cognee_lab.identity.validation import IntentError

    settled, reads = _settled(monkeypatch, [IntentError("ledger_format", "old")])
    with pytest.raises(IntentError, match="old"):
        await settled(None, "d1", "q")
    assert len(reads) == 1


@pytest.mark.parametrize(
    "kwargs, code",
    [
        (dict(scope="identity_and_unattributed"), "scope_not_built"),
        (dict(mode="source_aware"), "mode_not_built"),
    ],
)
async def test_an_unbuilt_scope_or_mode_is_refused_before_any_read(
    monkeypatch, kwargs, code
):
    from cognee_lab.identity.retrieve import SearchMode, SearchRefused, SearchScope

    settled, reads = _settled(monkeypatch, [])
    kwargs = dict(
        scope=SearchScope(kwargs.get("scope", "identity")),
        mode=SearchMode(kwargs.get("mode", "semantic")),
    )
    with pytest.raises(SearchRefused) as refused:
        await settled(None, "d1", "q", **kwargs)
    assert refused.value.code == code
    assert reads == []


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
