import argparse
import asyncio
from collections import Counter, defaultdict, deque

from dotenv import load_dotenv

load_dotenv()

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup


SEMANTIC_NODE_TYPES = {
    "Entity",
    "EntityType",
}


def node_type(props: dict) -> str:
    return str(props.get("type", ""))


def node_name(props: dict) -> str:
    return str(
        props.get("name")
        or props.get("surface_text")
        or ""
    )


def build_identity_adjacency(
    edges,
    nodes_by_id,
):
    """
    Build the semantic Entity identity graph.

    Support-layer relationships such as the old Stage-5.2
    Mention --resolves_to--> Entity edge are deliberately excluded.
    """

    adjacency = defaultdict(set)

    for source_id, target_id, relationship, props in edges:
        if relationship != "resolves_to":
            continue

        source_id = str(source_id)
        target_id = str(target_id)

        source_props = nodes_by_id.get(source_id, {})
        target_props = nodes_by_id.get(target_id, {})

        if (
            node_type(source_props) != "Entity"
            or node_type(target_props) != "Entity"
        ):
            continue

        if props.get("graph_layer") != "semantic":
            continue

        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)

    return adjacency


def identity_closure(seed_id: str, adjacency) -> set[str]:
    closure = set()
    queue = deque([seed_id])

    while queue:
        current = queue.popleft()

        if current in closure:
            continue

        closure.add(current)

        for neighbor in adjacency.get(current, ()):
            if neighbor not in closure:
                queue.append(neighbor)

    return closure


def find_canonical(
    closure: set[str],
    nodes_by_id: dict[str, dict],
) -> str | None:
    candidates = [
        node_id
        for node_id in closure
        if nodes_by_id[node_id].get("entity_role") == "canonical"
    ]

    if len(candidates) == 1:
        return candidates[0]

    return None


def build_global_canonical_map(
    entity_ids: set[str],
    adjacency,
    nodes_by_id,
):
    """
    Build a convenient materialized identity view in memory.

    This does NOT modify the graph.
    """

    canonical_of = {}
    visited = set()

    for entity_id in entity_ids:
        if entity_id in visited:
            continue

        closure = identity_closure(
            entity_id,
            adjacency,
        )

        visited.update(closure)

        canonical_id = find_canonical(
            closure,
            nodes_by_id,
        )

        if canonical_id is None:
            # No unambiguous canonical Entity.
            # Leave each representation as itself.
            for member_id in closure:
                canonical_of[member_id] = member_id
        else:
            for member_id in closure:
                canonical_of[member_id] = canonical_id

    return canonical_of


def semantic_incident_edges(
    closure: set[str],
    edges,
    nodes_by_id,
):
    """
    Return semantic edges touching any member of this identity closure.

    Source/context/support edges are deliberately excluded by endpoint type.
    """

    semantic = []
    excluded = []

    for source_id, target_id, relationship, props in edges:
        source_id = str(source_id)
        target_id = str(target_id)

        if (
            source_id not in closure
            and target_id not in closure
        ):
            continue

        # Identity edges define the closure; they are not domain facts.
        if relationship == "resolves_to":
            continue

        source_props = nodes_by_id.get(source_id, {})
        target_props = nodes_by_id.get(target_id, {})

        source_type = node_type(source_props)
        target_type = node_type(target_props)

        if (
            source_type in SEMANTIC_NODE_TYPES
            and target_type in SEMANTIC_NODE_TYPES
        ):
            semantic.append(
                (
                    source_id,
                    target_id,
                    relationship,
                    props,
                )
            )
        else:
            excluded.append(
                (
                    source_id,
                    target_id,
                    relationship,
                    props,
                )
            )

    return semantic, excluded


def canonicalize_edge(
    edge,
    canonical_of,
):
    source_id, target_id, relationship, props = edge

    source_id = str(source_id)
    target_id = str(target_id)

    return (
        canonical_of.get(source_id, source_id),
        relationship,
        canonical_of.get(target_id, target_id),
    )


async def main(focus: str | None, show_facts: bool):
    await setup()

    graph_engine = await get_graph_engine()
    nodes, edges = await graph_engine.get_graph_data()

    nodes_by_id = {
        str(node_id): props
        for node_id, props in nodes
    }

    entity_ids = {
        node_id
        for node_id, props in nodes_by_id.items()
        if node_type(props) == "Entity"
    }

    identity_adjacency = build_identity_adjacency(
        edges,
        nodes_by_id,
    )

    canonical_of = build_global_canonical_map(
        entity_ids,
        identity_adjacency,
        nodes_by_id,
    )

    # ----------------------------------------------------------
    # Find connected identity components.
    # ----------------------------------------------------------

    components = []
    visited = set()

    for entity_id in sorted(entity_ids):
        if entity_id in visited:
            continue

        closure = identity_closure(
            entity_id,
            identity_adjacency,
        )

        visited.update(closure)

        if len(closure) > 1:
            components.append(closure)

    # Optional focus by Entity name.
    if focus is not None:
        focus_norm = focus.casefold()

        matching_ids = {
            node_id
            for node_id, props in nodes_by_id.items()
            if (
                node_type(props) == "Entity"
                and node_name(props).casefold() == focus_norm
            )
        }

        if not matching_ids:
            raise RuntimeError(
                f"No Entity named {focus!r} found."
            )

        components = [
            component
            for component in components
            if component & matching_ids
        ]

        if not components:
            raise RuntimeError(
                f"Entity {focus!r} is not part of a "
                "multi-node resolves_to component."
            )

    print(
        f"Graph: {len(nodes)} nodes / {len(edges)} edges"
    )
    print(
        f"Identity components: {len(components)}"
    )

    # ----------------------------------------------------------
    # Inspect each identity component.
    # ----------------------------------------------------------

    for component_index, closure in enumerate(
        sorted(
            components,
            key=lambda c: sorted(
                node_name(nodes_by_id[x]).casefold()
                for x in c
            ),
        ),
        start=1,
    ):
        canonical_id = find_canonical(
            closure,
            nodes_by_id,
        )

        print()
        print("=" * 80)
        print(f"COMPONENT {component_index}")

        if canonical_id is not None:
            print(
                "canonical:",
                repr(
                    node_name(
                        nodes_by_id[canonical_id]
                    )
                ),
            )
        else:
            print("canonical: <ambiguous or absent>")

        print("\nmembers:")

        for member_id in sorted(
            closure,
            key=lambda x: (
                str(
                    nodes_by_id[x].get(
                        "entity_role"
                    )
                    or ""
                ),
                node_name(
                    nodes_by_id[x]
                ).casefold(),
            ),
        ):
            props = nodes_by_id[member_id]

            role = (
                props.get("entity_role")
                or "<unset>"
            )

            extras = []

            if role == "mention":
                extras.append(
                    f"occurrence={props.get('occurrence_index')}"
                )

                chunk_id = (
                    props.get("source_chunk_id")
                    or props.get("scope_chunk_id")
                )

                if chunk_id:
                    extras.append(
                        f"chunk={str(chunk_id)[:8]}"
                    )

            extra_text = (
                " [" + ", ".join(extras) + "]"
                if extras
                else ""
            )

            print(
                f"  {role:10s} "
                f"{node_name(props)!r} "
                f"id={member_id[:8]}"
                f"{extra_text}"
            )

        # Closure should be identical regardless of which resolved
        # representation is used as the starting node.
        closure_consistent = all(
            identity_closure(
                member_id,
                identity_adjacency,
            )
            == closure
            for member_id in closure
        )

        print(
            "\nclosure consistency:",
            "PASS" if closure_consistent else "FAIL",
        )

        semantic_edges, excluded_edges = (
            semantic_incident_edges(
                closure,
                edges,
                nodes_by_id,
            )
        )

        # Group structurally equivalent semantic relations after
        # canonicalizing known identity endpoints.
        #
        # This is an in-memory retrieval view, NOT a graph rewrite.
        logical_groups = defaultdict(list)

        for edge in semantic_edges:
            key = canonicalize_edge(
                edge,
                canonical_of,
            )

            logical_groups[key].append(edge)

        print(
            f"raw semantic incident edges: "
            f"{len(semantic_edges)}"
        )

        print(
            f"logical edge groups after identity normalization: "
            f"{len(logical_groups)}"
        )

        excluded_types = Counter(
            relationship
            for _, _, relationship, _ in excluded_edges
        )

        print(
            f"excluded source/support edges: "
            f"{len(excluded_edges)}"
        )

        if excluded_types:
            print(
                "excluded relationships:",
                dict(
                    sorted(
                        excluded_types.items()
                    )
                ),
            )

        if show_facts:
            print("\nlogical semantic neighborhood:")

            def fact_sort_key(item):
                (source_id, relationship, target_id), supports = item

                return (
                    node_name(
                        nodes_by_id[source_id]
                    ).casefold(),
                    relationship,
                    node_name(
                        nodes_by_id[target_id]
                    ).casefold(),
                )

            for (
                source_id,
                relationship,
                target_id,
            ), supports in sorted(
                logical_groups.items(),
                key=fact_sort_key,
            ):
                source_name = node_name(
                    nodes_by_id[source_id]
                )

                target_name = node_name(
                    nodes_by_id[target_id]
                )

                print(
                    f"  {source_name!r} "
                    f"--{relationship}--> "
                    f"{target_name!r}"
                )

                # Preserve which actual Entity representations supplied
                # this logical relation.
                origin_descriptions = []

                for (
                    raw_source_id,
                    raw_target_id,
                    _,
                    raw_props,
                ) in supports:
                    raw_source_id = str(
                        raw_source_id
                    )
                    raw_target_id = str(
                        raw_target_id
                    )

                    origin_descriptions.append(
                        (
                            node_name(
                                nodes_by_id[
                                    raw_source_id
                                ]
                            ),
                            node_name(
                                nodes_by_id[
                                    raw_target_id
                                ]
                            ),
                        )
                    )

                unique_origins = sorted(
                    set(origin_descriptions)
                )

                if (
                    len(supports) > 1
                    or unique_origins[0]
                    != (
                        source_name,
                        target_name,
                    )
                ):
                    print(
                        f"      raw supports: "
                        f"{len(supports)} "
                        f"{unique_origins}"
                    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--focus",
        help=(
            "Optional exact Entity name. "
            "Only inspect the identity component containing it."
        ),
    )

    parser.add_argument(
        "--show-facts",
        action="store_true",
        help="Print the canonicalized semantic neighborhood.",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            focus=args.focus,
            show_facts=args.show_facts,
        )
    )
