"""The conformance check's scoring and gate, without a root: value and word
matching, the ratchet against the baseline and the baseline it writes.
Running the check itself takes a conformance root (journey B1)."""

import json

import conformance_check as check
from conformance_check import Outcome

COUNTS = dict.fromkeys((*check.GATED_COUNTS, "logical_duplicates"), 0)
PASSED, UNOBSERVED, FAILED = Outcome.PASSED, Outcome.UNOBSERVED, Outcome.FAILED


def run(**cases):
    return {c: dict(metric="m", outcome=o) for c, o in cases.items()}


def baseline(**cases):
    return dict(
        cases={c: dict(metric="m", outcome=o.value) for c, o in cases.items()},
        counts=COUNTS,
    )


def test_a_value_matches_with_its_unit_and_any_written_precision():
    assert check.holds_value("a limit of 1.20 MA", "MA", 1.2, 1.2)
    assert check.holds_value("Typical full-field pulse length | 5–6 s", "s", 5, 6)
    assert not check.holds_value("a radius of 1.35 m", "MW", 1.35, 1.35)
    assert not check.holds_value("8 MW installed", "MW", 6, 6)


def test_an_object_matches_its_words_whatever_the_punctuation():
    assert check.words("compact high-field tokamak") in check.words(
        "Helios-1 is a compact, high-field tokamak operated by AFRL."
    )
    assert check.words("field") not in check.words("high-fields")


def test_a_case_that_moves_either_way_is_reported():
    regressions, improvements = check.compare(
        run(a=UNOBSERVED, b=FAILED, c=PASSED, d=FAILED),
        COUNTS,
        baseline(a=PASSED, b=UNOBSERVED, c=UNOBSERVED, d=FAILED),
    )
    assert regressions == [
        "a: passed on the baseline, now unobserved",
        "b: unobserved on the baseline, now failed",
    ]
    assert improvements == ["c: unobserved on the baseline, now passed"]


def test_a_missing_case_a_new_case_and_a_grown_count_are_regressions():
    counts = dict(COUNTS, leakage_violations=1, logical_duplicates=9)
    regressions, _ = check.compare(run(b=PASSED), counts, baseline(a=PASSED))
    assert regressions == [
        "a: missing from this run",
        "b: new case, not on the baseline",
        "leakage_violations: 1 (baseline 0)",
    ]


def test_a_written_baseline_keeps_each_gap_and_only_on_cases_that_do_not_pass():
    old = baseline(a=FAILED, b=PASSED)
    old["cases"]["a"]["gap"] = "why a fails"
    written, problems = check.baseline_of(run(a=UNOBSERVED, b=PASSED), COUNTS, old)
    assert problems == []
    assert written["cases"] == dict(
        a=dict(metric="m", outcome="unobserved", gap="why a fails"),
        b=dict(metric="m", outcome="passed"),
    )


def test_a_baseline_with_a_missing_or_stale_gap_or_a_gated_count_is_refused():
    old = baseline(a=FAILED)
    old["cases"]["a"]["gap"] = "why a fails"
    counts = dict(COUNTS, repeated_edge_ids=2)
    _, problems = check.baseline_of(run(a=PASSED, b=FAILED), counts, old)
    assert problems == [
        "a passes; delete its gap from the baseline",
        "b is failed; record its gap in the baseline",
        "repeated_edge_ids is 2; a gated count must be 0",
    ]


def test_the_committed_baseline_is_one_the_check_would_write():
    """Every case that does not pass has its gap, no case that passes has
    one, and every gated count is 0."""
    recorded = json.loads(check.BASELINE.read_text())
    cases = {
        c: dict(metric=v["metric"], outcome=Outcome(v["outcome"]))
        for c, v in recorded["cases"].items()
    }
    written, problems = check.baseline_of(cases, recorded["counts"], recorded)
    assert problems == []
    assert written == recorded
