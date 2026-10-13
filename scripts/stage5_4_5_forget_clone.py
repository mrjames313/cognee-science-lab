"""Full public Forget for DOC01 and DOC02 on separate Improve-baseline copies.

Requires all prior Stage 5.4.5 probe scripts alongside this file.
Copies and rebinds stored source files before deletion. No model calls.
"""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlparse
from uuid import UUID

from dotenv import load_dotenv
from stage5_4_5_improve_clone import DATASET, graph_diff
from stage5_4_5_memify_clone import plain, storage_diff


TARGETS = {
    "DOC01": (
        "c0e2ff53-9ea8-5752-941a-04502805bc5c",
        "d49200c9-3f11-44f0-976e-b3daba720957",
    ),
    "DOC02": (
        "88e9627a-9304-5637-aff3-a561c0d93daa",
        "a6e0a1a3-6d19-4bb9-adfe-d021a71942da",
    ),
}
SUPPORT = {
    "AbbreviationObservation",
    "IdentityResolution",
    "Mention",
    "DefinitionSummary",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(location):
    parsed = urlparse(location)
    if parsed.scheme == "file" and parsed.netloc in ("", "localhost"):
        return Path(unquote(parsed.path)).resolve()
    if not parsed.scheme:
        return Path(location).resolve()
    raise RuntimeError(
        "Source file is not local; this probe requires local stored files"
    )


def analyze(before, after, storage, dataset_id, generate_node_id):
    bnodes = {n["id"]: n["properties"] for n in before["nodes"]}
    anodes = {n["id"]: n["properties"] for n in after["nodes"]}
    removed_nodes = bnodes.keys() - anodes.keys()

    key = lambda e: (
        e["source_id"], e["relationship"], e["target_id"]
    )
    bedges = {key(e): e for e in before["edges"]}
    aedges = {key(e): e for e in after["edges"]}
    triplets = {
        r["id"]
        for r in storage["vectors"].get(
            "Triplet_text", {}
        ).get("rows", [])
    }

    remaining_deleted_triplets = [
        list(e)
        for e in sorted(bedges.keys() - aedges.keys())
        if str(generate_node_id("".join(e))) in triplets
    ]
    missing_surviving_triplets = [
        list(e)
        for e in sorted(bedges.keys() & aedges.keys())
        if str(generate_node_id("".join(e))) not in triplets
    ]

    shared = {
        nid: n
        for nid, n in before["native_provenance"]["nodes"].items()
        if dataset_id in n["source_dataset_ids"]
        and len(n["source_dataset_ids"]) > 1
    }
    shared_after = {
        nid: after["native_provenance"]["nodes"].get(
            nid, {}
        ).get("source_dataset_ids")
        for nid in sorted(shared)
    }

    support = []
    for nid, props in sorted(bnodes.items()):
        if props.get("type") not in SUPPORT:
            continue
        exists = nid in anodes
        stale = {
            field: value
            for field, value in anodes.get(nid, {}).items()
            if field.endswith("_id")
            and isinstance(value, str)
            and value in removed_nodes
        }
        support.append({
            "id": nid,
            "type": props["type"],
            "survives": exists,
            "stale_node_references": stale,
            "lost_incident_edges": sum(
                nid in (e[0], e[2])
                for e in bedges.keys() - aedges.keys()
            ),
            "remaining_incident_edges": sum(
                nid in (e[0], e[2]) for e in aedges
            ),
        })

    orphan_node_vectors = []
    for nid in sorted(removed_nodes):
        native = before["native_provenance"]["nodes"][nid]
        for field in native["indexed_fields"]:
            collection = f"{native['node_type']}_{field}"
            rows = storage["vectors"].get(
                collection, {}
            ).get("rows", [])
            if any(r["id"] == nid for r in rows):
                orphan_node_vectors.append({
                    "collection": collection,
                    "id": nid,
                })

    return {
        "before_counts": {
            "nodes": len(bnodes),
            "edges": len(bedges),
        },
        "after_counts": {
            "nodes": len(anodes),
            "edges": len(aedges),
        },
        "shared_nodes_after_dataset_ids": shared_after,
        "support_objects": support,
        "deleted_edge_triplets_still_present":
            remaining_deleted_triplets,
        "surviving_edge_triplets_missing":
            missing_surviving_triplets,
        "deleted_node_vectors_still_present":
            orphan_node_vectors,
    }


async def worker(root, case):
    load_dotenv()
    import cognee
    from sqlalchemy import select
    from cognee.api.v1.serve.state import get_remote_client
    from cognee.base_config import get_base_config
    from cognee.context_global_variables import backend_access_control_enabled
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.infrastructure.databases.relational.config import get_relational_config
    from cognee.infrastructure.databases.vector.config import get_vectordb_config
    from cognee.infrastructure.databases.cache.config import get_cache_config
    from cognee.infrastructure.files.storage import get_storage_config
    from cognee.modules.data.models import Data
    from cognee.modules.engine.utils import generate_node_id
    from stage5_4_5_snapshot import live_snapshot, finish
    from stage5_4_5_storage_snapshot import main as storage_snapshot

    paths = [
        get_base_config().system_root_directory,
        get_relational_config().db_path,
        get_graph_config().graph_file_path,
        get_vectordb_config().vector_db_url,
        get_storage_config()["data_root_directory"],
    ]
    expected_cache_url = (
        f"sqlite+aiosqlite:///{root / 'cache' / 'sessions.db'}"
    )
    if (
        cognee.__version__ != "1.6.2"
        or backend_access_control_enabled()
        or get_remote_client() is not None
        or not all(
            Path(p).resolve().is_relative_to(root) for p in paths
        )
        or get_cache_config().cache_backend != "sqlite"
        or get_cache_config().cache_db_url != expected_cache_url
    ):
        raise RuntimeError(
            "Expected isolated local 1.6.2 database, file, and cache paths"
        )

    dataset_id, data_id = TARGETS[case]
    report = {
        "case": case,
        "clone": str(root),
        "dataset_id": dataset_id,
        "data_id": data_id,
        "memory_only": False,
        "session_cache":
            "fresh isolated cache; session invalidation not measured",
    }

    def save():
        (root / "case_results.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n"
        )

    files = {}
    try:
        # Relocate source-file references in the COPY before deletion.
        engine = get_relational_engine()
        async with engine.get_async_session() as session:
            records = (
                await session.execute(select(Data))
            ).scalars().all()

            if {str(r.id) for r in records} != {
                d for _, d in TARGETS.values()
            }:
                raise RuntimeError(
                    "Expected exactly the two source data records"
                )

            for row in records:
                for field in [
                    "raw_data_location",
                    "original_data_location",
                ]:
                    location = getattr(row, field)
                    if not location:
                        continue
                    source = local_path(location)
                    if not source.is_file():
                        raise RuntimeError(
                            f"Stored source file missing: {source}"
                        )
                    if str(source) not in files:
                        filename = (
                            hashlib.sha256(
                                str(source).encode()
                            ).hexdigest()
                            + source.suffix
                        )
                        destination = root / "data" / filename
                        shutil.copy2(source, destination)
                        files[str(source)] = {
                            "copy": str(destination),
                            "sha256": digest(source),
                        }
                        if digest(destination) != files[
                            str(source)
                        ]["sha256"]:
                            raise RuntimeError(
                                "Source file changed while being copied"
                            )
                    setattr(
                        row,
                        field,
                        Path(files[str(source)]["copy"]).as_uri(),
                    )
            await session.commit()

        report["copied_files"] = files
        save()

        before = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        finish(before, root / "graph_before.json")
        if (
            len(before["nodes"]), len(before["edges"])
        ) != (281, 761):
            raise RuntimeError("Unexpected graph baseline")
        if before["graph_metadata"].get(
            "values", {}
        ).get("delete_mode") != "graph_native":
            raise RuntimeError(
                "Expected graph-native source ownership mode"
            )

        await storage_snapshot(SimpleNamespace(
            graph=root / "graph_before.json",
            output=root / "storage_before.json",
        ))
        before_storage = json.loads(
            (root / "storage_before.json").read_text()
        )
        if before_storage.get("error") or any(
            v["status"] != "captured"
            for v in before_storage["relational"].values()
        ):
            raise RuntimeError(
                "Incomplete baseline storage capture"
            )

        target = next(
            r
            for r in before_storage["relational"]["data"]["rows"]
            if r["id"] == data_id
        )
        if (
            target["dataset_id"] != dataset_id
            or before_storage["vectors"].get(
                "Triplet_text", {}
            ).get("found_count") != 761
        ):
            raise RuntimeError(
                "Wrong source ownership or incomplete triplet baseline"
            )

        report["forget_result"] = plain(await cognee.forget(
            dataset_id=UUID(dataset_id),
            data_id=UUID(data_id),
            memory_only=False,
        ))
        save()

        after = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        finish(after, root / "graph_after.json")

        # Query PRE-DELETION IDs and both original dataset scopes.
        # Surviving-graph-only queries would hide orphan vectors/evidence.
        await storage_snapshot(SimpleNamespace(
            graph=root / "graph_before.json",
            output=root / "storage_after.json",
        ))
        after_storage = json.loads(
            (root / "storage_after.json").read_text()
        )
        for state in [before_storage, after_storage]:
            if state.get("error") or any(
                v["status"] != "captured"
                for v in state["relational"].values()
            ):
                raise RuntimeError(
                    "Incomplete storage capture; inspect JSON"
                )

        report.update({
            "graph_diff": graph_diff(before, after),
            "storage_diff": storage_diff(
                before_storage, after_storage
            ),
            "analysis": analyze(
                before,
                after,
                after_storage,
                dataset_id,
                generate_node_id,
            ),
            "files_after": {
                src: {
                    "original_unchanged": (
                        Path(src).is_file()
                        and digest(Path(src)) == v["sha256"]
                    ),
                    "copy_exists": Path(v["copy"]).exists(),
                }
                for src, v in files.items()
            },
        })
        save()
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
            "Expected a separate baseline with the original storage layout"
        )
    relative = [p.relative_to(original) for p in paths]
    if (
        Path(rel.db_name).name != rel.db_name
        or not all((source / p).exists() for p in relative)
        or not (source / relative[1] / rel.db_name).is_file()
        or source.is_symlink()
        or any(p.is_symlink() for p in source.rglob("*"))
    ):
        raise RuntimeError(
            "Invalid baseline storage layout or symlinks"
        )

    outputs = Path("outputs").resolve()
    if (
        outputs.is_relative_to(source)
        or outputs.is_relative_to(original)
    ):
        raise RuntimeError(
            "Outputs must be outside source storage"
        )
    outputs.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(
        prefix="stage5_4_5_forget_", dir=outputs
    ))
    summary = {"baseline": str(baseline), "cases": []}
    summary_path = root / "forget_results.json"
    print(f"Experiment: {root}", flush=True)

    for case in TARGETS:
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
            "CACHE_BACKEND": "sqlite",
            "CACHE_DB_URL":
                f"sqlite+aiosqlite:///{child / 'cache' / 'sessions.db'}",
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
            else {"case": case, "error": "No worker report"}
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
    parser.add_argument("--case", choices=list(TARGETS))
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
