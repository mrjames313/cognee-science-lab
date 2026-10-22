import pytest

import occurrence_check
from cognee_lab.identity.admission import GroupFate, admit_general
from cognee_lab.identity.validation import IntentError
from occurrence_mutants import MUTANTS
from occurrence_worlds import DERIVED, Added, NewGroup, Old, World, materialize, oracle


def test_admission_agrees_with_the_oracle_on_small_worlds():
    tally, failures = occurrence_check.run(occurrence_check.SMALL)
    assert failures == []
    for name in (
        "general first attempt",
        "general retry",
        "general same text",
        "corrupt map: two origins",
        "corrupt description: continuing decision changed",
    ):
        assert tally[name] > 0
    for mode in ("prefix", "retention", "continuity", "regrouping"):
        assert tally[f"old {mode}"] > 0
        assert tally[f"convert {mode}"] > 0


@pytest.fixture(scope="module")
def caught():
    return occurrence_check.run_mutants()


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_each_rule_is_needed_by_some_small_world(caught, name):
    assert caught[name] is not None


def admit(world):
    case = materialize(world)
    return admit_general(
        case["old"], case["new"], case["before"], case["after"], case["general"]
    )


def test_strict_policy_refuses_peel_off_and_keyed_restart():
    peel_off = World(
        (("g1", 2),),
        0,
        (NewGroup("g1", "g1", (Old("g1", 0),)), NewGroup("n1", DERIVED, (Old("g1", 1),))),
    )
    restart = World((("g1", 1),), 1, (NewGroup("g1", "g1", (Added(0),)),))
    for world in (peel_off, restart):
        assert oracle(world) == ("refuse", {"key", "unused"})
        with pytest.raises(IntentError, match="key that no old group used"):
            admit(world)
    split = World(
        (("g1", 2),),
        0,
        (NewGroup("n1", DERIVED, (Old("g1", 0),)), NewGroup("n2", DERIVED, (Old("g1", 1),))),
    )
    mixed = World(
        (("g1", 2), ("g2", 1)),
        1,
        (NewGroup("g1", "g1", (Old("g1", 1), Added(0))),),
    )
    assert admit(split) == GroupFate(frozenset(), {"g1"}, {"n1", "n2"})
    assert admit(mixed) == GroupFate({"g1"}, {"g2"}, frozenset())
    assert [admit(w) for w in (split, mixed)] == [
        GroupFate(*oracle(w)[1:]) for w in (split, mixed)
    ]


def test_a_continuing_group_may_reorder_its_occurrences():
    world = World((("g1", 2),), 0, (NewGroup("g1", "g1", (Old("g1", 0), Old("g1", 1))),))
    case = materialize(world, same_text=True)
    swapped = {"g1": [["g1", 1], ["g1", 0]]}
    fate = admit_general(case["old"], case["new"], case["before"], case["after"], swapped)
    assert fate == GroupFate({"g1"}, frozenset(), frozenset())
