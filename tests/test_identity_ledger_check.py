from pathlib import Path

import pytest

import ledger_check
from ledger_check import Config
from ledger_mutants import MUTANTS

# The default-bound search size. A change to the step list, the symmetry rule
# or the no-op rule changes it; update it on purpose and say so in the commit.
PINNED = dict(nodes=3062, sequences=2961)


@pytest.fixture(scope="module")
def runs():
    configs = [Config(), *(Config(mutant=name) for name in MUTANTS)]
    results = ledger_check.run_all(configs, minimal=False)
    return dict(zip([None, *MUTANTS], results))


def test_ledger_properties_hold_within_default_bound(runs):
    result = runs[None]
    assert result.verdict == "PASS", ledger_check.report(result)
    assert dict(nodes=result.nodes, sequences=result.sequences) == PINNED


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_each_scratch_break_of_storage_is_caught(runs, name):
    result = runs[name]
    assert ledger_check.caught_as(result) == MUTANTS[name].prop, ledger_check.report(
        result
    )


def test_a_reported_sequence_replays_to_the_same_property():
    found = ledger_check.run_one(Config(mutant="no-replace-plan-preservation"))
    replayed = ledger_check.run_one(
        Config(
            mutant="no-replace-plan-preservation", replay=tuple(found.failure.sequence)
        )
    )
    assert replayed.failure.prop == found.failure.prop == "P5"
    assert replayed.failure.sequence == found.failure.sequence


def test_a_search_that_reaches_no_failure_is_inconclusive(capsys):
    assert ledger_check.main(["--depth", "1"]) == 2
    assert capsys.readouterr().out.startswith("INCONCLUSIVE")


def test_replay_takes_no_skip_probability():
    with pytest.raises(SystemExit) as refused:
        ledger_check.main(["--replay", "W1 complete", "--skip-probability", "0.5"])
    assert refused.value.code == 2


def test_served_copies_the_retrieval_eligibility_test():
    retrieve = Path(__file__).parents[1] / "src/cognee_lab/identity/retrieve.py"
    assert (
        'if row["state"] != "current" or row["revision"] != row["verified_revision"]:'
        in retrieve.read_text()
    ), "retrieve.py changed its eligibility test: update served() in support/ledger_check.py"
