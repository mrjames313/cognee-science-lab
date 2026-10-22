"""Bounded exhaustive check of text-change admission against the group-fate oracle.

Enumerates every small world in support/occurrence_worlds.py and materializes
real old and new descriptions. Three checks run:

- The general admitter agrees with the oracle on every world, on a first
  attempt and on a retry. Every admitted world is also checked with all
  occurrences sharing one surface text, and each of its corruptions must be
  refused by the rule it breaks.
- Each old admission mode that can express a world agrees with the oracle
  wherever it admits, refuses an oracle-admitted world only with its own
  "nothing of my kind changed" scope refusal, and converts to the world's
  general map.
- With --mutants, switching off any one rule of the general admitter makes
  some small world come out wrong.

The oracle covers group fate and fresh keys and UUIDs. The shape, slice,
revision and carryover rules are covered by the corruptions.

    uv run python support/occurrence_check.py
    uv run python support/occurrence_check.py --mutants
"""

import argparse
import json
import sys
import time
from collections import Counter
from contextlib import contextmanager

from cognee_lab.identity import admission
from cognee_lab.identity.models import IdentitySource
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


def outcome(case, admit):
    try:
        fate = admit()
    except IntentError as error:
        reason = next((r for m, r in REASONS.items() if m in str(error)), str(error))
        return ("refuse", reason)
    except Exception as error:  # a broken rule can let a bad map reach a lookup
        return ("crash", repr(error))
    if isinstance(fate, admission.GroupFate):
        return ("admit", fate.continuing, fate.retired, fate.fresh)
    continuing = frozenset(case["new"].mention_groups) - fate.fresh
    return (
        "admit",
        continuing,
        frozenset(case["old"].mention_groups) - continuing,
        frozenset(fate.fresh),
    )


def general(case, mapping=None, first_attempt=True, **parts):
    parts = {**case, **parts}
    return lambda: admission.admit_general(
        parts["old"],
        parts["new"],
        parts["before"],
        parts["after"],
        parts["general"] if mapping is None else mapping,
        first_attempt=first_attempt,
    )


def agrees(expected, got):
    if expected[0] == "admit":
        return got == expected
    return got[0] == "refuse" and got[1] in expected[1]


def check_general(world, case):
    for first_attempt in (True, False):
        expected = oracle(world, first_attempt)
        got = outcome(case, general(case, first_attempt=first_attempt))
        setting = "first attempt" if first_attempt else "retry"
        yield f"general {setting}", agrees(expected, got), expected, got


def rebuilt(payload, change):
    payload = json.loads(json.dumps(payload))
    change(payload)
    return IdentitySource.model_validate_json(json.dumps(payload))


def map_corruptions(case, same_text):
    """Maps that misstate the edit, each with the refusal it must meet. A swap
    of two same-text occurrences is a legal reorder, not a corruption."""
    mapping = case["general"]
    first = next(iter(mapping))
    yield (
        "group missing",
        "Map every old group",
        {k: v for k, v in mapping.items() if k != first},
    )
    yield "entry missing", "in order, once", {**mapping, first: mapping[first][:-1]}
    yield (
        "malformed entry",
        "null or one [group, index]",
        {**mapping, first: [[first]] + mapping[first][1:]},
    )
    entries = [(k, i, e) for k, v in mapping.items() for i, e in enumerate(v)]
    mapped = [x for x in entries if x[2] is not None]
    if not mapped:
        return

    def remap(*changes):
        result = {k: list(v) for k, v in mapping.items()}
        for key, index, entry in changes:
            result[key][index] = entry
        return result

    key, index, target = mapped[0]
    yield (
        "index out of range",
        "not in the new source",
        remap((key, index, [target[0], 99])),
    )
    yield "unknown group", "not in the new source", remap((key, index, ["zz", 0]))
    other = next((x for x in entries if x[:2] != (key, index)), None)
    if other is not None:
        yield "two origins", "at most one origin", remap((other[0], other[1], target))
    if len(mapped) > 1 and not same_text:
        second = mapped[1]
        yield (
            "swapped texts",
            "text differs",
            remap((key, index, second[2]), (second[0], second[1], target)),
        )


def payload_corruptions(case, fate):
    """Descriptions that break a slice, revision or carryover rule."""
    old_payload, new_payload = case["old_payload"], case["new_payload"]

    def shift(occurrence):
        occurrence.update(start=occurrence["start"] + 1, end=occurrence["end"] + 1)

    yield (
        "old slice",
        "Previous occurrence does not match",
        dict(
            old=rebuilt(
                old_payload,
                lambda p: shift(
                    next(iter(p["mention_groups"].values()))["occurrences"][0]
                ),
            )
        ),
    )
    if new_payload["mention_groups"]:
        yield (
            "new slice",
            "exact document slice",
            dict(
                new=rebuilt(
                    new_payload,
                    lambda p: shift(
                        next(iter(p["mention_groups"].values()))["occurrences"][-1]
                    ),
                )
            ),
        )
    yield (
        "revision skipped",
        "advances exactly one revision",
        dict(new=rebuilt(new_payload, lambda p: p.update(revision=3))),
    )
    yield (
        "variant changed",
        "Variant assignments stay unchanged",
        dict(
            new=rebuilt(
                new_payload,
                lambda p: p["variant_assignments"]["v01"].update(
                    applicability=dict(kind="corpus")
                ),
            )
        ),
    )
    for key in sorted(fate.continuing)[:1]:
        unresolved = dict(
            group_ref=key,
            status="unresolved",
            input_refs=["doc01"],
            producer_ref="fixture",
        )
        yield (
            "continuing decision changed",
            "keeps its reviewed resolutions",
            dict(
                new=rebuilt(
                    new_payload,
                    lambda p: p["mention_resolutions"].update({f"r{key}": unresolved}),
                )
            ),
        )
    for key in sorted(fate.fresh)[:1]:
        yield (
            "fresh resolution missing",
            "one resolution per fresh group",
            dict(
                new=rebuilt(
                    new_payload, lambda p: p["mention_resolutions"].pop(f"s{key}")
                )
            ),
        )
    for key in sorted(fate.retired)[:1]:
        retired = str(case["old"].mention_groups[key].entity_id)
        recipe = {retired: dict(name=key, description=key)}
        yield (
            "retired recipe kept",
            "Recipes are the old ones",
            dict(
                new=rebuilt(
                    new_payload, lambda p: p["entity_constructions"].update(recipe)
                )
            ),
        )


def check_corruptions(world, case):
    expected = oracle(world)
    if expected[0] != "admit":
        return
    fate = admission.GroupFate(*expected[1:])
    same = materialize(world, same_text=True)
    got = outcome(same, general(same))
    yield "general same text", got == expected, expected, got
    for variant, same_text in ((case, False), (same, True)):
        for name, message, mapping in map_corruptions(variant, same_text):
            got = outcome(variant, general(variant, mapping))
            ok = got[0] == "refuse" and message in got[1]
            yield f"corrupt map: {name}", ok, ("refuse", message), got
    for name, message, parts in payload_corruptions(case, fate):
        got = outcome(case, general(case, **parts))
        ok = got[0] == "refuse" and message in got[1]
        yield f"corrupt description: {name}", ok, ("refuse", message), got


def check_old_modes(world, case):
    expected = oracle(world)
    for mode, mapping in case["modes"].items():
        converted = admission.to_occurrence_map(case["old"], mode, mapping)
        yield (
            f"convert {mode}",
            converted == case["general"],
            case["general"],
            converted,
        )
        maps = {} if mode == "prefix" else {f"occurrence_{mode}": mapping}

        def admit():
            admitted = admission.admit_remap(
                case["old"], case["new"], case["before"], case["after"], **maps
            )
            admission.check_revision_scoped_ids(
                case["old"], case["new"], admitted.fresh
            )
            return admitted

        got = outcome(case, admit)
        if got[0] == "admit" or expected[0] == "refuse":
            ok = got[0] == expected[0] and (got[0] == "refuse" or got == expected)
            yield f"old {mode}", ok, expected, got
        else:
            scope = OLD_SCOPE_REFUSALS.get(mode)
            ok = scope is not None and scope in got[1]
            yield f"old {mode} scope refusal", ok, expected, got


CHECKS = (check_general, check_corruptions, check_old_modes)


def run(shapes=OLD_SHAPES, max_additions=1, checks=CHECKS):
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
            _, failures = run(SMALL, checks=(check_general, check_corruptions))
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
        f"worlds={tally['admit'] + tally['refuse']} "
        f"admitted={tally['admit']} refused={tally['refuse']}"
    )
    for name in sorted(k for k in tally if k not in ("admit", "refuse")):
        print(f"  {name:<44} {tally[name]}")
    print(f"seconds={time.monotonic() - started:.1f}")
    for world, name, expected, got in failures[:10]:
        print(f"FAIL {name}: {world}\n  expected={expected}\n  got={got}")
    print("FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
