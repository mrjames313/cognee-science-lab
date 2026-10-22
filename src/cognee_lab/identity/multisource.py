"""Two captured original documents sharing identity output in native stores."""

import json
from uuid import NAMESPACE_URL, UUID, uuid5

from .models import IdentitySource
from .native import edge_metadata
from .publish import Publisher, contributions
from .retrieve import retrieve
from .validation import IntentError, text_digest


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


def add_dependency(payload, first, text):
    """doc02 consumed doc01: its r01 decision lists doc01's text and doc01's
    private singleton as inputs, so forgetting doc01 would take away what doc02
    reasoned from."""
    from .validation import object_digest

    doc = first.inputs[first.original_input_ref]
    singleton = fixture_id("doc01:singleton")
    recipe = first.entity_constructions[UUID(singleton)]
    payload["inputs"]["doc01_text"] = dict(
        kind="source_text",
        dataset_id=str(doc.dataset_id),
        data_id=str(doc.data_id),
        text_sha256=doc.text_sha256,
    )
    payload["inputs"]["doc01_instrument"] = dict(
        kind="corpus_object",
        dataset_id=str(first.dataset_id),
        entity_id=singleton,
        selected_fields=["name", "description"],
        content_sha256=object_digest(
            dict(name=recipe.name, description=recipe.description)
        ),
    )
    payload["mention_resolutions"]["r01"]["input_refs"] += [
        "doc01_text",
        "doc01_instrument",
    ]


async def prepare(root, *, chunked=False, dependent=False):
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points
    from .fixture import prepare as prepare_first, context_for, load_chunks

    if cognee.__version__ != "1.6.2":
        raise IntentError(
            "unsupported_version", "First fixture requires inspected Cognee 1.6.2"
        )

    budget = 9 if chunked else 512
    text = None
    if chunked:
        from .fixture import FIXTURES

        text = (
            (FIXTURES / "source.txt")
            .read_text()
            .replace(". The controller", ", the controller")
            .replace("; it", ", and it")
        )
    first, chunks1, ctx1, publisher = await prepare_first(
        root, multi=True, chunk_budget=budget, source_text=text
    )
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
    chunks2 = await load_chunks(None, ctx2, budget=budget)
    await add_data_points(chunks2, ctx=ctx2)
    payload["inputs"]["doc01"]["text_sha256"] = text_digest(text)
    old_mid = str(first.mention_groups["g01"].entity_id)
    new_mid = fixture_id("doc02:mention")
    payload["entity_constructions"][new_mid] = payload["entity_constructions"].pop(
        old_mid
    )
    payload["mention_groups"]["g01"]["entity_id"] = new_mid
    for key in [fixture_id("doc01:singleton"), fixture_id("doc01:unresolved")]:
        payload["entity_constructions"].pop(key)
    add_lifecycle_records(payload, "doc02", text)
    if dependent:
        add_dependency(payload, first, text)
    from .captured_chunks import bind_chunks

    bind_chunks(payload, text, chunks2)
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
        dependent=dependent,
    )
    (root / "multi-fixture-info.json").write_text(json.dumps(info, indent=2))
    if chunked:
        (root / "chunked-fixture-info.json").write_text(
            json.dumps(dict(chunk_budget=budget, prefix="Δ review: "), indent=2)
        )
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
    expected_revision=0,
    fault_stage=None,
):
    """Publish a source. A publication (first, or a re-add after forget)
    introduces the next revision and writes the captured facts; a reconcile
    completes the saved revision and only verifies them."""
    from .fixture import context_for, write_semantics, verify_semantics
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    ctx = await context_for(source.identity_data_id)
    publishes = source.revision == expected_revision + 1

    async def task(items, ctx=None):
        from .registered import read_texts

        for item in items:
            await publisher.publish(
                item,
                texts=await read_texts(item),
                chunks={str(c.id): c for c in chunks},
                ctx=ctx,
                expected_revision=expected_revision,
                origin="test/fault_injection" if fault_stage else "test",
                fault_stage=fault_stage,
                semantic_writer=(
                    (lambda: write_semantics(publisher, item, chunks, original_ctx))
                    if publishes
                    else None
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


def describe_readd(forgotten, text, chunks):
    """The forgotten description again at the next revision. Every group is
    fresh, so its Entity UUID derives from the new revision and its key."""
    from .captured_chunks import bind_chunks
    from .validation import fresh_mention_id

    payload = forgotten.model_dump(mode="json")
    payload["revision"] = forgotten.revision + 1
    for key, group in payload["mention_groups"].items():
        fresh = str(
            fresh_mention_id(forgotten.identity_data_id, payload["revision"], key)
        )
        payload["entity_constructions"][fresh] = payload["entity_constructions"].pop(
            group["entity_id"]
        )
        group["entity_id"] = fresh
    bind_chunks(payload, text, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def readd(publisher, root, label, forgotten, *, expected_revision, fault_stage):
    """Add the forgotten document and identity source again from the files in
    the root, then publish at the next revision."""
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points
    from .fixture import context_for, load_chunks
    from .validation import text_digest

    row = await publisher.records.row(forgotten)
    if row["state"] != "forgotten":
        raise IntentError("forget_state", "Re-add needs a forgotten source")
    doc = forgotten.inputs[forgotten.original_input_ref]
    text_file = root / ("source.txt" if label == "doc01" else "source02.txt")
    text = text_file.read_text()
    if text_digest(text) != doc.text_sha256:
        raise IntentError("source_changed", "Re-add the forgotten document's text")
    budget = 512
    if (root / "chunked-fixture-info.json").exists():
        budget = json.loads((root / "chunked-fixture-info.json").read_text())[
            "chunk_budget"
        ]
    await cognee.add(
        DataItem(data=str(text_file), data_id=doc.data_id),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    ctx = await context_for(doc.data_id)
    chunks = await load_chunks(None, ctx, budget=budget)
    await add_data_points(chunks, ctx=ctx)
    source = describe_readd(forgotten, text, chunks)
    path = root / f"identity_{label}_revision{source.revision}.json"
    path.write_text(source.model_dump_json(indent=2) + "\n")
    await cognee.add(
        DataItem(data=str(path), data_id=source.identity_data_id),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    await publish_one(
        publisher,
        source,
        chunks,
        ctx,
        root,
        label,
        expected_revision=expected_revision,
        fault_stage=fault_stage,
    )


async def forget_checks(publisher, source, plan, label):
    """What remains of a source whose forget began, plus the fixture's own
    objects: the values a journey reads after a failure and after completion."""
    from .captured_chunks import fixture_mention_id
    from .forget import remains
    from .native import mention_fact

    graph, vector = publisher.graph, publisher.vector
    mention_ids = [str(g.entity_id) for g in source.mention_groups.values()]
    return dict(
        **await remains(publisher, source, plan),
        mention_nodes_present=[
            m for m in mention_ids if await graph.get_node(m) is not None
        ],
        mention_vectors_present=[
            m for m in mention_ids if await vector.retrieve("Entity_name", [m])
        ],
        original_fact_present=(
            await mention_fact(publisher, source, fixture_mention_id(source))
        ).edge
        is not None,
        private_singleton_present=await graph.get_node(fixture_id(label + ":singleton"))
        is not None,
        private_singleton_indexed=bool(
            await vector.retrieve("Entity_name", [fixture_id(label + ":singleton")])
        ),
    )


async def snapshot(publisher, sources, query="What does HC limit?"):
    from .fixture import OSCILLATIONS_ID
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records
    from .captured_chunks import fact_chunks, fixture_mention_id, retired_mentions
    from .models import ChunkInput
    from types import SimpleNamespace

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
    hc = await publisher.graph.get_node_delete_data([str(variant.source_entity_id)])
    result["hc_entity"] = dict(
        present=str(variant.source_entity_id) in hc,
        owners=sorted(
            hc[str(variant.source_entity_id)].source_ref_keys
            if str(variant.source_entity_id) in hc
            else []
        ),
    )
    for label, source in sources.items():
        from .registered import read_registered

        row = rows[str(source.identity_data_id)]
        if row["plan"].get("operation") == "identity_forget":
            result["sources"][label] = dict(
                identity_data_id=str(source.identity_data_id),
                state=row["state"],
                saved_revision=source.revision,
                verified_revision=row["verified_revision"],
                forget=await forget_checks(publisher, source, row["plan"], label),
            )
            continue
        registered = await read_registered(source)
        mid = fixture_mention_id(source)
        unresolved_group = source.mention_groups.get("g02")
        unresolved = (
            unresolved_group.entity_id
            if unresolved_group
            else fixture_id(label + ":unresolved")
        )
        group = source.mention_groups.get("g01")
        mapped = [i for i in source.inputs.values() if isinstance(i, ChunkInput)]
        chunks = []
        for item in mapped:
            node = await publisher.graph.get_node(str(item.chunk_id))
            if node is not None:
                chunks.append(
                    SimpleNamespace(
                        id=item.chunk_id,
                        chunk_index=node["chunk_index"],
                        text=node["text"],
                    )
                )
        selected = fact_chunks(source, chunks)
        doc = source.inputs[source.original_input_ref]
        fact = await edge_metadata(publisher.graph, mid, OSCILLATIONS_ID, "limits")
        refs = {
            make_chunk_source_ref_key(source.dataset_id, doc.data_id, c.id)
            for c in selected
        }
        evidence = await get_edge_evidence_records(
            [UUID(generate_edge_object_id(str(mid), str(OSCILLATIONS_ID), "limits"))],
            source.dataset_id,
            per_edge_limit=100,
            total_limit=100,
        )
        chunk_checks = []
        for i in mapped:
            node = next(c for c in chunks if c.id == i.chunk_id)
            chunk_ref = make_chunk_source_ref_key(
                source.dataset_id, doc.data_id, i.chunk_id
            )
            chunk_checks.append(
                dict(
                    chunk_id=str(i.chunk_id),
                    start=i.start,
                    end=i.end,
                    chunk_index=node.chunk_index,
                    mention_marker_present=await publisher.graph.has_edge(
                        str(i.chunk_id), str(mid), "has_identity_mention"
                    ),
                    owns_captured_fact=fact is not None
                    and chunk_ref in fact.source_ref_keys,
                    evidence_present=any(
                        e.data_id == doc.data_id
                        and e.chunk_id == i.chunk_id
                        and e.chunk_index == node.chunk_index
                        for e in evidence
                    ),
                )
            )
        result["sources"][label] = dict(
            identity_data_id=str(source.identity_data_id),
            state=rows[str(source.identity_data_id)]["state"],
            saved_revision=source.revision,
            verified_revision=rows[str(source.identity_data_id)]["verified_revision"],
            registered_revision=registered.revision,
            registered_matches_saved=registered == source,
            resolution_target_entity_id=(
                str(source.mention_resolutions["r01"].target_entity_id)
                if "r01" in source.mention_resolutions
                else None
            ),
            mention_entity_id=str(mid),
            original_marker_present=group is not None
            and all(
                [
                    await publisher.graph.has_edge(
                        str(source.inputs[k].chunk_id), str(mid), "has_identity_mention"
                    )
                    for k in group.chunk_refs
                ]
            ),
            original_fact_present=await publisher.graph.has_edge(
                str(mid), str(OSCILLATIONS_ID), "limits"
            ),
            original_fact_owned_by_chunk=fact is not None
            and refs <= set(fact.source_ref_keys),
            original_evidence_present=bool(selected)
            and {
                (e.chunk_id, e.chunk_index)
                for e in evidence
                if e.data_id == doc.data_id
            }
            == {(c.id, c.chunk_index) for c in selected},
            unresolved_marker_present=unresolved_group is not None
            and all(
                [
                    await publisher.graph.has_edge(
                        str(source.inputs[k].chunk_id),
                        str(unresolved),
                        "has_identity_mention",
                    )
                    for k in unresolved_group.chunk_refs
                ]
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
            chunk_count=len(mapped),
            chunk_mapping=chunk_checks,
            mention_marker_chunk_ids=(
                [str(source.inputs[k].chunk_id) for k in group.chunk_refs]
                if group
                else []
            ),
            fact_evidence_chunk_ids=[str(c.id) for c in selected],
        )
        if group is None:
            from .resolved_retirement import retirement_checks

            result["sources"][label]["resolved_group_retirement"] = (
                await retirement_checks(publisher, source, mid)
            )
            combined = {
                k: await retirement_checks(publisher, source, rid)
                for k, rid in retired_mentions(source).items()
                if k != "g01"
            }
            if combined:
                result["sources"][label]["combined_group_retirement"] = combined
    for row in rows.values():
        if row["plan"].get("text_change") and row["state"] == "current":
            from .text_fixture import transition_summary

            result.setdefault("text_changes", []).append(
                await transition_summary(publisher, row)
            )
    return result


async def run(args, root):
    from .fixture import context_for, load_chunks

    if args.command in {"multi-fixture", "chunked-fixture"}:
        publisher, prepared = await prepare(
            root,
            chunked=args.command == "chunked-fixture",
            dependent=args.dependent,
        )
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
        origin = "test/fault_injection" if args.fault_stage else "test"
        if args.command == "withdraw":
            await publisher.withdraw(
                selected,
                expected_revision=selected.revision,
                origin=origin,
                fault_stage=args.fault_stage,
            )
        elif args.command == "forget":
            await publisher.forget(
                selected,
                expected_revision=args.expected_revision,
                origin=origin,
                fault_stage=args.fault_stage,
            )
        elif args.command == "readd":
            await readd(
                publisher,
                root,
                args.source,
                selected,
                expected_revision=args.expected_revision,
                fault_stage=args.fault_stage,
            )
        elif args.command == "reconcile":
            row = await publisher.records.row(selected)
            if row["state"] == "forgotten":
                from .storage import FORGOTTEN_SOURCE

                raise IntentError("forgotten_source", FORGOTTEN_SOURCE)
            if (
                row["state"] == "failed"
                and row["plan"].get("operation") == "identity_forget"
            ):
                await publisher.forget(
                    selected, expected_revision=selected.revision, origin="test"
                )
            elif (
                row["state"] == "failed"
                and row["plan"].get("operation") == "identity_replace"
            ):
                if row["plan"].get("text_change"):
                    from .text_fixture import maintain_one
                    from .text_changes import TextChange

                    await maintain_one(
                        publisher,
                        selected,
                        TextChange.from_plan(row["plan"]),
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
                ctx = await context_for(
                    selected.inputs[selected.original_input_ref].data_id
                )
                await publish_one(
                    publisher,
                    selected,
                    await load_chunks(selected, ctx),
                    ctx,
                    root,
                    args.source,
                    expected_revision=selected.revision,
                )
        # Forget and re-add change the saved descriptions; report the new ones.
        sources = await current_sources(root, publisher)
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
