"""Bounded worlds of reviewed occurrence edits and an independent group-fate oracle.

A world names the old groups, which old occurrences survive, how many
occurrences are added, and how the new occurrences are grouped, keyed and
identified. `materialize` turns it into real old and new descriptions, texts
and maps; `oracle` decides it from the abstract world alone.
"""

import json
from dataclasses import dataclass
from itertools import combinations, permutations, product
from pathlib import Path
from typing import NamedTuple
from uuid import UUID, uuid5

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.validation import (
    fresh_entity_id,
    fresh_mention_id,
    text_digest,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "tests/fixtures/identity/cognee_identity_source_example.json"
)
HELIOS = "8b4bff50-907b-56b6-bc80-3b0a7018714a"
HC = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
OLD_SHAPES = ((1,), (2,), (3,), (1, 1), (2, 1), (1, 2), (1, 1, 1))
OLD_KEYS = ("g1", "g2", "g3")
FRESH_KEYS = ("n1", "n2", "n3", "n4")
# A new group's UUID is the one derived from its own key, an unrelated one, or
# an old group's UUID, named by that group's key.
DERIVED = "derived"
OTHER = "other"


class Old(NamedTuple):
    key: str
    index: int


class Added(NamedTuple):
    n: int


class NewGroup(NamedTuple):
    key: str
    uuid: str
    items: tuple


@dataclass(frozen=True)
class World:
    old: tuple[tuple[str, int], ...]
    additions: int
    new: tuple[NewGroup, ...]

    def old_occurrences(self):
        return [Old(k, i) for k, n in self.old for i in range(n)]


def set_partitions(items):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for partition in set_partitions(rest):
        yield [[first], *partition]
        for i in range(len(partition)):
            yield [*partition[:i], [first, *partition[i]], *partition[i + 1 :]]


def worlds(shapes=OLD_SHAPES, max_additions=1):
    for shape in shapes:
        old = tuple(zip(OLD_KEYS, shape))
        occurrences = World(old, 0, ()).old_occurrences()
        for size in range(len(occurrences) + 1):
            for survivors in combinations(occurrences, size):
                for additions in range(max_additions + 1):
                    items = [*survivors, *map(Added, range(additions))]
                    for partition in set_partitions(items):
                        yield from labelings(old, additions, partition)


def text_order(item):
    return (isinstance(item, Added), item)


def labelings(old, additions, partition):
    old_keys = [k for k, _ in old]
    groups = [tuple(sorted(g, key=text_order)) for g in partition]
    for keys in permutations(old_keys + list(FRESH_KEYS[: len(groups)]), len(groups)):
        for uuids in product([DERIVED, OTHER, *old_keys], repeat=len(groups)):
            borrowed = [u for u in uuids if u in old_keys]
            if len(set(borrowed)) == len(borrowed):
                yield World(old, additions, tuple(map(NewGroup, keys, uuids, groups)))


def oracle(world, first_attempt=True):
    """Decide a world from the group-fate rule alone.

    An old group continues only into the new group with its key and UUID that
    receives all of its surviving occurrences and none from another old group
    (strict: no peel-off, and nothing surviving means no continuation). Every
    other old group retires; every other new group is fresh and needs a key
    and UUID that no old group used. Only a first attempt also requires the
    fresh UUID to be the one derived from the group's key; a retry completes a
    saved plan.
    """
    old_keys = {k for k, _ in world.old}
    survivors = {
        k: {
            o.index
            for g in world.new
            for o in g.items
            if isinstance(o, Old) and o.key == k
        }
        for k in old_keys
    }
    continuing = set()
    for group in world.new:
        old_items = [o for o in group.items if isinstance(o, Old)]
        if (
            group.key in old_keys
            and group.uuid == group.key
            and {o.key for o in old_items} == {group.key}
            and {o.index for o in old_items} == survivors[group.key]
        ):
            continuing.add(group.key)
    fresh = [g for g in world.new if g.key not in continuing]
    reasons = set()
    for group in fresh:
        if group.key in old_keys:
            reasons.add("key")
        if group.uuid in old_keys:
            reasons.add("unused")
        if group.uuid == OTHER and first_attempt:
            reasons.add("derived")
    if reasons:
        return ("refuse", frozenset(reasons))
    return (
        "admit",
        frozenset(continuing),
        frozenset(old_keys - continuing),
        frozenset(g.key for g in fresh),
    )


def token(item, same_text):
    if same_text:
        return "it"
    return f"o{item.key}{item.index}" if isinstance(item, Old) else f"a{item.n}"


def layout(items, same_text, prefix=""):
    text, spans = prefix, {}
    for item in items:
        word = token(item, same_text)
        spans[item] = dict(start=len(text), end=len(text) + len(word), text=word)
        text += word + " "
    return text.rstrip() + "\n", spans


def base_payload():
    payload = json.loads(FIXTURE.read_text())
    payload["mention_groups"], payload["mention_resolutions"] = {}, {}
    payload["entity_constructions"] = {
        k: v for k, v in payload["entity_constructions"].items() if k in (HELIOS, HC)
    }
    return payload


def group(entity_id, occurrences):
    return dict(
        entity_id=str(entity_id),
        document_ref="doc01",
        occurrences=occurrences,
        chunk_refs=["chunk01"],
        input_refs=["doc01"],
        producer_ref="fixture",
    )


def resolution(key):
    return dict(
        group_ref=key,
        status="accepted",
        target_entity_id=HELIOS,
        input_refs=["doc01", "existing_A"],
        producer_ref="fixture",
    )


def describe(payload, text, revision):
    payload = json.loads(json.dumps(payload))
    payload["revision"] = revision
    payload["inputs"]["doc01"]["text_sha256"] = text_digest(text)
    payload["inputs"]["chunk01"].update(start=0, end=len(text))
    return payload


def stable(world):
    """Every old occurrence survives and nothing is added, so the same text can
    carry the new grouping."""
    kept = sum(len(g.items) for g in world.new)
    return world.additions == 0 and kept == len(world.old_occurrences())


def materialize(world, same_text=False, text_changed=True):
    """Real old and new descriptions as JSON payloads and models, both texts
    and the general map. With same_text, every occurrence has the same surface
    text. Without text_changed, a stable world keeps the old text as the new
    text, so only the grouping and decisions change."""
    if not text_changed and not stable(world):
        raise ValueError("only a stable world keeps its text")
    payload = base_payload()
    identity = UUID(payload["identity_data_id"])
    before, old_spans = layout(world.old_occurrences(), same_text)
    old_id = {k: fresh_mention_id(identity, 1, k) for k, _ in world.old}
    old = describe(payload, before, 1)
    for key, n in world.old:
        old["entity_constructions"][str(old_id[key])] = dict(name=key, description=key)
        old["mention_groups"][key] = group(
            old_id[key], [old_spans[Old(key, i)] for i in range(n)]
        )
        old["mention_resolutions"][f"r{key}"] = resolution(key)
    new_items = sorted((o for g in world.new for o in g.items), key=text_order)
    after, new_spans = layout(
        new_items, same_text, prefix="new " if text_changed else ""
    )
    new = describe(payload, after, 2)
    place = {}
    for key, uuid, items in world.new:
        entity_id = (
            fresh_mention_id(identity, 2, key)
            if uuid == DERIVED
            else uuid5(identity, f"other:{key}") if uuid == OTHER else old_id[uuid]
        )
        new["entity_constructions"][str(entity_id)] = dict(name=key, description=key)
        new["mention_groups"][key] = group(entity_id, [new_spans[o] for o in items])
        # A group that keeps its old key and UUID keeps its old resolution;
        # any other group declares one fresh resolution.
        rid = f"r{key}" if uuid == key else f"s{key}"
        new["mention_resolutions"][rid] = resolution(key)
        for index, o in enumerate(items):
            place[o] = [key, index]
    general = {key: [place.get(Old(key, i)) for i in range(n)] for key, n in world.old}
    return dict(
        old_payload=old,
        new_payload=new,
        old=IdentitySource.model_validate_json(json.dumps(old)),
        new=IdentitySource.model_validate_json(json.dumps(new)),
        before=before,
        after=after,
        general=general,
    )


# Decision choices layered on an admitted world. Each names the groups it
# needs, edits the old and new payloads, and states as data what the rules
# say on a first attempt and on a retry, with changed and with unchanged text.
ADMIT = "admit"
CORPUS = dict(kind="corpus")
DOCUMENT = dict(kind="document", document_ref="doc01")
SPANS = dict(kind="text_spans", document_ref="doc01", ranges=[dict(start=0, end=1)])


class Outcomes(NamedTuple):
    """ADMIT, or the refusal codes any of which may name the fault, with
    changed text and with unchanged text."""

    text_edit: object
    same_text: object


class Decision(NamedTuple):
    name: str
    rule: str
    needs: frozenset
    change: object
    first: Outcomes
    retry: Outcomes

    def expected(self, text_changed, first_attempt):
        outcomes = self.first if first_attempt else self.retry
        return outcomes.text_edit if text_changed else outcomes.same_text

    def attempt_sensitive(self):
        return self.retry != self.first


def refuse(*codes):
    return frozenset(codes)


def decision(name, rule, needs, change, *, text_edit, same_text, retry=None):
    """`retry` overrides the outcomes that differ on a retry, which completes
    a saved plan without the UUID derivation rules."""
    first = Outcomes(text_edit, same_text)
    return Decision(
        name, rule, frozenset(needs), change, first, first._replace(**(retry or {}))
    )


ADMITTED_ON_RETRY = dict(text_edit=ADMIT, same_text=ADMIT)


def derived(ctx, key):
    return str(fresh_entity_id(ctx["identity"], 2, key))


def other_entity(ctx):
    return str(uuid5(ctx["identity"], "other:entity"))


def add_recipe(payload, entity_id):
    payload["entity_constructions"][entity_id] = dict(name="new", description="new")


def retarget(payload, rid, entity_id):
    payload["mention_resolutions"][rid]["target_entity_id"] = entity_id


def variant(source_id, target_id, scope):
    return dict(
        status="accepted",
        source_entity_id=source_id,
        target_entity_id=target_id,
        applicability=scope,
        input_refs=["doc01"],
        producer_ref="fixture",
    )


def continuing_rid(ctx):
    return f"r{ctx['continuing']}"


def fresh_rid(ctx):
    return f"s{ctx['fresh']}"


def unresolve(old, new, ctx):
    new["mention_resolutions"][continuing_rid(ctx)] = dict(
        group_ref=ctx["continuing"],
        status="unresolved",
        input_refs=["doc01"],
        producer_ref="fixture",
    )


def retarget_continuing_to_derived(old, new, ctx):
    entity_id = derived(ctx, continuing_rid(ctx))
    add_recipe(new, entity_id)
    retarget(new, continuing_rid(ctx), entity_id)


def retarget_continuing_to_underived(old, new, ctx):
    add_recipe(new, other_entity(ctx))
    retarget(new, continuing_rid(ctx), other_entity(ctx))


def retarget_continuing_to_hc(old, new, ctx):
    retarget(new, continuing_rid(ctx), HC)


def rename_continuing_resolution(old, new, ctx):
    new["mention_resolutions"][f"t{ctx['continuing']}"] = new[
        "mention_resolutions"
    ].pop(continuing_rid(ctx))


def change_continuing_recipe(old, new, ctx):
    entity_id = new["mention_groups"][ctx["continuing"]]["entity_id"]
    new["entity_constructions"][entity_id]["name"] = "changed"


def keep_retired_recipe(old, new, ctx):
    add_recipe(new, old["mention_groups"][ctx["retired"]]["entity_id"])


def drop_unused_reusable(old, new, ctx):
    add_recipe(old, str(uuid5(ctx["identity"], "spare")))


def change_retained_reusable(old, new, ctx):
    new["entity_constructions"][HELIOS]["name"] = "changed"


def add_unreferenced_recipe(old, new, ctx):
    add_recipe(new, other_entity(ctx))


def add_corpus_entity(old, new, ctx, *, referenced):
    """A corpus input names a new reusable Entity. Only an input that the
    variant lists in its input_refs reaches validate_inputs, which proves the
    Entity exists in the graph with the recorded hash."""
    entity_id = str(uuid5(ctx["identity"], "corpus:entity"))
    add_recipe(new, entity_id)
    new["inputs"]["existing_Z"] = dict(new["inputs"]["existing_A"], entity_id=entity_id)
    new["variant_assignments"]["v02"] = variant(HC, entity_id, DOCUMENT)
    if referenced:
        new["variant_assignments"]["v02"]["input_refs"].append("existing_Z")
        attest(new, "v02")


def add_corpus_referenced_entity(old, new, ctx):
    add_corpus_entity(old, new, ctx, referenced=True)


def add_corpus_decoy_entity(old, new, ctx):
    add_corpus_entity(old, new, ctx, referenced=False)


def resolve_fresh_to_derived(old, new, ctx):
    entity_id = derived(ctx, fresh_rid(ctx))
    add_recipe(new, entity_id)
    retarget(new, fresh_rid(ctx), entity_id)


def resolve_fresh_to_underived(old, new, ctx):
    add_recipe(new, other_entity(ctx))
    retarget(new, fresh_rid(ctx), other_entity(ctx))


def derive_from_a_key_that_does_not_name_it(old, new, ctx):
    entity_id = derived(ctx, "zz")
    add_recipe(new, entity_id)
    new["variant_assignments"]["v01"]["target_entity_id"] = entity_id


def retarget_document_variant(old, new, ctx):
    entity_id = derived(ctx, "v01")
    add_recipe(new, entity_id)
    new["variant_assignments"]["v01"]["target_entity_id"] = entity_id


def drop_document_variant(old, new, ctx):
    new["variant_assignments"].pop("v01")


def add_document_variant(old, new, ctx):
    new["variant_assignments"]["v02"] = variant(HELIOS, HC, DOCUMENT)


def add_variant_under_old_resolution_key(old, new, ctx):
    new["variant_assignments"][f"r{ctx['retired']}"] = variant(HELIOS, HC, DOCUMENT)


def scope_both(scope):
    def change(old, new, ctx):
        for payload in (old, new):
            payload["variant_assignments"]["v01"]["applicability"] = scope

    return change


def retarget_corpus_variant(old, new, ctx):
    scope_both(CORPUS)(old, new, ctx)
    retarget_document_variant(old, new, ctx)


def drop_corpus_variant(old, new, ctx):
    scope_both(CORPUS)(old, new, ctx)
    drop_document_variant(old, new, ctx)


def add_corpus_variant(old, new, ctx):
    new["variant_assignments"]["v02"] = variant(HELIOS, HC, CORPUS)


def rescope_variant_to_corpus(old, new, ctx):
    new["variant_assignments"]["v01"]["applicability"] = CORPUS


def retarget_span_variant(old, new, ctx):
    scope_both(SPANS)(old, new, ctx)
    retarget_document_variant(old, new, ctx)


GLOSSARY_TEXT = "HC: Helios controller.\n"
GLOSSARY_ENTRY = "HC: Helios controller."


def add_glossary(payload, key="gloss", *, dataset=None, data_id=None):
    """Another document of the dataset, as a text input."""
    payload["inputs"][key] = dict(
        kind="source_text",
        dataset_id=dataset or payload["dataset_id"],
        data_id=data_id or str(uuid5(UUID(payload["dataset_id"]), key)),
        text_sha256=text_digest(GLOSSARY_TEXT),
    )


def glossary_span(
    payload, key="gloss_hc", *, start=0, entry=GLOSSARY_ENTRY, document="gloss"
):
    payload["inputs"][key] = dict(
        kind="text_span",
        document_ref=document,
        start=start,
        end=start + len(entry),
        text_sha256=text_digest(entry),
    )


def cite(payload, record, key):
    payload["variant_assignments"].get(
        record, payload["mention_resolutions"].get(record)
    )["input_refs"] = ["doc01", key]


def v01_reads_glossary(old, new, ctx):
    for payload in (old, new):
        add_glossary(payload)
        glossary_span(payload)
        cite(payload, "v01", "gloss_hc")


def move_foreign_span(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    glossary_span(new, start=7)


def change_foreign_span(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    glossary_span(new, entry="HC: Helios regulator.")


def move_foreign_span_to_another_document(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    add_glossary(new, "gloss2")
    glossary_span(new, document="gloss2")


def change_foreign_text(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    new["inputs"]["gloss"]["text_sha256"] = text_digest("changed\n")


def change_corpus_input(old, new, ctx):
    new["inputs"]["existing_A"]["content_sha256"] = text_digest("changed")


def reconfirm(record, *, producer):
    def change(old, new, ctx):
        for payload in (old, new):
            add_glossary(payload)
            glossary_span(payload)
        rid = record(ctx) if callable(record) else record
        cite(old, rid, "gloss_hc")
        new["inputs"].pop("gloss_hc")
        glossary_span(new, "gloss_hc_r2", entry="HC: Helios regulator.")
        cite(new, rid, "gloss_hc_r2")
        if producer:
            attest(new, rid)

    return change


def attest(payload, rid):
    """The decision names a producer new in this revision: a re-confirm."""
    payload["producers"]["reconfirm"] = dict(
        payload["producers"]["fixture"], implementation="re-confirmed"
    )
    target = (
        payload["variant_assignments"].get(rid) or payload["mention_resolutions"][rid]
    )
    target["producer_ref"] = "reconfirm"


def drop_foreign_input(*, producer):
    """The continuing resolution and its group read the glossary entry; the
    new revision drops that input from both, reviewed fields unchanged."""

    def change(old, new, ctx):
        rid, group = continuing_rid(ctx), ctx["continuing"]
        add_glossary(old)
        glossary_span(old)
        old["mention_resolutions"][rid]["input_refs"].append("gloss_hc")
        old["mention_groups"][group]["input_refs"].append("gloss_hc")
        if producer:
            attest(new, rid)

    return change


def move_group_to_new_input(*, producer):
    """Only the continuing group reads the glossary entry; the new revision
    points the group at a new input key, the resolution unchanged."""

    def change(old, new, ctx):
        group = ctx["continuing"]
        for payload in (old, new):
            add_glossary(payload)
        glossary_span(old)
        old["mention_groups"][group]["input_refs"].append("gloss_hc")
        glossary_span(new, "gloss_hc_r2", entry="HC: Helios regulator.")
        new["mention_groups"][group]["input_refs"].append("gloss_hc_r2")
        if producer:
            attest(new, continuing_rid(ctx))

    return change


def add_variant_reading_new_span(*, producer):
    def change(old, new, ctx):
        add_glossary(new)
        glossary_span(new)
        new["variant_assignments"]["v02"] = variant(HELIOS, HC, DOCUMENT)
        cite(new, "v02", "gloss_hc")
        if producer:
            attest(new, "v02")

    return change


def rename_variant_onto_new_span(*, producer):
    """v01 reads the glossary entry; the new revision renames it v01b and
    points it at the changed entry under a new key."""

    def change(old, new, ctx):
        reconfirm("v01", producer=False)(old, new, ctx)
        new["variant_assignments"]["v01b"] = new["variant_assignments"].pop("v01")
        if producer:
            attest(new, "v01b")

    return change


def retarget_resolution_onto_new_span(*, producer):
    """The continuing resolution reads the glossary entry; the new revision
    retargets it and points it at the changed entry under a new key."""

    def change(old, new, ctx):
        reconfirm(continuing_rid, producer=producer)(old, new, ctx)
        retarget_continuing_to_hc(old, new, ctx)

    return change


def add_text_of_another_dataset(old, new, ctx):
    add_glossary(new, dataset=str(uuid5(UUID(new["dataset_id"]), "other")))


def add_second_own_text(old, new, ctx):
    add_glossary(new, data_id=new["inputs"]["doc01"]["data_id"])


def add_saved_record(old, new, ctx):
    new["inputs"]["record"] = dict(
        kind="saved_record",
        dataset_id=new["dataset_id"],
        identity_data_id=new["identity_data_id"],
        record_id="r1",
        representation_revision=1,
        content_sha256=text_digest("record"),
    )


CONTINUING, RETIRED, FRESH = "continuing", "retired", "fresh"
NO_SPAN_VARIANT = refuse("span_variant_in_text_edit")
UNDERIVED = refuse("entity_uuid_not_derived")
# `rule` numbers the unified admission rules: 1 continuing decisions,
# 2 mention recipes, 3 reusable recipes, 4 variants, 5 other documents'
# inputs. A row that lists two codes for one outcome is refused by whichever
# rule `admit` applies first.
DECISIONS = [
    decision(
        "continuing group unresolved",
        "rule 1",
        [CONTINUING],
        unresolve,
        text_edit=refuse("continuing_decision_changed"),
        same_text=ADMIT,
    ),
    decision(
        "continuing group retargeted to a derived new Entity",
        "rules 1 and 3",
        [CONTINUING],
        retarget_continuing_to_derived,
        text_edit=refuse("continuing_decision_changed"),
        same_text=ADMIT,
    ),
    decision(
        "continuing group retargeted to an underived new Entity",
        "rules 1 and 3",
        [CONTINUING],
        retarget_continuing_to_underived,
        text_edit=refuse("continuing_decision_changed", "entity_uuid_not_derived"),
        same_text=UNDERIVED,
        retry=dict(same_text=ADMIT),
    ),
    decision(
        "continuing group retargeted to a declared Entity",
        "rule 1",
        [CONTINUING],
        retarget_continuing_to_hc,
        text_edit=refuse("continuing_decision_changed"),
        same_text=ADMIT,
    ),
    decision(
        "continuing resolution renamed",
        "rule 1",
        [CONTINUING],
        rename_continuing_resolution,
        text_edit=refuse("continuing_resolution_changed"),
        same_text=refuse("continuing_resolution_changed"),
    ),
    decision(
        "continuing mention recipe changed",
        "rule 2",
        [CONTINUING],
        change_continuing_recipe,
        text_edit=refuse("mention_recipe_changed"),
        same_text=refuse("mention_recipe_changed"),
    ),
    decision(
        "retired mention recipe kept",
        "rule 2",
        [RETIRED],
        keep_retired_recipe,
        text_edit=refuse("mention_recipe_changed"),
        same_text=refuse("mention_recipe_changed"),
    ),
    decision(
        "unused reusable recipe dropped",
        "rule 3",
        [],
        drop_unused_reusable,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "retained reusable recipe changed",
        "rule 3",
        [],
        change_retained_reusable,
        text_edit=refuse("reusable_recipe_changed"),
        same_text=refuse("reusable_recipe_changed"),
    ),
    decision(
        "new recipe that nothing names",
        "rule 3",
        [],
        add_unreferenced_recipe,
        text_edit=UNDERIVED,
        same_text=UNDERIVED,
        retry=ADMITTED_ON_RETRY,
    ),
    decision(
        "new Entity named by a corpus input",
        "rule 3",
        [],
        add_corpus_referenced_entity,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "new Entity named by a corpus input that nothing lists",
        "rule 3",
        [],
        add_corpus_decoy_entity,
        text_edit=UNDERIVED,
        same_text=UNDERIVED,
        retry=ADMITTED_ON_RETRY,
    ),
    decision(
        "fresh group resolved to a derived new Entity",
        "rule 3",
        [FRESH],
        resolve_fresh_to_derived,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "fresh group resolved to an underived new Entity",
        "rule 3",
        [FRESH],
        resolve_fresh_to_underived,
        text_edit=UNDERIVED,
        same_text=UNDERIVED,
        retry=ADMITTED_ON_RETRY,
    ),
    decision(
        "new Entity derived from a key that does not name it",
        "rule 3",
        [],
        derive_from_a_key_that_does_not_name_it,
        text_edit=UNDERIVED,
        same_text=UNDERIVED,
        retry=ADMITTED_ON_RETRY,
    ),
    decision(
        "document variant retargeted",
        "rule 4",
        [],
        retarget_document_variant,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "document variant dropped",
        "rule 4",
        [],
        drop_document_variant,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "document variant added",
        "rule 4",
        [],
        add_document_variant,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "document variant added under an old resolution key",
        "rule 4",
        [RETIRED],
        add_variant_under_old_resolution_key,
        text_edit=refuse("variant_key_reused"),
        same_text=refuse("variant_key_reused"),
    ),
    decision(
        "corpus variant retargeted",
        "rule 4",
        [],
        retarget_corpus_variant,
        text_edit=refuse("variant_changed"),
        same_text=refuse("variant_changed"),
    ),
    decision(
        "corpus variant dropped",
        "rule 4",
        [],
        drop_corpus_variant,
        text_edit=refuse("variant_changed"),
        same_text=refuse("variant_changed"),
    ),
    decision(
        "corpus variant added",
        "rule 4",
        [],
        add_corpus_variant,
        text_edit=refuse("variant_changed"),
        same_text=refuse("variant_changed"),
    ),
    decision(
        "variant rescoped to the corpus",
        "rule 4",
        [],
        rescope_variant_to_corpus,
        text_edit=refuse("variant_changed"),
        same_text=refuse("variant_changed"),
    ),
    decision(
        "span variant unchanged",
        "rule 4",
        [],
        scope_both(SPANS),
        text_edit=NO_SPAN_VARIANT,
        same_text=ADMIT,
    ),
    decision(
        "span variant retargeted",
        "rule 4",
        [],
        retarget_span_variant,
        text_edit=refuse("variant_changed", "span_variant_in_text_edit"),
        same_text=refuse("variant_changed"),
    ),
    decision(
        "foreign span moved with its digest unchanged",
        "rule 5",
        [],
        move_foreign_span,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "foreign span changed under its old key",
        "rule 5",
        [],
        change_foreign_span,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "foreign span moved to another document under its old key",
        "rule 5",
        [],
        move_foreign_span_to_another_document,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "foreign text changed under its old key",
        "rule 5",
        [],
        change_foreign_text,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "corpus input changed under its old key",
        "rule 5",
        [],
        change_corpus_input,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "variant re-confirmed on a new span under a new producer",
        "rule 5",
        [],
        reconfirm("v01", producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "variant cites a new span under its old producer",
        "rule 5",
        [],
        reconfirm("v01", producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution re-confirmed on a new span under a new producer",
        "rule 5",
        [CONTINUING],
        reconfirm(continuing_rid, producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "continuing resolution cites a new span under its old producer",
        "rule 5",
        [CONTINUING],
        reconfirm(continuing_rid, producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution drops a foreign input under its old producer",
        "rule 5",
        [CONTINUING],
        drop_foreign_input(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution drops a foreign input under a new producer",
        "rule 5",
        [CONTINUING],
        drop_foreign_input(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "continuing group moves to a new foreign input under its old producer",
        "rule 5",
        [CONTINUING],
        move_group_to_new_input(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing group moves to a new foreign input under a new producer",
        "rule 5",
        [CONTINUING],
        move_group_to_new_input(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "new variant reads a new span under its old producer",
        "rule 5",
        [],
        add_variant_reading_new_span(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "new variant reads a new span under a new producer",
        "rule 5",
        [],
        add_variant_reading_new_span(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "document variant renamed onto a new span under its old producer",
        "rule 5",
        [],
        rename_variant_onto_new_span(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "document variant renamed onto a new span under a new producer",
        "rule 5",
        [],
        rename_variant_onto_new_span(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "continuing resolution retargeted onto a new span under its old producer",
        "rule 5",
        [CONTINUING],
        retarget_resolution_onto_new_span(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution retargeted onto a new span under a new producer",
        "rule 5",
        [CONTINUING],
        retarget_resolution_onto_new_span(producer=True),
        text_edit=refuse("continuing_decision_changed"),
        same_text=ADMIT,
    ),
    decision(
        "text of another dataset",
        "rule 5",
        [],
        add_text_of_another_dataset,
        text_edit=refuse("not_admitted"),
        same_text=refuse("not_admitted"),
    ),
    decision(
        "second text of the own document",
        "rule 5",
        [],
        add_second_own_text,
        text_edit=refuse("not_admitted"),
        same_text=refuse("not_admitted"),
    ),
    decision(
        "saved-record input",
        "rule 5",
        [],
        add_saved_record,
        text_edit=refuse("not_admitted"),
        same_text=refuse("not_admitted"),
    ),
]
