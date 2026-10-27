"""The facts `retrieve` found and how a search mode delivers them. `retrieve`
collects each fact once, with one Support per served original document
that supports it; `semantic` and `source_aware` turn that into the result's
`facts`, and `source_aware` adds `documents`. Nothing here reads a store:
settled.py reads what a delivery needs and picks the delivery by mode."""

from dataclasses import dataclass, replace

from .models import Occurrence

LIMIT = 5


@dataclass(frozen=True)
class Evidence:
    """A checked evidence chunk, with its range in the document from the
    source's ChunkInput, which map_chunks checks after every text change."""

    chunk_id: str
    chunk_index: int
    text: str
    start: int
    end: int

    def cited(self, document_id) -> dict:
        return dict(
            data_id=document_id,
            chunk_id=self.chunk_id,
            chunk_index=self.chunk_index,
            text=self.text,
        )


@dataclass(frozen=True)
class Mention:
    """The accepted resolution of the source's mention group that covers a
    fact."""

    target_entity_id: str
    occurrences: tuple[Occurrence, ...]
    assignment_id: str


@dataclass(frozen=True)
class Support:
    """One served source's checked support for a fact: evidence from the
    source's own original only, and the mention when the source's mention
    group covers the fact. A fact holds one support per document_id, which
    assumes one served source per original: every builder gives each source
    its own original, and nothing enforces it."""

    document_id: str
    identity_data_id: str
    evidence: tuple[Evidence, ...]
    mention: Mention | None = None

    def identity(self) -> dict:
        return dict(
            state="accepted",
            target_entity_id=self.mention.target_entity_id,
            occurrences=[o.model_dump() for o in self.mention.occurrences],
            identity_data_id=self.identity_data_id,
            assignment_id=self.mention.assignment_id,
        )


@dataclass(frozen=True)
class Fact:
    """A fact (edge) with the support of the first source the traversal
    found it in, and the supports of later sources in found order."""

    edge_id: str
    source_id: str
    target_id: str
    relationship: str
    text: str
    score: int
    first: Support
    more: tuple[Support, ...] = ()

    @property
    def supports(self) -> tuple[Support, ...]:
        return (self.first, *self.more)

    def supported(self, support: Support) -> "Fact":
        return replace(self, more=(*self.more, support))

    def entry(self, evidence: list[dict]) -> dict:
        """The result's fact, with the identity record of the first support."""
        entry = dict(
            edge_id=self.edge_id,
            source_id=self.source_id,
            target_id=self.target_id,
            relationship=self.relationship,
            text=self.text,
            evidence=evidence,
            score=self.score,
        )
        if self.first.mention is not None:
            entry["identity"] = self.first.identity()
        return entry


@dataclass(frozen=True)
class Found:
    """One read: each fact once, in found order, and what the read reports
    beside its facts, which every delivery passes through after them."""

    facts: tuple[Fact, ...]
    report: dict


def ranked(found: Found, limit: int) -> list[Fact]:
    return sorted(found.facts, key=lambda f: (-f.score, f.edge_id))[:limit]


def documents_of(found: Found, limit: int) -> set[str]:
    """The documents that support the facts a delivery returns."""
    return {s.document_id for f in ranked(found, limit) for s in f.supports}


def semantic(found: Found, limit: int = LIMIT) -> dict:
    """Each fact with the evidence of the first source that supports it."""
    return dict(
        facts=[
            f.entry([e.cited(f.first.document_id) for e in f.first.evidence])
            for f in ranked(found, limit)
        ],
        **found.report,
    )


def spans(support: Support) -> list[dict]:
    """The occurrences of the covering mention group, else each evidence
    chunk's range: no fact writer records where a sentence sits in a chunk."""
    if support.mention is not None:
        return [
            dict(kind="occurrence", **o.model_dump())
            for o in support.mention.occurrences
        ]
    chunks = {
        e.chunk_id: dict(
            kind="evidence_chunk", chunk_id=e.chunk_id, start=e.start, end=e.end
        )
        for e in support.evidence
    }
    return list(chunks.values())


def union(fact: Fact) -> list[dict]:
    """The evidence of every support, once per (data_id, chunk_id), with its
    chunk range. Supports keep their found order and each support its read
    order; a repeated chunk keeps the place of its first read."""
    found = {}
    for support in fact.supports:
        for e in support.evidence:
            found.setdefault(
                (support.document_id, e.chunk_id),
                dict(e.cited(support.document_id), start=e.start, end=e.end),
            )
    return list(found.values())


def source_aware(found: Found, names: dict, limit: int = LIMIT) -> dict:
    """Each fact with the evidence of every document that supports it, and
    `documents`: the returned facts by supporting document, a document
    placed by its best fact, then by document_id. `names` holds the Data
    name of each document in documents_of(found, limit)."""
    top = ranked(found, limit)
    documents = {}
    for fact in top:
        for support in sorted(fact.supports, key=lambda s: s.document_id):
            document = documents.setdefault(
                support.document_id,
                dict(
                    document_id=support.document_id,
                    name=names.get(support.document_id),
                    identity_data_id=support.identity_data_id,
                    facts=[],
                ),
            )
            document["facts"].append(dict(edge_id=fact.edge_id, spans=spans(support)))
    return dict(
        facts=[f.entry(union(f)) for f in top],
        documents=list(documents.values()),
        **found.report,
    )
