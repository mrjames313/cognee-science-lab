"""The glossary dependency through real configured stores in fresh subprocesses."""

import json

import pytest

from test_identity_native import command

D01 = "718efce2-4251-5f6f-8318-417bb4dd3525"


def run(root, *args, expect=0):
    """Run a glossary command and return the result it saved."""
    command(root, *args, expect=expect)
    return json.loads((root / "glossary_result.json").read_text())


def printed(root, *args, expect=0):
    out = command(root, *args, expect=expect).stdout
    return json.loads(out[out.index("{\n") if "{\n" in out else out.rindex("{") :])


def withheld(result):
    return {
        (d["assignment_id"], d["reason"], d["status"])
        for d in result["withheld_decisions"]
    }


def fact_keys(answer):
    return [f.get("identity", {}).get("assignment_id") for f in answer["facts"]]


def unavailable(answer):
    return [(u["assignment_id"], u["reason"]) for u in answer["unavailable_sources"]]


def revisions(result, label):
    s = result["sources"][label]
    return (s["saved_revision"], s["registered_revision"], s["verified_revision"])


@pytest.mark.integration
def test_native_glossary_edits_withhold_refresh_and_reconfirm(tmp_path):
    root = tmp_path / "glossary"
    outputs = []
    base = run(root, "glossary-fixture")
    outputs.append(base)
    assert fact_keys(base["result"]) == ["r01"] and base["withheld_decisions"] == []
    span = base["sources"]["doc01"]["glossary_spans"]["glossary_hc"]
    assert (span["start"], span["end"]) == (10, 62)

    elsewhere = run(
        root,
        "edit-glossary",
        "--source",
        "glossary",
        "--case",
        "elsewhere",
        "--expected-revision",
        "1",
    )
    outputs.append(elsewhere)
    assert revisions(elsewhere, "glossary") == (2, 2, 2)
    assert revisions(elsewhere, "doc01") == (1, 1, 1)
    assert elsewhere["withholdings"] == [] and elsewhere["refreshed"] == []
    assert fact_keys(elsewhere["result"]) == ["r01"]

    inserted = run(
        root,
        "edit-glossary",
        "--source",
        "glossary",
        "--case",
        "insert",
        "--expected-revision",
        "2",
    )
    outputs.append(inserted)
    moved = inserted["sources"]["doc01"]["glossary_spans"]["glossary_hc"]
    assert (moved["start"], moved["end"]) == (54, 106)
    assert moved["text_sha256"] == span["text_sha256"]
    assert inserted["refreshed"] == [
        dict(
            identity_data_id=D01,
            revision=2,
            inputs=dict(glossary_hc=dict(start=54, end=106)),
        )
    ]
    assert (
        inserted["sources"]["doc01"]["decisions"]
        == base["sources"]["doc01"]["decisions"]
    )
    assert inserted["withholdings"] == [] and fact_keys(inserted["result"]) == ["r01"]

    cosmetic = run(
        root,
        "edit-glossary",
        "--source",
        "glossary",
        "--case",
        "cosmetic",
        "--expected-revision",
        "3",
    )
    outputs.append(cosmetic)
    assert withheld(cosmetic) == {
        ("r01", "input_changed", "refresh_needed"),
        ("v01", "input_changed", "refresh_needed"),
    }
    assert [r["old_digest"] for r in cosmetic["withholdings"]] == [
        span["text_sha256"]
    ] * 2
    assert cosmetic["result"]["facts"] == []
    assert unavailable(cosmetic["result"]) == [
        ("r01", "input_changed"),
        ("v01", "input_changed"),
    ]
    status = printed(root, "status")
    outputs.append(status)
    assert [p["state"] for p in status["publications"]] == ["current", "current"]
    assert {d["assignment_id"] for d in status["refresh_needed"]} == {"r01", "v01"}
    assert status["recovery_events"] == []

    first = run(root, "reconfirm", "--decision", "r01", "--expected-revision", "2")
    outputs.append(first)
    assert withheld(first) == {("v01", "input_changed", "refresh_needed")}
    review = first["sources"]["doc01"]["producers"]["review_r01_r3"]
    assert review["implementation"] == "re-confirmed"
    assert (
        review["configuration"]["new_digest"]
        == first["glossary"]["hc_entry"]["text_sha256"]
    )
    assert fact_keys(first["helios"]) == ["r01"] and first["result"]["facts"] == []

    second = run(root, "reconfirm", "--decision", "v01", "--expected-revision", "3")
    outputs.append(second)
    assert second["withheld_decisions"] == [] and fact_keys(second["result"]) == ["r01"]
    assert set(second["sources"]["doc01"]["glossary_spans"]) == {
        "glossary_hc_r3",
        "glossary_hc_r4",
    }

    substantive = run(
        root,
        "edit-glossary",
        "--source",
        "glossary",
        "--case",
        "substantive",
        "--expected-revision",
        "4",
    )
    outputs.append(substantive)
    assert {d[0] for d in withheld(substantive)} == {"r01", "v01"}
    replaced = run(
        root, "replace-decision", "--decision", "v01", "--expected-revision", "4"
    )
    outputs.append(replaced)
    assert set(replaced["sources"]["doc01"]["decisions"]) == {"r01", "v02"}
    assert withheld(replaced) == {("r01", "input_changed", "refresh_needed")}
    final = run(root, "reconfirm", "--decision", "r01", "--expected-revision", "5")
    outputs.append(final)
    assert final["withheld_decisions"] == [] and final["withholdings"] == []
    # HC now names the hybrid coil, so an HC query no longer reaches doc01's
    # controller fact; the Helios controller query does.
    assert final["result"]["facts"] == [] and fact_keys(final["helios"]) == ["r01"]
    assert revisions(final, "doc01") == (6, 6, 6)
    reopened = printed(
        root, "retrieve", "--query", "What does Helios controller limit?"
    )
    outputs.append(reopened)
    assert fact_keys(reopened) == ["r01"] and reopened["unavailable_sources"] == []
    assert final["recovery_events"] == []
    # Users see "input changed" or "input removed", never "forgotten".
    assert all("forgotten" not in json.dumps(o) for o in outputs)


@pytest.mark.integration
@pytest.mark.parametrize(
    "stage", ["replace_saved", "replace_dependents", "text_chunks"]
)
def test_native_failed_glossary_edit_withholds_until_reconciled(tmp_path, stage):
    root = tmp_path / stage
    run(root, "glossary-fixture")
    command(
        root,
        "edit-glossary",
        "--source",
        "glossary",
        "--case",
        "insert",
        "--expected-revision",
        "1",
        "--fault-stage",
        stage,
        expect=1,
    )
    answer = printed(root, "retrieve")
    assert answer["facts"] == []
    assert unavailable(answer) == [
        (None, "publication_failed"),
        ("r01", "input_changed"),
        ("v01", "input_changed"),
    ]
    status = printed(root, "status")
    assert {d["status"] for d in status["withheld_decisions"]} == {"edit_unfinished"}
    # The rows exist once the edit's own stage has run.
    assert len(status["withholdings"]) == (0 if stage == "replace_saved" else 2)
    done = run(root, "reconcile", "--source", "glossary")
    assert revisions(done, "glossary") == (2, 2, 2)
    assert revisions(done, "doc01") == (2, 2, 2)
    assert done["withheld_decisions"] == [] and fact_keys(done["result"]) == ["r01"]
    assert [e["outcome"] for e in done["recovery_events"]] == ["restored"]


@pytest.mark.integration
def test_native_interrupted_refresh_is_finished_by_a_rerun(tmp_path):
    root = tmp_path / "refresh"
    run(root, "glossary-fixture")
    command(
        root,
        "edit-glossary",
        "--source",
        "glossary",
        "--case",
        "insert",
        "--expected-revision",
        "1",
        "--fault-stage",
        "refresh_interrupted",
        expect=1,
    )
    answer = printed(root, "retrieve")
    assert unavailable(answer) == [(None, "publication_failed")]
    status = printed(root, "status")
    assert {d["status"] for d in status["withheld_decisions"]} == {"remap"}
    done = run(root, "refresh-dependents")
    assert revisions(done, "doc01") == (2, 2, 2)
    assert done["withholdings"] == [] and fact_keys(done["result"]) == ["r01"]
    assert [e["outcome"] for e in done["recovery_events"]] == ["restored"]
