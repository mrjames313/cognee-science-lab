# scripts/stage5_link_identity_evidence.py

import asyncio

from dotenv import load_dotenv

load_dotenv()

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup


def node_type(props: dict) -> str:
    return str(props.get("type", ""))


def norm(value: str | None) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .casefold()
        .replace("-", " ")
        .replace("_", " ")
    )


async def main():
    await setup()

    graph_engine = await get_graph_engine()
    nodes, existing_edges = await graph_engine.get_graph_data()

    nodes_by_id = {
        str(node_id): props
        for node_id, props in nodes
    }

    print(
        f"Existing graph: "
        f"{len(nodes)} nodes, {len(existing_edges)} edges"
    )

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    observations = [
        (str(node_id), props)
        for node_id, props in nodes
        if node_type(props) == "AbbreviationObservation"
    ]

    resolutions = [
        (str(node_id), props)
        for node_id, props in nodes
        if node_type(props) == "IdentityResolution"
    ]

    print("\nINVENTORY")
    print(
        f"  AbbreviationObservation: "
        f"{len(observations)}"
    )
    print(
        f"  IdentityResolution:      "
        f"{len(resolutions)}"
    )

    # ------------------------------------------------------------------
    # Index the document-scoped identity resolutions by source form.
    #
    # There should be exactly one resolution for each source form within
    # the current document.
    # ------------------------------------------------------------------

    resolution_by_source = {}

    for resolution_id, props in resolutions:
        source_name = norm(
            props.get("source_name")
        )

        if not source_name:
            continue

        if source_name in resolution_by_source:
            raise RuntimeError(
                "Multiple IdentityResolution nodes found for "
                f"source_name={props.get('source_name')!r}"
            )

        resolution_by_source[source_name] = (
            resolution_id,
            props,
        )

    # ------------------------------------------------------------------
    # Determine which AbbreviationObservation nodes directly support an
    # IdentityResolution.
    #
    # Rule for Stage 5.2:
    #
    #   * short_form must correspond to an IdentityResolution source_name
    #   * full_form must be non-empty
    #   * the observation must actually describe the same target identity
    #
    # We deliberately do NOT connect unresolved observations such as:
    #
    #       VCS -> ""
    #
    # Nor do we use observations to support semantic-variant resolutions
    # such as:
    #
    #       neutral beam injection system
    #           -> neutral beam injection
    #
    # because the abbreviation observation is not the evidence for that
    # particular reconciliation.
    # ------------------------------------------------------------------

    candidates = []

    for observation_id, obs in observations:
        short_form = obs.get("short_form")
        full_form = obs.get("full_form")

        # Empty full_form means the extractor observed the surface form
        # but did not resolve it locally.
        if not full_form:
            continue

        resolution_entry = resolution_by_source.get(
            norm(short_form)
        )

        if resolution_entry is None:
            continue

        resolution_id, resolution = resolution_entry

        canonical_name = resolution.get(
            "canonical_name"
        )

        resolution_kind = resolution.get(
            "resolution_kind"
        )

        # --------------------------------------------------------------
        # Validate that the resolved observation is genuinely compatible
        # with this resolution.
        #
        # Abbreviations:
        #   compare extracted full form against canonical form with simple
        #   normalization. This handles capitalization/hyphen variation.
        #
        # H-1:
        #   its observation says H-1 -> Helios 1, while the canonical graph
        #   entity is helios-1. This is the alias case we established in
        #   Stage 5.1, so simple normalization is sufficient here too.
        # --------------------------------------------------------------

        if norm(full_form) != norm(canonical_name):
            print(
                "\nSKIP: resolved observation does not directly "
                "match canonical target"
            )
            print(
                f"  observation: "
                f"{short_form!r} -> {full_form!r}"
            )
            print(
                f"  resolution:  "
                f"{resolution.get('source_name')!r} "
                f"-> {canonical_name!r}"
            )
            print(
                f"  kind:        "
                f"{resolution_kind!r}"
            )
            continue

        edge_text = (
            f"Abbreviation observation "
            f"{short_form} -> {full_form} "
            f"supports identity resolution "
            f"{resolution.get('source_name')} -> "
            f"{canonical_name}."
        )

        candidates.append(
            (
                observation_id,
                resolution_id,
                "supports",
                {
                    "edge_text": edge_text,
                },
            )
        )

    # ------------------------------------------------------------------
    # Deduplicate against existing graph.
    # ------------------------------------------------------------------

    existing_edge_keys = {
        (
            str(source_id),
            str(target_id),
            relationship_name,
        )
        for (
            source_id,
            target_id,
            relationship_name,
            _props,
        ) in existing_edges
    }

    new_edges = []

    print("\nPROPOSED SUPPORT EDGES")

    for (
        source_id,
        target_id,
        relationship_name,
        properties,
    ) in candidates:

        key = (
            source_id,
            target_id,
            relationship_name,
        )

        obs = nodes_by_id[source_id]
        resolution = nodes_by_id[target_id]

        already_exists = (
            key in existing_edge_keys
        )

        marker = (
            "EXISTS"
            if already_exists
            else "ADD"
        )

        print(
            f"  [{marker:6s}] "
            f"{obs.get('short_form')!r} -> "
            f"{obs.get('full_form')!r} "
            f"(chunk {obs.get('source_chunk_index')}) "
            f"--supports--> "
            f"{resolution.get('source_name')!r} -> "
            f"{resolution.get('canonical_name')!r}"
        )

        if not already_exists:
            new_edges.append(
                (
                    source_id,
                    target_id,
                    relationship_name,
                    properties,
                )
            )

    # ------------------------------------------------------------------
    # Persist
    # ------------------------------------------------------------------

    if new_edges:
        await graph_engine.add_edges(
            new_edges
        )

    print("\nRESULT")
    print(
        f"  Candidate support edges: "
        f"{len(candidates)}"
    )
    print(
        f"  Already present:         "
        f"{len(candidates) - len(new_edges)}"
    )
    print(
        f"  Added:                   "
        f"{len(new_edges)}"
    )

    print(
        "\nExpected for the current DOC01 graph: "
        "10 support edges."
    )


if __name__ == "__main__":
    asyncio.run(main())
