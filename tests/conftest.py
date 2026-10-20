import os
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config):
    # Configure before any lazy Cognee import. No lab store or API is touched.
    root = Path(tempfile.mkdtemp(prefix="cognee-stage6-unit-"))
    for name, value in {
        "SYSTEM_ROOT_DIRECTORY": str(root / "system"),
        "DATA_ROOT_DIRECTORY": str(root / "data"),
        "ENABLE_BACKEND_ACCESS_CONTROL": "false",
        "TELEMETRY_DISABLED": "true",
        "CACHING": "false",
        "LOG_LEVEL": "ERROR",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    }.items():
        os.environ[name] = value
    (root / "system/databases").mkdir(parents=True)


@pytest.fixture
def source_payload():
    import json

    return json.loads(
        (
            Path(__file__).parent
            / "fixtures/identity/cognee_identity_source_example.json"
        ).read_text()
    )
