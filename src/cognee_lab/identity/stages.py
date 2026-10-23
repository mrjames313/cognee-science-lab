"""The frame that replace, withdraw and forget share around one attempt.

Each operation reads its saved row and chooses its plan. `run_attempt` then
begins the attempt, runs its ordered stages with their fault injection,
completes it, and records a recovery event for a failure.
"""

from collections.abc import Awaitable, Callable, Iterable
from typing import NamedTuple

from .models import IdentitySource
from .validation import IntentError


class Operation(NamedTuple):
    method: str  # the RecordStore.begin() method
    label: str  # names the operation in a recovery_record_failed message
    faults: tuple[str, ...]  # fault stage names it accepts, in order
    # complete(state=...) after the last stage, or None when a stage completes
    # the attempt itself.
    state: str | None


class Run:
    """The begun attempt as its stages see it, and the stage it reached."""

    def __init__(self, attempt: str, fault_stage: str | None):
        self.attempt = attempt
        self.fault_stage = fault_stage
        self.stage: str | None = None

    def inject(self, name: str):
        """Fail here when the requested fault stage names this point."""
        if self.fault_stage == name:
            raise IntentError("injected_failure", f"Injected failure at {name}")

    async def boundary(self, name: str):
        """Reach a named point inside a stage: record it, and fail there on request."""
        self.stage = name
        self.inject(name)


Stage = tuple[str, Callable[[Run], Awaitable]]


async def saved_row(records, source, missing, exact=None):
    """The source's saved row, refused when it is missing or, given `exact`,
    when its description is not this one."""
    row = await records.row(source)
    if row is None:
        raise IntentError("source_missing", missing)
    if exact and IdentitySource.model_validate_json(row.description) != source:
        raise IntentError("revision_reuse", exact)
    return row


async def run_attempt(
    operation: Operation,
    records,
    source,
    plan,
    stages: Iterable[Stage],
    *,
    expected_revision,
    origin,
    fault_stage,
):
    """Begin the attempt and run the stages in order. A fault stage that names
    a stage in `operation.faults` fails the attempt right after that stage's
    work. Return the attempt id and each stage's result by name."""
    attempt = await records.begin(
        source,
        expected_revision=expected_revision,
        plan=plan,
        method=operation.method,
        origin=origin,
    )
    run = Run(attempt, fault_stage)
    results = {}
    try:
        for name, work in stages:
            run.stage = name
            results[name] = await work(run)
            if name in operation.faults:
                run.inject(name)
        if operation.state is not None:
            await records.complete(source, attempt, state=operation.state)
        return attempt, results
    except Exception as exc:
        if getattr(exc, "code", None) == "recovery_required":
            raise
        try:
            event = await records.fail(source, attempt, run.stage, exc, origin=origin)
        except Exception as diagnostic_error:
            raise IntentError(
                "recovery_record_failed",
                f"{operation.label} unavailable: attempt={attempt}, stage={run.stage}, "
                f"error={exc}; recovery-event write also failed: {diagnostic_error}",
            ) from diagnostic_error
        raise IntentError(
            "recovery_required", f"{exc}; recovery_event_id={event}"
        ) from exc
