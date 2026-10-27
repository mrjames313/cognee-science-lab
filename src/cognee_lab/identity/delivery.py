"""The facts `retrieve` found and how a search mode delivers them. `retrieve`
collects each fact once, with one Support per served original document
that supports it; `semantic` turns that into the result's `facts`."""

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


@dataclass(frozen=True)
class Support:
    """One served source's checked support for a fact: evidence from the
    source's own original only, and its identity record when the source's
    mention group covers the fact."""

    document_id: str
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

    def entry(self, supports):
        entry = dict(
            edge_id=self.edge_id,
            source_id=self.source_id,
            target_id=self.target_id,
            relationship=self.relationship,
            text=self.text,
            evidence=[
                dict(
                    data_id=support.document_id,
                    chunk_id=e.chunk_id,
                    chunk_index=e.chunk_index,
                    text=e.text,
                )
                for support in supports
                for e in support.evidence
            ],
            score=self.score,
        )
        if supports[0].identity is not None:
            entry["identity"] = supports[0].identity
        return entry


def ranked(facts: list[Fact], limit: int) -> list[Fact]:
    return sorted(facts, key=lambda f: (-f.score, f.edge_id))[:limit]


def semantic(facts: list[Fact], limit: int) -> dict:
    """Each fact with the evidence of the first source that supports it."""
    return dict(
        facts=[f.entry(list(f.supports.values())[:1]) for f in ranked(facts, limit)]
    )
