"""Generated JSON snapshots through Cognee's Data, ingestion and file interfaces."""

from uuid import UUID

from .models import IdentitySource
from .validation import IntentError


async def context_for(data_id):
    """The context the lab writes a registered Data item's content with:
    its user, Data row and dataset, and no pipeline run ID."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data, Dataset
    from cognee.modules.pipelines.models import PipelineContext
    from cognee.modules.users.methods import get_default_user

    user = await get_default_user()
    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, UUID(str(data_id)))
        if data is None:
            raise IntentError("source_missing", "Fixture Data item missing")
        dataset = await session.get(Dataset, data.dataset_id)
    return PipelineContext(
        user=user,
        data_item=data,
        dataset=dataset,
        pipeline_name="stage6_captured_fixture",
    )


async def read_registered(source):
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data
    from cognee.infrastructure.files.utils.open_data_file import open_data_file
    from cognee.modules.ingestion.data_types import TextData

    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, source.identity_data_id)
        if data is None or data.dataset_id != source.dataset_id:
            raise IntentError(
                "source_missing", "Registered identity Data item is missing"
            )
    try:
        async with open_data_file(
            data.raw_data_location, mode="r", encoding="utf-8"
        ) as f:
            text = f.read()
            result = IdentitySource.model_validate_json(text)
        if TextData(text).get_metadata()["content_hash"] != data.raw_content_hash:
            raise ValueError("Raw content hash does not match registered bytes")
    except (OSError, ValueError) as exc:
        raise IntentError(
            "generated_source_changed",
            "Registered identity snapshot is unreadable or invalid",
        ) from exc
    return result


async def read_texts(source, known=None):
    """The registered text of every source_text input, keyed by input ref.
    `known` supplies the text of inputs that are not registered yet. Another
    document whose Data item is gone has no entry."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.infrastructure.files.utils.open_data_file import open_data_file
    from cognee.modules.data.models import Data
    from .models import SourceTextInput

    texts = dict(known or {})
    async with get_relational_engine().get_async_session() as session:
        for key, item in source.inputs.items():
            if not isinstance(item, SourceTextInput) or key in texts:
                continue
            data = await session.get(Data, item.data_id)
            if data is None or data.dataset_id != item.dataset_id:
                # Another document that is gone withholds the decisions
                # citing it; validation reports it as input_removed.
                if key != source.original_input_ref:
                    continue
                raise IntentError("source_missing", "Original Data item missing")
            async with open_data_file(
                data.raw_data_location, mode="r", encoding="utf-8"
            ) as f:
                texts[key] = f.read()
    return texts


async def write_registered(source, ctx):
    payload = source.model_dump_json(indent=2) + "\n"
    await write_text(payload, ctx, source.identity_data_id)
    if await read_registered(source) != source:
        raise IntentError(
            "generated_source_changed",
            "Registered snapshot does not match saved intent",
        )


async def stamp(data_id, dataset_id):
    """Mark a lab-managed Data item as cognified, so a plain `cognee.cognify`
    skips it instead of extracting it with the LLM. Ingesting changed text
    and a per-item `cognee.forget(memory_only=True)` clear the mark, so each
    caller of those stamps again."""
    from cognee.modules.data.methods.publish_updated_data import mark_data_processed

    await mark_data_processed(data_id, dataset_id)


async def stamped(data_id, dataset_id) -> bool:
    """Whether a plain `cognee.cognify` of the dataset skips the item."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data
    from cognee.modules.pipelines.models.DataItemStatus import (
        is_data_item_completed,
    )

    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, data_id)
    status = (data.pipeline_status or {}) if data is not None else {}
    return is_data_item_completed(
        (status.get("cognify_pipeline") or {}).get(str(dataset_id))
    )


async def write_text(payload, ctx, data_id):
    """Update one explicitly selected Data item through the native ingestion
    Task, and stamp it again: changed text clears the stamp. The item keeps
    its name: the payload goes in as an upload of the item's own file name,
    because Cognee names a plain string `text_<md5>` and renames on update.
    The name rides on the stream, not on `filename`, because Cognee turns a
    `filename` into a `source_uri` that points at a file that does not exist.
    Changed text leaves the previous derived text file, which Cognee does not
    queue for removal, so it is removed here once no row references it."""
    from io import BytesIO
    from types import SimpleNamespace

    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.tasks.ingestion.data_item import DataItem
    from cognee.tasks.ingestion.ingest_data import ingest_data
    from cognee.modules.ingestion.data_types import TextData
    import json
    from copy import deepcopy

    old = ctx.data_item
    node_set = old.node_set
    if isinstance(node_set, str):
        node_set = json.loads(node_set)
    external = deepcopy(old.external_metadata) if old.external_metadata else None
    # The replacement is now managed from saved intent, rather than reloaded
    # from the previous caller's file URI. This includes original fixture text.
    if external and isinstance(external.get("_cognee"), dict):
        external["_cognee"].pop("source_uri", None)
    stream = BytesIO(payload.encode("utf-8"))
    stream.name = f"{old.name}.{old.extension}"
    upload = SimpleNamespace(file=stream, filename=None)
    previous_raw = old.raw_data_location
    items = await ingest_data(
        DataItem(
            data=upload,
            data_id=data_id,
            label=old.label,
            external_metadata=external,
            system_metadata=old.system_metadata,
        ),
        dataset_name=ctx.dataset.name,
        dataset_id=ctx.dataset.id,
        user=ctx.user,
        node_set=node_set,
        importance_weight=(
            old.importance_weight if old.importance_weight is not None else 0.5
        ),
        ctx=ctx,
    )
    if len(items) != 1 or items[0].id != data_id:
        raise IntentError(
            "generated_source_changed",
            "Ingestion did not preserve the selected Data identity",
        )
    ctx.data_item = items[0]
    metadata = TextData(payload).get_metadata()
    if (
        ctx.data_item.content_hash != metadata["content_hash"]
        or ctx.data_item.raw_content_hash != metadata["content_hash"]
        or ctx.data_item.data_size != metadata["file_size"]
    ):
        raise IntentError(
            "generated_source_changed",
            "Registered content metadata is inconsistent",
        )
    if previous_raw != ctx.data_item.raw_data_location:
        await get_relational_engine().remove_data_file_if_unreferenced(previous_raw)
    await stamp(data_id, ctx.dataset.id)
