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
