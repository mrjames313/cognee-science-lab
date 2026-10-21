import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "ledger_check", Path(__file__).parents[1] / "support/ledger_check.py"
)
ledger_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger_check)


async def test_ledger_properties_hold_within_default_bound():
    run = await ledger_check.check_ledger(
        ledger_check.Run(depth=ledger_check.DEFAULT_DEPTH, sources=2, writers=2)
    )
    assert run.failure is None, ledger_check.report(run)
    assert run.sequences > 0


@pytest.mark.parametrize("mutant", sorted(ledger_check.MUTANTS))
async def test_each_scratch_break_of_storage_is_caught(mutant):
    run = await ledger_check.check_ledger(
        ledger_check.Run(
            depth=ledger_check.DEFAULT_DEPTH, sources=2, writers=2, mutant=mutant
        )
    )
    assert run.failure is not None, f"{mutant} survived the default bound"
    assert run.failure["property"] == ledger_check.MUTANTS[mutant][2]
