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
from collections.abc import Awaitable, Callable
from typing import NamedTuple
from uuid import NAMESPACE_URL, uuid5

from .captured_chunks import bind_chunks
from .chain_fixture import cite, prepare_doc03
from .chain_kind_change import change_kind, dependents_withheld
from .entity_edit import edit_entity
from .fixture import context_for, expect_current, load_chunks
from .fixture import prepare as prepare_doc01
from .forget_fixture import (
    CALLER_FILES,
    forget_command,
    forget_dry_run,
    readd,
    reconcile_forget,
)
from .models import IdentitySource
from .multisource import current_sources, publish_one
from .publish import Publisher
from .records import saved_records
from .registered import read_registered, read_texts
from .retrieve import retrieve, withholding_status
from .revisions import refresh, refresh_dependents, replace_one
from .text_changes import TextChange, chunk_text, original_context, read_original
from .text_fixture import maintain_one
from .validation import IntentError, text_digest
from .withholding import document_inputs

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
    "edit-entity",
    "replace-citation",
)
REVIEW_COMMANDS = ("reconfirm", "replace-decision", "replace-citation")
# doc01's kind changes, which a glossary root also takes (chain_kind_change).
KIND_CHANGES = ("change-kind-to-mention", "change-kind-to-reusable")


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
    return await refresh_dependents(publisher, refresh_fault)


async def edit(
    publisher, root, glossary, case, *, expected_revision, fault_stage, refresh_fault
):
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


async def reconcile(publisher, label, selected):
    """Finish the selected source's failed attempt. A glossary edit refreshes
    its dependents when it completes; return what it refreshed."""
    row = await publisher.records.row(selected)
    if (finished := await reconcile_forget(publisher, row, selected)) is not None:
        return dict(no_refresh(), **finished)
    if row.resumed_by == "replace" and row.plan.get("text_change"):
        # The glossary's edit, or doc01's kind change (chain_kind_change.py).
        resume = change_glossary if label == "glossary" else maintain_one
        return await resume(
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


class Call(NamedTuple):
    """One command on an open glossary root. `selected` is the source
    `--source` names. `refresh_fault` is the stage at which the refresh
    fault fails each refresh revision, or None."""

    publisher: Publisher
    root: object
    args: object
    sources: dict
    selected: IdentitySource | None
    refresh_fault: str | None


class Scope(NamedTuple):
    """The sources a command accepts, and its refusal for any other, which
    names the command as `{command}`."""

    labels: tuple[str, ...]
    refusal: str


class Command(NamedTuple):
    """One command a glossary root takes.

    - `handler`: runs the command and returns the fields it adds to the
      root's snapshot.
    - `scope`: the sources it accepts; None for any source of the root.
    - `after`: the fields it adds once the snapshot is read, or None.
    - `opens`: how the command gets its root (`opened`; `create` makes it).
    - `snapshot`: False for a command that writes nothing, whose result is
      the handler's alone."""

    handler: Callable[["Call"], Awaitable[dict]]
    scope: Scope | None = None
    after: Callable[["Call", dict], Awaitable[dict]] | None = None
    opens: Callable[..., Awaitable["Call"]] | None = None
    snapshot: bool = True


async def create(args, root, scope) -> Call:
    """Make the root and publish each source in citation order: doc03 pins
    doc01's decisions as published. No current source is read first."""
    publisher, prepared = await prepare(root, chain=args.chain)
    args._fixture_publisher = publisher
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
    return Call(publisher, root, args, {}, None, None)


async def opened(args, root, scope: Scope | None) -> Call:
    """The existing root and the source `--source` names, refused when the
    root has no such source or the command does not accept it."""
    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    sources = await current_sources(root, publisher, INFO)
    if args.source not in sources:
        raise IntentError("source_missing", "Selected source is not in this fixture")
    if scope is not None and args.source not in scope.labels:
        raise IntentError("fixture_scope", scope.refusal.format(command=args.command))
    # The refresh fault fails each refresh revision at replace_registered.
    refresh_fault = "replace_registered" if args.fault_stage == REFRESH_FAULT else None
    return Call(publisher, root, args, sources, sources[args.source], refresh_fault)


async def created(call: Call) -> dict:
    return no_refresh()


async def edited_glossary(call: Call) -> dict:
    args = call.args
    return await edit(
        call.publisher,
        call.root,
        call.selected,
        args.case,
        expected_revision=args.expected_revision,
        fault_stage=None if call.refresh_fault else args.fault_stage,
        refresh_fault=call.refresh_fault,
    )


async def cited(call: Call) -> dict:
    await cite(call.publisher, call.root, call.args, call.sources)
    return no_refresh()


async def kind_changed(call: Call) -> dict:
    args = call.args
    return await change_kind(
        call.publisher,
        call.root,
        args.command,
        call.selected,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )


async def kind_change_dependents(call: Call, result) -> dict:
    sources = await current_sources(call.root, call.publisher, INFO)
    return await dependents_withheld(call.publisher, sources, result)


async def entity_edited(call: Call) -> dict:
    edited = await edit_entity(call.publisher, call.root, call.selected, call.args.case)
    return dict(no_refresh(), **edited)


async def reviewed(call: Call) -> dict:
    # Imported here: review.py imports INFO and hc_entry from this module.
    from .review import review

    args = call.args
    await review(
        call.publisher,
        call.root,
        args.source,
        call.selected,
        args.decision,
        command=args.command,
        cite=args.cite,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )
    return no_refresh()


async def withdrawn(call: Call) -> dict:
    fault = call.args.fault_stage
    await call.publisher.withdraw(
        call.selected,
        expected_revision=call.selected.revision,
        origin="test/fault_injection" if fault else "test",
        fault_stage=fault,
    )
    return no_refresh()


async def reconciled(call: Call) -> dict:
    return await reconcile(call.publisher, call.args.source, call.selected)


async def forgotten(call: Call) -> dict:
    args = call.args
    outcome = await forget_command(
        call.publisher, call.root, args, args.source, call.selected
    )
    return dict(no_refresh(), **outcome)


async def forget_previewed(call: Call) -> dict:
    args = call.args
    return await forget_dry_run(
        call.publisher, call.root, args, args.source, call.selected
    )


async def readded(call: Call) -> dict:
    args = call.args
    outcome = await readd(
        call.publisher,
        call.root,
        args.source,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )
    return dict(no_refresh(), **outcome)


async def refreshed(call: Call) -> dict:
    # The refresh is this command's own operation, so its failure raises.
    written = []
    await refresh(call.publisher, written, call.refresh_fault)
    return dict(refreshed=written, refresh_failed=None)


DOC01 = Scope(("doc01",), "{command} changes doc01")
REVIEWED = Scope(("doc01", "doc03"), "{command} reviews one decision of doc01 or doc03")
COMMAND_TABLE = {
    "glossary-fixture": Command(created, opens=create),
    "edit-glossary": Command(
        edited_glossary, Scope(("glossary",), "edit-glossary edits the glossary")
    ),
    "cite-record": Command(cited),
    **dict.fromkeys(KIND_CHANGES, Command(kind_changed, DOC01, kind_change_dependents)),
    "edit-entity": Command(
        entity_edited, Scope(("doc01",), "edit-entity edits the Entity doc01 reads")
    ),
    **dict.fromkeys(REVIEW_COMMANDS, Command(reviewed, REVIEWED)),
    "withdraw": Command(withdrawn),
    "reconcile": Command(reconciled),
    "forget": Command(forgotten),
    "readd": Command(readded),
    "refresh-dependents": Command(refreshed),
}
# `forget --dry-run` writes nothing and returns the preview alone.
FORGET_DRY_RUN = Command(forget_previewed, snapshot=False)


async def run(args, root):
    dry_run = args.command == "forget" and args.dry_run
    command = FORGET_DRY_RUN if dry_run else COMMAND_TABLE[args.command]
    call = await (command.opens or opened)(args, root, command.scope)
    handled = await command.handler(call)
    if not command.snapshot:
        return handled
    result = await snapshot(call.publisher, root, args.query)
    result.update(handled)
    if command.after is not None:
        result.update(await command.after(call, result))
    (root / "glossary_result.json").write_text(
        json.dumps(result, indent=2, default=str)
    )
    return result
