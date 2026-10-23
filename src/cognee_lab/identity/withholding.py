"""Decisions withheld from retrieval because an input they read changed.

A text edit of a consumed document records, in its own attempt, which
decisions of its dependents read what changed: `classify` compares each input
a dependent read from that document with the new text, and
`withhold_dependents` writes one row per affected (dependent, decision,
input). An unchanged span is valid automatically. A span whose text is
found exactly once elsewhere moved (`remap`): `revisions.refresh_dependents`
writes its new range. Anything else needs review (`refresh_needed`): a
reviewer re-confirms or replaces the decision.

The rows live in their own table beside the ledger, not in RecordStore.
`withheld_decisions` merges them with a rule derived from the ledger: while a
consumed source's text change is pending or failed, every decision citing
that document is withheld, so a crash before the rows are written never
serves a dependent stale. Withholding writes no recovery events.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import NamedTuple

from sqlalchemy import Integer, String, delete, select, tuple_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import ChunkInput, IdentitySource, SourceTextInput, TextSpanInput
from .retirement import consumes
from .validation import (
    Reason,
    decision_inputs,
    stronger,
    text_digest,
)


class Status(StrEnum):
    """What answers a withheld decision. Members are in increasing
    precedence: when several inputs withhold one decision it shows the
    strongest, since an unfinished edit blocks a review and a review blocks
    a refresh."""

    REMAP = "remap"
    REFRESH_NEEDED = "refresh_needed"
    EDIT_UNFINISHED = "edit_unfinished"


class Outcome(StrEnum):
    """What an edit did to one input a dependent read from the document."""

    UNCHANGED = "unchanged"
    MOVED = "moved"
    CHANGED = "changed"


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
    reason: Reason
    status: Status
    old_digest: str | None
    new_digest: str | None
    new_start: int | None = None
    new_end: int | None = None


@dataclass(frozen=True)
class Classified:
    """What an edit did to one input a dependent read from the document."""

    input_ref: str
    outcome: Outcome
    old_digest: str | None
    new_digest: str | None
    new_range: tuple[int, int] | None = None


class Withheld(NamedTuple):
    """One entry of the withheld-decision set: why, what answers it, and the
    input keys of the decision that withhold it."""

    reason: Reason
    status: Status
    inputs: frozenset[str] = frozenset()


WithheldSet = dict[str, dict[str, Withheld]]  # source -> assignment -> entry


class WithholdingStore:
    """The withholding table, through the ledger's relational sessions.
    `Publisher.configured` creates the table if it is missing, so a store
    made before this table opens unchanged."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def initialize(self):
        async with self.session_factory() as session:
            connection = await session.connection()
            await connection.run_sync(Base.metadata.create_all)
            await session.commit()

    async def rows(self, dataset=None) -> list[WithholdingRow]:
        async with self.session_factory() as session:
            statement = select(Withholding)
            if dataset is not None:
                statement = statement.where(Withholding.dataset == str(dataset))
            found = (await session.execute(statement)).scalars().all()
        rows = []
        for r in found:
            fields = {f: getattr(r, f) for f in WithholdingRow.__annotations__}
            fields.update(reason=Reason(r.reason), status=Status(r.status))
            rows.append(WithholdingRow(**fields))
        return sorted(rows, key=lambda r: (r.source, r.assignment, r.input_ref))

    async def replace(self, cleared, rows):
        """Delete the rows of each (dataset, source, input_ref) in `cleared`,
        then write `rows`, in one transaction."""
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


def document_inputs(reader: IdentitySource, target: IdentitySource) -> set[str]:
    """The reader's inputs that read the target's document: the text inputs
    through which it consumes that document (retirement.consumes) and every
    span or chunk of them."""
    texts = {
        d["input_ref"] for d in consumes(reader, target) if d["kind"] == "source_text"
    }
    return texts | {
        k
        for k, i in reader.inputs.items()
        if isinstance(i, (ChunkInput, TextSpanInput)) and i.document_ref in texts
    }


def current_readers(rows) -> dict[str, IdentitySource]:
    """The saved description of every source that is not retired: withdrawn
    and forgotten sources read nothing."""
    return {
        r.source: IdentitySource.model_validate_json(r.description)
        for r in rows
        if not r.is_retired
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
        return Classified(key, Outcome.UNCHANGED, item.text_sha256, item.text_sha256)
    length = item.end - item.start
    found = found_once(text, length, item.text_sha256)
    if found is not None:
        return Classified(
            key,
            Outcome.MOVED,
            item.text_sha256,
            item.text_sha256,
            (found, found + length),
        )
    return Classified(
        key, Outcome.CHANGED, item.text_sha256, text_digest(here) if here else None
    )


def classify(reader, keys, previous_text, text) -> list[Classified]:
    """What changing a document's text from `previous_text` to `text` did to
    each of `keys`, the reader's inputs of that document. A text input is
    classified only when a decision cites it directly; a chunk has no
    fingerprint and is renumbered, so any change needs review."""
    direct = set().union(*decision_inputs(reader).values())
    found = []
    for key in sorted(keys):
        item = reader.inputs[key]
        if isinstance(item, SourceTextInput):
            if key in direct:
                new = text_digest(text)
                outcome = (
                    Outcome.UNCHANGED if new == item.text_sha256 else Outcome.CHANGED
                )
                found.append(Classified(key, outcome, item.text_sha256, new))
        elif isinstance(item, TextSpanInput):
            found.append(classify_span(key, item, text))
        else:
            outcome = Outcome.UNCHANGED if previous_text == text else Outcome.CHANGED
            found.append(Classified(key, outcome, None, None))
    return found


async def withhold_dependents(publisher, edited, previous_text, text, revision):
    """Record, before the edit completes, which decisions of every current
    dependent read what the edit changed. Idempotent: each run recomputes the
    rows of every input of the document and replaces them, so a retry or a
    later edit converges."""
    own = str(edited.identity_data_id)
    cleared, written = [], []
    for source, reader in current_readers(await publisher.records.rows()).items():
        if source == own:
            continue
        dataset = str(reader.dataset_id)
        keys = document_inputs(reader, edited)
        for c in classify(reader, keys, previous_text, text):
            cleared.append((dataset, source, c.input_ref))
            if c.outcome == Outcome.UNCHANGED:
                continue
            for assignment in sorted(citing(reader, [c.input_ref])):
                written.append(
                    WithholdingRow(
                        dataset=dataset,
                        source=source,
                        assignment=assignment,
                        input_ref=c.input_ref,
                        consumed=own,
                        edit_revision=revision,
                        reason=Reason.CHANGED,
                        status=(
                            Status.REMAP
                            if c.outcome == Outcome.MOVED
                            else Status.REFRESH_NEEDED
                        ),
                        old_digest=c.old_digest,
                        new_digest=c.new_digest,
                        new_start=c.new_range[0] if c.new_range else None,
                        new_end=c.new_range[1] if c.new_range else None,
                    )
                )
    await publisher.withholdings.replace(cleared, written)
    return [asdict(r) for r in written]


def combine(previous: Withheld | None, entry: Withheld) -> Withheld:
    """One entry for a decision withheld more than once: the stronger reason
    and status, and every withholding input."""
    if previous is None:
        return entry
    return Withheld(
        stronger(previous.reason, entry.reason),
        stronger(previous.status, entry.status),
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


def recorded_rows(readers, table) -> list[WithholdingRow]:
    """The table rows that still apply: the dependent is one of the current
    `readers`, and its saved description still has the decision citing that
    input."""
    return [
        w
        for w in table
        if w.source in readers
        and w.input_ref in decision_inputs(readers[w.source]).get(w.assignment, ())
    ]


def withheld_decisions(rows, table) -> WithheldSet:
    """The withheld-decision set of the ledger rows and the withholding
    table: the recorded rows that still apply, and every decision citing a
    document whose text change is pending or failed (`input_changed`, status
    `edit_unfinished`)."""
    readers = current_readers(rows)
    held: WithheldSet = {}
    for w in recorded_rows(readers, table):
        entry = Withheld(w.reason, w.status, frozenset([w.input_ref]))
        merge(held, w.source, w.assignment, entry)
    for edit in unfinished_edits(rows):
        edited = IdentitySource.model_validate_json(edit.description)
        for source, reader in readers.items():
            if source == edit.source:
                continue
            keys = document_inputs(reader, edited)
            for assignment, inputs in decision_inputs(reader).items():
                if inputs & keys:
                    entry = Withheld(
                        Reason.CHANGED, Status.EDIT_UNFINISHED, inputs & keys
                    )
                    merge(held, source, assignment, entry)
    return held


async def pending_moves(publisher):
    """Each source's row with the `remap` rows that still apply to it and
    whose edit completed. A span moved by an edit that is still pending or
    failed waits for that edit."""
    rows = await publisher.records.rows()
    table = recorded_rows(current_readers(rows), await publisher.withholdings.rows())
    waiting = {r.source for r in unfinished_edits(rows)}
    found = {}
    for row in rows:
        moved = [
            w
            for w in table
            if w.source == row.source
            and w.status == Status.REMAP
            and w.consumed not in waiting
        ]
        if moved:
            found[row.source] = (row, moved)
    return found
