"""Small normalizers over documented Cognee interfaces, never adapter clients."""


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
