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
   it is refused while a saved source still cites or builds it, then
   builds it under a derived UUID (Q2, `check_readd`).

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
from .validation import MISSING_INPUT, IntentError, reusable_recipes

MESSAGES = dict(
    missing_reasoning_input=MISSING_INPUT,
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


def lab_removed(rows, own=None, verified=None, *, unserved=True) -> set[UUID]:
    """The Entities a lab operation removed, or may have: what each forget
    removed and each forgotten life's mention UUIDs; every reusable Entity
    of a forgotten life but those its forget found served
    (`Tombstone.served_entity_ids`), since a withdrawal or a failed attempt
    may have removed one before the forget found it gone; what a
    replacement planned to retire; and, with `unserved`, the recipes of a
    source that is not served. Less what a served source still builds,
    which no lab operation removes while it is served. `own` is the source
    being published, whose attempt in flight leaves it unserved: it builds
    the recipes of `verified`, its last verified description, that it has
    not planned to retire. A re-add passes `unserved=False`: an unserved
    source that names the Entity is a live citer (`live_citers`), whose
    retry would publish it again."""
    removed, built = set(), set()
    for row in rows:
        for tombstone in (row.tombstone, row.last_tombstone):
            if tombstone is not None:
                removed |= set(tombstone.removed_entity_ids)
                removed |= set(tombstone.all_mention_ids)
                removed |= tombstone.all_reusable_ids - set(tombstone.served_entity_ids)
        retired = {UUID(key) for key in row.plan.get("retired_entities", {})}
        removed |= retired
        if (row.dataset, row.source) == own:
            if verified is not None:
                built |= set(reusable_recipes(verified)) - retired
        elif row.description is None:
            continue
        elif row.is_served:
            built |= set(reusable_recipes(row.description))
        elif unserved:
            removed |= set(row.description.entity_constructions)
    return removed - built


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
    candidates = named - lab_removed(rows, own, verified)
    return frozenset([e for e in candidates if await graph.get_node(str(e)) is None])


class Part(NamedTuple):
    """A part of a description that cites or names an Entity: what it holds,
    and whether it cites the Entity as a corpus input."""

    held: object
    cites: bool


def touching(description, entity_id) -> dict:
    """Each part of the description that cites or names the Entity, by key:
    a record with its attribution, its producer and the inputs it cites; an
    unresolved group with the same; and the Entity's recipe, under the
    Entity's UUID as entity_constructions keys it."""
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
        found[entity_id] = Part(description.entity_constructions[entity_id], False)
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


def live_citers(rows, entity_id) -> list[dict]:
    """The saved sources that still cite or build the Entity: each row not
    forgotten whose latest description names it (`entity_ids_named`), a
    pending or failed one included, or whose replacement in flight replaces
    a description that names it. Withheld and withdrawn rows count, in any
    dataset: a later retry or reconcile of one would publish the Entity
    again under its old UUID."""
    found = []
    for row in rows:
        if row.state == "forgotten" or row.description is None:
            continue
        held = [row.description]
        if row.operation == "identity_replace" and row.state in {"pending", "failed"}:
            held.append(
                IdentitySource.model_validate_json(row.plan["previous_description"])
            )
        if any(entity_id in entity_ids_named(d) for d in held):
            found.append(
                dict(
                    dataset_id=row.dataset, identity_data_id=row.source, state=row.state
                )
            )
    return found


def check_readd(source, cited: dict[UUID, list[dict]]):
    """A re-add whose files name an Entity deleted outside the lab that a
    saved source still cites or builds (`cited`, from `live_citers`) is
    refused (`entity_recreation`), naming each such source: the user's
    decision of 2026-10-25 for Q2. Once each is forgotten, or replaced
    without the Entity, the re-add replaces it under a derived UUID as it
    does an Entity a lab operation removed."""
    named = sorted(set(cited) & entity_ids_named(source), key=str)
    if not named:
        return
    citers = [dict(c, entity_id=str(e)) for e in named for c in cited[e]]
    listed = "; ".join(
        f"{c['identity_data_id']} in dataset {c['dataset_id']} ({c['state']})"
        for c in citers
    )
    raise IntentError(
        "entity_recreation",
        "A re-add does not recreate an Entity deleted outside the lab while a "
        f"saved source still cites or builds it: {', '.join(map(str, named))} "
        f"by {listed}. Forget those sources, or replace their decisions "
        "without the Entity, then re-add",
        details=dict(citers=citers),
    )
