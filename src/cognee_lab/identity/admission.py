"""Admission of a reviewed replacement: what the new description may claim.

One map states the edit. For each old occurrence, in order, it gives the new
occurrence it became, or None if it was removed; a new occurrence that nothing
maps to is an addition. The rules are stated over occurrences and groups, never
over kinds of edit, so removal, addition, split, combination, a prefix shift,
a correction with unchanged text and their mixtures are particular maps.
Whether the text changed decides three rules: with unchanged text every mapped
occurrence keeps its span and a continuing group may change its decision in
place; with changed text span-scoped variants are refused. Another
document's inputs, corpus objects and other sources' saved records keep
their content under one key: a span may only move, and a decision
re-confirmed on a new input names a new producer. Functions below follow the order in which `admit` applies them.
Two rules read the graph, so their callers run them apart from `admit`. On
a first attempt no UUID the revision introduces may be a node yet
(`check_absent_from_graph`), and every corpus input a decision lists names
an Entity that exists (`check_corpus_inputs_exist`, run by every admission
of a publication), whether a decision or a group cites it.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import NamedTuple

from .models import (
    CorpusObjectInput,
    SourceTextInput,
)
from .decisions import naming_keys
from .records import record_inputs, reviewed_decisions
from .erasure_rules import (
    NO_ERASURES,
    check_erasure_removals,
    check_removal_producers_kept,
    erasure_of,
    erasure_step,
)
from .validation import (
    IntentError,
    cited_inputs,
    fresh_entity_id,
    fresh_mention_id,
    is_foreign,
    referenced_corpus_ids,
    reusable_recipes,
    text_digest,
    uses_of,
)


class OccurrenceRef(NamedTuple):
    group: str
    index: int


OccurrenceMap = dict[str, tuple[OccurrenceRef | None, ...]]


def parse_occurrence_map(raw) -> OccurrenceMap:
    """Parse a map from JSON or code into typed references."""
    if not isinstance(raw, dict) or not all(isinstance(k, str) for k in raw):
        raise IntentError("occurrence_changed", "An occurrence map is keyed by group")
    parsed = {}
    for key, entries in raw.items():
        if not isinstance(entries, (list, tuple)):
            raise IntentError(
                "occurrence_changed", "Map each old occurrence, in order, once"
            )
        refs = []
        for entry in entries:
            if entry is None:
                refs.append(None)
            elif (
                isinstance(entry, (list, tuple))
                and len(entry) == 2
                and isinstance(entry[0], str)
                and type(entry[1]) is int
            ):
                refs.append(OccurrenceRef(*entry))
            else:
                raise IntentError(
                    "occurrence_changed",
                    "Map an old occurrence to null or one [group, index] pair",
                )
        parsed[key] = tuple(refs)
    return parsed


def identity_map(source) -> OccurrenceMap:
    """Every occurrence stays where it is, as in a prefix insertion."""
    return {
        k: tuple(OccurrenceRef(k, i) for i in range(len(g.occurrences)))
        for k, g in source.mention_groups.items()
    }


@dataclass(frozen=True)
class GroupFate:
    continuing: frozenset[str]
    retired: frozenset[str]
    fresh: frozenset[str]


@dataclass(frozen=True)
class Origin:
    """One mapped old occurrence: where it was and where it is now."""

    old: OccurrenceRef
    new: OccurrenceRef


def admit(
    old,
    source,
    before,
    after,
    occurrence_map,
    *,
    first_attempt=True,
    erasures=NO_ERASURES,
):
    """Admit any reviewed mix of kept, removed, added and regrouped occurrences,
    with changed or unchanged text.

    Only a first attempt chooses new UUIDs; a retry completes a saved plan,
    which may predate the derivation rules. Only a first attempt checks that
    the removed records a removal cites are bound now: an upstream that
    retired since unbinds them without undoing the removal
    (`erasure_rules.erasure_of`). `erasures` is what the ledger
    lets a removal producer claim (`erasure_rules.erasures_of`); without it
    every removal producer is refused.
    """
    text_changed = before != after
    check_text_present(before, after)
    check_source_identity(old, source, before, after)
    check_next_revision(old, source)
    origins = map_origins(old, occurrence_map)
    check_old_slices(old, before)
    check_targets_exist(source, origins)
    check_single_origin(origins)
    check_same_text(old, source, origins)
    if not text_changed:
        check_same_spans(old, source, origins)
    check_new_slices(source, after)
    fate = group_fate(old, source, origins)
    check_fresh_keys(old, fate.fresh)
    check_unused_entity_ids(old, source, fate.fresh)
    if first_attempt:
        check_revision_scoped_ids(old, source, fate.fresh)
    check_continuing_resolutions(old, source, fate)
    check_fresh_resolution_ids(old, source, fate)
    check_one_resolution_per_fresh_group(source, fate)
    check_mention_recipes(old, source, fate)
    check_reusable_recipes(old, source)
    if first_attempt:
        check_derived_entity_ids(old, source)
    removal = erasure_step(old, erasure_of(old, source, erasures, bind=first_attempt))
    check_scoped_variants(old, source, removal)
    check_new_variant_keys(old, source)
    check_foreign_inputs(old, source)
    check_reconfirmations(old, source)
    check_removal_producers_kept(old, source)
    check_erasure_removals(
        old, source, removal, erasures.readers, frozenset([old.revision])
    )
    if text_changed:
        check_continuing_decisions(old, source, fate)
        check_no_span_variants(source)
    return fate


def check_text_present(before, after):
    if not before or not after:
        raise IntentError("empty_text", "A replacement keeps a non-empty text")


def check_source_identity(old, source, before, after):
    key = old.original_input_ref
    if (source.dataset_id, source.identity_data_id, source.original_input_ref) != (
        old.dataset_id,
        old.identity_data_id,
        key,
    ):
        raise IntentError(
            "not_admitted", "Text replacement must preserve source identity"
        )
    for value in [old, source]:
        check_input_kinds(value)
    a, b = old.inputs[key], source.inputs[key]
    if a.data_id != b.data_id or a.dataset_id != b.dataset_id:
        raise IntentError("not_admitted", "Original Data identity must remain stable")
    if text_digest(before) != a.text_sha256 or text_digest(after) != b.text_sha256:
        raise IntentError(
            "source_changed", "Saved text transition fingerprints disagree"
        )


def check_input_kinds(description):
    """Inputs are texts, spans, chunks, corpus objects and saved records.
    Every text but the original is another document of the same dataset.
    Publisher.admit_inputs, which every path runs, keeps each saved record
    another source's of the same dataset (chains.check_citation_scope)."""
    own = description.inputs[description.original_input_ref]
    for key, item in description.inputs.items():
        if (
            isinstance(item, SourceTextInput)
            and key != description.original_input_ref
            and (item.dataset_id != own.dataset_id or item.data_id == own.data_id)
        ):
            raise IntentError(
                "not_admitted",
                "Another text input is a different document of the same dataset",
            )


def check_next_revision(old, source):
    if source.revision != old.revision + 1:
        raise IntentError(
            "not_admitted", "A group change advances exactly one revision"
        )


def map_origins(old, occurrence_map: OccurrenceMap):
    if set(occurrence_map) != set(old.mention_groups):
        raise IntentError("occurrence_changed", "Map every old group")
    origins = []
    for key, previous in old.mention_groups.items():
        refs = occurrence_map[key]
        if len(refs) != len(previous.occurrences):
            raise IntentError(
                "occurrence_changed", "Map each old occurrence, in order, once"
            )
        origins += [
            Origin(OccurrenceRef(key, i), ref) for i, ref in enumerate(refs) if ref
        ]
    return origins


def check_old_slices(old, before):
    for group in old.mention_groups.values():
        if any(before[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed", "Previous occurrence does not match text"
            )


def check_targets_exist(source, origins):
    for o in origins:
        group = source.mention_groups.get(o.new.group)
        if group is None or not 0 <= o.new.index < len(group.occurrences):
            raise IntentError(
                "occurrence_changed", "Mapped occurrence is not in the new source"
            )


def check_single_origin(origins):
    if len({o.new for o in origins}) != len(origins):
        raise IntentError(
            "occurrence_changed", "A new occurrence has at most one origin"
        )


def occurrence(description, ref):
    return description.mention_groups[ref.group].occurrences[ref.index]


def check_same_text(old, source, origins):
    for o in origins:
        if occurrence(source, o.new).text != occurrence(old, o.old).text:
            raise IntentError(
                "occurrence_changed",
                "Mapped occurrence text differs from the old occurrence",
            )


def check_same_spans(old, source, origins):
    """With unchanged text nothing re-marks the document, so a mapped
    occurrence stays at its span even when another has the same text."""
    for o in origins:
        previous, current = occurrence(old, o.old), occurrence(source, o.new)
        if (current.start, current.end) != (previous.start, previous.end):
            raise IntentError(
                "occurrence_moved",
                "With unchanged text a mapped occurrence keeps its start and end",
            )


def check_new_slices(source, after):
    for group in source.mention_groups.values():
        if any(after[o.start : o.end] != o.text for o in group.occurrences):
            raise IntentError(
                "occurrence_changed",
                "New occurrence does not match its exact document slice",
            )


def same_identity(old, source, key):
    previous, current = old.mention_groups[key], source.mention_groups[key]
    return (current.entity_id, current.document_ref) == (
        previous.entity_id,
        previous.document_ref,
    )


def fed_only_by_itself(key, feeders):
    return feeders.get(key) == {key}


def lands_only_in_itself(key, landings):
    return landings.get(key, set()) <= {key}


def group_fate(old, source, origins):
    """Strict continuation: an old group continues only into the new group with
    its key and UUID that receives all of its surviving occurrences, at least
    one, and none from another old group. Order within a group may change."""
    feeders, landings = {}, {}
    for o in origins:
        feeders.setdefault(o.new.group, set()).add(o.old.group)
        landings.setdefault(o.old.group, set()).add(o.new.group)
    continuing = frozenset(
        key
        for key in old.mention_groups
        if key in source.mention_groups
        and same_identity(old, source, key)
        and fed_only_by_itself(key, feeders)
        and lands_only_in_itself(key, landings)
    )
    return GroupFate(
        continuing=continuing,
        retired=frozenset(old.mention_groups) - continuing,
        fresh=frozenset(source.mention_groups) - continuing,
    )


def check_fresh_keys(old, fresh):
    if fresh & set(old.mention_groups):
        raise IntentError(
            "fresh_key_reused", "A fresh group needs a key that no old group used"
        )


def check_unused_entity_ids(old, source, fresh):
    for key in fresh:
        if source.mention_groups[key].entity_id in old.entity_constructions:
            raise IntentError(
                "fresh_uuid_reused", "A fresh group requires a fresh Entity UUID"
            )


def check_revision_scoped_ids(old, source, fresh):
    """A fresh group's UUID is derived from its source, new revision and key.

    The record store advances one revision per step and refuses a changed
    description at a used revision, so no (source, revision, key) repeats and a
    retired key that returns gets a different UUID.
    """
    for key in fresh:
        entity_id = source.mention_groups[key].entity_id
        if entity_id != fresh_mention_id(old.identity_data_id, source.revision, key):
            raise IntentError(
                "fresh_uuid_not_derived",
                "A fresh group's Entity UUID derives from its source, revision and group key",
            )


def resolutions_of(description, groups):
    return {
        k: r
        for k, r in description.mention_resolutions.items()
        if r.group_ref in groups
    }


def check_continuing_resolutions(old, source, fate):
    """A continuing group keeps its resolution record: the same key, for the
    same group."""
    previous = resolutions_of(old, fate.continuing)
    current = resolutions_of(source, fate.continuing)
    if {k: r.group_ref for k, r in previous.items()} != {
        k: r.group_ref for k, r in current.items()
    }:
        raise IntentError(
            "continuing_resolution_changed",
            "A continuing group keeps its resolution record",
        )


def check_continuing_decisions(old, source, fate):
    """With changed text a continuing group keeps its reviewed decision,
    because a changed meaning in a text edit is a fresh group. With unchanged
    text the decision may change in place, so `admit` skips this rule."""
    previous = resolutions_of(old, fate.continuing)
    current = resolutions_of(source, fate.continuing)
    if reviewed_decisions(current) != reviewed_decisions(previous):
        raise IntentError(
            "continuing_decision_changed",
            "A continuing group keeps its reviewed decision when the text changes",
        )


def check_fresh_resolution_ids(old, source, fate):
    used = set(old.mention_resolutions) | set(old.variant_assignments)
    if set(resolutions_of(source, fate.fresh)) & used:
        raise IntentError(
            "not_admitted",
            "A fresh resolution needs an ID no old resolution or assignment used",
        )


def check_one_resolution_per_fresh_group(source, fate):
    # The model allows at most one resolution per group, so this needs at least one.
    declared = {r.group_ref for r in resolutions_of(source, fate.fresh).values()}
    if declared != fate.fresh:
        raise IntentError(
            "not_admitted", "Declare exactly one resolution per fresh group"
        )


def check_mention_recipes(old, source, fate):
    """Mention recipes are the old ones, minus the retired groups', plus the
    fresh groups'. The model supplies each fresh group's recipe, and the fresh
    UUID rules keep it distinct, so this checks the continuing and retired."""
    for key in fate.continuing:
        eid = old.mention_groups[key].entity_id
        if source.entity_constructions[eid] != old.entity_constructions[eid]:
            raise IntentError(
                "mention_recipe_changed",
                "A continuing group keeps its mention recipe",
            )
    for key in fate.retired:
        if old.mention_groups[key].entity_id in source.entity_constructions:
            raise IntentError(
                "mention_recipe_changed",
                "A retired group's mention recipe is dropped",
            )


def check_reusable_recipes(old, source):
    """A reusable recipe may be added or dropped in any edit; a retained one is
    unchanged."""
    previous, current = reusable_recipes(old), reusable_recipes(source)
    if any(current[eid] != previous[eid] for eid in set(previous) & set(current)):
        raise IntentError(
            "reusable_recipe_changed", "A retained reusable recipe stays unchanged"
        )


def new_reusable_ids(old, source):
    """Reusable Entities this revision creates: added recipes that no listed
    corpus input names as an existing Entity."""
    return (
        set(reusable_recipes(source))
        - set(old.entity_constructions)
        - referenced_corpus_ids(source)
    )


def check_derived_entity_ids(old, source):
    """A new reusable Entity's UUID derives from the source, the new revision
    and the key of a resolution or variant that names it."""
    for eid in new_reusable_ids(old, source):
        derived = {
            fresh_entity_id(old.identity_data_id, source.revision, k)
            for k in naming_keys(source, eid)
        }
        if eid not in derived:
            raise IntentError(
                "entity_uuid_not_derived",
                "A new reusable Entity's UUID derives from its source, revision and the key of a resolution or variant that names it",
            )


FIXED_SCOPES = frozenset({"corpus", "text_spans"})


def scoped_variants(description, kinds):
    return {
        k: v
        for k, v in description.variant_assignments.items()
        if v.applicability.kind in kinds
    }


def check_scoped_variants(old, source, removal=None):
    """Document-scoped variants may be added, dropped or retargeted. Corpus-
    and span-scoped ones reach beyond this edit, so they stay unchanged,
    except that an erasure removal drops one citing what the forget removed
    (`check_erasure_removals` then requires the drop)."""
    erased = removal.citing if removal else set()
    kept = {
        k: v for k, v in scoped_variants(old, FIXED_SCOPES).items() if k not in erased
    }
    if reviewed_decisions(scoped_variants(source, FIXED_SCOPES)) != (
        reviewed_decisions(kept)
    ):
        raise IntentError(
            "variant_changed",
            "Corpus- and span-scoped variant assignments stay unchanged",
        )


def check_new_variant_keys(old, source):
    added = set(source.variant_assignments) - set(old.variant_assignments)
    if added & set(old.mention_resolutions):
        raise IntentError(
            "variant_key_reused", "A new variant key is not an old resolution key"
        )


RANGE = frozenset({"start", "end"})


def without_range(item):
    return {k: v for k, v in item.model_dump(mode="json").items() if k not in RANGE}


def check_foreign_inputs(old, source):
    """Another document's input, a corpus object or another source's saved
    record that both descriptions hold under one key keeps its kind,
    document and digest, and a saved record its pinned revision. Only a
    span's range may change, with its digest unchanged: a pure move. A
    changed input takes a new key; an uncited key may be dropped."""
    for key in set(old.inputs) & set(source.inputs):
        if not (is_foreign(old, key) or is_foreign(source, key)):
            continue
        if without_range(old.inputs[key]) != without_range(source.inputs[key]):
            raise IntentError(
                "foreign_input_changed",
                "Another document's input keeps its kind, document and digest; only a span may move",
            )


def foreign_citations(description):
    """The foreign input keys each decision cites, its group's included."""
    return {
        key: frozenset(k for k in inputs if is_foreign(description, k))
        for key, inputs in record_inputs(description).items()
    }


def attested_inputs(description):
    """The foreign input keys each producer's decisions cite."""
    cited = foreign_citations(description)
    seen = defaultdict(set)
    for kind in ("mention_resolutions", "variant_assignments"):
        for key, decision in getattr(description, kind).items():
            seen[decision.producer_ref] |= cited[key]
    return seen


def check_reconfirmations(old, source):
    """Attestation is per producer and foreign input key. A foreign input
    keeps its content under its key (`check_foreign_inputs`), so a producer
    whose old decisions cited a key saw that content. A decision under a
    producer of the old revision, whatever its key and whether or not it
    changed, cites only foreign keys that producer's old decisions cited. A
    continuing decision that keeps its reviewed fields but changes its
    foreign inputs in any way also names a producer new in this revision: a
    dropped input releases a withholding. A producer new
    in this revision is unconstrained, and a pure move keeps its key and
    passes both."""
    before, after = foreign_citations(old), foreign_citations(source)
    seen = attested_inputs(old)
    for kind in ("mention_resolutions", "variant_assignments"):
        was, now = getattr(old, kind), getattr(source, kind)
        for key, decision in now.items():
            if decision.producer_ref not in old.producers:
                continue
            unattested = after[key] - seen[decision.producer_ref]
            recited = (
                key in was
                and before[key] != after[key]
                and reviewed_decisions({key: decision})
                == reviewed_decisions({key: was[key]})
            )
            if unattested or recited:
                raise IntentError(
                    "reconfirm_unattested",
                    "A decision that cites other foreign inputs names a producer new in this revision",
                )


def check_no_span_variants(source):
    if any(
        v.applicability.kind == "text_spans"
        for v in source.variant_assignments.values()
    ):
        raise IntentError(
            "span_variant_in_text_edit",
            "Span-scoped variants require explicit scope remapping",
        )


async def check_absent_from_graph(graph, old, source, fate):
    """On a first attempt, no UUID this revision introduces is a graph node yet."""
    probes = [
        (
            source.mention_groups[key].entity_id,
            "fresh_uuid_in_graph",
            "New mention Entity UUID already exists in the graph",
        )
        for key in sorted(fate.fresh)
    ] + [
        (
            eid,
            "entity_uuid_in_graph",
            "New reusable Entity UUID already exists in the graph",
        )
        for eid in sorted(new_reusable_ids(old, source))
    ]
    for entity_id, code, message in probes:
        if await graph.get_node(str(entity_id)) is not None:
            raise IntentError(code, message)


def mention_ids(saved) -> set:
    """Every mention UUID of these saved descriptions and tombstones: each
    group's Entity, and a tombstone's of every forgotten life."""
    return {entity_id for each in saved for entity_id in uses_of(each)[0]}


def check_mention_inputs(source, mentions):
    """Invariant: a corpus input names a reusable Entity, never a mention
    group's. A mention UUID is document-local and fresh at its declaration,
    and a retiring or regrouping edit removes it with no review of its
    readers. A source that depends on another source's mention cites that
    mention's resolution as a saved record instead, which withholding and
    erasure follow. `mentions` are the mention UUIDs of every saved source,
    this one included (`mention_ids`). Run by every admission of a
    publication (Publisher.admit_inputs), so no reader of a mention UUID is
    ever saved."""
    for key, item in sorted(source.inputs.items()):
        if isinstance(item, CorpusObjectInput) and item.entity_id in mentions:
            raise IntentError(
                "mention_input",
                f"A corpus input names a mention group's Entity: {key}; "
                "cite its resolution as a saved record instead",
            )


async def check_corpus_inputs_exist(graph, source):
    """Every corpus input the description cites, a group's included, names
    an Entity in the graph. `referenced_corpus_ids` relies on this, so a
    listed input cannot exempt an Entity this revision constructs from the
    derived-UUID rule. Only admission refuses; retrieval and publication
    verification withhold the decisions that read a removed Entity
    instead."""
    cited = {
        source.inputs[key].entity_id
        for key in cited_inputs(source)
        if isinstance(source.inputs[key], CorpusObjectInput)
    }
    for entity_id in sorted(cited, key=str):
        if await graph.get_node(str(entity_id)) is None:
            raise IntentError(
                "missing_reasoning_input", f"Corpus input missing: {entity_id}"
            )
