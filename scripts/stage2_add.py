import asyncio
from pathlib import Path

import cognee

DATASET = "helios_stage2"
DOC01 = Path("data/DOC01_helios1_technical_overview_V2.md").resolve()

async def main():
    print(f"Adding: {DOC01}")
    print(f"Dataset: {DATASET}")

    result = await cognee.add(
        str(DOC01),
        dataset_name=DATASET,
    )

    print("\nadd() results:")
    print(result)

    datasets = await cognee.datasets.list_datasets()

    print("\nDatasets:")
    for dataset in datasets:
        print(dataset)

    dataset = next(d for d in datasets if d.name == DATASET)

    print("\nData items in dataset:")
    data_items = await cognee.datasets.list_data(dataset.id)

    for item in data_items:
        print(item)
        if hasattr(item, "model_dump"):
            print(item.model_dump())

if __name__ == "__main__":
    asyncio.run(main())
