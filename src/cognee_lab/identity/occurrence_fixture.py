"""Captured occurrence removal; explicit review, not a Describe matcher."""

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


def describe_removal(old, before, chunks):
    if before != BEFORE or set(old.mention_groups) != set(REMOVAL_MAP):
        raise IntentError(
            "fixture_scope",
            "Use doc01 of a fresh chunked-fixture for captured occurrence removal",
        )
    payload = old.model_dump(mode="json")
    payload["revision"] += 1
    payload["inputs"][old.original_input_ref]["text_sha256"] = text_digest(AFTER)
    payload["producers"]["occurrence_review"] = dict(
        method="captured_fixture",
        implementation="stage6-captured-occurrence-removal",
        version="0.1",
        configuration={"policy": "explicit-survivors-unchanged-binding-v1"},
        run_id=None,
    )
    # Positions and continuity are captured example input, never nearest-text matching.
    start = len("Helios controller (HC) regulates heating, and ")
    payload["mention_groups"]["g01"]["occurrences"] = [
        dict(start=start, end=start + 2, text="it")
    ]
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
    bind_chunks(payload, AFTER, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


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
