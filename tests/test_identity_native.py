"""Real configured stores in fresh subprocesses; no user's .env/store is used."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def command(root, operation, *args, expect=0):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cognee_lab.identity",
            operation,
            "--root",
            str(root),
            *args,
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert result.returncode == expect, result.stdout[-7000:] + result.stderr[-2000:]
    return result


@pytest.mark.integration
def test_native_publish_query_and_idempotent_reconcile(tmp_path):
    root = tmp_path / "native"
    command(root, "fixture")
    first = json.loads((root / "result.json").read_text())
    fact = next(f for f in first["result"]["facts"] if f["relationship"] == "limits")
    assert fact["source_id"] == "233cb019-3986-5864-88bc-91f334a64372"
    assert (
        fact["identity"]["target_entity_id"] == "8b4bff50-907b-56b6-bc80-3b0a7018714a"
    )
    assert fact["evidence"][0]["data_id"] == "50d5313b-0fee-5945-b1d5-5c1d37a6f880"
    assert "it limits oscillations" in fact["evidence"][0]["text"]
    assert first["result"]["seed_entity_ids"] == [
        "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
    ]
    command(root, "retrieve")  # Reopen real stores in a second process.
    command(root, "reconcile")
    second = json.loads((root / "result.json").read_text())
    assert second["result"]["facts"] == first["result"]["facts"]
    assert second["recovery_events"] == []
    # A native property mutation invalidates a field actually consumed by
    # Describe; the saved recipe must not silently restore it during retrieval.
    script = """
import asyncio,json,sys
from pathlib import Path
from uuid import UUID
from cognee_lab.identity.fixture_embeddings import FixtureEmbeddings
from cognee_lab.identity.__main__ import configure
root=Path(sys.argv[1])
with FixtureEmbeddings() as endpoint:
 configure(root,endpoint)
 from cognee_lab.identity.publish import Publisher
 from cognee_lab.identity.retrieve import retrieve
 async def check():
  p=await Publisher.configured()
  await p.graph.update_node('8b4bff50-907b-56b6-bc80-3b0a7018714a',{'description':'changed input'})
  dataset=UUID(json.loads((root/'fixture-info.json').read_text())['dataset_id'])
  answer=await retrieve(p,dataset,'What does HC limit?')
  assert answer['facts']==[]
  assert answer['unavailable_sources'][0]['reason']=='input_changed'
  events=await p.records.events(dataset)
  assert len(events)==1 and events[0]['origin']=='test'
 asyncio.run(check())
"""
    mutated = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert mutated.returncode == 0, mutated.stdout[-4000:] + mutated.stderr[-2000:]


@pytest.mark.integration
def test_native_failure_is_unavailable_and_explicitly_recovered(tmp_path):
    root = tmp_path / "failure"
    failed = command(root, "fixture", "--fault-stage", "identity_edges", expect=1)
    assert "recovery_event_id=" in failed.stdout
    query = command(root, "retrieve")
    assert '"facts": []' in query.stdout
    command(root, "reconcile")
    result = json.loads((root / "result.json").read_text())
    assert result["result"]["facts"]
    assert len(result["recovery_events"]) == 1
    assert result["recovery_events"][0]["resolved_at"]
    assert result["recovery_events"][0]["origin"] == "test/fault_injection"


def test_application_code_has_no_concrete_backend_access():
    import ast

    for path in (REPO / "src/cognee_lab/identity").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(
                    x in (node.module or "").split(".")
                    for x in ["lancedb", "ladybug", "kuzu", "sqlite3", "dialects"]
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"query", "execute_sql", "connect"}, path
