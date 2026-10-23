"""Forget without a store: the Entities a forget removes and the readers it
revises, the fence on a source whose forget is unfinished, and the re-add's
derived UUIDs and admission."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from cognee_lab.identity.erasure_rules import (
    admit_readd,
    differs_from_forgotten,
    replacement_entity_id,
)
from cognee_lab.identity.fixture import FIXTURES
from cognee_lab.identity.erasure import impact
from cognee_lab.identity.forget_fixture import describe_readd
from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.retirement import refuse_retiring_inputs
from cognee_lab.identity.storage import PublicationRow
from cognee_lab.identity.validation import (
    IntentError,
    fresh_entity_id,
    fresh_mention_id,
    object_digest,
    text_digest,
    validate_uses,
)


def source_of(payload):
    return IdentitySource.model_validate_json(json.dumps(payload))


def row_of(source, state="current", plan=None):
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state=state,
        revision=source.revision,
        verified_revision=source.revision,
        attempt="attempt",
        description=source,
        tombstone=None,
        plan=plan or {"operation": "identity_publish"},
    )


def reader_of(source_payload, *, text=False, entity_id=None):
    """Another source whose r01 decision lists doc01's text, an Entity, or
    neither, as an input."""
    payload = json.loads(json.dumps(source_payload))
    payload["identity_data_id"] = str(uuid4())
    ours = dict(payload["inputs"]["doc01"])
    # The reader's own document is another one.
    payload["inputs"]["doc01"]["data_id"] = str(uuid4())
    if text:
        payload["inputs"]["doc01_text"] = ours
        payload["mention_resolutions"]["r01"]["input_refs"].append("doc01_text")
    if entity_id is not None:
        payload["inputs"]["read_entity"] = dict(
            kind="corpus_object",
            dataset_id=payload["dataset_id"],
            entity_id=str(entity_id),
            selected_fields=["name"],
            content_sha256=object_digest({"name": "x"}),
        )
        payload["mention_resolutions"]["r01"]["input_refs"].append("read_entity")
    return source_of(payload)


def owned_plan(source, entity, other_refs):
    """A forget plan whose one Entity is owned by this source and by
    `other_refs`."""
    own = f"source_ref:v1:{source.dataset_id}:{source.identity_data_id}"
    return dict(
        operation="identity_forget",
        entities={
            str(entity): dict(
                refs=[own, *other_refs], type="Entity", indexed_fields=["name"]
            )
        },
    )


def other_row(other, state):
    doc = other.inputs[other.original_input_ref]
    plan = {
        "current": {"operation": "identity_publish"},
        "failed_withdraw": {"operation": "identity_withdraw"},
        "withdrawn": {"operation": "identity_withdraw"},
        "failed_forget": {
            "operation": "identity_forget",
            "original_data_id": str(doc.data_id),
        },
        "forgotten": {
            "operation": "identity_forget",
            "original_data_id": str(doc.data_id),
        },
    }[state]
    row = row_of(
        other,
        state.removeprefix("failed_") if "failed" not in state else "failed",
        plan,
    )
    if state == "forgotten":
        return replace(row, description=None, tombstone=tomb(other))
    return row


def readers(found):
    """The sources an impact revises, with the inputs each decision cites."""
    return {
        d.identity_data_id: [c.consumed for r in d.decisions for c in r.citing]
        for d in found.dependents
    }


@pytest.mark.parametrize(
    "state, removed",
    [
        ("current", False),
        ("failed_withdraw", True),
        ("withdrawn", True),
        ("failed_forget", True),
        ("forgotten", True),
    ],
)
def test_an_entity_shared_only_with_a_retiring_owner_counts_as_removed(
    source_payload, state, removed
):
    """A reader of an Entity this source shares with another owner is a
    dependent of the forget only when that other owner is retired or
    retiring, because then the forget removes the Entity."""
    source = source_of(source_payload)
    other = reader_of(source_payload)
    entity = uuid4()
    reader = reader_of(source_payload, entity_id=entity)
    plan = owned_plan(
        source, entity, [f"source_ref:v1:{other.dataset_id}:{other.identity_data_id}"]
    )
    rows = [row_of(source), other_row(other, state), row_of(reader)]
    plan["revision"] = source.revision
    expected = {str(reader.identity_data_id): [str(entity)]} if removed else {}
    assert readers(impact(source, plan, rows)) == expected


def test_an_entity_owned_through_the_document_chunks_alone_is_removed(
    source_payload,
):
    source = source_of(source_payload)
    doc = source.inputs[source.original_input_ref]
    entity = uuid4()
    reader = reader_of(source_payload, entity_id=entity)
    plan = owned_plan(
        source, entity, [f"source_ref:v2:{doc.dataset_id}:{doc.data_id}:{uuid4()}"]
    )
    plan["revision"] = source.revision
    rows = [row_of(source), row_of(reader)]
    assert readers(impact(source, plan, rows)) == {
        str(reader.identity_data_id): [str(entity)]
    }


@pytest.mark.parametrize("state", ["failed", "pending"])
def test_a_new_consumer_of_a_source_whose_forget_is_unfinished_is_refused(
    source_payload, state
):
    source = source_of(source_payload)
    doc = source.inputs[source.original_input_ref]
    entity = uuid4()
    plan = dict(
        owned_plan(source, entity, []),
        original_data_id=str(doc.data_id),
    )
    for reader in (
        reader_of(source_payload, text=True),
        reader_of(source_payload, entity_id=entity),
    ):
        with pytest.raises(IntentError) as refused:
            refuse_retiring_inputs(reader, [row_of(source, state, plan)])
        assert refused.value.code == "retiring_source"
        assert [d["identity_data_id"] for d in refused.value.details["dependents"]] == [
            str(reader.identity_data_id)
        ]
        refuse_retiring_inputs(reader, [row_of(source, "current")])
        refuse_retiring_inputs(reader_of(source_payload), [row_of(source, state, plan)])


class AbsentGraph:
    async def get_node(self, node_id):
        return None


class OccupiedGraph:
    def __init__(self, present):
        self.present = {str(p) for p in present}

    async def get_node(self, node_id):
        return {"id": node_id} if str(node_id) in self.present else None


def chunks_of(source, text):
    from types import SimpleNamespace

    from cognee_lab.identity.models import ChunkInput

    return [
        SimpleNamespace(id=i.chunk_id, chunk_index=n, text=text[i.start : i.end])
        for n, i in enumerate(
            v for v in source.inputs.values() if isinstance(v, ChunkInput)
        )
    ]


TEXT = (FIXTURES / "source.txt").read_text()


HC = UUID("9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88")


def tomb(source, removed=()):
    return Tombstone.of(source, forgotten_at="t", removed_entity_ids=removed)


@pytest.mark.asyncio
async def test_a_readd_derives_every_group_from_the_next_revision(source_payload):
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(
        forgotten, tomb(forgotten), set(), text, chunks_of(forgotten, text)
    )
    assert readded.revision == forgotten.revision + 1
    for key, group in readded.mention_groups.items():
        assert group.entity_id == fresh_mention_id(
            forgotten.identity_data_id, readded.revision, key
        )
        assert group.entity_id != forgotten.mention_groups[key].entity_id
        assert group.entity_id in readded.entity_constructions
        assert group.occurrences == forgotten.mention_groups[key].occurrences
    assert set(readded.entity_constructions) ^ set(forgotten.entity_constructions) == {
        g.entity_id for g in readded.mention_groups.values()
    } | {g.entity_id for g in forgotten.mention_groups.values()}
    assert readded.mention_resolutions == forgotten.mention_resolutions
    assert readded.variant_assignments == forgotten.variant_assignments
    await admit_readd(AbsentGraph(), tomb(forgotten), readded, set())


@pytest.mark.asyncio
async def test_a_readd_derives_a_named_replacement_from_a_key_that_names_it(
    source_payload,
):
    """HC was owned by this source alone, so the forget removed it. The re-add
    does not recreate it under its old UUID. Variant v01 names HC, so its
    replacement derives from the next revision and that key, as any new
    reusable Entity does, and the variant follows."""
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(
        forgotten, tomb(forgotten), {HC}, text, chunks_of(forgotten, text)
    )
    new_hc = fresh_entity_id(forgotten.identity_data_id, 2, "v01")
    assert HC not in readded.entity_constructions
    assert readded.entity_constructions[new_hc] == forgotten.entity_constructions[HC]
    assert readded.variant_assignments["v01"].source_entity_id == new_hc
    await admit_readd(AbsentGraph(), tomb(forgotten), readded, {HC})

    kept = describe_readd(
        forgotten, tomb(forgotten), set(), text, chunks_of(forgotten, text)
    )
    assert HC in kept.entity_constructions
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), tomb(forgotten), kept, {HC})
    assert refused.value.code == "forgotten_uuid_reused"

    # The replaces form is only for an Entity nothing names.
    by_removed_uuid = replacement_entity_id(forgotten.identity_data_id, 2, HC)
    for wrong in (uuid4(), by_removed_uuid):
        underived = renamed_entity(readded, new_hc, wrong)
        with pytest.raises(IntentError) as refused:
            await admit_readd(AbsentGraph(), tomb(forgotten), underived, {HC})
        assert refused.value.code == "entity_uuid_not_derived"

    with pytest.raises(IntentError) as refused:
        await admit_readd(OccupiedGraph([new_hc]), tomb(forgotten), readded, {HC})
    assert refused.value.code == "entity_uuid_in_graph"


@pytest.mark.asyncio
async def test_a_readd_replaces_an_unnamed_entity_by_the_removed_uuid(source_payload):
    """No resolution or variant names a private singleton, so its replacement
    derives from the UUID it replaces."""
    payload = json.loads(json.dumps(source_payload))
    singleton = uuid4()
    payload["entity_constructions"][str(singleton)] = dict(
        name="doc01 instrument", description="Supported by this source only."
    )
    forgotten = source_of(payload)
    text = TEXT
    readded = describe_readd(
        forgotten, tomb(forgotten), {singleton}, text, chunks_of(forgotten, text)
    )
    new = replacement_entity_id(forgotten.identity_data_id, 2, singleton)
    assert singleton not in readded.entity_constructions
    assert (
        readded.entity_constructions[new] == forgotten.entity_constructions[singleton]
    )
    await admit_readd(AbsentGraph(), tomb(forgotten), readded, {singleton})

    underived = renamed_entity(readded, new, uuid4())
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), tomb(forgotten), underived, {singleton})
    assert refused.value.code == "entity_uuid_not_derived"


def test_a_readd_gives_two_removed_entities_one_key_names_separate_replacements(
    source_payload,
):
    """A and HC are both removed. v01 names both, r01 names A too, so A takes
    r01 and HC v01. When one variant is the only name of two removed
    Entities, no second key is free, and the describer refuses rather than
    merge them."""
    forgotten = source_of(source_payload)
    a = forgotten.mention_resolutions["r01"].target_entity_id
    readded = describe_readd(
        forgotten, tomb(forgotten), {a, HC}, TEXT, chunks_of(forgotten, TEXT)
    )
    identity = forgotten.identity_data_id
    v01 = readded.variant_assignments["v01"]
    assert v01.target_entity_id == fresh_entity_id(identity, 2, "r01")
    assert v01.source_entity_id == fresh_entity_id(identity, 2, "v01")

    payload = json.loads(json.dumps(source_payload))
    del payload["mention_resolutions"]["r01"]["target_entity_id"]
    payload["mention_resolutions"]["r01"]["status"] = "unresolved"
    payload["mention_resolutions"]["r01"]["explanation"] = None
    only_v01 = source_of(payload)
    with pytest.raises(IntentError) as refused:
        describe_readd(
            only_v01, tomb(only_v01), {a, HC}, TEXT, chunks_of(only_v01, TEXT)
        )
    assert refused.value.code == "entity_uuid_not_derived"


def renamed_entity(source, old, new):
    """The description with one Entity recipe moved to another UUID."""
    return source.model_copy(
        update={
            "entity_constructions": {
                (new if eid == old else eid): recipe
                for eid, recipe in source.entity_constructions.items()
            },
            "variant_assignments": {
                k: v.model_copy(
                    update={
                        end: new
                        for end in ("source_entity_id", "target_entity_id")
                        if getattr(v, end) == old
                    }
                )
                for k, v in source.variant_assignments.items()
            },
        }
    )


@pytest.mark.asyncio
async def test_a_readd_replaces_an_entity_a_later_forget_of_a_co_owner_removed(
    source_payload,
):
    """This source was forgotten while a co-owner kept the Entity. The
    co-owner's forget then removed it, and the co-owner was re-added, so the
    ledger shows a live owner again. The re-add still replaces the Entity,
    because the graph no longer holds it."""
    from cognee_lab.identity.retirement import readd_removed

    source = source_of(source_payload)
    other = reader_of(source_payload)
    entity = uuid4()
    doc = source.inputs[source.original_input_ref]
    plan = dict(
        owned_plan(
            source,
            entity,
            [f"source_ref:v1:{other.dataset_id}:{other.identity_data_id}"],
        ),
        original_data_id=str(doc.data_id),
    )
    rows = [row_of(source, "forgotten", plan), row_of(other, "current")]
    kept = tomb(source)
    assert await readd_removed(AbsentGraph(), kept, plan, rows) == {entity}
    assert await readd_removed(OccupiedGraph([entity]), kept, plan, rows) == set()


FORGET_GRAPH_METHODS = (
    "find_node_source_refs_by_dataset",
    "find_edge_source_refs_by_dataset",
    "get_node_delete_data",
    "get_edge_delete_data",
    "remove_node_source_refs",
    "remove_edge_source_refs",
    "delete_edge_triples",
    "delete_nodes",
    "add_edges",
)


@pytest.mark.asyncio
async def test_a_failed_forget_whose_plan_predates_stored_files_is_refused(
    source_payload,
):
    """A failed forget saved before plans recorded `stored_files` cannot be
    finished by this code. Its retry is refused before begin."""
    from types import SimpleNamespace

    from cognee_lab.identity.forget import forget

    source = source_of(source_payload)
    doc = source.inputs[source.original_input_ref]
    plan = dict(owned_plan(source, uuid4(), []), original_data_id=str(doc.data_id))
    row = row_of(source, "failed", plan)

    class Records:
        async def row(self, _):
            return row

        async def rows(self):
            return [row]

        async def begin(self, *_, **__):
            raise AssertionError("begin must not run")

    graph = type(
        "Graph", (), {name: lambda *_: None for name in FORGET_GRAPH_METHODS}
    )()
    publisher = SimpleNamespace(graph=graph, records=Records())
    with pytest.raises(IntentError) as refused:
        await forget(publisher, source, expected_revision=source.revision)
    assert refused.value.code == "recovery_plan"


@pytest.mark.asyncio
async def test_a_readd_with_the_forgotten_uuids_or_revision_is_refused(
    source_payload,
):
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(
        forgotten, tomb(forgotten), set(), text, chunks_of(forgotten, text)
    )

    same_ids = forgotten.model_copy(update={"revision": 2})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), tomb(forgotten), same_ids, set())
    assert refused.value.code == "fresh_uuid_reused"

    skipped = readded.model_copy(update={"revision": 3})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), tomb(forgotten), skipped, set())
    assert refused.value.code == "revision_sequence"

    wrong_derivation = describe_readd(
        forgotten,
        tomb(forgotten.model_copy(update={"revision": 5})),
        set(),
        text,
        chunks_of(forgotten, text),
    ).model_copy(update={"revision": 2})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), tomb(forgotten), wrong_derivation, set())
    assert refused.value.code == "fresh_uuid_not_derived"

    other = readded.model_copy(update={"identity_data_id": uuid4()})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), tomb(forgotten), other, set())
    assert refused.value.code == "source_changed"

    # A forgotten mention UUID returns in no role, here as a reusable recipe
    # a variant names, even when the forget's plan never held its node.
    payload = json.loads(readded.model_dump_json())
    mention = str(forgotten.mention_groups["g01"].entity_id)
    payload["entity_constructions"][mention] = dict(name="back", description="")
    payload["variant_assignments"]["v01"]["target_entity_id"] = mention
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), tomb(forgotten), source_of(payload), set())
    assert refused.value.code == "forgotten_uuid_reused"

    occupied = OccupiedGraph([readded.mention_groups["g01"].entity_id])
    with pytest.raises(IntentError) as refused:
        await admit_readd(occupied, tomb(forgotten), readded, set())
    assert refused.value.code == "fresh_uuid_in_graph"


def test_a_readd_reports_whether_its_text_and_decisions_differ(source_payload):
    """A re-add renames the source's own Entities and moves to the next
    revision, which is no difference. Other text is; so are another outcome,
    another variant endpoint and another recipe. How a decision was made
    (its producer and explanation) is not. The report never refuses."""
    forgotten = source_of(source_payload)
    tombstone = tomb(forgotten, [HC])
    readded = describe_readd(
        forgotten, tombstone, {HC}, TEXT, chunks_of(forgotten, TEXT)
    )
    assert HC not in readded.entity_constructions
    assert differs_from_forgotten(tombstone, readded) == dict(
        text=False, decisions=False
    )

    def changed(edit):
        payload = json.loads(readded.model_dump_json())
        edit(payload)
        return differs_from_forgotten(tombstone, source_of(payload))

    def other_text(p):
        p["inputs"]["doc01"]["text_sha256"] = text_digest(TEXT + " HC was serviced.")

    def unresolved(p):
        r01 = p["mention_resolutions"]["r01"]
        r01.pop("target_entity_id")
        r01["status"] = "unresolved"

    def swapped(p):
        v01 = p["variant_assignments"]["v01"]
        v01["source_entity_id"], v01["target_entity_id"] = (
            v01["target_entity_id"],
            v01["source_entity_id"],
        )

    def recipe(p):
        target = p["mention_resolutions"]["r01"]["target_entity_id"]
        p["entity_constructions"][target]["description"] = "Another controller."

    def provenance(p):
        p["producers"]["fixture"]["version"] = "0.2"
        p["mention_resolutions"]["r01"]["explanation"] = "Reviewed again."

    assert changed(other_text) == dict(text=True, decisions=False)
    for edit in (unresolved, swapped, recipe):
        assert changed(edit) == dict(text=False, decisions=True), edit.__name__
    assert changed(provenance) == dict(text=False, decisions=False)


def test_a_readd_reports_other_grouping_and_not_a_text_shift(source_payload):
    """g01 holds `The controller` and `it`, g02 holds `HC`. Dropping `it`,
    moving it to g02, or giving g01's `it` to g02 for g02's own `it`
    changes the grouping, which is a decision. Moving every occurrence by
    the same shift, as a prefix edit does, is not."""
    payload = json.loads(json.dumps(source_payload))
    g02 = dict(payload["mention_groups"]["g01"], entity_id=str(uuid4()))
    g02["occurrences"] = [dict(start=19, end=21, text="HC")]
    payload["mention_groups"]["g02"] = g02
    payload["entity_constructions"][g02["entity_id"]] = dict(
        name="HC", description="A mention group."
    )
    tombstone = tomb(source_of(payload))

    def differs(edit):
        edited = json.loads(json.dumps(payload))
        edit(edited["mention_groups"])
        return differs_from_forgotten(tombstone, source_of(edited))["decisions"]

    def dropped(groups):
        groups["g01"]["occurrences"].pop()

    def moved(groups):
        groups["g02"]["occurrences"].append(groups["g01"]["occurrences"].pop())

    def exchanged(groups):
        groups["g01"]["occurrences"][1].update(start=100, end=102)
        groups["g02"]["occurrences"][1].update(start=86, end=88)

    def shifted(groups):
        for group in groups.values():
            for o in group["occurrences"]:
                o["start"], o["end"] = o["start"] + 5, o["end"] + 5

    assert not differs(lambda groups: None)
    for edit in (dropped, moved):
        assert differs(edit), edit.__name__
    assert not differs(shifted)

    payload["mention_groups"]["g02"]["occurrences"].append(
        dict(start=100, end=102, text="it")
    )
    tombstone = tomb(source_of(payload))
    assert differs(exchanged)


async def test_a_tombstone_carries_the_uuids_of_every_forgotten_life(
    source_payload,
):
    """Forgotten, re-added and forgotten again, the source's second
    tombstone keeps its first life's mention UUID. A third life may not use
    it in any role, and validate_uses counts it."""
    life1 = source_of(source_payload)
    first = tomb(life1)
    life2 = describe_readd(life1, first, set(), TEXT, chunks_of(life1, TEXT))
    second = tomb(life2).carrying(first)
    old = life1.mention_groups["g01"].entity_id
    assert second.earlier_mention_ids == [old]
    assert second.mention_ids == {"g01": life2.mention_groups["g01"].entity_id}
    assert second.earlier_entity_ids == []
    assert old in second.used_entity_ids
    assert tomb(life2).carrying(None) == tomb(life2)

    life3 = describe_readd(life1, second, set(), TEXT, chunks_of(life1, TEXT))
    assert life3.revision == 3
    await admit_readd(AbsentGraph(), second, life3, set())

    payload = json.loads(life3.model_dump_json())
    payload["inputs"]["back"] = dict(
        kind="corpus_object",
        dataset_id=payload["dataset_id"],
        entity_id=str(old),
        selected_fields=["name"],
        content_sha256=object_digest({"name": "x"}),
    )
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), second, source_of(payload), set())
    assert refused.value.code == "forgotten_uuid_reused"

    new = life3.mention_groups["g01"].entity_id
    payload = json.loads(life3.model_dump_json().replace(str(new), str(old)))
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), second, source_of(payload), set())
    assert refused.value.code == "fresh_uuid_reused"

    other = json.loads(json.dumps(source_payload))
    other["identity_data_id"] = str(uuid4())
    with pytest.raises(IntentError) as refused:
        validate_uses([second, source_of(other)])
    assert refused.value.code == "incompatible_group"


async def test_a_second_readd_replaces_what_the_first_forget_removed(source_payload):
    """The caller's file still names the private singleton by its first
    UUID, which the first forget removed and the first re-add replaced. The
    second forget removes the replacement. The second re-add must replace
    the first UUID too, since it is gone, and may not bring it back."""
    from cognee_lab.identity.retirement import readd_removed

    payload = json.loads(json.dumps(source_payload))
    singleton = uuid4()
    payload["entity_constructions"][str(singleton)] = dict(
        name="doc01 instrument", description="Supported by this source only."
    )
    caller = source_of(payload)
    first = tomb(caller, [singleton])
    life2 = describe_readd(caller, first, {singleton}, TEXT, chunks_of(caller, TEXT))
    second_singleton = replacement_entity_id(caller.identity_data_id, 2, singleton)
    second = tomb(life2, [second_singleton]).carrying(first)
    assert second.earlier_entity_ids == [singleton]
    own = f"source_ref:v1:{caller.dataset_id}:{caller.identity_data_id}"
    plan = dict(
        entities={
            str(second_singleton): dict(refs=[own], type="Entity", indexed_fields=[])
        }
    )
    removed = await readd_removed(AbsentGraph(), second, plan, [])
    assert removed == {second_singleton, singleton}
    assert await readd_removed(OccupiedGraph([singleton]), second, plan, []) == {
        second_singleton
    }

    life3 = describe_readd(caller, second, removed, TEXT, chunks_of(caller, TEXT))
    third_singleton = replacement_entity_id(caller.identity_data_id, 3, singleton)
    assert third_singleton in life3.entity_constructions
    assert singleton not in life3.entity_constructions
    await admit_readd(AbsentGraph(), second, life3, removed)
    back = renamed_entity(life3, third_singleton, singleton)
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), second, back, removed)
    assert refused.value.code == "forgotten_uuid_reused"


async def test_admission_counts_a_readded_source_earlier_forgotten_lives(
    source_payload,
):
    """While a re-added source lives again, the UUIDs of its forgotten
    lives stay its own: another source may not take one for a mention."""
    from test_identity_dependencies import admitting_publisher, own_chunks

    source = source_of(source_payload)
    earlier = json.loads(json.dumps(source_payload))
    earlier["identity_data_id"] = str(uuid4())
    life1 = source_of(earlier)
    life2 = describe_readd(life1, tomb(life1), set(), TEXT, chunks_of(life1, TEXT))
    entity = str(source.inputs["existing_A"].entity_id)
    publisher = await admitting_publisher({entity: dict(type="Entity", name="A")})
    saved = [row_of(life2)]

    async def rows(dataset=None):
        return saved

    publisher.records.rows = rows
    await publisher.admit_inputs(source, {"doc01": TEXT}, own_chunks(source))
    saved[0] = replace(saved[0], last_tombstone=tomb(life1))
    with pytest.raises(IntentError) as refused:
        await publisher.admit_inputs(source, {"doc01": TEXT}, own_chunks(source))
    assert refused.value.code == "incompatible_group"
