"""What Cognee still holds of a saved source.

A delete outside the lab, through Cognee's own API, writes no ledger row:
`cognee.forget` of a Data item or a dataset, Cognee's default prune, or an
incremental `cognee.update` that replaces the chunks. `status` lists each
saved source whose native copy is gone or changed (`natively_deleted`),
`Publisher.refuse_natively_deleted` refuses to reconcile it, and `forget`
erases the lab's copy. A dependent whose copy is gone waits for its own
forget (`erasure.finish_dependents`).
"""

from typing import NamedTuple
from uuid import UUID

from .models import ChunkInput
from .retirement import source_ids


class NativeCopy(NamedTuple):
    """What Cognee still holds of a saved source. Each facet is needed: a
    native forget of the original takes its Data row and document node; a
    dataset forget takes both Data rows and the graph; the default prune
    keeps the Data rows but takes the graph and the stored files; an
    incremental `cognee.update` keeps the Data row and replaces the chunks."""

    original_data: bool
    identity_data: bool
    document_node: bool
    chunks: bool
    stored_files: bool

    @property
    def missing(self) -> list[str]:
        return [facet for facet in self._fields if not getattr(self, facet)]


async def data_present(data_id, dataset_id):
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data

    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, UUID(str(data_id)))
    return data is not None and data.dataset_id == dataset_id


async def raw_file_present(data_id, dataset_id) -> bool:
    """Whether the Data item is registered and its raw file can be opened."""
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.infrastructure.files.utils.open_data_file import open_data_file
    from cognee.modules.data.models import Data

    async with get_relational_engine().get_async_session() as session:
        data = await session.get(Data, UUID(str(data_id)))
    if data is None or data.dataset_id != dataset_id or not data.raw_data_location:
        return False
    try:
        async with open_data_file(data.raw_data_location, mode="rb"):
            return True
    except OSError:
        return False


async def native_copy(graph, source) -> NativeCopy:
    """The native copy of a saved description, facet by facet."""
    ids = source_ids(source)
    chunk_ids = [
        str(i.chunk_id) for i in source.inputs.values() if isinstance(i, ChunkInput)
    ]
    return NativeCopy(
        original_data=await data_present(ids.original_data_id, ids.dataset_id),
        identity_data=await data_present(ids.identity_data_id, ids.dataset_id),
        document_node=await graph.get_node(str(ids.original_data_id)) is not None,
        chunks=all([await graph.get_node(c) is not None for c in chunk_ids]),
        stored_files=all(
            [
                await raw_file_present(data_id, ids.dataset_id)
                for data_id in (ids.original_data_id, ids.identity_data_id)
            ]
        ),
    )


async def missing_native(graph, row) -> list[str]:
    """The facets of the row's native copy that are gone. None for a row
    with no native copy to compare: a forgotten row, one whose forget
    resumes, a pending one, or a failed text change, whose own retry
    rebuilds the document."""
    if (
        row.description is None
        or row.state == "pending"
        or row.resumed_by == "forget"
        or row.failed_attempt == "text_change"
    ):
        return []
    return (await native_copy(graph, row.description)).missing


def deleted_entry(row, missing) -> dict:
    """What `status` and a snapshot report of a row whose native copy is
    gone: its identifiers, state and saved revision, which a forget names,
    and the missing facets."""
    return dict(
        identity_data_id=row.source,
        dataset_id=row.dataset,
        state=row.state,
        revision=row.revision,
        missing=missing,
    )


async def natively_deleted(graph, rows) -> dict[str, dict]:
    """The rows whose native copy is gone or changed outside the lab, by
    identity Data ID (`deleted_entry`)."""
    return {
        row.source: deleted_entry(row, missing)
        for row in rows
        if (missing := await missing_native(graph, row))
    }


def refusal_message(name, missing, hint=None) -> str:
    """Why `reconcile` refuses a source whose native copy is gone, and the
    command that erases the lab's copy when the caller knows it."""
    then = f"Run `{hint}`" if hint else "Forget it"
    return (
        f"The native copy of {name} is gone or changed outside the lab (for "
        "example by cognee.forget, a prune or cognee.update): "
        f"{', '.join(missing)} missing. {then} to erase the lab's copy"
    )


def forget_hint(label, revision) -> str:
    """The command that erases the lab's copy of a source whose native copy
    is gone."""
    return f"forget --source {label} --expected-revision {revision}"
