"""Forget: the dependents check, the re-add admission and the ownership rules
that need no store."""

import json
from uuid import UUID, uuid4

import pytest

from cognee_lab.identity.admission import admit_readd, replacement_entity_id
from cognee_lab.identity.fixture import FIXTURES
from cognee_lab.identity.forget import refuse_dependents
from cognee_lab.identity.forget_fixture import describe_readd
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.retirement import dependents, refuse_retiring_inputs
from cognee_lab.identity.validation import IntentError, fresh_mention_id, object_digest


def source_of(payload):
    return IdentitySource.model_validate_json(json.dumps(payload))


def row_of(source, state="current", plan=None):
    return dict(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state=state,
        revision=source.revision,
        verified_revision=source.revision,
        description=source.model_dump_json(),
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


def test_a_source_that_consumed_the_text_is_a_dependent_unless_retired(
    source_payload,
):
    source = source_of(source_payload)
    reader = reader_of(source_payload, text=True)
    doc = source.inputs[source.original_input_ref]
    found = dependents(source, [row_of(source), row_of(reader)])
    assert found == [
        dict(
            dataset_id=str(reader.dataset_id),
            identity_data_id=str(reader.identity_data_id),
            input_ref="doc01_text",
            kind="source_text",
            consumed=str(doc.data_id),
        )
    ]
    for state in ("withdrawn", "forgotten"):
        assert dependents(source, [row_of(reader, state)]) == []
    assert dependents(source, [row_of(reader, "failed")]) == found
    # A text that is a different document, even if the same bytes, is not ours.
    assert dependents(source, [row_of(reader_of(source_payload))]) == []


def test_an_entity_is_a_dependency_only_while_this_source_alone_owns_it(
    source_payload,
):
    source = source_of(source_payload)
    entity = uuid4()
    reader = reader_of(source_payload, entity_id=entity)
    rows = [row_of(reader)]
    assert dependents(source, rows) == []
    found = dependents(source, rows, sole_owned={entity})
    assert [(d["input_ref"], d["kind"], d["consumed"]) for d in found] == [
        ("read_entity", "corpus_object", str(entity))
    ]


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
    return row_of(
        other,
        state.removeprefix("failed_") if "failed" not in state else "failed",
        plan,
    )


@pytest.mark.parametrize(
    "state, refused",
    [
        ("current", False),
        ("failed_withdraw", True),
        ("withdrawn", True),
        ("failed_forget", True),
        ("forgotten", True),
    ],
)
def test_an_entity_shared_only_with_a_retiring_owner_counts_as_removed(
    source_payload, state, refused
):
    """A reader of an Entity this source shares with another owner refuses
    the forget only when that other owner is retired or retiring, because
    then the forget removes the Entity."""
    source = source_of(source_payload)
    other = reader_of(source_payload)
    entity = uuid4()
    reader = reader_of(source_payload, entity_id=entity)
    plan = owned_plan(
        source, entity, [f"source_ref:v1:{other.dataset_id}:{other.identity_data_id}"]
    )
    rows = [row_of(source), other_row(other, state), row_of(reader)]
    if refused:
        with pytest.raises(IntentError) as found:
            refuse_dependents(source, plan, rows)
        assert found.value.code == "dependent_source"
        assert [d["consumed"] for d in found.value.details["dependents"]] == [
            str(entity)
        ]
    else:
        assert refuse_dependents(source, plan, rows) == set()


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
    with pytest.raises(IntentError) as found:
        refuse_dependents(source, plan, [row_of(source), row_of(reader)])
    assert found.value.code == "dependent_source"
    assert refuse_dependents(source, plan, [row_of(source)]) == {entity}


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


@pytest.mark.asyncio
async def test_a_readd_derives_every_group_from_the_next_revision(source_payload):
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(forgotten, set(), text, chunks_of(forgotten, text))
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
    await admit_readd(AbsentGraph(), forgotten, readded, set())


@pytest.mark.asyncio
async def test_a_readd_replaces_a_reusable_entity_the_forget_removed(source_payload):
    """HC was owned by this source alone, so the forget removed it. The re-add
    does not recreate it under its old UUID: the recipe returns under a UUID
    derived from the removed one, and the variant that named HC follows."""
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(forgotten, {HC}, text, chunks_of(forgotten, text))
    new_hc = replacement_entity_id(forgotten.identity_data_id, 2, HC)
    assert HC not in readded.entity_constructions
    assert readded.entity_constructions[new_hc] == forgotten.entity_constructions[HC]
    assert readded.variant_assignments["v01"].source_entity_id == new_hc
    await admit_readd(AbsentGraph(), forgotten, readded, {HC})

    kept = describe_readd(forgotten, set(), text, chunks_of(forgotten, text))
    assert HC in kept.entity_constructions
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, kept, {HC})
    assert refused.value.code == "forgotten_uuid_reused"

    underived = readded.model_copy(
        update={
            "entity_constructions": {
                (uuid4() if eid == new_hc else eid): recipe
                for eid, recipe in readded.entity_constructions.items()
            }
        }
    )
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, underived, {HC})
    assert refused.value.code == "entity_uuid_not_derived"

    with pytest.raises(IntentError) as refused:
        await admit_readd(OccupiedGraph([new_hc]), forgotten, readded, {HC})
    assert refused.value.code == "entity_uuid_in_graph"


@pytest.mark.asyncio
async def test_a_readd_with_the_forgotten_uuids_or_revision_is_refused(
    source_payload,
):
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(forgotten, set(), text, chunks_of(forgotten, text))

    same_ids = forgotten.model_copy(update={"revision": 2})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, same_ids, set())
    assert refused.value.code == "fresh_uuid_reused"

    skipped = readded.model_copy(update={"revision": 3})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, skipped, set())
    assert refused.value.code == "revision_sequence"

    wrong_derivation = describe_readd(
        forgotten.model_copy(update={"revision": 5}),
        set(),
        text,
        chunks_of(forgotten, text),
    ).model_copy(update={"revision": 2})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, wrong_derivation, set())
    assert refused.value.code == "fresh_uuid_not_derived"

    other = readded.model_copy(update={"identity_data_id": uuid4()})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, other, set())
    assert refused.value.code == "source_changed"

    occupied = OccupiedGraph([readded.mention_groups["g01"].entity_id])
    with pytest.raises(IntentError) as refused:
        await admit_readd(occupied, forgotten, readded, set())
    assert refused.value.code == "fresh_uuid_in_graph"
