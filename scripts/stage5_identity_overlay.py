import asyncio

from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.engine.operations.setup import setup
from cognee.tasks.storage import add_data_points

from cognee_lab.models import (
    DefinitionSummary,
    IdentityResolution,
    Mention,
)


DOCUMENT_NAME_FRAGMENT = "DOC01_helios1_technical_overview_v2"


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


def find_node_exact_name(nodes, wanted_name: str):
    """
    Find exactly one graph node whose normalized name matches wanted_name.

    Returns:
        (node_id, properties)
    """

    wanted = norm(wanted_name)

    matches = [
        (str(node_id), props)
        for node_id, props in nodes
        if norm(props.get("name")) == wanted
    ]

    if len(matches) != 1:
        print(
            f"\nExpected one match for {wanted_name!r}; "
            f"found {len(matches)}"
        )

        for node_id, props in matches:
            print(
                f"  id={node_id} "
                f"name={props.get('name')!r} "
                f"type={props.get('type')!r}"
            )

        raise RuntimeError(
            f"Could not uniquely resolve graph node {wanted_name!r}"
        )

    return matches[0]


def find_document(nodes, name_fragment: str):
    """
    Find the Cognee TextDocument corresponding to DOC01.
    """

    wanted = norm(name_fragment)

    matches = [
        (str(node_id), props)
        for node_id, props in nodes
        if wanted in norm(props.get("name"))
    ]

    if len(matches) != 1:
        print(
            f"\nExpected one document matching {name_fragment!r}; "
            f"found {len(matches)}"
        )

        for node_id, props in matches:
            print(
                f"  id={node_id} "
                f"name={props.get('name')!r} "
                f"type={props.get('type')!r}"
            )

        raise RuntimeError("Could not uniquely resolve source document")

    return matches[0]


def chunk_index(props) -> int | None:
    for key in ("chunk_index", "index"):
        value = props.get(key)

        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass

    return None


def find_document_chunk(
    nodes,
    edges,
    document_id: str,
    wanted_index: int,
):
    """
    Find chunk N belonging specifically to the selected TextDocument.
    """

    nodes_by_id = {
        str(node_id): props
        for node_id, props in nodes
    }

    candidates = []

    for source_id, target_id, relationship_name, _props in edges:
        if relationship_name != "is_part_of":
            continue

        if str(target_id) != str(document_id):
            continue

        source_id = str(source_id)
        props = nodes_by_id.get(source_id)

        if props is None:
            continue

        if chunk_index(props) == wanted_index:
            candidates.append((source_id, props))

    if len(candidates) != 1:
        print(
            f"\nExpected one chunk {wanted_index} belonging to "
            f"document {document_id}; found {len(candidates)}"
        )

        for node_id, props in candidates:
            print(
                f"  id={node_id} "
                f"name={props.get('name')!r} "
                f"index={chunk_index(props)}"
            )

        raise RuntimeError(
            f"Could not uniquely resolve document chunk {wanted_index}"
        )

    return candidates[0]


def make_resolution(
    *,
    source_name: str,
    canonical,
    document_id: str,
    resolution_kind: str,
    evidence: list[str],
    source_entity=None,
):
    """
    Construct a non-destructive identity assertion.

    source_entity may be None when Cognee already consolidated the source
    form into the canonical entity and therefore never materialized a
    separate generic Entity node.

    Example:
        source_name="VCS"
        source_entity=None
        canonical=Entity("vertical control system")
    """

    canonical_id, canonical_props = canonical

    source_entity_id = None

    if source_entity is not None:
        source_entity_id = source_entity[0]

    return IdentityResolution(
        source_name=source_name,
        source_entity_id=source_entity_id,
        canonical_entity_id=canonical_id,
        canonical_name=canonical_props["name"],
        resolution_kind=resolution_kind,
        scope="document",
        scope_document_id=document_id,
        evidence=evidence,
    )


async def main():
    await setup()

    graph_engine = await get_graph_engine()
    nodes, edges = await graph_engine.get_graph_data()

    print(
        f"Existing graph: "
        f"{len(nodes)} nodes, {len(edges)} edges"
    )

    # ------------------------------------------------------------------
    # Source document and contextual-reference chunk
    # ------------------------------------------------------------------

    document_id, document_props = find_document(
        nodes,
        DOCUMENT_NAME_FRAGMENT,
    )

    chunk2_id, chunk2_props = find_document_chunk(
        nodes,
        edges,
        document_id,
        wanted_index=2,
    )

    print("\nSOURCE DOCUMENT")
    print(f"  name={document_props.get('name')!r}")
    print(f"  id={document_id}")

    print("\nCONTEXTUAL-REFERENCE CHUNK")
    print("  chunk_index=2")
    print(f"  id={chunk2_id}")

    # ------------------------------------------------------------------
    # Canonical generic entities
    # ------------------------------------------------------------------

    afrl_full = find_node_exact_name(
        nodes,
        "aurora fusion research laboratory",
    )

    vcs = find_node_exact_name(
        nodes,
        "vertical control system",
    )

    edc = find_node_exact_name(
        nodes,
        "edge density controller",
    )

    helios1 = find_node_exact_name(
        nodes,
        "helios-1",
    )

    nbi_full = find_node_exact_name(
        nodes,
        "neutral beam injection",
    )

    ech_full = find_node_exact_name(
        nodes,
        "electron cyclotron heating",
    )

    # ------------------------------------------------------------------
    # Fragmented generic entities that also exist as standalone nodes
    # ------------------------------------------------------------------

    afrl = find_node_exact_name(
        nodes,
        "afrl",
    )

    nbi = find_node_exact_name(
        nodes,
        "nbi",
    )

    nbi_system = find_node_exact_name(
        nodes,
        "neutral beam injection system",
    )

    ech = find_node_exact_name(
        nodes,
        "ech",
    )

    ech_system = find_node_exact_name(
        nodes,
        "electron cyclotron heating system",
    )

    # ------------------------------------------------------------------
    # Identity-resolution overlay
    #
    # This includes BOTH:
    #
    #   1. repairs for fragmented generic entities; and
    #   2. identity knowledge that Cognee already resolved correctly.
    #
    # This makes IdentityResolution useful for later retrieval, encoding,
    # and document-context construction rather than merely serving as a
    # repair log.
    # ------------------------------------------------------------------

    resolutions = [

        # --------------------------------------------------------------
        # AFRL
        # --------------------------------------------------------------

        make_resolution(
            source_name="AFRL",
            source_entity=afrl,
            canonical=afrl_full,
            document_id=document_id,
            resolution_kind="abbreviation",
            evidence=[
                "explicit_abbreviation",
                "typed_observation",
                "document_context",
            ],
        ),

        # --------------------------------------------------------------
        # VCS
        #
        # Cognee already consolidated VCS into the full-name generic
        # entity, so there is no separate Entity("vcs").
        # --------------------------------------------------------------

        make_resolution(
            source_name="VCS",
            source_entity=None,
            canonical=vcs,
            document_id=document_id,
            resolution_kind="abbreviation",
            evidence=[
                "explicit_abbreviation",
                "typed_observation",
                "generic_graph_consolidation",
                "document_context",
            ],
        ),

        # --------------------------------------------------------------
        # EDC
        #
        # Like VCS, no separate generic Entity("edc") survived because
        # Cognee successfully consolidated it.
        # --------------------------------------------------------------

        make_resolution(
            source_name="EDC",
            source_entity=None,
            canonical=edc,
            document_id=document_id,
            resolution_kind="abbreviation",
            evidence=[
                "explicit_abbreviation",
                "typed_observation",
                "generic_graph_consolidation",
                "document_context",
            ],
        ),

        # --------------------------------------------------------------
        # H-1 / Helios 1 / Helios-1
        #
        # These forms are useful document vocabulary even though Cognee
        # already converged on the generic Entity("helios-1").
        # --------------------------------------------------------------

        make_resolution(
            source_name="H-1",
            source_entity=None,
            canonical=helios1,
            document_id=document_id,
            resolution_kind="alias",
            evidence=[
                "explicit_alias",
                "typed_observation",
                "generic_graph_consolidation",
                "document_context",
            ],
        ),

        make_resolution(
            source_name="Helios 1",
            source_entity=None,
            canonical=helios1,
            document_id=document_id,
            resolution_kind="alias",
            evidence=[
                "lexical_normalization",
                "typed_observation",
                "generic_graph_consolidation",
                "document_context",
            ],
        ),

        # --------------------------------------------------------------
        # NBI
        # --------------------------------------------------------------

        make_resolution(
            source_name="NBI",
            source_entity=nbi,
            canonical=nbi_full,
            document_id=document_id,
            resolution_kind="abbreviation",
            evidence=[
                "explicit_abbreviation",
                "typed_observation",
                "document_context",
            ],
        ),

        make_resolution(
            source_name="neutral beam injection system",
            source_entity=nbi_system,
            canonical=nbi_full,
            document_id=document_id,
            resolution_kind="semantic_variant",
            evidence=[
                "lexical_semantic_variant",
                "compatible_type",
                "shared_relations",
                "document_context",
            ],
        ),

        # --------------------------------------------------------------
        # ECH
        # --------------------------------------------------------------

        make_resolution(
            source_name="ECH",
            source_entity=ech,
            canonical=ech_full,
            document_id=document_id,
            resolution_kind="abbreviation",
            evidence=[
                "explicit_abbreviation",
                "typed_observation",
                "document_context",
            ],
        ),

        make_resolution(
            source_name="electron cyclotron heating system",
            source_entity=ech_system,
            canonical=ech_full,
            document_id=document_id,
            resolution_kind="semantic_variant",
            evidence=[
                "lexical_semantic_variant",
                "compatible_type",
                "shared_relations",
                "document_context",
            ],
        ),
    ]

    # ------------------------------------------------------------------
    # Mention overlay
    #
    # occurrence_index is zero-based among exact occurrences of the same
    # surface text within chunk 2.
    #
    # REF01:
    #   observable evidence shows that "the controller" resolved to VCS.
    #
    # REF02:
    #   benchmark ground truth says EDC, but the semantic event itself did
    #   not survive extraction. Therefore the persisted pipeline evidence
    #   does not tell us whether reference resolution succeeded.
    # ------------------------------------------------------------------

    mentions = [
        Mention(
            source_chunk_id=chunk2_id,
            source_chunk_index=2,
            surface_text="the controller",
            occurrence_index=0,
            resolution_status="resolved",
            canonical_entity_id=vcs[0],
            canonical_name=vcs[1]["name"],
            resolution_basis=[
                "source_context",
                "semantic_edge",
                "edge_text",
                "chunk_provenance",
                "generic_graph_consolidation",
            ],
        ),

        Mention(
            source_chunk_id=chunk2_id,
            source_chunk_index=2,
            surface_text="the controller",
            occurrence_index=1,
            resolution_status="indeterminate",
            canonical_entity_id=None,
            canonical_name=None,
            resolution_basis=[
                "source_context",
                "specific_assertion_not_materialized",
            ],
        ),
    ]

    # ------------------------------------------------------------------
    # DefinitionSummary
    #
    # This intentionally preserves useful vocabulary variants rather than
    # containing only canonical names.
    #
    # It is a document-level semantic/contextual materialized view, not
    # the canonical source of identity truth.
    # ------------------------------------------------------------------

    definition_summary = DefinitionSummary(
        source_document_id=document_id,
        definitions_text="""
AFRL — Aurora Fusion Research Laboratory.

VCS — Vertical Control System; controls vertical plasma position.

EDC — Edge Density Controller; adjusts commanded gas flow using density feedback.

NBI — neutral beam injection; also appears as "neutral beam injection system"; auxiliary heating system.

ECH — electron cyclotron heating; also appears as "electron cyclotron heating system"; auxiliary heating system.

H-1 and Helios 1 — aliases for Helios-1.
""".strip(),
    )

    # ------------------------------------------------------------------
    # Print overlay before persistence
    # ------------------------------------------------------------------

    print("\nIDENTITY RESOLUTIONS")

    for item in resolutions:
        source_entity_text = (
            item.source_entity_id
            if item.source_entity_id is not None
            else "<no separate generic entity>"
        )

        print(
            f"\n  {item.source_name!r}"
            f"  --{item.resolution_kind}-->"
            f"  {item.canonical_name!r}"
        )

        print(
            f"      source_entity_id="
            f"{source_entity_text}"
        )

        print(
            f"      canonical_entity_id="
            f"{item.canonical_entity_id}"
        )

        print(
            f"      evidence="
            f"{item.evidence}"
        )

    print("\nMENTIONS")

    for item in mentions:
        print(
            f"\n  chunk={item.source_chunk_index} "
            f"occurrence={item.occurrence_index} "
            f"{item.surface_text!r}"
        )

        print(
            f"      status="
            f"{item.resolution_status!r}"
        )

        print(
            f"      canonical="
            f"{item.canonical_name!r}"
        )

        print(
            f"      basis="
            f"{item.resolution_basis}"
        )

    print("\nDEFINITION SUMMARY")
    print(definition_summary.definitions_text)

    # ------------------------------------------------------------------
    # Persist
    #
    # Identity fields make rerunning this script deterministic rather than
    # creating a new semantic overlay every time.
    # ------------------------------------------------------------------

    overlay = [
        *resolutions,
        *mentions,
        definition_summary,
    ]

    await add_data_points(overlay)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    print("\nPERSISTED OVERLAY")
    print(
        f"  IdentityResolution: "
        f"{len(resolutions)}"
    )
    print(
        f"  Mention:            "
        f"{len(mentions)}"
    )
    print(
        "  DefinitionSummary:  1"
    )

    print("\nDATAPOINT IDS")

    for item in overlay:
        print(
            f"  {type(item).__name__:20s} "
            f"{item.id}"
        )

    print("\nIN-MEMORY PYDANTIC SERIALIZATION")

    for item in overlay:
        print(f"\n{type(item).__name__} {item.id}")
        pprint(
            item.model_dump(mode="json"),
            sort_dicts=True,
        )

if __name__ == "__main__":
    asyncio.run(main())
