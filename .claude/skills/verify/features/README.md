# Stage 6 identity verification map

This directory is the maintained source for verifying the user-facing behavior of the Stage 6 identity CLI. Read this index before you drive anything. Then use the matching feature file as the recipe.

Every journey names its guide under `docs/` and takes each expected value from that guide or from `docs/SESSION_HANDOFF.md`. A journey that disagrees with the code reports a failure. Do not weaken a journey to make it pass.

## Baseline preconditions

- Work from the repo root on a checkout where `uv sync --group dev` has run.
- Define the helper once per shell with `V=.claude/skills/verify/scripts/verify.py`.
- Run `$V doctor` and require `"ok": true`. The Cognee version must be `1.6.2`.
- Run a journey with `$V journey ID`. The runner gives each journey, and each stage, its own run. By hand, start each journey with its own `RUN=$($V new-run NAME)`.
- Use the helper's run roots only. Never pass `--root` yourself and never use a root under `outputs/stage6_*`.
- `cleanup` compares the lab stores with the fingerprint that `new-run` saved and logs the result in `assertions.tsv`. Do not touch `.cognee_data/`, `.cognee_system/` or the site-packages of `.venv`.
- Only `P5` needs `.env`. It reads `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` and calls the embedding API, so `journey all` skips it unless you pass `--include-env`.

## Feature entry contract

Each feature file lists its sub-features and holds one bold-led paragraph per journey. The paragraph names the sub-features that the journey proves, cites its guide, and states the expected values with the guide line that gives each one. A journey that disagrees with its guide reports a failure.

- **Fence.** A journey is a fenced block with the info string `bash journey ID [stages=a,b,c] [env]`. The block holds only `drive`, `check` and shell lines. It never defines `V`, `RUN`, `val` or a cleanup.
- **Stages.** `stages=` lists the fault stages. The runner sets `STAGE` for each one, in its own run. `--stage S` runs one.
- **env.** The `env` token marks a journey that calls the embedding API.
- **ID letters.** `P` is publication and retrieval, `W` is withdrawal, `R` is revision, `E` is text edits, `O` is occurrence changes, `G` is group regrouping, `I` is changed interpretation and `K` is kind change. The `E` journeys live in the revision file, and the `I` and `K` journeys live in the reinterpretation file.
- **Fault journeys.** A fault journey lives with the feature that it breaks.
- **Cited values.** Every expected value comes from a guide under `docs/` or from `docs/SESSION_HANDOFF.md`. An inference from a guide says so in the paragraph.
- **Non-vacuous checks.** A check on a field requires the field to exist. Use `length > 0`, a type test or `!= null` where a missing field would otherwise pass.

## Driving conventions

- The runner exports `V`, `RUN` and `STAGE` and defines `val LABEL 'JQ'`. `val` prints a value from that step's JSON so that a later check can compare across steps.
- `$V drive` adds `--root`. Later commands read the profile from the root marker and never take `--embedding`.
- Keep labels unique within a run. `$V check` reads the latest step with that label.
- A step that is meant to fail still runs through `drive`. The step exits 1, and a `check` on `.error` proves the failure.
- Read `retrieve` facts at `.facts`. Read every other command's facts at `.result.facts`. `status` returns only `.publications` and `.recovery_events`.
- Compare UUIDs only within one run.
- The `replace_published` stage records its incident under a stage named `replacement_cleanup`. Do not assert the incident `stage` field against the flag value.

## Proof and skip reporting

- Report the PASS and FAIL counts from `RUN/evidence/assertions.tsv` for every run. Quote each FAIL line. `$V journey` prints them.
- A passing journey proves that the lifecycle mechanics work through the real Ladybug, LanceDB and SQLite stores. `SKILL.md` says what captured decisions do not prove.
- A journey proves side effects, not only returned facts. That means revision triples, `recovery_events`, `unavailable_sources`, retired chunks and vectors, and a reopen in a new process.
- An injected fault has `origin: "test/fault_injection"`. It proves recovery mechanics only.
- If a precondition is unmet, report the command you tried and the precondition. Do not report the journey as verified through a different path.
- If `drive` shows `timeout` with `json=yes`, report the Linux teardown issue named in `SKILL.md`. Do not call it a pass or a fail.
- A feature the map does not list is not verified. A new feature adds its own journeys here when it lands.

## Features

- [Publication and retrieval](./publication-and-retrieval.md) covers `fixture`, `multi-fixture`, `chunked-fixture`, reopened `retrieve`, healthy `reconcile`, `status`, and a failed first publication with its recovery. One journey uses `--embedding env`.
- [Multi-source withdrawal](./multi-source-withdrawal.md) covers `withdraw` in both orders, repeated withdrawal, and a withdrawal fault with its retry.
- [Revision and text edits](./revision-and-text-edits.md) covers `revise` and `edit-text` on one chunk and on many chunks, with every documented fault stage and its recovery.
- [Occurrence changes](./occurrence-changes.md) covers `remove-occurrences`, `retire-resolved-group`, `add-occurrences` and `revise-occurrences`, each with its recovery case.
- [Group regrouping](./group-regrouping.md) covers `split-group` and `combine-groups`, each with its `replace_published` recovery case.
- [Reinterpretation](./reinterpretation.md) covers `reinterpret-new-entity`, `reinterpret-unresolved`, `change-kind-to-mention` and `change-kind-to-reusable`, their recovery cases and their scope refusals.

There is no separate failure-recovery file. Every fault journey lives with the feature that it breaks, so the recovery steps stay next to the happy path that they restore.

## Not yet supported

These are current refusals or gaps. They are not journeys. Do not write a journey that expects them to work.

- Mixed removal and addition has one captured case, `revise-occurrences`. Commands do not locate arbitrary phrases or infer an occurrence map (`docs/stage6_identity_mixed_occurrences.md`).
- Changed interpretation and representation-kind changes work only as the four captured commands `reinterpret-new-entity`, `reinterpret-unresolved`, `change-kind-to-mention` and `change-kind-to-reusable`. Other kind changes, other changed interpretations, a corpus-scoped variant change in a text edit and a retargeted continuing group in a text edit stay refused (`docs/stage6_identity_reinterpretation.md`).
- An edit that would affect a dependent saved identity source is refused before it changes anything. Automatic reconsideration of that source does not exist (`docs/stage6_identity_text_changes.md`).
- Arbitrary text edits are not supported. `edit-text` applies only the captured prefix insertion, and the removal, retirement, addition, split and combination commands apply only their captured edits (`docs/stage6_identity_group_split.md` for the last two).
- Identity withdrawal is not a full source Forget. It keeps the original Data, its facts, markers and evidence.
- A root made before embedding profiles opens only for `status` and `retrieve`. Do not use one as a verification root.
- A hard process crash can leave the project writer reserved. The map covers only caught, injected failures.

Add a journey to the matching feature file when a new feature lands. Move an item out of this list when its refusal becomes a supported behavior.
