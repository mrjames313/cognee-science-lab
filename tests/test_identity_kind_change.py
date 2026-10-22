"""Representation-kind changes with unchanged text: a TextChange with equal texts."""

import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from test_identity_occurrences import example
from test_identity_revisions import Graph
from cognee_lab.identity.admission import GroupFate
from cognee_lab.identity.captured_chunks import (
    captured_facts,
    fixture_mention_id,
    retired_facts,
    retired_mentions,
)
from cognee_lab.identity.captured_text import BEFORE
from cognee_lab.identity.kind_change import (
    HC_ID,
    HC_RECIPE,
    TO_MENTION_MAP,
    TO_REUSABLE_MAP,
    describe_to_mention,
    describe_to_reusable,
)
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.replace import admit_replacement
from cognee_lab.identity.text_changes import TextChange
from cognee_lab.identity.validation import (
    IntentError,
    fresh_mention_id,
    validate_inputs,
)

HC = UUID(HC_ID)


def revisions(payload):
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=BEFORE,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    mention = describe_to_mention(old, BEFORE, [chunk])
    reusable = describe_to_reusable(mention, BEFORE, [chunk])
    return old, mention, reusable, chunk


async def admit_equal(old, source, mapping, graph=None, text_change=True):
    change = TextChange(BEFORE, BEFORE, mapping) if text_change else None
    return await admit_replacement(
        graph or Graph(), old, source, {"doc01": BEFORE}, change, retry=False
    )


async def test_reusable_to_mention_keeps_g01_and_adds_a_fresh_hc_group(
    source_payload,
):
    old, mention, _, chunk = revisions(source_payload)
    fate = await admit_equal(old, mention, TO_MENTION_MAP)
    assert fate == GroupFate(frozenset({"g01", "g02"}), frozenset(), frozenset({"g09"}))
    g09 = mention.mention_groups["g09"]
    assert [o.model_dump() for o in g09.occurrences] == [
        dict(start=19, end=21, text="HC")
    ]
    assert g09.entity_id == fresh_mention_id(old.identity_data_id, 2, "g09")
    decision = mention.mention_resolutions["r09"]
    assert decision.status == "accepted"
    assert decision.target_entity_id == old.inputs["existing_A"].entity_id
    assert mention.variant_assignments == {} and HC not in mention.entity_constructions
    kept = mention.mention_groups["g01"], old.mention_groups["g01"]
    assert (kept[0].entity_id, kept[0].occurrences) == (
        kept[1].entity_id,
        kept[1].occurrences,
    )
    assert dict(captured_facts(mention)) == {"g01": "it limits oscillations"}
    assert dict(retired_facts(mention)) == {} and retired_mentions(mention) == {}


async def test_mention_to_reusable_retires_g09_and_names_the_listed_hc_entity(
    source_payload,
):
    _, mention, reusable, chunk = revisions(source_payload)
    graph = Graph()
    fate = await admit_equal(mention, reusable, TO_REUSABLE_MAP, graph)
    assert fate == GroupFate(frozenset({"g01", "g02"}), frozenset({"g09"}), frozenset())
    assert "g09" not in reusable.mention_groups and "r09" not in (
        reusable.mention_resolutions
    )
    assert reusable.entity_constructions[HC].name == "HC"
    v02 = reusable.variant_assignments["v02"]
    assert (v02.source_entity_id, v02.target_entity_id) == (
        HC,
        mention.inputs["existing_A"].entity_id,
    )
    assert "existing_HC" in v02.input_refs
    assert reusable.inputs["existing_HC"].entity_id == HC
    assert set(retired_mentions(reusable)) == {"g09"}
    assert retired_mentions(reusable)["g09"] == mention.mention_groups["g09"].entity_id
    assert dict(retired_facts(reusable)) == {}
    assert fixture_mention_id(reusable) == mention.mention_groups["g01"].entity_id


async def test_the_listed_corpus_input_matches_the_hc_entity_in_the_graph(
    source_payload,
):
    _, _, reusable, chunk = revisions(source_payload)
    nodes = {
        str(HC): dict(HC_RECIPE),
        str(reusable.inputs["existing_A"].entity_id): dict(
            name="Helios controller", description="Reusable controller identity."
        ),
    }

    class Entities:
        async def get_node(self, key):
            return nodes.get(key)

    await validate_inputs(
        reusable,
        texts={"doc01": BEFORE},
        chunks={str(chunk.id): chunk},
        graph=Entities(),
    )
    nodes[str(HC)]["description"] = "changed"
    with pytest.raises(IntentError) as refused:
        await validate_inputs(
            reusable,
            texts={"doc01": BEFORE},
            chunks={str(chunk.id): chunk},
            graph=Entities(),
        )
    assert refused.value.code == "input_changed"


async def test_a_fresh_group_needs_a_rebuild_even_when_the_text_is_unchanged(
    source_payload,
):
    old, mention, _, _ = revisions(source_payload)
    with pytest.raises(IntentError) as refused:
        await admit_equal(old, mention, TO_MENTION_MAP, text_change=False)
    assert refused.value.code == "rebuild_required"


async def test_an_hc_entity_that_no_record_lists_must_be_derived(source_payload):
    _, mention, reusable, _ = revisions(source_payload)
    payload = reusable.model_dump(mode="json")
    payload["variant_assignments"]["v02"]["input_refs"] = ["doc01", "existing_A"]
    unlisted = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="derives from its source") as refused:
        await admit_equal(mention, unlisted, TO_REUSABLE_MAP)
    assert refused.value.code == "entity_uuid_not_derived"


async def test_a_listed_hc_entity_that_is_already_a_node_is_admitted(
    source_payload,
):
    _, mention, reusable, _ = revisions(source_payload)
    graph = Graph({str(HC)})
    assert (await admit_equal(mention, reusable, TO_REUSABLE_MAP, graph)).retired == {
        "g09"
    }


async def test_a_mapped_occurrence_may_not_move_when_the_text_is_unchanged(
    source_payload,
):
    old, mention, _, _ = revisions(source_payload)
    payload = mention.model_dump(mode="json")
    payload["mention_groups"]["g01"]["occurrences"][0].update(start=50, end=64)
    moved = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError) as refused:
        await admit_equal(old, moved, TO_MENTION_MAP)
    assert refused.value.code == "occurrence_moved"


def test_the_describers_refuse_any_root_but_their_own_revision(source_payload):
    old, mention, reusable, chunk = revisions(source_payload)
    for source, describe in [
        (mention, describe_to_mention),
        (reusable, describe_to_mention),
        (old, describe_to_reusable),
        (reusable, describe_to_reusable),
    ]:
        with pytest.raises(IntentError) as refused:
            describe(source, BEFORE, [chunk])
        assert refused.value.code == "fixture_scope"
