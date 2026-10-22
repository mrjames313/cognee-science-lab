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
from cognee_lab.identity.validation import fresh_mention_id, text_digest

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


def materialize(world, same_text=False):
    """Real old and new descriptions as JSON payloads and models, both texts
    and the general map. With same_text, every occurrence has the same surface
    text."""
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
    after, new_spans = layout(new_items, same_text, prefix="new ")
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
