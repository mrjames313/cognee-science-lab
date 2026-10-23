"""Selected generated-source retirement using native provenance deletion.

`forget` is the sibling orchestration; `retirement.py` holds what both use.
"""

from .models import IdentitySource
from .native import require_graph_methods
from .retirement import (
    contribution_triples,
    owned_by,
    ownership_snapshot,
    released,
    retired_sources,
    verify_no_contributions,
    verify_survivors,
    withdraw_contributions,
)
from .validation import IntentError


async def withdraw(
    publisher, source, *, expected_revision, origin="runtime", fault_stage=None
):
    from cognee.infrastructure.databases.provenance import make_source_ref_key
    from cognee.infrastructure.databases.unified.capabilities import EngineCapability
    from cognee.infrastructure.databases.unified.unified_store_engine import (
        UnifiedStoreEngine,
    )
    from .publish import identity_edges

    graph, vector, records = publisher.graph, publisher.vector, publisher.records
    require_graph_methods(
        graph,
        [
            "find_nodes_by_source_ref",
            "find_edges_by_source_ref",
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
        raise IntentError("source_missing", "No saved publication to withdraw")
    if IdentitySource.model_validate_json(row.description) != source:
        raise IntentError("revision_reuse", "Withdraw the exact saved description")
    owner = make_source_ref_key(source.dataset_id, source.identity_data_id)
    # Keep the original retirement keys across interrupted retries, even after
    # native deletion has detached references or removed graph objects.
    if row.state != "withdrawn" and row.operation == "identity_withdraw":
        plan = dict(row.plan)
    else:
        nodes = await graph.get_node_delete_data(
            await graph.find_nodes_by_source_ref(owner)
        )
        edges = await graph.get_edge_delete_data(
            await graph.find_edges_by_source_ref(owner)
        )
        plan = dict(
            operation="identity_withdraw",
            revision=source.revision,
            runtime_profile=publisher.runtime_profile,
            identity_edges=[list(e[:3]) for e in identity_edges(source)],
            **ownership_snapshot(nodes, edges),
        )
    attempt = await records.begin(
        source,
        expected_revision=expected_revision,
        plan=plan,
        method="withdraw",
        origin=origin,
    )
    stage = "withdraw_contributions"
    try:
        triples = contribution_triples(plan)
        await withdraw_contributions(graph, source, triples)
        if fault_stage == stage:
            raise IntentError(
                "injected_failure", "Injected failure after contribution withdrawal"
            )
        stage = "withdraw_owners"
        unified = UnifiedStoreEngine(
            graph, vector, EngineCapability.GRAPH | EngineCapability.VECTOR
        )
        deleted = await unified.delete_by_source_ref(owner)
        if fault_stage == stage:
            raise IntentError(
                "injected_failure", "Injected failure after native owner removal"
            )
        stage = "withdraw_verification"
        retired = retired_sources(await records.rows())
        if await graph.find_nodes_by_source_ref(
            owner
        ) or await graph.find_edges_by_source_ref(owner):
            raise IntentError(
                "verify_owner", "Retired generated source still owns graph objects"
            )
        await verify_no_contributions(graph, source, triples)
        await verify_survivors(
            graph,
            vector,
            source,
            plan,
            released(owned_by(source, document=False), retired),
            retired,
        )
        if fault_stage == stage:
            raise IntentError(
                "injected_failure", "Injected failure before withdrawal acknowledgement"
            )
        await records.complete(source, attempt, state="withdrawn")
        return dict(
            attempt_id=attempt,
            state="withdrawn",
            deleted_node_ids=deleted.deleted_node_ids,
        )
    except Exception as exc:
        try:
            event = await records.fail(source, attempt, stage, exc, origin=origin)
        except Exception as diagnostic_error:
            raise IntentError(
                "recovery_record_failed",
                f"Withdrawal unavailable: attempt={attempt}, stage={stage}, error={exc}; "
                f"recovery-event write also failed: {diagnostic_error}",
            ) from diagnostic_error
        raise IntentError(
            "recovery_required", f"{exc}; recovery_event_id={event}"
        ) from exc
