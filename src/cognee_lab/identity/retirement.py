"""What withdraw and forget share: who owns an object, which sources are
retiring, what a retirement releases, and what must survive it.

A retirement removes one source's refs and contributions. `retired_sources`
names the sources whose survival is no longer owed, `released` says whether a
ref still owes survival, `dependents` finds the sources that consumed what a
retirement takes away, and `verify_survivors` checks that every other owner
kept its refs and contributions.
"""

from typing import NamedTuple, TypedDict
from uuid import UUID

from .models import CorpusObjectInput, IdentitySource, SourceTextInput, Tombstone
from .native import edge_metadata
from .validation import IntentError


class SourceIds(NamedTuple):
    """Who a source is: what ownership and consumption are decided by. A
    saved description and a forgotten source's tombstone both give it."""

    dataset_id: UUID
    identity_data_id: UUID
    original_data_id: UUID


def source_ids(source: "IdentitySource | Tombstone | SourceIds") -> SourceIds:
    if isinstance(source, SourceIds):
        return source
    if isinstance(source, Tombstone):
        return SourceIds(
            source.dataset_id, source.identity_data_id, source.original_data_id
        )
    doc = source.inputs[source.original_input_ref]
    return SourceIds(source.dataset_id, source.identity_data_id, doc.data_id)


class Dependent(TypedDict):
    """One input through which a saved source consumed a retiring source."""

    dataset_id: str
    identity_data_id: str
    input_ref: str
    kind: str
    consumed: str


def consumes(reader, target, sole_owned=frozenset()):
    """The inputs through which `reader` consumed `target`'s document, or an
    Entity in `sole_owned`. A chunk or span input names its document through
    a source_text input of the same description, so the text check covers
    it."""
    ids = source_ids(target)
    found = []
    for key, item in reader.inputs.items():
        if isinstance(item, SourceTextInput):
            consumed = (item.dataset_id, item.data_id) == (
                ids.dataset_id,
                ids.original_data_id,
            )
            consumed_id = item.data_id
        elif isinstance(item, CorpusObjectInput):
            consumed = item.entity_id in sole_owned
            consumed_id = item.entity_id
        else:
            continue
        if consumed:
            found.append(
                Dependent(
                    dataset_id=str(reader.dataset_id),
                    identity_data_id=str(reader.identity_data_id),
                    input_ref=key,
                    kind=item.kind,
                    consumed=str(consumed_id),
                )
            )
    return found


def dependents(source, rows, sole_owned=frozenset()):
    """The saved sources that consumed this source's document, or an Entity
    that only this source owns. Withdrawn and forgotten sources consume
    nothing."""
    own = (str(source.dataset_id), str(source.identity_data_id))
    found = []
    for row in rows:
        if (row.dataset, row.source) == own or row.is_retired:
            continue
        reader = IdentitySource.model_validate_json(row.description)
        found += consumes(reader, source, sole_owned)
    return found


def retired_sources(rows):
    """(dataset, data id) pairs whose survival is no longer an obligation: the
    identity source of every withdrawn, forgotten or retiring row, and the
    document of a forgotten or retiring-by-forget row. Another source may
    have retired between a failure and its retry."""
    retired = set()
    for r in rows:
        operation = r.operation
        if operation == "identity_withdraw" and r.state in {"withdrawn", "failed"}:
            retired.add((r.dataset, r.source))
        if operation == "identity_forget" and r.state in {"forgotten", "failed"}:
            retired.add((r.dataset, r.source))
            retired.add((r.dataset, r.plan["original_data_id"]))
    return retired


def removed_entities(source, plan, rows):
    """The Entities a forget with this plan removes: those whose every
    recorded owner is this source or a retiring one, since a retiring owner's
    refs leave too."""
    gone = released(owned_by(source, document=True), retired_sources(rows))
    return {
        UUID(key)
        for key, node in plan["entities"].items()
        if node["type"] == "Entity" and all(gone(r) for r in node["refs"])
    }


async def readd_removed(graph, source, plan, rows):
    """The Entities a re-add of this forgotten source must replace: those its
    forget removed, and every Entity its plan recorded that the graph no
    longer holds. A co-owner's later forget can remove an Entity this forget
    left, and that co-owner's re-add makes the ledger show a live owner
    again, so the rows alone cannot tell what is gone."""
    absent = {
        UUID(key)
        for key, node in plan["entities"].items()
        if node["type"] == "Entity" and await graph.get_node(key) is None
    }
    return removed_entities(source, plan, rows) | absent


def retiring_by_forget(row):
    return row.state in {"failed", "pending"} and row.operation == "identity_forget"


def refuse_retiring_inputs(source, rows):
    """Refuse a description that consumes a source whose forget is pending or
    failed. Admitting it would leave that forget refused by its dependent and
    the source half-forgotten."""
    own = (str(source.dataset_id), str(source.identity_data_id))
    for row in rows:
        if (row.dataset, row.source) == own or not retiring_by_forget(row):
            continue
        retiring = IdentitySource.model_validate_json(row.description)
        found = consumes(source, retiring, removed_entities(retiring, row.plan, rows))
        if found:
            raise IntentError(
                "retiring_source",
                "An input is a document or Entity whose forget is not finished; reconcile that forget first",
                details=dict(dependents=found),
            )


def owned_by(source, *, document):
    """Whether a source ref belongs to this source: its identity source and,
    with `document`, its document and the document's chunks."""
    from cognee.infrastructure.databases.provenance import parse_source_ref_key

    ids = source_ids(source)
    own = {ids.identity_data_id}
    if document:
        own.add(ids.original_data_id)

    def own_ref(ref):
        try:
            parsed = parse_source_ref_key(ref)
        except ValueError:
            return False
        return parsed.dataset_id == ids.dataset_id and parsed.data_id in own

    return own_ref


def released(own_ref, retired):
    """Whether a ref no longer owes survival: it is this source's, or it
    belongs to a source in `retired`."""
    from cognee.infrastructure.databases.provenance import parse_source_ref_key

    def test(ref):
        if own_ref(ref):
            return True
        parsed = parse_source_ref_key(ref)
        return (str(parsed.dataset_id), str(parsed.data_id)) in retired

    return test


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


async def has_contribution(graph, source, triples):
    """Whether any of the edges still carries this source's contribution."""
    from .publish import contributions

    for a, b, relation in triples:
        edge = await edge_metadata(graph, a, b, relation)
        if edge is not None and any(
            is_own(source, c) for c in contributions(edge.edge_properties)
        ):
            return True
    return False


async def verify_no_contributions(graph, source, triples):
    if await has_contribution(graph, source, triples):
        raise IntentError("verify_withdrawal", "Retired identity contribution remains")


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
