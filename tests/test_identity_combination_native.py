"""Group combination through native stores, reopen and forward recovery."""

import json
from uuid import UUID, uuid5

import pytest

from test_identity_native import command
from cognee_lab.identity.captured_chunks import FACT_TEXT
from cognee_lab.identity.group_regrouping import COMBINE_AFTER, COMBINE_REGROUPING

G01 = "233cb019-3986-5864-88bc-91f334a64372"


def split_root(root):
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(root, "split-group", "--expected-revision", "1")
    return before


def check_combination(root, before, after):
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    old = json.loads((root / "identity.json").read_text())
    identity_id = UUID(old["identity_data_id"])
    g04, g05, g06 = (
        str(uuid5(identity_id, f"mention:{k}")) for k in ("g04", "g05", "g06")
    )
    assert g06 == "3bda245c-19be-5f6e-b722-3785f6bc9447"
    assert a["state"] == "current"
    assert (
        a["saved_revision"] == a["registered_revision"] == a["verified_revision"] == 3
    )
    assert a["registered_matches_saved"]
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert a["unresolved_marker_present"] and a["unresolved_entity_present"]
    assert len(after["shared_variant"]["owners"]) == 2
    # g01 stays gone and g04 and g05 leave with their markers, links and the old fact.
    assert a["resolved_group_retirement"]["mention_entity_id"] == G01
    gone = {"g01": a["resolved_group_retirement"], **a["combined_group_retirement"]}
    assert set(gone) == {"g01", "g04", "g05"}
    for key, mention in (("g01", G01), ("g04", g04), ("g05", g05)):
        checks = gone[key]
        assert checks["mention_entity_id"] == mention
        for name in (
            "mention_entity_present",
            "mention_entity_indexed",
            "resolution_edge_present",
            "fact_edge_present",
            "fact_triplet_indexed",
            "resolution_triplet_indexed",
            "current_marker_present",
        ):
            assert checks[name] is False, (key, name)
        assert checks["fact_evidence_count"] == 0
        assert checks["shared_fact_endpoint_present"]
        assert checks["shared_fact_endpoint_indexed"]
        assert checks["shared_relationship_text_indexed"]
    if "text_changes" in after:
        (change,) = after["text_changes"]
        assert change["occurrence_regrouping"] == COMBINE_REGROUPING
        assert change["occurrence_retention"] is None
        assert change["occurrence_continuity"] is None
        assert change["position_shift"] is None
        assert (
            change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
        )
        assert (
            change["evidence_uses_current_chunks"] and change["mention_ids_preserved"]
        )
        assert set(change["added_groups"]) == {"g06"}
        group = change["added_groups"]["g06"]
        assert group["entity_id"] == g06
        assert group["entity_present"] and group["entity_indexed"]
        assert group["marker_chunk_ids"]
        assert change["groups"]["g06"]["previous_occurrences"] == []
        assert set(change["retired_groups"]) == {"g04", "g05"}
        for key, mention in (("g04", g04), ("g05", g05)):
            retired = change["retired_groups"][key]
            assert retired["entity_id"] == mention
            assert not (
                retired["entity_present"]
                or retired["entity_indexed"]
                or retired["marker_present"]
            )
        assert [o["start"] for o in change["groups"]["g06"]["occurrences"]] == [49, 109]
        assert [o["start"] for o in change["groups"]["g02"]["occurrences"]] == [33]
        assert (
            change["groups"]["g02"]["entity_id"]
            == old["mention_groups"]["g02"]["entity_id"]
        )
    facts = after["result"]["facts"]
    assert len(facts) == 2  # doc01's regenerated g06 fact and doc02's unchanged fact
    prior = next(
        f for f in before["result"]["facts"] if f["source_id"] == b["mention_entity_id"]
    )
    assert next(f for f in facts if f["source_id"] == b["mention_entity_id"]) == prior
    (new,) = [f for f in facts if f["source_id"] != b["mention_entity_id"]]
    assert new["source_id"] == g06
    assert new["relationship"] == "limits" and new["text"] == FACT_TEXT
    assert new["identity"]["assignment_id"] == "r06"
    assert new["identity"]["target_entity_id"] == (
        before["sources"]["doc01"]["resolution_target_entity_id"]
    )
    assert [o["text"] for o in new["identity"]["occurrences"]] == [
        "the controller",
        "it",
    ]
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
        assert e["text"] == COMBINE_AFTER[span["start"] : span["end"]]
    assert not any(f["source_id"] in (G01, g04, g05) for f in facts)


@pytest.mark.integration
def test_native_combine_groups_reopen_and_reconcile(tmp_path):
    root = tmp_path / "combine"
    before = split_root(root)
    command(root, "combine-groups", "--expected-revision", "2")
    after = json.loads((root / "group_combination_result.json").read_text())
    check_combination(root, before, after)
    assert after["recovery_events"] == []
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == after["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    check_combination(root, before, reconciled)
    assert reconciled["sources"] == after["sources"]
    assert reconciled["recovery_events"] == []


@pytest.mark.integration
def test_native_combine_refuses_a_root_that_was_not_split(tmp_path):
    root = tmp_path / "unsplit"
    command(root, "chunked-fixture")
    refused = command(root, "combine-groups", "--expected-revision", "1", expect=1)
    assert "requires doc01 produced by split-group" in refused.stdout
    status = json.loads(command(root, "status").stdout)
    assert [p["revision"] for p in status["publications"]] == [1, 1]
    assert all(p["state"] == "current" for p in status["publications"])


@pytest.mark.integration
def test_native_combine_recovers_the_exact_saved_group(tmp_path):
    root = tmp_path / "combine_failure"
    before = split_root(root)
    command(
        root,
        "combine-groups",
        "--expected-revision",
        "2",
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
    assert row["revision"] == 3 and row["verified_revision"] == 2
    assert row["plan"]["text_change"]["occurrence_regrouping"] == COMBINE_REGROUPING
    intended = json.loads(row["description"])
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    check_combination(root, before, after)
    # Forward completion keeps the saved fresh ID instead of choosing a new one.
    assert (
        after["text_changes"][0]["added_groups"]["g06"]["entity_id"]
        == intended["mention_groups"]["g06"]["entity_id"]
    )
    (event,) = after["recovery_events"]
    assert event["recovery_event_id"] == event_id and event["outcome"] == "restored"
    assert event["resolved_at"] and event["resolving_revision"] == 3
    assert len(event["recovery_attempts"]) == 1
    assert event["recovery_attempts"][0]["outcome"] == "verified"
