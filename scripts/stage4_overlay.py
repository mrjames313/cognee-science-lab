import asyncio
from pathlib import Path

import cognee

from cognee.tasks.storage import add_data_points

from cognee_lab.models import (
    AbbreviationObservation,
    MixedKnowledgeGraph,
)


DATASET = "helios_stage4_overlay"

DOCUMENT = Path(
    "data/DOC01_helios1_technical_overview_v2.md"
)


async def main():
    MixedKnowledgeGraph.clear_capture()

    await cognee.add(
        str(DOCUMENT),
        dataset_name=DATASET,
    )

    # Normal Cognee graph construction, but with the mixed
    # extraction envelope from 4.2b.
    await cognee.cognify(
        datasets=DATASET,
        graph_model=MixedKnowledgeGraph,
        chunk_size=1000,
    )

    extracted = MixedKnowledgeGraph.captured_abbreviations

    print("\nCaptured abbreviation DTOs:")
    for item in extracted:
        print(
            f"  {item.short_form!r}"
            f" -> {item.full_form!r}"
        )

    # Remove only exact duplicate observations.
    # Do NOT canonicalize different expansions yet.
    unique = {}

    for item in extracted:
        short_form = item.short_form.strip()
        full_form = item.full_form.strip()

        key = (short_form, full_form)

        unique[key] = AbbreviationObservation(
            short_form=short_form,
            full_form=full_form,
        )

    observations = list(unique.values())

    print(
        f"\nCaptured {len(extracted)} records; "
        f"{len(observations)} distinct observations."
    )

    # Typed overlay: persist alongside the already-built
    # generic Cognee graph.
    await add_data_points(observations)

    print(
        f"Persisted {len(observations)} "
        "AbbreviationObservation nodes."
    )


if __name__ == "__main__":
    asyncio.run(main())
