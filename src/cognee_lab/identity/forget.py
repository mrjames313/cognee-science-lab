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
    removed_entities,
    retired_sources,
    verify_survivors,
    withdraw_contributions,
)
from .storage import FORGET_STATE, FORGOTTEN_SOURCE, STALE_REVISION
from .validation import IntentError

STAGES = (
    "forget_contributions",
    "forget_identity",
    "forget_document",
    "forget_verification",
)
# A fault after Cognee committed the Data delete and before it swept the
# item's evidence rows and stored files, as a process that dies there leaves
# them. The event records the stage the item was in.
COMMITTED_FAULTS = {
    "forget_identity_committed": "forget_identity",
    "forget_document_committed": "forget_document",
}
FAULT_STAGES = (*STAGES, *COMMITTED_FAULTS)


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


async def stored_files(data_ids):
    """The raw and original file locations of Data items, by item."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data

    files = {}
    async with get_relational_engine().get_async_session() as session:
        for data_id in data_ids:
            data = await session.get(Data, UUID(str(data_id)))
            files[str(data_id)] = sorted(
                {
                    location
                    for location in (
                        (data.raw_data_location, data.original_data_location)
                        if data
                        else ()
                    )
                    if location
                }
            )
    return files


async def stored_file_present(location):
    """Whether a stored file that Cognee manages, one under the data root,
    still exists. A location outside the data root is the user's own file."""
    from urllib.parse import unquote
    from cognee.infrastructure.files.storage import get_file_storage, get_storage_config

    data_root = get_storage_config()["data_root_directory"]
    if data_root not in location:
        return False
    relative = unquote(location.split(data_root, 1)[1].lstrip("/\\"))
    return await get_file_storage(data_root).file_exists(relative)


async def sweep(dataset_id, data_id, locations):
    """Remove what Cognee's Data delete sweeps after its commit: the item's
    edge evidence rows and its stored files, once nothing references them.
    Idempotent, so a retry after a death between the commit and the sweep
    converges."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.provenance.edge_evidence.cleanup import delete_edge_evidence

    await delete_edge_evidence(dataset_id, UUID(str(data_id)))
    engine = get_relational_engine()
    for location in locations:
        await engine.remove_data_file_if_unreferenced(location)


def dying_after_commit(stage, fault_stage):
    """A context that makes the native forget of this stage's item fail right
    after Cognee committed the Data delete, when the fault stage asks for it."""
    from contextlib import nullcontext
    from unittest.mock import patch

    if COMMITTED_FAULTS.get(fault_stage) != stage:
        return nullcontext()

    async def die(*_):
        raise IntentError(
            "injected_failure",
            f"Injected failure after the Data delete commit at {stage}",
        )

    return patch(
        "cognee.modules.provenance.edge_evidence.cleanup.delete_edge_evidence", die
    )


async def forget_plan(publisher, source):
    """Everything the source owns, recorded before any destructive write."""
    from .publish import identity_edges

    graph = publisher.graph
    doc = source.inputs[source.original_input_ref]
    node_ids, edge_ids = await owned_objects(graph, source)
    return dict(
        operation="identity_forget",
        revision=source.revision,
        runtime_profile=publisher.runtime_profile,
        original_data_id=str(doc.data_id),
        stored_files=await stored_files([doc.data_id, source.identity_data_id]),
        chunk_ids=sorted(
            str(i.chunk_id) for i in source.inputs.values() if isinstance(i, ChunkInput)
        ),
        identity_edges=[list(e[:3]) for e in identity_edges(source)],
        **ownership_snapshot(
            await graph.get_node_delete_data(node_ids),
            await graph.get_edge_delete_data(edge_ids),
        ),
    )


def refuse_dependents(source, plan, rows):
    """Refuse while a saved source consumed this document or an Entity the
    forget removes. Returns the removed Entities."""
    removed = removed_entities(source, plan, rows)
    found = dependents(source, rows, removed)
    if found:
        raise IntentError(
            "dependent_source",
            "Another saved identity source consumed this document or an Entity only it owns; reconsider the dependents first",
            details=dict(dependents=found),
        )
    return removed


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
        stored_files_present=[
            location
            for locations in plan["stored_files"].values()
            for location in locations
            if await stored_file_present(location)
        ],
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
        raise IntentError("stale_revision", STALE_REVISION)
    retry = (
        row["state"] == "failed" and row["plan"].get("operation") == "identity_forget"
    )
    if retry:
        # The saved plan keeps the ownership the first attempt found, which
        # native deletion has since detached or removed.
        plan = dict(row["plan"])
        if "stored_files" not in plan:
            raise IntentError(
                "recovery_plan",
                "Failed forget plan predates stored_files; its sweep cannot be finished",
            )
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
        # Repeat under the writer reservation: a consumer may have published
        # between the check above and begin.
        refuse_dependents(source, plan, await records.rows())
        await withdraw_contributions(graph, source, contribution_triples(plan))
        injected(stage)
        user = await get_default_user()
        doc = source.inputs[source.original_input_ref]
        # Native deletion of a Data item removes every graph and vector object
        # that only its refs own, then its Data row, stored files and evidence
        # rows. On a missing item it finds nothing to delete and sweeps
        # nothing, so the sweep runs here too and a retry converges.
        for stage, data_id in (
            (identity_stage, source.identity_data_id),
            (document_stage, doc.data_id),
        ):
            with dying_after_commit(stage, fault_stage):
                await native_forget(
                    data_id=data_id, dataset_id=source.dataset_id, user=user
                )
            await sweep(source.dataset_id, data_id, plan["stored_files"][str(data_id)])
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
