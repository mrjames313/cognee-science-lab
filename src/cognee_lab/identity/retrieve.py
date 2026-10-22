"""Small fixture retriever; native requests/registration follow in the next milestone."""

import re
from types import SimpleNamespace
from uuid import UUID

from .models import Accepted, ChunkInput, IdentitySource
from .native import edge_metadata, fact_neighborhood
from .publish import contributions, identity_edges
from .retirement import RETIRED_STATES
from .validation import IntentError, validate_inputs


async def valid_sources(publisher, dataset_id, rows):
    from .registered import read_registered, read_texts

    valid, unavailable = [], []
    events = await publisher.records.events(dataset_id)
    for row in rows:
        if row["state"] != "current" or row["revision"] != row["verified_revision"]:
            # A deliberate retirement is not unavailable: nothing is withheld.
            if row["state"] not in RETIRED_STATES:
                incident = next(
                    (
                        e
                        for e in reversed(events)
                        if e["identity_data_id"] == row["source"]
                        and e.get("resolved_at") is None
                    ),
                    None,
                )
                unavailable.append(
                    dict(
                        identity_data_id=row["source"],
                        reason="publication_" + row["state"],
                        recovery_event_id=(
                            incident["recovery_event_id"] if incident else None
                        ),
                    )
                )
            continue
        source = IdentitySource.model_validate_json(row["description"])
        try:
            if await read_registered(source) != source:
                raise IntentError(
                    "generated_source_changed",
                    "Registered identity snapshot differs from saved current intent",
                )
            texts, chunks = await read_texts(source), {}
            for item in source.inputs.values():
                if isinstance(item, ChunkInput):
                    node = await publisher.graph.get_node(str(item.chunk_id))
                    parent = source.inputs[item.document_ref]
                    if (
                        node is None
                        or node.get("type") != "DocumentChunk"
                        or not await edge_metadata(
                            publisher.graph, item.chunk_id, parent.data_id, "is_part_of"
                        )
                    ):
                        raise IntentError(
                            "chunk_mapping", "Original chunk or document link missing"
                        )
                    chunks[str(item.chunk_id)] = SimpleNamespace(
                        id=item.chunk_id,
                        chunk_index=node["chunk_index"],
                        text=node["text"],
                        is_part_of=SimpleNamespace(id=parent.data_id),
                    )
            await validate_inputs(
                source, texts=texts, chunks=chunks, graph=publisher.graph
            )
            valid.append((source, row))
        except IntentError as exc:
            event = await publisher.records.fail(
                source, row["attempt"], "retrieval_validation", exc
            )
            unavailable.append(
                dict(
                    identity_data_id=row["source"],
                    reason=exc.code,
                    recovery_event_id=event,
                )
            )
    return valid, unavailable


def words(text):
    return {w.rstrip("s") for w in re.findall(r"\w+", text.casefold()) if len(w) > 1}


async def select_seed_entities(graph, candidates, mention_ids, query):
    """Prefer explicit reusable names, using current graph fields, not payload shape.

    Native vector indexes need not expose an Entity's ``name`` in their payload.
    Resolve their IDs through the graph interface and keep vector order only as
    the fallback for queries without an explicit candidate name.
    """
    reusable, exact, seen = [], [], set()
    query_words = words(query)
    for candidate in candidates:
        entity_id = str(candidate.id)
        if entity_id in mention_ids or entity_id in seen:
            continue
        seen.add(entity_id)
        node = await graph.get_node(entity_id)
        if node is None or node.get("type") != "Entity":
            continue
        reusable.append(entity_id)
        name_words = words(node.get("name") or "")
        if name_words and name_words <= query_words:
            exact.append(entity_id)
    return set(exact or reusable[:1])


async def retrieve(publisher, dataset_id, query, *, limit=5, work_limit=200):
    """Rank actual facts, with document-context variant expansion and local mentions.

    This intentionally bounded first slice scans saved source descriptions. Full
    graph traversal, arbitrary external facts and public SearchType are later work.
    """
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key

    rows = await publisher.records.rows(dataset_id)
    current, unavailable = await valid_sources(publisher, dataset_id, rows)
    # Original-owned markers can outlive generated-source withdrawal/failure.
    # Their local labels must never become reusable vector query aliases.
    mention_ids = {
        str(g.entity_id)
        for row in rows
        for g in IdentitySource.model_validate_json(
            row["description"]
        ).mention_groups.values()
    }
    if not await publisher.vector.has_collection("Entity_name"):
        return dict(
            facts=[],
            identity_expansion_limited=False,
            identity_work=0,
            fact_candidates_limited=False,
            seed_entity_ids=[],
            unavailable_sources=unavailable,
            identity_guide="Accepted links identify the scoped referent; ownership and provenance do not establish scientific support.",
        )
    candidates = await publisher.vector.search(
        "Entity_name",
        query_text=query,
        query_vector=None,
        limit=10,
        include_payload=False,
    )
    # Local mention labels are not reusable query aliases. Prefer explicit name
    # matches; vector candidates remain available for natural-language queries.
    seeds = await select_seed_entities(publisher.graph, candidates, mention_ids, query)
    facts, seen, work, limited, fact_limited = [], set(), 0, False, False
    for source, row in current:
        if work >= work_limit:
            limited = True
            break
        doc = source.inputs[source.original_input_ref]
        document_id = str(doc.data_id)
        eligible = set(seeds)
        expected_contributions = {
            c["assignment_id"]: c for *_, c in identity_edges(source)
        }

        # Read current physical links and validate each declared contribution.
        async def accepted_link(a, b, assignment):
            nonlocal work, limited
            if work >= work_limit:
                limited = True
                return False
            work += 1
            edge = await edge_metadata(publisher.graph, a, b, "resolves_to")
            if edge is None:
                return False
            expected = expected_contributions[assignment]
            if edge.edge_properties.get("resolution_kind") != expected["kind"]:
                return False
            for c in contributions(edge.edge_properties):
                if work >= work_limit:
                    limited = True
                    return False
                work += 1
                if c == expected:
                    return True
            return False

        changed = True
        while changed and not limited:
            changed = False
            for key, variant in source.variant_assignments.items():
                if work >= work_limit:
                    limited = True
                    break
                work += 1
                scope = variant.applicability
                # A span-specific alias needs a span-specific candidate context;
                # this first document-context route declines it rather than widen it.
                if scope.kind == "text_spans":
                    continue
                if (
                    scope.kind == "document"
                    and str(source.inputs[scope.document_ref].data_id) != document_id
                ):
                    continue
                a, b = str(variant.source_entity_id), str(variant.target_entity_id)
                if (a in eligible or b in eligible) and not {a, b} <= eligible:
                    if await accepted_link(a, b, key):
                        eligible.update((a, b))
                        changed = True
        mentions = {}
        for key, decision in source.mention_resolutions.items():
            if work >= work_limit:
                limited = True
                break
            work += 1
            if (
                isinstance(decision, Accepted)
                and str(decision.target_entity_id) in eligible
            ):
                group = source.mention_groups[decision.group_ref]
                mid = str(group.entity_id)
                if await accepted_link(mid, str(decision.target_entity_id), key):
                    mentions[mid] = (group, decision, key)
        for subject in eligible | set(mentions):
            neighborhood, cutoff = await fact_neighborhood(
                publisher.graph, subject, 200
            )
            fact_limited |= cutoff
            for a, b, relation, props in neighborhood:
                if str(a) != subject or relation in {
                    "resolves_to",
                    "has_identity_mention",
                    "contains",
                    "is_a",
                    "is_part_of",
                    "belongs_to_set",
                }:
                    continue
                edge_id = UUID(generate_edge_object_id(str(a), str(b), relation))
                evidence = await get_edge_evidence_records(
                    [edge_id], UUID(str(dataset_id))
                )
                own_evidence = [e for e in evidence if str(e.data_id) == document_id]
                checked = []
                for e in own_evidence:
                    # Old evidence rows are not a version authority. Only the
                    # checked current chunk mapping and native fact owner admit it.
                    if str(e.chunk_id) not in {
                        str(i.chunk_id)
                        for i in source.inputs.values()
                        if isinstance(i, ChunkInput)
                    }:
                        continue
                    chunk = await publisher.graph.get_node(str(e.chunk_id))
                    fact = await edge_metadata(publisher.graph, a, b, relation)
                    owner = make_chunk_source_ref_key(
                        source.dataset_id, e.data_id, e.chunk_id
                    )
                    if (
                        chunk is None
                        or fact is None
                        or owner not in fact.source_ref_keys
                        or e.chunk_index != chunk.get("chunk_index")
                    ):
                        continue
                    checked.append(
                        dict(
                            data_id=document_id,
                            chunk_id=str(e.chunk_id),
                            chunk_index=e.chunk_index,
                            text=chunk.get("text", ""),
                        )
                    )
                if not checked or str(edge_id) in seen:
                    continue
                target = await publisher.graph.get_node(str(b))
                text = (
                    props.get("edge_text")
                    or f'{relation} {(target or {}).get("name", "")}'
                )
                score = len(words(query) & words(text))
                entry = dict(
                    edge_id=str(edge_id),
                    source_id=str(a),
                    target_id=str(b),
                    relationship=relation,
                    text=text,
                    evidence=checked,
                    score=score,
                )
                if subject in mentions:
                    group, decision, key = mentions[subject]
                    # At least one supporting chunk must cover an occurrence.
                    # Additional checked chunks can hold the rest of the fact.
                    allowed_chunks = {
                        str(source.inputs[k].chunk_id) for k in group.chunk_refs
                    }
                    if not any(e["chunk_id"] in allowed_chunks for e in checked):
                        continue
                    # A captured fact can span a marker chunk and a continuation
                    # chunk. Keep its checked native-owned evidence together;
                    # continuation evidence does not create a mention marker.
                    entry["identity"] = dict(
                        state="accepted",
                        target_entity_id=str(decision.target_entity_id),
                        occurrences=[o.model_dump() for o in group.occurrences],
                        identity_data_id=str(source.identity_data_id),
                        assignment_id=key,
                    )
                facts.append(entry)
                seen.add(str(edge_id))
    # Recheck ledger to avoid delivering a source superseded during this read.
    after = {
        r["source"]: (r["state"], r["revision"], r["attempt"])
        for r in await publisher.records.rows(dataset_id)
    }
    if any(
        after.get(r["source"]) != ("current", r["revision"], r["attempt"])
        for _, r in current
    ):
        raise IntentError(
            "retrieval_changed", "Publication changed during retrieval; retry query"
        )
    facts.sort(key=lambda x: (-x["score"], x["edge_id"]))
    return dict(
        facts=facts[:limit],
        identity_expansion_limited=limited,
        identity_work=work,
        fact_candidates_limited=fact_limited,
        seed_entity_ids=sorted(seeds),
        unavailable_sources=unavailable,
        identity_guide="Accepted links identify the scoped referent; ownership and provenance do not establish scientific support.",
    )
