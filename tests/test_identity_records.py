import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.digests import object_digest
from cognee_lab.identity.validation import (
    IntentError,
    map_chunks,
    text_digest,
    validate_inputs,
    validate_uses,
)

from cognee_lab.identity.withholding import held_by


def withheld_reasons(source, drift):
    """Each decision live drift withholds, with its reason."""
    found = held_by(source, {}, drift, lambda item: None)
    return {key: entry.reason for key, entry in found.items()}


def parse(value):
    return IdentitySource.model_validate_json(json.dumps(value))


def test_example_and_exact_text(source_payload):
    source = parse(source_payload)
    text = (Path(__file__).parent / "fixtures/identity/source.txt").read_text()
    assert text_digest(text) == source.inputs["doc01"].text_sha256
    for occurrence in source.mention_groups["g01"].occurrences:
        assert text[occurrence.start : occurrence.end] == occurrence.text
    assert text_digest(text.rstrip()) != text_digest(text)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["mention_resolutions"]["r01"].pop("target_entity_id"),
        lambda p: p["mention_resolutions"]["r01"].update(status="unresolved"),
        lambda p: p["entity_constructions"].pop(
            p["mention_groups"]["g01"]["entity_id"]
        ),
        lambda p: p["mention_resolutions"]["r01"].update(group_ref="absent"),
        lambda p: p["mention_resolutions"].update(
            r02=dict(p["mention_resolutions"]["r01"])
        ),
        lambda p: p["mention_groups"]["g01"]["occurrences"][1].update(start=50),
        lambda p: p["mention_groups"]["g01"]["occurrences"][0].update(start=True),
        lambda p: p["variant_assignments"]["v01"].update(
            target_entity_id=p["mention_groups"]["g01"]["entity_id"]
        ),
        lambda p: p["mention_groups"]["g01"].update(producer_ref="absent"),
        lambda p: p["mention_resolutions"]["r01"].update(input_refs=["absent"]),
    ],
)
def test_rejects_invalid_forms(source_payload, mutation):
    mutation(source_payload)
    with pytest.raises(ValidationError):
        parse(source_payload)


def test_unresolved_keeps_group_without_target(source_payload):
    r = source_payload["mention_resolutions"]["r01"]
    r.pop("target_entity_id")
    r["status"] = "unresolved"
    source = parse(source_payload)
    from cognee_lab.identity.publish import identity_edges

    assert len(identity_edges(source)) == 1  # Variant remains; mention has no edge.


def test_cross_source_uuid_use(source_payload):
    a = parse(source_payload)
    source_payload["identity_data_id"] = str(uuid4())
    source_payload["mention_groups"] = {}
    source_payload["mention_resolutions"] = {}
    b = parse(source_payload)  # The same M is now declared a reusable singleton.
    with pytest.raises(IntentError, match="both mention and reusable"):
        validate_uses([a, b])


def test_repeated_unicode_chunks_map_in_order():
    chunks = [
        SimpleNamespace(id="a", chunk_index=0, text="α😀\n"),
        SimpleNamespace(id="b", chunk_index=1, text="α😀\n"),
    ]
    assert map_chunks("α😀\nα😀\n", chunks) == {"a": (0, 3), "b": (3, 6)}
    with pytest.raises(IntentError):
        map_chunks("α😀 α😀\n", chunks)


def test_jcs_and_exact_projection():
    assert object_digest({"b": 2, "a": 1}) == object_digest({"a": 1, "b": 2})
    assert object_digest([1, 2]) != object_digest([2, 1])
    assert object_digest({"x": None}) != object_digest({})
    with pytest.raises(ValueError):
        object_digest({"x": float("nan")})


def test_generated_schema_matches_and_example_validates(source_payload):
    from cognee_lab.identity.schema import schema
    from jsonschema import Draft202012Validator, FormatChecker

    checked = json.loads(
        (
            Path(__file__).parents[1]
            / "schemas/cognee_identity_source_schema_draft.json"
        ).read_text()
    )
    assert checked == schema()
    Draft202012Validator(checked, format_checker=FormatChecker()).validate(
        source_payload
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,reason", [("missing", "input_removed"), ("changed", "input_changed")]
)
async def test_recipe_does_not_replace_missing_or_changed_reasoning_input(
    source_payload, state, reason
):
    """A missing or changed corpus input withholds every decision that read
    it, with the reason a user sees; the saved recipe does not stand in."""
    source = parse(source_payload)
    text = (Path(__file__).parent / "fixtures/identity/source.txt").read_text()
    chunk = SimpleNamespace(
        id=source.inputs["chunk01"].chunk_id,
        chunk_index=0,
        text=text,
        is_part_of=SimpleNamespace(id=source.inputs["doc01"].data_id),
    )

    class Graph:
        async def get_node(self, _):
            return (
                None
                if state == "missing"
                else {"name": "Changed", "description": "Changed"}
            )

    drift = await validate_inputs(
        source, texts={"doc01": text}, chunks={str(chunk.id): chunk}, graph=Graph()
    )
    assert drift == {"existing_A": reason}
    assert withheld_reasons(source, drift) == {"r01": reason, "v01": reason}


def test_the_review_path_writes_resolutions_and_groups_only_through_records():
    """review.py and revisions.reconfirmed write a decision's resolution and
    group fields only through records.py (apply_removal, apply_reconfirm),
    so a record kind's hooks own its layout. Fixture builders such as
    revisions.corrected may write them directly."""
    import ast
    import inspect

    from cognee_lab.identity import review, revisions

    fields = {"mention_resolutions", "mention_groups"}
    for code in (inspect.getsource(review), inspect.getsource(revisions.reconfirmed)):
        written = {
            name.value
            for node in ast.walk(ast.parse(code))
            if isinstance(node, ast.Subscript)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            for name in ast.walk(node)
            if isinstance(name, ast.Constant) and name.value in fields
        }
        assert written == set()


def test_reconfirm_rewires_the_record_and_its_group_only(source_payload):
    """A re-confirmed resolution and its group cite the new input in place
    of the old one, and the resolution names the reviewer's producer. Its
    fingerprint stays, and a sibling resolution and its group, which cite
    the same old input, keep citing it."""
    import copy

    from cognee_lab.identity.records import apply_reconfirm, record_digest

    source_payload["mention_groups"]["g01"]["input_refs"].append("existing_A")
    sibling = copy.deepcopy(source_payload["mention_groups"]["g01"])
    sibling["entity_id"] = str(uuid4())
    sibling["occurrences"] = sibling["occurrences"][:1]
    source_payload["entity_constructions"][sibling["entity_id"]] = copy.deepcopy(
        source_payload["entity_constructions"][
            source_payload["mention_groups"]["g01"]["entity_id"]
        ]
    )
    source_payload["mention_groups"]["g02"] = sibling
    source_payload["mention_resolutions"]["r02"] = dict(
        source_payload["mention_resolutions"]["r01"], group_ref="g02"
    )
    source = IdentitySource.model_validate_json(json.dumps(source_payload))
    payload = source.model_dump(mode="json")
    payload["inputs"]["existing_A_r2"] = dict(
        payload["inputs"]["existing_A"], content_sha256="0" * 64
    )
    payload["producers"]["review"] = dict(
        payload["producers"]["fixture"], implementation="review"
    )

    apply_reconfirm(payload, source, "r01", {"existing_A": "existing_A_r2"}, "review")
    after = IdentitySource.model_validate_json(json.dumps(payload))

    assert after.mention_resolutions["r01"].input_refs == ["doc01", "existing_A_r2"]
    assert after.mention_resolutions["r01"].producer_ref == "review"
    assert after.mention_groups["g01"].input_refs == ["doc01", "existing_A_r2"]
    assert record_digest(after, "mention_resolution", "r01") == record_digest(
        source, "mention_resolution", "r01"
    )
    assert after.mention_resolutions["r02"] == source.mention_resolutions["r02"]
    assert after.mention_groups["g02"] == source.mention_groups["g02"]
    assert after.variant_assignments == source.variant_assignments
