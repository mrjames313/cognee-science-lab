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
from uuid import NAMESPACE_URL, uuid5

from .models import IdentitySource
from .records import citation, saved_records
from .validation import IntentError, fresh_mention_id, text_digest

DOC03_TEXT = "Operations log\n\nThe regulator kept HC stable during the run.\n"
DOC03_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:doc03:original")
DOC03_IDENTITY_ID = uuid5(NAMESPACE_URL, "cognee-lab:stage6:doc03:identity")
MENTION = "The regulator"
HELIOS = "8b4bff50-907b-56b6-bc80-3b0a7018714a"
HC = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
DOC03_REVIEW = "stage6-captured-chain-review"
# Each `cite-record --citation` case: the source that cites, and how its
# next revision cites. Admission refuses each one.
CITATIONS = ("cycle", "self", "missing", "stale", "digest")


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


async def prepare_doc03(root, doc01):
    """Register doc03's text, chunks and description; return them with its
    context."""
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points

    from .fixture import context_for, load_chunks

    (root / "doc03.txt").write_text(DOC03_TEXT)
    await cognee.add(
        DataItem(data=str(root / "doc03.txt"), data_id=DOC03_DATA_ID),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    ctx = await context_for(DOC03_DATA_ID)
    chunks = await load_chunks(None, ctx, budget=512)
    await add_data_points(chunks, ctx=ctx)
    doc03 = describe_doc03(doc01, chunks)
    (root / "doc03_identity.json").write_text(doc03.model_dump_json(indent=2) + "\n")
    await cognee.add(
        DataItem(data=str(root / "doc03_identity.json"), data_id=DOC03_IDENTITY_ID),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    return doc03, chunks, ctx


def cited_now(rows, source) -> dict[str, IdentitySource]:
    """The current description of each source `source` cites, by identity."""
    wanted = {str(i.identity_data_id) for i in saved_records(source).values()}
    return {r.source: r.description for r in rows if r.source in wanted}


def recited(source, entry, rows, revision):
    """A re-confirm of a decision withheld by saved-record drift: each
    withholding citation again, under a new key, as the cited record is
    now. Returns the replacements (old key to new key and input) and what
    the producer records."""
    current = cited_now(rows, source)
    replacements, old_digests, new_digests = {}, {}, {}
    for key in sorted(entry.inputs):
        item = source.inputs[key]
        upstream = current.get(str(item.identity_data_id))
        if upstream is None:
            raise IntentError("input_removed", f"The cited source is gone: {key}")
        new_key = f"{key}_r{revision}"
        replacements[key] = (new_key, citation(upstream, item.record_id))
        old_digests[key] = item.content_sha256
        new_digests[new_key] = replacements[key][1]["content_sha256"]
    return replacements, dict(old_digests=old_digests, new_digests=new_digests)


def unresolved_in_place(doc01, decision, old_key, span_key, span, key, review):
    """r01 resolved g01 to the Helios controller. The glossary entry it
    read changed, and the reviewer now leaves g01 unresolved: r01 keeps its
    key and changes in place, so its fingerprint changes."""
    from .revisions import next_revision

    if decision != "r01" or decision not in doc01.mention_resolutions:
        raise IntentError("fixture_scope", "Only r01 has an in-place replacement")

    def change(payload):
        old = payload["mention_resolutions"]["r01"]
        payload["inputs"][span_key] = span
        payload["producers"][key] = review
        payload["mention_resolutions"]["r01"] = dict(
            group_ref=old["group_ref"],
            status="unresolved",
            input_refs=[span_key if k == old_key else k for k in old["input_refs"]],
            producer_ref=key,
            explanation="The glossary entry for HC changed; g01 is left unresolved.",
        )

    return next_revision(doc01, change)


def citing_revision(source, case, sources, rows):
    """The next revision of the citing source for one refused `cite-record`
    case, under a producer new in that revision."""
    from .revisions import next_revision

    doc01, doc03 = sources["doc01"], sources["doc03"]
    revision = source.revision + 1
    key = f"chain_{case}_r{revision}"
    if case == "cycle":
        # doc03 cites doc01, so doc01 citing doc03 closes a cycle.
        decision, item = "v01", citation(doc03, "c02")
    elif case == "self":
        decision, item = "c01", citation(doc03, "c02")
    else:
        current = cited_now(rows, doc03)[str(doc01.identity_data_id)]
        decision, item = "c01", citation(current, "r01")
        if case == "missing":
            item["record_id"] = "r99"
        elif case == "stale":
            item["representation_revision"] = current.revision + 1
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
        payload["inputs"][key] = item
        payload["producers"][f"review_{decision}_r{revision}"] = producer(
            DOC03_REVIEW, "cited"
        )
        record["input_refs"] = [*record["input_refs"], key]
        record["producer_ref"] = f"review_{decision}_r{revision}"

    return next_revision(source, change)
