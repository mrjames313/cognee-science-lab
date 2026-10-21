"""Captured occurrence removal; explicit review, not a Describe matcher."""

import json

from .captured_chunks import bind_chunks
from .models import IdentitySource
from .validation import IntentError, text_digest

BEFORE = (
    "Helios controller (HC) regulates plasma heating, the controller adjusts "
    "coil current, and it limits oscillations.\n"
)
AFTER = "Helios controller (HC) regulates heating, and it limits oscillations.\n"
RETENTION = {"g01": [1], "g02": []}


def describe_removal(old, before, chunks):
    if before != BEFORE or set(old.mention_groups) != set(RETENTION):
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


async def run(args, root):
    from .captured_chunks import recorded_budget
    from .fixture import context_for
    from .multisource import current_sources, snapshot
    from .publish import Publisher
    from .text_changes import TextChange, chunk_text, original_context, read_original
    from .text_fixture import maintain_one

    if args.source != "doc01" or not (root / "chunked-fixture-info.json").exists():
        raise IntentError(
            "fixture_scope", "Occurrence removal requires doc01 of a chunked-fixture"
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
    after, retention, describe = AFTER, RETENTION, describe_removal
    result_name = "occurrence_revision_result.json"
    continuity = regrouping = None
    if args.command == "add-occurrences":
        from .occurrence_addition import (
            AFTER as added_text,
            CONTINUITY,
            describe_addition,
        )

        after, retention, describe = added_text, None, describe_addition
        continuity = CONTINUITY
        result_name = "occurrence_addition_result.json"
    if args.command == "split-group":
        from .group_regrouping import AFTER as split_text, REGROUPING, describe_split

        after, retention, describe = split_text, None, describe_split
        regrouping = REGROUPING
        result_name = "group_split_result.json"
    if args.command == "retire-resolved-group":
        from .resolved_retirement import (
            AFTER as retired_text,
            RETENTION as retired_indices,
            describe_retirement,
        )

        after, retention, describe = retired_text, retired_indices, describe_retirement
        result_name = "resolved_retirement_result.json"
    change = TextChange(
        before,
        after,
        await recorded_budget(old, publisher.graph),
        occurrence_retention=retention,
        occurrence_continuity=continuity,
        occurrence_regrouping=regrouping,
    )
    chunks = await chunk_text(
        after, await original_context(old, ctx), change.chunk_budget
    )
    intended = describe(old, before, chunks)
    (root / f"identity_doc01_occurrence_revision{intended.revision}.json").write_text(
        intended.model_dump_json(indent=2) + "\n"
    )
    (root / f"source_doc01_revision{intended.revision}.txt").write_text(after)
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
    (root / result_name).write_text(json.dumps(result, indent=2))
    return result
