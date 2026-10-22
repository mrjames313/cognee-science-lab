import occurrence_check
from occurrence_worlds import World, oracle

SMALL = ((1,), (2,), (1, 1))


def test_old_modes_agree_with_the_oracle_on_small_worlds():
    tally, failures = occurrence_check.run(SMALL, max_additions=1)
    assert failures == []
    for mode in ("prefix", "retention", "continuity", "regrouping"):
        assert tally[(mode, "agrees")] > 0


def test_strict_policy_refuses_peel_off_and_keyed_restart():
    peel_off = World(
        (("g1", 2),),
        0,
        (("g1", "g1", (("old", "g1", 0),)), ("n1", None, (("old", "g1", 1),))),
    )
    assert oracle(peel_off) == ("refuse", "key")
    split = World(
        (("g1", 2),),
        0,
        (("n1", None, (("old", "g1", 0),)), ("n2", None, (("old", "g1", 1),))),
    )
    assert oracle(split) == ("admit", frozenset(), {"g1"}, {"n1", "n2"})
    restart = World((("g1", 1),), 1, (("g1", "g1", (("add", 0),)),))
    assert oracle(restart) == ("refuse", "key")
    mixed = World(
        (("g1", 2), ("g2", 1)),
        1,
        (("g1", "g1", (("old", "g1", 1), ("add", 0))),),
    )
    assert oracle(mixed) == ("admit", {"g1"}, {"g2"}, frozenset())
