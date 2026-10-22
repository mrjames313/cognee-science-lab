"""Captured changed interpretation on doc01: a text edit changes what g01 refers to.

A changed meaning in a text edit is a fresh group, never a continuing group
with a new decision. g01 retires, a fresh g03 holds the new mention and the
carried-over `it`, and the fact is generated again from g03. The reviewer
wrote both texts and both maps; the process infers nothing.
"""

import json
from uuid import UUID

from .captured_chunks import (
    FACT_TEXT,
    REINTERPRET_ENTITY,
    REINTERPRET_UNRESOLVED,
    bind_chunks,
)
from .captured_revision import (
    begin_revision,
    declare_group,
    occurrence,
    require_fresh_doc01,
    retire_group,
    stamp_producer,
)
from .models import Accepted, IdentitySource, Unresolved
from .validation import fresh_entity_id

NEW_ENTITY_AFTER = (
    "Helios controller (HC) regulates plasma heating, the backup controller adjusts "
    "coil current, and it limits oscillations.\n"
)
UNRESOLVED_AFTER = (
    "Helios controller (HC) regulates plasma heating. A controller adjusts "
    "coil current, and it limits oscillations.\n"
)
# g01's `the controller` is removed and g01's `it` moves to g03, which also
# gains the new mention as an addition. g02 continues in place.
REINTERPRETATION_MAP = {"g01": [None, ["g03", 1]], "g02": [["g02", 0]]}
SCOPE = "Changed interpretation requires doc01 of a fresh chunked-fixture"
POLICY = "explicit-changed-interpretation-v1"
REF = "interpretation_review"


def describe_new_entity(old, before, chunks):
    """g03 resolves to a new reusable Backup controller, derived from r03."""
    require_fresh_doc01(old, before, set(REINTERPRETATION_MAP), SCOPE)
    payload = begin_revision(old, NEW_ENTITY_AFTER, REF, REINTERPRET_ENTITY, POLICY)
    backup = fresh_entity_id(old.identity_data_id, payload["revision"], "r03")
    payload["entity_constructions"][str(backup)] = dict(
        name="Backup controller",
        description="Captured reusable backup controller identity.",
    )
    retire_group(payload, "g01")
    declare_group(
        payload,
        old,
        "g03",
        "r03",
        "the backup controller; it",
        "Captured replacement local reference group g03.",
        [
            occurrence(NEW_ENTITY_AFTER, "the backup controller"),
            occurrence(NEW_ENTITY_AFTER, "it", " it limits"),
        ],
        Accepted(
            status="accepted",
            group_ref="g03",
            input_refs=[old.original_input_ref],
            producer_ref=REF,
            target_entity_id=backup,
        ),
        REF,
    )
    stamp_producer(payload, REF)
    bind_chunks(payload, NEW_ENTITY_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_unresolved(old, before, chunks):
    """g03 is unresolved: the reviewer does not say what `A controller` is."""
    require_fresh_doc01(old, before, set(REINTERPRETATION_MAP), SCOPE)
    payload = begin_revision(old, UNRESOLVED_AFTER, REF, REINTERPRET_UNRESOLVED, POLICY)
    retire_group(payload, "g01")
    declare_group(
        payload,
        old,
        "g03",
        "r03",
        "A controller; it",
        "Captured replacement local reference group g03.",
        [
            occurrence(UNRESOLVED_AFTER, "A controller"),
            occurrence(UNRESOLVED_AFTER, "it", " it limits"),
        ],
        Unresolved(
            status="unresolved",
            group_ref="g03",
            input_refs=[old.original_input_ref],
            producer_ref=REF,
        ),
        REF,
    )
    stamp_producer(payload, REF)
    bind_chunks(payload, UNRESOLVED_AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def local_fact(publisher, source, key):
    """The regenerated fact of a fresh group: graph edge, text and evidence."""
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records

    from .fixture import OSCILLATIONS_ID
    from .native import edge_metadata

    mid = source.mention_groups[key].entity_id
    edge = await edge_metadata(publisher.graph, mid, OSCILLATIONS_ID, "limits")
    edge_id = UUID(generate_edge_object_id(str(mid), str(OSCILLATIONS_ID), "limits"))
    evidence = await get_edge_evidence_records(
        [edge_id], source.dataset_id, per_edge_limit=100, total_limit=100
    )
    doc = source.inputs[source.original_input_ref]
    decision = next(
        r for r in source.mention_resolutions.values() if r.group_ref == key
    )
    return dict(
        group=key,
        mention_entity_id=str(mid),
        resolution_status=decision.status,
        fact_edge_id=str(edge_id),
        fact_present=edge is not None,
        fact_text=edge.edge_properties.get("edge_text") if edge else None,
        evidence_chunk_ids=sorted(
            str(e.chunk_id) for e in evidence if e.data_id == doc.data_id
        ),
    )


def inspector(queries):
    """Retrieval under the given named queries, and the regenerated g03 fact."""

    async def inspect(publisher, sources):
        from .retrieve import retrieve

        source = sources["doc01"]
        result = dict(
            queries={
                name: dict(
                    query=text, **await retrieve(publisher, source.dataset_id, text)
                )
                for name, text in queries.items()
            },
            g03=await local_fact(publisher, source, "g03"),
        )
        decision = source.mention_resolutions["r03"]
        if isinstance(decision, Accepted):
            target = str(decision.target_entity_id)
            result["g03"].update(
                target_entity_id=target,
                target_present=await publisher.graph.get_node(target) is not None,
                target_indexed=bool(
                    await publisher.vector.retrieve("Entity_name", [target])
                ),
            )
        return result

    return inspect


HELIOS = "What does Helios controller limit?"
inspect_new_entity = inspector(
    {
        "helios_controller": HELIOS,
        "backup_controller": "What does Backup controller limit?",
    }
)
inspect_unresolved = inspector({"helios_controller": HELIOS})
