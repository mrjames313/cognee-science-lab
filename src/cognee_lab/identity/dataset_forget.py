"""Forget the root's dataset: every saved source in it, then every Data
item no lab source publishes.

`forget-dataset --dry-run` reports the steps and a token; `forget-dataset
--confirm TOKEN` runs them. Each source goes through the lab's own
`forget`, readers before what they read (`order`), so each forget finds its
in-dataset readers already forgotten. Then each Data item the dry run
listed under `other_data` (the seed, anything added with plain
`cognee.add`) is deleted item by item, as `forget` deletes a source's own
Data: the user decided on 2026-10-25 that the dataset forget deletes them
and that the token covers the list (Q3). Cognee's own
`cognee.forget(dataset=...)` is never called: it deletes whatever Data the
dataset holds when it runs, listed or not.

The token digests the whole dry-run report. A crash anywhere changes the
report, so a rerun with the old token is refused (`impact_changed`); a new
dry run lists what is left, and the crashed source's forget resumes through
forget's own retry. A row still pending (a killed attempt) is listed and
refused before the first step. The forgets compose; the ledger sees no new
sequence.
"""

from dataclasses import replace
from uuid import UUID

from .dependency import Target, citations
from .digests import object_digest
from .erasure import RESIDUE, remaining, unfinished
from .forget import FAULT_STAGES as FORGET_FAULTS
from .forget import IMPACT_CHANGED, plan_for, preview, stored_files, sweep
from .retirement import removed_entities, source_ids
from .validation import IntentError

CLEANUP_FAULT = "dataset_cleanup"
FAULT_STAGES = (
    *(f"{end}:{stage}" for end in ("first", "last") for stage in FORGET_FAULTS),
    CLEANUP_FAULT,
)


def ids_of(row):
    return source_ids(row.description or row.tombstone)


def reads(reader, source) -> bool:
    """Whether `reader` reads `source`: its document, a saved record of it,
    or an Entity it builds that the reader does not build itself, by the
    descriptions alone (the graph may be gone during a repair). A forgotten
    source is read through what its forget removed."""
    ids = ids_of(source)
    built = (
        set(source.description.entity_constructions)
        if source.description is not None
        else set(source.tombstone.removed_entity_ids)
    )
    target = Target(
        ids.original_data_id,
        frozenset(built - set(reader.description.entity_constructions)),
        frozenset([ids.identity_data_id]),
    )
    return bool(citations(reader.description, target))


def order(rows) -> list:
    """The rows in the order a dataset forget takes them: each after every
    row that reads it (`reads`), ties and cycles broken by identity Data ID.
    In a cycle the first forget writes the other source's removal revision,
    as a single forget does."""
    left = sorted(rows, key=lambda r: r.source)
    readers = {
        r.source: {
            o.source
            for o in left
            if o is not r and o.description is not None and reads(o, r)
        }
        for r in left
    }
    done, ordered = set(), []
    while left:
        free = [r for r in left if readers[r.source] <= done] or left[:1]
        ordered.append(free[0])
        done.add(free[0].source)
        left.remove(free[0])
    return ordered


def as_forgotten(row):
    """The row as a forget leaves it, for the impact a later step sees."""
    ids = ids_of(row)
    return replace(
        row,
        state="forgotten",
        description=None,
        tombstone=None,
        plan=dict(
            operation="identity_forget", original_data_id=str(ids.original_data_id)
        ),
    )


def simulated(rows, gone) -> list:
    """The rows as they will be once the rows in `gone` are forgotten."""
    return [as_forgotten(r) if r.source in gone else r for r in rows]


async def dataset_data(dataset_id) -> dict[str, str]:
    """Each Data item of the dataset, by ID, with its name."""
    from sqlalchemy import select
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.data.models import Data

    async with get_relational_engine().get_async_session() as session:
        found = await session.execute(
            select(Data.id, Data.name).where(Data.dataset_id == UUID(str(dataset_id)))
        )
    return {str(i): name for i, name in found}


def lab_data(rows) -> set[str]:
    """The Data items the lab's sources publish: each source's document
    and generated identity source."""
    found = set()
    for row in rows:
        ids = ids_of(row)
        found |= {str(ids.original_data_id), str(ids.identity_data_id)}
    return found


def dependent_entries(found) -> list[dict]:
    """Each dependent a step's forget revises, as the report lists it."""
    return [
        dict(
            dataset_id=d.dataset_id,
            identity_data_id=d.identity_data_id,
            revision=d.revision,
            level=d.level,
        )
        for d in found.dependents
    ]


async def dry_run(publisher, root) -> dict:
    """What `forget-dataset` does, with the token it needs. Writes nothing."""
    from .erasure import impact
    from .forget_fixture import caller_files
    from .multisource import root_labels
    from .native_copy import native_copy

    rows = await publisher.records.rows()
    datasets = {r.dataset for r in rows}
    if len(datasets) != 1:
        raise IntentError(
            "dataset_scope", "forget-dataset needs a root with one saved dataset"
        )
    (dataset,) = datasets
    labels = root_labels(root)
    pending = [r for r in rows if r.state == "pending"]
    steps = order(
        [
            r
            for r in rows
            if r.state != "pending"
            and (r.tombstone is None or unfinished(r.tombstone, rows))
        ]
    )
    everyone = {r.source for r in rows}
    sources, removed, gone = [], set(), set()
    for row in rows:
        entry = dict(
            label=labels.get(row.source),
            identity_data_id=row.source,
            revision=row.revision,
            state=row.state,
            order=next((n for n, s in enumerate(steps) if s is row), None),
            native_copy=None,
            dependents=[],
            outside_dependents=[],
        )
        sources.append(entry)
    entries = {e["identity_data_id"]: e for e in sources}
    for step in steps:
        entry = entries[step.source]
        later = simulated(rows, gone)
        if step.tombstone is not None:
            found = remaining(step.tombstone, later)
        else:
            plan = await plan_for(publisher, step.description, step)
            found = impact(step.description, plan, later)
            removed |= removed_entities(
                ids_of(step), plan, simulated(rows, everyone - {step.source})
            )
            entry["native_copy"] = (
                await native_copy(publisher.graph, step.description)
            )._asdict()
        entry["dependents"] = dependent_entries(found)
        entry["outside_dependents"] = [
            d for d in entry["dependents"] if d["dataset_id"] != dataset
        ]
        gone.add(step.source)
    present = await dataset_data(dataset)
    report = dict(
        dry_run=True,
        dataset_id=dataset,
        sources=sources,
        pending=[r.source for r in pending],
        other_data=[
            dict(data_id=i, name=present[i])
            for i in sorted(set(present) - lab_data(rows))
        ],
        removed_entities=sorted(str(e) for e in removed),
        outside_dependents=[d for e in sources for d in e["outside_dependents"]],
        caller_files=sorted(
            {f for label in labels.values() for f in caller_files(root, label)}
        ),
        residue=[*RESIDUE, "The Dataset row stays, so a re-add keeps its dataset ID"],
    )
    return dict(report, token=object_digest(report))


async def forget_data(dataset_id, data_id):
    """Delete one Data item no lab source publishes, as `forget` deletes a
    source's own: Cognee's Data delete, then its sweep. Idempotent."""
    from cognee import forget as native_forget
    from cognee.modules.users.methods import get_default_user

    from .native_copy import data_present

    locations = (await stored_files([data_id])).get(str(data_id), [])
    if await data_present(data_id, dataset_id):
        await native_forget(
            data_id=data_id, dataset_id=dataset_id, user=await get_default_user()
        )
    await sweep(dataset_id, data_id, locations)


def step_fault(fault, n, count):
    """The forget fault stage for the n-th of `count` steps, if any."""
    if fault is None or fault == CLEANUP_FAULT:
        return None
    end, _, stage = fault.partition(":")
    return stage if n == (0 if end == "first" else count - 1) else None


async def forget_dataset(publisher, root, *, confirm, fault_stage=None) -> dict:
    """Run the dry run's steps once the caller confirms its token: each
    source's forget, in order, then the deletion of the listed Data no lab
    source publishes. Stops at a forget whose dependents' removal failed and
    reports it beside the forgets that completed."""
    from .forget import forget

    report = await dry_run(publisher, root)
    if report["pending"]:
        raise IntentError(
            "dataset_pending",
            "A source of the dataset has an attempt in flight; finish it, then "
            "rerun the dry run",
            details=report,
        )
    if confirm != report["token"]:
        code, message = (
            (
                "confirmation_required",
                "forget-dataset needs the dry run's token; review the report and "
                "rerun with --confirm <token>",
            )
            if confirm is None
            else IMPACT_CHANGED
        )
        raise IntentError(code, message, details=report)
    records = publisher.records
    dataset = UUID(report["dataset_id"])
    steps = sorted(
        (e for e in report["sources"] if e["order"] is not None),
        key=lambda e: e["order"],
    )
    origin = "test/fault_injection" if fault_stage else "test"
    forgotten = []
    for n, entry in enumerate(steps):
        row = next(
            r for r in await records.rows() if r.source == entry["identity_data_id"]
        )
        if row.tombstone is not None and not unfinished(
            row.tombstone, await records.rows()
        ):
            continue
        selected = row.description or row.tombstone
        if row.tombstone is None:
            seen = await preview(publisher, selected, expected_revision=row.revision)
            outside = [
                {
                    k: d[k]
                    for k in ("dataset_id", "identity_data_id", "revision", "level")
                }
                for d in seen["dependents"]
                if d["dataset_id"] != report["dataset_id"]
            ]
            if outside != entry["outside_dependents"]:
                raise IntentError(*IMPACT_CHANGED, details=report)
            confirm_step = seen["token"]
        else:
            confirm_step = None
        outcome = await forget(
            publisher,
            selected,
            expected_revision=row.revision,
            confirm=confirm_step,
            origin=origin,
            fault_stage=step_fault(fault_stage, n, len(steps)),
        )
        forgotten.append(
            dict(
                label=entry["label"],
                identity_data_id=entry["identity_data_id"],
                dependents_revised=outcome["dependents_revised"],
                dependents_waiting=outcome["dependents_waiting"],
            )
        )
        if outcome["dependents_failed"]:
            return dict(
                forgotten=forgotten,
                other_data_deleted=[],
                dependents_failed=outcome["dependents_failed"],
            )
    if fault_stage == CLEANUP_FAULT:
        raise IntentError(
            "injected_failure", "Injected failure before the dataset cleanup"
        )
    rows = await records.rows()
    if any(r.state != "forgotten" for r in rows):
        raise IntentError(*IMPACT_CHANGED, details=report)
    listed = [d["data_id"] for d in report["other_data"]]
    for data_id in listed:
        await forget_data(dataset, UUID(data_id))
    if unlisted := sorted(set(await dataset_data(dataset)) - lab_data(rows)):
        raise IntentError(*IMPACT_CHANGED, details=dict(report, unlisted_data=unlisted))
    tombstones = {r.source: r.tombstone for r in rows}
    for entry in forgotten:
        entry["tombstone"] = tombstones[entry["identity_data_id"]].model_dump(
            mode="json"
        )
    return dict(forgotten=forgotten, other_data_deleted=listed, dependents_failed=None)


async def run(args, root):
    from .publish import Publisher

    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    if args.dry_run:
        return await dry_run(publisher, root)
    return await forget_dataset(
        publisher, root, confirm=args.confirm, fault_stage=args.fault_stage
    )
