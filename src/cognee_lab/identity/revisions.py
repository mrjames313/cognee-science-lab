"""A source's next revision, and the unchanged-text replacement that writes it.

The captured doc01 correction retargets identity at revision 2, retaining
local facts. A dependent's refresh revision moves its spans, and a
reviewer's re-confirm cites the current input under a new producer; each is
a next revision that drops the inputs nothing cites any more.
"""

import json

from .models import IdentitySource
from .multisource import current_sources, fixture_id, snapshot
from .publish import Publisher
from .retrieve import retrieve
from .validation import IntentError, cited_inputs, fresh_entity_id
from .withholding import pending_moves


def corrected_id(source):
    """The revised controller is a new reusable Entity, so its UUID derives from
    the source, revision 2 and the resolution that names it."""
    return str(fresh_entity_id(source.identity_data_id, 2, "r01"))


def corrected(source):
    payload = source.model_dump(mode="json")
    payload["revision"] = 2
    revised = corrected_id(source)
    old_target = payload["mention_resolutions"]["r01"]["target_entity_id"]
    payload["mention_resolutions"]["r01"]["target_entity_id"] = revised
    payload["variant_assignments"]["v01"]["target_entity_id"] = revised
    payload["producers"]["correction"] = dict(
        method="captured_fixture",
        implementation="stage6-captured-revision-correction",
        version="0.1",
        configuration={"policy": "retarget-unchanged-text-v1"},
        run_id=None,
    )
    for item in [
        payload["mention_resolutions"]["r01"],
        payload["variant_assignments"]["v01"],
    ]:
        item["input_refs"] = ["doc01"]
        item["producer_ref"] = "correction"
    payload["inputs"].pop("existing_A", None)
    if old_target != revised:
        payload["entity_constructions"].pop(old_target, None)
    payload["entity_constructions"].pop(fixture_id("doc01:singleton"), None)
    payload["entity_constructions"][revised] = dict(
        name="Revised controller",
        description="Creation seed for the captured doc01 correction.",
    )
    return IdentitySource.model_validate_json(json.dumps(payload))


async def replace_one(publisher, source, *, expected_revision, fault_stage=None):
    """Replace any source with unchanged text through the native pipeline."""
    from .fixture import context_for, load_chunks, verify_semantics
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    original_ctx = await context_for(source.inputs[source.original_input_ref].data_id)
    chunks = await load_chunks(source, original_ctx)
    generated_ctx = await context_for(source.identity_data_id)

    async def task(items, ctx=None):
        from .registered import read_texts
        from .text_changes import read_original

        for item in items:
            own = {item.original_input_ref: await read_original(item, ctx)}
            await publisher.replace(
                item,
                texts=await read_texts(item, known=own),
                chunks={str(c.id): c for c in chunks},
                ctx=ctx,
                expected_revision=expected_revision,
                fault_stage=fault_stage,
                origin="test/fault_injection" if fault_stage else "test",
                verify_semantics=lambda: verify_semantics(
                    publisher, item, chunks, original_ctx
                ),
            )
        return items

    async for _ in run_tasks_base(
        [Task(task, needs_llm=False)], [source], generated_ctx.user, generated_ctx
    ):
        pass


def next_revision(reader: IdentitySource, change) -> IdentitySource:
    """The reader's next revision after `change(payload)`, with every input
    nothing cites any more dropped. Uncited inputs are known only once the
    changed payload validates, so a drop validates it a second time."""
    payload = reader.model_dump(mode="json")
    payload["revision"] += 1
    change(payload)
    revised = IdentitySource.model_validate_json(json.dumps(payload))
    uncited = set(revised.inputs) - cited_inputs(revised)
    if not uncited:
        return revised
    for key in uncited:
        payload["inputs"].pop(key)
    return IdentitySource.model_validate_json(json.dumps(payload))


def remapped(reader: IdentitySource, moved) -> IdentitySource:
    """The dependent's next revision with each moved span at its new range.
    Its decisions, producers and every other cited input are unchanged."""

    def change(payload):
        for w in moved:
            payload["inputs"][w.input_ref].update(start=w.new_start, end=w.new_end)

    return next_revision(reader, change)


def written_ranges(revised: IdentitySource, moved) -> dict:
    """What a refresh revision wrote: the range of each moved input it holds."""
    return dict(
        identity_data_id=str(revised.identity_data_id),
        revision=revised.revision,
        inputs={
            w.input_ref: dict(
                start=revised.inputs[w.input_ref].start,
                end=revised.inputs[w.input_ref].end,
            )
            for w in moved
        },
    )


async def refresh_dependents(publisher, fault_stage=None) -> dict:
    """After an edit completes, write each current dependent's next revision
    with its moved spans' new ranges: an ordinary unchanged-text replacement
    through replace_one, whose withholding cleanup releases the moved
    decisions once it completes. `fault_stage` fails each refresh revision
    there. A rerun finishes an
    interrupted refresh: a dependent whose replacement failed resumes its
    saved revision first. That revision may hold the range of an earlier
    edit, so when `remap` rows still apply after it, the refresh remaps
    again.

    Returns each range written (`refreshed`) and the failure that stopped
    the refresh (`refresh_failed`), not raised: the edit before it already
    completed, and `refresh-dependents` reruns the refresh."""
    refreshed = []
    try:
        for source, (row, moved) in (await pending_moves(publisher)).items():
            if row.state != "current" and row.resumed_by == "replace":
                saved = IdentitySource.model_validate_json(row.description)
                await replace_one(
                    publisher,
                    saved,
                    expected_revision=row.revision,
                    fault_stage=fault_stage,
                )
                refreshed.append(written_ranges(saved, moved))
                row, moved = (await pending_moves(publisher)).get(source, (row, []))
            if row.state == "current" and moved:
                revised = remapped(
                    IdentitySource.model_validate_json(row.description), moved
                )
                await replace_one(
                    publisher,
                    revised,
                    expected_revision=row.revision,
                    fault_stage=fault_stage,
                )
                refreshed.append(written_ranges(revised, moved))
    except IntentError as exc:
        failed = dict(code=exc.code, message=str(exc))
        return dict(refreshed=refreshed, refresh_failed=failed)
    return dict(refreshed=refreshed, refresh_failed=None)


def reconfirmed(reader, assignment, replacements, producer_key, producer):
    """Copy-on-write re-confirm of one withheld decision: its next revision
    cites each new input in place of the changed one under a producer new in
    this revision. Other decisions keep citing the old input, so they stay
    withheld until each is re-confirmed; an old input nothing cites any more
    is dropped. `replacements` maps an old input key to (new key, input)."""

    def change(payload):
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

    return next_revision(reader, change)


async def run(args, root):
    if args.source != "doc01" or not (root / "multi-fixture-info.json").exists():
        raise IntentError(
            "fixture_scope",
            "Captured revision correction requires doc01 of a two-source fixture",
        )
    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    sources = await current_sources(root, publisher)
    intended = corrected(sources["doc01"])
    (root / "identity_doc01_revision2.json").write_text(
        intended.model_dump_json(indent=2) + "\n"
    )
    await replace_one(
        publisher,
        intended,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )
    sources = await current_sources(root, publisher)
    result = await snapshot(publisher, sources, args.query)
    result["corrected_entity_result"] = await retrieve(
        publisher, intended.dataset_id, "What does Revised controller limit?"
    )
    (root / "revision_result.json").write_text(json.dumps(result, indent=2))
    return result
