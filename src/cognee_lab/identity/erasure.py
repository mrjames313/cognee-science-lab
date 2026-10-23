"""What forgetting a source does to the sources that read it.

A dependent decision is a resolution, with its group, or a variant whose
inputs cite the forgotten source: its document's text, a span or chunk of
it, or an Entity the forget removes. Forget erases the source first and then
writes each dependent's removal revision: a resolution becomes unresolved,
a variant is dropped, a reusable recipe that only removed decisions named
goes with them, and inputs nothing cites any more are dropped
(`removal_revision`). `revisions` yields each dependent's removal
revision with what it does; `impact` reports them from saved descriptions
and the forget plan, never the live graph, and its token is what a caller
confirms; `finish_dependents` writes them. Nothing here is a ledger state:
a dependent is unfinished while a saved source still cites the forgotten
document or a removed Entity (`unfinished`).
"""

import json
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import UUID

from .erasure_rules import (
    ERASURE_IMPLEMENTATION,
    corpus_reads,
    without_erased,
)
from .dependency import Citation, Target, citations
from .models import Accepted, CorpusObjectInput, IdentitySource
from .retirement import SourceIds, removed_entities, source_ids
from .validation import IntentError, decision_inputs, naming, object_digest

RESIDUE = (
    "LanceDB marks deleted vector rows; their bytes stay until a compaction and a cleanup of old table versions",
    "The graph store and SQLite keep deleted rows in their files until a checkpoint and VACUUM",
)


@dataclass(frozen=True)
class Removal:
    """One decision a forget removes from a dependent."""

    assignment: str
    kind: Literal["resolution", "variant"]
    outcome: Literal["unresolved", "dropped"]
    citing: tuple[Citation, ...]


@dataclass(frozen=True)
class DependentImpact:
    """What a forget does to one other source. `blocked` marks a source whose
    own attempt is pending or failed: its removal waits for that attempt."""

    dataset_id: str
    identity_data_id: str
    revision: int
    state: str
    blocked: bool
    decisions: tuple[Removal, ...]
    dropped_entities: tuple[str, ...]
    kept_entities: tuple[str, ...]
    unlinked_mentions: tuple[str, ...]
    dropped_inputs: tuple[str, ...]


@dataclass(frozen=True)
class Impact:
    source: SourceIds
    revision: int
    removed_entities: tuple[str, ...]
    dependents: tuple[DependentImpact, ...]

    @property
    def token(self) -> str:
        """A digest of the affected-decision set, which a caller confirms.
        It covers each dependent's revision and state, so it changes
        whenever anything the report shows could change."""
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
                        assignments=sorted(r.assignment for r in d.decisions),
                        decisions=[
                            dict(
                                assignment=r.assignment,
                                kind=r.kind,
                                outcome=r.outcome,
                                citing=[c._asdict() for c in r.citing],
                            )
                            for r in d.decisions
                        ],
                        dropped_entities=list(d.dropped_entities),
                        blocked=d.blocked,
                    )
                    for d in self.dependents
                ],
            )
        )


def removal_producer(ids: SourceIds, removed, token) -> dict:
    """The producer a removal revision names: it removed what the forget of
    this source took away, as the caller confirmed it."""
    return dict(
        method="captured_fixture",
        implementation=ERASURE_IMPLEMENTATION,
        version="0.1",
        configuration=dict(
            forgotten_identity_data_id=str(ids.identity_data_id),
            forgotten_document_id=str(ids.original_data_id),
            removed_entity_ids=sorted(str(e) for e in removed),
            impact_token=token,
        ),
        run_id=None,
    )


def producer_key(ids: SourceIds, revision: int) -> str:
    return f"forget_{ids.identity_data_id}_r{revision}"


def blocked(row) -> bool:
    """A dependent whose removal waits for its own attempt: a pending row,
    or a failed withdrawal or forget, which only its own method resumes and
    which leaves the source reading nothing. A failed replacement or
    publication takes the removal in its saved revision instead."""
    return row.state == "pending" or row.resumed_by in ("withdraw", "forget")


def removal_revision(row, cited, ids: SourceIds, removed, readers, token=None):
    """The dependent's removal revision, and what it does. `cited` are the
    inputs through which the row's description reads what the forget
    removed. A recipe that a removed decision named and no remaining
    decision names goes, unless a saved source, this one included, still
    cites that Entity as a corpus input (`readers`): dropping the last
    declaration would take the Entity out of the graph under a reader. A
    current row takes its next revision; a failed replacement or
    publication keeps its saved revision, which that attempt then finishes
    with."""
    from .revisions import next_revision

    reader = row.description
    erased = set(cited)
    own = reader.original_input_ref
    by_decision = decision_inputs(reader)
    citing = {a for a, inputs in by_decision.items() if inputs & erased}
    resolutions = {k: d for k, d in reader.mention_resolutions.items() if k in citing}
    variants = {k: v for k, v in reader.variant_assignments.items() if k in citing}
    remaining = set(by_decision) - citing
    mentions = {g.entity_id for g in reader.mention_groups.values()}
    candidates = (
        set().union(*(naming(reader, k) for k in citing))
        - set().union(*(naming(reader, k) for k in remaining))
        - mentions
    ) & set(reader.entity_constructions)
    revision = reader.revision + 1 if row.state == "current" else reader.revision
    key = producer_key(ids, revision)

    def change(payload):
        for k, d in resolutions.items():
            payload["mention_resolutions"][k] = dict(
                group_ref=d.group_ref,
                status="unresolved",
                input_refs=without_erased(d.input_refs, erased, own),
                producer_ref=key,
            )
        for k in variants:
            payload["variant_assignments"].pop(k)
        for group in payload["mention_groups"].values():
            group["input_refs"] = without_erased(group["input_refs"], erased, own)
        payload["producers"][key] = removal_producer(ids, removed, token)

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
        decisions=tuple(
            Removal(
                a,
                "resolution" if a in resolutions else "variant",
                "unresolved" if a in resolutions else "dropped",
                tuple(cited[k] for k in sorted(by_decision[a] & erased)),
            )
            for a in sorted(citing)
        ),
        dropped_entities=tuple(sorted(str(e) for e in dropped)),
        kept_entities=tuple(sorted(str(e) for e in candidates - dropped)),
        unlinked_mentions=tuple(
            sorted(
                str(reader.mention_groups[d.group_ref].entity_id)
                for d in resolutions.values()
                if isinstance(d, Accepted)
            )
        ),
        dropped_inputs=tuple(sorted(set(reader.inputs) - set(revised.inputs))),
    )


def dependents_of(rows, ids: SourceIds, removed):
    """Each saved source other than the forgotten one that reads its
    document or a removed Entity, with the inputs through which it does."""
    target = Target(ids.original_data_id, frozenset(UUID(str(e)) for e in removed))
    for row in sorted(rows, key=lambda r: r.source):
        if row.is_retired or row.source == str(ids.identity_data_id):
            continue
        if cited := citations(row.description, target):
            yield row, cited


def revisions(rows, ids: SourceIds, removed, token=None):
    """Each dependent's row, its removal revision and what the removal does,
    each row parsed once. `impact` reports them; `finish_dependents` writes
    them."""
    reads = {r.source: corpus_reads(r.description) for r in rows if not r.is_retired}
    for row, cited in dependents_of(rows, ids, removed):
        readers = set().union(*(e for k, e in reads.items() if k != row.source))
        yield row, *removal_revision(row, cited, ids, removed, readers, token)


def impact(source, plan, rows) -> Impact:
    """What forgetting `source` with this plan does to the other saved
    sources, from their descriptions and the plan's ownership snapshot."""
    ids = source_ids(source)
    removed = removed_entities(ids, plan, rows)
    return Impact(
        ids,
        plan["revision"],
        tuple(sorted(str(e) for e in removed)),
        tuple(found for _, _, found in revisions(rows, ids, removed)),
    )


def removal_of(row, ids: SourceIds) -> bool:
    """Whether a failed row is a removal revision for this forget: a
    replacement or publication whose saved revision introduced this source's
    removal producer. A later revision that only carries that producer
    forward is not."""
    return (
        row.state == "failed"
        and not blocked(row)
        and producer_key(ids, row.revision) in row.description.producers
    )


def unfinished(tombstone, rows) -> list:
    """The saved sources a completed forget has not revised yet: a source
    that still reads the forgotten document or a removed Entity, and a
    removal revision that failed. Derived from the rows, not stored."""
    ids = source_ids(tombstone)
    removed = set(tombstone.removed_entity_ids)
    found = {row.source: row for row, _ in dependents_of(rows, ids, removed)}
    found.update({r.source: r for r in rows if removal_of(r, ids)})
    return [found[k] for k in sorted(found)]


def report(impact: Impact, *, plan, description, events) -> dict:
    """The dry run: what a forget removes from other sources, the traces its
    tombstone scrubs and the token to confirm."""
    dependents = [
        dict(
            asdict(d),
            decisions=[
                dict(asdict(r), citing=[c._asdict() for c in r.citing])
                for r in d.decisions
            ],
        )
        for d in impact.dependents
    ]
    decisions = [r for d in impact.dependents for r in d.decisions]
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
        dependents=dependents,
        counts=dict(
            dependents=len(impact.dependents),
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


async def write_removal(publisher, row, description, revise, rebuild_text):
    """Write one dependent's removal revision under its own writer
    reservation: a current row's next revision or a failed replacement's
    retry through `replace_one`, a failed text change's retry through
    `rebuild_text`, the writer of that text change the caller supplies, and
    a failed publication's through `finish_publication`. Each retry
    supersedes the saved description (an erasure retry). `revise` fails
    each at one of its stages. False when the dependent waits instead: a
    failed text change and no writer for it."""
    from .revisions import finish_publication, replace_one
    from .text_changes import TextChange

    if row.state == "failed" and row.resumed_by is None:
        await finish_publication(
            publisher, description, fault_stage="nodes" if revise else None
        )
        return True
    fault_stage = "replace_registered" if revise else None
    if row.state == "failed" and row.plan.get("text_change"):
        if rebuild_text is None:
            return False
        await rebuild_text(
            publisher,
            description,
            TextChange.from_plan(row.plan),
            expected_revision=row.revision,
            fault_stage=fault_stage,
        )
        return True
    await replace_one(
        publisher, description, expected_revision=row.revision, fault_stage=fault_stage
    )
    return True


async def finish_dependents(
    publisher, tombstone, rows, fault=None, rebuild_text=None
) -> dict:
    """Write each unfinished dependent's removal revision after the forget
    completed (`write_removal`), from `rows` as the caller read them. A
    failed removal revision resumes with its saved description. A dependent
    whose own withdrawal or forget is pending or failed waits
    (`dependent_unfinished`) until that attempt finishes; so does a failed
    text change when the caller supplies no writer for it. Stops at the
    first failure and reports it, not raised: the forget before it already
    completed. `fault` is one of forget.DEPENDENT_FAULTS:
    `forget_dependents` stops before the first revision begins, when there
    is one; `forget_dependent_revision` fails each removal revision."""
    ids = source_ids(tombstone)
    removed = set(tombstone.removed_entity_ids)
    done, waiting = [], []
    try:
        todo = unfinished(tombstone, rows)
        if todo and fault == "forget_dependents":
            raise IntentError(
                "injected_failure",
                "Injected failure before the dependents' removal revisions",
            )
        planned = {
            row.source: revised
            for row, revised, _ in revisions(rows, ids, removed, tombstone.impact_token)
        }
        for row in todo:
            description = (
                row.description if removal_of(row, ids) else planned.get(row.source)
            )
            if blocked(row) or not await write_removal(
                publisher,
                row,
                description,
                fault == "forget_dependent_revision",
                rebuild_text,
            ):
                waiting.append(
                    dict(
                        identity_data_id=row.source,
                        state=row.state,
                        operation=row.operation,
                    )
                )
                continue
            done.append(
                dict(identity_data_id=row.source, revision=description.revision)
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
            message="A dependent's own withdrawal or forget is pending or failed, or its failed text change needs its writer; finish it, then run forget or reconcile on the forgotten source",
        )
    return dict(
        dependents_revised=done,
        dependents_waiting=waiting,
        dependents_failed=failed,
    )
