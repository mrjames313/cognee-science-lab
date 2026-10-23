"""Identity revision replacement with explicit, durable forward recovery."""

from .admission import admit, check_absent_from_graph, identity_map
from .models import IdentitySource
from .native import edge_metadata, require_graph_methods
from .registered import read_registered, write_registered
from .stages import Operation, run_attempt, saved_row
from .validation import IntentError

REPLACE = Operation(
    "replace", "Replacement", ("withhold_dependents", "replace_registered"), None
)
# replace_saved fails before the snapshot recheck, then the stages above
# (withhold_dependents only runs for a text change), then the points inside
# the shared publisher (after its writes, after retirement, before
# acknowledgement) and the text change's boundaries.
FAULT_STAGES = (
    "replace_saved",
    *REPLACE.faults,
    "replace_published",
    "replace_retired",
    "replace_verification",
    "text_removed",
    "text_registered",
    "text_chunks",
)
# The stages that run only for a text change.
TEXT_FAULT_STAGES = (
    "withhold_dependents",
    "text_removed",
    "text_registered",
    "text_chunks",
)


def transition(old, texts, text_change):
    """The text transition and map a replacement states: the text change's,
    or the same text with every occurrence in place."""
    if text_change is not None:
        return text_change.previous_text, text_change.text, text_change.occurrence_map
    text = texts.get(old.original_input_ref)
    if text is None:
        raise IntentError("source_changed", "Replacement text is missing")
    return text, text, identity_map(old)


async def admit_replacement(graph, old, source, texts, text_change, *, retry):
    """The one admission of a replacement. A first attempt also probes the
    graph for the UUIDs the revision introduces. Without a text change nothing
    rebuilds the document, so a retired or fresh group, or an added occurrence,
    is refused."""
    before, after, occurrence_map = transition(old, texts, text_change)
    fate = admit(old, source, before, after, occurrence_map, first_attempt=not retry)
    if not retry:
        await check_absent_from_graph(graph, old, source, fate)
    mapped = sum(ref is not None for refs in occurrence_map.values() for ref in refs)
    occurrences = sum(len(g.occurrences) for g in source.mention_groups.values())
    if text_change is None and (fate.retired or fate.fresh or occurrences > mapped):
        raise IntentError(
            "rebuild_required",
            "Retiring or adding a group or an occurrence requires a text change and its rebuild",
        )
    return fate


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
    from .storage import STALE_REVISION, encode

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
    row = await saved_row(records, source, "Replacement requires a saved publication")
    if row.revision != expected_revision:
        raise IntentError(*STALE_REVISION)
    saved = IdentitySource.model_validate_json(row.description)
    retry = row.resumed_by == "replace"
    if retry:
        if source != saved:
            raise IntentError(
                "revision_reuse", "Recovery must use the exact saved replacement intent"
            )
        plan = dict(row.plan)
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
        # Earlier than begin() on purpose, before the plan reads the graph. On
        # every row but a current one begin() refuses with another message.
        if row.state != "current" or source.revision != saved.revision + 1:
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
    if text_change is None and semantic_writer is not None:
        raise IntentError("not_admitted", "Semantic rebuilding requires a text change")
    if text_change is not None and (
        semantic_writer is None or verify_semantics is None
    ):
        raise IntentError(
            "semantic_rebuild",
            "Text replacement requires explicit semantic writer and verifier",
        )
    await admit_replacement(graph, old, source, texts, text_change, retry=retry)
    if text_change is not None:
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
        saved_revision=row.revision,
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

    async def retire_and_verify(run):
        run.inject("replace_published")
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
        run.inject("replace_retired")
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
            (r.dataset, r.source): IdentitySource.model_validate_json(r.description)
            for r in current_rows
            if r.state == "current"
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

    async def recheck(run):
        run.inject("replace_saved")
        # Recheck after taking the writer reservation and before native I/O.
        actual = await read_registered(source)
        if actual not in (old, source):
            raise IntentError(
                "generated_source_changed", "Registered identity snapshot changed"
            )

    async def withhold(_):
        # Before the text changes: the rows are durable before the edit can
        # complete, and the pending or failed row withholds every decision
        # citing this document until then (withheld_decisions).
        from .withholding import withhold_dependents

        return await withhold_dependents(
            publisher, old, text_change.previous_text, text_change.text, source.revision
        )

    async def clean_withholdings(_):
        # Rows carry forward across revisions until the input validates or
        # the decision or input is gone. Idempotent: a retry recomputes.
        from .validation import validate_inputs
        from .withholding import recorded_rows

        own = str(source.identity_data_id)
        table = await publisher.withholdings.rows(source.dataset_id)
        if not any(w.source == own for w in table):
            return
        drift = await validate_inputs(source, texts=texts, chunks=chunks, graph=graph)
        kept = {
            (w.assignment, w.input_ref)
            for w in recorded_rows({own: source}, table)
            if w.input_ref in drift
        }
        await publisher.withholdings.keep(source.dataset_id, own, kept)

    async def remove_text(run):
        await text_change.apply(publisher, old, source, chunks, ctx, run.boundary)

    async def register(_):
        await write_registered(source, ctx)

    async def publish(run):
        return await publisher._apply_pending(
            source,
            texts=texts,
            chunks=chunks,
            ctx=ctx,
            attempt=run.attempt,
            origin=origin,
            verify_semantics=verify_semantics,
            semantic_writer=semantic_writer,
            after_write=lambda: retire_and_verify(run),
            fault_stage=(
                "verification" if fault_stage == "replace_verification" else fault_stage
            ),
        )

    _, results = await run_attempt(
        REPLACE,
        records,
        source,
        plan,
        [
            ("replace_saved", recheck),
            *(
                [("withhold_dependents", withhold), ("text_removal", remove_text)]
                if text_change is not None
                else []
            ),
            ("replace_registered", register),
            ("withholding_cleanup", clean_withholdings),
            ("replacement_publish", publish),
        ],
        expected_revision=expected_revision,
        origin=origin,
        fault_stage=fault_stage,
    )
    return results["replacement_publish"]
