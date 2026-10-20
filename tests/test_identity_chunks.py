import json
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path

import pytest

from cognee_lab.identity.captured_chunks import (
    bind_chunks,
    fact_chunks,
    recorded_budget,
)
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.text_fixture import describe_prefix_edit
from cognee_lab.identity.validation import IntentError


def split_example(payload):
    text = (Path(__file__).parent / "fixtures/identity/source.txt").read_text()
    first, second = text.index("The controller") + 4, text.index("it limits") + 3
    chunks = [
        SimpleNamespace(id=uuid4(), chunk_index=i, text=value)
        for i, value in enumerate([text[:first], text[first:second], text[second:]])
    ]
    bind_chunks(payload, text, chunks)
    return text, chunks, IdentitySource.model_validate_json(json.dumps(payload))


def test_fact_support_and_mention_markers_have_distinct_exact_chunk_sets(
    source_payload,
):
    text, chunks, source = split_example(source_payload)
    # The first occurrence crosses a boundary; the fact crosses a different one.
    assert source.mention_groups["g01"].chunk_refs == ["chunk01", "chunk02"]
    assert [c.id for c in fact_chunks(source, chunks)] == [chunks[1].id, chunks[2].id]
    assert "it limits oscillations" in chunks[1].text + chunks[2].text
    # Context containing an earlier occurrence is not evidence for this fact.
    assert chunks[0].id not in {c.id for c in fact_chunks(source, chunks)}


async def test_native_budget_is_read_from_all_chunk_construction_metadata(
    source_payload,
):
    text, chunks, source = split_example(source_payload)

    class Graph:
        async def get_node(self, _):
            return {"max_chunk_tokens": 9}

    assert await recorded_budget(source, Graph()) == 9


@pytest.mark.parametrize("values", [[None, None, None], [9, None, 9], [9, 10, 9]])
async def test_missing_or_mixed_chunk_budget_is_refused(source_payload, values):
    text, chunks, source = split_example(source_payload)
    metadata = {str(c.id): n for c, n in zip(chunks, values)}

    class Graph:
        async def get_node(self, key):
            return {"max_chunk_tokens": metadata[key]}

    with pytest.raises(IntentError, match="missing or inconsistent"):
        await recorded_budget(source, Graph())


def test_captured_prefix_is_an_explicit_input_and_does_not_use_byte_offsets(
    source_payload,
):
    text, chunks, source = split_example(source_payload)
    prefix = "Δ review: "
    new = [SimpleNamespace(id=uuid4(), chunk_index=0, text=prefix + text)]
    intended = describe_prefix_edit(source, prefix + text, new, prefix=prefix)
    for a, b in zip(
        source.mention_groups["g01"].occurrences,
        intended.mention_groups["g01"].occurrences,
    ):
        assert b.start - a.start == len(prefix) == 10
        assert (prefix + text)[b.start : b.end] == b.text
    assert len(prefix.encode("utf-8")) == 11
