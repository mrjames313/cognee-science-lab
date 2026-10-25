"""Admission rules for an erasure removal and for a re-add after forget.

A removal revision names a removal producer (`ERASURE_IMPLEMENTATION`) whose
configuration names the forgotten document, the Entities its forget
removed, the records the revision removes (`removed_records`) and, below
the first level of a cascade, the removed records of other sources it
cites (`cited_records`). `check_erasure_removals` admits it as that
removal, all of it and nothing else; `check_retry_chain` admits a chain of
them, each in place of a failed attempt's saved revision
(`check_erasure_retry`). A cited record binds only when a removal written
for the same forget lists it, and that removal is bound in turn, back to
the tombstone (`bound_removals`). A removal producer never changes once
written (`check_removal_producers_kept`). A re-add is a fresh publication
at the next revision that never brings back a forgotten mention or Entity
UUID (`admit_readd`). `admission.admit` calls the removal rules in its rule
order; the replace path and Publisher.readd call the rest. Nothing here
imports admission.
"""

import json
from collections.abc import Hashable, Mapping
from itertools import pairwise
from types import MappingProxyType
from typing import NamedTuple
from uuid import UUID

from .decisions import decisions_digest, naming_keys
from .dependency import Target, citations, read_records
from .models import CorpusObjectInput, IdentitySource
from .records import (
    REGISTRY,
    RemovedRecord,
    naming,
    record_inputs,
    record_keys,
    record_type_of,
)
from .validation import (
    IntentError,
    fresh_entity_id,
    fresh_mention_id,
    referenced_corpus_ids,
    reusable_recipes,
)

ERASURE_IMPLEMENTATION = "removed by forget"
UNBOUND_RECORDS = (
    "erasure_unbound",
    "A removal names exactly the removed records its revision cites, each listed by a removal written for the same forget",
)


def producer_key(identity_data_id, revision: int) -> str:
    """The key of the removal producer a revision of a dependent names for
    the forget of this identity source."""
    return f"forget_{identity_data_id}_r{revision}"


def is_removal_producer(producer) -> bool:
    return (
        producer.method == "captured_fixture"
        and producer.implementation == ERASURE_IMPLEMENTATION
    )


class RemovalClaim(NamedTuple):
    """What a removal producer's configuration says its revision did: the
    forget it serves (its identity source, document and removed Entities),
    the records it removed and the removed records it cites."""

    forgotten: UUID
    document: UUID
    removed_entities: frozenset[UUID]
    removed_records: frozenset[RemovedRecord]
    cited_records: frozenset[RemovedRecord]


def removal_claim(producer) -> RemovalClaim:
    """The claim of one removal producer; `erasure_configuration` when its
    configuration is malformed."""
    try:
        config = producer.configuration
        return RemovalClaim(
            UUID(config["forgotten_identity_data_id"]),
            UUID(config["forgotten_document_id"]),
            frozenset(UUID(e) for e in config["removed_entity_ids"]),
            frozenset(map(RemovedRecord.parse, config["removed_records"])),
            frozenset(map(RemovedRecord.parse, config["cited_records"])),
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        raise IntentError(
            "erasure_configuration",
            "One removal producer names the forgotten source, its document, the removed Entities and the removed and cited records",
        ) from None


def written_claims(rows, document, entities) -> list[RemovalClaim]:
    """The removals written for the forget of `document` that removed
    `entities`: each removal producer of a saved source that names them,
    unless it is new in the row's revision and only a pending or failed
    attempt holds it (`PublicationRow.holds_served`): a removal served
    before a later attempt at its revision failed is written, and citers
    may pin what it removed.
    Producers are immutable (`check_removal_producers_kept`), so a later
    revision still carries a written one. A retired row's removals bind
    nothing: a withdrawal or forget of a source holding a removal waits for
    that forget's cascade (erasure.refuse_unfinished_cascade). A producer
    that does not parse binds nothing."""
    found = []
    for row in rows:
        if row.description is None or row.is_retired:
            continue
        for key, producer in sorted(row.description.producers.items()):
            if not is_removal_producer(producer):
                continue
            try:
                claim = removal_claim(producer)
            except IntentError:
                continue
            if (claim.document, claim.removed_entities) != (document, entities):
                continue
            introduced = key == producer_key(claim.forgotten, row.revision)
            if introduced and not row.holds_served:
                continue
            found.append(claim)
    return found


def levels(
    removals, known=MappingProxyType({})
) -> tuple[dict[Hashable, int], dict[RemovedRecord, int]]:
    """Each removal that binds, with its level, and each record a bound
    removal removes, with that level. `removals` maps each removal to the
    records it cites and the records it removes; `known` holds records
    already bound, with their levels. A removal binds when every record it
    cites is removed by a bound removal, one level below the deepest of
    them, or at level 1 when it cites none. So binding reaches back to the
    forget, and a removal that cites a record no bound removal lists binds
    nothing, nor does any removal below it."""
    depth, removed = {}, dict(known)
    grew = True
    while grew:
        grew = False
        for key, (cited, removes) in removals.items():
            if key in depth or not cited <= removed.keys():
                continue
            depth[key] = 1 + max((removed[r] for r in cited), default=0)
            for record in removes:
                removed.setdefault(record, depth[key])
            grew = True
    return depth, removed


def bound_removals(rows, document, entities) -> dict[RemovedRecord, int]:
    """Each record that a written removal for this forget removed, with the
    level of that removal, bound inductively (`levels`), so a removal
    written out of order binds nothing below it."""
    claims = written_claims(rows, document, entities)
    return levels(
        {i: (c.cited_records, c.removed_records) for i, c in enumerate(claims)}
    )[1]


class Erasures(NamedTuple):
    """What the ledger says a removal revision may erase: the document of
    each forgotten source with the Entities its forget removed, the
    Entities saved sources read as corpus inputs, which no removal drops,
    each forgotten document's identity source, whose saved records a
    removal may erase too, the records the bound removals of each forget
    removed (`bound_removals`), which a removal below them may cite, and
    the document of each source re-added since its last forget, with the
    Entities that forget removed, which only a retry's saved removal may
    name (`erasure_of`)."""

    forgotten: Mapping[UUID, frozenset[UUID]] = MappingProxyType({})
    readers: frozenset[UUID] = frozenset()
    sources: Mapping[UUID, UUID] = MappingProxyType({})
    records: Mapping[UUID, frozenset[RemovedRecord]] = MappingProxyType({})
    earlier: Mapping[UUID, frozenset[UUID]] = MappingProxyType({})


NO_ERASURES = Erasures()


def erasures_of(rows, source) -> Erasures:
    """The forgotten sources, the corpus readers among saved rows other
    than this source's, each forget's bound removed records and the last
    forget of each source re-added since (`PublicationRow.last_tombstone`)."""
    forgotten, sources, records, earlier = {}, {}, {}, {}
    for row in rows:
        if (last := row.last_tombstone) is not None:
            earlier[last.original_data_id] = frozenset(last.removed_entity_ids)
            sources.setdefault(last.original_data_id, last.identity_data_id)
        if (tomb := row.tombstone) is not None:
            took = frozenset(tomb.removed_entity_ids)
            forgotten[tomb.original_data_id] = took
            sources[tomb.original_data_id] = tomb.identity_data_id
            records[tomb.original_data_id] = frozenset(
                bound_removals(rows, tomb.original_data_id, took)
            )
    return Erasures(
        MappingProxyType(forgotten),
        frozenset(corpus_readers(rows, str(source.identity_data_id))),
        MappingProxyType(sources),
        MappingProxyType(records),
        MappingProxyType(earlier),
    )


def corpus_reads(description) -> set[UUID]:
    """The Entities a description lists as corpus inputs."""
    return {
        i.entity_id
        for i in description.inputs.values()
        if isinstance(i, CorpusObjectInput)
    }


def corpus_readers(rows, source: str) -> set[UUID]:
    """The Entities that saved sources other than `source` list as corpus
    inputs."""
    return set().union(
        *(
            corpus_reads(r.description)
            for r in rows
            if not r.is_retired and r.source != source
        )
    )


def drop_unnamed_recipes(old, removed, revised, readers):
    """`revised`, which is `old` after the removal of the records in
    `removed`, less the recipes only those records named.

    A recipe is a candidate when a removed record of `old` names it and no
    remaining record does. Mention Entities stay with their groups. A
    candidate stays when a saved source reads its Entity as a corpus input:
    `revised` itself, or another source (`readers`). Dropping its last
    declaration would take the Entity out of the graph under its reader
    (`check_dropped_unread`).

    An erasure's removal and a reviewer's both drop recipes this way.
    Returns the revision, the dropped recipes and the kept candidates."""
    remaining = set(record_keys(old)) - set(removed)
    candidates = (
        set().union(*(naming(old, k) for k in removed))
        - set().union(*(naming(old, k) for k in remaining))
        - {g.entity_id for g in old.mention_groups.values()}
    ) & set(old.entity_constructions)
    dropped = frozenset(candidates - corpus_reads(revised) - set(readers))
    payload = revised.model_dump(mode="json")
    for e in dropped:
        payload["entity_constructions"].pop(str(e))
    return (
        IdentitySource.model_validate_json(json.dumps(payload)),
        dropped,
        frozenset(candidates - dropped),
    )


class Erasure(NamedTuple):
    """A removal producer a revision introduces: its key, its claim and the
    target its revision erases."""

    producer: str
    claim: RemovalClaim
    target: Target


def erasure_of(old, source, erasures: Erasures, *, bind=True) -> Erasure | None:
    """The removal producer this revision introduces, with what it erases,
    or None. Its key is `producer_key` of the forgotten source and this
    revision, which `written_claims` and `erasure.removal_of` read to tell
    the revision that introduced it. Its configuration names the forgotten
    document and the removed
    Entities, and the ledger must agree: the document is a forgotten
    source's, and the Entities named are exactly the ones its forget
    removed, so no step removes only part of what the forget took. The
    ledger also names that source, whose saved records the removal
    erases with its document. The removed records it cites are exactly the
    bound ones (`bound_removals`) its old revision reads, so a removal
    neither leaves a citer of one nor claims one no bound removal lists.
    Without `bind`, for a retry's saved removal or a retry-chain step an
    earlier begin admitted, the records it cites count as bound too, so it
    still names every bound record its old revision reads and only records
    it reads: the attempt that admitted it found them bound, and an
    upstream that retired since unbinds them without undoing the removal
    (`admission.admit`, `check_retry_chain`). Its forget may then also be
    the last one of a source re-added since (`Erasures.earlier`): the
    re-add waited for that forget's cascade, which the removal was part
    of."""
    found = [
        (key, p)
        for key, p in source.producers.items()
        if key not in old.producers and is_removal_producer(p)
    ]
    if not found:
        return None
    if len(found) != 1:
        raise IntentError(
            "erasure_configuration", "A revision introduces one removal producer"
        )
    ((key, producer),) = found
    claim = removal_claim(producer)
    if key != producer_key(claim.forgotten, source.revision):
        raise IntentError(
            "erasure_configuration",
            "A removal producer's key names the forgotten source and its revision",
        )
    if claim.document == old.inputs[old.original_input_ref].data_id:
        raise IntentError(
            "erasure_configuration", "An erasure removes another document's inputs"
        )
    took = erasures.forgotten.get(claim.document)
    if not bind and claim.removed_entities != took:
        took = erasures.earlier.get(claim.document)
    if took is None or claim.removed_entities != took:
        raise IntentError(
            "erasure_unbound",
            "A removal producer names a forgotten source's document and exactly the Entities its forget removed",
        )
    bound = erasures.records.get(claim.document, frozenset())
    if not bind:
        bound |= claim.cited_records
    if not claim.cited_records <= bound or claim.cited_records != read_records(
        old, bound
    ):
        raise IntentError(*UNBOUND_RECORDS)
    identity = erasures.sources.get(claim.document)
    target = Target(
        claim.document,
        took,
        frozenset([identity] if identity else []),
        claim.cited_records,
    )
    return Erasure(key, claim, target)


def erased_decisions(old, erased) -> set[str]:
    """The old decisions that cite one of the erased input keys."""
    return {a for a, inputs in record_inputs(old).items() if inputs & erased}


class ErasureStep(NamedTuple):
    """One erasure removal step as the rules check it: the old revision's
    erased input keys and the decisions citing them, the removal producer's
    key and the records it says it removes."""

    producer: str
    erased: set[str]
    citing: set[str]
    removed_records: frozenset[RemovedRecord] = frozenset()


def erasure_step(old, found: Erasure | None) -> "ErasureStep | None":
    """The removal step `erasure_of` found, or None."""
    if found is None:
        return None
    erased = set(citations(old, found.target))
    return ErasureStep(
        found.producer,
        erased,
        erased_decisions(old, erased),
        found.claim.removed_records,
    )


def check_removal_producers_kept(old, source):
    """A removal producer stays, unchanged, in every later revision of its
    source: the removals below it read what it removed from its
    configuration (`bound_removals`)."""
    for key, producer in old.producers.items():
        if is_removal_producer(producer) and source.producers.get(key) != producer:
            raise IntentError(
                "removal_producer_changed",
                "A removal producer stays unchanged in every later revision of its source",
            )


def check_erasure_removals(
    old, source, removal: ErasureStep | None, readers, served: frozenset[int]
):
    """A revision that names a removal producer is an erasure removal, all
    of it and nothing else: it cites what the forget removed, removes every
    decision citing it (`check_erasure_complete`), changes nothing more
    (`check_erasure_confined`) and its producer lists what it removed
    (`check_erasure_records`). `served` holds the revisions the removal may
    name as the last the ledger served of its source: the old one, for a
    removal at the next revision."""
    if removal is None:
        return
    check_erasure_cites(removal)
    check_erasure_complete(old, source, removal)
    check_erasure_confined(old, source, removal, readers)
    check_erasure_records(old, source, removal, served)


def check_erasure_cites(removal: ErasureStep):
    """An erasure removal removes something: the old revision cites what
    the forget removed."""
    if not removal.erased:
        raise IntentError(
            "erasure_empty",
            "An erasure removal removes what its revision cites of the forgotten source",
        )


def check_erasure_records(old, source, removal: ErasureStep, served: frozenset[int]):
    """The removal producer lists exactly the records its revision removes,
    as the old revision held them and as last served (`RemovedRecord.of`),
    at one of the `served` revisions: the removals below it bind to that
    list (`bound_removals`)."""
    if removal.removed_records not in [
        {RemovedRecord.of(old, k, last) for k in removal.citing} for last in served
    ]:
        raise IntentError(
            "erasure_incomplete",
            "A removal producer lists exactly the records its revision removes, as they were before",
        )


def check_retry_chain(chain, erasures: Erasures, served: int, saved):
    """An erasure-retry chain: the saved descriptions that erasure retries
    superseded, in order, then the description the attempt begins with.
    Each step is an erasure removal in place of the one before
    (`check_erasure_retry`). A replacement's own step, from its previous
    revision to the chain's first description, is admission's. `served` is
    the row's verified revision and `saved` the description its failed
    attempt saved. A step that ends after `saved` is new in this begin: the
    removed records it cites are bound now, and it lists its records as
    last served at exactly `served`. A step up to `saved` was admitted by an
    earlier begin, which found what it cites bound; an upstream may have
    retired since, so its binding is not checked again, only its shape.
    The row may also have been served at that step's own revision since
    (the retry completed, and a later attempt at its revision failed), so
    it may also list the revision before."""
    steps = list(pairwise(chain))
    for i, (before, after) in enumerate(steps):
        new = i == len(steps) - 1 and after != saved
        last = frozenset({served} if new else {served, after.revision - 1})
        check_erasure_retry(before, after, erasures, last, bind=new)


def check_erasure_retry(
    saved, source, erasures: Erasures, served: frozenset[int], *, bind=True
):
    """A retry replaces a failed attempt's saved revision only by its
    erasure removal: the same revision, one removal producer new, and the
    removal rules (`erasure_of` says what `bind` checks)."""
    removal = erasure_step(saved, erasure_of(saved, source, erasures, bind=bind))
    if source.revision != saved.revision or removal is None:
        raise IntentError(
            "revision_reuse", "Recovery must use the exact saved replacement intent"
        )
    check_erasure_removals(saved, source, removal, erasures.readers, served)


def check_erasure_complete(old, source, removal: ErasureStep):
    """Every old decision citing what the forget removed is removed as its
    record type says (records.REGISTRY): a resolution becomes unresolved in
    place under the removal producer, with the erased inputs stripped, and
    a variant is dropped. No erased input remains, in the inputs or in the
    other parts that hold a record's inputs (`RecordKind.stripped`)."""
    erased, citing = removal.erased, removal.citing
    for key in sorted(citing):
        kind = REGISTRY[record_type_of(old, key)]
        removed = kind.removed(old, key, dict.fromkeys(erased), removal.producer, None)
        if getattr(source, kind.field).get(key) != removed:
            raise IntentError(
                "erasure_incomplete",
                "A decision citing what the forget removed is removed: a resolution becomes unresolved under the removal producer and a variant is dropped",
            )
    held = [
        part.input_refs
        for kind in REGISTRY.values()
        for field in kind.stripped(old, citing, dict.fromkeys(erased))
        for part in getattr(source, field).values()
    ]
    if set(source.inputs) & erased or any(set(refs) & erased for refs in held):
        raise IntentError("erasure_incomplete", "No erased input remains")


def check_erasure_confined(old, source, removal: ErasureStep, readers):
    """Every other decision, group, input, recipe and producer is unchanged:
    groups lose only the erased inputs, inputs nothing cites any more go, the
    removal producer is the one producer added, and a reusable recipe goes
    only when a removed decision named it, no remaining decision names it
    and no saved source reads it as a corpus input (`check_dropped_unread`)."""
    erased, citing = removal.erased, removal.citing

    def unrelated(message):
        raise IntentError("erasure_unrelated", "An erasure removal " + message)

    fields = ("dataset_id", "identity_data_id", "original_input_ref")
    if any(getattr(old, f) != getattr(source, f) for f in fields):
        unrelated("keeps the dataset, the identity source and its document")

    for kind in REGISTRY.values():
        was, now = getattr(old, kind.field), getattr(source, kind.field)
        if {k: v for k, v in now.items() if k not in citing} != {
            k: v for k, v in was.items() if k not in citing
        }:
            unrelated("changes only the decisions citing what the forget removed")
    stripped = {
        field: {**getattr(old, field), **parts}
        for kind in REGISTRY.values()
        for field, parts in kind.stripped(old, citing, dict.fromkeys(erased)).items()
    }
    if any(getattr(source, field) != parts for field, parts in stripped.items()) or any(
        old.inputs.get(k) != item for k, item in source.inputs.items()
    ):
        unrelated("keeps every group and input but the erased ones")
    if source.producers != {
        **old.producers,
        removal.producer: source.producers[removal.producer],
    }:
        unrelated("adds only its producer")
    removed_names = set().union(*(naming(old, k) for k in citing))
    remaining = set().union(*(naming(source, k) for k in record_keys(source)))
    for eid, recipe in old.entity_constructions.items():
        kept = source.entity_constructions.get(eid)
        if kept is None and (eid not in removed_names or eid in remaining):
            unrelated(
                "drops only a recipe that a removed decision named and no remaining decision names"
            )
        if kept is not None and kept != recipe:
            unrelated("keeps every recipe unchanged")
    if set(source.entity_constructions) - set(old.entity_constructions):
        unrelated("adds no recipe")
    check_dropped_unread(old, source, readers)


def check_dropped_unread(old, source, readers):
    """An erasure removal drops no recipe that a saved source reads as a
    corpus input, this one included: the last declaration's removal would
    take the Entity out of the graph under its reader."""
    dropped = set(old.entity_constructions) - set(source.entity_constructions)
    if dropped & (set(readers) | corpus_reads(source)):
        raise IntentError(
            "erasure_unrelated",
            "An erasure removal drops no recipe a saved source reads as a corpus input",
        )


def entity_ids_named(source):
    """Every Entity UUID a description names: its recipes, what each record
    names (`records.naming`) and its corpus inputs."""
    named = set(source.entity_constructions)
    named.update(*(naming(source, k) for k in record_keys(source)))
    named.update(
        i.entity_id for i in source.inputs.values() if isinstance(i, CorpusObjectInput)
    )
    return named


def check_removed_entity_ids(tombstone, source, removed):
    """A re-add names no Entity the forget removed and no mention UUID of
    any forgotten life, in any role: an old recipe does not authorize
    recreating a retired object under its UUID. A mention UUID is forbidden
    whether or not its node was ever written, since a publication that
    failed early leaves it out of the forget's plan."""
    forbidden = set(removed) | set(tombstone.all_mention_ids)
    if forbidden & entity_ids_named(source):
        raise IntentError(
            "forgotten_uuid_reused",
            "A re-add does not recreate a mention or Entity UUID the forget removed",
        )


def replacement_entity_id(identity_data_id, revision, removed_id):
    """The UUID a re-add gives the replacement of a removed Entity that no
    resolution or variant names."""
    return fresh_entity_id(identity_data_id, revision, f"replaces:{removed_id}")


def readd_ids(tombstone, source) -> set[UUID]:
    """Reusable Entities a re-add creates: its recipes that were not reusable
    Entities of any forgotten life of the source and that no listed corpus
    input names as existing."""
    return (
        set(reusable_recipes(source))
        - tombstone.all_reusable_ids
        - referenced_corpus_ids(source)
    )


def check_readd_entity_ids(tombstone, source, removed):
    """A new reusable Entity in a re-add derives from the key of a resolution
    or variant that names it, as in any revision. Only an Entity nothing
    names replaces a removed one by that Entity's UUID."""
    identity = tombstone.identity_data_id
    replacements = {
        replacement_entity_id(identity, source.revision, r) for r in removed
    }
    for eid in readd_ids(tombstone, source):
        keys = naming_keys(source, eid)
        allowed = {fresh_entity_id(identity, source.revision, k) for k in keys}
        if eid not in (allowed if keys else replacements):
            raise IntentError(
                "entity_uuid_not_derived",
                "A re-added reusable Entity's UUID derives from a key that names it; only an Entity nothing names derives from the removed Entity it replaces",
            )


def differs_from_forgotten(tombstone, source) -> dict[str, bool]:
    """Whether a re-add's text and its reviewed decisions differ from the
    forgotten revision's, by the tombstone's digests. A report, never a
    refusal: a re-add may bring other text or other decisions."""
    doc = source.inputs[source.original_input_ref]
    return dict(
        text=doc.text_sha256 != tombstone.text_sha256,
        decisions=decisions_digest(source) != tombstone.decisions_sha256,
    )


async def admit_readd(graph, tombstone, source, removed):
    """A re-add after forget is a fresh publication of the same identity
    source and document at the next revision, from the caller's files, with
    any text and decisions. Every group is fresh: its UUID derives from the
    new revision, repeats no mention or Entity UUID of any forgotten life,
    and is not in the graph. No Entity in `removed`, the ones the
    forget took away, returns; a reusable one is replaced by a derived UUID:
    from a key that names it, or from the removed UUID when nothing names
    it."""
    from .storage import READD_REVISION

    doc = source.inputs[source.original_input_ref]
    if (source.dataset_id, source.identity_data_id, doc.data_id) != (
        tombstone.dataset_id,
        tombstone.identity_data_id,
        tombstone.original_data_id,
    ):
        raise IntentError(
            "source_changed", "Re-add the forgotten identity source and its document"
        )
    if source.revision != tombstone.revision + 1:
        raise IntentError(*READD_REVISION)
    for key, group in source.mention_groups.items():
        if group.entity_id in tombstone.used_entity_ids:
            raise IntentError(
                "fresh_uuid_reused", "A fresh group requires a fresh Entity UUID"
            )
        if group.entity_id != fresh_mention_id(
            tombstone.identity_data_id, source.revision, key
        ):
            raise IntentError(
                "fresh_uuid_not_derived",
                "A fresh group's Entity UUID derives from its source, revision and group key",
            )
    check_removed_entity_ids(tombstone, source, removed)
    check_readd_entity_ids(tombstone, source, removed)
    probes = [
        (source.mention_groups[k].entity_id, "fresh_uuid_in_graph", "mention")
        for k in sorted(source.mention_groups)
    ] + [
        (e, "entity_uuid_in_graph", "reusable")
        for e in sorted(readd_ids(tombstone, source), key=str)
    ]
    for entity_id, code, kind in probes:
        if await graph.get_node(str(entity_id)) is not None:
            raise IntentError(
                code, f"New {kind} Entity UUID already exists in the graph"
            )
