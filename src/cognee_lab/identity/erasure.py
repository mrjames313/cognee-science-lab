"""What forgetting a source does to the sources that read it.

A dependent decision is a resolution, with its group, or a variant whose
inputs cite the forgotten source: its document's text, a span or chunk of
it, or an Entity the forget removes. Forget erases the source first and then
writes each dependent's removal revision: a resolution becomes unresolved,
a variant is dropped, a reusable recipe that only removed decisions named
goes with them, and inputs nothing cites any more are dropped
(`removal_revision`). `impact` computes all of it from saved descriptions
and the forget plan, never the live graph, and its token is what a caller
confirms. Nothing here is a ledger state: a dependent is unfinished while a
saved source still cites the forgotten document or a removed Entity
(`unfinished`).
"""

import json
from dataclasses import asdict, dataclass
from typing import Literal, NamedTuple
from uuid import UUID

from .erasure_rules import (
    ERASURE_IMPLEMENTATION,
    Erasure,
    erased_inputs,
    without_erased,
)
from .models import Accepted, CorpusObjectInput, IdentitySource
from .retirement import SourceIds, removed_entities, source_ids
from .validation import IntentError, decision_inputs, naming, object_digest

RESIDUE = (
    "LanceDB marks deleted vector rows; their bytes stay until a compaction and a cleanup of old table versions",
    "The graph store and SQLite keep deleted rows in their files until a checkpoint and VACUUM",
)


class Citation(NamedTuple):
    """One input through which a decision read what the forget removes."""

    input_ref: str
    kind: str
    consumed: str


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
        """A digest of the affected-decision set, which a caller confirms."""
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


def erasure_for(ids: SourceIds, removed) -> Erasure:
    return Erasure("", ids.original_data_id, frozenset(UUID(str(e)) for e in removed))


def citations(reader, erasure: Erasure) -> dict[str, Citation]:
    erased = erased_inputs(reader, erasure)
    found = {}
    for key in sorted(erased):
        item = reader.inputs[key]
        consumed = (
            item.entity_id if isinstance(item, CorpusObjectInput) else erasure.document
        )
        found[key] = Citation(key, item.kind, str(consumed))
    return found


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


def removal_revision(
    reader, ids: SourceIds, removed, readers=(), token=None, *, in_place=False
):
    """The dependent's next revision without what the forget removed, and
    what it removes. A recipe that a removed decision named and no remaining
    decision names goes, unless a saved source, this one included, still
    cites that Entity as a corpus input: dropping the last declaration would
    take the Entity out of the graph under a reader. `in_place` keeps the
    reader's revision: the removal applied to a failed replacement's saved
    revision, which that replacement then finishes with."""
    from .revisions import next_revision

    erasure = erasure_for(ids, removed)
    cited = citations(reader, erasure)
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
    revision = reader.revision if in_place else reader.revision + 1
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
    unlinked = sorted(
        str(reader.mention_groups[d.group_ref].entity_id)
        for d in resolutions.values()
        if isinstance(d, Accepted)
    )
    removals = tuple(
        Removal(
            a,
            "resolution" if a in resolutions else "variant",
            "unresolved" if a in resolutions else "dropped",
            tuple(cited[k] for k in sorted(by_decision[a] & erased)),
        )
        for a in sorted(citing)
    )
    return revised, dict(
        decisions=removals,
        dropped_entities=tuple(sorted(str(e) for e in dropped)),
        kept_entities=tuple(sorted(str(e) for e in candidates - dropped)),
        unlinked_mentions=tuple(unlinked),
        dropped_inputs=tuple(sorted(set(reader.inputs) - set(revised.inputs))),
    )


def readers_of(rows, *skip) -> set[UUID]:
    """Entities that saved sources other than `skip` list as corpus inputs."""
    found = set()
    for row in rows:
        if row.is_retired or row.source in skip:
            continue
        reader = IdentitySource.model_validate_json(row.description)
        found |= {
            i.entity_id
            for i in reader.inputs.values()
            if isinstance(i, CorpusObjectInput)
        }
    return found


def reads(reader, ids: SourceIds, removed) -> bool:
    return bool(erased_inputs(reader, erasure_for(ids, removed)))


def dependent_rows(rows, ids: SourceIds, removed):
    """Each saved source other than the forgotten one that reads its
    document or a removed Entity, with its description."""
    own = str(ids.identity_data_id)
    for row in sorted(rows, key=lambda r: r.source):
        if row.is_retired or row.source == own:
            continue
        reader = IdentitySource.model_validate_json(row.description)
        if reads(reader, ids, removed):
            yield row, reader


def impact(source, plan, rows) -> Impact:
    """What forgetting `source` with this plan does to the other saved
    sources, from their descriptions and the plan's ownership snapshot."""
    ids = source_ids(source)
    removed = removed_entities(ids, plan, rows)
    dependents = []
    for row, reader in dependent_rows(rows, ids, removed):
        _, parts = removal_revision(
            reader,
            ids,
            removed,
            readers_of(rows, row.source, str(ids.identity_data_id)),
            in_place=row.state != "current",
        )
        dependents.append(
            DependentImpact(
                dataset_id=row.dataset,
                identity_data_id=row.source,
                revision=row.revision,
                state=row.state,
                blocked=blocked(row),
                **parts,
            )
        )
    return Impact(
        ids,
        plan["revision"],
        tuple(sorted(str(e) for e in removed)),
        tuple(dependents),
    )


def blocked(row) -> bool:
    """A dependent whose removal waits for its own attempt: a pending row, or
    a failed one that replace does not resume. A failed replacement takes
    the removal in its saved revision instead."""
    return row.state != "current" and row.resumed_by != "replace"


def removal_of(row, ids: SourceIds) -> bool:
    """Whether a failed replacement row is the removal revision for this
    forget: its saved description names this source's removal producer."""
    if row.state != "failed" or row.resumed_by != "replace":
        return False
    saved = IdentitySource.model_validate_json(row.description)
    return any(
        p.implementation == ERASURE_IMPLEMENTATION
        and p.configuration.get("forgotten_identity_data_id")
        == str(ids.identity_data_id)
        for p in saved.producers.values()
    )


def unfinished(tombstone, rows) -> list:
    """The saved sources a completed forget has not revised yet: a source
    that still reads the forgotten document or a removed Entity, and a
    removal revision that failed. Derived from the rows, not stored."""
    ids = source_ids(tombstone)
    removed = set(tombstone.removed_entity_ids)
    found = {row.source: row for row, _ in dependent_rows(rows, ids, removed)}
    found.update({r.source: r for r in rows if removal_of(r, ids)})
    return [found[k] for k in sorted(found)]


def report(impact: Impact, *, plan, description, events, caller_files=()) -> dict:
    """The dry run: what a forget removes from other sources, the traces its
    tombstone scrubs, the files it leaves and the token to confirm."""
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
        caller_files=[str(f) for f in caller_files],
    )


async def remove_dependents(publisher, tombstone, *, fault_stage=None) -> dict:
    """Write each unfinished dependent's removal revision after the forget
    completed, each under its own writer reservation through `replace_one`.
    A failed removal revision resumes with its saved description, and a
    failed replacement finishes with the removal applied to its saved
    revision. A dependent whose own attempt is otherwise pending or failed
    waits
    (`dependent_unfinished`) until that attempt finishes and a rerun of
    forget or reconcile removes it. Stops at the first failure and reports
    it, not raised: the forget before it already completed. `fault_stage`
    "interrupted" stops before the first revision begins, when there is
    one; any other fails each removal revision there."""
    from .revisions import replace_one

    ids = source_ids(tombstone)
    removed = set(tombstone.removed_entity_ids)
    rows = await publisher.records.rows()
    revised, waiting = [], []
    try:
        todo = unfinished(tombstone, rows)
        if todo and fault_stage == "interrupted":
            raise IntentError(
                "injected_failure",
                "Injected failure before the dependents' removal revisions",
            )
        for row in todo:
            if removal_of(row, ids):
                description = IdentitySource.model_validate_json(row.description)
            elif blocked(row):
                waiting.append(
                    dict(
                        identity_data_id=row.source,
                        state=row.state,
                        operation=row.operation,
                    )
                )
                continue
            else:
                reader = IdentitySource.model_validate_json(row.description)
                description, _ = removal_revision(
                    reader,
                    ids,
                    removed,
                    readers_of(rows, row.source, str(ids.identity_data_id)),
                    tombstone.impact_token,
                    in_place=row.state != "current",
                )
            await replace_one(
                publisher,
                description,
                expected_revision=row.revision,
                fault_stage=fault_stage,
            )
            revised.append(
                dict(identity_data_id=row.source, revision=description.revision)
            )
    except Exception as exc:
        code = exc.code if isinstance(exc, IntentError) else type(exc).__name__
        return dict(
            dependents_revised=revised,
            dependents_waiting=waiting,
            dependents_failed=dict(code=code, message=str(exc)),
        )
    failed = None
    if waiting:
        failed = dict(
            code="dependent_unfinished",
            message="A dependent's own attempt is pending or failed; finish it, then run forget or reconcile on the forgotten source",
        )
    return dict(
        dependents_revised=revised,
        dependents_waiting=waiting,
        dependents_failed=failed,
    )
