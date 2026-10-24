"""Erasure's effect on dependents, from descriptions alone: the impact and
its token, the removal revision and its admission, what stays unfinished,
and what a tombstone and a scrubbed plan keep."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from cognee_lab.identity.admission import admit, identity_map
from cognee_lab.identity.erasure_rules import (
    Erasures,
    check_erasure_retry,
    check_retry_chain,
    erasures_of,
    producer_key,
)
from cognee_lab.identity.erasure import cascade, impact, unfinished
from cognee_lab.identity.records import RemovedRecord
from cognee_lab.identity.fixture import FIXTURES
from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.retirement import contribution_triples, source_ids
from cognee_lab.identity.storage import PublicationRow, scrubbed_plan
from cognee_lab.identity.validation import IntentError, object_digest, text_digest

TEXT = (FIXTURES / "source.txt").read_text()
HC = UUID("9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88")
HELIOS = UUID("8b4bff50-907b-56b6-bc80-3b0a7018714a")
ENTRY = "HC: Helios controller."


def source_of(payload):
    return IdentitySource.model_validate_json(json.dumps(payload))


def row_of(source, state="current", plan=None):
    """A saved row; a failed replacement's revision was never verified."""
    plan = plan or {"operation": "identity_publish"}
    unverified = state == "failed" and plan["operation"] == "identity_replace"
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        state=state,
        revision=source.revision,
        verified_revision=source.revision - unverified,
        attempt="attempt",
        description=source,
        tombstone=None,
        plan=plan,
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


def forgot(gloss, removed=(), readers=()):
    """What the ledger lets a removal claim once `gloss` is forgotten."""
    return Erasures(
        {gloss.inputs["doc01"].data_id: frozenset(removed)}, frozenset(readers)
    )


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


def removal(reader, gloss, *, token=None, state="current", plan=None):
    """The reader's removal revision for the forget of `gloss`, with what it
    does."""
    (step,) = cascade([row_of(reader, state, plan)], source_ids(gloss), set(), token)
    return step.description, step.impact


def test_a_reader_of_the_forgotten_span_loses_both_decisions(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    found = impact(gloss, forgotten_plan(gloss), [row_of(gloss), row_of(doc01)])
    (dependent,) = found.dependents
    assert dependent.identity_data_id == str(doc01.identity_data_id)
    assert not dependent.blocked
    assert dependent.level == 1 and dependent.cited_records == ()
    assert [(r.assignment, r.record_type, r.outcome) for r in dependent.decisions] == [
        ("r01", "mention_resolution", "unresolved"),
        ("v01", "variant_assignment", "dropped"),
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
    revised, _ = removal(doc01, gloss, token="t" * 64)
    assert revised.revision == doc01.revision + 1
    r01 = revised.mention_resolutions["r01"]
    assert r01.status == "unresolved"
    assert r01.input_refs == ["doc01", "existing_A"]
    assert r01.producer_ref == producer_key(ids.identity_data_id, 2)
    assert "v01" not in revised.variant_assignments
    assert HC not in revised.entity_constructions
    assert {"gloss", "gloss_hc"}.isdisjoint(revised.inputs)
    assert revised.producers[
        producer_key(ids.identity_data_id, 2)
    ].configuration == dict(
        forgotten_identity_data_id=str(gloss.identity_data_id),
        forgotten_document_id=str(gloss.inputs["doc01"].data_id),
        removed_entity_ids=[],
        impact_token="t" * 64,
        removed_records=[
            RemovedRecord.of(doc01, key, doc01.revision)._asdict()
            for key in ("r01", "v01")
        ],
        cited_records=[],
    )
    admit(doc01, revised, TEXT, TEXT, identity_map(doc01), erasures=forgot(gloss))


def test_a_corpus_scoped_variant_citing_the_span_is_dropped(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss, scope=dict(kind="corpus"))
    revised, found = removal(doc01, gloss)
    assert [r.assignment for r in found.decisions] == ["r01", "v01"]
    admit(doc01, revised, TEXT, TEXT, identity_map(doc01), erasures=forgot(gloss))


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
    # A dependent whose own withdrawal failed is listed, blocked, and
    # changes the token. One whose publication failed takes the removal in
    # its saved revision, and its state changes the token too.
    withdrawing = {"operation": "identity_withdraw"}
    blocked = impact(gloss, plan, [row_of(gloss), row_of(doc01, "failed", withdrawing)])
    assert blocked.dependents[0].blocked and blocked.token != one.token
    failed = impact(gloss, plan, [row_of(gloss), row_of(doc01, "failed")])
    assert not failed.dependents[0].blocked and failed.token != one.token
    # A new dependent changes it too.
    other = json.loads(doc01.model_dump_json())
    other["identity_data_id"] = str(uuid4())
    other["inputs"]["doc01"]["data_id"] = str(uuid4())
    two = impact(gloss, plan, [row_of(gloss), row_of(doc01), row_of(source_of(other))])
    assert len(two.dependents) == 2 and two.token != one.token
    # A dependent's next revision changes it even when the decisions it
    # would lose are the same.
    later = json.loads(doc01.model_dump_json())
    later["revision"] += 1
    assert impact(gloss, plan, [row_of(gloss), row_of(source_of(later))]).token != (
        one.token
    )
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
    revised, _ = removal(
        saved, gloss, state="failed", plan={"operation": "identity_replace"}
    )
    assert revised.revision == saved.revision
    assert revised.mention_resolutions["r01"].producer_ref == producer_key(
        ids.identity_data_id, saved.revision
    )
    # The saved revision was never served, so a citer pinned the one before.
    removed = revised.producers[producer_key(ids.identity_data_id, saved.revision)]
    assert {r["last_revision"] for r in removed.configuration["removed_records"]} == {
        saved.revision - 1
    }
    check_erasure_retry(saved, revised, forgot(gloss), saved.revision - 1)
    changed = json.loads(saved.model_dump_json())
    changed["mention_resolutions"]["r01"]["explanation"] = "changed"
    with pytest.raises(IntentError) as refused:
        check_erasure_retry(
            saved, source_of(changed), forgot(gloss), saved.revision - 1
        )
    assert refused.value.code == "revision_reuse"


def test_unfinished_is_derived_from_the_rows(source_payload):
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    ids = source_ids(gloss)
    tombstone = Tombstone.of(gloss, forgotten_at="t")
    revised, _ = removal(doc01, gloss)
    assert unfinished(tombstone, [row_of(doc01)]) == [row_of(doc01)]
    assert unfinished(tombstone, [row_of(revised)]) == []
    failed = row_of(revised, "failed", {"operation": "identity_replace"})
    assert unfinished(tombstone, [failed]) == [failed]
    assert unfinished(tombstone, [row_of(doc01, "withdrawn")]) == []
    # A later revision that only carries the removal producer forward is not
    # the removal revision, even when it fails.
    later = json.loads(revised.model_dump_json())
    later["revision"] += 1
    replacing = {"operation": "identity_replace"}
    assert unfinished(tombstone, [row_of(source_of(later), "failed", replacing)]) == []


SPARE = uuid4()
REPLACING = {"operation": "identity_replace"}
PUBLISHING = {"operation": "identity_publish"}
FORGETTING = {"operation": "identity_forget"}


def erasure_case(source_payload, change):
    """The removal revision with one change, admitted against doc01, which
    also declares a singleton that nothing names."""
    gloss = glossary(source_payload)
    payload = json.loads(json.dumps(source_payload))
    payload["entity_constructions"][str(SPARE)] = dict(name="spare", description="")
    doc01 = reader_of(payload, gloss)
    revised, _ = removal(doc01, gloss)
    payload = json.loads(revised.model_dump_json())
    change(payload, doc01)
    with pytest.raises(IntentError) as refused:
        admit(
            doc01,
            source_of(payload),
            TEXT,
            TEXT,
            identity_map(doc01),
            erasures=forgot(gloss),
        )
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


def claim_an_entity(payload, old):
    """The producer names an Entity the glossary's forget did not remove."""
    key = next(k for k in payload["producers"] if k.startswith("forget_"))
    payload["producers"][key]["configuration"]["removed_entity_ids"] = [str(HELIOS)]


def no_configuration(payload, old):
    key = next(k for k in payload["producers"] if k.startswith("forget_"))
    payload["producers"][key]["configuration"] = {}


def another_key(payload, old):
    """The removal producer under a key that is not its canonical one."""
    key = next(k for k in payload["producers"] if k.startswith("forget_"))
    payload["producers"]["erased"] = payload["producers"].pop(key)
    payload["mention_resolutions"]["r01"]["producer_ref"] = "erased"


@pytest.mark.parametrize(
    "change, code",
    [
        (keep_v01, "erasure_incomplete"),
        (another_key, "erasure_configuration"),
        # Rule 5 refuses it first: r01 drops a foreign input under its old
        # producer.
        (keep_r01_accepted, "reconfirm_unattested"),
        (drop_an_unrelated_recipe, "erasure_unrelated"),
        (wrong_document, "erasure_unbound"),
        (claim_an_entity, "erasure_unbound"),
        (no_configuration, "erasure_configuration"),
    ],
)
def test_an_erasure_removal_is_complete_and_nothing_else(source_payload, change, code):
    assert erasure_case(source_payload, change) == code


def test_a_removal_is_bound_to_a_forgotten_source(source_payload):
    """A removal producer may only claim what the ledger shows a forget took:
    naming a document no forgotten row held is refused, however it is
    configured, and so is naming only part of what its forget removed,
    which would leave decisions citing the rest."""
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    revised, _ = removal(doc01, gloss)
    live = erasures_of([row_of(gloss), row_of(doc01)], doc01)
    assert dict(live.forgotten) == {}
    with pytest.raises(IntentError) as refused:
        admit(doc01, revised, TEXT, TEXT, identity_map(doc01), erasures=live)
    assert refused.value.code == "erasure_unbound"

    def bound(removed):
        tombstone = Tombstone.of(gloss, forgotten_at="t", removed_entity_ids=removed)
        forgotten = replace(
            row_of(gloss, "forgotten"), description=None, tombstone=tombstone
        )
        return erasures_of([forgotten, row_of(doc01)], doc01)

    assert dict(bound([HC]).forgotten) == {
        gloss.inputs["doc01"].data_id: frozenset({HC})
    }
    with pytest.raises(IntentError) as refused:
        admit(doc01, revised, TEXT, TEXT, identity_map(doc01), erasures=bound([HC]))
    assert refused.value.code == "erasure_unbound"
    admit(doc01, revised, TEXT, TEXT, identity_map(doc01), erasures=bound([]))


def with_removal_producer(source, gloss):
    """`source` with the removal producer of the forget of `gloss` added at
    its own revision, and nothing removed."""
    from cognee_lab.identity.erasure import removal_producer

    ids = source_ids(gloss)
    payload = json.loads(source.model_dump_json())
    payload["producers"][producer_key(ids.identity_data_id, source.revision)] = (
        removal_producer(ids, (), None, (), ())
    )
    return source_of(payload)


def test_an_erasure_retry_step_removes_something(source_payload):
    """A step that names the removal producer but cites nothing of the
    forgotten source removes nothing, and is not an erasure removal."""
    gloss = glossary(source_payload)
    saved = source_of(source_payload)
    with pytest.raises(IntentError) as refused:
        check_erasure_retry(
            saved,
            with_removal_producer(saved, gloss),
            forgot(gloss),
            saved.revision - 1,
        )
    assert refused.value.code == "erasure_empty"


def test_an_erasure_retry_step_keeps_the_identity_source(source_payload):
    gloss = glossary(source_payload)
    saved = reader_of(source_payload, gloss)
    revised, _ = removal(saved, gloss, state="failed", plan=REPLACING)
    moved = json.loads(revised.model_dump_json())
    moved["identity_data_id"] = str(uuid4())
    with pytest.raises(IntentError) as refused:
        check_erasure_retry(saved, source_of(moved), forgot(gloss), saved.revision - 1)
    assert refused.value.code == "erasure_unrelated"


def test_every_step_of_a_retry_chain_is_an_erasure_removal(source_payload):
    """Each step must be a removal in place of the one before, at the same
    revision; a replacement's own step is admission's, not the chain's."""
    gloss = glossary(source_payload)
    old = source_of(source_payload)
    saved = reader_of(source_payload, gloss)
    saved = source_of(dict(json.loads(saved.model_dump_json()), revision=2))
    revised, _ = removal(saved, gloss, state="failed", plan=REPLACING)
    check_retry_chain([saved, revised], forgot(gloss), 1)
    check_retry_chain([revised], forgot(gloss), 1)
    with pytest.raises(IntentError) as refused:
        check_retry_chain([old, saved], forgot(gloss), 1)
    assert refused.value.code == "revision_reuse"
    with pytest.raises(IntentError) as refused:
        check_retry_chain(
            [saved, revised, with_removal_producer(revised, gloss)], forgot(gloss), 1
        )
    assert refused.value.code == "revision_reuse"


def test_a_removal_never_drops_a_recipe_another_source_reads(source_payload):
    """HC goes with v01 only while nothing reads it. A source that reads it
    as a corpus input after the removal was computed makes admission refuse
    the drop, and the readers come from the rows, the dependent's own
    excluded."""
    gloss = glossary(source_payload)
    doc01 = reader_of(source_payload, gloss)
    revised, found = removal(doc01, gloss)
    assert found.dropped_entities == (str(HC),)
    third = json.loads(json.dumps(source_payload))
    third["identity_data_id"] = str(uuid4())
    third["inputs"]["doc01"]["data_id"] = str(uuid4())
    third["inputs"]["hc"] = dict(third["inputs"]["existing_A"], entity_id=str(HC))
    third["variant_assignments"]["v01"]["input_refs"].append("hc")
    rows = [row_of(doc01), row_of(source_of(third))]
    assert HC in erasures_of(rows, doc01).readers
    assert HC not in erasures_of([row_of(doc01)], doc01).readers
    with pytest.raises(IntentError) as refused:
        admit(
            doc01,
            revised,
            TEXT,
            TEXT,
            identity_map(doc01),
            erasures=forgot(gloss, readers=[HC]),
        )
    assert refused.value.code == "erasure_unrelated"


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


def test_a_scrubbed_plan_names_every_edge_the_contribution_check_reads():
    """The fixture's check after a forget reads the scrubbed plan, so it
    covers the same edges as the forget's own check: a shared identity edge
    whose contribution property the scrub drops stays covered."""
    plan = dict(
        identity_edges=[["m", "e", "is_a"]],
        edges=[
            dict(
                source="m2",
                target="e",
                relation="is_a",
                refs=["r"],
                properties={"identity_contributions": "[]"},
            )
        ],
    )
    assert contribution_triples(scrubbed_plan(plan)) == contribution_triples(plan)
    assert ("m2", "e", "is_a") in contribution_triples(scrubbed_plan(plan))


async def failed_replacement_of(store, source):
    """`source` published, then its next revision failed as a replacement."""
    attempt = await store.begin(source, expected_revision=0, plan=dict(PUBLISHING))
    await store.complete(source, attempt)
    saved = source.model_copy(update={"revision": 2})
    plan = dict(REPLACING, previous_description=source.model_dump_json())
    attempt = await store.begin(saved, expected_revision=1, plan=plan, method="replace")
    await store.fail(saved, attempt, "replace_saved", IntentError("x", "x"))
    return saved, await store.row(saved)


async def test_the_ledger_begins_an_erasure_retry_only_with_the_removal(
    source_payload,
):
    """Under the writer reservation, the store checks the chain an erasure
    retry names against the forgotten rows it reads: a changed description
    that removes nothing is refused, the removal is begun."""
    from test_identity_storage import memory_store

    store = memory_store()
    await store.initialize()
    gloss = glossary(source_payload)
    attempt = await store.begin(gloss, expected_revision=0, plan=dict(PUBLISHING))
    await store.complete(gloss, attempt)
    attempt = await store.begin(
        gloss, expected_revision=1, plan=dict(FORGETTING), method="forget"
    )
    await store.complete(
        gloss,
        attempt,
        state="forgotten",
        tombstone=Tombstone.of(gloss, forgotten_at="t"),
    )
    saved, row = await failed_replacement_of(store, reader_of(source_payload, gloss))
    retry = dict(row.plan, erased_from=[saved.model_dump_json()])
    smuggled = json.loads(saved.model_dump_json())
    for recipe in smuggled["entity_constructions"].values():
        recipe["description"] = "smuggled"
    with pytest.raises(IntentError) as refused:
        await store.begin(
            source_of(smuggled), expected_revision=2, plan=dict(retry), method="replace"
        )
    assert refused.value.code == "revision_reuse"
    revised, _ = removal(saved, gloss, state="failed", plan=REPLACING)
    await store.begin(revised, expected_revision=2, plan=dict(retry), method="replace")
    now = await store.row(saved)
    assert (now.state, now.description) == ("pending", revised)
