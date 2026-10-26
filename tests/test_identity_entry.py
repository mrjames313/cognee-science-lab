"""The lab entry points' rules that need no store: which native facets a
failed publication reports, the chunk budget a reconcile chunks with,
the order a root's sources are added and published in, and the refusal of
a source with no publication."""

import json

import pytest

from cognee_lab.identity import entry, native_copy
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.storage import PublicationRow
from cognee_lab.identity.validation import IntentError


def described(source_payload):
    return IdentitySource.model_validate_json(json.dumps(source_payload))


def failed_publication(source, verified_revision):
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state="failed",
        revision=source.revision,
        verified_revision=verified_revision,
        attempt="attempt",
        description=source,
        tombstone=None,
        plan=dict(operation="identity_publish"),
    )


class Graph:
    def __init__(self, nodes=()):
        self.nodes = dict(nodes)

    async def get_node(self, node_id):
        return self.nodes.get(node_id)


@pytest.fixture
def emptied(monkeypatch):
    async def absent(*_):
        return False

    monkeypatch.setattr(native_copy, "data_present", absent)
    monkeypatch.setattr(native_copy, "raw_file_present", absent)


@pytest.mark.parametrize("verified_revision", [0, 1])
async def test_a_failed_publication_reports_every_missing_facet(
    source_payload, emptied, verified_revision
):
    """A memory-only forget or an outside text change of a failed first
    publication's original is a delete outside the lab like any other: the
    lab's cognify never rolls its own chunks back."""
    row = failed_publication(described(source_payload), verified_revision)
    assert await native_copy.missing_native(Graph(), row) == [
        "original_data",
        "identity_data",
        "document_node",
        "chunks",
        "stored_files",
    ]


async def test_reconcile_chunks_with_the_budget_the_native_chunks_record(
    source_payload,
):
    source = described(source_payload)
    (chunk,) = entry.described_chunks(source)
    graph = Graph({chunk: {"max_chunk_tokens": 9}})
    assert await entry.chunk_budget_of(source, graph, 512) == 9


async def test_reconcile_chunks_with_the_default_when_the_chunks_are_gone(
    source_payload,
):
    assert await entry.chunk_budget_of(described(source_payload), Graph(), 512) == 512


class Recorded:
    """A stand-in for `entry.cognify` that records each source it is given
    and fails the ones named in `failing`."""

    def __init__(self, failing=()):
        self.failing = set(failing)
        self.cognified = []

    async def __call__(self, publisher, source, *, semantics, fault_stage, **_):
        self.cognified.append((source, semantics, fault_stage))
        if source in self.failing:
            raise IntentError("injected_failure", source)


def adder(added, label):
    async def add(earlier):
        added.append((label, sorted(earlier)))
        return label

    return add


async def test_each_source_is_added_then_published_reading_only_earlier_ones(
    monkeypatch,
):
    cognify = Recorded()
    monkeypatch.setattr(entry, "cognify", cognify)
    added = []
    done = await entry.remember_in_order(
        "publisher",
        {label: adder(added, label) for label in ("glossary", "doc01", "doc03")},
        semantics=lambda label: f"facts of {label}",
        fault=("doc03", "nodes"),
    )
    assert added == [
        ("glossary", []),
        ("doc01", ["glossary"]),
        ("doc03", ["doc01", "glossary"]),
    ]
    assert cognify.cognified == [
        ("glossary", "facts of glossary", None),
        ("doc01", "facts of doc01", None),
        ("doc03", "facts of doc03", "nodes"),
    ]
    assert done == {"glossary": "glossary", "doc01": "doc01", "doc03": "doc03"}


async def test_a_source_after_a_failed_one_is_never_registered(monkeypatch):
    monkeypatch.setattr(entry, "cognify", Recorded(failing={"doc01"}))
    added = []
    with pytest.raises(IntentError) as failed:
        await entry.remember_in_order(
            "publisher",
            {label: adder(added, label) for label in ("doc01", "doc02")},
            semantics=lambda label: None,
        )
    assert failed.value.code == "injected_failure"
    assert added == [("doc01", [])]


async def test_remember_publishes_the_source_it_registered(monkeypatch, tmp_path):
    async def add(dataset_name, original, *, describe, identity_path, chunk_budget):
        return describe(entry.Draft(original.path.name, [], dataset_name))

    cognify = Recorded()
    monkeypatch.setattr(entry, "add", add)
    monkeypatch.setattr(entry, "cognify", cognify)
    source = await entry.remember(
        "publisher",
        "dataset",
        entry.Original(tmp_path / "doc.txt", None),
        describe=lambda draft: ("described", draft.text, draft.dataset_id),
        identity_path=tmp_path / "identity.json",
        semantics="facts",
        fault_stage="nodes",
    )
    assert source == ("described", "doc.txt", "dataset")
    assert cognify.cognified == [(source, "facts", "nodes")]


class Ledger:
    async def row(self, source):
        return None

    async def rows(self, dataset=None):
        return []


class Unpublished:
    """A publisher whose ledger has no row and whose stores were not reset."""

    records = Ledger()

    async def refuse_natively_deleted(self, source):
        return None


async def test_reconcile_refuses_a_source_with_no_publication(source_payload):
    from cognee_lab.identity.multisource import reconcile_selected

    with pytest.raises(IntentError) as refused:
        await reconcile_selected(
            Unpublished(), "doc02", described(source_payload), resume_text_change=None
        )
    assert refused.value.code == "not_published"
    assert "doc02" in str(refused.value)


async def test_the_glossary_snapshot_refuses_a_source_with_no_publication(
    source_payload, tmp_path
):
    from cognee_lab.identity import glossary_fixture

    (tmp_path / "glossary_identity.json").write_text(json.dumps(source_payload))
    (tmp_path / glossary_fixture.INFO).write_text(
        json.dumps(dict(sources=dict(glossary="glossary_identity.json")))
    )
    with pytest.raises(IntentError) as refused:
        await glossary_fixture.snapshot(Unpublished(), tmp_path, "query")
    assert refused.value.code == "not_published"
    assert "glossary" in str(refused.value)
