"""Captured glossary dependency: doc01's HC decisions read a glossary entry.

The glossary is a published source with no groups. doc01's resolution r01
and its HC variant v01 cite the glossary's HC entry as a span. Edits to the
glossary withhold what they affect: a change elsewhere leaves both decisions
valid, an insertion before the entry moves the span (a refresh writes its new
range), and a change to the entry needs a reviewer, who re-confirms a decision
or replaces it. The review decisions are captured fixture input, not Describe.
"""

import json
import re
from uuid import NAMESPACE_URL, uuid5

from .models import IdentitySource, TextSpanInput
from .multisource import current_sources
from .publish import Publisher
from .validation import IntentError, fresh_entity_id, text_digest

GLOSSARY_TEXT = (
    "Glossary\n"
    "\n"
    "HC: Helios controller, the plasma heating regulator.\n"
    "RF: radio frequency.\n"
)
GLOSSARY_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:glossary:original")
GLOSSARY_IDENTITY_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:glossary:identity")
INFO = "glossary-fixture-info.json"
CHUNK_BUDGET = 512
HC_LINE = re.compile(r"^HC: .*$", re.MULTILINE)
# A fault in the refresh that follows an edit: doc01's refresh revision
# fails at replace_registered, after the edit itself completed.
REFRESH_FAULT = "refresh_interrupted"
COMMANDS = (
    "glossary-fixture",
    "edit-glossary",
    "reconfirm",
    "replace-decision",
    "refresh-dependents",
    "cite-record",
)
DOC01_REVIEW = "stage6-captured-glossary-review"


def no_refresh():
    """A command result with no refresh, fresh for each command."""
    return dict(refreshed=[], refresh_failed=None)


def hc_entry(text):
    """The glossary's HC entry: the one line that starts with "HC: "."""
    found = list(HC_LINE.finditer(text))
    if len(found) != 1:
        raise IntentError("fixture_shape", "The glossary has no single HC entry")
    return found[0]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise IntentError("fixture_shape", f"The glossary does not hold {old!r} once")
    return text.replace(old, new)


def edit_hc(text, change):
    entry = hc_entry(text)
    return text[: entry.start()] + change(entry.group()) + text[entry.end() :]


# Each case edits the current glossary text, so the cases can follow one another.
CASES = {
    "elsewhere": lambda t: replace_once(
        t, "RF: radio frequency.", "RF: radio-frequency heating."
    ),
    "insert": lambda t: edit_hc(
        t, lambda line: "ECRH: electron cyclotron resonance heating.\n" + line
    ),
    "cosmetic": lambda t: edit_hc(
        t, lambda line: replace_once(line, "plasma heating", "plasma-heating")
    ),
    "substantive": lambda t: edit_hc(
        t, lambda _: "HC: hybrid coil, the auxiliary magnet winding."
    ),
}


def glossary_inputs(payload, text):
    """doc01's inputs for the glossary: its text and the HC entry as a span."""
    entry = hc_entry(text)
    payload["inputs"]["glossary"] = dict(
        kind="source_text",
        dataset_id=payload["dataset_id"],
        data_id=str(GLOSSARY_DATA_ID),
        text_sha256=text_digest(text),
    )
    payload["inputs"]["glossary_hc"] = dict(
        kind="text_span",
        document_ref="glossary",
        start=entry.start(),
        end=entry.end(),
        text_sha256=text_digest(entry.group()),
    )
    for record in (
        payload["mention_resolutions"]["r01"],
        payload["variant_assignments"]["v01"],
    ):
        record["input_refs"].append("glossary_hc")


def describe_glossary(dataset_id, text, chunks, revision=1, old=None):
    """The glossary's description: its text and complete chunk map, no groups."""
    from .captured_chunks import bind_chunks

    payload = (
        old.model_dump(mode="json")
        if old
        else dict(
            kind="cognee_identity_source",
            schema_version="0.1-draft",
            dataset_id=str(dataset_id),
            identity_data_id=str(GLOSSARY_IDENTITY_ID),
            revision=revision,
            original_input_ref="glossary",
            inputs={},
            producers=dict(
                fixture=dict(
                    method="captured_fixture",
                    implementation="stage6-captured-glossary",
                    version="0.1",
                    configuration={"policy": "definitions-without-groups-v1"},
                    run_id=None,
                )
            ),
            entity_constructions={},
            mention_groups={},
            mention_resolutions={},
            variant_assignments={},
        )
    )
    if old:
        payload["revision"] = old.revision + 1
    payload["inputs"]["glossary"] = dict(
        kind="source_text",
        dataset_id=str(dataset_id),
        data_id=str(GLOSSARY_DATA_ID),
        text_sha256=text_digest(text),
    )
    bind_chunks(payload, text, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def prepare(root, *, chain=False):
    """Register the glossary and doc01 and, with `chain`, doc03, which cites
    doc01's decisions (chain_fixture.py)."""
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points

    from .fixture import context_for, load_chunks
    from .fixture import prepare as prepare_doc01

    if cognee.__version__ != "1.6.2":
        raise IntentError(
            "unsupported_version", "Glossary fixture requires inspected Cognee 1.6.2"
        )
    doc01, chunks1, ctx1, publisher = await prepare_doc01(
        root, amend=lambda payload: glossary_inputs(payload, GLOSSARY_TEXT)
    )
    (root / "glossary.txt").write_text(GLOSSARY_TEXT)
    await cognee.add(
        DataItem(data=str(root / "glossary.txt"), data_id=GLOSSARY_DATA_ID),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    ctx = await context_for(GLOSSARY_DATA_ID)
    chunks = await load_chunks(None, ctx, budget=CHUNK_BUDGET)
    await add_data_points(chunks, ctx=ctx)
    glossary = describe_glossary(doc01.dataset_id, GLOSSARY_TEXT, chunks)
    (root / "glossary_identity.json").write_text(
        glossary.model_dump_json(indent=2) + "\n"
    )
    await cognee.add(
        DataItem(
            data=str(root / "glossary_identity.json"), data_id=GLOSSARY_IDENTITY_ID
        ),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    files = dict(doc01="identity.json", glossary="glossary_identity.json")
    prepared = {"glossary": (glossary, chunks, ctx), "doc01": (doc01, chunks1, ctx1)}
    if chain:
        from .chain_fixture import prepare_doc03

        files["doc03"] = "doc03_identity.json"
        prepared["doc03"] = await prepare_doc03(root, doc01)
    (root / INFO).write_text(
        json.dumps(
            dict(
                dataset_id=str(doc01.dataset_id),
                sources=files,
                chunk_budget=CHUNK_BUDGET,
            ),
            indent=2,
        )
    )
    return publisher, prepared


async def change_glossary(
    publisher,
    intended,
    change,
    *,
    expected_revision,
    fault_stage=None,
    refresh_fault=None,
):
    """The glossary's text change, with no captured facts to rebuild, then
    the refresh of its dependents' moved spans."""
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    from .fixture import context_for
    from .text_changes import chunk_text, original_context

    generated = await context_for(intended.identity_data_id)
    original = await original_context(intended, generated)
    prepared = await chunk_text(change.text, original, change.chunk_budget)

    async def nothing():
        return None

    async def task(items, ctx=None):
        for item in items:
            await publisher.replace(
                item,
                texts={item.original_input_ref: change.text},
                chunks={str(c.id): c for c in prepared},
                ctx=ctx,
                expected_revision=expected_revision,
                text_change=change,
                semantic_writer=nothing,
                verify_semantics=nothing,
                fault_stage=fault_stage,
                origin="test/fault_injection" if fault_stage else "test",
            )
        return items

    async for _ in run_tasks_base(
        [Task(task, needs_llm=False)], [intended], generated.user, generated
    ):
        pass
    from .revisions import refresh_dependents

    return await refresh_dependents(publisher, refresh_fault)


async def edit(
    publisher, root, glossary, case, *, expected_revision, fault_stage, refresh_fault
):
    from .fixture import context_for, expect_current
    from .text_changes import TextChange, chunk_text, original_context, read_original

    await expect_current(
        publisher,
        glossary,
        expected_revision,
        "Reconcile the exact saved glossary edit explicitly",
    )
    ctx = await context_for(glossary.identity_data_id)
    before = await read_original(glossary, ctx)
    change = TextChange(
        previous_text=before,
        text=CASES[case](before),
        occurrence_map={},
        chunk_budget=json.loads((root / INFO).read_text())["chunk_budget"],
    )
    chunks = await chunk_text(
        change.text, await original_context(glossary, ctx), change.chunk_budget
    )
    intended = describe_glossary(glossary.dataset_id, change.text, chunks, old=glossary)
    (root / f"glossary_revision{intended.revision}.txt").write_text(change.text)
    (root / f"glossary_identity_revision{intended.revision}.json").write_text(
        intended.model_dump_json(indent=2) + "\n"
    )
    return await change_glossary(
        publisher,
        intended,
        change,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
        refresh_fault=refresh_fault,
    )


async def review_gate(publisher, source, decision, command):
    """The withheld entry a reviewer answers, after the gates: no document
    the source reads has an edit that is pending or failed, and no source
    whose records it cites has an attempt that is, so the reviewer attests
    committed content; the decision waits for review, not for a record
    above it (`upstream_withheld`); a removed input is never re-confirmed."""
    from .records import saved_records
    from .retrieve import withheld_now
    from .validation import Reason
    from .withholding import (
        Status,
        document_inputs,
        unfinished_edits,
        unfinished_sources,
    )

    rows = await publisher.records.rows()
    for edit in unfinished_edits(rows):
        if document_inputs(source, edit.description):
            raise IntentError(
                "edit_unfinished",
                "Reconcile the edit of a document this source reads before a review",
            )
    cited = {str(i.identity_data_id) for i in saved_records(source).values()}
    if cited & unfinished_sources(rows):
        raise IntentError(
            "edit_unfinished",
            "Reconcile the attempt of a source whose records this source cites before a review",
        )
    entry = (
        (await withheld_now(publisher, rows))
        .get(str(source.identity_data_id), {})
        .get(decision)
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


async def review(
    publisher, root, source, decision, *, expected_revision, fault_stage, command
):
    """A reviewer's answer to one withheld decision. A decision of doc01
    that read the glossary's HC entry is re-confirmed on the entry as it is
    now, or replaced: v01 by a variant for the entry's new meaning, r01 in
    place as unresolved. A decision withheld because a saved record it
    cites changed is re-confirmed on the record as it is now."""
    from .fixture import context_for, expect_current
    from .records import saved_records
    from .revisions import reconfirmed, replace_one
    from .text_changes import read_original

    await expect_current(
        publisher, source, expected_revision, "Reconcile the source before a review"
    )
    entry, rows = await review_gate(publisher, source, decision, command)
    revision = source.revision + 1
    producer_key = f"review_{decision}_r{revision}"
    old_keys = sorted(entry.inputs)
    if old_keys and set(old_keys) <= set(saved_records(source)):
        from .chain_fixture import recited

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
            from .chain_fixture import unresolved_in_place

            intended = unresolved_in_place(
                source, decision, old_keys[0], span_key, span, producer_key, producer
            )
        else:
            intended = replaced_variant(
                source, decision, span_key, span, producer_key, producer
            )
    write_revision(root, intended)
    await replace_one(
        publisher,
        intended,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )


def write_revision(root, intended):
    """The caller's file for a reviewed or cited revision of doc01 or doc03
    (forget_fixture.CALLER_FILES)."""
    from .chain_fixture import DOC03_IDENTITY_ID

    label = "doc03" if intended.identity_data_id == DOC03_IDENTITY_ID else "doc01"
    (root / f"identity_{label}_revision{intended.revision}.json").write_text(
        intended.model_dump_json(indent=2) + "\n"
    )


def replaced_variant(doc01, decision, span_key, span, producer_key, producer):
    """v01 said HC is the Helios controller. The glossary now gives HC
    another meaning, so the reviewer drops v01 and adds v02: HC is a new
    "Hybrid coil" Entity, whose UUID derives from v02 and the new revision."""
    from .revisions import next_revision

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


async def reconcile(publisher, label, selected):
    """Finish the selected source's failed attempt. A glossary edit refreshes
    its dependents when it completes; return what it refreshed."""
    from .fixture import context_for, load_chunks
    from .multisource import publish_one
    from .text_changes import TextChange

    from .revisions import replace_one

    from .forget_fixture import CALLER_FILES, reconcile_forget

    row = await publisher.records.row(selected)
    if (finished := await reconcile_forget(publisher, row, selected)) is not None:
        return dict(no_refresh(), **finished)
    if row.resumed_by == "replace" and label == "glossary":
        return await change_glossary(
            publisher,
            selected,
            TextChange.from_plan(row.plan),
            expected_revision=selected.revision,
        )
    if row.resumed_by == "replace":
        await replace_one(publisher, selected, expected_revision=selected.revision)
    else:
        ctx = await context_for(selected.inputs[selected.original_input_ref].data_id)
        await publish_one(
            publisher,
            selected,
            await load_chunks(selected, ctx),
            ctx,
            operation="reconcile",
            semantics=CALLER_FILES[label].facts,
        )
    return no_refresh()


async def snapshot(publisher, root, query):
    from .records import saved_records
    from .registered import read_registered, read_texts
    from .retrieve import retrieve, withholding_status
    from .withholding import document_inputs

    sources = await current_sources(root, publisher, INFO)
    rows = await publisher.records.rows()
    by_source = {r.source: r for r in rows}
    found = {}
    for label, source in sources.items():
        row = by_source[str(source.identity_data_id)]
        if row.tombstone is not None:
            found[label] = dict(
                identity_data_id=row.source,
                state=row.state,
                saved_revision=row.revision,
                verified_revision=row.verified_revision,
                tombstone=row.tombstone.model_dump(mode="json"),
            )
            continue
        # A withdrawn source has no registered snapshot to read.
        registered = None if row.is_retired else await read_registered(source)
        reads = (
            set()
            if label == "glossary"
            else document_inputs(source, sources["glossary"]) - {"glossary"}
        )
        found[label] = dict(
            identity_data_id=str(source.identity_data_id),
            state=row.state,
            saved_revision=source.revision,
            verified_revision=row.verified_revision,
            registered_revision=registered.revision if registered else None,
            registered_matches_saved=registered == source,
            glossary_spans={
                k: source.inputs[k].model_dump(mode="json") for k in sorted(reads)
            },
            decisions={
                k: dict(
                    input_refs=d.input_refs,
                    producer_ref=d.producer_ref,
                    status=d.status,
                )
                for k, d in [
                    *source.mention_resolutions.items(),
                    *source.variant_assignments.items(),
                ]
            },
            records={
                k: i.model_dump(mode="json")
                for k, i in sorted(saved_records(source).items())
            },
            producers={
                k: dict(implementation=p.implementation, configuration=p.configuration)
                for k, p in source.producers.items()
            },
        )
    glossary = sources["glossary"]
    # A forgotten glossary's Data item is gone, so it has no text to show.
    erased = by_source[str(glossary.identity_data_id)].state == "forgotten"
    text = None if erased else (await read_texts(glossary))["glossary"]
    entry = hc_entry(text) if text is not None else None
    dataset = glossary.dataset_id
    return dict(
        sources=found,
        glossary=dict(
            text=text,
            text_sha256=text_digest(text) if text is not None else None,
            hc_entry=(
                dict(
                    text=entry.group(),
                    start=entry.start(),
                    end=entry.end(),
                    text_sha256=text_digest(entry.group()),
                )
                if entry
                else None
            ),
        ),
        **await withholding_status(
            publisher, [r for r in rows if r.dataset == str(dataset)]
        ),
        result=await retrieve(publisher, dataset, query),
        helios=await retrieve(publisher, dataset, "What does Helios controller limit?"),
        recovery_events=await publisher.records.events(dataset),
    )


async def run(args, root):
    from .fixture import expect_current
    from .forget_fixture import CALLER_FILES
    from .multisource import publish_one
    from .revisions import refresh_dependents

    if args.command == "glossary-fixture":
        publisher, prepared = await prepare(root, chain=args.chain)
        args._fixture_publisher = publisher
        # In citation order: doc03 pins doc01's decisions as published.
        for label, (source, chunks, ctx) in prepared.items():
            await publish_one(
                publisher,
                source,
                chunks,
                ctx,
                operation="publish",
                fault_stage=args.fault_stage if label == args.source else None,
                semantics=CALLER_FILES[label].facts,
            )
        refresh = no_refresh()
    else:
        publisher = await Publisher.configured()
        args._fixture_publisher = publisher
        sources = await current_sources(root, publisher, INFO)
        if args.source not in sources:
            raise IntentError(
                "source_missing", "Selected source is not in this fixture"
            )
        selected = sources[args.source]
        if args.command == "forget" and args.dry_run:
            from .forget_fixture import forget_dry_run

            return await forget_dry_run(publisher, root, args, args.source, selected)
        refreshing = args.fault_stage == REFRESH_FAULT
        # The refresh fault fails each refresh revision at replace_registered.
        refresh_fault = "replace_registered" if refreshing else None
        refresh = no_refresh()
        if args.command == "edit-glossary":
            if args.source != "glossary":
                raise IntentError("fixture_scope", "edit-glossary edits the glossary")
            refresh = await edit(
                publisher,
                root,
                selected,
                args.case,
                expected_revision=args.expected_revision,
                fault_stage=None if refreshing else args.fault_stage,
                refresh_fault=refresh_fault,
            )
        elif args.command == "cite-record":
            from .chain_fixture import citing_revision
            from .revisions import replace_one

            if "doc03" not in sources:
                raise IntentError(
                    "fixture_scope", "cite-record needs a glossary-fixture --chain root"
                )
            await expect_current(
                publisher,
                selected,
                args.expected_revision,
                "Reconcile the source before it cites a record",
            )
            intended = citing_revision(
                selected, args.citation, sources, await publisher.records.rows()
            )
            write_revision(root, intended)
            await replace_one(
                publisher,
                intended,
                expected_revision=args.expected_revision,
                fault_stage=args.fault_stage,
            )
        elif args.command in ("reconfirm", "replace-decision"):
            if args.source not in ("doc01", "doc03"):
                raise IntentError(
                    "fixture_scope",
                    f"{args.command} reviews one decision of doc01 or doc03",
                )
            await review(
                publisher,
                root,
                selected,
                args.decision,
                expected_revision=args.expected_revision,
                fault_stage=args.fault_stage,
                command=args.command,
            )
        elif args.command == "reconcile":
            refresh = await reconcile(publisher, args.source, selected)
        elif args.command == "forget":
            from .forget_fixture import forget_command

            refresh = dict(
                no_refresh(),
                **await forget_command(publisher, root, args, args.source, selected),
            )
        elif args.command == "readd":
            from .forget_fixture import readd

            refresh = dict(
                no_refresh(),
                **await readd(
                    publisher,
                    root,
                    args.source,
                    expected_revision=args.expected_revision,
                    fault_stage=args.fault_stage,
                ),
            )
        elif args.command == "refresh-dependents":
            refresh = await refresh_dependents(publisher, refresh_fault)
            # The refresh is this command's own operation, so it fails here.
            if failed := refresh["refresh_failed"]:
                raise IntentError(failed["code"], failed["message"])
    result = await snapshot(publisher, root, args.query)
    result.update(refresh)
    (root / "glossary_result.json").write_text(
        json.dumps(result, indent=2, default=str)
    )
    return result
