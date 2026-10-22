"""Forget a source that nothing depends on.

Forget removes the original document and the generated identity source through
Cognee's native document deletion, and everything only they owned: chunks and
their vectors, the document node, markers, the facts and evidence the chunks
produced, the mention Entities, the identity edges and contributions, and the
Entities only this source declared. An Entity or edge another source owns
survives with that source's refs and contributions. The ledger row ends as
`forgotten` at its last revision, so a re-add continues at the next revision.
`withdraw` is the sibling orchestration; `retirement.py` holds what both use.
"""

from uuid import UUID

from .models import ChunkInput, IdentitySource
from .native import require_graph_methods
from .retirement import (
    contribution_triples,
    dependents,
    has_contribution,
    owned_by,
    ownership_snapshot,
    released,
    retired_sources,
    verify_survivors,
    withdraw_contributions,
)
from .storage import FORGET_STATE, FORGOTTEN_SOURCE
from .validation import IntentError

STAGES = (
    "forget_contributions",
    "forget_identity",
    "forget_document",
    "forget_verification",
)


async def owned_objects(graph, source):
    """Graph nodes and edges that carry one of this source's refs."""
    own_ref = owned_by(source, document=True)
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


async def forget_plan(publisher, source):
    """Everything the source owns, recorded before any destructive write."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data
    from .publish import identity_edges

    graph = publisher.graph
    doc = source.inputs[source.original_input_ref]
    node_ids, edge_ids = await owned_objects(graph, source)
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
    own_ref = owned_by(source, document=True)
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


async def remains(publisher, source, plan):
    """What is left of a source whose forget began. Every value is false,
    empty or zero once the forget is complete."""
    graph, vector = publisher.graph, publisher.vector
    doc = source.inputs[source.original_input_ref]
    nodes, edges = await owned_objects(graph, source)
    return dict(
        original_data_present=await data_present(doc.data_id, source.dataset_id),
        identity_data_present=await data_present(
            source.identity_data_id, source.dataset_id
        ),
        document_node_present=await graph.get_node(str(doc.data_id)) is not None,
        chunks_present=[
            c for c in plan["chunk_ids"] if await graph.get_node(c) is not None
        ],
        chunk_vectors_present=[
            c
            for c in plan["chunk_ids"]
            if await vector.retrieve("DocumentChunk_text", [c])
        ],
        evidence_rows=await evidence_rows(source.dataset_id, doc.data_id),
        identity_contribution_present=await has_contribution(
            graph, source, contribution_triples(plan)
        ),
        owned_nodes=len(nodes),
        owned_edges=len(edges),
    )


async def verify_forgotten(publisher, source, plan):
    """Nothing of the source remains, and every survivor keeps what it owes."""
    left = [k for k, v in (await remains(publisher, source, plan)).items() if v]
    if left:
        raise IntentError(
            "forget_incomplete", "Forgotten source leaves " + ", ".join(left)
        )
    retired = retired_sources(await publisher.records.rows())
    await verify_survivors(
        publisher.graph,
        publisher.vector,
        source,
        plan,
        released(owned_by(source, document=True), retired),
        retired,
    )


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
    row = await records.row(source)
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
            raise IntentError("forget_state", FORGET_STATE)
        plan = await forget_plan(publisher, source)
    refuse_dependents(source, plan, await records.rows())
    attempt = await records.begin(
        source,
        expected_revision=expected_revision,
        plan=plan,
        method="forget",
        origin=origin,
    )
    contributions_stage, identity_stage, document_stage, verification_stage = STAGES
    stage = contributions_stage

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
        stage = identity_stage
        await native_forget(
            data_id=source.identity_data_id, dataset_id=source.dataset_id, user=user
        )
        injected(stage)
        stage = document_stage
        await native_forget(
            data_id=doc.data_id, dataset_id=source.dataset_id, user=user
        )
        injected(stage)
        stage = verification_stage
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
    from .storage import READD_REVISION

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
        raise IntentError("revision_sequence", READD_REVISION)
    fresh = frozenset(source.mention_groups)
    check_unused_entity_ids(forgotten, source, fresh)
    check_revision_scoped_ids(forgotten, source, fresh)
    check_derived_entity_ids(forgotten, source)
    fate = GroupFate(frozenset(), frozenset(forgotten.mention_groups), fresh)
    await check_absent_from_graph(graph, forgotten, source, fate)
