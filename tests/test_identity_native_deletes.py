"""Deletes outside the lab, without a store: which saved rows should still
have a native copy, and what a copy with a missing facet reports."""

import json

import pytest

from cognee_lab.identity.forget import NativeCopy, checks_native_copy
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.storage import PublicationRow


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
def test_a_saved_row_should_have_its_native_copy(
    source_payload, state, operation, plan
):
    assert checks_native_copy(row_of(source_payload, state, operation, **plan))


@pytest.mark.parametrize(
    "state, operation, plan",
    [
        ("pending", "identity_publish", {}),
        ("pending", "identity_replace", {}),
        ("failed", "identity_forget", {}),
        ("failed", "identity_replace", {"text_change": {"text": "edited"}}),
    ],
)
def test_a_row_whose_own_attempt_changes_the_native_copy_is_not_checked(
    source_payload, state, operation, plan
):
    assert not checks_native_copy(row_of(source_payload, state, operation, **plan))


def test_a_forgotten_row_is_not_checked(source_payload):
    from dataclasses import replace

    row = row_of(source_payload, "forgotten", "identity_forget")
    assert not checks_native_copy(replace(row, description=None))


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
