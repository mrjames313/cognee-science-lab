"""Two captured original documents sharing identity output in native stores."""

import json
from uuid import NAMESPACE_URL, UUID, uuid5

from .models import IdentitySource
from .native import edge_metadata
from .publish import Publisher, contributions
from .retrieve import retrieve
from .validation import IntentError, map_chunks, text_digest


def fixture_id(label):
    return str(uuid5(NAMESPACE_URL, "cognee-lab:stage6:multi:" + label))


def add_lifecycle_records(payload, label, text):
    payload["entity_constructions"][fixture_id("shared_singleton")] = dict(
        name="Shared calibrator",
        description="Independent singleton support from each document.",
    )
    payload["entity_constructions"][fixture_id(label + ":singleton")] = dict(
        name=label + " instrument",
        description="Singleton supported by this identity source only.",
    )
    mid = fixture_id(label + ":unresolved")
    payload["entity_constructions"][mid] = dict(
        name="local reference", description="Unresolved group with no semantic facts."
    )
    start = text.index("plasma")
    payload["mention_groups"]["g02"] = dict(
        entity_id=mid,
        document_ref="doc01",
        occurrences=[dict(start=start, end=start + 6, text="plasma")],
        chunk_refs=["chunk01"],
        input_refs=["doc01"],
        producer_ref="fixture",
    )
    payload["mention_resolutions"]["r02"] = dict(
        group_ref="g02",
        status="unresolved",
        input_refs=["doc01"],
        producer_ref="fixture",
        explanation=None,
    )


async def prepare(root):
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points
    from .fixture import prepare as prepare_first, context_for, load_chunks

    if cognee.__version__ != "1.6.2":
        raise IntentError(
            "unsupported_version", "First fixture requires inspected Cognee 1.6.2"
        )

    first, chunks1, ctx1, publisher = await prepare_first(root, multi=True)
    payload = first.model_dump(mode="json")
    payload["identity_data_id"] = fixture_id("doc02:identity")
    payload["inputs"]["doc01"]["data_id"] = fixture_id("doc02:original")
    text = (root / "source.txt").read_text().rstrip(
        "\n"
    ) + " During startup, HC remains active.\n"
    (root / "source02.txt").write_text(text)
    await cognee.add(
        DataItem(
            data=str(root / "source02.txt"), data_id=UUID(fixture_id("doc02:original"))
        ),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    ctx2 = await context_for(fixture_id("doc02:original"))
    chunks2 = await load_chunks(None, ctx2)
    await add_data_points(chunks2, ctx=ctx2)
    if len(chunks2) != 1:
        raise IntentError(
            "fixture_shape", "Two-source example expects one chunk per document"
        )
    start, end = map_chunks(text, chunks2)[str(chunks2[0].id)]
    payload["inputs"]["doc01"]["text_sha256"] = text_digest(text)
    payload["inputs"]["chunk01"].update(
        chunk_id=str(chunks2[0].id), start=start, end=end
    )
    old_mid = str(first.mention_groups["g01"].entity_id)
    new_mid = fixture_id("doc02:mention")
    payload["entity_constructions"][new_mid] = payload["entity_constructions"].pop(
        old_mid
    )
    payload["mention_groups"]["g01"]["entity_id"] = new_mid
    for key in [fixture_id("doc01:singleton"), fixture_id("doc01:unresolved")]:
        payload["entity_constructions"].pop(key)
    add_lifecycle_records(payload, "doc02", text)
    second = IdentitySource.model_validate_json(json.dumps(payload))
    (root / "identity02.json").write_text(second.model_dump_json(indent=2) + "\n")
    await cognee.add(
        DataItem(data=str(root / "identity02.json"), data_id=second.identity_data_id),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    info = dict(
        dataset_id=str(first.dataset_id),
        sources={"doc01": "identity.json", "doc02": "identity02.json"},
    )
    (root / "multi-fixture-info.json").write_text(json.dumps(info, indent=2))
    return publisher, {
        "doc01": (first, chunks1, ctx1),
        "doc02": (second, chunks2, ctx2),
    }


def read_sources(root):
    manifest = json.loads((root / "multi-fixture-info.json").read_text())
    return {
        label: IdentitySource.model_validate_json((root / path).read_text())
        for label, path in manifest["sources"].items()
    }


async def current_sources(root, publisher):
    sources = read_sources(root)
    rows = {r["source"]: r for r in await publisher.records.rows()}
    return {
        label: (
            IdentitySource.model_validate_json(
                rows[str(source.identity_data_id)]["description"]
            )
            if str(source.identity_data_id) in rows
            else source
        )
        for label, source in sources.items()
    }


async def publish_one(
    publisher,
    source,
    chunks,
    original_ctx,
    root,
    label,
    *,
    reconcile=False,
    fault_stage=None,
):
    from .fixture import context_for, write_semantics, verify_semantics
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    ctx = await context_for(source.identity_data_id)

    async def task(items, ctx=None):
        from .text_changes import read_original

        for item in items:
            await publisher.publish(
                item,
                texts={item.original_input_ref: await read_original(item, ctx)},
                chunks={str(c.id): c for c in chunks},
                ctx=ctx,
                expected_revision=source.revision if reconcile else 0,
                origin="test/fault_injection" if fault_stage else "test",
                fault_stage=fault_stage,
                semantic_writer=(
                    None
                    if reconcile
                    else lambda: write_semantics(publisher, item, chunks, original_ctx)
                ),
                verify_semantics=lambda: verify_semantics(
                    publisher, item, chunks, original_ctx
                ),
            )
        return items

    async for _ in run_tasks_base(
        [Task(task, needs_llm=False)], [source], ctx.user, ctx
    ):
        pass


async def snapshot(publisher, sources, query="What does HC limit?"):
    from .fixture import OSCILLATIONS_ID
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records

    first = sources["doc01"]
    # Keep the original shared edge/controller visible after doc01 retargets.
    variant = sources["doc02"].variant_assignments["v01"]
    shared = await edge_metadata(
        publisher.graph,
        variant.source_entity_id,
        variant.target_entity_id,
        "resolves_to",
    )
    rows = {r["source"]: r for r in await publisher.records.rows(first.dataset_id)}
    result = dict(
        result=await retrieve(publisher, first.dataset_id, query),
        sources={},
        shared_variant=dict(
            present=shared is not None,
            contributions=contributions(shared.edge_properties) if shared else [],
            owners=shared.source_ref_keys if shared else [],
            properties=shared.edge_properties if shared else {},
        ),
        shared_singleton_present=await publisher.graph.get_node(
            fixture_id("shared_singleton")
        )
        is not None,
        shared_singleton_indexed=bool(
            await publisher.vector.retrieve(
                "Entity_name", [fixture_id("shared_singleton")]
            )
        ),
        borrowed_entity=await publisher.graph.get_node(str(variant.target_entity_id)),
        recovery_events=await publisher.records.events(first.dataset_id),
    )
    for label, source in sources.items():
        from .registered import read_registered

        registered = await read_registered(source)
        mid = source.mention_groups["g01"].entity_id
        unresolved = source.mention_groups["g02"].entity_id
        chunk = source.inputs["chunk01"].chunk_id
        doc = source.inputs[source.original_input_ref]
        fact = await edge_metadata(publisher.graph, mid, OSCILLATIONS_ID, "limits")
        ref = make_chunk_source_ref_key(source.dataset_id, doc.data_id, chunk)
        evidence = await get_edge_evidence_records(
            [UUID(generate_edge_object_id(str(mid), str(OSCILLATIONS_ID), "limits"))],
            source.dataset_id,
        )
        result["sources"][label] = dict(
            identity_data_id=str(source.identity_data_id),
            state=rows[str(source.identity_data_id)]["state"],
            saved_revision=source.revision,
            verified_revision=rows[str(source.identity_data_id)]["verified_revision"],
            registered_revision=registered.revision,
            registered_matches_saved=registered == source,
            resolution_target_entity_id=str(
                source.mention_resolutions["r01"].target_entity_id
            ),
            mention_entity_id=str(mid),
            original_marker_present=await publisher.graph.has_edge(
                str(chunk), str(mid), "has_identity_mention"
            ),
            original_fact_present=await publisher.graph.has_edge(
                str(mid), str(OSCILLATIONS_ID), "limits"
            ),
            original_fact_owned_by_chunk=fact is not None
            and ref in fact.source_ref_keys,
            original_evidence_present=any(
                e.data_id == doc.data_id and e.chunk_id == chunk for e in evidence
            ),
            unresolved_marker_present=await publisher.graph.has_edge(
                str(chunk), str(unresolved), "has_identity_mention"
            ),
            unresolved_entity_present=await publisher.graph.get_node(str(unresolved))
            is not None,
            private_singleton_present=await publisher.graph.get_node(
                fixture_id(label + ":singleton")
            )
            is not None,
            private_singleton_indexed=bool(
                await publisher.vector.retrieve(
                    "Entity_name", [fixture_id(label + ":singleton")]
                )
            ),
        )
    for row in rows.values():
        if row["plan"].get("text_change") and row["state"] == "current":
            from .text_fixture import transition_summary

            result.setdefault("text_changes", []).append(
                await transition_summary(publisher, row)
            )
    return result


async def run(args, root):
    from .fixture import context_for, load_chunks

    if args.command == "multi-fixture":
        publisher, prepared = await prepare(root)
        args._fixture_publisher = publisher
        sources = {label: value[0] for label, value in prepared.items()}
        for label, (source, chunks, ctx) in prepared.items():
            await publish_one(
                publisher,
                source,
                chunks,
                ctx,
                root,
                label,
                fault_stage=args.fault_stage if label == args.source else None,
            )
    else:
        publisher = await Publisher.configured()
        args._fixture_publisher = publisher
        sources = (
            await current_sources(root, publisher)
            if (root / "multi-fixture-info.json").exists()
            else {
                "doc01": IdentitySource.model_validate_json(
                    (root / "identity.json").read_text()
                )
            }
        )
        if args.source not in sources:
            raise IntentError(
                "source_missing", "Selected document is not in this fixture"
            )
        selected = sources[args.source]
        if args.command == "withdraw":
            await publisher.withdraw(
                selected,
                expected_revision=selected.revision,
                origin="test/fault_injection" if args.fault_stage else "test",
                fault_stage=args.fault_stage,
            )
        elif args.command == "reconcile":
            ctx = await context_for(
                selected.inputs[selected.original_input_ref].data_id
            )
            row = next(
                r
                for r in await publisher.records.rows(selected.dataset_id)
                if r["source"] == str(selected.identity_data_id)
            )
            if (
                row["state"] == "failed"
                and row["plan"].get("operation") == "identity_replace"
            ):
                if row["plan"].get("text_change"):
                    from .text_fixture import maintain_one
                    from .text_changes import TextChange

                    await maintain_one(
                        publisher,
                        selected,
                        TextChange(**row["plan"]["text_change"]),
                        expected_revision=selected.revision,
                    )
                else:
                    from .revisions import replace_one

                    await replace_one(
                        publisher,
                        selected,
                        root,
                        args.source,
                        expected_revision=selected.revision,
                    )
            else:
                await publish_one(
                    publisher,
                    selected,
                    await load_chunks(selected, ctx),
                    ctx,
                    root,
                    args.source,
                    reconcile=True,
                )
    if len(sources) == 1:
        result = dict(
            result=await retrieve(publisher, selected.dataset_id, args.query),
            publications=await publisher.records.rows(selected.dataset_id),
            recovery_events=await publisher.records.events(selected.dataset_id),
        )
    else:
        result = await snapshot(publisher, sources, args.query)
    (root / "multisource_result.json").write_text(json.dumps(result, indent=2))
    return result
