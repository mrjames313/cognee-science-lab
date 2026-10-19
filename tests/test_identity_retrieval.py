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
        graph, candidates, {"mention"}, "What does HC limit?"
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
    assert await select_seed_entities(graph, candidates, set(), "regulation?") == {"a"}


async def test_no_eligible_candidate_returns_no_seed():
    graph = SimpleNamespace(get_node=AsyncMock(return_value=None))
    assert (
        await select_seed_entities(graph, [SimpleNamespace(id="missing")], set(), "HC")
        == set()
    )


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
