import asyncio

import cognee
from sqlalchemy import inspect as sa_inspect

DATASET = "helios_stage2"


def dump_orm(obj):
    mapper = sa_inspect(obj).mapper

    return {
        attr.key: getattr(obj, attr.key)
        for attr in mapper.column_attrs
    }


async def main():
    datasets = await cognee.datasets.list_datasets()

    dataset = next(d for d in datasets if d.name == DATASET)

    print("DATASET")
    for key,value in dump_orm(dataset).items():
        print(f"   {key}: {value!r}")

    data_items = await cognee.datasets.list_data(dataset.id)

    for i, item in enumerate(data_items):
        print(f"\nDATA ITEM {i}")

        for key, value in dump_orm(item).items():
            print(f"  {key}: {value!r}")


if __name__ == "__main__":
    asyncio.run(main())
    
