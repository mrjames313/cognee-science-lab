"""One edit that removes, keeps and adds occurrences, through native stores."""

import json

import pytest

from test_identity_native import command
from cognee_lab.identity.occurrence_fixture import MIXED_MAP


def check_mixed(before, after):
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
            assert f["identity"]["occurrences"] == [
                dict(start=46, end=48, text="it"),
                dict(start=86, end=100, text="the controller"),
            ]
            assert "it limits oscillations" in "".join(e["text"] for e in f["evidence"])
        else:
            assert f == old
    assert not a["unresolved_entity_present"] and not a["unresolved_marker_present"]
    if "text_changes" in after:
        (change,) = after["text_changes"]
        assert change["position_shift"] is None
        assert change["occurrence_map"] == MIXED_MAP
        assert change["added_groups"] == {}
        assert change["groups"]["g01"]["occurrences"] == [
            dict(start=46, end=48, text="it"),
            dict(start=86, end=100, text="the controller"),
        ]
        assert (
            change["retired_chunks_absent"]
            and change["retired_chunk_vectors_absent"]
            and change["mention_ids_preserved"]
            and change["evidence_uses_current_chunks"]
        )
        retired = change["retired_groups"]["g02"]
        assert not (
            retired["entity_present"]
            or retired["entity_indexed"]
            or retired["marker_present"]
        )


@pytest.mark.integration
def test_native_mixed_revision_reopen_and_reconcile(tmp_path):
    root = tmp_path / "mixed"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(root, "revise-occurrences", "--expected-revision", "1")
    after = json.loads((root / "occurrence_mix_result.json").read_text())
    check_mixed(before, after)
    assert after["recovery_events"] == []
    assert (
        json.loads(command(root, "retrieve").stdout)["facts"]
        == after["result"]["facts"]
    )
    command(root, "reconcile", "--source", "doc01")
    reconciled = json.loads((root / "multisource_result.json").read_text())
    check_mixed(before, reconciled)
    assert reconciled["sources"] == after["sources"]


@pytest.mark.integration
def test_native_mixed_revision_recovers_after_an_injected_failure(tmp_path):
    root = tmp_path / "mixed_failure"
    command(root, "chunked-fixture")
    before = json.loads((root / "multisource_result.json").read_text())
    command(
        root,
        "revise-occurrences",
        "--expected-revision",
        "1",
        "--fault-stage",
        "replace_published",
        expect=1,
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert len(query["facts"]) == 1
    assert query["unavailable_sources"][0]["reason"] == "publication_failed"
    failed = next(
        r
        for r in json.loads(command(root, "status").stdout)["publications"]
        if r["state"] == "failed"
    )
    assert failed["plan"]["text_change"]["occurrence_map"] == MIXED_MAP
    command(root, "reconcile", "--source", "doc01")
    after = json.loads((root / "multisource_result.json").read_text())
    check_mixed(before, after)
    (event,) = after["recovery_events"]
    assert event["outcome"] == "restored" and event["resolving_revision"] == 2
    assert event["resolved_at"] and len(event["recovery_attempts"]) == 1
