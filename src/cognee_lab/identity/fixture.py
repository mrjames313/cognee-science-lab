"""Real Cognee storage, captured decisions, synthetic original documents only."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from .models import IdentitySource
from .publish import Publisher
from .retrieve import retrieve
from .validation import IntentError, map_chunks

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


async def load_chunks(source, ctx):
    from cognee.modules.chunking.TextChunker import TextChunker
    from cognee.modules.data.processing.document_types import TextDocument

    doc = TextDocument(
        id=ctx.data_item.id,
        name=ctx.data_item.name,
        raw_data_location=ctx.data_item.raw_data_location,
        external_metadata=None,
    )
    return [
        chunk async for chunk in doc.read(chunker_cls=TextChunker, max_chunk_size=512)
    ]


async def write_semantics(publisher, source, chunks, ctx):
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
    from cognee.modules.engine.models import Entity
    from cognee.modules.graph.utils import ensure_default_edge_properties
    from cognee.modules.provenance.edge_evidence.capture import capture_graph_provenance
    from cognee.modules.provenance.edge_evidence.persistence import (
        flush_context_provenance,
    )
    from cognee.tasks.storage.index_data_points import index_data_points
    from cognee.tasks.storage.index_graph_edges import index_graph_edges

    chunk = chunks[0]
    group = source.mention_groups["g01"]
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
    await publisher.graph.attach_node_source_refs([str(group.entity_id)], [ref])
    edge = (
        str(group.entity_id),
        str(OSCILLATIONS_ID),
        "limits",
        {"edge_text": "it limits oscillations"},
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
    await flush_context_provenance(ctx)


async def verify_semantics(publisher, source, chunks, ctx):
    from cognee.infrastructure.databases.provenance import (
        EdgeIdentity,
        make_chunk_source_ref_key,
    )
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records

    mid = str(source.mention_groups["g01"].entity_id)
    identity = EdgeIdentity(mid, str(OSCILLATIONS_ID), "limits")
    metadata = (await publisher.graph.get_edge_delete_data([identity])).get(identity)
    ref = make_chunk_source_ref_key(source.dataset_id, ctx.data_item.id, chunks[0].id)
    if metadata is None or ref not in metadata.source_ref_keys:
        raise IntentError(
            "semantic_missing",
            "Original-chunk fact ownership missing; explicitly rebuild",
        )
    eid = UUID(generate_edge_object_id(mid, str(OSCILLATIONS_ID), "limits"))
    evidence = await get_edge_evidence_records([eid], source.dataset_id)
    if not any(
        e.data_id == ctx.data_item.id and e.chunk_id == chunks[0].id for e in evidence
    ):
        raise IntentError(
            "evidence_missing", "Native original evidence missing; explicitly rebuild"
        )
    if not await publisher.vector.retrieve("DocumentChunk_text", [str(chunks[0].id)]):
        raise IntentError("verify_index", "Original chunk vector missing")


async def prepare(root):
    import cognee
    from cognee.modules.engine.models import Entity
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points

    template = json.loads(
        (FIXTURES / "cognee_identity_source_example.json").read_text()
    )
    original_id = UUID(template["inputs"]["doc01"]["data_id"])
    generated_id = UUID(template["identity_data_id"])
    (root / "source.txt").write_bytes((FIXTURES / "source.txt").read_bytes())
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
    chunks = await load_chunks(None, original_ctx)
    if len(chunks) != 1:
        raise IntentError("fixture_shape", "Tiny fixture expected one native chunk")
    text = (root / "source.txt").read_text()
    mapping = map_chunks(text, chunks)
    start, end = mapping[str(chunks[0].id)]
    template["inputs"]["chunk01"].update(
        chunk_id=str(chunks[0].id), start=start, end=end
    )
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
        original_ctx = await context_for(
            source.inputs[source.original_input_ref].data_id
        )
        chunks = await load_chunks(source, original_ctx)
        publisher = await Publisher.configured()
    dataset_id = source.dataset_id
    if args.command == "status":
        return dict(
            publications=await publisher.records.rows(dataset_id),
            recovery_events=await publisher.records.events(dataset_id),
        )
    if args.command == "retrieve":
        return await retrieve(publisher, dataset_id, args.query)

    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    ctx = await context_for(source.identity_data_id)

    async def publish_fixture(items, ctx=None):
        for item in items:
            await publisher.publish(
                item,
                texts={"doc01": (root / "source.txt").read_text()},
                chunks={str(c.id): c for c in chunks},
                ctx=ctx,
                expected_revision=0 if args.command == "fixture" else source.revision,
                origin="test/fault_injection" if args.fault_stage else "test",
                fault_stage=args.fault_stage,
                semantic_writer=(
                    (lambda: write_semantics(publisher, item, chunks, original_ctx))
                    if args.command == "fixture"
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
        profile="native configured stores; local deterministic embedding service; no LLM",
        result=answer,
        recovery_events=await publisher.records.events(dataset_id),
    )
    (root / "result.json").write_text(json.dumps(result, indent=2))
    return result
