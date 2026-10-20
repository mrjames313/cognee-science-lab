import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MARKER = "stage6-fixture.json"
OPERATOR = {
    "EMBEDDING_PROVIDER": "openai_compatible",
    "EMBEDDING_MODEL": "operator-model",
    "EMBEDDING_DIMENSIONS": "2048",
    "EMBEDDING_ENDPOINT": "http://operator.invalid/v1",
    "EMBEDDING_API_KEY": "operator-secret",
    "HUGGINGFACE_TOKENIZER": "operator/tokenizer",
    "DATA_ROOT_DIRECTORY": "/decoy/data",
    "SYSTEM_ROOT_DIRECTORY": "/decoy/system",
    "LLM_API_KEY": "operator-llm-secret",
}
ENV_RECORD = {"profile": "env", "model": "operator-model", "dimensions": 2048}
LOOPBACK_RECORD = {
    "profile": "loopback",
    "model": "text-embedding-3-small",
    "dimensions": 64,
}
RESOLVE = """
import json,sys
from pathlib import Path
from cognee_lab.identity.__main__ import fixture_environment
with fixture_environment(Path(sys.argv[1])):
 import cognee
 from cognee.base_config import get_base_config
 from cognee.infrastructure.databases.vector.embeddings.config import get_embedding_config
 from cognee.infrastructure.llm.config import get_llm_config
 base,embedding,llm=get_base_config(),get_embedding_config(),get_llm_config()
 print(json.dumps(dict(
  data=base.data_root_directory,system=base.system_root_directory,
  cache=base.cache_root_directory,model=embedding.embedding_model,
  dimensions=embedding.embedding_dimensions,endpoint=embedding.embedding_endpoint,
  tokenizer=embedding.huggingface_tokenizer,llm_key=llm.llm_api_key)))
"""


def in_unit_root(path: str) -> bool:
    root = Path(path).resolve().parent
    return (
        root.name.startswith("cognee-stage6-unit-")
        and root.parent == Path(tempfile.gettempdir()).resolve()
    )


def test_unit_tests_do_not_use_the_lab_stores():
    import cognee  # noqa: F401  Loads Cognee's env file once for this process.
    from cognee.base_config import get_base_config

    config = get_base_config()
    # Names only: the failing values could come from the operator's .env.
    escaped = [
        name
        for name in (
            "data_root_directory",
            "system_root_directory",
            "cache_root_directory",
        )
        if not in_unit_root(getattr(config, name))
    ]
    assert escaped == []


def operator_env(tmp_path, **overrides) -> Path:
    path = tmp_path / "operator.env"
    values = {k: v for k, v in (OPERATOR | overrides).items() if v is not None}
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    return path


def fixture_root(tmp_path, embedding=None) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    marker = {"kind": "stage6-isolated-fixture"}
    if embedding is not None:
        marker["embedding"] = embedding
    (root / MARKER).write_text(json.dumps(marker))
    return root


def run(args, env_file):
    # Cognee loads its env file once per process, so each case gets a fresh one.
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO,
        env=os.environ | {"COGNEE_ENV_FILE": str(env_file)},
        capture_output=True,
        text=True,
        timeout=120,
    )


def resolved(root, env_file) -> dict:
    result = run(["-c", RESOLVE, str(root)], env_file)
    assert result.returncode == 0, result.stderr[-3000:]
    return json.loads(result.stdout.splitlines()[-1])


def assert_stores_inside(root, config):
    for name in ("data", "system", "cache"):
        assert Path(config[name]).resolve().is_relative_to(root.resolve()), name


def test_env_profile_uses_operator_embeddings_and_the_root_stores(tmp_path):
    root = fixture_root(tmp_path, ENV_RECORD)
    config = resolved(root, operator_env(tmp_path))
    assert_stores_inside(root, config)
    assert config["model"] == "operator-model"
    assert config["dimensions"] == 2048
    assert config["endpoint"] == "http://operator.invalid/v1"
    assert config["tokenizer"] == "operator/tokenizer"
    assert config["llm_key"] == "fixture"
    on_disk = [p for p in root.rglob("*") if p.is_file()]
    assert not any("operator-secret" in p.read_text(errors="ignore") for p in on_disk)


def test_loopback_profile_uses_local_embeddings(tmp_path):
    root = fixture_root(tmp_path, LOOPBACK_RECORD)
    config = resolved(root, operator_env(tmp_path))
    assert_stores_inside(root, config)
    assert config["dimensions"] == 64
    assert config["endpoint"].startswith("http://127.0.0.1:")
    assert config["llm_key"] == "fixture"


def test_env_creation_without_operator_embeddings_leaves_no_root(tmp_path):
    root = tmp_path / "root"
    env_file = operator_env(tmp_path, EMBEDDING_MODEL=None)
    result = run(
        ["-m", "cognee_lab.identity", "fixture", "--root", str(root)], env_file
    )
    assert result.returncode == 2
    assert "does not set EMBEDDING_MODEL" in result.stderr
    assert "--embedding loopback" in result.stderr
    assert not root.exists()


@pytest.mark.parametrize(
    "embedding, args, message",
    [
        (
            LOOPBACK_RECORD,
            ["status", "--embedding", "env"],
            "created with --embedding loopback",
        ),
        (
            {**ENV_RECORD, "model": "earlier-model"},
            ["status"],
            "Root vectors use earlier-model (2048 dims)",
        ),
        (None, ["reconcile"], "only status and retrieve open it"),
        (
            None,
            ["status", "--embedding", "loopback"],
            "its vectors use .env embeddings",
        ),
    ],
)
def test_reopen_refuses_a_different_embedding_profile(
    tmp_path, embedding, args, message
):
    root = fixture_root(tmp_path, embedding)
    command, *flags = args
    result = run(
        ["-m", "cognee_lab.identity", command, "--root", str(root), *flags],
        operator_env(tmp_path),
    )
    assert result.returncode == 2
    assert message in result.stderr
