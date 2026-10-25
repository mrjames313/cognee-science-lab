"""An Entity deleted outside the lab, without a store: which absent
Entities count as deleted outside the lab, the relaxed corpus check, the
refusal to recreate one, the last verified description a kept decision is
compared with, and the re-add refusal."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from cognee_lab.identity.admission import check_corpus_inputs_exist
from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.outside_deletion import (
    check_no_recreation,
    check_readd,
    deleted_outside,
    verified_description,
)
from cognee_lab.identity.publish import present_edges
from cognee_lab.identity.storage import PublicationRow
from cognee_lab.identity.validation import IntentError

HELIOS = UUID("8b4bff50-907b-56b6-bc80-3b0a7018714a")


class Graph:
    """Every node is present but the absent ones."""

    def __init__(self, *absent):
        self.absent = {str(a) for a in absent}

    async def get_node(self, node_id):
        return None if str(node_id) in self.absent else {"id": node_id}


def source_of(payload):
    return IdentitySource.model_validate_json(json.dumps(payload))


def row_of(source, state="current", plan=None, verified_revision=None, **fields):
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state=state,
        revision=source.revision,
        verified_revision=(
            source.revision if verified_revision is None else verified_revision
        ),
        attempt="attempt",
        description=source,
        tombstone=None,
        plan=plan or {"operation": "identity_publish"},
        **fields,
    )


def unresolved_r01(payload):
    """doc01 after replace-decision r01: g01 unresolved, without the input."""
    changed = json.loads(json.dumps(payload))
    changed["revision"] = 2
    changed["mention_resolutions"]["r01"] = dict(
        group_ref="g01",
        input_refs=["doc01"],
        producer_ref=changed["mention_resolutions"]["r01"]["producer_ref"],
        status="unresolved",
    )
    return changed


def other_reader(payload):
    """Another served source that cites Helios as a corpus input."""
    other = json.loads(json.dumps(payload))
    other["identity_data_id"] = str(uuid4())
    other["inputs"]["doc01"]["data_id"] = str(uuid4())
    return source_of(other)


def reader_only(payload):
    """Another served source whose r01, left unresolved, cites Helios as a
    corpus input; it declares no recipe of Helios."""
    reader = json.loads(json.dumps(payload))
    reader["identity_data_id"] = str(uuid4())
    reader["inputs"]["doc01"]["data_id"] = str(uuid4())
    reader["mention_resolutions"]["r01"] = dict(
        group_ref="g01",
        input_refs=["doc01", "existing_A"],
        producer_ref=reader["mention_resolutions"]["r01"]["producer_ref"],
        status="unresolved",
    )
    del reader["variant_assignments"]["v01"]
    del reader["entity_constructions"][str(HELIOS)]
    return source_of(reader)


def forgotten_row(source, served, removed=()):
    """The row a forget left: `served` says whether the source was served
    when it was forgotten, as the forget's plan records it."""
    tombstone = Tombstone.of(source, forgotten_at="now", removed_entity_ids=removed)
    return replace(
        row_of(
            source,
            state="forgotten",
            plan=dict(operation="identity_forget", served=served),
        ),
        description=None,
        tombstone=tombstone,
    )


async def test_an_absent_entity_a_served_source_names_is_deleted_outside(
    source_payload,
):
    source = source_of(source_payload)
    rows = [row_of(source)]
    assert await deleted_outside(Graph(HELIOS), rows, source, source) == {HELIOS}
    assert await deleted_outside(Graph(), rows, source, source) == frozenset()


async def test_an_entity_a_forget_removed_is_not_deleted_outside(source_payload):
    """A forget, and a forget whose dependents are still unrevised: the
    dependent still cites the Entity its tombstone lists as removed."""
    forgotten = source_of(source_payload)
    tombstone = Tombstone.of(forgotten, forgotten_at="now", removed_entity_ids=[HELIOS])
    gone = replace(
        row_of(forgotten, state="forgotten"), description=None, tombstone=tombstone
    )
    reader = reader_only(source_payload)
    rows = [gone, row_of(reader)]
    assert await deleted_outside(Graph(HELIOS), rows, reader, reader) == frozenset()


async def test_an_entity_a_withdrawn_sole_owner_declared_is_not_deleted_outside(
    source_payload,
):
    owner = source_of(source_payload)
    reader = reader_only(source_payload)
    rows = [row_of(owner, state="withdrawn"), row_of(reader)]
    assert await deleted_outside(Graph(HELIOS), rows, reader, reader) == frozenset()


async def test_what_a_failed_replacement_retires_is_not_deleted_outside(
    source_payload,
):
    """The retry of a failed replacement that retired the Entity before it
    failed: its saved plan lists it."""
    old = source_of(source_payload)
    new = source_of(unresolved_r01(source_payload))
    plan = dict(
        operation="identity_replace",
        previous_description=old.model_dump_json(),
        retired_entities={str(HELIOS): {}},
    )
    rows = [row_of(new, state="failed", plan=plan, verified_revision=1)]
    verified = verified_description(rows[0])
    assert verified == old
    assert await deleted_outside(Graph(HELIOS), rows, new, verified) == frozenset()


async def test_a_kept_citer_may_cite_an_entity_deleted_outside(source_payload):
    """replace-decision r01 while v01, unchanged, still cites Helios."""
    old = source_of(source_payload)
    new = source_of(unresolved_r01(source_payload))
    await check_corpus_inputs_exist(Graph(HELIOS), new, old, frozenset({HELIOS}))
    assert check_no_recreation(new, old, frozenset({HELIOS})) == {HELIOS}


async def test_a_changed_or_new_citer_of_an_entity_deleted_outside_is_refused(
    source_payload,
):
    old = source_of(source_payload)
    changed = json.loads(json.dumps(source_payload))
    changed["variant_assignments"]["v01"]["input_refs"] = ["existing_A"]
    added = json.loads(json.dumps(source_payload))
    added["variant_assignments"]["v02"] = dict(
        added["variant_assignments"]["v01"], producer_ref="review_v02"
    )
    added["producers"]["review_v02"] = added["producers"][
        added["variant_assignments"]["v01"]["producer_ref"]
    ]
    for payload in (changed, added):
        with pytest.raises(IntentError) as refused:
            await check_corpus_inputs_exist(
                Graph(HELIOS), source_of(payload), old, frozenset({HELIOS})
            )
        assert refused.value.code == "missing_reasoning_input"


async def test_a_missing_input_is_refused_without_a_verified_description_or_outside(
    source_payload,
):
    source = source_of(source_payload)
    for verified, outside in [(None, {HELIOS}), (source, frozenset())]:
        with pytest.raises(IntentError) as refused:
            await check_corpus_inputs_exist(
                Graph(HELIOS), source, verified, frozenset(outside)
            )
        assert refused.value.code == "missing_reasoning_input"


def test_a_changed_decision_naming_an_entity_deleted_outside_is_refused(
    source_payload,
):
    """r01 retargeted at Helios under another producer: a publication would
    recreate it."""
    old = source_of(unresolved_r01(source_payload))
    retargeted = source_of(source_payload)
    with pytest.raises(IntentError) as refused:
        check_no_recreation(retargeted, old, frozenset({HELIOS}))
    assert refused.value.code == "entity_recreation"


def test_the_verified_description_follows_the_row(source_payload):
    old = source_of(source_payload)
    new = source_of(unresolved_r01(source_payload))
    replacing = dict(
        operation="identity_replace", previous_description=old.model_dump_json()
    )
    assert verified_description(None) is None
    assert verified_description(row_of(old)) == old
    assert verified_description(row_of(old, state="withdrawn")) == old
    assert verified_description(row_of(new, "pending", replacing, 1)) == old
    assert verified_description(row_of(new, "failed", replacing, 1)) == old
    assert verified_description(row_of(old, "pending")) == old
    assert verified_description(row_of(old, "pending", verified_revision=0)) is None
    erasure = dict(operation="identity_publish", erased_from=["{}"])
    assert verified_description(row_of(old, "failed", erasure)) is None


def test_edges_to_an_entity_left_absent_are_not_written(source_payload):
    source = source_of(source_payload)
    assert len(present_edges(source, frozenset())) == 2
    assert present_edges(source, frozenset({HELIOS})) == []


async def test_a_readd_naming_an_entity_deleted_outside_is_refused(source_payload):
    """Helios was deleted outside the lab while its source was served, then
    the source was forgotten."""
    forgotten = source_of(source_payload)
    gone = forgotten_row(forgotten, served=True)
    tombstone = gone.tombstone
    with pytest.raises(IntentError) as refused:
        await check_readd(Graph(HELIOS), tombstone, forgotten, [gone])
    assert refused.value.code == "entity_recreation"
    await check_readd(Graph(), tombstone, forgotten, [gone])
    removed = Tombstone.of(
        other_reader(source_payload), forgotten_at="now", removed_entity_ids=[HELIOS]
    )
    other = replace(gone, source=str(uuid4()), tombstone=removed)
    await check_readd(Graph(HELIOS), tombstone, forgotten, [gone, other])


@pytest.mark.xfail(
    strict=True,
    reason="lab_removed counts a co-owner's or a forgotten owner's recipes wrongly",
)
async def test_an_entity_a_served_source_builds_is_deleted_outside_after_a_co_owner_left(
    source_payload,
):
    """doc03, which declares doc01's Helios recipe too, is withdrawn; then
    Helios is deleted outside the lab. doc01 still builds it."""
    doc01 = source_of(source_payload)
    co_owner = other_reader(source_payload)
    rows = [row_of(doc01), row_of(co_owner, state="withdrawn")]
    assert await deleted_outside(Graph(HELIOS), rows, doc01, doc01) == {HELIOS}
    failed = replace(rows[1], state="failed", verified_revision=0)
    assert await deleted_outside(Graph(HELIOS), [rows[0], failed], doc01, doc01) == {
        HELIOS
    }


@pytest.mark.xfail(
    strict=True,
    reason="lab_removed counts a co-owner's or a forgotten owner's recipes wrongly",
)
async def test_an_entity_a_withdrawal_removed_stays_lab_removed_after_the_forget(
    source_payload,
):
    """The owner, the only one to declare Helios, is withdrawn, which
    removes Helios, then forgotten: the forget finds Helios gone and does
    not list it as removed. Its reader still cites Helios."""
    owner = source_of(source_payload)
    reader = reader_only(source_payload)
    rows = [forgotten_row(owner, served=False), row_of(reader)]
    assert await deleted_outside(Graph(HELIOS), rows, reader, reader) == frozenset()
    with pytest.raises(IntentError) as refused:
        await check_corpus_inputs_exist(
            Graph(HELIOS),
            reader,
            reader,
            await deleted_outside(Graph(HELIOS), rows, reader, reader),
        )
    assert refused.value.code == "missing_reasoning_input"
    await check_readd(Graph(HELIOS), rows[0].tombstone, owner, rows)
