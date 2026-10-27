"""How each search mode delivers the facts retrieval found: semantic keeps
the first supporting source's evidence, source-aware keeps every
supporting document's evidence with its chunk range and lists the facts by
document."""

from cognee_lab.identity.delivery import (
    Evidence,
    Fact,
    Support,
    semantic,
    source_aware,
)

OCCURRENCES = [
    dict(start=49, end=63, text="The controller"),
    dict(start=86, end=88, text="it"),
]
IDENTITY = dict(
    state="accepted",
    target_entity_id="hc",
    occurrences=OCCURRENCES,
    identity_data_id="id-a",
    assignment_id="r01",
)


def chunk(name, index, start, end):
    return Evidence(
        chunk_id=name, chunk_index=index, text=f"text {name}", start=start, end=end
    )


def support(document, evidence, identity=None):
    return Support(
        document_id=document,
        name=f"name {document}",
        identity_data_id=f"id-{document}",
        evidence=evidence,
        identity=identity,
    )


def fact(edge, score, *supports):
    return Fact(
        edge_id=edge,
        source_id=f"{edge}-subject",
        target_id=f"{edge}-target",
        relationship="limits",
        text=f"{edge} limits oscillations",
        score=score,
        supports={s.document_id: s for s in supports},
    )


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
        support("a", [chunk("a0", 0, 0, 145), chunk("a1", 1, 145, 300)], IDENTITY),
        support("b", [chunk("b0", 0, 0, 158), chunk("b0", 0, 0, 158)]),
    )


def test_a_fact_two_documents_support_is_listed_under_both():
    found = source_aware([two_documents()], 5)
    (entry,) = found["facts"]
    assert entry["evidence"] == [
        cited("a", "a0", 0, 0, 145),
        cited("a", "a1", 1, 145, 300),
        cited("b", "b0", 0, 0, 158),
    ]
    assert entry["identity"] == IDENTITY
    assert found["documents"] == [
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


def test_semantic_keeps_the_first_supporting_source_and_no_ranges():
    assert semantic([two_documents()], 5) == dict(
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
        ]
    )


def test_semantic_keeps_evidence_rows_as_read():
    plain = fact("e1", 0, support("b", [chunk("b0", 0, 0, 9), chunk("b0", 0, 0, 9)]))
    (entry,) = semantic([plain], 5)["facts"]
    assert entry["evidence"] == [cited("b", "b0", 0)] * 2
    assert "identity" not in entry


def test_limit_picks_the_top_facts_and_documents_follow_them():
    facts = [
        fact("e3", 1, support("c", [chunk("c0", 0, 0, 10)])),
        fact("e2", 3, support("b", [chunk("b0", 0, 0, 10)])),
        fact("e4", 0, support("d", [chunk("d0", 0, 0, 10)])),
        fact(
            "e1",
            1,
            support("c", [chunk("c1", 1, 10, 20)]),
            support("a", [chunk("a0", 0, 0, 10)]),
        ),
    ]
    found = source_aware(facts, 3)
    assert [f["edge_id"] for f in found["facts"]] == ["e2", "e1", "e3"]
    assert [
        (d["document_id"], [f["edge_id"] for f in d["facts"]])
        for d in found["documents"]
    ] == [("b", ["e2"]), ("a", ["e1"]), ("c", ["e1", "e3"])]
    assert [f["edge_id"] for f in semantic(facts, 3)["facts"]] == ["e2", "e1", "e3"]


def test_nothing_found_is_no_fact_and_no_document():
    assert source_aware([], 5) == dict(facts=[], documents=[])
    assert semantic([], 5) == dict(facts=[])
