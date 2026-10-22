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
    reusable = (HELIOS, payload["variant_assignments"]["v01"]["source_entity_id"])
    payload["entity_constructions"] = {
        k: v for k, v in payload["entity_constructions"].items() if k in reusable
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
# needs, edits the old and new payloads, and states the outcome the rules
# give it from whether the text changed and whether this is a first attempt.
ADMIT = "admit"
HC = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
CORPUS = dict(kind="corpus")
DOCUMENT = dict(kind="document", document_ref="doc01")
SPANS = dict(kind="text_spans", document_ref="doc01", ranges=[dict(start=0, end=1)])


class Decision(NamedTuple):
    name: str
    needs: frozenset
    change: object
    expected: object

    def attempt_sensitive(self):
        return any(
            self.expected(text_changed, True) != self.expected(text_changed, False)
            for text_changed in (True, False)
        )


def admit_always(text_changed, first_attempt):
    return ADMIT


def always(*codes):
    return lambda text_changed, first_attempt: frozenset(codes)


def unless_unchanged_text(*codes):
    return lambda text_changed, first_attempt: (
        frozenset(codes) if text_changed else ADMIT
    )


def first_attempt_only(*codes):
    return lambda text_changed, first_attempt: (
        frozenset(codes) if first_attempt else ADMIT
    )


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


def underived_unless_text_edit(text_changed, first_attempt):
    # With changed text the derivation rule refuses first on a first attempt
    # and the decision rule on a retry; either names a real fault.
    if text_changed:
        return frozenset({"continuing_decision_changed", "entity_uuid_not_derived"})
    return frozenset({"entity_uuid_not_derived"}) if first_attempt else ADMIT


CONTINUING, RETIRED, FRESH = "continuing", "retired", "fresh"
DECISIONS = [
    Decision(name, frozenset(needs), change, expected)
    for name, needs, change, expected in [
        (
            "continuing group unresolved",
            [CONTINUING],
            unresolve,
            unless_unchanged_text("continuing_decision_changed"),
        ),
        (
            "continuing group retargeted to a derived new Entity",
            [CONTINUING],
            retarget_continuing_to_derived,
            unless_unchanged_text("continuing_decision_changed"),
        ),
        (
            "continuing group retargeted to an underived new Entity",
            [CONTINUING],
            retarget_continuing_to_underived,
            underived_unless_text_edit,
        ),
        (
            "continuing group retargeted to a declared Entity",
            [CONTINUING],
            retarget_continuing_to_hc,
            unless_unchanged_text("continuing_decision_changed"),
        ),
        (
            "continuing resolution renamed",
            [CONTINUING],
            rename_continuing_resolution,
            always("continuing_resolution_changed"),
        ),
        (
            "continuing mention recipe changed",
            [CONTINUING],
            change_continuing_recipe,
            always("mention_recipe_changed"),
        ),
        (
            "retired mention recipe kept",
            [RETIRED],
            keep_retired_recipe,
            always("mention_recipe_changed"),
        ),
        ("unused reusable recipe dropped", [], drop_unused_reusable, admit_always),
        (
            "retained reusable recipe changed",
            [],
            change_retained_reusable,
            always("reusable_recipe_changed"),
        ),
        (
            "new recipe that nothing names",
            [],
            add_unreferenced_recipe,
            first_attempt_only("entity_uuid_not_derived"),
        ),
        (
            "new Entity named by a corpus input",
            [],
            add_corpus_referenced_entity,
            admit_always,
        ),
        (
            "new Entity named by a corpus input that nothing lists",
            [],
            add_corpus_decoy_entity,
            first_attempt_only("entity_uuid_not_derived"),
        ),
        (
            "fresh group resolved to a derived new Entity",
            [FRESH],
            resolve_fresh_to_derived,
            admit_always,
        ),
        (
            "fresh group resolved to an underived new Entity",
            [FRESH],
            resolve_fresh_to_underived,
            first_attempt_only("entity_uuid_not_derived"),
        ),
        (
            "new Entity derived from a key that does not name it",
            [],
            derive_from_a_key_that_does_not_name_it,
            first_attempt_only("entity_uuid_not_derived"),
        ),
        ("document variant retargeted", [], retarget_document_variant, admit_always),
        ("document variant dropped", [], drop_document_variant, admit_always),
        ("document variant added", [], add_document_variant, admit_always),
        (
            "document variant added under an old resolution key",
            [RETIRED],
            add_variant_under_old_resolution_key,
            always("variant_key_reused"),
        ),
        (
            "corpus variant retargeted",
            [],
            retarget_corpus_variant,
            always("variant_changed"),
        ),
        ("corpus variant dropped", [], drop_corpus_variant, always("variant_changed")),
        ("corpus variant added", [], add_corpus_variant, always("variant_changed")),
        (
            "variant rescoped to the corpus",
            [],
            rescope_variant_to_corpus,
            always("variant_changed"),
        ),
        (
            "span variant unchanged",
            [],
            scope_both(SPANS),
            unless_unchanged_text("span_variant_in_text_edit"),
        ),
        (
            "span variant retargeted",
            [],
            retarget_span_variant,
            always("variant_changed", "span_variant_in_text_edit"),
        ),
    ]
]
