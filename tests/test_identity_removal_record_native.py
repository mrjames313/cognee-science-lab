"""The removal record through real configured stores in fresh
subprocesses: a replacement's retirement stays recorded after a later
operation overwrites the replacement's plan."""

import json

import pytest

from test_identity_native import command


def removed_entities(root):
    status = command(root, "status").stdout
    return json.loads(status[status.index("{") :])["removed_entities"]


@pytest.mark.integration
def test_native_a_retirement_stays_recorded_after_its_plan_is_overwritten(
    tmp_path,
):
    """retire-resolved-group's replacement retires the mention Entity of
    doc01's group, its only owner; doc01's withdrawal then overwrites the
    replacement's plan and removes what doc01 alone still owned."""
    root = tmp_path / "record"
    command(root, "chunked-fixture")
    assert removed_entities(root) == {}
    command(root, "retire-resolved-group", "--expected-revision", "1")
    retired = removed_entities(root)
    assert retired and set(retired.values()) == {"identity_replace"}
    command(root, "withdraw", "--source", "doc01")
    removed = removed_entities(root)
    assert {e: removed[e] for e in retired} == retired
    assert "identity_withdraw" in removed.values()
