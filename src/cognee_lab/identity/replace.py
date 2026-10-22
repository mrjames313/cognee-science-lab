"""Identity revision replacement with explicit, durable forward recovery."""

from .models import ChunkInput, IdentitySource, SourceTextInput
from .native import edge_metadata, require_graph_methods
from .registered import read_registered, write_registered
from .validation import IntentError


def unchanged_occurrences(old, intended):
    """This milestone admits decision/retention changes, not occurrence remapping."""

    def text_inputs(source):
        return {
            k: v
            for k, v in source.inputs.items()
            if isinstance(v, (SourceTextInput, ChunkInput))
        }

    if (
        old.dataset_id != intended.dataset_id
        or old.identity_data_id != intended.identity_data_id
        or old.original_input_ref != intended.original_input_ref
        or text_inputs(old) != text_inputs(intended)
        or old.mention_groups != intended.mention_groups
    ):
        raise IntentError(
            "not_admitted",
            "Text, chunk mapping and occurrence groups must remain unchanged in this replacement slice",
        )


def retained_contributions(source, previous, wanted, source_refs):
    from cognee.infrastructure.databases.provenance import make_source_ref_key

    owner_key = (str(source.dataset_id), str(source.identity_data_id))
    kept = [
        c
        for c in previous
        if (c.get("dataset_id"), c.get("identity_data_id")) != owner_key or c in wanted
    ]
    for c in kept:
        key = (c.get("dataset_id"), c.get("identity_data_id"))
        if key != owner_key and make_source_ref_key(*key) not in source_refs:
            raise IntentError(
                "foreign_owner_missing",
                "Surviving identity contribution has no native owner",
            )
    return kept


async def replace(
    publisher,
    source,
    *,
    texts,
    chunks,
    ctx,
    expected_revision,
    origin="runtime",
    fault_stage=None,
    verify_semantics=None,
    text_change=None,
    semantic_writer=None,
):
    from cognee.infrastructure.databases.provenance import (
        EdgeIdentity,
        make_source_ref_key,
    )
    from cognee.infrastructure.databases.unified.provenance_delete_planner import (
        execute_source_ref_removal,
    )
    from .publish import contributions, identity_edges
    from .storage import encode

    graph, vector, records = publisher.graph, publisher.vector, publisher.records
    require_graph_methods(
        graph,
        [
            "get_node_delete_data",
            "get_edge_delete_data",
            "remove_node_source_refs",
            "remove_edge_source_refs",
            "delete_nodes",
            "delete_edge_triples",
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
        raise IntentError("source_missing", "Replacement requires a saved publication")
    if row["revision"] != expected_revision:
        raise IntentError("stale_revision", "Saved revision changed")
    saved = IdentitySource.model_validate_json(row["description"])
    retry = (
        row["state"] == "failed" and row["plan"].get("operation") == "identity_replace"
    )
    if retry:
        if source != saved:
            raise IntentError(
                "revision_reuse", "Recovery must use the exact saved replacement intent"
            )
        plan = dict(row["plan"])
        try:
            old = IdentitySource.model_validate_json(plan["previous_description"])
            if (
                plan["revision"] != source.revision
                or old.revision + 1 != source.revision
            ):
                raise ValueError("inconsistent revisions")
        except (KeyError, ValueError) as exc:
            raise IntentError(
                "recovery_plan", "Saved replacement plan is missing or invalid"
            ) from exc
    else:
        if row["state"] != "current" or source.revision != saved.revision + 1:
            raise IntentError(
                "revision_sequence",
                "Replace a current description with exactly the next revision",
            )
        old = saved
        plan = dict(
            operation="identity_replace",
            revision=source.revision,
            previous_description=old.model_dump_json(),
            runtime_profile=publisher.runtime_profile,
        )
    if retry and plan.get("text_change"):
        from .text_changes import TextChange

        saved_change = TextChange.from_plan(plan)
        if text_change is not None and text_change != saved_change:
            raise IntentError("recovery_plan", "Use the exact saved text change")
        text_change = saved_change
    if text_change is None:
        unchanged_occurrences(old, source)
        if semantic_writer is not None:
            raise IntentError(
                "not_admitted", "Semantic rebuilding requires a text change"
            )
    else:
        if semantic_writer is None or verify_semantics is None:
            raise IntentError(
                "semantic_rebuild",
                "Text replacement requires explicit semantic writer and verifier",
            )
        await text_change.preflight(
            publisher, old, source, texts, chunks, ctx, retry=retry
        )
    registered = await read_registered(source)
    if registered not in (old, source):
        raise IntentError(
            "generated_source_changed",
            "Registered snapshot matches neither the previous nor intended revision",
        )
    if not retry and registered != old:
        raise IntentError(
            "generated_source_changed",
            "Current registered snapshot differs from the previous publication",
        )
    await publisher.preflight(
        source,
        texts,
        chunks,
        ctx,
        registered_source=registered,
        saved_revision=row["revision"],
        prepared_text=text_change is not None,
    )
    if verify_semantics is not None and text_change is None:
        await verify_semantics()
    owner = make_source_ref_key(source.dataset_id, source.identity_data_id)
    if not retry:
        if text_change is not None:
            from dataclasses import asdict

            plan["text_change"] = asdict(text_change)
        retired_ids = [
            str(i)
            for i in set(old.entity_constructions) - set(source.entity_constructions)
        ]
        node_data = await graph.get_node_delete_data(retired_ids)
        plan.update(
            retired_entities={
                key: dict(
                    refs=n.source_ref_keys,
                    type=n.node_type,
                    indexed_fields=n.indexed_fields,
                )
                for key, n in node_data.items()
            },
            old_edges=[list(e[:3]) for e in identity_edges(old)],
            new_edges=[list(e[:3]) for e in identity_edges(source)],
        )
        edges = await graph.get_edge_delete_data(
            [EdgeIdentity(*e) for e in plan["old_edges"]]
        )
        plan["previous_edges"] = [
            dict(
                source=e.source_id,
                target=e.target_id,
                relation=e.relationship_name,
                refs=data.source_ref_keys,
                properties=data.edge_properties,
            )
            for e, data in edges.items()
        ]
    attempt = await records.begin(
        source,
        expected_revision=expected_revision,
        plan=plan,
        method="replace",
        origin=origin,
    )
    stage = "replace_saved"

    def injected(name):
        if fault_stage == name:
            raise IntentError("injected_failure", f"Injected failure at {name}")

    async def retire_and_verify():
        injected("replace_published")
        wanted = {}
        for a, b, relation, c in identity_edges(source):
            wanted.setdefault((a, b, relation), []).append(c)
        retire_edges = []
        for triple in {tuple(e) for e in plan["old_edges"]}:
            edge = await edge_metadata(graph, *triple)
            if edge is None:
                continue
            before = contributions(edge.edge_properties)
            kept = retained_contributions(
                source, before, wanted.get(triple, []), edge.source_ref_keys
            )
            if kept != before:
                await graph.add_edges(
                    [
                        (
                            *triple,
                            dict(
                                edge.edge_properties,
                                identity_contributions=encode(kept),
                            ),
                        )
                    ]
                )
            if not wanted.get(triple):
                retire_edges.append(EdgeIdentity(*triple))
        nodes = await graph.get_node_delete_data(list(plan["retired_entities"]))
        edges = await graph.get_edge_delete_data(retire_edges)
        await execute_source_ref_removal(
            graph,
            vector,
            node_data=nodes,
            edge_data=edges,
            refs_by_node={key: [owner] for key in nodes},
            refs_by_edge={key: [owner] for key in edges},
        )
        injected("replace_retired")
        # New ownership/contributions are verified by the common publisher.
        # Here check that this source has no stale ownership or payloads.
        for triple in {tuple(e) for e in plan["old_edges"]}:
            edge = await edge_metadata(graph, *triple)
            if edge is None:
                continue
            own = [
                c
                for c in contributions(edge.edge_properties)
                if (c.get("dataset_id"), c.get("identity_data_id"))
                == (str(source.dataset_id), str(source.identity_data_id))
            ]
            if any(c not in wanted.get(triple, []) for c in own):
                raise IntentError(
                    "verify_retirement", "Obsolete identity contribution remains"
                )
            if triple not in wanted and owner in edge.source_ref_keys:
                raise IntentError(
                    "verify_retirement", "Obsolete identity edge ownership remains"
                )
        for key, old_node in plan["retired_entities"].items():
            current = (await graph.get_node_delete_data([key])).get(key)
            if current and owner in current.source_ref_keys:
                raise IntentError(
                    "verify_retirement",
                    "Retired Entity declaration still owns its node",
                )
            for field in old_node["indexed_fields"]:
                collection = f"{old_node['type']}_{field}"
                indexed = await vector.has_collection(collection) and bool(
                    await vector.retrieve(collection, [key])
                )
                if indexed != (current is not None):
                    raise IntentError(
                        "verify_index", "Retired Entity graph and vector disagree"
                    )
        current_rows = await records.rows()
        foreign_intent = {
            (r["dataset"], r["source"]): IdentitySource.model_validate_json(
                r["description"]
            )
            for r in current_rows
            if r["state"] == "current"
        }
        for prior in plan["previous_edges"]:
            edge = await edge_metadata(
                graph, prior["source"], prior["target"], prior["relation"]
            )
            for c in contributions(prior["properties"]):
                key = (c.get("dataset_id"), c.get("identity_data_id"))
                other = foreign_intent.get(key)
                if (
                    other
                    and key != (str(source.dataset_id), str(source.identity_data_id))
                    and any(
                        (a, b, rel)
                        == (prior["source"], prior["target"], prior["relation"])
                        and current == c
                        for a, b, rel, current in identity_edges(other)
                    )
                ):
                    foreign_owner = make_source_ref_key(*key)
                    if (
                        edge is None
                        or c not in contributions(edge.edge_properties)
                        or foreign_owner not in edge.source_ref_keys
                    ):
                        raise IntentError(
                            "verify_survivor",
                            "Independent identity contribution or owner was lost",
                        )
        if await read_registered(source) != source:
            raise IntentError(
                "generated_source_changed",
                "Registered snapshot changed during replacement",
            )
        if text_change is not None:
            await text_change.verify(publisher, old, source, chunks)

    try:
        injected(stage)
        # Recheck after taking the writer reservation and before native I/O.
        actual = await read_registered(source)
        if actual not in (old, source):
            raise IntentError(
                "generated_source_changed", "Registered identity snapshot changed"
            )
        if text_change is not None:

            async def boundary(name):
                nonlocal stage
                stage = name
                injected(name)

            stage = "text_removal"
            await text_change.apply(publisher, old, source, chunks, ctx, boundary)
        stage = "replace_registered"
        await write_registered(source, ctx)
        injected(stage)
        stage = "replacement_publish"
        return await publisher._apply_pending(
            source,
            texts=texts,
            chunks=chunks,
            ctx=ctx,
            attempt=attempt,
            origin=origin,
            verify_semantics=verify_semantics,
            semantic_writer=semantic_writer,
            after_write=retire_and_verify,
            fault_stage=(
                "verification" if fault_stage == "replace_verification" else fault_stage
            ),
        )
    except Exception as exc:
        if getattr(exc, "code", None) == "recovery_required":
            raise
        try:
            event = await records.fail(source, attempt, stage, exc, origin=origin)
        except Exception as diagnostic_error:
            raise IntentError(
                "recovery_record_failed",
                f"Replacement unavailable: attempt={attempt}, stage={stage}, error={exc}; "
                f"recovery-event write also failed: {diagnostic_error}",
            ) from diagnostic_error
        raise IntentError(
            "recovery_required", f"{exc}; recovery_event_id={event}"
        ) from exc
