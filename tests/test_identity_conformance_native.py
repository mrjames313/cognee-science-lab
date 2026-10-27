"""The conformance fixture through real configured stores: DOC01 publishes
through the lab's add and cognify, and `retrieve` serves its stated facts
with DOC01's own chunks as evidence."""

import json

import pytest

from test_identity_native import command


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    """One conformance root for the module: both tests only read it."""
    root = tmp_path_factory.mktemp("conformance") / "root"
    command(root, "conformance-fixture")
    return root


@pytest.mark.integration
def test_conformance_fixture_publishes_doc01_and_serves_its_facts(root):
    created = json.loads((root / "result.json").read_text())
    assert created["publications"] == [
        dict(state="current", revision=1, verified_revision=1)
    ]
    assert created["recovery_events"] == []
    source = json.loads((root / "identity.json").read_text())
    original = source["inputs"]["doc01"]["data_id"]
    chunks = {i["chunk_id"] for i in source["inputs"].values() if i["kind"] == "chunk"}
    answer = json.loads(
        command(root, "retrieve", "--query", "Helios-1 major radius").stdout
    )
    assert answer["unavailable_sources"] == []
    assert answer["facts"][0]["text"].startswith(
        "Helios-1 has a major radius of 1.35 m"
    )
    evidence = [e for f in answer["facts"] for e in f["evidence"]]
    assert evidence and all(
        e["data_id"] == original and e["chunk_id"] in chunks for e in evidence
    )


@pytest.mark.integration
def test_a_reference_group_serves_its_fact_under_its_referent(root):
    answer = json.loads(
        command(root, "retrieve", "--query", "Vertical Control System").stdout
    )
    (fact,) = [f for f in answer["facts"] if "identity" in f]
    assert fact["text"].startswith("The controller receives fast magnetic estimates")
    assert [o["text"] for o in fact["identity"]["occurrences"]] == [
        "The controller",
        "It",
    ]
