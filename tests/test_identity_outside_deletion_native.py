"""An Entity deleted outside the lab through real configured stores in
fresh subprocesses: `edit-entity --case delete`, the replacements that
answer its readers one at a time without recreating it, a failed
replacement's retry, and the re-add refusal."""

import json

import pytest

from test_identity_native import command

HELIOS = "8b4bff50-907b-56b6-bc80-3b0a7018714a"


def output_of(completed):
    return json.loads(completed.stdout[completed.stdout.index("{") :])


def helios_absent(root):
    refused = output_of(command(root, "edit-entity", "--case", "delete", expect=1))
    return refused["message"] == f"No such Entity: {HELIOS}"


@pytest.mark.integration
def test_native_a_deleted_entity_is_answered_without_being_recreated(tmp_path):
    root = tmp_path / "chain"
    command(root, "glossary-fixture", "--chain")
    deleted = output_of(command(root, "edit-entity", "--case", "delete"))
    assert deleted["entity_edit"]["node_present"] is False
    assert deleted["entity_edit"]["name_point_present"] is True
    first = output_of(
        command(
            root,
            "replace-decision",
            "--source",
            "doc01",
            "--decision",
            "r01",
            "--expected-revision",
            "1",
        )
    )
    assert first["sources"]["doc01"]["decisions"]["r01"]["status"] == "unresolved"
    assert first["recovery_events"] == []
    assert helios_absent(root)
    second = output_of(
        command(
            root,
            "replace-decision",
            "--source",
            "doc01",
            "--decision",
            "v01",
            "--expected-revision",
            "2",
        )
    )
    assert "v01" not in second["sources"]["doc01"]["decisions"]
    assert second["sources"]["doc01"]["verified_revision"] == 3
    status = output_of(command(root, "status"))
    [third] = [
        json.loads(p["description"])
        for p in status["publications"]
        if json.loads(p["description"])["revision"] == 3
    ]
    assert HELIOS not in third["entity_constructions"]
    assert "existing_A" not in third["inputs"]


@pytest.mark.integration
def test_native_a_failed_replacement_retries_without_recreating_the_entity(
    tmp_path,
):
    root = tmp_path / "retry"
    command(root, "glossary-fixture", "--chain")
    command(root, "edit-entity", "--case", "delete")
    failed = output_of(
        command(
            root,
            "replace-decision",
            "--source",
            "doc01",
            "--decision",
            "r01",
            "--expected-revision",
            "1",
            "--fault-stage",
            "replace_verification",
            expect=1,
        )
    )
    assert "recovery_event_id=" in failed["message"]
    finished = output_of(command(root, "reconcile", "--source", "doc01"))
    assert finished["sources"]["doc01"]["verified_revision"] == 2
    assert all(e["resolved_at"] for e in finished["recovery_events"])
    assert helios_absent(root)


@pytest.mark.integration
def test_native_a_readd_naming_a_deleted_entity_is_refused(tmp_path):
    root = tmp_path / "readd"
    command(root, "glossary-fixture", "--chain")
    command(root, "edit-entity", "--case", "delete")
    dry = output_of(
        command(
            root, "forget", "--source", "doc01", "--expected-revision", "1", "--dry-run"
        )
    )
    command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--confirm",
        dry["token"],
    )
    refused = output_of(
        command(
            root, "readd", "--source", "doc01", "--expected-revision", "1", expect=1
        )
    )
    assert refused["message"].startswith(
        "A publication does not recreate an Entity deleted outside the lab: " + HELIOS
    )
    assert helios_absent(root)
