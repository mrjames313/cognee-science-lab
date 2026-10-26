"""Captured chain: doc03 cites doc01's decisions as saved records.

`glossary-fixture --chain` adds doc03 to the glossary root, a third source
with its own text. Its resolution c01 (group g31, "The regulator", to the
Helios controller) cites doc01's r01, and its HC variant c02 cites doc01's
v01. The glossary's HC entry, doc01's decisions and doc03's decisions make
three levels. An edit of the entry withholds r01 and v01 for review and,
down the chain, c01 and c02 (`upstream_withheld`). A re-confirm upstream
keeps r01's and v01's fingerprints, so it releases c01 and c02 with no
doc03 revision; a replacement upstream changes the record c01 or c02
cites, so doc03 needs its own review. `cite-record` tries one citation
that admission refuses. The review decisions are captured fixture input,
not Describe.
"""

import json
from uuid import NAMESPACE_URL, UUID, uuid5

from .environment import DATASET_NAME
from .digests import object_digest
from .fixture import expect_current
from .models import IdentitySource
from .forget_fixture import write_revision
from .records import citation, current_record
from .revisions import next_revision, replace_one
from .validation import IntentError, fresh_mention_id, text_digest

DOC03_TEXT = "Operations log\n\nThe regulator kept HC stable during the run.\n"
DOC03_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:doc03:original")
DOC03_IDENTITY_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:doc03:identity")
MENTION = "The regulator"
HELIOS = "8b4bff50-907b-56b6-bc80-3b0a7018714a"
HC = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
DOC03_REVIEW = "stage6-captured-chain-review"
# Each `cite-record --citation` case: the source that cites, and how its
# next revision cites. Admission refuses each one but `entity`.
ENTITY_READS = ("entity", "mention")
CITATIONS = ("cycle", "self", "missing", "stale", "digest", *ENTITY_READS)


def entity_read(doc01, case) -> dict:
    """A corpus input of an Entity of doc01's: the HC Entity (`entity`),
    which doc03 then reads as doc01's alone, or doc01's g01 mention
    (`mention`), which admission refuses (`mention_input`)."""
    if case == "entity":
        entity_id = HC
        fields = doc01.entity_constructions[UUID(HC)].model_dump()
    else:
        entity_id = str(doc01.mention_groups["g01"].entity_id)
        fields = dict(name=doc01.entity_constructions[UUID(entity_id)].name)
    return dict(
        kind="corpus_object",
        dataset_id=str(doc01.dataset_id),
        entity_id=entity_id,
        selected_fields=sorted(fields),
        content_sha256=object_digest(fields),
    )


def producer(policy, implementation="stage6-captured-chain"):
    return dict(
        method="captured_fixture",
        implementation=implementation,
        version="0.1",
        configuration={"policy": policy},
        run_id=None,
    )


def describe_doc03(doc01: IdentitySource, chunks) -> IdentitySource:
    """doc03's revision 1: c01 cites doc01's r01 and c02 cites doc01's v01,
    each as doc01's revision is now."""
    from .captured_chunks import bind_chunks

    dataset = str(doc01.dataset_id)
    mention = str(fresh_mention_id(DOC03_IDENTITY_ID, 1, "g31"))
    start = DOC03_TEXT.index(MENTION)
    recipes = {str(k): v.model_dump() for k, v in doc01.entity_constructions.items()}
    payload = dict(
        kind="cognee_identity_source",
        schema_version="0.1-draft",
        dataset_id=dataset,
        identity_data_id=str(DOC03_IDENTITY_ID),
        revision=1,
        original_input_ref="doc03",
        inputs=dict(
            doc03=dict(
                kind="source_text",
                dataset_id=dataset,
                data_id=str(DOC03_DATA_ID),
                text_sha256=text_digest(DOC03_TEXT),
            ),
            doc01_r01=citation(doc01, "r01"),
            doc01_v01=citation(doc01, "v01"),
        ),
        producers=dict(fixture=producer("decisions-citing-doc01-v1")),
        entity_constructions={
            mention: dict(name=MENTION, description="doc03 local mention."),
            HELIOS: recipes[HELIOS],
            HC: recipes[HC],
        },
        mention_groups=dict(
            g31=dict(
                entity_id=mention,
                document_ref="doc03",
                occurrences=[dict(start=start, end=start + len(MENTION), text=MENTION)],
                chunk_refs=["placeholder"],
                input_refs=["doc03"],
                producer_ref="fixture",
            )
        ),
        mention_resolutions=dict(
            c01=dict(
                group_ref="g31",
                status="accepted",
                target_entity_id=HELIOS,
                input_refs=["doc03", "doc01_r01"],
                producer_ref="fixture",
            )
        ),
        variant_assignments=dict(
            c02=dict(
                status="accepted",
                source_entity_id=HC,
                target_entity_id=HELIOS,
                applicability=dict(kind="document", document_ref="doc03"),
                input_refs=["doc03", "doc01_v01"],
                producer_ref="fixture",
            )
        ),
    )
    bind_chunks(payload, DOC03_TEXT, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def add_doc03(root, doc01):
    """Register doc03's text and its description through the lab's `add`;
    return the description."""
    from . import entry

    original = entry.Original(root / "doc03.txt", DOC03_DATA_ID)
    original.path.write_text(DOC03_TEXT)
    return await entry.add(
        DATASET_NAME,
        original,
        describe=lambda draft: describe_doc03(doc01, draft.chunks),
        identity_path=root / "doc03_identity.json",
    )


async def cite(publisher, root, args, sources):
    """`cite-record`: the next revision of the selected source with one
    new citation (`citing_revision`), which admission refuses."""
    if "doc03" not in sources:
        raise IntentError(
            "fixture_scope", "cite-record needs a glossary-fixture --chain root"
        )
    selected = sources[args.source]
    await expect_current(
        publisher,
        selected,
        args.expected_revision,
        "Reconcile the source before it cites a record",
    )
    intended = citing_revision(
        selected, args.citation, sources, await publisher.records.rows()
    )
    write_revision(root, args.source, intended)
    await replace_one(
        publisher,
        intended,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )


def citing_revision(source, case, sources, rows):
    """The next revision of the citing source for one refused `cite-record`
    case, under a producer new in that revision."""
    doc01, doc03 = sources["doc01"], sources["doc03"]
    revision = source.revision + 1
    key = f"chain_{case}_r{revision}"
    if case == "cycle":
        # doc03 cites doc01, so doc01 citing doc03 closes a cycle.
        decision, item = "v01", citation(doc03, "c02")
    elif case in ENTITY_READS:
        decision, item = "c01", entity_read(doc01, case)
    elif case == "self":
        decision, item = "c01", citation(doc03, "c02")
    else:
        decision, item = "c01", current_record(rows, str(doc01.identity_data_id), "r01")
        if case == "missing":
            item["record_id"] = "r99"
        elif case == "stale":
            item["representation_revision"] += 1
        elif case == "digest":
            item["content_sha256"] = text_digest("not the record")
    if (case == "cycle") != (source.identity_data_id == doc01.identity_data_id):
        raise IntentError(
            "fixture_scope",
            "cite-record --citation cycle cites from doc01; the others from doc03",
        )

    def change(payload):
        record = payload["mention_resolutions"].get(decision) or (
            payload["variant_assignments"][decision]
        )
        if case == "entity":
            # doc03 stops declaring HC, so doc01 alone owns the HC it reads.
            payload["variant_assignments"].pop("c02")
            payload["entity_constructions"].pop(HC)
        payload["inputs"][key] = item
        payload["producers"][f"review_{decision}_r{revision}"] = producer(
            DOC03_REVIEW, "cited"
        )
        record["input_refs"] = [*record["input_refs"], key]
        record["producer_ref"] = f"review_{decision}_r{revision}"

    return next_revision(source, change)
