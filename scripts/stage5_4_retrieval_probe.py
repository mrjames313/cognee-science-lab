"""
Stage 5.4.3 — Native Cognee retrieval characterization.

Runs the same identity-sensitive queries through:

    RAG_COMPLETION
    GRAPH_COMPLETION
    HYBRID_COMPLETION

using the modern recall() interface and only_context=True.

No graph modifications are made.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import cognee
from cognee import SearchType
from dotenv import load_dotenv

load_dotenv()


DATASET = "helios_stage2"

OUTPUT = Path(
    "outputs/stage5_4_native_retrieval_probe.json"
)


QUERIES = [
    {
        "id": "RET01",
        "label": "NBI variant",
        "query": (
            "How much auxiliary heating power can NBI provide?"
        ),
    },
    {
        "id": "RET02",
        "label": "NBI canonical",
        "query": (
            "How much auxiliary heating power can "
            "neutral beam injection provide?"
        ),
    },
    {
        "id": "RET03",
        "label": "VCS variant",
        "query": (
            "During Campaign A, what did VCS do during "
            "the current ramp?"
        ),
    },
    {
        "id": "RET04",
        "label": "VCS canonical",
        "query": (
            "During Campaign A, what did the vertical "
            "control system do during the current ramp?"
        ),
    },
    {
        "id": "RET05",
        "label": "Contextual controller",
        "query": (
            "As edge density fell, what did the controller "
            "do with the gas command?"
        ),
    },
]


SEARCH_TYPES = [
    SearchType.RAG_COMPLETION,
    SearchType.GRAPH_COMPLETION,
    SearchType.HYBRID_COMPLETION,
]


def json_safe(value: Any):
    if isinstance(value, dict):
        return {
            str(k): json_safe(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            json_safe(v)
            for v in value
        ]

    if hasattr(value, "model_dump"):
        return json_safe(
            value.model_dump()
        )

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            type(None),
        ),
    ):
        return value

    return str(value)


def print_result(result):
    if not result:
        print("  <empty>")
        return

    for index, item in enumerate(
        result,
        start=1,
    ):
        print(
            f"\n--- result {index} ---"
        )

        if hasattr(item, "source"):
            print(
                "source:",
                getattr(item, "source"),
            )

        if hasattr(item, "text"):
            print(
                getattr(item, "text")
            )
        else:
            print(item)

        system_prompt = getattr(
            item,
            "system_prompt",
            None,
        )

        if system_prompt:
            print(
                "\n[SYSTEM PROMPT]"
            )
            print(system_prompt)


async def main():
    report = {
        "dataset": DATASET,
        "queries": [],
    }

    for query_case in QUERIES:
        print()
        print("=" * 80)

        print(
            query_case["id"],
            query_case["label"],
        )

        print(
            "QUERY:",
            query_case["query"],
        )

        case_report = {
            **query_case,
            "retrievals": {},
        }

        for search_type in SEARCH_TYPES:
            print()
            print("-" * 80)

            print(
                "SEARCH TYPE:",
                search_type.value,
            )

            try:
                result = await cognee.recall(
                    query_case["query"],
                    query_type=search_type,
                    datasets=[DATASET],
                    top_k=10,
                    only_context=True,
                )

                print_result(result)

                case_report[
                    "retrievals"
                ][search_type.value] = {
                    "status": "ok",
                    "result": json_safe(
                        result
                    ),
                }

            except Exception as exc:
                print(
                    "ERROR:",
                    repr(exc),
                )

                case_report[
                    "retrievals"
                ][search_type.value] = {
                    "status": "error",
                    "error": repr(exc),
                }

        report["queries"].append(
            case_report
        )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print(
        f"Saved: {OUTPUT}"
    )


if __name__ == "__main__":
    asyncio.run(main())
