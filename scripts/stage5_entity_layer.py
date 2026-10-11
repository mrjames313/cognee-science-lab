import argparse
import asyncio
from uuid import UUID, NAMESPACE_OID, uuid5

from dotenv import load_dotenv

load_dotenv()

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup
from cognee.tasks.storage import add_data_points

from cognee_lab.models import Entity


def node_type(props: dict) -> str:
    return str(props.get("type", ""))


def mention_entity_id(props: dict) -> UUID:
    """
    A Mention is an Entity, but its identity is one specific source occurrence.

    We therefore explicitly override Cognee Entity's normal name-based identity.
    """

    key = (
        f"EntityMention:"
        f"{props['source_chunk_id']}:"
        f"{props['surface_text']}:"
        f"{props['occurrence_index']}"
    )

    return uuid5(NAMESPACE_OID, key)


def build_existing_entity(
    node_id: str,
    props: dict,
    *,
    role: str,
) -> Entity:
    """
    Rehydrate an existing Cognee Entity while preserving its persisted
    DataPoint properties.

    Explicit id prevents any accidental identity recomputation.
    """

    kwargs = {}

    for field_name in Entity.model_fields:
        if field_name == "type":
            continue

        if field_name in props:
            kwargs[field_name] = props[field_name]

    kwargs["id"] = UUID(str(node_id))
    kwargs["name"] = str(props["name"])
    kwargs["description"] = str(
        props.get("description") or ""
    )

    kwargs["entity_role"] = role
    kwargs["graph_layer"] = "semantic"

    return Entity(**kwargs)


async def main(apply: bool):
    await setup()

    graph_engine = await get_graph_engine()

    nodes, existing_edges = (
        await graph_engine.get_graph_data()
    )

    nodes_by_id = {
        str(node_id): props
        for node_id, props in nodes
    }

    resolutions = [
        (str(node_id), props)
        for node_id, props in nodes
        if node_type(props) == "IdentityResolution"
    ]

    mention_helpers = [
        (str(node_id), props)
        for node_id, props in nodes
        if node_type(props) == "Mention"
    ]

    if not resolutions:
        raise RuntimeError(
            "No IdentityResolution nodes found."
        )

    document_ids = {
        str(props["scope_document_id"])
        for _, props in resolutions
    }

    if len(document_ids) != 1:
        raise RuntimeError(
            "Stage 5.3.0 currently expects exactly one "
            f"identity document; found {document_ids}"
        )

    document_id = next(iter(document_ids))

    # Make sure our experimental Entity keeps Cognee's Entity ID namespace.
    # This is critical: a future generic extraction of "VCS" should merge
    # with the variant Entity created here rather than create another node.
    from cognee.modules.engine.models.Entity import (
        Entity as CogneeEntity,
    )

    for test_name in [
        "NBI",
        "VCS",
        "H-1",
        "neutral beam injection",
    ]:
        assert (
            Entity.id_for(test_name)
            == CogneeEntity.id_for(test_name)
        )

    # --------------------------------------------------------------
    # Determine the semantic Entity nodes required by the identity
    # benchmark.
    # --------------------------------------------------------------

    semantic_entities: dict[str, Entity] = {}

    # IdentityResolution id -> source semantic Entity id.
    resolution_source_ids: dict[str, str] = {}

    # First mark every canonical target.
    for resolution_id, props in resolutions:
        canonical_id = str(
            props["canonical_entity_id"]
        )

        canonical_props = nodes_by_id.get(
            canonical_id
        )

        if canonical_props is None:
            raise RuntimeError(
                f"Canonical Entity missing: {canonical_id}"
            )

        if node_type(canonical_props) != "Entity":
            raise RuntimeError(
                f"Canonical target {canonical_id} "
                f"is {node_type(canonical_props)!r}, "
                "expected Entity."
            )

        semantic_entities[canonical_id] = (
            build_existing_entity(
                canonical_id,
                canonical_props,
                role="canonical",
            )
        )

    # Then mark or materialize all variants.
    for resolution_id, props in resolutions:
        source_name = str(
            props["source_name"]
        )

        source_entity_id = props.get(
            "source_entity_id"
        )

        if source_entity_id is not None:
            source_id = str(
                source_entity_id
            )

            source_props = nodes_by_id.get(
                source_id
            )

            if source_props is None:
                raise RuntimeError(
                    "IdentityResolution references "
                    f"missing source Entity {source_id}"
                )

            semantic_entities[source_id] = (
                build_existing_entity(
                    source_id,
                    source_props,
                    role="variant",
                )
            )

        else:
            # No distinct generic Entity was produced by Cognee.
            #
            # Materialize one now using ordinary Entity name identity.
            # Future generic extraction of the same name should therefore
            # address the same node.
            source_entity = Entity(
                name=source_name,
                description=(
                    "Identity variant materialized during "
                    "Stage 5.3 semantic-layer experiment."
                ),
                entity_role="variant",
                graph_layer="semantic",
            )

            source_id = str(
                source_entity.id
            )

            # A node with that deterministic Entity id may already exist
            # from a previous run.
            existing = nodes_by_id.get(
                source_id
            )

            if existing is not None:
                if node_type(existing) != "Entity":
                    raise RuntimeError(
                        f"Expected {source_id} to be Entity, "
                        f"found {node_type(existing)!r}"
                    )

                source_entity = (
                    build_existing_entity(
                        source_id,
                        existing,
                        role="variant",
                    )
                )

            semantic_entities[source_id] = (
                source_entity
            )

        resolution_source_ids[
            resolution_id
        ] = source_id

    # --------------------------------------------------------------
    # Materialize occurrence-scoped mentions as Entity nodes.
    #
    # The existing Stage-5.2 Mention DataPoints remain untouched as
    # support/provenance objects.
    # --------------------------------------------------------------

    mention_entity_ids: dict[str, str] = {}

    for helper_id, props in mention_helpers:
        entity_id = mention_entity_id(
            props
        )

        entity = Entity(
            id=entity_id,
            name=str(
                props["surface_text"]
            ),
            description=(
                "Source-scoped entity mention materialized "
                "during Stage 5.3."
            ),
            entity_role="mention",
            graph_layer="semantic",
            scope_kind="occurrence",
            scope_document_id=document_id,
            scope_chunk_id=str(
                props["source_chunk_id"]
            ),
            scope_chunk_index=int(
                props["source_chunk_index"]
            ),
            occurrence_index=int(
                props["occurrence_index"]
            ),
            start_char=props.get(
                "start_char"
            ),
            end_char=props.get(
                "end_char"
            ),
        )

        semantic_entities[
            str(entity_id)
        ] = entity

        mention_entity_ids[
            helper_id
        ] = str(entity_id)

    # --------------------------------------------------------------
    # Show planned node-role assignments.
    # --------------------------------------------------------------

    print(
        f"Existing graph: "
        f"{len(nodes)} nodes, "
        f"{len(existing_edges)} edges"
    )

    print(
        "\nSEMANTIC ENTITY ROLE ASSIGNMENTS"
    )

    for entity_id, entity in sorted(
        semantic_entities.items(),
        key=lambda item: (
            item[1].entity_role or "",
            item[1].name.casefold(),
        ),
    ):
        existed = (
            entity_id in nodes_by_id
        )

        marker = (
            "UPDATE"
            if existed
            else "CREATE"
        )

        scope = ""

        if entity.scope_kind:
            scope = (
                f" scope={entity.scope_kind}"
            )

        print(
            f"  [{marker:6s}] "
            f"{entity.entity_role:9s} "
            f"{entity.name!r}"
            f"{scope}"
        )

    # --------------------------------------------------------------
    # Construct direct semantic resolves_to edges.
    #
    # The IdentityResolution node remains the support/provenance
    # justification.  Its id is carried on the semantic edge so an
    # explanation-mode traversal can get back to it.
    # --------------------------------------------------------------

    edge_candidates = []

    for resolution_id, props in resolutions:
        source_id = (
            resolution_source_ids[
                resolution_id
            ]
        )

        canonical_id = str(
            props["canonical_entity_id"]
        )

        edge_candidates.append(
            (
                source_id,
                canonical_id,
                "resolves_to",
                {
                    "graph_layer": "semantic",
                    "edge_text": (
                        f"{props['source_name']} resolves to "
                        f"{props['canonical_name']}."
                    ),
                    "resolution_kind": props[
                        "resolution_kind"
                    ],
                    "identity_resolution_id": (
                        resolution_id
                    ),
                    "resolution_scope": props[
                        "scope"
                    ],
                    "resolution_scope_id": str(
                        props[
                            "scope_document_id"
                        ]
                    ),
                },
            )
        )

    # Resolved mention -> canonical Entity.
    for helper_id, props in mention_helpers:
        mention_id = (
            mention_entity_ids[
                helper_id
            ]
        )

        if (
            props.get(
                "resolution_status"
            )
            == "resolved"
            and props.get(
                "canonical_entity_id"
            )
            is not None
        ):
            canonical_id = str(
                props[
                    "canonical_entity_id"
                ]
            )

            edge_candidates.append(
                (
                    mention_id,
                    canonical_id,
                    "resolves_to",
                    {
                        "graph_layer": (
                            "semantic"
                        ),
                        "edge_text": (
                            f"Mention "
                            f"{props['surface_text']!r} "
                            f"resolves to "
                            f"{props['canonical_name']}."
                        ),
                        "mention_support_id": (
                            helper_id
                        ),
                        "resolution_scope": (
                            "occurrence"
                        ),
                        "resolution_scope_id": (
                            mention_id
                        ),
                    },
                )
            )

    # Keep a thin cross-layer connection from the existing Stage-5.2
    # Mention helper to its semantic Entity representation.
    for helper_id, entity_id in (
        mention_entity_ids.items()
    ):
        edge_candidates.append(
            (
                helper_id,
                entity_id,
                "materializes_as",
                {
                    "graph_layer": "support",
                    "edge_text": (
                        "Mention support record "
                        "materializes as an occurrence-scoped "
                        "semantic Entity."
                    ),
                },
            )
        )

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
            _,
        ) in existing_edges
    }

    new_edges = [
        edge
        for edge in edge_candidates
        if (
            edge[0],
            edge[1],
            edge[2],
        )
        not in existing_edge_keys
    ]

    print(
        "\nPLANNED NEW EDGES"
    )

    for (
        source_id,
        target_id,
        relationship,
        props,
    ) in new_edges:
        source = (
            semantic_entities.get(
                source_id
            )
        )

        source_name = (
            source.name
            if source is not None
            else nodes_by_id[
                source_id
            ].get("surface_text", "")
        )

        target = (
            semantic_entities.get(
                target_id
            )
        )

        target_name = (
            target.name
            if target is not None
            else nodes_by_id.get(
                target_id, {}
            ).get("name", "")
        )

        print(
            f"  {source_name!r} "
            f"--{relationship}--> "
            f"{target_name!r}"
        )

    print(
        "\nEXPECTED CURRENT-DOC01 DELTA"
    )
    print(
        "  new Entity nodes:       6"
    )
    print(
        "    4 variants"
    )
    print(
        "    2 mentions"
    )
    print(
        "  semantic resolves_to:  10"
    )
    print(
        "  support materializes_as: 2"
    )

    if not apply:
        print(
            "\nDRY RUN ONLY. "
            "Re-run with --apply to persist."
        )
        return

    # --------------------------------------------------------------
    # Persist nodes through Cognee's DataPoint path.
    # --------------------------------------------------------------

    await add_data_points(
        list(
            semantic_entities.values()
        )
    )

    # --------------------------------------------------------------
    # Persist only missing direct graph edges.
    # --------------------------------------------------------------

    if new_edges:
        await graph_engine.add_edges(
            new_edges
        )

    final_nodes, final_edges = (
        await graph_engine.get_graph_data()
    )

    print(
        "\nFINAL GRAPH"
    )
    print(
        f"  nodes: {len(final_nodes)}"
    )
    print(
        f"  edges: {len(final_edges)}"
    )

    print(
        "\nExpected from the current "
        "154-node / 365-edge baseline:"
    )
    print(
        "  160 nodes / 377 edges"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist Stage 5.3 semantic "
            "Entity roles and resolves_to edges."
        ),
    )

    args = parser.parse_args()

    asyncio.run(
        main(apply=args.apply)
    )
