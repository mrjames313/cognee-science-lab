"""The lab's cognify through real configured stores, in fresh subprocesses:
what Cognee's rollback of the run can reach, what Cognee's startup
recovery keeps of a failed first publication, a memory-only forget of one
reported as a delete, and the stamp gap that a plain
non-incremental cognify leaves."""

import json
import subprocess
import sys

import pytest

from test_identity_native import REPO, command

IN_ROOT = """
import asyncio, json, sys
from pathlib import Path
from cognee_lab.identity.environment import fixture_environment

async def runs_of(name):
    from sqlalchemy import select
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.pipelines.models import PipelineRun

    async with get_relational_engine().get_async_session() as session:
        rows = (await session.execute(select(PipelineRun))).scalars().all()
    return sorted({r.pipeline_run_id for r in rows if r.pipeline_name == name})

async def tagged_types(graph, run_id):
    ids = await graph.find_node_source_refs_by_pipeline_run(str(run_id))
    return sorted({(await graph.get_node(i) or {}).get("type") for i in ids})

async def main(root, action):
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee_lab.identity.fixture import context_for
    from cognee_lab.identity.models import IdentitySource
    from cognee_lab.identity.registered import stamped

    source = IdentitySource.model_validate_json((root / "identity.json").read_text())
    original = source.inputs[source.original_input_ref].data_id
    graph = await get_graph_engine()
    run_ids = await runs_of("cognify_pipeline")
    out = dict(tagged=sorted({t for r in run_ids for t in await tagged_types(graph, r)}))
    if action == "recover":
        from cognee.modules.cognify.rollback import cognify_rollback_handler

        # What Cognee's API startup recovery does to an abandoned run.
        (run_id,) = run_ids
        ctx = await context_for(original)
        await cognify_rollback_handler(
            pipeline_run_id=run_id, dataset=ctx.dataset, user=ctx.user,
            keep_completed_data=True,
        )
    if action == "forget-memory":
        import cognee

        await cognee.forget(
            data_id=original, dataset_id=source.dataset_id, memory_only=True
        )
    if action == "full-cognify":
        import cognee

        try:
            await cognee.cognify(datasets=[source.dataset_id], incremental_loading=False)
            out["cognify"] = "completed"
        except Exception as exc:
            out["cognify"] = type(exc).__name__
    chunks = [str(i.chunk_id) for i in source.inputs.values() if i.kind == "chunk"]
    mentions = [str(g.entity_id) for g in source.mention_groups.values()]
    out.update(
        chunks=[await graph.get_node(c) is not None for c in chunks],
        mentions=[await graph.get_node(m) is not None for m in mentions],
        stamped=await stamped(original, source.dataset_id),
    )
    print(json.dumps(out))

root = Path(sys.argv[1])
with fixture_environment(root):
    asyncio.run(main(root, sys.argv[2]))
"""


def in_root(root, action):
    result = subprocess.run(
        [sys.executable, "-c", IN_ROOT, str(root), action],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def output(result):
    return json.loads(result.stdout[result.stdout.index("{") :])


@pytest.mark.integration
def test_the_run_tags_only_native_chunks_and_document(tmp_path):
    root = tmp_path / "entry"
    command(root, "fixture")
    seen = in_root(root, "look")
    assert seen["tagged"] == ["DocumentChunk", "TextDocument"]
    assert all(seen["chunks"]) and all(seen["mentions"]) and seen["stamped"]


@pytest.mark.integration
def test_startup_recovery_keeps_a_failed_first_publication(tmp_path):
    root = tmp_path / "entry"
    failed = command(root, "fixture", "--fault-stage", "identity_edges", expect=1)
    assert "recovery_event_id=" in output(failed)["message"]
    recovered = in_root(root, "recover")
    # The lab Task stamped the original before it published, so the
    # recovery kept the native chunks.
    assert all(recovered["chunks"]) and recovered["stamped"]
    assert all(recovered["mentions"])
    status = output(command(root, "status"))
    assert [p["state"] for p in status["publications"]] == ["failed"]
    assert status["native_deleted"] == []
    reconciled = output(command(root, "reconcile"))
    assert len(reconciled["result"]["facts"]) == 1
    assert reconciled["cognify_stamps"] == dict(original=True, identity=True, seed=True)
    (event,) = reconciled["recovery_events"]
    assert event["outcome"] == "restored"


@pytest.mark.integration
def test_a_memory_only_forget_of_a_failed_first_publication_is_a_delete(tmp_path):
    root = tmp_path / "entry"
    command(root, "fixture", "--fault-stage", "identity_edges", expect=1)
    forgotten = in_root(root, "forget-memory")
    assert forgotten["chunks"] == [False] and forgotten["stamped"] is False
    (gone,) = output(command(root, "status"))["native_deleted"]
    assert gone["state"] == "failed"
    assert gone["missing"] == ["document_node", "chunks"]
    refused = output(command(root, "reconcile", expect=1))
    assert "gone or changed outside the lab" in refused["message"]


@pytest.mark.integration
def test_a_non_incremental_plain_cognify_ignores_the_stamps(tmp_path):
    """The documented gap: Cognee extracts the stamped items, and the
    closed LLM port makes the attempt fail instead of reaching a provider."""
    root = tmp_path / "entry"
    command(root, "fixture")
    seen = in_root(root, "full-cognify")
    assert seen["cognify"] != "completed"
