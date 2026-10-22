"""One edit that removes, keeps and adds occurrences, through native stores."""

import json

import pytest

from test_identity_native import command
from test_identity_occurrences_native import IT, check_continuing_g01
from cognee_lab.identity.occurrence_fixture import MIXED_MAP

STARTUP = dict(start=86, end=100, text="the controller")


def check_mixed(before, after, *, with_change=True):
    check_continuing_g01(
        before, after, (IT, STARTUP), MIXED_MAP, with_change=with_change
    )
    # The added occurrence lies in a chunk that holds no fact evidence, so
    # g01's marker chunks and fact chunks differ.
    doc01 = after["sources"]["doc01"]
    markers, facts = doc01["mention_marker_chunk_ids"], doc01["fact_evidence_chunk_ids"]
    assert len(markers) == 2 and len(facts) == 1
    assert set(facts) < set(markers)


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
    check_mixed(before, reconciled, with_change=False)
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
