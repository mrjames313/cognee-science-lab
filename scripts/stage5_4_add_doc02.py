"""
Stage 5.4 — Add DOC02 and inspect the unreconciled graph delta.

Purpose
-------

Establish the first evolving-corpus state:

    State A:
        DOC01 + Stage-5 identity/retrieval overlays

    State B:
        State A + DOC02 processed by ordinary Cognee Cognify

No Stage-5 identity reconciliation is applied to DOC02 here.

We want to observe what Cognee does naturally when a related second
scientific document is added to an existing graph.

In particular:

    - Which existing Entities are reused?
    - Which new representations/fragments appear?
    - Which existing nodes change?
    - Which semantic edges are added?
    - How are changed values such as current limits and VCS rates represented?
    - Does provenance remain document-specific?

Expected starting graph:

    160 nodes
    377 edges

Input document:

    data/DOC02_campaign_A_high_current_v2.md

Dataset:

    helios_stage2

Usage
-----

    uv run python scripts/stage5_4_add_doc02.py

This script should be run ONCE against the current Stage-5.3 graph.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import cognee
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATASET_NAME = "helios_stage2"

DOC02_PATH = Path(
    "data/DOC02_campaign_A_high_current_v2.md"
)

EXPECTED_START_NODES = 160
EXPECTED_START_EDGES = 377

CHUNK_SIZE = 1000

OUTPUT_PATH = Path(
    "outputs/stage5_4_doc02_delta.json"
)


# Properties that change routinely and are not useful for the structural
# comparison.
VOLATILE_NODE_PROPERTIES = {
    "created_at",
    "updated_at",
}

VOLATILE_EDGE_PROPERTIES = {
    "created_at",
    "updated_at",
}


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def node_name(
    props: dict[str, Any],
) -> str:
    return str(
        props.get("name")
        or props.get("surface_text")
        or props.get("short_form")
        or ""
    )


def node_type(
    props: dict[str, Any],
) -> str:
    return str(
        props.get("type", "")
    )


def clean_props(
    props: dict[str, Any],
    ignored: set[str],
) -> dict[str, Any]:
    """
    Remove routine timestamp-like properties before comparing graph state.
    """

    return {
        key: value
        for key, value in props.items()
        if key not in ignored
    }


def changed_keys(
    before: dict[str, Any],
    after: dict[str, Any],
    ignored: set[str],
) -> list[str]:
    """
    Return meaningful property keys whose values changed.
    """

    before_clean = clean_props(
        before,
        ignored,
    )

    after_clean = clean_props(
        after,
        ignored,
    )

    keys = (
        set(before_clean)
        | set(after_clean)
    )

    return sorted(
        key
        for key in keys
        if before_clean.get(key)
        != after_clean.get(key)
    )


# ---------------------------------------------------------------------------
# Snapshot representation
# ---------------------------------------------------------------------------

def edge_key(
    source_id,
    target_id,
    relationship,
    props,
):
    """
    Prefer Cognee's stable edge_object_id.

    Fall back to endpoint + relationship identity for thinner/manual edges.
    """

    edge_object_id = props.get(
        "edge_object_id"
    )

    if edge_object_id:
        return (
            "edge_object_id",
            str(edge_object_id),
        )

    return (
        "triple",
        str(source_id),
        str(target_id),
        str(relationship),
    )


def snapshot_graph(
    nodes,
    edges,
):
    nodes_by_id = {
        str(node_id): dict(props)
        for node_id, props in nodes
    }

    edges_by_key = {}

    for (
        source_id,
        target_id,
        relationship,
        props,
    ) in edges:
        key = edge_key(
            source_id,
            target_id,
            relationship,
            props,
        )

        edges_by_key[key] = {
            "source_id": str(source_id),
            "target_id": str(target_id),
            "relationship": str(
                relationship
            ),
            "props": dict(props),
        }

    return {
        "nodes": nodes_by_id,
        "edges": edges_by_key,
    }


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------

def compute_delta(
    before,
    after,
):
    before_nodes = before["nodes"]
    after_nodes = after["nodes"]

    before_edges = before["edges"]
    after_edges = after["edges"]

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    before_node_ids = set(
        before_nodes
    )

    after_node_ids = set(
        after_nodes
    )

    new_node_ids = (
        after_node_ids
        - before_node_ids
    )

    removed_node_ids = (
        before_node_ids
        - after_node_ids
    )

    common_node_ids = (
        before_node_ids
        & after_node_ids
    )

    changed_nodes = {}

    for node_id in common_node_ids:
        keys = changed_keys(
            before_nodes[node_id],
            after_nodes[node_id],
            VOLATILE_NODE_PROPERTIES,
        )

        if keys:
            changed_nodes[node_id] = {
                "changed_keys": keys,
                "before": before_nodes[
                    node_id
                ],
                "after": after_nodes[
                    node_id
                ],
            }

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    before_edge_keys = set(
        before_edges
    )

    after_edge_keys = set(
        after_edges
    )

    new_edge_keys = (
        after_edge_keys
        - before_edge_keys
    )

    removed_edge_keys = (
        before_edge_keys
        - after_edge_keys
    )

    common_edge_keys = (
        before_edge_keys
        & after_edge_keys
    )

    changed_edges = {}

    for key in common_edge_keys:
        before_edge = (
            before_edges[key]
        )

        after_edge = (
            after_edges[key]
        )

        keys = changed_keys(
            before_edge["props"],
            after_edge["props"],
            VOLATILE_EDGE_PROPERTIES,
        )

        if keys:
            changed_edges[str(key)] = {
                "changed_keys": keys,
                "before": before_edge,
                "after": after_edge,
            }

    return {
        "new_node_ids": sorted(
            new_node_ids
        ),
        "removed_node_ids": sorted(
            removed_node_ids
        ),
        "changed_nodes": changed_nodes,

        "new_edge_keys": list(
            new_edge_keys
        ),
        "removed_edge_keys": list(
            removed_edge_keys
        ),
        "changed_edges": changed_edges,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_graph_summary(
    label,
    snapshot,
):
    nodes = snapshot["nodes"]
    edges = snapshot["edges"]

    node_counts = Counter(
        node_type(props)
        for props in nodes.values()
    )

    relationship_counts = Counter(
        edge["relationship"]
        for edge in edges.values()
    )

    print()
    print("=" * 80)
    print(label)

    print(
        f"nodes: {len(nodes)}"
    )

    print(
        f"edges: {len(edges)}"
    )

    print()

    print("node types:")

    for type_name, count in sorted(
        node_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print(
            f"  {type_name:28s} "
            f"{count}"
        )

    return (
        node_counts,
        relationship_counts,
    )


def print_count_delta(
    title,
    before_counts,
    after_counts,
):
    print()
    print(title)

    all_keys = (
        set(before_counts)
        | set(after_counts)
    )

    rows = []

    for key in all_keys:
        before = before_counts.get(
            key,
            0,
        )

        after = after_counts.get(
            key,
            0,
        )

        delta = after - before

        if delta != 0:
            rows.append(
                (
                    key,
                    before,
                    after,
                    delta,
                )
            )

    if not rows:
        print("  <no changes>")
        return

    for (
        key,
        before,
        after,
        delta,
    ) in sorted(
        rows,
        key=lambda item: (
            -abs(item[3]),
            item[0],
        ),
    ):
        print(
            f"  {key:40s} "
            f"{before:4d} -> "
            f"{after:4d} "
            f"({delta:+d})"
        )


def print_new_nodes(
    delta,
    after,
):
    nodes = after["nodes"]

    new_nodes_by_type = (
        defaultdict(list)
    )

    for node_id in delta[
        "new_node_ids"
    ]:
        props = nodes[node_id]

        new_nodes_by_type[
            node_type(props)
        ].append(
            (
                node_id,
                props,
            )
        )

    print()
    print("=" * 80)
    print("NEW NODES")

    for type_name in sorted(
        new_nodes_by_type
    ):
        entries = (
            new_nodes_by_type[
                type_name
            ]
        )

        print()
        print(
            f"{type_name}: "
            f"{len(entries)}"
        )

        # For semantic and document-related nodes, print details.
        if type_name in {
            "Entity",
            "EntityType",
            "TextDocument",
            "DocumentChunk",
            "TextSummary",
        }:
            for node_id, props in sorted(
                entries,
                key=lambda item: (
                    node_name(
                        item[1]
                    ).casefold(),
                    item[0],
                ),
            ):
                name = node_name(
                    props
                )

                extra = ""

                if type_name == "DocumentChunk":
                    extra = (
                        f" chunk_index="
                        f"{props.get('chunk_index')}"
                    )

                print(
                    f"  {name!r:50s} "
                    f"id={node_id[:8]}"
                    f"{extra}"
                )


def print_changed_nodes(
    delta,
):
    changed = delta[
        "changed_nodes"
    ]

    print()
    print("=" * 80)
    print("CHANGED EXISTING NODES")

    if not changed:
        print(
            "<none, excluding routine timestamps>"
        )
        return

    interesting = []

    for node_id, change in (
        changed.items()
    ):
        before = change[
            "before"
        ]

        after = change[
            "after"
        ]

        interesting.append(
            (
                node_type(after),
                node_name(after),
                node_id,
                change,
            )
        )

    for (
        type_name,
        name,
        node_id,
        change,
    ) in sorted(
        interesting,
        key=lambda item: (
            item[0],
            item[1].casefold(),
        ),
    ):
        print()

        print(
            f"{type_name} "
            f"{name!r} "
            f"id={node_id[:8]}"
        )

        print(
            "  changed keys:",
            change["changed_keys"],
        )

        for key in (
            change[
                "changed_keys"
            ]
        ):
            before_value = (
                change[
                    "before"
                ].get(key)
            )

            after_value = (
                change[
                    "after"
                ].get(key)
            )

            print(
                f"    {key}:"
            )

            print(
                f"      BEFORE: "
                f"{before_value!r}"
            )

            print(
                f"      AFTER:  "
                f"{after_value!r}"
            )


def print_new_edges(
    delta,
    after,
):
    nodes = after["nodes"]
    edges = after["edges"]

    new_edges = [
        edges[key]
        for key in delta[
            "new_edge_keys"
        ]
    ]

    relationship_counts = Counter(
        edge["relationship"]
        for edge in new_edges
    )

    print()
    print("=" * 80)
    print("NEW EDGES")

    print(
        f"total: {len(new_edges)}"
    )

    print()

    print("relationship counts:")

    for relationship, count in (
        relationship_counts.most_common()
    ):
        print(
            f"  {relationship:45s} "
            f"{count}"
        )

    print()
    print(
        "new semantic Entity/EntityType edges:"
    )

    semantic_edges = []

    for edge in new_edges:
        source_props = nodes.get(
            edge["source_id"],
            {},
        )

        target_props = nodes.get(
            edge["target_id"],
            {},
        )

        if (
            node_type(source_props)
            in {"Entity", "EntityType"}
            and
            node_type(target_props)
            in {"Entity", "EntityType"}
        ):
            semantic_edges.append(
                edge
            )

    if not semantic_edges:
        print("  <none>")
        return

    for edge in sorted(
        semantic_edges,
        key=lambda edge: (
            node_name(
                nodes[
                    edge["source_id"]
                ]
            ).casefold(),
            edge["relationship"],
            node_name(
                nodes[
                    edge["target_id"]
                ]
            ).casefold(),
        ),
    ):
        source_props = nodes[
            edge["source_id"]
        ]

        target_props = nodes[
            edge["target_id"]
        ]

        print(
            f"  "
            f"{node_name(source_props)!r} "
            f"--{edge['relationship']}--> "
            f"{node_name(target_props)!r}"
        )


def print_delta_summary(
    before,
    after,
    delta,
):
    before_nodes = before[
        "nodes"
    ]

    after_nodes = after[
        "nodes"
    ]

    before_edges = before[
        "edges"
    ]

    after_edges = after[
        "edges"
    ]

    print()
    print("=" * 80)
    print("DELTA SUMMARY")

    print(
        f"nodes: "
        f"{len(before_nodes)} -> "
        f"{len(after_nodes)} "
        f"({len(after_nodes) - len(before_nodes):+d})"
    )

    print(
        f"edges: "
        f"{len(before_edges)} -> "
        f"{len(after_edges)} "
        f"({len(after_edges) - len(before_edges):+d})"
    )

    print(
        f"new nodes: "
        f"{len(delta['new_node_ids'])}"
    )

    print(
        f"removed nodes: "
        f"{len(delta['removed_node_ids'])}"
    )

    print(
        f"changed existing nodes: "
        f"{len(delta['changed_nodes'])}"
    )

    print(
        f"new edges: "
        f"{len(delta['new_edge_keys'])}"
    )

    print(
        f"removed edges: "
        f"{len(delta['removed_edge_keys'])}"
    )

    print(
        f"changed existing edges: "
        f"{len(delta['changed_edges'])}"
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def json_safe(
    value,
):
    """
    Recursively make graph structures JSON serializable.
    """

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): json_safe(
                item
            )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ) or value is None:
        return value

    return str(value)


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

async def main():
    if not DOC02_PATH.exists():
        raise FileNotFoundError(
            f"DOC02 not found: "
            f"{DOC02_PATH}"
        )

    await setup()

    graph_engine = (
        await get_graph_engine()
    )

    # ------------------------------------------------------------------
    # STATE A
    # ------------------------------------------------------------------

    before_nodes_raw, before_edges_raw = (
        await graph_engine.get_graph_data()
    )

    before = snapshot_graph(
        before_nodes_raw,
        before_edges_raw,
    )

    print_graph_summary(
        "STATE A — BEFORE DOC02",
        before,
    )

    if (
        len(before["nodes"])
        != EXPECTED_START_NODES
        or
        len(before["edges"])
        != EXPECTED_START_EDGES
    ):
        raise RuntimeError(
            "Unexpected starting graph. "
            f"Expected "
            f"{EXPECTED_START_NODES} nodes / "
            f"{EXPECTED_START_EDGES} edges, "
            f"found "
            f"{len(before['nodes'])} / "
            f"{len(before['edges'])}. "
            "Stop before ingesting DOC02 so the "
            "baseline can be checked."
        )

    existing_doc02 = [
        (
            node_id,
            props,
        )
        for node_id, props
        in before["nodes"].items()
        if (
            node_type(props)
            == "TextDocument"
            and
            node_name(props)
            == DOC02_PATH.stem
        )
    ]

    if existing_doc02:
        raise RuntimeError(
            "DOC02 already appears as a "
            "TextDocument in the graph. "
            "This experiment is intended to "
            "run only once."
        )

    # ------------------------------------------------------------------
    # Add DOC02.
    #
    # add() stages the new source document. It does not perform the semantic
    # graph extraction.
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("ADDING DOC02")

    print(
        f"path: {DOC02_PATH}"
    )

    print(
        f"dataset: {DATASET_NAME}"
    )

    await cognee.add(
        data=str(
            DOC02_PATH.resolve()
        ),
        dataset_name=DATASET_NAME,
        incremental_loading=True,
    )

    print(
        "DOC02 added successfully."
    )

    # ------------------------------------------------------------------
    # Cognify incrementally.
    #
    # The intent is:
    #
    #   - existing completed DOC01 data is skipped
    #   - DOC02 is processed
    #   - Stage-5 overlays already in the graph remain untouched
    #
    # Do NOT apply any Stage-5 identity overlay/reconciliation here.
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("COGNIFYING DOC02")

    await cognee.cognify(
        datasets=[
            DATASET_NAME
        ],
        chunk_size=CHUNK_SIZE,
        incremental_loading=True,
    )

    print(
        "Incremental cognify completed."
    )

    # ------------------------------------------------------------------
    # STATE B
    # ------------------------------------------------------------------

    after_nodes_raw, after_edges_raw = (
        await graph_engine.get_graph_data()
    )

    after = snapshot_graph(
        after_nodes_raw,
        after_edges_raw,
    )

    before_node_counts, (
        before_relationship_counts
    ) = print_graph_summary(
        "STATE A — BEFORE DOC02",
        before,
    )

    after_node_counts, (
        after_relationship_counts
    ) = print_graph_summary(
        "STATE B — AFTER ORDINARY DOC02 COGNIFY",
        after,
    )

    delta = compute_delta(
        before,
        after,
    )

    print_delta_summary(
        before,
        after,
        delta,
    )

    print_count_delta(
        "NODE TYPE DELTAS",
        before_node_counts,
        after_node_counts,
    )

    print_count_delta(
        "RELATIONSHIP TYPE DELTAS",
        before_relationship_counts,
        after_relationship_counts,
    )

    print_new_nodes(
        delta,
        after,
    )

    print_changed_nodes(
        delta,
    )

    print_new_edges(
        delta,
        after,
    )

    # ------------------------------------------------------------------
    # Persist a full machine-readable delta.
    # ------------------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "experiment": (
            "stage5_4_doc02_unreconciled_delta"
        ),

        "dataset": DATASET_NAME,

        "document": str(
            DOC02_PATH
        ),

        "chunk_size": CHUNK_SIZE,

        "before": {
            "node_count": len(
                before["nodes"]
            ),
            "edge_count": len(
                before["edges"]
            ),
        },

        "after": {
            "node_count": len(
                after["nodes"]
            ),
            "edge_count": len(
                after["edges"]
            ),
        },

        "delta": delta,
    }

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            json_safe(report),
            handle,
            indent=2,
            sort_keys=True,
        )

    print()
    print("=" * 80)

    print(
        "Full delta written to:"
    )

    print(
        f"  {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    asyncio.run(main())
