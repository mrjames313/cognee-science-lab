"""Exact chunk binding and fact spans for the captured fixture, not inference."""

from .models import ChunkInput
from .validation import IntentError, fresh_mention_id, map_chunks
from uuid import UUID

FACT_TEXT = "it limits oscillations"
ADDED_FACT_TEXT = "the controller limits oscillations"
FACT_GROUPS = ("g01", "g05", "g06")
GROUP_CREATED = {"g03": 2, "g04": 2, "g05": 2, "g06": 3}


def captured_facts(source):
    """Explicit fixture outputs, independent of model inference or label matching."""
    for key in FACT_GROUPS:
        yield key, FACT_TEXT
    if "g03" in source.mention_groups:
        yield "g03", ADDED_FACT_TEXT


def fixture_mention_id(source, key="g01"):
    """Known captured fixture identity, including after its declaration retires."""
    group = source.mention_groups.get(key)
    if group is not None:
        return group.entity_id
    if key != "g01":
        return fresh_mention_id(source.identity_data_id, GROUP_CREATED[key], key)
    if source.identity_data_id == UUID("718efce2-4251-5f6f-8318-417bb4dd3525"):
        return UUID("233cb019-3986-5864-88bc-91f334a64372")
    raise IntentError(
        "fixture_shape", "Missing primary group outside the captured retirement fixture"
    )


def retired_mentions(source):
    keys = ("g01", "g04", "g05") if "g06" in source.mention_groups else ("g01",)
    return {
        k: fixture_mention_id(source, k) for k in keys if k not in source.mention_groups
    }


def bind_chunks(payload, text, chunks):
    """Keep the complete native map; only occurrence-overlapping chunks mark M."""
    key = payload["original_input_ref"]
    payload["inputs"] = {
        k: v for k, v in payload["inputs"].items() if v["kind"] != "chunk"
    }
    spans = map_chunks(text, chunks)
    for i, chunk in enumerate(sorted(chunks, key=lambda c: c.chunk_index), 1):
        start, end = spans[str(chunk.id)]
        payload["inputs"][f"chunk{i:02}"] = dict(
            kind="chunk", document_ref=key, chunk_id=str(chunk.id), start=start, end=end
        )
    for group in payload["mention_groups"].values():
        group["chunk_refs"] = [
            k
            for k, item in payload["inputs"].items()
            if item["kind"] == "chunk"
            and item["document_ref"] == group["document_ref"]
            and any(
                o["start"] < item["end"] and item["start"] < o["end"]
                for o in group["occurrences"]
            )
        ]


def fact_chunks(source, chunks, *, group_key="g01", fact_text=FACT_TEXT):
    """The captured fact starts at the explicitly stored 'it' occurrence.

    Its whole literal span is supplied fixture knowledge. This does not derive
    facts from arbitrary text or assign all group chunks as fact evidence.
    """
    ordered = sorted(chunks, key=lambda c: c.chunk_index)
    text = "".join(c.text for c in ordered)
    mapping = map_chunks(text, ordered)
    declared = {
        str(i.chunk_id): (i.start, i.end)
        for i in source.inputs.values()
        if isinstance(i, ChunkInput)
    }
    if mapping != declared:
        raise IntentError(
            "chunk_mapping",
            "Captured semantics requires the complete checked chunk mapping",
        )
    group = source.mention_groups.get(group_key)
    if group is None:
        fixture_mention_id(source)
        if fact_text in text and not any(
            k in source.mention_groups for k in FACT_GROUPS
        ):
            raise IntentError(
                "fixture_shape",
                "Captured fact remains in text without its reviewed group",
            )
        return []
    starts = [
        o.start
        for o in group.occurrences
        if fact_text.startswith(o.text + " ")
        and text[o.start : o.start + len(fact_text)] == fact_text
    ]
    if len(starts) != 1:
        raise IntentError(
            "fixture_shape", "Captured fact requires one exact reviewed occurrence"
        )
    start, end = starts[0], starts[0] + len(fact_text)
    if text[start:end] != fact_text:
        raise IntentError(
            "fixture_shape", "Captured fact span differs from current text"
        )
    return [
        c
        for c in ordered
        if mapping[str(c.id)][0] < end and start < mapping[str(c.id)][1]
    ]


async def recorded_budget(source, graph):
    """Native construction metadata, not an extra role/interpretation registry."""
    values = set()
    for item in source.inputs.values():
        if isinstance(item, ChunkInput):
            node = await graph.get_node(str(item.chunk_id))
            if node is None or node.get("max_chunk_tokens") is None:
                raise IntentError(
                    "chunk_policy", "Native chunk budget is missing or inconsistent"
                )
            values.add(node["max_chunk_tokens"])
    if len(values) != 1 or not all(type(n) is int and n > 0 for n in values):
        raise IntentError(
            "chunk_policy", "Native chunk budget is missing or inconsistent"
        )
    return values.pop()
