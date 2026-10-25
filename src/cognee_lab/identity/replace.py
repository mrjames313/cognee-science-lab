"""Identity revision replacement with explicit, durable forward recovery."""

import copy

from .admission import admit, check_absent_from_graph, identity_map
from .erasure_rules import NO_ERASURES, check_retry_chain, erasures_of
from .models import IdentitySource
from .native import edge_metadata, require_graph_methods
from .registered import read_registered, write_registered
from .stages import Operation, run_attempt, saved_row
from .storage import STALE_REVISION, encode, erased_from, superseding_plan
from .validation import IntentError

# Text changes only: the dependents' withholding, then the text change's
# boundaries.
WITHHOLD = "withhold_dependents"
TEXT_BOUNDARIES = ("text_removed", "text_registered", "text_chunks")
TEXT_FAULT_STAGES = (WITHHOLD, *TEXT_BOUNDARIES)
REPLACE = Operation("replace", "Replacement", (WITHHOLD, "replace_registered"), None)
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
    *TEXT_BOUNDARIES,
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


async def admit_replacement(
    graph, old, source, texts, text_change, *, retry, erasures=NO_ERASURES
):
    """The one admission of a replacement. A first attempt also probes the
    graph for the UUIDs the revision introduces. Without a text change nothing
    rebuilds the document, so a retired or fresh group, or an added occurrence,
    is refused."""
    before, after, occurrence_map = transition(old, texts, text_change)
    fate = admit(
        old,
        source,
        before,
        after,
        occurrence_map,
        first_attempt=not retry,
        erasures=erasures,
    )
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


# What plan_retirement records in a plan.
RETIREMENT_FIELDS = ("retired_entities", "old_edges", "previous_edges")


def saved_retirement(plan) -> dict:
    """What a saved plan records of its retirement (`RETIREMENT_FIELDS`),
    copied for a retry, which extends it (plan_retirement): the first
    attempt may have retired part of it, which the graph no longer shows."""
    return {f: copy.deepcopy(plan[f]) for f in RETIREMENT_FIELDS if f in plan}


async def plan_retirement(graph, plan, olds, source):
    """Record what replacing `olds` by `source` retires: the recipes they
    declared and `source` does not, and their identity edges with the refs
    and contributions each holds now. A replacement's `olds` are its
    previous revision and the saved revisions erasure retries superseded; a
    reconcile's are the superseded ones alone, since a failed attempt may
    have written them. An erasure retry of a replacement adds what the
    saved revision it supersedes declared or wrote; what the plan already
    holds keeps the values its first attempt read. `new_edges` are the newest
    description's alone, on purpose: a superseded revision is never
    published, so only what it would retire carries over."""
    from cognee.infrastructure.databases.provenance import EdgeIdentity
    from .publish import identity_edges

    retired = plan.setdefault("retired_entities", {})
    keep = {str(i) for i in source.entity_constructions}
    gone = {str(i) for o in olds for i in o.entity_constructions} - keep - set(retired)
    for key, n in (await graph.get_node_delete_data(sorted(gone))).items():
        retired[key] = dict(
            refs=n.source_ref_keys, type=n.node_type, indexed_fields=n.indexed_fields
        )
    old_edges = plan.setdefault("old_edges", [])
    known = {tuple(e) for e in old_edges}
    added = []
    for o in olds:
        for edge in identity_edges(o):
            if tuple(edge[:3]) not in known:
                known.add(tuple(edge[:3]))
                added.append(list(edge[:3]))
    old_edges += added
    plan["new_edges"] = [list(e[:3]) for e in identity_edges(source)]
    edges = await graph.get_edge_delete_data([EdgeIdentity(*e) for e in added])
    plan.setdefault("previous_edges", []).extend(
        dict(
            source=e.source_id,
            target=e.target_id,
            relation=e.relationship_name,
            refs=data.source_ref_keys,
            properties=data.edge_properties,
        )
        for e, data in edges.items()
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


def wanted_contributions(source) -> dict:
    """The contributions `source` makes, by identity edge."""
    from .publish import identity_edges

    wanted = {}
    for a, b, relation, c in identity_edges(source):
        wanted.setdefault((a, b, relation), []).append(c)
    return wanted


async def retire(graph, vector, source, plan):
    """Remove what `plan` retires (plan_retirement): each contribution of
    `source`'s owner that its description no longer makes, the owner's ref
    on each identity edge nothing of it wants and on each retired recipe's
    node; a node or edge no other ref owns goes, with its vectors."""
    from cognee.infrastructure.databases.provenance import (
        EdgeIdentity,
        make_source_ref_key,
    )
    from cognee.infrastructure.databases.unified.provenance_delete_planner import (
        execute_source_ref_removal,
    )
    from .publish import contributions

    owner = make_source_ref_key(source.dataset_id, source.identity_data_id)
    wanted = wanted_contributions(source)
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
                        dict(edge.edge_properties, identity_contributions=encode(kept)),
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


async def verify_retired(graph, vector, records, source, plan):
    """Nothing `plan` retires keeps `source`'s ownership or contributions, a
    retired recipe's node and name vectors agree, and every contribution
    another current source still makes on those edges survived with its
    owner. New ownership and contributions are the common publisher's to
    verify."""
    from cognee.infrastructure.databases.provenance import make_source_ref_key
    from .publish import contributions, identity_edges

    owner = make_source_ref_key(source.dataset_id, source.identity_data_id)
    own_key = (str(source.dataset_id), str(source.identity_data_id))
    wanted = wanted_contributions(source)
    for triple in {tuple(e) for e in plan["old_edges"]}:
        edge = await edge_metadata(graph, *triple)
        if edge is None:
            continue
        own = [
            c
            for c in contributions(edge.edge_properties)
            if (c.get("dataset_id"), c.get("identity_data_id")) == own_key
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
    foreign_intent = {
        (r.dataset, r.source): r.description
        for r in await records.rows()
        if r.state == "current"
    }
    for prior in plan["previous_edges"]:
        triple = (prior["source"], prior["target"], prior["relation"])
        edge = await edge_metadata(graph, *triple)
        for c in contributions(prior["properties"]):
            key = (c.get("dataset_id"), c.get("identity_data_id"))
            other = foreign_intent.get(key)
            if (
                other
                and key != own_key
                and any(
                    (a, b, rel) == triple and current == c
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
    saved = row.description
    retry = row.resumed_by == "replace"
    # Only an erasure retry begins with another description: the removal of
    # what a forget took away, applied to the saved revision, which it
    # supersedes.
    erasure_retry = retry and source != saved
    if retry:
        plan = dict(row.plan, **superseding_plan(row, source))
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
    # The previous revision, the saved revisions erasure retries superseded,
    # and the one this attempt begins with.
    chain = [old, *erased_from(plan), source]

    async def admit_chain():
        # The first step is the replacement itself, which admission checks;
        # each later one is an erasure retry of the step before.
        erasures = erasures_of(await records.rows(), source)
        await admit_replacement(
            graph, old, chain[1], texts, text_change, retry=retry, erasures=erasures
        )
        check_retry_chain(chain[1:], erasures, row.verified_revision, row.description)

    await admit_chain()
    if text_change is not None:
        await text_change.preflight(
            publisher, old, source, texts, chunks, ctx, retry=retry
        )
    registered = await read_registered(source)
    if registered not in chain:
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
    if not retry and text_change is not None:
        from dataclasses import asdict

        plan["text_change"] = asdict(text_change)
    if erasure_retry or not retry:
        await plan_retirement(graph, plan, chain[:-1], source)

    async def retire_and_verify(run):
        run.inject("replace_published")
        await retire(graph, vector, source, plan)
        run.inject("replace_retired")
        await verify_retired(graph, vector, records, source, plan)
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
        if actual not in chain:
            raise IntentError(
                "generated_source_changed", "Registered identity snapshot changed"
            )
        # A source may have begun reading a recipe an erasure step drops
        # since admission read the rows.
        await admit_chain()

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
        from .withholding import record_reader

        drift = await validate_inputs(
            source,
            texts=texts,
            chunks=chunks,
            graph=graph,
            saved_record_reader=record_reader(await records.rows()),
        )
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
                [(WITHHOLD, withhold), ("text_removal", remove_text)]
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
