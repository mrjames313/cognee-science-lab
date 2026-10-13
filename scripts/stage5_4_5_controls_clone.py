'Dataset-wide Forget and Recall/Search bookkeeping on isolated clones.\nRequires previous probe scripts. Real embeddings and one answer call.'

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
    import cognee
    from sqlalchemy import select
    from cognee.api.v1.serve.state import get_remote_client
    from cognee.base_config import get_base_config
    from cognee.context_global_variables import (
        backend_access_control_enabled,
        set_session_user_context_variable,
    )
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.infrastructure.databases.relational.config import get_relational_config
    from cognee.infrastructure.databases.vector.config import get_vectordb_config
    from cognee.infrastructure.databases.vector import get_vector_engine_async
    from cognee.infrastructure.databases.cache.config import CacheConfig
    from cognee.infrastructure.files.storage import get_storage_config
    from cognee.infrastructure.session.get_session_manager import get_session_manager
    from cognee.infrastructure.session.session_embeddings import SESSION_QA_VECTOR_COLLECTION
    from cognee.modules.data.models import Data
    from cognee.modules.engine.utils import generate_node_id
    from cognee.modules.pipelines.models import PipelineRun
    from cognee.modules.search.models.Query import Query
    from cognee.modules.search.models.Result import Result
    from cognee.modules.search.types import SearchType
    from cognee.modules.session_lifecycle.models import SessionRecord, SessionModelUsage
    from cognee.modules.users.methods import get_default_user
    from stage5_4_5_snapshot import live_snapshot, finish
    from stage5_4_5_storage_snapshot import main as storage_snapshot

    cache_config = CacheConfig()
    paths = [
        get_base_config().system_root_directory,
        get_relational_config().db_path,
        get_graph_config().graph_file_path,
        get_vectordb_config().vector_db_url,
        get_storage_config()["data_root_directory"],
    ]
    if (
        cognee.__version__ != "1.6.2"
        or backend_access_control_enabled()
        or get_remote_client() is not None
        or not all(Path(p).resolve().is_relative_to(root) for p in paths)
        or cache_config.cache_backend != "sqlite"
        or cache_config.cache_db_url
            != f"sqlite+aiosqlite:///{root / 'cache' / 'sessions.db'}"
        or not cache_config.caching
        or cache_config.auto_feedback
    ):
        raise RuntimeError(
            "Expected isolated local paths, caching on, auto-feedback off"
        )

    user = await get_default_user()
    await set_session_user_context_variable(user)
    engine = get_relational_engine()
    manager = get_session_manager()
    if not manager.is_available:
        raise RuntimeError("Isolated session cache unavailable")

    session_ids = {"reads": f"{root.parent.name}/reads"}
    seen_qa_ids = set()
    files = {}
    report = {
        "case": case,
        "clone": str(root),
        "phases": [],
        "bookkeeping": {},
        "checks": {},
        "session_ids": session_ids,
        "settings": {
            "caching": True,
            "auto_feedback": False,
            "usage_logging": cache_config.usage_logging,
            "session_search_mode": cache_config.session_search_mode,
            "enable_last_accessed": os.getenv("ENABLE_LAST_ACCESSED", "false"),
        },
    }

    def normalize(value):
        return json.loads(json.dumps(plain(value), default=str))

    def save():
        (root / "case_results.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n"
        )

    async def bookkeeping():
        tables = {}
        models = [
            Query, Result, SessionRecord,
            SessionModelUsage, PipelineRun, Data,
        ]
        for model in models:
            async with engine.get_async_session() as session:
                rows = (
                    await session.execute(select(model.__table__))
                ).mappings().all()
            tables[model.__tablename__] = normalize([dict(r) for r in rows])

        qas = {}
        for label, sid in session_ids.items():
            entries = await manager.get_session(
                user_id=str(user.id), session_id=sid
            )
            qas[label] = normalize(entries)
            seen_qa_ids.update(str(e.qa_id) for e in entries if e.qa_id)

        vector = await get_vector_engine_async()
        points = {}
        if await vector.has_collection(SESSION_QA_VECTOR_COLLECTION):
            for qa_id in sorted(seen_qa_ids):
                rows = await vector.retrieve(
                    SESSION_QA_VECTOR_COLLECTION,
                    [qa_id],
                    include_vector=True,
                )
                points[qa_id] = []
                for row in rows:
                    payload = dict(row.payload)
                    values = payload.pop("vector", None)
                    points[qa_id].append({
                        "id": str(row.id),
                        "payload": payload,
                        "vector_dimensions": (
                            len(values) if values is not None else None
                        ),
                        "vector_sha256": (
                            hashlib.sha256(
                                json.dumps(
                                    values, separators=(",", ":")
                                ).encode()
                            ).hexdigest()
                            if values is not None else None
                        ),
                    })

        return {
            "tables": tables,
            "session_qas": qas,
            "session_qa_vectors": points,
            "all_seen_qa_ids": sorted(seen_qa_ids),
        }

    async def capture(name):
        graph = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        graph_path = root / f"graph_{name}.json"
        finish(graph, graph_path)

        # Keep querying original graph IDs and both original dataset scopes.
        query_graph = root / "graph_before.json"
        storage_path = root / f"storage_{name}.json"
        await storage_snapshot(
            SimpleNamespace(graph=query_graph, output=storage_path)
        )
        storage = json.loads(storage_path.read_text())
        if (
            storage.get("error")
            or any(
                v["status"] != "captured"
                for v in storage["relational"].values()
            )
            or any(
                v["status"] not in ["captured", "collection_absent"]
                for v in storage["vectors"].values()
            )
        ):
            raise RuntimeError("Incomplete storage capture")

        report["bookkeeping"][name] = await bookkeeping()
        save()
        return graph, storage

    def unchanged(diff):
        return not any(
            v for group in diff.values() for v in group.values()
        )

    def field_indexes_unchanged(diff):
        return all(
            not any(d[k] for k in ["added", "removed", "changed_records"])
            for d in diff["vectors"].values()
        )

    async def phase(name, call, previous):
        row = {"name": name}
        report["phases"].append(row)
        try:
            row["result"] = normalize(await call())
        except Exception as exc:
            row["error"] = {
                "type": type(exc).__name__, "message": str(exc)
            }
            save()
            raise

        current = await capture(name)
        row["graph_diff"] = graph_diff(previous[0], current[0])
        row["storage_diff"] = storage_diff(previous[1], current[1])
        save()
        return current

    try:
        if case != "reads":
            # Copy and rebind both documents' file locations inside this clone.
            async with engine.get_async_session() as session:
                records = (
                    await session.execute(select(Data))
                ).scalars().all()
                if {str(r.id) for r in records} != {
                    d for _, d in TARGETS.values()
                }:
                    raise RuntimeError("Expected exactly two source records")

                for row in records:
                    for field in [
                        "raw_data_location", "original_data_location"
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
                            dest = root / "data" / (
                                hashlib.sha256(
                                    str(source).encode()
                                ).hexdigest() + source.suffix
                            )
                            shutil.copy2(source, dest)
                            files[str(source)] = {
                                "copy": str(dest),
                                "sha256": digest(source),
                            }
                            if digest(dest) != files[str(source)]["sha256"]:
                                raise RuntimeError(
                                    "Source file changed while copying"
                                )
                        setattr(
                            row, field,
                            Path(files[str(source)]["copy"]).as_uri(),
                        )
                await session.commit()

            report["copied_files"] = files
            for tag, pair in TARGETS.items():
                sid = f"{root.parent.name}/{case}/{tag}"
                session_ids[tag] = sid
                sm = get_session_manager(dataset_id=UUID(pair[0]))
                qa_id = await sm.add_qa(
                    user_id=str(user.id),
                    session_id=sid,
                    question=f"Synthetic session fixture for {tag}",
                    context="Dataset-deletion bookkeeping control.",
                    answer=(
                        f"Synthetic cached answer for {tag}; "
                        "not a scientific assertion."
                    ),
                    used_graph_element_ids={
                        "node_ids": [pair[1]], "edge_ids": []
                    },
                )
                if not qa_id:
                    raise RuntimeError("Could not seed deletion session")

        before = await capture("before")
        if (
            len(before[0]["nodes"]), len(before[0]["edges"])
        ) != (281, 761):
            raise RuntimeError("Unexpected graph baseline")
        if (
            before[0]["graph_metadata"].get("values", {}).get("delete_mode")
            != "graph_native"
        ):
            raise RuntimeError("Expected graph-native ownership")
        if (
            before[1]["vectors"].get("Triplet_text", {}).get("found_count")
            != 761
        ):
            raise RuntimeError("Expected 761 baseline Triplets")

        if case != "reads":
            dataset_id, data_id = TARGETS["DOC01"]
            memory_only = case == "dataset_memory"
            report.update({
                "dataset_id": dataset_id,
                "memory_only": memory_only,
            })
            after = await phase(
                "dataset_forget",
                lambda: cognee.forget(
                    dataset_id=UUID(dataset_id),
                    memory_only=memory_only,
                ),
                before,
            )
            report["analysis"] = analyze(
                before[0], after[0], after[1],
                dataset_id, generate_node_id,
            )
            report["files_after"] = {
                src: {
                    "original_unchanged": (
                        Path(src).is_file()
                        and digest(Path(src)) == info["sha256"]
                    ),
                    "copy_exists": Path(info["copy"]).exists(),
                }
                for src, info in files.items()
            }

            bk = report["bookkeeping"]["dataset_forget"]
            seeded = report["bookkeeping"]["before"]
            deleted_qa = seeded["session_qas"]["DOC01"][0]["qa_id"]
            kept_qa = seeded["session_qas"]["DOC02"][0]["qa_id"]
            report["checks"] = {
                "target_dataset_retained_iff_memory_only": (
                    any(
                        r["id"] == dataset_id
                        for r in after[1]["relational"]["datasets"]["rows"]
                    ) == memory_only
                ),
                "target_data_retained_iff_memory_only": (
                    any(
                        r["id"] == data_id
                        for r in after[1]["relational"]["data"]["rows"]
                    ) == memory_only
                ),
                "target_cached_qa_removed": (
                    not bk["session_qas"]["DOC01"]
                ),
                "other_dataset_cached_qa_retained": (
                    len(bk["session_qas"]["DOC02"]) == 1
                ),
                "seeded_qa_vectors_present_before": all(
                    seeded["session_qa_vectors"].get(q)
                    for q in [deleted_qa, kept_qa]
                ),
                "target_qa_vector_removed": (
                    not bk["session_qa_vectors"].get(deleted_qa)
                ),
                "other_dataset_qa_vector_retained": (
                    bool(bk["session_qa_vectors"].get(kept_qa))
                ),
                "original_source_files_unchanged": all(
                    v["original_unchanged"]
                    for v in report["files_after"].values()
                ),
            }

        else:
            sid = session_ids["reads"]
            query = "What is the EDC controller sampling rate for Helios-1?"
            common = {
                "dataset_ids": [UUID(TARGETS["DOC01"][0])],
                "top_k": 3,
                "session_id": sid,
                "user": user,
                "feedback_influence": 0.0,
            }
            current = await phase(
                "search_chunks",
                lambda: cognee.search(
                    query_text=query,
                    query_type=SearchType.CHUNKS,
                    **common,
                ),
                before,
            )
            current = await phase(
                "recall_context",
                lambda: cognee.recall(
                    query,
                    query_type=SearchType.RAG_COMPLETION,
                    scope="graph",
                    only_context=True,
                    **common,
                ),
                current,
            )
            current = await phase(
                "recall_answer",
                lambda: cognee.recall(
                    query,
                    query_type=SearchType.RAG_COMPLETION,
                    scope="graph",
                    system_prompt=(
                        "Answer briefly using only the supplied context. "
                        "Mention conflicting rates if present."
                    ),
                    **common,
                ),
                current,
            )

            entries = await manager.get_session(
                user_id=str(user.id), session_id=sid
            )
            if not entries:
                raise RuntimeError(
                    "Answer produced no cached QA; inspect partial results"
                )
            qa_id = entries[-1].qa_id

            current = await phase(
                "recall_session",
                lambda: cognee.recall(
                    "EDC controller",
                    scope="session",
                    session_id=sid,
                    user=user,
                ),
                current,
            )
            current = await phase(
                "explicit_feedback",
                lambda: manager.add_feedback(
                    user_id=str(user.id),
                    session_id=sid,
                    qa_id=qa_id,
                    feedback_text="Synthetic bookkeeping fixture feedback.",
                    feedback_score=4,
                ),
                current,
            )

            phases = report["phases"]
            bk = report["bookkeeping"]
            report["checks"] = {
                "graph_and_native_provenance_unchanged_in_each_phase": all(
                    unchanged(p["graph_diff"]) for p in phases
                ),
                "baseline_graph_indexes_unchanged_in_each_phase": all(
                    field_indexes_unchanged(p["storage_diff"])
                    for p in phases
                ),
                "raw_search_did_not_create_session_qa": (
                    not bk["search_chunks"]["session_qas"]["reads"]
                ),
                "context_only_recall_did_not_create_session_qa": (
                    not bk["recall_context"]["session_qas"]["reads"]
                ),
                "answer_created_one_session_qa": (
                    len(bk["recall_answer"]["session_qas"]["reads"]) == 1
                ),
                "answer_session_qa_vector_present": (
                    bool(
                        bk["recall_answer"]["session_qa_vectors"].get(qa_id)
                    )
                ),
                "session_recall_added_no_qa": (
                    bk["recall_session"]["session_qas"]
                    == bk["recall_answer"]["session_qas"]
                ),
                "session_recall_returned_a_hit": bool(
                    next(
                        p for p in phases
                        if p["name"] == "recall_session"
                    )["result"]
                ),
                "feedback_updated_cached_score": (
                    bk["explicit_feedback"]["session_qas"]["reads"][0][
                        "feedback_score"
                    ] == 4
                ),
            }

        report["all_checks_passed"] = all(report["checks"].values())
        save()
    except Exception as exc:
        report["error"] = {
            "type": type(exc).__name__, "message": str(exc)
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
        prefix="stage5_4_5_controls_", dir=outputs
    ))
    summary = {"baseline": str(baseline), "cases": []}
    summary_path = root / "controls_results.json"
    print(f"Experiment: {root}", flush=True)

    for case in ["dataset_full", "dataset_memory", "reads"]:
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

        env.update({"CACHING": "true", "AUTO_FEEDBACK": "false", "USAGE_LOGGING": "false"})
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
    parser.add_argument("--case", choices=["dataset_full", "dataset_memory", "reads"])
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
