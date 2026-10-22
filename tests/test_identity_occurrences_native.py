"""Occurrence continuity and empty-group retirement through native stores."""

import json

import pytest

from test_identity_native import command
from cognee_lab.identity.occurrence_fixture import REMOVAL_MAP

IT = dict(start=46, end=48, text="it")


def check_continuing_g01(
    before, after, occurrences=(IT,), occurrence_map=REMOVAL_MAP, *, with_change=True
):
    """g01 continues with the given occurrences and its fact; g02 retires.

    A healthy reconcile's snapshot reports no text change, so pass
    with_change=False for it."""
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    assert (
        a["saved_revision"] == a["verified_revision"] == a["registered_revision"] == 2
    )
    assert a["registered_matches_saved"] and a["state"] == "current"
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert len(after["result"]["facts"]) == 2
    oldfacts = {f["source_id"]: f for f in before["result"]["facts"]}
    for f in after["result"]["facts"]:
        old = oldfacts[f["source_id"]]
        if f["source_id"] == a["mention_entity_id"]:
            assert f["edge_id"] == old["edge_id"]
            assert f["identity"]["occurrences"] == list(occurrences)
            assert "it limits oscillations" in "".join(e["text"] for e in f["evidence"])
        else:
            assert f == old
    assert not a["unresolved_entity_present"] and not a["unresolved_marker_present"]
    assert (
        a["original_marker_present"]
        and a["original_fact_owned_by_chunk"]
        and a["original_evidence_present"]
    )
    assert len(after["shared_variant"]["owners"]) == 2
    assert (
        next(
            c
            for c in before["shared_variant"]["contributions"]
            if c["identity_data_id"] == b["identity_data_id"]
        )
        in after["shared_variant"]["contributions"]
    )
    if not with_change:
        assert "text_changes" not in after
        return
    (change,) = after["text_changes"]
    assert change["position_shift"] is None
    assert change["occurrence_map"] == occurrence_map
    assert change["added_groups"] == {}
    assert change["groups"]["g01"]["occurrences"] == list(occurrences)
    assert change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
    assert change["mention_ids_preserved"] and change["evidence_uses_current_chunks"]
    retired = change["retired_groups"]["g02"]
    assert not (
        retired["entity_present"]
        or retired["entity_indexed"]
        or retired["marker_present"]
    )


@pytest.mark.integration
def test_native_remove_partial_and_empty_group_reopen_reconcile_withdraw(tmp_path):
    root = tmp_path / "occurrences"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(root, "remove-occurrences", "--expected-revision", "1")
    after = json.loads((root / "occurrence_revision_result.json").read_text())
    check_continuing_g01(before, after)
    assert after["recovery_events"] == []
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == after["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    check_continuing_g01(before, reconciled, with_change=False)
    # A healthy reconcile must not resurrect the retired group from baseline files.
    assert reconciled["sources"] == after["sources"]
    command(root, "withdraw", "--source", "doc01")
    withdrawn = json.loads((root / "multisource_result.json").read_text())
    assert len(withdrawn["result"]["facts"]) == 1
    assert not withdrawn["sources"]["doc01"]["unresolved_entity_present"]
    assert withdrawn["sources"]["doc02"] == before["sources"]["doc02"]


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["text_chunks", "replace_published"])
def test_native_occurrence_removal_recovers_exact_continuity_and_retirement(
    tmp_path, stage
):
    root = tmp_path / "removal_failure"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root,
        "remove-occurrences",
        "--expected-revision",
        "1",
        "--fault-stage",
        stage,
        expect=1,
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert len(query["facts"]) == 1
    assert query["facts"][0] == next(
        f
        for f in before["result"]["facts"]
        if f["source_id"] == before["sources"]["doc02"]["mention_entity_id"]
    )
    assert query["unavailable_sources"][0]["reason"] == "publication_failed"
    failed = next(
        r
        for r in json.loads(command(root, "status").stdout)["publications"]
        if r["state"] == "failed"
    )
    assert failed["plan"]["text_change"]["occurrence_map"] == REMOVAL_MAP
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    check_continuing_g01(before, after)
    (event,) = after["recovery_events"]
    assert event["outcome"] == "restored" and event["resolving_revision"] == 2
    assert event["resolved_at"] and len(event["recovery_attempts"]) == 1
