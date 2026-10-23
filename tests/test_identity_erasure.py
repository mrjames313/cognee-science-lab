"""Erasure's effect on dependents, from descriptions alone: the impact and
its token, the removal revision and its admission, what stays unfinished,
and what a tombstone and a scrubbed plan keep."""

import json
from uuid import UUID, uuid4

import pytest

from cognee_lab.identity.admission import admit, check_erasure_retry, identity_map
from cognee_lab.identity.erasure import (
    impact,
    producer_key,
    removal_producer,
    removal_revision,
    unfinished,
)
from cognee_lab.identity.fixture import FIXTURES
from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.retirement import source_ids
from cognee_lab.identity.storage import PublicationRow, scrubbed_plan
from cognee_lab.identity.validation import IntentError, object_digest, text_digest

TEXT = (FIXTURES / "source.txt").read_text()
HC = UUID("9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88")
HELIOS = UUID("8b4bff50-907b-56b6-bc80-3b0a7018714a")
ENTRY = "HC: Helios controller."


def source_of(payload):
    return IdentitySource.model_validate_json(json.dumps(payload))


def row_of(source, state="current", plan=None):
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state=state,
        revision=source.revision,
        verified_revision=source.revision,
        attempt="attempt",
        description=source.model_dump_json(),
        plan=plan or {"operation": "identity_publish"},
    )


def forgotten_plan(source, entities=()):
    """A forget plan whose Entities this source alone owns."""
    own = f"source_ref:v1:{source.dataset_id}:{source.identity_data_id}"
    return dict(
        operation="identity_forget",
        revision=source.revision,
        original_data_id=str(source.inputs[source.original_input_ref].data_id),
        entities={
            str(e): dict(refs=[own], type="Entity", indexed_fields=["name"])
            for e in entities
        },
        edges=[],
    )


def glossary(payload):
    """A glossary-like source: no groups and no decisions."""
    payload = json.loads(json.dumps(payload))
    payload["identity_data_id"] = str(uuid4())
    payload["inputs"] = {
        "doc01": dict(payload["inputs"]["doc01"], data_id=str(uuid4())),
    }
    payload["inputs"]["doc01"]["text_sha256"] = text_digest(ENTRY + "\n")
    payload["entity_constructions"] = {}
    payload["mention_groups"] = {}
    payload["mention_resolutions"] = {}
    payload["variant_assignments"] = {}
    return source_of(payload)


def reader_of(source_payload, read, *, entity=None, scope=None):
    """doc01 reading the glossary's entry as a span from r01 and v01, and
    optionally a corpus input naming `entity` from r01."""
    payload = json.loads(json.dumps(source_payload))
    doc = read.inputs[read.original_input_ref]
    payload["inputs"]["gloss"] = doc.model_dump(mode="json")
    payload["inputs"]["gloss_hc"] = dict(
        kind="text_span",
        document_ref="gloss",
        start=0,
        end=len(ENTRY),
        text_sha256=text_digest(ENTRY),
    )
    for record in ("r01", "v01"):
        target = (
            payload["mention_resolutions"].get(record)
            or payload["variant_assignments"][record]
        )
        target["input_refs"].append("gloss_hc")
    if scope:
        payload["variant_assignments"]["v01"]["applicability"] = scope
    if entity is not None:
        payload["inputs"]["read_entity"] = dict(
            kind="corpus_object",
            dataset_id=payload["dataset_id"],
            entity_id=str(entity),
            selected_fields=["name"],
            content_sha256=object_digest({"name": "x"}),
        )
        payload["mention_resolutions"]["r01"]["input_refs"].append("read_entity")
    return source_of(payload)


def test_a_reader_of_the_forgotten_span_loses_both_decisions(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    found = impact(gloss, forgotten_plan(gloss), [row_of(gloss), row_of(doc01)])
    (dependent,) = found.dependents
    assert dependent.identity_data_id == str(doc01.identity_data_id)
    assert not dependent.blocked
    assert [(r.assignment, r.kind, r.outcome) for r in dependent.decisions] == [
        ("r01", "resolution", "unresolved"),
        ("v01", "variant", "dropped"),
    ]
    assert [c._asdict() for c in dependent.decisions[0].citing] == [
        dict(
            input_ref="gloss_hc",
            kind="text_span",
            consumed=str(gloss.inputs["doc01"].data_id),
        )
    ]
    # HC was named only by v01; the Helios controller only by r01 and v01,
    # but doc01 still reads it as the corpus input existing_A.
    assert dependent.dropped_entities == (str(HC),)
    assert dependent.kept_entities == (str(HELIOS),)
    assert dependent.unlinked_mentions == (str(doc01.mention_groups["g01"].entity_id),)
    assert dependent.dropped_inputs == ("gloss", "gloss_hc")


def test_a_third_reader_keeps_the_recipe_a_removed_decision_named(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    third = json.loads(json.dumps(source_payload))
    third["identity_data_id"] = str(uuid4())
    third["inputs"]["doc01"]["data_id"] = str(uuid4())
    third["inputs"]["hc"] = dict(third["inputs"]["existing_A"], entity_id=str(HC))
    third["variant_assignments"]["v01"]["input_refs"].append("hc")
    rows = [row_of(gloss), row_of(doc01), row_of(source_of(third))]
    (dependent,) = impact(gloss, forgotten_plan(gloss), rows).dependents
    assert dependent.dropped_entities == ()
    assert set(dependent.kept_entities) == {str(HC), str(HELIOS)}


def test_the_removal_revision_is_admitted_and_cites_nothing_forgotten(
    source_payload,
):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    ids = source_ids(gloss)
    revised, _ = removal_revision(doc01, ids, set(), token="t" * 64)
    assert revised.revision == doc01.revision + 1
    r01 = revised.mention_resolutions["r01"]
    assert r01.status == "unresolved"
    assert r01.input_refs == ["doc01", "existing_A"]
    assert r01.producer_ref == producer_key(ids, 2)
    assert "v01" not in revised.variant_assignments
    assert HC not in revised.entity_constructions
    assert {"gloss", "gloss_hc"}.isdisjoint(revised.inputs)
    assert revised.producers[producer_key(ids, 2)].configuration == dict(
        forgotten_identity_data_id=str(gloss.identity_data_id),
        forgotten_document_id=str(gloss.inputs["doc01"].data_id),
        removed_entity_ids=[],
        impact_token="t" * 64,
    )
    admit(doc01, revised, TEXT, TEXT, identity_map(doc01))


def test_a_corpus_scoped_variant_citing_the_span_is_dropped(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss, scope=dict(kind="corpus"))
    revised, parts = removal_revision(doc01, source_ids(gloss), set())
    assert [r.assignment for r in parts["decisions"]] == ["r01", "v01"]
    admit(doc01, revised, TEXT, TEXT, identity_map(doc01))


def test_a_removed_entity_read_as_a_corpus_input_is_cited(source_payload):
    gloss = glossary(source_payload)
    entity = uuid4()
    doc01 = reader_of(source_payload, gloss, entity=entity)
    found = impact(
        gloss,
        forgotten_plan(gloss, [entity]),
        [row_of(gloss), row_of(doc01)],
    )
    r01, _ = found.dependents[0].decisions
    assert ("read_entity", "corpus_object", str(entity)) in [
        tuple(c) for c in r01.citing
    ]
    assert found.removed_entities == (str(entity),)


def test_the_token_names_the_affected_decision_set(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    plan = forgotten_plan(gloss)
    alone = impact(gloss, plan, [row_of(gloss)])
    assert alone.dependents == ()
    one = impact(gloss, plan, [row_of(gloss), row_of(doc01)])
    assert one.token != alone.token
    assert impact(gloss, plan, [row_of(doc01), row_of(gloss)]).token == one.token
    # A dependent whose own attempt failed is listed, blocked, and changes
    # the token.
    blocked = impact(gloss, plan, [row_of(gloss), row_of(doc01, "failed")])
    assert blocked.dependents[0].blocked and blocked.token != one.token
    # A new dependent changes it too.
    other = json.loads(doc01.model_dump_json())
    other["identity_data_id"] = str(uuid4())
    other["inputs"]["doc01"]["data_id"] = str(uuid4())
    two = impact(gloss, plan, [row_of(gloss), row_of(doc01), row_of(source_of(other))])
    assert len(two.dependents) == 2 and two.token != one.token
    # Withdrawn and forgotten sources read nothing.
    assert impact(gloss, plan, [row_of(gloss), row_of(doc01, "withdrawn")]).token == (
        alone.token
    )


def test_a_failed_replacement_takes_the_removal_in_its_saved_revision(
    source_payload,
):
    """The removal applied in place keeps the saved revision, so a retry of
    the failed replacement can finish with it. Any other description at that
    revision is not a retry."""
    gloss = glossary(source_payload)
    saved = reader_of(source_payload, gloss)
    ids = source_ids(gloss)
    found = impact(
        gloss,
        forgotten_plan(gloss),
        [row_of(gloss), row_of(saved, "failed", {"operation": "identity_replace"})],
    )
    assert not found.dependents[0].blocked
    revised, _ = removal_revision(saved, ids, set(), in_place=True)
    assert revised.revision == saved.revision
    assert revised.mention_resolutions["r01"].producer_ref == producer_key(
        ids, saved.revision
    )
    check_erasure_retry(saved, revised)
    changed = json.loads(saved.model_dump_json())
    changed["mention_resolutions"]["r01"]["explanation"] = "changed"
    with pytest.raises(IntentError) as refused:
        check_erasure_retry(saved, source_of(changed))
    assert refused.value.code == "revision_reuse"


def test_unfinished_is_derived_from_the_rows(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    ids = source_ids(gloss)
    tombstone = Tombstone.of(gloss, forgotten_at="t")
    revised, _ = removal_revision(doc01, ids, set())
    assert unfinished(tombstone, [row_of(doc01)]) == [row_of(doc01)]
    assert unfinished(tombstone, [row_of(revised)]) == []
    failed = row_of(revised, "failed", {"operation": "identity_replace"})
    assert unfinished(tombstone, [failed]) == [failed]
    assert unfinished(tombstone, [row_of(doc01, "withdrawn")]) == []


SPARE = uuid4()


def erasure_case(source_payload, change):
    """The removal revision with one change, admitted against doc01, which
    also declares a singleton that nothing names."""
    gloss = glossary(source_payload)
    payload = json.loads(json.dumps(source_payload))
    payload["entity_constructions"][str(SPARE)] = dict(name="spare", description="")
    doc01 = reader_of(payload, gloss)
    revised, _ = removal_revision(doc01, source_ids(gloss), set())
    payload = json.loads(revised.model_dump_json())
    change(payload, doc01)
    with pytest.raises(IntentError) as refused:
        admit(doc01, source_of(payload), TEXT, TEXT, identity_map(doc01))
    return refused.value.code


def keep_v01(payload, old):
    payload["variant_assignments"]["v01"] = old.variant_assignments["v01"].model_dump(
        mode="json"
    )
    for key in ("gloss", "gloss_hc"):
        payload["inputs"][key] = old.inputs[key].model_dump(mode="json")
    payload["entity_constructions"][str(HC)] = old.entity_constructions[HC].model_dump(
        mode="json"
    )


def keep_r01_accepted(payload, old):
    payload["mention_resolutions"]["r01"] = dict(
        old.mention_resolutions["r01"].model_dump(mode="json"),
        input_refs=["doc01", "existing_A"],
    )


def drop_an_unrelated_recipe(payload, old):
    payload["entity_constructions"].pop(str(SPARE))


def wrong_document(payload, old):
    key = next(k for k in payload["producers"] if k.startswith("forget_"))
    payload["producers"][key]["configuration"]["forgotten_document_id"] = str(uuid4())


def no_configuration(payload, old):
    key = next(k for k in payload["producers"] if k.startswith("forget_"))
    payload["producers"][key]["configuration"] = {}


@pytest.mark.parametrize(
    "change, code",
    [
        (keep_v01, "erasure_incomplete"),
        # Rule 5 refuses it first: r01 drops a foreign input under its old
        # producer.
        (keep_r01_accepted, "reconfirm_unattested"),
        (drop_an_unrelated_recipe, "erasure_unrelated"),
        (wrong_document, "erasure_unrelated"),
        (no_configuration, "erasure_configuration"),
    ],
)
def test_an_erasure_removal_is_complete_and_nothing_else(source_payload, change, code):
    assert erasure_case(source_payload, change) == code


def test_a_tombstone_keeps_identifiers_only(source_payload):
    source = source_of(source_payload)
    tombstone = Tombstone.of(source, forgotten_at="t", removed_entity_ids=[HC])
    text = tombstone.model_dump_json()
    for content in ("The controller", "Helios controller", "Abbreviated", "it"):
        assert f'"{content}' not in text
    assert tombstone.mention_ids == {"g01": source.mention_groups["g01"].entity_id}
    assert set(tombstone.entity_ids) == {HC, HELIOS}
    assert tombstone.used_entity_ids == {
        HC,
        HELIOS,
        source.mention_groups["g01"].entity_id,
    }


def test_a_scrubbed_plan_keeps_no_edge_property():
    plan = dict(
        operation="identity_forget",
        revision=1,
        runtime_profile={"cognee_version": "1.6.2"},
        stored_files={"d": ["/data/text_abc.txt"]},
        edges=[
            dict(
                source="a",
                target="b",
                relation="limits",
                refs=["r"],
                properties={"fact": "it limits oscillations"},
            )
        ],
    )
    assert scrubbed_plan(plan) == dict(
        operation="identity_forget",
        revision=1,
        stored_files={"d": ["/data/text_abc.txt"]},
        edges=[dict(source="a", target="b", relation="limits", refs=["r"])],
    )


def test_the_removal_producer_names_what_the_forget_took_away(source_payload):
    gloss = glossary(source_payload)
    producer = removal_producer(source_ids(gloss), {HC}, None)
    assert producer["implementation"] == "removed by forget"
    assert producer["configuration"]["removed_entity_ids"] == [str(HC)]
