"""Exact chunk binding and fact spans for the captured fixture, not inference."""

from dataclasses import dataclass
from uuid import UUID

from .models import ChunkInput
from .validation import IntentError, fresh_mention_id, map_chunks

FACT_TEXT = "it limits oscillations"
ADDITION = "stage6-captured-occurrence-addition"
SPLIT = "stage6-captured-group-split"
COMBINATION = "stage6-captured-group-combination"
ADDED_FACT_TEXT = "the controller limits oscillations"
REINTERPRET_ENTITY = "stage6-captured-reinterpretation-new-entity"
REINTERPRET_UNRESOLVED = "stage6-captured-reinterpretation-unresolved"
TO_MENTION = "stage6-captured-kind-change-to-mention"
TO_REUSABLE = "stage6-captured-kind-change-to-reusable"


@dataclass(frozen=True)
class CapturedGroup:
    key: str
    created: int
    creator: str | None
    fact: str | None


# `creator` is the producer implementation of the fixture edit that declares
# the group; None marks an original group. A group has retired only when its
# creating edit is in the source's lineage and the source no longer declares
# it, because different edit sequences reach the same revision number. This
# relies on describers only adding producers, never removing one. Edits that
# a root never combines may reuse a key, as g03 shows, so a source reads only
# the entries of its own lineage.
CAPTURED = (
    CapturedGroup("g01", 1, None, FACT_TEXT),
    CapturedGroup("g03", 2, ADDITION, ADDED_FACT_TEXT),
    CapturedGroup("g04", 2, SPLIT, None),
    CapturedGroup("g05", 2, SPLIT, FACT_TEXT),
    CapturedGroup("g06", 3, COMBINATION, FACT_TEXT),
    CapturedGroup("g03", 2, REINTERPRET_ENTITY, FACT_TEXT),
    CapturedGroup("g03", 2, REINTERPRET_UNRESOLVED, FACT_TEXT),
    CapturedGroup("g03", 2, TO_MENTION, None),
)


def lineage_groups(source):
    """The captured groups that the source's edits can have declared, by key."""
    lineage = {p.implementation for p in source.producers.values()}
    return {g.key: g for g in CAPTURED if g.creator is None or g.creator in lineage}


def captured_facts(source):
    """Explicit fixture outputs, independent of model inference or label matching."""
    for key, group in lineage_groups(source).items():
        if group.fact and key in source.mention_groups:
            yield key, group.fact


def retired_keys(source):
    return [key for key in lineage_groups(source) if key not in source.mention_groups]


def retired_facts(source):
    groups = lineage_groups(source)
    for key in retired_keys(source):
        if groups[key].fact:
            yield key, groups[key].fact


def fixture_mention_id(source, key="g01"):
    """Known captured fixture identity, including after its declaration retires."""
    group = source.mention_groups.get(key)
    if group is not None:
        return group.entity_id
    if key != "g01":
        groups = lineage_groups(source)
        if key not in groups:
            raise IntentError("fixture_shape", f"Unknown captured group {key}")
        return fresh_mention_id(source.identity_data_id, groups[key].created, key)
    if source.identity_data_id == UUID("718efce2-4251-5f6f-8318-417bb4dd3525"):
        return UUID("233cb019-3986-5864-88bc-91f334a64372")
    raise IntentError(
        "fixture_shape", "Missing primary group outside the captured retirement fixture"
    )


def retired_mentions(source):
    return {key: fixture_mention_id(source, key) for key in retired_keys(source)}


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
            k in source.mention_groups
            for k, g in lineage_groups(source).items()
            if g.fact == fact_text
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
