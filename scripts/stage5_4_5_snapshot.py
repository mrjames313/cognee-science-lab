"""Export graph properties and native provenance for Stage 5.4.5.

Run from the project root:
    uv run python scripts/stage5_4_5_snapshot.py --output outputs/stage5_4_5_before.json

This makes no Add/Cognify/Improve/Update/Forget, indexing, LLM, or embedding
calls. Engine initialization follows Cognee's normal adapter behavior. It
does not call setup() or migrations. Use the existing configured database.

For access-control-enabled storage, supply both --dataset-id and --owner-id.
Otherwise it snapshots the configured shared graph, as existing lab scripts do.
The JSON is evidence, not a portable database backup. Vector/relational state
is outside this first exporter and is explicitly marked uncaptured.

Offline conversion of an existing Cognee HTML visualization needs only Python:
    python3 scripts/stage5_4_5_snapshot.py --from-html outputs/stage5_graph.html \
        --output outputs/stage5_4_5_html_baseline.json

HTML does not expose native source-ref columns; those are marked unavailable.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted((json_safe(v) for v in value), key=str)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def embedded_array(html: str, variable: str) -> list:
    pattern = rf"(?:var|const|let)\s+{re.escape(variable)}\s*=\s*"
    for match in re.finditer(pattern, html):
        try:
            value, _ = json.JSONDecoder().raw_decode(html[match.end():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            if variable == "nodes" and "id" in value[0]:
                return value
            if variable == "links" and {"source", "target"} <= value[0].keys():
                return value
    raise ValueError(f"No populated JSON {variable} array found in HTML")


def from_html(path: Path) -> dict:
    html = path.read_text(encoding="utf-8")
    nodes = embedded_array(html, "nodes")
    links = embedded_array(html, "links")

    # Preserve presentation-added fields and explicitly identify this origin.
    return {
        "origin": "html_visualization_with_presentation_fields",
        "input_file": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "nodes": [{"id": str(n["id"]), "properties": n} for n in nodes],
        "edges": [
            {
                "source_id": str(e["source"]),
                "target_id": str(e["target"]),
                "relationship": e.get("relation") or e.get("relationship_type"),
                "properties": e.get("edge_info") or {},
            }
            for e in links
        ],
        "graph_metadata": {"status": "unavailable_from_html"},
        "native_provenance": {"status": "unavailable_from_html"},
    }


async def live_snapshot(args: argparse.Namespace) -> dict:
    from dotenv import load_dotenv

    load_dotenv()

    import cognee
    import cognee_lab.models  # Register the project's DataPoint definitions.
    from cognee.context_global_variables import (
        backend_access_control_enabled,
        set_database_global_context_variables,
    )
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.infrastructure.databases.provenance import EdgeIdentity
    from cognee.infrastructure.databases.exceptions.exceptions import (
        UnsupportedProvenanceCapability,
    )

    if bool(args.dataset_id) != bool(args.owner_id):
        raise ValueError("Supply both --dataset-id and --owner-id, or neither")

    if backend_access_control_enabled() and not args.dataset_id:
        raise ValueError(
            "Access control is enabled: supply --dataset-id and --owner-id"
        )

    async def capture() -> dict:
        engine = await get_graph_engine()
        nodes, edges = await engine.get_graph_data()

        metadata: dict = {"status": "unsupported"}
        provenance: dict = {"status": "unsupported"}

        try:
            metadata = {
                "status": "captured",
                "values": await engine.get_graph_metadata(),
            }
        except (NotImplementedError, UnsupportedProvenanceCapability) as exc:
            metadata["reason"] = type(exc).__name__

        # Ordinary get_graph_data omits Ladybug's native provenance columns.
        # These deletion-data interfaces only read the relevant metadata.
        try:
            nd = await engine.get_node_delete_data(
                [str(nid) for nid, _ in nodes]
            )
            identities = [
                EdgeIdentity(str(s), str(t), str(r))
                for s, t, r, _ in edges
            ]
            ed = await engine.get_edge_delete_data(identities)

            provenance = {
                "status": "captured",
                "nodes": {str(k): json_safe(v) for k, v in nd.items()},
                "edges": [json_safe(v) for v in ed.values()],
            }
        except (NotImplementedError, UnsupportedProvenanceCapability) as exc:
            provenance["reason"] = type(exc).__name__

        return {
            "origin": "live_graph_interfaces",
            "cognee_version": cognee.__version__,
            "graph_engine": type(engine).__name__,
            "scope": {
                "kind": (
                    "dataset"
                    if args.dataset_id
                    else "configured_shared_graph"
                ),
                "dataset_id": args.dataset_id,
                "owner_id": args.owner_id,
            },
            "nodes": [
                {"id": str(nid), "properties": props}
                for nid, props in nodes
            ],
            "edges": [
                {
                    "source_id": str(s),
                    "target_id": str(t),
                    "relationship": str(r),
                    "properties": props,
                }
                for s, t, r, props in edges
            ],
            "graph_metadata": metadata,
            "native_provenance": provenance,
        }

    if args.dataset_id:
        from uuid import UUID

        async with set_database_global_context_variables(
            UUID(args.dataset_id), UUID(args.owner_id)
        ):
            return await capture()

    return await capture()


def finish(snapshot: dict, output: Path) -> None:
    snapshot = json_safe(snapshot)
    snapshot["format_version"] = 1
    snapshot["captured_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["vector_state"] = {"status": "not_captured"}
    snapshot["relational_state"] = {"status": "not_captured"}
    snapshot["snapshot_is_transactional"] = False

    snapshot["nodes"].sort(key=lambda n: n["id"])
    snapshot["edges"].sort(
        key=lambda e: (
            e["source_id"],
            e["relationship"],
            e["target_id"],
            json.dumps(e["properties"], sort_keys=True),
        )
    )

    snapshot["summary"] = {
        "node_count": len(snapshot["nodes"]),
        "edge_count": len(snapshot["edges"]),
        "node_types": dict(
            Counter(
                n["properties"].get("type", "unknown")
                for n in snapshot["nodes"]
            )
        ),
        "relationships": dict(
            Counter(e["relationship"] for e in snapshot["edges"])
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(
        json.dumps(
            {"output": str(output), "summary": snapshot["summary"]},
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--from-html", type=Path)
    parser.add_argument("--dataset-id")
    parser.add_argument("--owner-id")
    args = parser.parse_args()

    if args.output.exists():
        parser.error(
            "Output exists; choose a new filename to preserve earlier evidence"
        )

    if args.from_html and (args.dataset_id or args.owner_id):
        parser.error("Dataset scope options apply to live capture only")

    if args.from_html:
        result = from_html(args.from_html)
    else:
        result = asyncio.run(live_snapshot(args))

    finish(result, args.output)


if __name__ == "__main__":
    main()
