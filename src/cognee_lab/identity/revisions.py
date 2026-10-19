"""Captured doc01 correction: revision 2 retargets identity, retaining local facts."""

import json

from .models import IdentitySource
from .multisource import current_sources, fixture_id, snapshot
from .publish import Publisher
from .retrieve import retrieve
from .validation import IntentError

CORRECTED_ID = fixture_id("doc01:corrected-controller")


def corrected(source):
    payload = source.model_dump(mode="json")
    payload["revision"] = 2
    old_target = payload["mention_resolutions"]["r01"]["target_entity_id"]
    payload["mention_resolutions"]["r01"]["target_entity_id"] = CORRECTED_ID
    payload["variant_assignments"]["v01"]["target_entity_id"] = CORRECTED_ID
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
    if old_target != CORRECTED_ID:
        payload["entity_constructions"].pop(old_target, None)
    payload["entity_constructions"].pop(fixture_id("doc01:singleton"), None)
    payload["entity_constructions"][CORRECTED_ID] = dict(
        name="Revised controller",
        description="Creation seed for the captured doc01 correction.",
    )
    return IdentitySource.model_validate_json(json.dumps(payload))


async def replace_one(
    publisher, source, root, label, *, expected_revision, fault_stage=None
):
    from .fixture import context_for, load_chunks, verify_semantics
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    original_ctx = await context_for(source.inputs[source.original_input_ref].data_id)
    chunks = await load_chunks(source, original_ctx)
    generated_ctx = await context_for(source.identity_data_id)

    async def task(items, ctx=None):
        for item in items:
            await publisher.replace(
                item,
                texts={
                    "doc01": (
                        root / ("source.txt" if label == "doc01" else "source02.txt")
                    ).read_text()
                },
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
        root,
        "doc01",
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
