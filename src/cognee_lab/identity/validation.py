"""Exact input checks. No identity judgments or approximate substring matching."""

from enum import StrEnum
from hashlib import sha256
from typing import Any, NamedTuple
from uuid import UUID, uuid5

from .models import (
    ChunkInput,
    CorpusObjectInput,
    IdentitySource,
    SavedRecordInput,
    SourceTextInput,
    TextScope,
    TextSpanInput,
    Tombstone,
)
from .digests import object_digest
from .records import REGISTRY, record_inputs


class IntentError(ValueError):
    """Intent cannot currently be published; code is suitable for diagnostics.
    `details` carries structured diagnostics for the CLI, such as the list of
    dependent sources that refused a forget."""

    def __init__(self, code: str, message: str, details=None):
        self.code = code
        self.details = details
        super().__init__(message)


MISSING_INPUT = "Corpus input missing: {}"


def text_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def fresh_mention_id(identity_data_id: UUID, revision: int, key: str) -> UUID:
    return uuid5(identity_data_id, f"mention:r{revision}:{key}")


def fresh_entity_id(identity_data_id: UUID, revision: int, key: str) -> UUID:
    """A new reusable Entity, named by the resolution or variant key that targets it."""
    return uuid5(identity_data_id, f"entity:r{revision}:{key}")


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


class Reason(StrEnum):
    """Why a decision is withheld, as users see it: an input it read no
    longer validates, or is gone. Members are in increasing precedence."""

    CHANGED = "input_changed"
    REMOVED = "input_removed"


def stronger(a: StrEnum, b: StrEnum) -> StrEnum:
    """The member of the two that comes later in its enum's order."""
    order = list(type(a))
    return max(a, b, key=order.index)


def is_foreign(source: IdentitySource, key: str) -> bool:
    """Whether an input is another document's text, span or chunk, a corpus
    object or another source's saved record. Its drift withholds the
    decisions that cite it; it does not fail the source."""
    item = source.inputs[key]
    own = source.inputs[source.original_input_ref].data_id
    if isinstance(item, SourceTextInput):
        return item.data_id != own
    if isinstance(item, (ChunkInput, TextSpanInput)):
        return source.inputs[item.document_ref].data_id != own
    return isinstance(item, (CorpusObjectInput, SavedRecordInput))


def reusable_recipes(description):
    mentions = {g.entity_id for g in description.mention_groups.values()}
    return {
        eid: recipe
        for eid, recipe in description.entity_constructions.items()
        if eid not in mentions
    }


def referenced_corpus_ids(source):
    """Existing Entities that a record lists as a corpus input in its own
    input_refs. A group's input_refs do not count: only a decision that
    names the Entity may exempt it from derivation, so this is not
    `records.record_inputs`. `check_corpus_inputs_exist` proves each one is
    in the graph."""
    listed = set()
    for kind in REGISTRY.values():
        for record in getattr(source, kind.field).values():
            listed.update(record.input_refs)
    return {
        i.entity_id
        for key, i in source.inputs.items()
        if key in listed and isinstance(i, CorpusObjectInput)
    }


def checked_inputs(source: IdentitySource, withheld=frozenset()) -> set[str]:
    """The inputs to validate: the original text and the groups' own structure
    always, and every input a decision outside `withheld` cites. A text reached
    only as a span's or chunk's document is read, not digest-checked."""
    used = {source.original_input_ref}
    resolved = {d.group_ref for d in source.mention_resolutions.values()}
    for key, group in source.mention_groups.items():
        used.update([group.document_ref, *group.chunk_refs])
        if key not in resolved:
            used.update(group.input_refs)
    for key, inputs in record_inputs(source).items():
        if key not in withheld:
            used.update(inputs)
    return used


def cited_inputs(source: IdentitySource) -> set[str]:
    """Every input key the description cites: what `checked_inputs` checks
    with nothing withheld, and the documents of cited spans and chunks. An
    input outside it may be dropped."""
    cited = checked_inputs(source)
    for key in list(cited):
        document = getattr(source.inputs[key], "document_ref", None)
        if document:
            cited.add(document)
    return cited


def selected_digest(node, item: CorpusObjectInput) -> str | None:
    """The digest a corpus input pins, of its Entity's node as it is now:
    its selected fields' values. None when the node or a selected field is
    gone."""
    if node is None or any(f not in node for f in item.selected_fields):
        return None
    return object_digest({f: node[f] for f in item.selected_fields})


class Failure(NamedTuple):
    """Why one input fails: the code that fails the source when the input is
    its own, the reason that withholds decisions when it is foreign."""

    code: str
    reason: Reason
    message: str


async def input_failure(
    source, key, *, texts, chunks, mapping, graph, saved_record_reader
) -> Failure | None:
    """Check one input against the supplied texts and chunks, the graph or
    the saved-record reader. None when it validates."""
    item = source.inputs[key]
    document = getattr(item, "document_ref", None)
    text = texts.get(document if document else key)
    if isinstance(item, (SourceTextInput, ChunkInput, TextSpanInput)) and text is None:
        return Failure("source_changed", Reason.REMOVED, f"Text missing: {key}")
    if isinstance(item, SourceTextInput):
        if text_digest(text) != item.text_sha256:
            return Failure("source_changed", Reason.CHANGED, f"Text changed: {key}")
    elif isinstance(item, TextSpanInput):
        if (
            item.end > len(text)
            or text_digest(text[item.start : item.end]) != item.text_sha256
        ):
            return Failure(
                "input_changed", Reason.CHANGED, f"Span missing/changed: {key}"
            )
    elif isinstance(item, CorpusObjectInput):
        node = await graph.get_node(str(item.entity_id))
        if node is None:
            return Failure(
                "missing_reasoning_input",
                Reason.REMOVED,
                MISSING_INPUT.format(key),
            )
        if selected_digest(node, item) != item.content_sha256:
            return Failure(
                "input_changed", Reason.CHANGED, f"Corpus fields changed: {key}"
            )
    elif isinstance(item, SavedRecordInput):
        # withholding.record_reader: the cited source's row, the record under
        # its type and its fingerprint; the pinned revision is provenance only.
        if saved_record_reader is None:
            raise IntentError("unsupported_input", "A saved-record reader is required")
        if (found := saved_record_reader(item)) is not None:
            return Failure(
                "input_changed", found[0], f"Saved record changed or removed: {key}"
            )
    elif isinstance(item, ChunkInput):
        chunk = chunks.get(str(item.chunk_id))
        parent = source.inputs[item.document_ref]
        if (
            chunk is None
            or str(chunk.is_part_of.id) != str(parent.data_id)
            or item.end > len(text)
            or chunk.text != text[item.start : item.end]
        ):
            return Failure(
                "chunk_mapping",
                Reason.CHANGED,
                f"Chunk missing or mapping changed: {key}",
            )
        # Only the own document's chunks are all supplied, so only they are
        # checked against the ordered native tiling.
        if not is_foreign(source, key) and mapping.get(str(item.chunk_id)) != (
            item.start,
            item.end,
        ):
            return Failure(
                "chunk_mapping",
                Reason.CHANGED,
                f"Chunk range differs from ordered native mapping: {key}",
            )
    return None


async def validate_inputs(
    source: IdentitySource,
    *,
    texts: dict[str, str],
    chunks: dict[str, Any],
    graph,
    saved_record_reader=None,
    withheld=frozenset(),
) -> dict[str, Reason]:
    """Validate the source's own inputs and the inputs its decisions outside
    `withheld` consume. An own input that fails raises. A foreign input that
    fails is returned with its reason (`input_changed` or `input_removed`),
    so the caller withholds the decisions citing it instead of the source."""
    own_ref = source.original_input_ref
    own = source.inputs[own_ref]
    if own_ref not in texts or text_digest(texts[own_ref]) != own.text_sha256:
        raise IntentError("source_changed", f"Text missing/changed: {own_ref}")
    mapping = {}
    matching = [c for c in chunks.values() if str(c.is_part_of.id) == str(own.data_id)]
    if matching:
        mapping = map_chunks(texts[own_ref], matching)

    drift = {}
    for key in sorted(checked_inputs(source, withheld) - {own_ref}):
        failure = await input_failure(
            source,
            key,
            texts=texts,
            chunks=chunks,
            mapping=mapping,
            graph=graph,
            saved_record_reader=saved_record_reader,
        )
        if failure is None:
            continue
        if not is_foreign(source, key):
            raise IntentError(failure.code, failure.message)
        drift[key] = failure.reason

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
            scoped = texts.get(scope.document_ref)
            if scoped is not None and any(r.end > len(scoped) for r in scope.ranges):
                raise IntentError("scope_range", "Variant range outside document")
    return drift


def uses_of(saved) -> tuple[dict[UUID, tuple], set[UUID]]:
    """One saved description's or tombstone's mention UUIDs, each with the
    (identity source, group key) it belongs to, and its reusable UUIDs. A
    mention UUID of an earlier forgotten life has no key of its own."""
    if isinstance(saved, Tombstone):
        mentions = {
            e: (saved.identity_data_id, k) for e, k in saved.all_mention_ids.items()
        }
        return mentions, set(saved.all_reusable_ids)
    mentions = {
        g.entity_id: (saved.identity_data_id, k)
        for k, g in saved.mention_groups.items()
    }
    return mentions, set(saved.entity_constructions) - set(mentions)


def validate_uses(saved: list) -> None:
    """Build a transient UUID-use view of saved descriptions and tombstones;
    singleton declarations count as reusable. A tombstone keeps the mention
    and reusable UUIDs of every forgotten life of its source, which count
    too."""
    mentions, reusable = {}, set()
    for groups, declared in map(uses_of, saved):
        reusable.update(declared)
        for entity_id, identity in groups.items():
            if entity_id in mentions and mentions[entity_id] != identity:
                raise IntentError(
                    "incompatible_group", "Mention UUID belongs to another group"
                )
            mentions[entity_id] = identity
    if set(mentions) & reusable:
        raise IntentError(
            "incompatible_use", "UUID used as both mention and reusable Entity"
        )
