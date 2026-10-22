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
        '                raise IntentError("stale_revision", "Saved revision changed")\n',
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
        '            or IdentitySource.model_validate_json(row["description"]) != source\n',
        "",
        "P3",
    ),
    "assert-pending-ignores-attempt": Mutant(
        '            or row["attempt"] != attempt\n',
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
        '                and json.loads(row.plan).get("operation") == "identity_replace"\n'
        '                and method != "replace"\n',
        '                and json.loads(row.plan).get("operation") == "identity_replace"\n'
        '                and method not in {"replace", "reconcile"}\n',
        "P5",
    ),
    "no-withdraw-recovery-choice": Mutant(
        '                and json.loads(row.plan).get("operation") == "identity_withdraw"\n'
        '                and method != "withdraw"\n',
        '                and json.loads(row.plan).get("operation") == "identity_withdraw"\n'
        "                and False\n",
        "P5",
    ),
    "no-withdrawn-guard": Mutant(
        '            if row and row.state == "withdrawn" and method != "withdraw":',
        "            if False:",
        "P5",
    ),
    "no-forgotten-guard": Mutant(
        '            if row and row.state == "forgotten" and method != "publish":',
        "            if False:",
        "P5",
    ),
    "publish-restarts-saved-row": Mutant(
        '                if row.state != "forgotten":\n'
        "                    raise IntentError(\n"
        '                        "recovery_choice", "Reconcile a saved publication explicitly"\n',
        "                if False:\n"
        "                    raise IntentError(\n"
        '                        "recovery_choice", "Reconcile a saved publication explicitly"\n',
        "P5",
    ),
    "readd-at-forgotten-revision": Mutant(
        "                if source.revision != actual_revision + 1:\n"
        "                    raise IntentError(\n"
        '                        "revision_sequence",\n'
        '                        "Re-add a forgotten source at exactly the next revision",\n',
        "                if False:\n"
        "                    raise IntentError(\n"
        '                        "revision_sequence",\n'
        '                        "Re-add a forgotten source at exactly the next revision",\n',
        "P5",
    ),
    "no-forget-recovery-choice": Mutant(
        '                and json.loads(row.plan).get("operation") == "identity_forget"\n'
        '                and method != "forget"\n',
        '                and json.loads(row.plan).get("operation") == "identity_forget"\n'
        "                and False\n",
        "P5",
    ),
    "forget-from-any-failed-row": Mutant(
        "                if not (\n"
        '                    row.state == "current"\n'
        '                    or json.loads(row.plan).get("operation") == "identity_forget"\n'
        "                ):",
        "                if False:",
        "P5",
    ),
    "forget-takes-any-plan": Mutant(
        '                if plan.get("operation") != "identity_forget":\n',
        "                if False:\n",
        "P5",
    ),
    "complete-forgotten-as-withdrawn": Mutant(
        '        values = {"state": state}\n',
        '        values = {"state": "withdrawn" if state == "forgotten" else state}\n',
        "P1",
    ),
    "no-advance-guard": Mutant(
        "            if row and source.revision != actual_revision:\n"
        "                if not (\n"
        '                    (method == "replace" and row.state == "current")\n'
        '                    or method == "publish"\n'
        "                ):\n"
        "                    raise IntentError(\n"
        '                        "recovery_choice",\n'
        '                        "Advance a current revision through replacement",\n'
        "                    )\n",
        "",
        "P5",
    ),
    "advance-guard-ignores-method": Mutant(
        '                    (method == "replace" and row.state == "current")\n',
        '                    (row.state == "current")\n',
        "P5",
    ),
    "no-revision-reuse": Mutant(
        "                if json.loads(payload) != json.loads(row.description):\n"
        "                    raise IntentError(\n"
        '                        "revision_reuse", "Changed description requires a new revision"\n'
        "                    )\n",
        "                pass\n",
        "P5",
    ),
    "no-plus-one": Mutant(
        "            elif source.revision != actual_revision + 1:",
        "            elif source.revision <= actual_revision:",
        "P5",
    ),
    "no-replace-plan-check": Mutant(
        '                if plan.get("operation") != "identity_replace":\n',
        "                if False:\n",
        "P5",
    ),
    "no-replace-plan-preservation": Mutant(
        '                if row.state == "failed" and (\n'
        '                    prior_plan.get("operation") != "identity_replace"\n',
        "                if False and (\n"
        '                    prior_plan.get("operation") != "identity_replace"\n',
        "P5",
    ),
    "no-text-change-preservation": Mutant(
        '                    or plan.get("text_change") != prior_plan.get("text_change")\n',
        "",
        "P5",
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
    "failed-row-never-recoverable": Mutant(
        '            if row and row.state == "pending":',
        '            if row and row.state in ("pending", "failed"):',
        "P6",
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
        '            if row and row.state == "withdrawn" and method != "withdraw":',
        '            if row and row.state == "withdrawn" and method not in ("withdraw", "replace"):',
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
