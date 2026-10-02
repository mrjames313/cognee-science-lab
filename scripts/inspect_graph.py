import asyncio
import cognee
import sqlite3
import uuid


from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.databases.provenance import EdgeIdentity
from cognee.modules.engine.operations.setup import setup

from cognee_lab.models import Facility

from collections import Counter, defaultdict
from pathlib import Path


def inspect_entity(
    name: str,
    nodes,
    edges,
    node_props,
    entity_chunks,
):
    matches = [
        (node_id, props)
        for node_id, props in nodes
        if props.get("type") == "Entity"
        and props.get("name", "").lower() == name.lower()
    ]

    if not matches:
        print(f"\n{name}: NOT FOUND")
        return

    for node_id, props in matches:
        print(f"\n=== {props.get('name')} ===")
        print(f"id:          {node_id}")
        print(f"description: {props.get('description')}")
        print(f"chunks:      {sorted(entity_chunks.get(node_id, []))}")

        print("edges:")

        for source, target, relationship, edge_props in edges:
            if source == node_id:
                target_props = node_props.get(target, {})
                print(
                    f"  OUT --{relationship}--> "
                    f"{target_props.get('name', target)} "
                    f"[{target_props.get('type')}]"
                )
                print(f"      {edge_props.get('edge_text')}")

            elif target == node_id:
                source_props = node_props.get(source, {})
                print(
                    f"  IN  <--{relationship}-- "
                    f"{source_props.get('name', source)} "
                    f"[{source_props.get('type')}]"
                )
                print(f"      {edge_props.get('edge_text')}")
                

def find_entity_id(
    name: str,
    nodes,):

    for node_id, props in nodes:
        if (
            props.get("type") == "Entity"
            and props.get("name", "").lower() == name.lower()
        ):
            return node_id
    return None


async def main():
    await setup()

    print("Effective configuration:")
    print("  system root: ", cognee.config.get("system_root_directory"))
    print("  data root: ", cognee.config.get("data_root_directory"))
    print("  graph backend: ", cognee.config.get("graph_database_provider"))
    print("  vector backend: ", cognee.config.get("vector_db_provider"))

    graph_engine = await get_graph_engine()
    print("   graph engine type: ", type(graph_engine))

    # Change this to display more or fewer nodes / edges
    display_max = 10

    
    nodes, edges = await graph_engine.get_graph_data()

    # Nodes and node types
    type_counts = Counter(
        props.get("type", "<unknown>")
        for _, props in nodes
    )

    print("\nNode types:")
    for node_type, count in type_counts.most_common():
        print(f"  {node_type:25} {count}")

    
    print(f"\nNodes: {len(nodes)} (showing up to {display_max})")
    for i, node in enumerate(nodes[:display_max]):
        node_id, properties = node
        print(f"\nNODE {i}")
        print("id:", node_id)

        for key,value in properties.items():
            print(f"  {key!r}: {value!r}")
            
        #print(repr(node))

    # Document chunks specifically
    chunks = [
        props
        for _, props in nodes
        if props.get("type") == "DocumentChunk"
    ]

    chunks.sort(key=lambda x: x["chunk_index"])

    print("\nDocument chunks:")
    for chunk in chunks:
        text = chunk["text"]

        print(
            f"\nchunk {chunk['chunk_index']}: "
            f"{chunk['chunk_size']} tokens, "
            f"cut={chunk['cut_type']}"
        )
        print(f"  start: {text[:120]!r}")
        print(f"  end:   {text[-120:]!r}")

        
    # Edges and relationships
    relationship_counts = Counter(
        edge[2]
        for edge in edges
    )

    print("\nRelationship types:")
    for relationship, count in relationship_counts.most_common():
        print(f"  {relationship:30} {count}")

    
    print(f"\nEdges: {len(edges)} (showing up to {display_max})")
    for i, edge in enumerate(edges[:display_max]):
        print(f"\nEDGE {i}")
        print(repr(edge))


    # Characterize triples:
    node_props = {
        node_id: props
        for node_id, props in nodes
    }

    
    edge_shapes = Counter()

    for source, target, relationship, properties in edges:
        source_type = node_props.get(source, {}).get("type", "<unknown>")
        target_type = node_props.get(target, {}).get("type", "<unknown>")

        edge_shapes[(source_type, relationship, target_type)] += 1

    print("\nEdge shapes:")
    for (source_type, relationship, target_type), count in edge_shapes.most_common():
        print(
            f"{count:4}  "
            f"{source_type:18} "
            f"--{relationship}--> "
            f"{target_type}"
        )

    print("\nEdge property keys:")
    edge_property_keys = Counter()

    for _, _, _, properties in edges:
        for key in properties:
            edge_property_keys[key] += 1

    for key, count in edge_property_keys.most_common():
        print(f"  {key:25} {count}")


    entity_chunks = defaultdict(set)

    for source, target, relationship, properties in edges:
        if relationship != "contains":
            continue

        source_props = node_props.get(source, {})
        target_props = node_props.get(target, {})

        if (
                source_props.get("type") == "DocumentChunk"
                and target_props.get("type") == "Entity"
        ):
            entity_chunks[target].add(source_props.get("chunk_index"))

    print("\nEntities appearing in multiple chunks:")

    for entity_id, chunk_indexes in sorted(
            entity_chunks.items(),
            key=lambda item: (-len(item[1]), sorted(item[1])),):
        if len(chunk_indexes) <= 1:
            continue

        props = node_props[entity_id]

        print(
            f"  {props.get('name', '<unnamed>'):35} "
            f"chunks={sorted(chunk_indexes)}"
        )

    # Start looking at entity resolution
    interesting_terms = [
        "helios",
        "h-1",
        "h1-",
        "tokamak",
        "machine",
        "aurora",
        "afrl",
        "vertical",
        "vcs",
        "density",
        "controller",
        "neutral beam",
        "nbi",
        "electron cyclotron",
        "ech",
    ]

    print("\nPotential aliases / coreferences:")

    entities = [
        (node_id, props)
        for node_id, props in nodes
        if props.get("type") == "Entity"
    ]

    for node_id, props in sorted(
            entities,
            key=lambda x: x[1].get("name", ""),
    ):
        name = props.get("name", "")

        if any(term in name.lower() for term in interesting_terms):
            print(
                f"{name:45} "
                f"chunks={sorted(entity_chunks.get(node_id, []))}"
            )

    print("\nSemantic 'contains' edges:")

    # Look into "contains" edges with different meanings
    for source, target, relationship, properties in edges:
        if relationship != "contains":
            continue

        source_props = node_props.get(source, {})
        target_props = node_props.get(target, {})

        if source_props.get("type") == "DocumentChunk":
            continue

        print(
            f"{source_props.get('name', source)} "
            f"--contains--> "
            f"{target_props.get('name', target)}"
        )
        print(f"  edge_text: {properties.get('edge_text')}")

    # Sanity check
    is_a_counts = Counter()

    for source, target, relationship, _ in edges:
        if relationship == "is_a":
            is_a_counts[source] += 1

    print("\nEntity type cardinality:")
    print(Counter(is_a_counts.values()))


    # Look at entity resolution for selected names
    names = [
        "helios-1",
        "afrl",
        "aurora fusion research laboratory",
        "vertical control system",
        "vertical-control system",
        "edge density controller",
        "nbi",
        "neutral beam injection",
        "neutral beam injection system",
        "ech",
        "electron cyclotron heating",
        "electron cyclotron heating system",
        "h1-1854",
        "discharge h1-1854",
    ]

    for name in names:
        inspect_entity(
            name,
            nodes,
            edges,
            node_props,
            entity_chunks,
        )


    # Now check for how units are handled
    for chunk_index in [0, 1]:
        chunk_ids = [
            node_id
            for node_id, props in nodes
            if props.get("type") == "DocumentChunk"
            and props.get("chunk_index") == chunk_index
        ]

        for chunk_id in chunk_ids:
            props = node_props[chunk_id]

            print(f"\n=== CHUNK {chunk_index} ===")
            print(props.get("text"))

            print("\nExtracted entities:")
            for source, target, relationship, _ in edges:
                if source == chunk_id and relationship == "contains":
                    target_props = node_props.get(target, {})
                    print(
                        f"  {target_props.get('name')} "
                        f"[{target_props.get('type')}]"
                    )

    # Investigate edge provenance
    graph_engine = await get_graph_engine()

    print("\nGraph provenance support:")
    print("  get_edge_delete_data:",
        hasattr(graph_engine, "get_edge_delete_data"))
    print("  find_edges_by_source_ref:",
        hasattr(graph_engine, "find_edges_by_source_ref"))

    source_id = find_entity_id("helios-1", nodes)
    target_id = find_entity_id("authorized plasma-current limit", nodes)

    edge_identity = EdgeIdentity(
        source_id=source_id,
        target_id=target_id,
        relationship_name="has_configuration_setting",
    )

    prov = await graph_engine.get_edge_delete_data([edge_identity])

    print("\nProvenance for Helios-1 current-limit edge:")
    print(prov)

    db = Path(".cognee_system/databases/cognee_db")
    con = sqlite3.connect(db)

    relationship = "has_configuration_setting"

    rows = con.execute(
        """
        SELECT
        id,
        dataset_id,
        data_id,
        pipeline_run_id,
        chunk_id,
        chunk_index,
        edge_id,
        evidence_kind,
        source_task,
        confidence
        FROM provenance_edge_evidence
        WHERE source_node_id = ?
        AND destination_node_id = ?
        AND relationship_name = ?
        ORDER BY chunk_index
        """,
        (
            source_id.replace("-", ""),
            target_id.replace("-", ""),
            relationship,
        ),
    ).fetchall()

    print("\nEvidence for current-limit edge:")
    
    for row in rows:
        (
            evidence_id,
            dataset_id,
            data_id,
            pipeline_run_id,
            chunk_id,
            chunk_index,
            edge_id,
            evidence_kind,
            source_task,
            confidence,
        ) = row

        print(f"\nevidence_id:   {evidence_id}")
        print(f"edge_id:       {edge_id}")
        print(f"data_id:       {data_id}")
        print(f"pipeline_run:  {pipeline_run_id}")
        print(f"chunk_id:      {chunk_id}")
        print(f"chunk_index:   {chunk_index}")
        print(f"kind:          {evidence_kind}")
        print(f"source_task:   {source_task}")
        print(f"confidence:    {confidence}")

        # Convert SQLite's compact UUID representation back to
        # the hyphenated form used by get_graph_data().
        graph_chunk_id = str(uuid.UUID(chunk_id))
        
        chunk_props = node_props.get(graph_chunk_id)

        if chunk_props:
            print("\nSupporting chunk:")
            print(chunk_props.get("text"))
        else:
            print("\nChunk node not found in graph.")

    multi_edge_id = "82710a60-d1ac-53c3-9f7d-fa8838d5249b"

    print("\n=== Multi-evidence edge ===")

    for source, target, relationship, edge_props in edges:
        if edge_props.get("edge_object_id") == multi_edge_id:
            source_props = node_props[source]
            target_props = node_props[target]

            print(
                f"{source_props.get('name')} "
                f"--{relationship}--> "
                f"{target_props.get('name')}"
            )
            print("edge text:", edge_props.get("edge_text"))

    rows = con.execute(
        """
        SELECT chunk_id, chunk_index
        FROM provenance_edge_evidence
        WHERE edge_id = ?
        ORDER BY chunk_index
        """,
        (multi_edge_id.replace("-", ""),),
    ).fetchall()

    for chunk_id, chunk_index in rows:
        graph_chunk_id = str(uuid.UUID(chunk_id))
        chunk = node_props.get(graph_chunk_id)

        print(f"\n--- supporting chunk {chunk_index} ---")
        print(chunk.get("text") if chunk else "Chunk not found")

    con.close()

        
    # Show all the fields that are created for a relatively simple DataPoint extension
    print("\nModel-specific investigation")
    print("model fields:")
    print(Facility.model_fields)

    print("\nmodel_config:")
    print(Facility.model_config)

    
    
if __name__ == "__main__":
    asyncio.run(main())
    
    
