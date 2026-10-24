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

The code under test is chains.check_citation_cycles,
withholding.record_reader, withholding.withheld_decisions and
chains.live_pass, the pass that retrieval and `status` run. Only live
validation itself (retrieve.live_drift) is replaced: `drift_of` returns the
reader's answer for each cited record, as validate_inputs does, and raises
for an invalid source.

With --mutants, each scratch break in MUTANTS must make the check fail.

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


MUTANTS = {
    "no_cycle_check": ("check_citation_cycles", skip),
    "one_level_closure": ("upstream_closure", one_level_closure),
    "removed_reads_changed": ("record_reader", removed_reads_changed),
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
        missed = [n for n, f in run_mutants().items() if f is None]
        for name in MUTANTS:
            print(f"{'MISSED' if name in missed else 'caught'}  {name}")
        print(f"{'FAIL' if missed else 'PASS'} in {time.monotonic() - started:.1f} s")
        sys.exit(1 if missed else 0)
    tally, failures = run(args.sources)
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
