"""Real Cognee storage, captured decisions, synthetic original documents only."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from .environment import DATASET_NAME, read_embedding
from .models import IdentitySource
from .publish import Publisher
from .registered import context_for
from .retrieve import retrieve
from .validation import IntentError

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/identity"
SEED_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:seed-document")
OSCILLATIONS_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:oscillations")


async def load_chunks(source, ctx):
    """The native chunks of a saved source's original, chunked again in
    memory with the budget its chunks record. Writes nothing."""
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.modules.chunking.TextChunker import TextChunker
    from cognee.modules.data.processing.document_types import TextDocument

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


async def fact_written(publisher, source, chunk, group, ctx):
    """Whether this chunk already owns the group's captured fact with its
    evidence row, so a reconcile after a failure writes only what is missing."""
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key

    from .native import mention_fact

    fact = await mention_fact(publisher, source, group.entity_id)
    ref = make_chunk_source_ref_key(source.dataset_id, ctx.data_item.id, chunk.id)
    return (
        fact.edge is not None
        and ref in fact.edge.source_ref_keys
        and any(
            e.data_id == ctx.data_item.id and e.chunk_id == chunk.id
            for e in fact.evidence
        )
    )


async def write_semantics(publisher, source, chunks, ctx):
    """Write the captured facts of the source's chunks. Idempotent: a chunk
    whose fact and evidence are in place is skipped, so a first publication, a
    re-add and the reconcile of either call this."""
    from cognee.modules.provenance.edge_evidence.persistence import (
        flush_context_provenance,
    )

    from .captured_chunks import captured_facts, fact_chunks

    for key, text in captured_facts(source):
        selected = fact_chunks(source, chunks, group_key=key, fact_text=text)
        group = source.mention_groups.get(key)
        for chunk in selected:
            if await fact_written(publisher, source, chunk, group, ctx):
                continue
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


class CapturedSemantics:
    """The captured fixture facts, as the lab's cognify writes and checks
    them (`entry.Semantics`)."""

    write = staticmethod(write_semantics)
    verify = staticmethod(verify_semantics)


async def expect_current(publisher, source, expected_revision, recovery):
    """A fixture command starts from the source's current row at the
    expected revision. `recovery` tells the user what to reconcile when the
    row is pending or failed."""
    from .storage import STALE_REVISION

    row = await publisher.records.row(source)
    if row.revision != expected_revision:
        raise IntentError(*STALE_REVISION)
    if row.state != "current":
        raise IntentError("recovery_choice", recovery)
    return row


def doc01_template(text=None) -> dict:
    """The captured doc01 description before it is bound to a dataset and
    chunks, for the fixture text or for `text`."""
    template = json.loads(
        (FIXTURES / "cognee_identity_source_example.json").read_text()
    )
    if text is not None:
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
    return template


def borrowed_entity(template):
    """The reusable Entity doc01 resolves to, which the seed document
    already holds."""
    from cognee.modules.engine.models import Entity

    a = UUID(template["mention_resolutions"]["r01"]["target_entity_id"])
    recipe = template["entity_constructions"][str(a)]
    return Entity(id=a, name=recipe["name"], description=recipe["description"])


def describe_doc01(template, dataset_id, text, chunks, *, multi=False, amend=None):
    """Bind the captured description to the dataset and the native chunks.
    `amend(payload)` edits it before validation."""
    from .captured_chunks import bind_chunks

    template["dataset_id"] = str(dataset_id)
    for item in template["inputs"].values():
        if "dataset_id" in item:
            item["dataset_id"] = str(dataset_id)
    a = template["mention_resolutions"]["r01"]["target_entity_id"]
    # Deliberately different creation values must not overwrite a borrowed node.
    template["entity_constructions"][a][
        "description"
    ] = "Creation seed only; never overwrite an existing Entity."
    if multi:
        from .multisource import add_lifecycle_records

        add_lifecycle_records(template, "doc01", text)
    if amend is not None:
        amend(template)
    bind_chunks(template, text, chunks)
    return IdentitySource.model_validate_json(json.dumps(template))


async def seed_corpus(root, template):
    """Register the seed document, stamped, with the Entity doc01 borrows,
    and return the publisher of the root's stores."""
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points

    from .registered import stamp

    (root / "seed.txt").write_text("Helios controller regulates plasma heating.\n")
    await cognee.add(
        DataItem(data=str(root / "seed.txt"), data_id=SEED_DATA_ID),
        dataset_name=DATASET_NAME,
        skip_connection_test=True,
    )
    seed = await context_for(SEED_DATA_ID)
    await stamp(SEED_DATA_ID, seed.dataset.id)
    entity = borrowed_entity(template)
    await add_data_points([entity], ctx=seed)
    publisher = await Publisher.configured()
    await publisher.graph.update_node(
        str(entity.id), {"fixture_sentinel": "preserve me"}
    )
    return publisher


def write_info(root, source):
    info = dict(
        dataset_id=str(source.dataset_id),
        original_data_id=str(source.inputs[source.original_input_ref].data_id),
        identity_data_id=str(source.identity_data_id),
        expected_fact_target=str(OSCILLATIONS_ID),
    )
    (root / "fixture-info.json").write_text(json.dumps(info, indent=2))


async def start_doc01(root, source_text=None):
    """doc01's captured template and original, the original's text written
    to the root (the fixture text or `source_text`), and the publisher of
    the root's stores once the seed corpus is registered."""
    from . import entry

    template = doc01_template(source_text)
    original = entry.Original(
        root / "source.txt", UUID(template["inputs"]["doc01"]["data_id"])
    )
    original.path.write_text(
        source_text
        if source_text is not None
        else (FIXTURES / "source.txt").read_text()
    )
    return template, original, await seed_corpus(root, template)


def doc01_describer(root, template, **options):
    """The lab's `add` describer for doc01 (`describe_doc01` with
    `options`), which also writes the root's fixture-info.json."""

    def describe(draft):
        # Written before the publication, so a failed run leaves it too.
        source = describe_doc01(
            template, draft.dataset_id, draft.text, draft.chunks, **options
        )
        write_info(root, source)
        return source

    return describe


async def create(root, args):
    """The doc01 root through the lab's remember: the seed corpus first,
    then doc01 registered, described from its chunks and published in
    Cognee's cognify pipeline. The CLI closes the publisher's stores."""
    from . import entry

    template, original, publisher = await start_doc01(root)
    args._fixture_publisher = publisher
    return await entry.remember(
        publisher,
        DATASET_NAME,
        original,
        describe=doc01_describer(root, template),
        identity_path=root / "identity.json",
        semantics=CapturedSemantics(),
        fault_stage=args.fault_stage,
        origin="test",
    )


async def add_doc01(root, *, chunk_budget=512, source_text=None, **options):
    """Register doc01 and its description through the lab's `add`, for a
    root with more sources, which then publishes each one in order. Returns
    the publisher and doc01's description (`doc01_describer`'s options)."""
    from . import entry

    template, original, publisher = await start_doc01(root, source_text)
    source = await entry.add(
        DATASET_NAME,
        original,
        describe=doc01_describer(root, template, **options),
        identity_path=root / "identity.json",
        chunk_budget=chunk_budget,
    )
    return publisher, source


async def run(args, root):
    import cognee

    if cognee.__version__ != "1.6.2":
        raise IntentError(
            "unsupported_version", "First fixture requires inspected Cognee 1.6.2"
        )
    if args.command == "fixture":
        source = await create(root, args)
        publisher = args._fixture_publisher
    else:
        source = IdentitySource.model_validate_json(
            (root / "identity.json").read_text()
        )
        publisher = await Publisher.configured()
        args._fixture_publisher = publisher
    dataset_id = source.dataset_id
    if args.command == "status":
        from .multisource import root_labels
        from .native_copy import forget_hint, natively_deleted
        from .retrieve import withholding_status

        rows = await publisher.records.rows(dataset_id)
        labels = root_labels(root)
        return dict(
            publications=[row.record() for row in rows],
            recovery_events=await publisher.records.events(dataset_id),
            removed_entities=await publisher.records.removal_report(),
            **await withholding_status(publisher, rows),
            native_deleted=[
                (
                    dict(entry, next=forget_hint(labels[key], entry["revision"]))
                    if key in labels
                    else entry
                )
                for key, entry in (
                    await natively_deleted(publisher.graph, rows)
                ).items()
            ],
        )
    if args.command == "retrieve":
        return await retrieve(publisher, dataset_id, args.query)
    if args.command == "reconcile":
        await reconcile(root, args, publisher, source)
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
        cognify_stamps=await cognify_stamps(source),
    )
    (root / "result.json").write_text(json.dumps(result, indent=2))
    return result


async def cognify_stamps(source):
    """Whether each Data item of the root is stamped as cognified, so a
    plain `cognee.cognify` skips it."""
    from .registered import stamped

    ids = dict(
        original=source.inputs[source.original_input_ref].data_id,
        identity=source.identity_data_id,
        seed=SEED_DATA_ID,
    )
    return {
        label: await stamped(data_id, source.dataset_id)
        for label, data_id in ids.items()
    }


async def reconcile(root, args, publisher, source):
    """Finish or verify doc01's saved revision (`reconcile_publication`)."""
    from .multisource import reconcile_publication

    await publisher.refuse_natively_deleted(source)
    await reconcile_publication(
        publisher, source, semantics=CapturedSemantics(), fault_stage=args.fault_stage
    )
