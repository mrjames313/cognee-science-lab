"""Compare Memify profiles on copies of the successful Improve clone.

Requires the three prior snapshot/Improve scripts in this directory.
Stop other lab jobs while copying. Default/empty cases use real embeddings.
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

from dotenv import load_dotenv
from stage5_4_5_improve_clone import DATASET, graph_diff


def plain(value):
    if hasattr(value, "model_dump"):
        return plain(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def storage_diff(before, after):
    vectors = {}
    for name in sorted(before["vectors"].keys() | after["vectors"].keys()):
        a, b = before["vectors"].get(name, {}), after["vectors"].get(name, {})
        ar = {r["id"]: r for r in a.get("rows", [])}
        br = {r["id"]: r for r in b.get("rows", [])}
        common = ar.keys() & br.keys()
        vectors[name] = {
            "before_status": a.get("status"),
            "after_status": b.get("status"),
            "before_count": len(ar),
            "after_count": len(br),
            "added": len(br.keys() - ar.keys()),
            "removed": len(ar.keys() - br.keys()),
            "changed_records": sum(ar[k] != br[k] for k in common),
            "changed_vector_hashes": sum(
                ar[k]["vector_sha256"] != br[k]["vector_sha256"]
                for k in common
            ),
            "changed_texts": sum(
                ar[k]["payload"].get("text") != br[k]["payload"].get("text")
                for k in common
            ),
        }
    relational = {}
    for name, b in after["relational"].items():
        a = before["relational"][name]
        encode = lambda r: json.dumps(r, sort_keys=True)
        ar = {encode(r) for r in a["rows"]}
        br = {encode(r) for r in b["rows"]}
        relational[name] = {
            "before_count": len(a["rows"]),
            "after_count": len(b["rows"]),
            "removed_rows": len(ar - br),
            "added_rows": [r for r in b["rows"] if encode(r) not in ar],
        }
    return {"vectors": vectors, "relational": relational}


async def worker(root, case):
    load_dotenv()
    import cognee
    from cognee.base_config import get_base_config
    from cognee.context_global_variables import backend_access_control_enabled
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational.config import get_relational_config
    from cognee.infrastructure.databases.vector.config import get_vectordb_config
    from cognee.modules.cognify.config import get_cognify_config
    from cognee.modules.pipelines.tasks.task import Task
    from cognee.api.v1.serve.state import get_remote_client
    from stage5_4_5_snapshot import live_snapshot, finish
    from stage5_4_5_storage_snapshot import main as storage_snapshot

    paths = [
        get_base_config().system_root_directory,
        get_relational_config().db_path,
        get_graph_config().graph_file_path,
        get_vectordb_config().vector_db_url,
    ]
    if (
        cognee.__version__ != "1.6.2"
        or backend_access_control_enabled()
        or get_remote_client() is not None
        or not all(Path(p).resolve().is_relative_to(root) for p in paths)
    ):
        raise RuntimeError(
            "Expected local 1.6.2 with every database inside this clone"
        )
    get_cognify_config().triplet_embedding = True
    report = {
        "case": case,
        "clone": str(root),
        "phases": [],
        "noop_calls": [],
    }

    def save():
        (root / "case_results.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n"
        )

    async def capture(name):
        graph_path = root / f"graph_{name}.json"
        storage_path = root / f"storage_{name}.json"
        graph = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        finish(graph, graph_path)
        await storage_snapshot(
            SimpleNamespace(graph=graph_path, output=storage_path)
        )
        storage = json.loads(storage_path.read_text())
        if storage.get("error") or any(
            v["status"] != "captured"
            for v in storage["relational"].values()
        ):
            raise RuntimeError("Incomplete storage capture; inspect its JSON")
        return graph, storage

    async def noop_extract(data):
        report["noop_calls"].append({
            "stage": "extract",
            "input": plain(data),
        })
        return data

    async def noop_enrich(data):
        report["noop_calls"].append({
            "stage": "enrich",
            "input": plain(data),
        })
        return data

    try:
        # Verify the copied Improve watermark.
        # This should not re-embed anything.
        gate = await cognee.improve(
            dataset=DATASET, run_in_background=False
        )
        report["improve_gate_before_memify"] = plain(gate)
        save()
        stage = next(
            s for s in gate.stages if s.stage == "triplet_enrichment"
        )
        if stage.status != "already_completed":
            raise RuntimeError(
                "Baseline Improve did not report already_completed; "
                "stop and inspect"
            )
        before_graph, before_storage = await capture("before")
        if (
            len(before_graph["nodes"]),
            len(before_graph["edges"]),
        ) != (281, 761):
            raise RuntimeError("Unexpected graph baseline")
        if before_storage["vectors"].get(
            "Triplet_text", {}
        ).get("found_count") != 761:
            raise RuntimeError(
                "Expected all 761 triplet vectors in the Improve baseline"
            )

        kwargs = {}
        if case == "empty":
            kwargs = {
                "extraction_tasks": [],
                "enrichment_tasks": [],
            }
        elif case == "noop":
            kwargs = {
                "extraction_tasks": [
                    Task(noop_extract, needs_llm=False)
                ],
                "enrichment_tasks": [
                    Task(noop_enrich, needs_llm=False)
                ],
            }

        for number in range(1, 3 if case == "default" else 2):
            # Truthy synthetic input bypasses implicit graph projection.
            # Native extraction can still independently read the engine.
            result = await cognee.memify(
                dataset=DATASET,
                data=[{"lab_probe": "input-only"}],
                run_in_background=False,
                **kwargs,
            )
            serialized = plain(result)
            report["phases"].append({
                "name": f"memify_{number}",
                "result": serialized,
            })
            save()
            if (
                not isinstance(serialized, dict)
                or not serialized
                or any(
                    v.get("status") != "PipelineRunCompleted"
                    for v in serialized.values()
                )
            ):
                raise RuntimeError(
                    "Memify did not complete; inspect case_results.json"
                )
            after_graph, after_storage = await capture(
                f"after_{number}"
            )
            report["phases"][-1].update({
                "graph_diff": graph_diff(before_graph, after_graph),
                "storage_diff": storage_diff(
                    before_storage, after_storage
                ),
            })
            save()
            before_graph, before_storage = after_graph, after_storage
    except Exception as exc:
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        save()
        raise


def launch(baseline):
    load_dotenv()
    import cognee
    from cognee.base_config import get_base_config
    from cognee.context_global_variables import backend_access_control_enabled
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational.config import get_relational_config
    from cognee.infrastructure.databases.vector.config import get_vectordb_config

    base, graph, rel, vector = (
        get_base_config(),
        get_graph_config(),
        get_relational_config(),
        get_vectordb_config(),
    )
    if (
        cognee.__version__ != "1.6.2"
        or backend_access_control_enabled()
        or graph.graph_database_provider != "ladybug"
        or rel.db_provider != "sqlite"
        or vector.vector_db_provider != "lancedb"
    ):
        raise RuntimeError(
            "Expected shared local 1.6.2 Ladybug/SQLite/LanceDB"
        )

    exporter = Path(__file__).with_name(
        "stage5_4_5_storage_snapshot.py"
    )
    if "await vector.close()" in exporter.read_text():
        raise RuntimeError(
            "Remove await vector.close() from the storage exporter first"
        )

    baseline = baseline.resolve()
    previous = json.loads(
        (baseline / "improve_results.json").read_text()
    )
    if (
        previous.get("dataset_id") != str(DATASET)
        or not any(
            p["name"] == "enabled"
            and p["result"]["status"] == "completed"
            for p in previous.get("phases", [])
        )
    ):
        raise RuntimeError("Choose the successful Improve clone")

    source = baseline / "system"
    original = Path(base.system_root_directory).resolve()
    paths = [
        Path(graph.graph_file_path).resolve(),
        Path(rel.db_path).resolve(),
        Path(vector.vector_db_url).resolve(),
    ]
    if source.resolve() == original or not all(
        p.is_relative_to(original) for p in paths
    ):
        raise RuntimeError(
            "Expected a separate clone with the original storage layout"
        )
    if Path(rel.db_name).name != rel.db_name:
        raise RuntimeError("Expected a plain SQLite filename")

    relative = [p.relative_to(original) for p in paths]
    if (
        not all((source / p).exists() for p in relative)
        or not (source / relative[1] / rel.db_name).is_file()
        or source.is_symlink()
        or any(p.is_symlink() for p in source.rglob("*"))
    ):
        raise RuntimeError(
            "Baseline storage missing or contains symlinks"
        )

    outputs = Path("outputs").resolve()
    if (
        outputs.is_relative_to(source)
        or outputs.is_relative_to(original)
    ):
        raise RuntimeError(
            "Outputs must be outside baseline and original storage"
        )
    outputs.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(
        prefix="stage5_4_5_memify_", dir=outputs
    ))
    summary = {
        "baseline": str(baseline),
        "dataset_id": str(DATASET),
        "cases": [],
    }
    summary_path = root / "memify_results.json"
    print(f"Experiment: {root}", flush=True)

    for case in ["default", "empty", "noop"]:
        child = root / case
        child.mkdir()
        destination = child / "system"
        shutil.copytree(source, destination)
        copied = [destination / p for p in relative]
        for name in ["data", "cache", "logs"]:
            (child / name).mkdir()

        env = os.environ.copy()
        env.update({
            "SYSTEM_ROOT_DIRECTORY": str(destination),
            "DB_PATH": str(copied[1]),
            "DB_NAME": rel.db_name,
            "GRAPH_FILE_PATH": str(copied[0].parent),
            "GRAPH_FILENAME": copied[0].name,
            "VECTOR_DB_URL": str(copied[2]),
            "DATA_ROOT_DIRECTORY": str(child / "data"),
            "CACHE_ROOT_DIRECTORY": str(child / "cache"),
            "LOGS_ROOT_DIRECTORY": str(child / "logs"),
            "COGNEE_LOGS_DIR": str(child / "logs"),
            "ENABLE_BACKEND_ACCESS_CONTROL": "false",
        })
        probe_env = child / "probe.env"
        probe_env.write_text(
            "# Settings supplied by the subprocess environment.\n"
        )
        env["COGNEE_ENV_FILE"] = str(probe_env)

        process = subprocess.run([
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker", str(child),
            "--case", case,
        ], env=env)

        result_path = child / "case_results.json"
        summary["cases"].append(
            json.loads(result_path.read_text())
            if result_path.exists()
            else {"case": case, "error": "Worker produced no report"}
        )
        summary_path.write_text(
            json.dumps(summary, indent=2, default=str) + "\n"
        )
        if process.returncode:
            raise RuntimeError(
                f"Case {case} failed; partial results: {summary_path}"
            )

    print(f"UPLOAD: {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--case", choices=["default", "empty", "noop"])
    args = parser.parse_args()
    if args.worker:
        if not args.case:
            parser.error("--worker requires --case")
        asyncio.run(worker(args.worker.resolve(), args.case))
    else:
        if not args.baseline:
            parser.error(
                "--baseline requires the successful Improve clone directory"
            )
        launch(args.baseline)
