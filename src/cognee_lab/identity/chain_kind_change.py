"""Representation-kind changes of doc01 on a glossary root, where other
sources read doc01.

The user decided on 2026-10-24 that a kind change retires the old group
and declares a fresh one; there is no in-place kind change. A glossary
root's doc01 is the first fixture's (one group, g01), so it has its own
describers beside kind_change.py's, with the same producers and the same
equal-text rebuild:

- `change-kind-to-mention` drops v01 and the HC recipe and declares the
  fresh mention group g09, `HC`, resolved to the Helios controller as r09.
- `change-kind-to-reusable` retires g09, declares the HC recipe again, reads
  the HC Entity through the corpus input `existing_HC` and names it in a
  variant under v01, the key the first change dropped.

The readers follow the rules that already hold. A citer of v01 is withheld
`input_removed`: `replace-citation` answers it and `reconfirm` refuses it.
While that citer still cites v01, bringing v01 back is refused
(`record_key_reused`). A source that reads an HC that doc01 alone owns as a
corpus object refuses the change before any write (`dependent_source`).
With no reader, an HC that doc01 alone owned leaves the graph. The result
lists the other sources' decisions that the completed revision leaves
withheld (`dependents_withheld`), from the live pass that retrieval and
`status` run.
"""

import json

from .captured_chunks import TO_MENTION, bind_chunks
from .captured_revision import (
    begin_revision,
    declare_group,
    occurrence,
    retire_group,
)
from .digests import object_digest
from .kind_change import (
    HC_ID,
    HC_RECIPE,
    MENTION_REF,
    REUSABLE_REF,
    TO_REUSABLE,
    inspect_hc_entity,
)
from .models import IdentitySource
from .validation import IntentError

TO_MENTION_MAP = {"g01": [["g01", 0], ["g01", 1]]}
TO_REUSABLE_MAP = {**TO_MENTION_MAP, "g09": [None]}


def describe_to_mention(old, before, chunks):
    """doc01 drops v01 and the HC recipe; a fresh g09 holds `HC` and
    resolves to the Helios controller. r01 is unchanged."""
    if (
        old.revision != 1
        or set(old.mention_groups) != {"g01"}
        or "v01" not in old.variant_assignments
    ):
        raise IntentError(
            "fixture_scope",
            "change-kind-to-mention on a glossary root needs doc01 at revision 1",
        )
    payload = begin_revision(
        old, before, MENTION_REF, TO_MENTION, "explicit-reusable-to-mention-v1"
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
        [occurrence(before, "HC")],
        MENTION_REF,
        status="accepted",
        target=old.mention_resolutions["r01"].target_entity_id,
    )
    bind_chunks(payload, before, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_to_reusable(old, before, chunks):
    """g09 retires. doc01 declares the HC recipe again, reads the HC Entity
    as a corpus input and names it in a document-scoped variant under v01."""
    made = old.producers.get(MENTION_REF)
    if (
        old.revision != 2
        or made is None
        or made.implementation != TO_MENTION
        or set(old.mention_groups) != {"g01", "g09"}
    ):
        raise IntentError(
            "fixture_scope",
            "change-kind-to-reusable on a glossary root needs doc01 that "
            "change-kind-to-mention produced at revision 2",
        )
    payload = begin_revision(
        old, before, REUSABLE_REF, TO_REUSABLE, "explicit-mention-to-reusable-v1"
    )
    retire_group(payload, "g09")
    payload["entity_constructions"][HC_ID] = HC_RECIPE
    payload["inputs"]["existing_HC"] = dict(
        kind="corpus_object",
        dataset_id=str(old.dataset_id),
        entity_id=HC_ID,
        selected_fields=list(HC_RECIPE),
        content_sha256=object_digest(HC_RECIPE),
    )
    payload["variant_assignments"]["v01"] = dict(
        status="accepted",
        source_entity_id=HC_ID,
        target_entity_id=str(old.mention_resolutions["r01"].target_entity_id),
        applicability=dict(kind="document", document_ref=old.original_input_ref),
        input_refs=[old.original_input_ref, "existing_HC"],
        producer_ref=REUSABLE_REF,
        explanation=None,
    )
    bind_chunks(payload, before, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


DESCRIBERS = {
    "change-kind-to-mention": (describe_to_mention, TO_MENTION_MAP),
    "change-kind-to-reusable": (describe_to_reusable, TO_REUSABLE_MAP),
}


async def change_kind(
    publisher, root, command, doc01, *, expected_revision, fault_stage
):
    """Write doc01's kind change through the equal-text rebuild, then
    refresh its dependents' moved spans. Returns the refresh result."""
    from .captured_chunks import recorded_budget
    from .fixture import context_for, expect_current
    from .review import write_revision
    from .text_changes import TextChange, chunk_text, original_context, read_original
    from .text_fixture import maintain_one

    describe, occurrence_map = DESCRIBERS[command]
    await expect_current(
        publisher,
        doc01,
        expected_revision,
        "Reconcile the exact saved replacement explicitly",
    )
    ctx = await context_for(doc01.identity_data_id)
    before = await read_original(doc01, ctx)
    change = TextChange(
        before, before, occurrence_map, await recorded_budget(doc01, publisher.graph)
    )
    chunks = await chunk_text(
        before, await original_context(doc01, ctx), change.chunk_budget
    )
    intended = describe(doc01, before, chunks)
    write_revision(root, "doc01", intended)
    return await maintain_one(
        publisher,
        intended,
        change,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )


async def dependents_withheld(publisher, sources, result) -> dict:
    """What the completed revision leaves withheld in the other sources,
    and who owns the HC Entity now."""
    own = str(sources["doc01"].identity_data_id)
    return dict(
        dependents_withheld=[
            d for d in result["withheld_decisions"] if d["identity_data_id"] != own
        ],
        **await inspect_hc_entity(publisher, sources),
    )
