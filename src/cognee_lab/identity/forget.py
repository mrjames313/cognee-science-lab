"""Forget a source: erase it, then remove what other sources based on it.

Forget removes the original document and the generated identity source through
Cognee's native document deletion, and everything only they owned: chunks and
their vectors, the document node, markers, the facts and evidence the chunks
produced, the mention Entities, the identity edges and contributions, and the
Entities only this source declared. An Entity or edge another source owns
survives with that source's refs and contributions. The ledger row ends as
`forgotten` with a tombstone that keeps identifiers only, so a re-add
continues at the next revision and never derives a retired UUID again.

A forget that changes another source's decisions needs the caller's
confirmation: the token of its impact (`erasure.py`). After the source is
erased, each dependent gets a removal revision of its own. Any source can be
forgotten: current, withdrawn, or one whose publication failed. `withdraw`
is the sibling orchestration; `retirement.py` holds what both use.
"""

from uuid import UUID

from .models import ChunkInput, Tombstone
from .native import require_graph_methods
from .retirement import (
    contribution_triples,
    current_claims,
    has_contribution,
    owned_by,
    ownership_snapshot,
    released,
    retired_sources,
    source_ids,
    verify_survivors,
    withdraw_contributions,
)
from .stages import Operation, run_attempt, saved_row
from .storage import FORGET_STATE, FORGOTTEN_SOURCE, STALE_REVISION, now
from .validation import IntentError

STAGES = (
    "forget_impact",
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
# Faults in the dependents' removal revisions, after the forget completed
# (erasure.finish_dependents). The first stops before the first revision
# begins, as a process that dies there leaves them; the second fails each
# removal revision, as REFRESH_FAULT does for a refresh; the third fails
# each one below level 1, once level 1 is written.
DEPENDENT_FAULTS = (
    "forget_dependents",
    "forget_dependent_revision",
    "forget_cascade_revision",
)
IMPACT_CHANGED = (
    "impact_changed",
    "The impact changed since the token was issued; rerun the dry run and confirm its token",
)
FORGET = Operation("forget", "Forget", STAGES, "forgotten")
FAULT_STAGES = (*STAGES, *COMMITTED_FAULTS, *DEPENDENT_FAULTS)


def split_fault(stage):
    """A fault stage as (the forget's own, the dependents'): at most one is
    set."""
    return (None, stage) if stage in DEPENDENT_FAULTS else (stage, None)


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


async def stored_file_present(location, data_ids):
    """Whether a stored file that Cognee manages, one under the data root,
    still exists and no Data row but `data_ids` references it. A location
    outside the data root is the user's own file. Cognee stores a file under a
    content address, so another item with the same bytes shares it, and
    `remove_data_file_if_unreferenced` keeps it for that item."""
    from urllib.parse import unquote
    from sqlalchemy import func, or_, select
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.infrastructure.files.storage import get_file_storage, get_storage_config
    from cognee.modules.data.models import Data

    data_root = get_storage_config()["data_root_directory"]
    if data_root not in location:
        return False
    async with get_relational_engine().get_async_session() as session:
        others = (
            await session.execute(
                select(func.count())
                .select_from(Data)
                .where(
                    or_(
                        Data.raw_data_location == location,
                        Data.original_data_location == location,
                    ),
                    Data.id.notin_([UUID(str(i)) for i in data_ids]),
                )
            )
        ).scalar()
    if others:
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
    empty or zero once the forget is complete. `source` is its description
    or, once forgotten, its tombstone."""
    graph, vector = publisher.graph, publisher.vector
    ids = source_ids(source)
    nodes, edges = await owned_objects(graph, ids)
    return dict(
        original_data_present=await data_present(ids.original_data_id, ids.dataset_id),
        identity_data_present=await data_present(ids.identity_data_id, ids.dataset_id),
        stored_files_present=[
            location
            for locations in plan["stored_files"].values()
            for location in locations
            if await stored_file_present(location, plan["stored_files"])
        ],
        document_node_present=await graph.get_node(str(ids.original_data_id))
        is not None,
        chunks_present=[
            c for c in plan["chunk_ids"] if await graph.get_node(c) is not None
        ],
        chunk_vectors_present=[
            c
            for c in plan["chunk_ids"]
            if await vector.retrieve("DocumentChunk_text", [c])
        ],
        evidence_rows=await evidence_rows(ids.dataset_id, ids.original_data_id),
        identity_contribution_present=await has_contribution(
            graph, ids, contribution_triples(plan)
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
    rows = await publisher.records.rows()
    retired = retired_sources(rows)
    await verify_survivors(
        publisher.graph,
        publisher.vector,
        source,
        plan,
        released(owned_by(source, document=True), retired),
        retired,
        current_claims(rows),
    )


async def clear_withholdings(publisher, source):
    """Delete the withholding rows this source holds as a dependent, and the
    rows its own edits wrote for other sources: their input is gone."""
    sid = str(source.identity_data_id)
    table = await publisher.withholdings.rows(source.dataset_id)
    await publisher.withholdings.replace(
        [
            (w.dataset, w.source, w.input_ref)
            for w in table
            if sid in (w.source, w.consumed)
        ],
        [],
    )


def resumes(row):
    """Whether forget resumes this row's failed forget. Refuses, earlier than
    begin(), a row forget neither begins nor resumes: a pending one, or a
    failed replacement or withdrawal, which only its own method resumes.
    begin() refuses the same rows under the reservation."""
    retry = row.resumed_by == "forget"
    fresh = row.state in ("current", "withdrawn") or (
        row.state == "failed" and row.resumed_by is None
    )
    if not (retry or fresh):
        raise IntentError(*FORGET_STATE)
    return retry


async def plan_for(publisher, source, row):
    """A failed forget's saved plan, which keeps the ownership the first
    attempt found before native deletion detached or removed it; otherwise a
    new plan from the graph."""
    if not resumes(row):
        return await forget_plan(publisher, source)
    plan = dict(row.plan)
    if "stored_files" not in plan:
        raise IntentError(
            "recovery_plan",
            "Failed forget plan predates stored_files; its sweep cannot be finished",
        )
    return plan


async def preview(publisher, source, *, expected_revision):
    """The dry run: what `forget` would do, with the token it would need.
    Writes nothing. On a forgotten source, the dependents it has not revised
    yet."""
    from .erasure import impact, report, unfinished

    records = publisher.records
    row = await saved_row(records, source, "No saved publication to forget")
    if row.revision != expected_revision:
        raise IntentError(*STALE_REVISION)
    rows = await records.rows()
    if row.tombstone is not None:
        return dict(
            dry_run=True,
            forgotten=True,
            unfinished=[r.source for r in unfinished(row.tombstone, rows)],
        )
    description = row.description
    plan = await plan_for(publisher, description, row)
    found = impact(description, plan, rows)
    return report(
        found,
        plan=plan,
        description=description,
        events=await records.events(description.dataset_id),
    )


def confirmed(found, plan, confirm, retry):
    """The forget may proceed: it affects no other source and no token was
    given, or the given token is this impact's. A retry without a token
    keeps the impact its first attempt confirmed."""
    if confirm is None and not found.dependents:
        return True
    if confirm is None and retry:
        return plan.get("impact_token") == found.token
    return confirm == found.token


async def forget(
    publisher,
    source,
    *,
    expected_revision,
    confirm=None,
    origin="runtime",
    fault_stage=None,
):
    """Erase the source under one reservation, then write each dependent's
    removal revision under its own (`erasure.finish_dependents`, which a
    stage in DEPENDENT_FAULTS fails). On a forgotten source, finish
    the dependents a completed forget did not revise; refuse when none is
    left. Returns the attempt and the dependents' outcome; a dependent
    failure is reported beside the completed forget, not raised."""
    from cognee import forget as native_forget
    from cognee.modules.users.methods import get_default_user

    from .erasure import (
        finish_dependents,
        impact,
        refuse_unfinished_cascade,
        report,
        unfinished,
    )

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
    row = await saved_row(
        records,
        source,
        "No saved publication to forget",
        "Forget the exact saved description",
    )
    if row.revision != expected_revision:
        raise IntentError(*STALE_REVISION)
    fault_stage, dependents_fault = split_fault(fault_stage)
    if row.tombstone is not None:
        rows = await records.rows()
        if not unfinished(row.tombstone, rows):
            raise IntentError(*FORGOTTEN_SOURCE)
        removal = await finish_dependents(
            publisher, row.tombstone, rows, dependents_fault
        )
        return dict(attempt_id=None, state="forgotten", **removal)
    retry = resumes(row)
    plan = await plan_for(publisher, source, row)
    rows = await records.rows()
    refuse_unfinished_cascade(source, rows)
    found = impact(source, plan, rows)
    if not confirmed(found, plan, confirm, retry):
        code, message = (
            (
                "confirmation_required",
                "This forget removes other sources' decisions; review the report and rerun with --confirm <token>",
            )
            if confirm is None
            else IMPACT_CHANGED
        )
        raise IntentError(
            code,
            message,
            details=report(
                found,
                plan=plan,
                description=source,
                events=await records.events(source.dataset_id),
            ),
        )
    plan.update(
        impact_token=found.token,
        dependents=[d.identity_data_id for d in found.dependents],
    )
    user = None

    async def check_impact(_):
        # Again under the writer reservation, from the saved plan: a source
        # may have published or changed between the check above and begin.
        nonlocal found
        rows = await records.rows()
        found = impact(source, plan, rows)
        if found.token != plan["impact_token"]:
            raise IntentError(*IMPACT_CHANGED)

    async def contributions(_):
        nonlocal user
        await withdraw_contributions(graph, source, contribution_triples(plan))
        await clear_withholdings(publisher, source)
        user = await get_default_user()

    # Native deletion of a Data item removes every graph and vector object
    # that only its refs own, then its Data row, stored files and evidence
    # rows. On a missing item it finds nothing to delete and sweeps nothing,
    # so the sweep runs here too and a retry converges.
    def native_delete(data_id):
        async def stage(run):
            with dying_after_commit(run.stage, fault_stage):
                await native_forget(
                    data_id=data_id, dataset_id=source.dataset_id, user=user
                )
            await sweep(source.dataset_id, data_id, plan["stored_files"][str(data_id)])

        return stage

    tombstone = None

    async def verification(run):
        nonlocal tombstone
        await verify_forgotten(publisher, source, plan)
        tombstone = Tombstone.of(
            source,
            forgotten_at=now(),
            removed_entity_ids=[UUID(e) for e in found.removed_entities],
            impact_token=found.token if found.dependents else None,
            earlier=(await records.row(source)).last_tombstone,
        )
        run.completion = dict(tombstone=tombstone)

    ids = source_ids(source)
    attempt, _ = await run_attempt(
        FORGET,
        records,
        source,
        plan,
        zip(
            STAGES,
            (
                check_impact,
                contributions,
                native_delete(ids.identity_data_id),
                native_delete(ids.original_data_id),
                verification,
            ),
            strict=True,
        ),
        expected_revision=expected_revision,
        origin=origin,
        fault_stage=fault_stage,
    )
    removal = await finish_dependents(
        publisher, tombstone, await records.rows(), dependents_fault
    )
    return dict(attempt_id=attempt, state="forgotten", **removal)
