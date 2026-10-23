"""Captured doc01 correction: revision 2 retargets identity, retaining local facts."""

import json

from .models import IdentitySource
from .multisource import current_sources, fixture_id, snapshot
from .publish import Publisher
from .retrieve import retrieve
from .validation import IntentError, fresh_entity_id


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


async def refresh_moved_spans(publisher, fault_stage=None):
    """After a text edit completes, give each dependent whose span the edit
    moved its next revision (withholding.refresh_dependents), each through
    replace_one. `fault_stage` fails each refresh revision there. Returns
    the ranges written and the failure that stopped the refresh, if any."""
    from .withholding import refresh_dependents

    async def replace(description, expected_revision):
        await replace_one(
            publisher,
            description,
            expected_revision=expected_revision,
            fault_stage=fault_stage,
        )

    return await refresh_dependents(publisher, replace)


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
