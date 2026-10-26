"""A re-add whose files name an Entity deleted outside the lab, without a
store: refused while a saved source still cites or builds it, naming each
one; once each is forgotten or replaced without it, the re-add replaces it
under a derived UUID and never writes the old one (the user's Q2 remedy of
2026-10-25)."""

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from cognee_lab.identity.erasure_rules import admit_readd
from cognee_lab.identity.forget_fixture import describe_readd
from cognee_lab.identity.retirement import readd_removed
from cognee_lab.identity.validation import IntentError
from test_identity_forget import TEXT, OccupiedGraph, chunks_of
from test_identity_outside_deletion import (
    HELIOS,
    Graph,
    forgotten_row,
    payload_with,
    reader_only,
    row_of,
    source_of,
    unresolved_r01,
)

PLAN = dict(entities={})


def without_input(payload):
    """doc01's own file with its corpus input of Helios dropped: the user's
    edit before a re-add, since a re-add may not cite a removed Entity."""
    changed = json.loads(json.dumps(payload))
    del changed["inputs"]["existing_A"]
    for record in (
        *changed["mention_resolutions"].values(),
        *changed["variant_assignments"].values(),
    ):
        record["input_refs"] = [k for k in record["input_refs"] if k != "existing_A"]
    return source_of(changed)


def co_owner(payload, dataset=None):
    """Another source that builds Helios and resolves its r01 to it, in
    `dataset` when given."""
    other = json.loads(json.dumps(payload))
    other["identity_data_id"] = str(uuid4())
    other["inputs"]["doc01"]["data_id"] = str(uuid4())
    if dataset is not None:
        other["dataset_id"] = dataset
        for item in other["inputs"].values():
            if "dataset_id" in item:
                item["dataset_id"] = dataset
    return source_of(other)


def dropped_helios(payload):
    """A source after replace-decision r01 and v01: no recipe, decision or
    input names Helios."""

    def drop(p):
        p["revision"] = 3
        del p["variant_assignments"]["v01"]
        del p["entity_constructions"][str(HELIOS)]
        p["inputs"].pop("existing_A", None)

    return payload_with(unresolved_r01(payload), drop)


async def test_the_refusal_names_every_live_citer_with_its_dataset_and_state(
    source_payload,
):
    """A served reader, a withdrawn co-owner, a pending publication in
    another dataset, and a failed replacement whose new description drops
    Helios but whose previous one names it. A forgotten citer does not
    count."""
    caller = without_input(source_payload)
    gone = forgotten_row(caller, served=True)
    reader = reader_only(source_payload)
    withdrawn = co_owner(source_payload)
    elsewhere = co_owner(source_payload, dataset=str(uuid4()))
    replacing = co_owner(source_payload)
    dropped = replace(
        row_of(dropped_helios(json.loads(replacing.model_dump_json()))),
        state="failed",
        verified_revision=1,
        plan=dict(
            operation="identity_replace",
            previous_description=replacing.model_dump_json(),
        ),
    )
    forgotten = forgotten_row(co_owner(source_payload), served=True)
    rows = [
        gone,
        row_of(reader),
        row_of(withdrawn, state="withdrawn"),
        row_of(elsewhere, state="pending", verified_revision=0),
        dropped,
        forgotten,
    ]
    with pytest.raises(IntentError) as refused:
        await readd_removed(Graph(HELIOS), gone.tombstone, PLAN, rows, caller)
    assert refused.value.code == "entity_recreation"
    named = [
        (c["identity_data_id"], c["dataset_id"], c["state"])
        for c in refused.value.details["citers"]
    ]
    assert named == [
        (str(reader.identity_data_id), str(reader.dataset_id), "current"),
        (str(withdrawn.identity_data_id), str(withdrawn.dataset_id), "withdrawn"),
        (str(elsewhere.identity_data_id), str(elsewhere.dataset_id), "pending"),
        (dropped.source, dropped.dataset, "failed"),
    ]
    message = str(refused.value)
    for identity, dataset, state in named:
        assert f"{identity} in dataset {dataset} ({state})" in message
    assert "Forget those sources, or replace their decisions" in message


async def test_a_readd_that_does_not_name_the_entity_is_not_refused(source_payload):
    caller = without_input(source_payload)
    gone = forgotten_row(caller, served=True)
    rows = [gone, row_of(reader_only(source_payload))]
    unnamed = dropped_helios(json.loads(caller.model_dump_json()))
    assert HELIOS in await readd_removed(
        Graph(HELIOS), gone.tombstone, PLAN, rows, unnamed
    )


async def readd_writes(rows, tombstone, caller):
    """The re-add described from the caller's file, admitted against the
    tombstone: what `forget_fixture.readd` and `Publisher.admit_readd` do
    before any write, both from `readd_removed`."""
    graph = OccupiedGraph(tombstone.all_reusable_ids - {HELIOS})
    removed = await readd_removed(graph, tombstone, PLAN, rows, caller)
    source = describe_readd(caller, tombstone, removed, TEXT, chunks_of(caller, TEXT))
    assert await readd_removed(graph, tombstone, PLAN, rows, source) == removed
    await admit_readd(graph, tombstone, source, removed)
    return source


async def test_once_the_citers_are_forgotten_the_readd_derives_a_new_uuid(
    source_payload,
):
    caller = without_input(source_payload)
    gone = forgotten_row(caller, served=True)
    reader = reader_only(source_payload)
    with pytest.raises(IntentError):
        await readd_writes([gone, row_of(reader)], gone.tombstone, caller)
    rows = [gone, forgotten_row(reader, served=True)]
    source = await readd_writes(rows, gone.tombstone, caller)
    assert HELIOS not in source.entity_constructions
    assert str(HELIOS) not in source.model_dump_json()
    target = source.mention_resolutions["r01"].target_entity_id
    assert source.entity_constructions[target].name == "Helios controller"


async def test_once_the_citer_is_replaced_without_it_the_readd_derives_a_new_uuid(
    source_payload,
):
    caller = without_input(source_payload)
    gone = forgotten_row(caller, served=True)
    owner = co_owner(source_payload)
    with pytest.raises(IntentError):
        await readd_writes([gone, row_of(owner)], gone.tombstone, caller)
    replaced = row_of(dropped_helios(json.loads(owner.model_dump_json())))
    source = await readd_writes([gone, replaced], gone.tombstone, caller)
    assert str(HELIOS) not in source.model_dump_json()


async def test_a_readd_still_citing_the_entity_is_refused_once_nothing_else_does(
    source_payload,
):
    """The caller's file keeps its corpus input of Helios: the re-add may
    not cite a removed Entity."""
    caller = source_of(source_payload)
    gone = forgotten_row(caller, served=True)
    with pytest.raises(IntentError) as refused:
        await readd_writes([gone], gone.tombstone, caller)
    assert refused.value.code == "forgotten_uuid_reused"


async def test_two_co_owners_readded_separately_derive_two_uuids(source_payload):
    """Case 10, kept as the user's review found it: each re-add derives its
    replacement from its own identity source, so one Entity becomes two."""
    first = without_input(source_payload)
    second = without_input(json.loads(co_owner(source_payload).model_dump_json()))
    rows = [forgotten_row(first, served=True), forgotten_row(second, served=True)]
    a = await readd_writes(rows, rows[0].tombstone, first)
    b = await readd_writes(rows, rows[1].tombstone, second)
    one = a.mention_resolutions["r01"].target_entity_id
    two = b.mention_resolutions["r01"].target_entity_id
    assert one != two
    assert a.entity_constructions[one] == b.entity_constructions[two]
