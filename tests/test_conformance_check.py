"""The conformance check's scoring and gate, without a root: value and word
matching, the regression rule and the committed baseline. Running the check
itself takes a conformance root (journey B1)."""

import json

import conformance_check as check

COUNTS = dict.fromkeys((*check.GATED_COUNTS, "logical_duplicates"), 0)


def baseline(**cases):
    return dict(
        cases={c: dict(metric="m", passed=p) for c, p in cases.items()}, counts=COUNTS
    )


def run(**cases):
    return {c: dict(metric="m", passed=p) for c, p in cases.items()}


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


def test_a_case_doing_worse_than_its_baseline_is_a_regression():
    regressions, improvements = check.compare(
        run(a=None, b=False, c=True, d=False),
        COUNTS,
        baseline(a=True, b=None, c=None, d=False),
    )
    assert [r.split(":")[0] for r in regressions] == ["a", "b"]
    assert improvements == ["c"]


def test_a_missing_case_a_new_case_and_a_grown_count_are_regressions():
    counts = dict(COUNTS, leakage_violations=1, logical_duplicates=9)
    regressions, _ = check.compare(run(b=True), counts, baseline(a=True))
    assert regressions == [
        "a: missing from this run",
        "b: new case, not on the baseline",
        "leakage_violations: 1 (baseline 0)",
    ]


def test_the_baseline_explains_every_case_that_does_not_pass():
    recorded = json.loads(check.BASELINE.read_text())
    gaps = {
        c: v["gap"] for c, v in recorded["cases"].items() if v["passed"] is not True
    }
    assert gaps and gaps == {c: check.KNOWN_GAPS[c] for c in gaps}
    assert set(check.KNOWN_GAPS) == set(gaps)
    assert all(recorded["counts"][name] == 0 for name in check.GATED_COUNTS)
