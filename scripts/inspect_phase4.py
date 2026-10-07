import asyncio
import cognee
import sqlite3
import uuid


from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.databases.provenance import EdgeIdentity
from cognee.infrastructure.databases.relational import (get_relational_engine,)
from cognee.modules.engine.operations.setup import setup

from cognee_lab.models import Facility
from cognee_lab.graph_snapshot import load_graph_snapshot

from collections import Counter, defaultdict
from pathlib import Path
from sqlalchemy import text as sql_text

GRAPH_OUTPUT_PATH = Path("outputs/stage4_graph.html").resolve()


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

    print(f"\nNodes: {len(nodes)}")
    print("\nNode types:")
    for node_type, count in type_counts.most_common():
        print(f"  {node_type:25} {count}")

    # Edges and relationships
    relationship_counts = Counter(
        edge[2]
        for edge in edges
    )

    print("\nRelationship types:")
    for relationship, count in relationship_counts.most_common():
        print(f"  {relationship:30} {count}")

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

    print(f"\nEdges: {len(edges)}")
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


    # Document chunks specifically
    chunks = [
        props
        for _, props in nodes
        if props.get("type") == "DocumentChunk"
    ]

    chunks.sort(key=lambda x: x["chunk_index"])


    print("\nDocument chunks:")
    for chunk in chunks:
        c_text = chunk["text"]

        print(
            f"\nchunk {chunk['chunk_index']}: "
            f"{chunk['chunk_size']} tokens, "
            f"cut={chunk['cut_type']}"
        )
        print(f"  start: {c_text[:120]!r}")
        print(f"  end:   {c_text[-120:]!r}")

        
    print(f"\nNodes: {len(nodes)} (showing up to {display_max})")
    for i, node in enumerate(nodes[:display_max]):
        node_id, properties = node
        print(f"\nNODE {i}")
        print("id:", node_id)

        for key,value in properties.items():
            print(f"  {key!r}: {value!r}")
            
        #print(repr(node))

    
    print(f"\nEdges: {len(edges)} (showing up to {display_max})")
    for i, edge in enumerate(edges[:display_max]):
        print(f"\nEDGE {i}")
        print(repr(edge))


    
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


    # Sanity check
    is_a_counts = Counter()

    for source, target, relationship, _ in edges:
        if relationship == "is_a":
            is_a_counts[source] += 1

    print("\nEntity type cardinality:")
    print(Counter(is_a_counts.values()))


    ## TEMP
    print("\nAbbreviation nodes:")

    for node_id, props in nodes:
        if props.get("type") == "Abbreviation":
            print(
                f"  id={node_id}\n"
                f"    short_form={props.get('short_form')!r}\n"
                f"    full_form={props.get('full_form')!r}"
            )
    print("\nAbbreviationObservation nodes:")

    observations = []

    for node_id, props in nodes:
        if props.get("type") == "AbbreviationObservation":
            observations.append((node_id, props))

    for node_id, props in observations:
        print(
            f"  {props.get('short_form')!r}"
            f" -> {props.get('full_form')!r}"
            f"  id={node_id}"
        )

    print(
        f"\nTotal AbbreviationObservation nodes: "
        f"{len(observations)}"
    )

    print("\nAbbreviationGraph nodes:")

    for node_id, props in nodes:
        if props.get("type") == "AbbreviationGraph":
            print(f"  id={node_id}")
            print(f"  properties={props}")



    abbreviation_edges = []

    for source_id, target_id, rel, props in edges:
        if rel == "abbreviations":
            abbreviation_edges.append(
                (
                    EdgeIdentity(
                        source_id=str(source_id),
                        target_id=str(target_id),
                        relationship_name=rel,
                    ),
                    props,
                )
            )

    print("\nAbbreviation edges:")

    for edge, props in abbreviation_edges:
        print(
            f"  {edge.source_id} --{edge.relationship_name}--> "
            f"{edge.target_id}"
        )
        print(f"    edge_object_id={props.get('edge_object_id')}")

    edge_identities = [
        edge for edge, _ in abbreviation_edges
    ]

    delete_data = await graph_engine.get_edge_delete_data(
        edge_identities
    )

    print("\nAbbreviation edge source refs:")

    for edge, data in delete_data.items():
        print(
            f"  {edge.source_id} --{edge.relationship_name}--> "
            f"{edge.target_id}"
        )
        print(f"    source_ref_keys={data.source_ref_keys}")


    edge_object_ids = {
        str(props["edge_object_id"])
        for _, props in abbreviation_edges
        if props.get("edge_object_id") is not None
    }

    relational_engine = get_relational_engine()

    async with relational_engine.get_async_session() as session:
        result = await session.execute(
            sql_text("SELECT * FROM provenance_edge_evidence")
        )
        evidence_rows = result.mappings().all()

    print("\nEdge-evidence columns:")

    if evidence_rows:
        print(" ", list(evidence_rows[0].keys()))
    else:
        print("  no evidence rows")

    print("\nEvidence for abbreviation edges:")

    for row in evidence_rows:
        row = dict(row)

        # Don't assume whether this version calls it edge_id,
        # edge_object_id, etc. Look at all edge-related fields.
        edge_values = {
            str(value)
            for key, value in row.items()
            if "edge" in key.lower() and value is not None
        }

        if edge_object_ids & edge_values:
            print(" ", row)

    chunk_index_by_id = {
        str(node_id): props.get("chunk_index")
        for node_id, props in nodes
        if props.get("type") == "DocumentChunk"
    }

    print("\nChunk IDs:")

    for chunk_id, chunk_index in chunk_index_by_id.items():
        print(f"  chunk {chunk_index}: {chunk_id}")


    print("\nTotal provenance_edge_evidence rows:", len(evidence_rows))

    print("\nEvidence relationship counts:")
    for name, count in Counter(
            row["relationship_name"] for row in evidence_rows
    ).most_common():
        print(f"  {name!r}: {count}")

    print("\nRows whose relationship_name is 'abbreviations':")
    for row in evidence_rows:
        if row["relationship_name"] == "abbreviations":
            print(" ", dict(row))


    abbr_pairs = {
        (edge.source_id, edge.target_id)
        for edge, _ in abbreviation_edges
    }

    print("\nEvidence matching abbreviation endpoints:")

    for row in evidence_rows:
        pair = (
            str(row["source_node_id"]),
            str(row["destination_node_id"]),
        )

        if pair in abbr_pairs:
            print(" ", dict(row))

    print("\nSource-linked abbreviation observations:")

    for node_id, props in nodes:
        if props.get("type") == "AbbreviationObservation":
            print(
                f"  chunk={props.get('source_chunk_index')} "
                f"{props.get('short_form')!r}"
                f" -> {props.get('full_form')!r} "
                f"id={node_id}"
            )

    # Produce the graph visualization
    await cognee.visualize_graph(
        str(GRAPH_OUTPUT_PATH),
        full=True,
    )

    print(f"\nGraph written to: {GRAPH_OUTPUT_PATH}")    
    
if __name__ == "__main__":
    asyncio.run(main())
    
    
