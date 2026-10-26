"""The IDENTITY SearchType through real configured stores, in fresh
subprocesses: `cognee.search` returns what the lab's retrieve returns, logs
the query as IDENTITY, serves facts between Entities only, and a refused
search logs nothing. The fixture environment points the LLM at a closed
port, so an LLM call would fail each search."""

import json
import subprocess
import sys

import pytest

from test_identity_native import REPO, command

IN_ROOT = """
import asyncio, json, sys
from pathlib import Path
from cognee_lab.identity.environment import fixture_environment

QUERY = "What does HC limit?"

def plain(value):
    return json.loads(json.dumps(value, default=str))

async def refused(**kwargs):
    import cognee
    from cognee_lab.identity.search import IDENTITY

    try:
        await cognee.search(QUERY, query_type=IDENTITY, **kwargs)
    except Exception as exc:
        return [type(exc).__name__, getattr(exc, "code", None)]
    return None

async def main(root, action):
    import cognee
    from cognee.modules.data.methods.get_datasets_by_name import get_datasets_by_name
    from cognee.modules.search.types import SearchType
    from cognee.modules.users.methods import get_default_user
    from cognee_lab.identity import search
    from cognee_lab.identity.environment import DATASET_NAME
    from cognee_lab.identity.publish import Publisher
    from cognee_lab.identity.native_search import OUTSIDE_DATASET, OUTSIDE_TEXT
    from cognee_lab.identity.search import search_history
    from cognee_lab.identity.settled import LIMIT, SearchRequest, retrieve_settled

    publisher = await Publisher.configured()
    user = await get_default_user()
    (dataset,) = await get_datasets_by_name(DATASET_NAME, user.id)
    out = {}
    if action == "compare":
        direct = plain(
            await retrieve_settled(publisher, dataset.id, QUERY, SearchRequest.parse())
        )
        named = await cognee.search(
            QUERY, query_type=SearchType.IDENTITY, datasets=[DATASET_NAME], top_k=LIMIT
        )
        unscoped = await cognee.search(
            QUERY, query_type=search.IDENTITY, datasets=None, top_k=LIMIT
        )
        verbose = await cognee.search(
            QUERY,
            query_type=search.IDENTITY,
            datasets=[DATASET_NAME],
            top_k=LIMIT,
            verbose=True,
            include_references=True,
        )
        ends = {e for f in direct["facts"] for e in (f["source_id"], f["target_id"])}
        out.update(
            direct=direct,
            named=plain(named),
            unscoped=plain(unscoped),
            context=json.loads(verbose[0]["context_result"]),
            evidence=[
                [e["kind"], e["artifact_id"], e["assertion_id"]]
                for e in verbose[0]["evidence"]
            ],
            endpoint_types=sorted(
                {(await publisher.graph.get_node(e) or {}).get("type") for e in ends}
            ),
            history=await search_history(),
        )
    if action == "refuse":
        await cognee.add(
            OUTSIDE_TEXT, dataset_name=OUTSIDE_DATASET, skip_connection_test=True
        )
        before = await search_history()
        out.update(
            unscoped=await refused(datasets=None),
            scope=await refused(
                datasets=[DATASET_NAME],
                retriever_specific_config={"scope": "identity_and_unattributed"},
            ),
            mode=await refused(
                datasets=[DATASET_NAME],
                retriever_specific_config={"mode": "source_aware"},
            ),
            logged_by_refusals=(await search_history())[len(before):],
            named=plain(
                await cognee.search(
                    QUERY, query_type=search.IDENTITY, datasets=[DATASET_NAME]
                )
            ),
        )
    print(json.dumps(out))

root = Path(sys.argv[1])
with fixture_environment(root):
    asyncio.run(main(root, sys.argv[2]))
"""


def in_root(root, action):
    done = subprocess.run(
        [sys.executable, "-c", IN_ROOT, str(root), action],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-4000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.integration
def test_search_returns_what_retrieve_returns_and_logs_identity(tmp_path):
    root = tmp_path / "search"
    command(root, "fixture")
    found = in_root(root, "compare")
    direct = found["direct"]
    assert [f["text"] for f in direct["facts"]] == ["it limits oscillations"]
    assert (direct["mode"], direct["scope"]) == ("semantic", "identity")
    assert found["named"] == [direct]
    # With one dataset Cognee hands the retriever that dataset unasked.
    assert found["unscoped"] == [direct]
    assert found["context"] == direct
    (fact,) = direct["facts"]
    assert found["evidence"] == [["triplet", fact["edge_id"], None]] + [
        ["segment", e["chunk_id"], fact["edge_id"]] for e in fact["evidence"]
    ]
    # Cognee's access tracking reads top-level chunks and entities keys.
    assert not {"chunks", "entities"} & set(direct)
    assert (
        found["history"]
        == [dict(query_type="IDENTITY", text="What does HC limit?")] * 3
    )


@pytest.mark.integration
def test_every_fact_endpoint_is_an_entity(tmp_path):
    """No helper node (document, chunk or identity mention record) is served
    as a fact endpoint."""
    root = tmp_path / "chunked"
    command(root, "chunked-fixture")
    found = in_root(root, "compare")
    assert found["direct"]["facts"]
    assert found["endpoint_types"] == ["Entity"]


@pytest.mark.integration
def test_a_refused_search_logs_nothing(tmp_path):
    root = tmp_path / "refuse"
    command(root, "fixture")
    found = in_root(root, "refuse")
    assert found["unscoped"] == ["SearchRefused", "dataset_required"]
    assert found["scope"] == ["SearchRefused", "scope_not_built"]
    assert found["mode"] == ["SearchRefused", "mode_not_built"]
    assert found["logged_by_refusals"] == []
    assert [f["text"] for f in found["named"][0]["facts"]] == ["it limits oscillations"]
