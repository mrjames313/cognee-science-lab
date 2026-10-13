"""Characterize custom writes, source context, and scientific prototype objects.

Requires the prior Stage 5.4.5 probe scripts alongside this file.
Uses a cloned store and memory-only Forget. Real embeddings; no LLM extraction.
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
from stage5_4_5_improve_clone import DATASET


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


async def worker(root, case):
    from dataclasses import replace
    from sqlalchemy import select
    import cognee

    from cognee.api.v1.serve.state import get_remote_client
    from cognee.base_config import get_base_config
    from cognee.context_global_variables import backend_access_control_enabled
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.infrastructure.databases.relational.config import get_relational_config
    from cognee.infrastructure.databases.vector import get_vector_engine_async
    from cognee.infrastructure.databases.vector.config import get_vectordb_config
    from cognee.infrastructure.databases.cache.config import get_cache_config
    from cognee.infrastructure.engine import DataPoint
    from cognee.modules.data.models import Data
    from cognee.modules.engine.utils import generate_node_id
    from cognee.modules.pipelines.tasks.task import Task
    from cognee.modules.provenance.edge_evidence.models import ProvenanceEdgeEvidence
    from cognee.infrastructure.databases.provenance import (
        make_source_ref_key,
        data_item_id,
    )
    from cognee.tasks.storage import add_data_points
    from stage5_4_5_snapshot import live_snapshot
    from stage5_4_5_memify_clone import plain

    paths = [
        get_base_config().system_root_directory,
        get_relational_config().db_path,
        get_graph_config().graph_file_path,
        get_vectordb_config().vector_db_url,
        get_base_config().data_root_directory,
    ]
    expected_cache = f"sqlite+aiosqlite:///{root / 'cache' / 'sessions.db'}"
    if (
        cognee.__version__ != "1.6.2"
        or backend_access_control_enabled()
        or get_remote_client() is not None
        or not all(Path(p).resolve().is_relative_to(root) for p in paths)
        or get_cache_config().cache_backend != "sqlite"
        or get_cache_config().cache_db_url != expected_cache
    ):
        raise RuntimeError("Expected isolated local database and cache paths")

    class ProbeMeasurement(DataPoint):
        name: str
        value: float
        unit: str
        metadata: dict = {
            "identity_fields": ["name"],
            "index_fields": ["name"],
        }

    class ProbeEvidence(DataPoint):
        name: str
        text: str
        source_document_id: str
        observed: ProbeMeasurement | None = None
        metadata: dict = {
            "identity_fields": ["name"],
            "index_fields": ["text"],
        }

    class ProbeClaim(DataPoint):
        name: str
        proposition: str
        status: str = "asserted"
        source_document_id: str | None = None
        measurement: ProbeMeasurement | None = None
        evidence: ProbeEvidence | None = None
        supersedes: "ProbeClaim | None" = None
        metadata: dict = {
            "identity_fields": ["name"],
            "index_fields": ["proposition"],
        }

    ProbeClaim.model_rebuild(
        _types_namespace={
            "ProbeClaim": ProbeClaim,
            "ProbeEvidence": ProbeEvidence,
            "ProbeMeasurement": ProbeMeasurement,
        }
    )

    engine = get_relational_engine()
    async with engine.get_async_session() as session:
        records = (await session.execute(select(Data))).scalars().all()

    sources = {
        tag: next(r for r in records if str(r.id) == pair[1])
        for tag, pair in TARGETS.items()
    }
    if any(str(sources[tag].dataset_id) != TARGETS[tag][0] for tag in sources):
        raise RuntimeError("Wrong source dataset membership")

    prefix = root.parent.name
    objects = {}

    def bundle(mode):
        measurement = ProbeMeasurement(
            name=f"{prefix}/{mode}/measurement",
            value=10,
            unit="kHz",
        )
        evidence = ProbeEvidence(
            name=f"{prefix}/{mode}/evidence",
            text="Fixture observation: 10 kHz.",
            source_document_id=TARGETS["DOC01"][1],
            observed=measurement,
        )
        claim = ProbeClaim(
            name=f"{prefix}/{mode}/claim",
            proposition="Fixture rate is 10 kHz.",
            source_document_id=TARGETS["DOC01"][1],
            measurement=measurement,
            evidence=evidence,
        )
        for item in [measurement, evidence, claim]:
            objects[str(item.id)] = item
        return claim

    none_claim, run_claim, owned_claim = [
        bundle(mode) for mode in ["none", "run", "owned"]
    ]
    revised_measurement = owned_claim.measurement.model_copy(
        update={"value": 12}
    )
    revision_evidence = ProbeEvidence(
        name=f"{prefix}/revision/evidence",
        text="Fixture correction: 12 kHz.",
        source_document_id=TARGETS["DOC02"][1],
        observed=revised_measurement,
    )
    revision = ProbeClaim(
        name=f"{prefix}/revision/claim",
        proposition="Fixture rate is 12 kHz.",
        source_document_id=TARGETS["DOC02"][1],
        measurement=revised_measurement,
        evidence=revision_evidence,
        supersedes=owned_claim,
    )
    for item in [revision, revision_evidence]:
        objects[str(item.id)] = item

    report = {
        "clone": str(root),
        "scope": "custom_tasks_and_source_context",
        "scientific_models": (
            "minimal characterization fixture, not a production schema"
        ),
        "snapshots": {},
        "runs": [],
        "checks": {},
        "task_contexts": [],
        "ids": {
            "no_context": str(none_claim.id),
            "run_context": str(run_claim.id),
            "owned": str(owned_claim.id),
            "shared_measurement": str(owned_claim.measurement.id),
            "revision": str(revision.id),
            "all_fixture_ids": sorted(objects),
        },
    }
    seen_triplets = set()

    def save():
        (root / "case_results.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n"
        )

    async def capture(name):
        graph = await live_snapshot(
            SimpleNamespace(dataset_id=None, owner_id=None)
        )
        nodes = {
            n["id"]: n["properties"]
            for n in graph["nodes"]
            if n["id"] in objects
        }
        edges = [
            e for e in graph["edges"]
            if e["source_id"] in objects or e["target_id"] in objects
        ]
        for e in edges:
            seen_triplets.add(
                str(generate_node_id(
                    e["source_id"] + e["relationship"] + e["target_id"]
                ))
            )

        vector = await get_vector_engine_async()
        points = {}
        for nid, obj in objects.items():
            for field in obj.metadata["index_fields"]:
                collection = f"{type(obj).__name__}_{field}"
                rows = (
                    await vector.retrieve(collection, [nid])
                    if await vector.has_collection(collection)
                    else []
                )
                points[f"{collection}/{nid}"] = [
                    {"id": str(r.id), "payload": dict(r.payload)}
                    for r in rows
                ]

        present_triplets = []
        if await vector.has_collection("Triplet_text"):
            for tid in sorted(seen_triplets):
                if await vector.retrieve("Triplet_text", [tid]):
                    present_triplets.append(tid)

        async with engine.get_async_session() as session:
            evidence_rows = (
                await session.execute(
                    select(ProvenanceEdgeEvidence.__table__).where(
                        ProvenanceEdgeEvidence.dataset_id.in_(
                            [UUID(p[0]) for p in TARGETS.values()]
                        )
                    )
                )
            ).mappings().all()

        fixture_evidence = [
            dict(r) for r in evidence_rows
            if str(r["source_node_id"]) in objects
            or str(r["destination_node_id"]) in objects
        ]
        result = {
            "whole_graph_counts": {
                "nodes": len(graph["nodes"]),
                "edges": len(graph["edges"]),
            },
            "nodes": nodes,
            "edges": edges,
            "native_nodes": {
                nid: row
                for nid, row in graph["native_provenance"]["nodes"].items()
                if nid in objects
            },
            "native_edges": [
                e for e in graph["native_provenance"]["edges"]
                if e["edge"]["source_id"] in objects
                or e["edge"]["target_id"] in objects
            ],
            "field_vectors": points,
            "triplet_ids_present": present_triplets,
            "all_seen_triplet_ids": sorted(seen_triplets),
            "fixture_relational_evidence": fixture_evidence,
            "total_source_evidence_rows": len(evidence_rows),
        }
        report["snapshots"][name] = result
        save()
        return result

    async def passthrough(data):
        return data

    async def run_task(name, fn, tag="DOC01"):
        result = await cognee.memify(
            dataset=UUID(TARGETS[tag][0]),
            data=[{"fixture_task": name}],
            extraction_tasks=[Task(passthrough, needs_llm=False)],
            enrichment_tasks=[Task(fn, needs_llm=False)],
            run_in_background=False,
        )
        serialized = plain(result)
        report["runs"].append({"name": name, "result": serialized})
        save()
        if not serialized or any(
            v.get("status") != "PipelineRunCompleted"
            for v in serialized.values()
        ):
            raise RuntimeError(f"Custom Task failed: {name}")

    def note(ctx, label):
        source_id = data_item_id(ctx.data_item)
        report["task_contexts"].append({
            "task": label,
            "dataset_id": str(ctx.dataset.id),
            "pipeline_run_id": str(ctx.pipeline_run_id),
            "incoming_data_item_type": type(ctx.data_item).__name__,
            "incoming_source_data_id": (
                str(source_id) if source_id else None
            ),
        })

    async def write_run_context(data, ctx=None):
        note(ctx, "write_run_context")
        await add_data_points(
            [run_claim], ctx=ctx, embed_triplets=True
        )
        return data

    async def write_bound_source(data, ctx=None):
        note(ctx, "write_bound_source")
        await add_data_points(
            [owned_claim],
            ctx=replace(ctx, data_item=sources["DOC01"]),
            embed_triplets=True,
        )
        return data

    async def patch_claim(data, ctx=None):
        graph = await get_graph_engine()
        if not await graph.update_node(
            str(owned_claim.id),
            {"lab_patch": "kept", "status": "reviewed"},
        ):
            raise RuntimeError("Patch did not find the claim")
        return data

    async def upsert_claim(data, ctx=None):
        fresh = ProbeClaim(
            id=owned_claim.id,
            name=owned_claim.name,
            proposition=owned_claim.proposition,
        )
        await add_data_points([fresh], embed_triplets=True)
        return data

    async def write_revision(data, ctx=None):
        note(ctx, "write_revision")
        owned_claim.status = "superseded"
        owned_claim.measurement = revised_measurement
        owned_claim.evidence.observed = revised_measurement
        await add_data_points(
            [revision],
            ctx=replace(ctx, data_item=sources["DOC02"]),
            embed_triplets=True,
        )
        return data

    try:
        baseline = await capture("baseline")
        if baseline["nodes"]:
            raise RuntimeError("Fixture IDs unexpectedly exist in baseline")

        await add_data_points([none_claim], embed_triplets=True)
        await run_task("run_context_without_source", write_run_context)
        await run_task("bound_source_context", write_bound_source)
        seeded = await capture("seeded")

        await run_task("targeted_patch", patch_claim)
        patched = await capture("patched")

        await run_task("full_upsert_without_context", upsert_claim)
        upserted = await capture("upserted")

        await run_task("source_bound_revision", write_revision, "DOC02")
        shared = await capture("shared")

        for tag in ["DOC01", "DOC02"]:
            result = await cognee.forget(
                dataset_id=UUID(TARGETS[tag][0]),
                data_id=UUID(TARGETS[tag][1]),
                memory_only=True,
            )
            report.setdefault("forget_results", {})[tag] = plain(result)
            await capture(f"after_{tag}")

        ref_a = make_source_ref_key(
            UUID(TARGETS["DOC01"][0]), UUID(TARGETS["DOC01"][1])
        )
        ref_b = make_source_ref_key(
            UUID(TARGETS["DOC02"][0]), UUID(TARGETS["DOC02"][1])
        )
        oid = str(owned_claim.id)
        mid = str(owned_claim.measurement.id)
        rid = str(revision.id)
        after_a = report["snapshots"]["after_DOC01"]
        after_b = report["snapshots"]["after_DOC02"]

        report["checks"] = {
            "without_ctx_has_no_native_owner": (
                not seeded["native_nodes"][str(none_claim.id)]["source_ref_keys"]
            ),
            "run_ctx_without_data_anchor_has_no_native_owner": (
                not seeded["native_nodes"][str(run_claim.id)]["source_ref_keys"]
            ),
            "bound_ctx_stamps_native_doc_ref": (
                ref_a in seeded["native_nodes"][oid]["source_ref_keys"]
            ),
            "bound_ctx_stamps_run_id": (
                bool(seeded["native_nodes"][oid]["source_run_ids"])
            ),
            "patch_preserves_proposition": (
                patched["nodes"][oid]["proposition"]
                == seeded["nodes"][oid]["proposition"]
            ),
            "patch_adds_sentinel": (
                patched["nodes"][oid].get("lab_patch") == "kept"
            ),
            "full_upsert_removes_patch_sentinel": (
                "lab_patch" not in upserted["nodes"][oid]
            ),
            "full_upsert_preserves_native_owner": (
                ref_a in upserted["native_nodes"][oid]["source_ref_keys"]
            ),
            "shared_measurement_has_both_refs": (
                set(shared["native_nodes"][mid]["source_ref_keys"])
                == {ref_a, ref_b}
            ),
            "explicit_supersession_link_exists": any(
                e["source_id"] == rid
                and e["target_id"] == oid
                and e["relationship"] == "supersedes"
                for e in shared["edges"]
            ),
            "first_owner_removal_preserves_shared_measurement": (
                mid in after_a["nodes"]
                and after_a["native_nodes"][mid]["source_ref_keys"] == [ref_b]
            ),
            "source_removal_does_not_restore_measurement_value": (
                after_a["nodes"].get(mid, {}).get("value") == 12
            ),
            "last_owner_removal_deletes_shared_measurement": (
                mid not in after_b["nodes"]
            ),
            "unanchored_claims_survive_both_removals": (
                str(none_claim.id) in after_b["nodes"]
                and str(run_claim.id) in after_b["nodes"]
            ),
            "typed_evidence_node_does_not_automatically_create_relational_evidence": (
                not shared["fixture_relational_evidence"]
            ),
        }
        report["all_checks_passed"] = all(report["checks"].values())
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
        raise RuntimeError("Expected shared local 1.6.2 Ladybug/SQLite/LanceDB")

    exporter = Path(__file__).with_name("stage5_4_5_storage_snapshot.py")
    if "await vector.close()" in exporter.read_text():
        raise RuntimeError("Remove await vector.close() from the storage exporter first")

    baseline = baseline.resolve()
    previous = json.loads((baseline / "improve_results.json").read_text())
    if (
        previous.get("dataset_id") != str(DATASET)
        or not any(
            p["name"] == "enabled" and p["result"]["status"] == "completed"
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
        raise RuntimeError("Expected a separate baseline with the original storage layout")

    relative = [p.relative_to(original) for p in paths]
    if (
        Path(rel.db_name).name != rel.db_name
        or not all((source / p).exists() for p in relative)
        or not (source / relative[1] / rel.db_name).is_file()
        or source.is_symlink()
        or any(p.is_symlink() for p in source.rglob("*"))
    ):
        raise RuntimeError("Invalid baseline storage layout or symlinks")

    outputs = Path("outputs").resolve()
    if outputs.is_relative_to(source) or outputs.is_relative_to(original):
        raise RuntimeError("Outputs must be outside source storage")
    outputs.mkdir(exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="stage5_4_5_custom_", dir=outputs))
    summary = {"baseline": str(baseline), "cases": []}
    summary_path = root / "custom_results.json"
    print(f"Experiment: {root}", flush=True)

    child = root / "fixture"
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
        "CACHE_DB_URL": f"sqlite+aiosqlite:///{child / 'cache' / 'sessions.db'}",
    })
    probe_env = child / "probe.env"
    probe_env.write_text("# Settings supplied by the subprocess environment.\n")
    env["COGNEE_ENV_FILE"] = str(probe_env)

    process = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            str(child),
            "--case",
            "fixture",
        ],
        env=env,
    )
    result_path = child / "case_results.json"
    summary["cases"].append(
        json.loads(result_path.read_text())
        if result_path.exists()
        else {"case": "fixture", "error": "No worker report"}
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, default=str) + "\n"
    )
    if process.returncode:
        raise RuntimeError(
            f"Fixture failed; partial results: {summary_path}"
        )
    print(f"UPLOAD: {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--case", choices=["fixture"])
    args = parser.parse_args()

    if args.worker:
        if not args.case:
            parser.error("--worker requires --case")
        asyncio.run(worker(args.worker.resolve(), args.case))
    else:
        if not args.baseline:
            parser.error("--baseline requires the successful Improve clone directory")
        launch(args.baseline)
