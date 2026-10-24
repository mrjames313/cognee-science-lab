"""A captured stand-in for an outside writer of a native Entity.

`edit-entity` changes the Helios controller Entity that doc01's corpus
input `existing_A` names, through Cognee's own `graph.update_node`, as a
writer outside the lab would. It writes no ledger row and takes no writer
reservation: nothing in the lab records the edit. Live validation finds it
at the next read (validation.input_failure digests a corpus input's
selected fields), so every decision that cites the Entity is withheld with
`input_changed` until a reviewer re-confirms or replaces it, or the edit
is reverted. The user decided this on 2026-10-24: a direct edit of a native
Entity withholds its dependents as a text edit of a consumed document
does.

- `description` changes a selected field.
- `unselected` sets a property no corpus input selects.
- `revert` puts back what the first `description` edit changed.
"""

import json

from .validation import IntentError, selected_digest

ENTITY_INPUT = "existing_A"
ORIGINAL = "entity_edit_original.json"
# Cognee keeps these as native columns, outside the property blob that
# update_node rewrites, and a lab Entity's identity rests on them.
PROTECTED = frozenset({"id", "name", "type"})
CASES = {
    "description": dict(description="Controller identity, edited outside the lab."),
    "unselected": dict(lab_note="Set outside the lab; no decision selects it."),
}
ENTITY_CASES = (*CASES, "revert")


def entity_input(doc01) -> str:
    """The key of doc01's corpus input of the edited Entity: `existing_A`,
    or after its re-confirms the latest key that re-reads it
    (`existing_A_r<revision>`)."""
    keys = [
        k
        for k, i in doc01.inputs.items()
        if k.startswith(ENTITY_INPUT) and i.kind == "corpus_object"
    ]
    if not keys:
        raise IntentError("fixture_scope", "edit-entity needs doc01's existing_A")
    if ENTITY_INPUT in keys:
        return ENTITY_INPUT
    return max(keys, key=lambda k: int(k.rsplit("_r", 1)[1]))


def patch_for(root, case, node) -> dict:
    """The properties a case writes. The first `description` edit saves the
    values it replaces, which `revert` writes back."""
    original = root / ORIGINAL
    if case == "revert":
        if not original.exists():
            raise IntentError("fixture_scope", "revert follows a description edit")
        return json.loads(original.read_text())
    values = CASES[case]
    if case == "description" and not original.exists():
        original.write_text(json.dumps({k: node[k] for k in values}, indent=2))
    return values


async def update_entity(graph, entity_id, values):
    """Write `values` into the Entity's properties, as an outside writer
    would. Refuses the native columns."""
    if refused := sorted(PROTECTED & set(values)):
        raise IntentError(
            "entity_field_protected", f"edit-entity does not change {refused}"
        )
    if not await graph.update_node(str(entity_id), values):
        raise IntentError("missing_reasoning_input", f"No such Entity: {entity_id}")


async def edit_entity(publisher, root, doc01, case) -> dict:
    """Edit the Entity doc01's `existing_A` names. Returns what changed:
    the fields written and the digest of the input's selected fields before
    and after."""
    key = entity_input(doc01)
    item = doc01.inputs[key]
    node = await publisher.graph.get_node(str(item.entity_id))
    if node is None:
        raise IntentError(
            "missing_reasoning_input", f"No such Entity: {item.entity_id}"
        )
    values = patch_for(root, case, node)
    await update_entity(publisher.graph, item.entity_id, values)
    after = await publisher.graph.get_node(str(item.entity_id))
    return dict(
        entity_edit=dict(
            case=case,
            entity_id=str(item.entity_id),
            input_ref=key,
            fields=sorted(values),
            selected_fields=list(item.selected_fields),
            pinned_sha256=item.content_sha256,
            before_sha256=selected_digest(node, item),
            after_sha256=selected_digest(after, item),
        )
    )
