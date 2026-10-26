"""`forget-dataset` through real configured stores in fresh subprocesses:
a live chain root whose Helios was deleted outside the lab, with the seed
deleted and the orphaned name point swept."""

import json

import pytest

from test_identity_native import command

HELIOS = "8b4bff50-907b-56b6-bc80-3b0a7018714a"


def output_of(completed):
    return json.loads(completed.stdout[completed.stdout.index("{") :])


@pytest.mark.integration
def test_native_forget_dataset_deletes_the_seed_and_sweeps_the_orphaned_point(
    tmp_path,
):
    root = tmp_path / "dataset"
    command(root, "glossary-fixture", "--chain")
    command(root, "edit-entity", "--case", "delete")
    dry = output_of(command(root, "forget-dataset", "--dry-run"))
    assert dry["orphan_name_points"] == [HELIOS]
    assert [d["name"] for d in dry["other_data"]] == ["seed"]
    done = output_of(command(root, "forget-dataset", "--confirm", dry["token"]))
    assert [s["label"] for s in done["forgotten"]] == ["doc03", "doc01", "glossary"]
    assert done["orphan_name_points_deleted"] == [HELIOS]
    assert done["other_data_deleted"] == [dry["other_data"][0]["data_id"]]
    again = output_of(command(root, "forget-dataset", "--dry-run"))
    assert again["other_data"] == [] and again["orphan_name_points"] == []
    assert all(s["order"] is None for s in again["sources"])
    stale = output_of(
        command(root, "forget-dataset", "--confirm", dry["token"], expect=1)
    )
    assert stale["message"].startswith("The impact changed since the token")
