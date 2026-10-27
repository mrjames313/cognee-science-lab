"""How each search mode delivers the facts retrieval found: semantic keeps
the first supporting source's evidence, source-aware keeps every
supporting document's evidence with its chunk range and lists the facts by
document."""

from cognee_lab.identity.delivery import (
    Evidence,
    Fact,
    Found,
    Mention,
    Support,
    documents_of,
    semantic,
    source_aware,
)
from cognee_lab.identity.models import Occurrence

OCCURRENCES = [
    dict(start=49, end=63, text="The controller"),
    dict(start=86, end=88, text="it"),
]
MENTION = Mention(
    target_entity_id="hc",
    occurrences=tuple(Occurrence(**o) for o in OCCURRENCES),
    assignment_id="r01",
)
IDENTITY = dict(
    state="accepted",
    target_entity_id="hc",
    occurrences=OCCURRENCES,
    identity_data_id="id-a",
    assignment_id="r01",
)
REPORT = dict(identity_work=1, unavailable_sources=[])


def chunk(name, index, start, end):
    return Evidence(
        chunk_id=name, chunk_index=index, text=f"text {name}", start=start, end=end
    )


def support(document, evidence, mention=None):
    return Support(
        document_id=document,
        identity_data_id=f"id-{document}",
        evidence=tuple(evidence),
        mention=mention,
    )


def fact(edge, score, first, *more):
    return Fact(
        edge_id=edge,
        source_id=f"{edge}-subject",
        target_id=f"{edge}-target",
        relationship="limits",
        text=f"{edge} limits oscillations",
        score=score,
        first=first,
        more=more,
    )


def found(*facts):
    return Found(facts=facts, report=REPORT)


def names(found, limit=5):
    return {d: f"name {d}" for d in documents_of(found, limit)}


def cited(document, name, index, start=None, end=None):
    found = dict(
        data_id=document, chunk_id=name, chunk_index=index, text=f"text {name}"
    )
    if start is not None:
        found.update(start=start, end=end)
    return found


def two_documents():
    """One fact that a mention of document a and a plain fact of document b
    support, with a's first chunk read twice."""
    return fact(
        "e1",
        1,
        support("a", [chunk("a0", 0, 0, 145), chunk("a1", 1, 145, 300)], MENTION),
        support("b", [chunk("b0", 0, 0, 158), chunk("b0", 0, 0, 158)]),
    )


def test_a_fact_two_documents_support_is_listed_under_both():
    both = found(two_documents())
    result = source_aware(both, names(both), 5)
    (entry,) = result["facts"]
    assert entry["evidence"] == [
        cited("a", "a0", 0, 0, 145),
        cited("a", "a1", 1, 145, 300),
        cited("b", "b0", 0, 0, 158),
    ]
    assert entry["identity"] == IDENTITY
    assert result["documents"] == [
        dict(
            document_id="a",
            name="name a",
            identity_data_id="id-a",
            facts=[
                dict(
                    edge_id="e1",
                    spans=[
                        dict(
                            kind="occurrence", start=49, end=63, text="The controller"
                        ),
                        dict(kind="occurrence", start=86, end=88, text="it"),
                        dict(kind="evidence_chunk", chunk_id="a0", start=0, end=145),
                        dict(kind="evidence_chunk", chunk_id="a1", start=145, end=300),
                    ],
                )
            ],
        ),
        dict(
            document_id="b",
            name="name b",
            identity_data_id="id-b",
            facts=[
                dict(
                    edge_id="e1",
                    spans=[
                        dict(kind="evidence_chunk", chunk_id="b0", start=0, end=158)
                    ],
                )
            ],
        ),
    ]
    assert {k: result[k] for k in REPORT} == REPORT


def test_semantic_keeps_the_first_supporting_source_and_no_ranges():
    assert semantic(found(two_documents()), 5) == dict(
        facts=[
            dict(
                edge_id="e1",
                source_id="e1-subject",
                target_id="e1-target",
                relationship="limits",
                text="e1 limits oscillations",
                evidence=[cited("a", "a0", 0), cited("a", "a1", 1)],
                score=1,
                identity=IDENTITY,
            )
        ],
        **REPORT,
    )


def test_semantic_keeps_evidence_rows_as_read():
    plain = fact("e1", 0, support("b", [chunk("b0", 0, 0, 9), chunk("b0", 0, 0, 9)]))
    (entry,) = semantic(found(plain), 5)["facts"]
    assert entry["evidence"] == [cited("b", "b0", 0)] * 2
    assert "identity" not in entry


def test_limit_picks_the_top_facts_and_documents_follow_them():
    facts = found(
        fact("e3", 1, support("c", [chunk("c0", 0, 0, 10)])),
        fact("e2", 3, support("b", [chunk("b0", 0, 0, 10)])),
        fact("e4", 0, support("d", [chunk("d0", 0, 0, 10)])),
        fact(
            "e1",
            1,
            support("c", [chunk("c1", 1, 10, 20)]),
            support("a", [chunk("a0", 0, 0, 10)]),
        ),
    )
    assert documents_of(facts, 3) == {"a", "b", "c"}
    result = source_aware(facts, names(facts, 3), 3)
    assert [f["edge_id"] for f in result["facts"]] == ["e2", "e1", "e3"]
    assert [
        (d["document_id"], d["name"], [f["edge_id"] for f in d["facts"]])
        for d in result["documents"]
    ] == [
        ("b", "name b", ["e2"]),
        ("a", "name a", ["e1"]),
        ("c", "name c", ["e1", "e3"]),
    ]
    assert [f["edge_id"] for f in semantic(facts, 3)["facts"]] == ["e2", "e1", "e3"]


def test_nothing_found_is_no_fact_and_no_document():
    assert documents_of(found(), 5) == set()
    assert source_aware(found(), {}, 5) == dict(facts=[], documents=[], **REPORT)
    assert semantic(found(), 5) == dict(facts=[], **REPORT)
