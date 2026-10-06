import asyncio
from pathlib import Path

import cognee

from cognee_lab.models import MixedKnowledgeGraph


DATASET = "helios_stage4_mixed"

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
        graph_model=MixedKnowledgeGraph,
        chunk_size=1000,
    )


if __name__ == "__main__":
    asyncio.run(main())
