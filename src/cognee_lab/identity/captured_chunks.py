"""Exact chunk binding and fact spans for the captured fixture, not inference."""

from .models import ChunkInput
from .validation import IntentError, map_chunks

FACT_TEXT = "it limits oscillations"


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


def fact_chunks(source, chunks):
    """The captured fact starts at the explicitly stored 'it' occurrence.

    Its whole literal span is supplied fixture knowledge. This does not derive
    facts from arbitrary text or assign all group chunks as fact evidence.
    """
    group = source.mention_groups["g01"]
    starts = [o.start for o in group.occurrences if o.text == "it"]
    if len(starts) != 1:
        raise IntentError(
            "fixture_shape", "Captured fact requires one explicit 'it' occurrence"
        )
    ordered = sorted(chunks, key=lambda c: c.chunk_index)
    text = "".join(c.text for c in ordered)
    mapping = map_chunks(text, ordered)
    start, end = starts[0], starts[0] + len(FACT_TEXT)
    if text[start:end] != FACT_TEXT:
        raise IntentError(
            "fixture_shape", "Captured fact span differs from current text"
        )
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
