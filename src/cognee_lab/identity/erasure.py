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
    erased_decisions,
    is_removal_producer,
    levels,
    producer_key,
    removal_claim,
)
from .models import CorpusObjectInput, IdentitySource
from .records import (
    REGISTRY,
    RemovedRecord,
    naming,
    record_inputs,
    record_type_of,
    saved_records,
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
from .digests import object_digest
from .validation import IntentError

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
    by_decision = record_inputs(reader)
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
    removed_records = removes(row, cited)
    cited_records = read_records(reader, records)
    kinds = {k: REGISTRY[record_type_of(reader, k)] for k in sorted(citing)}

    def change(payload):
        for k, kind in kinds.items():
            record = kind.removed(reader, k, erased, key)
            if record is None:
                payload[kind.field].pop(k)
            else:
                payload[kind.field][k] = record.model_dump(
                    mode="json", exclude_none=True
                )
        for kind in REGISTRY.values():
            for field, parts in kind.stripped(reader, erased).items():
                payload[field] = {
                    k: part.model_dump(mode="json") for k, part in parts.items()
                }
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
                kind.outcome,
                tuple(cited[i] for i in sorted(by_decision[k] & erased)),
            )
            for k, kind in kinds.items()
        ),
        dropped_entities=tuple(sorted(str(e) for e in dropped)),
        kept_entities=tuple(sorted(str(e) for e in candidates - dropped)),
        unlinked_mentions=tuple(
            sorted(
                str(e) for k, kind in kinds.items() for e in kind.unlinked(reader, k)
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
    this source's removal producer and was never served, or None. A later
    revision that only carries that producer forward is not one, nor is a
    removal served before a later attempt at its revision failed: it is
    written (`PublicationRow.holds_served`)."""
    if row.failed_attempt is None or blocked(row) or row.holds_served:
        return None
    producer = row.description.producers.get(
        producer_key(ids.identity_data_id, row.revision)
    )
    return removal_claim(producer) if producer is not None else None


def forget_target(ids: SourceIds, removed) -> Target:
    """What a forget takes away: its source's document, the Entities it
    removes and every saved record of its source."""
    return Target(
        ids.original_data_id, frozenset(removed), frozenset([ids.identity_data_id])
    )


def removes(row, cited) -> frozenset[RemovedRecord]:
    """The records a row's removal removes, given the inputs through which
    it reads what the forget removed, as last served."""
    reader = row.description
    return frozenset(
        RemovedRecord.of(reader, k, row.verified_revision)
        for k in erased_decisions(reader, set(cited))
    )


def cascade(rows, ids: SourceIds, removed, token=None) -> tuple[Step, ...]:
    """Every removal revision the forget of this source still has to write,
    derived from the rows, in level order. The removals that bind are found
    to a fixpoint from the written ones (erasure_rules.bound_removals): a
    failed removal revision whose cited records are all removed by a bound
    removal, and each other saved source that reads the forgotten source,
    or a record a bound removal removes as it was before, with one removal
    revision for all it reads. A failed removal revision whose cited
    records no bound removal lists any more, because the source that
    removed them was withdrawn, leaves the cascade, as a citer of a
    withdrawn intermediate does. A dependent's level is one more than the
    deepest removal it cites, or 1 (erasure_rules.levels)."""
    forgotten = str(ids.identity_data_id)
    removed = frozenset(UUID(str(e)) for e in removed)
    live = {
        r.source: r
        for r in sorted(rows, key=lambda r: r.source)
        if not r.is_retired and r.source != forgotten
    }
    written = bound_removals(rows, ids.original_data_id, removed)
    claims = {s: claim for s, r in live.items() if (claim := removal_of(r, ids))}
    base = forget_target(ids, removed)
    records = frozenset(written)
    while True:
        target = base._replace(records=records)
        cited = {
            s: found
            for s, r in live.items()
            if s not in claims and (found := citations(r.description, target))
        }
        depth, bound = levels(
            {s: (c.cited_records, c.removed_records) for s, c in claims.items()}
            | {
                s: (
                    frozenset(read_records(live[s].description, records)),
                    removes(live[s], c),
                )
                for s, c in cited.items()
            },
            written,
        )
        if bound.keys() <= records:
            break
        records |= bound.keys()

    reads = {r.source: corpus_reads(r.description) for r in rows if not r.is_retired}
    steps = [
        Step(live[s], live[s].description, None, depth[s], claim.cited_records)
        for s, claim in claims.items()
        if s in depth
    ]
    for s, found in cited.items():
        if s not in depth:
            continue
        readers = set().union(*(e for k, e in reads.items() if k != s))
        revised, impact = removal_revision(
            live[s], found, ids, removed, readers, records, token
        )
        steps.append(
            Step(
                live[s],
                revised,
                replace(impact, level=depth[s]),
                depth[s],
                frozenset(impact.cited_records),
            )
        )
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
        removed = removed_entities(row.description, row.plan, rows)
        found += consumes(source, forget_target(source_ids(row.description), removed))
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


def refuse_unfinished_cascade(source, rows):
    """Refuse withdrawing or forgetting a source that holds a removal
    producer, written or saved by a failed attempt, of a forget whose
    cascade is not finished (`unfinished`). The removals below it bind to
    that producer (erasure_rules.written_claims), so retiring the source
    first would free every citer further down, and the forget would report
    finished. Transitive, since `unfinished` covers every level. The
    forgotten source itself holds no removal of its own forget, so finishing
    it is never refused."""
    tombstones = {
        r.tombstone.identity_data_id: r.tombstone for r in rows if r.tombstone
    }
    for producer in source.producers.values():
        if not is_removal_producer(producer):
            continue
        try:
            claim = removal_claim(producer)
        except IntentError:
            continue
        tomb = tombstones.get(claim.forgotten)
        if tomb is None or (claim.document, claim.removed_entities) != (
            tomb.original_data_id,
            frozenset(tomb.removed_entity_ids),
        ):
            continue
        if left := unfinished(tomb, rows):
            raise IntentError(
                "cascade_unfinished",
                "This source holds a removal of a forget whose cascade is not finished; run forget on the forgotten source again first",
                details=dict(
                    forgotten=str(claim.forgotten),
                    unfinished=[r.source for r in left],
                ),
            )


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
    depths = sorted({d.level for d in impact.dependents})
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
            for n in depths
        ],
        counts=dict(
            dependents=len(impact.dependents),
            levels=len(depths),
            blocked=sum(d.blocked for d in impact.dependents),
            decisions=len(decisions),
            **{
                kind.outcome: sum(r.outcome == kind.outcome for r in decisions)
                for kind in REGISTRY.values()
            },
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
                    record.explanation is not None
                    for kind in REGISTRY.values()
                    for record in getattr(description, kind.field).values()
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


def ready(steps) -> tuple[list[Step], list[tuple[Step, list[str]]]]:
    """The removal revisions that can be written now, in the cascade's
    order, and the ones that wait, each with the sources it waits behind:
    one whose own attempt is pending, or whose withdrawal or forget failed
    (`blocked`), and every one below it that cites a record it removes. Its
    records are not removed yet, and a removal below binds only to written
    ones."""
    writable, waiting, held = [], [], set()
    for step in steps:
        behind = sorted({r.identity_data_id for r in step.cited_records} & held)
        if blocked(step.row) or behind:
            waiting.append((step, behind))
            held.add(step.row.source)
        else:
            writable.append(step)
    return writable, waiting


async def finish_dependents(publisher, tombstone, rows, fault=None) -> dict:
    """Write the cascade's removal revisions after the forget completed, in
    level order, each under its own writer reservation (`removal_writer`),
    from `rows` as the caller read them. A failed removal revision resumes
    with its saved description. A removal that waits (`ready`) is reported
    (`dependent_unfinished`) until the attempt it waits for finishes. Stops
    at the first failure and reports it, not raised: the forget before it
    already completed. `fault` is one of forget.DEPENDENT_FAULTS:
    `forget_dependents` stops before the first revision begins, when there
    is one; the others fail removal revisions (`failing`)."""
    ids = source_ids(tombstone)
    done, waiting = [], []
    try:
        steps = cascade(rows, ids, tombstone.removed_entity_ids, tombstone.impact_token)
        if steps and fault == "forget_dependents":
            raise IntentError(
                "injected_failure",
                "Injected failure before the dependents' removal revisions",
            )
        writable, held = ready(steps)
        waiting = [
            dict(
                identity_data_id=step.row.source,
                state=step.row.state,
                operation=step.row.operation,
                level=step.level,
                waits_for=behind,
            )
            for step, behind in held
        ]
        for step in writable:
            write = removal_writer(step.row)
            await write(publisher, step.row, step.description, failing(fault, step))
            done.append(
                dict(
                    identity_data_id=step.row.source,
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
