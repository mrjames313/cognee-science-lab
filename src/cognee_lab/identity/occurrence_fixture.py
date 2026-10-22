"""Captured occurrence edits on doc01; explicit review, not a Describe matcher."""

import json
from dataclasses import dataclass
from typing import Callable

from . import kind_change, reinterpretation
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
from .captured_revision import (
    begin_revision,
    occurrence,
    require_fresh_doc01,
    retire_group,
    stamp_producer,
)
from .validation import IntentError

AFTER = "Helios controller (HC) regulates heating, and it limits oscillations.\n"
REMOVAL_MAP = {"g01": [None, ["g01", 0]], "g02": [None]}
# The mixed edit drops `the controller` and `plasma`, keeps `it`, and adds a
# startup reference to g01. Its map equals the removal map: the addition is the
# new occurrence that no old occurrence maps to.
MIXED_AFTER = AFTER.rstrip("\n") + " During startup, the controller remains active.\n"
MIXED_MAP = REMOVAL_MAP


def keep_g01_retire_g02(old, before, chunks, *, after, occurrences, producer):
    """g01 continues with the captured occurrences; g02 retires."""
    require_fresh_doc01(
        old,
        before,
        {"g01", "g02"},
        "Use doc01 of a fresh chunked-fixture for this captured edit",
    )
    payload = begin_revision(old, after, "occurrence_review", *producer)
    # Positions and continuity are captured example input, never nearest-text matching.
    payload["mention_groups"]["g01"]["occurrences"] = occurrences
    retire_group(payload, "g02")
    stamp_producer(payload, "occurrence_review")
    bind_chunks(payload, after, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def describe_removal(old, before, chunks):
    return keep_g01_retire_g02(
        old,
        before,
        chunks,
        after=AFTER,
        occurrences=[occurrence(AFTER, "it", "it limits")],
        producer=(
            "stage6-captured-occurrence-removal",
            "explicit-survivors-unchanged-binding-v1",
        ),
    )


def describe_mixed(old, before, chunks):
    return keep_g01_retire_g02(
        old,
        before,
        chunks,
        after=MIXED_AFTER,
        occurrences=[
            occurrence(MIXED_AFTER, "it", "it limits"),
            occurrence(MIXED_AFTER, "the controller", "the controller remains"),
        ],
        producer=("stage6-captured-occurrence-revision", "explicit-occurrence-map-v1"),
    )


@dataclass(frozen=True)
class OccurrenceCommand:
    after: str
    describe: Callable
    result_name: str
    occurrence_map: dict
    # An async (publisher, sources) callable that adds what the shared snapshot
    # does not report, under the keys it returns.
    inspect: Callable | None = None


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
    "reinterpret-new-entity": OccurrenceCommand(
        reinterpretation.NEW_ENTITY_AFTER,
        reinterpretation.describe_new_entity,
        "reinterpretation_new_entity_result.json",
        reinterpretation.ENTITY_MAP,
        reinterpretation.inspect_new_entity,
    ),
    "reinterpret-unresolved": OccurrenceCommand(
        reinterpretation.UNRESOLVED_AFTER,
        reinterpretation.describe_unresolved,
        "reinterpretation_unresolved_result.json",
        reinterpretation.UNRESOLVED_MAP,
        reinterpretation.inspect_unresolved,
    ),
    "change-kind-to-mention": OccurrenceCommand(
        BEFORE,
        kind_change.describe_to_mention,
        "kind_change_to_mention_result.json",
        kind_change.TO_MENTION_MAP,
        kind_change.inspect,
    ),
    "change-kind-to-reusable": OccurrenceCommand(
        BEFORE,
        kind_change.describe_to_reusable,
        "kind_change_to_reusable_result.json",
        kind_change.TO_REUSABLE_MAP,
        kind_change.inspect,
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
    sources = await current_sources(root, publisher)
    result = await snapshot(publisher, sources, args.query)
    if command.inspect is not None:
        result.update(await command.inspect(publisher, sources))
    (root / command.result_name).write_text(json.dumps(result, indent=2))
    return result
