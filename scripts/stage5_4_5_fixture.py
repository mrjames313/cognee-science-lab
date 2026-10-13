"""Test graph primitives in a NEW, isolated Ladybug database.

Run: uv run python scripts/stage5_4_5_fixture.py

No configured graph handle, Add/Cognify/Improve/Forget, embeddings, or LLMs.
This exercises the adapter and source-ref planner, not complete public workflows.
Vector operations use a recording stub; real vector cleanup is not tested.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import cognee
from cognee.infrastructure.databases.graph.ladybug.adapter import LadybugAdapter
from cognee.infrastructure.databases.provenance import (
    EdgeIdentity,
    make_source_ref_key,
)
from cognee.infrastructure.databases.unified.provenance_delete_planner import (
    execute_source_ref_removal,
)
from cognee.infrastructure.engine import DataPoint


class ProbeSupport(DataPoint):
    name: str
    graph_layer: str = "support"
    source_document_id: str | None = None
    metadata: dict = {
        "index_fields": [],
        "identity_fields": ["name"],
    }


class VectorRecorder:
    """No vector database is opened. Record attempted cleanup only."""

    def __init__(self):
        self.calls = []

    async def has_collection(self, collection):
        self.calls.append({
            "method": "has_collection",
            "collection": collection,
        })
        return False

    async def delete_data_points(self, collection, ids):
        self.calls.append({
            "method": "delete_data_points",
            "collection": collection,
            "ids": ids,
        })


async def capture(graph):
    nodes, edges = await graph.get_graph_data()

    nd = await graph.get_node_delete_data(
        [str(i) for i, _ in nodes]
    )
    ed = await graph.get_edge_delete_data([
        EdgeIdentity(str(s), str(t), str(r))
        for s, t, r, _ in edges
    ])

    return {
        "nodes": {str(i): p for i, p in nodes},
        "edges": edges,
        "node_provenance": {
            str(i): dataclasses.asdict(v)
            for i, v in nd.items()
        },
        "edge_provenance": [
            dataclasses.asdict(v) for v in ed.values()
        ],
    }


async def remove_ref(graph, vector, ref):
    ids = await graph.find_nodes_by_source_ref(ref)
    edges = await graph.find_edges_by_source_ref(ref)

    nd = await graph.get_node_delete_data(ids)
    ed = await graph.get_edge_delete_data(edges)

    result = await execute_source_ref_removal(
        graph,
        vector,
        node_data=nd,
        edge_data=ed,
        refs_by_node={i: [ref] for i in nd},
        refs_by_edge={e: [ref] for e in ed},
    )
    return dataclasses.asdict(result)


async def main():
    if cognee.__version__ != "1.6.2":
        raise RuntimeError(
            f"Expected Cognee 1.6.2; got {cognee.__version__}"
        )

    outputs = Path("outputs").resolve()
    outputs.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(
        prefix="stage5_4_5_fixture_",
        dir=outputs,
    ))

    # Use a NEW explicit path. Never resolve the configured graph engine.
    graph = LadybugAdapter(
        db_path=str(root / "graph"),
        kuzu_buffer_pool_size=1 << 28,
        kuzu_max_db_size=1 << 30,
        kuzu_num_threads=2,
    )

    report = {
        "cognee_version": cognee.__version__,
        "fixture_directory": str(root),
        "scope": "isolated_adapter_and_planner",
        "real_vector_state_tested": False,
        "snapshots": {},
        "checks": {},
    }
    vector = VectorRecorder()

    try:
        dataset, doc_a, doc_b, run_a, run_b = [
            uuid4() for _ in range(5)
        ]
        ref_a = make_source_ref_key(dataset, doc_a)
        ref_b = make_source_ref_key(dataset, doc_b)

        # Test patching versus full upsert.
        probe = ProbeSupport(name="property probe")
        pid = str(probe.id)

        await graph.add_nodes(
            [probe],
            source_ref_key=ref_a,
            pipeline_run_id=str(run_a),
        )
        await graph.update_node(
            pid, {"sentinel": "keep", "patch_a": 1}
        )
        report["snapshots"]["before_patch"] = await capture(graph)

        await graph.update_node(pid, {"patch_b": 2})
        report["snapshots"]["after_patch"] = await capture(graph)

        patched = report["snapshots"]["after_patch"]["nodes"][pid]
        report["checks"]["patch_preserves_unmentioned_fields"] = (
            patched.get("sentinel") == "keep"
            and patched.get("patch_a") == 1
            and patched.get("patch_b") == 2
        )

        # Incoming object omits all three patch-only properties.
        await graph.add_nodes([
            ProbeSupport(id=UUID(pid), name="property probe")
        ])
        report["snapshots"]["after_upsert"] = await capture(graph)

        upserted = report["snapshots"]["after_upsert"]["nodes"][pid]
        report["checks"]["upsert_drops_unmentioned_fields"] = all(
            k not in upserted
            for k in ("sentinel", "patch_a", "patch_b")
        )

        refs = report["snapshots"]["after_upsert"][
            "node_provenance"
        ][pid]["source_ref_keys"]
        report["checks"][
            "unstamped_upsert_preserves_existing_native_ref"
        ] = ref_a in refs

        # Test single ownership, shared ownership, and unowned dependencies.
        owned = ProbeSupport(name="owned only by A")
        shared = ProbeSupport(name="shared by A and B")
        helper = ProbeSupport(
            name="unowned helper",
            source_document_id=str(doc_a),
        )
        oid, sid, hid = (
            str(owned.id), str(shared.id), str(helper.id)
        )

        await graph.add_nodes(
            [owned, shared],
            source_ref_key=ref_a,
            pipeline_run_id=str(run_a),
        )
        await graph.add_nodes(
            [shared],
            source_ref_key=ref_b,
            pipeline_run_id=str(run_b),
        )
        await graph.add_nodes([helper])

        await graph.add_edges(
            [
                (
                    oid, sid, "supports",
                    {"edge_text": "owned supports shared"},
                )
            ],
            source_ref_key=ref_a,
            pipeline_run_id=str(run_a),
        )
        await graph.add_edges([
            (
                hid, oid, "observed_in",
                {"edge_text": "helper observed in owned"},
            ),
            (
                hid, sid, "canonicalizes_to",
                {"edge_text": "helper canonicalizes to shared"},
            ),
        ])

        report["ids"] = {
            "property_probe": pid,
            "owned": oid,
            "shared": sid,
            "helper": hid,
        }
        report["snapshots"]["before_removal"] = await capture(graph)

        report["remove_a"] = await remove_ref(graph, vector, ref_a)
        report["snapshots"]["after_remove_a"] = await capture(graph)
        a = report["snapshots"]["after_remove_a"]

        report["checks"]["single_owner_deleted"] = (
            oid not in a["nodes"]
        )
        report["checks"]["shared_owner_survives"] = (
            sid in a["nodes"]
            and a["node_provenance"][sid]["source_ref_keys"] == [ref_b]
        )
        report["checks"]["unowned_helper_survives_with_source_id"] = (
            hid in a["nodes"]
            and a["nodes"][hid].get("source_document_id") == str(doc_a)
        )
        report["checks"]["unowned_incident_link_detached"] = not any(
            s == hid and t == oid
            for s, t, _, _ in a["edges"]
        )
        report["checks"]["link_to_surviving_shared_node_remains"] = any(
            s == hid and t == sid
            for s, t, _, _ in a["edges"]
        )

        report["remove_b"] = await remove_ref(graph, vector, ref_b)
        report["snapshots"]["after_remove_b"] = await capture(graph)
        b = report["snapshots"]["after_remove_b"]

        report["checks"]["last_owner_deleted"] = (
            sid not in b["nodes"]
        )
        report["checks"]["helper_survives_without_edges"] = (
            hid in b["nodes"]
            and not any(
                s == hid or t == hid
                for s, t, _, _ in b["edges"]
            )
        )

    except Exception as exc:
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        raise

    finally:
        report["vector_stub_calls"] = vector.calls
        report["all_checks_passed"] = (
            bool(report["checks"])
            and all(report["checks"].values())
            and "error" not in report
        )
        path = root / "results.json"
        path.write_text(
            json.dumps(report, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "output": str(path),
            "checks": report["checks"],
        }, indent=2))
        await graph.close()


if __name__ == "__main__":
    asyncio.run(main())
