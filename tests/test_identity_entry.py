"""The lab entry points' rules that need no store: which native facets a
failed first publication reports."""

import json

import pytest

from cognee_lab.identity import native_copy
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.storage import PublicationRow


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


async def test_a_failed_first_publication_does_not_report_its_chunks(
    source_payload, emptied
):
    row = failed_publication(described(source_payload), verified_revision=0)
    assert await native_copy.missing_native(Graph(), row) == [
        "original_data",
        "identity_data",
        "stored_files",
    ]


async def test_a_failed_publication_after_a_served_revision_reports_every_facet(
    source_payload, emptied
):
    row = failed_publication(described(source_payload), verified_revision=1)
    assert await native_copy.missing_native(Graph(), row) == [
        "original_data",
        "identity_data",
        "document_node",
        "chunks",
        "stored_files",
    ]
