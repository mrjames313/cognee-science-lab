"""Bounded exhaustive check of text-change admission against the group-fate oracle.

Enumerates every small world in support/occurrence_worlds.py and materializes
real old and new descriptions. Three checks run:

- The general admitter agrees with the oracle on every world, on a first
  attempt and on a retry, and refuses every corrupted map.
- Each old admission mode that can express a world agrees with the oracle
  wherever it admits, and refuses an oracle-admitted world only with its own
  "nothing of my kind changed" scope refusal.
- With --mutants, switching off any one group-fate or UUID rule of the general
  admitter makes some small world come out wrong.

    uv run python support/occurrence_check.py
    uv run python support/occurrence_check.py --mutants
"""

import argparse
import sys
import time
from collections import Counter
from contextlib import contextmanager

from cognee_lab.identity import admission
from cognee_lab.identity.validation import IntentError
from occurrence_mutants import MUTANTS
from occurrence_worlds import OLD_SHAPES, materialize, oracle, worlds

SMALL = ((1,), (2,), (1, 1))

# Each old mode admits only its own kind of change, so it refuses an unchanged
# grouping that the oracle admits as all-continuing.
OLD_SCOPE_REFUSALS = {
    "retention": "removes at least one occurrence",
    "continuity": "adds at least one occurrence",
    "regrouping": "regroups at least one group",
}
REASONS = {
    "key that no old group used": "key",
    "requires a fresh Entity UUID": "unused",
    "derives from its source": "derived",
}


def outcome(case, admit, first_attempt=True):
    try:
        admitted = admit()
        if first_attempt:
            admission.check_revision_scoped_ids(
                case["old"], case["new"], admitted.fresh
            )
    except IntentError as error:
        reason = next((r for m, r in REASONS.items() if m in str(error)), str(error))
        return ("refuse", reason)
    continuing = frozenset(case["new"].mention_groups) - admitted.fresh
    return (
        "admit",
        continuing,
        frozenset(case["old"].mention_groups) - continuing,
        frozenset(admitted.fresh),
    )


def general(case, mapping=None):
    return lambda: admission.admit_general(
        case["old"],
        case["new"],
        case["before"],
        case["after"],
        case["general"] if mapping is None else mapping,
    )


def agrees(expected, got):
    if expected[0] == "admit":
        return got == expected
    return got[0] == "refuse" and got[1] in expected[1]


def check_general(world, case):
    for first_attempt in (True, False):
        expected = oracle(world, first_attempt)
        got = outcome(case, general(case), first_attempt)
        setting = "first attempt" if first_attempt else "retry"
        yield f"general {setting}", agrees(expected, got), expected, got


def corruptions(case):
    """Maps that misstate the edit; each must be refused."""
    mapping = case["general"]
    targets = [e for entries in mapping.values() for e in entries if e is not None]
    first = next(iter(mapping))
    yield "group missing", {k: v for k, v in mapping.items() if k != first}
    yield "entry missing", {**mapping, first: mapping[first][:-1]}
    yield "malformed entry", {**mapping, first: [[first]] + mapping[first][1:]}
    if targets:
        key, entries = next((k, v) for k, v in mapping.items() if any(v))
        i = next(i for i, e in enumerate(entries) if e is not None)
        moved = lambda e: {**mapping, key: entries[:i] + [e] + entries[i + 1 :]}
        yield "index out of range", moved([entries[i][0], 99])
        yield "unknown group", moved(["zz", 0])
        others = [t for t in targets if t != entries[i]]
        if others:
            yield "two origins", moved(others[0])
        new = case["new"].mention_groups
        text = new[entries[i][0]].occurrences[entries[i][1]].text
        wrong = [
            [k, j]
            for k, g in new.items()
            for j, o in enumerate(g.occurrences)
            if o.text != text and [k, j] not in targets
        ]
        if wrong:
            yield "different text", moved(wrong[0])


def check_corruptions(world, case):
    if oracle(world)[0] != "admit":
        return
    for name, mapping in corruptions(case):
        got = outcome(case, general(case, mapping))
        yield f"corrupt: {name}", got[0] == "refuse", ("refuse",), got


def check_old_modes(world, case):
    expected = oracle(world)
    for mode, mapping in case["modes"].items():
        maps = {} if mode == "prefix" else {f"occurrence_{mode}": mapping}
        admit = lambda: admission.admit_remap(
            case["old"], case["new"], case["before"], case["after"], **maps
        )
        got = outcome(case, admit)
        if got[0] == "admit" or expected[0] == "refuse":
            ok = got[0] == expected[0] and (got[0] == "refuse" or got == expected)
            yield f"old {mode}", ok, expected, got
        else:
            yield (
                f"old {mode} scope refusal",
                OLD_SCOPE_REFUSALS.get(mode, "\0") in got[1],
                expected,
                got,
            )


def run(
    shapes=OLD_SHAPES,
    max_additions=1,
    checks=(check_general, check_corruptions, check_old_modes),
):
    tally, failures = Counter(), []
    for world in worlds(shapes, max_additions):
        case = materialize(world)
        tally[oracle(world)[0]] += 1
        for check in checks:
            for name, ok, expected, got in check(world, case):
                tally[name] += 1
                if not ok:
                    failures.append((world, name, expected, got))
    return tally, failures


@contextmanager
def patched(name):
    attribute, replacement = MUTANTS[name]
    original = getattr(admission, attribute)
    setattr(admission, attribute, replacement)
    try:
        yield
    finally:
        setattr(admission, attribute, original)


def run_mutants():
    caught = {}
    for name in MUTANTS:
        with patched(name):
            _, failures = run(SMALL, checks=(check_general,))
        # Prefer a world the broken admitter wrongly admits over one where only
        # the refusal reason changes.
        admitted = [f for f in failures if f[3][0] == "admit"]
        caught[name] = (admitted or failures or [None])[0]
    return caught


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-additions", type=int, default=1)
    parser.add_argument("--mutants", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    if args.mutants:
        missed = 0
        for name, failure in run_mutants().items():
            missed += failure is None
            detail = f"{failure[1]} on {failure[0]}" if failure else "NOT CAUGHT"
            print(f"  {name:<28} {detail}")
        print(f"seconds={time.monotonic() - started:.1f}")
        print("FAIL" if missed else "PASS")
        return 1 if missed else 0
    tally, failures = run(max_additions=args.max_additions)
    print(
        f"worlds={tally['admit'] + tally['refuse']} admitted={tally['admit']} refused={tally['refuse']}"
    )
    for name in sorted(k for k in tally if k not in ("admit", "refuse")):
        print(f"  {name:<36} {tally[name]}")
    print(f"seconds={time.monotonic() - started:.1f}")
    for world, name, expected, got in failures[:10]:
        print(f"FAIL {name}: {world}\n  oracle={expected}\n  got={got}")
    print("FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
