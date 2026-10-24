"""Bounded exhaustive check of replacement admission against the independent oracle.

Enumerates every small world in support/occurrence_worlds.py and materializes
real old and new descriptions. Three checks run:

- The admitter agrees with the group-fate oracle on every world, on a first
  attempt and on a retry. A stable world, where every occurrence survives and
  nothing is added, is also checked with unchanged text. Every admitted world
  is also checked with all occurrences sharing one surface text.
- Each corruption of an admitted world's map, slices or revision must be
  refused by the rule it breaks.
- Each decision choice in `DECISIONS` (a changed decision, a new or dropped
  Entity recipe, a variant change by scope, from support/dependency_worlds.py
  another document's input, and from support/erasure_worlds.py an erasure
  removal) layered on an admitted world must
  come out as the rules say, with changed and, where the world allows,
  unchanged text, and on a retry where the outcome depends on the attempt.
- With --mutants, switching off any one rule of the admitter makes some small
  world come out wrong.

    uv run python support/occurrence_check.py
    uv run python support/occurrence_check.py --mutants
"""

import argparse
import json
import sys
import time
from collections import Counter
from contextlib import contextmanager
from uuid import UUID

from cognee_lab.identity import admission, chains, erasure_rules
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.validation import IntentError, text_digest
from dependency_worlds import DEPENDENCY_DECISIONS
from erasure_worlds import ERASURE_DECISIONS, STEADY, forgotten
from occurrence_mutants import MUTANTS
from occurrence_worlds import (
    ADMIT,
    DECISIONS,
    OLD_SHAPES,
    materialize,
    oracle,
    stable,
    worlds,
)

SMALL = ((1,), (2,), (1, 1))

REASONS = {
    "fresh_key_reused": "key",
    "fresh_uuid_reused": "unused",
    "fresh_uuid_not_derived": "derived",
}


def outcome(admit):
    try:
        fate = admit()
    except IntentError as error:
        return ("refuse", error.code, str(error))
    except Exception as error:  # a broken rule can let a bad map reach a lookup
        return ("crash", repr(error))
    return ("admit", fate.continuing, fate.retired, fate.fresh)


def general(case, mapping=None, first_attempt=True, **parts):
    parts = {**case, **parts}
    raw = parts["general"] if mapping is None else mapping

    def admit():
        # Citation scope is checked in Publisher.admit_inputs, not in admit,
        # so the harness checks it here to keep those refusals in view.
        chains.check_citation_scope(parts["new"])
        return admission.admit(
            parts["old"],
            parts["new"],
            parts["before"],
            parts["after"],
            admission.parse_occurrence_map(raw),
            first_attempt=first_attempt,
            erasures=forgotten(parts["old"]),
        )

    return admit


def agrees(expected, got):
    if expected[0] == "admit":
        return got == expected
    return got[0] == "refuse" and REASONS.get(got[1]) in expected[1]


def refused_with(got, code=None, message=None):
    return (
        got[0] == "refuse"
        and (code is None or got[1] == code)
        and (message is None or message in got[2])
    )


def check_general(world, case):
    cases = [("", case)]
    if stable(world):
        cases.append(("unchanged text ", materialize(world, text_changed=False)))
    for label, variant in cases:
        for first_attempt in (True, False):
            expected = oracle(world, first_attempt)
            got = outcome(general(variant, first_attempt=first_attempt))
            setting = "first attempt" if first_attempt else "retry"
            yield f"general {label}{setting}", agrees(expected, got), expected, got


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


def moved_occurrences(case):
    """With unchanged text, a swap of two same-text occurrences moves each to
    the other's span, which no rebuild re-marks."""
    mapping = case["general"]
    mapped = [(k, i) for k, v in mapping.items() for i, e in enumerate(v) if e]
    if len(mapped) < 2:
        return
    (k1, i1), (k2, i2) = mapped[:2]
    swapped = {k: list(v) for k, v in mapping.items()}
    swapped[k1][i1], swapped[k2][i2] = mapping[k2][i2], mapping[k1][i1]
    yield "moved occurrence", "keeps its start and end", swapped


def payload_corruptions(case, fate):
    """Descriptions that break a slice, revision or fresh-resolution rule."""
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
    if not new_payload["mention_groups"]:

        def empty(p):
            p["inputs"].pop("chunk01")
            p["inputs"]["doc01"]["text_sha256"] = text_digest("")

        yield (
            "emptied text",
            "non-empty text",
            dict(after="", new=rebuilt(new_payload, empty)),
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
    for fresh, retired_key in list(zip(sorted(fate.fresh), sorted(fate.retired)))[:1]:

        def reuse_id(p):
            p["mention_resolutions"][f"r{retired_key}"] = p["mention_resolutions"].pop(
                f"s{fresh}"
            )

        yield (
            "fresh resolution reuses an old ID",
            "no old resolution or assignment",
            dict(new=rebuilt(new_payload, reuse_id)),
        )


def admitted_fate(world):
    expected = oracle(world)
    return admission.GroupFate(*expected[1:]) if expected[0] == "admit" else None


def check_corruptions(world, case):
    fate = admitted_fate(world)
    if fate is None:
        return
    expected = oracle(world)
    same = materialize(world, same_text=True)
    got = outcome(general(same))
    yield "general same text", got == expected, expected, got
    for variant, same_text in ((case, False), (same, True)):
        for name, message, mapping in map_corruptions(variant, same_text):
            got = outcome(general(variant, mapping))
            ok = refused_with(got, message=message)
            yield f"corrupt map: {name}", ok, ("refuse", message), got
    for name, message, parts in payload_corruptions(case, fate):
        got = outcome(general(case, **parts))
        ok = refused_with(got, message=message)
        yield f"corrupt description: {name}", ok, ("refuse", message), got
    if stable(world):
        unchanged = materialize(world, same_text=True, text_changed=False)
        for name, message, mapping in moved_occurrences(unchanged):
            got = outcome(general(unchanged, mapping))
            ok = refused_with(got, message=message)
            yield f"corrupt map: {name}", ok, ("refuse", message), got


def decided(case, decision, ctx, first_attempt):
    """The case with one decision choice applied to both descriptions."""
    old, new = (json.loads(json.dumps(case[k])) for k in ("old_payload", "new_payload"))
    decision.change(old, new, ctx)
    return general(
        case,
        first_attempt=first_attempt,
        old=IdentitySource.model_validate_json(json.dumps(old)),
        new=IdentitySource.model_validate_json(json.dumps(new)),
    )


def meets(expected, got, admitted):
    """Whether an outcome is the expected admission, or a refusal by one of
    the expected codes; and what was wanted."""
    if expected == ADMIT:
        return got == admitted, admitted
    return got[0] == "refuse" and got[1] in expected, ("refuse", expected)


def check_decisions(world, case):
    fate = admitted_fate(world)
    if fate is None:
        return
    admitted = ("admit", fate.continuing, fate.retired, fate.fresh)
    available = {
        kind for kind in ("continuing", "retired", "fresh") if getattr(fate, kind)
    }
    if not (fate.retired or fate.fresh):
        available.add(STEADY)
    ctx = dict(
        identity=UUID(case["old_payload"]["identity_data_id"]),
        **{
            kind: min(getattr(fate, kind), default=None)
            for kind in available - {STEADY}
        },
    )
    cases = [(True, case)]
    if stable(world):
        cases.append((False, materialize(world, text_changed=False)))
    for decision in [*DECISIONS, *DEPENDENCY_DECISIONS, *ERASURE_DECISIONS]:
        if not decision.needs <= available:
            continue
        attempts = (True, False) if decision.attempt_sensitive() else (True,)
        for text_changed, variant in cases:
            for first_attempt in attempts:
                expected = decision.expected(text_changed, first_attempt)
                got = outcome(decided(variant, decision, ctx, first_attempt))
                ok, want = meets(expected, got, admitted)
                yield f"decision: {decision.name}", ok, want, got


CHECKS = (check_general, check_corruptions, check_decisions)


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
    """Replace one rule where its callers look it up: admission, the
    erasure rules that admission imports, and the citation scope that
    preflight checks (chains)."""
    attribute, replacement = MUTANTS[name]
    modules = [m for m in (admission, erasure_rules, chains) if hasattr(m, attribute)]
    originals = [getattr(m, attribute) for m in modules]
    for m in modules:
        setattr(m, attribute, replacement)
    try:
        yield
    finally:
        for m, original in zip(modules, originals):
            setattr(m, attribute, original)


def run_mutants():
    caught = {}
    for name in MUTANTS:
        with patched(name):
            _, failures = run(SMALL)
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
            print(f"  {name:<40} {detail}")
        print(f"seconds={time.monotonic() - started:.1f}")
        print("FAIL" if missed else "PASS")
        return 1 if missed else 0
    tally, failures = run(max_additions=args.max_additions)
    print(
        f"worlds={tally['admit'] + tally['refuse']} "
        f"admitted={tally['admit']} refused={tally['refuse']}"
    )
    for name in sorted(k for k in tally if k not in ("admit", "refuse")):
        print(f"  {name:<64} {tally[name]}")
    print(f"seconds={time.monotonic() - started:.1f}")
    for world, name, expected, got in failures[:10]:
        print(f"FAIL {name}: {world}\n  expected={expected}\n  got={got}")
    print("FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
