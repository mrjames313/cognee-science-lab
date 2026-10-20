"""Captured semantics across real native chunk boundaries and source revisions."""

import json

import pytest

from test_identity_native import command
from cognee_lab.identity.captured_chunks import FACT_TEXT

PREFIX = "Δ review: "


def check_chunks(result):
    assert len(result["result"]["facts"]) == 2
    for label, source in result["sources"].items():
        assert source["chunk_count"] > 1
        assert source["original_marker_present"]
        assert (
            source["original_fact_owned_by_chunk"]
            and source["original_evidence_present"]
        )
        mapping = source["chunk_mapping"]
        assert [c["chunk_index"] for c in mapping] == list(range(len(mapping)))
        assert mapping[0]["start"] == 0
        assert all(a["end"] == b["start"] for a, b in zip(mapping, mapping[1:]))
        marker_ids = set(source["mention_marker_chunk_ids"])
        support_ids = set(source["fact_evidence_chunk_ids"])
        assert len(marker_ids) >= 2 and len(support_ids) == 2
        assert support_ids - marker_ids  # fact continuation with no mention marker
        assert marker_ids - support_ids  # another occurrence is not this fact's support
        for c in mapping:
            assert c["mention_marker_present"] == (c["chunk_id"] in marker_ids)
            assert c["owns_captured_fact"] == (c["chunk_id"] in support_ids)
            assert c["evidence_present"] == (c["chunk_id"] in support_ids)
        fact = next(
            f
            for f in result["result"]["facts"]
            if f["source_id"] == source["mention_entity_id"]
        )
        assert {e["chunk_id"] for e in fact["evidence"]} == support_ids
        ordered = sorted(fact["evidence"], key=lambda e: e["chunk_index"])
        assert FACT_TEXT in "".join(e["text"] for e in ordered)
        for e in ordered:
            assert e["chunk_index"] == next(
                c["chunk_index"] for c in mapping if c["chunk_id"] == e["chunk_id"]
            )


def check_edit(before, after, revision=2):
    check_chunks(after)
    a, b = after["sources"]["doc01"], after["sources"]["doc02"]
    assert (
        a["saved_revision"]
        == a["verified_revision"]
        == a["registered_revision"]
        == revision
    )
    assert b == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert len(after["shared_variant"]["owners"]) == 2
    old_other = next(
        c
        for c in before["shared_variant"]["contributions"]
        if c["identity_data_id"] == b["identity_data_id"]
    )
    assert old_other in after["shared_variant"]["contributions"]
    assert (
        next(
            c
            for c in after["shared_variant"]["contributions"]
            if c["identity_data_id"] == a["identity_data_id"]
        )["revision"]
        == revision
    )
    oldfacts = {f["source_id"]: f for f in before["result"]["facts"]}
    for fact in after["result"]["facts"]:
        old = oldfacts[fact["source_id"]]
        assert fact["edge_id"] == old["edge_id"]
        if fact["source_id"] == a["mention_entity_id"]:
            for o, n in zip(
                old["identity"]["occurrences"], fact["identity"]["occurrences"]
            ):
                assert n["start"] == o["start"] + len(PREFIX)
                assert n["end"] == o["end"] + len(PREFIX)
        else:
            assert fact == old
    assert a["chunk_mapping"] != before["sources"]["doc01"]["chunk_mapping"]
    if "text_changes" in after:
        change = after["text_changes"][0]
        assert change["chunk_budget"] == 9 and change["position_shift"] == 10
        assert (
            change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
        )
        assert (
            change["mention_ids_preserved"] and change["evidence_uses_current_chunks"]
        )


@pytest.mark.integration
def test_native_multichunk_edit_reconcile_repeated_edit_and_withdraw(tmp_path):
    root = tmp_path / "chunked"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    check_chunks(before)
    assert before["sources"]["doc01"]["chunk_count"] == 6
    command(root, "edit-text", "--expected-revision", "1")
    after = json.loads((root / "text_revision_result.json").read_text())
    check_edit(before, after)
    # After the edit 'the controller' itself crosses a native chunk boundary.
    change = after["text_changes"][0]
    assert len(change["groups"]["g01"]["previous_marker_chunk_ids"]) == 2
    assert len(change["groups"]["g01"]["marker_chunk_ids"]) == 3
    assert change["content_ids_present_in_both"]
    assert after["recovery_events"] == []
    query = json.loads(command(root, "retrieve").stdout)
    assert query["facts"] == after["result"]["facts"]
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    assert reconciled["result"]["facts"] == after["result"]["facts"]
    command(root, "edit-text", "--expected-revision", "2")
    again = json.loads((root / "text_revision_result.json").read_text())
    check_edit(after, again, revision=3)
    previous_indexes = {
        c["chunk_id"]: c["chunk_index"]
        for c in after["sources"]["doc01"]["chunk_mapping"]
    }
    assert any(
        c["chunk_id"] in previous_indexes
        and c["chunk_index"] != previous_indexes[c["chunk_id"]]
        for c in again["sources"]["doc01"]["chunk_mapping"]
    )
    assert again["recovery_events"] == []
    command(root, "withdraw", "--source", "doc01")
    withdrawn = json.loads((root / "multisource_result.json").read_text())
    assert len(withdrawn["result"]["facts"]) == 1
    assert withdrawn["sources"]["doc01"]["original_fact_owned_by_chunk"]
    assert withdrawn["sources"]["doc01"]["original_evidence_present"]
    assert withdrawn["sources"]["doc01"]["original_marker_present"]


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["text_chunks", "replace_published"])
def test_native_multichunk_recovery_keeps_complete_fact_evidence(tmp_path, stage):
    root = tmp_path / "chunked_failure"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root, "edit-text", "--expected-revision", "1", "--fault-stage", stage, expect=1
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert len(query["facts"]) == 1 and len(query["facts"][0]["evidence"]) == 2
    assert (
        query["facts"][0]["source_id"]
        == before["sources"]["doc02"]["mention_entity_id"]
    )
    assert query["unavailable_sources"][0]["reason"] == "publication_failed"
    status = json.loads(command(root, "status").stdout)
    failed = next(r for r in status["publications"] if r["state"] == "failed")
    assert failed["plan"]["text_change"]["chunk_budget"] == 9
    command(root, "reconcile", "--source", "doc01")
    recovered = json.loads((root / "multisource_result.json").read_text())
    check_edit(before, recovered)
    (event,) = recovered["recovery_events"]
    assert (
        event["outcome"] == "restored"
        and event["resolved_at"]
        and event["resolving_revision"] == 2
    )
    assert recovered["result"]["unavailable_sources"] == []
