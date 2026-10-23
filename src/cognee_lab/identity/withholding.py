"""Decisions withheld from retrieval because an input they read changed.

A text edit of a consumed document records, in its own attempt, which
decisions of its dependents read what changed: `classify` compares each input
a dependent read from that document with the new text, and
`withhold_dependents` writes one row per affected (dependent, decision,
input). An unchanged span is valid automatically. A span whose text is found
exactly once elsewhere moved (`remap`): `refresh_dependents` writes its new
range. Anything else needs review (`refresh_needed`): a reviewer re-confirms
or replaces the decision.

The rows live in their own table beside the ledger, not in RecordStore.
`withheld_decisions` merges them with a rule derived from the ledger: while a
consumed source's text change is pending or failed, every decision citing
that document is withheld, so a crash before the rows are written never
serves a dependent stale. Withholding writes no recovery events.
"""

import json
from dataclasses import asdict, dataclass
from typing import NamedTuple

from sqlalchemy import Integer, String, delete, select, tuple_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import ChunkInput, IdentitySource, SourceTextInput, TextSpanInput
from .validation import INPUT_CHANGED, INPUT_REMOVED, decision_inputs, text_digest

REMAP = "remap"
REFRESH_NEEDED = "refresh_needed"
EDIT_UNFINISHED = "edit_unfinished"
# When several inputs withhold one decision, it shows the strongest status:
# an unfinished edit blocks a review, and a review blocks a refresh.
STATUS_ORDER = (REMAP, REFRESH_NEEDED, EDIT_UNFINISHED)
UNCHANGED, MOVED, CHANGED = "unchanged", "moved", "changed"


class Base(DeclarativeBase):
    pass


class Withholding(Base):
    __tablename__ = "lab_identity_withholdings"
    dataset: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(36), primary_key=True)
    assignment: Mapped[str] = mapped_column(String(255), primary_key=True)
    input_ref: Mapped[str] = mapped_column(String(255), primary_key=True)
    consumed: Mapped[str] = mapped_column(String(36))
    edit_revision: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    old_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_end: Mapped[int | None] = mapped_column(Integer, nullable=True)


@dataclass(frozen=True)
class WithholdingRow:
    """One decision of a dependent withheld because one input it read
    changed. `consumed` is the edited source and `edit_revision` the revision
    whose text was classified. A moved span carries its new range."""

    dataset: str
    source: str
    assignment: str
    input_ref: str
    consumed: str
    edit_revision: int
    reason: str
    status: str
    old_digest: str | None
    new_digest: str | None
    new_start: int | None = None
    new_end: int | None = None


@dataclass(frozen=True)
class Classified:
    """What an edit did to one input a dependent read from the document."""

    input_ref: str
    outcome: str  # UNCHANGED, MOVED or CHANGED
    old_digest: str | None
    new_digest: str | None
    new_range: tuple[int, int] | None = None


class Withheld(NamedTuple):
    """One entry of the withheld-decision set: why, what answers it, and the
    input keys of the decision that withhold it."""

    reason: str
    status: str
    inputs: frozenset[str] = frozenset()


WithheldSet = dict[str, dict[str, Withheld]]  # source -> assignment -> entry


class WithholdingStore:
    """The withholding table, through the ledger's relational sessions. Each
    call creates the table if it is missing, so a store made before this
    table opens unchanged."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def initialize(self):
        async with self.session_factory() as session:
            connection = await session.connection()
            await connection.run_sync(Base.metadata.create_all)
            await session.commit()

    async def rows(self, dataset=None) -> list[WithholdingRow]:
        await self.initialize()
        async with self.session_factory() as session:
            statement = select(Withholding)
            if dataset is not None:
                statement = statement.where(Withholding.dataset == str(dataset))
            found = (await session.execute(statement)).scalars().all()
            return sorted(
                (
                    WithholdingRow(
                        **{f: getattr(r, f) for f in WithholdingRow.__annotations__}
                    )
                    for r in found
                ),
                key=lambda r: (r.source, r.assignment, r.input_ref),
            )

    async def replace(self, cleared, rows):
        """Delete the rows of each (dataset, source, input_ref) in `cleared`,
        then write `rows`, in one transaction."""
        await self.initialize()
        async with self.session_factory() as session:
            if cleared:
                await session.execute(
                    delete(Withholding).where(
                        tuple_(
                            Withholding.dataset,
                            Withholding.source,
                            Withholding.input_ref,
                        ).in_(sorted(set(cleared)))
                    )
                )
            for row in rows:
                await session.merge(Withholding(**asdict(row)))
            await session.commit()

    async def keep(self, dataset, source, kept):
        """Delete the source's rows whose (assignment, input_ref) is not in
        `kept`."""
        await self.initialize()
        async with self.session_factory() as session:
            found = (
                (
                    await session.execute(
                        select(Withholding).where(
                            Withholding.dataset == str(dataset),
                            Withholding.source == str(source),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for row in found:
                if (row.assignment, row.input_ref) not in kept:
                    await session.delete(row)
            await session.commit()


def document_inputs(reader: IdentitySource, data_id) -> set[str]:
    """The reader's inputs that read a document: its text inputs and every
    span or chunk of them."""
    texts = {
        k
        for k, i in reader.inputs.items()
        if isinstance(i, SourceTextInput) and str(i.data_id) == str(data_id)
    }
    return texts | {
        k
        for k, i in reader.inputs.items()
        if isinstance(i, (ChunkInput, TextSpanInput)) and i.document_ref in texts
    }


def citing(reader: IdentitySource, keys) -> set[str]:
    """The decisions that cite any of `keys` directly."""
    return {a for a, inputs in decision_inputs(reader).items() if inputs & set(keys)}


def found_once(text: str, length: int, digest: str) -> int | None:
    """The start of the one window of `text` with this length and digest, or
    None when there is no such window or more than one."""
    found = None
    for start in range(len(text) - length + 1):
        if text_digest(text[start : start + length]) == digest:
            if found is not None:
                return None
            found = start
    return found


def classify_span(key, item, text):
    """An unchanged span validates in place. One whose text is found exactly
    once in the new text moved. Anything else changed. The span's text is
    found by its length and digest, never by slicing an earlier text, so a
    retry, or an edit after an unrefreshed move, classifies the same way."""
    here = text[item.start : item.end] if item.end <= len(text) else None
    if here is not None and text_digest(here) == item.text_sha256:
        return Classified(key, UNCHANGED, item.text_sha256, item.text_sha256)
    length = item.end - item.start
    found = found_once(text, length, item.text_sha256)
    if found is not None:
        return Classified(
            key, MOVED, item.text_sha256, item.text_sha256, (found, found + length)
        )
    return Classified(
        key, CHANGED, item.text_sha256, text_digest(here) if here else None
    )


def classify(reader, data_id, previous_text, text) -> list[Classified]:
    """What changing a document's text from `previous_text` to `text` did to
    each input the reader read from it. A text input is classified only when
    a decision cites it directly; a chunk has no fingerprint and is renumbered,
    so any change needs review."""
    keys = document_inputs(reader, data_id)
    direct = set().union(*decision_inputs(reader).values())
    found = []
    for key in sorted(keys):
        item = reader.inputs[key]
        if isinstance(item, SourceTextInput):
            if key in direct:
                new = text_digest(text)
                outcome = UNCHANGED if new == item.text_sha256 else CHANGED
                found.append(Classified(key, outcome, item.text_sha256, new))
        elif isinstance(item, TextSpanInput):
            found.append(classify_span(key, item, text))
        else:
            outcome = UNCHANGED if previous_text == text else CHANGED
            found.append(Classified(key, outcome, None, None))
    return found


async def withhold_dependents(publisher, edited, previous_text, text, revision):
    """Record, before the edit completes, which decisions of every current
    dependent read what the edit changed. Idempotent: each run recomputes the
    rows of every input of the document and replaces them, so a retry or a
    later edit converges."""
    store = publisher.withholdings
    doc = edited.inputs[edited.original_input_ref].data_id
    own = (str(edited.dataset_id), str(edited.identity_data_id))
    cleared, written = [], []
    for row in await publisher.records.rows():
        if (row.dataset, row.source) == own or row.is_retired:
            continue
        reader = IdentitySource.model_validate_json(row.description)
        for c in classify(reader, doc, previous_text, text):
            cleared.append((row.dataset, row.source, c.input_ref))
            if c.outcome == UNCHANGED:
                continue
            for assignment in sorted(citing(reader, [c.input_ref])):
                written.append(
                    WithholdingRow(
                        dataset=row.dataset,
                        source=row.source,
                        assignment=assignment,
                        input_ref=c.input_ref,
                        consumed=own[1],
                        edit_revision=revision,
                        reason=INPUT_CHANGED,
                        status=REMAP if c.outcome == MOVED else REFRESH_NEEDED,
                        old_digest=c.old_digest,
                        new_digest=c.new_digest,
                        new_start=c.new_range[0] if c.new_range else None,
                        new_end=c.new_range[1] if c.new_range else None,
                    )
                )
    await store.replace(cleared, written)
    return [asdict(r) for r in written]


def combine(previous: Withheld | None, entry: Withheld) -> Withheld:
    """One entry for a decision withheld more than once: `input_removed` over
    `input_changed`, the strongest status, and every withholding input."""
    if previous is None:
        return entry
    return Withheld(
        (
            INPUT_REMOVED
            if INPUT_REMOVED in (previous.reason, entry.reason)
            else entry.reason
        ),
        max(previous.status, entry.status, key=STATUS_ORDER.index),
        previous.inputs | entry.inputs,
    )


def merge(held: WithheldSet, source, assignment, entry: Withheld):
    entries = held.setdefault(source, {})
    entries[assignment] = combine(entries.get(assignment), entry)


def unfinished_edits(rows):
    """Sources whose latest text change is pending or failed."""
    return [
        r
        for r in rows
        if r.state in ("pending", "failed")
        and r.operation == "identity_replace"
        and r.plan.get("text_change")
    ]


def recorded_rows(rows, table) -> list[WithholdingRow]:
    """The table rows that still apply: the dependent is not retired, and its
    saved description still has the decision citing that input."""
    readers = {
        r.source: IdentitySource.model_validate_json(r.description)
        for r in rows
        if not r.is_retired
    }
    return [
        w
        for w in table
        if w.source in readers
        and w.input_ref in decision_inputs(readers[w.source]).get(w.assignment, ())
    ]


async def withheld_decisions(rows, store) -> WithheldSet:
    """The withheld-decision set: the recorded rows that still apply, and
    every decision citing a document whose text change is pending or failed
    (`input_changed`, status `edit_unfinished`)."""
    held: WithheldSet = {}
    for w in recorded_rows(rows, await store.rows()):
        merge(
            held,
            w.source,
            w.assignment,
            Withheld(w.reason, w.status, frozenset([w.input_ref])),
        )
    readers = {
        r.source: IdentitySource.model_validate_json(r.description)
        for r in rows
        if not r.is_retired
    }
    for edit in unfinished_edits(rows):
        edited = IdentitySource.model_validate_json(edit.description)
        doc = edited.inputs[edited.original_input_ref].data_id
        for source, reader in readers.items():
            if source == edit.source:
                continue
            keys = document_inputs(reader, doc)
            for assignment, inputs in decision_inputs(reader).items():
                if inputs & keys:
                    merge(
                        held,
                        source,
                        assignment,
                        Withheld(INPUT_CHANGED, EDIT_UNFINISHED, inputs & keys),
                    )
    return held


def remapped(reader: IdentitySource, moved) -> IdentitySource:
    """The dependent's next revision with each moved span at its new range.
    Its decisions, producers and every other input are unchanged."""
    payload = reader.model_dump(mode="json")
    payload["revision"] += 1
    for w in moved:
        payload["inputs"][w.input_ref].update(start=w.new_start, end=w.new_end)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def refresh_dependents(publisher, replace):
    """After an edit completes, write each current dependent's next revision
    with its moved spans' new ranges: an ordinary unchanged-text replacement,
    `replace(description, expected_revision)`, whose withholding cleanup
    releases the moved decisions once it completes. A rerun finishes an
    interrupted refresh: a dependent whose refresh failed resumes its saved
    revision. A span moved by an edit that is still pending or failed waits
    for that edit."""
    rows = await publisher.records.rows()
    table = recorded_rows(rows, await publisher.withholdings.rows())
    waiting = {r.source for r in unfinished_edits(rows)}
    refreshed = []
    for row in rows:
        moved = [
            w
            for w in table
            if w.source == row.source
            and w.status == REMAP
            and w.consumed not in waiting
        ]
        if not moved:
            continue
        saved = IdentitySource.model_validate_json(row.description)
        if row.state == "current":
            revised = remapped(saved, moved)
        elif row.resumed_by == "replace":
            revised = saved
        else:
            continue
        await replace(revised, expected_revision=row.revision)
        refreshed.append(
            dict(
                identity_data_id=row.source,
                revision=revised.revision,
                inputs={
                    w.input_ref: dict(start=w.new_start, end=w.new_end) for w in moved
                },
            )
        )
    return refreshed


def cited_inputs(source: IdentitySource) -> set[str]:
    """Every input key a record or scope cites, with the documents of cited
    spans and chunks."""
    cited = {source.original_input_ref}
    for group in source.mention_groups.values():
        cited.update([group.document_ref, *group.chunk_refs, *group.input_refs])
    for inputs in decision_inputs(source).values():
        cited.update(inputs)
    for key in list(cited):
        document = getattr(source.inputs[key], "document_ref", None)
        if document:
            cited.add(document)
    return cited


def reconfirmed(reader, assignment, replacements, producer_key, producer):
    """Copy-on-write re-confirm of one withheld decision: its next revision
    cites each new input in place of the changed one under a producer new in
    this revision. Other decisions keep citing the old input, so they stay
    withheld until each is re-confirmed; an old input nothing cites any more
    is dropped. `replacements` maps an old input key to (new key, input)."""
    payload = reader.model_dump(mode="json")
    payload["revision"] += 1
    records = [
        payload["mention_resolutions"].get(assignment)
        or payload["variant_assignments"][assignment]
    ]
    if assignment in payload["mention_resolutions"]:
        records.append(payload["mention_groups"][records[0]["group_ref"]])
    for old, (new, item) in replacements.items():
        payload["inputs"][new] = item
        for record in records:
            record["input_refs"] = [
                new if k == old else k for k in record["input_refs"]
            ]
    records[0]["producer_ref"] = producer_key
    payload["producers"][producer_key] = producer
    revised = IdentitySource.model_validate_json(json.dumps(payload))
    uncited = set(replacements) - cited_inputs(revised)
    for key in uncited:
        payload["inputs"].pop(key)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def withholding_status(publisher, rows):
    """What `status` lists: the recorded rows that still apply, and the
    withheld-decision set retrieval applies (live validation included, so
    this reads the graph) with the decisions a reviewer answers."""
    from .retrieve import withheld_now

    held = await withheld_now(publisher, rows)
    decisions = [
        dict(
            identity_data_id=source,
            assignment_id=key,
            reason=w.reason,
            status=w.status,
            input_refs=sorted(w.inputs),
        )
        for source, entries in sorted(held.items())
        for key, w in sorted(entries.items())
    ]
    return dict(
        withholdings=[
            asdict(w) for w in recorded_rows(rows, await publisher.withholdings.rows())
        ],
        withheld_decisions=decisions,
        refresh_needed=[d for d in decisions if d["status"] == REFRESH_NEEDED],
    )
