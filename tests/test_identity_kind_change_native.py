"""Kind changes with unchanged text through native stores, on one chained root."""

import json

import pytest

from test_identity_native import command
from cognee_lab.identity.kind_change import HC_ID, TO_MENTION_MAP, TO_REUSABLE_MAP

TO_MENTION = "kind_change_to_mention_result.json"
TO_REUSABLE = "kind_change_to_reusable_result.json"


def doc_facts(result, before, doc):
    mention = before["sources"][doc]["mention_entity_id"]
    return [f for f in result["facts"] if f["source_id"] == mention]


def check_common(before, after, revision):
    """doc01 is current at the revision, doc02 is untouched and the rebuild
    left no incident, no stale chunk and exactly one HC Entity."""
    a = after["sources"]["doc01"]
    assert a["saved_revision"] == a["verified_revision"] == a["registered_revision"]
    assert a["saved_revision"] == revision and a["state"] == "current"
    assert a["registered_matches_saved"]
    assert a["mention_entity_id"] == before["sources"]["doc01"]["mention_entity_id"]
    assert after["sources"]["doc02"] == before["sources"]["doc02"]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert after["recovery_events"] == []
    assert after["hc_entity"]["entity_ids_named_hc"] == [HC_ID]
    assert after["hc_entity"]["present"] and after["hc_entity"]["indexed"]
    (change,) = after["text_changes"]
    assert change["position_shift"] is None and change["text_length_delta"] == 0
    assert change["previous_text_sha256"] == change["text_sha256"]
    assert change["previous_chunk_ids"] == change["chunk_ids"]
    assert change["retired_chunks_absent"] and change["retired_chunk_vectors_absent"]
    assert change["evidence_uses_current_chunks"] and change["mention_ids_preserved"]
    # Equal texts rebuild every chunk with the same content-derived ID.
    assert change["content_ids_present_in_both"] == change["chunk_ids"]
    return change


def check_mention(before, after):
    change = check_common(before, after, 2)
    assert change["occurrence_map"] == TO_MENTION_MAP
    assert change["retired_groups"] == {}
    added = change["added_groups"]["g03"]
    assert added["entity_present"] and added["entity_indexed"]
    assert len(added["marker_chunk_ids"]) == 1
    assert change["groups"]["g03"]["occurrences"] == [dict(start=19, end=21, text="HC")]
    # The shared HC edge keeps only doc02's contribution and owner; the HC
    # Entity survives because doc02 owns it.
    shared = after["shared_variant"]
    doc02 = before["sources"]["doc02"]["identity_data_id"]
    assert shared["present"] and len(shared["owners"]) == 1
    assert [c["identity_data_id"] for c in shared["contributions"]] == [doc02]
    assert after["hc_entity"]["owner_count"] == 1
    # HC no longer reaches doc01. The Helios controller still does, with the
    # same fact and with the facts generated again from the rebuilt chunks.
    assert after["queries"]["hc"]["facts"] == doc_facts(
        after["queries"]["hc"], before, "doc02"
    )
    helios = after["queries"]["helios_controller"]["facts"]
    old = {f["source_id"]: f for f in before["result"]["facts"]}
    assert {f["source_id"] for f in helios} == set(old)
    for fact in helios:
        assert fact == old[fact["source_id"]]


def check_reusable(before, after):
    change = check_common(before, after, 3)
    assert change["occurrence_map"] == TO_REUSABLE_MAP
    assert change["added_groups"] == {}
    retired = change["retired_groups"]["g03"]
    assert not (
        retired["entity_present"]
        or retired["entity_indexed"]
        or retired["marker_present"]
    )
    shared = after["shared_variant"]
    assert len(shared["owners"]) == 2
    assert {c["assignment_id"] for c in shared["contributions"]} == {"v01", "v02"}
    assert after["hc_entity"]["owner_count"] == 2
    # HC reaches both documents' facts again, as at revision 1.
    assert after["queries"]["hc"]["facts"] == before["result"]["facts"]
    assert after["queries"]["helios_controller"]["facts"] == before["result"]["facts"]
    assert after["result"]["facts"] == before["result"]["facts"]


@pytest.mark.integration
def test_native_kind_change_there_and_back_with_reopen_and_reconcile(tmp_path):
    root = tmp_path / "kind_change"
    command(root, "chunked-fixture")
    baseline = json.loads((root / "multisource_result.json").read_text())
    command(
        root, "change-kind", "--direction", "to-mention", "--expected-revision", "1"
    )
    mention = json.loads((root / TO_MENTION).read_text())
    check_mention(baseline, mention)
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == mention["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    assert reconciled["sources"] == mention["sources"]
    assert reconciled["result"]["facts"] == mention["result"]["facts"]

    command(
        root, "change-kind", "--direction", "to-reusable", "--expected-revision", "2"
    )
    reusable = json.loads((root / TO_REUSABLE).read_text())
    check_reusable(baseline, reusable)
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == reusable["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    assert reconciled["sources"] == reusable["sources"]
    assert reconciled["result"]["facts"] == reusable["result"]["facts"]


@pytest.mark.integration
def test_native_kind_change_refuses_the_wrong_root_or_revision(tmp_path):
    root = tmp_path / "kind_change_scope"
    command(root, "chunked-fixture")
    refused = command(
        root,
        "change-kind",
        "--direction",
        "to-reusable",
        "--expected-revision",
        "1",
        expect=1,
    )
    assert "requires doc01 produced by to-mention" in refused.stdout
    command(
        root, "change-kind", "--direction", "to-mention", "--expected-revision", "1"
    )
    for direction, revision in [("to-mention", "2"), ("to-reusable", "1")]:
        command(
            root,
            "change-kind",
            "--direction",
            direction,
            "--expected-revision",
            revision,
            expect=1,
        )
    status = json.loads(command(root, "status").stdout)
    assert [r["revision"] for r in status["publications"]].count(2) == 1


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["text_chunks", "replace_published"])
def test_native_kind_change_recovers_after_an_injected_failure(tmp_path, stage):
    root = tmp_path / "kind_change_failure"
    command(root, "chunked-fixture")
    baseline = json.loads((root / "multisource_result.json").read_text())
    command(
        root,
        "change-kind",
        "--direction",
        "to-mention",
        "--expected-revision",
        "1",
        "--fault-stage",
        stage,
        expect=1,
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert query["facts"] == doc_facts(query, baseline, "doc02")
    assert query["unavailable_sources"][0]["reason"] == "publication_failed"
    failed = next(
        r
        for r in json.loads(command(root, "status").stdout)["publications"]
        if r["state"] == "failed"
    )
    assert failed["plan"]["text_change"]["occurrence_map"] == TO_MENTION_MAP
    assert failed["plan"]["text_change"]["previous_text"] == (
        failed["plan"]["text_change"]["text"]
    )
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    (event,) = after["recovery_events"]
    assert event["outcome"] == "restored" and event["resolving_revision"] == 2
    assert event["resolved_at"] and len(event["recovery_attempts"]) == 1
    assert after["sources"]["doc01"]["state"] == "current"
    assert after["sources"]["doc02"] == baseline["sources"]["doc02"]
    helios = json.loads(
        command(
            root, "retrieve", "--query", "What does Helios controller limit?"
        ).stdout
    )
    assert len(helios["facts"]) == 2


@pytest.mark.integration
def test_native_mention_to_reusable_recovers_after_an_injected_failure(tmp_path):
    root = tmp_path / "kind_change_back_failure"
    command(root, "chunked-fixture")
    baseline = json.loads((root / "multisource_result.json").read_text())
    command(
        root, "change-kind", "--direction", "to-mention", "--expected-revision", "1"
    )
    command(
        root,
        "change-kind",
        "--direction",
        "to-reusable",
        "--expected-revision",
        "2",
        "--fault-stage",
        "replace_published",
        expect=1,
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert query["facts"] == doc_facts(query, baseline, "doc02")
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    (event,) = [e for e in after["recovery_events"] if e["resolved_at"]]
    assert event["outcome"] == "restored" and event["resolving_revision"] == 3
    assert after["sources"]["doc01"]["saved_revision"] == 3
    hc = json.loads(command(root, "retrieve").stdout)
    assert hc["facts"] == baseline["result"]["facts"]
