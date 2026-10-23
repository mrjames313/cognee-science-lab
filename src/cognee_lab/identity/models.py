from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Key = Annotated[str, Field(min_length=1)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Range(Strict):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("range must be nonempty [start,end)")
        return self


class Occurrence(Range):
    text: str = Field(min_length=1)


class SourceTextInput(Strict):
    kind: Literal["source_text"]
    dataset_id: UUID
    data_id: UUID
    text_sha256: Digest


class ChunkInput(Range):
    kind: Literal["chunk"]
    document_ref: Key
    chunk_id: UUID


class TextSpanInput(Range):
    kind: Literal["text_span"]
    document_ref: Key
    text_sha256: Digest


class CorpusObjectInput(Strict):
    kind: Literal["corpus_object"]
    dataset_id: UUID
    entity_id: UUID
    selected_fields: list[Key] = Field(min_length=1)
    content_sha256: Digest


class SavedRecordInput(Strict):
    kind: Literal["saved_record"]
    dataset_id: UUID
    identity_data_id: UUID
    record_id: Key
    representation_revision: int = Field(ge=1)
    content_sha256: Digest


Input = Annotated[
    Union[
        SourceTextInput, ChunkInput, TextSpanInput, CorpusObjectInput, SavedRecordInput
    ],
    Field(discriminator="kind"),
]


class Producer(Strict):
    method: Literal["rules", "llm", "decision_model", "captured_fixture"]
    implementation: Key
    version: Key
    configuration: dict[str, Any]
    run_id: str | None = None


class Recipe(Strict):
    name: str
    description: str


class Group(Strict):
    entity_id: UUID
    document_ref: Key
    occurrences: list[Occurrence] = Field(min_length=1)
    chunk_refs: list[Key] = Field(min_length=1)
    input_refs: list[Key] = Field(min_length=1)
    producer_ref: Key

    @model_validator(mode="after")
    def nonoverlapping(self):
        if any(b.start < a.end for a, b in zip(self.occurrences, self.occurrences[1:])):
            raise ValueError("occurrences must be sorted and nonoverlapping")
        return self


class DecisionBase(Strict):
    group_ref: Key
    input_refs: list[Key] = Field(min_length=1)
    producer_ref: Key
    explanation: str | None = None


class Accepted(DecisionBase):
    status: Literal["accepted"]
    target_entity_id: UUID


class Unresolved(DecisionBase):
    status: Literal["unresolved"]
    candidate_entity_ids: list[UUID] | None = None


class Ambiguous(DecisionBase):
    status: Literal["ambiguous"]
    candidate_entity_ids: list[UUID] | None = None


MentionResolution = Annotated[
    Union[Accepted, Unresolved, Ambiguous], Field(discriminator="status")
]


class CorpusScope(Strict):
    kind: Literal["corpus"]


class DocumentScope(Strict):
    kind: Literal["document"]
    document_ref: Key


class TextScope(Strict):
    kind: Literal["text_spans"]
    document_ref: Key
    ranges: list[Range] = Field(min_length=1)


Scope = Annotated[
    Union[CorpusScope, DocumentScope, TextScope], Field(discriminator="kind")
]


class Variant(Strict):
    status: Literal["accepted"]
    source_entity_id: UUID
    target_entity_id: UUID
    applicability: Scope
    input_refs: list[Key] = Field(min_length=1)
    producer_ref: Key
    explanation: str | None = None


class IdentitySource(Strict):
    kind: Literal["cognee_identity_source"]
    schema_version: Literal["0.1-draft"]
    dataset_id: UUID
    identity_data_id: UUID
    revision: int = Field(ge=1)
    original_input_ref: Key
    inputs: dict[Key, Input]
    producers: dict[Key, Producer]
    entity_constructions: dict[UUID, Recipe]
    mention_groups: dict[Key, Group]
    mention_resolutions: dict[Key, MentionResolution]
    variant_assignments: dict[Key, Variant]

    @model_validator(mode="after")
    def references(self):
        if not isinstance(self.inputs.get(self.original_input_ref), SourceTextInput):
            raise ValueError("original_input_ref must identify source_text")
        for item in self.inputs.values():
            if isinstance(item, (ChunkInput, TextSpanInput)) and not isinstance(
                self.inputs.get(item.document_ref), SourceTextInput
            ):
                raise ValueError("text/chunk document_ref must identify source_text")
        mention_ids = set()
        for group in self.mention_groups.values():
            if group.entity_id in mention_ids:
                raise ValueError("mention groups need distinct Entity UUIDs")
            mention_ids.add(group.entity_id)
            if group.document_ref != self.original_input_ref:
                raise ValueError("initial local groups belong to the original document")
            if group.entity_id not in self.entity_constructions:
                raise ValueError("missing mention construction recipe")
            chunks = [self.inputs.get(k) for k in group.chunk_refs]
            if any(
                not isinstance(c, ChunkInput) or c.document_ref != group.document_ref
                for c in chunks
            ):
                raise ValueError("group chunk_refs must identify original chunks")
            for occurrence in group.occurrences:
                intervals = sorted(
                    (max(c.start, occurrence.start), min(c.end, occurrence.end))
                    for c in chunks
                    if c.start < occurrence.end and c.end > occurrence.start
                )
                cursor = occurrence.start
                for a, b in intervals:
                    if a > cursor:
                        break
                    cursor = max(cursor, b)
                if cursor < occurrence.end:
                    raise ValueError("chunk mappings must cover each occurrence")
        assigned = set()
        if set(self.mention_resolutions) & set(self.variant_assignments):
            raise ValueError("assignment IDs must be unique within source")
        for decision in self.mention_resolutions.values():
            if (
                decision.group_ref not in self.mention_groups
                or decision.group_ref in assigned
            ):
                raise ValueError(
                    "unknown group or competing current resolution records"
                )
            assigned.add(decision.group_ref)
            if isinstance(decision, Accepted):
                if (
                    decision.target_entity_id in mention_ids
                    or decision.target_entity_id not in self.entity_constructions
                ):
                    raise ValueError(
                        "accepted mention target needs reusable endpoint recipe"
                    )
        for variant in self.variant_assignments.values():
            endpoints = (variant.source_entity_id, variant.target_entity_id)
            if endpoints[0] == endpoints[1] or any(
                e in mention_ids or e not in self.entity_constructions
                for e in endpoints
            ):
                raise ValueError("variant endpoints need distinct reusable recipes")
            if isinstance(
                variant.applicability, (DocumentScope, TextScope)
            ) and not isinstance(
                self.inputs.get(variant.applicability.document_ref), SourceTextInput
            ):
                raise ValueError("variant scope must identify source text")
        for record in (
            list(self.mention_groups.values())
            + list(self.mention_resolutions.values())
            + list(self.variant_assignments.values())
        ):
            if record.producer_ref not in self.producers or any(
                k not in self.inputs for k in record.input_refs
            ):
                raise ValueError("unknown producer/input reference")
        return self


class Tombstone(Strict):
    """What a forgotten source's row keeps: identifiers, digests, its last
    revision and when it was forgotten, never content. `mention_ids` and
    `entity_ids` are the last revision's mention and reusable Entity UUIDs,
    which a re-add may not use again. `removed_entity_ids` are the Entities
    the forget removed; a dependent still citing one of them, or the
    document, has not been revised yet. `impact_token` is the confirmed
    impact on other sources, None when the forget affected none."""

    kind: Literal["identity_source_tombstone"]
    dataset_id: UUID
    identity_data_id: UUID
    original_data_id: UUID
    revision: int = Field(ge=1)
    text_sha256: Digest
    description_sha256: Digest
    mention_ids: dict[Key, UUID]
    entity_ids: list[UUID]
    removed_entity_ids: list[UUID]
    impact_token: Digest | None
    forgotten_at: str

    @classmethod
    def of(
        cls,
        source: IdentitySource,
        *,
        forgotten_at: str,
        removed_entity_ids=(),
        impact_token: str | None = None,
    ) -> Tombstone:
        from hashlib import sha256

        doc = source.inputs[source.original_input_ref]
        mentions = {k: g.entity_id for k, g in source.mention_groups.items()}
        return cls(
            kind="identity_source_tombstone",
            dataset_id=source.dataset_id,
            identity_data_id=source.identity_data_id,
            original_data_id=doc.data_id,
            revision=source.revision,
            text_sha256=doc.text_sha256,
            description_sha256=sha256(
                source.model_dump_json().encode("utf-8")
            ).hexdigest(),
            mention_ids=mentions,
            entity_ids=sorted(
                set(source.entity_constructions) - set(mentions.values()), key=str
            ),
            removed_entity_ids=sorted(set(removed_entity_ids), key=str),
            impact_token=impact_token,
            forgotten_at=forgotten_at,
        )

    @property
    def used_entity_ids(self) -> frozenset[UUID]:
        return frozenset(self.mention_ids.values()) | frozenset(self.entity_ids)
