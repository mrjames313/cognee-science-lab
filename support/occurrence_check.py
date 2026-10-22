"""Bounded exhaustive check of text-change admission against the group-fate oracle.

Enumerates every small world in support/occurrence_worlds.py, materializes real
old and new descriptions, and runs each old admission mode that can express the
world. An old mode must agree with the oracle wherever it admits, and may refuse
an oracle-admitted world only with its own "nothing of my kind changed" scope
refusal.

    uv run python support/occurrence_check.py
"""

import argparse
import sys
import time
from collections import Counter

from cognee_lab.identity.admission import admit_remap, check_revision_scoped_ids
from cognee_lab.identity.validation import IntentError
from occurrence_worlds import OLD_SHAPES, materialize, oracle, worlds

# Each old mode admits only its own kind of change, so it refuses an unchanged
# grouping that the oracle admits as all-continuing.
OLD_SCOPE_REFUSALS = {
    "retention": "removes at least one occurrence",
    "continuity": "adds at least one occurrence",
    "regrouping": "regroups at least one group",
}


def decide(old, new, before, after, **maps):
    try:
        admitted = admit_remap(old, new, before, after, **maps)
        check_revision_scoped_ids(old, new, admitted.fresh)
    except IntentError as error:
        return ("refuse", str(error))
    continuing = frozenset(new.mention_groups) - admitted.fresh
    return (
        "admit",
        continuing,
        frozenset(old.mention_groups) - continuing,
        frozenset(admitted.fresh),
    )


def compare_old_modes(world, expected, case):
    for mode, mapping in case["modes"].items():
        maps = {} if mode == "prefix" else {f"occurrence_{mode}": mapping}
        got = decide(case["old"], case["new"], case["before"], case["after"], **maps)
        if got[0] == "admit" and got != expected:
            yield mode, "admits differently", got
        elif got[0] == "refuse" and expected[0] == "admit":
            if OLD_SCOPE_REFUSALS.get(mode, "\0") in got[1]:
                yield mode, "scope refusal", got
            else:
                yield mode, "refuses an admitted world", got
        else:
            yield mode, "agrees", got


def run(shapes=OLD_SHAPES, max_additions=1):
    tally, failures = Counter(), []
    for world in worlds(shapes, max_additions):
        expected = oracle(world)
        tally[expected[0]] += 1
        case = materialize(world)
        for mode, verdict, got in compare_old_modes(world, expected, case):
            tally[(mode, verdict)] += 1
            if verdict not in ("agrees", "scope refusal"):
                failures.append((world, mode, verdict, expected, got))
    return tally, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-additions", type=int, default=1)
    args = parser.parse_args()
    started = time.monotonic()
    tally, failures = run(max_additions=args.max_additions)
    worlds_seen = tally["admit"] + tally["refuse"]
    print(f"worlds={worlds_seen} admitted={tally['admit']} refused={tally['refuse']}")
    for key in sorted(k for k in tally if isinstance(k, tuple)):
        print(f"  {key[0]:<11} {key[1]:<26} {tally[key]}")
    print(f"seconds={time.monotonic() - started:.1f}")
    for world, mode, verdict, expected, got in failures[:10]:
        print(f"FAIL {mode} {verdict}: {world}\n  oracle={expected}\n  got={got}")
    print("FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
