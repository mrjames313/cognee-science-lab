"""A publication never writes an absent Entity the removal record lists. A
re-add derives a new UUID for such an Entity (the user's decision of
2026-10-26), so a retry, reconcile or replacement that wrote the old one
would split the Entity in two. The record outlives every later operation,
which may overwrite the plan or the tombstone that once listed the
removal. Without a store."""

import json
from dataclasses import replace

import pytest
from cognee.infrastructure.databases.provenance import make_source_ref_key

from cognee_lab.identity.validation import IntentError
from test_identity_outside_deletion import (
    HELIOS,
    Graph,
    admit,
    forget_of,
    readd_removed,
    readded,
    forgotten_row,
    renamed,
    row_of,
)
from test_identity_readd_outside_deletion import (
    PLAN,
    co_owner,
    dropped_helios,
    readd_writes,
    without_input,
)

FORGOT = {HELIOS: "identity_forget"}
RETIRED = {HELIOS: "identity_replace"}


def builders(source_payload):
    """A, whose forget removed Helios, and C, which builds Helios too and
    whose first attempt failed, so its refs were never on Helios."""
    a = without_input(source_payload)
    c = without_input(json.loads(co_owner(renamed(source_payload)).model_dump_json()))
    return a, c


def failed_first(source):
    return row_of(source, state="failed", verified_revision=0)


async def refusal(rows, source, removed):
    with pytest.raises(IntentError) as refused:
        await admit(rows, source, removed=removed)
    assert refused.value.code == "entity_recreation"
    return str(refused.value)


async def test_a_failed_co_owner_retry_does_not_write_a_helios_a_forget_removed(
    source_payload,
):
    """Forget A removes Helios; C's retry would write the old UUID that A's
    re-add replaces under a derived one. A failed first publication may
    only be forgotten and re-added."""
    a, c = builders(source_payload)
    rows = [forgotten_row(a, removed=(HELIOS,)), failed_first(c)]
    message = await refusal(rows, c, FORGOT)
    assert str(HELIOS) in message and "never reused" in message
    assert "Forget this source and re-add it" in message
    assert "Replace" not in message
    assert HELIOS in (await admit(rows, c)).entities


async def test_the_remedy_follows_the_refused_source_state(source_payload):
    """A current source may replace its decisions; a new one picks another
    target in its files."""
    a, c = builders(source_payload)
    gone = forgotten_row(a, removed=(HELIOS,))
    served = await refusal([gone, row_of(c)], c, FORGOT)
    assert "Replace the decisions without it" in served
    fresh = await refusal([gone], c, FORGOT)
    assert fresh.endswith("Pick another target or leave the mention unresolved")


async def test_a_retirement_outlives_the_plan_that_listed_it(source_payload):
    """The review's HIGH steps: A and B build Helios; C's first attempt
    failed; B is forgotten; A's replacement retires Helios, which goes; B
    is re-added under a derived UUID, without waiting for C; A's next
    operation overwrites its plan. C's retry would write the old UUID."""
    a, c = builders(source_payload)
    b = without_input(json.loads(co_owner(renamed(source_payload)).model_dump_json()))
    gone_b = forgotten_row(b)
    a_reconciled = row_of(dropped_helios(json.loads(a.model_dump_json())))
    rows = [gone_b, a_reconciled, failed_first(c)]
    found = await readd_removed(Graph(HELIOS), gone_b.tombstone, PLAN, rows, b, RETIRED)
    assert HELIOS in found
    b_live = row_of(readded(b), last_tombstone=gone_b.tombstone)
    await refusal([b_live, a_reconciled, failed_first(c)], c, RETIRED)


async def test_a_forget_removal_outlives_the_next_forget(source_payload):
    """The review's MEDIUM steps: A's forget removes Helios; A is re-added
    under a derived Helios and forgotten again, which leaves a tombstone
    without the first removal. C's retry would write the old UUID."""
    a, c = builders(source_payload)
    first = forgotten_row(a, removed=(HELIOS,))
    second = forget_of(readded(a), earlier=first.tombstone)
    await refusal([second, failed_first(c)], c, FORGOT)


async def test_a_present_entity_a_forget_once_removed_is_written(source_payload):
    """Only an absent Entity is a recreation: a present one gains a ref."""
    a, c = builders(source_payload)
    rows = [forgotten_row(a, removed=(HELIOS,)), failed_first(c)]
    assert HELIOS in (await admit(rows, c, absent=(), removed=FORGOT)).entities


async def test_the_refused_source_is_forgotten_and_its_readd_derives_a_new_uuid(
    source_payload,
):
    """The remedy the refusal names: C's re-add builds Helios under a
    derived UUID, beside A's own."""
    a, c = builders(source_payload)
    rows = [forgotten_row(a, removed=(HELIOS,)), forgotten_row(c)]
    readded_c = await readd_writes(rows, rows[1].tombstone, c, FORGOT)
    assert str(HELIOS) not in readded_c.model_dump_json()
    target = readded_c.mention_resolutions["r01"].target_entity_id
    assert readded_c.entity_constructions[target].name == "Helios controller"


async def test_a_withdrawal_removal_waits_for_its_citers(source_payload):
    """A and D own Helios when A is forgotten, so A's forget keeps it; D's
    withdrawal then removes it and records the removal. A's re-add replaces
    Helios, as the forget would now remove it, and waits while C, whose
    first attempt failed, still builds it: a withdrawal's removal waits for
    its citers (the user's decision of 2026-10-26)."""
    a, c = builders(source_payload)
    d = co_owner(renamed(source_payload))
    refs = [make_source_ref_key(s.dataset_id, s.identity_data_id) for s in (a, d)]
    plan = dict(entities={str(HELIOS): dict(type="Entity", refs=refs)})
    gone = forgotten_row(a)
    rows = [
        replace(gone, plan=dict(gone.plan, **plan)),
        row_of(d, state="withdrawn", plan=dict(operation="identity_withdraw")),
        failed_first(c),
    ]
    withdrew = {HELIOS: "identity_withdraw"}
    with pytest.raises(IntentError) as refused:
        await readd_removed(Graph(HELIOS), gone.tombstone, plan, rows, a, withdrew)
    assert refused.value.code == "entity_recreation"
    assert [x["state"] for x in refused.value.details["citers"]] == [
        "withdrawn",
        "failed",
    ]
    await refusal(rows, c, withdrew)
