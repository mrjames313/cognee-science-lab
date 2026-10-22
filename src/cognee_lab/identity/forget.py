"""Forget a source that nothing depends on.

Forget removes the original document and the generated identity source through
Cognee's native document deletion, and everything only they owned: chunks and
their vectors, the document node, markers, the facts and evidence the chunks
produced, the mention Entities, the identity edges and contributions, and the
Entities only this source declared. An Entity or edge another source owns
survives with that source's refs and contributions. The ledger row ends as
`forgotten` at its last revision, so a re-add continues at the next revision.
"""

from uuid import UUID

from .models import IdentitySource
from .native import require_graph_methods
from .storage import FORGOTTEN_SOURCE
from .validation import IntentError, dependents
from .withdraw import (
    contribution_triples,
    ownership_snapshot,
    retired_sources,
    verify_no_contributions,
    verify_survivors,
    withdraw_contributions,
)

STAGES = (
    "forget_contributions",
    "forget_identity",
    "forget_document",
    "forget_verification",
)


def owned_by(source):
    """Whether a source ref belongs to this source: its identity source, or
    its document and the document's chunks."""
    from cognee.infrastructure.databases.provenance import parse_source_ref_key

    doc = source.inputs[source.original_input_ref]
    own = {source.identity_data_id, doc.data_id}

    def own_ref(ref):
        try:
            parsed = parse_source_ref_key(ref)
        except ValueError:
            return False
        return parsed.dataset_id == source.dataset_id and parsed.data_id in own

    return own_ref


async def forget_plan(publisher, source):
    """Everything the source owns, recorded before any destructive write."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data
    from .models import ChunkInput
    from .publish import identity_edges

    graph = publisher.graph
    own_ref = owned_by(source)
    dataset = str(source.dataset_id)
    doc = source.inputs[source.original_input_ref]
    node_ids = [
        node_id
        for node_id, refs in (
            await graph.find_node_source_refs_by_dataset(dataset)
        ).items()
        if any(own_ref(r) for r in refs)
    ]
    edge_ids = [
        edge
        for edge, refs in (
            await graph.find_edge_source_refs_by_dataset(dataset)
        ).items()
        if any(own_ref(r) for r in refs)
    ]
    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, doc.data_id)
    return dict(
        operation="identity_forget",
        revision=source.revision,
        runtime_profile=publisher.runtime_profile,
        original_data_id=str(doc.data_id),
        raw_data_location=data.raw_data_location if data else None,
        chunk_ids=sorted(
            str(i.chunk_id) for i in source.inputs.values() if isinstance(i, ChunkInput)
        ),
        identity_edges=[list(e[:3]) for e in identity_edges(source)],
        **ownership_snapshot(
            await graph.get_node_delete_data(node_ids),
            await graph.get_edge_delete_data(edge_ids),
        ),
    )


def sole_owned(source, plan):
    """The Entities whose every recorded owner is this source."""
    own_ref = owned_by(source)
    return {
        UUID(key)
        for key, node in plan["entities"].items()
        if node["type"] == "Entity" and all(own_ref(r) for r in node["refs"])
    }


def refuse_dependents(source, plan, rows):
    found = dependents(source, rows, sole_owned(source, plan))
    if found:
        raise IntentError(
            "dependent_source",
            "Another saved identity source consumed this document or an Entity only it owns; reconsider the dependents first",
            details=dict(dependents=found),
        )


async def data_present(data_id, dataset_id):
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data

    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, UUID(str(data_id)))
    return data is not None and data.dataset_id == dataset_id


async def evidence_rows(dataset_id, data_id):
    from sqlalchemy import func, select
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.provenance.edge_evidence.models import ProvenanceEdgeEvidence

    async with get_relational_engine().get_async_session() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(ProvenanceEdgeEvidence)
                .where(
                    ProvenanceEdgeEvidence.dataset_id == dataset_id,
                    ProvenanceEdgeEvidence.data_id == UUID(str(data_id)),
                )
            )
        ).scalar()


async def owned_objects(graph, source):
    """Graph nodes and edges that still carry one of this source's refs."""
    own_ref = owned_by(source)
    dataset = str(source.dataset_id)
    nodes = [
        n
        for n, refs in (await graph.find_node_source_refs_by_dataset(dataset)).items()
        if any(own_ref(r) for r in refs)
    ]
    edges = [
        e
        for e, refs in (await graph.find_edge_source_refs_by_dataset(dataset)).items()
        if any(own_ref(r) for r in refs)
    ]
    return nodes, edges


async def verify_forgotten(publisher, source, plan):
    """Nothing of the source remains, and every survivor keeps what it owes."""
    from cognee.infrastructure.databases.provenance import parse_source_ref_key

    graph, vector, records = publisher.graph, publisher.vector, publisher.records
    own_ref = owned_by(source)
    doc = source.inputs[source.original_input_ref]
    retired = retired_sources(await records.rows())

    def released(ref):
        parsed = parse_source_ref_key(ref)
        return own_ref(ref) or (str(parsed.dataset_id), str(parsed.data_id)) in retired

    nodes, edges = await owned_objects(graph, source)
    if nodes or edges:
        raise IntentError(
            "verify_owner", "Forgotten source or document still owns graph objects"
        )
    await verify_no_contributions(graph, source, contribution_triples(plan))
    await verify_survivors(graph, vector, source, plan, released, retired)
    for chunk_id in plan["chunk_ids"]:
        if await graph.get_node(chunk_id) is not None:
            raise IntentError("stale_chunk", "Forgotten chunk remains in graph")
        if await vector.retrieve("DocumentChunk_text", [chunk_id]):
            raise IntentError("stale_chunk", "Forgotten chunk remains in vector index")
    if await graph.get_node(str(doc.data_id)) is not None:
        raise IntentError("verify_withdrawal", "Forgotten document node remains")
    for data_id, what in (
        (doc.data_id, "Original"),
        (source.identity_data_id, "Identity"),
    ):
        if await data_present(data_id, source.dataset_id):
            raise IntentError("verify_withdrawal", f"{what} Data item was not removed")
    if await evidence_rows(source.dataset_id, doc.data_id):
        raise IntentError("verify_withdrawal", "Forgotten document evidence remains")


async def forget(
    publisher, source, *, expected_revision, origin="runtime", fault_stage=None
):
    from cognee import forget as native_forget
    from cognee.modules.users.methods import get_default_user

    graph, records = publisher.graph, publisher.records
    require_graph_methods(
        graph,
        [
            "find_node_source_refs_by_dataset",
            "find_edge_source_refs_by_dataset",
            "get_node_delete_data",
            "get_edge_delete_data",
            "remove_node_source_refs",
            "remove_edge_source_refs",
            "delete_edge_triples",
            "delete_nodes",
            "add_edges",
        ],
    )
    row = next(
        (
            r
            for r in await records.rows(source.dataset_id)
            if r["source"] == str(source.identity_data_id)
        ),
        None,
    )
    if row is None:
        raise IntentError("source_missing", "No saved publication to forget")
    if IdentitySource.model_validate_json(row["description"]) != source:
        raise IntentError("revision_reuse", "Forget the exact saved description")
    if row["revision"] != expected_revision:
        raise IntentError("stale_revision", "Saved revision changed")
    retry = (
        row["state"] == "failed" and row["plan"].get("operation") == "identity_forget"
    )
    if retry:
        # The saved plan keeps the ownership the first attempt found, which
        # native deletion has since detached or removed.
        plan = dict(row["plan"])
    else:
        if row["state"] == "forgotten":
            raise IntentError("forgotten_source", FORGOTTEN_SOURCE)
        if row["state"] != "current":
            raise IntentError(
                "forget_state", "Forget a current source, or retry its failed forget"
            )
        plan = await forget_plan(publisher, source)
    refuse_dependents(source, plan, await records.rows())
    attempt = await records.begin(
        source,
        expected_revision=expected_revision,
        plan=plan,
        method="forget",
        origin=origin,
    )
    stage = STAGES[0]

    def injected(name):
        if fault_stage == name:
            raise IntentError("injected_failure", f"Injected failure at {name}")

    try:
        await withdraw_contributions(graph, source, contribution_triples(plan))
        injected(stage)
        user = await get_default_user()
        doc = source.inputs[source.original_input_ref]
        # Native deletion of a Data item removes every graph and vector object
        # that only its refs own, then its Data row, stored file and evidence
        # rows. Both calls converge on a missing item, so a retry repeats them.
        stage = "forget_identity"
        await native_forget(
            data_id=source.identity_data_id, dataset_id=source.dataset_id, user=user
        )
        injected(stage)
        stage = "forget_document"
        await native_forget(
            data_id=doc.data_id, dataset_id=source.dataset_id, user=user
        )
        injected(stage)
        stage = "forget_verification"
        await verify_forgotten(publisher, source, plan)
        injected(stage)
        await records.complete(source, attempt, state="forgotten")
        return dict(attempt_id=attempt, state="forgotten")
    except Exception as exc:
        try:
            event = await records.fail(source, attempt, stage, exc, origin=origin)
        except Exception as diagnostic_error:
            raise IntentError(
                "recovery_record_failed",
                f"Forget unavailable: attempt={attempt}, stage={stage}, error={exc}; "
                f"recovery-event write also failed: {diagnostic_error}",
            ) from diagnostic_error
        raise IntentError(
            "recovery_required", f"{exc}; recovery_event_id={event}"
        ) from exc


async def admit_readd(graph, forgotten, source):
    """A re-add after forget publishes the same identity source and document
    at the next revision. Every group is fresh: its UUID derives from the new
    revision, repeats nothing the forgotten revision used, and is not in the
    graph. A new reusable Entity derives the same way."""
    from .admission import (
        GroupFate,
        check_absent_from_graph,
        check_derived_entity_ids,
        check_revision_scoped_ids,
        check_unused_entity_ids,
    )

    old_doc = forgotten.inputs[forgotten.original_input_ref]
    doc = source.inputs[source.original_input_ref]
    if (source.dataset_id, source.identity_data_id, doc.data_id) != (
        forgotten.dataset_id,
        forgotten.identity_data_id,
        old_doc.data_id,
    ):
        raise IntentError(
            "source_changed", "Re-add the forgotten identity source and its document"
        )
    if source.revision != forgotten.revision + 1:
        raise IntentError(
            "revision_sequence",
            "Re-add a forgotten source at exactly the next revision",
        )
    fresh = frozenset(source.mention_groups)
    check_unused_entity_ids(forgotten, source, fresh)
    check_revision_scoped_ids(forgotten, source, fresh)
    check_derived_entity_ids(forgotten, source)
    fate = GroupFate(frozenset(), frozenset(forgotten.mention_groups), fresh)
    await check_absent_from_graph(graph, forgotten, source, fate)
