"""Captured stand-ins for plain Cognee calls outside the lab that meet search.

- `native-add`: a plain `cognee.add` of one text into a second dataset,
  `outside_dataset`, so the user can read two datasets and a search with
  `datasets=None` gives the retriever none.
- `native-search`: a plain `cognee.search` with `SearchType.CHUNKS` on the
  root's dataset. It reads Cognee's chunk index, which ignores the ledger, so
  it serves the chunks of failed and withheld sources too.

Neither writes a ledger row.
"""

OUTSIDE_DATASET = "outside_dataset"
OUTSIDE_TEXT = "Aurora controller limits vibrations in the cryostat."


async def run(args, root):
    import cognee
    from cognee.modules.data.methods import get_datasets
    from cognee.modules.search.types import SearchType
    from cognee.modules.users.methods import get_default_user

    from .environment import DATASET_NAME
    from .publish import Publisher

    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    if args.command == "native-add":
        await cognee.add(
            OUTSIDE_TEXT, dataset_name=OUTSIDE_DATASET, skip_connection_test=True
        )
        user = await get_default_user()
        return dict(
            native_add=dict(
                dataset=OUTSIDE_DATASET,
                datasets=sorted(d.name for d in await get_datasets(user.id)),
            )
        )
    (found,) = await cognee.search(
        args.query, query_type=SearchType.CHUNKS, datasets=[DATASET_NAME], verbose=True
    )
    return dict(
        native_search=dict(
            search_type="CHUNKS",
            chunks=[
                dict(id=str(c.id), text=c.payload.get("text", ""))
                for c in found["objects_result"] or []
            ],
        )
    )
