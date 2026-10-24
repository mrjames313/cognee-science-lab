"""Checkpoint K: readers of a changed or retired Entity or record.

An outside edit of an Entity, the review of a decision by input kind, the
reviewer's answer to a removed citation, and the refusals `record_key_reused`
and `mention_input`.
"""

import asyncio
import dataclasses
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from cascade_worlds import cascade_rows
from chain_worlds import described, identity, record_key, row_of, world_rows
from cognee_lab.identity import chains, entity_edit, erasure, review
from cognee_lab.identity.admission import check_mention_inputs, mention_ids
from cognee_lab.identity.digests import object_digest
from cognee_lab.identity.kind_change import HC_ID
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.records import RemovedRecord, names_record, saved_records
from cognee_lab.identity.retirement import source_ids
from cognee_lab.identity.validation import (
    IntentError,
    Reason,
    input_failure,
    selected_digest,
)
from cognee_lab.identity.withholding import Status, Withheld
from test_identity_dependencies import glossary_doc01

CHAIN = {"s0": frozenset(), "s1": frozenset({"s0"})}


class Graph:
    """Nodes by ID; update_node merges a patch, as Cognee's adapter does."""

    def __init__(self, nodes):
        self.nodes = {k: dict(v) for k, v in nodes.items()}

    async def get_node(self, key):
        node = self.nodes.get(key)
        return dict(node) if node is not None else None

    async def update_node(self, key, values):
        if key not in self.nodes:
            return False
        self.nodes[key].update(values)
        return True


HELIOS_FIELDS = dict(name="Helios controller", description="Reusable controller.")


def s1(state="ok"):
    """s1 of the chain worlds, its Entity input selecting the name and the
    description, as the glossary fixture's existing_A does."""
    payload = json.loads(described("s1", CHAIN["s1"], state).model_dump_json())
    payload["inputs"]["existing_A"].update(
        selected_fields=list(HELIOS_FIELDS),
        content_sha256=object_digest(HELIOS_FIELDS),
    )
    return IdentitySource.model_validate_json(json.dumps(payload))


def helios(source):
    return str(source.inputs["existing_A"].entity_id)


def graph_of(source, **fields):
    node = dict(id=helios(source), type="Entity", **HELIOS_FIELDS)
    node.update(fields)
    return Graph({helios(source): node})


def corpus_failure(source, graph):
    return asyncio.run(
        input_failure(
            source,
            "existing_A",
            texts={},
            chunks={},
            mapping={},
            graph=graph,
            saved_record_reader=None,
        )
    )


def test_an_outside_edit_of_a_selected_field_changes_the_corpus_input(tmp_path):
    source = s1()
    graph = graph_of(source)
    assert corpus_failure(source, graph) is None
    publisher = SimpleNamespace(graph=graph)
    edited = asyncio.run(
        entity_edit.edit_entity(publisher, tmp_path, source, "unselected")
    )["entity_edit"]
    assert (
        edited["before_sha256"]
        == edited["after_sha256"]
        == source.inputs["existing_A"].content_sha256
    )
    assert corpus_failure(source, graph) is None
    edited = asyncio.run(
        entity_edit.edit_entity(publisher, tmp_path, source, "description")
    )["entity_edit"]
    assert edited["after_sha256"] != edited["before_sha256"]
    assert corpus_failure(source, graph).reason == Reason.CHANGED
    asyncio.run(entity_edit.edit_entity(publisher, tmp_path, source, "revert"))
    assert corpus_failure(source, graph) is None


def test_edit_entity_refuses_a_field_the_entity_lacks_and_saves_nothing(tmp_path):
    source = s1()
    graph = graph_of(source)
    graph.nodes[helios(source)].pop("description")
    publisher = SimpleNamespace(graph=graph)
    with pytest.raises(IntentError) as refused:
        asyncio.run(entity_edit.edit_entity(publisher, tmp_path, source, "description"))
    assert refused.value.code == "fixture_scope"
    assert not (tmp_path / entity_edit.ORIGINAL).exists()
    assert "description" not in graph.nodes[helios(source)]


def test_edit_entity_finds_the_entity_input_by_its_entity(tmp_path):
    """After a re-confirm the input that reads the Entity has another key."""
    payload = json.loads(s1().model_dump_json())
    payload["inputs"]["read_again"] = payload["inputs"].pop("existing_A")
    for record in (
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ):
        record["input_refs"] = [
            "read_again" if k == "existing_A" else k for k in record["input_refs"]
        ]
    source = IdentitySource.model_validate_json(json.dumps(payload))
    graph = graph_of(s1())
    edited = asyncio.run(
        entity_edit.edit_entity(
            SimpleNamespace(graph=graph), tmp_path, source, "description"
        )
    )["entity_edit"]
    assert edited["input_ref"] == "read_again"
    assert edited["after_sha256"] != edited["pinned_sha256"]


def test_edit_entity_refuses_the_native_columns_and_a_revert_with_no_edit(tmp_path):
    source = s1()
    graph = graph_of(source)
    for field in ("id", "name", "type"):
        with pytest.raises(IntentError) as refused:
            asyncio.run(entity_edit.update_entity(graph, helios(source), {field: "x"}))
        assert refused.value.code == "entity_field_protected"
    with pytest.raises(IntentError) as refused:
        asyncio.run(
            entity_edit.edit_entity(
                SimpleNamespace(graph=graph), tmp_path, source, "revert"
            )
        )
    assert refused.value.code == "fixture_scope"


def test_a_removed_corpus_node_is_input_removed_and_never_reconfirmed():
    source = s1()
    assert corpus_failure(source, Graph({})).reason == Reason.REMOVED
    entry = Withheld(Reason.REMOVED, Status.REFRESH_NEEDED, frozenset(["existing_A"]))
    with pytest.raises(IntentError) as refused:
        review.refuse_command(source, entry, "reconfirm")
    assert refused.value.code == "input_removed"
    assert "replace the decision" in str(refused.value)
    cited = Withheld(Reason.REMOVED, Status.REFRESH_NEEDED, frozenset(["rec_s0"]))
    with pytest.raises(IntentError) as refused:
        review.refuse_command(source, cited, "reconfirm")
    assert "replace-citation" in str(refused.value)
    review.refuse_command(source, cited, "replace-citation")
    with pytest.raises(IntentError) as refused:
        review.refuse_command(source, cited, "replace-decision")
    assert "replaced with replace-citation" in str(refused.value)
    with pytest.raises(IntentError) as refused:
        review.refuse_command(source, entry, "replace-citation")
    assert refused.value.code == "fixture_scope"


def reviewed(monkeypatch, tmp_path, source, entry, decision, *, command, **options):
    """The revision `review.review` writes for one withheld decision. The
    ledger rows (`rows`), the graph (`graph`) and the registered texts
    (`texts`) stand in for the stores; the withheld set holds `entry`."""
    rows, written = options.pop("rows", []), []

    async def read_rows(dataset=None):
        return rows

    async def withheld(publisher, rows):
        return {str(source.identity_data_id): {decision: entry}}

    async def current(*args):
        return None

    async def replaced(publisher, intended, **guards):
        written.append(intended)

    async def texts(source, known=None):
        return options.get("texts", {})

    monkeypatch.setattr(review, "withheld_now", withheld)
    monkeypatch.setattr(review, "expect_current", current)
    monkeypatch.setattr(review, "replace_one", replaced)
    monkeypatch.setattr(review, "read_texts", texts)
    publisher = SimpleNamespace(
        records=SimpleNamespace(rows=read_rows), graph=options.get("graph")
    )
    asyncio.run(
        review.review(
            publisher,
            tmp_path,
            "doc01",
            source,
            decision,
            command=command,
            expected_revision=source.revision,
            fault_stage=None,
            **options.get("cite", {}),
        )
    )
    (intended,) = written
    return intended


REMOVED_ENTITY = Withheld(
    Reason.REMOVED, Status.REFRESH_NEEDED, frozenset(["existing_A"])
)


def test_replace_decision_strips_a_removed_corpus_input(monkeypatch, tmp_path):
    """The Entity a decision read is gone (Cognee or another writer deleted
    it outside forget): the replacement leaves the resolution unresolved
    without it and drops the variant, as an erasure would."""
    source = s1()
    rows, _ = world_rows(CHAIN, dict(s0="ok", s1="ok"))
    options = dict(graph=Graph({}), rows=rows, command="replace-decision")
    d = reviewed(monkeypatch, tmp_path, source, REMOVED_ENTITY, "d", **options)
    resolution = d.mention_resolutions["d"]
    assert (resolution.status, resolution.producer_ref) == ("unresolved", "review_d_r2")
    assert "existing_A" not in resolution.input_refs
    assert resolution.explanation == (
        "An input it read went (existing_A); its group is left unresolved."
    )
    # The variant still cites the Entity, so its input stays.
    assert "existing_A" in d.variant_assignments["v"].input_refs
    v = reviewed(monkeypatch, tmp_path, source, REMOVED_ENTITY, "v", **options)
    assert "v" not in v.variant_assignments
    assert v.mention_resolutions == source.mention_resolutions
    # Only the variant named HC, so its recipe goes with it.
    assert UUID(HC_ID) not in v.entity_constructions
    assert UUID(helios(source)) in v.entity_constructions


def test_a_dropped_variant_names_no_input_it_drops(
    monkeypatch, tmp_path, source_payload
):
    """v01 reads the glossary span, which went, and the Entity, which
    changed. The variant goes, so the new read of the Entity goes with it:
    the producer names its old digests and no new one, and HC's recipe,
    which only v01 named, goes as an erasure drops it."""
    doc01 = glossary_doc01(source_payload)
    graph = Graph({helios(doc01): dict(HELIOS_FIELDS, description="Edited.")})
    entry = Withheld(
        Reason.REMOVED, Status.REFRESH_NEEDED, frozenset(["glossary_hc", "existing_A"])
    )
    options = dict(graph=graph, command="replace-decision")
    v = reviewed(monkeypatch, tmp_path, doc01, entry, "v01", **options)
    assert "v01" not in v.variant_assignments and "existing_A_r2" not in v.inputs
    digests = v.producers["review_v01_r2"].configuration
    assert set(digests["old_digests"]) == {"existing_A", "glossary_hc"}
    assert digests["new_digests"] == {}
    assert UUID(HC_ID) not in v.entity_constructions
    assert UUID(helios(doc01)) in v.entity_constructions
    r01 = reviewed(monkeypatch, tmp_path, doc01, entry, "r01", **options)
    assert r01.mention_resolutions["r01"].explanation == (
        "An input it read changed or went (existing_A, glossary_hc);"
        " its group is left unresolved."
    )
    # Another source reads HC as a corpus object, so its recipe stays.
    payload = json.loads(described("s0", frozenset()).model_dump_json())
    payload["inputs"]["existing_A"]["entity_id"] = HC_ID
    reader = row_of(IdentitySource.model_validate_json(json.dumps(payload)), "ok")
    v = reviewed(monkeypatch, tmp_path, doc01, entry, "v01", rows=[reader], **options)
    assert UUID(HC_ID) in v.entity_constructions


def test_replace_decision_strips_a_removed_glossary_span(
    monkeypatch, tmp_path, source_payload
):
    """The glossary document doc01 reads is gone, so its HC span is
    removed: r01 is left unresolved without it."""
    doc01 = glossary_doc01(source_payload)
    entry = Withheld(Reason.REMOVED, Status.REFRESH_NEEDED, frozenset(["glossary_hc"]))
    intended = reviewed(
        monkeypatch, tmp_path, doc01, entry, "r01", command="replace-decision"
    )
    r01 = intended.mention_resolutions["r01"]
    assert r01.status == "unresolved" and "glossary_hc" not in r01.input_refs
    assert "glossary_hc" in intended.variant_assignments["v01"].input_refs
    assert r01.explanation == (
        "An input it read went (glossary_hc); its group is left unresolved."
    )


def test_one_reconfirm_reads_every_withholding_input_by_its_kind(monkeypatch, tmp_path):
    """A decision withheld by a saved record and its Entity is re-cited on
    both, as each is now, under new keys, in one revision."""
    source = s1()
    graph = graph_of(source, description="Edited outside the lab.")
    rows, _ = world_rows(CHAIN, dict(s0="replaced", s1="ok"))
    entry = Withheld(
        Reason.CHANGED, Status.REFRESH_NEEDED, frozenset({"existing_A", "rec_s0"})
    )
    options = dict(graph=graph, rows=rows, command="reconfirm")
    intended = reviewed(monkeypatch, tmp_path, source, entry, "d", **options)
    d = intended.mention_resolutions["d"]
    assert {"existing_A_r2", "rec_s0_r2"} <= set(d.input_refs)
    corpus, record = intended.inputs["existing_A_r2"], intended.inputs["rec_s0_r2"]
    assert str(corpus.entity_id) == helios(source) and corpus.content_sha256 == (
        selected_digest(graph.nodes[helios(source)], source.inputs["existing_A"])
    )
    assert record.content_sha256 != source.inputs["rec_s0"].content_sha256
    digests = intended.producers["review_d_r2"].configuration
    assert set(digests["old_digests"]) == {"existing_A", "rec_s0"}
    assert set(digests["new_digests"]) == {"existing_A_r2", "rec_s0_r2"}
    # A field the Entity no longer has cannot be read as it is now.
    graph.nodes[helios(source)].pop("description")
    with pytest.raises(IntentError) as refused:
        reviewed(monkeypatch, tmp_path, source, entry, "d", **options)
    assert refused.value.code == "input_removed"


def with_sibling(source, record):
    """`source` with a second group g2 and its resolution d2, whose group
    cites `record` too, and with g citing it as well."""
    payload = json.loads(source.model_dump_json())
    mention = str(uuid4())
    payload["entity_constructions"][mention] = dict(name="sibling", description="")
    payload["mention_groups"]["g"]["input_refs"].append(record)
    payload["mention_groups"]["g2"] = dict(
        payload["mention_groups"]["g"], entity_id=mention
    )
    payload["mention_resolutions"]["d2"] = dict(
        payload["mention_resolutions"]["d"], group_ref="g2"
    )
    return IdentitySource.model_validate_json(json.dumps(payload))


def test_drop_removes_a_variant_and_unresolves_only_the_resolution_it_drops(
    monkeypatch, tmp_path
):
    """`replace-citation --drop`: a variant goes and a resolution stays,
    unresolved. Only the dropped decision's own group stops citing the
    record; a sibling resolution whose group cites it keeps citing it under
    its own producer."""
    resolution_key, variant_key = record_key("s0"), record_key("s0", "v")
    source = with_sibling(s1(), resolution_key)
    rows, _ = world_rows(CHAIN, dict(s0="replaced", s1="ok"))
    options = dict(rows=rows, command="replace-citation")
    held = Withheld(Reason.CHANGED, Status.REFRESH_NEEDED, frozenset([variant_key]))
    no_variant = reviewed(monkeypatch, tmp_path, source, held, "v", **options)
    assert "v" not in no_variant.variant_assignments
    assert variant_key not in no_variant.inputs and no_variant.revision == 2
    assert UUID(HC_ID) not in no_variant.entity_constructions
    held = held._replace(inputs=frozenset([resolution_key]))
    unresolved = reviewed(monkeypatch, tmp_path, source, held, "d", **options)
    d = unresolved.mention_resolutions["d"]
    assert (d.status, d.producer_ref) == ("unresolved", "review_d_r2")
    assert resolution_key not in d.input_refs
    assert resolution_key not in unresolved.mention_groups["g"].input_refs
    assert unresolved.mention_groups["g2"] == source.mention_groups["g2"]
    assert unresolved.mention_resolutions["d2"] == source.mention_resolutions["d2"]
    assert resolution_key in unresolved.inputs


def test_cite_recites_the_decision_on_another_record(monkeypatch, tmp_path):
    """`replace-citation --cite`: the decision cites the named record as its
    source holds it now, under a new key; its reviewed fields stay."""
    source = s1()
    rows, _ = world_rows(CHAIN, dict(s0="replaced", s1="ok"))
    held = Withheld(
        Reason.CHANGED, Status.REFRESH_NEEDED, frozenset([record_key("s0", "v")])
    )

    async def sources(root, publisher, info):
        return {"s0": rows[0].description}

    monkeypatch.setattr(review, "current_sources", sources)
    intended = reviewed(
        monkeypatch,
        tmp_path,
        source,
        held,
        "v",
        rows=rows,
        command="replace-citation",
        cite=dict(cite=("s0", "v")),
    )
    v = intended.variant_assignments["v"]
    assert "s0_v_r2" in v.input_refs and record_key("s0", "v") not in v.input_refs
    assert v.target_entity_id == source.variant_assignments["v"].target_entity_id
    assert intended.inputs["s0_v_r2"].record_id == "v"


def next_revision_of(label, cites, previous):
    return described(label, cites).model_copy(
        update=dict(revision=previous.revision + 1)
    )


def test_a_key_that_comes_back_is_refused_while_another_source_cites_it():
    graph = {"s0": frozenset(), "s1": frozenset({"s0"})}
    rows, _ = world_rows(graph, dict(s0="rekeyed", s1="ok"))
    previous = rows[0]
    candidate = next_revision_of("s0", graph["s0"], previous)
    keys = chains.new_record_keys(candidate, previous)
    assert keys == {"d"}
    with pytest.raises(IntentError) as refused:
        chains.check_record_key_reuse(candidate, rows, keys)
    assert refused.value.code == "record_key_reused"
    # A withdrawn citer reads nothing; a retry adds no key.
    rows, _ = world_rows(graph, dict(s0="rekeyed", s1="withdrawn"))
    chains.check_record_key_reuse(candidate, rows, keys)
    failed = dataclasses.replace(previous, state="failed")
    assert chains.new_record_keys(candidate, failed) == set()


def test_a_readd_checks_every_key_against_the_remaining_citers():
    graph = {"s0": frozenset(), "s1": frozenset({"s0"})}
    rows, _ = world_rows(graph, dict(s0="ok", s1="ok"))
    forgotten = SimpleNamespace(tombstone=object(), state="forgotten")
    candidate = described("s0", graph["s0"])
    assert chains.new_record_keys(candidate, forgotten) == {"d", "v"}
    with pytest.raises(IntentError) as refused:
        chains.check_record_key_reuse(candidate, rows[1:], {"d", "v"})
    assert refused.value.code == "record_key_reused"


def test_one_test_decides_whether_a_citation_names_a_record():
    citer = s1()
    item = citer.inputs[record_key("s0")]
    s0 = str(identity("s0"))
    assert names_record(item, s0, "d") and not names_record(item, s0, "v")
    assert not names_record(item, str(identity("s1")), "d")
    removed = RemovedRecord(s0, item.record_type, "d", item.content_sha256, 1)
    assert removed.reads(item)
    other = removed._replace(identity_data_id=str(identity("s1")))
    assert not other.reads(item)


def test_a_corpus_input_of_a_mention_uuid_is_refused():
    source = s1()
    mention = source.mention_groups["g"].entity_id
    payload = json.loads(source.model_dump_json())
    payload["inputs"]["read_mention"] = dict(
        payload["inputs"]["existing_A"], entity_id=str(mention)
    )
    reader = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError) as refused:
        check_mention_inputs(reader, mention_ids([reader]))
    assert refused.value.code == "mention_input"
    other = described("s0", frozenset())
    payload["inputs"]["read_mention"]["entity_id"] = str(
        other.mention_groups["g"].entity_id
    )
    reader = IdentitySource.model_validate_json(json.dumps(payload))
    with pytest.raises(IntentError):
        check_mention_inputs(reader, mention_ids([other, reader]))
    check_mention_inputs(s1(), mention_ids([other, s1()]))


def test_a_citation_a_kind_change_removed_does_not_hold_a_later_cascade():
    """s1 drops its variant (a kind change), so s2's variant cites a record
    that is gone. A later forget of s0 removes s1's resolution, then s2's;
    s2's stale variant citation is no removal, and the cascade finishes."""
    graph = {"s0": frozenset(), "s1": frozenset({"s0"}), "s2": frozenset({"s1"})}
    rows = cascade_rows(graph, dict(s1="ok", s2="ok"))
    s1_row = next(r for r in rows if r.source == str(identity("s1")))
    payload = json.loads(s1_row.description.model_dump_json())
    payload["variant_assignments"].pop("v")
    payload["inputs"].pop(record_key("s0", "v"))
    payload["revision"] = 2
    kind_changed = row_of(IdentitySource.model_validate_json(json.dumps(payload)), "ok")
    rows = [kind_changed if r.source == s1_row.source else r for r in rows]
    ids = source_ids(rows[0].tombstone)
    for _ in range(2):
        step = erasure.cascade(rows, ids, ())[0]
        rows = [
            row_of(step.description, "ok") if r.source == step.row.source else r
            for r in rows
        ]
    s2 = next(r for r in rows if r.source == str(identity("s2")))
    assert record_key("s1", "v") in saved_records(s2.description)
    assert erasure.cascade(rows, ids, ()) == ()
    assert erasure.unfinished(rows[0].tombstone, rows) == []


def test_an_entity_edit_changes_neither_the_forget_token_nor_its_write_order():
    """The impact, its token and the write order read the ledger rows only.
    An outside Entity edit writes no row, so the token of a dry run before
    it confirms the forget after it, and a dependent whose decision the
    edit withholds is no blocked removal: its row is served."""
    graph = {"s0": frozenset(), "s1": frozenset({"s0"}), "s2": frozenset({"s1"})}
    rows = cascade_rows(graph, dict(s1="ok", s2="ok"))
    ids = source_ids(rows[0].tombstone)
    held, _ = world_rows(graph, dict(s0="ok", s1="held", s2="ok"))
    assert [r.description for r in held[1:]] == [r.description for r in rows[1:]]
    steps = erasure.cascade(rows, ids, ())
    ready, waiting = erasure.ready(steps)
    assert [s.level for s in ready] == [1, 2] and waiting == []
    assert not any(erasure.blocked(s.row) for s in steps)
