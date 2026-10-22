"""Scratch breaks of the general admitter, one rule each.

Each mutant replaces one function in cognee_lab.identity.admission. The check
must find a small world that the broken admitter decides wrongly.
"""

from cognee_lab.identity import admission


def continue_with_any_uuid(old, source, key, origins):
    current = source.mention_groups.get(key)
    if current is None:
        return False
    sources = {o[0] for (k, _), o in origins.items() if k == key}
    survivors = {k for k, o in origins.items() if o[0] == key}
    return sources == {key} and all(k == key for k, _ in survivors)


def continue_after_merge(old, source, key, origins):
    current = source.mention_groups.get(key)
    if current is None or current.entity_id != old.mention_groups[key].entity_id:
        return False
    sources = {o[0] for (k, _), o in origins.items() if k == key}
    survivors = {k for k, o in origins.items() if o[0] == key}
    return key in sources and all(k == key for k, _ in survivors)


def continue_after_peel_off(old, source, key, origins):
    current = source.mention_groups.get(key)
    if current is None or current.entity_id != old.mention_groups[key].entity_id:
        return False
    sources = {o[0] for (k, _), o in origins.items() if k == key}
    return sources == {key}


def continue_without_survivor(old, source, key, origins):
    current = source.mention_groups.get(key)
    if current is None or current.entity_id != old.mention_groups[key].entity_id:
        return False
    sources = {o[0] for (k, _), o in origins.items() if k == key}
    survivors = {k for k, o in origins.items() if o[0] == key}
    return sources <= {key} and all(k == key for k, _ in survivors)


def skip(*_):
    return None


MUTANTS = {
    "continue_with_any_uuid": ("continues", continue_with_any_uuid),
    "continue_after_merge": ("continues", continue_after_merge),
    "continue_after_peel_off": ("continues", continue_after_peel_off),
    "continue_without_survivor": ("continues", continue_without_survivor),
    "reuse_old_keys": ("check_fresh_keys", skip),
    "reuse_old_uuids": ("check_unused_entity_ids", skip),
    "skip_derived_uuids": ("check_revision_scoped_ids", skip),
}
assert all(hasattr(admission, attribute) for attribute, _ in MUTANTS.values())
