"""Retirement intent and absence verification are separate from read eligibility."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_identity_occurrences import example
from cognee_lab.identity.captured_chunks import fact_chunks, fixture_mention_id
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.occurrence_fixture import BEFORE
from cognee_lab.identity.resolved_retirement import (
    AFTER,
    RETENTION,
    describe_retirement,
)
from cognee_lab.identity.text_changes import admit_remap
from cognee_lab.identity.validation import IntentError


def retired_example(payload):
    old, _, _ = example(payload)
    chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        text=AFTER,
        is_part_of=SimpleNamespace(id=old.inputs["doc01"].data_id),
    )
    return old, chunk, describe_retirement(old, BEFORE, [chunk])


def test_last_resolved_group_retirement_keeps_unrelated_declarations(source_payload):
    old, chunk, intended = retired_example(source_payload)
    assert admit_remap(old, intended, BEFORE, AFTER, RETENTION) is None
    assert list(intended.mention_groups) == ["g02"]
    assert list(intended.mention_resolutions) == ["r02"]
    assert (
        intended.mention_groups["g02"].entity_id == old.mention_groups["g02"].entity_id
    )
    assert old.mention_groups["g01"].entity_id not in intended.entity_constructions
    assert (
        intended.variant_assignments["v01"].target_entity_id
        in intended.entity_constructions
    )
    assert fixture_mention_id(intended) == old.mention_groups["g01"].entity_id
    assert fact_chunks(intended, [chunk]) == []


def test_absent_group_is_not_permission_to_skip_a_remaining_fact(source_payload):
    old, _, intended = retired_example(source_payload)
    payload = intended.model_dump(mode="json")
    text = AFTER + "it limits oscillations.\n"
    from cognee_lab.identity.captured_chunks import bind_chunks
    from cognee_lab.identity.validation import text_digest

    payload["inputs"]["doc01"]["text_sha256"] = text_digest(text)
    chunk = SimpleNamespace(id=uuid4(), chunk_index=0, text=text)
    bind_chunks(payload, text, [chunk])
    changed = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError, match="remains in text"):
        fact_chunks(changed, [chunk])


def test_empty_fact_capture_still_requires_complete_chunk_mapping(source_payload):
    _, chunk, intended = retired_example(source_payload)
    chunk.id = uuid4()
    with pytest.raises(IntentError, match="complete checked chunk"):
        fact_chunks(intended, [chunk])


def test_captured_retirement_refuses_a_later_revision(source_payload):
    old, chunk, _ = retired_example(source_payload)
    later = old.model_copy(update={"revision": 2})
    with pytest.raises(IntentError, match="fresh chunked-fixture"):
        describe_retirement(later, BEFORE, [chunk])
