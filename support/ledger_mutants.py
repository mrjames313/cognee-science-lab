"""Scratch breaks of storage.py that support/ledger_check.py must catch.

Each break replaces one exact text in storage.py. load_storage() applies it to an
in-memory copy of the file, so the working tree never changes. `prop` names the
property the break must violate, or INCONCLUSIVE when the break makes an outcome
unreachable, so that the search proves nothing about it.
"""

import sys
import types
from pathlib import Path
from typing import NamedTuple

import cognee_lab.identity.storage as real_storage

STORAGE_PATH = Path(real_storage.__file__)


class Mutant(NamedTuple):
    old: str
    new: str
    prop: str


MUTANTS = {
    "begin-keeps-state": Mutant(
        'row.revision, row.state, row.attempt = source.revision, "pending", attempt',
        'row.revision, row.state, row.attempt = (source.revision, row.state or "pending", attempt)',
        "P1",
    ),
    "complete-skips-verified-revision": Mutant(
        '        if state == "current":\n'
        '            values["verified_revision"] = source.revision\n',
        "",
        "P1",
    ),
    "fail-keeps-state": Mutant('            row.state = "failed"\n', "", "P1"),
    "begin-links-every-source": Mutant(
        "                            RecoveryEvent.dataset == dataset,\n"
        "                            RecoveryEvent.source == sid,\n"
        "                        )\n"
        "                    )\n"
        "                )\n"
        "                .scalars()\n"
        "                .all()\n"
        "            )\n"
        "            for event in events:",
        "                            RecoveryEvent.dataset == dataset,\n"
        "                        )\n"
        "                    )\n"
        "                )\n"
        "                .scalars()\n"
        "                .all()\n"
        "            )\n"
        "            for event in events:",
        "P2",
    ),
    "complete-resolves-every-source": Mutant(
        "                        RecoveryEvent.dataset == dataset, RecoveryEvent.source == sid\n",
        "                        RecoveryEvent.dataset == dataset\n",
        "P2",
    ),
    "no-stale-revision-guard": Mutant(
        "            if actual_revision != expected_revision:\n"
        "                raise IntentError(*STALE_REVISION)\n",
        "",
        "P3",
    ),
    "complete-ignores-attempt": Mutant(
        "                    Publication.attempt == attempt,\n"
        '                    Publication.state == "pending",\n',
        "",
        "P3",
    ),
    "fail-ignores-attempt": Mutant(
        "            if row is None or row.attempt != attempt:",
        "            if row is None:",
        "P3",
    ),
    "assert-pending-ignores-description": Mutant(
        "            or row.description != source\n",
        "",
        "P3",
    ),
    "assert-pending-ignores-attempt": Mutant(
        "            or row.attempt != attempt\n",
        "",
        "P3",
    ),
    "no-writer-reservation": Mutant(
        "            if locked.rowcount != 1:",
        "            if False:",
        "P4",
    ),
    "complete-keeps-reservation": Mutant(
        "            await session.execute(\n"
        "                update(Writer)\n"
        "                .where(\n"
        '                    Writer.dataset == "shared-identity-publication",\n'
        "                    Writer.owner == attempt,\n"
        "                )\n"
        "                .values(owner=None)\n"
        "            )\n"
        "            for event in (",
        "            for event in (",
        "P4",
    ),
    "fail-always-new-event": Mutant(
        "            event = await session.get(RecoveryEvent, event_id)\n"
        "            if event is None:\n",
        "            event = await session.get(RecoveryEvent, event_id)\n"
        "            if False:\n",
        "P5",
    ),
    "no-replace-recovery-choice": Mutant(
        'owned("replace", FAILED_REPLACEMENT)',
        'lineage_row({"replace": 0, "reconcile": 0}, FAILED_REPLACEMENT, owner="replace")',
        "P5",
    ),
    # The failed withdrawal row falls back to the plain failed row's entry.
    "no-withdraw-recovery-choice": Mutant(
        '    ("failed", "identity_withdraw"): owned("withdraw", FAILED_WITHDRAWAL),\n',
        "",
        "P5",
    ),
    # Without the guard a withdrawn row took reconcile and a replace retry.
    "no-withdrawn-guard": Mutant(
        "Transition(\n"
        '        {"withdraw": 0, "forget": 0}, otherwise=WITHDRAWN_SOURCE\n'
        "    )",
        'lineage_row({"withdraw": 0, "forget": 0, "reconcile": 0, "replace": 0})',
        "P5",
    ),
    # Forget refuses a withdrawn source, as before checkpoint I.
    "forget-refuses-withdrawn": Mutant(
        '{"withdraw": 0, "forget": 0}, otherwise=WITHDRAWN_SOURCE',
        '{"withdraw": 0}, otherwise=WITHDRAWN_SOURCE',
        "INCONCLUSIVE",
    ),
    # Forget refuses a source whose publication failed, as before.
    "forget-refuses-failed-publication": Mutant(
        'lineage_row({"reconcile": 0, "withdraw": 0, "forget": 0})',
        'lineage_row({"reconcile": 0, "withdraw": 0})',
        "INCONCLUSIVE",
    ),
    # A forgotten row's tombstone already refuses every begin at its revision
    # (revision_reuse), so the break that matters admits a new replacement.
    "no-forgotten-guard": Mutant(
        '{"publish": 1}, otherwise=FORGOTTEN_SOURCE, sequence=READD_REVISION',
        '{"publish": 1, "reconcile": 0, "withdraw": 0, "replace": 1, "forget": 0},'
        " sequence=READD_REVISION",
        "P5",
    ),
    # Publish admitted on every saved row that no method owns, held to the
    # next revision as a re-add is.
    "publish-restarts-saved-row": Mutant(
        '    return Transition(admits, {"publish": SAVED_LINEAGE}, otherwise, sequence, owner)\n',
        '    return Transition({"publish": 1, **admits} if otherwise is None else admits,'
        " {}, otherwise, sequence or READD_REVISION, owner)\n",
        "P5",
    ),
    # The failed forget row admits reconcile and withdraw besides forget.
    "no-forget-recovery-choice": Mutant(
        'owned("forget", FAILED_FORGET)',
        'lineage_row({"forget": 0, "reconcile": 0, "withdraw": 0}, owner="forget")',
        "P5",
    ),
    # A failed replacement or withdrawal is resumed only by its own method,
    # never erased by a forget that would drop its saved intent.
    "forget-on-failed-replacement": Mutant(
        'owned("replace", FAILED_REPLACEMENT)',
        'lineage_row({"replace": 0, "forget": 0}, FAILED_REPLACEMENT, owner="replace")',
        "P5",
    ),
    "forget-on-failed-withdrawal": Mutant(
        'owned("withdraw", FAILED_WITHDRAWAL)',
        'lineage_row({"withdraw": 0, "forget": 0}, FAILED_WITHDRAWAL, owner="withdraw")',
        "P5",
    ),
    "forget-takes-any-plan": Mutant(
        '    if required and plan.get("operation") != required.operation:\n',
        '    if required and method != "forget" and plan.get("operation") != required.operation:\n',
        "P5",
    ),
    # A forgotten row keeps its description, its plan or its event messages.
    "complete-keeps-description": Mutant(
        '            values["description"] = tombstone.model_dump_json()\n',
        "",
        "P7",
    ),
    "complete-keeps-plan": Mutant(
        "                row.plan = encode(scrubbed_plan(json.loads(row.plan)))\n",
        "                pass\n",
        "P7",
    ),
    "complete-keeps-messages": Mutant(
        "                if tombstone is not None:\n"
        "                    info = scrubbed_event(info)\n",
        "",
        "P7",
    ),
    "complete-forgotten-as-withdrawn": Mutant(
        '        values = {"state": state}\n',
        '        values = {"state": "withdrawn" if state == "forgotten" else state}\n',
        "P1",
    ),
    "no-advance-guard": Mutant(
        "    if row and step != 1 and revision != actual:\n"
        "        return ADVANCE_THROUGH_REPLACEMENT\n",
        "",
        "P5",
    ),
    # Every method on a current row skips the advance guard, not only replace.
    "advance-guard-ignores-method": Mutant(
        "    if row and step != 1 and revision != actual:\n",
        '    if row and step != 1 and row.state != "current" and revision != actual:\n',
        "P5",
    ),
    "no-revision-reuse": Mutant(
        "    if not superseding and source != row.description:\n"
        "        return REVISION_REUSE\n",
        "",
        "P5",
    ),
    # An erasure retry supersedes a description it does not name.
    "supersede-any-description": Mutant(
        "            and erased_from(plan) == erased_from(superseding_plan(row, source))\n",
        "            and len(erased_from(plan)) == len(erased_from(row.plan)) + 1\n",
        "P5",
    ),
    # A first publication may skip revisions.
    "no-plus-one": Mutant(
        "        return None if revision == actual + 1 else NEW_REVISION",
        "        return None if revision > actual else NEW_REVISION",
        "P5",
    ),
    "no-replace-plan-check": Mutant(
        '    if required and plan.get("operation") != required.operation:\n',
        '    if required and method != "replace" and plan.get("operation") != required.operation:\n',
        "P5",
    ),
    # A replace retry is never held to the saved replacement plan.
    "no-replace-plan-preservation": Mutant(
        'preserved=("previous_description", "text_change", ERASED_FROM)',
        "preserved=(ERASED_FROM,)",
        "P5",
    ),
    "no-text-change-preservation": Mutant(
        'preserved=("previous_description", "text_change", ERASED_FROM)',
        'preserved=("previous_description", ERASED_FROM)',
        "P5",
    ),
    # A plan names superseded revisions outside a retry of a failed row.
    "erasure-outside-retry": Mutant(
        "    elif plan.get(ERASED_FROM):\n        return STRAY_ERASURE\n",
        "",
        "P5",
    ),
    # A failed publication never takes a removal in its saved revision.
    "reconcile-never-supersedes": Mutant(
        "        preserved=(ERASED_FROM,),\n        supersedes=True,\n",
        "        preserved=(ERASED_FROM,),\n",
        "INCONCLUSIVE",
    ),
    # The store begins an erasure retry without checking that each step of
    # its chain is the removal a forget allows (erasure_rules).
    "erasure-chain-unchecked": Mutant(
        "    if chain := erasure_chain(row, method, plan):\n",
        "    if False and (chain := erasure_chain(row, method, plan)):\n",
        "P5",
    ),
    # A retry of a failed erasure retry drops the saved revisions it
    # superseded from its plan.
    "supersede-drops-chain": Mutant(
        "            and erased_from(plan) == erased_from(superseding_plan(row, source))\n",
        "            and erased_from(plan)[-1:] in ([], [row.description])\n",
        "P5",
    ),
    # begin() reads no saved row for the chain check, so no erasure retry
    # finds the forget it erases.
    "begin-reads-no-rows": Mutant(
        "            if erasure_chain(saved, method, plan):\n",
        "            if False:\n",
        "INCONCLUSIVE",
    ),
    "begin-resolves-open-event": Mutant(
        '                    info.setdefault("recovery_attempts", []).append(\n'
        '                        {"attempt_id": attempt, "method": method, "started_at": now()}\n'
        "                    )\n",
        '                    info["resolved_at"] = now()\n',
        "P5",
    ),
    "complete-deletes-open-events": Mutant(
        '                if info.get("resolved_at") is None:\n'
        "                    info.update(\n",
        '                if info.get("resolved_at") is None:\n'
        "                    await session.delete(event)\n"
        "                    continue\n"
        "                    info.update(\n",
        "P5",
    ),
    "begin-drops-open-event": Mutant(
        '                    info.setdefault("recovery_attempts", []).append(\n'
        '                        {"attempt_id": attempt, "method": method, "started_at": now()}\n'
        "                    )\n"
        "                    event.details = encode(info)\n",
        "                    await session.delete(event)\n",
        "P5",
    ),
    "begin-links-resolved-events": Mutant(
        '                if info.get("resolved_at") is None:\n'
        "                    info.setdefault(",
        "                if True:\n                    info.setdefault(",
        "P5",
    ),
    "complete-always-refuses": Mutant(
        "            if result.rowcount != 1:",
        "            if True:",
        "P6",
    ),
    # Every failed row is refused as a pending one.
    "failed-row-never-recoverable": Mutant(
        "    for key in ((row.state, row.operation), (row.state, None)):\n",
        '    for key in [("pending" if row.state == "failed" else row.state, None)]:\n',
        "P6",
    ),
    "advance-guard-refuses-readd": Mutant(
        "    if row and step != 1 and revision != actual:\n",
        '    if row and (step != 1 or method == "publish") and revision != actual:\n',
        "INCONCLUSIVE",
    ),
    # A missing row admits forget like the other first steps.
    "forget-without-a-row": Mutant(
        '        {"publish": 1, "reconcile": 1, "withdraw": 1},\n'
        '        {"replace": REPLACEMENT_MISSING, "forget": FORGET_MISSING},\n',
        '        {"publish": 1, "reconcile": 1, "withdraw": 1, "forget": 1},\n'
        '        {"replace": REPLACEMENT_MISSING},\n',
        "P5",
    ),
    "complete-misnames-outcome": Mutant(
        '                        outcome="restored" if state == "current" else state,\n',
        '                        outcome="restored",\n',
        "P5",
    ),
    "begin-always-busy": Mutant(
        "            if locked.rowcount != 1:",
        "            if True:",
        "INCONCLUSIVE",
    ),
}

# Breaks that the default bound misses and a deeper manual search catches.
# --mutants and the pytest file leave them out. Run one with
# --mutant NAME --depth N. The test replays the minimal sequence of each.
DEEP_MUTANTS = {
    # Caught at depth 7: a replace retry built from a stale read of the
    # current replacement row, sent after the row was withdrawn.
    "withdrawn-guard-admits-replace": Mutant(
        '{"withdraw": 0, "forget": 0}, otherwise=WITHDRAWN_SOURCE',
        '{"withdraw": 0, "forget": 0, "replace": 0}, otherwise=WITHDRAWN_SOURCE',
        "P5",
    ),
}
assert (
    not MUTANTS.keys() & DEEP_MUTANTS.keys()
), "a break name is in both MUTANTS and DEEP_MUTANTS"


def load_storage(mutant):
    if mutant is None:
        return real_storage
    old, new, _ = (MUTANTS | DEEP_MUTANTS)[mutant]
    text = STORAGE_PATH.read_text()
    if text.count(old) != 1:
        raise SystemExit(
            f"mutant {mutant} no longer matches storage.py exactly once; "
            "update it in support/ledger_mutants.py"
        )
    module = types.ModuleType(f"cognee_lab.identity._ledger_mutant_{mutant}")
    module.__package__ = "cognee_lab.identity"
    sys.modules[module.__name__] = module
    exec(compile(text.replace(old, new), str(STORAGE_PATH), "exec"), module.__dict__)
    return module
