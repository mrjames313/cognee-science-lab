"""Forget and re-add through real configured stores in fresh subprocesses."""

import json

import pytest

from cognee_lab.identity.forget import STAGES
from test_identity_native import command

ABSENT = dict(
    original_data_present=False,
    identity_data_present=False,
    raw_file_present=False,
    document_node_present=False,
    chunks_present=[],
    chunk_vectors_present=[],
    mention_nodes_present=[],
    mention_vectors_present=[],
    original_fact_present=False,
    evidence_rows=0,
    private_singleton_present=False,
    private_singleton_indexed=False,
    identity_contribution_present=False,
    owned_nodes=0,
    owned_edges=0,
)


def result_of(root):
    return json.loads((root / "multisource_result.json").read_text())


def error_of(completed):
    return json.loads(completed.stdout.strip().splitlines()[-1])


def intact(before, after, label):
    """The other source's snapshot entry is unchanged by the operation."""
    assert after["sources"][label] == before["sources"][label]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert after["shared_singleton_present"] and after["shared_singleton_indexed"]


@pytest.mark.integration
@pytest.mark.parametrize("first", ["doc01", "doc02"])
def test_native_forget_removes_one_source_and_a_readd_continues_the_revision(
    tmp_path, first
):
    root = tmp_path / "forget"
    command(root, "multi-fixture")
    initial = result_of(root)
    other = "doc02" if first == "doc01" else "doc01"
    assert len(initial["result"]["facts"]) == 2
    assert len(initial["hc_entity"]["owners"]) == 2

    command(root, "forget", "--source", first, "--expected-revision", "1")
    one = result_of(root)
    gone = one["sources"][first]
    assert gone["state"] == "forgotten"
    assert gone["saved_revision"] == 1 and gone["verified_revision"] == 1
    assert gone["forget"] == ABSENT
    intact(initial, one, other)
    other_id = one["sources"][other]["identity_data_id"]
    assert [c["identity_data_id"] for c in one["shared_variant"]["contributions"]] == [
        other_id
    ]
    assert len(one["shared_variant"]["owners"]) == 1
    assert one["hc_entity"]["owners"] == [
        o for o in initial["hc_entity"]["owners"] if o.endswith(other_id)
    ]
    assert [f["source_id"] for f in one["result"]["facts"]] == [
        one["sources"][other]["mention_entity_id"]
    ]
    assert one["result"]["unavailable_sources"] == []
    assert one["recovery_events"] == []

    reopened = json.loads(command(root, "retrieve").stdout)
    assert len(reopened["facts"]) == 1 and reopened["unavailable_sources"] == []
    status = json.loads(command(root, "status").stdout)
    assert sorted(p["state"] for p in status["publications"]) == [
        "current",
        "forgotten",
    ]
    forgotten_row = next(p for p in status["publications"] if p["state"] == "forgotten")
    assert forgotten_row["revision"] == 1 and forgotten_row["verified_revision"] == 1
    assert forgotten_row["plan"]["operation"] == "identity_forget"

    for operation in ("forget", "reconcile"):
        refused = command(
            root, operation, "--source", first, "--expected-revision", "1", expect=1
        )
        assert "Forgotten source" in error_of(refused)["message"]

    command(root, "readd", "--source", first, "--expected-revision", "1")
    two = result_of(root)
    back = two["sources"][first]
    assert back["state"] == "current"
    assert (back["saved_revision"], back["verified_revision"]) == (2, 2)
    assert back["registered_revision"] == 2 and back["registered_matches_saved"]
    assert back["mention_entity_id"] != initial["sources"][first]["mention_entity_id"]
    for key in (
        "original_marker_present",
        "original_fact_present",
        "original_fact_owned_by_chunk",
        "original_evidence_present",
        "unresolved_marker_present",
        "unresolved_entity_present",
        "private_singleton_present",
        "private_singleton_indexed",
    ):
        assert back[key], key
    intact(initial, two, other)
    assert sorted(f["source_id"] for f in two["result"]["facts"]) == sorted(
        [back["mention_entity_id"], two["sources"][other]["mention_entity_id"]]
    )
    assert len(two["shared_variant"]["contributions"]) == 2
    assert len(two["shared_variant"]["owners"]) == 2
    assert sorted(two["hc_entity"]["owners"]) == sorted(initial["hc_entity"]["owners"])
    assert two["recovery_events"] == []
    reopened = json.loads(command(root, "retrieve").stdout)
    assert len(reopened["facts"]) == 2 and reopened["unavailable_sources"] == []

    refused = command(
        root, "readd", "--source", first, "--expected-revision", "2", expect=1
    )
    assert "Re-add needs a forgotten source" in error_of(refused)["message"]


@pytest.mark.integration
def test_native_forget_refuses_a_dependent_until_it_is_withdrawn(tmp_path):
    root = tmp_path / "dependent"
    command(root, "multi-fixture", "--dependent")
    initial = result_of(root)
    assert len(initial["result"]["facts"]) == 2
    reader = initial["sources"]["doc02"]["identity_data_id"]
    document = next(
        f["evidence"][0]["data_id"]
        for f in initial["result"]["facts"]
        if f["identity"]["identity_data_id"]
        == initial["sources"]["doc01"]["identity_data_id"]
    )

    refused = command(
        root, "forget", "--source", "doc01", "--expected-revision", "1", expect=1
    )
    report = error_of(refused)
    assert "reconsider the dependents" in report["message"]
    found = report["details"]["dependents"]
    assert {d["identity_data_id"] for d in found} == {reader}
    assert sorted((d["input_ref"], d["kind"]) for d in found) == [
        ("doc01_instrument", "corpus_object"),
        ("doc01_text", "source_text"),
    ]
    assert next(d["consumed"] for d in found if d["kind"] == "source_text") == document
    unchanged = json.loads(command(root, "retrieve").stdout)
    assert len(unchanged["facts"]) == 2 and unchanged["unavailable_sources"] == []
    status = json.loads(command(root, "status").stdout)
    assert [p["state"] for p in status["publications"]] == ["current", "current"]
    assert status["recovery_events"] == []

    command(root, "withdraw", "--source", "doc02")
    command(root, "forget", "--source", "doc01", "--expected-revision", "1")
    final = result_of(root)
    assert final["sources"]["doc01"]["state"] == "forgotten"
    assert final["sources"]["doc01"]["forget"] == ABSENT
    withdrawn = final["sources"]["doc02"]
    assert withdrawn["state"] == "withdrawn"
    assert withdrawn["original_fact_present"] and withdrawn["original_evidence_present"]
    assert not final["hc_entity"]["present"]
    assert not final["shared_singleton_present"]
    assert final["result"]["facts"] == []
    assert final["result"]["unavailable_sources"] == []
    assert final["recovery_events"] == []


@pytest.mark.integration
@pytest.mark.parametrize("stage", STAGES)
def test_native_forget_failure_withholds_the_source_and_reconcile_finishes_it(
    tmp_path, stage
):
    root = tmp_path / "forget_failure"
    command(root, "multi-fixture")
    initial = result_of(root)
    failed = command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--fault-stage",
        stage,
        expect=1,
    )
    assert "recovery_event_id=" in error_of(failed)["message"]
    query = json.loads(command(root, "retrieve").stdout)
    assert [f["source_id"] for f in query["facts"]] == [
        initial["sources"]["doc02"]["mention_entity_id"]
    ]
    assert [u["reason"] for u in query["unavailable_sources"]] == ["publication_failed"]
    status = json.loads(command(root, "status").stdout)
    (incident,) = status["recovery_events"]
    assert incident["operation"] == "forget" and incident["stage"] == stage
    assert incident["origin"] == "test/fault_injection"
    assert incident["resolved_at"] is None
    blocked = command(root, "withdraw", "--source", "doc01", expect=1)
    assert "Retry the failed forget explicitly" in error_of(blocked)["message"]

    command(root, "reconcile", "--source", "doc01")
    recovered = result_of(root)
    assert recovered["sources"]["doc01"]["state"] == "forgotten"
    assert recovered["sources"]["doc01"]["forget"] == ABSENT
    intact(initial, recovered, "doc02")
    assert [f["source_id"] for f in recovered["result"]["facts"]] == [
        initial["sources"]["doc02"]["mention_entity_id"]
    ]
    assert recovered["result"]["unavailable_sources"] == []
    (incident,) = recovered["recovery_events"]
    assert incident["outcome"] == "forgotten" and incident["resolved_at"]
    assert incident["recovery_attempts"][-1]["method"] == "forget"
    assert incident["recovery_attempts"][-1]["outcome"] == "verified"
