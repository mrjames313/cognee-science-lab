"""Real deletion of local resolution/fact/evidence with independent survival."""

import json

import pytest

from test_identity_native import command


def check_retired(before, after):
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    assert a["state"] == "current"
    assert (
        a["saved_revision"] == a["registered_revision"] == a["verified_revision"] == 2
    )
    assert a["registered_matches_saved"]
    assert a["resolution_target_entity_id"] is None
    assert not a["original_marker_present"] and not a["original_fact_present"]
    assert not a["original_fact_owned_by_chunk"] and not a["original_evidence_present"]
    assert a["unresolved_entity_present"] and a["unresolved_marker_present"]
    assert a["mention_marker_chunk_ids"] == a["fact_evidence_chunk_ids"] == []
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    other = next(
        f for f in before["result"]["facts"] if f["source_id"] == b["mention_entity_id"]
    )
    assert after["result"]["facts"] == [other]
    assert after["result"]["unavailable_sources"] == []
    checks = a["resolved_group_retirement"]
    for key in [
        "mention_entity_present",
        "mention_entity_indexed",
        "resolution_edge_present",
        "fact_edge_present",
        "fact_evidence_count",
        "fact_triplet_indexed",
        "resolution_triplet_indexed",
        "current_marker_present",
    ]:
        assert not checks[key], key
    for key in [
        "shared_fact_endpoint_present",
        "shared_fact_endpoint_indexed",
        "shared_relationship_text_indexed",
    ]:
        assert checks[key], key
    assert len(after["shared_variant"]["owners"]) == 2
    own = next(
        c
        for c in after["shared_variant"]["contributions"]
        if c["identity_data_id"] == a["identity_data_id"]
    )
    assert own["revision"] == 2
    assert (
        next(
            c
            for c in before["shared_variant"]["contributions"]
            if c["identity_data_id"] == b["identity_data_id"]
        )
        in after["shared_variant"]["contributions"]
    )
    if "text_changes" in after:
        change = after["text_changes"][0]
        assert change["occurrence_retention"] == {"g01": [], "g02": [0]}
        assert (
            change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
        )
        assert (
            change["evidence_uses_current_chunks"]
            and change["evidence_chunk_ids"] == []
        )
        assert not any(
            change["retired_groups"]["g01"][k]
            for k in ["entity_present", "entity_indexed", "marker_present"]
        )


@pytest.mark.integration
def test_native_resolved_retirement_reopen_reconcile_and_withdraw(tmp_path):
    root = tmp_path / "resolved"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(root, "retire-resolved-group", "--expected-revision", "1")
    after = json.loads((root / "resolved_retirement_result.json").read_text())
    check_retired(before, after)
    assert after["recovery_events"] == []
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == after["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    check_retired(before, reconciled)
    assert reconciled["sources"] == after["sources"]
    command(root, "withdraw", "--source", "doc01")
    withdrawn = json.loads((root / "multisource_result.json").read_text())
    assert withdrawn["result"]["facts"] == after["result"]["facts"]
    assert withdrawn["sources"]["doc02"] == before["sources"]["doc02"]
    assert len(withdrawn["shared_variant"]["owners"]) == 1
    assert not withdrawn["sources"]["doc01"]["resolved_group_retirement"][
        "mention_entity_present"
    ]


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["text_chunks", "replace_published"])
def test_native_interrupted_resolved_retirement_uses_exact_plan(tmp_path, stage):
    root = tmp_path / "resolved_failure"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root,
        "retire-resolved-group",
        "--expected-revision",
        "1",
        "--fault-stage",
        stage,
        expect=1,
    )
    withheld = json.loads(command(root, "retrieve").stdout)
    assert len(withheld["facts"]) == 1
    assert withheld["facts"][0] == next(
        f
        for f in before["result"]["facts"]
        if f["source_id"] == before["sources"]["doc02"]["mention_entity_id"]
    )
    event_id = withheld["unavailable_sources"][0]["recovery_event_id"]
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    check_retired(before, after)
    (event,) = after["recovery_events"]
    assert event["recovery_event_id"] == event_id
    assert event["outcome"] == "restored" and event["resolving_revision"] == 2
    assert event["resolved_at"] and len(event["recovery_attempts"]) == 1
