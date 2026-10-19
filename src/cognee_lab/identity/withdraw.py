"""Selected generated-source retirement using native provenance deletion."""

from .models import IdentitySource
from .native import edge_metadata, require_graph_methods
from .validation import IntentError


async def withdraw(
    publisher, source, *, expected_revision, origin="runtime", fault_stage=None
):
    from cognee.infrastructure.databases.provenance import make_source_ref_key
    from cognee.infrastructure.databases.unified.capabilities import EngineCapability
    from cognee.infrastructure.databases.unified.unified_store_engine import (
        UnifiedStoreEngine,
    )
    from .publish import contributions, identity_edges
    from .storage import encode

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
        owned_edges = await graph.find_edges_by_source_ref(owner)
        edges = await graph.get_edge_delete_data(owned_edges)
        plan = dict(
            operation="identity_withdraw",
            revision=source.revision,
            runtime_profile=publisher.runtime_profile,
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
            identity_edges=[list(e[:3]) for e in identity_edges(source)],
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
        triples = {tuple(e) for e in plan["identity_edges"]}
        triples.update(
            (e["source"], e["target"], e["relation"])
            for e in plan["edges"]
            if "identity_contributions" in e["properties"]
        )
        for a, b, relation in sorted(triples):
            edge = await edge_metadata(graph, a, b, relation)
            if edge is None:
                continue
            previous = contributions(edge.edge_properties)
            kept = [
                c
                for c in previous
                if (c.get("dataset_id"), c.get("identity_data_id"))
                != (str(source.dataset_id), str(source.identity_data_id))
            ]
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
        # Another selected source may have been retired between failed retries.
        # Its historical refs/contributions are no longer survival obligations.
        retired = {
            (r["dataset"], r["source"])
            for r in await records.rows()
            if r["plan"].get("operation") == "identity_withdraw"
            and r["state"] in {"withdrawn", "failed"}
        }
        from cognee.infrastructure.databases.provenance import parse_source_ref_key

        def required_ref(ref):
            parsed = parse_source_ref_key(ref)
            return (str(parsed.dataset_id), str(parsed.data_id)) not in retired

        if await graph.find_nodes_by_source_ref(
            owner
        ) or await graph.find_edges_by_source_ref(owner):
            raise IntentError(
                "verify_owner", "Retired generated source still owns graph objects"
            )
        for a, b, relation in triples:
            edge = await edge_metadata(graph, a, b, relation)
            if edge and any(
                (c.get("dataset_id"), c.get("identity_data_id"))
                == (str(source.dataset_id), str(source.identity_data_id))
                for c in contributions(edge.edge_properties)
            ):
                raise IntentError(
                    "verify_withdrawal", "Retired identity contribution remains"
                )
        for key, old in plan["entities"].items():
            current = (await graph.get_node_delete_data([key])).get(key)
            remaining = {
                ref for ref in old["refs"] if ref != owner and required_ref(ref)
            }
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
            edge = await edge_metadata(
                graph, old["source"], old["target"], old["relation"]
            )
            remaining = {
                ref for ref in old["refs"] if ref != owner and required_ref(ref)
            }
            if remaining and (
                edge is None or not remaining <= set(edge.source_ref_keys)
            ):
                raise IntentError(
                    "verify_survivor", "Independent edge ownership was lost"
                )
            for c in contributions(old["properties"]):
                if (c.get("dataset_id"), c.get("identity_data_id")) not in retired and (
                    c.get("dataset_id"),
                    c.get("identity_data_id"),
                ) != (
                    str(source.dataset_id),
                    str(source.identity_data_id),
                ):
                    if edge is None or c not in contributions(edge.edge_properties):
                        raise IntentError(
                            "verify_survivor", "Independent contribution was lost"
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
