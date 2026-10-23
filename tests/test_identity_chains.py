"""Saved-record citations: what a citation pins, and how withholding spreads
down a chain of citing sources."""

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
    record_reader,
)
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.records import citation, record_digest
from cognee_lab.identity.validation import IntentError, Reason
from cognee_lab.identity.withholding import Status, Withheld, withheld_decisions


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
    assert new_citations(source, None) == {"rec_s1"}
    assert new_citations(later, row_of(world_source("s0", frozenset()), "ok")) == {
        "rec_s1"
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


def test_the_reader_tells_a_changed_record_from_a_removed_one():
    item = world_source("s0", CHAIN["s0"]).inputs["rec_s1"]
    for state, reason in (
        ("ok", None),
        ("held", None),
        ("replaced", Reason.CHANGED),
        ("rekeyed", Reason.REMOVED),
        ("pending", Reason.CHANGED),
        ("withdrawn", Reason.REMOVED),
    ):
        assert record_reader(chain_rows(s1=state))(item) == reason, state


def test_an_unfinished_cited_source_withholds_its_citers_from_the_rows():
    held = withheld_decisions(chain_rows(s1="pending"), [])
    assert held[str(identity("s0"))] == {
        "d": Withheld(Reason.CHANGED, Status.EDIT_UNFINISHED, frozenset({"rec_s1"}))
    }


def test_withholding_spreads_down_the_whole_chain_and_releases_with_its_cause():
    held = chain_check.held_now(CHAIN, {"s0": "ok", "s1": "ok", "s2": "held"})
    assert held[str(identity("s0"))]["d"] == Withheld(
        Reason.CHANGED, Status.UPSTREAM_WITHHELD, frozenset({"rec_s1"})
    )
    # A re-confirm upstream keeps the fingerprint: nothing is withheld.
    assert chain_check.held_now(CHAIN, dict.fromkeys(CHAIN, "ok")) == {}


def test_chains_agree_with_the_oracle_on_three_sources():
    tally, failures = chain_check.run(3)
    assert failures == []
    assert tally["acyclic graphs"] == 25 and tally["cycle refusal"] == 192


@pytest.mark.parametrize("name", sorted(chain_check.MUTANTS))
def test_each_chain_mutant_is_caught(name):
    with chain_check.patched(name):
        _, failures = chain_check.run(3)
    assert failures
