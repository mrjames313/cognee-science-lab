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
)
DOC01_REVIEW = "stage6-captured-glossary-review"


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


async def prepare(root):
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
    (root / INFO).write_text(
        json.dumps(
            dict(
                dataset_id=str(doc01.dataset_id),
                sources=dict(doc01="identity.json", glossary="glossary_identity.json"),
                chunk_budget=CHUNK_BUDGET,
            ),
            indent=2,
        )
    )
    return publisher, {
        "glossary": (glossary, chunks, ctx),
        "doc01": (doc01, chunks1, ctx1),
    }


async def current_sources(root, publisher):
    manifest = json.loads((root / INFO).read_text())
    rows = {r.source: r for r in await publisher.records.rows()}
    found = {}
    for label, path in manifest["sources"].items():
        source = IdentitySource.model_validate_json((root / path).read_text())
        row = rows.get(str(source.identity_data_id))
        found[label] = (
            IdentitySource.model_validate_json(row.description) if row else source
        )
    return found


async def change_glossary(
    publisher, intended, change, *, expected_revision, fault_stage=None
):
    """The glossary's text change, with no captured facts to rebuild."""
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


async def edit(publisher, root, glossary, case, *, expected_revision, fault_stage):
    from .fixture import context_for
    from .text_changes import TextChange, chunk_text, original_context, read_original

    row = await publisher.records.row(glossary)
    if row.revision != expected_revision:
        from .storage import STALE_REVISION

        raise IntentError(*STALE_REVISION)
    if row.state != "current":
        raise IntentError(
            "recovery_choice", "Reconcile the exact saved glossary edit explicitly"
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
    await change_glossary(
        publisher,
        intended,
        change,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )


def replace_doc01(publisher, root, fault_stage=None):
    from .revisions import replace_one

    async def replace(description, expected_revision):
        await replace_one(
            publisher,
            description,
            root,
            "doc01",
            expected_revision=expected_revision,
            fault_stage=fault_stage,
        )

    return replace


async def review(
    publisher, root, doc01, decision, *, expected_revision, fault_stage, command
):
    """A reviewer's answer to one withheld decision of doc01: re-confirm it on
    the glossary's current HC entry, or, for v01, replace it with a variant
    for the entry's new meaning."""
    from .fixture import context_for
    from .text_changes import read_original
    from .withholding import REFRESH_NEEDED, reconfirmed, withheld_decisions

    row = await publisher.records.row(doc01)
    if row.revision != expected_revision:
        from .storage import STALE_REVISION

        raise IntentError(*STALE_REVISION)
    rows = await publisher.records.rows()
    held = (await withheld_decisions(rows, publisher.withholdings)).get(
        str(doc01.identity_data_id), {}
    )
    if decision not in held or held[decision].status != REFRESH_NEEDED:
        raise IntentError(
            "not_withheld", f"{decision} is not withheld for review in doc01"
        )
    glossary = (await current_sources(root, publisher))["glossary"]
    text = await read_original(glossary, await context_for(glossary.identity_data_id))
    entry = hc_entry(text)
    revision = doc01.revision + 1
    span_key = f"glossary_hc_r{revision}"
    span = dict(
        kind="text_span",
        document_ref="glossary",
        start=entry.start(),
        end=entry.end(),
        text_sha256=text_digest(entry.group()),
    )
    rows_for = [
        w
        for w in await publisher.withholdings.rows()
        if w.source == str(doc01.identity_data_id) and w.assignment == decision
    ]
    old_keys = sorted({w.input_ref for w in rows_for})
    if len(old_keys) != 1 or not isinstance(doc01.inputs[old_keys[0]], TextSpanInput):
        raise IntentError(
            "fixture_scope", "This fixture reviews one withheld glossary span"
        )
    producer_key = f"review_{decision}_r{revision}"
    producer = dict(
        method="captured_fixture",
        implementation="re-confirmed" if command == "reconfirm" else "replaced",
        version="0.1",
        configuration=dict(
            policy=DOC01_REVIEW,
            confirmed_by="captured fixture reviewer",
            withholding=[
                dict(input_ref=w.input_ref, reason=w.reason, status=w.status)
                for w in rows_for
            ],
            old_digests={k: doc01.inputs[k].text_sha256 for k in old_keys},
            new_digest=span["text_sha256"],
        ),
        run_id=None,
    )
    if command == "reconfirm":
        intended = reconfirmed(
            doc01,
            decision,
            {old_keys[0]: (span_key, span)},
            producer_key,
            producer,
        )
    else:
        intended = replaced_variant(
            doc01, decision, span_key, span, producer_key, producer
        )
    (root / f"identity_doc01_revision{intended.revision}.json").write_text(
        intended.model_dump_json(indent=2) + "\n"
    )
    await replace_doc01(publisher, root, fault_stage)(
        intended, expected_revision=expected_revision
    )


def replaced_variant(doc01, decision, span_key, span, producer_key, producer):
    """v01 said HC is the Helios controller. The glossary now gives HC
    another meaning, so the reviewer drops v01 and adds v02: HC is a new
    "Hybrid coil" Entity, whose UUID derives from v02 and the new revision."""
    from .withholding import cited_inputs

    if decision != "v01" or decision not in doc01.variant_assignments:
        raise IntentError("fixture_scope", "Only v01 has a captured replacement")
    payload = doc01.model_dump(mode="json")
    payload["revision"] += 1
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
    revised = IdentitySource.model_validate_json(json.dumps(payload))
    for key in set(doc01.inputs) - cited_inputs(revised):
        if key != doc01.original_input_ref:
            payload["inputs"].pop(key)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def reconcile(publisher, root, label, selected):
    from .fixture import context_for, load_chunks
    from .multisource import publish_one
    from .text_changes import TextChange

    row = await publisher.records.row(selected)
    if row.resumed_by == "replace" and label == "glossary":
        await change_glossary(
            publisher,
            selected,
            TextChange.from_plan(row.plan),
            expected_revision=selected.revision,
        )
    elif row.resumed_by == "replace":
        await replace_doc01(publisher, root)(
            selected, expected_revision=selected.revision
        )
    else:
        ctx = await context_for(selected.inputs[selected.original_input_ref].data_id)
        await publish_one(
            publisher,
            selected,
            await load_chunks(selected, ctx),
            ctx,
            operation="reconcile",
            semantics=label != "glossary",
        )


async def snapshot(publisher, root, query):
    from .registered import read_registered, read_texts
    from .retrieve import retrieve
    from .withholding import document_inputs, withholding_status

    sources = await current_sources(root, publisher)
    rows = await publisher.records.rows()
    by_source = {r.source: r for r in rows}
    found = {}
    for label, source in sources.items():
        row = by_source[str(source.identity_data_id)]
        registered = await read_registered(source)
        reads = (
            set()
            if label == "glossary"
            else document_inputs(source, GLOSSARY_DATA_ID) - {"glossary"}
        )
        found[label] = dict(
            identity_data_id=str(source.identity_data_id),
            state=row.state,
            saved_revision=source.revision,
            verified_revision=row.verified_revision,
            registered_revision=registered.revision,
            registered_matches_saved=registered == source,
            glossary_spans={
                k: source.inputs[k].model_dump(mode="json") for k in sorted(reads)
            },
            decisions={
                k: dict(input_refs=d.input_refs, producer_ref=d.producer_ref)
                for k, d in [
                    *source.mention_resolutions.items(),
                    *source.variant_assignments.items(),
                ]
            },
            producers={
                k: dict(implementation=p.implementation, configuration=p.configuration)
                for k, p in source.producers.items()
            },
        )
    glossary = sources["glossary"]
    text = (await read_texts(glossary))["glossary"]
    entry = hc_entry(text)
    dataset = glossary.dataset_id
    return dict(
        sources=found,
        glossary=dict(
            text=text,
            text_sha256=text_digest(text),
            hc_entry=dict(
                text=entry.group(),
                start=entry.start(),
                end=entry.end(),
                text_sha256=text_digest(entry.group()),
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
    from .multisource import publish_one
    from .withholding import refresh_dependents

    if args.command == "glossary-fixture":
        publisher, prepared = await prepare(root)
        args._fixture_publisher = publisher
        for label in ("glossary", "doc01"):
            source, chunks, ctx = prepared[label]
            await publish_one(
                publisher,
                source,
                chunks,
                ctx,
                operation="publish",
                fault_stage=args.fault_stage if label == args.source else None,
                semantics=label != "glossary",
            )
        refreshed = []
    else:
        publisher = await Publisher.configured()
        args._fixture_publisher = publisher
        sources = await current_sources(root, publisher)
        if args.source not in sources:
            raise IntentError(
                "source_missing", "Selected source is not in this fixture"
            )
        selected = sources[args.source]
        edit_fault = None if args.fault_stage == REFRESH_FAULT else args.fault_stage
        if args.command == "edit-glossary":
            if args.source != "glossary":
                raise IntentError("fixture_scope", "edit-glossary edits the glossary")
            await edit(
                publisher,
                root,
                selected,
                args.case,
                expected_revision=args.expected_revision,
                fault_stage=edit_fault,
            )
        elif args.command in ("reconfirm", "replace-decision"):
            if args.source != "doc01" or not args.decision:
                raise IntentError(
                    "fixture_scope", f"{args.command} reviews one decision of doc01"
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
            await reconcile(publisher, root, args.source, selected)
        # Every command that may complete an edit refreshes the moved spans.
        refresh_fault = (
            "replace_registered" if args.fault_stage == REFRESH_FAULT else None
        )
        refreshed = (
            await refresh_dependents(
                publisher, replace_doc01(publisher, root, refresh_fault)
            )
            if args.command in ("edit-glossary", "reconcile", "refresh-dependents")
            else []
        )
    result = await snapshot(publisher, root, args.query)
    result["refreshed"] = refreshed
    (root / "glossary_result.json").write_text(
        json.dumps(result, indent=2, default=str)
    )
    return result
