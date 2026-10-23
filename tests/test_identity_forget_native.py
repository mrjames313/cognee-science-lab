"""Forget and re-add through real configured stores in fresh subprocesses."""

import json
from pathlib import Path

import pytest

from cognee_lab.identity.forget import COMMITTED_FAULTS, DEPENDENT_FAULTS, STAGES
from test_identity_native import command

ABSENT = dict(
    original_data_present=False,
    identity_data_present=False,
    stored_files_present=[],
    document_node_present=False,
    chunks_present=[],
    chunk_vectors_present=[],
    mention_nodes_present=[],
    mention_vectors_present=[],
    original_fact_present=False,
    evidence_rows=0,
    private_singleton_present=False,
    private_singleton_indexed=False,
    identity_contribution_present=False,
    owned_nodes=0,
    owned_edges=0,
)


def erased(report):
    """The forget report shows nothing of the source left."""
    return {k: report[k] for k in ABSENT} == ABSENT and (
        report["removed_entities_present"] == []
    )


def result_of(root):
    return json.loads((root / "multisource_result.json").read_text())


def error_of(completed):
    return json.loads(completed.stdout.strip().splitlines()[-1])


def intact(before, after, label):
    """The other source's snapshot entry is unchanged by the operation."""
    assert after["sources"][label] == before["sources"][label]
    assert after["borrowed_entity"] == before["borrowed_entity"]
    assert after["shared_singleton_present"] and after["shared_singleton_indexed"]


@pytest.mark.integration
@pytest.mark.parametrize("first", ["doc01", "doc02"])
def test_native_forget_removes_one_source_and_a_readd_continues_the_revision(
    tmp_path, first
):
    root = tmp_path / "forget"
    command(root, "multi-fixture")
    initial = result_of(root)
    other = "doc02" if first == "doc01" else "doc01"
    assert len(initial["result"]["facts"]) == 2
    assert len(initial["hc_entity"]["owners"]) == 2

    command(root, "forget", "--source", first, "--expected-revision", "1")
    one = result_of(root)
    gone = one["sources"][first]
    assert gone["state"] == "forgotten"
    assert gone["saved_revision"] == 1 and gone["verified_revision"] == 1
    assert erased(gone["forget"])
    intact(initial, one, other)
    other_id = one["sources"][other]["identity_data_id"]
    assert [c["identity_data_id"] for c in one["shared_variant"]["contributions"]] == [
        other_id
    ]
    assert len(one["shared_variant"]["owners"]) == 1
    assert one["hc_entity"]["owners"] == [
        o for o in initial["hc_entity"]["owners"] if o.endswith(other_id)
    ]
    assert [f["source_id"] for f in one["result"]["facts"]] == [
        one["sources"][other]["mention_entity_id"]
    ]
    assert one["result"]["unavailable_sources"] == []
    assert one["recovery_events"] == []

    reopened = json.loads(command(root, "retrieve").stdout)
    assert len(reopened["facts"]) == 1 and reopened["unavailable_sources"] == []
    status = json.loads(command(root, "status").stdout)
    assert sorted(p["state"] for p in status["publications"]) == [
        "current",
        "forgotten",
    ]
    forgotten_row = next(p for p in status["publications"] if p["state"] == "forgotten")
    assert forgotten_row["revision"] == 1 and forgotten_row["verified_revision"] == 1
    assert forgotten_row["plan"]["operation"] == "identity_forget"
    tombstone = json.loads(forgotten_row["description"])
    assert tombstone["kind"] == "identity_source_tombstone"
    assert (
        tombstone["mention_ids"]["g01"]
        == initial["sources"][first]["mention_entity_id"]
    )
    for content in ("The controller", "instrument", "limits oscillations"):
        assert content not in json.dumps(forgotten_row)
    assert "runtime_profile" not in forgotten_row["plan"]
    assert all("properties" not in e for e in forgotten_row["plan"]["edges"])

    for operation in ("forget", "reconcile"):
        refused = command(
            root, operation, "--source", first, "--expected-revision", "1", expect=1
        )
        assert "Forgotten source" in error_of(refused)["message"]

    command(root, "readd", "--source", first, "--expected-revision", "1")
    two = result_of(root)
    back = two["sources"][first]
    assert back["state"] == "current"
    assert (back["saved_revision"], back["verified_revision"]) == (2, 2)
    assert back["registered_revision"] == 2 and back["registered_matches_saved"]
    assert back["mention_entity_id"] != initial["sources"][first]["mention_entity_id"]
    # The forget removed the private singleton, so the re-add does not bring
    # back its UUID; the shared HC Entity survived and is referenced again.
    assert (
        back["private_singleton_entity_id"]
        != initial["sources"][first]["private_singleton_entity_id"]
    )
    assert two["hc_entity"]["present"]
    for key in (
        "original_marker_present",
        "original_fact_present",
        "original_fact_owned_by_chunk",
        "original_evidence_present",
        "unresolved_marker_present",
        "unresolved_entity_present",
        "private_singleton_present",
        "private_singleton_indexed",
    ):
        assert back[key], key
    intact(initial, two, other)
    assert sorted(f["source_id"] for f in two["result"]["facts"]) == sorted(
        [back["mention_entity_id"], two["sources"][other]["mention_entity_id"]]
    )
    assert len(two["shared_variant"]["contributions"]) == 2
    assert len(two["shared_variant"]["owners"]) == 2
    assert sorted(two["hc_entity"]["owners"]) == sorted(initial["hc_entity"]["owners"])
    assert two["recovery_events"] == []
    reopened = json.loads(command(root, "retrieve").stdout)
    assert len(reopened["facts"]) == 2 and reopened["unavailable_sources"] == []

    refused = command(
        root, "readd", "--source", first, "--expected-revision", "2", expect=1
    )
    assert "Re-add needs a forgotten source" in error_of(refused)["message"]


def readded_description(root, label):
    from cognee_lab.identity.models import IdentitySource

    path = root / f"identity_{label}_revision2.json"
    return IdentitySource.model_validate_json(path.read_text())


@pytest.mark.integration
def test_native_readd_replaces_what_a_later_forget_of_a_co_owner_removed(tmp_path):
    """doc02 is forgotten while doc01 still owns HC and the shared singleton,
    so they survive. doc01's forget then removes them. Neither re-add brings
    them back under their old UUIDs: HC, which variant v01 names, returns
    under the v01-derived UUID of each source's revision 2, and the shared
    singleton, which nothing names, under the UUID derived from the removed
    one. The two sources get separate replacements."""
    from cognee_lab.identity.erasure_rules import replacement_entity_id
    from cognee_lab.identity.multisource import fixture_id
    from cognee_lab.identity.validation import fresh_entity_id

    root = tmp_path / "interleaved"
    command(root, "multi-fixture")
    old_hc = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
    shared = fixture_id("shared_singleton")

    command(root, "forget", "--source", "doc02", "--expected-revision", "1")
    survived = result_of(root)
    assert survived["hc_entity"]["present"] and survived["shared_singleton_present"]
    command(root, "forget", "--source", "doc01", "--expected-revision", "1")
    removed = result_of(root)
    assert not removed["hc_entity"]["present"]
    assert not removed["shared_singleton_present"]

    for label in ("doc01", "doc02"):
        command(root, "readd", "--source", label, "--expected-revision", "1")
        source = readded_description(root, label)
        identity = source.identity_data_id
        new_hc = fresh_entity_id(identity, 2, "v01")
        new_shared = replacement_entity_id(identity, 2, shared)
        assert source.variant_assignments["v01"].source_entity_id == new_hc
        assert {str(e) for e in source.entity_constructions} >= {
            str(new_hc),
            str(new_shared),
        }
        assert not {old_hc, shared} & {str(e) for e in source.entity_constructions}

    final = result_of(root)
    assert [final["sources"][d]["state"] for d in ("doc01", "doc02")] == [
        "current",
        "current",
    ]
    doc02 = final["sources"]["doc02"]["identity_data_id"]
    # The snapshot follows doc02's v01 variant: its new HC, owned by doc02 alone.
    assert final["hc_entity"]["present"]
    assert [o.rsplit(":", 1)[-1] for o in final["hc_entity"]["owners"]] == [doc02]
    assert not final["shared_singleton_present"]
    assert len(final["result"]["facts"]) == 2
    assert final["recovery_events"] == []


DUPLICATE = """
import asyncio, sys, uuid
from pathlib import Path
from cognee_lab.identity.environment import fixture_environment

root = Path(sys.argv[1])
copy = root / "copy" / "source.txt"
copy.parent.mkdir()
copy.write_text((root / "source.txt").read_text())
with fixture_environment(root):
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem

    asyncio.run(
        cognee.add(
            DataItem(data=str(copy), data_id=uuid.uuid4()),
            dataset_name="stage6_isolated_fixture",
            skip_connection_test=True,
        )
    )
"""


@pytest.mark.integration
def test_native_forget_finishes_when_another_item_keeps_the_stored_file(tmp_path):
    """Cognee stores a file under a content address, so another Data item with
    the same bytes and name shares doc01's stored file and Cognee keeps it.
    The forget completes and leaves that file for the other item."""
    import subprocess
    import sys
    from urllib.parse import unquote, urlparse

    from test_identity_native import REPO

    root = tmp_path / "duplicate"
    command(root, "multi-fixture")
    subprocess.run(
        [sys.executable, "-c", DUPLICATE, str(root)],
        cwd=REPO,
        check=True,
        capture_output=True,
        timeout=300,
    )
    command(root, "forget", "--source", "doc01", "--expected-revision", "1")
    final = result_of(root)
    assert final["sources"]["doc01"]["state"] == "forgotten"
    assert erased(final["sources"]["doc01"]["forget"])
    status = json.loads(command(root, "status").stdout)
    plan = next(p for p in status["publications"] if p["state"] == "forgotten")["plan"]
    kept = [
        unquote(urlparse(location).path) if "://" in location else location
        for location in plan["stored_files"][plan["original_data_id"]]
        if str(root.resolve() / "data") in location
    ]
    assert kept and all(Path(k).exists() for k in kept)


def token_of(root, label):
    """The dry run's token for forgetting a source at revision 1."""
    report = json.loads(
        command(
            root, "forget", "--source", label, "--expected-revision", "1", "--dry-run"
        ).stdout
    )
    return report["token"], report


def removed(entry):
    """doc02's r01 no longer reads doc01: unresolved under the removal
    producer, with doc01's inputs dropped."""
    r01 = entry["decisions"]["r01"]
    return (
        entry["resolution_status"] == "unresolved"
        and r01["producer_ref"].startswith("forget_")
        and r01["input_refs"] == ["doc01", "existing_A"]
        and not {"doc01_text", "doc01_instrument"} & set(entry["input_keys"])
    )


@pytest.mark.integration
def test_native_forget_removes_a_dependents_decision_once_confirmed(tmp_path):
    """doc02's r01 read doc01's text and private singleton. The forget is
    refused without the dry run's token, writes nothing on a dry run, and
    with the token erases doc01 and then unresolves doc02's r01 in a revision
    of its own. A re-add of doc01 does not bring the decision back."""
    root = tmp_path / "dependent"
    command(root, "multi-fixture", "--dependent")
    initial = result_of(root)
    assert len(initial["result"]["facts"]) == 2
    reader = initial["sources"]["doc02"]["identity_data_id"]
    document = next(
        f["evidence"][0]["data_id"]
        for f in initial["result"]["facts"]
        if f["identity"]["identity_data_id"]
        == initial["sources"]["doc01"]["identity_data_id"]
    )

    token, report = token_of(root, "doc01")
    assert report["confirmation_required"]
    (dependent,) = report["dependents"]
    assert dependent["identity_data_id"] == reader and not dependent["blocked"]
    (r01,) = dependent["decisions"]
    assert (r01["assignment"], r01["outcome"]) == ("r01", "unresolved")
    assert sorted((c["input_ref"], c["kind"]) for c in r01["citing"]) == [
        ("doc01_instrument", "corpus_object"),
        ("doc01_text", "source_text"),
    ]
    assert (
        next(c for c in r01["citing"] if c["kind"] == "source_text")["consumed"]
        == document
    )
    assert dependent["unlinked_mentions"] == [
        initial["sources"]["doc02"]["mention_entity_id"]
    ]
    assert any(str(root) in f for f in report["caller_files"])

    refused = command(
        root, "forget", "--source", "doc01", "--expected-revision", "1", expect=1
    )
    answer = error_of(refused)
    assert answer["message"].startswith("This forget removes other sources")
    assert answer["details"]["token"] == token
    unchanged = json.loads(command(root, "retrieve").stdout)
    assert len(unchanged["facts"]) == 2 and unchanged["unavailable_sources"] == []
    status = json.loads(command(root, "status").stdout)
    assert [p["state"] for p in status["publications"]] == ["current", "current"]
    assert status["recovery_events"] == []

    command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--confirm",
        token,
    )
    final = result_of(root)
    assert final["sources"]["doc01"]["state"] == "forgotten"
    assert erased(final["sources"]["doc01"]["forget"])
    assert final["forget"]["dependents_revised"] == [
        dict(identity_data_id=reader, revision=2)
    ]
    assert final["dependents_failed"] is None
    doc02 = final["sources"]["doc02"]
    assert doc02["state"] == "current" and doc02["verified_revision"] == 2
    assert removed(doc02)
    # The local fact stays; no identity query reaches it.
    assert doc02["original_fact_present"] and doc02["original_evidence_present"]
    assert final["result"]["facts"] == []
    assert final["result"]["unavailable_sources"] == []
    assert final["recovery_events"] == []

    command(root, "readd", "--source", "doc01", "--expected-revision", "1")
    back = result_of(root)
    assert back["sources"]["doc01"]["state"] == "current"
    assert removed(back["sources"]["doc02"])
    assert [f["source_id"] for f in back["result"]["facts"]] == [
        back["sources"]["doc01"]["mention_entity_id"]
    ]


@pytest.mark.integration
def test_native_forget_refuses_a_token_whose_impact_changed(tmp_path):
    """The dry run of doc01's forget finds no dependent while doc02 is
    forgotten. doc02's re-add reads doc01 again, so that token no longer
    matches, and the forget is refused before any write."""
    root = tmp_path / "stale"
    command(root, "multi-fixture", "--dependent")
    command(root, "forget", "--source", "doc02", "--expected-revision", "1")
    token, report = token_of(root, "doc01")
    assert not report["confirmation_required"] and report["dependents"] == []
    command(root, "readd", "--source", "doc02", "--expected-revision", "1")
    refused = command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--confirm",
        token,
        expect=1,
    )
    answer = error_of(refused)
    assert answer["message"].startswith("The impact changed")
    assert answer["details"]["token"] != token
    assert len(answer["details"]["dependents"]) == 1
    status = json.loads(command(root, "status").stdout)
    assert [p["state"] for p in status["publications"]] == ["current", "current"]


@pytest.mark.integration
@pytest.mark.parametrize("fault", sorted(DEPENDENT_FAULTS))
def test_native_an_interrupted_removal_resumes_through_reconcile(tmp_path, fault):
    """The forget completes and its dependent's removal is interrupted:
    before the removal revision begins, doc02's r01 still reads doc01 and is
    withheld as input_removed; when the removal revision fails, doc02 is
    withheld whole. A re-add waits. reconcile on doc01 finishes the
    removal."""
    root = tmp_path / "interrupted"
    command(root, "multi-fixture", "--dependent")
    token, _ = token_of(root, "doc01")
    command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--confirm",
        token,
        "--fault-stage",
        fault,
        expect=1,
    )
    stopped = result_of(root)
    assert stopped["sources"]["doc01"]["state"] == "forgotten"
    assert stopped["dependents_failed"]["code"] in (
        "injected_failure",
        "recovery_required",
    )
    query = json.loads(command(root, "retrieve").stdout)
    assert query["facts"] == []
    reasons = [(u["assignment_id"], u["reason"]) for u in query["unavailable_sources"]]
    if fault == "forget_dependents":
        assert stopped["sources"]["doc02"]["saved_revision"] == 1
        assert reasons == [("r01", "input_removed")]
    else:
        assert stopped["sources"]["doc02"]["state"] == "failed"
        assert reasons == [(None, "publication_failed")]
    waiting = command(
        root, "readd", "--source", "doc01", "--expected-revision", "1", expect=1
    )
    assert "has not revised every dependent" in error_of(waiting)["message"]

    command(root, "reconcile", "--source", "doc01")
    done = result_of(root)
    doc02 = done["sources"]["doc02"]
    assert doc02["state"] == "current" and doc02["verified_revision"] == 2
    assert removed(doc02)
    assert done["result"]["unavailable_sources"] == []
    assert all(e["resolved_at"] for e in done["recovery_events"])
    refused = command(
        root, "forget", "--source", "doc01", "--expected-revision", "1", expect=1
    )
    assert "Forgotten source" in error_of(refused)["message"]


@pytest.mark.integration
def test_native_a_dependent_with_an_unfinished_attempt_waits(tmp_path):
    """doc02's withdrawal failed, so it is a blocked dependent: the token
    names it, the forget completes, and its removal waits. Once its
    withdrawal finishes it reads nothing, and the forget has nothing left."""
    root = tmp_path / "blocked"
    command(root, "multi-fixture", "--dependent")
    command(
        root,
        "withdraw",
        "--source",
        "doc02",
        "--fault-stage",
        "withdraw_contributions",
        expect=1,
    )
    token, report = token_of(root, "doc01")
    assert [d["blocked"] for d in report["dependents"]] == [True]
    command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--confirm",
        token,
        expect=1,
    )
    waiting = result_of(root)
    assert waiting["sources"]["doc01"]["state"] == "forgotten"
    assert waiting["dependents_failed"]["code"] == "dependent_unfinished"
    assert [d["state"] for d in waiting["forget"]["dependents_waiting"]] == ["failed"]
    command(root, "withdraw", "--source", "doc02")
    refused = command(root, "reconcile", "--source", "doc01", expect=1)
    assert "Forgotten source" in error_of(refused)["message"]


@pytest.mark.integration
@pytest.mark.parametrize("prior", ["withdrawn", "failed"])
def test_native_any_source_can_be_forgotten(tmp_path, prior):
    """A withdrawn doc02 keeps its document, facts and evidence until the
    forget removes them; a doc02 whose first publication failed is forgotten
    as it stands."""
    root = tmp_path / prior
    if prior == "withdrawn":
        command(root, "multi-fixture")
        command(root, "withdraw", "--source", "doc02")
    else:
        command(
            root,
            "multi-fixture",
            "--source",
            "doc02",
            "--fault-stage",
            "nodes",
            expect=1,
        )
    command(root, "forget", "--source", "doc02", "--expected-revision", "1")
    final = result_of(root)
    assert final["sources"]["doc02"]["state"] == "forgotten"
    assert erased(final["sources"]["doc02"]["forget"])
    assert final["sources"]["doc01"]["state"] == "current"
    assert [f["source_id"] for f in final["result"]["facts"]] == [
        final["sources"]["doc01"]["mention_entity_id"]
    ]
    assert all(
        e["resolved_at"] and e["message"] is None for e in final["recovery_events"]
    )


@pytest.mark.integration
def test_native_readd_takes_the_callers_changed_files(tmp_path):
    """A re-add is a fresh publication from the caller's files: here doc01's
    text gains a sentence, and its identity file states the new digest."""
    from cognee_lab.identity.validation import text_digest

    root = tmp_path / "changed"
    command(root, "multi-fixture")
    command(root, "forget", "--source", "doc01", "--expected-revision", "1")
    text = (root / "source.txt").read_text().rstrip("\n") + " HC was serviced.\n"
    (root / "source.txt").write_text(text)
    refused = command(
        root, "readd", "--source", "doc01", "--expected-revision", "1", expect=1
    )
    assert "text file and identity file disagree" in error_of(refused)["message"]
    identity = json.loads((root / "identity.json").read_text())
    identity["inputs"]["doc01"]["text_sha256"] = text_digest(text)
    (root / "identity.json").write_text(json.dumps(identity))
    command(root, "readd", "--source", "doc01", "--expected-revision", "1")
    back = result_of(root)
    doc01 = back["sources"]["doc01"]
    assert doc01["state"] == "current" and doc01["verified_revision"] == 2
    assert doc01["original_fact_present"] and doc01["registered_matches_saved"]
    assert len(back["result"]["facts"]) == 2
    readded = readded_description(root, "doc01")
    assert readded.inputs["doc01"].text_sha256 == text_digest(text)


@pytest.mark.integration
def test_native_forget_of_the_glossary_removes_what_doc01_read(tmp_path):
    """doc01's r01 and v01 read the glossary's HC entry. Forgetting the
    glossary unresolves r01, drops v01 and HC, which only v01 named, and
    keeps the Helios controller, which doc01 still reads as a corpus input.
    The glossary comes back from its files; the decisions do not."""
    root = tmp_path / "glossary"
    command(root, "glossary-fixture")
    token, report = token_of(root, "glossary")
    (dependent,) = report["dependents"]
    assert [(d["assignment"], d["outcome"]) for d in dependent["decisions"]] == [
        ("r01", "unresolved"),
        ("v01", "dropped"),
    ]
    assert dependent["dropped_entities"] == ["9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"]
    assert dependent["kept_entities"] == ["8b4bff50-907b-56b6-bc80-3b0a7018714a"]
    assert dependent["dropped_inputs"] == ["glossary", "glossary_hc"]
    command(
        root,
        "forget",
        "--source",
        "glossary",
        "--expected-revision",
        "1",
        "--confirm",
        token,
    )
    final = json.loads((root / "glossary_result.json").read_text())
    assert final["sources"]["glossary"]["state"] == "forgotten"
    doc01 = final["sources"]["doc01"]
    assert doc01["state"] == "current" and doc01["saved_revision"] == 2
    assert list(doc01["decisions"]) == ["r01"]
    assert doc01["decisions"]["r01"]["producer_ref"].startswith("forget_")
    assert doc01["glossary_spans"] == {}
    assert final["glossary"]["text"] is None
    assert final["result"]["facts"] == [] and final["helios"]["facts"] == []
    assert final["result"]["unavailable_sources"] == []
    command(root, "readd", "--source", "glossary", "--expected-revision", "1")
    back = json.loads((root / "glossary_result.json").read_text())
    assert back["sources"]["glossary"]["state"] == "current"
    assert back["glossary"]["hc_entry"]["start"] == 10
    assert list(back["sources"]["doc01"]["decisions"]) == ["r01"]
    assert back["helios"]["facts"] == []


@pytest.mark.integration
def test_native_a_failed_refresh_takes_the_removal_in_its_saved_revision(tmp_path):
    """After a glossary edit, doc01's refresh failed: its saved revision 2
    reads the glossary at the new range, and only replace resumes it, which
    can never register the forgotten glossary again. Forgetting the glossary
    applies the removal to that saved revision and the replacement finishes
    with it, so nothing is left unfinished and the glossary comes back."""
    root = tmp_path / "glossary"
    command(root, "glossary-fixture")
    command(
        root,
        "edit-glossary",
        "--source",
        "glossary",
        "--case",
        "insert",
        "--expected-revision",
        "1",
        "--fault-stage",
        "refresh_interrupted",
    )
    forget = ("forget", "--source", "glossary", "--expected-revision", "2")
    report = json.loads(command(root, *forget, "--dry-run").stdout)
    (dependent,) = report["dependents"]
    assert (dependent["state"], dependent["revision"]) == ("failed", 2)
    assert not dependent["blocked"]
    command(root, *forget, "--confirm", report["token"])
    final = json.loads((root / "glossary_result.json").read_text())
    assert final["dependents_failed"] is None
    doc01 = final["sources"]["doc01"]
    assert doc01["state"] == "current" and doc01["saved_revision"] == 2
    assert list(doc01["decisions"]) == ["r01"]
    assert doc01["decisions"]["r01"]["producer_ref"].startswith("forget_")
    assert doc01["glossary_spans"] == {}
    assert final["result"]["unavailable_sources"] == []
    refused = command(root, "reconcile", "--source", "glossary", expect=1)
    assert "Forgotten source" in error_of(refused)["message"]
    command(root, "readd", "--source", "glossary", "--expected-revision", "2")
    back = json.loads((root / "glossary_result.json").read_text())
    assert back["sources"]["glossary"]["state"] == "current"
    assert list(back["sources"]["doc01"]["decisions"]) == ["r01"]


@pytest.mark.integration
def test_native_a_failed_first_publication_takes_the_removal_in_its_saved_revision(
    tmp_path,
):
    """doc02's first publication failed while it reads doc01's text. Once
    doc01 is forgotten, doc02's own reconcile cannot finish its saved
    revision, which cites a document that is no longer registered, and
    nothing of doc02 is served. Reconciling the forgotten doc01 applies the
    removal to doc02's saved revision and finishes the publication with it."""
    root = tmp_path / "failed_first"
    command(
        root,
        "multi-fixture",
        "--dependent",
        "--source",
        "doc02",
        "--fault-stage",
        "nodes",
        expect=1,
    )
    token, report = token_of(root, "doc01")
    (dependent,) = report["dependents"]
    assert (dependent["state"], dependent["blocked"]) == ("failed", False)
    forget = ("forget", "--source", "doc01", "--expected-revision", "1")
    command(
        root,
        *forget,
        "--confirm",
        token,
        "--fault-stage",
        "forget_dependents",
        expect=1,
    )
    interrupted = result_of(root)
    assert interrupted["dependents_failed"]["code"] == "injected_failure"
    assert interrupted["sources"]["doc02"]["state"] == "failed"
    assert interrupted["result"]["facts"] == []
    refused = command(root, "reconcile", "--source", "doc02", expect=1)
    assert "Original Data item is not registered" in error_of(refused)["message"]
    command(root, "reconcile", "--source", "doc01")
    final = result_of(root)
    assert final["dependents_failed"] is None
    doc02 = final["sources"]["doc02"]
    assert doc02["state"] == "current" and removed(doc02)
    # The local fact stays; no identity query reaches it.
    assert doc02["original_fact_present"] and doc02["original_evidence_present"]
    assert final["result"]["facts"] == []
    assert final["result"]["unavailable_sources"] == []
    assert all(e["resolved_at"] for e in final["recovery_events"])
    refused = command(root, "reconcile", "--source", "doc01", expect=1)
    assert "Forgotten source" in error_of(refused)["message"]


@pytest.mark.integration
def test_native_readd_of_a_consumer_waits_for_the_unfinished_forget(tmp_path):
    """doc02 consumed doc01. With doc02 forgotten, doc01's forget fails at its
    first stage. Re-adding doc02 would make it a dependent again and leave
    doc01's forget refused, so the re-add is refused until doc01 is forgotten."""
    root = tmp_path / "fence"
    command(root, "multi-fixture", "--dependent")
    command(root, "forget", "--source", "doc02", "--expected-revision", "1")
    command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--fault-stage",
        "forget_contributions",
        expect=1,
    )
    refused = command(
        root, "readd", "--source", "doc02", "--expected-revision", "1", expect=1
    )
    report = error_of(refused)
    assert "forget is not finished" in report["message"]
    assert sorted(d["input_ref"] for d in report["details"]["dependents"]) == [
        "doc01_instrument",
        "doc01_text",
    ]
    status = json.loads(command(root, "status").stdout)
    assert sorted(p["state"] for p in status["publications"]) == ["failed", "forgotten"]

    command(root, "reconcile", "--source", "doc01")
    recovered = result_of(root)
    assert recovered["sources"]["doc01"]["state"] == "forgotten"
    assert erased(recovered["sources"]["doc01"]["forget"])
    # The refused re-add came before any write: nothing of doc02 came back.
    assert recovered["sources"]["doc02"]["state"] == "forgotten"
    assert erased(recovered["sources"]["doc02"]["forget"])


@pytest.mark.integration
@pytest.mark.parametrize("fault", [*STAGES, *COMMITTED_FAULTS])
def test_native_forget_failure_withholds_the_source_and_reconcile_finishes_it(
    tmp_path, fault
):
    stage = COMMITTED_FAULTS.get(fault, fault)
    root = tmp_path / "forget_failure"
    command(root, "multi-fixture")
    initial = result_of(root)
    failed = command(
        root,
        "forget",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--fault-stage",
        fault,
        expect=1,
    )
    assert "recovery_event_id=" in error_of(failed)["message"]
    query = json.loads(command(root, "retrieve").stdout)
    assert [f["source_id"] for f in query["facts"]] == [
        initial["sources"]["doc02"]["mention_entity_id"]
    ]
    assert [u["reason"] for u in query["unavailable_sources"]] == ["publication_failed"]
    status = json.loads(command(root, "status").stdout)
    (incident,) = status["recovery_events"]
    assert incident["operation"] == "forget" and incident["stage"] == stage
    assert incident["origin"] == "test/fault_injection"
    assert incident["resolved_at"] is None
    blocked = command(root, "withdraw", "--source", "doc01", expect=1)
    assert "Retry the failed forget explicitly" in error_of(blocked)["message"]

    command(root, "reconcile", "--source", "doc01")
    recovered = result_of(root)
    assert recovered["sources"]["doc01"]["state"] == "forgotten"
    assert erased(recovered["sources"]["doc01"]["forget"])
    intact(initial, recovered, "doc02")
    assert [f["source_id"] for f in recovered["result"]["facts"]] == [
        initial["sources"]["doc02"]["mention_entity_id"]
    ]
    assert recovered["result"]["unavailable_sources"] == []
    (incident,) = recovered["recovery_events"]
    assert incident["outcome"] == "forgotten" and incident["resolved_at"]
    assert incident["recovery_attempts"][-1]["method"] == "forget"
    assert incident["recovery_attempts"][-1]["outcome"] == "verified"


@pytest.mark.integration
def test_native_reconcile_finishes_a_readd_that_failed_before_its_facts(tmp_path):
    """A fault at the nodes stage comes before the captured facts are written.
    The reconcile of that failed re-add writes them."""
    root = tmp_path / "readd_failure"
    command(root, "multi-fixture")
    initial = result_of(root)
    command(root, "forget", "--source", "doc01", "--expected-revision", "1")
    failed = command(
        root,
        "readd",
        "--source",
        "doc01",
        "--expected-revision",
        "1",
        "--fault-stage",
        "nodes",
        expect=1,
    )
    assert "recovery_event_id=" in error_of(failed)["message"]
    status = json.loads(command(root, "status").stdout)
    assert sorted(p["state"] for p in status["publications"]) == ["current", "failed"]

    command(root, "reconcile", "--source", "doc01")
    recovered = result_of(root)
    back = recovered["sources"]["doc01"]
    assert back["state"] == "current"
    assert (back["saved_revision"], back["verified_revision"]) == (2, 2)
    assert back["original_fact_present"] and back["original_evidence_present"]
    intact(initial, recovered, "doc02")
    assert len(recovered["result"]["facts"]) == 2
    (incident,) = recovered["recovery_events"]
    assert incident["outcome"] == "restored" and incident["resolved_at"]


@pytest.mark.integration
def test_native_reconcile_finishes_a_first_publication_that_failed_before_its_facts(
    tmp_path,
):
    root = tmp_path / "publish_failure"
    command(root, "fixture", "--fault-stage", "nodes", expect=1)
    status = json.loads(command(root, "status").stdout)
    assert [p["state"] for p in status["publications"]] == ["failed"]
    command(root, "reconcile")
    recovered = json.loads((root / "result.json").read_text())
    fact = next(
        f for f in recovered["result"]["facts"] if f["relationship"] == "limits"
    )
    assert fact["identity"]["state"] == "accepted" and fact["evidence"]
    assert recovered["result"]["unavailable_sources"] == []
    (incident,) = recovered["recovery_events"]
    assert incident["stage"] == "nodes"
    assert incident["outcome"] == "restored" and incident["resolved_at"]
    status = json.loads(command(root, "status").stdout)
    assert [p["state"] for p in status["publications"]] == ["current"]
