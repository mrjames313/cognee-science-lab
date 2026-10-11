"""
Stage 5.3.2 — Query-time Entity Resolution

Purpose
-------

Test the resolution step that occurs BEFORE semantic recall.

The key distinction is:

    canonical / variant Entity names
        -> reusable identity mappings

    historical mention Entity names
        -> occurrence-specific evidence only
        -> must NOT automatically become reusable aliases

Examples:

    "NBI"
        -> reusable variant
        -> neutral beam injection

    "H-1"
        -> reusable variant
        -> helios-1

    "the controller"
        -> NOT reusable from a historical mention
        -> must be resolved again from current query context

Once a query mention resolves to a canonical Entity, the canonical Entity can
be handed to the Stage-5.3.1 identity-aware recall mechanism.


Expected benchmark file
-----------------------

    data/hidden/stage5_query_resolution_benchmark_v0.1.yaml

Example:

    cases:
      - id: QRY01
        mention: "NBI"
        context: "How much auxiliary heating power can NBI provide?"
        expected: "neutral beam injection"
        expected_status: resolved
        mechanism: reusable_variant

      - id: QRY02
        mention: "H-1"
        context: "What is the nominal toroidal field of H-1?"
        expected: "helios-1"
        expected_status: resolved
        mechanism: reusable_variant

      - id: QRY03
        mention: "the controller"
        context: >
          During the current ramp, the controller reduced vertical motion
          and used magnetic estimates to command the coils.
        expected: "vertical control system"
        expected_status: resolved
        mechanism: contextual

      - id: QRY04
        mention: "the controller"
        context: >
          As edge density fell, the controller increased commanded gas flow.
        expected: "edge density controller"
        expected_status: resolved
        mechanism: contextual

      - id: QRY05
        mention: "the controller"
        context: "What does the controller do?"
        expected: null
        expected_status: ambiguous
        mechanism: contextual


Usage
-----

Run benchmark:

    uv run python scripts/stage5_query_resolution.py

Show more candidate rankings:

    uv run python scripts/stage5_query_resolution.py --top-k 10

Run one ad-hoc query:

    uv run python scripts/stage5_query_resolution.py \
        --mention "the controller" \
        --context "The controller increased gas flow as edge density fell."

"""

from __future__ import annotations

import argparse
import asyncio
import math
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BENCHMARK = Path(
    "data/hidden/stage5_query_resolution_benchmark_v0.1.yaml"
)

SEMANTIC_NODE_TYPES = {
    "Entity",
    "EntityType",
}

REUSABLE_ENTITY_ROLES = {
    "canonical",
    "variant",
}

# These are intentionally modest and experimental.
#
# They are NOT intended as final resolver thresholds.
# The candidate ranking is more important at this stage than the exact
# resolved/ambiguous decision boundary.
MIN_CONTEXT_SCORE = 2.0
MIN_SCORE_MARGIN = 0.75


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "did",
    "do",
    "does",
    "during",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}

# Extremely conservative normalization.
#
# This is only intended to make obvious morphological variants such as
# controller/controllers line up with graph vocabulary like control.
#
# Do not turn this into a large hand-built ontology.
NORMALIZE_TERMS = {
    "controller": "control",
    "controllers": "control",
    "controlled": "control",
    "controlling": "control",
    "controls": "control",

    "coils": "coil",

    "estimates": "estimate",
    "estimated": "estimate",
    "estimating": "estimate",

    "measurements": "measurement",

    "systems": "system",

    "profiles": "profile",

    "commands": "command",
    "commanded": "command",
    "commanding": "command",

    "reduces": "reduce",
    "reduced": "reduce",
    "reducing": "reduce",

    "increases": "increase",
    "increased": "increase",
    "increasing": "increase",
}


def normalize_surface(text: str) -> str:
    """
    Normalize a surface form for exact reusable-name matching.

    Deliberately conservative:
      - case folding
      - whitespace normalization

    We do NOT aggressively strip punctuation/hyphens because those may
    distinguish meaningful scientific names.
    """

    return " ".join(str(text).casefold().split())


def tokens(text: str) -> set[str]:
    """
    Produce a small lexical feature set for contextual ranking.
    """

    result: set[str] = set()

    for token in re.findall(r"[a-z0-9]+", str(text).casefold()):
        if token in STOPWORDS:
            continue

        token = NORMALIZE_TERMS.get(token, token)

        result.add(token)

    return result


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def node_type(props: dict[str, Any]) -> str:
    return str(props.get("type", ""))


def node_name(props: dict[str, Any]) -> str:
    return str(
        props.get("name")
        or props.get("surface_text")
        or ""
    )


def is_semantic_node(props: dict[str, Any]) -> bool:
    """
    For this experiment, Entity and EntityType are treated as the semantic
    graph.

    Source/support nodes such as:
        Mention
        IdentityResolution
        DocumentChunk
        TextDocument
        AbbreviationObservation

    are excluded.
    """

    return node_type(props) in SEMANTIC_NODE_TYPES


def build_identity_adjacency(
    edges,
    nodes_by_id: dict[str, dict[str, Any]],
):
    """
    Build the semantic Entity identity graph.

    IMPORTANT:

    The stored graph currently contains both:

        Entity --resolves_to--> Entity

    and the older Stage-5.2 helper form:

        Mention --resolves_to--> Entity

    Only Entity-to-Entity semantic resolution edges belong in semantic
    identity closure.

    The graph edge is stored directionally, but once a resolution has already
    been established, identity-aware recall may navigate it bidirectionally.
    """

    adjacency: dict[str, set[str]] = defaultdict(set)

    for source_id, target_id, relationship, props in edges:
        if relationship != "resolves_to":
            continue

        source_id = str(source_id)
        target_id = str(target_id)

        source_props = nodes_by_id.get(source_id, {})
        target_props = nodes_by_id.get(target_id, {})

        if node_type(source_props) != "Entity":
            continue

        if node_type(target_props) != "Entity":
            continue

        # Stage-5.3 semantic resolution edges were explicitly marked.
        #
        # Keep this guard so old support-layer resolution edges do not leak
        # into the semantic identity graph.
        if props.get("graph_layer") != "semantic":
            continue

        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)

    return adjacency


def identity_closure(
    seed_id: str,
    adjacency: dict[str, set[str]],
) -> set[str]:
    """
    Return the connected semantic identity component containing seed_id.
    """

    closure: set[str] = set()
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
    nodes_by_id: dict[str, dict[str, Any]],
) -> str | None:
    """
    Return the unique canonical Entity in an identity component.

    If no canonical Entity exists, or more than one exists, return None.
    """

    canonical_ids = [
        entity_id
        for entity_id in closure
        if (
            nodes_by_id.get(entity_id, {}).get("entity_role")
            == "canonical"
        )
    ]

    if len(canonical_ids) == 1:
        return canonical_ids[0]

    return None


def build_global_canonical_map(
    entity_ids: set[str],
    identity_adjacency: dict[str, set[str]],
    nodes_by_id: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """
    Build an in-memory Entity -> canonical Entity mapping.

    This is a retrieval view only.
    The graph is NOT modified.

    Identity components lacking exactly one canonical Entity are intentionally
    left uncollapsed: each representation maps to itself.
    """

    canonical_of: dict[str, str] = {}
    visited: set[str] = set()

    for entity_id in entity_ids:
        if entity_id in visited:
            continue

        closure = identity_closure(
            entity_id,
            identity_adjacency,
        )

        visited.update(closure)

        canonical_id = find_canonical(
            closure,
            nodes_by_id,
        )

        if canonical_id is None:
            for member_id in closure:
                canonical_of[member_id] = member_id
        else:
            for member_id in closure:
                canonical_of[member_id] = canonical_id

    return canonical_of


# ---------------------------------------------------------------------------
# Reusable surface-form resolution
# ---------------------------------------------------------------------------

def reusable_surface_candidates(
    surface_text: str,
    nodes_by_id: dict[str, dict[str, Any]],
    canonical_of: dict[str, str],
) -> set[str]:
    """
    Find canonical Entities that can be reached through a reusable surface
    representation.

    Only:

        canonical
        variant

    participate.

    Historical mention Entities deliberately do NOT.

    Therefore:

        NBI
            may resolve from a stored variant

        the controller
            does not become a reusable alias merely because a historical
            occurrence resolved to VCS
    """

    normalized_surface = normalize_surface(surface_text)

    candidates: set[str] = set()

    for node_id, props in nodes_by_id.items():
        if node_type(props) != "Entity":
            continue

        role = props.get("entity_role")

        if role not in REUSABLE_ENTITY_ROLES:
            continue

        name = node_name(props)

        if normalize_surface(name) != normalized_surface:
            continue

        candidates.add(
            canonical_of.get(
                node_id,
                node_id,
            )
        )

    return candidates


# ---------------------------------------------------------------------------
# Candidate profile construction
# ---------------------------------------------------------------------------

def build_candidate_profile(
    canonical_id: str,
    identity_adjacency: dict[str, set[str]],
    nodes_by_id: dict[str, dict[str, Any]],
    edges,
) -> set[str]:
    """
    Construct a lightweight lexical-semantic profile for one canonical Entity.

    Profile evidence includes:

      - canonical name
      - variant names
      - canonical/variant/mention descriptions
      - semantic relationship names
      - semantic neighbor names
      - semantic neighbor descriptions

    Historical mention SURFACE STRINGS are deliberately excluded from reusable
    vocabulary.

    However, semantic relationships attached to a resolved mention are allowed
    to contribute to the canonical Entity's profile because they represent
    actual knowledge associated with that resolved identity component.
    """

    closure = identity_closure(
        canonical_id,
        identity_adjacency,
    )

    profile: set[str] = set()

    # ------------------------------------------------------------------
    # Identity-component representations
    # ------------------------------------------------------------------

    for entity_id in closure:
        props = nodes_by_id.get(entity_id, {})

        role = props.get("entity_role")

        # Canonical + variant names are reusable vocabulary.
        #
        # Mention names are occurrence-specific and therefore intentionally
        # omitted here.
        if role != "mention":
            profile |= tokens(
                node_name(props)
            )

        # Descriptions may contain useful semantic information regardless of
        # role. For mention Entities this can include contextual information.
        profile |= tokens(
            props.get("description", "")
        )

    # ------------------------------------------------------------------
    # Semantic neighborhood
    # ------------------------------------------------------------------

    for source_id, target_id, relationship, edge_props in edges:
        source_id = str(source_id)
        target_id = str(target_id)

        if (
            source_id not in closure
            and target_id not in closure
        ):
            continue

        # Identity itself is not a contextual semantic feature.
        if relationship == "resolves_to":
            continue

        source_props = nodes_by_id.get(source_id, {})
        target_props = nodes_by_id.get(target_id, {})

        if not is_semantic_node(source_props):
            continue

        if not is_semantic_node(target_props):
            continue

        # Predicate vocabulary.
        profile |= tokens(
            relationship.replace("_", " ")
        )

        # The other endpoint provides contextual meaning.
        if source_id in closure:
            other_id = target_id
        else:
            other_id = source_id

        other_props = nodes_by_id.get(
            other_id,
            {},
        )

        profile |= tokens(
            node_name(other_props)
        )

        profile |= tokens(
            other_props.get("description", "")
        )

    return profile


def build_candidate_profiles(
    canonical_ids: set[str],
    identity_adjacency: dict[str, set[str]],
    nodes_by_id: dict[str, dict[str, Any]],
    edges,
) -> dict[str, set[str]]:
    """
    Construct profiles for all explicitly marked canonical Entities.
    """

    return {
        canonical_id: build_candidate_profile(
            canonical_id=canonical_id,
            identity_adjacency=identity_adjacency,
            nodes_by_id=nodes_by_id,
            edges=edges,
        )
        for canonical_id in canonical_ids
    }


# ---------------------------------------------------------------------------
# Contextual scoring
# ---------------------------------------------------------------------------

def score_context(
    context: str,
    profiles: dict[str, set[str]],
) -> dict[str, tuple[float, list[str]]]:
    """
    Score candidate profiles against query context.

    Uses a deliberately simple TF-IDF-like overlap score.

    Query terms that occur in only a few candidate profiles carry more weight
    than terms that occur in nearly every profile.

    This is intended as an interpretable baseline, not a production resolver.
    """

    query_tokens = tokens(context)

    candidate_count = len(profiles)

    document_frequency: Counter[str] = Counter()

    for profile in profiles.values():
        for token in profile:
            document_frequency[token] += 1

    scores: dict[str, tuple[float, list[str]]] = {}

    for candidate_id, profile in profiles.items():
        overlap = query_tokens & profile

        score = 0.0

        for token in overlap:
            df = document_frequency[token]

            # Smoothed inverse document frequency.
            idf = math.log(
                (candidate_count + 1)
                / (df + 1)
            ) + 1.0

            score += idf

        scores[candidate_id] = (
            score,
            sorted(overlap),
        )

    return scores


def rank_scores(
    scores: dict[str, tuple[float, list[str]]],
):
    """
    Rank contextual candidates from strongest to weakest.
    """

    return sorted(
        scores.items(),
        key=lambda item: (
            -item[1][0],
            item[0],
        ),
    )


def choose_candidate(
    scores: dict[str, tuple[float, list[str]]],
) -> tuple[str, str | None, dict[str, Any]]:
    """
    Conservative contextual decision rule.

    Returns:

        status
        selected canonical Entity ID or None
        diagnostic details

    Thresholds are experimental and intentionally exposed in the returned
    diagnostics.
    """

    ranked = rank_scores(scores)

    if not ranked:
        return (
            "unresolved",
            None,
            {
                "reason": "no_candidates",
            },
        )

    best_id, (best_score, best_overlap) = ranked[0]

    if len(ranked) >= 2:
        second_id, (second_score, second_overlap) = ranked[1]
    else:
        second_id = None
        second_score = 0.0
        second_overlap = []

    margin = best_score - second_score

    diagnostics = {
        "best_id": best_id,
        "best_score": best_score,
        "best_overlap": best_overlap,
        "second_id": second_id,
        "second_score": second_score,
        "second_overlap": second_overlap,
        "margin": margin,
        "min_context_score": MIN_CONTEXT_SCORE,
        "min_score_margin": MIN_SCORE_MARGIN,
    }

    if best_score < MIN_CONTEXT_SCORE:
        diagnostics["reason"] = "insufficient_context_score"

        return (
            "ambiguous",
            None,
            diagnostics,
        )

    if margin < MIN_SCORE_MARGIN:
        diagnostics["reason"] = "insufficient_margin"

        return (
            "ambiguous",
            None,
            diagnostics,
        )

    diagnostics["reason"] = "clear_contextual_winner"

    return (
        "resolved",
        best_id,
        diagnostics,
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_query_mention(
    mention: str,
    context: str,
    *,
    nodes_by_id: dict[str, dict[str, Any]],
    canonical_ids: set[str],
    canonical_of: dict[str, str],
    candidate_profiles: dict[str, set[str]],
) -> dict[str, Any]:
    """
    Resolve one query-time mention.

    Resolution sequence:

        1. reusable exact surface match over canonical + variant Entities
        2. if exactly one reusable canonical target exists:
               resolve immediately
        3. otherwise contextual candidate scoring
        4. return resolved / ambiguous / unresolved

    Historical mention surface strings never provide direct reusable matches.
    """

    reusable_candidates = reusable_surface_candidates(
        surface_text=mention,
        nodes_by_id=nodes_by_id,
        canonical_of=canonical_of,
    )

    # ------------------------------------------------------------------
    # Unique reusable mapping.
    # ------------------------------------------------------------------

    if len(reusable_candidates) == 1:
        canonical_id = next(
            iter(reusable_candidates)
        )

        return {
            "status": "resolved",
            "canonical_id": canonical_id,
            "mechanism": "reusable_variant",
            "reusable_candidates": sorted(
                reusable_candidates
            ),
            "scores": {},
            "diagnostics": {
                "reason": "unique_reusable_surface_mapping",
            },
        }

    # ------------------------------------------------------------------
    # Candidate set for contextual scoring.
    #
    # If the surface matched multiple reusable meanings, contextual ranking
    # only needs to discriminate among those meanings.
    #
    # If there was no reusable mapping at all (e.g. "the controller"), rank
    # all currently marked canonical Entities.
    # ------------------------------------------------------------------

    if reusable_candidates:
        contextual_candidate_ids = (
            reusable_candidates
        )
    else:
        contextual_candidate_ids = (
            canonical_ids
        )

    contextual_profiles = {
        candidate_id: candidate_profiles[
            candidate_id
        ]
        for candidate_id in contextual_candidate_ids
        if candidate_id in candidate_profiles
    }

    scores = score_context(
        context=context,
        profiles=contextual_profiles,
    )

    status, selected_id, diagnostics = (
        choose_candidate(scores)
    )

    return {
        "status": status,
        "canonical_id": selected_id,
        "mechanism": "contextual",
        "reusable_candidates": sorted(
            reusable_candidates
        ),
        "scores": scores,
        "diagnostics": diagnostics,
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def format_entity(
    entity_id: str | None,
    nodes_by_id: dict[str, dict[str, Any]],
) -> str:
    if entity_id is None:
        return "<none>"

    props = nodes_by_id.get(entity_id, {})

    return (
        f"{node_name(props)!r} "
        f"id={entity_id[:8]}"
    )


def print_rankings(
    scores: dict[str, tuple[float, list[str]]],
    nodes_by_id: dict[str, dict[str, Any]],
    *,
    top_k: int,
):
    if not scores:
        print("candidate ranking: <not needed>")
        return

    ranked = rank_scores(scores)

    print("candidate ranking:")

    for rank, (
        candidate_id,
        (
            score,
            overlap,
        ),
    ) in enumerate(
        ranked[:top_k],
        start=1,
    ):
        candidate_name = node_name(
            nodes_by_id[candidate_id]
        )

        print(
            f"  {rank:2d}. "
            f"{candidate_name!r:40s} "
            f"score={score:6.3f}"
        )

        print(
            f"      matched={overlap}"
        )


# ---------------------------------------------------------------------------
# Benchmark loading
# ---------------------------------------------------------------------------

def load_benchmark(
    path: Path,
) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Benchmark file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError(
            "Benchmark YAML must contain a top-level mapping."
        )

    cases = data.get("cases")

    if not isinstance(cases, list):
        raise ValueError(
            "Benchmark YAML must contain a 'cases' list."
        )

    return cases


# ---------------------------------------------------------------------------
# Benchmark evaluation
# ---------------------------------------------------------------------------

def evaluate_case(
    case: dict[str, Any],
    result: dict[str, Any],
    nodes_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    expected_status = case.get(
        "expected_status"
    )

    expected_name = case.get(
        "expected"
    )

    expected_mechanism = case.get(
        "mechanism"
    )

    actual_status = result["status"]

    canonical_id = result.get(
        "canonical_id"
    )

    if canonical_id is None:
        actual_name = None
    else:
        actual_name = node_name(
            nodes_by_id[canonical_id]
        )

    status_pass = (
        expected_status is None
        or actual_status == expected_status
    )

    if expected_name is None:
        entity_pass = canonical_id is None
    else:
        entity_pass = (
            actual_name is not None
            and normalize_surface(actual_name)
            == normalize_surface(
                expected_name
            )
        )

    mechanism_pass = (
        expected_mechanism is None
        or result["mechanism"]
        == expected_mechanism
    )

    passed = (
        status_pass
        and entity_pass
        and mechanism_pass
    )

    return {
        "pass": passed,
        "status_pass": status_pass,
        "entity_pass": entity_pass,
        "mechanism_pass": mechanism_pass,
        "actual_name": actual_name,
    }


# ---------------------------------------------------------------------------
# Main graph setup
# ---------------------------------------------------------------------------

async def load_graph_state():
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

    identity_adjacency = (
        build_identity_adjacency(
            edges,
            nodes_by_id,
        )
    )

    canonical_of = (
        build_global_canonical_map(
            entity_ids=entity_ids,
            identity_adjacency=identity_adjacency,
            nodes_by_id=nodes_by_id,
        )
    )

    canonical_ids = {
        node_id
        for node_id, props in nodes_by_id.items()
        if (
            node_type(props) == "Entity"
            and props.get("entity_role")
            == "canonical"
        )
    }

    candidate_profiles = (
        build_candidate_profiles(
            canonical_ids=canonical_ids,
            identity_adjacency=identity_adjacency,
            nodes_by_id=nodes_by_id,
            edges=edges,
        )
    )

    return {
        "nodes": nodes,
        "edges": edges,
        "nodes_by_id": nodes_by_id,
        "entity_ids": entity_ids,
        "identity_adjacency": identity_adjacency,
        "canonical_of": canonical_of,
        "canonical_ids": canonical_ids,
        "candidate_profiles": candidate_profiles,
    }


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

async def run_benchmark(
    benchmark_path: Path,
    *,
    top_k: int,
):
    graph = await load_graph_state()

    nodes = graph["nodes"]
    edges = graph["edges"]
    nodes_by_id = graph["nodes_by_id"]
    canonical_of = graph["canonical_of"]
    canonical_ids = graph["canonical_ids"]
    candidate_profiles = graph[
        "candidate_profiles"
    ]

    cases = load_benchmark(
        benchmark_path
    )

    print(
        f"Graph: {len(nodes)} nodes / "
        f"{len(edges)} edges"
    )

    print(
        f"Canonical candidates: "
        f"{len(canonical_ids)}"
    )

    print(
        f"Benchmark cases: "
        f"{len(cases)}"
    )

    passed_count = 0

    for case in cases:
        case_id = str(
            case.get("id", "<unknown>")
        )

        mention = str(
            case["mention"]
        )

        context = str(
            case.get("context", "")
        )

        print()
        print("=" * 80)
        print(case_id)

        print(
            "mention:",
            repr(mention),
        )

        print(
            "context:",
            repr(context),
        )

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

        if (
            result["mechanism"]
            == "contextual"
            and diagnostics
        ):
            best_score = diagnostics.get(
                "best_score"
            )

            second_score = diagnostics.get(
                "second_score"
            )

            margin = diagnostics.get(
                "margin"
            )

            if best_score is not None:
                print(
                    f"best score: "
                    f"{best_score:.3f}"
                )

            if second_score is not None:
                print(
                    f"second score: "
                    f"{second_score:.3f}"
                )

            if margin is not None:
                print(
                    f"margin: "
                    f"{margin:.3f}"
                )

        evaluation = evaluate_case(
            case=case,
            result=result,
            nodes_by_id=nodes_by_id,
        )

        print()

        print(
            "expected status:",
            case.get(
                "expected_status"
            ),
        )

        print(
            "expected entity:",
            repr(
                case.get("expected")
            ),
        )

        print(
            "expected mechanism:",
            case.get("mechanism"),
        )

        print()

        print(
            "RESULT:",
            "PASS"
            if evaluation["pass"]
            else "FAIL",
        )

        if not evaluation["status_pass"]:
            print(
                "  status mismatch"
            )

        if not evaluation["entity_pass"]:
            print(
                "  entity mismatch:"
                f" actual="
                f"{evaluation['actual_name']!r}"
            )

        if not evaluation[
            "mechanism_pass"
        ]:
            print(
                "  mechanism mismatch"
            )

        if evaluation["pass"]:
            passed_count += 1

    print()
    print("=" * 80)

    print(
        f"SUMMARY: "
        f"{passed_count}/{len(cases)} PASS"
    )


# ---------------------------------------------------------------------------
# Ad-hoc runner
# ---------------------------------------------------------------------------

async def run_single_query(
    mention: str,
    context: str,
    *,
    top_k: int,
):
    graph = await load_graph_state()

    nodes = graph["nodes"]
    edges = graph["edges"]
    nodes_by_id = graph["nodes_by_id"]
    canonical_of = graph["canonical_of"]
    canonical_ids = graph["canonical_ids"]
    candidate_profiles = graph[
        "candidate_profiles"
    ]

    print(
        f"Graph: {len(nodes)} nodes / "
        f"{len(edges)} edges"
    )

    print(
        f"Canonical candidates: "
        f"{len(canonical_ids)}"
    )

    print()

    print(
        "mention:",
        repr(mention),
    )

    print(
        "context:",
        repr(context),
    )

    result = resolve_query_mention(
        mention=mention,
        context=context,
        nodes_by_id=nodes_by_id,
        canonical_ids=canonical_ids,
        canonical_of=canonical_of,
        candidate_profiles=candidate_profiles,
    )

    print()

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

    if result["mechanism"] == "contextual":
        best_score = diagnostics.get(
            "best_score"
        )

        second_score = diagnostics.get(
            "second_score"
        )

        margin = diagnostics.get(
            "margin"
        )

        if best_score is not None:
            print(
                f"best score: "
                f"{best_score:.3f}"
            )

        if second_score is not None:
            print(
                f"second score: "
                f"{second_score:.3f}"
            )

        if margin is not None:
            print(
                f"margin: "
                f"{margin:.3f}"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Stage 5.3.2 query-time Entity "
            "resolution experiment."
        )
    )

    parser.add_argument(
        "--benchmark",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=(
            "Benchmark YAML path. "
            f"Default: {DEFAULT_BENCHMARK}"
        ),
    )

    parser.add_argument(
        "--mention",
        help=(
            "Run one ad-hoc mention instead "
            "of the benchmark."
        ),
    )

    parser.add_argument(
        "--context",
        help=(
            "Context for --mention. "
            "Required when --mention is used."
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help=(
            "Number of contextual candidates "
            "to print. Default: 5"
        ),
    )

    return parser.parse_args()


async def main():
    args = parse_args()

    if args.mention is not None:
        if args.context is None:
            raise SystemExit(
                "--context is required when "
                "--mention is supplied."
            )

        await run_single_query(
            mention=args.mention,
            context=args.context,
            top_k=args.top_k,
        )

        return

    await run_benchmark(
        benchmark_path=args.benchmark,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    asyncio.run(main())
