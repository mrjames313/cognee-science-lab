"""A fixture root's marker and the process environment it selects.

This module imports no cognee: fixture_environment must run before Cognee's
import loads an env file.
"""

import json
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path

from dotenv import dotenv_values

from .fixture_embeddings import FixtureEmbeddings

# Cognee loads exactly this comment-only file instead of searching for the repo .env.
FIXTURE_ENV = Path(__file__).with_name("fixture.env")
MARKER = "stage6-fixture.json"
MARKER_KIND = "stage6-isolated-fixture"
CREATION_COMMANDS = frozenset(
    {"fixture", "multi-fixture", "chunked-fixture", "glossary-fixture"}
)
_MALFORMED = "Root marker embedding record is malformed"


def _loopback_record() -> dict:
    return {"profile": "loopback", "model": "text-embedding-3-small", "dimensions": 64}


def _operator_file() -> Path:
    named = os.environ.get("COGNEE_ENV_FILE", "").strip()
    if not named:
        # Cognee finds the repo .env by searching up from the working directory.
        # Resolve it from this file so any working directory reads the same .env.
        return Path(__file__).resolve().parents[3] / ".env"
    path = Path(named).expanduser()
    if not path.is_file():
        raise ValueError(f"COGNEE_ENV_FILE={named} does not name a file")
    return path


def _operator_embedding() -> dict[str, str]:
    # The env file Cognee would load. Values, the API key included, stay in memory.
    source = _operator_file()
    values = dotenv_values(source) if source.is_file() else {}
    settings = {
        key: value
        for key, value in values.items()
        if value is not None
        and (key.startswith("EMBEDDING_") or key == "HUGGINGFACE_TOKENIZER")
    }
    missing = [
        key
        for key in ("EMBEDDING_DIMENSIONS", "EMBEDDING_MODEL")
        if not settings.get(key, "").strip()
    ]
    if missing:
        raise ValueError(
            f"{source} does not set {' or '.join(missing)}; "
            "use --embedding loopback for an offline fixture root"
        )
    try:
        int(settings["EMBEDDING_DIMENSIONS"])
    except ValueError:
        raise ValueError(
            f"{source} sets EMBEDDING_DIMENSIONS to "
            f"{settings['EMBEDDING_DIMENSIONS']!r}, which is not an integer"
        ) from None
    return settings


def _env_record(settings: dict[str, str]) -> dict:
    return {
        "profile": "env",
        "model": settings["EMBEDDING_MODEL"],
        "dimensions": int(settings["EMBEDDING_DIMENSIONS"]),
    }


def create_root(root: Path, profile: str) -> None:
    """Make the root and write its marker with the non-secret embedding record.

    The record is resolved first, so a ValueError leaves no root.
    """
    embedding = (
        _loopback_record()
        if profile == "loopback"
        else _env_record(_operator_embedding())
    )
    root.mkdir(parents=True, exist_ok=False)
    (root / MARKER).write_text(
        json.dumps({"kind": MARKER_KIND, "embedding": embedding})
    )


def read_embedding(root: Path) -> dict | None:
    """The root's embedding record, or None for a root made before profiles."""
    try:
        marker = json.loads((root / MARKER).read_text())
    except (OSError, ValueError):
        raise ValueError(_MALFORMED) from None
    if not isinstance(marker, dict):
        raise ValueError(_MALFORMED)
    if "embedding" not in marker:
        return None
    record = marker["embedding"]
    if not (
        isinstance(record, dict)
        and record.get("profile") in {"env", "loopback"}
        and isinstance(record.get("model"), str)
        and type(record.get("dimensions")) is int
    ):
        raise ValueError(_MALFORMED)
    return {key: record[key] for key in ("profile", "model", "dimensions")}


def reopen_problem(root: Path) -> str | None:
    """Why fixture_environment would refuse this root, or None. Read-only.

    Covers a malformed marker and, for an env root, an operator file that is
    missing, incomplete, or names a different model or dimension count.
    """
    try:
        recorded = read_embedding(root)
        if recorded is not None and recorded["profile"] == "env":
            current = _env_record(_operator_embedding())
            if current != recorded:
                return (
                    f"Root vectors use {recorded['model']} "
                    f"({recorded['dimensions']} dims); the env file now names "
                    f"{current['model']} ({current['dimensions']} dims)"
                )
    except ValueError as exc:
        return str(exc)
    return None


@contextmanager
def fixture_environment(root: Path):
    """Point this process at the root's own stores and its recorded embedding profile.

    Enter before importing cognee: Cognee loads its env file once, at import, and
    caches its config. Raises ValueError before yielding when the marker is
    malformed or an env root's file no longer names the model and dimensions
    that wrote its vectors. The environment changes persist after exit; only the
    loopback embedding server stops.
    """
    if problem := reopen_problem(root):
        raise ValueError(problem)
    recorded = read_embedding(root)
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
                loopback = _loopback_record()
                env |= dict(
                    EMBEDDING_PROVIDER="openai_compatible",
                    EMBEDDING_MODEL=loopback["model"],
                    EMBEDDING_DIMENSIONS=str(loopback["dimensions"]),
                    EMBEDDING_ENDPOINT=stack.enter_context(FixtureEmbeddings()),
                    EMBEDDING_API_KEY="fixture",
                )
            env["COGNEE_ENV_FILE"] = str(FIXTURE_ENV)
        os.environ.update(env)
        os.environ["NO_PROXY"] = ",".join(
            filter(None, [os.environ.get("NO_PROXY"), "127.0.0.1", "localhost"])
        )
        (root / "relational").mkdir(parents=True, exist_ok=True)
        yield
