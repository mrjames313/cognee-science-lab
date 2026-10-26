"""An Entity deleted outside the lab through real configured stores in
fresh subprocesses: `edit-entity --case delete`, the replacements that
answer its readers one at a time without recreating it, a failed
replacement's retry, and a re-add that waits for the Entity's live citer."""

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
def test_native_a_readd_waits_for_the_live_citer_then_derives_a_new_uuid(tmp_path):
    """doc03 is forgotten; its re-add is refused while doc01 still builds
    Helios. Once doc01 is forgotten and the caller drops doc03's citations
    of doc01's records, doc03 is re-added with Helios under a new UUID."""
    root = tmp_path / "readd"
    fixture = output_of(command(root, "glossary-fixture", "--chain"))
    command(root, "edit-entity", "--case", "delete")
    forget = ("forget", "--expected-revision", "1")
    command(root, *forget, "--source", "doc03")
    readd = ("readd", "--source", "doc03", "--expected-revision", "1")
    refused = output_of(command(root, *readd, expect=1))
    doc01 = fixture["sources"]["doc01"]["identity_data_id"]
    assert refused["message"].startswith(
        "A re-add does not recreate an Entity deleted outside the lab while a "
        f"saved source still cites or builds it: {HELIOS} by {doc01} in dataset "
    )
    assert [c["identity_data_id"] for c in refused["details"]["citers"]] == [doc01]
    command(root, *forget, "--source", "doc01")
    path = root / "doc03_identity.json"
    caller = json.loads(path.read_text())
    for key in ("doc01_r01", "doc01_v01"):
        del caller["inputs"][key]
    for record in (
        *caller["mention_resolutions"].values(),
        *caller["variant_assignments"].values(),
    ):
        record["input_refs"] = [
            k for k in record["input_refs"] if not k.startswith("doc01_")
        ]
    path.write_text(json.dumps(caller))
    command(root, *readd)
    status = output_of(command(root, "status"))
    served = [p for p in status["publications"] if p["state"] == "current"]
    assert [p["revision"] for p in served] == [1, 2]
    assert not any(HELIOS in p["description"] for p in served)
    doc03 = json.loads((root / "identity_doc03_revision2.json").read_text())
    names = [e["name"] for e in doc03["entity_constructions"].values()]
    assert "Helios controller" in names


@pytest.mark.integration
def test_native_a_withdrawn_co_owner_leaves_the_entity_deleted_outside(tmp_path):
    """doc03 declares doc01's Helios recipe too. Once doc03 is withdrawn,
    Helios is doc01's alone, so its delete outside the lab is answered as
    before: r01 is replaced and Helios stays absent."""
    root = tmp_path / "co-owner"
    command(root, "glossary-fixture", "--chain")
    command(root, "withdraw", "--source", "doc03")
    command(root, "edit-entity", "--case", "delete")
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
    assert helios_absent(root)
