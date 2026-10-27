"""Query seed selection must not depend on vector payload layout or lucky rank."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cognee_lab.identity.retrieve import select_seed_entities
from cognee_lab.identity.settled import SearchRefused, SearchRequest, SearchScope


@pytest.mark.parametrize("payload", [None, {"text": "HC"}, {"name": "wrong"}])
async def test_explicit_name_beats_higher_ranked_fact_target(payload):
    nodes = {
        "oscillations": {"type": "Entity", "name": "oscillations"},
        "hc": {"type": "Entity", "name": "HC"},
        "mention": {"type": "Entity", "name": "HC"},
    }
    graph = SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get))
    candidates = [
        SimpleNamespace(id=key, payload=payload)
        for key in ["oscillations", "mention", "hc", "hc"]
    ]
    assert await select_seed_entities(
        graph, candidates, "What does HC limit?", skip={"mention"}, allowed=set(nodes)
    ) == {"hc"}
    assert [call.args[0] for call in graph.get_node.await_args_list] == [
        "oscillations",
        "hc",
    ]


async def test_fallback_skips_stale_and_non_entity_vector_entries():
    nodes = {
        "chunk": {"type": "DocumentChunk", "name": "HC"},
        "a": {"type": "Entity", "name": "Helios controller"},
        "b": {"type": "Entity", "name": "Other device"},
    }
    graph = SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get))
    candidates = [SimpleNamespace(id=key) for key in ["missing", "chunk", "a", "b"]]
    assert await select_seed_entities(
        graph, candidates, "regulation?", skip=set(), allowed={"a", "b"}
    ) == {"a"}


async def test_no_eligible_candidate_returns_no_seed():
    graph = SimpleNamespace(get_node=AsyncMock(return_value=None))
    assert (
        await select_seed_entities(
            graph,
            [SimpleNamespace(id="missing")],
            "HC",
            skip=set(),
            allowed={"missing"},
        )
        == set()
    )


@pytest.mark.parametrize(
    "ranked, query, seeds",
    [
        (["aurora", "helios"], "What does Aurora controller limit?", set()),
        (["aurora", "helios"], "limits?", set()),
        (["aurora", "helios"], "What does Helios controller limit?", {"helios"}),
        (["helios", "aurora"], "limits?", {"helios"}),
        (["mention", "helios", "aurora"], "limits?", {"helios"}),
    ],
)
async def test_an_entity_no_served_source_constructs_never_seeds(ranked, query, seeds):
    """Another dataset's Entity shares Entity_name (probe E5). It is never a
    seed, and when it ranks first no lab Entity takes its place: a query
    about another dataset's Entity returns no lab fact."""
    nodes = {
        "aurora": {"type": "Entity", "name": "Aurora controller"},
        "helios": {"type": "Entity", "name": "Helios controller"},
        "mention": {"type": "Entity", "name": "The controller"},
    }
    graph = SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get))
    candidates = [SimpleNamespace(id=key) for key in ranked]
    assert (
        await select_seed_entities(
            graph, candidates, query, skip={"mention"}, allowed={"helios"}
        )
        == seeds
    )


def _settled(monkeypatch, outcomes):
    """retrieve_settled over a retrieve that raises or returns `outcomes` in
    turn, the query of each read it made, and the document IDs of each Data
    names read."""
    from cognee_lab.identity import settled as module

    reads, named = [], []

    async def fake(publisher, dataset_id, query):
        reads.append(query)
        outcome = outcomes[len(reads) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def names(dataset_id, ids):
        named.append(ids)
        return {i: f"name {i}" for i in ids}

    monkeypatch.setattr(module, "retrieve", fake)
    monkeypatch.setattr(module, "dataset_data", names)
    return module.retrieve_settled, reads, named


def _found(*documents):
    """A read that found one fact for each document, scored by its place."""
    from cognee_lab.identity.delivery import Evidence, Fact, Found, Support

    return Found(
        facts=tuple(
            Fact(
                edge_id=f"e-{d}",
                source_id="s",
                target_id="t",
                relationship="limits",
                text="limits t",
                score=-place,
                first=Support(
                    document_id=d,
                    identity_data_id=f"id-{d}",
                    evidence=(Evidence("c", 0, "text", 0, 4),),
                ),
            )
            for place, d in enumerate(documents)
        ),
        report=dict(identity_work=1),
    )


@pytest.mark.parametrize("code", ["retrieval_changed", "stale_attempt"])
async def test_a_writer_during_the_read_gets_one_more_read(monkeypatch, code):
    from cognee_lab.identity.validation import IntentError

    settled, reads, _ = _settled(
        monkeypatch, [IntentError(code, "changed"), _found("a", "b")]
    )
    found = await settled(None, "d1", "q", SearchRequest.parse(), limit=1)
    assert found == dict(
        mode="semantic",
        scope="identity",
        dataset_id="d1",
        facts=[
            dict(
                edge_id="e-a",
                source_id="s",
                target_id="t",
                relationship="limits",
                text="limits t",
                evidence=[dict(data_id="a", chunk_id="c", chunk_index=0, text="text")],
                score=0,
            )
        ],
        identity_work=1,
    )
    # Cognee's search history stores the result as str(list).
    assert repr(found["mode"]) == "'semantic'"
    assert reads == ["q", "q"]


@pytest.mark.parametrize(
    "mode, keys, named",
    [
        ("semantic", {"facts"}, []),
        ("source_aware", {"facts", "documents"}, [{"a", "b"}]),
    ],
)
async def test_the_mode_decides_how_the_found_facts_are_delivered(
    monkeypatch, mode, keys, named
):
    """Only source_aware reads Data names: once, for the documents of the
    facts it returns."""
    settled, _, reads = _settled(monkeypatch, [_found("a", "b", "c")])
    found = await settled(None, "d1", "q", SearchRequest.parse(mode=mode), limit=2)
    assert found["mode"] == mode
    assert set(found) - {"mode", "scope", "dataset_id", "identity_work"} == keys
    assert reads == named


@pytest.mark.parametrize("code", ["retrieval_changed", "stale_attempt"])
async def test_a_second_change_fails_the_search(monkeypatch, code):
    from cognee_lab.identity.validation import IntentError

    settled, reads, _ = _settled(
        monkeypatch, [IntentError(code, "first"), IntentError(code, "second")]
    )
    with pytest.raises(IntentError, match="second"):
        await settled(None, "d1", "q", SearchRequest.parse())
    assert len(reads) == 2


async def test_another_failure_is_not_read_again(monkeypatch):
    from cognee_lab.identity.validation import IntentError

    settled, reads, _ = _settled(monkeypatch, [IntentError("ledger_format", "old")])
    with pytest.raises(IntentError, match="old"):
        await settled(None, "d1", "q", SearchRequest.parse())
    assert len(reads) == 1


@pytest.mark.parametrize(
    "scope, mode, code",
    [
        ("identity_and_unattributed", None, "scope_not_built"),
        (None, "everything", "config_invalid"),
        ("everything", None, "config_invalid"),
    ],
)
def test_a_request_refuses_what_is_not_built(scope, mode, code):
    """However it is made: parsed from CLI values, from a search's
    retriever_specific_config, or constructed directly."""
    given = {k: v for k, v in dict(scope=scope, mode=mode).items() if v is not None}
    for make in (
        lambda: SearchRequest.parse(scope, mode),
        lambda: SearchRequest.from_config(given),
        lambda: SearchRequest(**given),
    ):
        with pytest.raises(SearchRefused) as refused:
            make()
        assert refused.value.code == code


def test_a_config_key_that_is_not_a_request_field_is_invalid():
    with pytest.raises(SearchRefused) as refused:
        SearchRequest.from_config(dict(scope="identity", top_k=3))
    assert refused.value.code == "config_invalid"
    assert SearchRequest.from_config(None) == SearchRequest()


def test_a_request_defaults_to_scope_identity_and_mode_semantic():
    request = SearchRequest.parse()
    assert (request.scope, request.mode) == ("identity", "semantic")
    assert request == SearchRequest.parse(SearchScope.IDENTITY, "semantic")


def test_capability_check_sees_through_transparent_engine_handle():
    from cognee.infrastructure.databases.graph.graph_db_interface import (
        GraphDBInterface,
    )
    from cognee_lab.identity.native import require_graph_methods
    from cognee_lab.identity.validation import IntentError

    class Unsupported(GraphDBInterface):
        pass

    class Handle:
        @property
        def __class__(self):
            return Unsupported

    with pytest.raises(IntentError, match="remove_node_source_refs"):
        require_graph_methods(Handle(), ["remove_node_source_refs"])

    class Supported(Unsupported):
        async def remove_node_source_refs(self, *args):
            pass

    class SupportedHandle:
        @property
        def __class__(self):
            return Supported

    require_graph_methods(SupportedHandle(), ["remove_node_source_refs"])


@pytest.mark.parametrize("writer_completes", [False, True])
async def test_a_writer_between_the_read_and_the_fail_gets_a_second_read(
    monkeypatch, source_payload, writer_completes
):
    """Spec review R5 through a real RecordStore: retrieval reads a current
    row, finds its own input failed, and a writer begins on the source
    before RecordStore.fail runs. The fail raises stale_attempt and records
    nothing, and the second read serves the rows the writer left."""
    import json

    from test_identity_storage import PUBLISH_INTENT, memory_store

    from cognee_lab.identity import retrieve as module
    from cognee_lab.identity import settled
    from cognee_lab.identity.models import IdentitySource
    from cognee_lab.identity.validation import IntentError

    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    store = memory_store()
    await store.initialize()
    await store.complete(
        source, await store.begin(source, expected_revision=0, plan={})
    )
    publisher = SimpleNamespace(
        records=store,
        withholdings=SimpleNamespace(rows=AsyncMock(return_value=[])),
        vector=SimpleNamespace(has_collection=AsyncMock(return_value=False)),
    )
    writers = []

    async def drift(publisher, source, reader):
        if writers:
            return {}
        writers.append(
            await store.begin(
                source,
                expected_revision=1,
                plan=dict(PUBLISH_INTENT),
                method="reconcile",
            )
        )
        if writer_completes:
            await store.complete(source, writers[0])
        raise IntentError("source_missing", "own chunks are gone")

    refusals = []

    async def read(*args, **kwargs):
        try:
            return await module.retrieve(*args, **kwargs)
        except IntentError as exc:
            refusals.append(exc.code)
            raise

    monkeypatch.setattr(module, "live_drift", drift)
    monkeypatch.setattr(settled, "retrieve", read)
    found = await settled.retrieve_settled(
        publisher, source.dataset_id, "q", SearchRequest.parse()
    )
    assert refusals == ["stale_attempt"]
    (row,) = await store.rows(source.dataset_id)
    assert await store.events(source.dataset_id) == []
    assert row.attempt == writers[0]
    if writer_completes:
        assert row.state == "current"
        assert found["unavailable_sources"] == []
    else:
        assert row.state == "pending"
        assert found["unavailable_sources"] == [
            dict(
                identity_data_id=str(source.identity_data_id),
                assignment_id=None,
                reason="publication_pending",
                recovery_event_id=None,
            )
        ]


async def test_a_fact_two_sources_support_keeps_both_supports(
    monkeypatch, source_payload
):
    """Two served sources support the same Entity-subject fact, each with
    evidence in its own original. Semantic delivers the first source's
    evidence alone, as before; source_aware delivers the union and both
    documents."""
    import json
    from uuid import UUID

    import cognee.modules.provenance.edge_evidence.lookup as lookup
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
    from cognee.modules.engine.utils import generate_edge_object_id

    from cognee_lab.identity import retrieve as module
    from cognee_lab.identity.delivery import documents_of, semantic, source_aware
    from cognee_lab.identity.models import IdentitySource

    helios, target = "8b4bff50-907b-56b6-bc80-3b0a7018714a", "oscillations"
    for key in ("mention_groups", "mention_resolutions", "variant_assignments"):
        source_payload[key] = {}
    first = IdentitySource.model_validate_json(json.dumps(source_payload))
    second = first.model_copy(
        update=dict(
            identity_data_id=UUID("718efce2-4251-5f6f-8318-417bb4dd3526"),
            inputs=dict(
                doc01=first.inputs["doc01"].model_copy(
                    update=dict(data_id=UUID("50d5313b-0fee-5945-b1d5-5c1d37a6f881"))
                ),
                chunk01=first.inputs["chunk01"].model_copy(
                    update=dict(
                        chunk_id=UUID("2e57c22b-e0d2-51cb-85e2-aa6831e6c2a7"), end=90
                    )
                ),
                existing_A=first.inputs["existing_A"],
            ),
        )
    )
    sources = [first, second]
    documents = [str(s.inputs["doc01"].data_id) for s in sources]
    chunks = [str(s.inputs["chunk01"].chunk_id) for s in sources]
    rows = [
        SimpleNamespace(
            source=str(s.identity_data_id),
            state="current",
            revision=1,
            attempt=1,
            description=None,
        )
        for s in sources
    ]
    nodes = {
        helios: {"type": "Entity", "name": "Helios controller"},
        target: {"name": "oscillations"},
        chunks[0]: {"chunk_index": 0, "text": "first chunk"},
        chunks[1]: {"chunk_index": 0, "text": "second chunk"},
    }
    owners = {
        make_chunk_source_ref_key(first.dataset_id, UUID(d), UUID(c))
        for d, c in zip(documents, chunks)
    }

    async def valid_sources(publisher, dataset_id, rows, withheld):
        return [(s, r, {}) for s, r in zip(sources, rows)], []

    async def edge_metadata(graph, a, b, relation):
        return SimpleNamespace(source_ref_keys=owners)

    async def fact_neighborhood(graph, subject, limit):
        edge = (helios, target, "limits", {"edge_text": "limits oscillations"})
        return ([edge] if subject == helios else []), False

    async def evidence(edge_ids, dataset_id):
        return [
            SimpleNamespace(data_id=UUID(d), chunk_id=UUID(c), chunk_index=0)
            for d, c in zip(documents, chunks)
        ]

    monkeypatch.setattr(module, "valid_sources", valid_sources)
    monkeypatch.setattr(module, "withheld_decisions", lambda rows, table: {})
    monkeypatch.setattr(module, "edge_metadata", edge_metadata)
    monkeypatch.setattr(module, "fact_neighborhood", fact_neighborhood)
    monkeypatch.setattr(lookup, "get_edge_evidence_records", evidence)
    publisher = SimpleNamespace(
        records=SimpleNamespace(rows=AsyncMock(return_value=rows)),
        withholdings=SimpleNamespace(rows=AsyncMock(return_value=[])),
        vector=SimpleNamespace(
            has_collection=AsyncMock(return_value=True),
            search=AsyncMock(return_value=[SimpleNamespace(id=helios)]),
        ),
        graph=SimpleNamespace(get_node=AsyncMock(side_effect=nodes.get)),
    )
    found = await module.retrieve(
        publisher, first.dataset_id, "What does Helios controller limit?"
    )

    def cited(index, **ranges):
        return dict(
            data_id=documents[index],
            chunk_id=chunks[index],
            chunk_index=0,
            text=nodes[chunks[index]]["text"],
            **ranges,
        )

    fact = dict(
        edge_id=generate_edge_object_id(helios, target, "limits"),
        source_id=helios,
        target_id=target,
        relationship="limits",
        text="limits oscillations",
    )
    (plain,) = semantic(found)["facts"]
    assert plain == dict(fact, evidence=[cited(0)], score=1)
    names = {d: f"name {d}" for d in documents_of(found, 5)}
    result = source_aware(found, names)
    (aware,) = result["facts"]
    assert aware == dict(
        fact,
        evidence=[cited(0, start=0, end=110), cited(1, start=0, end=90)],
        score=1,
    )
    assert [
        (d["document_id"], d["identity_data_id"], d["facts"])
        for d in result["documents"]
    ] == sorted(
        (
            documents[i],
            rows[i].source,
            [
                dict(
                    edge_id=fact["edge_id"],
                    spans=[
                        dict(
                            kind="evidence_chunk", chunk_id=chunks[i], start=0, end=end
                        )
                    ],
                )
            ],
        )
        for i, end in enumerate((110, 90))
    )
