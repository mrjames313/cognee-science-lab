"""Bounded exhaustive check of saved-record chains.

On every citation graph of up to four sources (chain_worlds.py), it checks:

- Cycles. Admitting any source's citations is refused (`citation_cycle`)
  exactly when a path of citations leads from that source back to it, so a
  graph is admitted if and only if it is acyclic.
- Withholding. On every acyclic graph, with every source in every state
  (ok, held, replaced, rekeyed, pending, unverified, withdrawn, invalid),
  the withheld-decision set that retrieval and `status` read equals the
  oracle's: each decision's reason, status and withholding inputs, for a
  resolution and a variant of each source, with withholding spread down
  the whole chain as `input_changed` and `upstream_withheld`.
- Key reuse (checkpoint K). On every acyclic graph, with every source
  holding `d` and `v`, having dropped `d` (rekeyed) or `v` (rekeyed_v),
  pending or withdrawn, a source's next revision that declares the dropped
  key again is refused (`record_key_reused`) exactly when another source
  that is not retired cites it. Both record types have a key that comes
  back.
- The erasure cascade (cascade_check.py): with s0 forgotten, the levels,
  the token, the write order and resume, the inductive gate and the rule
  that a confirmed cascade only shrinks.

The code under test is chains.check_citation_cycles,
chains.check_record_key_reuse with chains.new_record_keys,
withholding.record_reader, withholding.withheld_decisions and
chains.live_pass, the pass that retrieval and `status` run. Only live
validation itself (retrieve.live_drift) is replaced: `drift_of` returns the
reader's answer for each cited record, as validate_inputs does, and raises
for an invalid source.

With --mutants, each scratch break in MUTANTS and in
cascade_check.MUTANTS must make the check fail.

    uv run python support/chain_check.py
    uv run python support/chain_check.py --mutants
"""

import argparse
import asyncio
import sys
import time
from collections import Counter
from contextlib import contextmanager
from itertools import product

import cascade_check
from chain_worlds import (
    LABELS,
    STATES,
    acyclic,
    cyclic_from,
    described,
    graphs,
    identity,
    oracle,
    world_rows,
)
from cognee_lab.identity import chains, withholding
from cognee_lab.identity.records import REGISTRY, saved_records
from cognee_lab.identity.validation import IntentError
from cognee_lab.identity.withholding import (
    Status,
    Withheld,
    combine,
    withheld_decisions,
)


def refused(graph, label) -> bool:
    """Whether admission refuses this source's citations for a cycle, with
    every source of the graph current."""
    rows, _ = world_rows(graph, dict.fromkeys(graph, "ok"))
    try:
        chains.check_citation_cycles(described(label, graph[label]), rows)
    except IntentError as exc:
        if exc.code != "citation_cycle":
            raise
        return True
    return False


async def held_now(graph, states):
    """The withheld-decision set of the served sources that validate."""
    rows, table = world_rows(graph, states)
    invalid = {str(identity(label)) for label in graph if states[label] == "invalid"}

    async def drift_of(source, read):
        if str(source.identity_data_id) in invalid:
            raise IntentError("source_changed", "An own input fails")
        return {
            key: found[0]
            for key, item in saved_records(source).items()
            if (found := read(item)) is not None
        }

    live = await chains.live_pass(rows, withheld_decisions(rows, table), drift_of)
    return {
        key: held
        for key, (_, _, held) in live.items()
        if not isinstance(held, IntentError) and held
    }


def key_reused(graph, states, label) -> bool:
    """Whether admission refuses the source's next revision, which declares
    its resolution under `d` and its variant under `v` again, for a reused
    key. Each source cites every source it points at, `d` from its `d` and
    `v` from its `v`."""
    rows, _ = world_rows(graph, states)
    previous = next(r for r in rows if r.source == str(identity(label)))
    candidate = described(label, graph[label]).model_copy(
        update=dict(revision=previous.revision + 1)
    )
    try:
        chains.check_record_key_reuse(
            candidate, rows, chains.new_record_keys(candidate, previous)
        )
    except IntentError as exc:
        if exc.code != "record_key_reused":
            raise
        return True
    return False


def key_reuse_oracle(graph, states, label) -> bool:
    """The user's rule (2026-10-24): a key the revision brings back, here
    `d` or `v` after a rekey, is refused while another source that is not
    retired cites it."""
    return states[label] in KEY_DROPS and any(
        label in graph[other] and states[other] != "withdrawn"
        for other in graph
        if other != label
    )


# The states that decide key reuse: a source that holds `d` and `v`, one
# that dropped one of them, and a citer that still reads (pending) or reads
# nothing.
KEY_DROPS = ("rekeyed", "rekeyed_v")
KEY_STATES = ("ok", *KEY_DROPS, "pending", "withdrawn")


async def search(count, states):
    labels = LABELS[:count]
    tally, failures = Counter(), []
    for graph in graphs(labels):
        for label in labels:
            tally["cycle refusal"] += 1
            want, got = cyclic_from(graph, label), refused(graph, label)
            if want != got:
                failures.append(("cycle", graph, label, want, got))
        if not acyclic(graph):
            continue
        tally["acyclic graphs"] += 1
        for chosen in product(KEY_STATES, repeat=count):
            world = dict(zip(labels, chosen))
            for label in labels:
                if world[label] not in ("ok", *KEY_DROPS):
                    continue
                tally["key reuse cases"] += 1
                want = key_reuse_oracle(graph, world, label)
                got = key_reused(graph, world, label)
                if want != got:
                    failures.append(("key reuse", graph, world, label, want, got))
        for chosen in product(states, repeat=count):
            world = dict(zip(labels, chosen))
            tally["withholding worlds"] += 1
            want, got = oracle(graph, world), await held_now(graph, world)
            if want != got:
                failures.append(("withholding", graph, world, want, got))
    return tally, failures


def run(count=len(LABELS), states=STATES):
    return asyncio.run(search(count, states))


def skip(*_):
    return None


def one_level_closure(held, readers):
    """Withholding spreads one citation down, not down the whole chain."""
    above = {source: dict(entries) for source, entries in held.items()}
    held = {source: dict(entries) for source, entries in held.items()}
    for source, reader in sorted(readers.items()):
        for key, item in saved_records(reader).items():
            cited = str(item.identity_data_id)
            if cited in readers and REGISTRY[item.record_type].held(
                above.get(cited, {}), readers[cited], item.record_id
            ):
                entry = Withheld(
                    chains.Reason.CHANGED, Status.UPSTREAM_WITHHELD, frozenset([key])
                )
                for assignment in chains.citing(reader, [key]):
                    entries = held.setdefault(source, {})
                    entries[assignment] = combine(entries.get(assignment), entry)
    return held


def removed_reads_changed(rows, failed=frozenset()):
    """A record gone from its source reads as changed, not removed."""
    read = withholding.record_reader(rows, failed)

    def changed(item):
        found = read(item)
        return withholding.CHANGED if found == withholding.REMOVED else found

    return changed


def key_reuse_only_previous(source, rows, keys):
    """Key reuse judged against the revision before only, as the fresh-key
    rules are: a citer of an earlier life is not looked for."""
    return None


def key_reuse_served_citers(source, rows, keys):
    """Only a served citer counts, so a pending citer's citation is missed."""
    original = MUTANT_ORIGINALS["check_record_key_reuse"]
    return original(source, [r for r in rows if r.is_served], keys)


def key_reuse_resolutions_only(source, rows, keys):
    """Only a resolution key is looked for, so a variant key comes back."""
    original = MUTANT_ORIGINALS["check_record_key_reuse"]
    return original(source, rows, set(keys) & set(source.mention_resolutions))


MUTANT_ORIGINALS = {"check_record_key_reuse": chains.check_record_key_reuse}
MUTANTS = {
    "no_cycle_check": ("check_citation_cycles", skip),
    "one_level_closure": ("upstream_closure", one_level_closure),
    "removed_reads_changed": ("record_reader", removed_reads_changed),
    "key_reuse_unchecked": ("check_record_key_reuse", key_reuse_only_previous),
    "key_reuse_served_citers": ("check_record_key_reuse", key_reuse_served_citers),
    "key_reuse_resolutions_only": (
        "check_record_key_reuse",
        key_reuse_resolutions_only,
    ),
}


@contextmanager
def patched(name):
    attribute, replacement = MUTANTS[name]
    original = getattr(chains, attribute)
    setattr(chains, attribute, replacement)
    try:
        yield
    finally:
        setattr(chains, attribute, original)


def run_mutants(count=3):
    caught = {}
    for name in MUTANTS:
        with patched(name):
            _, failures = run(count)
        caught[name] = failures[0] if failures else None
    return caught


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sources", type=int, default=len(LABELS))
    parser.add_argument("--mutants", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    if args.mutants:
        caught = {**run_mutants(), **cascade_check.run_mutants()}
        missed = [n for n, f in caught.items() if f is None]
        for name in caught:
            print(f"{'MISSED' if name in missed else 'caught'}  {name}")
        print(f"{'FAIL' if missed else 'PASS'} in {time.monotonic() - started:.1f} s")
        sys.exit(1 if missed else 0)
    tally, failures = run(args.sources)
    more, cascade_failures = cascade_check.search(args.sources)
    tally.update(more)
    failures += cascade_failures
    for name, count in sorted(tally.items()):
        print(f"{name}: {count}")
    for failure in failures[:5]:
        print("FAIL", failure)
    print(
        f"{'FAIL' if failures else 'PASS'}: {len(failures)} disagreements, "
        f"{args.sources} sources, {time.monotonic() - started:.1f} s"
    )
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
