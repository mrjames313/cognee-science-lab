"""Scratch breaks of the general admitter, one rule each.

Each mutant replaces one function in cognee_lab.identity.admission, in the
erasure rules it imports (cognee_lab.identity.erasure_rules), or in the
citation scope that preflight checks first (cognee_lab.identity.chains).
The check must find a small world that the broken admitter decides wrongly.
"""

from uuid import UUID

from cognee_lab.identity import admission, chains, erasure_rules, validation
from cognee_lab.identity.models import SavedRecordInput
from cognee_lab.identity.records import saved_records


def skip(*_):
    return None


def own_foreign_refs(description):
    """Each decision's own foreign input_refs, without its group's."""
    return {
        key: frozenset(k for k in d.input_refs if admission.is_foreign(description, k))
        for key, d in [
            *description.mention_resolutions.items(),
            *description.variant_assignments.items(),
        ]
    }


def attest_continuing_keys_only(old, source):
    """The re-confirm rule checked only keys in both revisions, so a renamed,
    changed or new decision could cite a new foreign input unattested."""
    before = admission.foreign_citations(old)
    after = admission.foreign_citations(source)
    for kind in ("mention_resolutions", "variant_assignments"):
        was, now = getattr(old, kind), getattr(source, kind)
        for key in set(was) & set(now):
            if (
                before[key] != after[key]
                and admission.reviewed_decisions({key: now[key]})
                == admission.reviewed_decisions({key: was[key]})
                and now[key].producer_ref in old.producers
            ):
                raise admission.IntentError("reconfirm_unattested", "")


def attest_any_old_input(old, source):
    """The round-3 re-confirm rule let an old producer cite any foreign key
    the old revision held, so a renamed or changed decision could borrow a
    key a sibling's producer re-confirmed."""
    before = admission.foreign_citations(old)
    after = admission.foreign_citations(source)
    for kind in ("mention_resolutions", "variant_assignments"):
        was, now = getattr(old, kind), getattr(source, kind)
        for key, decision in now.items():
            if decision.producer_ref not in old.producers:
                continue
            unseen = after[key] - set(old.inputs)
            recited = (
                key in was
                and before[key] != after[key]
                and admission.reviewed_decisions({key: decision})
                == admission.reviewed_decisions({key: was[key]})
            )
            if unseen or recited:
                raise admission.IntentError("reconfirm_unattested", "")


def drop_scoped_variants_freely(old, source, removal=None):
    """Corpus- and span-scoped variants may be dropped without a removal
    producer; only a kept one must be unchanged."""
    kept = {
        k: v
        for k, v in admission.scoped_variants(old, admission.FIXED_SCOPES).items()
        if k in source.variant_assignments
    }
    if admission.reviewed_decisions(
        admission.scoped_variants(source, admission.FIXED_SCOPES)
    ) != admission.reviewed_decisions(kept):
        raise admission.IntentError("variant_changed", "")


_bound_erasure_of = erasure_rules.erasure_of


def trust_the_producer(old, source, erasures):
    """A removal producer claims whatever its configuration names, as if the
    ledger agreed."""
    claimed = {}
    for producer in source.producers.values():
        config = producer.configuration or {}
        try:
            document = UUID(config["forgotten_document_id"])
            removed = frozenset(UUID(e) for e in config["removed_entity_ids"])
        except (KeyError, TypeError, ValueError):
            continue
        claimed[document] = removed
    return _bound_erasure_of(old, source, erasures._replace(forgotten=claimed))


class AnyKey:
    """Equal to every key."""

    __hash__ = None

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


def any_producer_key(identity_data_id, revision):
    """A removal producer may sit under any key."""
    return AnyKey()


def trust_cited_records(old, source, erasures):
    """A removal may cite whatever removed records its configuration names,
    as if a bound removal listed each one."""
    claimed = {}
    for producer in source.producers.values():
        try:
            claim = erasure_rules.removal_claim(producer)
        except validation.IntentError:
            continue
        claimed[claim.document] = claim.cited_records
    return _bound_erasure_of(old, source, erasures._replace(records=claimed))


def saved_records_not_foreign(source, key):
    """A saved record counts as the source's own input, so rule 5 never
    sees it."""
    if isinstance(source.inputs[key], SavedRecordInput):
        return False
    return validation.is_foreign(source, key)


def allow_self_citation(description):
    """Only the dataset of a cited record is checked."""
    for item in saved_records(description).values():
        if item.dataset_id != description.dataset_id:
            raise validation.IntentError("not_admitted", "Another dataset")


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
    "allow_moved_occurrences": ("check_same_spans", skip),
    "skip_old_slices": ("check_old_slices", skip),
    "skip_new_slices": ("check_new_slices", skip),
    "skip_revision_step": ("check_next_revision", skip),
    "allow_empty_text": ("check_text_present", skip),
    "allow_renamed_resolutions": ("check_continuing_resolutions", skip),
    "allow_changed_decisions": ("check_continuing_decisions", skip),
    "allow_reused_resolution_ids": ("check_fresh_resolution_ids", skip),
    "allow_unresolved_fresh_groups": ("check_one_resolution_per_fresh_group", skip),
    "allow_changed_mention_recipes": ("check_mention_recipes", skip),
    "allow_changed_reusable_recipes": ("check_reusable_recipes", skip),
    "allow_underived_entities": ("check_derived_entity_ids", skip),
    "allow_changed_scoped_variants": ("check_scoped_variants", skip),
    "allow_old_keys_on_new_variants": ("check_new_variant_keys", skip),
    "allow_span_variants": ("check_no_span_variants", skip),
    "allow_any_input_kinds": ("check_input_kinds", skip),
    "allow_changed_foreign_inputs": ("check_foreign_inputs", skip),
    "allow_unattested_reconfirms": ("check_reconfirmations", skip),
    "reconfirm_by_own_refs": ("foreign_citations", own_foreign_refs),
    "attest_continuing_keys_only": (
        "check_reconfirmations",
        attest_continuing_keys_only,
    ),
    "attest_any_old_input": ("check_reconfirmations", attest_any_old_input),
    "allow_any_erasure": ("check_erasure_removals", skip),
    "erase_partially": ("check_erasure_complete", skip),
    "erase_nothing": ("check_erasure_cites", skip),
    "erase_beyond_the_forgotten": ("check_erasure_confined", skip),
    "erase_unbound": ("erasure_of", trust_the_producer),
    "trust_cited_records": ("erasure_of", trust_cited_records),
    "erasure_under_any_key": ("producer_key", any_producer_key),
    "erasure_records_unchecked": ("check_erasure_records", skip),
    "removal_producers_mutable": ("check_removal_producers_kept", skip),
    "drop_read_recipes": ("check_dropped_unread", skip),
    "saved_records_not_foreign": ("is_foreign", saved_records_not_foreign),
    "allow_self_citation": ("check_citation_scope", allow_self_citation),
    "drop_scoped_variants_freely": (
        "check_scoped_variants",
        drop_scoped_variants_freely,
    ),
}
assert all(
    any(hasattr(m, attribute) for m in (admission, erasure_rules, chains))
    for attribute, _ in MUTANTS.values()
)
