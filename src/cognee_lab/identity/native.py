"""Small normalizers over documented Cognee interfaces, never adapter clients."""

from typing import Any, NamedTuple
from uuid import UUID


def require_graph_methods(graph, methods):
    """Honor transparent engine handles when rejecting interface-only stubs."""
    from cognee.infrastructure.databases.graph.graph_db_interface import (
        GraphDBInterface,
    )
    from .validation import IntentError

    for method in methods:
        implementation = getattr(graph.__class__, method, None)
        if implementation is None or implementation is getattr(
            GraphDBInterface, method, None
        ):
            raise IntentError("unsupported_capability", f"Graph lacks {method}")


async def edge_metadata(graph, source_id, target_id, relationship):
    from cognee.infrastructure.databases.provenance import EdgeIdentity

    identity = EdgeIdentity(str(source_id), str(target_id), relationship)
    return (await graph.get_edge_delete_data([identity])).get(identity)


async def fact_neighborhood(graph, subject, max_nodes):
    """Uniform EdgeData with real direction/properties, unlike legacy get_edges."""
    nodes, edges = [], []
    async for chunk_nodes, chunk_edges in graph.iter_bounded_neighborhood(
        [subject], depth=1, max_nodes=max_nodes
    ):
        nodes.extend(chunk_nodes)
        edges.extend(chunk_edges)
    return edges, len(nodes) >= max_nodes


class MentionFact(NamedTuple):
    edge_id: UUID
    edge: Any
    evidence: list


async def mention_fact(publisher, source, mid):
    """The `limits` fact edge of a mention Entity, and its evidence records."""
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records

    from .fixture import OSCILLATIONS_ID

    edge_id = UUID(generate_edge_object_id(str(mid), str(OSCILLATIONS_ID), "limits"))
    edge = await edge_metadata(publisher.graph, mid, OSCILLATIONS_ID, "limits")
    evidence = await get_edge_evidence_records(
        [edge_id], source.dataset_id, per_edge_limit=100, total_limit=100
    )
    return MentionFact(edge_id, edge, evidence)
