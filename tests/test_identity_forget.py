"""Forget: the dependents check, the re-add admission and the ownership rules
that need no store."""

import json
from uuid import UUID, uuid4

import pytest

from cognee_lab.identity.fixture import FIXTURES
from cognee_lab.identity.forget import admit_readd, sole_owned
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.multisource import describe_readd
from cognee_lab.identity.validation import (
    IntentError,
    dependents,
    fresh_mention_id,
    object_digest,
)
from cognee_lab.identity.withdraw import retired_sources


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


def test_sole_ownership_reads_the_plan_refs(source_payload):
    source = source_of(source_payload)
    doc = source.inputs[source.original_input_ref]
    dataset = source.dataset_id
    own = f"source_ref:v1:{dataset}:{source.identity_data_id}"
    chunk = f"source_ref:v2:{dataset}:{doc.data_id}:{uuid4()}"
    other = f"source_ref:v1:{dataset}:{uuid4()}"
    plan = dict(
        entities={
            "11111111-1111-5111-8111-111111111111": dict(
                refs=[own], type="Entity", indexed_fields=["name"]
            ),
            "22222222-2222-5222-8222-222222222222": dict(
                refs=[own, chunk], type="Entity", indexed_fields=["name"]
            ),
            "33333333-3333-5333-8333-333333333333": dict(
                refs=[own, other], type="Entity", indexed_fields=["name"]
            ),
            "44444444-4444-5444-8444-444444444444": dict(
                refs=[chunk], type="DocumentChunk", indexed_fields=["text"]
            ),
        }
    )
    assert sole_owned(source, plan) == {
        UUID("11111111-1111-5111-8111-111111111111"),
        UUID("22222222-2222-5222-8222-222222222222"),
    }


def test_retired_sources_release_the_identity_and_the_forgotten_document():
    withdrawn = dict(
        dataset="d",
        source="w",
        state="withdrawn",
        plan={"operation": "identity_withdraw"},
    )
    forgotten = dict(
        dataset="d",
        source="f",
        state="forgotten",
        plan={"operation": "identity_forget", "original_data_id": "f-doc"},
    )
    failing = dict(
        dataset="d",
        source="g",
        state="failed",
        plan={"operation": "identity_forget", "original_data_id": "g-doc"},
    )
    current = dict(dataset="d", source="c", state="current", plan={})
    assert retired_sources([withdrawn, forgotten, failing, current]) == {
        ("d", "w"),
        ("d", "f"),
        ("d", "f-doc"),
        ("d", "g"),
        ("d", "g-doc"),
    }


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


@pytest.mark.asyncio
async def test_a_readd_derives_every_group_from_the_next_revision(source_payload):
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(forgotten, text, chunks_of(forgotten, text))
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
    await admit_readd(AbsentGraph(), forgotten, readded)


@pytest.mark.asyncio
async def test_a_readd_with_the_forgotten_uuids_or_revision_is_refused(
    source_payload,
):
    forgotten = source_of(source_payload)
    text = TEXT
    readded = describe_readd(forgotten, text, chunks_of(forgotten, text))

    same_ids = forgotten.model_copy(update={"revision": 2})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, same_ids)
    assert refused.value.code == "fresh_uuid_reused"

    skipped = readded.model_copy(update={"revision": 3})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, skipped)
    assert refused.value.code == "revision_sequence"

    wrong_derivation = describe_readd(
        forgotten.model_copy(update={"revision": 5}), text, chunks_of(forgotten, text)
    ).model_copy(update={"revision": 2})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, wrong_derivation)
    assert refused.value.code == "fresh_uuid_not_derived"

    other = readded.model_copy(update={"identity_data_id": uuid4()})
    with pytest.raises(IntentError) as refused:
        await admit_readd(AbsentGraph(), forgotten, other)
    assert refused.value.code == "source_changed"

    occupied = OccupiedGraph([readded.mention_groups["g01"].entity_id])
    with pytest.raises(IntentError) as refused:
        await admit_readd(occupied, forgotten, readded)
    assert refused.value.code == "fresh_uuid_in_graph"
