import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_identity_occurrences import example
from cognee_lab.identity.admission import GroupFate, admit, parse_occurrence_map
from cognee_lab.identity.captured_chunks import (
    FACT_TEXT,
    captured_facts,
    fact_chunks,
    retired_mentions,
)
from cognee_lab.identity.captured_text import BEFORE
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.occurrence_fixture import (
    MIXED_AFTER,
    MIXED_MAP,
    describe_mixed,
)
from cognee_lab.identity.validation import IntentError, validate_inputs


def mixed(payload):
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=MIXED_AFTER,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return old, chunk, describe_mixed(old, BEFORE, [chunk])


def admit_mixed(old, source, mapping=MIXED_MAP):
    return admit(old, source, BEFORE, MIXED_AFTER, parse_occurrence_map(mapping))


async def test_one_edit_removes_keeps_and_adds_occurrences(source_payload):
    old, chunk, intended = mixed(source_payload)
    assert admit_mixed(old, intended) == GroupFate(
        frozenset({"g01"}), frozenset({"g02"}), frozenset()
    )
    g01 = intended.mention_groups["g01"]
    assert g01.entity_id == old.mention_groups["g01"].entity_id
    assert [o.model_dump() for o in g01.occurrences] == [
        dict(start=46, end=48, text="it"),
        dict(start=86, end=100, text="the controller"),
    ]
    assert list(intended.mention_groups) == ["g01"]
    assert "r02" not in intended.mention_resolutions
    assert old.mention_groups["g02"].entity_id not in intended.entity_constructions
    assert intended.mention_resolutions["r01"].target_entity_id == (
        old.mention_resolutions["r01"].target_entity_id
    )
    payload = intended.model_dump(mode="json")
    for assignment in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        assignment["input_refs"] = ["doc01"]
    checked = IdentitySource.model_validate_json(json.dumps(payload))
    await validate_inputs(
        checked, texts={"doc01": MIXED_AFTER}, chunks={str(chunk.id): chunk}, graph=None
    )
    assert dict(captured_facts(intended)) == {"g01": FACT_TEXT}
    assert fact_chunks(intended, [chunk]) == [chunk]
    assert retired_mentions(intended) == {}


def test_the_mixed_map_needs_its_one_survivor(source_payload):
    old, _, intended = mixed(source_payload)
    nothing_survives = {"g01": [None, None], "g02": [None]}
    with pytest.raises(IntentError, match="key that no old group used") as refused:
        admit_mixed(old, intended, nothing_survives)
    assert refused.value.code == "fresh_key_reused"
    keeps_plasma = {"g01": [None, ["g01", 0]], "g02": [["g02", 0]]}
    with pytest.raises(IntentError, match="not in the new source"):
        admit_mixed(old, intended, keeps_plasma)
    the_controller_as_it = {"g01": [["g01", 0], None], "g02": [None]}
    with pytest.raises(IntentError, match="text differs"):
        admit_mixed(old, intended, the_controller_as_it)
