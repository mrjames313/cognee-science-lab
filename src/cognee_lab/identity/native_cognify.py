"""A captured stand-in for a plain `cognee.cognify` outside the lab.

`native-cognify` runs Cognee's own cognify on the root's dataset as a user
would, with Cognee's defaults. The lab stamps every file it manages as
cognified, so Cognee skips each one and makes no LLM call. The fixture
environment points the LLM at a closed loopback port, so an item Cognee did
not skip fails the command instead of reaching a provider.
"""


async def run(args, root):
    import os

    os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"
    import cognee

    from .environment import DATASET_NAME
    from .publish import Publisher

    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    runs = await cognee.cognify(datasets=[DATASET_NAME])
    items = {
        str(item["data_id"]): type(item["run_info"]).__name__
        for info in runs.values()
        for item in info.data_ingestion_info or []
    }
    return dict(native_cognify=dict(items=items))
