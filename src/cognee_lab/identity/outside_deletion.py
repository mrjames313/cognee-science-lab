"""Entities deleted outside the lab.

A writer outside the lab can delete an Entity that a saved source names,
through Cognee's own graph API (`edit-entity --case delete` stands in for
one), and nothing in the lab records it. Live validation then withholds
every decision that cites the Entity with `input_removed`. The user decided
on 2026-10-25:

1. A withheld decision may keep citing the deleted Entity while a
   neighbouring decision is replaced, so the decisions are answered one at
   a time.
2. A publication never recreates the Entity: a replacement picks a new
   target or leaves the mention unresolved, and a re-add whose files name
   it is refused.

An Entity counts as deleted outside the lab when a served source's
description, or the publishing source's last verified one, names it as a
corpus input or a reusable recipe, its node is absent, and no lab operation
removed it (`lab_removed`). A decision is kept when it, its group and the
inputs it cites are as the source's last verified description has them.
"""

from uuid import UUID

from .erasure_rules import entity_ids_named
from .models import CorpusObjectInput, IdentitySource
from .records import REGISTRY, naming, record_inputs, record_type_of
from .validation import IntentError, reusable_recipes

RECREATION = (
    "entity_recreation",
    "A publication does not recreate an Entity deleted outside the lab: {}; "
    "pick another target or leave the mention unresolved",
)


def verified_description(row) -> IdentitySource | None:
    """The source's description as last verified: a current or withdrawn
    row's; a replacement's previous one while it is pending or failed; a
    pending or failed publication's own when it was verified at that
    revision, as a reconcile of a served row is. None for a first
    publication and for an erasure retry, whose description is new."""
    if row is None or row.description is None:
        return None
    if row.state in ("current", "withdrawn"):
        return row.description
    if row.operation == "identity_replace":
        return IdentitySource.model_validate_json(row.plan["previous_description"])
    if row.verified_revision == row.revision and not row.plan.get("erased_from"):
        return row.description
    return None


def corpus_entities(description) -> set[UUID]:
    """The reusable Entities a description names as existing or declares:
    its corpus inputs and its reusable recipes."""
    return {
        i.entity_id
        for i in description.inputs.values()
        if isinstance(i, CorpusObjectInput)
    } | set(reusable_recipes(description))


def lab_removed(rows, own=None) -> set[UUID]:
    """Entities a lab operation removed, or may have: every forget's removed
    Entities and mention UUIDs, what a replacement planned to retire, and
    the recipes of a source that is not served, which a withdrawal or a
    failed attempt may have removed. The recipes of `own`, the source being
    published, are named, not removed, while its own attempt is in flight."""
    removed = set()
    for row in rows:
        for tombstone in (row.tombstone, row.last_tombstone):
            if tombstone is not None:
                removed |= set(tombstone.removed_entity_ids)
                removed |= set(tombstone.all_mention_ids)
        removed |= {UUID(key) for key in row.plan.get("retired_entities", {})}
        if (
            row.description is not None
            and not row.is_served
            and (row.dataset, row.source) != own
        ):
            removed |= set(row.description.entity_constructions)
    return removed


async def deleted_outside(graph, rows, source, verified) -> frozenset[UUID]:
    """The Entities deleted outside the lab, as the publication of `source`
    sees them. Its own row counts through `verified` alone, since an
    attempt in flight leaves it unserved."""
    own = (str(source.dataset_id), str(source.identity_data_id))
    named = set().union(
        *(
            corpus_entities(r.description)
            for r in rows
            if r.is_served and (r.dataset, r.source) != own
        ),
        corpus_entities(verified) if verified is not None else (),
    )
    candidates = named - lab_removed(rows, own)
    return frozenset([e for e in candidates if await graph.get_node(str(e)) is None])


def touching(description, entity_id) -> dict:
    """Each part of the description that cites or names the Entity, by key,
    with what it holds: the record, attribution included, or an unresolved
    group, and the inputs it cites."""
    keys = {
        k
        for k, i in description.inputs.items()
        if isinstance(i, CorpusObjectInput) and i.entity_id == entity_id
    }
    found = {}
    for key, inputs in record_inputs(description).items():
        if inputs & keys or entity_id in naming(description, key):
            kind = REGISTRY[record_type_of(description, key)]
            found[key] = (
                getattr(description, kind.field)[key],
                {i: description.inputs[i] for i in sorted(inputs)},
            )
    resolved = {d.group_ref for d in description.mention_resolutions.values()}
    for key, group in description.mention_groups.items():
        if key not in resolved and keys & set(group.input_refs):
            found[key] = (
                group,
                {i: description.inputs[i] for i in sorted(group.input_refs)},
            )
    return found


def kept(source, verified, entity_id) -> bool:
    """Whether every part of `source` that cites or names the Entity is kept
    from `verified`."""
    if verified is None:
        return False
    before = touching(verified, entity_id)
    return all(before.get(k) == held for k, held in touching(source, entity_id).items())


def check_no_recreation(source, verified, outside) -> frozenset[UUID]:
    """The Entities deleted outside the lab that this publication leaves
    absent: each one it names whose citing and naming parts are all kept.
    Refuses one that a changed or new part names (`entity_recreation`).
    The publisher skips their recipes, edges and contributions, in the
    write and in its verification."""
    named = outside & entity_ids_named(source)
    for entity_id in sorted(named, key=str):
        if not kept(source, verified, entity_id):
            code, message = RECREATION
            raise IntentError(code, message.format(entity_id))
    return frozenset(named)


async def check_readd(graph, tombstone, source, rows):
    """A re-add whose files name a reusable Entity of a forgotten life that
    is now deleted outside the lab is refused (`entity_recreation`): the
    user's default of 2026-10-25 for Q2. An Entity a lab operation removed
    is replaced by a derived UUID instead (`describe_readd`)."""
    candidates = (
        set(tombstone.all_reusable_ids) & entity_ids_named(source)
    ) - lab_removed(rows)
    for entity_id in sorted(candidates, key=str):
        if await graph.get_node(str(entity_id)) is None:
            code, message = RECREATION
            raise IntentError(code, message.format(entity_id))
