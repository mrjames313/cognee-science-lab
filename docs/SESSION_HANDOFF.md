# Session handoff — resume here

**Updated:** 2026-10-21 (America/Detroit). **Current work:** Stage 6, accepted implementation step 4 / M3, partially complete. The captured group split and combination checkpoint is implemented and verified. **Next task:** pick the next step-4 item. The proposed default is mixed occurrence addition and removal, as a concrete case for the user to review before any code. This document records the current continuation state; dated experiment writeups describe their own checkpoints.

## Objective and reading order

Develop a method to integrate structured knowledge into Cognee. The method has four operations: **Describe, Publish, Maintain and Retrieve**. Identity is the first worked example. Use the demonstrated mechanisms and tests when examining other domains, including scientific measurements. Keep each domain's meaning and rules explicit. This implementation does not provide scientific justification or scientific reasoning.

Read this document first, then:

1. [ROADMAP.md](../ROADMAP.md): project stages and current scope.
2. [Stage-6 architecture/contract](../results/cognee_identity_stage6_handoff.md): physical representation, ownership, continuity, recovery and original six-step build order. Its dated implementation subsections are checkpoint history.
3. [R1–R6 requirements](../results/cognee_stage5_4_5_requirements_review.md): outcome constraints, not a claim of complete coverage.
4. [Latest fixture guide](stage6_identity_group_split.md), followed by the earlier guides linked below for individual commands.
5. [Integration playbook](../results/cognee_knowledge_integration_playbook.md): findings tagged with Describe/Publish/Maintain/Retrieve and transfer questions for other integrations.

The [representation decision record](../results/cognee_stage5_4_5_identity_representation_proposal.md) and [pinned native extension reference](../results/cognee_extension_architecture_reference_v1.6.2.md) explain rationale and native behavior. Do not treat their early dated “next” or “not implemented at that checkpoint” statements as current implementation status. The roadmap and this handoff identify current work; later explicit approved scope changes supersede earlier proposals.

## Code baseline and delivery status

Runtime code is in `src/cognee_lab/identity/`. The implementation includes a **captured group split and combination** through the `occurrence_regrouping` admission mode, following captured occurrence additions and new-group publication. It does not include general regrouping, automatic Describe, dependent-source reconsideration or a standard-entry-point extension. The regrouping update extends transition admission, captured semantic output, diagnostics, CLI commands, the ledger model, verify journeys and tests. The saved-source schema and dependencies are unchanged.

The user's Mac addition, reopened retrieval, healthy reconcile and `replace_published` failure/recovery outputs have been reviewed. The user approved the split and combination case on 2026-10-21. The assistant's subagents verified the implementation on the user's Mac with loopback embeddings. This handoff records no user-reviewed fixture roots for it. [Next task](#next-task) gives the next task.

Generation began from lab checkout commit `5a179881b4314ba458ed2836fc3d7e78edae8169`. Later code was first delivered as patches. That hash identifies only the generation base. The code and documents are now committed.

Before branch `docs/handoff-2026-10-21`, `main` was at `c3becf2` and in sync with `origin/main`. GitHub Actions `unit-tests` passed on `c3becf2` with 143 passed and 29 deselected. The work after `ccc85d6` landed on `main` by local `git merge --ff-only` merges after `/pstack:thermos` reviews. No pull requests were opened. That work is:

- The `.env` fix and per-root embedding profiles (2026-10-20). See [the resolved `.env` issue](#resolved-the-repository-env-overrode-the-fixture-profile).
- The build fix (2026-10-20). `pyproject.toml` misspelled the key as `build_backend`, so the build used setuptools. It now sets `build-backend = "uv_build"` and requires `uv_build>=0.12,<0.13`. Git no longer tracks the `*.egg-info/` directory and ignores it. The `pytest-timeout` dependency is removed.
- The project verify skill and its journeys (2026-10-20 to 2026-10-21).
- The identity-ledger check (2026-10-21).
- The unit-test workflow and the landing playbook.

Branch `stage6-group-combine` (2026-10-21) adds the captured group split and combination, the fresh-ID rule and the revised verification routine. It lands through the same playbook.

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
| Group split and combination | Explicit `occurrence_regrouping` map; g01 splits into fresh g04 and g05, then g04 and g05 combine into fresh g06; retired groups, links, facts, evidence and triplets physically removed; facts generated again from the fresh groups, never transferred; fresh IDs from source, new revision and key; reopen/reconcile and explicit recovery | [Group split](stage6_identity_group_split.md) |

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

Proof history, 2026-10-20 to 2026-10-21:

- 2026-10-20. The 20 journey blocks ran as 31 runs on the Mac against Cognee 1.6.2, with 500 assertions and 0 failures. The tokenizer fix was applied.
- 2026-10-21. A fix round added the `journey` runner, `probe`, the lab-store guard and `reopen_problem`. The rerun passed all 31 runs with 567 assertions and 0 failures. `journey all` ran the 30 loopback runs, and `journey P5 --include-env` ran the env run.
- 2026-10-21, before the regrouping journeys. The assistant ran `journey all` on the Mac. The 19 loopback journey blocks ran as 30 runs, with 586 PASS rows and 0 FAIL rows. P5 is the 20th block. It needs `--include-env` and did not run in this pass.
- 2026-10-21, group split and combination. The assistant's subagents ran journeys G1 (32 PASS rows), G2 (20), G3 (36) and G4 (21) on the Mac with loopback embeddings, with 0 FAIL rows. After the fresh-ID change they reran O5 (27), O6 `replace_published` (17) and O6 `text_chunks` (17), with 0 FAIL rows. The map now has 24 journey blocks, and `journey all` runs the 23 loopback blocks as 34 runs.
- 2026-10-21, checkpoint run for group split and combination. The assistant ran `journey all` on the Mac on the final branch head, serially. The 23 loopback blocks ran as 34 runs, with 695 PASS rows and 0 FAIL rows, in 15 min 17 s. P5 needs `--include-env` and did not run.
- Not exercised against an env root. The warning path for a missing tokenizer fix, and the doctor failure path for an operator file that lacks a key.
- Exercised. The doctor failure path for a pre-profile marker, a malformed marker, and an env root whose operator file names another model.

## Original six-step implementation sequence

This is **step 4 within Stage 6**, not project Stage 4.

| Step | Current status |
|---|---|
| 1 / M0 | Runtime forms/schema, exact chunk mapping, portable bookkeeping and capability checks implemented for the initial profile |
| 2 / M1 | Captured Task → native publication → useful fact/evidence retrieval → reconcile demonstrated |
| 3 / M2 | Multi-source ownership/withdrawal demonstrated; general exact-ID semantic conversion remains broader than the captured writer |
| 4 / M3 | Partly complete: corrections, prefix/rechunk edits, partial occurrence removal, empty unresolved and resolved fact-bearing group retirement, captured additions/new group, captured group split and combination, and explicit caught-failure recovery |
| 5 / M4 | Standard Cognify/Remember/full Update B Task-transform wiring, source-removal entry-point hooks, public Retriever/SearchType, broader traversal/delivery/diagnostics not implemented |
| 6 / M5 | Seeded rules/model Describe and separate quality/consistency evaluation not implemented |

### Remaining step-4 work

1. **Occurrence/group changes:** mixed addition/removal, representation-kind changes using separate suitable Entities, and broader addition and regrouping cases. Captured continuing-group additions, new-group publication, unresolved/resolved removal and one captured split and combination are implemented. Their fixtures do not establish general regrouping or automatic matching.
2. **Changed interpretation and semantic refresh:** edits changing a referent/definition/scope, with coordinated saved decisions and regenerated facts/evidence. Existing unchanged-text retargeting and captured same-binding edits do not establish this generally.
3. **Dependencies:** identify and reconsider affected sources that consumed another document, corpus fields or saved records; support admitted span/record remapping. Current code rejects known dependent-document text edits rather than silently propagating them. New-corpus opportunity selection is not solved by positive dependencies alone.
4. **Full source lifecycle:** coordinate original removal with generated-source retirement, generated-source rebuild and authorized endpoint reconstruction; preserve remaining owners and distinguish missing reasoning inputs from missing reconstructible output. Identity withdrawal alone keeps Data/description and original facts; it is not full source Forget.
5. **Verification/recovery coverage:** extend current revision/attempt/currentness, ownership/index/evidence and retirement checks across those operations, including incomplete/missing-plan diagnostics. Do not make a general crash-recovery framework a new prerequisite.

### Group split and combination, completed 2026-10-21

The user approved this case on 2026-10-21, before implementation. The [group split guide](stage6_identity_group_split.md) gives the exact texts, offsets, maps and UUIDs.

- **Split, revision 1 to 2.** A paragraph break splits g01 into fresh g04 (`the controller`) and fresh g05 (`it`). Accepted resolutions r04 and r05 link both to the same Helios controller. g02 continues. The `it limits oscillations` fact is generated again from g05, never transferred. g01, r01 and g01's fact edge, evidence and triplets are physically retired.
- **Combination, revision 2 to 3.** Rejoining the paragraphs merges g04 and g05 into fresh g06, with resolution r06. g04, g05, r04, r05 and g05's fact retire. The fact is generated again from g06. g01 is never resurrected.

The `occurrence_regrouping` mode maps each old occurrence to one `[new group, new index]` pair. `occurrence_retention` handles removals, and `occurrence_continuity` handles additions. One change selects only one mode, so mixed removal and addition stays unsupported.

The review added the fresh-ID rule. A fresh group's UUID is `uuid5(identity_data_id, f"mention:r{revision}:{key}")` with the new revision, and both addition and regrouping admission enforce it. Both also require the source revision to be the old revision plus one. The record store keeps only the current revision, so a key-only derivation re-derived a retired UUID when a key returned. The guide explains why the rule is sound and lists the old and new UUIDs. Roots reviewed before this change keep their key-only IDs as history.

### Next task

Pick the next step-4 item. The assistant proposes **mixed occurrence addition and removal** as the default next case. This is a proposal, and the user decides. Do the task in this order:

1. Draft the concrete case and give it to the user for approval before you write code. Name each old occurrence that continues, each one that is removed, each addition and each fresh group. Name the captured decisions, the retired groups, the replacement IDs and the facts and evidence to regenerate.
2. After the user approves the case, implement the smallest captured example. Reuse the whole-document rebuild and the common publisher. Preserve independent doc02 support. Do not infer fact transfer from group continuity.
3. Add verify journeys in `.claude/skills/verify/features/`, and update "Not yet supported" in `features/README.md`.
4. Extend the identity-ledger checker if the plan sent to `RecordStore` changes. Follow "Add an operation" in `.claude/skills/identity-ledger/SKILL.md`.
5. Add a fixture guide under `docs/`. Update this handoff, [ROADMAP.md](../ROADMAP.md) and the integration playbook.
6. Land the branch through [the landing playbook](../.agents/playbooks/landing-on-main.md).

### Tracked follow-ups

These came out of the 2026-10-21 review. Neither blocks the next case.

- Replace the three nullable map fields on `TextChange` with a tagged union. Parse saved plans with a versioned reader and use typed occurrence references. Merge the removal, addition and regrouping maps into one partial occurrence map. Mixed addition and removal may be the natural place to do this.
- Move the admitters out of `text_changes.py` into their own module.

## Code map

Paths below are relative to `src/cognee_lab/identity/`.

| Module | Responsibility / boundary |
|---|---|
| `models.py`, `schema.py` | Runtime saved forms; generated draft JSON Schema |
| `validation.py` | SHA-256/JCS fingerprints, exact slices/native chunk tiling, input and cross-source UUID-use checks |
| `storage.py` | Namespaced relational publication/event tables; portable expected-revision/attempt and project-writer guards |
| `registered.py` | Real Data JSON/raw-text ingestion/readback and registered snapshot checks |
| `publish.py` | Missing-node creation, safe existing-node retention, original markers, aggregated generated-source identity contributions and verification |
| `replace.py`, `withdraw.py` | Guarded replacement/withdrawal, durable old/new intent, selective retirement and explicit forward recovery |
| `text_changes.py` | `TextChange` and its `mode`, prefix/removal/addition/regrouping admission (`admit_occurrence_regrouping`, shared `check_fresh_group`, `check_next_revision` and `check_carryover`), dependency/cascade guards, native whole-document Forget/ingest/chunk rebuild and retired chunk checks |
| `retrieve.py` | Bounded fixture retrieval, saved-source eligibility, scoped identity links/local mention facts and native current evidence; not a public corpus-wide retriever |
| `native.py` | Normalizers over graph/provenance/neighborhood interfaces |
| `fixture.py`, `multisource.py`, `captured_chunks.py` | Captured facts, source contexts, exact producing/evidence chunk binding, single/two-source setup and diagnostics. `CAPTURED_GROUPS` in `captured_chunks.py` names each captured group's creating revision, retiring revision and fact |
| `captured_text.py` | The original doc01 text `BEFORE`, shared by the captured edits |
| `revisions.py`, `text_fixture.py` | Captured identity correction/prefix edit, shared maintenance callbacks and transition diagnostics |
| `occurrence_fixture.py`, `occurrence_addition.py`, `resolved_retirement.py` | Captured addition/removal/retirement examples and physical absence/shared-survival checks. `COMMANDS` in `occurrence_fixture.py` maps each occurrence command to its text, describer, result file and transition map |
| `group_regrouping.py` | Captured split and combination texts, regrouping maps and the `describe_split` and `describe_combination` intended descriptions |
| `__main__.py` | Fixture CLI arguments, `--embedding` reopen checks and command dispatch |
| `environment.py`, `fixture.env`, `fixture_embeddings.py` | Root marker, per-root embedding profile and store isolation. `environment.py` imports no Cognee. Cognee loads the comment-only `fixture.env` instead of `.env`. `fixture_embeddings.py` is the deterministic loopback embedding service |

Tests live in `tests/test_identity*.py`; original forms/text in `tests/fixtures/identity/`; exported schema in `schemas/cognee_identity_source_schema_draft.json`. Module/fixture IDs and phrases in the captured adapters are not a completed generic extraction layer.

## Resume and verification commands

From the repository root, inspect the checkout first. Use the lockfile and confirm the inspected Cognee version before native tests:

```bash
git status --short
git log -1 --oneline
uv sync --group dev
uv run python -c "import cognee; print(cognee.__version__)"
uv run pytest -q -m 'not integration'
```

On branch `stage6-group-combine` (2026-10-21) the unit suite gives 207 passed and 34 deselected. On `c3becf2` it gave 143 passed and 29 deselected. The inspected native version must be **1.6.2**. If the version differs, inspect compatibility again. Do not identify another version as the tested profile. Run focused native tests for the changed path first. The full native suite is `uv run pytest -q -m integration`. It creates fresh stores and can take minutes.

The latest happy path, with a **new** root, is:

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/stage6_resume_check --embedding loopback
uv run python -m cognee_lab.identity split-group --root outputs/stage6_resume_check --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity combine-groups --root outputs/stage6_resume_check --source doc01 --expected-revision 2
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_resume_check --source doc01
```

This sequence uses loopback embeddings. Without `--embedding loopback`, `chunked-fixture` uses the default `--embedding env` profile. That profile needs `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` in the repository `.env`, and it calls that embedding endpoint. Later commands read the profile from the root marker, so they do not need the flag. pytest always uses loopback and does not need `.env`.

Expected: two facts after the split and after the combination, doc01 current at 2/2/2 after the split and 3/3/3 after the combination, doc02 unchanged at 1/1/1, fresh g06 and its generated fact, g01, g04 and g05 absent, g02/shared support present, no recovery incident. The [group split guide](stage6_identity_group_split.md) has the expected values and separate fresh-root `replace_published` failure/recovery sequences. `status` and `retrieve` inspect existing marked roots; fixture creation refuses existing directories. A root made before the `.env` fix opens only for `status` and `retrieve`.

## Verification and landing

The user agreed this routine on 2026-10-21:

1. **Unit tests on every commit.** Run `uv run pytest -q -m 'not integration'`. The suite uses loopback embeddings and includes the identity-ledger check at its default depth. GitHub Actions runs the same command on every push (`.github/workflows/unit-tests.yml`).
2. **Identity-ledger check when `RecordStore` or its callers change.** Run `uv run python support/ledger_check.py`.
3. **The changed feature's verify journeys on every feature change.** Run `.claude/skills/verify/scripts/verify.py journey <ID>` for each journey in the changed feature's file under `.claude/skills/verify/features/`. For example, a regrouping change runs G1 to G4.
4. **`verify.py journey all` once per checkpoint, before the merge to `main`.**

The integration suite, `uv run pytest -q -m integration`, takes about 10 minutes and runs only on a local machine. Run the focused native tests for the changed path.

**Verify journeys.** The journeys drive the CLI through real Cognee stores in fresh roots under `outputs/verify/`. The map in `.claude/skills/verify/features/` has 24 journey blocks. `journey all` runs the 23 loopback blocks as 34 runs. Journey P5 calls the NVIDIA embedding API in `.env`, so it runs only with `--include-env`. Journeys use `--embedding loopback` unless a block asks for `env`. `.claude/skills/verify/SKILL.md` gives the helper commands and proof rules. The earlier `journey all` run on 2026-10-21, before the regrouping journeys, gave 586 PASS rows and 0 FAIL rows on the Mac.

An earlier full run on 2026-10-21 took about 2 hours. The step timings suggest that macOS idle throttling caused most of it. Every step took a flat 40 s or so until `caffeinate` started, and about 4 s after. This is an inference from the timings, not a proven cause. A warm step costs about 3.6 to 6.7 s, and about 2.4 s of that is imports. An unthrottled full run is estimated at about 11 minutes. A separate branch is adding `--jobs N` and automatic `caffeinate` to `verify.py`. That work is in progress.

**Identity-ledger check.** It runs every sequence of real `RecordStore` calls up to a depth bound, with two sources and two writers. It checks properties P1 to P6 after each step. The default depth is 5. Since the regrouping plan joined the model on 2026-10-21, depth 5 gives 3828 nodes and 3717 sequences in about 6.7 s. Before that it gave 3062 nodes. `PINNED` in `tests/test_identity_ledger_check.py` holds the current counts. Depths 6 to 8 are manual runs. `--skip-probability P --seed S` samples a deeper search, and a sampled run never reports `verified within bound`. At depth 5 the check catches all 30 scratch breaks in `support/ledger_mutants.py`: 29 as a property failure and one as `INCONCLUSIVE`. The unit suite runs each break. One more break, in `DEEP_MUTANTS`, needs depth 7. The check found no bug in the current code. The user chose a Python checker over TLA+. `.claude/skills/identity-ledger/SKILL.md` says when to run it, and `reference.md` holds the measurements.

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
