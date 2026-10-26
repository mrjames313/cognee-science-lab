"""The lab entry points' rules that need no store: which native facets a
failed publication reports, the chunk budget a reconcile chunks with,
and the whole-chunk-set check of the lab Task."""

import json

import pytest

from cognee_lab.identity import entry, native_copy
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.storage import PublicationRow
from cognee_lab.identity.validation import IntentError


def described(source_payload):
    return IdentitySource.model_validate_json(json.dumps(source_payload))


def failed_publication(source, verified_revision):
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state="failed",
        revision=source.revision,
        verified_revision=verified_revision,
        attempt="attempt",
        description=source,
        tombstone=None,
        plan=dict(operation="identity_publish"),
    )


class Graph:
    def __init__(self, nodes=()):
        self.nodes = dict(nodes)

    async def get_node(self, node_id):
        return self.nodes.get(node_id)


@pytest.fixture
def emptied(monkeypatch):
    async def absent(*_):
        return False

    monkeypatch.setattr(native_copy, "data_present", absent)
    monkeypatch.setattr(native_copy, "raw_file_present", absent)


@pytest.mark.parametrize("verified_revision", [0, 1])
async def test_a_failed_publication_reports_every_missing_facet(
    source_payload, emptied, verified_revision
):
    """A memory-only forget or an outside text change of a failed first
    publication's original is a delete outside the lab like any other: the
    lab's cognify never rolls its own chunks back."""
    row = failed_publication(described(source_payload), verified_revision)
    assert await native_copy.missing_native(Graph(), row) == [
        "original_data",
        "identity_data",
        "document_node",
        "chunks",
        "stored_files",
    ]


async def test_reconcile_chunks_with_the_budget_the_native_chunks_record(
    source_payload,
):
    source = described(source_payload)
    (chunk,) = entry.described_chunks(source)
    graph = Graph({chunk: {"max_chunk_tokens": 9}})
    assert await entry.chunk_budget_of(source, graph, 512) == 9


async def test_reconcile_chunks_with_the_default_when_the_chunks_are_gone(
    source_payload,
):
    assert await entry.chunk_budget_of(described(source_payload), Graph(), 512) == 512


class Untouchable:
    @property
    def records(self):
        raise AssertionError("the ledger was read")


async def test_the_lab_task_refuses_part_of_the_chunk_set_before_the_ledger(
    source_payload,
):
    source = described(source_payload)
    with pytest.raises(IntentError) as refused:
        await entry.publish_one(Untouchable(), source, [], None, None, None, "test")
    assert refused.value.code == "chunk_mapping"
