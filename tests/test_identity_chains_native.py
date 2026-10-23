"""Saved-record chains through real configured stores in fresh subprocesses."""

import json

import pytest

from test_identity_dependencies_native import printed, run, unavailable, withheld
from test_identity_native import command

D03 = "bbbc442e-0647-552e-bb54-071604d213fa"


def refused(root, *args):
    """A refused command's error report: its last line of output."""
    out = command(root, *args, expect=1).stdout
    return json.loads(out.strip().splitlines()[-1])


@pytest.mark.integration
def test_native_chain_withholds_down_and_releases_with_the_upstream(tmp_path):
    root = tmp_path / "chain"
    base = run(root, "glossary-fixture", "--chain")
    assert base["sources"]["doc03"]["identity_data_id"] == D03
    assert base["withheld_decisions"] == []

    edit = run(
        root,
        *("edit-glossary", "--source", "glossary", "--case", "cosmetic"),
        *("--expected-revision", "1"),
    )
    assert withheld(edit) == {
        ("r01", "input_changed", "refresh_needed"),
        ("v01", "input_changed", "refresh_needed"),
        ("c01", "input_changed", "upstream_withheld"),
        ("c02", "input_changed", "upstream_withheld"),
    }
    assert [d["assignment_id"] for d in edit["refresh_needed"]] == ["r01", "v01"]
    refusal = refused(
        root,
        *("reconfirm", "--source", "doc03", "--decision", "c01"),
        *("--expected-revision", "1"),
    )
    assert "waits for a record it cites" in refusal["message"]

    run(root, "reconfirm", "--decision", "r01", "--expected-revision", "1")
    done = run(root, "reconfirm", "--decision", "v01", "--expected-revision", "2")
    assert done["withheld_decisions"] == []
    assert done["sources"]["doc03"]["saved_revision"] == 1
    assert unavailable(done["result"]) == []


@pytest.mark.integration
def test_native_chain_replacements_upstream(tmp_path):
    root = tmp_path / "chain"
    run(root, "glossary-fixture", "--chain")
    run(
        root,
        *("edit-glossary", "--source", "glossary", "--case", "substantive"),
        *("--expected-revision", "1"),
    )
    keyed = run(
        root, "replace-decision", "--decision", "v01", "--expected-revision", "1"
    )
    assert ("c02", "input_removed", "refresh_needed") in withheld(keyed)
    in_place = run(
        root, "replace-decision", "--decision", "r01", "--expected-revision", "2"
    )
    assert in_place["sources"]["doc01"]["decisions"]["r01"]["status"] == "unresolved"
    assert withheld(in_place) == {
        ("c01", "input_changed", "refresh_needed"),
        ("c02", "input_removed", "refresh_needed"),
    }
    reviewed = run(
        root,
        *("reconfirm", "--source", "doc03", "--decision", "c01"),
        *("--expected-revision", "1"),
    )
    doc03 = reviewed["sources"]["doc03"]
    assert doc03["saved_revision"] == 2 and doc03["verified_revision"] == 2
    assert doc03["records"]["doc01_r01_r2"]["representation_revision"] == 3
    assert withheld(reviewed) == {("c02", "input_removed", "refresh_needed")}


@pytest.mark.integration
def test_native_chain_refusals_and_level_one_erasure(tmp_path):
    root = tmp_path / "chain"
    run(root, "glossary-fixture", "--chain")
    for source, case, message in (
        ("doc01", "cycle", "leads back here"),
        ("doc03", "self", "does not cite its own"),
        ("doc03", "missing", "No such saved record"),
        ("doc03", "stale", "current revision"),
        ("doc03", "digest", "fingerprint differs"),
    ):
        refusal = refused(
            root,
            *("cite-record", "--source", source, "--citation", case),
            *("--expected-revision", "1"),
        )
        assert message in refusal["message"], case
    refusal = refused(
        root,
        *("forget", "--source", "glossary", "--expected-revision", "1", "--dry-run"),
    )
    assert "not built yet" in refusal["message"]
    dry = printed(
        root, "forget", "--source", "doc01", "--expected-revision", "1", "--dry-run"
    )
    assert [d["identity_data_id"] for d in dry["dependents"]] == [D03]
    forgotten = run(
        root,
        *("forget", "--source", "doc01", "--expected-revision", "1"),
        *("--confirm", dry["token"]),
    )
    doc03 = forgotten["sources"]["doc03"]
    assert doc03["saved_revision"] == 2 and doc03["records"] == {}
    assert set(doc03["decisions"]) == {"c01"}
    c01 = doc03["decisions"]["c01"]
    assert (c01["status"], c01["input_refs"]) == ("unresolved", ["doc03"])
    assert unavailable(forgotten["result"]) == []


@pytest.mark.integration
def test_native_chain_waits_for_an_unfinished_upstream(tmp_path):
    root = tmp_path / "chain"
    run(root, "glossary-fixture", "--chain")
    run(
        root,
        *("edit-glossary", "--source", "glossary", "--case", "cosmetic"),
        *("--expected-revision", "1"),
    )
    refused(
        root,
        *("reconfirm", "--decision", "r01", "--expected-revision", "1"),
        *("--fault-stage", "replace_registered"),
    )
    status = printed(root, "status")
    assert {
        (d["assignment_id"], d["status"])
        for d in status["withheld_decisions"]
        if d["identity_data_id"] == D03
    } == {("c01", "edit_unfinished"), ("c02", "edit_unfinished")}
    waits = refused(
        root,
        *("reconfirm", "--source", "doc03", "--decision", "c01"),
        *("--expected-revision", "1"),
    )
    assert "whose records this source cites" in waits["message"]
    done = run(root, "reconcile", "--source", "doc01")
    assert withheld(done) == {
        ("v01", "input_changed", "refresh_needed"),
        ("c02", "input_changed", "upstream_withheld"),
    }
