"""Saved-record citations: what a citation pins, and how withholding spreads
down a chain of citing sources."""

import json
from uuid import NAMESPACE_URL, uuid5

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.records import citation, record_digest


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
