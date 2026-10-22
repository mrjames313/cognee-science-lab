"""Building blocks for captured revision descriptions.

Each captured describer composes these with its own scope guard, texts and
reviewed decisions. They edit a JSON payload of the old description.
"""

from .captured_text import BEFORE
from .validation import IntentError, fresh_mention_id, text_digest


def require_fresh_doc01(old, before, groups, message):
    """The captured edits apply only to doc01 of a fresh chunked-fixture."""
    if old.revision != 1 or before != BEFORE or set(old.mention_groups) != groups:
        raise IntentError("fixture_scope", message)


def begin_revision(old, after, ref, implementation, policy):
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(after)
    payload["producers"][ref] = dict(
        method="captured_fixture",
        implementation=implementation,
        version="0.1",
        configuration={"policy": policy},
        run_id=None,
    )
    return payload


def retire_group(payload, key):
    entity_id = payload["mention_groups"].pop(key)["entity_id"]
    payload["entity_constructions"].pop(entity_id)
    payload["mention_resolutions"] = {
        k: r for k, r in payload["mention_resolutions"].items() if r["group_ref"] != key
    }


def occurrence(after, text, anchor=None):
    anchor = anchor or text
    start = after.index(anchor) + anchor.index(text)
    return dict(start=start, end=start + len(text), text=text)


def declare_group(
    payload, old, key, rid, name, description, occurrences, resolution, ref
):
    entity_id = str(fresh_mention_id(old.identity_data_id, payload["revision"], key))
    payload["entity_constructions"][entity_id] = dict(
        name=name, description=description
    )
    payload["mention_groups"][key] = dict(
        entity_id=entity_id,
        document_ref=old.original_input_ref,
        occurrences=occurrences,
        chunk_refs=["chunk01"],
        input_refs=[old.original_input_ref],
        producer_ref=ref,
    )
    payload["mention_resolutions"][rid] = dict(
        group_ref=key,
        status="accepted",
        target_entity_id=str(resolution.target_entity_id),
        input_refs=list(resolution.input_refs),
        producer_ref=ref,
        explanation=None,
    )


def stamp_producer(payload, ref):
    for record in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["producer_ref"] = ref
