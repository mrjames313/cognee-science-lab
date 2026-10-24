"""Saved-record citations: what a citation pins, and how withholding spreads
down a chain of citing sources."""

import asyncio
import dataclasses
import json
from uuid import NAMESPACE_URL, uuid5

import pytest

import chain_check
from chain_worlds import described as world_source
from chain_worlds import identity, row_of, world_rows
from cognee_lab.identity.chains import (
    check_citation_cycles,
    check_citation_scope,
    check_record_citations,
    new_citations,
)
from cognee_lab.identity.admission import admit, identity_map
from cognee_lab.identity.erasure import (
    cascade,
    refuse_retiring_inputs,
    remaining,
    unfinished,
)
from cognee_lab.identity.erasure_rules import erasures_of
from cognee_lab.identity.retirement import source_ids
from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.records import citation, record_digest
from cognee_lab.identity.validation import IntentError, Reason
from cognee_lab.identity.withholding import (
    CHANGED,
    REMOVED,
    UNFINISHED,
    Status,
    Withheld,
    record_reader,
    withheld_decisions,
)


def described(payload, change=None):
    payload = json.loads(json.dumps(payload))
    if change:
        change(payload)
    return IdentitySource.model_validate_json(json.dumps(payload))


def test_a_reconfirm_keeps_a_records_fingerprint(source_payload):
    base = described(source_payload)

    def reconfirm(payload):
        payload["producers"]["review"] = dict(
            payload["producers"]["fixture"], implementation="re-confirmed"
        )
        for record in (
            payload["mention_resolutions"]["r01"],
            payload["variant_assignments"]["v01"],
        ):
            record.update(input_refs=["doc01"], producer_ref="review")
            record["explanation"] = "re-confirmed"

    again = described(source_payload, reconfirm)
    for record_type, key in (
        ("mention_resolution", "r01"),
        ("variant_assignment", "v01"),
    ):
        assert record_digest(base, record_type, key) == record_digest(
            again, record_type, key
        )


def test_an_in_place_replacement_or_a_new_mention_changes_the_fingerprint(
    source_payload,
):
    base = described(source_payload)
    digest = record_digest(base, "mention_resolution", "r01")

    def unresolve(payload):
        r01 = payload["mention_resolutions"]["r01"]
        payload["mention_resolutions"]["r01"] = dict(
            group_ref=r01["group_ref"],
            status="unresolved",
            input_refs=r01["input_refs"],
            producer_ref=r01["producer_ref"],
        )

    assert record_digest(described(source_payload, unresolve), *_r01()) != digest

    def new_mention(payload):
        group = payload["mention_groups"]["g01"]
        old = group["entity_id"]
        group["entity_id"] = str(uuid5(NAMESPACE_URL, "test:new-mention"))
        payload["entity_constructions"][group["entity_id"]] = payload[
            "entity_constructions"
        ].pop(old)

    # Same key, same group key, same target: a different mention.
    assert record_digest(described(source_payload, new_mention), *_r01()) != digest


def _r01():
    return "mention_resolution", "r01"


def test_a_missing_record_has_no_fingerprint(source_payload):
    base = described(source_payload)
    assert record_digest(base, "mention_resolution", "v01") is None
    assert record_digest(base, "variant_assignment", "r99") is None


def test_a_citation_names_the_records_type_revision_and_fingerprint(
    source_payload,
):
    base = described(source_payload)
    cited = citation(base, "v01")
    assert cited["record_type"] == "variant_assignment"
    assert cited["representation_revision"] == base.revision
    assert cited["content_sha256"] == record_digest(base, "variant_assignment", "v01")


def refusal(check, *args):
    with pytest.raises(IntentError) as caught:
        check(*args)
    return caught.value.code


CHAIN = {"s0": frozenset({"s1"}), "s1": frozenset({"s2"}), "s2": frozenset()}


def chain_rows(**states):
    """s0 cites d of s1, which cites d of s2."""
    return world_rows(CHAIN, {label: states.get(label, "ok") for label in CHAIN})[0]


def pinned(source, key, **changes):
    payload = source.model_dump(mode="json")
    payload["inputs"][key].update(changes)
    return described(payload)


def test_a_citation_stays_in_its_dataset_and_off_the_citing_source():
    source = world_source("s0", CHAIN["s0"])
    check_citation_scope(source)
    own = pinned(source, "rec_s1", identity_data_id=str(source.identity_data_id))
    assert refusal(check_citation_scope, own) == "self_citation"
    elsewhere = pinned(source, "rec_s1", dataset_id=str(identity("elsewhere")))
    assert refusal(check_citation_scope, elsewhere) == "not_admitted"


def test_a_new_citation_pins_a_served_record_as_it_is_now():
    rows, source, new = chain_rows(), world_source("s0", CHAIN["s0"]), {"rec_s1"}
    check_record_citations(source, rows, new)
    for changes, code in (
        (dict(record_id="r99"), "record_missing"),
        (dict(representation_revision=2), "record_stale"),
        (dict(content_sha256="0" * 64), "record_digest"),
    ):
        changed = pinned(source, "rec_s1", **changes)
        assert refusal(check_record_citations, changed, rows, new) == code
    pending = chain_rows(s1="pending")
    assert (
        refusal(check_record_citations, source, pending, new)
        == "record_source_unavailable"
    )


def test_only_a_first_attempt_checks_its_new_citations():
    source = world_source("s0", CHAIN["s0"])
    later = described(source.model_dump(mode="json") | {"revision": 2})
    assert new_citations(source, None) == {"rec_s1", "var_s1"}
    assert new_citations(later, row_of(world_source("s0", frozenset()), "ok")) == {
        "rec_s1",
        "var_s1",
    }
    assert new_citations(later, row_of(source, "ok")) == set()
    # A retry reuses its saved intent: the failed row holds the description.
    failed = dataclasses.replace(row_of(later, "ok"), state="failed")
    assert new_citations(later, failed) == set()


def test_admission_refuses_a_citation_that_closes_a_cycle():
    rows = chain_rows()
    check_citation_cycles(world_source("s0", CHAIN["s0"]), rows)
    closing = world_source("s2", frozenset({"s0"}))
    assert refusal(check_citation_cycles, closing, rows) == "citation_cycle"
    mutual = world_source("s2", frozenset({"s1"}))
    assert refusal(check_citation_cycles, mutual, rows) == "citation_cycle"
    # A retired source reads nothing, so it closes no cycle.
    s0 = str(identity("s0"))
    retired = [
        dataclasses.replace(r, state="withdrawn") if r.source == s0 else r for r in rows
    ]
    check_citation_cycles(closing, retired)


def test_the_reader_tells_a_changed_record_from_a_removed_or_unfinished_one():
    item = world_source("s0", CHAIN["s0"]).inputs["rec_s1"]
    for state, verdict in (
        ("ok", None),
        ("held", None),
        ("replaced", CHANGED),
        ("rekeyed", REMOVED),
        ("pending", UNFINISHED),
        ("unverified", UNFINISHED),
        ("withdrawn", REMOVED),
    ):
        assert record_reader(chain_rows(s1=state))(item) == verdict, state
    # A source whose own input failed live validation is unfinished too.
    failed = {str(identity("s1"))}
    assert record_reader(chain_rows(), failed)(item) == UNFINISHED


def test_an_unfinished_cited_source_withholds_its_citers_from_the_rows():
    held = withheld_decisions(chain_rows(s1="pending"), [])
    assert held[str(identity("s0"))] == {
        "d": Withheld(*UNFINISHED, frozenset({"rec_s1"})),
        "v": Withheld(*UNFINISHED, frozenset({"var_s1"})),
    }


def held_now(**states):
    world = {label: states.get(label, "ok") for label in CHAIN}
    return asyncio.run(chain_check.held_now(CHAIN, world))


def test_withholding_spreads_down_the_whole_chain_and_releases_with_its_cause():
    # s2's resolution is withheld, its variant is not: s0's variant is served.
    assert held_now(s2="held")[str(identity("s0"))] == {
        "d": Withheld(Reason.CHANGED, Status.UPSTREAM_WITHHELD, frozenset({"rec_s1"}))
    }
    # A re-confirm upstream keeps the fingerprint: nothing is withheld.
    assert held_now() == {}


def test_chains_agree_with_the_oracle_on_three_sources():
    tally, failures = chain_check.run(3)
    assert failures == []
    assert tally["acyclic graphs"] == 25 and tally["cycle refusal"] == 192


@pytest.mark.parametrize("name", sorted(chain_check.MUTANTS))
def test_each_chain_mutant_is_caught(name):
    with chain_check.patched(name):
        _, failures = chain_check.run(3)
    assert failures


def forget_rows(state):
    """s2's forget under way while s1, which cites s2's `d`, is not revised
    yet: s2's forget is pending or failed, or it completed and left s1."""
    s2 = world_source("s2", CHAIN["s2"])
    doc = s2.inputs[s2.original_input_ref]
    plan = dict(
        operation="identity_forget",
        entities={},
        revision=s2.revision,
        original_data_id=str(doc.data_id),
    )
    forgotten = dataclasses.replace(row_of(s2, "ok"), state=state, plan=plan)
    if state == "forgotten":
        tombstone = Tombstone.of(s2, forgotten_at="t", removed_entity_ids=())
        forgotten = dataclasses.replace(
            forgotten, description=None, tombstone=tombstone
        )
    return [forgotten, row_of(world_source("s1", CHAIN["s1"]), "ok")]


@pytest.mark.parametrize("state", ["pending", "failed", "forgotten"])
def test_a_new_citation_of_a_record_a_forget_under_way_removes_is_refused(state):
    rows = forget_rows(state)
    citer = world_source("s0", CHAIN["s0"])
    with pytest.raises(IntentError) as refused:
        refuse_retiring_inputs(citer, rows)
    assert refused.value.code == "retiring_source"
    assert [
        (d["identity_data_id"], d["input_ref"])
        for d in refused.value.details["dependents"]
    ] == [(str(identity("s0")), "rec_s1"), (str(identity("s0")), "var_s1")]
    # Once s1's removal revision is written, nothing is left to remove.
    revised = world_source("s1", frozenset())
    refuse_retiring_inputs(citer, [rows[0], row_of(revised, "ok")])


def written(step):
    """The row after a removal revision is written."""
    return row_of(step.description, "ok")


def test_a_forget_cascades_down_the_chain_by_level():
    """s2 is forgotten: s1 cites it, so s1 is level 1; s0 cites the records
    s1's removal removes, so s0 is level 2."""
    rows = forget_rows("forgotten") + [row_of(world_source("s0", CHAIN["s0"]), "ok")]
    found = remaining(rows[0].tombstone, rows)
    assert [(d.identity_data_id, d.level) for d in found.dependents] == [
        (str(identity("s1")), 1),
        (str(identity("s0")), 2),
    ]
    s1, s0 = found.dependents
    assert s0.cited_records == s1.removed_records
    assert [r.record_id for r in s1.removed_records] == ["d", "v"]
    assert {r.last_revision for r in s1.removed_records} == {1}


def test_a_resume_converges_from_the_rows_in_level_order():
    rows = forget_rows("forgotten") + [row_of(world_source("s0", CHAIN["s0"]), "ok")]
    tomb = rows[0].tombstone
    first, second = cascade(rows, source_ids(tomb), ())
    after_first = [rows[0], written(first), rows[2]]
    (resumed,) = cascade(after_first, source_ids(tomb), ())
    assert resumed.description == second.description and resumed.level == 2
    assert [r.source for r in unfinished(tomb, after_first)] == [str(identity("s0"))]
    assert unfinished(tomb, [rows[0], written(first), written(second)]) == []


def test_a_level_two_removal_binds_only_once_level_one_is_written():
    rows = forget_rows("forgotten") + [row_of(world_source("s0", CHAIN["s0"]), "ok")]
    first, second = cascade(rows, source_ids(rows[0].tombstone), ())
    s0 = rows[2].description
    text = "The controller limits oscillations.\n"

    def admitted(rows):
        admit(
            s0,
            second.description,
            text,
            text,
            identity_map(s0),
            erasures=erasures_of(rows, s0),
        )

    assert refusal(admitted, rows) == "erasure_unbound"
    admitted([rows[0], written(first), rows[2]])


def test_a_citation_pinned_before_another_fingerprint_is_not_cascaded():
    """s0's `d` cites s1's `d` at a fingerprint s1's `d` no longer has: the
    removal of s1's `d` does not reach it, only live withholding does. s0's
    `v` still goes."""
    stale = pinned(world_source("s0", CHAIN["s0"]), "rec_s1", content_sha256="0" * 64)
    rows = forget_rows("forgotten") + [row_of(stale, "ok")]
    s1, s0 = remaining(rows[0].tombstone, rows).dependents
    assert [r.assignment for r in s0.decisions] == ["v"]
    assert [r.record_id for r in s0.cited_records] == ["v"]


def test_a_citation_made_after_a_removal_is_not_cascaded():
    """A record that returns to the fingerprint it had before its removal
    is read by a later citation as it is now: the citation pins a revision
    after the removal's last one."""
    rows = forget_rows("forgotten") + [row_of(world_source("s0", CHAIN["s0"]), "ok")]
    s1, s0 = remaining(rows[0].tombstone, rows).dependents
    removed = s1.removed_records[0]
    later = pinned(
        world_source("s0", CHAIN["s0"]), "rec_s1", representation_revision=3
    ).inputs["rec_s1"]
    assert removed.reads(rows[2].description.inputs["rec_s1"])
    assert not removed.reads(later)


@pytest.mark.parametrize("state", ["pending", "failed", "forgotten"])
def test_a_new_citation_of_a_record_removed_below_level_one_is_refused(state):
    rows = forget_rows(state) + [row_of(world_source("s0", CHAIN["s0"]), "ok")]
    citer = world_source("s3", frozenset({"s0"}))
    with pytest.raises(IntentError) as refused:
        refuse_retiring_inputs(citer, rows)
    assert refused.value.code == "retiring_source"
    assert [d["input_ref"] for d in refused.value.details["dependents"]] == [
        "rec_s0",
        "var_s0",
    ]


def test_an_unverified_cited_source_waits_for_its_attempt_not_for_a_review():
    unfinished = Withheld(Reason.CHANGED, Status.EDIT_UNFINISHED, frozenset({"rec_s1"}))
    item = world_source("s0", CHAIN["s0"]).inputs["rec_s1"]
    rows = chain_rows(s1="unverified")
    assert record_reader(rows)(item) == unfinished[:2]
    assert withheld_decisions(rows, [])[str(identity("s0"))]["d"] == unfinished
    assert held_now(s1="unverified")[str(identity("s0"))]["d"] == unfinished
