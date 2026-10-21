"""Exact input checks. No identity judgments or approximate substring matching."""

from hashlib import sha256
from typing import Any
from uuid import UUID, uuid5

import rfc8785

from .models import (
    ChunkInput,
    CorpusObjectInput,
    IdentitySource,
    SavedRecordInput,
    SourceTextInput,
    TextScope,
    TextSpanInput,
)


class IntentError(ValueError):
    """Intent cannot currently be published; code is suitable for diagnostics."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def text_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def fresh_mention_id(identity_data_id: UUID, key: str) -> UUID:
    return uuid5(identity_data_id, f"mention:{key}")


def object_digest(value: Any) -> str:
    return sha256(rfc8785.dumps(value)).hexdigest()


def map_chunks(document_text: str, chunks: list) -> dict[str, tuple[int, int]]:
    """Use Cognee's exact tiling check, not a separate mapping algorithm."""
    from cognee.modules.chunking.incremental_chunking import chunk_offsets

    ordered = sorted(chunks, key=lambda c: c.chunk_index)
    if len({c.chunk_index for c in ordered}) != len(ordered):
        raise IntentError("chunk_mapping", "Duplicate chunk indexes")
    if len({str(c.id) for c in ordered}) != len(ordered):
        raise IntentError("chunk_mapping", "Duplicate chunk UUIDs")
    try:
        offsets = chunk_offsets(document_text, [c.text for c in ordered])
    except ValueError as exc:
        raise IntentError("chunk_mapping", str(exc)) from exc
    except Exception as exc:
        from cognee.modules.chunking.incremental_chunking import IncrementalPlanError

        if isinstance(exc, IncrementalPlanError):
            raise IntentError("chunk_mapping", str(exc)) from exc
        raise
    return {str(c.id): span for c, span in zip(ordered, offsets, strict=True)}


async def validate_inputs(
    source: IdentitySource,
    *,
    texts: dict[str, str],
    chunks: dict[str, Any],
    graph,
    saved_record_reader=None,
) -> None:
    """Validate the current source and the union of actually consumed dependencies."""
    used = {source.original_input_ref}
    for record in [
        *source.mention_groups.values(),
        *source.mention_resolutions.values(),
        *source.variant_assignments.values(),
    ]:
        used.update(record.input_refs)
    for group in source.mention_groups.values():
        used.add(group.document_ref)
        used.update(group.chunk_refs)
    for variant in source.variant_assignments.values():
        if hasattr(variant.applicability, "document_ref"):
            used.add(variant.applicability.document_ref)
    for key in list(used):
        item = source.inputs[key]
        if isinstance(item, (ChunkInput, TextSpanInput)):
            used.add(item.document_ref)

    mappings = {}
    for key in used:
        item = source.inputs[key]
        if isinstance(item, SourceTextInput):
            if key not in texts or text_digest(texts[key]) != item.text_sha256:
                raise IntentError("source_changed", f"Text missing/changed: {key}")
            matching = [
                c for c in chunks.values() if str(c.is_part_of.id) == str(item.data_id)
            ]
            if matching:
                mappings[key] = map_chunks(texts[key], matching)

    for key in used:
        item = source.inputs[key]
        if isinstance(item, SourceTextInput):
            text = texts.get(key)
            if text is None or text_digest(text) != item.text_sha256:
                raise IntentError("source_changed", f"Text missing/changed: {key}")
        elif isinstance(item, TextSpanInput):
            text = texts[item.document_ref]
            if (
                item.end > len(text)
                or text_digest(text[item.start : item.end]) != item.text_sha256
            ):
                raise IntentError("input_changed", f"Span missing/changed: {key}")
        elif isinstance(item, CorpusObjectInput):
            node = await graph.get_node(str(item.entity_id))
            if node is None:
                raise IntentError(
                    "missing_reasoning_input", f"Corpus input missing: {key}"
                )
            if any(field not in node for field in item.selected_fields):
                raise IntentError("input_changed", f"Corpus fields missing: {key}")
            if (
                object_digest({field: node[field] for field in item.selected_fields})
                != item.content_sha256
            ):
                raise IntentError("input_changed", f"Corpus fields changed: {key}")
        elif isinstance(item, SavedRecordInput):
            if saved_record_reader is None:
                raise IntentError(
                    "unsupported_input", "A saved-record reader is required"
                )
            value, revision = await saved_record_reader(item)
            if (
                revision != item.representation_revision
                or object_digest(value) != item.content_sha256
            ):
                raise IntentError("input_changed", f"Saved record changed: {key}")
        elif isinstance(item, ChunkInput):
            chunk = chunks.get(str(item.chunk_id))
            parent = source.inputs[item.document_ref]
            text = texts[item.document_ref]
            if (
                chunk is None
                or str(chunk.is_part_of.id) != str(parent.data_id)
                or item.end > len(text)
                or chunk.text != text[item.start : item.end]
            ):
                raise IntentError(
                    "chunk_mapping", f"Chunk missing or mapping changed: {key}"
                )
            if mappings.get(item.document_ref, {}).get(str(item.chunk_id)) != (
                item.start,
                item.end,
            ):
                raise IntentError(
                    "chunk_mapping",
                    f"Chunk range differs from ordered native mapping: {key}",
                )

    for group in source.mention_groups.values():
        text = texts[group.document_ref]
        for occurrence in group.occurrences:
            if (
                occurrence.end > len(text)
                or text[occurrence.start : occurrence.end] != occurrence.text
            ):
                raise IntentError(
                    "occurrence_changed", "Occurrence does not match document slice"
                )
        for key in group.chunk_refs:
            chunk = source.inputs[key]
            if not any(
                o.start < chunk.end and chunk.start < o.end for o in group.occurrences
            ):
                raise IntentError(
                    "context_marker", "Context-only chunk cannot own a mention marker"
                )
    for variant in source.variant_assignments.values():
        scope = variant.applicability
        if isinstance(scope, TextScope):
            if any(r.end > len(texts[scope.document_ref]) for r in scope.ranges):
                raise IntentError("scope_range", "Variant range outside document")


def validate_uses(sources: list[IdentitySource]) -> None:
    """Build a transient UUID-use view; singleton declarations count as reusable."""
    mentions, reusable = {}, set()
    for source in sources:
        local_mentions = {g.entity_id for g in source.mention_groups.values()}
        reusable.update(set(source.entity_constructions) - local_mentions)
        for key, group in source.mention_groups.items():
            identity = (source.identity_data_id, key)
            if group.entity_id in mentions and mentions[group.entity_id] != identity:
                raise IntentError(
                    "incompatible_group", "Mention UUID belongs to another group"
                )
            mentions[group.entity_id] = identity
    if set(mentions) & reusable:
        raise IntentError(
            "incompatible_use", "UUID used as both mention and reusable Entity"
        )
