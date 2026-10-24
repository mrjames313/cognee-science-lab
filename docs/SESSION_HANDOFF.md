# Session handoff — resume here

**Updated:** 2026-10-24 (America/Detroit). **Current work:** Stage 6, accepted implementation step 4 / M3, partially complete. The user approved one general occurrence map on 2026-10-21, to replace the three admission modes. All three checkpoints are complete: A (the general admitter and its proof), B (every text change switched to the general map, old modes deleted) and C (the captured mixed addition and removal case). On 2026-10-22 Checkpoint D folded the unchanged-text correction into the same admission and relaxed its recipe and document-variant rules, Checkpoint E added four changed-interpretation and kind-change fixtures, and Checkpoint F added `forget` and `readd` for a source nothing depends on. A no-behavior-change refactor of the ledger and the retiring operations followed. On 2026-10-23 Checkpoint H, the first dependencies checkpoint (step-4 item 3), made a text edit of a consumed document withhold from retrieval only the dependents' decisions that read what changed, until they are refreshed or re-confirmed. Later on 2026-10-23 Checkpoint I made `forget` an erasure. It accepts any source, leaves a tombstone of identifiers and, after the caller confirms a dry run, removes the decisions of other sources that cited the forgotten source. The re-add follow-ups F1 and F2 landed on `main` the same day. Also on 2026-10-23 Checkpoint J1, the first chains checkpoint, let a decision cite another source's decision and withholds the citing decision whenever what it cites is withheld, changed or gone, down the whole chain. On 2026-10-24 Checkpoint J2 made a forget cascade down that chain, level by level, under one dry run, one token and one confirmation, and the user decided the kind-change, Entity-edit, facts and non-identity questions. Later on 2026-10-24 Checkpoint K answered what happens to the readers of an Entity or a saved record that changed or went. It added a lab `edit-entity` command and reviewer paths for an Entity input, `replace-citation` for a citer of a removed record, the refusals `record_key_reused` and `mention_input`, and kind changes on a root where other sources read doc01. **Next task:** no step-4 item can start without the user. See [Next task](#next-task). This document records the current continuation state; dated experiment writeups describe their own checkpoints.

## Objective and reading order

Develop a method to integrate structured knowledge into Cognee. The method has four operations: **Describe, Publish, Maintain and Retrieve**. Identity is the first worked example. Use the demonstrated mechanisms and tests when examining other domains, including scientific measurements. Keep each domain's meaning and rules explicit. This implementation does not provide scientific justification or scientific reasoning.

Read this document first, then:

1. [ROADMAP.md](../ROADMAP.md): project stages and current scope.
2. [Stage-6 architecture/contract](../results/cognee_identity_stage6_handoff.md): physical representation, ownership, continuity, recovery and original six-step build order. Its dated implementation subsections are checkpoint history.
3. [R1–R6 requirements](../results/cognee_stage5_4_5_requirements_review.md): outcome constraints, not a claim of complete coverage.
4. [Latest fixture guide](stage6_identity_entity_edits.md), the [cascade](stage6_identity_forget.md#the-cascade) and the [chains guide](stage6_identity_chains.md), followed by the earlier guides linked below for individual commands.
5. [Integration playbook](../results/cognee_knowledge_integration_playbook.md): findings tagged with Describe/Publish/Maintain/Retrieve and transfer questions for other integrations.

The [representation decision record](../results/cognee_stage5_4_5_identity_representation_proposal.md) and [pinned native extension reference](../results/cognee_extension_architecture_reference_v1.6.2.md) explain rationale and native behavior. Do not treat their early dated “next” or “not implemented at that checkpoint” statements as current implementation status. The roadmap and this handoff identify current work; later explicit approved scope changes supersede earlier proposals.

## Code baseline and delivery status

Runtime code is in `src/cognee_lab/identity/`. The implementation admits every text change through one **general occurrence map** (`admit` in `admission.py`), which covers the captured prefix edits, removals, additions, split, combination and one mixed edit. Since 2026-10-22 the unchanged-text correction goes through the same `admit`, by way of `admit_replacement` in `replace.py`. The map refuses a changed resolution or meaning, a change of representation kind, a move to another document and span-scoped variants. Since 2026-10-23 a text edit of a document that another source read is admitted: it withholds the dependents' decisions that read what changed (see [Checkpoint H](#dependencies-decided-and-built-2026-10-23)). Since Checkpoint I (2026-10-23) `forget` erases a source of any state and removes the dependents' decisions that cite it (see [Checkpoint I](#erasure-decided-and-built-2026-10-23)). Since Checkpoint J1 (2026-10-23) a decision may cite another source's resolution or variant assignment, and withholding spreads down the chain of citations (see [Checkpoint J1](#chains-j1-decided-and-built-2026-10-23)). Since Checkpoint J2 (2026-10-24) a forget removes every level of that chain under one confirmed dry run (see [Checkpoint J2](#cascade-j2-built-2026-10-24)). Since Checkpoint K (2026-10-24) a reviewer can answer a decision withheld by an edited Entity or by a removed record, a cited record key cannot come back with another meaning, no corpus input may name a mention UUID, and a kind change runs where other sources read the changed document (see [Checkpoint K](#readers-of-a-changed-or-retired-entity-or-record-k-built-2026-10-24)). The implementation does not include automatic Describe, facts as citable records or a standard-entry-point extension. The general-map update changed admission, the saved text-change plan, result JSON, the captured describers, a CLI command, the ledger model, verify journeys and tests. The saved-source schema and dependencies are unchanged.

The user's Mac addition, reopened retrieval, healthy reconcile and `replace_published` failure/recovery outputs have been reviewed. The user approved the split and combination case and the general occurrence map on 2026-10-21, and the mixed case on the same day. The assistant and its subagents verified their implementation on the user's Mac with loopback embeddings. This handoff records no user-reviewed fixture roots for them. [Next task](#next-task) gives the next task.

Generation began from lab checkout commit `5a179881b4314ba458ed2836fc3d7e78edae8169`. Later code was first delivered as patches. That hash identifies only the generation base. The code and documents are now committed.

Before branch `docs/handoff-2026-10-21`, `main` was at `c3becf2` and in sync with `origin/main`. GitHub Actions `unit-tests` passed on `c3becf2` with 143 passed and 29 deselected. The work after `ccc85d6` landed on `main` by local `git merge --ff-only` merges after `/pstack:thermos` reviews. No pull requests were opened. That work is:

- The `.env` fix and per-root embedding profiles (2026-10-20). See [the resolved `.env` issue](#resolved-the-repository-env-overrode-the-fixture-profile).
- The build fix (2026-10-20). `pyproject.toml` misspelled the key as `build_backend`, so the build used setuptools. It now sets `build-backend = "uv_build"` and requires `uv_build>=0.12,<0.13`. Git no longer tracks the `*.egg-info/` directory and ignores it. The `pytest-timeout` dependency is removed.
- The project verify skill and its journeys (2026-10-20 to 2026-10-21).
- The identity-ledger check (2026-10-21).
- The unit-test workflow and the landing playbook.

Branch `stage6-group-combine` (2026-10-21) adds the captured group split and combination, the fresh-ID rule and the revised verification routine. It lands through the same playbook.

Branch `stage6-dependencies` (2026-10-23) adds Checkpoint H on top of `main` at `a1e781c`: the withholding table, per-decision validation, admission rule 5 for other documents' inputs, the refresh after an edit, the reviewer commands and the glossary fixture. It landed through the same playbook; `main` is at `012d8a6` with its docs.

Branch `stage6-erasure` (2026-10-23) adds Checkpoint I on top of `main` at `012d8a6`: the tombstone and scrubs, the impact report with its dry run and token, the dependents' removal revisions and their admission rules, forget of a withdrawn source and of a failed first publication, re-add from the caller's files, and the erasure retry of a dependent's failed attempt. It has 20 commits: the implementation, then three fix rounds. It landed through the same playbook.

Branch `stage6-readd-followups` (2026-10-23) closes follow-ups F1 and F2 and landed through the same playbook. `main` is at `497ba58`.

Branch `stage6-chains` (2026-10-23) adds Checkpoint J1 on top of `main` at `497ba58`: the saved-record registry and citation format, the citation admission rules and the cycle refusal, withholding down the chain, the reviewer commands for saved records, the chain fixture, `support/chain_check.py` and journeys D7 to D11. It has 11 commits: the implementation (6 commits, to `637bfcc`), fix round 1 (4 commits, to `8167c25`) and a wording fix (`2002a77`). It landed through the same playbook; `main` is at `17a2467` with its docs.

Branch `stage6-cascade` (2026-10-24) adds Checkpoint J2 on top of `main` at `17a2467`: the erasure cascade by level, the removal producer's `removed_records` and `cited_records` with their inductive binding, immutable removal producers, the fence over every level, the `cascade_unfinished` refusal, the cascade half of the chain check (`support/cascade_check.py`) and journeys F16 to F20. It has 25 commits to `74ec093` and a docs commit: the implementation (5 commits, to `231c2e6`) and four fix rounds. It landed through the same playbook; `main` is at `a4cc0d5` with its docs. `9c6f16e` then moved the chain check to its own CI job, `chains`.

Branch `stage6-entity-edits` (2026-10-24) adds Checkpoint K on top of `main` at `9c6f16e`: `edit-entity`, review by input kind, `replace-citation`, `record_key_reused`, `mention_input`, kind changes on a glossary root and journeys D12 to D16 and K6 to K9. It has 13 commits to `514c0bb`, plus this docs commit: the implementation (4 commits, to `3237563`), fix round 1 (5 commits, to `94d54bb`), fix round 2 (3 commits, to `5e0c314`) and a docstring wrap. It lands through the same playbook. After its `--ff-only` merge, `main` is the baseline for the next task.

[Verification and landing](#verification-and-landing) describes the tools and the landing steps.

The following patch order records past deliveries. Use it only to reconstruct an older checkout:

1. Main-compatible initial implementation: `stage6_main_5a17988.patch` (an earlier initial delivery was named `stage6_initial.patch`; do not apply both).
2. `stage6_seed_selection_fix.patch`.
3. `stage6_multisource_withdrawal.patch`.
4. `stage6_revision_replacement.patch`.
5. `stage6_source_text_changes.patch`.
6. `stage6_multichunk_maintenance.patch`.
7. `stage6_occurrence_removal.patch`.
8. `stage6_resolved_group_retirement.patch`.
9. `stage6_docs_handoff_update.patch` (documentation only).
10. `stage6_occurrence_addition.patch`.
11. `stage6_occurrence_addition_mac_verification.patch` (documentation only).

These are delivery filenames, not required runtime files or a promise that patch archives are committed. Do not reapply patches when the checkout already contains their changes. The occurrence-removal and resolved-group-retirement code-patch SHA-256 values are respectively `d01d68c99051c4b26cb08ce8f9ed3a240b44b71d16f5076c684004bfb4f5b0c2` and `0086ae816b52cc23803e93cfc932497920d5efe8811c6040189c56c2b28fda60`.

At session start, inspect `git status --short`, `git log -1 --oneline`, the files below and CLI commands. Preserve local changes. After you integrate a delivered update, commit and push the relevant source, tests, schema, dependencies and documents. A fresh GitHub checkout must contain the complete baseline. User-local output stores and downloaded chat archives are not substitutes for committed source.

## Completed functionality and evidence

“Implemented” below means a bounded deterministic fixture through actual configured stores. Identity/semantic judgments are supplied as captured fixture input; their quality has not been evaluated.

| Checkpoint | Implemented behavior | Guide |
|---|---|---|
| Initial publication and seed fix | Validated records, exact UUID creation/reference, native ownership/evidence, HC-seeded local-fact retrieval, explicit same-revision reconcile and caught-failure visibility | [First slice](stage6_identity_first_slice.md) |
| Multi-source withdrawal | Shared contributions/owners, both withdrawal orders, unresolved mentions, singleton retention, independent original facts/evidence and explicit withdrawal retry | [First slice](stage6_identity_first_slice.md#two-source-lifecycle-fixture) |
| Unchanged-text correction | Guarded next revision; retarget doc01 while preserving doc02; registered/saved/graph agreement; retire obsolete declarations; forward recovery | [Revision replacement](stage6_identity_revision_replacement.md) |
| Prefix edit and native rebuild | Same original Data ID, checked Unicode offsets/hashes, whole-document native memory removal/ingestion/chunk rebuild, refreshed captured facts/evidence and unsafe-cascade/dependency refusal | [Text changes](stage6_identity_text_changes.md) |
| Multi-chunk maintenance | Split occurrence markers, complete fact continuation evidence, repeated edits/current chunk indexes, current-budget reconstruction and caught-failure recovery | [Multi-chunk](stage6_identity_multichunk.md) |
| Partial/empty unresolved groups | Explicit old-occurrence retention indices, stable continuing group, retirement of empty unresolved group/node/vector/markers, independent support preserved | [Occurrence removal](stage6_identity_occurrence_removal.md) |
| Empty resolved fact-bearing group | Retire saved group/resolution/declaration, physical mention/node vector, resolution link, local fact/evidence/markers; preserve doc02's distinct fact and shared endpoint/index | [Resolved retirement](stage6_identity_resolved_retirement.md) |
| Occurrence additions and new group | Explicit old-to-new continuity, stable continuing IDs/fresh same-text local group, accepted link and new original-owned local fact/evidence, reopen/reconcile and explicit recovery | [Occurrence addition](stage6_identity_occurrence_addition.md) |
| Changed interpretation and kind change | Text edits that retire g01 for a fresh group resolved to a new derived Entity or unresolved; unchanged-text edits that turn doc01's HC variant into a local mention and back, referencing doc02's existing HC Entity; reopen/reconcile and explicit recovery | [Reinterpretation](stage6_identity_reinterpretation.md) |
| Mixed occurrence revision | One edit keeps `it`, removes `the controller`, adds a startup `the controller` to continuing g01 and retires g02, through the general occurrence map with no admission change; reopen/reconcile and explicit recovery | [Mixed occurrences](stage6_identity_mixed_occurrences.md) |
| Group split and combination | Explicit `occurrence_regrouping` map (since replaced by the general map); g01 splits into fresh g04 and g05, then g04 and g05 combine into fresh g06; retired groups, links, facts, evidence and triplets physically removed; facts generated again from the fresh groups, never transferred; fresh IDs from source, new revision and key; reopen/reconcile and explicit recovery | [Group split](stage6_identity_group_split.md) |
| Forget and re-add | `forget` removes a source nothing depends on through Cognee's native document deletion; `readd` publishes it again at the next revision with new IDs; six fault stages and explicit recovery | [Forget](stage6_identity_forget.md) |
| Erasure with dependents | `forget` erases a current, withdrawn or failed-first-publication source to a tombstone of identifiers and scrubs its plan and event messages. A forget that changes another source's decisions needs `--confirm` with the token of its `--dry-run`. Each dependent then gets a removal revision: a resolution citing the source becomes unresolved, a variant is dropped, and a recipe only removed decisions named goes with them. A dependent's failed attempt finishes with the removal applied. `readd` publishes from the caller's files | [Forget](stage6_identity_forget.md) |
| Dependencies (glossary) | A glossary edit withholds only doc01's decisions that read the changed entry: unchanged in place stays valid, a moved entry is refreshed with its new range, a changed entry needs a reviewer who re-confirms or replaces the decision; a failed edit withholds every citing decision until reconcile; an interrupted refresh resumes | [Dependencies](stage6_identity_dependencies.md) |
| Chains (J1) | doc03's decisions cite doc01's r01 and v01 as saved records. A glossary edit withholds r01 and v01 for review and, down the chain, c01 and c02 (`upstream_withheld`); a re-confirm upstream releases doc03 with no doc03 revision; a replacement upstream needs doc03's own review; admission refuses a cycle, a self-citation and a missing, stale or changed record; a forget that would remove a cited record was refused (`chain_erasure_pending`) until J2 | [Chains](stage6_identity_chains.md) |
| Cascade (J2) | Forgetting the glossary on a chain root removes doc01's r01 and v01 at level 1, then doc03's c01 and c02 at level 2, under one dry run and one token. A crash at level 2 resumes in order and the re-add waits for it; a token is refused when a new level appears; a blocked level-2 dependent waits; doc01 cannot be withdrawn or forgotten while the cascade below it is unfinished (`cascade_unfinished`) | [Forget](stage6_identity_forget.md#the-cascade) |
| Entity edits and removed records (K) | `edit-entity` edits the Helios controller Entity that doc01 reads, with no ledger row, and withholds r01 and v01 and, down the chain, c01 and c02; a revert releases them; a re-confirm or an in-place replacement answers the edit; `replace-citation` re-cites or drops a citer of a removed record; a returning cited key and a corpus input of a mention UUID are refused; a kind change on a chain root leaves its citer withheld `input_removed` and recovers after a fault | [Entity edits](stage6_identity_entity_edits.md) |

### Tests run in the generation environment

The previous resolved-retirement code checkpoint recorded **59 programmatic tests and 7 selected native sequence tests passing (66 distinct cases)**. The native selection was three resolved-retirement sequences, three preceding occurrence-removal sequences and one multi-chunk repeated-edit/reconcile/withdraw sequence. The other 19 native cases were not rerun in that checkpoint. Earlier delivery counts overlap; do not add them or claim a fresh full-suite run.

Tests used Python 3.12.14, Cognee 1.6.2, actual configured Ladybug/LanceDB/SQLite stores, deterministic loopback embeddings and no LLM. The generation environment had no `.env`, so these tests used loopback. Only that native profile is demonstrated in the generation environment. Final code-patch application and affected-file byte equality were checked. The preceding documentation-only update did not rerun the runtime suite.

The **2026-10-20 addition checkpoint** passed **81 programmatic tests and 3 new native sequence tests (84 distinct cases)**; the other 26 native cases were not rerun. The native selection covers addition/reopen/reconcile/another prefix edit/withdrawal, plus exact forward recovery after `text_chunks` and `replace_published`. User-Mac reproduction is recorded separately below. The test runs for the `.env` fix were on the user's Mac, not in the generation environment. The [resolved `.env` issue](#resolved-the-repository-env-overrode-the-fixture-profile) records them.

The **2026-10-21 group split and combination checkpoint** ran on the user's Mac, not in the generation environment. The assistant's subagents ran it with loopback embeddings. The unit suite gave 207 passed and 34 deselected. A focused integration run of the split, combination, addition and resolved-retirement native tests gave 11 passed in 236 s. The other native cases were not rerun in that pass. [Verification skill](#verification-skill) lists the journey results, and the [group split guide](stage6_identity_group_split.md#verification-profile-and-evidence) has the full list.

Native assertions used actual configured stores and fresh child processes. A **host-only test launcher** exited after the ordinary CLI returned and its explicit engine-close path completed. This bypassed interpreter finalization.

Ordinary CLI publication and reopened retrieval produced the expected three facts. However, one reopened retrieval exceeded the 300-second process-exit allowance on this Linux host. The launcher results therefore establish the tested lifecycle operations, reopen, and verification. They do not establish clean ordinary interpreter teardown here.

The application has no forced-exit workaround. The delivery's `TESTS.md` and `support/host_native_launcher.py` record this limitation and the local reproduction procedure. The isolated profile uses LiteLLM's bundled pricing map to avoid unrelated startup metadata fetching. The lockfile and dependencies are unchanged.

### Results verified on the user's Mac

The user ran and supplied terminal output; the assistant reviewed the returned JSON. This is independent reproduction on the user's machine, not execution there by the assistant. These runs predate the `.env` fix. They used the `.env` NVIDIA embeddings (2048 dimensions), not loopback, and wrote raw fixture text into the lab `.cognee_data/`. Their retrieved facts matched expectations, but they do not demonstrate the offline loopback profile. Verified sequences include initial publication/reconcile, multi-source withdrawal/retry, unchanged-text correction/recovery, prefix-edit/recovery, and the following latest checkpoints:

| User-local root(s) | Reviewed result |
|---|---|
| `outputs/stage6_multichunk` and `_failure` | Edit and healthy reconcile preserve complete evidence/current chunk mapping; failed doc01 withheld while doc02 survives; explicit reconcile completes revision 2 and resolves incident |
| `outputs/stage6_occurrences` and `_failure` | g01 keeps only `it` at `[46,48)`; empty unresolved g02 is removed; healthy reconcile does not resurrect it; interrupted cleanup completes with the same event resolved |
| `outputs/stage6_resolved_retirement` and `_failure` | g01/r01/local fact/evidence are removed; unresolved g02 survives; only doc02's unchanged fact returns; healthy reconcile preserves retirement; explicit recovery resolves the same event at revision 2 |
| `outputs/stage6_additions` | Addition returns three facts; g01 continues and g03 is created with its name index, accepted link, original-owned local fact and current evidence; reopened retrieval and healthy reconcile preserve results without increasing revisions or creating incidents |
| `outputs/stage6_additions_failure` | Injected `replace_published` failure withholds doc01 while doc02's unchanged fact remains available; explicit reconcile completes revision 2, restores three facts and resolves the same incident with one verified recovery attempt |

For these reviewed maintenance checkpoints, doc01 reaches saved/registered/verified revision 2 and doc02 stays at 1. Borrowed Entity fields and independent shared support survive. Successful paths produce no incidents; injected failures produce one test-labeled incident closed after verified forward completion. The latest resolved-retirement recovery was reviewed on 2026-10-19, from the run ending approximately 22:45 America/Detroit.

The addition recovery was reviewed on 2026-10-20, from the run ending approximately 10:49 America/Detroit. Incident `f93491d5-3f5a-58c0-b786-a3874c27059c` records the injected failure and a single verified recovery attempt ending `restored` at revision 2. Fresh g03 `a75636db-c46d-5261-a21e-010647bfe4f4` survives recovery with its node/name index, accepted r03 and two current evidence/marker chunks. Continuing mention IDs, doc02's full fact/evidence and source summary, and borrowed Entity fields are unchanged; retired chunks/vectors are absent.

These Mac results cover successful addition, reopen/healthy reconcile and post-publication recovery. The user did not review three later cases: a `text_chunks` failure after addition, a prefix edit after addition and withdrawal after addition. On 2026-10-21 the assistant ran verify journeys O5 and O6 on the user's Mac with loopback embeddings, and they cover these three cases. O5 runs the addition, a later prefix edit and the withdrawal. O6 injects the `text_chunks` failure, and also `replace_published`, and recovers each one. These are the assistant's runs in fresh roots, not reviews of the roots in the table. The generation-environment native tests retain the host-only-launcher qualification above. The Mac results do not establish clean ordinary Linux interpreter teardown.

Raw terminal transcripts were supplied in chat and are not asserted to be committed. This table is the durable verification summary. The roots above are user-local existing stores: reuse them for inspection only, and use new roots for new fixture creation. Dataset IDs vary by root; never substitute IDs from another run.

## Resolved: the repository `.env` overrode the fixture profile

**Found and fixed on 2026-10-20, on branch `fix/fixture-embedding-profile` (commits `ab67118`, `9048b71`, `dbcf727`).**

### What was wrong

Cognee 1.6.2 loads an env file once, on its first import, with `override=True` (`cognee/shared/env_file.py`). If `COGNEE_ENV_FILE` is not set, Cognee loads the repository `.env`. The old CLI set the fixture settings in `__main__.configure()` and imported Cognee after that. The lab `.env` therefore replaced each key that both set. A fixture root used the `.env` NVIDIA embeddings instead of the 64-dimension loopback service, and wrote raw text into the lab `.cognee_data/`. `tests/conftest.py` set the unit-test environment in the same order.

The assistant measured these results on the user's Mac on 2026-10-20, before the fix:

- A new `chunked-fixture` root had no `data/` directory. Two new `text_*.txt` files appeared in the lab `.cognee_data/`. The LanceDB vectors in the root had 2048 dimensions.
- `uv run pytest -q -m 'not integration'` changed the lab `.cognee_system/databases/cognee_db` (mtime 16:55:12, during the run). That database has rows in `lab_identity_publications` (4), `lab_identity_writers` (1) and `lab_identity_recovery_events` (4). Unit tests such as `tests/test_identity_storage.py` wrote them through the default relational engine.

Later on 2026-10-20 the user deleted these unit-test rows from the lab database. The user made a backup first and later deleted the backup.

### The fix

- Each root keeps its data, system, cache, graph, vector and relational stores inside the root.
- The CLI sets `COGNEE_ENV_FILE` to `src/cognee_lab/identity/fixture.env`, which contains only comments. Cognee's import-time load then does not replace the fixture settings. The LLM settings stay fake. No fixture command calls an LLM.
- The creation commands (`fixture`, `multi-fixture`, `chunked-fixture`) take `--embedding env|loopback`. The default is `env`.
  - `env` reads `EMBEDDING_*` and `HUGGINGFACE_TOKENIZER` from the repository `.env`, or from the file that `COGNEE_ENV_FILE` names. The values stay in process memory. Creation fails before it makes the root in these cases:
    - The file does not set `EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS`, or sets one of them to an empty value.
    - `EMBEDDING_DIMENSIONS` is not an integer.
    - `COGNEE_ENV_FILE` does not name a file.
  - `loopback` is the earlier offline service with deterministic 64-dimension embeddings.
- The root marker `stage6-fixture.json` records `embedding` as `{"profile", "model", "dimensions"}`. It records no key and no endpoint. Later commands read the marker and refuse a different `--embedding` value. For an `env` root, they also refuse a `.env` whose embedding model or dimensions changed.
- The `result.json` file from the `fixture` command copies `embedding` from the marker. It no longer states that every root used a local deterministic service.
- pytest keeps the loopback profile. `tests/conftest.py` sets `COGNEE_ENV_FILE` to `fixture.env` and puts the cache root in its temporary directory. The native `command()` helper passes `--embedding loopback`. `tests/test_identity_environment.py` checks that unit tests do not use the lab stores.
- `python-dotenv` is now a declared dependency.

### Roots made before the fix

A root whose marker has no `embedding` record opens only for `status` and `retrieve`. Those two commands still load `.env`, because `.env` embeddings wrote the vectors of those roots.

One limit predates the fix and the fix does not cause it. A copy of `outputs/stage6_additions` fails `retrieve` with `FileNotFoundError` for a `.cognee_data/text_*.txt` file. The old code (`ccc85d6`) and the new code fail in the same way. Older Mac roots depend on raw text in the lab data directory, and that file no longer exists. `status` still works on the copy.

### Evidence after the fix

The assistant measured these results on the user's Mac after the fix:

- A new root, `outputs/repro_env_after`, ran `chunked-fixture`, then `add-occurrences --source doc01 --expected-revision 1`, then `reconcile --source doc01`, with the default `env` profile. All three commands exited 0. The result had 3 facts, doc01 at saved/registered/verified revision 2/2/2, and no recovery events.
- The vectors in that root had 2048 dimensions. The marker names `nvidia/nemotron-3-embed-1b`. Raw text was in `<root>/data/`. The lab `.cognee_data/` got no new files, and the lab `cognee_db` mtime did not change. No file under the root contains the API key.
- `uv run pytest -q -m 'not integration'`: 89 passed.
- A delegate agent ran the full integration suite: 29 passed in 605 s, with no teardown hang. These tests use the loopback profile.
- After `dbcf727`, a focused native rerun: 1 passed.

### Verification skill

The project verification skill (`.claude/skills/verify/`) found this issue, and the fix removed its blocker. Its grounding-run evidence is in `outputs/verify/20261020T201147Z-grounding/evidence/`. The 24 lab data files that the probe and grounding runs of that session wrote are listed in `outputs/verify/lab-data-leaked-files-2026-10-20.txt`. The lab relational store does not reference them.

Proof history, 2026-10-20 to 2026-10-23:

- 2026-10-20. The 20 journey blocks ran as 31 runs on the Mac against Cognee 1.6.2, with 500 assertions and 0 failures. The tokenizer fix was applied.
- 2026-10-21. A fix round added the `journey` runner, `probe`, the lab-store guard and `reopen_problem`. The rerun passed all 31 runs with 567 assertions and 0 failures. `journey all` ran the 30 loopback runs, and `journey P5 --include-env` ran the env run.
- 2026-10-21, before the regrouping journeys. The assistant ran `journey all` on the Mac. The 19 loopback journey blocks ran as 30 runs, with 586 PASS rows and 0 FAIL rows. P5 is the 20th block. It needs `--include-env` and did not run in this pass.
- 2026-10-21, group split and combination. The assistant's subagents ran journeys G1 (32 PASS rows), G2 (20), G3 (36) and G4 (21) on the Mac with loopback embeddings, with 0 FAIL rows. After the fresh-ID change they reran O5 (27), O6 `replace_published` (17) and O6 `text_chunks` (17), with 0 FAIL rows. The map now has 24 journey blocks, and `journey all` runs the 23 loopback blocks as 34 runs.
- 2026-10-21, checkpoint run for group split and combination. The assistant ran `journey all` on the Mac on the final branch head, serially. The 23 loopback blocks ran as 34 runs, with 695 PASS rows and 0 FAIL rows, in 15 min 17 s. P5 needs `--include-env` and did not run.
- 2026-10-22, checkpoint run for the mixed revision. The assistant ran `journey all` on the Mac with 4 jobs. The 25 loopback blocks ran as 37 runs, with 735 PASS rows and 2 FAIL rows, in 308 s. Both FAIL rows were new O7 checks with wrong expectations, not code faults. The O7 expectations in the feature map were corrected, and an O7 rerun gave 17 PASS rows and 0 FAIL rows. No file under `src/` changed after the full run.
- 2026-10-22, clean checkpoint rerun. The assistant ran `journey all` again on the Mac with 4 jobs, on `main` at `5603310` plus documentation changes only. The 25 loopback blocks ran as 37 runs, with 736 PASS rows and 0 FAIL rows, in 307 s.
- 2026-10-23, dependencies (Checkpoint H). The assistant added journeys D1 to D6 in `features/dependencies.md` and ran them on the Mac with loopback embeddings: 127 PASS rows and 0 FAIL rows in 10 runs at first, 128 after fix round 2. The map now has 45 journey blocks, and `journey all` runs the 44 loopback blocks as 68 runs.
- 2026-10-23, checkpoint runs for dependencies. The assistant ran `journey all` on the Mac with loopback embeddings: 1286 PASS rows and 0 FAIL rows in 68 runs on `5c50a6f` and again on `b04ffde`, and 1287 PASS rows and 0 FAIL rows in 68 runs on `2fcf78c`. Later commits change only documentation and one docstring. P5 needs `--include-env` and did not run.
- 2026-10-23, erasure (Checkpoint I). The assistant's subagents rewrote and extended `features/source-lifecycle.md` to journeys F1 to F14 and ran them on the Mac with loopback embeddings, with 0 FAIL rows in each fix round. The map now has 55 journey blocks, and `journey all` runs the 54 loopback blocks as 80 runs.
- 2026-10-23, checkpoint runs for erasure. The assistant and its subagents ran `journey all` on the Mac with loopback embeddings: 1407 PASS rows on `d94b0a3`, 1416 on `686dc16`, 1429 on `af7218a` and 1439 on `d6133c7`, each with 0 FAIL rows; the last ran 80 runs. P5 needs `--include-env` and did not run.
- 2026-10-23, chains (Checkpoint J1). The assistant's subagents added journeys D7 to D11 to `features/dependencies.md` and ran them on the Mac with loopback embeddings: 63 PASS rows and 0 FAIL rows. With F15 from the re-add follow-ups, the map now has 61 journey blocks, and `journey all` runs the 60 loopback blocks as 86 runs.
- 2026-10-23, checkpoint runs for chains. The assistant and its subagents ran `journey all` on the Mac with loopback embeddings: 1519 PASS rows and 0 FAIL rows in 86 runs on `637bfcc` and again on `8167c25`. The later commit `2002a77` changes one refusal message and one comment. P5 needs `--include-env` and did not run.
- 2026-10-24, cascade (Checkpoint J2). The assistant's subagents added journeys F16 to F20 to `features/source-lifecycle.md` and ran them on the Mac with loopback embeddings, with 0 FAIL rows in each fix round. The map now has 66 journey blocks, and `journey all` runs the 65 loopback blocks as 91 runs.
- 2026-10-24, checkpoint runs for the cascade. The assistant and its subagents ran `journey all` on the Mac with loopback embeddings: 1565 PASS rows on `231c2e6`, 1567 on `9d2b47d`, 1576 on `a136d06`, 1576 on `d1192ba` and 1576 in 91 runs on `74ec093`, each with 0 FAIL rows. P5 needs `--include-env` and did not run.
- 2026-10-24, entity edits (Checkpoint K). The assistant's subagents added journeys D12 to D16 to `features/dependencies.md` and K6 to K9 to `features/reinterpretation.md` and ran them on the Mac with loopback embeddings, with 0 FAIL rows in each fix round. The map now has 75 journey blocks, and `journey all` runs the 74 loopback blocks as 101 runs.
- 2026-10-24, checkpoint runs for entity edits. The assistant and its subagents ran `journey all` on the Mac with loopback embeddings: 1658 PASS rows in 101 runs on `40d7d20`, on `94d54bb` and on `5e0c314`, each with 0 FAIL rows. P5 needs `--include-env` and did not run.
- Not exercised against an env root. The warning path for a missing tokenizer fix, and the doctor failure path for an operator file that lacks a key.
- Exercised. The doctor failure path for a pre-profile marker, a malformed marker, and an env root whose operator file names another model.

## Original six-step implementation sequence

This is **step 4 within Stage 6**, not project Stage 4.

| Step | Current status |
|---|---|
| 1 / M0 | Runtime forms/schema, exact chunk mapping, portable bookkeeping and capability checks implemented for the initial profile |
| 2 / M1 | Captured Task → native publication → useful fact/evidence retrieval → reconcile demonstrated |
| 3 / M2 | Multi-source ownership/withdrawal demonstrated; general exact-ID semantic conversion remains broader than the captured writer |
| 4 / M3 | Partly complete: corrections, prefix/rechunk edits, partial occurrence removal, empty unresolved and resolved fact-bearing group retirement, captured additions/new group, captured group split and combination, one general occurrence map for every text change, a captured mixed addition/removal edit, explicit caught-failure recovery, forget and re-add of a source nothing depends on, per-decision withholding of dependents after a text edit (glossary fixture), erasure of any source with removal of the dependents' decisions that cite it, decisions that cite other sources' decisions, with withholding down the chain (chain fixture), erasure down the chain under one confirmed dry run, and reviewer paths for the readers of an edited Entity or a removed record, with kind changes under readers |
| 5 / M4 | Standard Cognify/Remember/full Update B Task-transform wiring, source-removal entry-point hooks, public Retriever/SearchType, broader traversal/delivery/diagnostics not implemented |
| 6 / M5 | Seeded rules/model Describe and separate quality/consistency evaluation not implemented |

### Remaining step-4 work

1. **Occurrence/group changes:** representation-kind changes using separate suitable Entities. On 2026-10-24 the user decided that a kind change retires the old group and declares a fresh one. Since Checkpoint K (2026-10-24) the kind changes run on a root where other sources read doc01, and their citers follow the citation rules. One general occurrence map now admits any mix of kept, removed, added and regrouped occurrences that satisfies the approved rules (2026-10-21), with captured fixtures for removal, retirement, addition, split, combination and one mixed edit. Those fixtures do not establish automatic matching or Describe.
2. **Changed interpretation and semantic refresh:** edits changing a referent/definition/scope, with coordinated saved decisions and regenerated facts/evidence. Existing unchanged-text retargeting and captured same-binding edits do not establish this generally.
3. **Dependencies:** identify and reconsider affected sources that consumed another document, corpus fields or saved records; support admitted span/record remapping. Current code rejects known dependent-document text edits rather than silently propagating them. New-corpus opportunity selection is not solved by positive dependencies alone. *Since 2026-10-23 (Checkpoint H):* a text edit of a consumed document no longer refuses. It withholds the decisions that read what changed, remaps a moved span and leaves the rest for a reviewer. *Since Checkpoint I (2026-10-23):* `forget` removes the dependents' decisions that cite the erased source, in a removal revision of each dependent, after a confirmed dry run. *Since Checkpoint J1 (2026-10-23):* a resolution or variant assignment may cite another source's decision as a saved record, and withholding spreads down the whole chain of citations. *Since Checkpoint J2 (2026-10-24):* a forget cascades down the chain, one removal revision per dependent at its level. On 2026-10-24 the user decided that a direct native Entity edit withholds its dependents (`input_changed`). *Since Checkpoint K (2026-10-24):* `edit-entity` drives such an edit, a reviewer re-confirms or replaces a decision withheld by an Entity input, and `replace-citation` answers a citer of a removed record. Facts as citable records moved to step 6.
4. **Full source lifecycle:** coordinate original removal with generated-source retirement, generated-source rebuild and authorized endpoint reconstruction; preserve remaining owners and distinguish missing reasoning inputs from missing reconstructible output. Identity withdrawal alone keeps Data/description and original facts; it is not full source Forget. *Since Checkpoint I (2026-10-23):* `forget` accepts a withdrawn source and a failed first publication, and leaves only a tombstone of identifiers. Erasure is logical: the stores' soft-deleted bytes and free pages stay until they compact, and the dry run lists them.
5. **Verification/recovery coverage:** extend current revision/attempt/currentness, ownership/index/evidence and retirement checks across those operations, including incomplete/missing-plan diagnostics. Do not make a general crash-recovery framework a new prerequisite.

### Group split and combination, completed 2026-10-21

The user approved this case on 2026-10-21, before implementation. The [group split guide](stage6_identity_group_split.md) gives the exact texts, offsets, maps and UUIDs.

- **Split, revision 1 to 2.** A paragraph break splits g01 into fresh g04 (`the controller`) and fresh g05 (`it`). Accepted resolutions r04 and r05 link both to the same Helios controller. g02 continues. The `it limits oscillations` fact is generated again from g05, never transferred. g01, r01 and g01's fact edge, evidence and triplets are physically retired.
- **Combination, revision 2 to 3.** Rejoining the paragraphs merges g04 and g05 into fresh g06, with resolution r06. g04, g05, r04, r05 and g05's fact retire. The fact is generated again from g06. g01 is never resurrected.

At this checkpoint the `occurrence_regrouping` mode mapped each old occurrence to one `[new group, new index]` pair, beside separate removal and addition modes. The general occurrence map replaced all three on 2026-10-21.

The review added the fresh-ID rule. A fresh group's UUID is `uuid5(identity_data_id, f"mention:r{revision}:{key}")` with the new revision, and both addition and regrouping admission enforce it. Both also require the source revision to be the old revision plus one. The record store keeps only the current revision, so a key-only derivation re-derived a retired UUID when a key returned. The guide explains why the rule is sound and lists the old and new UUIDs. Roots reviewed before this change keep their key-only IDs as history.

### General occurrence map, approved 2026-10-21

The assistant drafted a mixed addition and removal case. The user asked why one edit could not combine the existing operations, and whether every mix of removing and adding would need its own design. It would have, because each admission mode admitted only its own kind of change. On 2026-10-21 the user approved one general map with one set of rules, delivered in three checkpoints.

**The map.** For each old occurrence, in order, the map gives its new place as `[group, index]`, or `null` if it was removed. A new occurrence that nothing maps to is an addition.

**The rules.** They are stated over occurrences and groups, never over kinds of edit.

- Every old group is in the map, and every old occurrence has one entry whose slice matches the old text.
- Each target exists in the new description, has at most one origin and has the same text. Every new occurrence matches its slice of the new text. The revision advances by one.
- An old group continues only into the new group with its key and Entity UUID that receives all of its surviving occurrences, at least one, and none from another old group. It may also gain additions. Its occurrences may change order, because moving text does not change which mentions belong together. The old modes refused a reorder; the approved rules do not.
- Every other old group retires. Every other new group is fresh. A fresh group needs a key and an Entity UUID that no old group used, and on a first attempt its revision-scoped UUID.
- The decision and recipe rules then apply to the continuing, retired and fresh groups. A continuing group keeps its reviewed resolutions. Each fresh group declares exactly one resolution, with an ID no old resolution or assignment used. Retired groups lose their recipes, fresh groups add theirs, and every other recipe stays. Variant assignments stay unchanged, and span-scoped variants are refused.

**The user's policy decisions.**

1. Strict peel-off. If a group keeps some occurrences and others move to another group, the group does not continue. The reviewer declares fresh groups for both parts.
2. Fresh group when nothing survives. A group whose old occurrences are all removed does not continue, even if new occurrences take its key. The reviewer declares a fresh group with a new key.

**Still refused.** A continuing group whose resolution or meaning changes, a change of representation kind, an occurrence that moves to another document, span-scoped variants and dependent sources.

**Checkpoint A, completed 2026-10-21.** This checkpoint made no change to runtime behavior.

- The admitters moved out of `text_changes.py` into `admission.py`.
- `admit_general` in `admission.py` implements the rules beside the old modes, one named function per rule, and returns a `GroupFate` with the continuing, retired and fresh groups. It applies the revision-scoped UUID rule when `first_attempt` is true. No command uses it yet. `to_occurrence_map` writes an old-mode map as the general map.
- `support/occurrence_worlds.py` enumerates small worlds and has an independent oracle for group fate and fresh keys and UUIDs. A world has up to three old groups, three old occurrences and one addition, with every grouping, key and UUID choice, including an unrelated UUID. `support/occurrence_check.py` checks the admitters against the oracle. For each admitted world it also checks a variant where every occurrence has the same text, and corruptions that each break one shape, slice, revision or carryover rule and must meet that rule's refusal. `support/occurrence_mutants.py` holds 14 breaks, one per rule.
- The assistant ran `uv run python support/occurrence_check.py` on the user's Mac on 2026-10-21. The general admitter agreed with the oracle on all 540,045 worlds, on a first attempt and on a retry, and on the 1,410 admitted worlds with shared text. Each of 27,102 corruptions met the refusal of the rule it breaks. (An earlier version of this line said 39,309; that was a summing error, corrected on 2026-10-21 from the run's own per-kind counts.) Each old mode agreed with the oracle wherever it could express a world, except for 21 scope refusals of an unchanged grouping, and each of 21,472 old-mode maps converted to the world's general map. The run took 95 s. `--mutants` caught all 14 breaks in 11 s.
- The worlds do not cover more than one addition, changed decisions other than the corruptions, or reordering. Reordering is admitted and pinned by a unit test.
- `tests/test_identity_general_map.py` pins the general map and the group fates of each of the six captured fixtures. `tests/test_occurrence_check.py` runs a small bound and the mutants in the unit suite, which adds about 11 s.

**Checkpoint B, completed 2026-10-21.**

- `admit(old, source, before, after, occurrence_map, *, first_attempt)` in `admission.py` is the only admission path. It returns a `GroupFate`. Its 20 rules are named functions in the order it applies them, and `support/occurrence_mutants.py` breaks each one. The carryover rules are now six separate functions. The old rule "every resolution belongs to a continuing or fresh group" was dropped, because model validation already guarantees it.
- `TextChange(previous_text, text, occurrence_map, chunk_budget)` parses the map into `OccurrenceRef` pairs. Preflight calls `admit` with `first_attempt=not retry`, then checks that no fresh UUID is in the graph.
- `TextChange.from_plan` reads every saved plan. A plan saved before this checkpoint holds `occurrence_retention`, `occurrence_continuity`, `occurrence_regrouping` or none (a prefix shift). The reader converts it against the plan's previous description and refuses a malformed or mixed plan with `recovery_plan`. Delete the reader once no kept root holds a plan without `occurrence_map`.
- The general rules are stricter than the old prefix mode: a converted prefix plan must also advance one revision and match every slice. A unit test pins the revision rule. They are looser in two ways the approved design allows: a continuing group may reorder, and an unchanged grouping with changed text is admitted.
- Fresh-group refusals have distinct codes: `fresh_key_reused`, `fresh_uuid_reused`, `fresh_uuid_not_derived` and `fresh_uuid_in_graph`.
- Result JSON reports `occurrence_map` instead of the three mode fields. `decision_method` is now a list of the producers that the revision's groups and decisions cite. `position_shift` is set only when every occurrence moved by the prefix length. Fixture maps are `REMOVAL_MAP`, `RETIREMENT_MAP`, `ADDITION_MAP`, `SPLIT_MAP` and `COMBINE_MAP`.
- Evidence, run by the assistant on the user's Mac on 2026-10-21: 264 unit tests passed. `support/occurrence_check.py` agreed with the oracle on all 540,045 worlds, and 29,793 corruptions each met their rule's refusal (91.6 s). `--mutants` caught all 20 breaks. The ledger check passed with `PINNED` unchanged at 3828 nodes and 3717 sequences. `verify.py journey all` gave 695 PASS and 0 FAIL in 34 runs (285 s). Its only expectation changes were the seven checks that read the old map fields, which now read `occurrence_map`. The 23 native integration tests in the seven touched test files passed (465 s). Two thermo reviews found no high or medium bug; their fixes are in the branch.

**Checkpoint C, completed 2026-10-22.** `revise-occurrences` publishes the case the user reviewed on 2026-10-21. g01 keeps `it` ([90,92) to [46,48)), loses `the controller` at [49,63) and gains `the controller` at [86,100); g02 retires. Its map, `{"g01": [null, ["g01", 0]], "g02": [null]}`, equals the removal map, because a map states only where old occurrences went. No admission code changed. `describe_mixed` and `describe_removal` share `keep_g01_retire_g02` in `occurrence_fixture.py`, and every captured describer is now built from the helpers in `captured_revision.py`; a byte comparison showed all seven describers produce the same descriptions as before. The added occurrence lies in a chunk without fact evidence, so g01 marks two chunks while its fact uses one. The [mixed occurrences guide](stage6_identity_mixed_occurrences.md) has the texts, decisions, run and evidence. Evidence, by the assistant on the user's Mac on 2026-10-21 and 2026-10-22: 269 unit tests passed. `support/occurrence_check.py` agreed with the oracle on all 540,045 worlds and 29,793 corruptions, and `--mutants` caught all 20 breaks. The ledger check passed. A native run of 16 tests in six touched files gave 13 passed and 3 failed. The 3 failures were wrong test expectations: the assistant had assumed four chunks where the native chunker makes five, and had assumed a healthy `reconcile` keeps the text-change record, which it does not. The other 13 tests passed in that run. After the corrections, only the 5 tests in `test_identity_mixed_native.py` and `test_identity_occurrences_native.py` were rerun, and all passed. No file under `src/` changed after the first run. Verify journeys O7 (17 PASS rows) and O8 (12 PASS rows for each of two fault stages) gave 0 FAIL. Each count includes three lab-store guard rows. The `journey all` run is under [Verification skill](#verification-skill).

### Step-4 decisions, 2026-10-22

The user and the assistant reviewed the remaining step-4 items on 2026-10-22.

**Decisions the user made.**

1. A changed decision in a text edit means a fresh group. If a text edit changes what a group refers to (a different referent, resolved to unresolved or the reverse), the group does not continue. The group retires. The reviewer declares a fresh group. Facts are generated again from the fresh group. A retired ID is never served with a new meaning. This keeps the admission rule `check_continuing_decisions`. The existing correction that retargets a group without a text change is the one exception: it changes a continuing group's target in place and retires nothing. A variant applicability change cannot be expressed by retire-and-fresh; since Checkpoint D a corpus- or span-scoped variant may not change at all (`check_scoped_variants`). Decide how to treat a scope change only when a concrete case needs it.
2. No successor record yet. Nothing records that an old group ID was replaced by a new one, beyond the revision's result file and the current revision's saved plan, which the next revision overwrites. Decide it with step-4 item 3 or the step-5 retrieval contract, where its callers are designed.

**What follows for each item.**

- Changed interpretation (item 2) needs no logic to correct references. References inside the document are rebuilt by the retire-and-fresh path. References from other sources are dependencies (item 3). Today a source that consumes the edited text is refused (`reject_dependents`). A source that consumes a mention UUID as a corpus object or saved record is not detected; that is an item-3 gap, and no fixture has one.
- Before Checkpoint D, a fresh group could resolve only to an Entity whose recipe the old description already declared, or stay unresolved. Checkpoint D relaxed that rule; see the next section.
- Representation-kind changes (item 1): the design already answers ownership (the document's generated identity source retains the endpoints it needs, and other sources add their own ownership). The later decisions are in the next section.
- Dependencies (item 3), including span-scoped variants and moves to another document, cannot be fully specified yet. The dependency record and the propagation policy (block, mark unavailable, queue for review or reconsider) depend on real dependent sources in the user's intended use. The cross-document parts of items 1, 2 and 4 wait for this policy.
- Full source lifecycle (item 4): removing a source that no other source consumed can be specified now. Removing a consumed source waits for item 3.
- Verification and recovery (item 5) follows each operation. Open choice: whether new operations get a small-world oracle check like admission.

### One admission for every replacement, 2026-10-22

The user reviewed the open questions for a fuller changed-interpretation and representation-kind implementation on 2026-10-22.

**Decisions the user made.**

1. Relax the recipe rule. The rule that new descriptions keep the old reusable recipes came from the first text-edit slice on 2026-10-19, which admitted moved text only. It was a scope limit, not an identity property.
2. A new reusable Entity that a source creates gets the UUID `uuid5(identity_data_id, f"entity:r{revision}:{key}")`, where `key` is a resolution or variant in the new description that names it. Two documents that introduce the same new Entity get different UUIDs; merging them is matching work for Describe (step 6).
3. A source may drop a reusable Entity it no longer uses. Ownership is per source, so the Entity survives while another source owns it.
4. Fold the unchanged-text correction into the general admission. It was a fourth admission path, and lesson G22 applies to it.
5. A text edit may add, remove or retarget document-scoped variants. A document-scoped variant names its document, not positions, so a text edit cannot invalidate it. Corpus-scoped variant changes wait for dependencies (step-4 item 3), because they change what queries over other documents can follow. Span-scoped variants stay refused in text edits until scope ranges can be remapped.
6. Fixtures: both directions of changed interpretation (to a new Entity, and to unresolved), and a chained kind-change pair (reusable to mention, then mention back to reusable referencing doc02's existing HC Entity).

The assistant planned fold-in, rule relaxation and fixtures as three checkpoints, then landed fold-in and relaxation as one checkpoint, because a fold-in under the old correction rules would have been an intermediate rule set built only to be replaced.

**Checkpoint D, completed 2026-10-22.** `admit_replacement` in `replace.py` admits every replacement, with or without a text change: it calls `admit`, probes the graph on a first attempt, and refuses a retired or fresh group, or an added occurrence, without a TextChange (`rebuild_required`), because nothing else rebuilds the document's markers and facts. `unchanged_occurrences` and the correction path's separate admission are deleted, and `TextChange.preflight` no longer admits. `admit` applies these rules, in order, with the gate in brackets:

| Rule | Code |
|---|---|
| `check_text_present` | `empty_text` |
| `check_source_identity`, `check_next_revision` | `not_admitted`, `source_changed` |
| `map_origins`, `check_old_slices`, `check_targets_exist`, `check_single_origin`, `check_same_text` | `occurrence_changed` |
| [unchanged text] `check_same_spans` | `occurrence_moved` |
| `check_new_slices` | `occurrence_changed` |
| `group_fate`, `check_fresh_keys`, `check_unused_entity_ids`, [first attempt] `check_revision_scoped_ids` | `fresh_key_reused`, `fresh_uuid_reused`, `fresh_uuid_not_derived` |
| `check_continuing_resolutions` | `continuing_resolution_changed` |
| `check_fresh_resolution_ids`, `check_one_resolution_per_fresh_group` | `not_admitted` |
| `check_mention_recipes` | `mention_recipe_changed` |
| `check_reusable_recipes` | `reusable_recipe_changed` |
| [first attempt] `check_derived_entity_ids` | `entity_uuid_not_derived` |
| `check_scoped_variants` | `variant_changed` |
| `check_new_variant_keys` | `variant_key_reused` |
| [changed text] `check_continuing_decisions` | `continuing_decision_changed` |
| [changed text] `check_no_span_variants` | `span_variant_in_text_edit` |

After `admit`, `check_absent_from_graph` refuses a fresh mention UUID (`fresh_uuid_in_graph`) or a new reusable UUID (`entity_uuid_in_graph`) that is already in the graph. A new reusable Entity is exempt from derivation and the probe only when a resolution or variant lists a corpus input that names it, so input validation proves it exists and matches its hash.

Behavior changes:
- With unchanged text, a continuing group may change its reviewed decision in place, and every carried-over occurrence keeps its exact span. With changed text, a continuing group keeps its decision.
- A correction is now held to the full rule set. Before, only text inputs and mention groups had to stay identical. It may no longer change corpus- or span-scoped variants, a continuing mention recipe or a retained reusable recipe, or rename a resolution record, and a new Entity must be derived or corpus-referenced.
- A text edit may add or drop reusable recipes and change document-scoped variants, and a fresh group may resolve to a new derived Entity.
- The captured correction's revised controller is now the derived UUID for key r01 at revision 2 (`ce975bb8-61e4-57b1-af7c-fe9215402851` for the standard fixture identity). Roots made before keep the old fixture ID as history. A `revise` that failed on such a root cannot be retried with `revise`, because the retry would carry the new ID.
- Unchanged text with a TextChange is admitted. Empty text is refused by its own rule.
- Changing a document-scoped variant also changes which Entities retrieve that document's facts. The effect stays inside the document.

The oracle covers the 540,045 fate worlds, the 18,842 stable worlds again with unchanged text, and a `DECISIONS` table in `support/occurrence_worlds.py`. Each row names a spec rule and states its expected outcome for a text edit, for unchanged text and, where it matters, on a retry. The table is written from the rules, not computed by an independent model like group fate. `support/occurrence_mutants.py` breaks each of 25 rules.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-22 with loopback embeddings: 282 unit tests passed. `support/occurrence_check.py` passed on all 540,045 fate worlds (about 100 s alone, 119 s under load), and `--mutants` caught all 25 rule breaks. The ledger check passed with `PINNED` unchanged at 3828 nodes and 3717 sequences. `verify.py journey all` gave 736 PASS and 0 FAIL in 37 runs on `f90652d`. The last commit only adds the added-occurrence refusal and two tests, and journey R1 gave 27 PASS on it. The 36 native integration tests in the nine files that drive the touched modules passed (722 s). Three thermo reviews found two medium holes and four low issues, all fixed with a test that failed first. A correction could move an occurrence to another span with the same text. An unreferenced corpus input let a new Entity skip derivation. A correction could add an occurrence without a rebuild. Empty text was no longer refused.

**Checkpoint E, completed 2026-10-22.** Four captured fixtures on doc01 of a `chunked-fixture` root, which the user approved on 2026-10-22. The [reinterpretation guide](stage6_identity_reinterpretation.md) has the texts, spans, maps, UUIDs, runs and evidence.

- `reinterpret-new-entity` (text edit, revision 1 to 2): g01 retires; fresh g07 holds `the backup controller` and `it` and resolves (r07) to a new "Backup controller" Entity whose UUID derives from r07. A Helios controller query no longer returns doc01's fact; a Backup controller query returns g07's regenerated fact.
- `reinterpret-unresolved` (text edit, revision 1 to 2): g01 retires; fresh g08 holds `A controller` and `it` and is unresolved. Its fact is in the graph with evidence, and no query returns it.
- `change-kind-to-mention` (unchanged text, revision 1 to 2): doc01 drops v01 and its HC recipe; fresh mention group g09 `HC` resolves to the Helios controller. The shared HC edge and the HC Entity survive on doc02's claim. An HC query no longer reaches doc01's fact, because a local mention is not a global name.
- `change-kind-to-reusable` (unchanged text, revision 2 to 3): g09 retires; doc01 references doc02's existing HC Entity through a corpus input that v02 lists, and adds the doc01-scoped variant v02. The HC edge regains doc01's contribution, one HC Entity remains with two owners, and an HC query returns the same two facts as at revision 1.

The two kind changes are the first runs of a TextChange with equal texts. It needed no code change: the document was forgotten, ingested again and rebuilt with the same chunk IDs. Shared changes: `declare_group` takes a status and an optional target; `require_fresh_doc01` became `require_root`; `mention_fact` in `native.py` is the one fact-and-evidence lookup; each command may list retrieval `queries`; `transition_summary` reports each fresh group's resolution and fact.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-22 with loopback embeddings: 299 unit tests passed. 45 native integration tests passed (983 s), covering the two new native files and every module the change touched. `verify.py journey all` gave 965 PASS and 0 FAIL in 49 runs on `63b30b7`. The admission code, `replace.py` and `text_changes.py` did not change, so the occurrence and ledger checks were not rerun. Two thermo reviews found no medium or high issue; their simplifications are in the branch: unique group keys g07 to g09 instead of reusing g03, four flat commands, and one fact-and-evidence lookup. A third review compared every earlier captured describer with `main` and found them byte-identical.

### Forget, decided and built 2026-10-22

The user decided on 2026-10-22, for `forget`:

- A forgotten source leaves a record of its last revision, so a re-added document continues at the next revision and never derives a retired UUID again.
- `forget` is a separate command from `withdraw`, which keeps the original Data and facts.
- Verification is the ledger model plus fault-stage journeys, with no small-world oracle.

Definition of "depends on", approved 2026-10-22. Source X consumed Y when X's description lists Y as an input. A source depends on doc01 when it consumed doc01's text, a span or a chunk of it, or lists as a corpus input an Entity that only doc01 owns. An Entity that another source also owns survives with unchanged fields, so a source that read it is unaffected. Indirect dependence through a third document belongs to step-4 item 3.

Forget has two intents, which the user raised on 2026-10-22. Cleanup ("no longer needed") may safely refuse when dependents exist. Erasure ("must go": privacy, legal, licence, a fabricated source) must not be blocked by dependents, and step 5 will route Cognee's own deletes here. Both intents agree when nothing depends on the source, so build that part now. While dependents exist, `forget` refuses and lists them; this refusal is a placeholder until item 3 decides what erasure does to dependents (withhold them from retrieval until reconsidered, remove them too, or withhold by default with an explicit removal option). Record as an item-3 requirement: when a source must go, its dependents cannot block it.

Dependency examples for item 3, given to the user on 2026-10-22: a glossary or abbreviation list, a protocol or method document, an instrument calibration record, a review or meta-analysis, and measurement records naming a sample defined elsewhere. Corrections and retractions are left out until time is handled explicitly (user, 2026-10-22).

The user decided on 2026-10-22 to retire the reviewed roots under `outputs/stage6_*` as history. Their result files stay readable, but current code need not open them, so delete `TextChange.from_plan`'s legacy readers and the tracked follow-up that kept them. Run `support/occurrence_check.py` for any change to `admission.py`.

**Checkpoint F, completed 2026-10-22.** `forget --source <doc> --expected-revision N` removes a current source's original Data and its identity Data through Cognee's native document deletion, with the chunks, facts, evidence, markers, identity edges and contributions, and every Entity only it owned. Entities and shared edges another source owns survive with only their contributions. The ledger row ends `forgotten` and keeps its revision and description. `readd` publishes the source again at the next revision through `Publisher.readd`: every group's UUID is derived again, and an Entity the forget removed comes back under a new UUID, derived from a key that names it or, for an Entity nothing names, from the removed UUID. `status` shows a forgotten row; `retrieve` neither returns it nor lists it as unavailable. The [forget guide](stage6_identity_forget.md) has the commands, results, UUIDs, scope and a list of what survives a forget.

- Dependents are found by `dependents()` in `retirement.py`, which text changes use too. A source whose forget is unfinished fences its inputs: a publish, re-add or replace that consumes them is refused (`retiring_source`). Forget checks dependents again after `begin`.
- Forget has six fault stages. Two of them fail inside Cognee's own delete, after it commits the Data row and before it sweeps evidence rows and stored files; `reconcile` finishes the sweep. A stored file another Data row still references is kept and does not block the forget.
- Reconcile of a failed publication now rebuilds its captured facts (`write_semantics` skips a chunk whose fact and evidence exist), which also fixes a failed first publication that could not be reconciled before.
- The legacy plan readers are deleted. A plan without `occurrence_map` is refused with `recovery_plan`; the reviewed `outputs/stage6_*` roots are history.
- Shared retirement code moved from `withdraw.py` to `retirement.py`; fixture drivers are in `forget_fixture.py`; `RecordStore.row(source)` replaces row scans.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-22 with loopback embeddings: 315 unit tests passed. The full native integration suite passed (59 tests, 1232 s). The ledger check passed with `PINNED` at 5889 nodes and 5770 sequences, and its mutants caught all 40 breaks, including 10 new ones for forget and re-add. `support/occurrence_check.py` and its mutants passed. `verify.py journey all` gave 1159 PASS and 0 FAIL in 58 runs on `5f5dd37`, including journeys F1 to F4 in `source-lifecycle.md`. Five thermo reviews over three rounds found five medium issues, all fixed with a test that failed first: a native delete that commits before sweeping evidence and files, an unfenced half-finished forget, retiring owners counted as independent, a re-add that could recreate a removed Entity, and a shared stored file that blocked a forget. The remaining low items are tracked follow-ups.

### Ledger refactor, completed 2026-10-22

A refactor with no behavior change, from the Checkpoint F code review.

- `RecordStore.begin` reads a transition table in `storage.py` (`TRANSITIONS`, keyed by row state and saved plan operation, with `REQUIRED_PLANS` and the pure `admissible()`), instead of a chain of conditionals. Each owned failed row names its owner. begin keeps main's final check that an admitted advance is exactly one revision.
- `RecordStore.rows()` and `row()` return a frozen `PublicationRow`; `RETIRED_STATES` lives in `storage.py`.
- `stages.py` holds one attempt frame, `run_attempt`, shared by replace, withdraw and forget: begin, ordered stages with fault injection, complete, and the recovery-required failure path. `__main__` builds `--fault-stage` from each operation's stages.
- `support/ledger_model.py` states each Method fact once (`begins`, `owns_terminal`, `recovers`, `requires_plan`). The ledger mutants were rewritten for the table.
- The caller pre-checks in `publish.py`, `forget.py` and `replace.py` stay earlier than begin and refuse differently on some rows; each says so in a comment.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-22 with loopback embeddings: an equivalence harness ran 26,240 begin calls against `main` with 0 differences in code, message or written row. The ledger check passed with `PINNED` unchanged at 5889 nodes and 5770 sequences, and the `--mutants` output is byte-identical to main's. A scope comparison showed each revision break admits exactly the calls main's break admits. 372 unit tests passed, including a 45-case begin matrix that pins each code and message and a completeness test over every table entry. The occurrence check and its mutants passed. The full native suite passed (59 tests). `verify.py journey all` gave 1159 PASS and 0 FAIL in 58 runs on `7ffd87a`, the same totals as before the refactor. Two thermo reviews found no behavior change beyond two the author admitted (withdrawal fault messages and the `replace_saved` fault point); both were restored. The second round's changes were restorations checked against main, so no further review ran.

### Dependencies, decided and built 2026-10-23

The user decided on 2026-10-22 and 2026-10-23, for step-4 item 3:

1. When a consumed input changes, the affected dependents are withheld from retrieval until refreshed. They are not blocked, as before, and they are not served with a stale flag. The unit is one decision: only decisions whose inputs cite the changed input are withheld, with the facts generated from their groups. Refresh starts at once. The edit records the withholding before it completes, mechanical re-checks run at once, and anything that needs judgment becomes a "refresh needed" item. Today a reviewer clears it. Once Describe exists (step 6), the same trigger runs Describe.
2. Erasure's effect on dependents is not in this checkpoint. The user leans toward "withhold by default, with an explicit option to remove too", with removal per decision: the decisions that cite the erased input, and what only they produced. `forget` still refuses a source with dependents.
3. A reviewer may re-confirm a withheld decision. A re-confirm records the new fingerprint and who confirmed it. No IDs change.
4. The first example is a glossary. A second example, outside identity, comes in a later checkpoint.
5. Users see the reasons "input changed" (`input_changed`) and "input removed" (`input_removed`), never "input forgotten".

These decisions supersede the design handoff's "callers select whole documents": the unit of withholding is one decision, not one document. A reviewer model (Sonnet) checked the spec against these decisions and the code before implementation, gave the verdict "proceed" and added 15 resolutions. The [dependencies guide](stage6_identity_dependencies.md) records them as the data shapes, rules, fixture and choices below.

**Checkpoint H, completed 2026-10-23.**

What changes for users:

- A text edit of a document that another source read is admitted. Before, it was refused with `dependent_source`. One refusal stays: an edit that drops a reusable recipe only the edited source owns, while another source reads that Entity as a corpus input (`reject_sole_owned_readers`).
- The edit withholds only the dependents' decisions that read what changed. A span unchanged in place stays valid. A span whose text is found exactly once elsewhere has moved: it is withheld until the refresh writes its new range. A changed span, a chunk or a whole text needs review. A changed or missing corpus field that a decision read withholds that decision at retrieval, not the whole source, and writes no recovery event.
- `retrieve` lists each withheld decision in `unavailable_sources`, with `assignment_id` and the reason. `status` gains `withholdings`, `withheld_decisions` and `refresh_needed`.
- New commands: `glossary-fixture`, `edit-glossary`, `reconfirm`, `replace-decision` and `refresh-dependents`. `reconcile`, `forget` and `readd` work on glossary roots.

The data shape:

- **The withholding table** (`lab_identity_withholdings`, module `withholding.py`) holds one row per withheld decision and input: key (dataset, dependent source, assignment, input key), with the edited source and its revision, the reason, the status (`remap` or `refresh_needed`), the old and new digests and, for a moved span, the new range. Keying by input lets a later checkpoint chain withholdings through saved records. The table lives beside the ledger, so `RecordStore`, `TRANSITIONS` and the ledger check's `PINNED` counts are unchanged, and withholding writes no recovery events.
- **The withheld-decision set** maps source to assignment to (reason, status, the input keys that withhold it). `withheld_decisions(rows, table)` merges the rows that still apply with one rule derived from the ledger: while a consumed source's text change is pending or failed, every decision citing that document is withheld with `input_changed` and status `edit_unfinished`. So a crash before the rows are written never serves a dependent stale. Retrieval and `status` share one live-validation pass (`live_held` in `retrieve.py`), so a decision withheld only by live drift, such as a changed corpus field, shows in `status` and can be reviewed.

The attestation rule (`check_reconfirmations`, code `reconfirm_unattested`) is per producer and foreign input key. A decision under a producer the old revision has may cite only foreign input keys, its group's included, that this producer's decisions cited in the old revision. A continuing decision that keeps its reviewed fields but changes its foreign inputs in any way also names a producer new in this revision. A producer new in this revision is unconstrained, and a pure range move keeps its key and passes. The rule rests on a second one: `check_foreign_inputs` keeps the content under an existing foreign key immutable (same kind, document and digest; only a span's range may move), so a producer that cited a key saw that key's content. The session owner set this rule in the fourth fix round, after three reviews each found one more shape of the same bypass (the same key, a new key, a key a sibling decision's re-confirm had added). It is reversible.

Refresh after the edit: every text-change command (`edit-glossary`, `edit-text`, the occurrence commands, and a `reconcile` that completes a text change) runs `refresh_dependents` after the edit completes. The writer reservation forbids running it inside the edit. Each dependent with a moved span gets an unchanged-text replacement with the new range and no decision change; in the fixture, the insertion takes doc01 from revision 1 to 2. A refresh that fails, from any exception, does not fail the completed edit: the command reports `refresh_failed` beside it, and `refresh-dependents` or `reconcile` finishes the rest.

Process, run by the assistant and its subagents on 2026-10-23. Opus at high effort wrote the implementation. Four fix rounds followed `/pstack:thermos` reviews:

1. Nineteen items. Among them, a re-confirm that dropped or replaced a foreign key without a new producer, corpus inputs that no longer had to exist at admission, live withholding that `status` and the reviewers could not see, and a refresh that ran only from the glossary commands.
2. A regression in the corpus-existence rule for inputs cited only by a group, a refresh that resumed a stale saved revision, one live-validation pass shared by retrieval and `status`, and a table of each command's fault stages.
3. A new producer for any decision that cites a foreign key the old revision lacked. The implementer stopped because one oracle row it had written contradicted the brief. The session owner chose option (a), the stricter rule, and the row flipped.
4. The per-producer attestation invariant above, after a third bypass shape; the rule-5 oracle rows moved to `support/dependency_worlds.py`; `refresh_dependents` reports any exception after a completed edit.

A final targeted review found the branch merge-ready and listed the follow-ups recorded below.

Evidence, run by the assistant on the user's Mac on 2026-10-23 with loopback embeddings:

- `verify.py journey all` on `2fcf78c`: 1287 PASS and 0 FAIL in 68 runs. Later commits change only documentation and the `check_reconfirmations` docstring. P5 calls the embedding API and was skipped. Earlier full runs gave 1286 PASS and 0 FAIL on `5c50a6f` and on `b04ffde`. The one extra row is in D1 to D6, which grew from 127 to 128 PASS rows in fix round 2; the other journeys' totals are unchanged at 1159.
- Journeys D1 to D6 in `.claude/skills/verify/features/dependencies.md`: 128 PASS and 0 FAIL in 10 runs (D5 runs five fault stages).
- Unit suite on `12c8d30`: 405 passed, 67 deselected.
- `support/occurrence_check.py`: PASS on all 540,045 fate worlds, with 50 decision rows (25 for rule 5). `--mutants`: all 31 breaks caught.
- `support/ledger_check.py`: PASS, `PINNED` unchanged at 5889 nodes and 5770 sequences. `--mutants`: the 40 breaks as expected.
- Integration: the full suite gave 64 passed in 1366 s on `5c50a6f`. `tests/test_identity_native.py` with `tests/test_identity_dependencies_native.py` gave 19 passed on `7181689`. `tests/test_identity_dependencies_native.py` gave 8 passed on `12c8d30`.

No user-reviewed glossary root exists yet. The [dependencies guide](stage6_identity_dependencies.md#evidence) has each round's evidence.

### Erasure, decided and built 2026-10-23

The user decided on 2026-10-23, for erasure (step-4 items 3 and 4):

1. There is one command, `forget`, and it always erases. There is no restorable forget.
2. After verification the forgotten row keeps only identifiers: IDs, including every mention and Entity UUID its last revision used, digests, the revision and the time of the forget. Occurrence texts, recipe names and descriptions, and every excerpt go. The forget plan keeps IDs, refs and ranges and loses its text fields. Recovery-event messages of the source go; IDs, stage and attempts stay.
3. Fixture input files are the caller's own inputs. The report and the dry run list them, and a forget never deletes them.
4. Dependents are removed, not withheld. This reverses the earlier lean toward "withhold by default" (decision 2 of Checkpoint H). A dependent decision is a resolution, with its group, or a variant assignment whose inputs cite the forgotten source: its text, a span or chunk of it, or an Entity the forget removes. Its removal is a new revision of the dependent. A resolution's group becomes unresolved and keeps its mention and local fact. A variant is dropped with this dependent's contribution to its edge. A recipe the dependent declared that no remaining decision names goes with it. Inputs nothing cites any more are dropped.
5. A forget that affects no other source runs at once. A forget that would change another source's decisions needs `--confirm <token>`. `forget --dry-run` writes nothing and returns the impact and the token, a hash of the affected-decision set. A changed impact refuses with `impact_changed`. Thresholds for what is significant belong to the caller, never to the code.
6. `readd` stays, as a fresh publication from the caller's files at the next revision. The tombstone's UUID lists forbid a forgotten mention or Entity UUID from returning. The comparison with the kept description goes away.
7. Any source can be forgotten: current, withdrawn, or one whose first publication failed. This clears two Checkpoint F follow-ups.
8. Old formats are not read. A forgotten row that still holds its description is refused at the `rows()` boundary. Development roots that hold one are regenerated.
9. Withholding stays for text edits (Checkpoint H), where the input still exists and may be re-confirmed. The per-decision removal reviewer command proposed earlier is dropped.
10. Saved-record inputs, chains and the non-identity example are deferred.

A reviewer checked the spec against these decisions and the code before implementation and gave the verdict "proceed", with ten resolutions: erase the source first, then write each dependent's removal revision under its own reservation; derive "dependents unfinished" from live rows, with no new ledger state; check the token before `begin` and again in the stage `forget_impact`; write the tombstone as JSON in the existing `description` column, in the transaction that flips the state; and admit a removal under a removal producer through a new rule. The session owner reported three defaults to the user, each reversible:

- A dependent that is itself pending or failed does not block the forget (erasure is never blocked by dependents). The dry run lists it and the token covers it.
- Erasure is logical. LanceDB's soft-deleted rows and the graph's and SQLite's free pages stay until the stores compact them; the dry run lists them under `residue`.
- A dependent's failed first publication or failed text change finishes with the removal applied to its saved revision (the erasure retry). Without it such a dependent could never converge, because its own retry needs the forgotten document. A failed replacement takes the same path since fix round 1.

**Checkpoint I, completed 2026-10-23.**

What changes for users:

- `forget` takes `--dry-run` and `--confirm <token>`. The dry run reports each dependent, each decision it would remove with the input that causes it, the Entities that would go, the facts that would lose their identity link, the traces the tombstone scrubs, the caller's files it leaves and the token. Without dependents a forget runs at once. With dependents and no token it exits 1 with `confirmation_required` and the report.
- After the source is erased, each dependent gets a removal revision under a producer named for the forget. A dependent removal that fails is reported beside the completed forget (`dependents_failed`, exit 1). `forget` or `reconcile` on the forgotten source resumes it. `readd` waits until no dependent is unfinished. Meanwhile Checkpoint H's live validation withholds each citing decision with `input_removed`.
- `status` shows a forgotten row as a tombstone with a scrubbed plan. `readd` publishes the caller's files as written, under fresh UUIDs.
- The `dependent_source` refusal of a forget is gone. Text edits keep it, with `reject_sole_owned_readers`. The fence (`retiring_source`) stays.

The data shape and rules:

- **The tombstone** (`models.Tombstone`) holds the identity, original data and dataset IDs, the digests, the revision, the time of the forget, the last revision's mention and reusable Entity UUIDs and the plan snapshot's IDs. `storage.scrubbed_plan` keeps a whitelist of plan fields (`FORGOTTEN_PLAN_FIELDS`) and `scrubbed_event` clears every message of the source's recovery events, resolved ones included.
- **The impact** (`erasure.impact`) comes from saved descriptions and the forget plan, never from the live graph. One predicate, `dependency.citations`, decides whether a reader cites a document or an Entity; forget's erasure, a text edit's withholding and the retiring-source fence all use it. `revisions` yields each dependent's removal revision.
- **The removal rules** (`erasure_rules.py`). `check_erasure_removals` admits a removal under the removal producer only when every decision citing the forgotten document or a removed Entity is dropped or unresolved, nothing else changes, and no recipe another saved source reads is dropped. The ledger binds a removal producer to a forgotten row. `check_retry_chain` checks each step of an erasure retry against the forgotten rows. `admit_readd` refuses a forgotten mention UUID in any role.
- **The ledger.** `forget` begins on a withdrawn row and on a failed first publication. `complete` writes the tombstone. `begin` admits an erasure retry in place of a failed attempt (`supersedes`), and reads every row only for that case. The ledger check gained property P7 (a forgotten row holds no description content), now in `support/ledger_properties.py`.

Process, run by the assistant and its subagents on 2026-10-23. A subagent wrote the implementation. Four rounds of `/pstack:thermos` reviews (bug and quality, Opus) followed; each fix came with a regression test that failed first.

1. A dependent whose own replacement had failed never converged (HIGH, probed). A removal was not bound to a real forget (MEDIUM, probed). A re-add could reuse a forgotten mention UUID. The token did not cover each dependent's revision. The fixture check shrank after the scrub. The quality review moved the erasure rules to their own module, parsed a row once and put forget's dependents on one predicate.
2. A dependent's failed text change could not finish (MEDIUM). The ledger accepted any description at an erasure retry (LOW, probed). A removal step could remove nothing or only part of what its forget removed.
3. An erasure retry of a failed first publication left the dropped recipe's node, name vector and edge contribution, so the HC query still seeded HC (HIGH, reproduced). A reconcile that supersedes a description now retires what it wrote.
4. A final targeted review of `d6133c7` found the branch merge-ready on correctness and listed the follow-ups below.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-23 with loopback embeddings:

- `verify.py journey all` on `d6133c7`: 1439 PASS and 0 FAIL in 80 runs. P5 calls the embedding API and was skipped. Earlier full runs on the branch: 1407 PASS on `d94b0a3`, 1416 on `686dc16` and 1429 on `af7218a`, each with 0 FAIL.
- Journeys F1 to F14 in `.claude/skills/verify/features/source-lifecycle.md` cover the dry run, the confirmation, the removal revisions, interrupted removals, the erasure retries, forget of any source, the glossary and re-add.
- Unit suite: 448 passed, 81 deselected.
- `support/ledger_check.py`: PASS at depth 5, with `PINNED` at 8504 nodes and 8349 sequences (from 5889 and 5770 at Checkpoint H), and at depth 6 with 56089 nodes. `--mutants`: all 51 breaks caught.
- `support/occurrence_check.py` and `--mutants`: PASS, with the erasure decision rows in `support/erasure_worlds.py`.
- Integration: the native forget, dependencies and erasure-retry tests gave 36 passed in 905 s on `ae64aed`. The full suite gave 76 passed in 1806 s on `d94b0a3`.

No user-reviewed erasure root exists yet. The [forget guide](stage6_identity_forget.md#evidence) has each round's evidence.

### Chains (J1), decided and built 2026-10-23

The user decided on 2026-10-23, for saved-record inputs and chains (step-4 item 3):

1. Citable records are decisions only: mention resolutions and variant assignments. The citation format and the chain logic stay generic over record type, so another record type needs no redesign. Facts as citable records wait for a separate discussion with the user, because they overlap the semantic-output item. Native Cognee edges stay outside withholding.
2. Withholding spreads down the whole chain. It is derived at retrieval with no new rows, and the reason shown is `input_changed`. A re-confirm upstream releases downstream. A replacement upstream changes the cited record, so downstream needs its own review. Admission refuses cycles.
3. Erasure cascades down the chain in dependency order, with one dry run, one token and one confirmation for every level (Checkpoint J2).
4. The non-identity example is deferred as later work.

A reviewer checked the spec against these decisions and the code at `98ecaca` before implementation and gave the verdict "proceed", with 16 resolutions. The first split the work into J1 (citations, admission, cycles, withholding down the chain, the reviewer commands, the chain fixture and its checks) and J2 (the erasure cascade, with the ledger work it needs). The others, in short:

- A resolution's fingerprint also names its group's mention UUID (`group_entity_id`). Mention UUIDs are never reused, so a key and group key that return later with the same target cannot release a citer of the old mention (an ABA release). With that, validation drops the pinned-revision test and the fingerprint decides.
- The scope checks (same dataset, no self-citation) run on every path, including a first publication and a re-add. The record checks (served source, record present, current revision, fingerprint) run on a first attempt only, so a retry reuses its saved intent and a drifted citation is withheld instead of refused forever.
- The cycle check reads the latest saved description of every source that is not retired, so a failed attempt's citation is already an edge and its retry is not refused. It runs once, before `begin`; the writer reservation serializes writers.
- Every `validate_inputs` caller passes the saved-record reader. Retrieval and `status` share one live pass with the closure, so they agree.
- The reader checks an unfinished cited source before anything else, so a pending upstream never shows `input_removed`. Status precedence is `remap` < `refresh_needed` < `upstream_withheld` < `edit_unfinished`. `upstream_withheld` is derived only; it does not fit the table's `String(16)` column.
- A text edit's withholding keeps naming only the document, so an edit of a cited source writes no rows for its citers. A group may cite a saved record, with no new rule.
- For J2: removed records carry their pre-removal digest, cascade targets only shrink after confirmation, and removal producers are immutable.
- `support/chain_check.py` runs in CI and in the verify routine.

The session owner reported these defaults to the user, each reversible:

- Cycles are refused per source, not per decision. The rule also refuses every mutual citation between two sources, even when no decision cycle exists.
- A replacement upstream under a new key, and a withdrawn upstream, show `input_removed` downstream, as in Checkpoint H.
- The derived status `upstream_withheld` is new and user-visible. No reviewer answers it; it releases when the cited decision does.
- CLAUDE.md's verify step 2 lists `support/chain_check.py` and `--mutants`, for changes to `admission.py`, `records.py`, `chains.py`, `withholding.py` or `erasure.py`, and CI runs the check (about 200 s). This amends the routine the user agreed on 2026-10-21.
- Until J2, a forget whose removal would remove a record another source cites is refused with `chain_erasure_pending`. Chains did not exist before J1, so the refusal removes no capability.

**Checkpoint J1, completed 2026-10-23.**

What changes for users:

- A resolution or a variant assignment may list a saved-record input that cites a decision of another source in the same dataset. Before, admission refused every saved-record input.
- A citing decision is withheld when its cited record changes in place (`input_changed`, `refresh_needed`), when the record's key is gone or its source is withdrawn or forgotten (`input_removed`, `refresh_needed`), when the cited source is unfinished (`input_changed`, `edit_unfinished`), and when the cited decision is itself withheld (`input_changed`, `upstream_withheld`). Nothing is written, so a release upstream releases downstream on the next read.
- `reconfirm` re-cites a changed record as it is now, under a new key and a new producer. Every review refuses an `upstream_withheld` decision. The review gate waits while any source the reviewed source cites is unfinished. `replace-decision --decision r01` makes r01 unresolved in place.
- New refusals: `self_citation`, `record_source_unavailable`, `record_missing`, `record_stale`, `record_digest`, `citation_cycle` and, for a forget, `chain_erasure_pending`. The fence (`retiring_source`) also refuses a citation of a record that an unfinished forget's level-1 removal will remove.
- New commands: `glossary-fixture --chain` adds doc03, whose c01 cites doc01's r01 and whose c02 cites doc01's v01, and `cite-record` drives each refused citation through the CLI.

The data shape and rules:

- **A citation** (`models.SavedRecordInput`) names the dataset, the cited identity source, `record_type`, `record_id` (the decision key), the revision it was made at (provenance only) and the record's fingerprint.
- **The registry** (`records.REGISTRY`) maps each record type to where its records live, its fingerprint projection and its `held` hook. Admission, validation and withholding read records only through it. An import-time check ties it to `models.RecordType`.
- **The source graph** (`chains.source_graph`) has an edge from A to B when A cites any record of B. `chains.check_citation_cycles` keeps it acyclic.
- **The live pass** (`chains.live_pass`) validates each served source through `withholding.record_reader`, combines the table, drift and the reader in `withholding.held_by`, then withholds down the chain to a fixpoint (`chains.upstream_closure`). Retrieval passes `retrieve.live_drift`; the chain check passes a drift built from the reader, so it runs the real pass. "Unfinished" is one rule, `withholding.unfinished`: not retired and not served (pending, failed, or current but not verified), or its own input fails live validation.
- `RecordStore`, `TRANSITIONS`, the ledger model and the withholding table are unchanged.

Process, run by the assistant and its subagents on 2026-10-23. A subagent wrote the implementation in six commits, to `637bfcc`. One round of `/pstack:thermos` reviews (bug and quality, Opus) followed, then fix round 1 in four commits, to `8167c25`; each bug fix came with a test that failed first.

1. The bug review found the branch merge-ready except M1 and two low items. M1: a forget whose level-1 removals were not all written let a new source cite a dependent's record that the removal then removed, leaving the citer withheld and never cascaded. The fence now refuses it, and the resume path runs the interim refusal. L2: an unverified cited source offered a review the reviewer could not complete; it is now `edit_unfinished`. L1, dismissed: the record checks run only before the writer reservation, and live withholding catches drift after them.
2. The quality review found that the closure assumed every record is a decision (fixed: the registry's `held` hook) and that the chain check tested a hand copy of the live pass (fixed: the shared `chains.live_pass`). It also moved the reviewer commands to `review.py` (`glossary_fixture.py` from 735 to 523 lines) and made `cite-record` one call.
3. A final targeted review of `8167c25` found the branch merge-ready. `2002a77` fixed the fence's remedy wording ("run forget on that source again first") and a comment in the occurrence check.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-23 with loopback embeddings:

- `verify.py journey all`: 1519 PASS and 0 FAIL in 86 runs on `637bfcc` and again on `8167c25`. P5 calls the embedding API and was skipped.
- Journeys D7 to D11 in `.claude/skills/verify/features/dependencies.md`: 63 PASS and 0 FAIL. They cover the chain hold, the release by an upstream re-confirm, the replacement under a new key, the in-place replacement with doc03's re-confirm, the refused citations, the interim erasure refusal, the level-1 removal and an unfinished upstream.
- Unit suite on `2002a77`: 487 passed, 85 deselected.
- `support/chain_check.py`: PASS on 543 acyclic citation graphs of up to four sources, 16,384 cycle cases and 2,224,128 withholding worlds (about 200 s). `--mutants`: 3 of 3 breaks caught.
- `support/occurrence_check.py`: PASS, with 33 rule-5 rows and 23 rule-6 rows. `--mutants`: every break caught, including the two new ones.
- `support/ledger_check.py`: PASS, `PINNED` unchanged at 8504 nodes and 8349 sequences; `RecordStore` is unchanged.
- Integration: the native chains, dependencies and forget tests gave 37 passed in 837 s on `8167c25`.

No user-reviewed chain root exists yet. The [chains guide](stage6_identity_chains.md#evidence) has each round's evidence.

### Cascade (J2), built 2026-10-24

The user decided on 2026-10-23 (chains decision 3) that erasure cascades down the chain in dependency order, with one dry run, one token and one confirmation for every level. Checkpoint J2 builds the ten J2 items of the spec review: the interim refusal removed, levels by longest path, one token, ordered writes and resume, the inductive gate, pre-removal digests, targets that only shrink after confirmation, immutable removal producers, a removal side generic over record type, and journeys F16 onward with the cascade half of the chain check.

**Checkpoint J2, completed 2026-10-24.**

What changes for users:

- A forget whose removal would remove a record another source cites is no longer refused. The J1 interim refusal `chain_erasure_pending` is gone.
- A dependent that cites a record another dependent's removal removes, as that record was before the removal, is one level below that dependent, at its longest path. It gets one removal revision for everything it loses. A citation made after a removal reads the record as it is now and is not cascaded, even if the record later returns to its old fingerprint.
- The dry run lists `levels`, each with its dependents, and `counts.levels`. One token covers every level, with each dependent's level and the records it removes and cites. One `--confirm <token>` writes the removal revisions in level order, each under its own writer reservation. A blocked dependent waits (`dependent_unfinished`), and so does every removal below it that cites what it removes (`waits_for`). `forget` or `reconcile` on the forgotten source resumes, and `readd` waits while any level is unfinished.
- New refusals: `removal_producer_changed` (a later revision drops or changes a removal producer), `erasure_unbound` and `erasure_incomplete` for a removal that does not cite exactly its bound records or lists them at the wrong revision, and `cascade_unfinished` (below). The fence `retiring_source` now covers every level of every unfinished forget.
- New fault stage: `forget_cascade_revision`, which fails each removal revision below level 1 once level 1 is written.

The data shape and rules:

- **A removed record** (`records.RemovedRecord`) names its source, record type and key, its fingerprint before the removal and `last_revision`, the last served revision of its source that held it, capped at the row's verified revision. A citation reads a removed record when it pins that fingerprint at that revision or before (`RemovedRecord.reads`).
- **The removal producer** lists `removed_records` and, below level 1, `cited_records`. Its key must be `forget_<forgotten identity ID>_r<revision>`. Admission accepts the cited records only when each is bound: a written removal producer of the same forget lists it, and that producer is bound in turn, back to the tombstone. A producer counts as written unless it is new in the row's revision and only a pending or failed attempt holds it (`PublicationRow.holds_served`).
- **The cascade** (`erasure.cascade`) is computed from the saved rows to one fixpoint that starts from the records written removals removed (`erasure_rules.bound_removals`, over `written_claims`). Levels come from one function, `erasure_rules.levels`. `impact`, `remaining`, `unfinished` and `finish_dependents` all read it, and `erasure.ready` gives the write order. Nothing new is stored in the ledger.
- **The record registry** answers every record-type fact the erasure reads, through the `RecordKind` hooks `removed`, `inputs`, `outcome`, `stripped`, `unlinked`, `names` and `held`, so the removal side is generic over record type.
- **Retiring a source that holds a removal.** `erasure.refuse_unfinished_cascade` refuses a `withdraw` or `forget` of a source holding a removal of an unfinished forget when retiring it would change what the cascade still does to any other source (`erasure.reach`; `details.freed`).

The session owner reported these defaults to the user during J2, each reversible:

- A withdrawal or forget of a source that holds a removal of an unfinished forget is refused (`cascade_unfinished`) when it would change what the cascade still does to any other source. The remedy is to run `forget` on the forgotten source again first. Finishing the original forget is never refused.
- A retry of an erasure step rechecks the binding only for the step that is new in that begin. A first attempt always checks the binding. This was the orchestrator's call under the user's standing autonomy, and it can be tightened.

Process, run by the assistant and its subagents on 2026-10-24 on branch `stage6-cascade`. A subagent wrote the implementation in five commits, to `231c2e6`. Four rounds of `/pstack:thermos` reviews and fixes followed, from local, untracked briefs `.audit/cascade-fix1.todo.md` to `cascade-fix4.todo.md`: round 1 in eight commits, to `9d2b47d`; round 2 in three, to `a136d06`; round 3, to `d1192ba`; round 4, to `74ec093`. Each bug fix came with a test that failed first.

1. Round 1. The bug review found M1: a removed record's last served revision was inferred from the row's state, so a reconcile of a served row that failed at the same revision dropped that row's level-2 citers from the cascade. It now comes from the ledger's verified revision. M2: when a failed removal's upstream was withdrawn, every reader of the cascade raised `KeyError`; that removal now leaves the cascade. The quality review found decision kinds hard-coded outside the registry, and a hand copy of the write order in the cascade check. Both now go through the registry and `erasure.ready`.
2. Round 2. The bug review found H1: retiring a written intermediate, or a failed attempt on it, freed every citer further down while the forget reported finished. This was present since the first build. A served removal now still binds, and `cascade_unfinished` refuses the retirement. M1': a relaxed in-place rule admitted a removal that left out the citers pinned at the served revision. A new erasure-retry step now lists exactly the verified revision.
3. Round 3. The review found the retire refusal too broad (it refused a leaf whose own failed removal was all that was left), and a completed removal stuck after its upstream withdrew, with no way out for a failed replacement or text change. The refusal now lets that leaf retire, and a retry checks the binding only for what is new in it.
4. Round 4. The review found a diamond-shaped chain that slipped past the narrowed refusal: withdrawing one intermediate left a citer's removal smaller, and the forget finished with that citer still citing a removed record. The fix stated the invariant (retiring a source never changes what the unfinished cascade does to any other source) and made the cascade check test it on every world. That check also caught an unnamed three-source shape. The same round let a removal rejected after a re-add of the forgotten source resume by its own retry.
5. A final review of `74ec093` found the branch merge-ready.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-24 with loopback embeddings:

- `verify.py journey all`: 1565 PASS on `231c2e6`, 1567 on `9d2b47d`, 1576 on `a136d06`, 1576 on `d1192ba` and 1576 in 91 runs on `74ec093`, each with 0 FAIL. P5 calls the embedding API and was skipped.
- Journeys F16 to F20 in `.claude/skills/verify/features/source-lifecycle.md`: the two-level forget, a token refused when a new level appears, a crash at the level-2 removal with its resume and the re-add that waits for it, a blocked level-2 dependent, and the refused retirement of doc01 mid-cascade.
- Unit suite on `74ec093`: 533 passed, 86 deselected.
- `support/chain_check.py`: PASS, 0 disagreements, with the cascade half (`support/cascade_check.py` over `support/cascade_worlds.py`) on 34,752 worlds: every acyclic citation graph of up to four sources, at depth up to 3, with each source in one of four states. `--mutants`: 19 of 19 breaks caught.
- `support/occurrence_check.py` and `--mutants`: PASS.
- `support/ledger_check.py`: PASS verified within bound at depth 5, `PINNED` at 9205 nodes and 9050 sequences, up from 8504 and 8349. `.claude/skills/identity-ledger/SKILL.md` explains the change: the erasure-retry rule for the served revision, and the model's split of that step into its variants. `--mutants`: 53 of 53 breaks caught.
- Integration: the four native files (forget, chains, erasure retry, dependencies) gave 41 passed.

No user-reviewed cascade root exists yet. The [forget guide](stage6_identity_forget.md#evidence) has each round's evidence.

### User decisions after J2, 2026-10-24

The user decided on 2026-10-24:

1. **Representation-kind change** (for example, a local mention becomes a shared Entity): retire the old group and declare a fresh one, as for a changed meaning. There is no in-place kind change.
2. **A direct edit of a native Entity** withholds the decisions that depend on it, with reason `input_changed`, as a text edit of a consumed document does.
3. **Facts as saved records move to step 6**, with the model that produces semantic output, after a discussion with the user. Step 4's changed-meaning item finishes with the captured fixture writer, as before.
4. **The non-identity example** is written into the roadmap and this handoff as the planned example. A measured value comes from a datasheet span, and an analysis note cites it. A datasheet edit withholds the note's use of the value, and forgetting the datasheet removes it. No work on it now. It needs architecture planning first: a new source kind with its own describer, admission and fixture.

### Readers of a changed or retired Entity or record (K), built 2026-10-24

Checkpoint K implements decisions 1 and 2 of [User decisions after J2](#user-decisions-after-j2-2026-10-24) and chains decision 2 of 2026-10-23: withholding spreads down the chain, a re-confirm upstream releases downstream, and a replacement upstream needs downstream's own review. Its spec merged the kind-change draft and the Entity-edit draft, because both ask what happens to the readers of an Entity or a saved record that changed or went. A read-only review on 2026-10-24 gave the verdict "proceed" once J2 merged.

**Checkpoint K, completed 2026-10-24.**

What changes for users:

- `edit-entity --case description|unselected|revert` edits the Helios controller Entity that doc01 reads as a corpus input (`existing_A`), on a glossary root, chain roots included. It writes no ledger row and no recovery event. Live validation finds the edit at the next read: `description` withholds r01 and v01 (`input_changed`, `refresh_needed`) and, down the chain, c01 and c02 (`upstream_withheld`). `revert` releases them with no revision.
- `reconfirm` answers an Entity edit by citing the Entity as it reads now under a new key. One re-confirm answers a decision withheld by inputs of several kinds, such as the glossary span and the Entity together. `replace-decision --decision r01` leaves g01 unresolved on the Entity as it reads now.
- `replace-citation --source <label> --decision <key> (--cite <source>:<record> | --drop)` answers a decision withheld by a saved record it cites, at any chain level. D9's c02 had no reviewer path since J1. `--cite` keeps the decision's reviewed fields, so its own citers release with it. `--drop` removes the decision as an erasure would.
- `change-kind-to-mention` and `change-kind-to-reusable` run on a glossary root, where other sources read doc01. Their result lists `dependents_withheld`, the other sources' decisions the completed revision leaves withheld.
- New refusals: `record_key_reused` (a record key that comes back while another source that is not retired cites it), `mention_input` (a corpus input that names a mention UUID of any saved source) and `entity_field_protected` (`edit-entity` of `id`, `name` or `type`). The `input_removed` refusal of `reconfirm` now names `replace-citation` for a removed citation.

The data shape and rules:

- No saved schema changed. `RecordStore`, `TRANSITIONS`, the ledger model and the withholding table are unchanged.
- **One review flow** (`review.review`): the gate (`review_gate`, with `refuse_command`), what the reviewer reads now (`Now`, built by input kind through `AS_NOW`), then the intended revision (`intended_revision`). A review producer records `old_digests` and `new_digests` for every input kind, and `new_digests` names only inputs the written revision keeps. `REPLACEMENTS` is the captured replacement by record type.
- **One removal** (`records.apply_removal`) removes records as their type says and rewires the parts that hold their inputs through a ref map. The erasure's removal revision, `--drop`, the in-place replacement and the replacement of a decision whose input went all use it. Each then drops the recipes only the removed records named, through `erasure_rules.drop_unnamed_recipes`.
- **Record keys stay single-meaning.** `chains.check_record_key_reuse` runs in `Publisher.admit_inputs` beside `check_record_citations`, on a first attempt only. It shares `records.names_record` with J2's `RemovedRecord.reads`.
- **No reader of a mention UUID.** `admission.check_mention_inputs` runs in every admission of a publication. A source that depends on a mention cites its resolution as a saved record instead.

The session owner reported these defaults to the user, each reversible:

- Admission refuses a corpus input of a mention UUID (`mention_input`). The spec's drafts had extended `text_changes.reject_sole_owned_readers` to mentions at kind-change time. That rule runs on every text change, so it would have blocked changed-meaning edits, regroupings and plain edits whenever another source read the mention.
- `cognify` cannot overwrite an Entity the lab declares, because Cognee 1.6.2 derives an extracted Entity's ID from its name and the lab derives its own IDs another way. The overwrite concern applies only to a Cognee-extracted Entity that a decision cites, which no fixture has.
- From the fix rounds: a `replace-decision` of a variant whose input went drops the variant as an erasure drops it, its recipes included; an erasure strips only the citing resolutions' own groups; a glossary replacement row with no `text_change` resumes as a plain replacement.

Process, run by the assistant and its subagents on 2026-10-24 on branch `stage6-entity-edits`. A subagent wrote the implementation in four commits, rebased onto `main` at `9c6f16e` as `3237563`. Two rounds of `/pstack:thermos` reviews and fixes followed, from local, untracked briefs `.audit/checkpoint-k-fix1.todo.md` and `checkpoint-k-fix2.todo.md`: round 1 in five commits, to `94d54bb`, and round 2 in three, to `5e0c314`. The orchestrator then rewrapped the `entity_edit.py` docstring (`514c0bb`). Each bug fix came with a test that failed first.

1. Round 1. The bug review of `40d7d20` found one medium item: a decision withheld by a removed corpus input or glossary span had no working reviewer path, because the review read every input as it is now before it branched. Such an input is now stripped from the decision. Three low items followed: `--drop` stripped the dropped keys from every group, `edit-entity` crashed on a node that lacked the field, and the mention set left out the source's own `last_tombstone`. The quality review asked for the rebase, one removal helper instead of the review drop's copy of the erasure's removal, no decision fields named outside `records.py`, and the variant key in the key-reuse worlds.
2. Round 2. Both re-reviews of `94d54bb` found the branch merge-ready. The bug review raised two probed low items: a review producer named an input the revision drops, and a review drop left a recipe that only the dropped variant named. Both now follow the erasure's rule. The quality items shared the to-reusable variant describer and the root check of a kind change.
3. Both re-reviews of round 2 found the branch merge-ready, with no blockers.

Evidence, run by the assistant and its subagents on the user's Mac on 2026-10-24 with loopback embeddings:

- `verify.py journey all`: 1658 PASS and 0 FAIL in 101 runs on `40d7d20` (before fix round 1), on `94d54bb` and on `5e0c314`. `514c0bb` changes only a docstring. P5 calls the embedding API and was skipped.
- Journeys D12 to D16 in `.claude/skills/verify/features/dependencies.md`: the Entity edit and its revert, the corpus re-confirm, the in-place replacement, one re-confirm of the span and the Entity together, and `replace-citation` on D9's c02. Journeys K6 to K9 in `features/reinterpretation.md`: a kind change that removes a cited record, a sole-owned HC refused under a reader and retired with none, the refused mention reader, and a failed chain kind change with its recovery.
- Unit suite on `514c0bb`: 560 passed, 86 deselected.
- `support/occurrence_check.py`: PASS on 540,045 worlds. `--mutants`: PASS, including the two `mention_input` mutants.
- `support/chain_check.py`: PASS, 0 disagreements, with 814,500 key-reuse cases and 34,752 cascade worlds. `--mutants`: PASS, including the three key-reuse mutants.
- `support/ledger_check.py`: PASS verified within bound at depth 5, `PINNED` unchanged at 9205 nodes and 9050 sequences. `--mutants`: PASS.
- Integration: the native files for dependencies, chains, forget, erasure retry, kind change and the shared native file gave 57 passed.

No user-reviewed root for this checkpoint exists yet. The [entity edits guide](stage6_identity_entity_edits.md#evidence) has each round's evidence.

### Next task

No step-4 item is left that can start without the user. Each remaining direction needs the user first:

1. **Facts as saved records** are step 6, with the model that produces semantic output. They need a discussion with the user about what a fact as a saved record looks like.
2. **The non-identity example** is deferred. It needs architecture planning first: a new source kind with its own describer, admission and fixture.
3. **Step 5**, the standard-entry-point wiring and public retrieval, needs a retrieval contract.

The user picks the next direction. Small items that need no decision are listed in [Tracked follow-ups](#tracked-follow-ups); B8 is the next quality item.

### Tracked follow-ups

None blocks the next task.

- The replace `source_missing` guard in `RecordStore.begin` is not covered by the ledger model, which sends no replace for a missing row.
- `describe_readd` assigns naming keys to removed Entities greedily, so it can refuse a re-add for which a valid assignment exists (a refusal, never a merge; no fixture reaches it). A bipartite matching would fix it.
- `check_readd_entity_ids` accepts `replaces:<uuid>` for any removed UUID, not only the Entity's own. The results are still fresh and probed, so this is looser than the guide's wording, not unsafe.
- `remains()` reads `stored_files` without the guard `forget()` has, so a development root with a forget plan saved before that field crashes the snapshot. No kept root has one.
- The oracle's worlds do not cover more than one addition or reordering. A unit test pins reordering, and the captured addition fixture's general map pins two additions. Widen the bound if a later rule depends on either.

Added by Checkpoint H on 2026-10-23, from its final review and the dependencies guide's "Not in this checkpoint":

- Attestation is per producer, not per decision. A renamed or new decision may name a sibling's re-confirm producer and cite the key that producer attested, so one decision's re-confirm can cover another decision's interpretation. The record stays true about which content was seen. A per-decision attestation would close it.
- A producer's identity is its key, not its content. A revision may rewrite an old producer's configuration without changing a decision. The attestation rule still constrains it and nothing is released, but recorded provenance is not immutable.
- `describe_prefix_edit` (`text_fixture.py`) stamps every record with the fixed producer key `text_review`. A second prefix edit after a re-confirm on the same source would be refused by the attestation rule. No CLI path reaches it today. A per-revision key would remove the hazard.
- `refresh-dependents` re-raises a refresh failure that is not an `IntentError` as an `IntentError` whose code is the original class name. The exit code is still 1, but the exception class and traceback are lost.
- `classify` finds a moved span by hashing every window of the new text with the span's length: O(n·len) for a text of n code points. That is fine for a glossary. A long consumed document with many spans needs a substring search first, confirmed by digest.
- A chunk of another document has no refusal rule and always needs review; no fixture has one. Moves across documents and span-scoped variant ranges count as a change, not a remap.

Added by Checkpoint I on 2026-10-23, from its final review:

- A reconcile of an erasure retry reruns `plan_retirement` against the current graph and keeps only `erased_from` from the saved plan. After a partial retirement `verify_survivor` therefore sees fewer previous contributions than a replace would (low). Merging the saved `previous_edges` and `retired_entities`, as replace does, would fix it.
- The registered snapshot of an erasure retry is written before `begin`. It is harmless and converges on rerun.
- A dependent whose text change finishes through the erasure retry leaves its own dependents' moved ranges for `refresh-dependents`.
- `publish.py` has an unused `ChunkInput` import that predates this branch. Journey F9 edits root files with `python3` lines inside the journey.
- The ledger check got slower, because `begin` parses every row under the reservation for an erasure retry: depth 5 takes about 15 s and depth 6 about 95 s.
- Closed by branch `stage6-readd-followups`, merged into `main` at `497ba58` on 2026-10-23: F1, a re-add reports `differs_from_forgotten` by text and by decisions from the tombstone's digests, and F2, each tombstone carries the mention and Entity UUIDs of the source's earlier forgotten lives. The same round fixed a second re-add from the original files, which was refused as `entity_uuid_not_derived` because the file still named an Entity by the UUID the first forget removed. Its fix round 1 made the decisions digest count each group's occurrences, added ledger property P8 for `last_tombstone`, refused roots from before the follow-ups by name (`ledger_format`, `forgotten_format`), and let a third life reuse an earlier life's Entity still in the graph. See the [forget guide](stage6_identity_forget.md#re-add).

Added by the re-add follow-ups on 2026-10-23:

- No record keeps every UUID a source used at every revision. A tombstone holds the last revision's UUIDs and those of each earlier forgotten life, not the UUIDs an edit retired in the middle of a life; the derivation rules cover those. A per-source table of every UUID at every revision would close it.
- `forget.py` builds the tombstone carry outside the six checked `RecordStore` methods, and the ledger model's descriptions share their UUIDs across revisions, so the ledger check cannot see a dropped carry. P8 checks that `last_tombstone` reaches the next forget; the forget unit tests and journey F15 check the carry.
- The decisions digest names a reusable Entity by the keys of the decisions that name it, so a re-add that renames a decision key reports other decisions even when the outcomes match.
- `describe_readd` renames a removed Entity's UUID in recipes, targets and variant endpoints but not in an unresolved or ambiguous resolution's `candidate_entity_ids`. No fixture has a candidate list; such a re-add would keep a removed UUID as a candidate and report other decisions.

Added by Checkpoint J1 on 2026-10-23, from its reviews:

- A replacement that adds a self-citation or a cross-dataset citation under an old producer is refused as `reconfirm_unattested`, because `admit` runs before `check_citation_scope` on a replacement. It is still refused; the code is less specific than `self_citation`.
- `withheld_decisions`, `held_by` and `erasure.removed_records` still assume decision records. J2 made the erasure side generic through the registry's hooks; `withheld_decisions` and `held_by` wait for facts as saved records (step 6).
- The record checks run only before the writer reservation. Live withholding catches a record that drifts between the check and `begin` (review finding L1, dismissed).
- doc03 has no captured facts, so its withholding shows in `status` and in the withheld lists, not in the returned facts.
- The CLI prints a refusal's message, not its code, so journeys check messages and unit tests check codes.

Added by Checkpoint J2 on 2026-10-24, from its reviews:

- After a second forget of a source, the tombstone keeps the earlier lives' UUIDs but not the Entities each earlier forget removed. A rejected completed removal from the first life is therefore refused again on its retry. Closing it needs a tombstone field.
- The cascade check's retire oracle recomputes `cascade` the way the code does. Add an end-to-end check that, after an allowed retirement and a finished cascade, no live source cites a removed record.
- L1: a retry is refused when the bound set for the same document grew after admission and its old revision reads the new record. It predates the fix rounds (first commit `3ebd8bb`).
- The retire refusal is stricter than needed in one shape: a blocked dependent that cites both an intermediate and the forgotten source. The user can withdraw the dependent.
- A re-add's never-served revision lists a served revision from the earlier life. It is harmless and documented in `RemovedRecord.of`.

Added by Checkpoint K on 2026-10-24, from its reviews:

- B8: `glossary_fixture.run` dispatches its commands through a growing `elif` chain. Replace it with a command table before a fourth command arm lands. A table needs one handler signature across ten commands in four modules.
- `revisions.reconfirmed` writes resolution and group fields outside `records.py`. It predates K.
- `erasure_rules.corpus_readers` repeats the reader filter of the Erasures builder, and three review docstrings restate `drop_unnamed_recipes` instead of pointing to it.
- A review drop, like an erasure, removes a recipe that only the dropped variant named. A source that cites that variant as a saved record is withheld by its changed citation, not by the missing recipe.
- No journey drives a decision withheld by a removed corpus node or glossary text, because the lab's own commands cannot remove one under a reader. Unit tests drive that reviewer path.

## Code map

Paths below are relative to `src/cognee_lab/identity/`.

| Module | Responsibility / boundary |
|---|---|
| `models.py`, `schema.py` | Runtime saved forms; generated draft JSON Schema |
| `validation.py` | SHA-256/JCS fingerprints, exact slices/native chunk tiling, input and cross-source UUID-use checks |
| `storage.py` | Namespaced relational publication/event tables, the begin transition table (`TRANSITIONS`, `admissible`) and the `PublicationRow` view with `is_served` and, since J2, `holds_served`; portable expected-revision/attempt and project-writer guards |
| `stages.py` | `run_attempt`, the one attempt frame for replace, withdraw and forget |
| `registered.py` | Real Data JSON/raw-text ingestion/readback and registered snapshot checks |
| `publish.py` | Missing-node creation, safe existing-node retention, original markers, aggregated generated-source identity contributions and verification; `Publisher.admit_inputs` runs the citation, key-reuse and mention-input refusals before `begin`, and since K `saved_lives` gives every saved description and tombstone, `last_tombstone` included |
| `replace.py`, `withdraw.py`, `forget.py` | Guarded replacement, withdrawal and forget, `admit_replacement` (the one admission call site), the replace stages `withhold_dependents` (text changes) and `withholding_cleanup`, durable old/new intent, selective retirement and explicit forward recovery |
| `erasure.py` | What a forget does to its dependents: `cascade` (the steps by level, from the rows) with `Step`, `impact` and its token, `removal_revision` and `removal_producer` (with `removed_records` and `cited_records`), `unfinished`, `report`, `removal_writer`, `ready` (the write order) and `finish_dependents`; the fence `refuse_retiring_inputs` over every level, and `reach` and `refuse_unfinished_cascade` (`cascade_unfinished`). The J1 interim refusal `impact_checked` is gone |
| `erasure_rules.py` | Admission rules for an erasure removal (`check_erasure_removals`, `check_erasure_records`, `check_retry_chain`, `check_erasure_retry`, `check_removal_producers_kept`), the binding of removals to a forget (`written_claims`, `bound_removals`, `levels`, `producer_key`) and a re-add against a tombstone (`admit_readd`); since K, `drop_unnamed_recipes` (the recipes a removal drops, shared by the erasure and the reviews) and `corpus_readers` (the Entities other saved sources read as corpus inputs); imports nothing from `admission.py` |
| `dependency.py` | `citations` and `Target` (a document, Entities and, since J1, every record of a source), the one dependency predicate shared by forget's erasure, a text edit's withholding and the retiring-source fence |
| `records.py` | The saved-record registry (`REGISTRY`, one `RecordKind` per citable record type with its hooks `held`, `inputs`, `names`, `removed`, `outcome`, `stripped` and `unlinked`), `record_inputs` and `naming` over every kind, `reviewed_decisions`, the fingerprint `record_digest`, `cited_row` and, since J2, `RemovedRecord`. Since K: `apply_removal`, the one removal of records by a ref map (`RefMap`, an input key to its new key or None), which the erasure's removal revision and every review removal use; `drops`, whether a removal drops the record; `current_record`, a citation of a record as its source holds it now; and `names_record`, the one test of whether a citation names a record key, shared by `RemovedRecord.reads` and the key-reuse rule |
| `digests.py` | `object_digest`, the SHA-256 of canonical JSON, shared by `records.py` and `validation.py` with no package import (J2 fix round 2 broke their import cycle) |
| `chains.py` | The citation rules (`check_citation_scope`, `check_record_citations`, `check_citation_cycles` and, since K, `check_record_key_reuse` over `new_record_keys`, which refuses `record_key_reused`), the source graph, `upstream_closure` and `live_pass`, the one live pass that retrieval, `status` and the chain check run; writes nothing |
| `retirement.py`, `forget_fixture.py` | Shared retirement primitives (ownership snapshots, contributions, `dependents`, removed Entities, survivor checks against `current_claims` and `Claims`, what each other source still writes) and the forget, re-add and dependent-fixture drivers; since K, `forget_fixture.write_revision` writes the caller's file for a reviewed or cited revision, next to `CALLER_FILES` |
| `admission.py` | What a reviewed replacement may claim: `parse_occurrence_map`, `identity_map`, `admit` and its rules in the order it applies them, returning a `GroupFate`, the graph probe `check_absent_from_graph` and, since K, `check_mention_inputs` over `mention_ids` (`mention_input`), which every admission of a publication runs |
| `text_changes.py` | `TextChange` with its typed `occurrence_map`, `from_plan` (which refuses a plan without `occurrence_map`) and `prefix_shift`; `preflight` calls `admit` with `first_attempt=not retry`; the cascade guard and `reject_sole_owned_readers`, native whole-document Forget/ingest/chunk rebuild and retired chunk checks |
| `retrieve.py` | Bounded fixture retrieval, saved-source eligibility, `live_drift` for `chains.live_pass` (shared with `status` through `withheld_now`), withheld decisions skipped, scoped identity links/local mention facts and native current evidence; not a public corpus-wide retriever |
| `withholding.py` | The withholding table (`WithholdingStore`), `classify` for one input against an edited text, the edit stage `withhold_dependents` and `withheld_decisions`, which merges the rows with the rule derived from the ledger; since J1 the saved-record reader `record_reader`, the one unfinished rule `unfinished` and `held_by` |
| `native.py` | Normalizers over graph/provenance/neighborhood interfaces |
| `fixture.py`, `multisource.py`, `captured_chunks.py` | Captured facts, source contexts, exact producing/evidence chunk binding, single/two-source setup and diagnostics. `CAPTURED_GROUPS` in `captured_chunks.py` names each captured group's creating revision, creating producer and fact. A group has retired when its creating producer is in the source's lineage and the source no longer declares it |
| `captured_text.py` | The original doc01 text `BEFORE`, shared by the captured edits |
| `kind_change.py` | The chunked root's kind changes; since K, `describe_to_mention` takes the root's groups and text and a `stamp` flag, so the glossary root shares it, and `declare_hc_variant` builds both to-reusable variants |
| `revisions.py`, `text_fixture.py` | Captured identity correction/prefix edit, shared maintenance callbacks, `refresh_dependents` (the refresh after an edit) and transition diagnostics |
| `glossary_fixture.py` | The glossary root creator (with `--chain`, doc03 too), the four glossary edits, the glossary result document and `REVIEW_COMMANDS`, the three review commands that `__main__.py` dispatches |
| `review.py` | Since K, one flow (`review`) for the reviewer commands `reconfirm`, `replace-decision` and `replace-citation`: the gate (`review_gate`, with `refuse_command`), what the reviewer reads now (`Now`, through `AS_NOW` by input kind), the producer (`review_producer`, with `old_digests` and `new_digests`) and the revision (`intended_revision`); `REPLACEMENTS` is the captured replacement by record type |
| `entity_edit.py` | `edit-entity`, a captured stand-in for an outside writer of the Helios controller Entity, through Cognee's `graph.update_node`; writes no ledger row |
| `chain_kind_change.py` | `change-kind-to-mention` and `change-kind-to-reusable` on a glossary root, with `dependents_withheld` from the live pass |
| `chain_fixture.py` | The captured doc03 that cites doc01's r01 and v01, and `cite` for the `cite-record` refusal cases |
| `occurrence_fixture.py`, `occurrence_addition.py`, `resolved_retirement.py` | Captured addition/removal/mixed/retirement examples and physical absence/shared-survival checks. `COMMANDS` in `occurrence_fixture.py` maps each occurrence command to its text, describer, result file and occurrence map |
| `group_regrouping.py` | Captured split and combination texts, regrouping maps and the `describe_split` and `describe_combination` intended descriptions |
| `captured_revision.py` | Shared building blocks for captured describers: `require_root` (since K with `text=` for another root's text), `begin_revision`, `retire_group`, `declare_group`, `occurrence` and `stamp_producer` |
| `__main__.py` | Fixture CLI arguments, `--embedding` reopen checks and command dispatch |
| `environment.py`, `fixture.env`, `fixture_embeddings.py` | Root marker, per-root embedding profile and store isolation. `environment.py` imports no Cognee. Cognee loads the comment-only `fixture.env` instead of `.env`. `fixture_embeddings.py` is the deterministic loopback embedding service |

The proof checks live in `support/`. `support/chain_check.py` checks the cycle rule and withholding down the chain against an oracle over every citation graph in `support/chain_worlds.py`. Since J2 it also runs the cascade half, `support/cascade_check.py`, over the forget worlds in `support/cascade_worlds.py`. Since K it checks `record_key_reused` on key-reuse cases in which a source has dropped its resolution key (`rekeyed`) or its variant key (`rekeyed_v`). `support/erasure_worlds.py` holds the occurrence check's erasure decision rows, and `support/ledger_properties.py` holds the eight properties the ledger check runs after each step. Tests live in `tests/test_identity*.py`; original forms/text in `tests/fixtures/identity/`; exported schema in `schemas/cognee_identity_source_schema_draft.json`. Module/fixture IDs and phrases in the captured adapters are not a completed generic extraction layer.

## Resume and verification commands

From the repository root, inspect the checkout first. Use the lockfile and confirm the inspected Cognee version before native tests:

```bash
git status --short
git log -1 --oneline
uv sync --group dev
uv run python -c "import cognee; print(cognee.__version__)"
uv run pytest -q -m 'not integration'
```

On branch `stage6-entity-edits` at `514c0bb` (2026-10-24) the unit suite gives 560 passed and 86 deselected. On branch `stage6-cascade` at `74ec093` (2026-10-24) it gave 533 passed and 86 deselected. On branch `stage6-chains` at `2002a77` (2026-10-23) it gave 487 passed and 85 deselected. On branch `stage6-erasure` at `d6133c7` (2026-10-23) it gave 448 passed and 81 deselected. On branch `stage6-dependencies` at `12c8d30` (2026-10-23) the unit suite gives 405 passed and 67 deselected. On `main` at `5603310` (2026-10-22) it gave 269 passed and 36 deselected. On branch `stage6-group-combine` (2026-10-21) it gave 207 passed and 34 deselected. On `c3becf2` it gave 143 passed and 29 deselected. The inspected native version must be **1.6.2**. If the version differs, inspect compatibility again. Do not identify another version as the tested profile. Run focused native tests for the changed path first. The full native suite is `uv run pytest -q -m integration`. It creates fresh stores and can take minutes.

The latest happy path, with a **new** root, is:

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/stage6_resume_check --embedding loopback
uv run python -m cognee_lab.identity revise-occurrences --root outputs/stage6_resume_check --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_resume_check
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_resume_check --source doc01
```

This sequence uses loopback embeddings. Without `--embedding loopback`, `chunked-fixture` uses the default `--embedding env` profile. That profile needs `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` in the repository `.env`, and it calls that embedding endpoint. Later commands read the profile from the root marker, so they do not need the flag. pytest always uses loopback and does not need `.env`.

Expected: two retrieved facts, doc01 current at 2/2/2, doc02 unchanged at 1/1/1, continuing g01 with `it` at [46,48) and `the controller` at [86,100), g02 retired with no Entity, index entry or marker, and no recovery incident. The [mixed occurrences guide](stage6_identity_mixed_occurrences.md) has the expected values and the injected-failure recovery. The [dependencies guide](stage6_identity_dependencies.md#commands) has the glossary sequence: an edit that needs review, `status` and two re-confirms. The [chains guide](stage6_identity_chains.md#commands) runs the same sequence on a `glossary-fixture --chain` root, where doc03's decisions wait for doc01's. The [group split guide](stage6_identity_group_split.md) has the split and combination sequence. `status` and `retrieve` inspect existing marked roots; fixture creation refuses existing directories. A root made before the `.env` fix opens only for `status` and `retrieve`.

## Verification and landing

The user agreed this routine on 2026-10-21:

1. **Unit tests on every commit.** Run `uv run pytest -q -m 'not integration'`. The suite uses loopback embeddings and includes the identity-ledger check at its default depth. It also runs the occurrence check on small worlds, with every mutant. GitHub Actions runs the same command on every push, then `support/occurrence_check.py` at its default bound (`.github/workflows/unit-tests.yml`). CI runs after a push, not before a merge, so it does not replace the local checks below.
2. **Proof checks for the riskiest code.** When `RecordStore` or its callers change, run `uv run python support/ledger_check.py`. When `src/cognee_lab/identity/admission.py` changes, run `uv run python support/occurrence_check.py` and `uv run python support/occurrence_check.py --mutants`. Since Checkpoint J1 (2026-10-23, a reversible default reported to the user), a change to `admission.py`, `records.py`, `chains.py`, `withholding.py` or `erasure.py` also runs `uv run python support/chain_check.py` and `uv run python support/chain_check.py --mutants`. CI runs the chain check after the occurrence check. It took about 200 s at J1 and about 490 s with the J2 cascade half. On 2026-10-24 the J2 push hit the CI job's 30-minute limit during the chain check (the unit suite and the occurrence check had passed), so the chain check now runs as its own CI job, `chains`, beside the unit job, with a 45-minute limit.
3. **The changed feature's verify journeys on every feature change.** Run `.claude/skills/verify/scripts/verify.py journey <ID>` for each journey in the changed feature's file under `.claude/skills/verify/features/`. For example, a regrouping change runs G1 to G4.
4. **`verify.py journey all` once per checkpoint, before the merge to `main`.**

The integration suite, `uv run pytest -q -m integration`, takes about 10 minutes and runs only on a local machine. Run the focused native tests for the changed path.

**Verify journeys.** The journeys drive the CLI through real Cognee stores in fresh roots under `outputs/verify/`. The map in `.claude/skills/verify/features/` has 75 journey blocks. `journey all` runs the 74 loopback blocks as 101 runs. Journey P5 calls the NVIDIA embedding API in `.env`, so it runs only with `--include-env`. Journeys use `--embedding loopback` unless a block asks for `env`. `.claude/skills/verify/SKILL.md` gives the helper commands and proof rules. [Verification skill](#verification-skill) lists each `journey all` run.

An earlier full run on 2026-10-21 took about 2 hours. The step timings suggest that macOS idle throttling caused most of it. Every step took a flat 40 s or so until `caffeinate` started, and about 4 s after. This is an inference from the timings, not a proven cause. A warm step costs about 3.6 to 6.7 s, and about 2.4 s of that is imports. An unthrottled full run is estimated at about 11 minutes.

`verify.py journey` now runs 4 journey runs at once by default (`--jobs N`; 1 with `--include-env`) and starts `caffeinate -i` on macOS. On 2026-10-21 the assistant measured `journey all` on the user's 10-core Mac, before the regrouping journeys, with 30 runs and 586 PASS rows each time: 839 s with 1 job, 250 s with 4 and 180 s with 8, with no failure that appeared only in parallel. After the regrouping journeys landed, the same 34-run set gave 695 PASS rows and 0 FAIL rows in 281 s with 4 jobs, against 917 s serially. A worker error becomes a FAIL row and Ctrl-C cancels queued runs. If a `lab_store` check fails under parallel runs, rerun with `--jobs 1` to find the journey.

**Identity-ledger check.** It runs every sequence of real `RecordStore` calls up to a depth bound, with two sources and two writers. It checks properties P1 to P6 after each step. The default depth is 5. Since the regrouping plan joined the model on 2026-10-21, depth 5 gives 3828 nodes and 3717 sequences in about 6.7 s. Before that it gave 3062 nodes. `PINNED` in `tests/test_identity_ledger_check.py` holds the current counts: 9205 nodes and 9050 sequences since Checkpoint J2 fix round 3 (8504 and 8349 from Checkpoint I), in about 15 s. Depths 6 to 8 are manual runs. `--skip-probability P --seed S` samples a deeper search, and a sampled run never reports `verified within bound`. At depth 5 the check catches all 30 scratch breaks in `support/ledger_mutants.py`: 29 as a property failure and one as `INCONCLUSIVE`. The unit suite runs each break. One more break, in `DEEP_MUTANTS`, needs depth 7. The check found no bug in the current code. The user chose a Python checker over TLA+. `.claude/skills/identity-ledger/SKILL.md` says when to run it, and `reference.md` holds the measurements.

To land a branch, follow [the landing playbook](../.agents/playbooks/landing-on-main.md). In short:

1. Work on a branch off `main`.
2. Review `main..<branch>` with `/pstack:thermos`. Fix each finding, or dismiss it with a concrete reason.
3. Run `uv run pytest -q -m 'not integration'` on the branch. At a checkpoint, also run `verify.py journey all`.
4. Merge with `git merge --ff-only <branch>` into `main`.
5. Push `main` only when the user asks.

The user prefers the NVIDIA embeddings in the repository `.env` for real fixture runs, and loopback for pytest and verify journeys. The user works in auto mode. A user auto-mode rule allows deletion under `outputs/`. The user approves each other deletion.

## Constraints to preserve

- Use **singleton**, **identity group (variants)** and document-local mention groups; no privileged canonical member, authoritative `entity_role` field or permanent identity-group registry. Do not silently promote a mention into a reusable Entity.
- Saved descriptions and the publication ledger govern intent/currentness. Graph properties or an old recipe alone do not authorize resurrection. Existing compatible Entities are referenced/retained without ordinary-field overwrite; populated nested existing DataPoints can accidentally enter the write set.
- Original occurrence chunks own/retain markers; original producing chunks own semantic facts/evidence; generated identity Data owns identity contributions and required-endpoint retention. Attaching a fact owner alone does not protect an unretained endpoint from cascading deletion. Preserve the reused-endpoint retention fix.
- Occurrence coordinates are exact Unicode code points in the extracted document string, `[start,end)`. Validate source fingerprint, slices and complete native chunk mapping. Never choose the first repeated substring as an implicit locator. Content-derived chunk IDs can recur while positions/indexes change.
- Use configured Cognee interfaces and backend-neutral relational operations. Ladybug/LanceDB/SQLite are the tested fixture profile; no vendor-specific implementation is authorized. The old NVIDIA tokenizer patch is separate from the fixture code. Every fixture root keeps its stores inside the root. The default `env` profile calls the `.env` embedding endpoint. The `loopback` profile calls no external API.
- Pending/failed sources are withheld; independent valid sources survive. Recovery is explicitly selected forward completion of saved intent, not rollback or automatic retry. Native readers ignoring the ledger can see intermediate graph state. Hard crashes can leave a writer reservation; do not casually clear it or claim general restart recovery.
- Prefer programmatic validation/publication/traversal. Capture where rules/model judgment is required. Captured fixture decisions establish lifecycle mechanics with either embedding profile, not extraction/search quality or scientific support.
- A/B staging, incremental chunk reuse, comprehensive semantic replay/archives, automatic orchestration, all-alias Triplet text and universal scope/ontology frameworks are deferred. Size/density/token-overhead tooling is future evaluation work. Do not enable diagnostic Triplet/cache/optional native stages without admitting their actual lifecycle and consumed-store behavior.

After each next checkpoint update this handoff's baseline, implemented/remaining status and verification table, together with the roadmap and relevant guide/playbook findings. Preserve dates and distinguish generated-here tests, user-reported native reproduction and untested design.
