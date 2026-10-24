"""A reviewer's answer to one withheld decision of the captured glossary
and chain fixtures.

The gate decides whether a decision can be reviewed now (`review_gate`). A
decision of doc01 that read the glossary's HC entry is re-confirmed on the
entry as it is now, or replaced: v01 by a variant for the entry's new
meaning (`replaced_variant`), r01 in place as unresolved
(`unresolved_in_place`). A decision withheld because a saved record it
cites changed is re-confirmed on the record as it is now (`recited`). The
review decisions are captured fixture input, not Describe.
"""

from .fixture import context_for, expect_current
from .forget_fixture import CALLER_FILES
from .glossary_fixture import INFO, hc_entry
from .models import IdentitySource, TextSpanInput
from .multisource import current_sources
from .records import cited_row, citation, saved_records
from .retrieve import withheld_now
from .revisions import next_revision, reconfirmed, replace_one
from .text_changes import read_original
from .validation import IntentError, Reason, fresh_entity_id, text_digest
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
    if command == "reconfirm" and entry.reason == Reason.REMOVED:
        raise IntentError(
            "input_removed",
            "A removed input is never re-confirmed; replace the decision",
        )
    return entry, rows


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


def recited(source, entry, rows, revision):
    """A re-confirm of a decision withheld by saved-record drift: each
    withholding citation again, under a new key, as the cited record is
    now. Returns the replacements (old key to new key and input) and what
    the producer records."""
    current = cited_now(rows, source)
    replacements, old_digests, new_digests = {}, {}, {}
    for key in sorted(entry.inputs):
        item = source.inputs[key]
        upstream = current.get(str(item.identity_data_id))
        if upstream is None:
            raise IntentError("input_removed", f"The cited source is gone: {key}")
        new_key = f"{key}_r{revision}"
        replacements[key] = (new_key, citation(upstream, item.record_id))
        old_digests[key] = item.content_sha256
        new_digests[new_key] = replacements[key][1]["content_sha256"]
    return replacements, dict(old_digests=old_digests, new_digests=new_digests)


def unresolved_in_place(doc01, decision, old_key, span_key, span, key, review):
    """r01 resolved g01 to the Helios controller. The glossary entry it
    read changed, and the reviewer now leaves g01 unresolved: r01 keeps its
    key and changes in place, so its fingerprint changes."""
    if decision != "r01" or decision not in doc01.mention_resolutions:
        raise IntentError("fixture_scope", "Only r01 has an in-place replacement")

    def change(payload):
        old = payload["mention_resolutions"]["r01"]
        payload["inputs"][span_key] = span
        payload["producers"][key] = review
        payload["mention_resolutions"]["r01"] = dict(
            group_ref=old["group_ref"],
            status="unresolved",
            input_refs=[span_key if k == old_key else k for k in old["input_refs"]],
            producer_ref=key,
            explanation="The glossary entry for HC changed; g01 is left unresolved.",
        )

    return next_revision(doc01, change)


def replaced_variant(doc01, decision, span_key, span, producer_key, producer):
    """v01 said HC is the Helios controller. The glossary now gives HC
    another meaning, so the reviewer drops v01 and adds v02: HC is a new
    "Hybrid coil" Entity, whose UUID derives from v02 and the new revision."""
    if decision != "v01" or decision not in doc01.variant_assignments:
        raise IntentError("fixture_scope", "Only v01 has a captured replacement")

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


def write_revision(root, label, intended):
    """The caller's file for a reviewed or cited revision of a source, named
    as forget_fixture.CALLER_FILES names that source's revisions."""
    name = CALLER_FILES[label].revisions[0].replace("*", str(intended.revision))
    (root / name).write_text(intended.model_dump_json(indent=2) + "\n")


async def review(
    publisher, root, label, source, decision, *, expected_revision, fault_stage, command
):
    """A reviewer's answer to one withheld decision. A decision of doc01
    that read the glossary's HC entry is re-confirmed on the entry as it is
    now, or replaced: v01 by a variant for the entry's new meaning, r01 in
    place as unresolved. A decision withheld because a saved record it
    cites changed is re-confirmed on the record as it is now."""
    await expect_current(
        publisher, source, expected_revision, "Reconcile the source before a review"
    )
    entry, rows = await review_gate(publisher, source, decision, command)
    revision = source.revision + 1
    producer_key = f"review_{decision}_r{revision}"
    old_keys = sorted(entry.inputs)
    if old_keys and set(old_keys) <= set(saved_records(source)):
        if command != "reconfirm":
            raise IntentError(
                "fixture_scope", "A saved-record citation has no captured replacement"
            )
        replacements, digests = recited(source, entry, rows, revision)
        producer = review_producer(entry, command, digests)
        intended = reconfirmed(source, decision, replacements, producer_key, producer)
    else:
        if len(old_keys) != 1 or not isinstance(
            source.inputs[old_keys[0]], TextSpanInput
        ):
            raise IntentError(
                "fixture_scope", "This fixture reviews one withheld glossary span"
            )
        glossary = (await current_sources(root, publisher, INFO))["glossary"]
        text = await read_original(
            glossary, await context_for(glossary.identity_data_id)
        )
        entry_line = hc_entry(text)
        span_key = f"glossary_hc_r{revision}"
        span = dict(
            kind="text_span",
            document_ref="glossary",
            start=entry_line.start(),
            end=entry_line.end(),
            text_sha256=text_digest(entry_line.group()),
        )
        producer = review_producer(
            entry,
            command,
            dict(
                old_digests={k: source.inputs[k].text_sha256 for k in old_keys},
                new_digest=span["text_sha256"],
            ),
        )
        if command == "reconfirm":
            intended = reconfirmed(
                source,
                decision,
                {old_keys[0]: (span_key, span)},
                producer_key,
                producer,
            )
        elif decision in source.mention_resolutions:
            intended = unresolved_in_place(
                source, decision, old_keys[0], span_key, span, producer_key, producer
            )
        else:
            intended = replaced_variant(
                source, decision, span_key, span, producer_key, producer
            )
    write_revision(root, label, intended)
    await replace_one(
        publisher,
        intended,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )
