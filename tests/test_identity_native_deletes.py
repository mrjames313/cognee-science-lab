"""Deletes outside the lab, against stores that hold nothing: which saved
rows report their native copy missing, and what a copy with a missing facet
reports."""

import json

import pytest

from cognee_lab.identity import native_copy
from cognee_lab.identity.native_copy import NativeCopy, missing_native
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.storage import PublicationRow


class EmptyGraph:
    async def get_node(self, node_id):
        return None


@pytest.fixture
def emptied(monkeypatch):
    """Stores with no Data row, no stored file and no node."""

    async def absent(*_):
        return False

    monkeypatch.setattr(native_copy, "data_present", absent)
    monkeypatch.setattr(native_copy, "raw_file_present", absent)


ALL = ["original_data", "identity_data", "document_node", "chunks", "stored_files"]


def row_of(source_payload, state, operation, **plan):
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state=state,
        revision=source.revision,
        verified_revision=source.revision,
        attempt="attempt",
        description=source,
        tombstone=None,
        plan=dict(operation=operation, **plan),
    )


@pytest.mark.parametrize(
    "state, operation, plan",
    [
        ("current", "identity_publish", {}),
        ("withdrawn", "identity_withdraw", {}),
        ("failed", "identity_publish", {}),
        ("failed", "identity_replace", {}),
        ("failed", "identity_withdraw", {}),
    ],
)
async def test_a_saved_row_reports_its_native_copy_missing(
    source_payload, state, operation, plan, emptied
):
    row = row_of(source_payload, state, operation, **plan)
    assert await missing_native(EmptyGraph(), row) == ALL


@pytest.mark.parametrize(
    "state, operation, plan",
    [
        ("pending", "identity_publish", {}),
        ("pending", "identity_replace", {}),
        ("failed", "identity_forget", {}),
        ("failed", "identity_replace", {"text_change": {"text": "edited"}}),
    ],
)
async def test_a_row_whose_own_attempt_changes_the_native_copy_is_not_checked(
    source_payload, state, operation, plan, emptied
):
    row = row_of(source_payload, state, operation, **plan)
    assert await missing_native(EmptyGraph(), row) == []


async def test_a_forgotten_row_is_not_checked(source_payload, emptied):
    from dataclasses import replace

    row = row_of(source_payload, "forgotten", "identity_forget")
    assert await missing_native(EmptyGraph(), replace(row, description=None)) == []


@pytest.mark.parametrize(
    "copy, missing",
    [
        (NativeCopy(True, True, True, True, True), []),
        (
            NativeCopy(False, True, False, False, False),
            ["original_data", "document_node", "chunks", "stored_files"],
        ),
        (
            NativeCopy(True, True, False, False, False),
            ["document_node", "chunks", "stored_files"],
        ),
        (NativeCopy(True, True, True, False, True), ["chunks"]),
    ],
    ids=["intact", "data_forget", "prune", "incremental_update"],
)
def test_a_native_copy_names_each_missing_facet(copy, missing):
    assert copy.missing == missing
