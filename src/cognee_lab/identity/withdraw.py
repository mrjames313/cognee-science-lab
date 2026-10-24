"""Selected generated-source retirement using native provenance deletion.

`forget` is the sibling orchestration; `retirement.py` holds what both use.
"""

from .erasure import refuse_unfinished_cascade
from .native import require_graph_methods
from .retirement import (
    contribution_triples,
    current_claims,
    owned_by,
    ownership_snapshot,
    released,
    retired_sources,
    verify_no_contributions,
    verify_survivors,
    withdraw_contributions,
)
from .stages import Operation, run_attempt, saved_row
from .validation import IntentError

STAGES = ("withdraw_contributions", "withdraw_owners", "withdraw_verification")
# Each stage injects its own fault, to keep the withdrawal's fault messages.
WITHDRAW = Operation("withdraw", "Withdrawal", (), "withdrawn")
FAULT_STAGES = STAGES


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
    row = await saved_row(
        records,
        source,
        "No saved publication to withdraw",
        "Withdraw the exact saved description",
    )
    refuse_unfinished_cascade(source, await records.rows())
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

    async def contributions(run):
        await withdraw_contributions(graph, source, contribution_triples(plan))
        run.inject(run.stage, "Injected failure after contribution withdrawal")

    async def owners(run):
        unified = UnifiedStoreEngine(
            graph, vector, EngineCapability.GRAPH | EngineCapability.VECTOR
        )
        deleted = await unified.delete_by_source_ref(owner)
        run.inject(run.stage, "Injected failure after native owner removal")
        return deleted

    async def verification(run):
        rows = await records.rows()
        retired = retired_sources(rows)
        if await graph.find_nodes_by_source_ref(
            owner
        ) or await graph.find_edges_by_source_ref(owner):
            raise IntentError(
                "verify_owner", "Retired generated source still owns graph objects"
            )
        await verify_no_contributions(graph, source, contribution_triples(plan))
        await verify_survivors(
            graph,
            vector,
            source,
            plan,
            released(owned_by(source, document=False), retired),
            retired,
            current_claims(rows),
        )
        run.inject(run.stage, "Injected failure before withdrawal acknowledgement")

    attempt, results = await run_attempt(
        WITHDRAW,
        records,
        source,
        plan,
        zip(STAGES, (contributions, owners, verification), strict=True),
        expected_revision=expected_revision,
        origin=origin,
        fault_stage=fault_stage,
    )
    return dict(
        attempt_id=attempt,
        state="withdrawn",
        deleted_node_ids=results["withdraw_owners"].deleted_node_ids,
    )
