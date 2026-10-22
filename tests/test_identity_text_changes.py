import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.admission import admit, identity_map, parse_occurrence_map
from cognee_lab.identity.text_changes import TextChange
from cognee_lab.identity.text_fixture import PREFIX, describe_prefix_edit
from cognee_lab.identity.validation import IntentError, text_digest, validate_inputs


def test_only_an_unmoved_prefix_insertion_reports_a_shift(source_payload):
    old, before, after, _, intended = example(source_payload)
    unmoved = TextChange(before, after, identity_map(old))
    assert unmoved.prefix_shift(old, intended) == len(PREFIX)
    assert (
        TextChange(before, after + "x", identity_map(old)).prefix_shift(old, intended)
        is None
    )
    swapped = {"g01": [["g01", 1], ["g01", 0]]}
    assert TextChange(before, after, swapped).prefix_shift(old, intended) is None

    def move_it(p):
        p["mention_groups"]["g01"]["occurrences"][1]["start"] += 1

    payload = intended.model_dump(mode="json")
    move_it(payload)
    shifted = intended.model_validate_json(json.dumps(payload))
    assert unmoved.prefix_shift(old, shifted) is None


def example(source_payload):
    old = IdentitySource.model_validate_json(json.dumps(source_payload))
    before = (Path(__file__).parent / "fixtures/identity/source.txt").read_text()
    after = PREFIX + before
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=after,
        is_part_of=SimpleNamespace(id=old.inputs[old.original_input_ref].data_id),
    )
    return old, before, after, chunk, describe_prefix_edit(old, after, [chunk])


def test_exact_unicode_remap_preserves_occurrence_identity_and_reviews_context(
    source_payload,
):
    old, before, after, chunk, intended = example(source_payload)
    assert admit(old, intended, before, after, identity_map(old)).fresh == frozenset()
    assert len(PREFIX.encode("utf-8")) != len(PREFIX)
    assert intended.inputs["chunk01"].chunk_id == chunk.id
    assert (
        intended.mention_groups["g01"].entity_id == old.mention_groups["g01"].entity_id
    )
    for previous, current in zip(
        old.mention_groups["g01"].occurrences,
        intended.mention_groups["g01"].occurrences,
    ):
        assert current.start == previous.start + len(PREFIX)
        assert after[current.start : current.end] == current.text
    assert intended.mention_resolutions["r01"].producer_ref == "text_review"
    assert intended.producers["text_review"].method == "captured_fixture"


@pytest.mark.parametrize(
    "kind,code,message",
    [
        ("stale_offsets", "occurrence_changed", "exact document slice"),
        (
            "changed_interpretation",
            "continuing_decision_changed",
            "keeps its reviewed decision",
        ),
        ("group_uuid", "fresh_key_reused", "key that no old group used"),
        ("arbitrary_edit", "source_changed", "fingerprints disagree"),
    ],
)
def test_text_admission_requires_exact_edit_and_reviewed_semantics(
    source_payload, kind, code, message
):
    old, before, after, chunk, intended = example(source_payload)
    payload = intended.model_dump(mode="json")
    if kind == "stale_offsets":
        payload["mention_groups"]["g01"]["occurrences"] = [
            o.model_dump() for o in old.mention_groups["g01"].occurrences
        ]
    elif kind == "changed_interpretation":
        payload["mention_resolutions"]["r01"]["status"] = "ambiguous"
        payload["mention_resolutions"]["r01"].pop("target_entity_id")
        payload["mention_resolutions"]["r01"]["candidate_entity_ids"] = []
    elif kind == "group_uuid":
        group = payload["mention_groups"]["g01"]
        old_id = group["entity_id"]
        group["entity_id"] = str(uuid4())
        payload["entity_constructions"][group["entity_id"]] = payload[
            "entity_constructions"
        ].pop(old_id)
    else:
        after = after.replace("limits", "increases")
    changed = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match=message) as refused:
        admit(old, changed, before, after, identity_map(old))
    assert refused.value.code == code


async def test_current_text_hash_does_not_make_stale_offsets_valid(source_payload):
    old, before, after, chunk, intended = example(source_payload)
    # Remove the unrelated corpus dependency to isolate the occurrence check.
    payload = intended.model_dump(mode="json")
    for item in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        item["input_refs"] = ["doc01"]
    payload["mention_groups"]["g01"]["occurrences"] = [
        o.model_dump() for o in old.mention_groups["g01"].occurrences
    ]
    stale = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="Occurrence does not match"):
        await validate_inputs(
            stale, texts={"doc01": after}, chunks={str(chunk.id): chunk}, graph=None
        )


async def test_occurrence_crossing_chunk_boundary_requires_both_markers(source_payload):
    old, before, after, chunk, intended = example(source_payload)
    # Split through 'The controller': both native position ranges must participate.
    split = intended.mention_groups["g01"].occurrences[0].start + 5
    a = SimpleNamespace(
        id=uuid4(), chunk_index=0, text=after[:split], is_part_of=chunk.is_part_of
    )
    b = SimpleNamespace(
        id=uuid4(), chunk_index=1, text=after[split:], is_part_of=chunk.is_part_of
    )
    intended = describe_prefix_edit(old, after, [a, b])
    payload = intended.model_dump(mode="json")
    for item in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        item["input_refs"] = ["doc01"]
    valid = IdentitySource.model_validate_json(json.dumps(payload))
    await validate_inputs(
        valid, texts={"doc01": after}, chunks={str(c.id): c for c in [a, b]}, graph=None
    )
    assert valid.mention_groups["g01"].chunk_refs == ["chunk01", "chunk02"]
    payload["mention_groups"]["g01"]["chunk_refs"] = ["chunk02"]
    with pytest.raises(ValidationError, match="cover each occurrence"):
        IdentitySource.model_validate_json(json.dumps(payload))


def test_dependent_source_requires_reconsideration_before_edit(source_payload):
    from cognee_lab.identity.text_changes import reject_dependents

    old, before, after, chunk, intended = example(source_payload)
    dependent = old.model_copy(update={"identity_data_id": uuid4()})
    row = dict(
        source=str(dependent.identity_data_id),
        dataset=str(dependent.dataset_id),
        state="current",
        description=dependent.model_dump_json(),
    )
    with pytest.raises(IntentError, match="reconsideration is required"):
        reject_dependents(old, [row])
    row["state"] = "withdrawn"
    reject_dependents(old, [row])


async def test_unretained_endpoint_cannot_cascade_into_another_owner_edge(
    source_payload,
):
    from cognee.infrastructure.databases.provenance import (
        EdgeIdentity,
        make_chunk_source_ref_key,
    )
    from cognee_lab.identity.text_changes import reject_unsafe_cascades

    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    own = make_chunk_source_ref_key(
        source.dataset_id,
        source.inputs["doc01"].data_id,
        source.inputs["chunk01"].chunk_id,
    )
    foreign = make_chunk_source_ref_key(source.dataset_id, uuid4(), uuid4())
    edge = EdgeIdentity("shared_endpoint", "other", "limits")

    class Graph:
        retained = False

        async def find_node_source_refs_by_dataset(self, _):
            return {"shared_endpoint": [own, foreign] if self.retained else [own]}

        async def iter_bounded_neighborhood(self, *args, **kwargs):
            yield ["shared_endpoint", "other"], [
                ("shared_endpoint", "other", "limits", {})
            ]

        async def get_edge_delete_data(self, edges):
            return {edge: SimpleNamespace(source_ref_keys=[foreign])}

    publisher = SimpleNamespace(graph=Graph())
    with pytest.raises(IntentError, match="another owner's edge"):
        await reject_unsafe_cascades(publisher, source)
    publisher.graph.retained = True
    await reject_unsafe_cascades(publisher, source)


def test_an_edit_to_empty_text_is_refused_even_when_it_removes_every_group(
    source_payload,
):
    old, before, _, _, _ = example(source_payload)
    payload = old.model_dump(mode="json")
    payload["revision"] = 2
    payload["inputs"]["doc01"]["text_sha256"] = text_digest("")
    payload["inputs"].pop("chunk01")
    payload["entity_constructions"].pop(payload["mention_groups"]["g01"]["entity_id"])
    payload["mention_groups"], payload["mention_resolutions"] = {}, {}
    emptied = IdentitySource.model_validate_json(json.dumps(payload))
    everything_removed = parse_occurrence_map({"g01": [None, None]})
    with pytest.raises(IntentError, match="empty") as refused:
        admit(old, emptied, before, "", everything_removed)
    assert refused.value.code == "empty_text"
