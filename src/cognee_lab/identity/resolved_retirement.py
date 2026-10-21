"""Captured retirement of the primary mention, resolution and local fact."""

import json
from uuid import UUID

from .captured_chunks import FACT_TEXT, bind_chunks
from .models import IdentitySource
from .validation import IntentError, text_digest

AFTER = "Helios controller (HC) regulates plasma heating.\n"
RETENTION = {"g01": [], "g02": [0]}


def describe_retirement(old, before, chunks):
    from .occurrence_fixture import BEFORE

    if (
        old.revision != 1
        or before != BEFORE
        or set(old.mention_groups) != set(RETENTION)
    ):
        raise IntentError(
            "fixture_scope",
            "Resolved retirement requires doc01 of a fresh chunked-fixture",
        )
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(AFTER)
    payload["producers"]["retirement_review"] = dict(
        method="captured_fixture",
        implementation="stage6-captured-resolved-retirement",
        version="0.1",
        configuration={"policy": "explicit-group-and-local-fact-retirement-v1"},
        run_id=None,
    )
    mid = payload["mention_groups"].pop("g01")["entity_id"]
    payload["entity_constructions"].pop(mid)
    payload["mention_resolutions"] = {
        k: r
        for k, r in payload["mention_resolutions"].items()
        if r["group_ref"] != "g01"
    }
    for record in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["producer_ref"] = "retirement_review"
    bind_chunks(payload, AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def retirement_checks(publisher, source, mid):
    """Check a retired mention and its fact are gone and the shared objects remain."""
    from .fixture import OSCILLATIONS_ID
    from .native import edge_metadata
    from cognee.modules.engine.utils import generate_edge_object_id, generate_node_id
    from cognee.modules.graph.models.EdgeType import EdgeType
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records
    from .models import ChunkInput

    target = source.variant_assignments["v01"].target_entity_id
    fact_id = UUID(generate_edge_object_id(str(mid), str(OSCILLATIONS_ID), "limits"))
    evidence = await get_edge_evidence_records(
        [fact_id], source.dataset_id, per_edge_limit=100, total_limit=100
    )

    async def indexed(collection, key):
        return await publisher.vector.has_collection(collection) and bool(
            await publisher.vector.retrieve(collection, [str(key)])
        )

    fact_triplet = generate_node_id(str(mid) + "limits" + str(OSCILLATIONS_ID))
    resolution_triplet = generate_node_id(str(mid) + "resolves_to" + str(target))
    return dict(
        mention_entity_id=str(mid),
        fact_edge_id=str(fact_id),
        mention_entity_present=await publisher.graph.get_node(str(mid)) is not None,
        mention_entity_indexed=await indexed("Entity_name", mid),
        resolution_edge_present=await edge_metadata(
            publisher.graph, mid, target, "resolves_to"
        )
        is not None,
        fact_edge_present=await edge_metadata(
            publisher.graph, mid, OSCILLATIONS_ID, "limits"
        )
        is not None,
        fact_evidence_count=len(evidence),
        fact_triplet_indexed=await indexed("Triplet_text", fact_triplet),
        resolution_triplet_indexed=await indexed("Triplet_text", resolution_triplet),
        current_marker_present=any(
            [
                await publisher.graph.has_edge(
                    str(i.chunk_id), str(mid), "has_identity_mention"
                )
                for i in source.inputs.values()
                if isinstance(i, ChunkInput)
            ]
        ),
        shared_fact_endpoint_present=await publisher.graph.get_node(
            str(OSCILLATIONS_ID)
        )
        is not None,
        shared_fact_endpoint_indexed=await indexed("Entity_name", OSCILLATIONS_ID),
        shared_relationship_text_indexed=await indexed(
            "EdgeType_relationship_name", EdgeType.id_for(FACT_TEXT)
        ),
    )


async def verify_retirement(publisher, source, mid):
    checks = await retirement_checks(publisher, source, mid)
    absent = [
        "mention_entity_present",
        "mention_entity_indexed",
        "resolution_edge_present",
        "fact_edge_present",
        "fact_evidence_count",
        "fact_triplet_indexed",
        "resolution_triplet_indexed",
        "current_marker_present",
    ]
    retained = [
        "shared_fact_endpoint_present",
        "shared_fact_endpoint_indexed",
        "shared_relationship_text_indexed",
    ]
    if any(checks[k] for k in absent) or not all(checks[k] for k in retained):
        raise IntentError(
            "verify_retirement",
            "Resolved-group cleanup or independent shared index retention failed",
        )
