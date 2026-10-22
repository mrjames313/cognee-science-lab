"""Building blocks for captured revision descriptions.

Each captured describer composes these with its own scope guard, texts and
reviewed decisions. They edit a JSON payload of the old description.
"""

from .captured_text import BEFORE
from .validation import IntentError, fresh_mention_id, text_digest


def require_root(old, before, groups, message, *, revision=1, produced=None):
    """A captured edit applies only to doc01 of the root it was written for.

    The default is a fresh chunked-fixture at revision 1. `produced` is the
    (producer ref, implementation) of the edit that must have made `old`.
    """
    made = old.producers.get(produced[0]) if produced else None
    wrong_edit = produced and (made is None or made.implementation != produced[1])
    if (
        old.revision != revision
        or before != BEFORE
        or set(old.mention_groups) != groups
        or wrong_edit
    ):
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
    payload,
    old,
    key,
    rid,
    name,
    description,
    occurrences,
    ref,
    *,
    status,
    target=None,
):
    """Declare a fresh group with its reviewed decision. A target that `old`
    lists as an input is listed in the decision's `input_refs`."""
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
    decision = dict(
        group_ref=key,
        status=status,
        input_refs=[
            old.original_input_ref,
            *(
                k
                for k, item in old.inputs.items()
                if target and getattr(item, "entity_id", None) == target
            ),
        ],
        producer_ref=ref,
        explanation=None,
    )
    if target:
        decision["target_entity_id"] = str(target)
    payload["mention_resolutions"][rid] = decision


def stamp_producer(payload, ref):
    for record in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        record["producer_ref"] = ref
