import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.multisource import add_lifecycle_records
from cognee_lab.identity.captured_text import BEFORE
from cognee_lab.identity.occurrence_fixture import (
    AFTER,
    COMMANDS,
    REMOVAL_MAP,
    describe_removal,
)
from cognee_lab.identity.admission import admit, identity_map, parse_occurrence_map
from cognee_lab.identity.validation import IntentError, text_digest, validate_inputs


def test_each_occurrence_command_has_its_own_result_file():
    assert len({c.result_name for c in COMMANDS.values()}) == len(COMMANDS)


def example(payload):
    payload["inputs"]["doc01"]["text_sha256"] = text_digest(BEFORE)
    payload["inputs"]["chunk01"]["end"] = len(BEFORE)
    payload["mention_groups"]["g01"]["occurrences"] = [
        dict(start=49, end=63, text="the controller"),
        dict(start=90, end=92, text="it"),
    ]
    add_lifecycle_records(payload, "doc01", BEFORE)
    old = IdentitySource.model_validate_json(json.dumps(payload))
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=AFTER,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return old, chunk, describe_removal(old, BEFORE, [chunk])


async def test_reviewed_partial_and_empty_group_removal(source_payload):
    old, chunk, intended = example(source_payload)
    assert (
        admit(old, intended, BEFORE, AFTER, parse_occurrence_map(REMOVAL_MAP)).fresh
        == frozenset()
    )
    assert list(intended.mention_groups) == ["g01"]
    assert (
        intended.mention_groups["g01"].entity_id == old.mention_groups["g01"].entity_id
    )
    assert intended.mention_groups["g01"].occurrences[0].text == "it"
    assert "r02" not in intended.mention_resolutions
    assert old.mention_groups["g02"].entity_id not in intended.entity_constructions
    # Isolate the exact new text/chunk checks from external graph dependencies.
    payload = intended.model_dump(mode="json")
    for assignment in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        assignment["input_refs"] = ["doc01"]
    checked = IdentitySource.model_validate_json(json.dumps(payload))
    await validate_inputs(
        checked, texts={"doc01": AFTER}, chunks={str(chunk.id): chunk}, graph=None
    )
    with pytest.raises(IntentError, match="Mapped occurrence is not in the new source"):
        admit(old, intended, BEFORE, AFTER, identity_map(old))


@pytest.mark.parametrize(
    "mapping",
    [
        {"g01": [None, ["g01", 0]]},
        {"g01": [["g01", 0]], "g02": [None]},
        {"g01": [None, ["g01", 0]], "g02": []},
        {"g01": [None, ["g01", 0], None], "g02": [None]},
        {"g01": [None, ["g01", 0]], "g02": [["g01", 0]]},
        {"g01": [None, ["g01", True]], "g02": [None]},
        {"g01": [None, ["g01", 1]], "g02": [None]},
        {"g01": [None, ["g01", 0]], "g02": [None], "unknown": []},
        {"g01": [None, "g01"], "g02": [None]},
    ],
)
def test_a_map_must_state_every_old_occurrence_once_and_truthfully(
    source_payload, mapping
):
    old, _, intended = example(source_payload)
    with pytest.raises(IntentError) as refused:
        admit(old, intended, BEFORE, AFTER, parse_occurrence_map(mapping))
    assert refused.value.code == "occurrence_changed"


def test_removal_does_not_silently_retarget_a_continuing_group(source_payload):
    old, _, intended = example(source_payload)
    payload = intended.model_dump(mode="json")
    payload["mention_resolutions"]["r01"]["target_entity_id"] = payload[
        "variant_assignments"
    ]["v01"]["source_entity_id"]
    changed = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="keeps its resolution record"):
        admit(old, changed, BEFORE, AFTER, parse_occurrence_map(REMOVAL_MAP))


def test_new_positions_must_match_text_even_with_a_current_fingerprint(source_payload):
    old, _, intended = example(source_payload)
    payload = intended.model_dump(mode="json")
    occurrence = payload["mention_groups"]["g01"]["occurrences"][0]
    occurrence["start"] -= 1
    occurrence["end"] -= 1
    changed = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="exact document slice"):
        admit(old, changed, BEFORE, AFTER, parse_occurrence_map(REMOVAL_MAP))
