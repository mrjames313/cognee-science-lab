"""Read graph-associated vector rows and relational records. No model calls.

Uses existing configured shared storage; avoids setup and migrations.
This is a targeted, sequential baseline, not a full transactional backup.
"""

import argparse
import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv


async def main(args):
    snapshot = json.loads(args.graph.read_text())
    if snapshot["scope"]["kind"] != "configured_shared_graph":
        raise ValueError("This probe expects the shared-graph baseline")

    load_dotenv()

    import cognee
    from sqlalchemy import select
    from cognee.context_global_variables import backend_access_control_enabled
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.infrastructure.databases.vector import get_vector_engine_async
    from cognee.modules.data.models import Dataset, Data
    from cognee.modules.pipelines.models import PipelineRun
    from cognee.modules.provenance.edge_evidence.models import (
        ProvenanceEdgeEvidence,
    )
    from cognee.modules.engine.utils import generate_node_id
    from cognee.modules.graph.models.EdgeType import EdgeType
    from cognee.modules.graph.utils.prepare_edges_for_storage import (
        get_edge_retrieval_text,
    )

    if cognee.__version__ != "1.6.2":
        raise RuntimeError(f"Expected 1.6.2; got {cognee.__version__}")
    if backend_access_control_enabled():
        raise RuntimeError(
            "Shared-storage probe requires access control disabled"
        )

    report = {
        "cognee_version": cognee.__version__,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "input_sha256": hashlib.sha256(args.graph.read_bytes()).hexdigest(),
        "scope": "graph_associated_rows_in_configured_shared_storage",
        "transactional": False,
        "vector_values": "hash_and_dimensions_only",
        "vectors": {},
        "relational": {},
    }

    candidates = defaultdict(set)
    provenance = snapshot["native_provenance"]

    for nid, node in provenance["nodes"].items():
        for field in node["indexed_fields"]:
            candidates[f"{node['node_type']}_{field}"].add(nid)

    for edge in snapshot["edges"]:
        source, target, relation = (
            edge["source_id"],
            edge["target_id"],
            edge["relationship"],
        )
        candidates["Triplet_text"].add(
            str(generate_node_id(source + relation + target))
        )
        text = get_edge_retrieval_text(
            edge["properties"].get("edge_text"), relation
        )
        if text:
            candidates["EdgeType_relationship_name"].add(
                str(EdgeType.id_for(text))
            )

    vector = await get_vector_engine_async()
    semaphore = asyncio.Semaphore(4)

    async def read_point(collection, point_id):
        # Singleton queries avoid backend default result limits.
        async with semaphore:
            rows = await vector.retrieve(
                collection, [point_id], include_vector=True
            )

        output = []
        for row in rows:
            payload = dict(row.payload)
            values = payload.pop("vector", None)
            output.append({
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
        return output

    try:
        for collection, ids in sorted(candidates.items()):
            if not await vector.has_collection(collection):
                report["vectors"][collection] = {
                    "status": "collection_absent",
                    "requested_count": len(ids),
                }
                continue

            records = []
            ordered = sorted(ids)
            for offset in range(0, len(ordered), 32):
                batches = await asyncio.gather(*[
                    read_point(collection, i)
                    for i in ordered[offset:offset + 32]
                ])
                records.extend(
                    row for batch in batches for row in batch
                )

            found = {row["id"] for row in records}
            report["vectors"][collection] = {
                "status": "captured",
                "requested_count": len(ids),
                "found_count": len(found),
                "missing_ids": sorted(ids - found),
                "rows": sorted(records, key=lambda row: row["id"]),
            }
            print(
                f"{collection}: "
                f"{len(found)}/{len(ids)} associated IDs present"
            )

        dataset_ids = {
            UUID(i)
            for node in provenance["nodes"].values()
            for i in node["source_dataset_ids"]
        }
        for edge in provenance["edges"]:
            dataset_ids.update(
                UUID(i) for i in edge["source_dataset_ids"]
            )

        engine = get_relational_engine()
        queries = {
            "datasets": select(
                Dataset.id,
                Dataset.name,
                Dataset.owner_id,
                Dataset.tenant_id,
            ).where(
                Dataset.id.in_(dataset_ids)
                | (Dataset.name == "helios_stage2")
            ),
            "data": select(
                Data.id,
                Data.name,
                Data.dataset_id,
                Data.owner_id,
                Data.legacy_id,
                Data.pipeline_status,
            ).where(Data.dataset_id.in_(dataset_ids)),
            "pipeline_runs": select(
                PipelineRun.__table__
            ).where(PipelineRun.dataset_id.in_(dataset_ids)),
            "edge_evidence": select(
                ProvenanceEdgeEvidence.__table__
            ).where(
                ProvenanceEdgeEvidence.dataset_id.in_(dataset_ids)
            ),
        }

        for name, query in queries.items():
            try:
                async with engine.get_async_session() as session:
                    rows = (
                        await session.execute(query)
                    ).mappings().all()
                report["relational"][name] = {
                    "status": "captured",
                    "rows": [dict(row) for row in rows],
                }
                print(f"{name}: {len(rows)} rows")
            except Exception as exc:
                report["relational"][name] = {
                    "status": "read_failed",
                    "error_type": type(exc).__name__,
                }

    except Exception as exc:
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        raise

    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
            handle.write("\n")
        print(f"Output: {args.output}")
        # Cognee owns this cached adapter, later operations need it


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(
            "Choose a new output filename; this file already exists"
        )
    asyncio.run(main(args))
