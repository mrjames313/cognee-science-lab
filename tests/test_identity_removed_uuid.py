"""A publication never writes an absent Entity whose UUID a lab record
proves removed: a forget's removed Entities or a replacement's planned
retirements. A re-add derives a new UUID for such an Entity (the user's
decision of 2026-10-26), so a retry, reconcile or replacement that wrote the
old one would split the Entity in two. Without a store."""

import json
from dataclasses import replace

import pytest
from cognee.infrastructure.databases.provenance import make_source_ref_key

from cognee_lab.identity.validation import IntentError
from test_identity_outside_deletion import (
    HELIOS,
    Graph,
    admit,
    readd_removed,
    forgotten_row,
    renamed,
    row_of,
    source_of,
)
from test_identity_readd_outside_deletion import (
    co_owner,
    dropped_helios,
    readd_writes,
    without_input,
)


def builders(source_payload):
    """A, whose forget removed Helios, and C, which builds Helios too and
    whose first attempt failed, so its refs were never on Helios."""
    a = without_input(source_payload)
    c = without_input(json.loads(co_owner(renamed(source_payload)).model_dump_json()))
    return a, c


async def test_a_failed_co_owner_retry_does_not_write_a_helios_a_forget_removed(
    source_payload,
):
    """The review's steps: forget A removes Helios; C's retry would write
    the old UUID that A's re-add replaces under a derived one."""
    a, c = builders(source_payload)
    rows = [
        forgotten_row(a, served=True, removed=(HELIOS,)),
        row_of(c, state="failed", verified_revision=0),
    ]
    with pytest.raises(IntentError) as refused:
        await admit(rows, c)
    assert refused.value.code == "entity_recreation"
    message = str(refused.value)
    assert str(HELIOS) in message and "never reused" in message
    assert "forget this source and re-add it" in message


async def test_a_retry_does_not_write_a_helios_a_replacement_retired(source_payload):
    a, c = builders(source_payload)
    replaced = row_of(
        dropped_helios(json.loads(a.model_dump_json())),
        plan=dict(operation="identity_replace", retired_entities={str(HELIOS): {}}),
    )
    rows = [replaced, row_of(c, state="failed", verified_revision=0)]
    with pytest.raises(IntentError) as refused:
        await admit(rows, c)
    assert refused.value.code == "entity_recreation"


async def test_a_present_entity_a_forget_once_removed_is_written(source_payload):
    """Only an absent Entity is a recreation: a present one gains a ref."""
    a, c = builders(source_payload)
    rows = [
        forgotten_row(a, served=True, removed=(HELIOS,)),
        row_of(c, state="failed", verified_revision=0),
    ]
    assert HELIOS in (await admit(rows, c, absent=())).entities


async def test_a_failed_first_publication_builds_an_entity_nobody_removed(
    source_payload,
):
    _, c = builders(source_payload)
    rows = [row_of(c, state="failed", verified_revision=0)]
    assert HELIOS in (await admit(rows, c)).entities


async def test_the_refused_source_is_forgotten_and_its_readd_derives_a_new_uuid(
    source_payload,
):
    """The remedy the refusal names: C's re-add builds Helios under a
    derived UUID, beside A's own."""
    a, c = builders(source_payload)
    rows = [
        forgotten_row(a, served=True, removed=(HELIOS,)),
        forgotten_row(c, served=False),
    ]
    readded = await readd_writes(rows, rows[1].tombstone, c)
    assert str(HELIOS) not in readded.model_dump_json()
    target = readded.mention_resolutions["r01"].target_entity_id
    assert readded.entity_constructions[target].name == "Helios controller"


async def test_an_entity_a_later_withdrawal_left_removed_waits_for_its_citers(
    source_payload,
):
    """A and D own Helios when A is forgotten, so A's forget keeps it; D's
    withdrawal then removes it, which no record shows. A's re-add replaces
    Helios, as the forget would now remove it, and waits while C, whose
    first attempt failed, still builds it: its retry would write the old
    UUID."""
    a, c = builders(source_payload)
    d = co_owner(renamed(source_payload))
    refs = [make_source_ref_key(s.dataset_id, s.identity_data_id) for s in (a, d)]
    plan = dict(entities={str(HELIOS): dict(type="Entity", refs=refs)})
    gone = forgotten_row(a, served=True)
    rows = [
        replace(gone, plan=dict(gone.plan, **plan)),
        row_of(d, state="withdrawn", plan=dict(operation="identity_withdraw")),
        row_of(c, state="failed", verified_revision=0),
    ]
    with pytest.raises(IntentError) as refused:
        await readd_removed(Graph(HELIOS), gone.tombstone, plan, rows, a)
    assert refused.value.code == "entity_recreation"
    assert [x["state"] for x in refused.value.details["citers"]] == [
        "withdrawn",
        "failed",
    ]
