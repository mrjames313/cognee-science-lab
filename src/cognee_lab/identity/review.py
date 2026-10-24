"""A reviewer's answer to one withheld decision of the captured glossary
and chain fixtures.

One flow answers each review command (`review`). The gate decides whether
the decision can be reviewed now and whether the command answers its
inputs (`review_gate`, `refuse_command`). The reviewer then reads each
input that withholds the decision as it is now (`Now`): `reconfirm` and
`replace-decision` read it by its kind (`AS_NOW`), `replace-citation`
names the record to cite (`--cite`) or drops the decision (`--drop`). The
intended revision follows from the command and what was read
(`intended_revision`):

- a re-confirm, or a citation of another record, cites each input as it is
  now under a new key (revisions.reconfirmed);
- a replacement is per decision, by its record type (`REPLACEMENTS`): a
  resolution unresolved in place, v01 by a variant for the glossary
  entry's new meaning;
- an input that went, or a dropped citation, is removed from the decision
  as an erasure removes it (records.apply_removal): a resolution stays,
  unresolved, a variant goes.

The review decisions are captured fixture input, not Describe.
"""

from .fixture import expect_current
from .forget_fixture import CALLER_FILES
from .glossary_fixture import INFO, hc_entry
from .models import CorpusObjectInput, SavedRecordInput, TextSpanInput
from .multisource import current_sources
from .records import (
    REGISTRY,
    apply_removal,
    cited_row,
    citation,
    record_type_of,
    saved_records,
)
from .registered import read_texts
from .retrieve import withheld_now
from .revisions import next_revision, reconfirmed, replace_one
from .validation import (
    IntentError,
    Reason,
    fresh_entity_id,
    selected_digest,
    text_digest,
)
from .withholding import Status, document_inputs, unfinished, unfinished_edits

DOC01_REVIEW = "stage6-captured-glossary-review"

# Each input key that withholds the decision: its new key and the input as
# the reviewer reads it now, or None when it is gone or the reviewer drops it.
Now = dict[str, tuple[str, dict] | None]


async def review_gate(publisher, source, decision, command):
    """The withheld entry a reviewer answers, after the gates: no document
    the source reads has an edit that is pending or failed, and no source
    whose records it cites is unfinished (withholding.unfinished, or its own
    input fails live validation), so the reviewer attests committed content;
    the decision waits for review, not for a record above it
    (`upstream_withheld`); and the command answers its inputs
    (`refuse_command`)."""
    rows = await publisher.records.rows()
    for edit in unfinished_edits(rows):
        if document_inputs(source, edit.description):
            raise IntentError(
                "edit_unfinished",
                "Reconcile the edit of a document this source reads before a review",
            )
    entry = (
        (await withheld_now(publisher, rows))
        .get(str(source.identity_data_id), {})
        .get(decision)
    )
    cited = (cited_row(rows, i) for i in saved_records(source).values())
    if any(row and unfinished(row) for row in cited) or (
        entry is not None and entry.status == Status.EDIT_UNFINISHED
    ):
        raise IntentError(
            "edit_unfinished",
            "Reconcile the attempt of a source whose records this source cites before a review",
        )
    if entry is not None and entry.status == Status.UPSTREAM_WITHHELD:
        raise IntentError(
            "upstream_withheld",
            f"{decision} waits for a record it cites; review that record first",
        )
    if entry is None or entry.status != Status.REFRESH_NEEDED:
        raise IntentError(
            "not_withheld", f"{decision} is not withheld for review in this source"
        )
    refuse_command(source, entry, command)
    return entry, rows


def refuse_command(source, entry, command):
    """Whether the command answers the inputs that withhold the decision. A
    removed input is never re-confirmed; the refusal names the answer,
    `replace-citation` for a removed saved record, else `replace-decision`.
    A saved-record citation is replaced only with `replace-citation`, which
    answers nothing else."""
    cites = entry.inputs & set(saved_records(source))
    if command == "reconfirm" and entry.reason == Reason.REMOVED:
        answer = (
            "replace the citation with replace-citation"
            if cites
            else "replace the decision"
        )
        raise IntentError(
            "input_removed", f"A removed input is never re-confirmed; {answer}"
        )
    if command == "replace-decision" and cites:
        raise IntentError(
            "fixture_scope",
            "A saved-record citation is replaced with replace-citation",
        )
    if command == "replace-citation" and entry.inputs - cites:
        raise IntentError(
            "fixture_scope",
            "replace-citation answers a decision withheld by saved-record citations",
        )


def input_digest(item: dict) -> str:
    """What an input pins of its content: a span's digest, or a corpus
    object's or a saved record's fingerprint."""
    return item.get("text_sha256") or item["content_sha256"]


def review_producer(entry, command, source, now: Now):
    """The producer a review names, new in its revision: the withholding it
    answers, and the old digest of each input and the new digest of each
    input that replaces one."""
    return dict(
        method="captured_fixture",
        implementation="re-confirmed" if command == "reconfirm" else "replaced",
        version="0.1",
        configuration=dict(
            policy=DOC01_REVIEW,
            confirmed_by="captured fixture reviewer",
            withholding=[
                dict(input_ref=k, reason=entry.reason, status=entry.status)
                for k in sorted(entry.inputs)
            ],
            old_digests={
                k: input_digest(source.inputs[k].model_dump(mode="json"))
                for k in sorted(now)
            },
            new_digests={
                new: input_digest(item)
                for new, item in (now[k] for k in sorted(now) if now[k])
            },
        ),
        run_id=None,
    )


def current_record(rows, identity_data_id: str, record_id) -> dict | None:
    """A citation of one record as the source `identity_data_id` holds it
    now, or None when no saved description of that source holds it."""
    upstream = next((r.description for r in rows if r.source == identity_data_id), None)
    if upstream is None or record_type_of(upstream, record_id) is None:
        return None
    return citation(upstream, record_id)


async def record_now(publisher, rows, source, item):
    """A saved-record citation of the cited record as its source holds it
    now."""
    return current_record(rows, str(item.identity_data_id), item.record_id)


async def span_now(publisher, rows, source, item):
    """A span of the glossary's HC entry as the glossary reads now, from the
    registered text that live validation reads; None when that text is
    gone."""
    text = (await read_texts(source)).get(item.document_ref)
    if text is None:
        return None
    entry = hc_entry(text)
    return dict(
        kind="text_span",
        document_ref=item.document_ref,
        start=entry.start(),
        end=entry.end(),
        text_sha256=text_digest(entry.group()),
    )


async def corpus_now(publisher, rows, source, item):
    """A corpus object as its Entity reads now: the same Entity and
    selected fields, the digest of their values now; None when the Entity
    or a field it selected is gone."""
    digest = selected_digest(await publisher.graph.get_node(str(item.entity_id)), item)
    if digest is None:
        return None
    return dict(item.model_dump(mode="json"), content_sha256=digest)


# How a review reads one input as it is now, by the input's kind.
AS_NOW = {
    SavedRecordInput: record_now,
    TextSpanInput: span_now,
    CorpusObjectInput: corpus_now,
}


async def as_now(publisher, rows, source, keys, revision) -> Now:
    """Each input in `keys` as it is now, under the new key
    `<key>_r<revision>`, read by its kind (`AS_NOW`); None for one that is
    gone."""
    now = {}
    for key in sorted(keys):
        item = source.inputs[key]
        read = AS_NOW.get(type(item))
        if read is None:
            raise IntentError(
                "fixture_scope", f"This fixture does not read this input again: {key}"
            )
        found = await read(publisher, rows, source, item)
        now[key] = None if found is None else (f"{key}_r{revision}", found)
    return now


async def cited_now(root, publisher, rows, entry, cite, revision) -> Now:
    """`replace-citation`'s reading: the record `cite` names (a source label
    and a record key) as its source holds it now, in place of the one
    withholding citation, under a new key; or, with no `cite`, every
    withholding citation dropped."""
    if cite is None:
        return dict.fromkeys(entry.inputs)
    if len(entry.inputs) != 1:
        raise IntentError("fixture_scope", "--cite replaces one withholding citation")
    cited_label, record_id = cite
    sources = await current_sources(root, publisher, INFO)
    if cited_label not in sources:
        raise IntentError("source_missing", f"No such source: {cited_label}")
    item = current_record(rows, str(sources[cited_label].identity_data_id), record_id)
    if item is None:
        raise IntentError("record_missing", f"No such saved record: {record_id}")
    (old_key,) = entry.inputs
    return {old_key: (f"{cited_label}_{record_id}_r{revision}", item)}


def removal(source, decision, now: Now, producer_key, producer, explanation=None):
    """The decision removed as an erasure removes it (records.apply_removal),
    under the review producer: it and the parts that hold its inputs cite
    each input that changed as it is now and stop citing one that went."""

    def change(payload):
        for new_key, item in filter(None, now.values()):
            payload["inputs"][new_key] = item
        refs = {k: v[0] if v else None for k, v in now.items()}
        apply_removal(payload, source, {decision}, refs, producer_key, explanation)
        payload["producers"][producer_key] = producer

    return next_revision(source, change)


def unresolved_in_place(source, decision, now: Now, producer_key, producer):
    """A resolution whose input changed or went, which the reviewer now
    leaves unresolved: it keeps its key and changes in place, so its
    fingerprint changes."""
    how = "changed" if None not in now.values() else "changed or went"
    return removal(
        source,
        decision,
        now,
        producer_key,
        producer,
        f"An input it read {how} ({', '.join(sorted(now))});"
        " its group is left unresolved.",
    )


def replaced_variant(doc01, decision, now: Now, producer_key, producer):
    """v01 said HC is the Helios controller. The glossary now gives HC
    another meaning, so the reviewer drops v01 and adds v02: HC is a new
    "Hybrid coil" Entity, whose UUID derives from v02 and the new revision.
    Only the changed glossary span carries that meaning. A variant whose
    input went is dropped (`removal`)."""
    if None in now.values():
        return removal(doc01, decision, now, producer_key, producer)
    if decision != "v01" or [type(doc01.inputs[k]) for k in now] != [TextSpanInput]:
        raise IntentError(
            "fixture_scope",
            "Only v01 withheld by the glossary span has a captured replacement",
        )
    ((span_key, span),) = now.values()

    def change(payload):
        old = payload["variant_assignments"].pop("v01")
        coil = str(fresh_entity_id(doc01.identity_data_id, payload["revision"], "v02"))
        payload["entity_constructions"][coil] = dict(
            name="Hybrid coil", description="HC as the glossary now defines it."
        )
        payload["inputs"][span_key] = span
        payload["producers"][producer_key] = producer
        payload["variant_assignments"]["v02"] = dict(
            old,
            target_entity_id=coil,
            input_refs=[old["input_refs"][0], span_key],
            producer_ref=producer_key,
            explanation="The glossary entry for HC changed meaning.",
        )

    return next_revision(doc01, change)


# The captured replacement of a withheld decision, by its record type.
REPLACEMENTS = {
    "mention_resolution": unresolved_in_place,
    "variant_assignment": replaced_variant,
}
if not REPLACEMENTS.keys() <= REGISTRY.keys():
    raise TypeError("review.REPLACEMENTS names a type records.REGISTRY lacks")


def no_replacement(source, decision, now, producer_key, producer):
    raise IntentError(
        "fixture_scope", f"{decision} has no captured replacement in this fixture"
    )


def intended_revision(command, source, decision, now: Now, producer_key, producer):
    """The revision that answers the decision, from the command and what
    the reviewer read now. A re-confirm, or `--cite`, cites each input as
    it is now; `--drop` removes the decision; `replace-decision` replaces
    it by its record type (`REPLACEMENTS`)."""
    if command == "replace-decision":
        replace = REPLACEMENTS.get(record_type_of(source, decision), no_replacement)
        return replace(source, decision, now, producer_key, producer)
    gone = sorted(k for k, v in now.items() if v is None)
    if command == "replace-citation" and len(gone) == len(now):
        return removal(source, decision, now, producer_key, producer)
    if gone:
        raise IntentError(
            "input_removed", f"A removed input is never re-confirmed: {', '.join(gone)}"
        )
    return reconfirmed(source, decision, now, producer_key, producer)


def write_revision(root, label, intended):
    """The caller's file for a reviewed or cited revision of a source, named
    as forget_fixture.CALLER_FILES names that source's revisions."""
    name = CALLER_FILES[label].revisions[0].replace("*", str(intended.revision))
    (root / name).write_text(intended.model_dump_json(indent=2) + "\n")


async def review(
    publisher,
    root,
    label,
    source,
    decision,
    *,
    command,
    cite=None,
    expected_revision,
    fault_stage,
):
    """A reviewer's answer to one withheld decision, for each review
    command: the gate, what the reviewer reads now, the intended revision,
    the caller's file and the unchanged-text replacement."""
    await expect_current(
        publisher, source, expected_revision, "Reconcile the source before a review"
    )
    entry, rows = await review_gate(publisher, source, decision, command)
    revision = source.revision + 1
    if command == "replace-citation":
        now = await cited_now(root, publisher, rows, entry, cite, revision)
    else:
        now = await as_now(publisher, rows, source, entry.inputs, revision)
    producer_key = f"review_{decision}_r{revision}"
    producer = review_producer(entry, command, source, now)
    intended = intended_revision(command, source, decision, now, producer_key, producer)
    write_revision(root, label, intended)
    await replace_one(
        publisher,
        intended,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )
