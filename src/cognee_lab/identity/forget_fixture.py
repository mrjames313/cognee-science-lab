"""The fixtures' side of forget: the dependent variant, the commands both
drivers share, the re-add from the caller's files and the report of what
remains."""

import json
from uuid import UUID

from .models import IdentitySource
from .validation import IntentError, text_digest

# The root files that hold each source's own inputs: the caller's, which a
# forget lists and never deletes. Revision files follow the fixture's names.
CALLER_FILES = {
    "doc01": ("source.txt", "identity.json", "identity_doc01_revision*.json"),
    "doc02": ("source02.txt", "identity02.json", "identity_doc02_revision*.json"),
    "glossary": (
        "glossary.txt",
        "glossary_identity.json",
        "glossary_revision*.txt",
        "glossary_identity_revision*.json",
    ),
}
RESULT_FILES = ("*_result.json", "result.json")


def add_dependency(payload, first, text):
    """doc02 consumed doc01: its r01 decision lists doc01's text and doc01's
    private singleton as inputs, so forgetting doc01 removes that decision."""
    from .multisource import fixture_id
    from .validation import object_digest

    doc = first.inputs[first.original_input_ref]
    singleton = fixture_id("doc01:singleton")
    recipe = first.entity_constructions[UUID(singleton)]
    payload["inputs"]["doc01_text"] = dict(
        kind="source_text",
        dataset_id=str(doc.dataset_id),
        data_id=str(doc.data_id),
        text_sha256=doc.text_sha256,
    )
    payload["inputs"]["doc01_instrument"] = dict(
        kind="corpus_object",
        dataset_id=str(first.dataset_id),
        entity_id=singleton,
        selected_fields=["name", "description"],
        content_sha256=object_digest(
            dict(name=recipe.name, description=recipe.description)
        ),
    )
    payload["mention_resolutions"]["r01"]["input_refs"] += [
        "doc01_text",
        "doc01_instrument",
    ]


def caller_files(root, label):
    """The caller's own files for one source in the root, and the result
    files the commands wrote there."""
    patterns = (*CALLER_FILES.get(label, ()), *RESULT_FILES)
    return sorted({p for pattern in patterns for p in root.glob(pattern)})


async def forget_command(publisher, root, args, label, selected):
    """`forget`, with `--dry-run` or `--confirm`, on either driver. A dry run
    returns its report and writes nothing; a forget returns the outcome of
    its dependents' removal revisions beside the completed forget."""
    from .forget import forget, preview

    row = await publisher.records.row(selected)
    files = caller_files(root, label)
    if args.dry_run:
        return await preview(
            publisher,
            selected,
            expected_revision=args.expected_revision,
            caller_files=files,
        )
    outcome = await forget(
        publisher,
        selected,
        expected_revision=args.expected_revision,
        confirm=args.confirm,
        caller_files=files,
        origin="test/fault_injection" if args.fault_stage else "test",
        fault_stage=args.fault_stage,
    )
    return dict(forget_outcome(outcome, row), caller_files=[str(f) for f in files])


def forget_outcome(outcome, row):
    """What a command reports of a forget: its dependents' removal revisions,
    and the failure that stopped them, if any."""
    return dict(
        forget=dict(
            identity_data_id=row.source if row else None,
            attempt_id=outcome["attempt_id"],
            dependents_revised=outcome["dependents_revised"],
            dependents_waiting=outcome["dependents_waiting"],
        ),
        dependents_failed=outcome["dependents_failed"],
    )


async def reconcile_forget(publisher, row, selected):
    """`reconcile` of a source whose forget failed, or of a forgotten source
    whose dependents are not all revised: finish it. None for any other row."""
    if row.resumed_by != "forget" and row.state != "forgotten":
        return None
    outcome = await publisher.forget(
        selected, expected_revision=row.revision, origin="test"
    )
    return forget_outcome(outcome, row)


def describe_readd(caller, tombstone, removed, text, chunks):
    """The caller's description as a fresh publication at the next revision.
    Every group is fresh, so its Entity UUID derives from the new revision
    and its key. A reusable Entity the forget removed is replaced: under the
    UUID derived from the first key of a resolution or variant that names it
    and that no other replacement took, or, when nothing names it, under the
    UUID derived from the removed one."""
    from .erasure_rules import replacement_entity_id
    from .validation import naming_keys
    from .captured_chunks import bind_chunks
    from .validation import fresh_entity_id, fresh_mention_id

    payload = caller.model_dump(mode="json")
    revision = payload["revision"] = tombstone.revision + 1
    identity = caller.identity_data_id
    renamed = {}
    for key, group in payload["mention_groups"].items():
        renamed[group["entity_id"]] = str(fresh_mention_id(identity, revision, key))
    for old in sorted(str(e) for e in removed):
        if old not in payload["entity_constructions"] or old in renamed:
            continue
        keys = sorted(naming_keys(caller, UUID(old)))
        if not keys:
            renamed[old] = str(replacement_entity_id(identity, revision, UUID(old)))
            continue
        derived = (str(fresh_entity_id(identity, revision, k)) for k in keys)
        free = [u for u in derived if u not in renamed.values()]
        if not free:
            raise IntentError(
                "entity_uuid_not_derived",
                "Every key that names a removed Entity already names another replacement",
            )
        renamed[old] = free[0]
    payload["entity_constructions"] = {
        renamed.get(eid, eid): recipe
        for eid, recipe in payload["entity_constructions"].items()
    }
    for group in payload["mention_groups"].values():
        group["entity_id"] = renamed[group["entity_id"]]
    for decision in payload["mention_resolutions"].values():
        target = decision.get("target_entity_id")
        if target in renamed:
            decision["target_entity_id"] = renamed[target]
    for variant in payload["variant_assignments"].values():
        for end in ("source_entity_id", "target_entity_id"):
            variant[end] = renamed.get(variant[end], variant[end])
    bind_chunks(payload, text, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def chunk_budget(root):
    if (root / "chunked-fixture-info.json").exists():
        return json.loads((root / "chunked-fixture-info.json").read_text())[
            "chunk_budget"
        ]
    return 512


async def readd(
    publisher,
    root,
    label,
    text_file,
    identity_file,
    *,
    expected_revision,
    fault_stage,
    semantics=True,
):
    """Publish a forgotten source again from the caller's files: its text and
    identity description, which may differ from what was forgotten. The
    re-add is admitted on the in-memory text and chunks before anything is
    written, so a refusal leaves the stores as the forget left them."""
    import cognee
    from types import SimpleNamespace
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.storage import add_data_points
    from .fixture import context_for, load_chunks
    from .multisource import publish_one
    from .registered import read_texts
    from .retirement import readd_removed
    from .text_changes import chunk_text

    caller = IdentitySource.model_validate_json(identity_file.read_text())
    row = await publisher.forgotten_row(caller)
    tombstone = row.tombstone
    doc = caller.inputs[caller.original_input_ref]
    text = text_file.read_text()
    if text_digest(text) != doc.text_sha256:
        raise IntentError(
            "source_changed", "The caller's text file and identity file disagree"
        )
    removed = await readd_removed(
        publisher.graph, tombstone, row.plan, await publisher.records.rows()
    )
    budget = chunk_budget(root)
    document = SimpleNamespace(
        data_item=SimpleNamespace(
            id=doc.data_id, name=text_file.stem, raw_data_location=str(text_file)
        )
    )
    projected = await chunk_text(text, document, budget)
    source = describe_readd(caller, tombstone, removed, text, projected)
    texts = await read_texts(source, known={source.original_input_ref: text})
    await publisher.admit_readd(source, texts, {str(c.id): c for c in projected})

    await cognee.add(
        DataItem(data=str(text_file), data_id=doc.data_id),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    ctx = await context_for(doc.data_id)
    chunks = await load_chunks(None, ctx, budget=budget)
    if [(str(c.id), c.text) for c in chunks] != [
        (str(c.id), c.text) for c in projected
    ]:
        raise IntentError(
            "chunk_mapping", "Native chunks differ from the admitted ones"
        )
    await add_data_points(chunks, ctx=ctx)
    path = root / f"identity_{label}_revision{source.revision}.json"
    path.write_text(source.model_dump_json(indent=2) + "\n")
    await cognee.add(
        DataItem(data=str(path), data_id=source.identity_data_id),
        dataset_name="stage6_isolated_fixture",
        skip_connection_test=True,
    )
    await publish_one(
        publisher,
        source,
        chunks,
        ctx,
        operation="readd",
        expected_revision=expected_revision,
        fault_stage=fault_stage,
        semantics=semantics,
    )


async def forget_checks(publisher, tombstone, plan, singleton):
    """What remains of a forgotten source, plus the fixture's own objects:
    the values a journey reads after the forget completed."""
    from .forget import remains
    from .native import mention_fact

    graph, vector = publisher.graph, publisher.vector
    mention_ids = [str(m) for m in tombstone.mention_ids.values()]
    removed = [str(e) for e in tombstone.removed_entity_ids]
    primary = tombstone.mention_ids.get("g01")
    return dict(
        **await remains(publisher, tombstone, plan),
        mention_nodes_present=[
            m for m in mention_ids if await graph.get_node(m) is not None
        ],
        mention_vectors_present=[
            m for m in mention_ids if await vector.retrieve("Entity_name", [m])
        ],
        removed_entities=removed,
        removed_entities_present=[
            e for e in removed if await graph.get_node(e) is not None
        ],
        original_fact_present=primary is not None
        and (await mention_fact(publisher, tombstone, primary)).edge is not None,
        private_singleton_present=await graph.get_node(singleton) is not None,
        private_singleton_indexed=bool(
            await vector.retrieve("Entity_name", [singleton])
        ),
    )
