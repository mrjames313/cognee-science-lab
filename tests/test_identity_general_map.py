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

# The text-change field each fixture saved before the general map, if any.
LEGACY_FIELDS = {
    prefix_case: None,
    removal_case: ("occurrence_retention", {"g01": [1], "g02": []}),
    retirement_case: ("occurrence_retention", {"g01": [], "g02": [0]}),
    addition_case: ("occurrence_continuity", {"g01": [0, 1], "g02": [0]}),
    split_case: ("occurrence_regrouping", SPLIT_MAP),
    combination_case: ("occurrence_regrouping", COMBINE_MAP),
}


def legacy_plan(old, before, after, field):
    text_change = dict(previous_text=before, text=after, chunk_budget=512)
    if field:
        text_change[field[0]] = field[1]
    return dict(text_change=text_change, previous_description=old.model_dump_json())


@pytest.mark.parametrize("case", GENERAL_MAPS, ids=lambda c: c.__name__)
def test_each_fixture_admits_its_general_map_with_the_pinned_group_fate(
    source_payload, case
):
    old, new, before, after = case(source_payload)
    general, expected = GENERAL_MAPS[case]
    assert admit(old, new, before, after, parse_occurrence_map(general)) == expected


@pytest.mark.parametrize("case", GENERAL_MAPS, ids=lambda c: c.__name__)
def test_a_plan_saved_with_the_old_fields_reads_as_the_fixture_general_map(
    source_payload, case
):
    old, new, before, after = case(source_payload)
    general, expected = GENERAL_MAPS[case]
    change = TextChange.from_plan(legacy_plan(old, before, after, LEGACY_FIELDS[case]))
    assert change.occurrence_map == parse_occurrence_map(general)
    assert admit(old, new, before, after, change.occurrence_map) == expected


@pytest.mark.parametrize(
    "field",
    [
        ("occurrence_retention", {"g01": [1, 1], "g02": []}),
        ("occurrence_retention", {"g01": [1, 0], "g02": []}),
        ("occurrence_retention", {"g01": [2], "g02": []}),
        ("occurrence_retention", {"g01": [True], "g02": []}),
        ("occurrence_retention", {"g01": [1]}),
        ("occurrence_retention", {"g01": [1], "g02": [], "g03": []}),
        ("occurrence_retention", [1]),
        ("occurrence_continuity", {"g01": [0, 1]}),
        ("occurrence_regrouping", {"g01": [["g04", 0], ["g05", 0]]}),
    ],
)
def test_a_malformed_old_map_is_refused_when_the_plan_is_read(source_payload, field):
    old, _, before, after = removal_case(source_payload)
    with pytest.raises(IntentError) as refused:
        TextChange.from_plan(legacy_plan(old, before, after, field))
    assert refused.value.code == "recovery_plan"


def test_a_plan_cannot_select_two_old_maps(source_payload):
    old, _, before, after = removal_case(source_payload)
    plan = legacy_plan(
        old, before, after, ("occurrence_retention", {"g01": [1], "g02": []})
    )
    plan["text_change"]["occurrence_continuity"] = {"g01": [0, 1], "g02": [0]}
    with pytest.raises(IntentError) as refused:
        TextChange.from_plan(plan)
    assert refused.value.code == "recovery_plan"


def test_a_plan_cannot_hold_the_general_map_and_an_old_map(source_payload):
    old, _, before, after = removal_case(source_payload)
    plan = legacy_plan(
        old, before, after, ("occurrence_retention", {"g01": [1], "g02": []})
    )
    plan["text_change"]["occurrence_map"] = REMOVAL_MAP
    with pytest.raises(IntentError) as refused:
        TextChange.from_plan(plan)
    assert refused.value.code == "recovery_plan"
    plan["text_change"]["occurrence_retention"] = None
    assert TextChange.from_plan(plan).occurrence_map == parse_occurrence_map(
        REMOVAL_MAP
    )


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


def test_the_general_rules_are_stricter_than_the_old_prefix_mode(source_payload):
    old, new, before, after = prefix_case(source_payload)
    change = TextChange.from_plan(legacy_plan(old, before, after, None))
    assert change.is_prefix_shift
    skipped = new.model_copy(update=dict(revision=old.revision + 2))
    with pytest.raises(IntentError, match="advances exactly one revision") as refused:
        admit(old, skipped, before, after, change.occurrence_map)
    assert refused.value.code == "not_admitted"
