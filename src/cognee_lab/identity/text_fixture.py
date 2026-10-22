"""Captured prefix-edit example; semantic/identity decisions are explicit test input."""

import json

from .models import ChunkInput, IdentitySource
from .multisource import current_sources, snapshot
from .publish import Publisher
from .admission import identity_map
from .text_changes import TextChange, chunk_text, original_context, read_original
from .validation import IntentError, text_digest

PREFIX = "Revision note: Δ calibration schedule updated.\n\n"


def describe_prefix_edit(old, text, chunks, *, prefix=PREFIX):
    """Exact remapping for a known edit, with captured review of all local groups.

    Not a general Describe algorithm: no nearest-text matching, implicit identity
    inference or automatic assumption that a new context preserves interpretation.
    """
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    key = old.original_input_ref
    payload["inputs"][key]["text_sha256"] = text_digest(text)
    payload["producers"]["text_review"] = dict(
        method="captured_fixture",
        implementation="stage6-captured-prefix-edit",
        version="0.1",
        configuration={"policy": "explicit-unchanged-interpretation-v1"},
        run_id=None,
    )
    for group in payload["mention_groups"].values():
        for occurrence in group["occurrences"]:
            occurrence["start"] += len(prefix)
            occurrence["end"] += len(prefix)
        group["producer_ref"] = "text_review"
    for item in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        item["producer_ref"] = "text_review"
    from .captured_chunks import bind_chunks

    bind_chunks(payload, text, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def verify_rebuilt_semantics(publisher, source, chunks, ctx):
    from .fixture import verify_semantics
    from .native import mention_fact

    await verify_semantics(publisher, source, chunks, ctx)
    from .captured_chunks import fixture_mention_id

    fact = await mention_fact(publisher, source, fixture_mention_id(source))
    allowed = {c.id for c in chunks}
    own = [e for e in fact.evidence if e.data_id == ctx.data_item.id]
    if ("g01" in source.mention_groups and not own) or any(
        e.chunk_id not in allowed for e in own
    ):
        raise IntentError(
            "stale_evidence", "Old document evidence survived the native memory rebuild"
        )


async def maintain_one(
    publisher, source, change, *, expected_revision, fault_stage=None
):
    from .fixture import context_for, write_semantics
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    generated = await context_for(source.identity_data_id)
    original = await original_context(source, generated)
    prepared = await chunk_text(change.text, original, change.chunk_budget)
    chunks = {str(c.id): c for c in prepared}

    async def write():
        original = await original_context(source, generated)
        await write_semantics(publisher, source, list(chunks.values()), original)

    async def verify():
        original = await original_context(source, generated)
        await verify_rebuilt_semantics(
            publisher, source, list(chunks.values()), original
        )
        from .captured_chunks import retired_mentions
        from .resolved_retirement import verify_retirement

        for mid in retired_mentions(source).values():
            await verify_retirement(publisher, source, mid)
        # This two-document fixture promises survival of the independent local
        # fact, in addition to the common publisher's identity-owner checks.
        from .fixture import load_chunks, verify_semantics

        for row in await publisher.records.rows(source.dataset_id):
            if (
                row["source"] == str(source.identity_data_id)
                or row["state"] != "current"
            ):
                continue
            other = IdentitySource.model_validate_json(row["description"])
            other_ctx = await original_context(other, generated)
            other_chunks = await load_chunks(other, other_ctx)
            await verify_semantics(publisher, other, other_chunks, other_ctx)

    async def task(items, ctx=None):
        for item in items:
            await publisher.replace(
                item,
                texts={item.original_input_ref: change.text},
                chunks=chunks,
                ctx=ctx,
                expected_revision=expected_revision,
                text_change=change,
                semantic_writer=write,
                verify_semantics=verify,
                fault_stage=fault_stage,
                origin="test/fault_injection" if fault_stage else "test",
            )
        return items

    async for _ in run_tasks_base(
        [Task(task, needs_llm=False)], [source], generated.user, generated
    ):
        pass


def decision_method(source):
    """The captured reviews that the revision's groups and decisions cite."""
    refs = {
        r.producer_ref
        for r in [
            *source.mention_groups.values(),
            *source.mention_resolutions.values(),
            *source.variant_assignments.values(),
        ]
    }
    return [
        dict(
            implementation=source.producers[ref].implementation,
            policy=source.producers[ref].configuration.get("policy"),
            mapping="explicit old-to-new occurrence map; whole-document rebuild",
        )
        for ref in sorted(refs)
    ]


async def added_group(publisher, source, key):
    """A fresh group's Entity, markers, decision and regenerated fact."""
    from .models import Accepted
    from .native import mention_fact

    group = source.mention_groups[key]
    mid = str(group.entity_id)
    decision = next(
        (r for r in source.mention_resolutions.values() if r.group_ref == key), None
    )
    resolution = dict(status=decision.status) if decision else None
    if isinstance(decision, Accepted):
        target = str(decision.target_entity_id)
        resolution.update(
            target_entity_id=target,
            target_present=await publisher.graph.get_node(target) is not None,
            target_indexed=bool(
                await publisher.vector.retrieve("Entity_name", [target])
            ),
        )
    fact = await mention_fact(publisher, source, mid)
    doc = source.inputs[source.original_input_ref]
    return dict(
        entity_id=mid,
        entity_present=await publisher.graph.get_node(mid) is not None,
        entity_indexed=bool(await publisher.vector.retrieve("Entity_name", [mid])),
        marker_chunk_ids=[
            str(i.chunk_id)
            for i in source.inputs.values()
            if isinstance(i, ChunkInput)
            and await publisher.graph.has_edge(
                str(i.chunk_id), mid, "has_identity_mention"
            )
        ],
        resolution=resolution,
        fact=dict(
            edge_id=str(fact.edge_id),
            present=fact.edge is not None,
            text=fact.edge.edge_properties.get("edge_text") if fact.edge else None,
            evidence_chunk_ids=sorted(
                str(e.chunk_id) for e in fact.evidence if e.data_id == doc.data_id
            ),
        ),
    )


async def transition_summary(publisher, row):
    from .captured_chunks import fixture_mention_id
    from .native import mention_fact

    old = IdentitySource.model_validate_json(row["plan"]["previous_description"])
    source = IdentitySource.model_validate_json(row["description"])
    change = TextChange.from_plan(row["plan"])
    key = source.original_input_ref
    old_ids = {
        str(i.chunk_id) for i in old.inputs.values() if isinstance(i, ChunkInput)
    }
    new_ids = {
        str(i.chunk_id) for i in source.inputs.values() if isinstance(i, ChunkInput)
    }
    retired = old_ids - new_ids
    primary = await mention_fact(publisher, source, fixture_mention_id(source))
    own_ids = {
        str(e.chunk_id)
        for e in primary.evidence
        if e.data_id == source.inputs[key].data_id
    }
    return dict(
        identity_data_id=str(source.identity_data_id),
        original_data_id=str(source.inputs[key].data_id),
        position_unit="Unicode code points; document-relative [start, end)",
        position_shift=change.prefix_shift(old, source),
        text_length_delta=len(change.text) - len(change.previous_text),
        previous_text_sha256=old.inputs[key].text_sha256,
        text_sha256=source.inputs[key].text_sha256,
        previous_chunk_ids=sorted(old_ids),
        chunk_ids=sorted(new_ids),
        retired_chunks_absent=all(
            [await publisher.graph.get_node(i) is None for i in retired]
        ),
        retired_chunk_vectors_absent=all(
            [
                not await publisher.vector.retrieve("DocumentChunk_text", [i])
                for i in retired
            ]
        ),
        evidence_uses_current_chunks=(
            bool(own_ids) or "g01" not in source.mention_groups
        )
        and own_ids <= new_ids,
        evidence_chunk_ids=sorted(own_ids),
        mention_ids_preserved=all(
            g.entity_id == old.mention_groups[k].entity_id
            for k, g in source.mention_groups.items()
            if k in old.mention_groups
        ),
        chunk_budget=change.chunk_budget,
        previous_chunk_mapping=[
            dict(chunk_id=str(i.chunk_id), start=i.start, end=i.end)
            for i in old.inputs.values()
            if isinstance(i, ChunkInput)
        ],
        chunk_mapping=[
            dict(chunk_id=str(i.chunk_id), start=i.start, end=i.end)
            for i in source.inputs.values()
            if isinstance(i, ChunkInput)
        ],
        content_ids_present_in_both=sorted(old_ids & new_ids),
        groups={
            k: dict(
                previous_occurrences=(
                    [o.model_dump() for o in old.mention_groups[k].occurrences]
                    if k in old.mention_groups
                    else []
                ),
                entity_id=str(g.entity_id),
                occurrences=[o.model_dump() for o in g.occurrences],
                chunk_refs=g.chunk_refs,
                previous_marker_chunk_ids=(
                    [
                        str(old.inputs[k].chunk_id)
                        for k in old.mention_groups[k].chunk_refs
                    ]
                    if k in old.mention_groups
                    else []
                ),
                marker_chunk_ids=[str(source.inputs[k].chunk_id) for k in g.chunk_refs],
            )
            for k, g in source.mention_groups.items()
        },
        occurrence_map=change.occurrence_map,
        added_groups={
            k: await added_group(publisher, source, k)
            for k in source.mention_groups
            if k not in old.mention_groups
        },
        retired_groups={
            k: dict(
                entity_id=str(g.entity_id),
                previous_occurrences=[o.model_dump() for o in g.occurrences],
                entity_present=await publisher.graph.get_node(str(g.entity_id))
                is not None,
                entity_indexed=bool(
                    await publisher.vector.retrieve("Entity_name", [str(g.entity_id)])
                ),
                marker_present=any(
                    [
                        await publisher.graph.has_edge(
                            c, str(g.entity_id), "has_identity_mention"
                        )
                        for c in old_ids | new_ids
                    ]
                ),
            )
            for k, g in old.mention_groups.items()
            if k not in source.mention_groups
        },
        decision_method=decision_method(source),
    )


async def run(args, root):
    if args.source != "doc01" or not (root / "multi-fixture-info.json").exists():
        raise IntentError(
            "fixture_scope", "Captured text edit requires doc01 of a two-source fixture"
        )
    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    sources = await current_sources(root, publisher)
    old = sources["doc01"]
    row = await publisher.records.row(old)
    if row["revision"] != args.expected_revision:
        raise IntentError("stale_revision", "Saved revision changed")
    if row["state"] != "current":
        raise IntentError(
            "recovery_choice", "Reconcile the exact saved text replacement explicitly"
        )
    from .fixture import context_for

    ctx = await context_for(old.identity_data_id)
    before = await read_original(old, ctx)
    from .captured_chunks import recorded_budget

    prefix = PREFIX
    if (root / "chunked-fixture-info.json").exists():
        prefix = json.loads((root / "chunked-fixture-info.json").read_text())["prefix"]
    change = TextChange(
        previous_text=before,
        text=prefix + before,
        occurrence_map=identity_map(old),
        chunk_budget=await recorded_budget(old, publisher.graph),
    )
    chunks = await chunk_text(
        change.text, await original_context(old, ctx), change.chunk_budget
    )
    intended = describe_prefix_edit(old, change.text, chunks, prefix=prefix)
    (root / f"identity_doc01_text_revision{intended.revision}.json").write_text(
        intended.model_dump_json(indent=2) + "\n"
    )
    (root / f"source_doc01_revision{intended.revision}.txt").write_text(change.text)
    await maintain_one(
        publisher,
        intended,
        change,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )
    result = await snapshot(
        publisher, await current_sources(root, publisher), args.query
    )
    (root / "text_revision_result.json").write_text(json.dumps(result, indent=2))
    return result
