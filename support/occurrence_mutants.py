"""Scratch breaks of the general admitter, one rule each.

Each mutant replaces one function in cognee_lab.identity.admission. The check
must find a small world that the broken admitter decides wrongly.
"""

from cognee_lab.identity import admission


def skip(*_):
    return None


MUTANTS = {
    "continue_with_any_uuid": ("same_identity", lambda *_: True),
    "continue_after_merge": (
        "fed_only_by_itself",
        lambda key, feeders: key in feeders.get(key, set()),
    ),
    "continue_without_survivor": (
        "fed_only_by_itself",
        lambda key, feeders: feeders.get(key, set()) <= {key},
    ),
    "continue_after_peel_off": ("lands_only_in_itself", lambda *_: True),
    "reuse_old_keys": ("check_fresh_keys", skip),
    "reuse_old_uuids": ("check_unused_entity_ids", skip),
    "skip_derived_uuids": ("check_revision_scoped_ids", skip),
    "allow_two_origins": ("check_single_origin", skip),
    "allow_missing_targets": ("check_targets_exist", skip),
    "allow_changed_text": ("check_same_text", skip),
    "skip_old_slices": ("check_old_slices", skip),
    "skip_new_slices": ("check_new_slices", skip),
    "skip_revision_step": ("check_next_revision", skip),
    "allow_unchanged_text": ("check_changed_text", skip),
    "allow_changed_decisions": ("check_continuing_decisions", skip),
    "allow_changed_variants": ("check_variants_unchanged", skip),
    "allow_reused_resolution_ids": ("check_fresh_resolution_ids", skip),
    "allow_unresolved_fresh_groups": ("check_one_resolution_per_fresh_group", skip),
    "allow_changed_recipes": ("check_recipes", skip),
    "allow_span_variants": ("check_no_span_variants", skip),
}
assert all(hasattr(admission, attribute) for attribute, _ in MUTANTS.values())
