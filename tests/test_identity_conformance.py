"""The conformance fixture's describer over DOC01: its four name rules, its
hand-read references, and the sentence rule's facts. Native chunks are
stood in for by fixed slices; tests/test_identity_conformance_native.py
publishes the real fixture."""

import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID, uuid5

import pytest

from cognee_lab.identity import conformance_fixture as conformance
from cognee_lab.identity.environment import create_root
from cognee_lab.identity.validation import IntentError

TEXT = conformance.DOC01.read_text()
DATASET = UUID("3335f62e-9730-51e8-9be4-facf916eafa1")


def slices(text, size=1500):
    return [
        SimpleNamespace(
            id=uuid5(DATASET, f"chunk:{i}"), chunk_index=i, text=text[at : at + size]
        )
        for i, at in enumerate(range(0, len(text), size))
    ]


@pytest.fixture(scope="module")
def source():
    return conformance.describe(TEXT, slices(TEXT), DATASET)


def names_of(source):
    return {e: r.name for e, r in source.entity_constructions.items()}


def test_name_rules_find_the_defined_names_and_their_variants():
    names, variants = conformance.reusable_names(TEXT)
    assert variants == [
        ("AFRL", "Aurora Fusion Research Laboratory"),
        ("NBI", "neutral beam injection"),
        ("ECH", "electron cyclotron heating"),
        ("PCPS", "Plasma Current Power Supply"),
        ("VCS", "Vertical Control System"),
        ("EDC", "Edge Density Controller"),
        ("RCM", "Rogowski Current Monitor"),
        ("MPA", "Magnetic Probe Array"),
        ("Neutral Beam Injection System", "neutral beam injection"),
        ("Electron Cyclotron Heating System", "electron cyclotron heating"),
        ("Helios 1", "Helios-1"),
        ("H-1", "Helios-1"),
    ]
    named = {n for pair in variants for n in pair}
    assert set(names.values()) - named == {"Aurora Reconstruction Suite", "Campaign A"}


def test_alias_statement_stops_at_its_where_qualifier():
    """“Helios” and “the machine” are context-dependent in DOC01, so neither
    becomes a reusable name."""
    names, _ = conformance.reusable_names(TEXT)
    assert "helios" not in names and "the machine" not in names


def test_references_resolve_to_reusable_names(source):
    names = names_of(source)
    groups = {
        key: (
            [o.text for o in g.occurrences],
            names[
                next(
                    d.target_entity_id
                    for d in source.mention_resolutions.values()
                    if d.group_ref == key
                )
            ],
        )
        for key, g in source.mention_groups.items()
    }
    assert groups["g01"] == (["The controller", "It"], "Vertical Control System")
    assert groups["g05"] == (
        ["Aurora", "The suite", "The suite", "It"],
        "Aurora Reconstruction Suite",
    )
    assert all(
        TEXT[o.start : o.end] == o.text
        for g in source.mention_groups.values()
        for o in g.occurrences
    )
    assert all(g.chunk_refs for g in source.mention_groups.values())


def test_a_passage_must_occur_once():
    with pytest.raises(IntentError) as refused:
        conformance.locate(TEXT, "It", "It")
    assert refused.value.code == "fixture_shape"


def test_sentence_rule_states_each_target_with_the_first_named_subject(source):
    names = names_of(source)
    facts = {
        (names[f.subject_id], f.target.name): f
        for f in conformance.facts_of(source, TEXT)
    }
    assert {
        ("Helios-1", "Aurora Fusion Research Laboratory"),
        ("Helios-1", "1.35 m"),
        ("Helios-1", "0.42 m"),
        ("Helios-1", "6.2 T"),
        ("VCS", "10 kHz"),
        ("The controller; It", "Magnetic Probe Array"),
    } <= set(facts)
    radius = facts[("Helios-1", "1.35 m")]
    assert radius.text == TEXT[radius.start : radius.end]
    assert radius.text.startswith("Helios-1 has a major radius of 1.35 m")


def test_sentence_rule_never_targets_a_mention_or_the_subjects_group(source):
    mentions = {g.entity_id for g in source.mention_groups.values()}
    variants = {
        frozenset((v.source_entity_id, v.target_entity_id))
        for v in source.variant_assignments.values()
    }
    for fact in conformance.facts_of(source, TEXT):
        assert fact.target.id not in mentions
        assert frozenset((fact.subject_id, fact.target.id)) not in variants


def test_facts_come_from_doc01_text_alone(source):
    """The same text gives the same facts on other chunk boundaries."""
    other = conformance.describe(TEXT, slices(TEXT, 900), DATASET)
    assert conformance.facts_of(source, TEXT) == conformance.facts_of(other, TEXT)


def test_a_conformance_root_takes_only_status_retrieve_and_search(tmp_path):
    root = tmp_path / "root"
    create_root(root, "loopback", "conformance-fixture")
    refused = subprocess.run(
        [sys.executable, "-m", "cognee_lab.identity", "reconcile", "--root", str(root)],
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 2
    assert "takes retrieve, search, status only" in refused.stderr
