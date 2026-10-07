import asyncio
import cognee
import re
import yaml

from collections import defaultdict
from sqlalchemy import text as sql_text

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.databases.relational import (get_relational_engine,)
from cognee.modules.engine.operations.setup import setup


BENCHMARK = "data/hidden/stage5_identity_benchmark_v0.1.yaml"


def norm(text: str | None) -> str:
    if not text:
        return ""

    text = text.casefold()
    text = text.replace("-", " ")
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def matches_form(name: str, forms: list[str]) -> bool:
    n = norm(name)
    return any(n == norm(form) for form in forms)


def report_identity_case(
    case,
    entities,
    observations,
    entity_chunks,
    incident_edges,
    nodes_by_id,
):
    forms = case["forms"]

    matched = [
        (node_id, props)
        for node_id, props in entities
        if matches_form(props.get("name", ""), forms)
    ]

    print(f"\n[{case['id']}] ENTITY IDENTITY")
    print(f"expected canonical: {case['canonical_name']!r}")

    print("\ngeneric Entity representations:")

    if not matched:
        print("  NONE")

    for node_id, props in matched:
        print(
            f"  {props.get('name')!r}"
            f"  id={node_id}"
            f"  chunks={sorted(entity_chunks[node_id])}"
        )

        print("    incident relations:")

        for source_id, target_id, rel, edge_props in incident_edges[node_id]:
            other_id = (
                target_id
                if source_id == node_id
                else source_id
            )

            other = nodes_by_id.get(other_id, {})

            print(
                f"      {rel}"
                f"  <-> {other.get('name')!r}"
            )

    print("\ntyped observations:")

    found_obs = False

    for node_id, props in observations:
        short_form = props.get("short_form", "")
        full_form = props.get("full_form", "")

        if (
            matches_form(short_form, forms)
            or matches_form(full_form, forms)
        ):
            found_obs = True

            print(
                f"  chunk={props.get('source_chunk_index')}"
                f"  {short_form!r} -> {full_form!r}"
            )

    if not found_obs:
        print("  NONE")

    distinct_names = {
        norm(props.get("name"))
        for _, props in matched
    }

    if len(distinct_names) > 1:
        state = "FRAGMENTED"
    elif len(distinct_names) == 1:
        state = "SINGLE GENERIC REPRESENTATION"
    else:
        state = "NO MATCHING GENERIC ENTITY"

    print(f"\ncurrent state: {state}")


def report_reference_case(
    case,
    chunks,
    entities,
    entity_chunks,
    incident_edges,
    nodes_by_id,
    evidence_rows,
):
    phrase = norm(case["source"]["contains"])

    source_chunks = [
        (node_id, props)
        for node_id, props in chunks
        if phrase in norm(props.get("text", ""))
    ]

    print(f"\n[{case['id']}] CONTEXTUAL REFERENCE")
    print(f"surface: {case['source']['surface']!r}")
    print(
        "expected referent:",
        case["expected_referent"]["canonical_name"],
    )

    print("\nsource chunks:")

    for chunk_id, props in source_chunks:
        print(
            f"  chunk={props.get('chunk_index')}"
            f" id={chunk_id}"
        )

    forms = case["expected_referent"]["acceptable_forms"]

    candidate_entities = [
        (node_id, props)
        for node_id, props in entities
        if matches_form(props.get("name", ""), forms)
    ]

    print("\ncandidate referent entities:")

    for node_id, props in candidate_entities:
        print(
            f"  {props.get('name')!r}"
            f" chunks={sorted(entity_chunks[node_id])}"
        )

        print("    candidate semantic edges:")

        for source_id, target_id, rel, edge_props in incident_edges[node_id]:
            other_id = (
                target_id
                if source_id == node_id
                else source_id
            )

            other = nodes_by_id.get(other_id, {})
            other_name = other.get("name", "")

            haystack = norm(
                f"{rel} {other_name} "
                f"{edge_props.get('edge_text', '')}"
            )

            keywords = case.get(
                "diagnostic_keywords", []
            )

            hits = [
                keyword
                for keyword in keywords
                if norm(keyword) in haystack
            ]

            if hits:
                print(
                    f"      {rel}"
                    f" <-> {other_name!r}"
                    f"  keyword_hits={hits}"
                )


def report_distinct_case(
    case,
    entities,
    entity_chunks,
):
    forms_a = case["forms_a"]
    forms_b = case["forms_b"]

    matched_a = [
        (node_id, props)
        for node_id, props in entities
        if matches_form(props.get("name", ""), forms_a)
    ]

    matched_b = [
        (node_id, props)
        for node_id, props in entities
        if matches_form(props.get("name", ""), forms_b)
    ]

    print(f"\n[{case['id']}] DISTINCT ENTITIES")
    print(f"expected: {case['expected']}")
    print(f"reason: {case.get('reason', '')}")

    print("\nside A:")

    if not matched_a:
        print("  NONE")

    for node_id, props in matched_a:
        print(
            f"  {props.get('name')!r}"
            f"  id={node_id}"
            f"  chunks={sorted(entity_chunks[node_id])}"
        )

    print("\nside B:")

    if not matched_b:
        print("  NONE")

    for node_id, props in matched_b:
        print(
            f"  {props.get('name')!r}"
            f"  id={node_id}"
            f"  chunks={sorted(entity_chunks[node_id])}"
        )

    ids_a = {
        node_id
        for node_id, _ in matched_a
    }

    ids_b = {
        node_id
        for node_id, _ in matched_b
    }

    overlap = ids_a & ids_b

    print("\ncurrent state:")

    if overlap:
        print(
            "  COLLAPSED / AMBIGUOUS:"
            " at least one generic Entity matches both sides"
        )

        for node_id in overlap:
            print(f"    shared node id={node_id}")

    elif matched_a and matched_b:
        print(
            "  DISTINCT:"
            " separate generic Entity representations exist"
        )

    elif not matched_a and not matched_b:
        print(
            "  INCONCLUSIVE:"
            " neither expected entity was found"
        )

    else:
        print(
            "  INCONCLUSIVE:"
            " only one side was found in the generic graph"
        )

def row_value(row, key):
    """Support dict-like rows and sqlite Row objects."""
    try:
        return row[key]
    except (KeyError, TypeError):
        return getattr(row, key, None)

def norm_id(value):
    if value is None:
        return None
    return str(value).replace("-", "")

def report_edge_provenance(
    relationship_name,
    nodes_by_id,
    edges,
    evidence_rows,
):
    print(
        f"\nPROVENANCE FOR RELATIONSHIP "
        f"{relationship_name!r}"
    )

    matching_edges = [
        (source_id, target_id, rel, props)
        for source_id, target_id, rel, props in edges
        if rel == relationship_name
    ]

    if not matching_edges:
        print("  no graph edges found")
        return

    for source_id, target_id, rel, props in matching_edges:
        source = nodes_by_id.get(source_id, {})
        target = nodes_by_id.get(target_id, {})

        edge_id = props.get("edge_object_id")

        print(
            f"\n  {source.get('name')!r}"
            f" --{rel}-->"
            f" {target.get('name')!r}"
        )
        print(f"    edge_id: {edge_id}")
        print(
            f"    edge_text: "
            f"{props.get('edge_text')!r}"
        )

        matching_evidence = [
            row
            for row in evidence_rows
            if (
                norm_id(row_value(row, "edge_id")) == norm_id(edge_id)
                or (
                    norm_id(row_value(
                        row,
                        "relationship_name",
                    )) == relationship_name
                    and norm_id(row_value(
                        row,
                        "source_node_id",
                    )) == source_id
                    and norm_id(row_value(
                        row,
                        "destination_node_id",
                    )) == target_id
                )
            )
        ]

        if not matching_evidence:
            print("    provenance: NONE")
            continue

        print("    provenance:")

        for row in matching_evidence:
            print(
                "      "
                f"chunk_index="
                f"{row_value(row, 'chunk_index')} "
                f"chunk_id="
                f"{row_value(row, 'chunk_id')} "
                f"source_task="
                f"{row_value(row, 'source_task')!r} "
                f"evidence_kind="
                f"{row_value(row, 'evidence_kind')!r}"
            )
            
def dump_evidence_for_relationship(
    relationship_name,
    evidence_rows,
):
    print(
        f"\nRAW EVIDENCE FOR "
        f"{relationship_name!r}"
    )

    found = False

    for row in evidence_rows:
        if row_value(
            row,
            "relationship_name",
        ) != relationship_name:
            continue

        found = True
        print()
        print(
            f"  chunk_index: "
            f"{row_value(row, 'chunk_index')}"
        )
        print(
            f"  chunk_id: "
            f"{row_value(row, 'chunk_id')}"
        )
        print(
            f"  edge_id: "
            f"{row_value(row, 'edge_id')}"
        )
        print(
            f"  source_node_id: "
            f"{row_value(row, 'source_node_id')}"
        )
        print(
            f"  destination_node_id: "
            f"{row_value(row, 'destination_node_id')}"
        )
        print(
            f"  source_task: "
            f"{row_value(row, 'source_task')}"
        )
        print(
            f"  evidence_kind: "
            f"{row_value(row, 'evidence_kind')}"
        )

    if not found:
        print("  NONE")

        
async def main():
    await setup()

    graph_engine = await get_graph_engine()

    nodes, edges = await graph_engine.get_graph_data()

    relational_engine = get_relational_engine()

    async with relational_engine.get_async_session() as session:
        result = await session.execute(
            sql_text("SELECT * FROM provenance_edge_evidence")
        )
        evidence_rows = result.mappings().all()

        
    with open(BENCHMARK) as f:
        benchmark = yaml.safe_load(f)

    nodes_by_id = {
        node_id: props
        for node_id, props in nodes
    }

    entities = [
        (node_id, props)
        for node_id, props in nodes
        if props.get("type") == "Entity"
    ]

    chunks = [
        (node_id, props)
        for node_id, props in nodes
        if props.get("type") == "DocumentChunk"
    ]

    observations = [
        (node_id, props)
        for node_id, props in nodes
        if props.get("type") == "AbbreviationObservation"
    ]

    incident_edges = defaultdict(list)

    for source_id, target_id, rel, props in edges:
        incident_edges[source_id].append(
            (source_id, target_id, rel, props)
        )
        incident_edges[target_id].append(
            (source_id, target_id, rel, props)
        )

    entity_chunks = defaultdict(set)

    for source_id, target_id, rel, props in edges:
        if rel != "contains":
            continue

        source = nodes_by_id.get(source_id, {})
        target = nodes_by_id.get(target_id, {})

        if (
            source.get("type") == "DocumentChunk"
            and target.get("type") == "Entity"
        ):
            entity_chunks[target_id].add(
                source.get("chunk_index")
            )

    for case in benchmark["cases"]:
        if case["type"] == "entity_identity":
            report_identity_case(
                case,
                entities,
                observations,
                entity_chunks,
                incident_edges,
                nodes_by_id,
            )

        elif case["type"] == "contextual_reference":
            report_reference_case(
                case,
                chunks,
                entities,
                entity_chunks,
                incident_edges,
                nodes_by_id,
                evidence_rows,
            )

        elif case["type"] == "distinct_entities":
            report_distinct_case(
                case,
                entities,
                entity_chunks,
            )

    # Targetted eval of VCS
    report_edge_provenance(
        "has_vcs_update_rate",
        nodes_by_id,
        edges,
        evidence_rows,
    )

    report_edge_provenance(
        "has_configuration_dependent_update_rate",
        nodes_by_id,
        edges,
        evidence_rows,
    )

    dump_evidence_for_relationship(
        "has_vcs_update_rate",
        evidence_rows,
    )

    dump_evidence_for_relationship(
        "has_configuration_dependent_update_rate",
        evidence_rows,
    )

    # Targetted eval of vertical motion
    report_edge_provenance(
        "reduces_vertical_motion_in",
        nodes_by_id,
        edges,
        evidence_rows,
    )

    # Targetted eval for EDC gas flow
    print("\n Examine edges for EDC gas flow")
    for source_id, target_id, rel, props in edges:
        text = norm(
            f"{rel} "
            f"{props.get('edge_text', '')}"
        )

        if (
                "gas flow" in text
                and "density" in text
        ):
            source = nodes_by_id.get(source_id, {})
            target = nodes_by_id.get(target_id, {})

            print(
                f"{source.get('name')!r}"
                f" --{rel}-->"
                f" {target.get('name')!r}"
            )
            print(
                f"  edge_text="
                f"{props.get('edge_text')!r}"
            )
    
if __name__ == "__main__":
    asyncio.run(main())
