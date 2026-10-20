import tempfile
from pathlib import Path


def in_unit_root(path: str) -> bool:
    root = Path(path).resolve().parent
    return root.name.startswith("cognee-stage6-unit-") and root.parent == Path(
        tempfile.gettempdir()
    ).resolve()


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
