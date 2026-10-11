"""
Stage 5.3.3 — End-to-End Query Resolution + Semantic Recall

This experiment composes the two mechanisms already validated:

    Stage 5.3.2
        query mention + context
            -> canonical Entity

    Stage 5.3.1
        canonical Entity
            -> identity closure
            -> union semantic neighborhoods
            -> canonicalized logical facts

Important rule:

    Resolution happens BEFORE semantic recall.

An ambiguous query mention does not trigger recall over all historical
mentions with the same surface form.

Examples:

    "the controller" + vertical-motion context
        -> Vertical Control System
        -> VCS semantic neighborhood

    "the controller" + density/gas-flow context
        -> Edge Density Controller
        -> EDC semantic neighborhood

    "the controller" + no useful context
        -> ambiguous
        -> STOP; no semantic recall

Usage:

    uv run python scripts/stage5_end_to_end_recall.py \
        --mention "the controller" \
        --context "During the current ramp, the controller reduced vertical motion and commanded the coils."

    uv run python scripts/stage5_end_to_end_recall.py \
        --mention "the controller" \
        --context "As edge density fell, the controller increased commanded gas flow."

    uv run python scripts/stage5_end_to_end_recall.py \
        --mention "the controller" \
        --context "What does the controller do?"

    uv run python scripts/stage5_end_to_end_recall.py \
        --mention "NBI" \
        --context "How much auxiliary heating power can NBI provide?"
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from typing import Any

from stage5_query_resolution import (
    format_entity,
    identity_closure,
    load_graph_state,
    node_name,
    node_type,
    print_rankings,
    resolve_query_mention,
)


# ---------------------------------------------------------------------------
# Semantic recall helpers
# ---------------------------------------------------------------------------

SEMANTIC_NODE_TYPES = {
    "Entity",
    "EntityType",
}


def is_semantic_node(
    props: dict[str, Any],
) -> bool:
    return node_type(props) in SEMANTIC_NODE_TYPES


def semantic_incident_edges(
    closure: set[str],
    edges,
    nodes_by_id: dict[str, dict[str, Any]],
):
    """
    Return domain-semantic edges touching members of an identity closure.

    Excludes:

        resolves_to

    because resolves_to defines identity rather than a domain fact.

    Also excludes edges involving support/source nodes such as:

        IdentityResolution
        Mention helper
        AbbreviationObservation
        DocumentChunk
        TextDocument

    Existing Cognee Entity <-> EntityType semantic edges are retained.
    """

    semantic = []
    excluded = []

    for (
        source_id,
        target_id,
        relationship,
        props,
    ) in edges:

        source_id = str(source_id)
        target_id = str(target_id)

        if (
            source_id not in closure
            and target_id not in closure
        ):
            continue

        if relationship == "resolves_to":
            continue

        source_props = nodes_by_id.get(
            source_id,
            {},
        )

        target_props = nodes_by_id.get(
            target_id,
            {},
        )

        if (
            is_semantic_node(source_props)
            and is_semantic_node(target_props)
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
    canonical_of: dict[str, str],
):
    """
    Construct the logical semantic form of one raw graph edge.

    Only Entity endpoints participating in a known identity component are
    changed.

    The stored graph itself is NOT modified.
    """

    (
        source_id,
        target_id,
        relationship,
        props,
    ) = edge

    source_id = str(source_id)
    target_id = str(target_id)

    logical_source_id = canonical_of.get(
        source_id,
        source_id,
    )

    logical_target_id = canonical_of.get(
        target_id,
        target_id,
    )

    return (
        logical_source_id,
        relationship,
        logical_target_id,
    )


def logical_semantic_neighborhood(
    canonical_id: str,
    *,
    identity_adjacency,
    canonical_of,
    nodes_by_id,
    edges,
):
    """
    Compute the canonicalized semantic neighborhood for a resolved Entity.

    Returns both:

      logical_groups
          logical semantic fact -> list of raw graph-edge supports

      metadata
          closure and excluded-edge diagnostics
    """

    closure = identity_closure(
        canonical_id,
        identity_adjacency,
    )

    semantic_edges, excluded_edges = (
        semantic_incident_edges(
            closure=closure,
            edges=edges,
            nodes_by_id=nodes_by_id,
        )
    )

    logical_groups = defaultdict(list)

    for edge in semantic_edges:
        logical_key = canonicalize_edge(
            edge,
            canonical_of,
        )

        logical_groups[
            logical_key
        ].append(edge)

    return (
        logical_groups,
        {
            "closure": closure,
            "semantic_edges": semantic_edges,
            "excluded_edges": excluded_edges,
        },
    )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_identity_component(
    closure: set[str],
    *,
    nodes_by_id: dict[str, dict[str, Any]],
):
    print("identity representations:")

    def sort_key(entity_id: str):
        props = nodes_by_id[entity_id]

        role = str(
            props.get("entity_role")
            or ""
        )

        return (
            role,
            node_name(props).casefold(),
            entity_id,
        )

    for entity_id in sorted(
        closure,
        key=sort_key,
    ):
        props = nodes_by_id[
            entity_id
        ]

        role = (
            props.get("entity_role")
            or "<unset>"
        )

        extras = []

        if role == "mention":
            occurrence_index = props.get(
                "occurrence_index"
            )

            if occurrence_index is not None:
                extras.append(
                    f"occurrence="
                    f"{occurrence_index}"
                )

            chunk_id = (
                props.get("source_chunk_id")
                or props.get("scope_chunk_id")
            )

            if chunk_id:
                extras.append(
                    f"chunk="
                    f"{str(chunk_id)[:8]}"
                )

        extra_text = ""

        if extras:
            extra_text = (
                " ["
                + ", ".join(extras)
                + "]"
            )

        print(
            f"  {role:10s} "
            f"{node_name(props)!r} "
            f"id={entity_id[:8]}"
            f"{extra_text}"
        )


def print_logical_facts(
    logical_groups,
    *,
    nodes_by_id,
    show_supports: bool,
):
    print("logical semantic neighborhood:")

    def sort_key(item):
        (
            source_id,
            relationship,
            target_id,
        ), supports = item

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
        key=sort_key,
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

        if not show_supports:
            continue

        raw_supports = []

        for (
            raw_source_id,
            raw_target_id,
            raw_relationship,
            raw_props,
        ) in supports:
            raw_source_id = str(
                raw_source_id
            )

            raw_target_id = str(
                raw_target_id
            )

            raw_supports.append(
                (
                    node_name(
                        nodes_by_id[
                            raw_source_id
                        ]
                    ),
                    raw_relationship,
                    node_name(
                        nodes_by_id[
                            raw_target_id
                        ]
                    ),
                )
            )

        # Only show support detail where it adds information:
        #
        #   - multiple raw assertions collapsed into one logical fact
        #   - raw endpoints differ from canonicalized endpoints
        #
        logical_tuple = (
            source_name,
            relationship,
            target_name,
        )

        unique_raw_supports = sorted(
            set(raw_supports)
        )

        needs_detail = (
            len(unique_raw_supports) > 1
            or (
                len(unique_raw_supports) == 1
                and unique_raw_supports[0]
                != logical_tuple
            )
        )

        if needs_detail:
            print(
                "      raw supports:"
            )

            for raw_support in (
                unique_raw_supports
            ):
                print(
                    "        "
                    f"{raw_support[0]!r} "
                    f"--{raw_support[1]}--> "
                    f"{raw_support[2]!r}"
                )


# ---------------------------------------------------------------------------
# End-to-end recall
# ---------------------------------------------------------------------------

async def run(
    *,
    mention: str,
    context: str,
    top_k: int,
    show_supports: bool,
):
    graph = await load_graph_state()

    nodes = graph["nodes"]
    edges = graph["edges"]

    nodes_by_id = graph[
        "nodes_by_id"
    ]

    identity_adjacency = graph[
        "identity_adjacency"
    ]

    canonical_of = graph[
        "canonical_of"
    ]

    canonical_ids = graph[
        "canonical_ids"
    ]

    candidate_profiles = graph[
        "candidate_profiles"
    ]

    print(
        f"Graph: {len(nodes)} nodes / "
        f"{len(edges)} edges"
    )

    print()

    print(
        "query mention:",
        repr(mention),
    )

    print(
        "query context:",
        repr(context),
    )

    # ------------------------------------------------------------------
    # STEP 1 — Resolve query-time mention
    # ------------------------------------------------------------------

    result = resolve_query_mention(
        mention=mention,
        context=context,
        nodes_by_id=nodes_by_id,
        canonical_ids=canonical_ids,
        canonical_of=canonical_of,
        candidate_profiles=(
            candidate_profiles
        ),
    )

    print()
    print("=" * 80)
    print("RESOLUTION")

    print(
        "mechanism:",
        result["mechanism"],
    )

    reusable_names = [
        node_name(
            nodes_by_id[candidate_id]
        )
        for candidate_id in result[
            "reusable_candidates"
        ]
    ]

    print(
        "reusable candidates:",
        reusable_names,
    )

    if result["scores"]:
        print()

        print_rankings(
            result["scores"],
            nodes_by_id,
            top_k=top_k,
        )

    print()

    print(
        "status:",
        result["status"],
    )

    print(
        "resolved:",
        format_entity(
            result["canonical_id"],
            nodes_by_id,
        ),
    )

    diagnostics = result.get(
        "diagnostics",
        {},
    )

    print(
        "decision reason:",
        diagnostics.get(
            "reason"
        ),
    )

    # ------------------------------------------------------------------
    # IMPORTANT:
    #
    # No semantic recall happens until resolution succeeds.
    # ------------------------------------------------------------------

    if result["status"] != "resolved":
        print()
        print("=" * 80)
        print("RECALL")

        print(
            "SKIPPED: query mention was "
            "not resolved to a canonical Entity."
        )

        return

    canonical_id = result[
        "canonical_id"
    ]

    assert canonical_id is not None

    # ------------------------------------------------------------------
    # STEP 2 — Identity-aware semantic recall
    # ------------------------------------------------------------------

    (
        logical_groups,
        recall_metadata,
    ) = logical_semantic_neighborhood(
        canonical_id=canonical_id,
        identity_adjacency=(
            identity_adjacency
        ),
        canonical_of=canonical_of,
        nodes_by_id=nodes_by_id,
        edges=edges,
    )

    closure = recall_metadata[
        "closure"
    ]

    semantic_edges = recall_metadata[
        "semantic_edges"
    ]

    excluded_edges = recall_metadata[
        "excluded_edges"
    ]

    print()
    print("=" * 80)
    print("RECALL")

    print()

    print_identity_component(
        closure,
        nodes_by_id=nodes_by_id,
    )

    print()

    print(
        "raw semantic incident edges:",
        len(semantic_edges),
    )

    print(
        "logical semantic facts:",
        len(logical_groups),
    )

    print(
        "excluded source/support edges:",
        len(excluded_edges),
    )

    if excluded_edges:
        excluded_relationships = Counter(
            relationship
            for (
                source_id,
                target_id,
                relationship,
                props,
            ) in excluded_edges
        )

        print(
            "excluded relationships:",
            dict(
                sorted(
                    excluded_relationships.items()
                )
            ),
        )

    print()

    print_logical_facts(
        logical_groups,
        nodes_by_id=nodes_by_id,
        show_supports=show_supports,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Stage 5.3.3 end-to-end "
            "query resolution and semantic recall."
        )
    )

    parser.add_argument(
        "--mention",
        required=True,
        help=(
            "Surface form being resolved, "
            'for example "NBI" or '
            '"the controller".'
        ),
    )

    parser.add_argument(
        "--context",
        required=True,
        help=(
            "Current query/conversation context "
            "used for disambiguation."
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help=(
            "Number of contextual resolution "
            "candidates to display. Default: 5"
        ),
    )

    parser.add_argument(
        "--show-supports",
        action="store_true",
        help=(
            "Show underlying raw semantic edges "
            "when canonicalization changes or "
            "deduplicates a logical fact."
        ),
    )

    return parser.parse_args()


async def main():
    args = parse_args()

    await run(
        mention=args.mention,
        context=args.context,
        top_k=args.top_k,
        show_supports=args.show_supports,
    )


if __name__ == "__main__":
    asyncio.run(main())
