"""Checkpoint K: kind changes of the glossary root's doc01, and the J2 rules
they meet."""

import dataclasses
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from cascade_worlds import pending_row
from chain_worlds import described, record_key, row_of
from test_identity_dependencies import TEXT, glossary_doc01
from cognee_lab.identity.admission import admit, parse_occurrence_map
from cognee_lab.identity.chain_kind_change import (
    TO_MENTION_MAP,
    TO_REUSABLE_MAP,
    describe_to_mention,
    describe_to_reusable,
)
from cognee_lab.identity.erasure import refuse_retiring_inputs
from cognee_lab.identity.erasure_rules import (
    ERASURE_IMPLEMENTATION,
    check_removal_producers_kept,
)
from cognee_lab.identity.kind_change import HC_ID
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.validation import IntentError, fresh_entity_id


def chunk_of(source):
    return SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=TEXT,
        is_part_of=SimpleNamespace(id=source.inputs["doc01"].data_id),
    )


def admitted(old, new, mapping, first_attempt=True):
    return admit(
        old,
        new,
        TEXT,
        TEXT,
        parse_occurrence_map(mapping),
        first_attempt=first_attempt,
    )


def test_to_mention_drops_v01_and_keeps_r01_and_every_producer(source_payload):
    """A removal producer a cascade wrote stays in the kind change's
    revision: the describers start from the old producers."""
    payload = json.loads(json.dumps(source_payload))
    payload["producers"]["removed_r1"] = dict(
        payload["producers"]["fixture"], implementation=ERASURE_IMPLEMENTATION
    )
    old = glossary_doc01(payload)
    new = describe_to_mention(old, TEXT, [chunk_of(old)])
    fate = admitted(old, new, TO_MENTION_MAP)
    assert fate.fresh == {"g09"} and fate.continuing == {"g01"}
    assert set(new.variant_assignments) == set()
    assert UUID(HC_ID) not in new.entity_constructions
    assert new.mention_resolutions["r01"] == old.mention_resolutions["r01"]
    assert new.producers["removed_r1"] == old.producers["removed_r1"]
    check_removal_producers_kept(old, new)


def test_to_reusable_brings_v01_back_on_the_listed_hc_entity(source_payload):
    old = glossary_doc01(source_payload)
    mention = describe_to_mention(old, TEXT, [chunk_of(old)])
    reusable = describe_to_reusable(mention, TEXT, [chunk_of(old)])
    fate = admitted(mention, reusable, TO_REUSABLE_MAP)
    assert fate.retired == {"g09"}
    v01 = reusable.variant_assignments["v01"]
    assert str(v01.source_entity_id) == HC_ID and "existing_HC" in v01.input_refs
    with pytest.raises(IntentError) as refused:
        describe_to_reusable(old, TEXT, [chunk_of(old)])
    assert refused.value.code == "fixture_scope"


def test_a_mention_becomes_a_new_shared_entity_under_a_derived_uuid(source_payload):
    """g09 retires for a new reusable Entity that a new variant names. Its
    UUID derives from the source, the new revision and the variant's key;
    any other UUID is refused on a first attempt."""
    old = glossary_doc01(source_payload)
    mention = describe_to_mention(old, TEXT, [chunk_of(old)])

    def shared(entity_id):
        payload = json.loads(
            describe_to_reusable(mention, TEXT, [chunk_of(old)]).model_dump_json()
        )
        payload["inputs"].pop("existing_HC")
        payload["entity_constructions"].pop(HC_ID)
        payload["entity_constructions"][entity_id] = dict(
            name="HC", description="A new shared Entity for HC."
        )
        v02 = payload["variant_assignments"].pop("v01")
        payload["variant_assignments"]["v02"] = dict(
            v02, source_entity_id=entity_id, input_refs=["doc01"]
        )
        return IdentitySource.model_validate_json(json.dumps(payload))

    derived = str(fresh_entity_id(old.identity_data_id, 3, "v02"))
    fate = admitted(mention, shared(derived), TO_REUSABLE_MAP)
    assert fate.retired == {"g09"}
    with pytest.raises(IntentError) as refused:
        admitted(mention, shared(str(uuid4())), TO_REUSABLE_MAP)
    assert refused.value.code == "entity_uuid_not_derived"


def test_a_kind_change_that_still_reads_a_source_being_forgotten_meets_the_fence():
    """s1 cites s0, whose forget is pending. s1's next revision drops its
    variant, as a kind change does, and still cites s0's resolution, so the
    fence refuses it."""
    graph = {"s0": frozenset(), "s1": frozenset({"s0"})}
    s1 = described("s1", graph["s1"])
    payload = json.loads(s1.model_dump_json())
    payload["variant_assignments"].pop("v")
    payload["inputs"].pop(record_key("s0", "v"))
    payload["revision"] = 2
    changed = IdentitySource.model_validate_json(json.dumps(payload))
    rows = [pending_row(graph), row_of(s1, "ok")]
    with pytest.raises(IntentError) as refused:
        refuse_retiring_inputs(changed, rows)
    assert refused.value.code == "retiring_source"
    rows[0] = dataclasses.replace(rows[0], state="current", plan={})
    refuse_retiring_inputs(changed, rows)
