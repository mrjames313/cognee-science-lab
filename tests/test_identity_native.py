"""Real configured stores in fresh subprocesses; no user's .env/store is used."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def command(root, operation, *args, expect=0):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cognee_lab.identity",
            operation,
            "--root",
            str(root),
            *args,
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,  # Allow cold native imports/migrations on slower test hosts.
    )
    assert result.returncode == expect, result.stdout[-7000:] + result.stderr[-2000:]
    return result


@pytest.mark.integration
def test_native_publish_query_and_idempotent_reconcile(tmp_path):
    root = tmp_path / "native"
    command(root, "fixture")
    first = json.loads((root / "result.json").read_text())
    fact = next(f for f in first["result"]["facts"] if f["relationship"] == "limits")
    assert fact["source_id"] == "233cb019-3986-5864-88bc-91f334a64372"
    assert (
        fact["identity"]["target_entity_id"] == "8b4bff50-907b-56b6-bc80-3b0a7018714a"
    )
    assert fact["evidence"][0]["data_id"] == "50d5313b-0fee-5945-b1d5-5c1d37a6f880"
    assert "it limits oscillations" in fact["evidence"][0]["text"]
    assert first["result"]["seed_entity_ids"] == [
        "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
    ]
    command(root, "retrieve")  # Reopen real stores in a second process.
    command(root, "reconcile")
    second = json.loads((root / "result.json").read_text())
    assert second["result"]["facts"] == first["result"]["facts"]
    assert second["recovery_events"] == []
    # A native property mutation invalidates a field actually consumed by
    # Describe; the saved recipe must not silently restore it during retrieval.
    script = """
import asyncio,json,sys
from pathlib import Path
from uuid import UUID
from cognee_lab.identity.fixture_embeddings import FixtureEmbeddings
from cognee_lab.identity.__main__ import configure
root=Path(sys.argv[1])
with FixtureEmbeddings() as endpoint:
 configure(root,endpoint)
 from cognee_lab.identity.publish import Publisher
 from cognee_lab.identity.retrieve import retrieve
 async def check():
  p=await Publisher.configured()
  await p.graph.update_node('8b4bff50-907b-56b6-bc80-3b0a7018714a',{'description':'changed input'})
  dataset=UUID(json.loads((root/'fixture-info.json').read_text())['dataset_id'])
  answer=await retrieve(p,dataset,'What does HC limit?')
  assert answer['facts']==[]
  assert answer['unavailable_sources'][0]['reason']=='input_changed'
  events=await p.records.events(dataset)
  assert len(events)==1 and events[0]['origin']=='test'
 asyncio.run(check())
"""
    mutated = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert mutated.returncode == 0, mutated.stdout[-4000:] + mutated.stderr[-2000:]


@pytest.mark.integration
def test_native_failure_is_unavailable_and_explicitly_recovered(tmp_path):
    root = tmp_path / "failure"
    failed = command(root, "fixture", "--fault-stage", "identity_edges", expect=1)
    assert "recovery_event_id=" in failed.stdout
    query = command(root, "retrieve")
    assert '"facts": []' in query.stdout
    withheld = json.loads(query.stdout)
    assert withheld["unavailable_sources"][0]["reason"] == "publication_failed"
    assert withheld["unavailable_sources"][0]["recovery_event_id"]
    command(root, "reconcile")
    result = json.loads((root / "result.json").read_text())
    assert result["result"]["facts"]
    assert len(result["recovery_events"]) == 1
    assert result["recovery_events"][0]["resolved_at"]
    assert result["recovery_events"][0]["origin"] == "test/fault_injection"


@pytest.mark.integration
@pytest.mark.parametrize("first", ["doc01", "doc02"])
def test_native_two_source_withdrawal_in_both_orders(tmp_path, first):
    root = tmp_path / "shared"
    command(root, "multi-fixture")
    initial = json.loads((root / "multisource_result.json").read_text())
    assert len(initial["result"]["facts"]) == 2
    assert len(initial["shared_variant"]["contributions"]) == 2
    assert len(initial["shared_variant"]["owners"]) == 2
    assert initial["shared_singleton_present"]
    for value in initial["sources"].values():
        assert value["unresolved_entity_present"] and value["unresolved_marker_present"]
    other = "doc02" if first == "doc01" else "doc01"
    # Reopen stores for each selected operation, including repeated withdrawal.
    command(root, "withdraw", "--source", first)
    one = json.loads((root / "multisource_result.json").read_text())
    assert one["sources"][first]["state"] == "withdrawn"
    assert one["sources"][other]["state"] == "current"
    assert not one["sources"][first]["private_singleton_present"]
    assert one["sources"][other]["private_singleton_present"]
    assert one["shared_singleton_present"]
    assert one["shared_singleton_indexed"]
    assert one["borrowed_entity"] == initial["borrowed_entity"]
    assert one["borrowed_entity"]["fixture_sentinel"] == "preserve me"
    assert not one["sources"][first]["private_singleton_indexed"]
    assert len(one["shared_variant"]["owners"]) == 1
    assert [c["identity_data_id"] for c in one["shared_variant"]["contributions"]] == [
        one["sources"][other]["identity_data_id"]
    ]
    expected = [
        c
        for c in initial["shared_variant"]["contributions"]
        if c["identity_data_id"] == one["sources"][other]["identity_data_id"]
    ]
    assert one["shared_variant"]["contributions"] == expected
    assert {
        k: v
        for k, v in one["shared_variant"]["properties"].items()
        if k != "identity_contributions"
    } == {
        k: v
        for k, v in initial["shared_variant"]["properties"].items()
        if k != "identity_contributions"
    }
    assert [f["source_id"] for f in one["result"]["facts"]] == [
        one["sources"][other]["mention_entity_id"]
    ]
    command(root, "withdraw", "--source", first)
    command(root, "withdraw", "--source", other)
    # A later retirement ends that source's historical survival obligations.
    command(root, "withdraw", "--source", first)
    both = json.loads((root / "multisource_result.json").read_text())
    assert not both["shared_variant"]["present"]
    assert not both["shared_singleton_present"]
    assert not both["shared_singleton_indexed"]
    assert both["borrowed_entity"] == initial["borrowed_entity"]
    assert both["result"]["facts"] == []
    assert both["result"]["unavailable_sources"] == []
    assert both["recovery_events"] == []
    for value in both["sources"].values():
        assert value["state"] == "withdrawn"
        assert value["original_marker_present"] and value["original_fact_present"]
        assert (
            value["original_fact_owned_by_chunk"] and value["original_evidence_present"]
        )
        assert value["unresolved_entity_present"] and value["unresolved_marker_present"]
        assert not value["private_singleton_present"]
        assert not value["private_singleton_indexed"]


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["withdraw_contributions", "withdraw_owners"])
def test_native_withdrawal_failure_preserves_other_source_and_retries(tmp_path, stage):
    root = tmp_path / "retirement_failure"
    command(root, "multi-fixture")
    command(root, "withdraw", "--source", "doc01", "--fault-stage", stage, expect=1)
    query = json.loads(command(root, "retrieve").stdout)
    assert len(query["facts"]) == 1
    assert (
        query["facts"][0]["identity"]["identity_data_id"]
        == "ca84d73d-ee72-5dd2-8e33-4117bb6cac36"
    )
    assert query["unavailable_sources"][0]["reason"] == "publication_failed"
    rejected = command(root, "reconcile", "--source", "doc01", expect=1)
    assert "Retry the failed withdrawal explicitly" in rejected.stdout
    # Retire the other source before retry: the original durable plan must
    # tolerate that legitimate independent change.
    command(root, "withdraw", "--source", "doc02")
    command(root, "withdraw", "--source", "doc01")
    recovered = json.loads((root / "multisource_result.json").read_text())
    assert recovered["result"]["facts"] == []
    assert not recovered["shared_variant"]["present"]
    assert not recovered["shared_singleton_present"]
    assert len(recovered["recovery_events"]) == 1
    incident = recovered["recovery_events"][0]
    assert incident["outcome"] == "withdrawn" and incident["resolved_at"]
    assert incident["recovery_attempts"][-1]["method"] == "withdraw"


def test_application_code_has_no_concrete_backend_access():
    import ast

    for path in (REPO / "src/cognee_lab/identity").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(
                    x in (node.module or "").split(".")
                    for x in ["lancedb", "ladybug", "kuzu", "sqlite3", "dialects"]
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"query", "execute_sql", "connect"}, path


@pytest.mark.integration
def test_native_revision_replacement_preserves_other_source_and_local_facts(tmp_path):
    root = tmp_path / "revisions"
    command(root, "multi-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    stale = command(root, "revise", "--expected-revision", "0", expect=1)
    assert "Saved revision changed" in stale.stdout
    command(root, "revise", "--expected-revision", "1")
    after = json.loads((root / "revision_result.json").read_text())
    a = after["sources"]["doc01"]
    b = after["sources"]["doc02"]
    assert (
        a["saved_revision"] == a["verified_revision"] == a["registered_revision"] == 2
    )
    assert (
        b["saved_revision"] == b["verified_revision"] == b["registered_revision"] == 1
    )
    assert a["registered_matches_saved"] and b["registered_matches_saved"]
    assert a["resolution_target_entity_id"] != b["resolution_target_entity_id"]
    assert not a["private_singleton_present"] and not a["private_singleton_indexed"]
    assert after["shared_singleton_present"] and after["shared_singleton_indexed"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    expected = [
        c
        for c in before["shared_variant"]["contributions"]
        if c["identity_data_id"] == b["identity_data_id"]
    ]
    assert after["shared_variant"]["contributions"] == expected
    assert len(after["shared_variant"]["owners"]) == 1
    old_facts = {f["source_id"]: f for f in before["result"]["facts"]}
    assert len(after["result"]["facts"]) == 2
    for fact in after["result"]["facts"]:
        previous = old_facts[fact["source_id"]]
        assert fact["edge_id"] == previous["edge_id"]
        assert fact["evidence"] == previous["evidence"]
        assert fact["target_id"] == previous["target_id"]
    corrected = after["corrected_entity_result"]["facts"]
    assert len(corrected) == 1 and corrected[0]["source_id"] == a["mention_entity_id"]
    assert (
        corrected[0]["identity"]["target_entity_id"] == a["resolution_target_entity_id"]
    )
    assert after["recovery_events"] == []
    # Stale callers cannot replace or republish revision 1 after revision 2.
    stale = command(root, "revise", "--expected-revision", "1", expect=1)
    assert "Saved revision changed" in stale.stdout
    command(root, "reconcile", "--source", "doc01")
    current = json.loads((root / "multisource_result.json").read_text())
    assert current["result"]["facts"] == after["result"]["facts"]
    assert current["recovery_events"] == []


@pytest.mark.integration
@pytest.mark.parametrize(
    "stage",
    ["replace_saved", "replace_registered", "replace_published", "replace_retired"],
)
def test_native_failed_replacement_withholds_one_source_and_reconciles(tmp_path, stage):
    root = tmp_path / "revision_failure"
    command(root, "multi-fixture")
    command(
        root, "revise", "--expected-revision", "1", "--fault-stage", stage, expect=1
    )
    withheld = json.loads(command(root, "retrieve").stdout)
    assert len(withheld["facts"]) == 1
    assert (
        withheld["facts"][0]["identity"]["identity_data_id"]
        == "ca84d73d-ee72-5dd2-8e33-4117bb6cac36"
    )
    assert withheld["unavailable_sources"][0]["reason"] == "publication_failed"
    status = json.loads(command(root, "status").stdout)
    row = next(
        r
        for r in status["publications"]
        if r["source"] == "718efce2-4251-5f6f-8318-417bb4dd3525"
    )
    assert (
        row["revision"] == 2
        and row["verified_revision"] == 1
        and row["state"] == "failed"
    )
    assert row["plan"]["previous_description"]
    command(root, "reconcile", "--source", "doc01")
    recovered = json.loads((root / "multisource_result.json").read_text())
    source = recovered["sources"]["doc01"]
    assert source["state"] == "current"
    assert (
        source["saved_revision"]
        == source["verified_revision"]
        == source["registered_revision"]
        == 2
    )
    assert source["registered_matches_saved"]
    assert len(recovered["result"]["facts"]) == 2
    assert len(recovered["shared_variant"]["contributions"]) == 1
    assert not source["private_singleton_present"]
    assert (
        source["original_fact_owned_by_chunk"] and source["original_evidence_present"]
    )
    assert len(recovered["recovery_events"]) == 1
    event = recovered["recovery_events"][0]
    assert event["operation"] == "replace" and event["outcome"] == "restored"
    assert event["resolved_at"] and event["resolving_revision"] == 2
