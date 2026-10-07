import asyncio
from pprint import pprint

from dotenv import load_dotenv

load_dotenv()

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup


OVERLAY_TYPES = {
    "IdentityResolution",
    "Mention",
    "DefinitionSummary",
    "AbbreviationObservation",
}


def node_type(props: dict) -> str:
    """
    Cognee graph nodes normally expose their DataPoint class through `type`.
    Keep this isolated in case a backend represents it differently.
    """
    return str(props.get("type", ""))


async def main():
    await setup()

    graph_engine = await get_graph_engine()
    nodes, edges = await graph_engine.get_graph_data()

    nodes_by_id = {
        str(node_id): props
        for node_id, props in nodes
    }

    print(
        f"Graph contains {len(nodes)} nodes "
        f"and {len(edges)} edges."
    )

    # ---------------------------------------------------------------
    # 1. Inventory relevant node types
    # ---------------------------------------------------------------

    print("\nOVERLAY NODE INVENTORY")

    counts = {}

    for node_id, props in nodes:
        t = node_type(props)

        if t in OVERLAY_TYPES:
            counts[t] = counts.get(t, 0) + 1

    for t in sorted(OVERLAY_TYPES):
        print(f"  {t:24s} {counts.get(t, 0)}")

    # ---------------------------------------------------------------
    # 2. Dump exact persisted representation
    # ---------------------------------------------------------------

    for wanted_type in [
        "IdentityResolution",
        "Mention",
        "DefinitionSummary",
        "AbbreviationObservation",
    ]:
        print(
            "\n"
            + "=" * 80
            + f"\n{wanted_type}\n"
            + "=" * 80
        )

        matches = [
            (str(node_id), props)
            for node_id, props in nodes
            if node_type(props) == wanted_type
        ]

        for node_id, props in matches:
            print(f"\nNODE {node_id}")
            pprint(props, sort_dicts=True)

    # ---------------------------------------------------------------
    # 3. Explicitly inspect nullable IdentityResolution serialization
    # ---------------------------------------------------------------

    print(
        "\n"
        + "=" * 80
        + "\nIDENTITY RESOLUTION SERIALIZATION\n"
        + "=" * 80
    )

    for node_id, props in nodes:
        if node_type(props) != "IdentityResolution":
            continue

        print(
            f"\n{props.get('source_name')!r}"
            f" -> {props.get('canonical_name')!r}"
        )

        print(
            "  source_entity_id:",
            repr(props.get("source_entity_id")),
        )

        print(
            "  source_entity_id key present:",
            "source_entity_id" in props,
        )

        print(
            "  canonical_entity_id:",
            repr(props.get("canonical_entity_id")),
        )

        print(
            "  resolution_kind:",
            repr(props.get("resolution_kind")),
        )

        print(
            "  evidence:",
            repr(props.get("evidence")),
        )

    # ---------------------------------------------------------------
    # 4. Show every incident edge for overlay nodes.
    #
    # At this stage IdentityResolution, Mention and DefinitionSummary
    # are expected to be isolated. AbbreviationObservation should still
    # have its Stage 4 observed_in relationships.
    # ---------------------------------------------------------------

    overlay_ids = {
        str(node_id)
        for node_id, props in nodes
        if node_type(props) in OVERLAY_TYPES
    }

    print(
        "\n"
        + "=" * 80
        + "\nOVERLAY INCIDENT EDGES\n"
        + "=" * 80
    )

    found_edge = False

    for source_id, target_id, relationship_name, props in edges:
        source_id = str(source_id)
        target_id = str(target_id)

        if (
            source_id not in overlay_ids
            and target_id not in overlay_ids
        ):
            continue

        found_edge = True

        source_props = nodes_by_id.get(source_id, {})
        target_props = nodes_by_id.get(target_id, {})

        print(
            f"\n"
            f"{node_type(source_props)}"
            f"({source_props.get('name')!r})"
            f"\n    --{relationship_name}-->"
            f"\n{node_type(target_props)}"
            f"({target_props.get('name')!r})"
        )

        print("  edge properties:")
        pprint(props, sort_dicts=True)

    if not found_edge:
        print("  <none>")

    # ---------------------------------------------------------------
    # 5. Look for properties potentially relevant to schema grouping.
    #
    # Rather than assuming which property the graph viewer uses,
    # show all keys present for each overlay type.
    # ---------------------------------------------------------------

    print(
        "\n"
        + "=" * 80
        + "\nPROPERTY KEYS BY NODE TYPE\n"
        + "=" * 80
    )

    for wanted_type in sorted(OVERLAY_TYPES):
        keys = set()

        for _node_id, props in nodes:
            if node_type(props) == wanted_type:
                keys.update(props.keys())

        print(f"\n{wanted_type}:")
        for key in sorted(keys):
            print(f"  {key}")


if __name__ == "__main__":
    asyncio.run(main())
