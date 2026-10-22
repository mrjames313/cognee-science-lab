"""Bounded worlds of reviewed occurrence edits and an independent group-fate oracle.

A world names the old groups, which old occurrences survive, how many
occurrences are added, and how the new occurrences are grouped, keyed and
identified. `materialize` turns it into real old and new descriptions, texts
and maps; `oracle` decides it from the abstract world alone.
"""

import json
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path
from uuid import UUID

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


@dataclass(frozen=True)
class World:
    """`old` is the occurrence count per old key. Each new group is
    (key, id_owner, items): id_owner is the old key whose Entity UUID the group
    carries, or None for the revision-scoped UUID derived from its own key.
    Items are ("old", key, index) or ("add", n), in new text order."""

    old: tuple[tuple[str, int], ...]
    additions: int
    new: tuple[tuple[str, str | None, tuple[tuple, ...]], ...]


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
        occurrences = [("old", k, i) for k, n in old for i in range(n)]
        old_keys = [k for k, _ in old]
        for size in range(len(occurrences) + 1):
            for survivors in combinations(occurrences, size):
                for additions in range(max_additions + 1):
                    items = [*survivors, *(("add", n) for n in range(additions))]
                    for partition in set_partitions(items):
                        yield from labelings(old, old_keys, additions, partition)


def labelings(old, old_keys, additions, partition):
    order = {
        item: i
        for i, item in enumerate(
            [("old", k, i) for k, n in old for i in range(n)]
            + [("add", n) for n in range(additions)]
        )
    }
    groups = [tuple(sorted(g, key=order.get)) for g in partition]
    keys = old_keys + list(FRESH_KEYS[: len(groups)])
    for chosen in product(keys, repeat=len(groups)):
        if len(set(chosen)) != len(chosen):
            continue
        # Also try every adversarial UUID: each group may carry any old
        # group's UUID or its own derived one, as long as UUIDs stay distinct.
        for ids in product([None, *old_keys], repeat=len(groups)):
            used = [i for i in ids if i is not None]
            if len(set(used)) != len(used):
                continue
            yield World(old, additions, tuple(zip(chosen, ids, groups)))


def oracle(world):
    """Decide a world from the group-fate rule alone.

    An old group continues only into the new group with its key and UUID that
    receives all of its surviving occurrences and none from another old group
    (strict: no peel-off, and nothing surviving means no continuation). Every
    other old group retires; every other new group is fresh and needs a key
    and UUID that no old group used.
    """
    old_keys = {k for k, _ in world.old}
    survivors = {
        k: {x[2] for _, _, items in world.new for x in items if x[:2] == ("old", k)}
        for k in old_keys
    }
    continuing = set()
    for key, owner, items in world.new:
        sources = {x[1] for x in items if x[0] == "old"}
        own = {x[2] for x in items if x[0] == "old" and x[1] == key}
        if (
            key in old_keys
            and owner == key
            and sources == {key}
            and own == survivors[key]
        ):
            continuing.add(key)
    fresh = {key for key, _, _ in world.new} - continuing
    for key, owner, _ in world.new:
        if key in fresh and key in old_keys:
            return ("refuse", "key")
        if key in fresh and owner is not None:
            return ("refuse", "uuid")
    return (
        "admit",
        frozenset(continuing),
        frozenset(old_keys - continuing),
        frozenset(fresh),
    )


def token(item):
    return f"o{item[1]}{item[2]}" if item[0] == "old" else f"a{item[1]}"


def layout(items, prefix=""):
    text, spans = prefix, {}
    for item in items:
        spans[item] = (len(text), len(text) + len(token(item)))
        text += token(item) + " "
    return text.rstrip() + "\n", spans


def base_payload():
    payload = json.loads(FIXTURE.read_text())
    payload["mention_groups"], payload["mention_resolutions"] = {}, {}
    payload["entity_constructions"] = {
        k: v
        for k, v in payload["entity_constructions"].items()
        if k in (HELIOS, payload["variant_assignments"]["v01"]["source_entity_id"])
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


def materialize(world):
    """Real old and new descriptions, both texts, the general map and the
    old-mode maps that can express the world (absent when none can)."""
    payload = base_payload()
    identity = UUID(payload["identity_data_id"])
    old_items = [("old", k, i) for k, n in world.old for i in range(n)]
    before, old_spans = layout(old_items)
    old_id = {k: fresh_mention_id(identity, 1, k) for k, _ in world.old}
    old = describe(payload, before, 1)
    for key, n in world.old:
        old["entity_constructions"][str(old_id[key])] = dict(name=key, description=key)
        old["mention_groups"][key] = group(
            old_id[key],
            [
                dict(start=a, end=b, text=token(("old", key, i)))
                for i in range(n)
                for a, b in [old_spans[("old", key, i)]]
            ],
        )
        old["mention_resolutions"][f"r{key}"] = resolution(key)
    new_items = sorted(
        (x for _, _, items in world.new for x in items),
        key=lambda x: (x[0] == "add", x[1:]),
    )
    after, new_spans = layout(new_items, prefix="new ")
    new = describe(payload, after, 2)
    place = {}
    for key, owner, items in world.new:
        entity_id = old_id[owner] if owner else fresh_mention_id(identity, 2, key)
        new["entity_constructions"][str(entity_id)] = dict(name=key, description=key)
        new["mention_groups"][key] = group(
            entity_id,
            [
                dict(start=a, end=b, text=token(x))
                for x in items
                for a, b in [new_spans[x]]
            ],
        )
        # A group that keeps its old key and UUID keeps its old resolution;
        # any other group declares one fresh resolution.
        rid = f"r{key}" if owner == key else f"s{key}"
        new["mention_resolutions"][rid] = resolution(key)
        for index, x in enumerate(items):
            place[x] = (key, index)
    general = {
        key: [
            list(place[("old", key, i)]) if ("old", key, i) in place else None
            for i in range(n)
        ]
        for key, n in world.old
    }
    return dict(
        old=IdentitySource.model_validate_json(json.dumps(old)),
        new=IdentitySource.model_validate_json(json.dumps(new)),
        before=before,
        after=after,
        general=general,
        modes=old_mode_maps(world, place),
    )


def old_mode_maps(world, place):
    old_keys = {k for k, _ in world.old}
    everyone = [("old", k, i) for k, n in world.old for i in range(n)]
    survived = [x for x in everyone if x in place]
    groups = {key: (owner, items) for key, owner, items in world.new}
    # Old-mode maps are keyed by group, so they can carry any UUID choice;
    # the admitter, not expressibility, judges the UUID.
    keeps_own = {
        key: key in groups and all(place[x][0] == key for x in survived if x[1] == key)
        for key in old_keys
    }
    modes = {}
    if len(survived) == len(everyone) and not world.additions:
        modes["regrouping"] = {
            key: [list(place[("old", key, i)]) for i in range(n)]
            for key, n in world.old
        }
        if (
            all(keeps_own[k] and len(groups[k][1]) == n for k, n in world.old)
            and set(groups) == old_keys
        ):
            modes["prefix"] = None
    if (
        not world.additions
        and all(
            key in old_keys and all(x[0] == "old" and x[1] == key for x in items)
            for key, _, items in world.new
        )
        and all(keeps_own[k] or not any(x[1] == k for x in survived) for k in old_keys)
    ):
        modes["retention"] = {
            key: [i for i in range(n) if ("old", key, i) in place]
            for key, n in world.old
        }
    if (
        len(survived) == len(everyone)
        and all(keeps_own[k] for k in old_keys)
        and all(
            all(x[0] == "add" for x in items)
            for key, _, items in world.new
            if key not in old_keys
        )
    ):
        modes["continuity"] = {
            key: [place[("old", key, i)][1] for i in range(n)] for key, n in world.old
        }
    return modes
