"""Selected generated-source retirement using native provenance deletion.

`forget` reuses the ownership snapshot, the contribution withdrawal and the
survivor checks defined here, with a wider set of released refs.
"""

from .models import IdentitySource
from .native import edge_metadata, require_graph_methods
from .validation import IntentError


def ownership_snapshot(nodes, edges):
    """The refs, types, indexed fields and properties of owned graph objects,
    as a plan records them before any destructive write."""
    return dict(
        entities={
            key: dict(
                refs=value.source_ref_keys,
                type=value.node_type,
                indexed_fields=value.indexed_fields,
            )
            for key, value in nodes.items()
        },
        edges=[
            dict(
                source=e.source_id,
                target=e.target_id,
                relation=e.relationship_name,
                refs=data.source_ref_keys,
                properties=data.edge_properties,
            )
            for e, data in edges.items()
        ],
    )


def contribution_triples(plan):
    """The identity edges a plan's source contributed to."""
    triples = {tuple(e) for e in plan["identity_edges"]}
    triples.update(
        (e["source"], e["target"], e["relation"])
        for e in plan["edges"]
        if "identity_contributions" in e["properties"]
    )
    return triples


def is_own(source, contribution):
    return (contribution.get("dataset_id"), contribution.get("identity_data_id")) == (
        str(source.dataset_id),
        str(source.identity_data_id),
    )


async def withdraw_contributions(graph, source, triples):
    """Drop this source's contribution payloads from shared identity edges,
    keeping every other owner's payload and native ownership."""
    from cognee.infrastructure.databases.provenance import make_source_ref_key
    from .publish import contributions
    from .storage import encode

    for a, b, relation in sorted(triples):
        edge = await edge_metadata(graph, a, b, relation)
        if edge is None:
            continue
        previous = contributions(edge.edge_properties)
        kept = [c for c in previous if not is_own(source, c)]
        for c in kept:
            ref = make_source_ref_key(c["dataset_id"], c["identity_data_id"])
            if ref not in edge.source_ref_keys:
                raise IntentError(
                    "foreign_owner_missing",
                    "Surviving identity contribution has no native owner",
                )
        if kept != previous:
            props = dict(edge.edge_properties, identity_contributions=encode(kept))
            # Existing edge only: retain native owners and all other fields.
            await graph.add_edges([(a, b, relation, props)])


def retired_sources(rows):
    """(dataset, data id) pairs whose survival is no longer an obligation: the
    identity source of every withdrawn, forgotten or retiring row, and the
    document of a forgotten or retiring-by-forget row. Another source may
    have retired between a failure and its retry."""
    retired = set()
    for r in rows:
        operation = r["plan"].get("operation")
        if operation == "identity_withdraw" and r["state"] in {"withdrawn", "failed"}:
            retired.add((r["dataset"], r["source"]))
        if operation == "identity_forget" and r["state"] in {"forgotten", "failed"}:
            retired.add((r["dataset"], r["source"]))
            retired.add((r["dataset"], r["plan"]["original_data_id"]))
    return retired


async def verify_no_contributions(graph, source, triples):
    for a, b, relation in triples:
        edge = await edge_metadata(graph, a, b, relation)
        if edge is not None:
            from .publish import contributions

            if any(is_own(source, c) for c in contributions(edge.edge_properties)):
                raise IntentError(
                    "verify_withdrawal", "Retired identity contribution remains"
                )


async def verify_survivors(graph, vector, source, plan, released, retired):
    """Every owned object the plan recorded is either gone with its index, or
    survives for the refs it still owes: `released(ref)` says a ref no longer
    owes survival, and `retired` names the sources whose contributions do not
    either."""
    from .publish import contributions

    for key, old in plan["entities"].items():
        current = (await graph.get_node_delete_data([key])).get(key)
        remaining = {ref for ref in old["refs"] if not released(ref)}
        if remaining and (
            current is None or not remaining <= set(current.source_ref_keys)
        ):
            raise IntentError(
                "verify_survivor", "Independent Entity ownership was lost"
            )
        if current is not None and not current.source_ref_keys:
            raise IntentError("verify_withdrawal", "Unowned Entity was not removed")
        for field in old["indexed_fields"]:
            collection = f'{old["type"]}_{field}'
            indexed = await vector.has_collection(collection) and bool(
                await vector.retrieve(collection, [key])
            )
            if indexed != (current is not None):
                raise IntentError(
                    "verify_index",
                    "Withdrawn/surviving Entity vector disagrees with graph",
                )
    for old in plan["edges"]:
        edge = await edge_metadata(graph, old["source"], old["target"], old["relation"])
        remaining = {ref for ref in old["refs"] if not released(ref)}
        if remaining and (edge is None or not remaining <= set(edge.source_ref_keys)):
            raise IntentError("verify_survivor", "Independent edge ownership was lost")
        for c in contributions(old["properties"]):
            key = (c.get("dataset_id"), c.get("identity_data_id"))
            if key not in retired and not is_own(source, c):
                if edge is None or c not in contributions(edge.edge_properties):
                    raise IntentError(
                        "verify_survivor", "Independent contribution was lost"
                    )


async def withdraw(
    publisher, source, *, expected_revision, origin="runtime", fault_stage=None
):
    from cognee.infrastructure.databases.provenance import (
        make_source_ref_key,
        parse_source_ref_key,
    )
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
    row = next(
        (
            r
            for r in await records.rows(source.dataset_id)
            if r["source"] == str(source.identity_data_id)
        ),
        None,
    )
    if row is None:
        raise IntentError("source_missing", "No saved publication to withdraw")
    if IdentitySource.model_validate_json(row["description"]) != source:
        raise IntentError("revision_reuse", "Withdraw the exact saved description")
    owner = make_source_ref_key(source.dataset_id, source.identity_data_id)
    # Keep the original retirement keys across interrupted retries, even after
    # native deletion has detached references or removed graph objects.
    if (
        row["state"] != "withdrawn"
        and row["plan"].get("operation") == "identity_withdraw"
    ):
        plan = dict(row["plan"])
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

        def released(ref):
            parsed = parse_source_ref_key(ref)
            return ref == owner or (str(parsed.dataset_id), str(parsed.data_id)) in (
                retired
            )

        if await graph.find_nodes_by_source_ref(
            owner
        ) or await graph.find_edges_by_source_ref(owner):
            raise IntentError(
                "verify_owner", "Retired generated source still owns graph objects"
            )
        await verify_no_contributions(graph, source, triples)
        await verify_survivors(graph, vector, source, plan, released, retired)
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
