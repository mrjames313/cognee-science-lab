"""Deletes outside the lab through real configured stores in fresh
subprocesses: Cognee's own forget and prune (`native-forget`), what
`status` then reports, and the lab forget that erases the lab's copy."""

import json

import pytest

from test_identity_native import command

DOC01 = "718efce2-4251-5f6f-8318-417bb4dd3525"


def output_of(completed):
    return json.loads(completed.stdout[completed.stdout.index("{") :])


def status_of(root):
    return output_of(command(root, "status"))


@pytest.mark.integration
@pytest.mark.parametrize(
    "case, missing",
    [
        ("data", ["original_data", "document_node", "chunks", "stored_files"]),
        (
            "dataset",
            [
                "original_data",
                "identity_data",
                "document_node",
                "chunks",
                "stored_files",
            ],
        ),
        ("prune", ["document_node", "chunks", "stored_files"]),
    ],
)
def test_native_status_lists_a_source_deleted_outside_the_lab(tmp_path, case, missing):
    root = tmp_path / case
    command(root, "fixture")
    assert status_of(root)["native_deleted"] == []
    command(root, "native-forget", "--case", case)
    assert status_of(root)["native_deleted"] == [
        dict(
            identity_data_id=DOC01,
            dataset_id=status_of(root)["publications"][0]["dataset"],
            state="current",
            revision=1,
            missing=missing,
            next="forget --source doc01 --expected-revision 1",
        )
    ]


@pytest.mark.integration
def test_native_status_lists_no_source_the_lab_itself_changed(tmp_path):
    withdrawn = tmp_path / "withdrawn"
    command(withdrawn, "multi-fixture")
    command(withdrawn, "withdraw", "--source", "doc02")
    failed = tmp_path / "failed"
    command(failed, "fixture", "--fault-stage", "nodes", expect=1)
    text = tmp_path / "text"
    command(text, "multi-fixture")
    command(
        text,
        "edit-text",
        "--expected-revision",
        "1",
        "--fault-stage",
        "text_removed",
        expect=1,
    )
    chunked = tmp_path / "chunked"
    command(chunked, "chunked-fixture")
    chain = tmp_path / "chain"
    command(chain, "glossary-fixture", "--chain")
    for root, states in [
        (withdrawn, ["current", "withdrawn"]),
        (failed, ["failed"]),
        (text, ["current", "failed"]),
        (chunked, ["current", "current"]),
        (chain, ["current", "current", "current"]),
    ]:
        status = status_of(root)
        assert sorted(p["state"] for p in status["publications"]) == states
        assert status["native_deleted"] == [], root.name
    command(text, "reconcile", "--source", "doc01")
    assert [p["state"] for p in status_of(text)["publications"]] == [
        "current",
        "current",
    ]


@pytest.mark.integration
@pytest.mark.parametrize(
    "creation, label",
    [
        (["fixture"], "doc01"),
        (["multi-fixture"], "doc01"),
        (["multi-fixture"], "doc02"),
        (["glossary-fixture", "--chain"], "doc01"),
    ],
    ids=["fixture", "multi", "multi-doc02", "chain"],
)
def test_native_reconcile_refuses_a_source_deleted_outside_the_lab(
    tmp_path, creation, label
):
    root = tmp_path / creation[0]
    command(root, *creation)
    command(root, "native-forget", "--case", "data", "--source", label)
    before = status_of(root)
    [gone] = before["native_deleted"]
    refused = output_of(command(root, "reconcile", "--source", label, expect=1))
    assert refused["message"].startswith(
        f"The native copy of {label} is gone or changed outside the lab"
    )
    assert refused["details"] == dict(
        source=gone["identity_data_id"],
        missing=["original_data", "document_node", "chunks", "stored_files"],
        revision=1,
        next=f"forget --source {label} --expected-revision 1",
    )
    assert gone["next"] == refused["details"]["next"]
    after = status_of(root)
    assert after["publications"] == before["publications"]
    assert after["recovery_events"] == before["recovery_events"]


CASES = ["data", "dataset", "prune"]


@pytest.mark.integration
@pytest.mark.parametrize("case", CASES)
def test_native_forget_erases_a_source_deleted_outside_the_lab(tmp_path, case):
    root = tmp_path / case
    command(root, "fixture")
    command(root, "native-forget", "--case", case)
    forgotten = output_of(
        command(root, "forget", "--source", "doc01", "--expected-revision", "1")
    )
    assert [[p["state"], p["revision"]] for p in forgotten["publications"]] == [
        ["forgotten", 1]
    ]
    assert forgotten["dependents_failed"] is None
    status = status_of(root)
    assert status["native_deleted"] == []
    assert all(e["resolved_at"] for e in status["recovery_events"])


def forget_confirmed(root, label, expect=0):
    dry = output_of(
        command(
            root, "forget", "--source", label, "--expected-revision", "1", "--dry-run"
        )
    )
    return output_of(
        command(
            root,
            "forget",
            "--source",
            label,
            "--expected-revision",
            "1",
            "--confirm",
            dry["token"],
            expect=expect,
        )
    )


@pytest.mark.integration
def test_native_forget_revises_a_dependent_whose_copy_remains(tmp_path):
    root = tmp_path / "data"
    command(root, "multi-fixture", "--dependent")
    command(root, "native-forget", "--source", "doc01", "--case", "data")
    forgotten = forget_confirmed(root, "doc01")
    assert [
        [d["revision"], d["level"]] for d in forgotten["forget"]["dependents_revised"]
    ] == [[2, 1]]
    assert forgotten["dependents_failed"] is None
    assert [forgotten["sources"][k]["state"] for k in ("doc01", "doc02")] == [
        "forgotten",
        "current",
    ]
    assert status_of(root)["native_deleted"] == []


@pytest.mark.integration
@pytest.mark.parametrize("case", ["dataset", "prune"])
def test_native_a_dependent_deleted_outside_the_lab_waits_for_its_own_forget(
    tmp_path, case
):
    root = tmp_path / case
    command(root, "multi-fixture", "--dependent")
    command(root, "native-forget", "--case", case)
    forgotten = forget_confirmed(root, "doc01", expect=1)
    assert forgotten["forget"]["dependents_revised"] == []
    [waiting] = forgotten["forget"]["dependents_waiting"]
    assert (
        waiting["identity_data_id"] == forgotten["sources"]["doc02"]["identity_data_id"]
    )
    assert "chunks" in waiting["missing"]
    assert forgotten["dependents_failed"]["code"] == "dependent_unfinished"
    assert forgotten["sources"]["doc02"]["missing"] == waiting["missing"]
    second = output_of(
        command(root, "forget", "--source", "doc02", "--expected-revision", "1")
    )
    assert second["dependents_failed"] is None
    finished = output_of(
        command(
            root, "forget", "--source", "doc01", "--expected-revision", "1", "--dry-run"
        )
    )
    assert finished["unfinished"] == []
    status = status_of(root)
    assert [p["state"] for p in status["publications"]] == ["forgotten", "forgotten"]
    assert status["native_deleted"] == []
    assert all(e["resolved_at"] for e in status["recovery_events"])


@pytest.mark.integration
def test_native_a_chain_root_reports_a_glossary_deleted_outside_the_lab(tmp_path):
    root = tmp_path / "chain"
    command(root, "glossary-fixture", "--chain")
    command(root, "native-forget", "--case", "data", "--source", "glossary")
    forgotten = forget_confirmed(root, "doc01")
    assert forgotten["glossary"]["text"] is None
    assert forgotten["sources"]["glossary"]["missing"] == [
        "original_data",
        "document_node",
        "chunks",
        "stored_files",
    ]
