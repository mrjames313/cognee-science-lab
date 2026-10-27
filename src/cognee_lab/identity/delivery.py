"""The facts `retrieve` found and how a search mode delivers them. `retrieve`
collects each fact once, with one Support per served original document
that supports it; `semantic` and `source_aware` turn that into the result's
`facts`, and `source_aware` adds `documents`."""

from dataclasses import dataclass, field


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
class Support:
    """One served source's checked support for a fact: evidence from the
    source's own original only, and its identity record when the source's
    mention group covers the fact."""

    document_id: str
    name: str | None
    identity_data_id: str
    evidence: list[Evidence]
    identity: dict | None = None


@dataclass
class Fact:
    """A fact (edge) and its supports by document_id, in the order the
    traversal found them."""

    edge_id: str
    source_id: str
    target_id: str
    relationship: str
    text: str
    score: int
    supports: dict[str, Support] = field(default_factory=dict)

    @property
    def first(self) -> Support:
        return next(iter(self.supports.values()))

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
        if self.first.identity is not None:
            entry["identity"] = self.first.identity
        return entry


def ranked(facts: list[Fact], limit: int) -> list[Fact]:
    return sorted(facts, key=lambda f: (-f.score, f.edge_id))[:limit]


def semantic(facts: list[Fact], limit: int) -> dict:
    """Each fact with the evidence of the first source that supports it."""
    return dict(
        facts=[
            f.entry([e.cited(f.first.document_id) for e in f.first.evidence])
            for f in ranked(facts, limit)
        ]
    )


def spans(support: Support) -> list[dict]:
    """The occurrences of the covering mention group, else each evidence
    chunk's range: no fact writer records where a sentence sits in a chunk."""
    if support.identity is not None:
        return [dict(kind="occurrence", **o) for o in support.identity["occurrences"]]
    chunks = {
        e.chunk_id: dict(
            kind="evidence_chunk", chunk_id=e.chunk_id, start=e.start, end=e.end
        )
        for e in support.evidence
    }
    return list(chunks.values())


def union(fact: Fact) -> list[dict]:
    """The evidence of every support, once per (data_id, chunk_id), with its
    chunk range."""
    found = {}
    for support in fact.supports.values():
        for e in support.evidence:
            found.setdefault(
                (support.document_id, e.chunk_id),
                dict(e.cited(support.document_id), start=e.start, end=e.end),
            )
    return list(found.values())


def source_aware(facts: list[Fact], limit: int) -> dict:
    """Each fact with the evidence of every document that supports it, and
    `documents`: the returned facts by supporting document, a document
    placed by its best fact, then by document_id."""
    top = ranked(facts, limit)
    documents = {}
    for fact in top:
        for document_id, support in sorted(fact.supports.items()):
            document = documents.setdefault(
                document_id,
                dict(
                    document_id=document_id,
                    name=support.name,
                    identity_data_id=support.identity_data_id,
                    facts=[],
                ),
            )
            document["facts"].append(dict(edge_id=fact.edge_id, spans=spans(support)))
    return dict(
        facts=[f.entry(union(f)) for f in top],
        documents=list(documents.values()),
    )
