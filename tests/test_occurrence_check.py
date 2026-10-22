import pytest

import occurrence_check
from occurrence_mutants import MUTANTS
from occurrence_worlds import World, oracle


def test_admission_agrees_with_the_oracle_on_small_worlds():
    tally, failures = occurrence_check.run(occurrence_check.SMALL)
    assert failures == []
    for name in ("general first attempt", "general retry", "corrupt: two origins"):
        assert tally[name] > 0
    for mode in ("prefix", "retention", "continuity", "regrouping"):
        assert tally[f"old {mode}"] > 0


@pytest.fixture(scope="module")
def caught():
    return occurrence_check.run_mutants()


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_each_rule_is_needed_by_some_small_world(caught, name):
    assert caught[name] is not None


def test_strict_policy_refuses_peel_off_and_keyed_restart():
    peel_off = World(
        (("g1", 2),),
        0,
        (("g1", "g1", (("old", "g1", 0),)), ("n1", None, (("old", "g1", 1),))),
    )
    assert oracle(peel_off) == ("refuse", {"key", "unused"})
    split = World(
        (("g1", 2),),
        0,
        (("n1", None, (("old", "g1", 0),)), ("n2", None, (("old", "g1", 1),))),
    )
    assert oracle(split) == ("admit", frozenset(), {"g1"}, {"n1", "n2"})
    restart = World((("g1", 1),), 1, (("g1", "g1", (("add", 0),)),))
    assert oracle(restart) == ("refuse", {"key", "unused"})
    mixed = World(
        (("g1", 2), ("g2", 1)),
        1,
        (("g1", "g1", (("old", "g1", 1), ("add", 0))),),
    )
    assert oracle(mixed) == ("admit", {"g1"}, {"g2"}, frozenset())
