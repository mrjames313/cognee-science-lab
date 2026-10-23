---
name: verify
description: Drive the cognee-science-lab Stage 6 identity CLI (`python -m cognee_lab.identity`) end to end in fresh isolated fixture roots and capture JSON evidence. Use to prove a change to src/cognee_lab/identity works through the real Cognee 1.6.2 graph/vector/relational stores (publication, retrieval, maintenance edits, withdrawal, injected-failure recovery), not just that unit tests pass.
---

# Verify the Stage 6 identity CLI

> **Status: proven 2026-10-20 on Cognee 1.6.2.** The feature map in `features/` holds the journey blocks. Run counts and the paths each run exercised are in `docs/SESSION_HANDOFF.md`, subsection "Verification skill".

## What a user touches

The product surface is a CLI that writes to real Cognee stores (Ladybug graph, LanceDB vector, SQLite relational) inside a root directory you name, then prints one JSON document:

```bash
uv run python -m cognee_lab.identity <command> --root <dir> [--source doc01|doc02|glossary] [--expected-revision N] [--fault-stage STAGE] [--query TEXT]
```

Commands: `fixture`, `multi-fixture`, `chunked-fixture`, `glossary-fixture` (create a root, with `--embedding env|loopback`; `multi-fixture --dependent` makes doc02 consume doc01; `glossary-fixture` makes doc01 read a glossary entry), `revise`, `edit-text`, `remove-occurrences`, `retire-resolved-group`, `add-occurrences`, `split-group`, `combine-groups`, `reinterpret-new-entity`, `reinterpret-unresolved`, `change-kind-to-mention`, `change-kind-to-reusable`, `forget`, `readd`, `edit-glossary --case`, `reconfirm --decision`, `replace-decision --decision` (maintenance commands that need `--expected-revision`), `refresh-dependents`, `withdraw`, `retrieve`, `status`, `reconcile`. The fixtures use captured decisions and make no LLM call.

Other surfaces, not covered here: `main.py` is a stub. `scripts/stage1_*` to `stage5_*` are historical lab experiments that need API keys and the shared lab store. Do not drive them for verification. `uv run pytest` is the test suite. It complements this skill and does not replace it.

Read `docs/SESSION_HANDOFF.md` before you verify a behavior change. It says which outcomes are current and what each checkpoint claims.

## Hard rules

- **Never pass a `--root` under `outputs/stage6_*` or any other existing directory.** Those are the user's reviewed stores. The helper below always builds the root path itself under `outputs/verify/<run>/roots/`, so use it.
- Run one CLI process per root at a time. Commands on one root run sequentially. Separate runs can run in parallel, and each CLI picks its own free loopback port. Do not drive two roots of one run in parallel, because step numbers come from a count of the run's evidence files and can collide.
- Fixture commands refuse an existing root. To re-run a journey, start a new run.

## Helper

`.claude/skills/verify/scripts/verify.py` (executable, runs itself through `uv run`). From the repo root:

```bash
V=.claude/skills/verify/scripts/verify.py
$V journey ID [--stage S] [--include-env] [--jobs N]  # run one journey block, clean up, print PASS/FAIL counts
$V journey all [--include-env] [--jobs N]  # run every journey block, print a summary table
$V new-run NAME                      # prints outputs/verify/<UTC stamp>-NAME
$V doctor [RUN]                      # read-only health check, JSON, exit 1 on a failing gate
$V drive RUN ROOT LABEL -- CMD ARGS  # runs: uv run python -m cognee_lab.identity CMD ARGS --root RUN/roots/ROOT
$V check RUN LABEL 'JQ' 'what it proves'   # jq -e over that step's JSON, logged PASS/FAIL
$V val RUN LABEL 'JQ'                # prints jq -r over that step's JSON, for a later check
$V probe RUN ROOT LABEL              # records marker, data files, vector widths and a key-leak scan as a step
$V cleanup RUN                       # deletes RUN/roots (stores), keeps RUN/evidence, guards the lab store
```

**Loopback default.** The CLI creation default is `--embedding env`, which calls the embedding API named in the repo `.env`. `drive` adds `--embedding loopback` to `fixture`, `multi-fixture` and `chunked-fixture` unless the line supplies `--embedding` or an abbreviation of it. A journey costs nothing unless it asks for `env`. The `.cmd` evidence file records the effective command. A hand-typed command without the flag calls the embedding API.

`drive` exits with the CLI's status (0 ok, 1 CLI error or timeout) and prints one line: step number, exit, seconds, whether JSON was found. Its default timeout is 600 s. Pass `--timeout N` before `--`. On timeout it kills only the process it started and records `timeout`.

`journey` finds the block `bash journey ID` in `features/*.md`. It creates one run per journey, or one per stage, and exports `V`, `RUN` and `STAGE`. It defines `val` as a shell function and runs the block with `bash`. Then it runs cleanup and prints the PASS and FAIL counts from `assertions.tsv`. The block output goes to `evidence/journey.log`. A journey that lists stages runs every stage unless you pass `--stage`. `journey all` skips journeys that call the embedding API unless you pass `--include-env`. A named env journey also needs `--include-env`. Blocks have no branches, so the runner expects one row per `$V check` line. A run with fewer rows, or a bash syntax error, gets a FAIL row. The command exits 1 on any FAIL row. `--jobs N` runs N journey runs at once (default 4, or 1 with `--include-env`, so env journeys do not hit the embedding API together). On a 10-core Mac, 4 jobs ran about 3x faster than 1. Each run has its own directory, roots, stores and loopback port, but every run checks the lab-store fingerprint. If a `lab_store` check fails under `--jobs` above 1, rerun with `--jobs 1` to find the journey. The summary table keeps definition order. On macOS, `journey` also starts `caffeinate -i -w <its pid>` to prevent idle sleep. On 2026-10-21 an unattended run's steps dropped from about 40 s to about 4 s after caffeinate started. The cause is unproven.

## Launch

There is no server. "Launch" is:

```bash
uv sync --group dev
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run my-journey)
$V doctor "$RUN"
$V drive "$RUN" main fixture -- chunked-fixture
```

Ready means the fixture step printed `exit=0 ... json=yes` and `$V check "$RUN" fixture '[.sources[].state] == ["current","current"]'` passes. On this Mac each command takes about 3 to 15 s, including a cold import.

To prove the NVIDIA embedding path, run `$V journey P5 --include-env`. It costs a few API calls and needs `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` in the repo `.env`. No other journey uses `env`.

## Doctor

Run `$V doctor [RUN]` first, and again when a step behaves strangely. Require `"ok": true` and read `warnings`. Doctor is read-only. It never imports Cognee, because the import loads the lab `.env`. It stops at any Cognee version except `1.6.2`, the only tested profile, and you then stop and report. A failing gate exits 1. Informational fields and warnings never fail it, and a missing tokenizer fix is a warning.

## Drive

Pick the journey from `features/README.md`. Run it with `$V journey ID`. To explore by hand, use the same `drive` and `check` lines that the block holds. The pattern:

```bash
$V drive "$RUN" main add -- add-occurrences --source doc01 --expected-revision 1
$V check "$RUN" add '.result.facts | length == 3' 'three facts after addition'
```

Stable handles are JSON field paths (`.result.facts`, `.sources.doc01.saved_revision`, `.text_changes[0].groups.g03`, `.recovery_events`, `.unavailable_sources`) and the fixture group keys `g01`/`g02`/`g03` and sources `doc01`/`doc02`/`glossary`. UUIDs differ per root. Compare IDs only within one run.

Output-shape gotchas:

- `fixture`/`multi-fixture`/`chunked-fixture` print Cognee log lines ("... table already exists, skipping creation") to stdout before the JSON. `drive` extracts the JSON. Do not `jq` the raw `.stdout`.
- `retrieve` returns facts at top level (`.facts`). Fixture, maintenance and `reconcile` return them under `.result.facts`. `status` returns `.publications`, `.recovery_events`, `.withholdings`, `.withheld_decisions` and `.refresh_needed`. A glossary root's commands write `glossary_result.json` and print the same document.
- `.sources` is keyed `doc01`/`doc02`. `status` `.publications[].source` is an identity-data UUID, not `doc01`.
- An injected `--fault-stage` failure exits 1. It prints `{"error": "IntentError", "message": "... recovery_event_id=<uuid>"}` on stdout and a rich traceback on stderr. That is the expected result for a failure journey, so check for it and do not treat it as a broken run.

## Evidence

Everything lands in `RUN/evidence/`:

- `NN-LABEL.cmd`: the exact CLI command line.
- `NN-LABEL.stdout`, `.stderr`, `.json`: raw output and the extracted JSON document. A `probe` step writes only `.cmd` and `.json`.
- `steps.tsv`: step, label, root, exit, seconds, json-found.
- `assertions.tsv`: PASS/FAIL, file, jq filter, description. A `check` on a step with no JSON writes a FAIL row.
- `journey.log`: the output of a `journey` block.
- `root-files/<root>/` (written by cleanup): the result/review files the CLI writes at the top of a root (`*_result.json`, `identity*.json`, `source*.txt`, `fixture-info.json` …).
- `../run.json`: git HEAD, whether the worktree was dirty, and the lab-store fingerprint.

Proof standards:

- Drive the CLI commands a user runs. Don't call internal Python functions or test helpers as proof.
- Capture each action and the state that follows it: the maintenance step's JSON, then a separate `retrieve` and `status`. One final screen doesn't prove the steps before it.
- Check side effects, not only the returned facts. These are revision triples (`saved/registered/verified`), `recovery_events` empty or resolved, `unavailable_sources`, retired chunks and vectors absent (`.text_changes[0].retired_chunks_absent`, `retired_chunk_vectors_absent`), and the files the command writes into the root.
- A reopened `retrieve` in a new process must return the same facts. That separates persisted state from in-process state.
- `--fault-stage` is a deliberate test-only failure injection. Its incident has `origin: "test/fault_injection"`. It proves recovery mechanics only.
- Captured decisions prove lifecycle mechanics, with either embedding profile. They don't prove extraction or search quality. Say so in any report.
- `cleanup` compares the lab stores with the fingerprint that `new-run` saved. The fingerprint is the newest modification time and the file count under `.cognee_system` (relational, graph, vector and SQLite `-wal` files), plus the `.cognee_data` file count. It logs three PASS or FAIL rows. A FAIL means something wrote to the lab store.
- Report the counts from `assertions.tsv` and quote the FAIL lines. Never weaken a `check` to make it pass. If an expectation is wrong, show why, with the guide line it came from.

## Cleanup

`$V journey` cleans up by itself. After a manual run, use:

```bash
$V cleanup "$RUN"
```

Cleanup refuses while any identity CLI is still running against the run. It copies each root's top-level files into `evidence/root-files/`, then deletes `RUN/roots/`. It records the lab-store guard rows and exits 1 on a FAIL. It never touches anything outside `outputs/verify/<run>/`. Evidence stays at `outputs/verify/<run>/evidence/`, which git ignores. Delete old runs yourself when you no longer need them. Run cleanup after failed attempts too.

## Limits to report honestly

- Mac runs exit cleanly. The handoff records a Linux host where ordinary CLI teardown exceeded 300 s after printing correct JSON. If `drive` shows `timeout` with `json=yes`, report it as that teardown issue. Do not report it as a functional pass or fail.
- Doctor prints each root's marker record, which includes the embedding model name and dimension count. Those are not secrets. It never prints other `.env` values.
- Journey `P5` proves the `env` profile only for the `.env` that the handoff names (`nvidia/nemotron-3-embed-1b`, 2048 dimensions). A different `.env` fails its marker check by design. Report that as a mismatch.
- Native pytest (`uv run pytest -q -m integration`) takes minutes per sequence and uses `support/host_native_launcher.py` only on that Linux host. It is not part of this skill.
