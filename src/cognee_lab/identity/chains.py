"""Chains of saved-record citations: who cites whose records, the rules that
admit a citation, and how withholding spreads down a chain.

A source cites another source's record through a saved-record input
(records.py says what it pins). The citations form a source graph, with an
edge from A to B when A cites any record of B. Admission keeps it acyclic,
so every chain has a top. Nothing here writes: withholding down a chain is
derived each time from the ledger rows, the withholding table and live
validation (`live_pass`), and releases as soon as its cause does.
"""

from collections.abc import Awaitable, Callable, Mapping

from .models import IdentitySource
from .records import (
    REGISTRY,
    cited_row,
    names_record,
    record_digest,
    record_keys,
    saved_records,
)
from .storage import PublicationRow
from .validation import IntentError, Reason
from .withholding import (
    RecordReader,
    Status,
    Withheld,
    WithheldSet,
    citing,
    combine,
    held_by,
    merge,
    record_reader,
)


def check_citation_scope(description):
    """A saved record cited is another source's, in the same dataset. A
    source's own decisions already relate through its groups and inputs,
    and a citation of its own record would pin the revision being
    written."""
    for item in saved_records(description).values():
        if item.dataset_id != description.dataset_id:
            raise IntentError(
                "not_admitted", "A saved record cited is of the same dataset"
            )
        if item.identity_data_id == description.identity_data_id:
            raise IntentError(
                "self_citation", "A source does not cite its own saved records"
            )


def new_citations(source, previous) -> set[str]:
    """The saved-record keys a first attempt adds: every key of a first
    publication or a re-add, and on a replacement the keys the current
    revision lacks. A retry or a reconcile reuses its saved intent, so it
    adds none: a record that drifted since the attempt began is admitted
    and withheld, as an existing key is."""
    if previous is None or previous.tombstone is not None:
        return set(saved_records(source))
    if previous.state == "current" and previous.revision < source.revision:
        return set(saved_records(source)) - set(previous.description.inputs)
    return set()


def new_record_keys(source, previous) -> set[str]:
    """The record keys a first attempt adds, of every type: every key of a
    first publication or a re-add, and on a replacement the keys the
    current revision lacks. A retry or a reconcile reuses its saved intent,
    so it adds none."""
    if previous is None or previous.tombstone is not None:
        return set(record_keys(source))
    if previous.state == "current" and previous.revision < source.revision:
        return set(record_keys(source)) - set(record_keys(previous.description))
    return set()


def check_record_key_reuse(source, rows, keys):
    """Invariant: a record key that another source cites names one record
    of this source for as long as the citation lasts. A citation pins its
    record by key and fingerprint, so a key that came back (the same
    reviewed fields fingerprint the same) would serve the old citation a
    record nobody reviewed for it. So a key this revision adds (`keys`,
    `new_record_keys`) that another source's saved description, not
    retired, still cites at this source is refused. That citation was made
    against an earlier life of the key: the key is absent from the revision
    before. Only a first attempt checks this, as `check_record_citations`."""
    own = str(source.identity_data_id)
    for row in rows:
        if row.is_retired or row.source == own:
            continue
        for item in saved_records(row.description).values():
            if item.record_id in keys and names_record(item, own, item.record_id):
                raise IntentError(
                    "record_key_reused",
                    f"Another source still cites an earlier {item.record_id} of "
                    "this source; give the record a new key",
                )


def check_record_citations(source, rows, keys):
    """Each newly cited record is, as the citation pins it, a record of a
    served source at that source's current revision. Only a first attempt
    checks this (`new_citations`)."""
    for key in sorted(keys):
        item = source.inputs[key]
        row = cited_row(rows, item)
        if row is None or not row.is_served:
            raise IntentError(
                "record_source_unavailable",
                f"The cited source is not served: {key}",
            )
        digest = record_digest(row.description, item.record_type, item.record_id)
        if digest is None:
            raise IntentError("record_missing", f"No such saved record: {key}")
        if item.representation_revision != row.revision:
            raise IntentError(
                "record_stale",
                f"A new citation pins the cited source's current revision: {key}",
            )
        if digest != item.content_sha256:
            raise IntentError(
                "record_digest", f"The cited record's fingerprint differs: {key}"
            )


def source_graph(descriptions: Mapping[str, IdentitySource]) -> dict[str, set[str]]:
    """Each source's cited sources: an edge from A to B when A cites any
    record of B."""
    return {
        source: {str(i.identity_data_id) for i in saved_records(d).values()}
        for source, d in descriptions.items()
    }


def on_cycle(graph: Mapping[str, set[str]], start: str) -> bool:
    """Whether a path of citations leads from `start` back to it."""
    seen, todo = set(), list(graph.get(start, ()))
    while todo:
        node = todo.pop()
        if node == start:
            return True
        if node not in seen:
            seen.add(node)
            todo.extend(graph.get(node, ()))
    return False


def check_citation_cycles(source, rows):
    """The source graph stays acyclic. It holds the latest saved description
    of every source that is not retired (current, pending and failed) with
    `source` in place of its own, so a failed attempt's citation is already
    an edge and its retry is never refused for a cycle."""
    descriptions = {r.source: r.description for r in rows if not r.is_retired}
    own = str(source.identity_data_id)
    descriptions[own] = source
    if on_cycle(source_graph(descriptions), own):
        raise IntentError(
            "citation_cycle", "A chain of saved-record citations leads back here"
        )


def upstream_closure(
    held: WithheldSet, readers: Mapping[str, IdentitySource]
) -> WithheldSet:
    """`held` with withholding spread down every chain. `readers` are the
    served sources that validate. A decision of one of them that cites a
    withheld record of another is withheld too, with `input_changed` and
    status `upstream_withheld`, which no reviewer answers; whether a record
    is withheld is its type's to say (records.REGISTRY). A cited source
    that is not one of `readers` already gave its citers their entry
    through the record reader. This repeats until nothing changes, which
    reaches the same set as one pass in the topological order of the source
    graph and ends on a cycle that a race could leave. Nothing is written:
    an entry releases when the one above it does."""
    held = {source: dict(entries) for source, entries in held.items()}
    grew = True
    while grew:
        grew = False
        for source, reader in sorted(readers.items()):
            for key, item in sorted(saved_records(reader).items()):
                cited = str(item.identity_data_id)
                if cited not in readers or not REGISTRY[item.record_type].held(
                    held.get(cited, {}), readers[cited], item.record_id
                ):
                    continue
                entry = Withheld(
                    Reason.CHANGED, Status.UPSTREAM_WITHHELD, frozenset([key])
                )
                for assignment in sorted(citing(reader, [key])):
                    before = held.get(source, {}).get(assignment)
                    if combine(before, entry) != before:
                        merge(held, source, assignment, entry)
                        grew = True
    return held


# One served row after the live pass: its source, its row, and its withheld
# decisions or the IntentError of an own input that failed.
Live = tuple[IdentitySource, PublicationRow, dict[str, Withheld] | IntentError]
DriftOf = Callable[[IdentitySource, RecordReader], Awaitable[dict]]


async def live_pass(rows, withheld: WithheldSet, drift_of: DriftOf) -> dict[str, Live]:
    """The one live-validation pass that retrieval and `status` share.
    `drift_of` (retrieve.live_drift) validates each served source with a
    record reader: it returns the foreign inputs that fail, with their
    reasons, or raises the IntentError of an own input that fails. Each
    source that validates holds `withheld`, its entries of the
    withheld-decision set, combined with that drift (withholding.held_by),
    a saved record answered by a reader that counts a cited source that
    failed as unfinished. Then `upstream_closure` spreads withholding down
    every chain."""
    read = record_reader(rows)
    found = {}
    for row in rows:
        if not row.is_served:
            continue
        try:
            found[row.source] = (row, await drift_of(row.description, read))
        except IntentError as exc:
            found[row.source] = (row, exc)
    if failed := {k for k, (_, d) in found.items() if isinstance(d, IntentError)}:
        read = record_reader(rows, failed)
    readers = {k: row.description for k, (row, _) in found.items() if k not in failed}
    held = {
        k: held_by(readers[k], withheld.get(k, {}), found[k][1], read) for k in readers
    }
    closed = upstream_closure(held, readers)
    return {
        k: (row.description, row, drift if k in failed else closed[k])
        for k, (row, drift) in found.items()
    }
