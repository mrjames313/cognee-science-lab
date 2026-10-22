from pathlib import Path

import pytest

import ledger_check
from ledger_check import Config
from ledger_mutants import DEEP_MUTANTS, MUTANTS
from ledger_model import TEXT_REGROUP
from cognee_lab.identity.group_regrouping import SPLIT_MAP

# The default-bound search size. A change to the step list, the symmetry rule
# or the no-op rule changes it; update it on purpose and say so in the commit.
PINNED = dict(nodes=3828, sequences=3717)


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


def test_a_replay_runs_the_steps_after_a_refused_step():
    replayed = ledger_check.run_one(
        Config(
            mutant="complete-skips-verified-revision",
            replay=(
                "W1 publish S1 rev=2 expect=0 plan=publish",
                "W1 publish S1 rev=1 expect=0 plan=publish",
                "W1 complete",
            ),
        )
    )
    assert replayed.verdict == "FAIL", ledger_check.report(replayed)
    assert replayed.failure.prop == "P1"


# The minimal sequence that a search at the named depth reports for each break.
DEEP_SEQUENCES = {
    "withdrawn-guard-admits-replace": (
        "W1 publish S1 rev=1 expect=0 plan=publish",
        "W1 complete",
        "W1 replace S1 rev=2 expect=1 plan=replace<r1",
        "W1 complete",
        "W1 withdraw S1 rev=2 expect=2 plan=withdraw",
        "W1 complete",
        "W1 replace S1 rev=2 expect=2 plan=replace<r1",
    ),
}


@pytest.mark.parametrize("name", sorted(DEEP_MUTANTS))
def test_each_deep_break_fails_on_its_recorded_sequence(name):
    replayed = ledger_check.run_one(Config(mutant=name, replay=DEEP_SEQUENCES[name]))
    assert replayed.failure is not None, ledger_check.report(replayed)
    assert replayed.failure.prop == DEEP_MUTANTS[name].prop, ledger_check.report(
        replayed
    )


def test_the_modelled_regrouping_is_the_one_split_group_sends():
    assert TEXT_REGROUP["occurrence_map"] == SPLIT_MAP


def test_a_retry_cannot_swap_a_text_change_for_a_regrouping():
    swap = (
        "W1 publish S1 rev=1 expect=0 plan=publish",
        "W1 complete",
        "W1 replace S1 rev=2 expect=1 plan=text<r1",
        "W1 fail@replace_saved",
        "W1 replace S1 rev=2 expect=2 plan=regroup<r1",
    )
    assert ledger_check.run_one(Config(replay=swap)).verdict == "PASS"
    broken = ledger_check.run_one(
        Config(mutant="no-text-change-preservation", replay=swap)
    )
    assert broken.failure.prop == "P5"


def test_a_search_that_reaches_no_failure_is_inconclusive(capsys):
    assert ledger_check.main(["--depth", "1"]) == 2
    out = capsys.readouterr().out
    assert out.startswith("INCONCLUSIVE") and "verified" not in out


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
