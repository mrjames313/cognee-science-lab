"""Bounded exhaustive check of saved-record chains.

On every citation graph of up to four sources (chain_worlds.py), it checks:

- Cycles. Admitting any source's citations is refused (`citation_cycle`)
  exactly when a path of citations leads from that source back to it, so a
  graph is admitted if and only if it is acyclic.
- Withholding. On every acyclic graph, with every source in every state
  (ok, held, replaced, rekeyed, pending, withdrawn, invalid), the
  withheld-decision set that retrieval and `status` read equals the
  oracle's: each decision's reason, status and withholding inputs, with
  withholding spread down the whole chain as `input_changed` and
  `upstream_withheld`.

The code under test is chains.check_citation_cycles, chains.record_reader,
withholding.withheld_decisions and chains.close_live, which retrieve's live
pass calls. Live validation of the documents is replaced by the reader's
answer for each cited record and, for an invalid source, its IntentError.

With --mutants, each scratch break in MUTANTS must make the check fail.

    uv run python support/chain_check.py
    uv run python support/chain_check.py --mutants
"""

import argparse
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
from cognee_lab.identity import chains
from cognee_lab.identity.records import saved_records
from cognee_lab.identity.retrieve import is_served
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


def held_now(graph, states):
    """The withheld-decision set of the served sources that validate."""
    rows, table = world_rows(graph, states)
    withheld = withheld_decisions(rows, table)
    reader = chains.record_reader(rows)
    invalid = {str(identity(label)) for label in graph if states[label] == "invalid"}
    found = {}
    for row in rows:
        if not is_served(row):
            continue
        source = row.description
        if row.source in invalid:
            found[row.source] = (source, row, IntentError("source_changed", "x"))
            continue
        drift = {
            key: reason
            for key, item in saved_records(source).items()
            if (reason := reader(item)) is not None
        }
        found[row.source] = (source, row, drift)
    return {
        key: held
        for key, (_, _, held) in chains.close_live(found, withheld).items()
        if not isinstance(held, IntentError) and held
    }


def run(count=len(LABELS), states=STATES):
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
            want, got = oracle(graph, world), held_now(graph, world)
            if want != got:
                failures.append(("withholding", graph, world, want, got))
    return tally, failures


def skip(*_):
    return None


def one_level_closure(held, readers, failed=frozenset()):
    """Withholding spreads one citation down, not down the whole chain."""
    held = {source: dict(entries) for source, entries in held.items()}
    chains.citing_unfinished(held, readers, failed)
    above = {source: set(entries) for source, entries in held.items()}
    for source, reader in sorted(readers.items()):
        for key, item in saved_records(reader).items():
            if item.record_id in above.get(str(item.identity_data_id), ()):
                entry = Withheld(
                    chains.Reason.CHANGED, Status.UPSTREAM_WITHHELD, frozenset([key])
                )
                for assignment in chains.citing(reader, [key]):
                    entries = held.setdefault(source, {})
                    entries[assignment] = combine(entries.get(assignment), entry)
    return held


_bound_reader = chains.record_reader


def removed_reads_changed(rows):
    """A record gone from its source reads as changed, not removed."""
    read = _bound_reader(rows)

    def changed(item):
        reason = read(item)
        return chains.Reason.CHANGED if reason is not None else None

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
