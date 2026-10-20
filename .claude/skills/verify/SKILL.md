---
name: verify
description: Drive the cognee-science-lab Stage 6 identity CLI (`python -m cognee_lab.identity`) end to end in fresh isolated fixture roots and capture JSON evidence. Use to prove a change to src/cognee_lab/identity works through the real Cognee 1.6.2 graph/vector/relational stores — publication, retrieval, maintenance edits, withdrawal, injected-failure recovery — not just that unit tests pass.
---

# Verify the Stage 6 identity CLI

> **Status: DRAFT (updated 2026-10-20).** The `.env` override that blocked this skill is fixed: each root keeps its stores inside the root and records its embedding profile (`--embedding env|loopback`). See "Resolved" in `docs/SESSION_HANDOFF.md`. `drive` and `doctor` predate that fix and do not pass `--embedding` yet. The feature map (`features/README.md`) and the end-to-end proof run are unfinished.

## What a user touches

The product surface is a CLI that writes to real Cognee stores (Ladybug graph, LanceDB vector, SQLite relational) inside a root directory you name, then prints one JSON document:

```bash
uv run python -m cognee_lab.identity <command> --root <dir> [--source doc01|doc02] [--expected-revision N] [--fault-stage STAGE] [--query TEXT]
```

Commands: `fixture`, `multi-fixture`, `chunked-fixture` (create a root), `revise`, `edit-text`, `remove-occurrences`, `retire-resolved-group`, `add-occurrences` (maintenance; need `--expected-revision`), `withdraw`, `retrieve`, `status`, `reconcile`. The fixtures use captured decisions and make no LLM call. Creation defaults to `--embedding env`, which calls the embedding API named in the repo `.env`. Pass `--embedding loopback` for the offline deterministic server the CLI starts itself.

Other surfaces, not covered here: `main.py` is a stub; `scripts/stage1_*`–`stage5_*` are historical lab experiments that need API keys and the shared lab store. Do not drive them for verification. `uv run pytest` is the test suite, which is a complement to this skill, not a substitute for it.

Read `docs/SESSION_HANDOFF.md` before verifying a behavior change; it says which outcomes are current and what each checkpoint claims.

## Hard rules

- **Never pass a `--root` under `outputs/stage6_*` or any other existing directory.** Those are the user's reviewed stores. The helper below always builds the root path itself under `outputs/verify/<run>/roots/`, so use it.
- One CLI process per root at a time. Commands on one root run sequentially; separate roots can run in parallel (each CLI picks its own free loopback port).
- Fixture commands refuse an existing root. To re-run a journey, start a new run.

## Helper

`.claude/skills/verify/scripts/verify.py` (executable, runs itself through `uv run`). From the repo root:

```bash
V=.claude/skills/verify/scripts/verify.py
$V new-run NAME                      # prints outputs/verify/<UTC stamp>-NAME
$V doctor [RUN]                      # read-only health check, JSON, exit 1 on any problem
$V drive RUN ROOT LABEL -- CMD ARGS  # runs: uv run python -m cognee_lab.identity CMD ARGS --root RUN/roots/ROOT
$V check RUN LABEL 'JQ' 'what it proves'   # jq -e over that step's JSON, logged PASS/FAIL
$V cleanup RUN                       # deletes RUN/roots (stores), keeps RUN/evidence
```

`drive` exits with the CLI's status (0 ok, 1 CLI error or timeout) and prints one line: step number, exit, seconds, whether JSON was found. Its default timeout is 600 s; pass `--timeout N` before `--`. On timeout it kills only the process it started and records `timeout`.

## Launch

There is no server. "Launch" is:

```bash
uv sync --group dev
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run my-journey)
$V doctor
$V drive "$RUN" main fixture -- chunked-fixture
```

Ready means the fixture step printed `exit=0 ... json=yes` and `$V check "$RUN" fixture '[.sources[].state] == ["current","current"]'` passes. On this Mac each command takes about 3–15 s, including a cold import.

## Doctor

`$V doctor RUN` checks, read-only: repo root, Python 3.12, Cognee import reports exactly `1.6.2` (the only tested profile; anything else means stop and report), `jq` present, CLI argument parsing works, every root in the run carries the `stage6-fixture.json` marker, and no identity CLI process is still running against the run. Run it first and again whenever a step behaves strangely.

## Drive

Pick the journey from `features/README.md`; each feature file lists the exact `drive` and `check` lines. The pattern:

```bash
$V drive "$RUN" main add -- add-occurrences --source doc01 --expected-revision 1
$V check "$RUN" add '.result.facts | length == 3' 'three facts after addition'
```

Stable handles are JSON field paths (`.result.facts`, `.sources.doc01.saved_revision`, `.text_changes[0].groups.g03`, `.recovery_events`, `.unavailable_sources`) and the fixture group keys `g01`/`g02`/`g03` and sources `doc01`/`doc02`. UUIDs differ per root; compare IDs only within one run.

Output-shape gotchas:

- `fixture`/`multi-fixture`/`chunked-fixture` print Cognee log lines ("... table already exists, skipping creation") to stdout before the JSON. `drive` extracts the JSON; don't `jq` the raw `.stdout`.
- `retrieve` returns facts at top level (`.facts`); fixture, maintenance and `reconcile` return them under `.result.facts`. `status` returns `.publications` and `.recovery_events` only.
- `.sources` is keyed `doc01`/`doc02`; `status` `.publications[].source` is an identity-data UUID, not `doc01`.
- An injected `--fault-stage` failure exits 1, prints `{"error": "IntentError", "message": "... recovery_event_id=<uuid>"}` on stdout and a rich traceback on stderr. That is the expected result for a failure journey, so check for it rather than treating it as a broken run.

## Evidence

Everything lands in `RUN/evidence/`:

- `NN-LABEL.cmd`: the exact CLI command line.
- `NN-LABEL.stdout`, `.stderr`, `.json`: raw output and the extracted JSON document.
- `steps.tsv`: step, label, root, exit, seconds, json-found.
- `assertions.tsv`: PASS/FAIL, file, jq filter, description.
- `root-files/<root>/` (written by cleanup): the result/review files the CLI writes at the top of a root (`*_result.json`, `identity*.json`, `source*.txt`, `fixture-info.json` …).
- `../run.json`: git HEAD and whether the worktree was dirty.

Proof standards:

- Drive the CLI commands a user runs. Don't call internal Python functions or test helpers as proof.
- Capture each action and the state that follows it: the maintenance step's JSON, then a separate `retrieve` and `status`. One final screen doesn't prove the steps before it.
- Check side effects, not only the returned facts: revision triples (`saved/registered/verified`), `recovery_events` empty or resolved, `unavailable_sources`, retired chunks/vectors absent (`.text_changes[0].retired_chunks_absent`, `retired_chunk_vectors_absent`), and the files the command writes into the root.
- A reopened `retrieve` in a new process must return the same facts. That separates persisted state from in-process state.
- `--fault-stage` is a deliberate test-only failure injection; its incident has `origin: "test/fault_injection"`. It proves recovery mechanics only.
- Captured decisions prove lifecycle mechanics, with either embedding profile. They don't prove extraction or search quality. Say so in any report.
- Report the counts from `assertions.tsv` and quote the FAIL lines. Never weaken a `check` to make it pass. If an expectation is wrong, show why, with the guide line it came from.

## Cleanup

```bash
$V cleanup "$RUN"
```

Cleanup refuses while any identity CLI is still running against the run, copies each root's top-level files into `evidence/root-files/`, then deletes `RUN/roots/`. It never touches anything outside `outputs/verify/<run>/`. Evidence stays at `outputs/verify/<run>/evidence/`, which git ignores. Delete old runs yourself when they're no longer needed. Run cleanup after failed attempts too.

## Limits to report honestly

- Mac runs exit cleanly. The handoff records a Linux host where ordinary CLI teardown exceeded 300 s after printing correct JSON. If `drive` shows `timeout` with `json=yes`, report it as that teardown issue, not as a functional pass or fail.
- Native pytest (`uv run pytest -q -m integration`) takes minutes per sequence and uses `support/host_native_launcher.py` only on that Linux host. It is not part of this skill.
