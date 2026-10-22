"""Captured representation-kind changes on doc01, with the text unchanged.

HC is first a reusable Entity that doc01 declares and names in the document-
scoped variant v01. The first edit makes HC a document-local mention group,
g09, that resolves to the Helios controller. The second edit makes it
reusable again, by referencing the HC Entity that doc02 still owns. Neither
edit changes the text, so each is a TextChange whose before and after texts
are equal: only a rebuild writes a fresh group's markers or drops a retired
group's.
"""

import json

from .captured_chunks import TO_MENTION, bind_chunks
from .captured_revision import (
    begin_revision,
    declare_group,
    occurrence,
    require_fresh_doc01,
    retire_group,
    stamp_producer,
)
from .captured_text import BEFORE
from .models import IdentitySource
from .validation import IntentError, object_digest

TO_REUSABLE = "stage6-captured-kind-change-to-reusable"
HC_ID = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
HC_RECIPE = dict(name="HC", description="Abbreviated reusable form in DOC01.")
QUERIES = {
    "hc": "What does HC limit?",
    "helios_controller": "What does Helios controller limit?",
}
TO_MENTION_MAP = {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]}
TO_REUSABLE_MAP = {**TO_MENTION_MAP, "g09": [None]}
MENTION_REF = "to_mention_review"
REUSABLE_REF = "to_reusable_review"


def describe_to_mention(old, before, chunks):
    """doc01 drops v01 and the HC recipe; a fresh g09 holds `HC` and resolves to
    the Helios controller. doc02 still declares HC and its own HC variant."""
    require_fresh_doc01(
        old,
        before,
        set(TO_MENTION_MAP),
        "Reusable to mention requires doc01 of a fresh chunked-fixture",
    )
    payload = begin_revision(
        old, BEFORE, MENTION_REF, TO_MENTION, "explicit-reusable-to-mention-v1"
    )
    payload["variant_assignments"].pop("v01")
    payload["entity_constructions"].pop(HC_ID)
    declare_group(
        payload,
        old,
        "g09",
        "r09",
        "HC (local mention)",
        "Captured document-local mention group g09.",
        [occurrence(BEFORE, "HC")],
        old.mention_resolutions["r01"],
        MENTION_REF,
    )
    stamp_producer(payload, MENTION_REF)
    bind_chunks(payload, BEFORE, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_to_reusable(old, before, chunks):
    """g09 retires. doc01 declares the HC recipe again, reads doc02's HC Entity
    through a corpus input that the new variant v02 lists, and names it in v02."""
    made = old.producers.get(MENTION_REF)
    if (
        old.revision != 2
        or before != BEFORE
        or set(old.mention_groups) != set(TO_REUSABLE_MAP)
        or made is None
        or made.implementation != TO_MENTION
    ):
        raise IntentError(
            "fixture_scope", "Mention to reusable requires doc01 produced by to-mention"
        )
    payload = begin_revision(
        old, BEFORE, REUSABLE_REF, TO_REUSABLE, "explicit-mention-to-reusable-v1"
    )
    helios = old.inputs["existing_A"].entity_id
    retire_group(payload, "g09")
    payload["entity_constructions"][HC_ID] = HC_RECIPE
    payload["inputs"]["existing_HC"] = dict(
        kind="corpus_object",
        dataset_id=str(old.dataset_id),
        entity_id=HC_ID,
        selected_fields=list(HC_RECIPE),
        content_sha256=object_digest(HC_RECIPE),
    )
    payload["variant_assignments"]["v02"] = dict(
        status="accepted",
        source_entity_id=HC_ID,
        target_entity_id=str(helios),
        applicability=dict(kind="document", document_ref=old.original_input_ref),
        input_refs=[old.original_input_ref, "existing_A", "existing_HC"],
        producer_ref=REUSABLE_REF,
        explanation=None,
    )
    stamp_producer(payload, REUSABLE_REF)
    bind_chunks(payload, BEFORE, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def inspect_hc_entity(publisher, sources):
    """Who owns the HC Entity, and every Entity that carries the name HC."""
    nodes, _ = await publisher.graph.get_graph_data()
    owners = (await publisher.graph.get_node_delete_data([HC_ID])).get(HC_ID)
    return dict(
        hc_entity=dict(
            id=HC_ID,
            present=owners is not None,
            indexed=bool(await publisher.vector.retrieve("Entity_name", [HC_ID])),
            owner_count=len(owners.source_ref_keys) if owners else 0,
            entity_ids_named_hc=sorted(
                node_id
                for node_id, props in nodes
                if props.get("type") == "Entity" and props.get("name") == "HC"
            ),
        ),
    )
