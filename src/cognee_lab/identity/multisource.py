"""Two captured original documents sharing identity output in native stores."""

import json
from uuid import NAMESPACE_URL, UUID, uuid5

from .environment import DATASET_NAME
from .models import IdentitySource
from .native import edge_metadata
from .publish import Publisher, contributions
from .retrieve import retrieve
from .validation import IntentError, text_digest


def fixture_id(label):
    return str(uuid5(NAMESPACE_URL, "cognee-lab:stage6:multi:" + label))


def private_singleton_id(source, label):
    """The UUID this description gives the label's private singleton: the
    fixture's at first publication, a derived replacement after a re-add. A
    revision that dropped the recipe is checked against the fixture's UUID,
    which its replacement retired."""
    return next(
        (
            str(eid)
            for eid, recipe in source.entity_constructions.items()
            if recipe.name == label + " instrument"
        ),
        fixture_id(label + ":singleton"),
    )


def add_lifecycle_records(payload, label, text):
    payload["entity_constructions"][fixture_id("shared_singleton")] = dict(
        name="Shared calibrator",
        description="Independent singleton support from each document.",
    )
    payload["entity_constructions"][fixture_id(label + ":singleton")] = dict(
        name=label + " instrument",
        description="Singleton supported by this identity source only.",
    )
    mid = fixture_id(label + ":unresolved")
    payload["entity_constructions"][mid] = dict(
        name="local reference", description="Unresolved group with no semantic facts."
    )
    start = text.index("plasma")
    payload["mention_groups"]["g02"] = dict(
        entity_id=mid,
        document_ref="doc01",
        occurrences=[dict(start=start, end=start + 6, text="plasma")],
        chunk_refs=["chunk01"],
        input_refs=["doc01"],
        producer_ref="fixture",
    )
    payload["mention_resolutions"]["r02"] = dict(
        group_ref="g02",
        status="unresolved",
        input_refs=["doc01"],
        producer_ref="fixture",
        explanation=None,
    )


def describe_doc02(first, text, chunks, *, dependent=False):
    """doc02's captured description, derived from doc01's (`first`): its own
    Data items, mention and private records over `text` and its chunks,
    and with `dependent` the consumption of doc01 (forget_fixture)."""
    from .captured_chunks import bind_chunks

    payload = first.model_dump(mode="json")
    payload["identity_data_id"] = fixture_id("doc02:identity")
    payload["inputs"]["doc01"]["data_id"] = fixture_id("doc02:original")
    payload["inputs"]["doc01"]["text_sha256"] = text_digest(text)
    old_mid = str(first.mention_groups["g01"].entity_id)
    new_mid = fixture_id("doc02:mention")
    payload["entity_constructions"][new_mid] = payload["entity_constructions"].pop(
        old_mid
    )
    payload["mention_groups"]["g01"]["entity_id"] = new_mid
    for key in [fixture_id("doc01:singleton"), fixture_id("doc01:unresolved")]:
        payload["entity_constructions"].pop(key)
    add_lifecycle_records(payload, "doc02", text)
    if dependent:
        from .forget_fixture import add_dependency

        add_dependency(payload, first, text)
    bind_chunks(payload, text, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


async def prepare(root, *, chunked=False, dependent=False):
    """Register doc01 and doc02 and their descriptions through the lab's
    `add`. Returns the publisher, the descriptions in publication order and
    the chunk budget."""
    import cognee

    from . import entry
    from .fixture import add_doc01

    if cognee.__version__ != "1.6.2":
        raise IntentError(
            "unsupported_version", "First fixture requires inspected Cognee 1.6.2"
        )

    budget = 9 if chunked else 512
    text = None
    if chunked:
        from .fixture import FIXTURES

        text = (
            (FIXTURES / "source.txt")
            .read_text()
            .replace(". The controller", ", the controller")
            .replace("; it", ", and it")
        )
    publisher, first = await add_doc01(
        root, multi=True, chunk_budget=budget, source_text=text
    )
    original = entry.Original(root / "source02.txt", UUID(fixture_id("doc02:original")))
    original.path.write_text(
        (root / "source.txt").read_text().rstrip("\n")
        + " During startup, HC remains active.\n"
    )
    second = await entry.add(
        DATASET_NAME,
        original,
        describe=lambda draft: describe_doc02(
            first, draft.text, draft.chunks, dependent=dependent
        ),
        identity_path=root / "identity02.json",
        chunk_budget=budget,
    )
    info = dict(
        dataset_id=str(first.dataset_id),
        sources={"doc01": "identity.json", "doc02": "identity02.json"},
        dependent=dependent,
    )
    (root / INFO).write_text(json.dumps(info, indent=2))
    if chunked:
        (root / "chunked-fixture-info.json").write_text(
            json.dumps(dict(chunk_budget=budget, prefix="Δ review: "), indent=2)
        )
    return publisher, {"doc01": first, "doc02": second}, budget


INFO = "multi-fixture-info.json"


def read_sources(root, info=INFO):
    """The identity file of each source a fixture manifest names."""
    manifest = json.loads((root / info).read_text())
    return {
        label: IdentitySource.model_validate_json((root / path).read_text())
        for label, path in manifest["sources"].items()
    }


async def saved_or_file(publisher, files):
    """Each source's saved description, or its file from the root when it
    has no row or a tombstone, which keeps no description."""
    rows = {r.source: r for r in await publisher.records.rows()}
    return {
        label: getattr(rows.get(str(source.identity_data_id)), "description", None)
        or source
        for label, source in files.items()
    }


def fixture_files(root):
    """Each source's identity file on a root this driver runs: the two the
    manifest names, or a single-source `fixture` root's doc01."""
    if (root / INFO).exists():
        return read_sources(root)
    return {
        "doc01": IdentitySource.model_validate_json(
            (root / "identity.json").read_text()
        )
    }


def root_files(root):
    """Each source's identity file, by label, on a root of any kind."""
    from .environment import read_fixture
    from .glossary_fixture import files as glossary_files

    if read_fixture(root) == "glossary-fixture":
        return glossary_files(root)
    return fixture_files(root)


def root_labels(root) -> dict[str, str]:
    """Each source's label on the root, by identity Data ID."""
    return {str(s.identity_data_id): k for k, s in root_files(root).items()}


async def current_sources(root, publisher, info=INFO):
    """Each source a fixture manifest names, as it is saved now
    (`saved_or_file`): a two-source root's by default, or another fixture's
    manifest."""
    return await saved_or_file(publisher, read_sources(root, info))


async def reconcile_one(publisher, source, *, semantics, fault_stage=None):
    """Reconcile the saved revision over the chunks Cognee holds, in the
    native pipeline: finish a failed attempt or verify a current one.
    `semantics` writes the missing captured facts and verifies them; None
    for a source without captured facts."""
    from .fixture import load_chunks
    from .registered import context_for, read_texts
    from cognee.modules.pipelines.operations.run_tasks_base import run_tasks_base
    from cognee.modules.pipelines.tasks.task import Task

    original = await context_for(source.inputs[source.original_input_ref].data_id)
    chunks = await load_chunks(source, original)
    ctx = await context_for(source.identity_data_id)

    async def task(items, ctx=None):
        for item in items:
            await publisher.reconcile(
                item,
                texts=await read_texts(item),
                chunks={str(c.id): c for c in chunks},
                ctx=ctx,
                origin="test/fault_injection" if fault_stage else "test",
                fault_stage=fault_stage,
                semantic_writer=(
                    None
                    if semantics is None
                    else lambda: semantics.write(publisher, item, chunks, original)
                ),
                verify_semantics=(
                    None
                    if semantics is None
                    else lambda: semantics.verify(publisher, item, chunks, original)
                ),
            )
        return items

    async for _ in run_tasks_base(
        [Task(task, needs_llm=False)], [source], ctx.user, ctx
    ):
        pass


async def reconcile_publication(publisher, source, *, semantics, fault_stage=None):
    """Finish or verify a publication's saved revision. A failed first
    publication finishes through the lab's cognify, as it started; any other
    row is reconciled over the chunks Cognee holds (`reconcile_one`). The
    caller refuses a source whose native copy is gone first."""
    from . import entry

    row = await publisher.records.row(source)
    if (
        row is not None
        and row.failed_attempt == "publish"
        and not row.verified_revision
    ):
        await entry.cognify(
            publisher,
            [source],
            semantics=semantics,
            fault_stage=fault_stage,
            origin="test",
        )
        return
    await reconcile_one(publisher, source, semantics=semantics, fault_stage=fault_stage)


async def reconcile_selected(publisher, label, selected, *, resume_text_change) -> dict:
    """Finish the selected source's failed attempt, after refusing one whose
    native copy is gone. Returns what the command reports beside the
    snapshot: a finished forget's outcome, or what a completed text change
    (`resume_text_change`) refreshed."""
    from .forget_fixture import reconcile_forget, semantics_for
    from .revisions import replace_one
    from .text_changes import TextChange

    await publisher.refuse_natively_deleted(selected)
    row = await publisher.records.row(selected)
    if (finished := await reconcile_forget(publisher, row, selected)) is not None:
        return finished
    if row.resumed_by == "replace" and row.plan.get("text_change"):
        return await resume_text_change(
            publisher,
            selected,
            TextChange.from_plan(row.plan),
            expected_revision=selected.revision,
        )
    if row.resumed_by == "replace":
        await replace_one(publisher, selected, expected_revision=selected.revision)
    else:
        await reconcile_publication(publisher, selected, semantics=semantics_for(label))
    return {}


async def snapshot(publisher, sources, query="What does HC limit?"):
    from .fixture import OSCILLATIONS_ID
    from cognee.infrastructure.databases.provenance import make_chunk_source_ref_key
    from cognee.modules.engine.utils import generate_edge_object_id
    from cognee.modules.provenance.edge_evidence.lookup import get_edge_evidence_records
    from .captured_chunks import fact_chunks, fixture_mention_id, retired_mentions
    from .models import ChunkInput
    from types import SimpleNamespace

    first = sources["doc01"]
    # Keep the original shared edge/controller visible after doc01 retargets.
    variant = sources["doc02"].variant_assignments["v01"]
    shared = await edge_metadata(
        publisher.graph,
        variant.source_entity_id,
        variant.target_entity_id,
        "resolves_to",
    )
    rows = {r.source: r for r in await publisher.records.rows(first.dataset_id)}
    result = dict(
        result=await retrieve(publisher, first.dataset_id, query),
        sources={},
        shared_variant=dict(
            present=shared is not None,
            contributions=contributions(shared.edge_properties) if shared else [],
            owners=shared.source_ref_keys if shared else [],
            properties=shared.edge_properties if shared else {},
        ),
        shared_singleton_present=await publisher.graph.get_node(
            fixture_id("shared_singleton")
        )
        is not None,
        shared_singleton_indexed=bool(
            await publisher.vector.retrieve(
                "Entity_name", [fixture_id("shared_singleton")]
            )
        ),
        borrowed_entity=await publisher.graph.get_node(str(variant.target_entity_id)),
        recovery_events=await publisher.records.events(first.dataset_id),
    )
    hc = await publisher.graph.get_node_delete_data([str(variant.source_entity_id)])
    result["hc_entity"] = dict(
        present=str(variant.source_entity_id) in hc,
        owners=sorted(
            hc[str(variant.source_entity_id)].source_ref_keys
            if str(variant.source_entity_id) in hc
            else []
        ),
    )
    from .native_copy import deleted_entry, missing_native

    for label, source in sources.items():
        from .registered import read_registered

        row = rows[str(source.identity_data_id)]
        if row.operation == "identity_forget":
            from .forget_fixture import forget_checks
            from .retirement import source_ids

            # A forgotten row reads its tombstone; an unfinished forget the
            # identifiers of its saved description.
            if (tomb := row.tombstone) is not None:
                mentions, removed = tomb.mention_ids, tomb.removed_entity_ids
            else:
                mentions = {k: g.entity_id for k, g in source.mention_groups.items()}
                removed = []
            result["sources"][label] = dict(
                identity_data_id=str(source.identity_data_id),
                state=row.state,
                saved_revision=row.revision,
                verified_revision=row.verified_revision,
                forget=await forget_checks(
                    publisher,
                    source_ids(source),
                    mentions,
                    removed,
                    row.plan,
                    private_singleton_id(source, label),
                ),
            )
            continue
        if missing := await missing_native(publisher.graph, row):
            result["sources"][label] = deleted_entry(row, missing)
            continue
        registered = await read_registered(source)
        mid = fixture_mention_id(source)
        unresolved_group = source.mention_groups.get("g02")
        unresolved = (
            unresolved_group.entity_id
            if unresolved_group
            else fixture_id(label + ":unresolved")
        )
        group = source.mention_groups.get("g01")
        mapped = [i for i in source.inputs.values() if isinstance(i, ChunkInput)]
        chunks = []
        for item in mapped:
            node = await publisher.graph.get_node(str(item.chunk_id))
            if node is not None:
                chunks.append(
                    SimpleNamespace(
                        id=item.chunk_id,
                        chunk_index=node["chunk_index"],
                        text=node["text"],
                    )
                )
        selected = fact_chunks(source, chunks)
        doc = source.inputs[source.original_input_ref]
        fact = await edge_metadata(publisher.graph, mid, OSCILLATIONS_ID, "limits")
        refs = {
            make_chunk_source_ref_key(source.dataset_id, doc.data_id, c.id)
            for c in selected
        }
        evidence = await get_edge_evidence_records(
            [UUID(generate_edge_object_id(str(mid), str(OSCILLATIONS_ID), "limits"))],
            source.dataset_id,
            per_edge_limit=100,
            total_limit=100,
        )
        chunk_checks = []
        for i in mapped:
            node = next(c for c in chunks if c.id == i.chunk_id)
            chunk_ref = make_chunk_source_ref_key(
                source.dataset_id, doc.data_id, i.chunk_id
            )
            chunk_checks.append(
                dict(
                    chunk_id=str(i.chunk_id),
                    start=i.start,
                    end=i.end,
                    chunk_index=node.chunk_index,
                    mention_marker_present=await publisher.graph.has_edge(
                        str(i.chunk_id), str(mid), "has_identity_mention"
                    ),
                    owns_captured_fact=fact is not None
                    and chunk_ref in fact.source_ref_keys,
                    evidence_present=any(
                        e.data_id == doc.data_id
                        and e.chunk_id == i.chunk_id
                        and e.chunk_index == node.chunk_index
                        for e in evidence
                    ),
                )
            )
        result["sources"][label] = dict(
            identity_data_id=str(source.identity_data_id),
            state=rows[str(source.identity_data_id)].state,
            saved_revision=source.revision,
            verified_revision=rows[str(source.identity_data_id)].verified_revision,
            registered_revision=registered.revision,
            registered_matches_saved=registered == source,
            input_keys=sorted(source.inputs),
            decisions={
                k: dict(
                    status=d.status,
                    producer_ref=d.producer_ref,
                    input_refs=d.input_refs,
                )
                for k, d in [
                    *source.mention_resolutions.items(),
                    *source.variant_assignments.items(),
                ]
            },
            resolution_status=(
                source.mention_resolutions["r01"].status
                if "r01" in source.mention_resolutions
                else None
            ),
            resolution_target_entity_id=(
                str(source.mention_resolutions["r01"].target_entity_id)
                if "r01" in source.mention_resolutions
                and source.mention_resolutions["r01"].status == "accepted"
                else None
            ),
            mention_entity_id=str(mid),
            original_marker_present=group is not None
            and all(
                [
                    await publisher.graph.has_edge(
                        str(source.inputs[k].chunk_id), str(mid), "has_identity_mention"
                    )
                    for k in group.chunk_refs
                ]
            ),
            original_fact_present=await publisher.graph.has_edge(
                str(mid), str(OSCILLATIONS_ID), "limits"
            ),
            original_fact_owned_by_chunk=fact is not None
            and refs <= set(fact.source_ref_keys),
            original_evidence_present=bool(selected)
            and {
                (e.chunk_id, e.chunk_index)
                for e in evidence
                if e.data_id == doc.data_id
            }
            == {(c.id, c.chunk_index) for c in selected},
            unresolved_marker_present=unresolved_group is not None
            and all(
                [
                    await publisher.graph.has_edge(
                        str(source.inputs[k].chunk_id),
                        str(unresolved),
                        "has_identity_mention",
                    )
                    for k in unresolved_group.chunk_refs
                ]
            ),
            unresolved_entity_present=await publisher.graph.get_node(str(unresolved))
            is not None,
            private_singleton_entity_id=private_singleton_id(source, label),
            private_singleton_present=await publisher.graph.get_node(
                private_singleton_id(source, label)
            )
            is not None,
            private_singleton_indexed=bool(
                await publisher.vector.retrieve(
                    "Entity_name", [private_singleton_id(source, label)]
                )
            ),
            chunk_count=len(mapped),
            chunk_mapping=chunk_checks,
            mention_marker_chunk_ids=(
                [str(source.inputs[k].chunk_id) for k in group.chunk_refs]
                if group
                else []
            ),
            fact_evidence_chunk_ids=[str(c.id) for c in selected],
        )
        if group is None:
            from .resolved_retirement import retirement_checks

            result["sources"][label]["resolved_group_retirement"] = (
                await retirement_checks(publisher, source, mid)
            )
            combined = {
                k: await retirement_checks(publisher, source, rid)
                for k, rid in retired_mentions(source).items()
                if k != "g01"
            }
            if combined:
                result["sources"][label]["combined_group_retirement"] = combined
    for row in rows.values():
        if row.plan.get("text_change") and row.state == "current":
            from .text_fixture import transition_summary

            result.setdefault("text_changes", []).append(
                await transition_summary(publisher, row)
            )
    return result


async def run(args, root):
    refresh = {}
    if args.command in {"multi-fixture", "chunked-fixture"}:
        from . import entry
        from .fixture import CapturedSemantics

        publisher, sources, budget = await prepare(
            root,
            chunked=args.command == "chunked-fixture",
            dependent=args.dependent,
        )
        args._fixture_publisher = publisher
        for label, source in sources.items():
            await entry.cognify(
                publisher,
                [source],
                semantics=CapturedSemantics(),
                chunk_budget=budget,
                fault_stage=args.fault_stage if label == args.source else None,
                origin="test",
            )
    else:
        publisher = await Publisher.configured()
        args._fixture_publisher = publisher
        sources = await saved_or_file(publisher, fixture_files(root))
        if args.source not in sources:
            raise IntentError(
                "source_missing", "Selected document is not in this fixture"
            )
        selected = sources[args.source]
        if args.command == "forget" and args.dry_run:
            from .forget_fixture import forget_dry_run

            return await forget_dry_run(publisher, root, args, args.source, selected)
        origin = "test/fault_injection" if args.fault_stage else "test"
        if args.command == "withdraw":
            await publisher.withdraw(
                selected,
                expected_revision=selected.revision,
                origin=origin,
                fault_stage=args.fault_stage,
            )
        elif args.command == "forget":
            from .forget_fixture import forget_command

            refresh = await forget_command(publisher, root, args, args.source, selected)
        elif args.command == "readd":
            from .forget_fixture import readd

            refresh = await readd(
                publisher,
                root,
                args.source,
                expected_revision=args.expected_revision,
                fault_stage=args.fault_stage,
            )
        elif args.command == "reconcile":
            from .text_fixture import maintain_one

            refresh = await reconcile_selected(
                publisher, args.source, selected, resume_text_change=maintain_one
            )
        # Forget and re-add change the saved descriptions; report the new ones.
        sources = await saved_or_file(publisher, fixture_files(root))
    if len(sources) == 1:
        result = dict(
            result=await retrieve(publisher, selected.dataset_id, args.query),
            publications=[
                row.record()
                for row in await publisher.records.rows(selected.dataset_id)
            ],
            recovery_events=await publisher.records.events(selected.dataset_id),
        )
    else:
        result = await snapshot(publisher, sources, args.query)
    if args.command == "status":
        result["removed_entities"] = await publisher.records.removal_report()
    # A reconcile that completed a text change reports its refresh beside it.
    result.update(refresh)
    (root / "multisource_result.json").write_text(json.dumps(result, indent=2))
    return result
