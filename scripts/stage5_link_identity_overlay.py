import asyncio

from dotenv import load_dotenv

load_dotenv()

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup


OVERLAY_TYPES = {
    "IdentityResolution",
    "Mention",
    "DefinitionSummary",
}


def node_type(props: dict) -> str:
    return str(props.get("type", ""))


def require_node(
    nodes_by_id: dict,
    node_id: str,
    *,
    expected_type: str | None = None,
):
    """
    Verify that a referenced node actually exists.

    This is intentionally strict: a dangling overlay reference should stop
    the experiment rather than silently create an incomplete identity graph.
    """

    node_id = str(node_id)

    props = nodes_by_id.get(node_id)

    if props is None:
        raise RuntimeError(
            f"Referenced node does not exist: {node_id}"
        )

    if (
        expected_type is not None
        and node_type(props) != expected_type
    ):
        raise RuntimeError(
            f"Expected node {node_id} to have type "
            f"{expected_type!r}, found {node_type(props)!r}"
        )

    return props


def add_candidate_edge(
    candidates: list,
    *,
    source_id: str,
    target_id: str,
    relationship_name: str,
    edge_text: str,
):
    candidates.append(
        (
            str(source_id),
            str(target_id),
            relationship_name,
            {
                "edge_text": edge_text,
            },
        )
    )


async def main():
    await setup()

    graph_engine = await get_graph_engine()

    nodes, existing_edges = await graph_engine.get_graph_data()

    nodes_by_id = {
        str(node_id): props
        for node_id, props in nodes
    }

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

    print(
        f"Existing graph: "
        f"{len(nodes)} nodes, "
        f"{len(existing_edges)} edges"
    )

    # ------------------------------------------------------------------
    # Locate overlay nodes
    # ------------------------------------------------------------------

    identity_resolutions = [
        (str(node_id), props)
        for node_id, props in nodes
        if node_type(props) == "IdentityResolution"
    ]

    mentions = [
        (str(node_id), props)
        for node_id, props in nodes
        if node_type(props) == "Mention"
    ]

    definition_summaries = [
        (str(node_id), props)
        for node_id, props in nodes
        if node_type(props) == "DefinitionSummary"
    ]

    print("\nOVERLAY INVENTORY")
    print(
        f"  IdentityResolution: "
        f"{len(identity_resolutions)}"
    )
    print(
        f"  Mention:            "
        f"{len(mentions)}"
    )
    print(
        f"  DefinitionSummary:  "
        f"{len(definition_summaries)}"
    )

    # ------------------------------------------------------------------
    # Build desired graph relationships
    #
    # The scalar UUID fields remain in the DataPoints. These edges provide
    # graph-native traversal paths in addition to those denormalized IDs.
    # ------------------------------------------------------------------

    candidates = []

    # ================================================================
    # IdentityResolution
    # ================================================================

    for resolution_id, props in identity_resolutions:
        source_name = props["source_name"]
        canonical_name = props["canonical_name"]

        canonical_entity_id = str(
            props["canonical_entity_id"]
        )

        document_id = str(
            props["scope_document_id"]
        )

        source_entity_id = props.get(
            "source_entity_id"
        )

        # Validate references before creating anything.
        require_node(
            nodes_by_id,
            canonical_entity_id,
            expected_type="Entity",
        )

        require_node(
            nodes_by_id,
            document_id,
            expected_type="TextDocument",
        )

        # --------------------------------------------------------------
        # IdentityResolution --canonicalizes_to--> Entity
        # --------------------------------------------------------------

        add_candidate_edge(
            candidates,
            source_id=resolution_id,
            target_id=canonical_entity_id,
            relationship_name="canonicalizes_to",
            edge_text=(
                f"{source_name} resolves to canonical entity "
                f"{canonical_name}."
            ),
        )

        # --------------------------------------------------------------
        # IdentityResolution --source_representation--> Entity
        #
        # Only present when Cognee actually created a fragmented source
        # Entity node.
        #
        # For VCS, EDC, H-1, etc. this edge is deliberately absent because
        # the source form was never materialized as a distinct Entity.
        # --------------------------------------------------------------

        if source_entity_id is not None:
            source_entity_id = str(
                source_entity_id
            )

            source_entity_props = require_node(
                nodes_by_id,
                source_entity_id,
                expected_type="Entity",
            )

            add_candidate_edge(
                candidates,
                source_id=resolution_id,
                target_id=source_entity_id,
                relationship_name="source_representation",
                edge_text=(
                    f"Identity resolution for {source_name} "
                    f"references extracted entity "
                    f"{source_entity_props.get('name')!r}."
                ),
            )

        # --------------------------------------------------------------
        # IdentityResolution --scoped_to--> TextDocument
        # --------------------------------------------------------------

        add_candidate_edge(
            candidates,
            source_id=resolution_id,
            target_id=document_id,
            relationship_name="scoped_to",
            edge_text=(
                f"Identity resolution {source_name} -> "
                f"{canonical_name} is scoped to this document."
            ),
        )

    # ================================================================
    # Mention
    # ================================================================

    for mention_id, props in mentions:
        surface_text = props["surface_text"]

        source_chunk_id = str(
            props["source_chunk_id"]
        )

        status = props["resolution_status"]

        canonical_entity_id = props.get(
            "canonical_entity_id"
        )

        canonical_name = props.get(
            "canonical_name"
        )

        chunk_props = require_node(
            nodes_by_id,
            source_chunk_id,
            expected_type="DocumentChunk",
        )

        # --------------------------------------------------------------
        # Mention --observed_in--> DocumentChunk
        # --------------------------------------------------------------

        add_candidate_edge(
            candidates,
            source_id=mention_id,
            target_id=source_chunk_id,
            relationship_name="observed_in",
            edge_text=(
                f"Mention {surface_text!r} observed in "
                f"document chunk "
                f"{props.get('source_chunk_index')}."
            ),
        )

        # --------------------------------------------------------------
        # Mention --resolves_to--> Entity
        #
        # Only materialize this edge when the persisted overlay says the
        # reference is resolved.
        #
        # REF02 therefore remains connected only to its source chunk.
        # --------------------------------------------------------------

        if (
            status == "resolved"
            and canonical_entity_id is not None
        ):
            canonical_entity_id = str(
                canonical_entity_id
            )

            require_node(
                nodes_by_id,
                canonical_entity_id,
                expected_type="Entity",
            )

            add_candidate_edge(
                candidates,
                source_id=mention_id,
                target_id=canonical_entity_id,
                relationship_name="resolves_to",
                edge_text=(
                    f"Mention {surface_text!r} resolves to "
                    f"{canonical_name}."
                ),
            )

    # ================================================================
    # DefinitionSummary
    # ================================================================

    for summary_id, props in definition_summaries:
        document_id = str(
            props["source_document_id"]
        )

        require_node(
            nodes_by_id,
            document_id,
            expected_type="TextDocument",
        )

        add_candidate_edge(
            candidates,
            source_id=summary_id,
            target_id=document_id,
            relationship_name=(
                "summarizes_definitions_for"
            ),
            edge_text=(
                "Definition summary provides document-scoped "
                "semantic vocabulary and identity context."
            ),
        )

    # ------------------------------------------------------------------
    # Make this script safely rerunnable.
    #
    # Do not depend on backend duplicate-edge behavior. Explicitly compare
    # against the graph we loaded above.
    # ------------------------------------------------------------------

    new_edges = []

    print("\nPROPOSED RELATIONSHIPS")

    for edge in candidates:
        (
            source_id,
            target_id,
            relationship_name,
            properties,
        ) = edge

        key = (
            source_id,
            target_id,
            relationship_name,
        )

        source_props = nodes_by_id[source_id]
        target_props = nodes_by_id[target_id]

        source_label = (
            source_props.get("source_name")
            or source_props.get("surface_text")
            or source_props.get("name")
            or source_id
        )

        target_label = (
            target_props.get("name")
            or target_props.get("canonical_name")
            or target_id
        )

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
            f"{node_type(source_props)}"
            f"({source_label!r}) "
            f"--{relationship_name}--> "
            f"{node_type(target_props)}"
            f"({target_label!r})"
        )

        if not already_exists:
            new_edges.append(edge)

    # ------------------------------------------------------------------
    # Persist only missing relationships.
    # ------------------------------------------------------------------

    if new_edges:
        await graph_engine.add_edges(
            new_edges
        )

    print("\nRESULT")
    print(
        f"  Candidate relationships: "
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

    # ------------------------------------------------------------------
    # Expected counts for the current graph:
    #
    # IdentityResolution:
    #   9 canonicalizes_to
    #   5 source_representation
    #   9 scoped_to
    #
    # Mention:
    #   2 observed_in
    #   1 resolves_to
    #
    # DefinitionSummary:
    #   1 summarizes_definitions_for
    #
    # Total expected new edges = 27
    # ------------------------------------------------------------------

    print(
        "\nFor the current DOC01 overlay, "
        "the expected total is 27 relationships."
    )


if __name__ == "__main__":
    asyncio.run(main())
