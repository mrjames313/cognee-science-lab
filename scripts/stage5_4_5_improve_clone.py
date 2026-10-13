"""Run dataset-only Improve on a cold copy of local Cognee storage.

Requires the snapshot and storage-snapshot scripts alongside this file.
Run while other lab jobs are stopped. Enabled phase uses real embeddings.
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from dotenv import load_dotenv


DATASET = UUID("88e9627a-9304-5637-aff3-a561c0d93daa")


def graph_diff(before, after):
    def rows(snapshot):
        return {
            "nodes": {
                n["id"]: n["properties"]
                for n in snapshot["nodes"]
            },
            "edges": {
                json.dumps([
                    e["source_id"],
                    e["target_id"],
                    e["relationship"],
                ]): e["properties"]
                for e in snapshot["edges"]
            },
            "native_nodes": snapshot["native_provenance"]["nodes"],
            "native_edges": {
                json.dumps(e["edge"], sort_keys=True): e
                for e in snapshot["native_provenance"]["edges"]
            },
        }

    a, b = rows(before), rows(after)
    return {
        kind: {
            "added": sorted(b[kind].keys() - a[kind].keys()),
            "removed": sorted(a[kind].keys() - b[kind].keys()),
            "changed": sorted(
                i for i in a[kind].keys() & b[kind].keys()
                if a[kind][i] != b[kind][i]
            ),
        }
        for kind in a
    }


async def worker(root):
    load_dotenv()

    import cognee
    from cognee.base_config import get_base_config
    from cognee.context_global_variables import backend_access_control_enabled
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational.config import (
        get_relational_config,
    )
    from cognee.infrastructure.databases.vector.config import get_vectordb_config
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.modules.cognify.config import get_cognify_config
    from cognee.api.v1.serve.state import get_remote_client
    from stage5_4_5_snapshot import live_snapshot, finish
    from stage5_4_5_storage_snapshot import main as storage_snapshot

    if cognee.__version__ != "1.6.2" or backend_access_control_enabled():
        raise RuntimeError("Expected 1.6.2 with shared storage")
    if get_remote_client() is not None:
        raise RuntimeError("This experiment requires local SDK execution")

    paths = [
        get_base_config().system_root_directory,
        get_relational_config().db_path,
        get_graph_config().graph_file_path,
        get_vectordb_config().vector_db_url,
    ]
    if not all(Path(p).resolve().is_relative_to(root) for p in paths):
        raise RuntimeError("A storage path points outside the clone")

    config = get_cognify_config()
    report = {
        "clone": str(root),
        "original_triplet_embedding": config.triplet_embedding,
        "dataset_id": str(DATASET),
        "phases": [],
    }

    async def capture(name):
        snapshot = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        finish(snapshot, root / f"graph_{name}.json")
        return snapshot

    baseline = await capture("before")
    if len(baseline["nodes"]) != 281 or len(baseline["edges"]) != 761:
        raise RuntimeError(
            "Clone differs from the expected 281-node/761-edge baseline"
        )

    await storage_snapshot(SimpleNamespace(
        graph=root / "graph_before.json",
        output=root / "storage_before.json",
    ))

    async def phase(name, before):
        result = await cognee.improve(
            dataset=DATASET,
            run_in_background=False,
        )
        after = await capture(name)
        report["phases"].append({
            "name": name,
            "result": result.model_dump(mode="json"),
            "graph_diff": graph_diff(before, after),
        })
        (root / "improve_results.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(name, result.stage_summary())
        if result.status == "errored":
            raise RuntimeError(
                f"Improve reported an errored stage in {name}"
            )
        return after

    baseline = await phase("as_configured", baseline)

    config.triplet_embedding = True
    baseline = await phase("enabled", baseline)
    baseline = await phase("repeat", baseline)

    # Direct graph write has no completed pipeline-run record.
    helper = next(
        n for n in baseline["nodes"]
        if n["properties"].get("type") == "IdentityResolution"
    )
    graph = await get_graph_engine()
    patched_ok = await graph.update_node(
        helper["id"],
        {"lab_probe_sentinel": "direct-write"},
    )
    if not patched_ok:
        raise RuntimeError("Direct patch failed")

    patched = await capture("manual_patch")
    report["manual_patch_diff"] = graph_diff(baseline, patched)
    baseline = await phase("after_direct_write", patched)

    await storage_snapshot(SimpleNamespace(
        graph=root / "graph_after_direct_write.json",
        output=root / "storage_after.json",
    ))
    report["final_graph_diff_from_original"] = graph_diff(
        json.loads((root / "graph_before.json").read_text()),
        baseline,
    )
    (root / "improve_results.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(f"UPLOAD: {root / 'improve_results.json'}")
    print(f"UPLOAD: {root / 'storage_after.json'}")


def launch():
    load_dotenv()

    import cognee
    from cognee.base_config import get_base_config
    from cognee.context_global_variables import backend_access_control_enabled
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational.config import (
        get_relational_config,
    )
    from cognee.infrastructure.databases.vector.config import get_vectordb_config

    base = get_base_config()
    graph = get_graph_config()
    rel = get_relational_config()
    vector = get_vectordb_config()

    if (
        cognee.__version__ != "1.6.2"
        or backend_access_control_enabled()
        or graph.graph_database_provider != "ladybug"
        or rel.db_provider != "sqlite"
        or vector.vector_db_provider != "lancedb"
    ):
        raise RuntimeError(
            "Expected local 1.6.2, Ladybug/SQLite/LanceDB, shared storage"
        )

    source = Path(base.system_root_directory).resolve()
    paths = [
        Path(graph.graph_file_path).resolve(),
        Path(rel.db_path).resolve(),
        Path(vector.vector_db_url).resolve(),
    ]
    if not all(
        p.exists() and p.is_relative_to(source) for p in paths
    ):
        raise RuntimeError(
            "All configured databases must exist within the system root"
        )
    if Path(rel.db_name).name != rel.db_name:
        raise RuntimeError("Expected a simple SQLite database filename")
    if not (Path(rel.db_path) / rel.db_name).is_file():
        raise RuntimeError("Configured SQLite database file does not exist")
    if any(p.is_symlink() for p in source.rglob("*")):
        raise RuntimeError(
            "Resolve system-root symlinks before this copy experiment"
        )

    outputs = Path("outputs").resolve()
    if outputs.is_relative_to(source):
        raise RuntimeError("Outputs must be outside the source system root")
    outputs.mkdir(exist_ok=True)

    root = Path(tempfile.mkdtemp(
        prefix="stage5_4_5_improve_",
        dir=outputs,
    ))
    destination = root / "system"
    shutil.copytree(source, destination)
    copied = [
        destination / p.relative_to(source)
        for p in paths
    ]

    for name in ["data", "cache", "logs"]:
        (root / name).mkdir()

    env = os.environ.copy()
    env.update({
        "SYSTEM_ROOT_DIRECTORY": str(destination),
        "DB_PATH": str(copied[1]),
        "DB_NAME": rel.db_name,
        "GRAPH_FILE_PATH": str(copied[0].parent),
        "GRAPH_FILENAME": copied[0].name,
        "VECTOR_DB_URL": str(copied[2]),
        "DATA_ROOT_DIRECTORY": str(root / "data"),
        "CACHE_ROOT_DIRECTORY": str(root / "cache"),
        "LOGS_ROOT_DIRECTORY": str(root / "logs"),
        "COGNEE_LOGS_DIR": str(root / "logs"),
        "ENABLE_BACKEND_ACCESS_CONTROL": "false",
    })

    # Preserve subprocess settings when Cognee imports its configuration.
    probe_env = root / "probe.env"
    probe_env.write_text(
        "# Probe settings come from the subprocess environment.\n"
    )
    env["COGNEE_ENV_FILE"] = str(probe_env)
    
    print(f"Clone: {root}", flush=True)
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            str(root),
        ],
        env=env,
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.worker:
        asyncio.run(worker(args.worker.resolve()))
    else:
        launch()
