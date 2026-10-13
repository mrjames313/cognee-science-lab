"""Compare native Update eligibility and project-model rebuild for DOC01.

Requires all previous Stage 5.4.5 probe scripts alongside this file.
Uses real LLM/embedding calls on separate copies of the Improve baseline.
"""

import argparse
import asyncio
import hashlib
import importlib
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
from stage5_4_5_improve_clone import DATASET, graph_diff
from stage5_4_5_memify_clone import plain, storage_diff
from stage5_4_5_forget_clone import TARGETS, analyze, digest, local_path


CASES = ["native_candidate", "project_rebuild"]


def union_candidates(before, after):
    """Keep old and new IDs, fields, relationship texts, and dataset scopes."""
    result = dict(before)
    native = dict(before["native_provenance"]["nodes"])
    for nid, row in after["native_provenance"]["nodes"].items():
        old = native.get(nid, {})
        native[nid] = dict(
            row,
            indexed_fields=sorted(
                set(old.get("indexed_fields", []))
                | set(row["indexed_fields"])
            ),
            source_dataset_ids=sorted(
                set(old.get("source_dataset_ids", []))
                | set(row["source_dataset_ids"])
            ),
        )
    result["native_provenance"] = dict(
        before["native_provenance"],
        nodes=native,
        edges=(
            before["native_provenance"]["edges"]
            + after["native_provenance"]["edges"]
        ),
    )
    result["edges"] = before["edges"] + after["edges"]
    return result


def chunk_rows(graph, data_id):
    ids = {
        e["source_id"]
        for e in graph["edges"]
        if e["relationship"] == "is_part_of"
        and e["target_id"] == data_id
    }
    return {
        n["id"]: n["properties"]
        for n in graph["nodes"]
        if n["id"] in ids
        and n["properties"].get("type") == "DocumentChunk"
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
    from cognee.modules.cognify.config import get_cognify_config
    from cognee.modules.data.models import Data
    from cognee.modules.engine.utils import generate_node_id
    from cognee_lab.models import MixedKnowledgeGraph
    from stage5_4_5_snapshot import live_snapshot, finish
    from stage5_4_5_storage_snapshot import main as storage_snapshot

    paths = [
        get_base_config().system_root_directory,
        get_relational_config().db_path,
        get_graph_config().graph_file_path,
        get_vectordb_config().vector_db_url,
        get_storage_config()["data_root_directory"],
    ]
    cache_url = (
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
        or get_cache_config().cache_db_url != cache_url
    ):
        raise RuntimeError(
            "Expected isolated local 1.6.2 storage and cache paths"
        )

    dataset_id, data_id = TARGETS["DOC01"]
    report = {
        "case": case,
        "clone": str(root),
        "dataset_id": dataset_id,
        "data_id": data_id,
        "triplet_embedding": get_cognify_config().triplet_embedding,
        "maintenance_replay": False,
        "core_cognify_calls": [],
        "retirement_checkpoints": [],
        "session_cache":
            "fresh isolated cache; invalidation not measured",
    }
    module = importlib.import_module(
        "cognee.api.v1.update.update"
    )
    actual_forget = module.forget
    actual_cognify = module.cognify
    files = {}

    def save():
        (root / "case_results.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n"
        )

    async def storage_read(graph, name):
        candidates = root / f"candidates_{name}.json"
        candidates.write_text(json.dumps(graph, default=str))
        output = root / f"storage_{name}.json"
        await storage_snapshot(
            SimpleNamespace(graph=candidates, output=output)
        )
        result = json.loads(output.read_text())
        if result.get("error") or any(
            v["status"] != "captured"
            for v in result["relational"].values()
        ):
            raise RuntimeError(
                f"Incomplete storage capture: {name}"
            )
        return result

    async def observed_forget(*args, **kwargs):
        result = await actual_forget(*args, **kwargs)
        retired = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        finish(retired, root / "graph_retired.json")
        storage = await storage_read(before, "retired")
        report["retirement_checkpoints"].append({
            "memory_only": kwargs.get("memory_only"),
            "result": plain(result),
            "graph_diff": graph_diff(before, retired),
            "storage_diff": storage_diff(
                before_storage, storage
            ),
            "analysis": analyze(
                before, retired, storage,
                dataset_id, generate_node_id,
            ),
        })
        save()
        return result

    async def observed_cognify(*args, **kwargs):
        model = kwargs.get("graph_model")
        report["core_cognify_calls"].append({
            "graph_model": getattr(model, "__name__", None),
            "chunk_size": kwargs.get("chunk_size"),
            "custom_prompt_supplied":
                kwargs.get("custom_prompt") is not None,
        })
        save()
        return await actual_cognify(*args, **kwargs)

    try:
        engine = get_relational_engine()
        async with engine.get_async_session() as session:
            records = (
                await session.execute(select(Data))
            ).scalars().all()
            if {str(r.id) for r in records} != {
                d for _, d in TARGETS.values()
            }:
                raise RuntimeError(
                    "Expected the two original source data records"
                )
            target = next(
                r for r in records if str(r.id) == data_id
            )
            if (
                str(target.dataset_id) != dataset_id
                or not target.original_data_location
            ):
                raise RuntimeError(
                    "Wrong DOC01 ownership or missing original file"
                )

            original_input = local_path(
                target.original_data_location
            )
            old_text = original_input.read_text(encoding="utf-8")
            if (
                original_input.suffix != ".md"
                or old_text.count("10 kHz") != 2
            ):
                raise RuntimeError(
                    "Expected DOC01 markdown with exactly "
                    "two 10 kHz references"
                )
            edited = old_text.replace("10 kHz", "12 kHz")
            replacement = root / "input" / original_input.name
            replacement.parent.mkdir()
            replacement.write_text(edited, encoding="utf-8")
            report["edit"] = {
                "old": "10 kHz",
                "new": "12 kHz",
                "occurrences": 2,
                "old_sha256": hashlib.sha256(
                    old_text.encode()
                ).hexdigest(),
                "new_sha256": digest(replacement),
            }

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
                                "Source changed during copying"
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
            (len(before["nodes"]), len(before["edges"]))
            != (281, 761)
            or before["graph_metadata"].get(
                "values", {}
            ).get("delete_mode") != "graph_native"
        ):
            raise RuntimeError(
                "Unexpected shared graph-native baseline"
            )

        config = get_cognify_config()
        config.triplet_embedding = True
        try:
            prime = await cognee.improve(
                dataset=UUID(dataset_id), run_in_background=False
            )
        finally:
            config.triplet_embedding = report["triplet_embedding"]
        report["watermark_prime"] = plain(prime)
        save()
        prime_stage = next(
            s for s in prime.stages if s.stage == "triplet_enrichment"
        )
        if prime.status == "errored" or prime_stage.status != "completed":
            raise RuntimeError("Expected a newly completed DOC01 enrichment")
        primed_graph = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        if any(
            ids for change in graph_diff(before, primed_graph).values()
            for ids in change.values()
        ):
            raise RuntimeError("Priming unexpectedly changed the graph")
        before_storage = await storage_read(before, "before")
        if before_storage["vectors"].get(
            "Triplet_text", {}
        ).get("found_count") != 761:
            raise RuntimeError(
                "Expected the completed Improve triplet baseline"
            )

        # Read-only checkpoints around the real native rebuild calls.
        module.forget = observed_forget
        module.cognify = observed_cognify
        kwargs = (
            {"graph_model": MixedKnowledgeGraph}
            if case == "project_rebuild"
            else {}
        )
        report["update_result"] = plain(await cognee.update(
            data_id=UUID(data_id),
            dataset_id=UUID(dataset_id),
            data=str(replacement),
            chunk_level_diff=True,
            **kwargs,
        ))
        save()

        after = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        finish(after, root / "graph_after.json")
        after_storage = await storage_read(
            union_candidates(before, after), "after"
        )
        bchunks = chunk_rows(before, data_id)
        achunks = chunk_rows(after, data_id)
        present_triplets = {
            r["id"]
            for r in after_storage["vectors"].get(
                "Triplet_text", {}
            ).get("rows", [])
        }
        missing_after = [
            [e["source_id"], e["relationship"], e["target_id"]]
            for e in after["edges"]
            if str(generate_node_id(
                e["source_id"]
                + e["relationship"]
                + e["target_id"]
            )) not in present_triplets
        ]
        target_rows = [
            r
            for r in after_storage["relational"]["data"]["rows"]
            if r["id"] == data_id
        ]
        async with engine.get_async_session() as session:
            refreshed = (
                await session.execute(
                    select(Data).where(Data.id == UUID(data_id))
                )
            ).scalars().one()
            stored_text = local_path(
                refreshed.raw_data_location
            ).read_text(encoding="utf-8")
            published = {
                "data_id": str(refreshed.id),
                "name": refreshed.name,
                "content_hash": refreshed.content_hash,
                "old_rate_occurrences":
                    stored_text.count("10 kHz"),
                "new_rate_occurrences":
                    stored_text.count("12 kHz"),
                "raw_path_inside_clone": local_path(
                    refreshed.raw_data_location
                ).is_relative_to(root),
            }

        report.update({
            "graph_diff": graph_diff(before, after),
            "storage_diff": storage_diff(
                before_storage, after_storage
            ),
            "analysis": analyze(
                before, after, after_storage,
                dataset_id, generate_node_id,
            ),
            "chunks": {
                "before_count": len(bchunks),
                "after_count": len(achunks),
                "removed_ids": sorted(
                    bchunks.keys() - achunks.keys()
                ),
                "added_ids": sorted(
                    achunks.keys() - bchunks.keys()
                ),
                "retained_ids": sorted(
                    bchunks.keys() & achunks.keys()
                ),
                "changed_retained_ids": sorted(
                    k
                    for k in bchunks.keys() & achunks.keys()
                    if bchunks[k] != achunks[k]
                ),
            },
            "missing_triplets_for_after_graph": missing_after,
            "target_data_rows_after": target_rows,
            "published_text": published,
            "original_files_unchanged": {
                src: (
                    Path(src).is_file()
                    and digest(Path(src)) == v["sha256"]
                )
                for src, v in files.items()
            },
        })
        save()
        if report["update_result"].get("status") == "failed":
            raise RuntimeError(
                "Update reported failure; captured partial state "
                "in case_results.json"
            )
        if (
            len(target_rows) != 1
            or published["data_id"] != data_id
            or published["old_rate_occurrences"] != 0
            or published["new_rate_occurrences"] != 2
            or not published["raw_path_inside_clone"]
            or not all(
                report["original_files_unchanged"].values()
            )
        ):
            raise RuntimeError(
                "Update identity, published text, "
                "or file-isolation check failed"
            )
        get_cognify_config().triplet_embedding = True
        gate = await cognee.improve(
            dataset=UUID(dataset_id), run_in_background=False
        )
        report["watermark_after_update"] = plain(gate)
        save()
        if gate.status == "errored":
            raise RuntimeError("Post-Update Improve reported an error")
        final_graph = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        finish(final_graph, root / "graph_after_improve.json")
        final_storage = await storage_read(
            union_candidates(before, final_graph), "after_improve"
        )
        report["improve_after_update_diff"] = {
            "graph": graph_diff(after, final_graph),
            "storage": storage_diff(after_storage, final_storage),
        }
        rows = final_storage["vectors"].get("Triplet_text", {}).get("rows", [])
        indexed_ids = {r["id"] for r in rows}
        expected_ids = {
            str(generate_node_id(
                e["source_id"] + e["relationship"] + e["target_id"]
            ))
            for e in final_graph["edges"]
        }
        report["triplet_coverage_after_improve"] = {
            "current_graph_edge_count": len(final_graph["edges"]),
            "current_graph_triplets_present": len(expected_ids & indexed_ids),
            "current_graph_triplets_missing": len(expected_ids - indexed_ids),
            "associated_triplet_records": len(indexed_ids),
            "indexed_triplets_without_current_edges": sorted(indexed_ids - expected_ids),
        }
        save()
    except Exception as exc:
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        save()
        raise
    finally:
        module.forget = actual_forget
        module.cognify = actual_cognify


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
        prefix="stage5_4_5_watermark_", dir=outputs
    ))
    summary = {"baseline": str(baseline), "cases": []}
    summary_path = root / "watermark_results.json"
    print(f"Experiment: {root}", flush=True)

    for case in CASES:
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
    parser.add_argument("--case", choices=CASES)
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
