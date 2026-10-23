"""Chains of saved-record citations: who cites whose records, the rules that
admit a citation, and how withholding spreads down a chain.

A source cites another source's record through a saved-record input
(records.py says what it pins). The citations form a source graph, with an
edge from A to B when A cites any record of B. Admission keeps it acyclic,
so every chain has a top. Nothing here writes: withholding down a chain is
derived each time from the ledger rows, the withholding table and live
validation, and releases as soon as its cause does.
"""

from collections.abc import Callable, Mapping

from .models import IdentitySource, SavedRecordInput
from .records import record_digest, saved_records
from .storage import PublicationRow
from .validation import IntentError, Reason, decision_inputs, stronger, withheld_by
from .withholding import (
    Status,
    Withheld,
    WithheldSet,
    citing,
    citing_unfinished,
    combine,
    merge,
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


RecordReader = Callable[[SavedRecordInput], Reason | None]


def record_reader(rows) -> RecordReader:
    """What validation asks of one cited record, from the ledger rows: None
    while the cited source is served with the record under its type and
    pinned fingerprint. A withdrawn, forgotten or missing source, or a key
    its current revision lacks, gives `input_removed`. A pending, failed or
    unverified source, or another fingerprint, gives `input_changed`. An
    unfinished source is checked before anything else, so a pending
    upstream never shows `input_removed`."""
    from .retrieve import is_served

    by_source = {(r.dataset, r.source): r for r in rows}

    def read(item: SavedRecordInput) -> Reason | None:
        row = by_source.get((str(item.dataset_id), str(item.identity_data_id)))
        if row is None or row.is_retired:
            return Reason.REMOVED
        if not is_served(row):
            return Reason.CHANGED
        digest = record_digest(row.description, item.record_type, item.record_id)
        if digest is None:
            return Reason.REMOVED
        return None if digest == item.content_sha256 else Reason.CHANGED

    return read


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


def check_record_citations(source, rows, keys):
    """Each newly cited record is, as the citation pins it, a record of a
    served source at that source's current revision. Only a first attempt
    checks this (`new_citations`)."""
    from .retrieve import is_served

    by_source = {(r.dataset, r.source): r for r in rows}
    for key in sorted(keys):
        item = source.inputs[key]
        row = by_source.get((str(item.dataset_id), str(item.identity_data_id)))
        if row is None or not is_served(row):
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
    held: WithheldSet, readers: Mapping[str, IdentitySource], failed=frozenset()
) -> WithheldSet:
    """`held` with withholding spread down every chain. A decision of one of
    `readers` that cites a record of a source in `failed` (its own input
    failed live validation) is withheld as one citing an unfinished source.
    Then a decision that cites a withheld record is withheld too, with
    `input_changed` and status `upstream_withheld`, which no reviewer
    answers. This repeats until nothing changes, which reaches the same set
    as one pass in the topological order of the source graph. Nothing is
    written: an entry releases when the one above it does."""
    held = {source: dict(entries) for source, entries in held.items()}
    citing_unfinished(held, readers, failed)
    grew = True
    while grew:
        grew = False
        for source, reader in sorted(readers.items()):
            for key, item in sorted(saved_records(reader).items()):
                if item.record_id not in held.get(str(item.identity_data_id), {}):
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


def held_by(source, recorded, drift):
    """The source's withheld decisions: `recorded`, its entries of the
    withheld-decision set, combined with every decision citing an input that
    failed live validation. Live drift that a recorded entry already holds,
    for a reason no stronger, adds nothing: a recorded move still waits for
    its refresh. Anything else no edit classified, so a reviewer answers it
    (`refresh_needed`)."""
    held = dict(recorded)
    cited = decision_inputs(source)
    for key, reason in withheld_by(source, drift).items():
        inputs = cited[key] & set(drift)
        entry = recorded.get(key)
        if (
            entry
            and inputs <= entry.inputs
            and stronger(reason, entry.reason) == entry.reason
        ):
            continue
        held[key] = combine(entry, Withheld(reason, Status.REFRESH_NEEDED, inputs))
    return held


# One served row after live validation: its source, its row, and its
# withheld decisions or the IntentError of an own input that failed.
Live = tuple[IdentitySource, PublicationRow, dict[str, Withheld] | IntentError]


def close_live(found, withheld: WithheldSet) -> dict[str, Live]:
    """The live pass's result, with withholding spread down every chain.
    `found` maps each served source to (source, row, drift): what live
    validation returned, or the IntentError of an own input that failed.
    Each source's held decisions combine `withheld`, its entries of the
    withheld-decision set, with its drift (`held_by`); then
    `upstream_closure` spreads them, and a source that failed counts as
    unfinished for the decisions citing it."""
    held, readers, failed = {}, {}, set()
    for key, (source, _, drift) in found.items():
        if isinstance(drift, IntentError):
            failed.add(key)
            continue
        readers[key] = source
        held[key] = held_by(source, withheld.get(key, {}), drift)
    closed = upstream_closure({**withheld, **held}, readers, failed)
    return {
        key: (
            source,
            row,
            drift if isinstance(drift, IntentError) else closed.get(key, {}),
        )
        for key, (source, row, drift) in found.items()
    }
