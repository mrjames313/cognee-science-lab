"""Native whole-document edit/rebuild tests; captured decisions, no LLM."""

import json

import pytest

from test_identity_native import command
from cognee_lab.identity.text_fixture import PREFIX


def check_text_result(before, after):
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    assert a["state"] == b["state"] == "current"
    assert (
        a["saved_revision"] == a["registered_revision"] == a["verified_revision"] == 2
    )
    assert (
        b["saved_revision"] == b["registered_revision"] == b["verified_revision"] == 1
    )
    assert a["registered_matches_saved"] and b["registered_matches_saved"]
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert len(after["result"]["facts"]) == 2
    old_facts = {f["source_id"]: f for f in before["result"]["facts"]}
    for fact in after["result"]["facts"]:
        old = old_facts[fact["source_id"]]
        assert fact["edge_id"] == old["edge_id"]
        assert (
            fact["identity"]["target_entity_id"] == old["identity"]["target_entity_id"]
        )
        if fact["source_id"] == a["mention_entity_id"]:
            assert fact["evidence"][0]["text"] == PREFIX + old["evidence"][0]["text"]
            assert fact["evidence"][0]["chunk_id"] != old["evidence"][0]["chunk_id"]
            assert fact["evidence"][0]["data_id"] == old["evidence"][0]["data_id"]
            for prev, current in zip(
                old["identity"]["occurrences"], fact["identity"]["occurrences"]
            ):
                assert current["start"] == prev["start"] + len(PREFIX)
                assert current["end"] == prev["end"] + len(PREFIX)
        else:
            assert fact == old
    assert len(after["shared_variant"]["owners"]) == 2
    own = {c["identity_data_id"]: c for c in after["shared_variant"]["contributions"]}
    assert own[a["identity_data_id"]]["revision"] == 2
    old_other = next(
        c
        for c in before["shared_variant"]["contributions"]
        if c["identity_data_id"] == b["identity_data_id"]
    )
    assert own[b["identity_data_id"]] == old_other
    # A later healthy reconcile replaces the completed mutation plan with its
    # own publication plan; the edit's JSON result retains historical diagnostics.
    if "text_changes" in after:
        change = after["text_changes"][0]
        assert change["position_shift"] == len(PREFIX)
        assert change["previous_text_sha256"] != change["text_sha256"]
        assert change["previous_chunk_ids"] != change["chunk_ids"]
        assert (
            change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
        )
        assert (
            change["evidence_uses_current_chunks"] and change["mention_ids_preserved"]
        )
    for source in after["sources"].values():
        assert (
            source["original_marker_present"] and source["original_fact_owned_by_chunk"]
        )
        assert (
            source["original_evidence_present"] and source["unresolved_marker_present"]
        )
        assert source["unresolved_entity_present"]
    assert after["shared_singleton_present"] and after["shared_singleton_indexed"]
    assert after["result"]["unavailable_sources"] == []


@pytest.mark.integration
def test_native_text_edit_replaces_chunks_evidence_and_reconciles(tmp_path):
    root = tmp_path / "text_revision"
    command(root, "multi-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    baseline_text = (root / "source.txt").read_text()
    stale = command(root, "edit-text", "--expected-revision", "0", expect=1)
    assert "Saved revision changed" in stale.stdout
    command(root, "edit-text", "--expected-revision", "1")
    after = json.loads((root / "text_revision_result.json").read_text())
    assert after["text_changes"]
    check_text_result(before, after)
    assert after["recovery_events"] == []
    assert (
        root / "source.txt"
    ).read_text() == baseline_text  # immutable fixture baseline
    assert (root / "source_doc01_revision2.txt").read_text() == PREFIX + baseline_text
    command(root, "reconcile", "--source", "doc01")
    repeated = json.loads((root / "multisource_result.json").read_text())
    check_text_result(before, repeated)
    assert repeated["result"]["facts"] == after["result"]["facts"]
    # Native original-chunk ownership now points at the new chunks, so subsequent
    # identity withdrawal preserves the rebuilt fact/markers/evidence.
    command(root, "withdraw", "--source", "doc01")
    withdrawn = json.loads((root / "multisource_result.json").read_text())
    assert len(withdrawn["result"]["facts"]) == 1
    assert withdrawn["sources"]["doc01"]["original_fact_owned_by_chunk"]
    assert withdrawn["sources"]["doc01"]["original_evidence_present"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "stage", ["text_removed", "text_registered", "text_chunks", "replace_published"]
)
def test_native_interrupted_text_change_finishes_saved_intent(tmp_path, stage):
    root = tmp_path / "text_failure"
    command(root, "multi-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root, "edit-text", "--expected-revision", "1", "--fault-stage", stage, expect=1
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert len(query["facts"]) == 1
    assert (
        query["facts"][0]["source_id"]
        == before["sources"]["doc02"]["mention_entity_id"]
    )
    assert query["unavailable_sources"][0]["reason"] == "publication_failed"
    status = json.loads(command(root, "status").stdout)
    row = next(
        r
        for r in status["publications"]
        if r["source"] == before["sources"]["doc01"]["identity_data_id"]
    )
    assert (
        row["revision"] == 2
        and row["verified_revision"] == 1
        and row["state"] == "failed"
    )
    assert (
        row["plan"]["text_change"]["text"]
        == PREFIX + row["plan"]["text_change"]["previous_text"]
    )
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    assert after["text_changes"]
    check_text_result(before, after)
    assert len(after["recovery_events"]) == 1
    event = after["recovery_events"][0]
    assert event["resolved_at"] and event["resolving_revision"] == 2
    assert event["outcome"] == "restored"


@pytest.mark.integration
def test_native_missing_endpoint_owner_is_refused_before_memory_removal(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = tmp_path / "ownership_gap"
    command(root, "multi-fixture")
    script = r"""
import asyncio,sys
from pathlib import Path
from uuid import UUID
from cognee_lab.identity.environment import fixture_environment
root=Path(sys.argv[1])
with fixture_environment(root):
 from cognee_lab.identity.publish import Publisher
 from cognee_lab.identity.multisource import current_sources
 from cognee_lab.identity.fixture import OSCILLATIONS_ID
 from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
 async def corrupt():
  p=await Publisher.configured()
  s=(await current_sources(root,p))["doc02"]
  ref=make_chunk_source_ref_key(s.dataset_id,s.inputs["doc01"].data_id,s.inputs["chunk01"].chunk_id)
  await p.graph.remove_node_source_refs([str(OSCILLATIONS_ID)],[ref])
  for engine in (p.vector,p.graph):
   result=engine.close()
   if hasattr(result,"__await__"): await result
 asyncio.run(corrupt())
"""
    corrupted = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert corrupted.returncode == 0, (
        corrupted.stdout[-2000:] + corrupted.stderr[-2000:]
    )
    rejected = command(root, "edit-text", "--expected-revision", "1", expect=1)
    assert "another owner's edge" in rejected.stdout
    state = json.loads(command(root, "status").stdout)
    assert all(
        r["state"] == "current" and r["revision"] == 1 for r in state["publications"]
    )
    assert state["recovery_events"] == []
    assert len(json.loads(command(root, "retrieve").stdout)["facts"]) == 2
