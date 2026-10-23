"""Dependencies: a decision that read another document is withheld, not the
source, when what it read changes."""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.validation import (
    IntentError,
    text_digest,
    validate_inputs,
    withheld_by,
)

GLOSSARY = (
    "Glossary\n"
    "HC: Helios controller, the plasma heating regulator.\n"
    "RF: radio frequency.\n"
)
ENTRY = "HC: Helios controller, the plasma heating regulator."
GLOSSARY_ID = str(uuid5(NAMESPACE_URL, "test:glossary"))
TEXT = (Path(__file__).parent / "fixtures/identity/source.txt").read_text()


def citing(payload, glossary=GLOSSARY, *, cite_text=False):
    """doc01 whose r01 and v01 read the glossary's HC entry as a span."""
    payload = json.loads(json.dumps(payload))
    start = glossary.index(ENTRY)
    payload["inputs"]["glossary"] = dict(
        kind="source_text",
        dataset_id=payload["dataset_id"],
        data_id=GLOSSARY_ID,
        text_sha256=text_digest(glossary),
    )
    payload["inputs"]["glossary_hc"] = dict(
        kind="text_span",
        document_ref="glossary",
        start=start,
        end=start + len(ENTRY),
        text_sha256=text_digest(ENTRY),
    )
    for key in ("r01", "v01"):
        record = payload["mention_resolutions"].get(key) or (
            payload["variant_assignments"][key]
        )
        record["input_refs"] = ["doc01", "glossary_hc"]
    if cite_text:
        payload["mention_resolutions"]["r01"]["input_refs"].append("glossary")
    return IdentitySource.model_validate_json(json.dumps(payload))


class Graph:
    def __init__(self, nodes=None):
        self.nodes = nodes or {}

    async def get_node(self, key):
        return self.nodes.get(key)


def own_chunks(source):
    item = source.inputs["chunk01"]
    return {
        str(item.chunk_id): SimpleNamespace(
            id=item.chunk_id,
            chunk_index=0,
            text=TEXT,
            is_part_of=SimpleNamespace(id=source.inputs["doc01"].data_id),
        )
    }


async def drift_of(source, glossary, **options):
    texts = {"doc01": TEXT}
    if glossary is not None:
        texts["glossary"] = glossary
    return await validate_inputs(
        source, texts=texts, chunks=own_chunks(source), graph=Graph(), **options
    )


def strip_corpus(payload):
    payload = json.loads(json.dumps(payload))
    payload["inputs"].pop("existing_A")
    for record in [
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["input_refs"] = ["doc01"]
    return payload


async def test_an_unchanged_span_validates_wherever_the_glossary_changed(
    source_payload,
):
    source = citing(strip_corpus(source_payload))
    assert await drift_of(source, GLOSSARY) == {}
    # A change elsewhere changes the glossary digest. A text reached only as
    # a span's document is not digest-checked, so the span still validates.
    elsewhere = GLOSSARY.replace("radio frequency", "radio-frequency heating")
    assert await drift_of(source, elsewhere) == {}


async def test_a_moved_or_changed_span_withholds_each_decision_citing_it(
    source_payload,
):
    source = citing(strip_corpus(source_payload))
    for edited in (
        GLOSSARY.replace("HC:", "ECRH: electron cyclotron heating.\nHC:"),
        GLOSSARY.replace("plasma heating", "plasma-heating"),
    ):
        drift = await drift_of(source, edited)
        assert drift == {"glossary_hc": "input_changed"}
        assert withheld_by(source, drift) == {
            "r01": "input_changed",
            "v01": "input_changed",
        }


async def test_a_glossary_that_is_gone_is_an_input_removed(source_payload):
    source = citing(strip_corpus(source_payload))
    drift = await drift_of(source, None)
    assert drift == {"glossary_hc": "input_removed"}
    assert set(withheld_by(source, drift).values()) == {"input_removed"}


async def test_a_directly_cited_text_is_digest_checked(source_payload):
    source = citing(strip_corpus(source_payload), cite_text=True)
    elsewhere = GLOSSARY.replace("radio frequency", "radio-frequency heating")
    drift = await drift_of(source, elsewhere)
    assert drift == {"glossary": "input_changed"}
    assert withheld_by(source, drift) == {"r01": "input_changed"}


async def test_inputs_of_withheld_decisions_are_not_checked(source_payload):
    source = citing(strip_corpus(source_payload))
    changed = GLOSSARY.replace("plasma heating", "plasma-heating")
    assert await drift_of(source, changed, withheld={"r01"}) == {
        "glossary_hc": "input_changed"
    }
    assert await drift_of(source, changed, withheld={"r01", "v01"}) == {}


async def test_an_own_input_still_fails_the_source(source_payload):
    source = citing(strip_corpus(source_payload))
    with pytest.raises(IntentError) as refused:
        await validate_inputs(
            source,
            texts={"doc01": TEXT + "x", "glossary": GLOSSARY},
            chunks=own_chunks(source),
            graph=Graph(),
        )
    assert refused.value.code == "source_changed"


# The withholding table and the withheld-decision set.

from dataclasses import replace as replaced  # noqa: E402
from uuid import uuid4  # noqa: E402

from cognee_lab.identity.storage import PublicationRow  # noqa: E402
from cognee_lab.identity.withholding import (  # noqa: E402
    WithholdingStore,
    classify,
    withheld_decisions,
    withhold_dependents,
)

INSERTED = GLOSSARY.replace("HC:", "ECRH: electron cyclotron heating.\nHC:")
COSMETIC = GLOSSARY.replace("plasma heating", "plasma-heating")
ELSEWHERE = GLOSSARY.replace("radio frequency", "radio-frequency heating")


def glossary_source(payload):
    """The glossary as an identity source with no groups or decisions."""
    payload = json.loads(json.dumps(payload))
    payload["identity_data_id"] = str(uuid5(NAMESPACE_URL, "test:glossary:identity"))
    payload["original_input_ref"] = "glossary"
    payload["inputs"] = {
        "glossary": dict(
            kind="source_text",
            dataset_id=payload["dataset_id"],
            data_id=GLOSSARY_ID,
            text_sha256=text_digest(GLOSSARY),
        )
    }
    for key in ("entity_constructions", "mention_groups"):
        payload[key] = {}
    payload["mention_resolutions"], payload["variant_assignments"] = {}, {}
    return IdentitySource.model_validate_json(json.dumps(payload))


def row_of(source, state="current", plan=None):
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        revision=source.revision,
        verified_revision=source.revision if state == "current" else 0,
        state=state,
        attempt=str(uuid4()),
        description=source.model_dump_json(),
        plan=plan or {},
    )


def memory_publisher(rows):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    class Records:
        session_factory = factory

        async def rows(self, dataset=None):
            return list(rows)

    publisher = SimpleNamespace(records=Records())
    publisher.withholdings = WithholdingStore(factory)
    return publisher


def test_each_glossary_edit_is_classified_as_the_user_decided(source_payload):
    source = citing(strip_corpus(source_payload))
    entry = GLOSSARY.index(ENTRY)
    outcomes = {
        name: [
            (c.input_ref, c.outcome, c.new_range)
            for c in classify(source, GLOSSARY_ID, GLOSSARY, edited)
        ]
        for name, edited in [
            ("elsewhere", ELSEWHERE),
            ("inserted", INSERTED),
            ("cosmetic", COSMETIC),
        ]
    }
    shift = len("ECRH: electron cyclotron heating.\n")
    assert outcomes == {
        "elsewhere": [("glossary_hc", "unchanged", None)],
        "inserted": [
            ("glossary_hc", "moved", (entry + shift, entry + shift + len(ENTRY)))
        ],
        "cosmetic": [("glossary_hc", "changed", None)],
    }
    # A span whose text now appears twice needs review, not a guess.
    doubled = INSERTED.replace("RF:", ENTRY + "\nRF:")
    assert [c.outcome for c in classify(source, GLOSSARY_ID, GLOSSARY, doubled)] == [
        "changed"
    ]
    # A directly cited text is classified too; any change needs review.
    direct = citing(strip_corpus(source_payload), cite_text=True)
    assert [
        (c.input_ref, c.outcome)
        for c in classify(direct, GLOSSARY_ID, GLOSSARY, ELSEWHERE)
    ] == [("glossary", "changed"), ("glossary_hc", "unchanged")]


async def test_the_edit_writes_rows_per_decision_and_a_retry_converges(
    source_payload,
):
    glossary = glossary_source(source_payload)
    doc01 = citing(strip_corpus(source_payload))
    publisher = memory_publisher([row_of(glossary), row_of(doc01)])
    written = await withhold_dependents(publisher, glossary, GLOSSARY, COSMETIC, 2)
    assert [(w["assignment"], w["status"], w["reason"]) for w in written] == [
        ("r01", "refresh_needed", "input_changed"),
        ("v01", "refresh_needed", "input_changed"),
    ]
    assert written[0]["old_digest"] == text_digest(ENTRY)
    again = await withhold_dependents(publisher, glossary, GLOSSARY, COSMETIC, 2)
    assert again == written and len(await publisher.withholdings.rows()) == 2
    moved = await withhold_dependents(publisher, glossary, GLOSSARY, INSERTED, 2)
    assert {w["status"] for w in moved} == {"remap"}
    assert len(await publisher.withholdings.rows()) == 2
    # An edit that leaves the span in place clears its rows.
    assert await withhold_dependents(publisher, glossary, GLOSSARY, GLOSSARY, 3) == []
    assert await publisher.withholdings.rows() == []


async def test_an_unfinished_edit_withholds_every_decision_citing_the_document(
    source_payload,
):
    glossary = glossary_source(source_payload)
    doc01 = citing(strip_corpus(source_payload))
    rows = [row_of(glossary), row_of(doc01)]
    publisher = memory_publisher(rows)
    assert await withheld_decisions(rows, publisher.withholdings) == {}
    for state in ("pending", "failed"):
        editing = row_of(
            glossary,
            state,
            dict(operation="identity_replace", text_change={"text": "x"}),
        )
        held = await withheld_decisions([editing, rows[1]], publisher.withholdings)
        assert held == {
            str(doc01.identity_data_id): {
                "r01": ("input_changed", "edit_unfinished"),
                "v01": ("input_changed", "edit_unfinished"),
            }
        }
    # A failed replacement with unchanged text changes no input.
    unchanged = row_of(glossary, "failed", dict(operation="identity_replace"))
    assert await withheld_decisions([unchanged, rows[1]], publisher.withholdings) == {}


async def test_rows_apply_only_while_the_decision_still_cites_the_input(
    source_payload,
):
    glossary = glossary_source(source_payload)
    doc01 = citing(strip_corpus(source_payload))
    rows = [row_of(glossary), row_of(doc01)]
    publisher = memory_publisher(rows)
    await withhold_dependents(publisher, glossary, GLOSSARY, COSMETIC, 2)
    held = await withheld_decisions(rows, publisher.withholdings)
    assert set(held[str(doc01.identity_data_id)]) == {"r01", "v01"}
    payload = doc01.model_dump(mode="json")
    payload["variant_assignments"]["v01"]["input_refs"] = ["doc01"]
    revised = IdentitySource.model_validate_json(json.dumps(payload))
    held = await withheld_decisions([rows[0], row_of(revised)], publisher.withholdings)
    assert set(held[str(doc01.identity_data_id)]) == {"r01"}
    retired = replaced(rows[1], state="withdrawn")
    assert await withheld_decisions([rows[0], retired], publisher.withholdings) == {}


# The glossary fixture's revisions of doc01, through the one admission.

from cognee_lab.identity.admission import admit, identity_map  # noqa: E402
from cognee_lab.identity.glossary_fixture import (  # noqa: E402
    CASES,
    GLOSSARY_TEXT,
    glossary_inputs,
    hc_entry,
    replaced_variant,
)
from cognee_lab.identity.withholding import (  # noqa: E402
    WithholdingRow,
    reconfirmed,
    remapped,
)


def glossary_doc01(payload):
    payload = json.loads(json.dumps(payload))
    glossary_inputs(payload, GLOSSARY_TEXT)
    return IdentitySource.model_validate_json(json.dumps(payload))


def admit_same_text(old, new):
    return admit(old, new, TEXT, TEXT, identity_map(old))


def span_for(text):
    entry = hc_entry(text)
    return dict(
        kind="text_span",
        document_ref="glossary",
        start=entry.start(),
        end=entry.end(),
        text_sha256=text_digest(entry.group()),
    )


def producer(name):
    return dict(
        method="captured_fixture",
        implementation=name,
        version="0.1",
        configuration={"confirmed_by": "test"},
        run_id=None,
    )


def test_the_glossary_cases_edit_the_text_as_the_guide_says():
    inserted = CASES["insert"](GLOSSARY_TEXT)
    assert hc_entry(inserted).group() == hc_entry(GLOSSARY_TEXT).group()
    assert hc_entry(inserted).start() > hc_entry(GLOSSARY_TEXT).start()
    assert hc_entry(CASES["elsewhere"](GLOSSARY_TEXT)).span() == (
        hc_entry(GLOSSARY_TEXT).span()
    )
    assert "plasma-heating" in hc_entry(CASES["cosmetic"](GLOSSARY_TEXT)).group()
    assert hc_entry(CASES["substantive"](GLOSSARY_TEXT)).group() == (
        "HC: hybrid coil, the auxiliary magnet winding."
    )
    with pytest.raises(IntentError):
        CASES["cosmetic"](CASES["substantive"](GLOSSARY_TEXT))


def test_a_refresh_moves_the_span_and_changes_no_decision(source_payload):
    old = glossary_doc01(source_payload)
    inserted = CASES["insert"](GLOSSARY_TEXT)
    start, end = hc_entry(inserted).span()
    moved = [
        WithholdingRow(
            str(old.dataset_id),
            str(old.identity_data_id),
            key,
            "glossary_hc",
            "g",
            2,
            "input_changed",
            "remap",
            None,
            None,
            start,
            end,
        )
        for key in ("r01", "v01")
    ]
    new = remapped(old, moved)
    assert (new.inputs["glossary_hc"].start, new.inputs["glossary_hc"].end) == (
        start,
        end,
    )
    assert new.mention_resolutions == old.mention_resolutions
    assert new.variant_assignments == old.variant_assignments
    # The glossary text input keeps its old digest: only a span may move.
    assert new.inputs["glossary"] == old.inputs["glossary"]
    assert admit_same_text(old, new).retired == frozenset()


def test_a_reconfirm_is_copy_on_write_under_a_new_producer(source_payload):
    old = glossary_doc01(source_payload)
    span = span_for(CASES["cosmetic"](GLOSSARY_TEXT))
    first = reconfirmed(
        old,
        "r01",
        {"glossary_hc": ("glossary_hc_r2", span)},
        "review_r01_r2",
        producer("re-confirmed"),
    )
    assert first.mention_resolutions["r01"].input_refs[-1] == "glossary_hc_r2"
    assert first.variant_assignments["v01"].input_refs[-1] == "glossary_hc"
    assert {"glossary_hc", "glossary_hc_r2"} <= set(first.inputs)
    admit_same_text(old, first)
    second = reconfirmed(
        first,
        "v01",
        {"glossary_hc": ("glossary_hc_r3", span)},
        "review_v01_r3",
        producer("re-confirmed"),
    )
    assert "glossary_hc" not in second.inputs
    admit_same_text(first, second)
    # Pointing at the new input under the old producer is not a re-confirm.
    payload = first.model_dump(mode="json")
    payload["mention_resolutions"]["r01"]["producer_ref"] = "fixture"
    payload["producers"].pop("review_r01_r2")
    unattested = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError) as refused:
        admit_same_text(old, unattested)
    assert refused.value.code == "reconfirm_unattested"


def test_a_substantive_change_replaces_v01_with_a_derived_variant(source_payload):
    old = glossary_doc01(source_payload)
    span = span_for(CASES["substantive"](GLOSSARY_TEXT))
    new = replaced_variant(
        old, "v01", "glossary_hc_r2", span, "review_v01_r2", producer("replaced")
    )
    assert set(new.variant_assignments) == {"v02"}
    coil = new.variant_assignments["v02"].target_entity_id
    assert new.entity_constructions[coil].name == "Hybrid coil"
    assert new.mention_resolutions["r01"].input_refs[-1] == "glossary_hc"
    admit_same_text(old, new)


# Admission keeps corpus object existence as a hard rule.


def admitting_publisher(nodes):
    from cognee_lab.identity.publish import Publisher

    records = memory_publisher([]).records

    async def row(_):
        return None

    records.row = row
    return Publisher(Graph(nodes), None, records)


async def test_admission_refuses_a_corpus_input_whose_entity_is_missing(
    source_payload,
):
    """Retrieval withholds a decision whose Entity is gone, but admission
    still refuses one: the derived-UUID rule trusts that a listed corpus input
    names an Entity that exists, not one this revision constructs."""
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    entity = source.inputs["existing_A"].entity_id
    texts = {"doc01": TEXT}
    with pytest.raises(IntentError) as refused:
        await admitting_publisher({}).admit_inputs(source, texts, own_chunks(source))
    assert refused.value.code == "missing_reasoning_input"
    # A changed field still only withholds the decisions that read it.
    changed = {str(entity): dict(type="Entity", name="Changed", description="Changed")}
    await admitting_publisher(changed).admit_inputs(source, texts, own_chunks(source))


async def test_a_retried_second_edit_classifies_as_its_first_attempt_did(
    source_payload,
):
    """The first edit moved the span and no refresh ran, so doc01 still holds
    the revision-1 range. The second edit's retry must find the move again,
    not slice the previous text with a range taken from the new text."""
    glossary = glossary_source(source_payload)
    doc01 = citing(strip_corpus(source_payload))
    publisher = memory_publisher([row_of(glossary), row_of(doc01)])
    await withhold_dependents(publisher, glossary, GLOSSARY, INSERTED, 2)
    twice = "Preface.\n" + INSERTED
    first = await withhold_dependents(publisher, glossary, INSERTED, twice, 3)
    retry = await withhold_dependents(publisher, glossary, INSERTED, twice, 3)
    start = twice.index(ENTRY)
    assert [(w["status"], w["new_start"], w["new_end"]) for w in first] == [
        ("remap", start, start + len(ENTRY))
    ] * 2
    assert retry == first
