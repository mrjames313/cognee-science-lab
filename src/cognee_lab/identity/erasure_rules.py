"""Admission rules for an erasure removal and for a re-add after forget.

A removal revision names a removal producer (`ERASURE_IMPLEMENTATION`) whose
configuration names the forgotten document and the Entities its forget
removed. `check_erasure_removals` admits it as that removal, all of it and
nothing else; `check_retry_chain` admits a chain of them, each in place
of a failed attempt's saved revision (`check_erasure_retry`). A re-add is a
fresh publication at the next revision that never brings back a forgotten
mention or Entity UUID (`admit_readd`). `admission.admit` calls the removal
rules in its rule order; the replace path and Publisher.readd call the
rest. Nothing here imports admission.
"""

from collections.abc import Mapping
from itertools import pairwise
from types import MappingProxyType
from typing import NamedTuple
from uuid import UUID

from .dependency import Target, citations
from .models import Accepted, CorpusObjectInput, Unresolved
from .validation import (
    IntentError,
    decision_inputs,
    decisions_digest,
    fresh_entity_id,
    fresh_mention_id,
    naming,
    naming_keys,
    referenced_corpus_ids,
    reusable_recipes,
)

ERASURE_IMPLEMENTATION = "removed by forget"


class Erasures(NamedTuple):
    """What the ledger says a removal revision may erase: the document of
    each forgotten source with the Entities its forget removed, and the
    Entities saved sources read as corpus inputs, which no removal drops."""

    forgotten: Mapping[UUID, frozenset[UUID]] = MappingProxyType({})
    readers: frozenset[UUID] = frozenset()


NO_ERASURES = Erasures()


def erasures_of(rows, source) -> Erasures:
    """The forgotten sources and the corpus readers among saved rows other
    than this source's."""
    forgotten, readers = {}, set()
    own = str(source.identity_data_id)
    for row in rows:
        if (tomb := row.tombstone) is not None:
            forgotten[tomb.original_data_id] = frozenset(tomb.removed_entity_ids)
        elif not row.is_retired and row.source != own:
            readers |= corpus_reads(row.description)
    return Erasures(MappingProxyType(forgotten), frozenset(readers))


def corpus_reads(description) -> set[UUID]:
    """The Entities a description lists as corpus inputs."""
    return {
        i.entity_id
        for i in description.inputs.values()
        if isinstance(i, CorpusObjectInput)
    }


def erasure_of(old, source, erasures: Erasures) -> tuple[str, Target] | None:
    """The removal producer this revision introduces, with what it erases,
    or None. Its configuration names the forgotten document and the removed
    Entities, and the ledger must agree: the document is a forgotten
    source's, and the Entities named are exactly the ones its forget
    removed, so no step removes only part of what the forget took."""
    found = [
        (key, p)
        for key, p in source.producers.items()
        if key not in old.producers
        and p.method == "captured_fixture"
        and p.implementation == ERASURE_IMPLEMENTATION
    ]
    if not found:
        return None
    try:
        ((key, producer),) = found
        config = producer.configuration
        document = UUID(config["forgotten_document_id"])
        removed = frozenset(UUID(e) for e in config["removed_entity_ids"])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise IntentError(
            "erasure_configuration",
            "One removal producer names the forgotten document and the removed Entities",
        ) from None
    if document == old.inputs[old.original_input_ref].data_id:
        raise IntentError(
            "erasure_configuration", "An erasure removes another document's inputs"
        )
    took = erasures.forgotten.get(document)
    if took is None or removed != took:
        raise IntentError(
            "erasure_unbound",
            "A removal producer names a forgotten source's document and exactly the Entities its forget removed",
        )
    return key, Target(document, removed)


def erased_decisions(old, erased) -> set[str]:
    """The old decisions that cite one of the erased input keys."""
    return {a for a, inputs in decision_inputs(old).items() if inputs & erased}


def without_erased(refs, erased, fallback):
    """Input refs with the erased keys stripped; the original document when
    nothing else remains."""
    return [k for k in refs if k not in erased] or [fallback]


class ErasureStep(NamedTuple):
    """One erasure removal step as the rules check it: the old revision's
    erased input keys and the decisions citing them, and the removal
    producer's key."""

    producer: str
    erased: set[str]
    citing: set[str]


def erasure_step(old, found) -> "ErasureStep | None":
    """The removal step `erasure_of` found, or None."""
    if found is None:
        return None
    producer, erasure = found
    erased = set(citations(old, erasure))
    return ErasureStep(producer, erased, erased_decisions(old, erased))


def check_erasure_removals(old, source, removal: ErasureStep | None, readers):
    """A revision that names a removal producer is an erasure removal, all
    of it and nothing else: it cites what the forget removed, removes every
    decision citing it (`check_erasure_complete`) and changes nothing more
    (`check_erasure_confined`)."""
    if removal is None:
        return
    check_erasure_cites(removal)
    check_erasure_complete(old, source, removal)
    check_erasure_confined(old, source, removal, readers)


def check_erasure_cites(removal: ErasureStep):
    """An erasure removal removes something: the old revision cites what
    the forget removed."""
    if not removal.erased:
        raise IntentError(
            "erasure_empty",
            "An erasure removal removes what its revision cites of the forgotten source",
        )


def check_retry_chain(chain, erasures: Erasures):
    """An erasure-retry chain: the saved descriptions that erasure retries
    superseded, in order, then the description the attempt begins with.
    Each step is an erasure removal in place of the one before
    (`check_erasure_retry`). A replacement's own step, from its previous
    revision to the chain's first description, is admission's."""
    for saved, source in pairwise(chain):
        check_erasure_retry(saved, source, erasures)


def check_erasure_retry(saved, source, erasures: Erasures):
    """A retry replaces a failed attempt's saved revision only by its
    erasure removal: the same revision, one removal producer new, and the
    removal rules."""
    removal = erasure_step(saved, erasure_of(saved, source, erasures))
    if source.revision != saved.revision or removal is None:
        raise IntentError(
            "revision_reuse", "Recovery must use the exact saved replacement intent"
        )
    check_erasure_removals(saved, source, removal, erasures.readers)


def check_erasure_complete(old, source, removal: ErasureStep):
    """Every old decision citing what the forget removed is removed: a
    resolution becomes unresolved in place under the removal producer, with
    the erased inputs stripped, and a variant is dropped. No erased input
    remains, in the inputs or a group's."""
    erased, citing = removal.erased, removal.citing
    for key in citing & set(old.mention_resolutions):
        was = old.mention_resolutions[key]
        removed = Unresolved(
            group_ref=was.group_ref,
            status="unresolved",
            input_refs=without_erased(was.input_refs, erased, old.original_input_ref),
            producer_ref=removal.producer,
        )
        if source.mention_resolutions.get(key) != removed:
            raise IntentError(
                "erasure_incomplete",
                "A resolution citing what the forget removed becomes unresolved under the removal producer",
            )
    if citing & set(source.variant_assignments):
        raise IntentError(
            "erasure_incomplete", "A variant citing what the forget removed is dropped"
        )
    if set(source.inputs) & erased or any(
        set(g.input_refs) & erased for g in source.mention_groups.values()
    ):
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

    for kind in ("mention_resolutions", "variant_assignments"):
        was, now = getattr(old, kind), getattr(source, kind)
        if {k: v for k, v in now.items() if k not in citing} != {
            k: v for k, v in was.items() if k not in citing
        }:
            unrelated("changes only the decisions citing what the forget removed")
    stripped = {
        k: g.model_copy(
            update=dict(
                input_refs=without_erased(g.input_refs, erased, old.original_input_ref)
            )
        )
        for k, g in old.mention_groups.items()
    }
    if source.mention_groups != stripped or any(
        old.inputs.get(k) != item for k, item in source.inputs.items()
    ):
        unrelated("keeps every group and input but the erased ones")
    if source.producers != {
        **old.producers,
        removal.producer: source.producers[removal.producer],
    }:
        unrelated("adds only its producer")
    removed_names = set().union(*(naming(old, k) for k in citing))
    remaining = set().union(
        *(
            naming(source, k)
            for k in [*source.mention_resolutions, *source.variant_assignments]
        )
    )
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
    """Every Entity UUID a description names: its recipes, its accepted
    targets, its variant endpoints and its corpus inputs."""
    named = set(source.entity_constructions)
    named.update(
        r.target_entity_id
        for r in source.mention_resolutions.values()
        if isinstance(r, Accepted)
    )
    for v in source.variant_assignments.values():
        named.update((v.source_entity_id, v.target_entity_id))
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
