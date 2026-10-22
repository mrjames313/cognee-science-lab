"""Changed interpretation through native stores: g01 retires, a fresh group follows."""

import json
from uuid import UUID

import pytest

from test_identity_native import command, doc_facts
from cognee_lab.identity.reinterpretation import ENTITY_MAP, UNRESOLVED_MAP
from cognee_lab.identity.validation import fresh_entity_id, fresh_mention_id

KEYS = {"new-entity": ("g07", "r07"), "unresolved": ("g08", "r08")}
MAPS = {"new-entity": ENTITY_MAP, "unresolved": UNRESOLVED_MAP}
RESULTS = {
    "new-entity": "reinterpretation_new_entity_result.json",
    "unresolved": "reinterpretation_unresolved_result.json",
}
OCCURRENCES = {
    "new-entity": [
        dict(start=49, end=70, text="the backup controller"),
        dict(start=97, end=99, text="it"),
    ],
    "unresolved": [
        dict(start=49, end=61, text="A controller"),
        dict(start=88, end=90, text="it"),
    ],
}


def check_reinterpreted(case, before, after):
    """doc01's g01 is gone, the fresh group is current and holds the regenerated
    fact, and doc02 is unchanged."""
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    assert (
        a["saved_revision"] == a["verified_revision"] == a["registered_revision"] == 2
    )
    assert a["registered_matches_saved"] and a["state"] == "current"
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    identity = UUID(a["identity_data_id"])
    key, rid = KEYS[case]
    occurrences = OCCURRENCES[case]
    (change,) = after["text_changes"]
    fresh = change["added_groups"][key]
    mention = str(fresh_mention_id(identity, 2, key))
    assert fresh["entity_id"] == mention != a["mention_entity_id"]
    assert fresh["entity_present"] and fresh["entity_indexed"]
    assert fresh["marker_chunk_ids"]
    fact = fresh["fact"]
    assert fact["present"] and fact["text"] == "it limits oscillations"
    assert fact["evidence_chunk_ids"]
    # The retired g01 leaves no fact, link, marker or node, and the shared
    # endpoint stays.
    gone = a["resolved_group_retirement"]
    assert not any(
        gone[k]
        for k in [
            "mention_entity_present",
            "mention_entity_indexed",
            "resolution_edge_present",
            "fact_edge_present",
            "current_marker_present",
        ]
    )
    assert gone["shared_fact_endpoint_present"] and gone["fact_evidence_count"] == 0
    # Neither the default query nor the Helios controller reaches doc01's fact.
    expected = doc_facts(before, "doc02")
    assert after["result"]["facts"] == expected
    assert after["queries"]["helios_controller"]["facts"] == expected
    assert after["recovery_events"] == []
    if case == "new-entity":
        backup = str(fresh_entity_id(identity, 2, rid))
        assert fresh["resolution"] == dict(
            status="accepted",
            target_entity_id=backup,
            target_present=True,
            target_indexed=True,
        )
        (answer,) = after["queries"]["backup_controller"]["facts"]
        assert answer["source_id"] == mention
        assert answer["identity"]["assignment_id"] == rid
        assert answer["identity"]["target_entity_id"] == backup
        assert answer["identity"]["occurrences"] == occurrences
        assert "it limits oscillations" in "".join(
            e["text"] for e in answer["evidence"]
        )
        assert after["queries"]["backup_controller"]["seed_entity_ids"] == [backup]
    else:
        assert fresh["resolution"] == dict(status="unresolved")
        # An unresolved mention is not reached through any reusable Entity.
        assert all(
            f["source_id"] != mention
            for q in after["queries"].values()
            for f in q["facts"]
        )
    assert change["occurrence_map"] == MAPS[case]
    assert change["position_shift"] is None
    assert change["groups"][key]["occurrences"] == occurrences
    retired = change["retired_groups"]["g01"]
    assert not (
        retired["entity_present"]
        or retired["entity_indexed"]
        or retired["marker_present"]
    )
    assert change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
    assert change["evidence_uses_current_chunks"]
    assert set(change["groups"]) == {"g02", key}


@pytest.mark.integration
@pytest.mark.parametrize("case", ["new-entity", "unresolved"])
def test_native_reinterpretation_reopen_and_reconcile(tmp_path, case):
    root = tmp_path / "reinterpretation"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(root, f"reinterpret-{case}", "--expected-revision", "1")
    after = json.loads((root / RESULTS[case]).read_text())
    check_reinterpreted(case, before, after)
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == after["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    assert reconciled["sources"] == after["sources"]
    assert reconciled["recovery_events"] == []
    assert reconciled["result"]["facts"] == after["result"]["facts"]


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["text_chunks", "replace_published"])
def test_native_reinterpretation_recovers_after_an_injected_failure(tmp_path, stage):
    root = tmp_path / "reinterpretation_failure"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root,
        "reinterpret-new-entity",
        "--expected-revision",
        "1",
        "--fault-stage",
        stage,
        expect=1,
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert query["facts"] == doc_facts(before, "doc02")
    assert query["unavailable_sources"][0]["reason"] == "publication_failed"
    failed = next(
        r
        for r in json.loads(command(root, "status").stdout)["publications"]
        if r["state"] == "failed"
    )
    assert failed["plan"]["text_change"]["occurrence_map"] == ENTITY_MAP
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    (event,) = reconciled["recovery_events"]
    assert event["outcome"] == "restored" and event["resolving_revision"] == 2
    assert event["resolved_at"] and len(event["recovery_attempts"]) == 1
    assert reconciled["sources"]["doc01"]["state"] == "current"
    assert reconciled["sources"]["doc02"] == before["sources"]["doc02"]
    # The regenerated fact is reachable through the new Entity after recovery.
    identity = UUID(reconciled["sources"]["doc01"]["identity_data_id"])
    backup = str(fresh_entity_id(identity, 2, "r07"))
    answer = json.loads(
        command(
            root, "retrieve", "--query", "What does Backup controller limit?"
        ).stdout
    )
    assert [f["identity"]["target_entity_id"] for f in answer["facts"]] == [backup]
