"""The IDENTITY SearchType without stores: its registration guards, the
retriever's refusals and what it hands back to Cognee. The search through
real stores is in test_identity_search_native.py."""

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cognee.modules.retrieval.registered_community_retrievers import (
    registered_community_retrievers,
)
from cognee.modules.search.types import SearchType

from cognee_lab.identity import search
from cognee_lab.identity.settled import SearchRefused

REPO = Path(__file__).resolve().parents[1]
DATASET = SimpleNamespace(id=uuid4(), name="stage6_isolated_fixture")
EDGE, CHUNK, DATA = str(uuid4()), str(uuid4()), str(uuid4())
RESULT = dict(
    mode="semantic",
    scope="identity",
    dataset_id=str(DATASET.id),
    facts=[
        dict(
            edge_id=EDGE,
            source_id=str(uuid4()),
            target_id=str(uuid4()),
            relationship="limits",
            text="it limits oscillations",
            evidence=[
                dict(data_id=DATA, chunk_id=CHUNK, chunk_index=0, text="… it limits")
            ],
            score=1,
        )
    ],
    unavailable_sources=[],
)


def test_importing_search_adds_identity_beside_the_built_in_types():
    assert search.register() is search.IDENTITY
    assert SearchType["IDENTITY"] is SearchType("IDENTITY") is SearchType.IDENTITY
    assert SearchType._member_names_.count("IDENTITY") == 1
    assert SearchType("CHUNKS") is SearchType.CHUNKS
    assert registered_community_retrievers[search.IDENTITY] is search.IdentityRetriever


def test_another_cognee_version_fails_registration(monkeypatch):
    import cognee

    monkeypatch.setattr(cognee, "__version__", "1.7.0")
    with pytest.raises(search.RegistrationError, match="found 1.7.0"):
        search.register()


def test_another_python_fails_registration(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 13, 0, "final", 0))
    with pytest.raises(search.RegistrationError, match="found Python 3.13"):
        search.register()


def test_an_identity_member_the_lab_did_not_add_keeps_its_retriever(monkeypatch):
    """Cognee's registry silently replaces the retriever of an existing
    member, so a member IDENTITY with no lab retriever is refused."""
    monkeypatch.delitem(registered_community_retrievers, search.IDENTITY)
    with pytest.raises(search.RegistrationError, match="did not add"):
        search.register()
    assert search.IDENTITY not in registered_community_retrievers


def test_a_lookup_that_misses_fails_the_self_test(monkeypatch):
    monkeypatch.delitem(SearchType._value2member_map_, "IDENTITY")
    with pytest.raises(search.RegistrationError, match="self-test"):
        search.register()


@pytest.mark.parametrize(
    "kwargs, code",
    [
        (dict(dataset=None), "dataset_required"),
        (
            dict(retriever_specific_config={"scope": "identity_and_unattributed"}),
            "scope_not_built",
        ),
        (dict(retriever_specific_config={"mode": "source_aware"}), "mode_not_built"),
        (dict(retriever_specific_config={"scope": "everything"}), "config_invalid"),
        (dict(retriever_specific_config={"top_k": 3}), "config_invalid"),
    ],
)
def test_cognee_meets_each_refusal_when_it_builds_the_retriever(kwargs, code):
    with pytest.raises(SearchRefused) as refused:
        search.IdentityRetriever(**{"dataset": DATASET, "top_k": 15, **kwargs})
    assert refused.value.code == code


def test_access_control_on_is_refused(monkeypatch):
    import cognee.context_global_variables as variables

    monkeypatch.setattr(variables, "backend_access_control_enabled", lambda: True)
    with pytest.raises(SearchRefused) as refused:
        search.IdentityRetriever(dataset=DATASET)
    assert refused.value.code == "access_control_on"


async def test_context_is_the_result_as_json_and_the_completion_is_the_result():
    retriever = search.IdentityRetriever(dataset=DATASET)
    context = await retriever.get_context_from_objects(retrieved_objects=RESULT)
    assert isinstance(context, str) and json.loads(context) == RESULT
    assert await retriever.get_completion_from_context(
        retrieved_objects=RESULT, context=context
    ) == [RESULT]


def test_evidence_names_each_fact_and_only_its_checked_chunks():
    """No graph_edge reference: Cognee would add the edge sidecar's chunks of
    every document, served or not."""
    retriever = search.IdentityRetriever(dataset=DATASET)
    found = retriever.get_context_evidence(RESULT, dataset_id=DATASET.id)
    assert [
        (e.kind, e.artifact_id, e.role, e.assertion_id, e.data_id) for e in found
    ] == [
        ("triplet", EDGE, "used_as_context", None, None),
        ("segment", CHUNK, "supports_assertion", EDGE, DATA),
    ]
    assert {e.dataset_id for e in found} == {str(DATASET.id)}


def test_no_src_module_reads_the_hidden_benchmark_data():
    """data/hidden holds the benchmark answers; only the benchmark check in
    support/ may read them (spec review R3)."""
    readers = [
        str(path.relative_to(REPO))
        for path in sorted((REPO / "src").rglob("*.py"))
        if re.search(r"\bhidden\b", path.read_text())
    ]
    assert readers == []
