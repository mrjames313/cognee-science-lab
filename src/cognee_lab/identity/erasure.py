"""What forgetting a source does to the sources that read it, down every
chain of citations.

A dependent decision is a resolution, with its group, or a variant whose
inputs cite the forgotten source: its document's text, a span or chunk of
it, an Entity the forget removes, one of its saved records, or a record
that another dependent's removal removes, as that record was before
(records.RemovedRecord). Forget erases the source first and then writes
each dependent's removal revision: a resolution becomes unresolved, a
variant is dropped, a reusable recipe that only removed decisions named
goes with them, and inputs nothing cites any more are dropped
(`removal_revision`). The dependents form levels: a dependent that reads
the forgotten source directly is at level 1, and one that cites a record
removed at level n is at level n + 1 or below, at its longest path, with
one removal revision for all it loses (`cascade`). `impact` reports the
cascade from saved descriptions and the forget plan, never the live graph,
and its token, over every level, is what a caller confirms;
`finish_dependents` writes the removal revisions in level order. Nothing
here is a ledger state: the cascade is derived from the rows each time, so
a resume after a crash continues where the rows say it stopped
(`unfinished`).
"""

import json
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple, assert_never
from uuid import UUID

from .dependency import Citation, Target, citations, read_records
from .erasure_rules import (
    ERASURE_IMPLEMENTATION,
    bound_removals,
    corpus_reads,
    producer_key,
    removal_claim,
)
from .models import Accepted, CorpusObjectInput, IdentitySource
from .records import (
    REGISTRY,
    RemovedRecord,
    record_type_of,
    saved_records,
    without_erased,
)
from .retirement import (
    Dependent,
    SourceIds,
    consumes,
    removed_entities,
    retiring_by_forget,
    source_ids,
)
from .storage import PublicationRow
from .validation import IntentError, decision_inputs, naming, object_digest

RESIDUE = (
    "LanceDB marks deleted vector rows; their bytes stay until a compaction and a cleanup of old table versions",
    "The graph store and SQLite keep deleted rows in their files until a checkpoint and VACUUM",
)


@dataclass(frozen=True)
class Removal:
    """One decision a forget removes from a dependent, and what is left of
    it (`outcome`: its status, or dropped)."""

    assignment: str
    record_type: str
    outcome: str
    citing: tuple[Citation, ...]


@dataclass(frozen=True)
class DependentImpact:
    """What a forget does to one other source. `blocked` marks a source whose
    own attempt is pending or failed: its removal waits for that attempt.
    `level` is its place in the cascade, `removed_records` the records its
    removal removes and `cited_records` the removed records of other
    dependents it cites."""

    dataset_id: str
    identity_data_id: str
    revision: int
    state: str
    blocked: bool
    level: int
    decisions: tuple[Removal, ...]
    dropped_entities: tuple[str, ...]
    kept_entities: tuple[str, ...]
    unlinked_mentions: tuple[str, ...]
    dropped_inputs: tuple[str, ...]
    removed_records: tuple[RemovedRecord, ...]
    cited_records: tuple[RemovedRecord, ...]


def records_json(records) -> list[dict]:
    return [r._asdict() for r in records]


@dataclass(frozen=True)
class Impact:
    source: SourceIds
    revision: int
    removed_entities: tuple[str, ...]
    dependents: tuple[DependentImpact, ...]

    @property
    def token(self) -> str:
        """A digest of the affected-decision set over every level, which a
        caller confirms. It covers each dependent's revision, state, level
        and the records it removes and cites, so it changes whenever
        anything the report shows could change."""
        return object_digest(
            dict(
                source=dict(
                    dataset_id=str(self.source.dataset_id),
                    identity_data_id=str(self.source.identity_data_id),
                    revision=self.revision,
                ),
                removed_entities=list(self.removed_entities),
                dependents=[
                    dict(
                        identity_data_id=d.identity_data_id,
                        revision=d.revision,
                        state=d.state,
                        level=d.level,
                        assignments=sorted(r.assignment for r in d.decisions),
                        decisions=[
                            dict(
                                assignment=r.assignment,
                                record_type=r.record_type,
                                outcome=r.outcome,
                                citing=[c._asdict() for c in r.citing],
                            )
                            for r in d.decisions
                        ],
                        dropped_entities=list(d.dropped_entities),
                        removed_records=records_json(d.removed_records),
                        cited_records=records_json(d.cited_records),
                        blocked=d.blocked,
                    )
                    for d in self.dependents
                ],
            )
        )


def removal_producer(ids: SourceIds, removed, token, removed_records, cited_records):
    """The producer a removal revision names: it removed what the forget of
    this source took away, as the caller confirmed it, and lists the
    records it removed and the removed records it cites, which bind the
    removals below it (erasure_rules.bound_removals)."""
    return dict(
        method="captured_fixture",
        implementation=ERASURE_IMPLEMENTATION,
        version="0.1",
        configuration=dict(
            forgotten_identity_data_id=str(ids.identity_data_id),
            forgotten_document_id=str(ids.original_data_id),
            removed_entity_ids=sorted(str(e) for e in removed),
            impact_token=token,
            removed_records=records_json(sorted(removed_records)),
            cited_records=records_json(sorted(cited_records)),
        ),
        run_id=None,
    )


def removal_writer(row):
    """How a dependent row takes its removal revision, by the attempt it
    saved: a current row writes its next revision; a failed publication,
    replacement or text change retries its saved revision with the removal
    applied, which supersedes it (an erasure retry). None while the row
    waits for its own attempt: a pending row, or a failed withdrawal or
    forget, which leaves the source reading nothing once it finishes."""
    if row.state == "pending":
        return None
    match row.failed_attempt:
        case None | "replace":
            return write_replacement
        case "text_change":
            return write_text_change
        case "publish":
            return write_publication
        case "withdraw" | "forget":
            return None
        case unknown:
            assert_never(unknown)


def blocked(row) -> bool:
    """A dependent whose removal waits for its own attempt."""
    return removal_writer(row) is None


def removal_revision(row, cited, ids: SourceIds, removed, readers, records, token=None):
    """The dependent's removal revision, and what it does. `cited` are the
    inputs through which the row's description reads what the forget
    removed, and `records` the removed records the cascade knows of. Each
    citing decision is removed as its record type says (records.REGISTRY).
    A recipe that a removed decision named and no remaining decision names
    goes, unless a saved source, this one included, still cites that Entity
    as a corpus input (`readers`): dropping the last declaration would take
    the Entity out of the graph under a reader. A current row takes its
    next revision; a failed replacement or publication keeps its saved
    revision, which that attempt then finishes with. The level is the
    cascade's to set."""
    from .revisions import next_revision

    reader = row.description
    erased = set(cited)
    by_decision = decision_inputs(reader)
    citing = {a for a, inputs in by_decision.items() if inputs & erased}
    remaining = set(by_decision) - citing
    mentions = {g.entity_id for g in reader.mention_groups.values()}
    candidates = (
        set().union(*(naming(reader, k) for k in citing))
        - set().union(*(naming(reader, k) for k in remaining))
        - mentions
    ) & set(reader.entity_constructions)
    revision = reader.revision + 1 if row.state == "current" else reader.revision
    key = producer_key(ids.identity_data_id, revision)
    in_place = row.state != "current" and not blocked(row)
    removed_records = {RemovedRecord.of(reader, k, in_place=in_place) for k in citing}
    cited_records = read_records(reader, records)
    after = {}
    for k in sorted(citing):
        kind = REGISTRY[record_type_of(reader, k)]
        after[k] = (kind.field, kind.removed(reader, k, erased, key))

    def change(payload):
        for k, (field, record) in after.items():
            if record is None:
                payload[field].pop(k)
            else:
                payload[field][k] = record.model_dump(mode="json", exclude_none=True)
        for group in payload["mention_groups"].values():
            group["input_refs"] = without_erased(
                group["input_refs"], erased, reader.original_input_ref
            )
        payload["producers"][key] = removal_producer(
            ids, removed, token, removed_records, cited_records
        )

    stripped = next_revision(reader, change, revision=revision)
    read = {
        i.entity_id
        for i in stripped.inputs.values()
        if isinstance(i, CorpusObjectInput)
    } | set(readers)
    dropped = {e for e in candidates if e not in read}
    payload = stripped.model_dump(mode="json")
    for e in dropped:
        payload["entity_constructions"].pop(str(e))
    revised = IdentitySource.model_validate_json(json.dumps(payload))
    return revised, DependentImpact(
        dataset_id=row.dataset,
        identity_data_id=row.source,
        revision=row.revision,
        state=row.state,
        blocked=blocked(row),
        level=0,
        decisions=tuple(
            Removal(
                k,
                record_type_of(reader, k),
                "dropped" if record is None else record.status,
                tuple(cited[i] for i in sorted(by_decision[k] & erased)),
            )
            for k, (_, record) in after.items()
        ),
        dropped_entities=tuple(sorted(str(e) for e in dropped)),
        kept_entities=tuple(sorted(str(e) for e in candidates - dropped)),
        unlinked_mentions=tuple(
            sorted(
                str(reader.mention_groups[d.group_ref].entity_id)
                for k, d in reader.mention_resolutions.items()
                if k in citing and isinstance(d, Accepted)
            )
        ),
        dropped_inputs=tuple(sorted(set(reader.inputs) - set(revised.inputs))),
        removed_records=tuple(sorted(removed_records)),
        cited_records=tuple(sorted(cited_records)),
    )


class Step(NamedTuple):
    """One removal revision the cascade still has to write, in level order:
    a dependent's planned removal (with its impact), or the retry of a
    removal revision that failed (impact None), with its saved
    description."""

    row: PublicationRow
    description: IdentitySource
    impact: DependentImpact | None
    level: int
    cited_records: frozenset[RemovedRecord]


def removal_of(row, ids: SourceIds):
    """The claim of a failed row's removal revision for this forget: a
    publication, replacement or text change whose saved revision introduced
    this source's removal producer, or None. A later revision that only
    carries that producer forward is not one."""
    if row.failed_attempt is None or blocked(row):
        return None
    producer = row.description.producers.get(
        producer_key(ids.identity_data_id, row.revision)
    )
    return removal_claim(producer) if producer is not None else None


def cascade(rows, ids: SourceIds, removed, token=None) -> tuple[Step, ...]:
    """Every removal revision the forget of this source still has to write,
    derived from the rows, in level order. The records that written
    removals removed (erasure_rules.bound_removals), that failed removal
    revisions remove and that planned ones will remove are found to a
    fixpoint: each saved source that reads the forgotten source, or a
    removed record as it was before, is a dependent with one removal
    revision for all it reads. A dependent's level is one more than the
    deepest removal it cites, or 1."""
    forgotten = str(ids.identity_data_id)
    removed = frozenset(UUID(str(e)) for e in removed)
    live = sorted(
        (r for r in rows if not r.is_retired and r.source != forgotten),
        key=lambda r: r.source,
    )
    written = bound_removals(rows, ids.original_data_id, removed)
    retries = {r.source: (r, claim) for r in live if (claim := removal_of(r, ids))}
    base = Target(ids.original_data_id, removed, frozenset([ids.identity_data_id]))
    reads = {r.source: corpus_reads(r.description) for r in rows if not r.is_retired}
    remover = {
        record: source
        for source, (_, claim) in retries.items()
        for record in claim.removed_records
    }
    found: dict[str, tuple] = {}
    grew = True
    while grew:
        grew = False
        records = frozenset(written) | frozenset(remover)
        target = base._replace(records=records)
        for row in live:
            if row.source in retries:
                continue
            cited = citations(row.description, target)
            if not cited or found.get(row.source, (None,))[0] == cited:
                continue
            readers = set().union(*(e for k, e in reads.items() if k != row.source))
            revised, impact = removal_revision(
                row, cited, ids, removed, readers, records, token
            )
            found[row.source] = (cited, row, revised, impact)
            remover.update(dict.fromkeys(impact.removed_records, row.source))
            grew = True

    cited_of = {s: claim.cited_records for s, (_, claim) in retries.items()}
    cited_of.update({s: frozenset(f[3].cited_records) for s, f in found.items()})
    levels: dict[str, int] = {}

    def level(source, seen=()):
        if source in seen:
            raise IntentError(
                "citation_cycle", "A chain of saved-record citations leads back here"
            )
        if source not in levels:
            levels[source] = 1 + max(
                (
                    written[r] if r in written else level(remover[r], (*seen, source))
                    for r in cited_of[source]
                ),
                default=0,
            )
        return levels[source]

    steps = [
        Step(row, row.description, None, level(s), cited_of[s])
        for s, (row, _) in retries.items()
    ] + [
        Step(row, revised, replace(impact, level=level(s)), level(s), cited_of[s])
        for s, (_, row, revised, impact) in found.items()
    ]
    return tuple(sorted(steps, key=lambda s: (s.level, s.row.source)))


def impact_of(ids: SourceIds, revision, removed, rows) -> Impact:
    return Impact(
        ids,
        revision,
        tuple(sorted(str(e) for e in removed)),
        tuple(s.impact for s in cascade(rows, ids, removed) if s.impact),
    )


def impact(source, plan, rows) -> Impact:
    """What forgetting `source` with this plan does to the other saved
    sources, from their descriptions and the plan's ownership snapshot."""
    ids = source_ids(source)
    return impact_of(ids, plan["revision"], removed_entities(ids, plan, rows), rows)


def remaining(tombstone, rows) -> Impact:
    """What a completed forget has still to do: the removal revisions of
    the dependents it has not revised yet, at every level."""
    return impact_of(
        source_ids(tombstone),
        tombstone.revision,
        set(tombstone.removed_entity_ids),
        rows,
    )


def under_way(rows):
    """The impact of each forget not finished: a pending or failed one, by
    its saved plan, and a completed one with dependents left."""
    for row in rows:
        if retiring_by_forget(row):
            yield impact(row.description, row.plan, rows)
        elif row.tombstone is not None:
            yield remaining(row.tombstone, rows)


def removed_records(found: Impact) -> set[RemovedRecord]:
    """Each record a removal revision of this impact removes, at every
    level, as it is before the removal."""
    return {r for d in found.dependents for r in d.removed_records}


def refuse_retiring_inputs(source, rows):
    """Refuse a description that reads what a forget not finished removes:
    the document, an Entity or a saved record of a source whose forget is
    pending or failed, or a record that a removal revision of a pending,
    failed or completed forget has still to remove, at any level, as that
    record is now. The cascade is simulated from the rows (`under_way`), so
    once a forget is confirmed what it removes can only shrink. Admitting
    such a description would leave that forget refused by its new
    dependent, the source half-forgotten, or a citation of a record the
    cascade then removes without its citer. A citation of a removed record
    as it is after its removal reads nothing the forget removes."""
    own = (str(source.dataset_id), str(source.identity_data_id))
    found = []
    for row in rows:
        if (row.dataset, row.source) == own or not retiring_by_forget(row):
            continue
        ids = source_ids(row.description)
        removed = removed_entities(row.description, row.plan, rows)
        target = Target(
            ids.original_data_id, frozenset(removed), frozenset([ids.identity_data_id])
        )
        found += consumes(source, target)
    if cited := saved_records(source):
        doomed = set().union(*map(removed_records, under_way(rows)))
        found += [
            Dependent(
                dataset_id=str(source.dataset_id),
                identity_data_id=str(source.identity_data_id),
                input_ref=key,
                kind=item.kind,
                consumed=str(item.identity_data_id),
            )
            for key, item in sorted(cited.items())
            if any(r.reads(item) for r in doomed)
        ]
    if found:
        raise IntentError(
            "retiring_source",
            "An input is a document, Entity or saved record whose forget is not finished, or a record that forget removes; run forget on that source again first",
            details=dict(dependents=found),
        )


def unfinished(tombstone, rows) -> list:
    """The saved sources a completed forget has not revised yet, at every
    level: a dependent the cascade still finds in the rows, and a removal
    revision that failed. Derived from the rows, not stored."""
    steps = cascade(rows, source_ids(tombstone), tombstone.removed_entity_ids)
    return sorted((s.row for s in steps), key=lambda r: r.source)


def dependent_json(d: DependentImpact) -> dict:
    return dict(
        asdict(d),
        decisions=[
            dict(asdict(r), citing=[c._asdict() for c in r.citing]) for r in d.decisions
        ],
        removed_records=records_json(d.removed_records),
        cited_records=records_json(d.cited_records),
    )


def report(impact: Impact, *, plan, description, events) -> dict:
    """The dry run: what a forget removes from other sources, level by
    level, the traces its tombstone scrubs and the token to confirm."""
    decisions = [r for d in impact.dependents for r in d.decisions]
    levels = sorted({d.level for d in impact.dependents})
    return dict(
        dry_run=True,
        source=dict(
            dataset_id=str(impact.source.dataset_id),
            identity_data_id=str(impact.source.identity_data_id),
            original_data_id=str(impact.source.original_data_id),
            revision=impact.revision,
        ),
        confirmation_required=bool(impact.dependents),
        token=impact.token,
        removed_entities=list(impact.removed_entities),
        dependents=[dependent_json(d) for d in impact.dependents],
        levels=[
            dict(
                level=n,
                dependents=[
                    d.identity_data_id for d in impact.dependents if d.level == n
                ],
            )
            for n in levels
        ],
        counts=dict(
            dependents=len(impact.dependents),
            levels=len(levels),
            blocked=sum(d.blocked for d in impact.dependents),
            decisions=len(decisions),
            unresolved=sum(r.outcome == "unresolved" for r in decisions),
            dropped=sum(r.outcome == "dropped" for r in decisions),
            dropped_entities=sum(len(d.dropped_entities) for d in impact.dependents),
            unlinked_facts=sum(len(d.unlinked_mentions) for d in impact.dependents),
        ),
        scrubbed=dict(
            description=dict(
                occurrences=sum(
                    len(g.occurrences) for g in description.mention_groups.values()
                ),
                recipes=len(description.entity_constructions),
                explanations=sum(
                    d.explanation is not None
                    for d in [
                        *description.mention_resolutions.values(),
                        *description.variant_assignments.values(),
                    ]
                ),
            ),
            plan=dict(
                edge_properties=sum(bool(e.get("properties")) for e in plan["edges"]),
            ),
            recovery_event_messages=sum(
                e["identity_data_id"] == str(impact.source.identity_data_id)
                for e in events
            ),
        ),
        residue=list(RESIDUE),
    )


async def write_replacement(publisher, row, description, revise):
    """A current row's next revision, or a failed replacement's retry,
    through `replace_one`."""
    from .revisions import replace_one

    await replace_one(
        publisher,
        description,
        expected_revision=row.revision,
        fault_stage="replace_registered" if revise else None,
    )


async def write_text_change(publisher, row, description, revise):
    """A failed text change's retry with its saved text change, through the
    writer and verifier that text change needs (`text_fixture.rebuild`)."""
    from .text_changes import TextChange
    from .text_fixture import rebuild

    await rebuild(
        publisher,
        description,
        TextChange.from_plan(row.plan),
        expected_revision=row.revision,
        fault_stage="replace_registered" if revise else None,
    )


async def write_publication(publisher, row, description, revise):
    """A failed publication's retry through `finish_publication`."""
    from .revisions import finish_publication

    await finish_publication(
        publisher, description, fault_stage="nodes" if revise else None
    )


def failing(fault, step: Step) -> bool:
    """Whether a dependents fault fails this removal revision:
    `forget_dependent_revision` fails each one, `forget_cascade_revision`
    each one below level 1."""
    return fault == "forget_dependent_revision" or (
        fault == "forget_cascade_revision" and step.level > 1
    )


async def finish_dependents(publisher, tombstone, rows, fault=None) -> dict:
    """Write the cascade's removal revisions after the forget completed, in
    level order, each under its own writer reservation (`removal_writer`),
    from `rows` as the caller read them. A failed removal revision resumes
    with its saved description. A dependent whose own attempt is pending,
    or whose withdrawal or forget failed, waits (`dependent_unfinished`)
    until that attempt finishes, and so does every removal below it that
    cites a record it removes (`waits_for`): its records are not removed
    yet, and the removals below bind only to written ones. Stops at the
    first failure and reports it, not raised: the forget before it already
    completed. `fault` is one of forget.DEPENDENT_FAULTS:
    `forget_dependents` stops before the first revision begins, when there
    is one; the others fail removal revisions (`failing`)."""
    ids = source_ids(tombstone)
    done, waiting, held = [], [], set()
    try:
        steps = cascade(rows, ids, tombstone.removed_entity_ids, tombstone.impact_token)
        if steps and fault == "forget_dependents":
            raise IntentError(
                "injected_failure",
                "Injected failure before the dependents' removal revisions",
            )
        for step in steps:
            row = step.row
            behind = sorted({r.identity_data_id for r in step.cited_records} & held)
            write = removal_writer(row)
            if write is None or behind:
                waiting.append(
                    dict(
                        identity_data_id=row.source,
                        state=row.state,
                        operation=row.operation,
                        level=step.level,
                        waits_for=behind,
                    )
                )
                held.add(row.source)
                continue
            await write(publisher, row, step.description, failing(fault, step))
            done.append(
                dict(
                    identity_data_id=row.source,
                    revision=step.description.revision,
                    level=step.level,
                )
            )
    except Exception as exc:
        code = exc.code if isinstance(exc, IntentError) else type(exc).__name__
        return dict(
            dependents_revised=done,
            dependents_waiting=waiting,
            dependents_failed=dict(code=code, message=str(exc)),
        )
    failed = None
    if waiting:
        failed = dict(
            code="dependent_unfinished",
            message="A dependent's own attempt is pending, or its withdrawal or forget failed, or a removal above it waits; finish that attempt, then run forget or reconcile on the forgotten source",
        )
    return dict(
        dependents_revised=done,
        dependents_waiting=waiting,
        dependents_failed=failed,
    )
