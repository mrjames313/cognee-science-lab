"""Real Cognee storage, captured decisions, synthetic original documents only."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from .environment import read_embedding
from .models import IdentitySource
from .publish import Publisher
from .retrieve import retrieve
from .validation import IntentError

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/identity"
SEED_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:seed-document")
OSCILLATIONS_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:oscillations")


async def context_for(data_id):
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data, Dataset
    from cognee.modules.pipelines.models import PipelineContext
    from cognee.modules.users.methods import get_default_user

    user = await get_default_user()
    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, UUID(str(data_id)))
        if data is None:
            raise IntentError("source_missing", "Fixture Data item missing")
        dataset = await session.get(Dataset, data.dataset_id)
    return PipelineContext(
        user=user,
        data_item=data,
        dataset=dataset,
        pipeline_name="stage6_captured_fixture",
    )


async def load_chunks(source, ctx, *, budget=None):
    from cognee.modules.chunking.TextChunker import TextChunker
    from cognee.modules.data.processing.document_types import TextDocument

    if budget is None:
        if source is None:
            budget = 512
        else:
            from cognee.infrastructure.databases.graph import get_graph_engine
            from .captured_chunks import recorded_budget

            budget = await recorded_budget(source, await get_graph_engine())

    doc = TextDocument(
        id=ctx.data_item.id,
        name=ctx.data_item.name,
        raw_data_location=ctx.data_item.raw_data_location,
        external_metadata=None,
    )
    return [
        chunk
        async for chunk in doc.read(chunker_cls=TextChunker, max_chunk_size=budget)
    ]


async def write_semantics(publisher, source, chunks, ctx):
    from cognee.modules.provenance.edge_evidence.persistence import (
        flush_context_provenance,
    )

    from .captured_chunks import captured_facts, fact_chunks

    for key, text in captured_facts(source):
        selected = fact_chunks(source, chunks, group_key=key, fact_text=text)
        group = source.mention_groups.get(key)
        for chunk in selected:
            await write_fact_chunk(publisher, source, chunk, group, ctx, fact_text=text)
    await flush_context_provenance(ctx)


async def write_fact_chunk(
    publisher, source, chunk, group, ctx, *, fact_text="it limits oscillations"
):
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
    from cognee.modules.engine.models import Entity
    from cognee.modules.graph.utils import ensure_default_edge_properties
    from cognee.modules.provenance.edge_evidence.capture import capture_graph_provenance
    from cognee.tasks.storage.index_data_points import index_data_points
    from cognee.tasks.storage.index_graph_edges import index_graph_edges

    ref = make_chunk_source_ref_key(source.dataset_id, ctx.data_item.id, chunk.id)
    target = await publisher.graph.get_node(str(OSCILLATIONS_ID))
    if target is None:
        node = Entity(
            id=OSCILLATIONS_ID, name="oscillations", description="Plasma oscillations."
        )
        await publisher.graph.add_nodes([node], source_ref_key=ref)
        await index_data_points([node], vector_engine=publisher.vector)
    elif target.get("type") != "Entity":
        raise IntentError("incompatible_type", "Fact endpoint is not an Entity")
    else:
        # Reusing an endpoint must retain it for this original chunk too.
        # Owning the incident fact alone does not protect the endpoint from
        # another document's removal and the resulting cascade.
        await publisher.graph.attach_node_source_refs([str(OSCILLATIONS_ID)], [ref])
    await publisher.graph.attach_node_source_refs([str(group.entity_id)], [ref])
    edge = (
        str(group.entity_id),
        str(OSCILLATIONS_ID),
        "limits",
        {"edge_text": fact_text},
    )
    edges = ensure_default_edge_properties([edge])
    await publisher.graph.add_edges(edges, source_ref_key=ref)
    await index_graph_edges(edges, vector_engine=publisher.vector)
    contained = ensure_default_edge_properties(
        [
            (str(chunk.id), str(group.entity_id), "contains", {}),
            (str(chunk.id), str(OSCILLATIONS_ID), "contains", {}),
        ]
    )
    await publisher.graph.add_edges(contained, source_ref_key=ref)
    # Use native per-chunk production/evidence buffering, including exact IDs.
    chunk._produced_edge_identities = [(edge[0], edge[1], edge[2])]
    chunk._provenance_edges = edges
    await capture_graph_provenance([chunk], [*edges, *contained], ctx)


async def verify_semantics(publisher, source, chunks, ctx):
    from .captured_chunks import captured_facts, retired_facts

    for key, text in (*captured_facts(source), *retired_facts(source)):
        await verify_fact(publisher, source, chunks, ctx, group_key=key, fact_text=text)


async def verify_fact(publisher, source, chunks, ctx, *, group_key, fact_text):
    from cognee.infrastructure.databases.provenance import (
        EdgeIdentity,
        make_chunk_source_ref_key,
        parse_source_ref_key,
    )
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records

    from .captured_chunks import fixture_mention_id

    mid = str(fixture_mention_id(source, group_key))
    identity = EdgeIdentity(mid, str(OSCILLATIONS_ID), "limits")
    metadata = (await publisher.graph.get_edge_delete_data([identity])).get(identity)
    from .captured_chunks import fact_chunks

    expected = fact_chunks(source, chunks, group_key=group_key, fact_text=fact_text)
    refs = {
        make_chunk_source_ref_key(source.dataset_id, ctx.data_item.id, c.id)
        for c in expected
    }
    own_refs = set()
    if metadata is not None:
        for ref in metadata.source_ref_keys:
            parsed = parse_source_ref_key(ref)
            if (
                parsed.dataset_id == source.dataset_id
                and parsed.data_id == ctx.data_item.id
            ):
                own_refs.add(ref)
    if (expected and metadata is None) or own_refs != refs:
        raise IntentError(
            "semantic_missing",
            "Original-chunk fact ownership missing; explicitly rebuild",
        )
    if not expected and metadata is not None:
        raise IntentError(
            "semantic_retirement", "Retired captured fact remains in graph"
        )
    eid = UUID(generate_edge_object_id(mid, str(OSCILLATIONS_ID), "limits"))
    evidence = await get_edge_evidence_records(
        [eid], source.dataset_id, per_edge_limit=100, total_limit=100
    )
    own = {
        (e.chunk_id, e.chunk_index) for e in evidence if e.data_id == ctx.data_item.id
    }
    if own != {(c.id, c.chunk_index) for c in expected}:
        raise IntentError(
            "evidence_missing", "Native original evidence missing; explicitly rebuild"
        )
    for chunk in chunks:
        if not await publisher.vector.retrieve("DocumentChunk_text", [str(chunk.id)]):
            raise IntentError("verify_index", "Original chunk vector missing")


async def prepare(root, *, multi=False, chunk_budget=512, source_text=None):
    import cognee
    from cognee.modules.engine.models import Entity
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points

    template = json.loads(
        (FIXTURES / "cognee_identity_source_example.json").read_text()
    )
    original_id = UUID(template["inputs"]["doc01"]["data_id"])
    generated_id = UUID(template["identity_data_id"])
    text = (
        source_text
        if source_text is not None
        else (FIXTURES / "source.txt").read_text()
    )
    (root / "source.txt").write_text(text)
    if source_text is not None:
        from .validation import text_digest

        template["inputs"]["doc01"]["text_sha256"] = text_digest(text)
        template["mention_groups"]["g01"]["occurrences"] = [
            dict(
                start=text.index("the controller"),
                end=text.index("the controller") + len("the controller"),
                text="the controller",
            ),
            dict(
                start=text.index("it limits"),
                end=text.index("it limits") + 2,
                text="it",
            ),
        ]
    (root / "seed.txt").write_text("Helios controller regulates plasma heating.\n")
    await cognee.add(
        [
            DataItem(data=str(root / "seed.txt"), data_id=SEED_DATA_ID),
            DataItem(data=str(root / "source.txt"), data_id=original_id),
        ],
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    original_ctx = await context_for(original_id)
    dataset = original_ctx.dataset.id
    template["dataset_id"] = str(dataset)
    for item in template["inputs"].values():
        if "dataset_id" in item:
            item["dataset_id"] = str(dataset)
    a = UUID(template["mention_resolutions"]["r01"]["target_entity_id"])
    recipe = template["entity_constructions"][str(a)]
    await add_data_points(
        [Entity(id=a, name=recipe["name"], description=recipe["description"])],
        ctx=await context_for(SEED_DATA_ID),
    )
    publisher = await Publisher.configured()
    await publisher.graph.update_node(str(a), {"fixture_sentinel": "preserve me"})
    # Deliberately different creation values must not overwrite a borrowed node.
    recipe["description"] = "Creation seed only; never overwrite an existing Entity."
    chunks = await load_chunks(None, original_ctx, budget=chunk_budget)
    if multi:
        from .multisource import add_lifecycle_records

        add_lifecycle_records(template, "doc01", text)
    from .captured_chunks import bind_chunks

    bind_chunks(template, text, chunks)
    await add_data_points(chunks, ctx=original_ctx)
    source = IdentitySource.model_validate_json(json.dumps(template))
    (root / "identity.json").write_text(source.model_dump_json(indent=2) + "\n")
    await cognee.add(
        DataItem(data=str(root / "identity.json"), data_id=generated_id),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    info = dict(
        dataset_id=str(dataset),
        original_data_id=str(original_id),
        identity_data_id=str(generated_id),
        expected_fact_target=str(OSCILLATIONS_ID),
    )
    (root / "fixture-info.json").write_text(json.dumps(info, indent=2))
    return source, chunks, original_ctx, publisher


async def run(args, root):
    import cognee

    if cognee.__version__ != "1.6.2":
        raise IntentError(
            "unsupported_version", "First fixture requires inspected Cognee 1.6.2"
        )
    if args.command == "fixture":
        source, chunks, original_ctx, publisher = await prepare(root)
    else:
        source = IdentitySource.model_validate_json(
            (root / "identity.json").read_text()
        )
        publisher = await Publisher.configured()
        original_ctx, chunks = None, None
    dataset_id = source.dataset_id
    args._fixture_publisher = publisher
    if args.command == "status":
        return dict(
            publications=await publisher.records.rows(dataset_id),
            recovery_events=await publisher.records.events(dataset_id),
        )
    if args.command == "retrieve":
        return await retrieve(publisher, dataset_id, args.query)
    if chunks is None:
        original_ctx = await context_for(
            source.inputs[source.original_input_ref].data_id
        )
        chunks = await load_chunks(source, original_ctx)

    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    ctx = await context_for(source.identity_data_id)

    creating = args.command == "fixture"

    async def publish_fixture(items, ctx=None):
        for item in items:
            await (publisher.publish if creating else publisher.reconcile)(
                item,
                texts={"doc01": (root / "source.txt").read_text()},
                chunks={str(c.id): c for c in chunks},
                ctx=ctx,
                origin="test/fault_injection" if args.fault_stage else "test",
                fault_stage=args.fault_stage,
                semantic_writer=(
                    (lambda: write_semantics(publisher, item, chunks, original_ctx))
                    if creating
                    else None
                ),
                verify_semantics=lambda: verify_semantics(
                    publisher, item, chunks, original_ctx
                ),
            )
        return items

    async for _ in run_tasks_base(
        [Task(publish_fixture, needs_llm=False)], [source], ctx.user, ctx
    ):
        pass
    answer = await retrieve(publisher, dataset_id, args.query)
    if not any(
        f["relationship"] == "limits"
        and f["target_id"] == str(OSCILLATIONS_ID)
        and f.get("identity", {}).get("state") == "accepted"
        for f in answer["facts"]
    ):
        raise IntentError(
            "fixture_retrieval", "Expected mention-anchored fact was not retrieved"
        )
    result = dict(
        cognee_version=cognee.__version__,
        fixture_root=str(root),
        profile="native configured stores; no LLM",
        embedding=read_embedding(root),
        result=answer,
        recovery_events=await publisher.records.events(dataset_id),
    )
    (root / "result.json").write_text(json.dumps(result, indent=2))
    return result
