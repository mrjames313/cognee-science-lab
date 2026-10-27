"""Real Cognee storage, captured decisions, synthetic original documents only."""

import json
from pathlib import Path
from typing import NamedTuple
from uuid import NAMESPACE_URL, UUID, uuid5

from .environment import DATASET_NAME, read_embedding
from .forget_fixture import CALLER_FILES, semantics_for
from .models import IdentitySource
from .publish import Publisher
from .registered import context_for
from .retrieve import retrieve
from .settled import SearchRequest, retrieve_settled
from .validation import IntentError

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/identity"
SEED_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:seed-document")
OSCILLATIONS_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:oscillations")


class FactTarget(NamedTuple):
    """The Entity a fact points at, as it is created when missing."""

    id: UUID
    name: str
    description: str


OSCILLATIONS = FactTarget(OSCILLATIONS_ID, "oscillations", "Plasma oscillations.")


class ChunkFact(NamedTuple):
    """A fact one chunk of the original owns: `subject_id` -`relation`->
    `target`, with its text."""

    subject_id: UUID
    target: FactTarget
    relation: str
    text: str


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
            await write_chunk_facts(
                publisher,
                source,
                chunk,
                ctx,
                [ChunkFact(group.entity_id, OSCILLATIONS, "limits", text)],
            )
    await flush_context_provenance(ctx)


async def write_chunk_facts(publisher, source, chunk, ctx, facts):
    """Write `facts` (ChunkFacts) owned by `chunk` of the original, with their
    native evidence, in one write per kind: Ladybug grows with each write
    transaction until it checkpoints. A missing target Entity is created."""
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
    from cognee.modules.engine.models import Entity
    from cognee.modules.graph.utils import ensure_default_edge_properties
    from cognee.modules.provenance.edge_evidence.capture import capture_graph_provenance
    from cognee.tasks.storage.index_data_points import index_data_points
    from cognee.tasks.storage.index_graph_edges import index_graph_edges

    ref = make_chunk_source_ref_key(source.dataset_id, ctx.data_item.id, chunk.id)
    targets = {str(f.target.id): f.target for f in facts}
    subjects = list(dict.fromkeys(str(f.subject_id) for f in facts))
    created, reused = [], []
    for target_id, target in targets.items():
        node = await publisher.graph.get_node(target_id)
        if node is None:
            created.append(
                Entity(id=target.id, name=target.name, description=target.description)
            )
        elif node.get("type") != "Entity":
            raise IntentError("incompatible_type", "Fact endpoint is not an Entity")
        else:
            reused.append(target_id)
    if created:
        await publisher.graph.add_nodes(created, source_ref_key=ref)
        await index_data_points(created, vector_engine=publisher.vector)
    if reused:
        # Reusing an endpoint must retain it for this original chunk too.
        # Owning the incident fact alone does not protect the endpoint from
        # another document's removal and the resulting cascade.
        await publisher.graph.attach_node_source_refs(reused, [ref])
    await publisher.graph.attach_node_source_refs(subjects, [ref])
    edges = ensure_default_edge_properties(
        [
            (str(f.subject_id), str(f.target.id), f.relation, {"edge_text": f.text})
            for f in facts
        ]
    )
    await publisher.graph.add_edges(edges, source_ref_key=ref)
    await index_graph_edges(edges, vector_engine=publisher.vector)
    contained = ensure_default_edge_properties(
        [
            (str(chunk.id), endpoint, "contains", {})
            for endpoint in dict.fromkeys(
                e for f in facts for e in (str(f.subject_id), str(f.target.id))
            )
        ]
    )
    await publisher.graph.add_edges(contained, source_ref_key=ref)
    # Use native per-chunk production/evidence buffering, including exact IDs.
    chunk._produced_edge_identities = [(e[0], e[1], e[2]) for e in edges]
    chunk._provenance_edges = edges
    await capture_graph_provenance([chunk], [*edges, *contained], ctx)


async def verify_semantics(publisher, source, chunks, ctx):
    from .captured_chunks import captured_facts, retired_facts

    for key, text in (*captured_facts(source), *retired_facts(source)):
        await verify_fact(publisher, source, chunks, ctx, group_key=key, fact_text=text)


async def verify_fact(publisher, source, chunks, ctx, *, group_key, fact_text):
    from .captured_chunks import fact_chunks, fixture_mention_id

    await check_fact_edge(
        publisher,
        source,
        ctx,
        subject_id=fixture_mention_id(source, group_key),
        target_id=OSCILLATIONS_ID,
        relation="limits",
        expected=fact_chunks(source, chunks, group_key=group_key, fact_text=fact_text),
    )
    await check_chunk_vectors(publisher, chunks)


async def check_fact_edge(
    publisher, source, ctx, *, subject_id, target_id, relation, expected
):
    """The fact edge is owned by exactly the `expected` chunks of the
    original, each with its native evidence row; with no expected chunk, the
    edge is gone."""
    from cognee.infrastructure.databases.provenance import (
        EdgeIdentity,
        make_chunk_source_ref_key,
        parse_source_ref_key,
    )
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records

    identity = EdgeIdentity(str(subject_id), str(target_id), relation)
    metadata = (await publisher.graph.get_edge_delete_data([identity])).get(identity)
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
    eid = UUID(generate_edge_object_id(str(subject_id), str(target_id), relation))
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


async def check_chunk_vectors(publisher, chunks):
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


async def seed_corpus(root):
    """Register the seed document, stamped, with the Entity doc01 borrows,
    and return the publisher of the root's stores. Every creation command
    starts here."""
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points

    from .registered import stamp

    if cognee.__version__ != "1.6.2":
        raise IntentError(
            "unsupported_version", "Fixtures require inspected Cognee 1.6.2"
        )
    (root / "seed.txt").write_text("Helios controller regulates plasma heating.\n")
    await cognee.add(
        DataItem(data=str(root / "seed.txt"), data_id=SEED_DATA_ID),
        dataset_name=DATASET_NAME,
        skip_connection_test=True,
    )
    seed = await context_for(SEED_DATA_ID)
    await stamp(SEED_DATA_ID, seed.dataset.id)
    entity = borrowed_entity(doc01_template())
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


async def add_doc01(root, *, chunk_budget=512, source_text=None, **options):
    """Register doc01's original (the fixture text or `source_text`) and its
    captured description (`describe_doc01` with `options`) through the
    lab's `add`, and return the description. The describer also writes the
    root's fixture-info.json, so a failed publication leaves it too."""
    from . import entry

    files = CALLER_FILES["doc01"]
    template = doc01_template(source_text)
    original = entry.Original(
        root / files.text, UUID(template["inputs"]["doc01"]["data_id"])
    )
    original.path.write_text(
        source_text
        if source_text is not None
        else (FIXTURES / "source.txt").read_text()
    )

    def describe(draft):
        source = describe_doc01(
            template, draft.dataset_id, draft.text, draft.chunks, **options
        )
        write_info(root, source)
        return source

    return await entry.add(
        DATASET_NAME,
        original,
        describe=describe,
        identity_path=root / files.identity,
        chunk_budget=chunk_budget,
    )


async def create(root, args):
    """The doc01 root: the seed corpus, then doc01 added and published in
    Cognee's cognify pipeline. The CLI closes the publisher's stores."""
    from . import entry

    publisher = await seed_corpus(root)
    args._fixture_publisher = publisher
    done = await entry.remember_in_order(
        publisher,
        {"doc01": lambda _: add_doc01(root)},
        semantics=semantics_for,
        fault=("doc01", args.fault_stage),
        origin="test",
    )
    return done["doc01"]


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
        return await retrieve_settled(
            publisher,
            dataset_id,
            args.query,
            SearchRequest.parse(args.scope, args.mode),
        )
    if args.command == "search":
        from .search import searched

        return await searched(
            dataset_id,
            args.query,
            SearchRequest.parse(args.scope, args.mode),
            all_datasets=args.all_datasets,
        )
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
        publisher,
        source,
        semantics=semantics_for("doc01"),
        fault_stage=args.fault_stage,
    )
