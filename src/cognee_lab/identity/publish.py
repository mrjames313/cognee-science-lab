"""Initial publisher: new source or same-revision reconciliation, through Cognee APIs."""

import json
from dataclasses import dataclass

from .models import Accepted, ChunkInput, IdentitySource, SourceTextInput
from .native import edge_metadata
from .storage import RecordStore, encode
from .validation import IntentError, validate_inputs, validate_uses


def contribution(source, assignment_id, kind, applicability):
    return dict(
        dataset_id=str(source.dataset_id),
        identity_data_id=str(source.identity_data_id),
        revision=source.revision,
        assignment_id=assignment_id,
        kind=kind,
        applicability=applicability,
    )


def identity_edges(source):
    edges = []
    for key, decision in source.mention_resolutions.items():
        if isinstance(decision, Accepted):
            group = source.mention_groups[decision.group_ref]
            doc = source.inputs[group.document_ref]
            scope = dict(
                kind="text_spans",
                data_id=str(doc.data_id),
                text_sha256=doc.text_sha256,
                ranges=[dict(start=o.start, end=o.end) for o in group.occurrences],
            )
            edges.append(
                (
                    str(group.entity_id),
                    str(decision.target_entity_id),
                    "resolves_to",
                    contribution(source, key, "mention", scope),
                )
            )
    for key, variant in source.variant_assignments.items():
        scope = variant.applicability.model_dump(mode="json")
        if scope["kind"] != "corpus":
            doc = source.inputs[scope.pop("document_ref")]
            scope.update(data_id=str(doc.data_id), text_sha256=doc.text_sha256)
        edges.append(
            (
                str(variant.source_entity_id),
                str(variant.target_entity_id),
                "resolves_to",
                contribution(source, key, "variant", scope),
            )
        )
    return edges


def contributions(properties):
    try:
        result = json.loads(properties.get("identity_contributions", "[]"))
    except (TypeError, ValueError) as exc:
        raise IntentError(
            "invalid_contributions", "Malformed identity edge payload"
        ) from exc
    if not isinstance(result, list) or any(not isinstance(x, dict) for x in result):
        raise IntentError(
            "invalid_contributions", "Identity contributions must be a list of objects"
        )
    return result


@dataclass
class PublishResult:
    attempt_id: str
    created: list[str]
    referenced: list[str]


class Publisher:
    def __init__(self, graph, vector, records: RecordStore, runtime_profile=None):
        self.graph, self.vector, self.records = graph, vector, records
        self.runtime_profile = runtime_profile or {}

    @classmethod
    async def configured(cls):
        from cognee.infrastructure.databases.graph import get_graph_engine
        from cognee.infrastructure.databases.vector import get_vector_engine_async
        from cognee.infrastructure.databases.graph.config import get_graph_config
        from cognee.infrastructure.databases.vector.config import get_vectordb_config
        from cognee.infrastructure.databases.relational.config import (
            get_relational_config,
        )
        from cognee import __version__

        records = RecordStore()
        await records.initialize()
        return cls(
            await get_graph_engine(),
            await get_vector_engine_async(),
            records,
            runtime_profile=dict(
                cognee_version=__version__,
                graph_provider=get_graph_config().graph_database_provider,
                vector_provider=get_vectordb_config().vector_db_provider,
                relational_provider=get_relational_config().db_provider,
            ),
        )

    async def preflight(self, source, texts, chunks, ctx):
        from cognee.infrastructure.databases.graph.graph_db_interface import (
            GraphDBInterface,
        )
        from cognee.modules.data.methods.get_data import get_data
        from cognee.infrastructure.files.utils.open_data_file import open_data_file

        required = [
            "attach_node_source_refs",
            "attach_edge_source_refs",
            "get_node_delete_data",
            "get_edge_delete_data",
        ]
        for method in required:
            implementation = getattr(type(self.graph), method, None)
            if implementation is getattr(GraphDBInterface, method, None):
                raise IntentError("unsupported_capability", f"Graph lacks {method}")
        if (
            ctx.user is None
            or str(ctx.dataset.id) != str(source.dataset_id)
            or str(ctx.data_item.id) != str(source.identity_data_id)
        ):
            raise IntentError(
                "source_context", "Expected real generated-source PipelineContext"
            )
        for item in source.inputs.values():
            if isinstance(item, SourceTextInput):
                if item.dataset_id != source.dataset_id:
                    raise IntentError(
                        "dataset_scope",
                        "Cross-dataset text inputs are not admitted yet",
                    )
                record = await get_data(ctx.user.id, item.data_id, source.dataset_id)
                if record is None:
                    raise IntentError(
                        "source_missing", "Original Data item is not registered"
                    )
                key = next(k for k, value in source.inputs.items() if value is item)
                if key in texts:
                    async with open_data_file(
                        record.raw_data_location, mode="r", encoding="utf-8"
                    ) as f:
                        if f.read() != texts[key]:
                            raise IntentError(
                                "source_changed",
                                "Supplied text differs from registered original",
                            )
        generated = await get_data(
            ctx.user.id, source.identity_data_id, source.dataset_id
        )
        if generated is None:
            raise IntentError(
                "source_missing", "Generated identity Data item is not registered"
            )
        async with open_data_file(
            generated.raw_data_location, mode="r", encoding="utf-8"
        ) as f:
            try:
                registered = IdentitySource.model_validate_json(f.read())
            except ValueError as exc:
                raise IntentError(
                    "generated_source_kind",
                    "Registered Data is not an identity description",
                ) from exc
        if registered != source:
            raise IntentError(
                "generated_source_changed",
                "Registered identity description differs from selected intent",
            )
        for chunk_id, chunk in chunks.items():
            stored = await self.graph.get_node(chunk_id)
            if stored is None or stored.get("text") != chunk.text:
                raise IntentError(
                    "chunk_mapping", "Original chunk is absent or differs in the graph"
                )
        await validate_inputs(source, texts=texts, chunks=chunks, graph=self.graph)
        rows = await self.records.rows()
        descriptions = [
            IdentitySource.model_validate_json(r["description"])
            for r in rows
            if (r["dataset"], r["source"])
            != (str(source.dataset_id), str(source.identity_data_id))
        ]
        validate_uses([*descriptions, source])
        previous = next(
            (
                r
                for r in rows
                if (r["dataset"], r["source"])
                == (str(source.dataset_id), str(source.identity_data_id))
            ),
            None,
        )
        if previous and previous["revision"] != source.revision:
            raise IntentError(
                "not_admitted", "Revision replacement/withdrawal is a later milestone"
            )
        for entity_id in source.entity_constructions:
            node = await self.graph.get_node(str(entity_id))
            if node is not None and node.get("type") != "Entity":
                raise IntentError("incompatible_type", f"{entity_id} is not an Entity")

    async def publish(
        self,
        source: IdentitySource,
        *,
        texts,
        chunks,
        ctx,
        expected_revision=0,
        origin="runtime",
        fault_stage=None,
        semantic_writer=None,
        verify_semantics=None,
    ):
        from cognee.infrastructure.databases.provenance import (
            EdgeIdentity,
            make_chunk_source_ref_key,
            make_source_ref_key,
        )
        from cognee.modules.engine.models import Entity
        from cognee.modules.graph.utils import ensure_default_edge_properties
        from cognee.tasks.storage import add_data_points

        await self.preflight(source, texts, chunks, ctx)
        wanted = identity_edges(source)
        markers = [
            (str(source.inputs[key].chunk_id), str(group.entity_id), key)
            for group in source.mention_groups.values()
            for key in group.chunk_refs
        ]
        plan = dict(
            operation="identity_publish",
            revision=source.revision,
            entities=[str(i) for i in source.entity_constructions],
            identity_edges=[list(e[:3]) for e in wanted],
            markers=[list(m[:2]) for m in markers],
            withdraw=[],
            runtime_profile=self.runtime_profile,
        )
        attempt = await self.records.begin(
            source,
            expected_revision=expected_revision,
            plan=plan,
            origin=origin,
            method="reconcile" if expected_revision else "publish",
        )
        stage, created, referenced = "validation", [], []
        try:
            # Repeat after taking the project writer reservation.
            await self.preflight(source, texts, chunks, ctx)
            owner = make_source_ref_key(source.dataset_id, source.identity_data_id)
            old_properties = {}
            stage = "nodes"
            new_nodes = []
            for entity_id, recipe in source.entity_constructions.items():
                node = await self.graph.get_node(str(entity_id))
                if node is None:
                    new_nodes.append(
                        Entity(
                            id=entity_id,
                            name=recipe.name,
                            description=recipe.description,
                        )
                    )
                    created.append(str(entity_id))
                else:
                    old_properties[str(entity_id)] = node
                    referenced.append(str(entity_id))
            if new_nodes:
                await add_data_points(new_nodes, ctx=ctx)
            if referenced:
                await self.graph.attach_node_source_refs(referenced, [owner])
            if fault_stage == stage:
                raise IntentError(
                    "injected_failure", "Injected failure after node persistence"
                )

            if semantic_writer is not None:
                stage = "semantic_write"
                await semantic_writer()

            stage = "markers"
            for chunk_id, mention_id, key in markers:
                chunk_input = source.inputs[key]
                doc = source.inputs[chunk_input.document_ref]
                ref = make_chunk_source_ref_key(
                    source.dataset_id, doc.data_id, chunk_input.chunk_id
                )
                await self.graph.add_edges(
                    ensure_default_edge_properties(
                        [(chunk_id, mention_id, "has_identity_mention", {})]
                    ),
                    source_ref_key=ref,
                )
            stage = "identity_edges"
            for source_id, target_id, relation, own in wanted:
                existing = await edge_metadata(
                    self.graph, source_id, target_id, relation
                )
                props = dict(existing.edge_properties) if existing else {}
                if existing and props.get("resolution_kind") != own["kind"]:
                    raise IntentError(
                        "edge_collision", "Existing resolves_to has incompatible kind"
                    )
                previous = contributions(props)
                key = (own["dataset_id"], own["identity_data_id"], own["assignment_id"])
                kept = [
                    c
                    for c in previous
                    if (
                        c.get("dataset_id"),
                        c.get("identity_data_id"),
                        c.get("assignment_id"),
                    )
                    != key
                ]
                props.update(
                    resolution_kind=own["kind"],
                    identity_contributions=encode([*kept, own]),
                )
                # Helper links are graph-only, excluded from semantic index discovery.
                await self.graph.add_edges(
                    ensure_default_edge_properties(
                        [(source_id, target_id, relation, props)]
                    ),
                    source_ref_key=owner,
                )
            if fault_stage == stage:
                raise IntentError(
                    "injected_failure", "Injected failure after identity edges"
                )

            stage = "verification"
            for entity_id in source.entity_constructions:
                sid = str(entity_id)
                node = await self.graph.get_node(sid)
                if node is None or node.get("type") != "Entity":
                    raise IntentError("verify_node", "Expected Entity missing")
                if sid in old_properties and node != old_properties[sid]:
                    raise IntentError(
                        "unexpected_overwrite", "Referencing changed ordinary fields"
                    )
                metadata = (await self.graph.get_node_delete_data([sid]))[sid]
                if owner not in metadata.source_ref_keys:
                    raise IntentError("verify_owner", "Entity owner missing")
                if not await self.vector.retrieve("Entity_name", [sid]):
                    raise IntentError("verify_index", "Entity name vector missing")
            for source_id, target_id, relation, own in wanted:
                edge = await edge_metadata(self.graph, source_id, target_id, relation)
                if edge is None or own not in contributions(edge.edge_properties):
                    raise IntentError("verify_edge", "Identity contribution missing")
                ref = EdgeIdentity(source_id, target_id, relation)
                if (
                    owner
                    not in (await self.graph.get_edge_delete_data([ref]))[
                        ref
                    ].source_ref_keys
                ):
                    raise IntentError("verify_owner", "Identity edge owner missing")
            for chunk_id, mention_id, key in markers:
                if not await self.graph.has_edge(
                    chunk_id, mention_id, "has_identity_mention"
                ):
                    raise IntentError("verify_marker", "Mention marker missing")
                item = source.inputs[key]
                doc = source.inputs[item.document_ref]
                marker = await edge_metadata(
                    self.graph, chunk_id, mention_id, "has_identity_mention"
                )
                ref = make_chunk_source_ref_key(
                    source.dataset_id, doc.data_id, item.chunk_id
                )
                if marker is None or ref not in marker.source_ref_keys:
                    raise IntentError(
                        "verify_owner", "Original-chunk marker owner missing"
                    )
            await validate_inputs(source, texts=texts, chunks=chunks, graph=self.graph)
            if verify_semantics is not None:
                await verify_semantics()
            if fault_stage == stage:
                raise IntentError(
                    "injected_failure", "Injected failure before acknowledgement"
                )
            await self.records.complete(source, attempt)
            return PublishResult(attempt, created, referenced)
        except Exception as exc:
            try:
                event = await self.records.fail(
                    source, attempt, stage, exc, origin=origin
                )
            except Exception as diagnostic_error:
                raise IntentError(
                    "recovery_record_failed",
                    f"Publication unavailable: attempt={attempt}, stage={stage}, error={exc}; "
                    f"recovery-event write also failed: {diagnostic_error}",
                ) from diagnostic_error
            raise IntentError(
                "recovery_required", f"{exc}; recovery_event_id={event}"
            ) from exc
