import json
from dataclasses import asdict

import pytest

from test_identity_additions import addition
from test_identity_occurrences import example as removal
from test_identity_regrouping import combine, split
from test_identity_resolved_retirement import retired_example
from test_identity_text_changes import example as prefix_edit
from cognee_lab.identity.admission import (
    GroupFate,
    OccurrenceRef,
    admit,
    parse_occurrence_map,
)
from cognee_lab.identity.captured_text import BEFORE
from cognee_lab.identity.text_changes import TextChange
from cognee_lab.identity.validation import IntentError
from cognee_lab.identity.group_regrouping import (
    COMBINE_AFTER,
    COMBINE_MAP,
    SPLIT_AFTER,
    SPLIT_MAP,
)
from cognee_lab.identity.occurrence_addition import AFTER as ADDED, ADDITION_MAP
from cognee_lab.identity.occurrence_fixture import AFTER as REMOVED, REMOVAL_MAP
from cognee_lab.identity.resolved_retirement import (
    AFTER as RETIRED,
    RETIREMENT_MAP,
)


def prefix_case(payload):
    old, before, after, _, new = prefix_edit(payload)
    return old, new, before, after


def removal_case(payload):
    old, _, new = removal(payload)
    return old, new, BEFORE, REMOVED


def retirement_case(payload):
    old, _, new = retired_example(payload)
    return old, new, BEFORE, RETIRED


def addition_case(payload):
    old, _, new = addition(payload)
    return old, new, BEFORE, ADDED


def split_case(payload):
    old, _, new = split(payload)
    return old, new, BEFORE, SPLIT_AFTER


def combination_case(payload):
    old, _, new = combine(payload)
    return old, new, SPLIT_AFTER, COMBINE_AFTER


def fate(continuing, retired=(), fresh=()):
    return GroupFate(frozenset(continuing), frozenset(retired), frozenset(fresh))


PREFIX_MAP = {"g01": [["g01", 0], ["g01", 1]]}

# Each captured fixture's edit, stated as the general map a reviewer writes,
# and the group fates it must produce.
GENERAL_MAPS = {
    prefix_case: (PREFIX_MAP, fate({"g01"})),
    removal_case: (REMOVAL_MAP, fate({"g01"}, {"g02"})),
    retirement_case: (RETIREMENT_MAP, fate({"g02"}, {"g01"})),
    addition_case: (ADDITION_MAP, fate({"g01", "g02"}, (), {"g03"})),
    split_case: (SPLIT_MAP, fate({"g02"}, {"g01"}, {"g04", "g05"})),
    combination_case: (COMBINE_MAP, fate({"g02"}, {"g04", "g05"}, {"g06"})),
}


@pytest.mark.parametrize("case", GENERAL_MAPS, ids=lambda c: c.__name__)
def test_each_fixture_admits_its_general_map_with_the_pinned_group_fate(
    source_payload, case
):
    old, new, before, after = case(source_payload)
    general, expected = GENERAL_MAPS[case]
    assert admit(old, new, before, after, parse_occurrence_map(general)) == expected


@pytest.mark.parametrize(
    "old_field",
    [
        None,
        ("occurrence_retention", {"g01": [1], "g02": []}),
        ("occurrence_continuity", {"g01": [0, 1], "g02": [0]}),
        ("occurrence_regrouping", SPLIT_MAP),
    ],
    ids=["prefix", "retention", "continuity", "regrouping"],
)
def test_a_plan_without_the_general_map_is_refused_as_history(
    source_payload, old_field
):
    old, _, before, after = removal_case(source_payload)
    text_change = dict(previous_text=before, text=after, chunk_budget=512)
    if old_field:
        text_change[old_field[0]] = old_field[1]
    plan = dict(text_change=text_change, previous_description=old.model_dump_json())
    with pytest.raises(
        IntentError, match="predates the general occurrence map"
    ) as refused:
        TextChange.from_plan(plan)
    assert refused.value.code == "recovery_plan"


def test_a_plan_with_the_general_map_and_a_legacy_key_is_refused(source_payload):
    _, _, before, after = removal_case(source_payload)
    text_change = dict(
        previous_text=before,
        text=after,
        chunk_budget=512,
        occurrence_map={"g01": [None, ["g01", 0]], "g02": [["g02", 0]]},
        occurrence_retention={"g01": [1], "g02": []},
    )
    with pytest.raises(IntentError) as refused:
        TextChange.from_plan(dict(text_change=text_change))
    assert refused.value.code == "recovery_plan"


@pytest.mark.parametrize("case", GENERAL_MAPS, ids=lambda c: c.__name__)
def test_a_text_change_survives_the_saved_plan(source_payload, case):
    _, _, before, after = case(source_payload)
    general, _ = GENERAL_MAPS[case]
    change = TextChange(before, after, general, chunk_budget=300)
    saved = json.loads(json.dumps(asdict(change)))
    assert TextChange.from_plan(dict(text_change=saved)) == change
    assert all(
        isinstance(ref, OccurrenceRef) or ref is None
        for refs in change.occurrence_map.values()
        for ref in refs
    )


def test_a_prefix_plan_must_also_advance_one_revision(source_payload):
    old, new, before, after = prefix_case(source_payload)
    change = TextChange(before, after, PREFIX_MAP)
    assert change.prefix_shift(old, new) == len(after) - len(before)
    skipped = new.model_copy(update=dict(revision=old.revision + 2))
    with pytest.raises(IntentError, match="advances exactly one revision") as refused:
        admit(old, skipped, before, after, change.occurrence_map)
    assert refused.value.code == "not_admitted"
