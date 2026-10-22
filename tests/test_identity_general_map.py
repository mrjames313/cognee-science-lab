import pytest

from test_identity_additions import addition
from test_identity_occurrences import example as removal
from test_identity_regrouping import combine, split
from test_identity_resolved_retirement import retired_example
from test_identity_text_changes import example as prefix_edit
from cognee_lab.identity.admission import admit_general, admit_remap, to_occurrence_map
from cognee_lab.identity.captured_text import BEFORE
from cognee_lab.identity.group_regrouping import (
    COMBINE_AFTER,
    COMBINE_REGROUPING,
    SPLIT_AFTER,
    SPLIT_REGROUPING,
)
from cognee_lab.identity.occurrence_addition import AFTER as ADDED, CONTINUITY
from cognee_lab.identity.occurrence_fixture import AFTER as REMOVED, RETENTION
from cognee_lab.identity.resolved_retirement import (
    AFTER as RETIRED,
    RETENTION as RETIRED_RETENTION,
)


def prefix_case(payload):
    old, before, after, _, new = prefix_edit(payload)
    return old, new, before, after, "prefix", None


def removal_case(payload):
    old, _, new = removal(payload)
    return old, new, BEFORE, REMOVED, "retention", RETENTION


def retirement_case(payload):
    old, _, new = retired_example(payload)
    return old, new, BEFORE, RETIRED, "retention", RETIRED_RETENTION


def addition_case(payload):
    old, _, new = addition(payload)
    return old, new, BEFORE, ADDED, "continuity", CONTINUITY


def split_case(payload):
    old, _, new = split(payload)
    return old, new, BEFORE, SPLIT_AFTER, "regrouping", SPLIT_REGROUPING


def combination_case(payload):
    old, _, new = combine(payload)
    return old, new, SPLIT_AFTER, COMBINE_AFTER, "regrouping", COMBINE_REGROUPING


# Each captured fixture's edit, stated as the general map a reviewer writes.
GENERAL_MAPS = {
    prefix_case: {"g01": [["g01", 0], ["g01", 1]]},
    removal_case: {"g01": [None, ["g01", 0]], "g02": [None]},
    retirement_case: {"g01": [None, None], "g02": [["g02", 0]]},
    addition_case: {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]},
    split_case: {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]},
    combination_case: {"g04": [["g06", 0]], "g05": [["g06", 1]], "g02": [["g02", 0]]},
}


@pytest.mark.parametrize("case", GENERAL_MAPS, ids=lambda c: c.__name__)
def test_each_fixture_admits_the_same_edit_as_a_general_map(source_payload, case):
    old, new, before, after, kind, reviewed = case(source_payload)
    general = to_occurrence_map(old, kind, reviewed)
    assert general == GENERAL_MAPS[case]
    maps = {} if kind == "prefix" else {f"occurrence_{kind}": reviewed}
    assert admit_general(old, new, before, after, general) == admit_remap(
        old, new, before, after, **maps
    )
