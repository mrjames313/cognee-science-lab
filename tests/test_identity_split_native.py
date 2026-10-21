"""Group split through native stores, reopen and forward recovery."""

import json
from uuid import UUID, uuid5

import pytest

from test_identity_native import command
from cognee_lab.identity.captured_chunks import FACT_TEXT
from cognee_lab.identity.group_regrouping import AFTER, REGROUPING


def check_split(root, before, after):
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    old = json.loads((root / "identity.json").read_text())
    identity_id = UUID(old["identity_data_id"])
    g04, g05 = (str(uuid5(identity_id, f"mention:{k}")) for k in ("g04", "g05"))
    retired = old["mention_groups"]["g01"]["entity_id"]
    assert a["state"] == "current"
    assert (
        a["saved_revision"] == a["registered_revision"] == a["verified_revision"] == 2
    )
    assert a["registered_matches_saved"]
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert a["unresolved_marker_present"] and a["unresolved_entity_present"]
    assert len(after["shared_variant"]["owners"]) == 2
    # The retired group's declaration, markers, resolution and old fact are gone;
    # the shared endpoint and the shared relationship text index remain.
    gone = a["resolved_group_retirement"]
    assert gone["mention_entity_id"] == retired
    for name in (
        "mention_entity_present",
        "mention_entity_indexed",
        "resolution_edge_present",
        "fact_edge_present",
        "fact_triplet_indexed",
        "resolution_triplet_indexed",
        "current_marker_present",
    ):
        assert gone[name] is False, name
    assert gone["fact_evidence_count"] == 0
    assert gone["shared_fact_endpoint_present"] and gone["shared_fact_endpoint_indexed"]
    assert gone["shared_relationship_text_indexed"]
    if "text_changes" in after:
        (change,) = after["text_changes"]
        assert change["occurrence_regrouping"] == REGROUPING
        assert change["occurrence_retention"] is None
        assert change["occurrence_continuity"] is None
        assert change["position_shift"] is None
        assert (
            change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
        )
        assert (
            change["evidence_uses_current_chunks"] and change["mention_ids_preserved"]
        )
        assert set(change["added_groups"]) == {"g04", "g05"}
        for key, expected in (("g04", g04), ("g05", g05)):
            group = change["added_groups"][key]
            assert group["entity_id"] == expected
            assert group["entity_present"] and group["entity_indexed"]
            assert group["marker_chunk_ids"]
            assert change["groups"][key]["previous_occurrences"] == []
        assert set(change["retired_groups"]) == {"g01"}
        old_group = change["retired_groups"]["g01"]
        assert old_group["entity_id"] == retired
        assert not (
            old_group["entity_present"]
            or old_group["entity_indexed"]
            or old_group["marker_present"]
        )
        assert [o["start"] for o in change["groups"]["g04"]["occurrences"]] == [53]
        assert [o["start"] for o in change["groups"]["g05"]["occurrences"]] == [111]
        assert (
            change["groups"]["g02"]["entity_id"]
            == old["mention_groups"]["g02"]["entity_id"]
        )
    facts = after["result"]["facts"]
    assert len(facts) == 2  # doc01's regenerated g05 fact and doc02's unchanged fact
    prior = next(
        f for f in before["result"]["facts"] if f["source_id"] == b["mention_entity_id"]
    )
    assert next(f for f in facts if f["source_id"] == b["mention_entity_id"]) == prior
    (new,) = [f for f in facts if f["source_id"] != b["mention_entity_id"]]
    assert new["source_id"] == g05
    assert new["relationship"] == "limits" and new["text"] == FACT_TEXT
    assert new["identity"]["assignment_id"] == "r05"
    assert new["identity"]["target_entity_id"] == (
        before["sources"]["doc01"]["resolution_target_entity_id"]
    )
    assert [o["text"] for o in new["identity"]["occurrences"]] == ["it"]
    original_data_id = next(
        f for f in before["result"]["facts"] if f["source_id"] == a["mention_entity_id"]
    )["evidence"][0]["data_id"]
    assert new["evidence"] and all(
        e["data_id"] == original_data_id for e in new["evidence"]
    )
    allowed = {c["chunk_id"]: c for c in a["chunk_mapping"]}
    for e in new["evidence"]:
        span = allowed[e["chunk_id"]]
        assert e["chunk_index"] == span["chunk_index"]
        assert e["text"] == AFTER[span["start"] : span["end"]]
    assert not any(f["source_id"] in (retired, g04) for f in facts)


@pytest.mark.integration
def test_native_split_group_reopen_and_reconcile(tmp_path):
    root = tmp_path / "split"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(root, "split-group", "--expected-revision", "1")
    after = json.loads((root / "group_split_result.json").read_text())
    check_split(root, before, after)
    assert after["recovery_events"] == []
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == after["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    check_split(root, before, reconciled)
    assert reconciled["sources"] == after["sources"]
    assert reconciled["recovery_events"] == []


@pytest.mark.integration
def test_native_split_recovers_the_exact_saved_groups(tmp_path):
    root = tmp_path / "split_failure"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root,
        "split-group",
        "--expected-revision",
        "1",
        "--fault-stage",
        "replace_published",
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
    assert row["plan"]["text_change"]["occurrence_regrouping"] == REGROUPING
    intended = json.loads(row["description"])
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    check_split(root, before, after)
    # Forward completion keeps the saved fresh IDs instead of choosing new ones.
    for key in ("g04", "g05"):
        assert (
            after["text_changes"][0]["added_groups"][key]["entity_id"]
            == intended["mention_groups"][key]["entity_id"]
        )
    (event,) = after["recovery_events"]
    assert event["recovery_event_id"] == event_id and event["outcome"] == "restored"
    assert event["resolved_at"] and event["resolving_revision"] == 2
    assert len(event["recovery_attempts"]) == 1
    assert event["recovery_attempts"][0]["outcome"] == "verified"
