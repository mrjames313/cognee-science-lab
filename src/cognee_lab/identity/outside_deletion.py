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

from typing import NamedTuple
from uuid import UUID

from .erasure_rules import entity_ids_named
from .models import CorpusObjectInput, IdentitySource
from .records import REGISTRY, naming, record_inputs, record_type_of
from .validation import IntentError, reusable_recipes

MESSAGES = dict(
    missing_reasoning_input="Corpus input missing: {}",
    entity_recreation="A publication does not recreate an Entity deleted outside "
    "the lab: {}; pick another target or leave the mention unresolved",
)


def verified_description(row) -> IdentitySource | None:
    """The source's description as last verified: a replacement's previous
    one while it is pending or failed, otherwise the row's own when the
    ledger served it (`holds_served`). None for a first publication and for
    an erasure retry, whose description is new."""
    if row is None or row.description is None:
        return None
    if row.operation == "identity_replace" and row.state != "current":
        return IdentitySource.model_validate_json(row.plan["previous_description"])
    return row.description if row.holds_served else None


def corpus_entities(description) -> set[UUID]:
    """The reusable Entities a description names as existing or declares:
    its corpus inputs and its reusable recipes."""
    return {
        i.entity_id
        for i in description.inputs.values()
        if isinstance(i, CorpusObjectInput)
    } | set(reusable_recipes(description))


def lab_removed(rows, own=None, own_built=frozenset()) -> set[UUID]:
    """The Entities a lab operation removed, or may have: what each forget
    removed and each forgotten life's mention UUIDs; every reusable Entity
    of a forgotten life but those its forget found served
    (`Tombstone.served_entity_ids`), since a withdrawal or a failed attempt
    may have removed one before the forget found it gone;
    what a replacement planned to retire; and the recipes of a source that
    is not served. Less what a served source still builds, which no lab
    operation removes while it is served: `own_built` for `own`, the source
    being published, whose own attempt in flight leaves it unserved."""
    removed, built = set(), set(own_built)
    for row in rows:
        for tombstone in (row.tombstone, row.last_tombstone):
            if tombstone is not None:
                removed |= set(tombstone.removed_entity_ids)
                removed |= set(tombstone.all_mention_ids)
                removed |= tombstone.all_reusable_ids - set(tombstone.served_entity_ids)
        removed |= {UUID(key) for key in row.plan.get("retired_entities", {})}
        if row.description is None or (row.dataset, row.source) == own:
            continue
        if row.is_served:
            built |= set(reusable_recipes(row.description))
        else:
            removed |= set(row.description.entity_constructions)
    return removed - built


async def deleted_outside(graph, rows, source, verified) -> frozenset[UUID]:
    """The Entities deleted outside the lab, as the publication of `source`
    sees them. Its own row counts through `verified` alone, since an
    attempt in flight leaves it unserved."""
    own = (str(source.dataset_id), str(source.identity_data_id))
    own_built = set(reusable_recipes(verified)) if verified is not None else set()
    previous = next((r for r in rows if (r.dataset, r.source) == own), None)
    if previous is not None:
        own_built -= {UUID(k) for k in previous.plan.get("retired_entities", {})}
    named = set().union(
        *(
            corpus_entities(r.description)
            for r in rows
            if r.is_served and (r.dataset, r.source) != own
        ),
        corpus_entities(verified) if verified is not None else (),
    )
    candidates = named - lab_removed(rows, own, own_built)
    return frozenset([e for e in candidates if await graph.get_node(str(e)) is None])


class Part(NamedTuple):
    """A part of a description that cites or names an Entity: what it holds,
    and whether it cites the Entity as a corpus input."""

    held: object
    cites: bool


RECIPE = ("recipe",)


def touching(description, entity_id) -> dict:
    """Each part of the description that cites or names the Entity, by key:
    a record with its attribution, its producer and the inputs it cites; an
    unresolved group with the same; and the Entity's recipe."""
    keys = {
        k
        for k, i in description.inputs.items()
        if isinstance(i, CorpusObjectInput) and i.entity_id == entity_id
    }

    def held(part, inputs):
        return (
            part,
            description.producers[part.producer_ref],
            {i: description.inputs[i] for i in sorted(inputs)},
        )

    found = {}
    for key, inputs in record_inputs(description).items():
        if inputs & keys or entity_id in naming(description, key):
            kind = REGISTRY[record_type_of(description, key)]
            record = getattr(description, kind.field)[key]
            found[key] = Part(held(record, inputs), bool(inputs & keys))
    resolved = {d.group_ref for d in description.mention_resolutions.values()}
    for key, group in description.mention_groups.items():
        if key not in resolved and keys & set(group.input_refs):
            found[key] = Part(held(group, group.input_refs), True)
    if entity_id in description.entity_constructions:
        found[RECIPE] = Part(description.entity_constructions[entity_id], False)
    return found


def refusal(source, verified, entity_id) -> str | None:
    """Why a publication of `source` may not leave the Entity absent, or
    None: every part of `source` that cites or names it is as `verified`,
    the last verified description, has it. A new or changed part that cites
    it as a corpus input is `missing_reasoning_input`, as for any missing
    input; any other new or changed part would recreate it
    (`entity_recreation`)."""
    before = touching(verified, entity_id) if verified is not None else {}
    changed = [
        part
        for key, part in touching(source, entity_id).items()
        if before.get(key) != part
    ]
    if not changed:
        return None
    return (
        "missing_reasoning_input"
        if any(part.cites for part in changed)
        else "entity_recreation"
    )


async def left_absent(graph, rows, source, previous) -> frozenset[UUID]:
    """The Entities deleted outside the lab that a publication of `source`
    names and leaves absent: those whose citing and naming parts are all
    kept from the last verified description of `previous`, the source's
    row. Refuses any other (`refusal`). The publisher skips their recipes,
    edges and contributions, in the write and in its verification, and
    admission lets a kept decision cite them."""
    verified = verified_description(previous)
    named = await deleted_outside(graph, rows, source, verified)
    named &= entity_ids_named(source)
    for entity_id in sorted(named, key=str):
        if code := refusal(source, verified, entity_id):
            raise IntentError(code, MESSAGES[code].format(entity_id))
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
            code = "entity_recreation"
            raise IntentError(code, MESSAGES[code].format(entity_id))
