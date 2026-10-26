"""Captured glossary dependency: doc01's HC decisions read a glossary entry.

The glossary is a published source with no groups. doc01's resolution r01
and its HC variant v01 cite the glossary's HC entry as a span. Edits to the
glossary withhold what they affect: a change elsewhere leaves both decisions
valid, an insertion before the entry moves the span (a refresh writes its new
range), and a change to the entry needs a reviewer, who re-confirms a decision
or replaces it. The review decisions are captured fixture input, not Describe.
"""

import argparse
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import NamedTuple
from uuid import NAMESPACE_URL, uuid5

from .environment import DATASET_NAME
from .captured_chunks import bind_chunks
from .chain_fixture import add_doc03, cite
from .chain_kind_change import change_kind, dependents_withheld
from .entity_edit import edit_entity
from .entry_update import replace_text, update
from .fixture import add_doc01, expect_current, seed_corpus
from .forget_fixture import (
    CALLER_FILES,
    forget_command,
    forget_dry_run,
    readd,
    semantics_for,
)
from .models import IdentitySource
from .multisource import current_sources, not_published, reconcile_selected
from .multisource import read_sources, write_manifest
from .native_copy import deleted_entry, missing_native
from .publish import Publisher
from .records import saved_records
from .registered import context_for, read_registered, read_texts
from .retrieve import retrieve, withholding_status
from .revisions import refresh
from .text_changes import read_original
from .text_fixture import maintain_one, record_revision, then_refresh
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
# doc01's kind changes, which a glossary root also takes (chain_kind_change).
KIND_CHANGES = ("change-kind-to-mention", "change-kind-to-reusable")


def files(root):
    """Each source's identity file on a glossary root, by label."""
    return read_sources(root, INFO)


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


async def add_glossary(root):
    """Register the glossary's original and its description through the
    lab's `add`, and return the description."""
    from . import entry

    files = CALLER_FILES["glossary"]
    original = entry.Original(root / files.text, GLOSSARY_DATA_ID)
    original.path.write_text(GLOSSARY_TEXT)
    return await entry.add(
        DATASET_NAME,
        original,
        describe=lambda draft: describe_glossary(
            draft.dataset_id, draft.text, draft.chunks
        ),
        identity_path=root / files.identity,
        chunk_budget=CHUNK_BUDGET,
    )


async def change_glossary(
    publisher,
    intended,
    change,
    *,
    expected_revision,
    fault_stage=None,
    refresh_fault=None,
):
    """Finish a failed glossary edit with the text change its plan saved
    (`entry_update.replace_text`), then refresh its dependents' moved spans."""
    return await then_refresh(
        publisher,
        replace_text(
            publisher,
            intended,
            change,
            expected_revision=expected_revision,
            semantics=None,
            fault_stage=fault_stage,
            origin="test",
        ),
        refresh_fault,
    )


async def edit(
    publisher, root, glossary, case, *, expected_revision, fault_stage, refresh_fault
):
    """The glossary's text change through the lab's update, with no
    captured facts to rebuild, then the refresh of its dependents' moved
    spans."""
    await expect_current(
        publisher,
        glossary,
        expected_revision,
        "Reconcile the exact saved glossary edit explicitly",
    )
    before = await read_original(glossary, await context_for(glossary.identity_data_id))

    def describe(draft):
        intended = describe_glossary(
            glossary.dataset_id, draft.text, draft.chunks, old=draft.old
        )
        record_revision(
            root,
            "glossary_identity_revision{}.json",
            "glossary_revision{}.txt",
            intended,
            draft.text,
        )
        return intended

    return await then_refresh(
        publisher,
        update(
            publisher,
            glossary,
            CASES[case](before),
            {},
            describe_edit=describe,
            expected_revision=expected_revision,
            semantics=None,
            fault_stage=fault_stage,
            origin="test",
        ),
        refresh_fault,
    )


async def reconcile(publisher, label, selected):
    """Finish the selected source's failed attempt (`reconcile_selected`). A
    glossary edit refreshes its dependents; doc01's text change is its kind
    change (chain_kind_change.py)."""
    return await reconcile_selected(
        publisher,
        label,
        selected,
        resume_text_change=change_glossary if label == "glossary" else maintain_one,
    )


async def snapshot(publisher, root, query):
    sources = await current_sources(root, publisher, INFO)
    rows = await publisher.records.rows()
    by_source = {r.source: r for r in rows}
    found = {}
    for label, source in sources.items():
        if (row := by_source.get(str(source.identity_data_id))) is None:
            raise not_published(label)
        if missing := await missing_native(publisher.graph, row):
            found[label] = deleted_entry(row, missing)
            continue
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
    # A forgotten glossary's Data item is gone, as is the native copy of one
    # deleted outside the lab, so it has no text to show.
    erased = (
        by_source[str(glossary.identity_data_id)].state == "forgotten"
        or "missing" in found["glossary"]
    )
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
    `--source` names."""

    publisher: Publisher
    root: Path
    args: argparse.Namespace
    sources: dict[str, IdentitySource]
    selected: IdentitySource

    @property
    def refresh_fault(self) -> str | None:
        """The stage at which the refresh fault fails each refresh revision
        (replace_registered), or None."""
        return "replace_registered" if self.args.fault_stage == REFRESH_FAULT else None


class Scope(NamedTuple):
    """The sources a command accepts, and its refusal for any other, which
    names the command as `{command}`."""

    labels: tuple[str, ...]
    refusal: str


class Command(NamedTuple):
    """One command an open glossary root takes: its handler, which returns
    the command's whole result, and the sources it accepts (None for any
    source of the root)."""

    handler: Callable[[Call], Awaitable[dict]]
    scope: Scope | None = None


def saved(root, result) -> dict:
    (root / "glossary_result.json").write_text(
        json.dumps(result, indent=2, default=str)
    )
    return result


async def finish(publisher, root, query, **extra) -> dict:
    """A command's whole result: the root's snapshot after it, with no
    refresh unless `extra` reports one, and `extra`. Saved as
    glossary_result.json."""
    result = await snapshot(publisher, root, query)
    result.update(dict(refreshed=[], refresh_failed=None), **extra)
    return saved(root, result)


async def create(args, root) -> dict:
    """Make the root: the glossary, doc01 and, with `--chain`, doc03, each
    added and published in citation order (`entry.remember_in_order`).
    doc01 publishes after the glossary is registered, because admission
    reads doc01's glossary input from the registered copy; doc03 cites
    doc01's decisions as published. No current source is read first."""
    from . import entry

    publisher = await seed_corpus(root)
    args._fixture_publisher = publisher
    adds = dict(
        glossary=lambda _: add_glossary(root),
        doc01=lambda _: add_doc01(
            root, amend=lambda payload: glossary_inputs(payload, GLOSSARY_TEXT)
        ),
    )
    if args.chain:
        adds["doc03"] = lambda done: add_doc03(root, done["doc01"])
    await write_manifest(root, INFO, tuple(adds), chunk_budget=CHUNK_BUDGET)
    await entry.remember_in_order(
        publisher,
        adds,
        semantics=semantics_for,
        chunk_budget=CHUNK_BUDGET,
        fault=(args.source, args.fault_stage),
        origin="test",
    )
    return await finish(publisher, root, args.query)


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
    return Call(publisher, root, args, sources, sources[args.source])


async def edited_glossary(call: Call) -> dict:
    args = call.args
    outcome = await edit(
        call.publisher,
        call.root,
        call.selected,
        args.case,
        expected_revision=args.expected_revision,
        fault_stage=None if call.refresh_fault else args.fault_stage,
        refresh_fault=call.refresh_fault,
    )
    return await finish(call.publisher, call.root, args.query, **outcome)


async def cited(call: Call) -> dict:
    await cite(call.publisher, call.root, call.args, call.sources)
    return await finish(call.publisher, call.root, call.args.query)


async def kind_changed(call: Call) -> dict:
    """doc01's kind change, its refresh, and what it leaves withheld in the
    other sources, which the snapshot after it shows. It builds its result
    without `finish`, because `dependents_withheld` reads that snapshot."""
    args = call.args
    outcome = await change_kind(
        call.publisher,
        call.root,
        args.command,
        call.selected,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )
    result = await snapshot(call.publisher, call.root, args.query)
    result.update(outcome)
    sources = await current_sources(call.root, call.publisher, INFO)
    result.update(await dependents_withheld(call.publisher, sources, result))
    return saved(call.root, result)


async def entity_edited(call: Call) -> dict:
    edited = await edit_entity(call.publisher, call.root, call.selected, call.args.case)
    return await finish(call.publisher, call.root, call.args.query, **edited)


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
    return await finish(call.publisher, call.root, args.query)


async def withdrawn(call: Call) -> dict:
    fault = call.args.fault_stage
    await call.publisher.withdraw(
        call.selected,
        expected_revision=call.selected.revision,
        origin="test/fault_injection" if fault else "test",
        fault_stage=fault,
    )
    return await finish(call.publisher, call.root, call.args.query)


async def reconciled(call: Call) -> dict:
    outcome = await reconcile(call.publisher, call.args.source, call.selected)
    return await finish(call.publisher, call.root, call.args.query, **outcome)


async def forgotten(call: Call) -> dict:
    args = call.args
    if args.dry_run:
        # A dry run writes nothing: its preview is the whole result.
        return await forget_dry_run(
            call.publisher, call.root, args, args.source, call.selected
        )
    outcome = await forget_command(
        call.publisher, call.root, args, args.source, call.selected
    )
    return await finish(call.publisher, call.root, args.query, **outcome)


async def readded(call: Call) -> dict:
    args = call.args
    outcome = await readd(
        call.publisher,
        call.root,
        args.source,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )
    return await finish(call.publisher, call.root, args.query, **outcome)


async def refreshed(call: Call) -> dict:
    # The refresh is this command's own operation, so its failure raises.
    written = [w async for w in refresh(call.publisher, call.refresh_fault)]
    return await finish(call.publisher, call.root, call.args.query, refreshed=written)


DOC01 = Scope(("doc01",), "{command} changes doc01")
REVIEW = Command(
    reviewed,
    Scope(("doc01", "doc03"), "{command} reviews one decision of doc01 or doc03"),
)
# The commands only a glossary root takes, beside glossary-fixture, which
# creates one.
OWN_COMMANDS = {
    "edit-glossary": Command(
        edited_glossary, Scope(("glossary",), "edit-glossary edits the glossary")
    ),
    "reconfirm": REVIEW,
    "replace-decision": REVIEW,
    "refresh-dependents": Command(refreshed),
    "cite-record": Command(cited),
    "edit-entity": Command(
        entity_edited, Scope(("doc01",), "edit-entity edits the Entity doc01 reads")
    ),
    "replace-citation": REVIEW,
}
# Commands other fixture kinds also take, which a glossary root runs here.
SHARED_COMMANDS = {
    **dict.fromkeys(KIND_CHANGES, Command(kind_changed, DOC01)),
    "withdraw": Command(withdrawn),
    "reconcile": Command(reconciled),
    "forget": Command(forgotten),
    "readd": Command(readded),
}
COMMANDS = ("glossary-fixture", *OWN_COMMANDS)
REVIEW_COMMANDS = tuple(c for c, command in OWN_COMMANDS.items() if command is REVIEW)


async def run(args, root):
    if args.command == "glossary-fixture":
        return await create(args, root)
    command = OWN_COMMANDS.get(args.command) or SHARED_COMMANDS[args.command]
    return await command.handler(await opened(args, root, command.scope))
