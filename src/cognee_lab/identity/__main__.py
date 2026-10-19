"""Isolated initial fixture commands. Never reset or open the user's lab store."""

import argparse
import asyncio
import json
import inspect
import os
from pathlib import Path

from .fixture_embeddings import FixtureEmbeddings


def configure(root: Path, endpoint: str):
    # Test-profile configuration only; persistence uses configured Cognee APIs.
    env = dict(
        SYSTEM_ROOT_DIRECTORY=str(root / "system"),
        DATA_ROOT_DIRECTORY=str(root / "data"),
        DB_PATH=str(root / "relational"),
        DB_PROVIDER="sqlite",
        GRAPH_DATABASE_PROVIDER="ladybug",
        GRAPH_FILE_PATH=str(root / "graph"),
        VECTOR_DB_PROVIDER="lancedb",
        VECTOR_DB_URL=str(root / "vector"),
        ENABLE_BACKEND_ACCESS_CONTROL="false",
        GRAPH_DATABASE_SUBPROCESS_ENABLED="false",
        VECTOR_DB_SUBPROCESS_ENABLED="false",
        EMBEDDING_PROVIDER="openai_compatible",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS="64",
        EMBEDDING_ENDPOINT=endpoint,
        EMBEDDING_API_KEY="fixture",
        LLM_PROVIDER="openai",
        LLM_MODEL="gpt-4o-mini",
        LLM_API_KEY="fixture",
        CACHING="false",
        TELEMETRY_DISABLED="true",
        EDGE_EVIDENCE_ENABLED="true",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        LOG_LEVEL="ERROR",
        KUZU_BUFFER_POOL_SIZE=str(128 << 20),
        KUZU_MAX_DB_SIZE=str(1 << 30),
        KUZU_NUM_THREADS="2",
    )
    for key, value in env.items():
        os.environ[key] = value
    os.environ["NO_PROXY"] = ",".join(
        filter(None, [os.environ.get("NO_PROXY"), "127.0.0.1", "localhost"])
    )
    (root / "relational").mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "fixture",
            "multi-fixture",
            "withdraw",
            "retrieve",
            "status",
            "reconcile",
        ],
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--query", default="What does HC limit?")
    parser.add_argument(
        "--source",
        choices=["doc01", "doc02"],
        default="doc01",
        help="Selected original document in the isolated fixture",
    )
    parser.add_argument(
        "--fault-stage",
        choices=[
            "nodes",
            "identity_edges",
            "verification",
            "withdraw_contributions",
            "withdraw_owners",
            "withdraw_verification",
        ],
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if args.fault_stage and args.fault_stage.startswith("withdraw_") != (
        args.command == "withdraw"
    ):
        parser.error("Fault stage does not match the selected operation")
    if args.command in {"fixture", "multi-fixture"}:
        if root.exists():
            parser.error("Fixture root already exists; choose a new directory")
        root.mkdir(parents=True, exist_ok=False)
        (root / "stage6-fixture.json").write_text(
            json.dumps({"kind": "stage6-isolated-fixture"})
        )
    elif not (root / "stage6-fixture.json").exists():
        parser.error("Root is not an isolated Stage 6 fixture directory")
    with FixtureEmbeddings() as endpoint:
        configure(root, endpoint)
        if args.command in {"multi-fixture", "withdraw"} or (
            args.command == "reconcile" and (root / "multi-fixture-info.json").exists()
        ):
            from .multisource import run
        else:
            from .fixture import run

        async def execute():
            try:
                return await run(args, root)
            finally:
                publisher = getattr(args, "_fixture_publisher", None)
                if publisher is not None:
                    # This CLI owns the isolated stores. Close before interpreter
                    # teardown; never rely on object-finalizer order for durability.
                    for engine in (publisher.vector, publisher.graph):
                        close = getattr(engine, "close", None)
                        if close is not None:
                            closing = close()
                            if inspect.isawaitable(closing):
                                await closing

        try:
            result = asyncio.run(execute())
        except Exception as exc:
            print(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise SystemExit(1) from exc
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
