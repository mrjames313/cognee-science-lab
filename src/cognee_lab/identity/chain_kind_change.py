"""Representation-kind changes of doc01 on a glossary root, where other
sources read doc01.

The user decided on 2026-10-24 that a kind change retires the old group
and declares a fresh one; there is no in-place kind change. A glossary
root's doc01 is the first fixture's (one group, g01, and its own text), with
the same producers and the same equal-text rebuild as kind_change.py:

- `change-kind-to-mention` is kind_change.py's describer for that root: it
  drops v01 and the HC recipe and declares the fresh mention group g09,
  `HC`, resolved to the Helios controller as r09. r01 keeps its producer.
- `change-kind-to-reusable` has its own describer: it retires g09, declares
  the HC recipe again, reads the HC Entity through the corpus input
  `existing_HC` and names it in a variant under v01, the key the first
  change dropped. HC must still be in the graph: on a chain root doc03
  co-owns it, but a root where doc01 alone owned HC and nothing read it
  loses HC at the first change, and this one is then refused.

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
from functools import partial

from .captured_chunks import TO_MENTION, bind_chunks, recorded_budget
from .captured_revision import begin_revision, require_root, retire_group
from .fixture import FIXTURES, context_for, expect_current
from .forget_fixture import write_revision
from .kind_change import (
    MENTION_REF,
    REUSABLE_REF,
    TO_REUSABLE,
    declare_hc_variant,
    inspect_hc_entity,
)
from .kind_change import describe_to_mention as to_mention
from .models import IdentitySource
from .text_changes import TextChange, chunk_text, original_context, read_original
from .text_fixture import maintain_one

TO_MENTION_MAP = {"g01": [["g01", 0], ["g01", 1]]}
TO_REUSABLE_MAP = {**TO_MENTION_MAP, "g09": [None]}
ROOT_TEXT = (FIXTURES / "source.txt").read_text()

describe_to_mention = partial(
    to_mention,
    groups=TO_MENTION_MAP,
    text=ROOT_TEXT,
    stamp=False,
    scope="change-kind-to-mention on a glossary root needs doc01 at revision 1",
)


def describe_to_reusable(old, before, chunks):
    """g09 retires. doc01 declares the HC recipe again, reads the HC Entity
    as a corpus input and names it in a document-scoped variant under v01."""
    require_root(
        old,
        before,
        set(TO_REUSABLE_MAP),
        "change-kind-to-reusable on a glossary root needs doc01 that "
        "change-kind-to-mention produced at revision 2",
        revision=2,
        produced=(MENTION_REF, TO_MENTION),
        text=ROOT_TEXT,
    )
    payload = begin_revision(
        old, before, REUSABLE_REF, TO_REUSABLE, "explicit-mention-to-reusable-v1"
    )
    retire_group(payload, "g09")
    declare_hc_variant(
        payload,
        old,
        "v01",
        old.mention_resolutions["r01"].target_entity_id,
        [old.original_input_ref, "existing_HC"],
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
