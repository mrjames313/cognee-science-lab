"""The one dependency predicate: the inputs through which a reader reads a
document, an Entity or a source's saved records. Forget's erasure, a text
edit's withholding and the retiring-source fence all decide dependency
here, each with its own target; nothing here knows which of them asks."""

from typing import NamedTuple
from uuid import UUID

from .models import (
    ChunkInput,
    CorpusObjectInput,
    SavedRecordInput,
    SourceTextInput,
    TextSpanInput,
)


class Target(NamedTuple):
    """What a reader may depend on: a document, by its Data UUID, Entities,
    and the saved records of identity sources, by their identity UUIDs. A
    text edit's withholding names only the document: its citers' saved-record
    inputs are not what the edit changed."""

    document: UUID
    entities: frozenset[UUID] = frozenset()
    sources: frozenset[UUID] = frozenset()


class Citation(NamedTuple):
    """One input through which a reader reads a target: its key, its kind
    and the document, Entity or identity source UUID it consumes."""

    input_ref: str
    kind: str
    consumed: str


def citations(reader, target: Target) -> dict[str, Citation]:
    """The reader's inputs, by key, that read the target's document (its
    text, or a span or chunk of it), one of its Entities or a saved record
    of one of its sources. Text inputs and saved records of another dataset
    are not admitted, so the reader's own dataset names the target's."""
    texts = {
        k
        for k, i in reader.inputs.items()
        if isinstance(i, SourceTextInput)
        and (i.dataset_id, i.data_id) == (reader.dataset_id, target.document)
    }
    found = {}
    for key, item in sorted(reader.inputs.items()):
        if key in texts or (
            isinstance(item, (ChunkInput, TextSpanInput)) and item.document_ref in texts
        ):
            found[key] = Citation(key, item.kind, str(target.document))
        elif isinstance(item, CorpusObjectInput) and item.entity_id in target.entities:
            found[key] = Citation(key, item.kind, str(item.entity_id))
        elif (
            isinstance(item, SavedRecordInput)
            and item.identity_data_id in target.sources
        ):
            found[key] = Citation(key, item.kind, str(item.identity_data_id))
    return found
