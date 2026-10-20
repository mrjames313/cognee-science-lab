"""Occurrence/group additions through native stores, reopen and forward recovery."""

import json
import pytest

from test_identity_native import command
from cognee_lab.identity.occurrence_addition import AFTER, CONTINUITY


def check_addition(before, after):
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    assert a["state"] == "current"
    assert (
        a["saved_revision"] == a["registered_revision"] == a["verified_revision"] == 2
    )
    assert a["registered_matches_saved"]
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert (
        a["original_marker_present"]
        and a["original_fact_owned_by_chunk"]
        and a["original_evidence_present"]
    )
    assert a["unresolved_marker_present"] and a["unresolved_entity_present"]
    assert len(after["shared_variant"]["owners"]) == 2
    prior = next(
        c
        for c in before["shared_variant"]["contributions"]
        if c["identity_data_id"] == b["identity_data_id"]
    )
    assert prior in after["shared_variant"]["contributions"]
    assert (
        next(
            c
            for c in after["shared_variant"]["contributions"]
            if c["identity_data_id"] == a["identity_data_id"]
        )["revision"]
        == 2
    )
    if "text_changes" in after:
        (change,) = after["text_changes"]
        assert change["occurrence_continuity"] == CONTINUITY
        assert (
            change["occurrence_retention"] is None and change["position_shift"] is None
        )
        assert (
            change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
        )
        assert (
            change["mention_ids_preserved"] and change["evidence_uses_current_chunks"]
        )
        assert change["retired_groups"] == {}
        assert set(change["added_groups"]) == {"g03"}
        group = change["added_groups"]["g03"]
        assert group["entity_present"] and group["entity_indexed"]
        assert group["entity_id"] != a["mention_entity_id"]
        assert set(group["marker_chunk_ids"]) == set(
            change["groups"]["g03"]["marker_chunk_ids"]
        )
        assert len(change["groups"]["g01"]["previous_occurrences"]) == 2
        assert len(change["groups"]["g01"]["occurrences"]) == 3
        assert change["groups"]["g03"]["previous_occurrences"] == []
        assert (
            change["groups"]["g03"]["occurrences"][0]["text"]
            == change["groups"]["g01"]["occurrences"][-1]["text"]
        )
    facts = after["result"]["facts"]
    assert len(facts) == 3
    old = next(
        f for f in before["result"]["facts"] if f["source_id"] == b["mention_entity_id"]
    )
    assert next(f for f in facts if f["source_id"] == b["mention_entity_id"]) == old
    new = next(f for f in facts if f["identity"]["assignment_id"] == "r03")
    assert new["source_id"] != a["mention_entity_id"]
    continuing = next(f for f in facts if f["source_id"] == a["mention_entity_id"])
    assert len(continuing["identity"]["occurrences"]) == 3
    assert (
        new["relationship"] == "limits"
        and new["text"] == "the controller limits oscillations"
    )
    assert new["identity"]["assignment_id"] == "r03"
    assert new["identity"]["target_entity_id"] == a["resolution_target_entity_id"]
    original_data_id = next(
        f for f in before["result"]["facts"] if f["source_id"] == a["mention_entity_id"]
    )["evidence"][0]["data_id"]
    assert all(e["data_id"] == original_data_id for e in new["evidence"])
    # Evidence is the exact fresh native map, not the original baseline chunks.
    allowed = {c["chunk_id"]: c for c in a["chunk_mapping"]}
    for f in facts:
        if f["source_id"] == b["mention_entity_id"]:
            continue
        for e in f["evidence"]:
            span = allowed[e["chunk_id"]]
            assert e["chunk_index"] == span["chunk_index"]
            assert e["text"] == AFTER[span["start"] : span["end"]]


@pytest.mark.integration
def test_native_add_occurrences_reopen_reconcile_prefix_and_withdraw(tmp_path):
    root = tmp_path / "additions"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(root, "add-occurrences", "--expected-revision", "1")
    after = json.loads((root / "occurrence_addition_result.json").read_text())
    check_addition(before, after)
    assert after["recovery_events"] == []
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == after["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    check_addition(before, reconciled)
    assert reconciled["sources"] == after["sources"]
    # A subsequent rebuild must use saved g03 intent, not just the original fixture.
    command(root, "edit-text", "--expected-revision", "2")
    edited = json.loads((root / "text_revision_result.json").read_text())
    assert len(edited["result"]["facts"]) == 3
    assert edited["sources"]["doc01"]["verified_revision"] == 3
    assert edited["sources"]["doc02"] == before["sources"]["doc02"]
    command(root, "withdraw", "--source", "doc01")
    withdrawn = json.loads((root / "multisource_result.json").read_text())
    assert len(withdrawn["result"]["facts"]) == 1
    assert withdrawn["sources"]["doc02"] == before["sources"]["doc02"]
    assert withdrawn["borrowed_entity"] == before["borrowed_entity"]


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["text_chunks", "replace_published"])
def test_native_addition_recovers_exact_new_group_and_fact(tmp_path, stage):
    root = tmp_path / "addition_failure"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root,
        "add-occurrences",
        "--expected-revision",
        "1",
        "--fault-stage",
        stage,
        expect=1,
    )
    failed = json.loads(command(root, "retrieve").stdout)
    expected = next(
        f
        for f in before["result"]["facts"]
        if f["source_id"] == before["sources"]["doc02"]["mention_entity_id"]
    )
    assert failed["facts"] == [expected]
    assert failed["unavailable_sources"][0]["reason"] == "publication_failed"
    event_id = failed["unavailable_sources"][0]["recovery_event_id"]
    row = next(
        r
        for r in json.loads(command(root, "status").stdout)["publications"]
        if r["state"] == "failed"
    )
    assert row["plan"]["text_change"]["occurrence_continuity"] == CONTINUITY
    intended = json.loads(row["description"])
    mid = intended["mention_groups"]["g03"]["entity_id"]
    # Explicit same-intent forward completion, not regeneration of a new group ID.
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    check_addition(before, after)
    assert after["text_changes"][0]["added_groups"]["g03"]["entity_id"] == mid
    (event,) = after["recovery_events"]
    assert event["recovery_event_id"] == event_id and event["outcome"] == "restored"
    assert event["resolved_at"] and event["resolving_revision"] == 2
    assert len(event["recovery_attempts"]) == 1
