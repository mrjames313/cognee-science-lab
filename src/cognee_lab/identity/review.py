"""A reviewer's answer to one withheld decision of the captured glossary
and chain fixtures.

The gate decides whether a decision can be reviewed now (`review_gate`). A
re-confirm cites each input that withholds the decision as that input is
now, under a new key, by the input's kind (`AS_NOW`): a saved record as
its source holds it now (`record_now`), the glossary's HC entry as the
glossary reads now (`span_now`), so one revision answers a decision whose
inputs span several kinds. A replacement is per decision, by its record
type (`REPLACEMENTS`): a resolution in place as unresolved
(`unresolved_in_place`), v01 by a variant for the glossary entry's new
meaning (`replaced_variant`). The review decisions are captured fixture
input, not Describe.
"""

from .fixture import context_for, expect_current
from .forget_fixture import CALLER_FILES
from .glossary_fixture import INFO, hc_entry
from .models import CorpusObjectInput, IdentitySource, SavedRecordInput, TextSpanInput
from .multisource import current_sources
from .records import REGISTRY, cited_row, citation, record_type_of, saved_records
from .retrieve import withheld_now
from .revisions import next_revision, reconfirmed, replace_one
from .text_changes import read_original
from .validation import (
    IntentError,
    Reason,
    fresh_entity_id,
    selected_digest,
    text_digest,
)
from .withholding import Status, document_inputs, unfinished, unfinished_edits

DOC01_REVIEW = "stage6-captured-glossary-review"


async def review_gate(publisher, source, decision, command):
    """The withheld entry a reviewer answers, after the gates: no document
    the source reads has an edit that is pending or failed, and no source
    whose records it cites is unfinished (withholding.unfinished, or its own
    input fails live validation), so the reviewer attests committed content;
    the decision waits for review, not for a record above it
    (`upstream_withheld`); a removed input is never re-confirmed."""
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
    refuse_removed(source, entry, command)
    return entry, rows


def refuse_removed(source, entry, command):
    """A removed input is never re-confirmed. The refusal names the answer:
    `replace-citation` for a removed saved record, else `replace-decision`."""
    if command == "reconfirm" and entry.reason == Reason.REMOVED:
        answer = (
            "replace the citation with replace-citation"
            if entry.inputs & set(saved_records(source))
            else "replace the decision"
        )
        raise IntentError(
            "input_removed", f"A removed input is never re-confirmed; {answer}"
        )


def review_producer(entry, command, digests):
    """The producer a review names, new in its revision."""
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
            **digests,
        ),
        run_id=None,
    )


def cited_now(rows, source) -> dict[str, IdentitySource]:
    """The current description of each source `source` cites, by identity."""
    wanted = {str(i.identity_data_id) for i in saved_records(source).values()}
    return {r.source: r.description for r in rows if r.source in wanted}


async def record_now(publisher, root, rows, item):
    """A saved-record citation of the cited record as its source holds it
    now."""
    upstream = next(
        (r.description for r in rows if r.source == str(item.identity_data_id)),
        None,
    )
    if upstream is None or record_type_of(upstream, item.record_id) is None:
        raise IntentError(
            "input_removed", f"The cited record is gone: {item.record_id}"
        )
    return citation(upstream, item.record_id)


async def span_now(publisher, root, rows, item):
    """A span of the glossary's HC entry as the glossary reads now."""
    glossary = (await current_sources(root, publisher, INFO))["glossary"]
    text = await read_original(glossary, await context_for(glossary.identity_data_id))
    entry = hc_entry(text)
    return dict(
        kind="text_span",
        document_ref=item.document_ref,
        start=entry.start(),
        end=entry.end(),
        text_sha256=text_digest(entry.group()),
    )


async def corpus_now(publisher, root, rows, item):
    """A corpus object as its Entity reads now: the same Entity and
    selected fields, the digest of their values now."""
    digest = selected_digest(await publisher.graph.get_node(str(item.entity_id)), item)
    if digest is None:
        raise IntentError(
            "input_removed",
            f"The Entity or a field it selected is gone: {item.entity_id}",
        )
    return dict(item.model_dump(mode="json"), content_sha256=digest)


# How a review reads one input as it is now, by the input's kind.
AS_NOW = {
    SavedRecordInput: record_now,
    TextSpanInput: span_now,
    CorpusObjectInput: corpus_now,
}


def input_digest(item: dict) -> str:
    """What an input pins of its content: a span's digest, or a corpus
    object's or a saved record's fingerprint."""
    return item.get("text_sha256") or item["content_sha256"]


async def as_now(publisher, root, rows, source, keys, revision):
    """Each input in `keys` as it is now, under the new key
    `<key>_r<revision>`, read by its kind (`AS_NOW`). Returns the
    replacements (old key to new key and input) and what the review
    producer records: the old and the new digests."""
    replacements, old_digests, new_digests = {}, {}, {}
    for key in sorted(keys):
        item = source.inputs[key]
        read = AS_NOW.get(type(item))
        if read is None:
            raise IntentError(
                "fixture_scope", f"This fixture does not read this input again: {key}"
            )
        new_key = f"{key}_r{revision}"
        replacements[key] = (new_key, await read(publisher, root, rows, item))
        old_digests[key] = input_digest(item.model_dump(mode="json"))
        new_digests[new_key] = input_digest(replacements[key][1])
    return replacements, dict(old_digests=old_digests, new_digests=new_digests)


def unresolved_in_place(source, decision, replacements, key, review):
    """A resolution whose input changed, which the reviewer now leaves
    unresolved: it keeps its key and changes in place, so its fingerprint
    changes. It and its group cite each replaced input as it is now."""

    def change(payload):
        old = payload["mention_resolutions"][decision]
        group = payload["mention_groups"][old["group_ref"]]
        for previous, (new_key, item) in replacements.items():
            payload["inputs"][new_key] = item
            group["input_refs"] = [
                new_key if k == previous else k for k in group["input_refs"]
            ]
        payload["producers"][key] = review
        payload["mention_resolutions"][decision] = dict(
            group_ref=old["group_ref"],
            status="unresolved",
            input_refs=[replacements.get(k, (k,))[0] for k in old["input_refs"]],
            producer_ref=key,
            explanation=f"An input it read changed ({', '.join(sorted(replacements))});"
            " its group is left unresolved.",
        )

    return next_revision(source, change)


def replaced_variant(doc01, decision, replacements, producer_key, producer):
    """v01 said HC is the Helios controller. The glossary now gives HC
    another meaning, so the reviewer drops v01 and adds v02: HC is a new
    "Hybrid coil" Entity, whose UUID derives from v02 and the new revision.
    Only the changed glossary span carries that meaning."""
    if decision != "v01" or [type(doc01.inputs[k]) for k in replacements] != [
        TextSpanInput
    ]:
        raise IntentError(
            "fixture_scope",
            "Only v01 withheld by the glossary span has a captured replacement",
        )
    ((span_key, span),) = replacements.values()

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


def write_revision(root, label, intended):
    """The caller's file for a reviewed or cited revision of a source, named
    as forget_fixture.CALLER_FILES names that source's revisions."""
    name = CALLER_FILES[label].revisions[0].replace("*", str(intended.revision))
    (root / name).write_text(intended.model_dump_json(indent=2) + "\n")


async def review(
    publisher, root, label, source, decision, *, expected_revision, fault_stage, command
):
    """A reviewer's answer to one withheld decision. A re-confirm cites each
    input that withholds it as that input is now (`as_now`), whatever its
    kind, in one revision. A replacement is per decision, by its record type
    (`REPLACEMENTS`)."""
    await expect_current(
        publisher, source, expected_revision, "Reconcile the source before a review"
    )
    entry, rows = await review_gate(publisher, source, decision, command)
    if command != "reconfirm" and entry.inputs & set(saved_records(source)):
        raise IntentError(
            "fixture_scope",
            "A saved-record citation is replaced with replace-citation",
        )
    revision = source.revision + 1
    producer_key = f"review_{decision}_r{revision}"
    replacements, digests = await as_now(
        publisher, root, rows, source, entry.inputs, revision
    )
    producer = review_producer(entry, command, digests)
    if command == "reconfirm":
        intended = reconfirmed(source, decision, replacements, producer_key, producer)
    else:
        replace = REPLACEMENTS[record_type_of(source, decision)]
        intended = replace(source, decision, replacements, producer_key, producer)
    write_revision(root, label, intended)
    await replace_one(
        publisher,
        intended,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )


def dropped(source, decision, erased, producer_key, producer):
    """The decision removed as an erasure removes it (records.REGISTRY): a
    resolution stays, unresolved in place, a variant goes; what holds its
    records' inputs loses the erased keys."""
    kind = REGISTRY[record_type_of(source, decision)]

    def change(payload):
        record = kind.removed(source, decision, erased, producer_key)
        if record is None:
            payload[kind.field].pop(decision)
        else:
            payload[kind.field][decision] = record.model_dump(
                mode="json", exclude_none=True
            )
        for each in REGISTRY.values():
            for field, parts in each.stripped(source, erased).items():
                payload[field] = {
                    k: p.model_dump(mode="json") for k, p in parts.items()
                }
        payload["producers"][producer_key] = producer

    return next_revision(source, change)


def cited_record(rows, sources, cite, revision):
    """The new key and the citation of the record `cite` names (a source
    label and a record key) as its source holds it now."""
    cited_label, record_id = cite
    if cited_label not in sources:
        raise IntentError("source_missing", f"No such source: {cited_label}")
    cited = str(sources[cited_label].identity_data_id)
    upstream = next((r.description for r in rows if r.source == cited), None)
    if upstream is None or record_type_of(upstream, record_id) is None:
        raise IntentError("record_missing", f"No such saved record: {record_id}")
    return f"{cited_label}_{record_id}_r{revision}", citation(upstream, record_id)


async def replace_citation(
    publisher, root, label, source, decision, *, cite, expected_revision, fault_stage
):
    """The reviewer's answer to a decision withheld by a saved record it
    cites, removed or changed. `cite` (a source label and a record key)
    re-cites the decision on that record as it is now, under a new key, its
    reviewed fields unchanged; None drops the decision (`dropped`). Either
    names a producer new in the revision (implementation `replaced`) that
    records the withholding it answers."""
    await expect_current(
        publisher, source, expected_revision, "Reconcile the source before a review"
    )
    entry, rows = await review_gate(publisher, source, decision, "replace-citation")
    old_keys = sorted(entry.inputs)
    if not entry.inputs <= set(saved_records(source)):
        raise IntentError(
            "fixture_scope",
            "replace-citation answers a decision withheld by saved-record citations",
        )
    revision = source.revision + 1
    producer_key = f"review_{decision}_r{revision}"
    digests = dict(
        old_digests={k: source.inputs[k].content_sha256 for k in old_keys},
        new_digests={},
    )
    if cite is None:
        producer = review_producer(entry, "replace-citation", digests)
        intended = dropped(source, decision, set(old_keys), producer_key, producer)
    else:
        if len(old_keys) != 1:
            raise IntentError(
                "fixture_scope", "--cite replaces one withholding citation"
            )
        sources = await current_sources(root, publisher, INFO)
        new_key, item = cited_record(rows, sources, cite, revision)
        digests["new_digests"][new_key] = item["content_sha256"]
        producer = review_producer(entry, "replace-citation", digests)
        intended = reconfirmed(
            source, decision, {old_keys[0]: (new_key, item)}, producer_key, producer
        )
    write_revision(root, label, intended)
    await replace_one(
        publisher,
        intended,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )
