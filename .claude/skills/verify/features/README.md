# Stage 6 identity verification map

This directory is the maintained source for verifying the user-facing behavior of the Stage 6 identity CLI. Read this index before you drive anything. Then use the matching feature file as the recipe.

Every journey names its guide under `docs/` and takes each expected value from that guide or from `docs/SESSION_HANDOFF.md`. A journey that disagrees with the code reports a failure. Do not weaken a journey to make it pass.

## Baseline preconditions

- Work from the repo root on a checkout where `uv sync --group dev` has run.
- Define the helper once per shell with `V=.claude/skills/verify/scripts/verify.py`.
- Run `$V doctor` and require `"ok": true`. The Cognee version must be `1.6.2`.
- Start each journey with its own `RUN=$($V new-run NAME)`. A journey never shares a run with another journey.
- Use the helper's run roots only. Never pass `--root` yourself and never use a root under `outputs/stage6_*`.
- Record the lab store before and after you run any journeys. Both values must be unchanged.
  - `stat -f %Sm .cognee_system/databases/cognee_db`
  - `ls .cognee_data | wc -l`
- Loopback journeys need no network and no `.env`. The one `env` journey (`P5` in the publication file) reads `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` from the repo `.env` and calls the embedding API.
- Do not touch `.cognee_data/`, `.cognee_system/` or the site-packages of `.venv`.

## Driving conventions

- Each journey is one fenced block labeled `bash journey ID`. The block is self-contained and runs top to bottom with `bash`. It ends with `$V cleanup "$RUN"`.
- Some journeys take a fault stage. Their block starts with `STAGE=${STAGE:-<first stage>}`. Run the block once per listed stage, each in its own run, with `STAGE=<stage> bash ...`.
- `$V drive` adds `--root`. For `fixture`, `multi-fixture` and `chunked-fixture` it also adds `--embedding loopback` unless the line passes `--embedding`. The `.cmd` evidence file records the effective command.
- Later commands read the profile from the root marker. They never take `--embedding`.
- Keep labels unique within a run. `$V check` reads the latest step with that label.
- `val LABEL 'JQ'` is a shell function in each block. It prints a value from that step's JSON so that a later check can compare across steps.
- A step that is meant to fail still runs through `drive`. The step exits 1, and a `check` on `.error` proves the failure.
- Read `retrieve` facts at `.facts`. Read every other command's facts at `.result.facts`. `status` returns only `.publications` and `.recovery_events`.
- Compare UUIDs only within one run.

## Proof and skip reporting

- Report the PASS and FAIL counts from `RUN/evidence/assertions.tsv` for every run. Quote each FAIL line.
- A passing journey proves that the lifecycle mechanics work through the real Ladybug, LanceDB and SQLite stores. Captured decisions do not prove extraction or search quality. Say so.
- A journey proves side effects, not only returned facts. That means revision triples, `recovery_events`, `unavailable_sources`, retired chunks and vectors, and a reopen in a new process.
- An injected fault has `origin: "test/fault_injection"`. It proves recovery mechanics only.
- If a precondition is unmet, report the command you tried and the precondition. Do not report the journey as verified through a different path.
- If `drive` shows `timeout` with `json=yes`, report the Linux teardown issue named in `SKILL.md`. Do not call it a pass or a fail.
- A feature the map does not list is not verified. A new feature adds its own journeys here when it lands.

## Features

- [Publication and retrieval](./publication-and-retrieval.md) covers `fixture`, `multi-fixture`, `chunked-fixture`, reopened `retrieve`, healthy `reconcile`, `status`, and a failed first publication with its recovery. One journey uses `--embedding env`.
- [Multi-source withdrawal](./multi-source-withdrawal.md) covers `withdraw` in both orders, repeated withdrawal, and a withdrawal fault with its retry.
- [Revision and text edits](./revision-and-text-edits.md) covers `revise` and `edit-text` on one chunk and on many chunks, with every documented fault stage and its recovery.
- [Occurrence changes](./occurrence-changes.md) covers `remove-occurrences`, `retire-resolved-group` and `add-occurrences`, each with its recovery case.

There is no separate failure-recovery file. Every fault journey lives with the feature that it breaks, so the recovery steps stay next to the happy path that they restore.

## Not yet supported

These are current refusals or gaps. They are not journeys. Do not write a journey that expects them to work.

- Group splits and combinations are not supported. This is the next task in `docs/SESSION_HANDOFF.md`.
- A single edit cannot mix occurrence removal and occurrence addition. Removal and addition modes do not combine (`docs/stage6_identity_occurrence_addition.md`).
- Representation-kind changes, new reusable identities in an addition, and changed interpretations are not supported.
- An edit that would affect a dependent saved identity source is refused before it changes anything. Automatic reconsideration of that source does not exist (`docs/stage6_identity_text_changes.md`).
- Arbitrary text edits are not supported. `edit-text` applies only the captured prefix insertion, and the removal, retirement and addition commands apply only their captured edits.
- Identity withdrawal is not a full source Forget. It keeps the original Data, its facts, markers and evidence.
- A root made before embedding profiles opens only for `status` and `retrieve`. Do not use one as a verification root.
- A hard process crash can leave the project writer reserved. The map covers only caught, injected failures.

Add a journey to the matching feature file when a new feature lands. Move an item out of this list when its refusal becomes a supported behavior.
