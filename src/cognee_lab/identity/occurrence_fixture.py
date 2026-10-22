"""Captured occurrence edits on doc01; explicit review, not a Describe matcher."""

import json
from dataclasses import dataclass
from typing import Callable

from .captured_chunks import bind_chunks
from .captured_text import BEFORE
from .group_regrouping import (
    COMBINE_AFTER,
    COMBINE_MAP,
    SPLIT_AFTER,
    SPLIT_MAP,
    describe_combination,
    describe_split,
)
from .models import IdentitySource
from .occurrence_addition import AFTER as added_text, ADDITION_MAP, describe_addition
from .resolved_retirement import (
    AFTER as retired_text,
    RETIREMENT_MAP,
    describe_retirement,
)
from .validation import IntentError, text_digest

AFTER = "Helios controller (HC) regulates heating, and it limits oscillations.\n"
REMOVAL_MAP = {"g01": [None, ["g01", 0]], "g02": [None]}
# The mixed edit drops `the controller` and `plasma`, keeps `it`, and adds a
# startup reference to g01. Its map equals the removal map: the addition is the
# new occurrence that no old occurrence maps to.
MIXED_AFTER = AFTER.rstrip("\n") + " During startup, the controller remains active.\n"
MIXED_MAP = {"g01": [None, ["g01", 0]], "g02": [None]}


def occurrence(text, phrase, anchor=None):
    anchor = anchor or phrase
    start = text.index(anchor) + anchor.index(phrase)
    return dict(start=start, end=start + len(phrase), text=phrase)


def revise_doc01(old, before, chunks, after, occurrences, implementation, policy):
    """Keep g01 with the captured occurrences and retire g02."""
    if before != BEFORE or set(old.mention_groups) != {"g01", "g02"}:
        raise IntentError(
            "fixture_scope",
            "Use doc01 of a fresh chunked-fixture for this captured edit",
        )
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(after)
    payload["producers"]["occurrence_review"] = dict(
        method="captured_fixture",
        implementation=implementation,
        version="0.1",
        configuration={"policy": policy},
        run_id=None,
    )
    # Positions and continuity are captured example input, never nearest-text matching.
    payload["mention_groups"]["g01"]["occurrences"] = occurrences
    retired = payload["mention_groups"].pop("g02")["entity_id"]
    payload["entity_constructions"].pop(retired)
    payload["mention_resolutions"] = {
        k: v
        for k, v in payload["mention_resolutions"].items()
        if v["group_ref"] != "g02"
    }
    for item in [
        *payload["mention_groups"].values(),
        *payload["mention_resolutions"].values(),
        *payload["variant_assignments"].values(),
    ]:
        item["producer_ref"] = "occurrence_review"
    bind_chunks(payload, after, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_removal(old, before, chunks):
    return revise_doc01(
        old,
        before,
        chunks,
        AFTER,
        [occurrence(AFTER, "it", "it limits")],
        "stage6-captured-occurrence-removal",
        "explicit-survivors-unchanged-binding-v1",
    )


def describe_mixed(old, before, chunks):
    return revise_doc01(
        old,
        before,
        chunks,
        MIXED_AFTER,
        [
            occurrence(MIXED_AFTER, "it", "it limits"),
            occurrence(MIXED_AFTER, "the controller", "the controller remains"),
        ],
        "stage6-captured-occurrence-revision",
        "explicit-occurrence-map-v1",
    )


@dataclass(frozen=True)
class OccurrenceCommand:
    after: str
    describe: Callable
    result_name: str
    occurrence_map: dict


COMMANDS = {
    "remove-occurrences": OccurrenceCommand(
        AFTER,
        describe_removal,
        "occurrence_revision_result.json",
        REMOVAL_MAP,
    ),
    "revise-occurrences": OccurrenceCommand(
        MIXED_AFTER,
        describe_mixed,
        "occurrence_mix_result.json",
        MIXED_MAP,
    ),
    "retire-resolved-group": OccurrenceCommand(
        retired_text,
        describe_retirement,
        "resolved_retirement_result.json",
        RETIREMENT_MAP,
    ),
    "add-occurrences": OccurrenceCommand(
        added_text,
        describe_addition,
        "occurrence_addition_result.json",
        ADDITION_MAP,
    ),
    "split-group": OccurrenceCommand(
        SPLIT_AFTER,
        describe_split,
        "group_split_result.json",
        SPLIT_MAP,
    ),
    "combine-groups": OccurrenceCommand(
        COMBINE_AFTER,
        describe_combination,
        "group_combination_result.json",
        COMBINE_MAP,
    ),
}


async def run(args, root):
    from .captured_chunks import recorded_budget
    from .fixture import context_for
    from .multisource import current_sources, snapshot
    from .publish import Publisher
    from .text_changes import TextChange, chunk_text, original_context, read_original
    from .text_fixture import maintain_one

    command = COMMANDS[args.command]
    if args.source != "doc01" or not (root / "chunked-fixture-info.json").exists():
        raise IntentError(
            "fixture_scope", f"{args.command} requires doc01 of a chunked-fixture"
        )
    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    old = (await current_sources(root, publisher))["doc01"]
    row = next(
        r
        for r in await publisher.records.rows(old.dataset_id)
        if r["source"] == str(old.identity_data_id)
    )
    if row["revision"] != args.expected_revision:
        raise IntentError("stale_revision", "Saved revision changed")
    if row["state"] != "current":
        raise IntentError(
            "recovery_choice", "Reconcile the exact saved replacement explicitly"
        )
    ctx = await context_for(old.identity_data_id)
    before = await read_original(old, ctx)
    change = TextChange(
        before,
        command.after,
        command.occurrence_map,
        await recorded_budget(old, publisher.graph),
    )
    chunks = await chunk_text(
        command.after, await original_context(old, ctx), change.chunk_budget
    )
    intended = command.describe(old, before, chunks)
    (root / f"identity_doc01_occurrence_revision{intended.revision}.json").write_text(
        intended.model_dump_json(indent=2) + "\n"
    )
    (root / f"source_doc01_revision{intended.revision}.txt").write_text(command.after)
    await maintain_one(
        publisher,
        intended,
        change,
        expected_revision=args.expected_revision,
        fault_stage=args.fault_stage,
    )
    result = await snapshot(
        publisher, await current_sources(root, publisher), args.query
    )
    (root / command.result_name).write_text(json.dumps(result, indent=2))
    return result
