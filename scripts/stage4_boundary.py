import asyncio
from pathlib import Path

import cognee
from cognee import SearchType

from cognee_lab.models import AbbreviationGraph


DATASET = "helios_stage4_boundary"

DOCUMENT = Path(
    "data/DOC01_helios1_technical_overview_v2.md"
)


async def main():
    await cognee.add(
        str(DOCUMENT),
        dataset_name=DATASET,
    )

    await cognee.cognify(
        datasets=DATASET,
        graph_model=AbbreviationGraph,
        chunk_size=1000,
    )

    # Verify that non-semantic retrieval infrastructure still works.
    for search_type in (
        SearchType.CHUNKS,
        SearchType.SUMMARIES,
    ):
        print("\n" + "=" * 80)
        print(search_type.value)
        print("=" * 80)

        results = await cognee.search(
            query_text="Vertical Control System VCS",
            query_type=search_type,
            datasets=DATASET,
            top_k=2,
        )

        print("results:", len(results))

        for result in results:
            if hasattr(result, "model_dump"):
                print(result.model_dump())
            else:
                print(result)


if __name__ == "__main__":
    asyncio.run(main())
