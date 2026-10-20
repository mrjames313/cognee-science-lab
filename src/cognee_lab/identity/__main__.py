"""Isolated initial fixture commands. Never reset or open the user's lab store."""

import argparse
import asyncio
import json
import inspect
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path

from dotenv import dotenv_values

from .fixture_embeddings import FixtureEmbeddings

# Cognee loads exactly this comment-only file instead of searching for the repo .env.
FIXTURE_ENV = Path(__file__).with_name("fixture.env")
_LOOPBACK = {"profile": "loopback", "model": "text-embedding-3-small", "dimensions": 64}


def _operator_embedding() -> dict[str, str]:
    # The env file Cognee would load. Values, the API key included, stay in memory.
    source = Path(
        os.environ.get("COGNEE_ENV_FILE", "").strip()
        or Path(__file__).resolve().parents[3] / ".env"
    )
    values = dotenv_values(source) if source.is_file() else {}
    settings = {
        key: value
        for key, value in values.items()
        if value is not None
        and (key.startswith("EMBEDDING_") or key == "HUGGINGFACE_TOKENIZER")
    }
    missing = sorted({"EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS"} - settings.keys())
    if missing:
        raise ValueError(
            f"{source} does not set {' or '.join(missing)}; "
            "use --embedding loopback for an offline fixture root"
        )
    return settings


def embedding_record(profile: str) -> dict:
    """The non-secret description of a root's vectors, as its marker records it."""
    if profile == "loopback":
        return _LOOPBACK
    settings = _operator_embedding()
    return {
        "profile": "env",
        "model": settings["EMBEDDING_MODEL"],
        "dimensions": int(settings["EMBEDDING_DIMENSIONS"]),
    }


def _recorded_embedding(root: Path) -> dict | None:
    return json.loads((root / "stage6-fixture.json").read_text()).get("embedding")


@contextmanager
def fixture_environment(root: Path):
    """Point this process at the root's own stores and its recorded embedding profile.

    Enter before importing cognee: Cognee loads its env file once, at import, and
    caches its config. main() has already checked the marker against the request.
    """
    recorded = _recorded_embedding(root)
    env = dict(
        SYSTEM_ROOT_DIRECTORY=str(root / "system"),
        DATA_ROOT_DIRECTORY=str(root / "data"),
        CACHE_ROOT_DIRECTORY=str(root / "cache"),
        DB_PATH=str(root / "relational"),
        DB_PROVIDER="sqlite",
        GRAPH_DATABASE_PROVIDER="ladybug",
        GRAPH_FILE_PATH=str(root / "graph"),
        VECTOR_DB_PROVIDER="lancedb",
        VECTOR_DB_URL=str(root / "vector"),
        ENABLE_BACKEND_ACCESS_CONTROL="false",
        GRAPH_DATABASE_SUBPROCESS_ENABLED="false",
        VECTOR_DB_SUBPROCESS_ENABLED="false",
        # No fixture command calls an LLM; a fake key fails instead of spending.
        LLM_PROVIDER="openai",
        LLM_MODEL="gpt-4o-mini",
        LLM_API_KEY="fixture",
        CACHING="false",
        TELEMETRY_DISABLED="true",
        EDGE_EVIDENCE_ENABLED="true",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        LITELLM_LOCAL_MODEL_COST_MAP="True",
        LOG_LEVEL="ERROR",
        KUZU_BUFFER_POOL_SIZE=str(128 << 20),
        KUZU_MAX_DB_SIZE=str(1 << 30),
        KUZU_NUM_THREADS="2",
    )
    with ExitStack() as stack:
        # A pre-profile root keeps loading the repo .env, which wrote its vectors.
        if recorded is not None:
            if recorded["profile"] == "env":
                env |= _operator_embedding()
            else:
                endpoint = stack.enter_context(FixtureEmbeddings())
                env |= dict(
                    EMBEDDING_PROVIDER="openai_compatible",
                    EMBEDDING_MODEL=_LOOPBACK["model"],
                    EMBEDDING_DIMENSIONS=str(_LOOPBACK["dimensions"]),
                    EMBEDDING_ENDPOINT=endpoint,
                    EMBEDDING_API_KEY="fixture",
                )
            env["COGNEE_ENV_FILE"] = str(FIXTURE_ENV)
        os.environ.update(env)
        os.environ["NO_PROXY"] = ",".join(
            filter(None, [os.environ.get("NO_PROXY"), "127.0.0.1", "localhost"])
        )
        (root / "relational").mkdir(parents=True, exist_ok=True)
        yield


def _reopen_error(args, root: Path) -> str | None:
    recorded = _recorded_embedding(root)
    if recorded is None:
        if args.command not in {"status", "retrieve"}:
            return "Root predates embedding profiles; only status and retrieve open it"
        if args.embedding == "loopback":
            return "Root predates embedding profiles; its vectors use .env embeddings"
        return None
    if args.embedding not in (None, recorded["profile"]):
        return f"Root was created with --embedding {recorded['profile']}"
    if recorded["profile"] == "loopback":
        return None
    try:
        current = embedding_record("env")
    except ValueError as exc:
        return str(exc)
    if current != recorded:
        return (
            f"Root vectors use {recorded['model']} ({recorded['dimensions']} dims); "
            f"the env file now names {current['model']} ({current['dimensions']} dims)"
        )
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "fixture",
            "multi-fixture",
            "chunked-fixture",
            "revise",
            "edit-text",
            "remove-occurrences",
            "retire-resolved-group",
            "add-occurrences",
            "withdraw",
            "retrieve",
            "status",
            "reconcile",
        ],
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--query", default="What does HC limit?")
    parser.add_argument(
        "--expected-revision",
        type=int,
        help="Required saved revision guard for revision-changing commands",
    )
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
            "replace_saved",
            "replace_registered",
            "replace_published",
            "replace_retired",
            "replace_verification",
            "text_removed",
            "text_registered",
            "text_chunks",
        ],
    )
    parser.add_argument(
        "--embedding",
        choices=["env", "loopback"],
        help="Embedding profile. Creation records it (default env: EMBEDDING_* from "
        "the repo .env or COGNEE_ENV_FILE); reopening refuses a different one.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if (
        args.command
        in {
            "revise",
            "edit-text",
            "remove-occurrences",
            "retire-resolved-group",
            "add-occurrences",
        }
        and args.expected_revision is None
    ):
        parser.error(f"{args.command} requires --expected-revision")
    if args.fault_stage:
        if args.command in {
            "edit-text",
            "remove-occurrences",
            "retire-resolved-group",
            "add-occurrences",
        }:
            if not args.fault_stage.startswith(("text_", "replace_")):
                parser.error("Fault stage does not match the selected operation")
        elif args.fault_stage.startswith("text_"):
            parser.error("Text failure boundaries require a text-changing command")
        prefix = (
            "withdraw_"
            if args.command == "withdraw"
            else "replace_" if args.command == "revise" else None
        )
        if (prefix and not args.fault_stage.startswith(prefix)) or (
            not prefix
            and args.command
            not in {
                "edit-text",
                "remove-occurrences",
                "retire-resolved-group",
                "add-occurrences",
            }
            and args.fault_stage.startswith(("withdraw_", "replace_"))
        ):
            parser.error("Fault stage does not match the selected operation")
    if args.command in {"fixture", "multi-fixture", "chunked-fixture"}:
        if root.exists():
            parser.error("Fixture root already exists; choose a new directory")
        # Resolve before mkdir so a failed creation leaves no root behind.
        try:
            embedding = embedding_record(args.embedding or "env")
        except ValueError as exc:
            parser.error(str(exc))
        root.mkdir(parents=True, exist_ok=False)
        (root / "stage6-fixture.json").write_text(
            json.dumps({"kind": "stage6-isolated-fixture", "embedding": embedding})
        )
    elif not (root / "stage6-fixture.json").exists():
        parser.error("Root is not an isolated Stage 6 fixture directory")
    elif error := _reopen_error(args, root):
        parser.error(error)
    with fixture_environment(root):
        if args.command in {
            "remove-occurrences",
            "retire-resolved-group",
            "add-occurrences",
        }:
            from .occurrence_fixture import run
        elif args.command == "edit-text":
            from .text_fixture import run
        elif args.command == "revise":
            from .revisions import run
        elif args.command in {"multi-fixture", "chunked-fixture", "withdraw"} or (
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
