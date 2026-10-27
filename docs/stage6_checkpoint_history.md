# Stage 6 checkpoint history

This document holds the dated checkpoint history of Stage 6 that [the session handoff](SESSION_HANDOFF.md) carried until 2026-10-27. On 2026-10-27 the assistant moved it here verbatim, so that the handoff could become a short resume document. Only headings and links changed. The old header paragraph and the old counts and timings sit under new headings. The old "Next task" and "Tracked follow-ups" sections carry their date in the heading. A link to a section that stayed in the handoff now points there.

The sections keep their original order. Read [the session handoff](SESSION_HANDOFF.md) for the current state, the next task and the working rules. A statement here such as "next", "open" or "since" is true as of its date, not necessarily today.

## Handoff header as of 2026-10-26

The handoff opened with this paragraph until 2026-10-27.

**Updated:** 2026-10-26 (America/Detroit). **Current work:** Stage 6, accepted implementation step 5 / M4. Its removal checkpoint, S2 "deletes outside the lab", merged into `main` at `c711997` on 2026-10-26, and its first entry-point checkpoint, S3a "the lab's add, cognify and remember", merged at `3da0d7f` the same day. Its second entry-point checkpoint, S3b "every builder on the entry points", merged at `3207a72` later on 2026-10-26. Its third, S4 "the lab update", merged at `399ce94` later the same day. Its retrieval checkpoint, S1 "the public retriever", merged into `main` on 2026-10-26. Step 4 / M3 completed on 2026-10-25. The step-4 history follows. The user approved one general occurrence map on 2026-10-21, to replace the three admission modes. All three checkpoints are complete: A (the general admitter and its proof), B (every text change switched to the general map, old modes deleted) and C (the captured mixed addition and removal case). On 2026-10-22 Checkpoint D folded the unchanged-text correction into the same admission and relaxed its recipe and document-variant rules, Checkpoint E added four changed-interpretation and kind-change fixtures, and Checkpoint F added `forget` and `readd` for a source nothing depends on. A no-behavior-change refactor of the ledger and the retiring operations followed. On 2026-10-23 Checkpoint H, the first dependencies checkpoint (step-4 item 3), made a text edit of a consumed document withhold from retrieval only the dependents' decisions that read what changed, until they are refreshed or re-confirmed. Later on 2026-10-23 Checkpoint I made `forget` an erasure. It accepts any source, leaves a tombstone of identifiers and, after the caller confirms a dry run, removes the decisions of other sources that cited the forgotten source. The re-add follow-ups F1 and F2 landed on `main` the same day. Also on 2026-10-23 Checkpoint J1, the first chains checkpoint, let a decision cite another source's decision and withholds the citing decision whenever what it cites is withheld, changed or gone, down the whole chain. On 2026-10-24 Checkpoint J2 made a forget cascade down that chain, level by level, under one dry run, one token and one confirmation, and the user decided the kind-change, Entity-edit, facts and non-identity questions. Later on 2026-10-24 Checkpoint K answered what happens to the readers of an Entity or a saved record that changed or went. It added a lab `edit-entity` command and reviewer paths for an Entity input, `replace-citation` for a citer of a removed record, the refusals `record_key_reused` and `mention_input`, and kind changes on a root where other sources read doc01. On 2026-10-25 branch `stage6-cleanups` closed the small tracked follow-ups, two real-embedding fixtures passed on the user's Mac, and the user declared step 4 done (see [Cleanups and step-4 close](#cleanups-and-step-4-close-2026-10-25)). On 2026-10-25 a discussion session with the user settled the step-5 work units. S2 then made the lab detect a delete made through Cognee's own API, erase the lab's copy afterwards, forget a whole dataset and never reuse a removed Entity UUID (see [Step 5 S2](#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26)). S3a then gave the lab its own `add`, `cognify` and `remember` over Cognee's `cognify_pipeline`, moved the doc01 `fixture` onto them and stamped the lab's files so a plain `cognee.cognify` skips them (see [Step 5 S3a](#step-5-s3a-the-lab-entry-points-2026-10-26)). S3b then moved every other creation command and `readd` onto `add` and `cognify`, one source at a time in publication order, and deleted the hand-built creation path (see [Step 5 S3b](#step-5-s3b-every-builder-on-the-entry-points-2026-10-26)). S4 then moved every text edit onto the lab's `update`, which rebuilds the original's chunks with Cognee's standard Tasks inside one lab Task, and deleted the hand-built edit path (see [Step 5 S4](#step-5-s4-the-lab-update-2026-10-26)). S1 then added the lab's `IDENTITY` search type to Cognee's `SearchType`, so `cognee.search` returns the lab's checked facts with no LLM call, and added a conformance check that gates retrieval changes against a committed baseline (see [Step 5 S1](#step-5-s1-the-public-retriever-2026-10-26)). On 2026-10-26 the user confirmed the assistant's S3a decisions. **Next task:** the source-aware mode and the other step-5 delivery items. See [Next task](#next-task-and-the-overnight-decisions-as-of-2026-10-26). This document records the current continuation state; dated experiment writeups describe their own checkpoints.

## Code baseline and delivery status

Runtime code is in `src/cognee_lab/identity/`. The implementation admits every text change through one **general occurrence map** (`admit` in `admission.py`), which covers the captured prefix edits, removals, additions, split, combination and one mixed edit. Since 2026-10-22 the unchanged-text correction goes through the same `admit`, by way of `admit_replacement` in `replace.py`. The map refuses a changed resolution or meaning, a change of representation kind, a move to another document and span-scoped variants. Since 2026-10-23 a text edit of a document that another source read is admitted: it withholds the dependents' decisions that read what changed (see [Checkpoint H](#dependencies-decided-and-built-2026-10-23)). Since Checkpoint I (2026-10-23) `forget` erases a source of any state and removes the dependents' decisions that cite it (see [Checkpoint I](#erasure-decided-and-built-2026-10-23)). Since Checkpoint J1 (2026-10-23) a decision may cite another source's resolution or variant assignment, and withholding spreads down the chain of citations (see [Checkpoint J1](#chains-j1-decided-and-built-2026-10-23)). Since Checkpoint J2 (2026-10-24) a forget removes every level of that chain under one confirmed dry run (see [Checkpoint J2](#cascade-j2-built-2026-10-24)). Since Checkpoint K (2026-10-24) a reviewer can answer a decision withheld by an edited Entity or by a removed record, a cited record key cannot come back with another meaning, no corpus input may name a mention UUID, and a kind change runs where other sources read the changed document (see [Checkpoint K](#readers-of-a-changed-or-retired-entity-or-record-k-built-2026-10-24)). On 2026-10-25 the cleanups branch made no change to what the lab admits or serves. It replaced the glossary root's `elif` chain with a command table, moved the re-confirm's record writes into `records.py` and fixed small defects, among them `forget`, `readd` and `withdraw` on a single-source `fixture` root (see [Cleanups and step-4 close](#cleanups-and-step-4-close-2026-10-25)). The implementation does not include automatic Describe or facts as citable records. The general-map update changed admission, the saved text-change plan, result JSON, the captured describers, a CLI command, the ledger model, verify journeys and tests. The saved-source schema and dependencies are unchanged. Since step 5 S2 (2026-10-25 to 2026-10-26) `status` lists a source whose native copy Cognee deleted or changed (`native_deleted`), `reconcile` refuses it, and `forget` erases the lab's copy afterwards. A kept decision may keep citing an Entity deleted outside the lab, and no publication recreates it. `forget-dataset` forgets a root's whole dataset under one dry run and token, and repairs a root after a native dataset forget or prune. An append-only removal record (`lab_identity_removed_entities`) keeps every Entity UUID a lab operation removed, and no removed UUID is used again (see [Step 5 S2](#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26)). Since step 5 S3a (2026-10-26) `entry.py` holds the lab's `add`, `cognify` and `remember`, which run Cognee's chunking Tasks and one lab publication Task under the pipeline name `cognify_pipeline`. The lab stamps the files it manages as cognified, so a plain `cognee.cognify` with its defaults skips them (see [Step 5 S3a](#step-5-s3a-the-lab-entry-points-2026-10-26)). Since step 5 S3b (2026-10-26) every creation command and `readd` registers and publishes through `add` and `cognify`, one source per `cognify` in publication order (`entry.remember_in_order`), and a source with no publication is refused `not_published`. The hand-built creation path is gone (see [Step 5 S3b](#step-5-s3b-every-builder-on-the-entry-points-2026-10-26)). Since step 5 S4 (2026-10-26) every text edit goes through `entry_update.update`, and `reconcile` of a failed text change goes through `entry_update.replace_text`. Both run one lab Task under `cognify_pipeline` that calls `publisher.replace` with a `TextChange`, so the occurrence-map admission and the incremental identity revision are unchanged. Inside the text change, Cognee's standard Tasks rebuild the original's chunks (`native_chunks.build_chunks`). An edit of a source whose native copy is gone is refused `native_deleted` before it reads the registered text or the chunk budget. The hand-built edit path is gone (see [Step 5 S4](#step-5-s4-the-lab-update-2026-10-26)). Since step 5 S1 (2026-10-26) importing `search.py` adds the member `IDENTITY` to Cognee's `SearchType` enum and registers `IdentityRetriever` for it, so `cognee.search` with `IDENTITY` and one dataset returns what the CLI `retrieve` returns. Both run `settled.retrieve_settled`. Only an Entity that a served source of the searched dataset constructs can seed a search. `support/conformance_check.py` scores `IDENTITY` searches on a DOC01 fixture against the Stage 5.3 benchmarks and fails when a case moves from its committed baseline (see [Step 5 S1](#step-5-s1-the-public-retriever-2026-10-26)).

The user's Mac addition, reopened retrieval, healthy reconcile and `replace_published` failure/recovery outputs have been reviewed. The user approved the split and combination case and the general occurrence map on 2026-10-21, and the mixed case on the same day. The assistant and its subagents verified their implementation on the user's Mac with loopback embeddings. This handoff records no user-reviewed fixture roots for them. [Next task](SESSION_HANDOFF.md#next-task) gives the next task.

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

Branch `stage6-entity-edits` (2026-10-24) adds Checkpoint K on top of `main` at `9c6f16e`: `edit-entity`, review by input kind, `replace-citation`, `record_key_reused`, `mention_input`, kind changes on a glossary root and journeys D12 to D16 and K6 to K9. It has 13 commits to `514c0bb`, plus this docs commit: the implementation (4 commits, to `3237563`), fix round 1 (5 commits, to `94d54bb`), fix round 2 (3 commits, to `5e0c314`) and a docstring wrap. It landed through the same playbook; `main` is at `c4de4ad` with its docs. `768654b` then changed only the landing playbook and `CLAUDE.md`.

Branch `stage6-cleanups` (2026-10-25) closes step 4 on top of `main` at `768654b`. It has the cleanups and the single-source forget fix (11 commits, to `78b70df`), then a fix round after `/pstack:thermos` (6 commits, to `66fda9f`), plus the closing docs. It lands through the same playbook. After its `--ff-only` merge, `main` is the baseline for step 5.

Step 5 S2 (2026-10-25 to 2026-10-26) landed in three parts through the same playbook. Branch `stage5-s2-removal` (part 1, 16 commits from `dc538d0` to `e2dd353`) added the detection, the reconcile refusal, the lab forget after a native delete and the outside-deletion rules. Branch `stage5-s2-part2` (part 2, 13 commits to `c6a5f59`) added the re-add remedy, `forget-dataset`, the repair, the orphan sweep and the no-reuse rule. Branch `stage5-s2-removed-uuid` (15 commits to `c711997`) added the removal record. `main` was at `c711997`, and GitHub Actions passed on it.

Step 5 S3a (2026-10-26) landed through the same playbook. Branch `stage5-s3a-entry` has 14 commits from `b21576f` to `3da0d7f`: the build (6 commits, to `698ea0a`) and a fix round after `/pstack:thermos` (8 commits). `main` was at `3da0d7f`.

Step 5 S3b (2026-10-26) landed through the same playbook. Branch `stage5-s3b-entry` has 5 commits after the S3a docs commit `9d1a946`, from `4922fc5` to `3207a72`: the build (3 commits, to `8aa1235`) and a fix round after `/pstack:thermos` (2 commits). `main` was at `3207a72`.

Step 5 S4 (2026-10-26) landed through the same playbook. Branch `stage5-s4-update` has 8 commits after the S3b docs commit `7d43ec7`, from `602cfb3` to `399ce94`: the build (3 commits, to `e07e435`) and a fix round after `/pstack:thermos` (5 commits). `main` was at `399ce94`.

Step 5 S1 (2026-10-26) landed through the same playbook. Branch `stage5-s1` has 22 commits after `main` at `70d100f`, from `62ef936` to `cdbb6bf`, and this docs commit. `70d100f` is the last of the design-snapshot commits that followed the S4 docs. The 22 commits are the build (4 commits, to `f82b1aa`), fix round 1 after `/pstack:thermos` (6 commits, to `b904df3`), the conformance check (3 commits, to `64bad48`) and fix round 2 after a second `/pstack:thermos` (9 commits, to `cdbb6bf`). The probe commit `21a74e7` was dropped from the branch and kept at the tag `s1-probes-2026-10-26`. The branch merged into `main` on 2026-10-26, so `main` is at this docs commit.

[Verification and landing](SESSION_HANDOFF.md#verification-and-landing) describes the tools and the landing steps.

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
| Deletes outside the lab (step 5 S2) | `status` lists a source whose native copy is gone or changed (`native_deleted`), including the chunk loss after a plain `cognee.update`; `reconcile` refuses it; `forget` erases the lab's copy afterwards. An Entity deleted outside the lab stays absent while kept decisions cite it, and journey D17 answers its readers one at a time. A re-add waits for live citers, then derives a new UUID. `forget-dataset` forgets a dataset with its non-lab Data, and repairs a root after a native dataset forget or prune. An append-only removal record keeps every removed Entity UUID from use again | [Forget](stage6_identity_forget.md#deletes-outside-the-lab), [Entity edits](stage6_identity_entity_edits.md#outside-deletion-built-in-step-5-s2) |
| Lab entry points (step 5 S3a) | `fixture` builds doc01 through the lab's `remember`: Cognee's `cognify_pipeline` chunks the original and one lab Task publishes the captured description with writes that carry no Cognee run ID. The original, the identity file and the seed are stamped as cognified, so `native-cognify` (a plain `cognee.cognify()`) skips all three with no LLM call. A failed first publication keeps its chunks and stamp, and `reconcile` chunks the original again and restores the fact. A leaked LLM call fails at a closed loopback port | [Entry points](stage6_identity_standard_entry_points.md) |
| Every builder on the entry points (step 5 S3b) | `multi-fixture`, `chunked-fixture` and `glossary-fixture [--chain]` add, then cognify, each source in publication order, and `native-cognify` skips the five Data items of a two-source root and the seven of a chain root. A first publication that fails on a later source stops the run before the next source is added; `reconcile --source` finishes it through `cognify`. `readd` registers and stamps through `add` and publishes through `cognify` at the expected revision. A source with no publication is refused `not_published` | [Entry points](stage6_identity_standard_entry_points.md#which-commands-use-them) |
| The lab update (step 5 S4) | `edit-text`, the occurrence commands, the kind changes and `edit-glossary` edit through `update`: one lab Task under `cognify_pipeline` calls `replace` with the text change, and Cognee's standard Tasks rebuild the chunks with the lab's untagged context. doc01 reaches revision 2, and `native-cognify` then skips every Data item. A failure at each replacement stage exits 1 with `recovery_event_id`, leaves the original stamped, and `reconcile` finishes it through `replace_text`. An edit of a natively deleted source is refused `native_deleted` with the forget hint | [Entry points](stage6_identity_standard_entry_points.md#the-labs-update) |
| The public retriever (step 5 S1) | `search` calls `cognee.search` with the lab's `IDENTITY` search type and returns the `retrieve` result field for field, with `mode`, `scope` and `dataset_id`, logged once as `IDENTITY` and with no LLM call. A failed publication, a withheld decision and a source deleted outside the lab are listed under `unavailable_sources` as `retrieve` and `status` list them. An unbuilt scope or mode, and `datasets=None` once the user can read two datasets, are refused `SearchRefused` with no search history row. A plain `CHUNKS` search (`native-search`) serves a failed source's text. The conformance check on a DOC01 root exits 0 against its baseline | [IDENTITY search](stage6_identity_public_search.md), [Conformance check](stage6_conformance_check.md) |

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
- 2026-10-25, cleanups. The assistant's subagents added journey F21 to `features/source-lifecycle.md`: a single-source root forgets, re-adds and withdraws doc01. The map now has 76 journey blocks, and `journey all` runs the 75 loopback blocks.
- 2026-10-25, real-embedding runs. The user ran journeys M1 (from D3) and M2 (from F18) with `--embedding env` on their Mac: 22 PASS and 16 PASS, 0 FAIL. The journeys are not in the feature map; see [Cleanups and step-4 close](#cleanups-and-step-4-close-2026-10-25).
- 2026-10-25, checkpoint run for the step-4 close. The assistant ran `journey all` on the Mac with loopback embeddings: 1666 PASS rows in 102 runs on `66fda9f`, 0 FAIL rows. P5 needs `--include-env` and did not run. After a last tidy commit, journeys D1 to D16, G1 to G4 and K1 to K9 gave 508 PASS rows, 0 FAIL.
- 2026-10-25 to 2026-10-26, step 5 S2. The assistant's subagents added journeys F22 to F28 to `features/source-lifecycle.md` and D17 to `features/dependencies.md`, and ran them on the Mac with loopback embeddings, with 0 FAIL rows in each round. Journeys D1 to D17, F1 to F22, E1 to E4, G1 to G4 and K1 to K9 gave 1086 PASS rows after part 1, and with F23 to F28 1168 PASS rows after part 2. The map now has 84 journey blocks, and `journey all` runs the 83 loopback blocks as 110 runs.
- 2026-10-26, checkpoint run for S2. The assistant ran `journey all` on the Mac with loopback embeddings: 1775 PASS rows and 0 FAIL rows in 110 runs, on `3bc84eb` plus its review fixes. The final head `c711997` differs from that run only by a retry bound that unit tests cover. P5 needs `--include-env` and did not run.
- 2026-10-26, step 5 S3a. The assistant's subagents added journeys L1 to L3 in a new feature file, `features/standard-entry-points.md`, with the letter `L`. The map now has 87 journey blocks, and `journey all` runs the 86 loopback blocks as 115 runs.
- 2026-10-26, checkpoint run for S3a. The assistant's subagent ran `journey all` on the Mac with loopback embeddings: 1818 PASS rows and 0 FAIL rows in 115 runs, on the fix-round head `14c2911`. The final head `3da0d7f` adds one CLI step to a native test, which passed. P5 needs `--include-env` and did not run.
- 2026-10-26, step 5 S3b. The assistant's subagents added journeys L4 to L7 to `features/standard-entry-points.md`: every two-source root, a chain root with a failed doc03, a failed doc02 and a re-add. The map now has 91 journey blocks, and `journey all` runs the 90 loopback blocks as 120 runs.
- 2026-10-26, checkpoint run for S3b. The assistant's subagent ran `journey all` on the Mac with loopback embeddings: 1853 PASS rows and 0 FAIL rows in 120 runs. P5 needs `--include-env` and did not run.
- 2026-10-26, step 5 S4. The assistant's subagents added journeys L8 to L10 to `features/standard-entry-points.md`: a text edit through the lab's `update`, a failed update at every replacement stage with its `reconcile`, and `native-cognify` after a kind change and a glossary edit on a chain root. The map now has 94 journey blocks, and `journey all` runs the 93 loopback blocks as 131 runs.
- 2026-10-26, checkpoint run for S4. The assistant's subagent ran `journey all` on the Mac with loopback embeddings: 1953 PASS rows and 0 FAIL rows in 131 runs. P5 needs `--include-env` and did not run.
- 2026-10-26, step 5 S1. The assistant's subagents added the feature file `features/public-search.md` with journeys S1 to S7 (letter `S`) and B1 (letter `B`, the conformance check), and a `verify.py script` step that runs a `support/` script inside a journey. The map now has 102 journey blocks, and `journey all` runs the 101 loopback blocks as 140 runs.
- 2026-10-26, checkpoint run for S1. The assistant's subagent ran `journey all` on the Mac with loopback embeddings on `cdbb6bf`: 2022 PASS rows and 0 FAIL rows in 140 runs. B1 holds 7 checks. P5 needs `--include-env` and did not run.
- Not exercised against an env root. The warning path for a missing tokenizer fix, and the doctor failure path for an operator file that lacks a key.
- Exercised. The doctor failure path for a pre-profile marker, a malformed marker, and an env root whose operator file names another model.

## Original six-step implementation sequence

This is **step 4 within Stage 6**, not project Stage 4.

| Step | Current status |
|---|---|
| 1 / M0 | Runtime forms/schema, exact chunk mapping, portable bookkeeping and capability checks implemented for the initial profile |
| 2 / M1 | Captured Task → native publication → useful fact/evidence retrieval → reconcile demonstrated |
| 3 / M2 | Multi-source ownership/withdrawal demonstrated; general exact-ID semantic conversion remains broader than the captured writer |
| 4 / M3 | Complete (2026-10-25): corrections, prefix/rechunk edits, partial occurrence removal, empty unresolved and resolved fact-bearing group retirement, captured additions/new group, captured group split and combination, one general occurrence map for every text change, a captured mixed addition/removal edit, explicit caught-failure recovery, forget and re-add of a source nothing depends on, per-decision withholding of dependents after a text edit (glossary fixture), erasure of any source with removal of the dependents' decisions that cite it, decisions that cite other sources' decisions, with withholding down the chain (chain fixture), erasure down the chain under one confirmed dry run, and reviewer paths for the readers of an edited Entity or a removed record, with kind changes under readers. The rest moved to step 5 or step 6, or stays a documented limit; see [the step-4 close](#cleanups-and-step-4-close-2026-10-25) |
| 5 / M4 | In progress. S2 (2026-10-26): detection of deletes made outside the lab, the lab forget afterwards, dataset forget and repair, and the removal record. On 2026-10-25 the user chose lab entry points over the B Task-transform patch and detection over delete hooks. S3a (2026-10-26): the lab `add`, `cognify` and `remember` entry points, with the doc01 `fixture` on them. S3b (2026-10-26): every other creation command and `readd` on them, and the hand-built creation path deleted. S4 (2026-10-26): the lab `update`, with every text edit on it and the hand-built edit path deleted. S1 (2026-10-26): the `IDENTITY` search type in `cognee.search`, semantic mode, and a conformance check against the Stage 5.3 benchmarks that gates retrieval changes. Next: the source-aware mode. Grouped delivery, annotation states, broader traversal and offline diagnostics are not implemented |
| 6 / M5 | Seeded rules/model Describe and separate quality/consistency evaluation not implemented |

### Remaining step-4 work

This list is history. Step 4 closed on 2026-10-25. [Where the rest went](#where-the-rest-of-step-4-went) says which step owns each remaining part.

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

### Cleanups and step-4 close, 2026-10-25

On 2026-10-25 the user asked for the small tracked follow-ups that needed no decision, then made these decisions:

1. The remaining [tracked follow-ups](#tracked-follow-ups-as-of-2026-10-26) stay documented limits, the second-forget tombstone gap included.
2. Step 4 is done once three things land: the cleanups branch `stage6-cleanups`, `journey all` and the closing docs.
3. Step 5 is next.

**What the cleanups changed.** No saved schema, admission rule or retrieval result changed. Each item lists its commits on `stage6-cleanups`.

- **Command table (B8).** `glossary_fixture.run` dispatches through a table instead of an `elif` chain (`f0e9e3b`, `547d891`). A `Command` is a handler and a `Scope`, the sources the command accepts with its refusal. Each handler returns the command's whole result through `finish`, which takes the snapshot and writes `glossary_result.json`. `OWN_COMMANDS` holds the commands only a glossary root takes, and `SHARED_COMMANDS` the commands other fixture kinds also take. `COMMANDS` and `REVIEW_COMMANDS` derive from the table. The package imports moved to module level, except in the review handler: `review.py` imports `INFO` and `hc_entry` from `glossary_fixture`. A test imports `__main__` in a subprocess and checks that Cognee is not loaded, so a hoisted import cannot open the user's lab store.
- **Re-confirm writes in `records.py`.** `records.apply_reconfirm`, beside `apply_removal`, rewires a re-confirmed decision and the parts its kind's `stripped` hook names through a ref map (`b311ddb`, `6beecf4`). Both share `records.write_parts`. A behaviour test checks the rewired resolution and group, the unchanged fingerprint and an untouched sibling. A guard test flags a stored or deleted subscript of `mention_resolutions` or `mention_groups` in `review.py` or `revisions.reconfirmed`.
- **Small duplication.** `erasure_rules.erasures_of` takes its readers from `corpus_readers`, and `review.py` points to `drop_unnamed_recipes` instead of restating it (`9ea2941`). The unused `ChunkInput` import in `publish.py` is gone (`106fb29`).
- **`refresh-dependents` raises a failure as itself.** Before, it re-raised a failure that was not an `IntentError` as an `IntentError` named after the class, which lost the class and the traceback (`6bfd097`). The exit code stays 1. `revisions.refresh` is now an async generator that yields each written range, and `refresh_dependents` collects the ranges inside its `try` (`8734f8b`).
- **`remains()` guard.** A forget snapshot of a plan saved before `stored_files` is refused as `recovery_plan` through `forget.require_stored_files`, which a forget retry also uses (`56118a3`, `66fda9f`).
- **A producer per prefix edit.** `describe_prefix_edit` names `text_review_r<N>` instead of the fixed `text_review`, so a second prefix edit after a re-confirm is admitted (`72a6608`). The test failed with `reconfirm_unattested` first.
- **Cascade check, end to end.** `support/cascade_check.py` now also checks the outcome: once a cascade finishes, with no retirement or after any withdrawal the fence allows, no live source cites a removed record (`a7f6fb6`, `e0c58a1`). The new mutant `skip_citers_of_withdrawn` is caught only by this property. The four-source cascade search took about 343 s against 258 s without it, measured on a loaded machine. A try that checked once on the initial rows also caught the mutant but saved no time, so the check stays per step.
- **Erasure-retry reconcile keeps the saved plan.** `Publisher.superseded` now carries the saved `retired_entities`, `old_edges` and `previous_edges` forward, not only `erased_from` (`3b8f68d`). `replace.saved_retirement` copies those `RETIREMENT_FIELDS` with `copy.deepcopy` (`b41764a`). The unit test failed first.
- **Single-source forget, re-add and withdrawal.** On a `fixture` root, `forget`, `readd` and `withdraw` finished their writes and then exited 1 with `FileNotFoundError` on `multi-fixture-info.json` (`78b70df`). The step-5 probe E4 found it on 2026-10-25. `multisource.fixture_files` now names each identity file for both root shapes. A native test and journey F21 forget, re-add and withdraw doc01 on a `fixture` root.

**Outside deletion of a cited Entity (cleanups item 4), deferred.** Item 4 asked for a stand-in that deletes the Helios controller Entity through Cognee's own graph API, and a journey D17. The brief said to prototype first and to stop if a user decision showed. The assistant's subagent ran the probe on the user's Mac on 2026-10-25, in a new loopback root, `outputs/verify/20261025T144616Z-item4-delete-probe/` in the cleanups worktree. Deleting Helios withholds r01 and v01 (`input_removed`) and, down the chain, c01 and c02 (`upstream_withheld`). `reconfirm` is refused, and retrieval serves 0 facts. But `replace-decision` on r01 and on v01 are both refused `missing_reasoning_input`, because the other withheld decision still cites `existing_A`. Neither decision can be answered first. `graph.delete_node` also left Helios's `Entity_name` vector point behind.

The user decided on 2026-10-25:

1. A withheld decision may keep citing a deleted Entity while a neighbouring decision is replaced. The fix relaxes `admission.check_corpus_inputs_exist` for citers that are already withheld.
2. A republish may not recreate an Entity deleted outside the lab. A replacement picks a new target or leaves the mention unresolved.
3. Step 4 records the deadlock as a documented limit. The fix, journey D17 and the orphaned vector point go to step 5 S2 (removal).

No stand-in was committed, and the glossary text removal was left out: only `forget` removes the glossary.

**Real-embedding runs.** The user ran two fixtures on their Mac on 2026-10-25, in a new user account, from worktree `mac-env-runs` at `main` `768654b`. `COGNEE_ENV_FILE` pointed at the repository `.env`, and the roots used `--embedding env` (`nvidia/nemotron-3-embed-1b`, 2048 dimensions). The journeys were built from D3 and F18 with the env profile, plus the P5 probe checks. The user decided that both passing lets step 4 close. The evidence is in `outputs/step4_mac_env_20261025/`, with the journeys in `journeys.md`.

- M1, from D3: a cosmetic glossary edit withholds r01 and v01, and two re-confirms release them. 22 PASS and 0 FAIL, run `20261025T142056Z-m1`.
- M2, from F18: a forget cascades down a two-level chain, the level-2 removal crashes, the re-add is refused, `reconcile` finishes the cascade and the re-add succeeds. 16 PASS and 0 FAIL, run `20261025T142152Z-m2`.
- Both probes: the marker records `env`, `nemotron-3-embed-1b` and 2048; every vector column has 2048 dimensions; `reopen_problem` is null; the key scan found no leak.
- Earlier attempts stopped at step 1, because the sandbox and the old account could not read `.env`. They made no API calls.

**Process.** Run by the assistant and its subagents on 2026-10-25. A subagent wrote the cleanups from the local, untracked brief `.audit/step4-cleanups.todo.md`, in 11 commits to `78b70df`. A `/pstack:thermos` review followed. The bug review found no medium or higher issue, and the quality review asked for changes. A subagent answered them from `.audit/step4-cleanups-fix.todo.md` in 6 commits, to `66fda9f`, and the assistant added one tidy commit after the final review.

**Evidence**, run by the assistant and its subagents on the user's Mac with loopback embeddings, except the real-embedding runs above:

- On the final head: unit suite 569 passed, 87 deselected. `support/ledger_check.py` PASS at depth 5, `PINNED` unchanged at 9205 nodes and 9050 sequences. Journeys D1 to D16, G1 to G4 and K1 to K9: 508 PASS rows, 0 FAIL.
- In the fix round, on `66fda9f`: `chain_check` PASS with 0 disagreements and `--mutants` 23 of 23 caught; `ledger_check --mutants` as expected; journeys D, E, F, G and K 1061 PASS rows, 0 FAIL, and all 456 step JSONs matching a `78b70df` baseline once IDs and timestamps were masked. A final `/pstack:thermos` review of the whole branch found nothing at medium or higher; its low findings went into the last tidy commit.
- `journey all` on `66fda9f`: 1666 PASS rows in 102 runs, 0 FAIL.

#### Where the rest of step 4 went

The [Stage-6 handoff](../results/cognee_identity_stage6_handoff.md#step-4--m3-closing-summary-2026-10-25) has the closing table: each item, its checkpoints, its evidence and where the rest went. In short:

- **Step 5:** source-removal hooks, dataset Forget (T20), endpoint gaps during a generated-source rebuild, and the outside-deletion deadlock with journey D17 and the orphaned `Entity_name` point.
- **Step 6:** facts as saved records, and Describe-driven corpus matching (new-corpus opportunity selection and automatic grouping).
- **Closed in practice:** the verification and recovery item, by the ledger, occurrence, chain and cascade checks, each with mutants that prove it can fail.
- **Documented limits:** the [tracked follow-ups](#tracked-follow-ups-as-of-2026-10-26) below.

### Step 5 S2, deletes outside the lab, 2026-10-25 to 2026-10-26

**The step-5 discussion, 2026-10-25.** The user and the assistant went through the seven work units and the questions U1 to U6. The assistant's working notes, which are not committed, record these decisions:

- Unit 1. A registered IDENTITY SearchType is a first step only. The long-term retrieval entry needs a discussion before it becomes the plan of record.
- Unit 2. No Cognee patch. The lab gets its own `add`, `cognify`, `remember` and `update` entry points, which run Cognee's standard Tasks and the lab's Tasks under Cognee's pipeline names. The docs warn that plain `cognee.cognify`, `cognee.remember` and `cognee.update` bypass identity. The lab must keep native Cognify from parsing the lab's own files (`identity.json`, `seed.txt`) as text. A patch can come later if a caller needs plain Cognee calls to run identity.
- Unit 3. The lab `update` reuses step 4's edit path. Cognee rebuilds the whole document, and the identity revision stays incremental. A probe of plain `cognee.update` comes before S4. Native incremental update waits for step 6.
- Unit 4 (U4). Native deletes stay unwrapped (option c). Lab `forget` is the supported delete. `status` detects a native delete, `reconcile` refuses it, and `forget` works on a source whose native copy is gone. A delete wrapper (option a) comes back only if erasure from plain Cognee calls becomes a requirement.
- Unit 5 (U5). A lab dataset forget that keeps tombstones, and detection and repair after a native dataset forget or prune. A full prune is a reset.
- Unit 6. U1 option (a) for now, to revisit later. U2: the identity search returns evidence only, with no LLM answer. U3: a function argument selects the scope, with identity-anchored facts by default and unattributed native hits as an opt-in. Semantic retrieval comes first, then source-aware retrieval. The Stage 5.3 benchmark joins unit 6. The retrieval modes still await a decision, so the public retriever has not started.

**User decisions for S2.** The outside-deletion decisions of 2026-10-25 are under [Cleanups and step-4 close](#cleanups-and-step-4-close-2026-10-25). The S2 spec asked three more questions, and the user answered:

1. Q1 (2026-10-25). A corpus Entity input may cross datasets, as before. A reader in another dataset counts as a dependent, and a forget removes its decision under the token.
2. Q2 (2026-10-25). A re-add whose files name an Entity deleted outside the lab is refused while a live saved source still cites or builds the Entity. The refusal names each citer, with its dataset and state, and its remedy. With no live citer, the re-add builds the Entity under a derived UUID.
3. Q3 (2026-10-25). `forget-dataset` also deletes Data that no lab source publishes, such as the seed and anything added with plain `cognee.add`. The dry run lists that Data separately, and the token covers the list.
4. No reuse (2026-10-26, option 1). A removed Entity UUID is never used again, including an Entity that a withdrawal deleted. To restore a source after a withdrawal, forget it, forget or replace each source that still names a deleted Entity, re-add the source, and publish each reader again against the new UUIDs.

The assistant reported one default, which is reversible: Cognee's default prune (`prune_system` with `metadata=False`) is a delete the lab repairs and keeps tombstones for, and `prune_system(metadata=True)` is a reset.

**What changes for users.**

- Part 1 (`e2dd353`). `status` lists under `native_deleted` each saved source whose native copy Cognee deleted or changed: after `cognee.forget` of the document or the dataset, after the default prune, and after a plain incremental `cognee.update`, which replaces the chunks the lab's markers and facts sit on. `reconcile` refuses such a source (`native_deleted`) and names the `forget` that erases the lab's copy. `forget` then completes whatever the delete left. `native-forget --case data|dataset|prune|reset` stands in for the delete. `edit-entity --case delete` deletes the Helios controller through `graph.delete_node`. Kept decisions may keep citing the deleted Entity, no publication recreates it (`entity_recreation`), and journey D17 answers r01 and v01 one at a time. This closes the step-4 deadlock.
- Part 2 (`c6a5f59`). A re-add follows Q2 (journey F28). `forget-dataset --dry-run` and `forget-dataset --confirm <token>` forget every source of the root's dataset, readers first, then delete the Data no lab source publishes, item by item. Cognee's `cognee.forget(dataset=...)` is never called. The same command repairs a root after a native dataset forget or prune, and its run deletes each orphaned `Entity_name` point that its dry run listed. On a reset root `reconcile` refuses with `stores_reset` instead of a raw Cognee error.
- Removal record (`c711997`). The ledger table `lab_identity_removed_entities` holds every Entity UUID a lab operation removed, appended once and never changed. A publication that would rebuild a recorded, absent Entity under its old UUID is refused (`entity_recreation`), and a re-add derives a new UUID for it. `forget` may now begin on a failed replacement, which otherwise had no way out once its retry would rebuild a removed Entity. `status` lists the record as `removed_entities`. A failed withdrawal's `reconcile` is refused before admission, as a failed replacement's is.

**The data shapes.**

- `native_copy.NativeCopy` has five facets: the original's Data row, the identity Data row, the document node, every chunk the saved description names, and the raw files of both Data items. A row is natively deleted when a facet is missing and the row's own attempt does not explain it. `status` skips a pending row, a failed forget and a failed text change.
- An Entity counts as deleted outside the lab when a served description, or the publishing source's last verified one, names it as a corpus input or a recipe, its node is absent, and the removal record does not list it (`outside_deletion.lab_removed`). `outside_deletion.left_absent` admits a part that cites it only when the part is as in the last verified description, and the publisher then skips its recipe, edges and contributions in the write and in verification.
- The removal record is the only new saved state. Each operation appends in its verification stage, after its delete. A withdrawal or forget that begins over a failed publication appends that attempt's retirements before `begin` replaces the plan. A repair and the delete of non-lab Data append nothing. At every `initialize` a ledger from before the record gains each tombstone's removed Entities and mention UUIDs.
- `RecordStore` gains `record_removed`, `removed`, `removal_report` and the fill `record_tombstone_removals`, mixed in from `removal_record.RemovalRecord`. `TRANSITIONS` admits forget on a failed replacement. `forget-dataset` only composes `forget` calls, so the ledger sees no other new sequence, and `PINNED` stays at 9205 nodes and 9050 sequences.

**Process.** The assistant and its subagents worked on the user's Mac from 2026-10-25 to 2026-10-26, from a spec that an independent Opus reviewer checked twice, once before each part. Each part had `/pstack:thermos` reviews and fix rounds, and every bug fix came with a test that failed first.

1. Part 1, branch `stage5-s2-removal`. A prototype showed that Cognee's `add_edges` drops an edge to a missing endpoint without making a stub node, and that the corpus-check relaxation alone let `replace-decision --decision r01` recreate Helios, so the publisher also skips the recipe. Fix round 1 gave one definition of a lab removal and one rule for leaving an Entity absent, and moved detection into `native_copy.py`.
2. Part 2, branch `stage5-s2-part2`. Three bug-review rounds each found a re-add that wrote an old UUID again: an unserved source's tombstone, a co-owner's forget while the source was withdrawn, and the source's own forget with a failed co-owner. The user then chose option 1.
3. Removed-UUID record, branch `stage5-s2-removed-uuid`. The three part-2 rounds shared one premise. Each assumed that the lab could rebuild "removed by the lab" from tombstones and plans. A review of `fb4afd2` found a high-severity regression from `main`, because a later operation overwrites those records. The assistant tested the premise directly and replaced the reconstruction with the append-only record. The bug review of the record found two blockers: roots from `main` with `served_entity_ids` in a tombstone failed to open, and a failed replacement whose retry rebuilds a removed Entity had no way out. Both were fixed. The final review found nothing blocking. Two of its low items are fixed: a re-add now derives a new UUID for an Entity an earlier replacement retired (`f4f478c`), and `record_removed` stops retrying after a fixed number of attempts (`a52608c`, `c711997`). Journey W3 found that a failed withdrawal's `reconcile` got the wrong refusal, fixed in `27bfb8d`.

**Evidence**, run by the assistant and its subagents on the user's Mac with loopback embeddings:

- `verify.py journey all` on 2026-10-26: 1775 PASS rows and 0 FAIL rows in 110 runs, on `3bc84eb` plus its review fixes. The final head `c711997` differs from that run only by the retry bound in `removal_record.record_removed`, which unit tests cover. P5 calls the embedding API and did not run.
- Unit suite on `c711997`: 641 passed.
- `support/ledger_check.py`: PASS, `PINNED` unchanged at 9205 nodes and 9050 sequences, and its mutants caught. The checker never calls the new record methods. The new break `forget-refuses-failed-replacement` is `INCONCLUSIVE`. Only the `REACHABLE` count catches it (the final review's third low item). The identity-ledger skill has a dated note.
- `support/occurrence_check.py` and `support/chain_check.py`, each with `--mutants`: PASS.
- GitHub Actions passed on `main`.
- Journeys D1 to D17, F1 to F22, E1 to E4, G1 to G4 and K1 to K9 gave 1086 PASS rows and 0 FAIL rows after part 1. With F23 to F28 they gave 1168 PASS rows and 0 FAIL rows after part 2.

No user-reviewed root for this checkpoint exists yet. The [forget guide](stage6_identity_forget.md#deletes-outside-the-lab) and the [entity edits guide](stage6_identity_entity_edits.md#outside-deletion-built-in-step-5-s2) have the commands, the refusals and the restore steps.

**Known follow-ups**, from the reviews:

1. Case 10, which predates S2. Two forgotten co-owners re-added separately each derive their own replacement UUID, because the derivation keys on the identity source, so one Entity becomes two. Journey F28 shows it.
2. A failed first publication whose recipe builds an Entity deleted outside the lab, and which no served source names, still recreates that Entity on `reconcile`. The case is narrow and cannot split an identity, since nothing else holds the Entity.
3. A withdrawal that lands between a forget's plan and its `begin`. The part-1 form of this item concerned the forget plan's `served` field, which the removal record deleted (`3fbf67b`). The record is append-once, so whichever operation records a UUID first names it. This is an inference from the code, not re-probed. With a single-user CLI the window needs two processes.
4. `reconcile` on a reset root refuses (`stores_reset`). It does not publish the root files again, which still hold the old UUIDs with no ledger to fence them.

### Step 5 S3a, the lab entry points, 2026-10-26

The step-5 discussion of 2026-10-25 chose lab entry points over a Cognee patch ([Step 5 S2](#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26), unit 2). S3a is the first of three checkpoints that build them. S3a adds `add`, `cognify` and `remember` and moves the doc01 `fixture` onto them, S3b moves the other builders, and S4 adds the lab `update`.

**What changes for users.**

- `fixture` builds doc01 through the lab's `remember`. Its output adds `cognify_stamps`, and `original`, `identity` and `seed` are each `true`. The other creation commands and `readd` still register their documents by hand until S3b.
- The lab stamps each file it manages as cognified, so a plain `cognee.cognify` with its defaults skips the file and makes no LLM call. `native-cognify` stands in for that plain call. The [entry-point guide](stage6_identity_standard_entry_points.md#warning-a-plain-cognee-call-bypasses-the-identity-layer) lists the gaps in this protection, among them `cognify(incremental_loading=False)`, a memory-only forget and Cognee's full update path.
- A failure in the lab Task is recorded in the ledger as a failed attempt with its recovery event, as before, and the CLI exits 1 with the same error and `recovery_event_id`. Cognee's own run status still shows `cognify_pipeline` completed, so read `status` for the lab's outcome.
- `reconcile` of a failed first publication runs the lab's `cognify` again. Cognee chunks the original again with the same chunk IDs, and the lab Task finishes the saved plan.
- `status` compares a failed first publication with Cognee's copy like any other row. If its chunks are gone, something outside the lab removed them, so `status` lists the row under `native_deleted` and `reconcile` refuses it.
- The fixture environment points the LLM at a closed loopback port (`http://127.0.0.1:9/v1`). A leaked LLM call fails at once with a connection error and never sends the fixture's fake key to a provider.

**The design.**

- `add` registers the original through `cognee.add`, chunks it in memory with Cognee's chunker, asks the caller's describer for the identity description, writes the description to `identity.json`, registers it and stamps it. `fixture.seed_corpus` registers and stamps the seed.
- `cognify` calls `run_pipeline` under the pipeline name `cognify_pipeline`. `run_custom_pipeline` cannot pass the options the lab needs. Cognee's `classify_documents`, `extract_chunks_from_documents` and `add_data_points` run first. Then the lab Task `identity_publish` runs once per document over the whole chunk set. It stamps the original, then makes a first publication when the source has no row, or else a reconcile. Every Task passes `needs_llm=False`, so the run skips Cognee's LLM connection probe. `cognify` refuses more than one source (`one_source`) until S3b tests that case.
- The lab Task writes with contexts it builds itself (`registered.context_for`), and none carries Cognee's pipeline run ID. Cognee's inline rollback and its API-startup recovery find a run's writes by that ID, so they can reach only the native document node and chunks. The run passes no rollback handler, so a failed run removes nothing, and startup recovery keeps a stamped item.
- `remember` is `add`, then `cognify`. It never runs Cognee's improve step. Cognee's `extract_graph_and_summarize` does not run, and the captured decisions are the only extractor.

**Spec, review and probes.** An Opus subagent drafted the spec read-only on 2026-10-26 against `main` at `e2dd353` and Cognee 1.6.2. An independent Opus reviewer checked it (verdict: proceed with changes) and split the work into S3a, S3b and S4. An Opus subagent then probed Cognee on the user's Mac on `main` at `c6a5f59` with loopback embeddings and the closed LLM port:

- P1. Nested `cognee.add`, ingest, memory-only forget and Data delete inside a `cognify_pipeline` item Task complete with no deadlock. With backend access control on, a one-slot queue could block (inference). The guide notes it.
- P2. Cognee's standard chunks equal the lab's in-memory chunks at budgets 512, 64 and 24, except the document node's `external_metadata`.
- P3. The cognified stamp survives a same-text ingest and a same-file add. A changed-text ingest and a per-item memory-only forget clear it, so the lab stamps again after each.
- P4. A plain `cognee.cognify` on stamped items skips them with 0 LLM calls. Unstamped items made 12 calls to the closed port.
- P5. Only what `add_data_points` writes with the pipeline context carries the run tag. A rollback that removes a chunk also removes every edge that ends at it, the lab's markers and fact edges among them, so untagged writes protect the lab's nodes only.
- P6. Cognee's provider check tests only that a key exists, so only the closed port makes a leaked call visible.

The assistant's working notes, which are not committed, hold the spec, its review, the probe results, the build report and the two reviews below.

**Process.** An Opus subagent built S3a on branch `stage5-s3a-entry` from `c711997` on the user's Mac on 2026-10-26. A `/pstack:thermos` review followed, and neither the bug review nor the quality review found anything blocking. The fix round made these changes:

1. The native-copy exemption for a failed first publication is gone (`40aee33`). The spec review (its item C5) had exempted the document node and chunks of a failed first publication, on the premise that Cognee's rollback might remove them. The bug review showed that a memory-only forget or an outside text change of the original then went unreported, and `reconcile` chunked again what the user had removed on purpose. With no rollback handler, and the stamp written before the lab publishes, no lab cause removes those chunks. A missing chunk is therefore a delete outside the lab. `3da0d7f` shows that the forget the refusal names then erases the row.
2. `cognify` refuses more than one source (`56a9859`). Several sources ran their lab Tasks at once with untested writer contention, and only the first failure was raised.
3. `context_for` moved from `fixture.py` to `registered.py` (`dd5c807`), which removes an import cycle between `entry.py` and `fixture.py`.
4. `fixture.prepare` calls `seed_corpus` (`63fbf00`), so every root it builds has a stamped seed.
5. Smaller fixes. A failed fixture run keeps `fixture-info.json`, and the reconcile of a failed first publication records the test origin (`b5c39e8`). The guide says that Cognee's run status shows a lab failure as completed, and a native test pins it (`ac199c4`). The lab Task's one-caller helper is inlined, and `Semantics` and `Draft` are typed (`14c2911`).

**Evidence**, run by the assistant's subagents on the user's Mac on 2026-10-26 with loopback embeddings:

- `verify.py journey all`: 1818 PASS rows and 0 FAIL rows in 115 runs, on the fix-round head `14c2911`. The final head `3da0d7f` adds one CLI step to a native test, which passed. P5 calls the embedding API and did not run.
- Unit suite: 646 passed.
- The focused native tests for the entry points: 15 passed, the final head's added step included. They pin that the run tags only the document node and its chunks, that Cognee's run status shows a lab failure as completed, that `reconcile` finishes a failed first publication after a rollback removed its chunks, and that `cognee.cognify(incremental_loading=False)` ignores the stamps and fails at the closed port.
- `support/ledger_check.py`: PASS, `PINNED` unchanged at 9205 nodes and 9050 sequences, and its 53 mutants caught. S3a passes no new arguments to `RecordStore`.
- GitHub Actions on `main` at `3da0d7f` (run 40314011240): the `unit` and `chains` jobs passed.

No user-reviewed root for this checkpoint exists yet. The [entry-point guide](stage6_identity_standard_entry_points.md#commands) has the commands and the expected values.

**Known limits**, from the build report and the reviews:

1. `multi-fixture`, `chunked-fixture`, `glossary-fixture` and `readd` still register their documents by hand, and those documents carry no stamp until something the lab writes stamps them. Roots made before S3a carry none either. Closed for new roots by S3b on 2026-10-26.
2. When every chunk of a source is gone, `cognify` chunks again with the default budget of 512 and refuses if the chunk IDs differ from the description. A partial chunk loss gives a misleading message.
3. Short unstamped windows remain, before native chunking and between a forget or a changed-text ingest and the stamp that follows it. A plain `cognee.cognify` in such a window extracts the file. In a fixture root it fails at the closed port.
4. With `ENABLE_BACKEND_ACCESS_CONTROL=true`, each nested Cognee call inside the lab Task asks for a fresh dataset-queue slot, so a queue of one slot could block. The fixtures run with access control off, and this case is untested.

### Step 5 S3b, every builder on the entry points, 2026-10-26

S3b is the second of the three entry-point checkpoints. It moves `multi-fixture`, `chunked-fixture`, `glossary-fixture [--chain]` and `readd` onto the lab's `add` and `cognify`, and deletes the hand-built creation path.

**What changes for users.**

- Every creation command registers and publishes each source through `add`, then `cognify`, one source at a time in publication order. A two-source root runs doc01, then doc02. A chain root runs the glossary, doc01, then doc03. Every file on a new root is stamped, so `native-cognify` skips the five Data items of a two-source root and the seven of a chain root.
- With `--fault-stage` and `--source`, the selected source's first publication fails and the run stops there. The sources after it are never added, so no original is left registered without a stamp. The root's manifest still names them, and a command that selects one refuses it (`source_missing`).
- `readd` admits the re-add on the in-memory text and chunks, as before. It then registers and stamps the files through `add` and publishes through `cognify` at `--expected-revision`. `add` refuses (`chunk_mapping`) if Cognee's chunks differ from the admitted ones.
- `reconcile` of a failed first publication runs `cognify` again on every root kind. Any other row is reconciled over the chunks Cognee holds, as before.
- A new refusal, `not_published`, names a source that was added but has no publication, because its first `cognify` never began. `reconcile --source` and the glossary root's report refuse it. In the build, `reconcile` crashed on the missing row and the glossary snapshot raised a `KeyError`.
- The [entry-point guide](stage6_identity_standard_entry_points.md#which-commands-use-them) lists each command, its sources in order and the entry point it runs. Roots made before S3b carry no stamp on the files their creation command registered by hand.

**The design.**

- `entry.remember_in_order` runs `add`, then `cognify`, for each source of a root in publication order, by label. A failure stops it before the next `add`.
- Each source has one builder, `add_<label>`: `fixture.add_doc01`, `multisource.add_doc02`, `glossary_fixture.add_glossary` and `chain_fixture.add_doc03`. A builder registers its source and returns its description. It reads only the descriptions of the sources before it.
- `cognify` takes one source. Cognee runs the data items of one run concurrently, up to 20 at a time (`run_tasks.py`), and doc03 cites doc01's published decisions, so the sources must publish in order. The `one_source` refusal went with the sequence argument.
- `cognify` re-adds a forgotten source (`publisher.readd` at `expected_revision`). It publishes a source with no captured facts (the glossary, doc03) with `semantics=None`.
- `entry.semantic_hooks` gives the publisher's `semantic_writer` and `verify_semantics` for a source's semantics, or None for both. `cognify` and `multisource.reconcile_one` share it.
- `reconcile` of an already-published source stays on `multisource.reconcile_one`, over the chunks Cognee holds. `cognify` writes the native chunks again before the lab Task runs, so a verify through it would no longer prove that Cognee still holds the chunks and vectors the publication wrote.
- `entry.remember`, one `add` and one `cognify`, lost its fixture caller to `remember_in_order`. The assistant kept it as the spec's public entry point, and a unit test now covers it.
- Deleted: `fixture.prepare`, `prepare_doc03`, `publish_one` and the hand-built publish routes (chunk in memory, `add_data_points`, then a publish Task in `run_tasks_base`). `fixture.load_chunks` stays as a read-only chunking of the original for `reconcile` and the revisions.

**Process.** An Opus subagent built S3b on branch `stage5-s3b-entry` from `3da0d7f` on the user's Mac on 2026-10-26 (`4922fc5` to `8aa1235`). A `/pstack:thermos` review followed, and neither the bug review nor the quality review found anything blocking. The fix round (`899c260`, then the guide in `3207a72`) made these changes:

1. Each source is added, then cognified, before the next is added. The build added every source first and then cognified each in turn. A source after a failed one was then left registered without a stamp, a plain `cognee.cognify` in a real environment would extract it with the LLM, and no lab command could publish it. The bug review proposed the new order, and the assistant chose it.
2. `reconcile` and the glossary snapshot refuse a source with no row (`not_published`).
3. `cognify` takes one source, and `remember_in_order` replaces two copies of the per-source loop. The builders share one shape, `add_<label>`. `semantic_hooks` replaces two copies of the hook pair. `revisions.finish_publication` takes its semantics from `semantics_for(label)` instead of a fixed `CapturedSemantics`.
4. Two review proposals were dismissed with a reason. Every `reconcile` through `cognify` would rewrite the chunks that the verify must find. Deleting `entry.remember` would remove the spec's public entry point, so it stays with a test.

The assistant's working notes, which are not committed, hold the build report and the two reviews with the assistant's decision.

**Evidence**, run on the user's Mac on 2026-10-26 with loopback embeddings:

- `verify.py journey all`, run by the assistant's subagent: 1853 PASS rows and 0 FAIL rows in 120 runs. L4 to L7 are new. P5 calls the embedding API and did not run.
- Unit suite: 650 passed.
- Native tests run by the assistant's subagents: 59 passed.
- `support/ledger_check.py`: PASS, `PINNED` unchanged at 9205 nodes and 9050 sequences, and the mutants run exited 0.
- GitHub Actions on `main` at `3207a72` (run 40327229829): the `unit` and `chains` jobs passed.

No user-reviewed root for this checkpoint exists yet.

**Known limits**, from the review of the fix round:

1. A first publication that fails at creation on the first source leaves the later sources never added, and no command adds them. On a two-source root the command then prints the single-source result shape.
2. A registered source whose `cognify` crashed before the ledger began is refused `not_published`, and no command recovers it. The hand-built path had the same gap.
3. The review also claimed that `status` on a reset two-source or glossary root raises `not_published`. The assistant checked it, and the claim is false: `status` prints an empty ledger.
4. S3a's known limits 2 to 4 stay open.

### Step 5 S4, the lab update, 2026-10-26

S4 is the third and last of the entry-point checkpoints. It adds the lab's `update` and moves every text edit onto it. The step-5 discussion of 2026-10-25 (unit 3) set its shape: Cognee rebuilds the whole document, and the identity revision stays incremental.

**What changes for users.**

- `edit-text`, `remove-occurrences`, `retire-resolved-group`, `add-occurrences`, `split-group`, `combine-groups`, `reinterpret-new-entity`, `reinterpret-unresolved`, `change-kind-to-mention`, `change-kind-to-reusable` and `edit-glossary` edit through `entry_update.update`. Their journeys in the other feature files pass unchanged.
- Cognee's standard Tasks (`classify_documents`, `extract_chunks_from_documents`, `add_data_points`) now write the edited original's chunks. The lab no longer writes them with a direct `add_data_points`.
- After an edit, `native-cognify` (a plain `cognee.cognify()`) still skips every Data item of the root.
- An edit of a source whose native copy is gone or changed outside the lab is refused `native_deleted` with the forget hint, as `reconcile` is. In the build, such an edit could stop on a misleading `chunk_policy` message instead.
- A failure at any replacement stage exits 1 with `recovery_event_id`, as before. The original stays stamped at every stage, `text_removed` included. `reconcile` finishes the saved text change through `entry_update.replace_text`.
- Every edit adds a `cognify_pipeline` run row to Cognee's run table. Cognee shows the run as completed even when the lab Task failed, so read `status` for the lab's outcome.

**The design.**

- `update(publisher, source, text, occurrence_map, *, describe_edit, expected_revision, semantics)` refuses a natively deleted source first, reads the registered text and the chunk budget the native chunks record, chunks the new text in memory once and calls `describe_edit` with an `EditDraft` (the current description, the registered text, the new text and its chunks). The occurrence map is a parameter of `update`, because it never depends on the new chunks. `describe_edit` is required, so the type signature enforces U-e and the run-time refusal `describer_missing` is gone.
- `update` and `replace_text` share a private `_replace`, which runs one lab Task, `identity_update`, under `cognify_pipeline` over the original, with no rollback handler, `incremental_loading=False` and `needs_llm=False`. The Task calls `publisher.replace` with the text change and the identity Data item's untagged context.
- Inside `TextChange.apply`, the per-item `cognee.forget(memory_only=True)` clears the original's stamp, and the lab stamps it again at once. Then `native_chunks.build_chunks` runs the standard Tasks nested, outside any run, with the lab's context. A rollback or a startup recovery of the update run therefore never finds the rebuilt chunks (the spec review's item C3).
- `native_chunks.py` holds the chunk builders: `WHOLE_DOCUMENT`, `chunk_text` (in memory), `standard_tasks` and `build_chunks`. `entry.cognify` and the text change share them, so `text_changes.py` no longer imports from `entry.py`.
- `entry.semantic_hooks` takes callables for the chunks and the original's context and reads them when a hook runs, because a text change rebuilds the chunks after the hooks are made. `entry_update.NoFacts` is the writer and verifier for a source with no captured facts (the glossary), since a text change always names both.
- `text_fixture.record_revision` writes an edit's revision and text files to the root, and `text_fixture.then_refresh` awaits an edit, then refreshes its dependents. `edit_one`, `maintain_one` and the glossary edit share it.
- Deleted: `text_fixture.rebuild`, the glossary's `run_tasks_base` edit path and `describer_missing`.

**Process.** An Opus subagent built S4 on branch `stage5-s4-update` from `7d43ec7` on the user's Mac on 2026-10-26 (`602cfb3` to `e07e435`). A `/pstack:thermos` review followed, and neither the bug review nor the quality review found anything blocking. The fix round (`236f08e` to `399ce94`) made these changes:

1. An edit refuses a natively deleted source with `native_deleted` and the forget hint, before it reads the chunk budget (`236f08e`). The bug review found the build stopping on `chunk_policy`.
2. The entry-point guide names the crash window between a text change's per-item forget and its stamp (`fc11445`). The bug review found it undocumented.
3. The chunk builders moved into `native_chunks.py` (`a7fb55d`), and the edit half of `entry.py` moved into `entry_update.py` (`d1bcadb`). The quality review found `entry.py` at 511 lines with two lifecycles and a layer inversion.
4. One `semantic_hooks` with callables replaced a copy, `NoFacts` replaced the glossary's empty hooks, the occurrence map became an `update` parameter, `record_revision` and `then_refresh` replaced duplicated code, an edit chunks the new text once, and `describe_edit` became required (`399ce94`).

The assistant's working notes, which are not committed, hold the build report and the two reviews.

**Evidence**, run on the user's Mac on 2026-10-26 with loopback embeddings:

- `verify.py journey all`, run by the assistant's subagent: 1953 PASS rows and 0 FAIL rows in 131 runs. L8 to L10 are new. The build report says that L9 fails without the stamp after the forget. P5 calls the embedding API and did not run.
- Unit suite: 650 passed. The fix round deleted the `describer_missing` test.
- Native tests run by the assistant's subagents: 56 passed.
- `support/ledger_check.py` and its mutants: PASS, `PINNED` unchanged at 9205 nodes and 9050 sequences.
- `support/chain_check.py` and its mutants: PASS. `erasure.py` changed, so the routine requires it.
- GitHub Actions on `main` at `399ce94` (run 40349867398) passed: `unit` gave 650 passed.

No user-reviewed root for this checkpoint exists yet. The [entry-point guide](stage6_identity_standard_entry_points.md#the-labs-update) has the commands and the expected values.

**Known limits**, from the reviews:

1. A hard kill between a text change's per-item forget and the stamp after it leaves the original without chunks and without a stamp, and the row `pending`. A plain `cognee.cognify` in that window extracts the previous text with the LLM. Resuming the text change forgets and stamps the original again. The guide names the window.
2. An edit after a native forget of the whole original stops with `source_missing` in the command's own `read_original` (for example `text_fixture.py`), before `update` reaches the `native_deleted` refusal. This predates S4.
3. `erasure.py` imports the fixture class `text_fixture.RebuiltSemantics` for the erasure retry of a text change. This predates S4 and goes to step 6.
4. A describer writes the revision files before `replace` checks `expected_revision`. The callers check the current revision first, as before S4.
5. S3a's known limits 2 to 4 and S3b's known limits 1 and 2 stay open.

### Step 5 S1, the public retriever, 2026-10-26

S1 is step 5's retrieval checkpoint (unit 1). It puts the lab's retriever behind Cognee's own `cognee.search` and adds a check that gates later retrieval changes. The user's decisions of 2026-10-25 set its frame: the semantic mode first, evidence with no LLM completion, identity-anchored facts by default, and a warning that the other search types do not check eligibility (U1 option (a)).

**What changes for users.**

- `cognee.search(query, query_type=SearchType.IDENTITY, datasets=[name])` returns one result equal to the CLI `retrieve` output: the identity-anchored facts with their checked evidence chunks, `unavailable_sources`, and the new fields `mode`, `scope` and `dataset_id`. No LLM runs. Cognee logs the query with the type `IDENTITY`. With `include_references=True` each fact is a `triplet` reference and each checked chunk a `segment` reference.
- The CLI has a new `search` command, with `--scope`, `--mode` and `--all-datasets`, and `retrieve` takes `--scope` and `--mode`. Both run `settled.retrieve_settled`.
- The ranking is unchanged from the first slice: name-match seeds, else the top vector hit, the closure over accepted links, one-hop facts with own-chunk evidence and a word-overlap score.
- Seeds come only from the searched dataset's served sources. Cognee's `Entity_name` collection holds the Entities of every dataset in the store, and probe E5 measured another dataset's Entity seeding a query and displacing the lab's seed, so the query returned no fact. Now only a reusable Entity that a served source of the searched dataset constructs can seed. The fallback to the top vector hit applies only when the first reusable candidate overall is such an Entity. When another dataset's Entity ranks first, the search has no seed and returns no fact. In the build the fallback walked down to the first allowed Entity, so `What does Aurora controller limit?` returned the lab's Helios facts (bug review M1). The CLI `retrieve` follows the same rule.
- A search reads the ledger at its start and again at its end. When a writer moved a served row between the two reads (`retrieval_changed`), or began on a source that the search was failing (`stale_attempt`), the search reads once more. A second change fails the search. The CLI `retrieve` does the same.
- A refused search raises `SearchRefused`, an `IntentError` with a code, in the retriever's constructor. That is before the retriever reads a lab store and before Cognee logs the query, so a refused search writes no history row. It is not a Cognee `NoDataError`, so it fails the whole search instead of becoming one dataset's empty entry. The codes are `dataset_required` (Cognee gave the retriever no dataset, which with access control off happens whenever the search covers more than one dataset), `access_control_on`, `scope_not_built` (`identity_and_unattributed`), `mode_not_built` (`source_aware`) and `config_invalid`. The CLI prints the code and exits 1.
- Cognee's other search types read the graph, the chunk index and the triplet index as they stand, so they serve withheld decisions, a failed publication's new text and the mention labels. The [search guide](stage6_identity_public_search.md#warning-the-other-search-types-serve-withheld-and-failed-state) opens with this warning and probe E2's counts, and journey S7 shows a plain `CHUNKS` search serving a failed source's text.

**The guarded `IDENTITY` member.** Cognee 1.6.2's `SearchType` is a closed enum, and Cognee turns a search type into an enum member before it finds the retriever. Probe E1 showed that a member added through Python 3.12's enum internals works for lookups, iteration, pickling, search history and `recall(query_type=...)`. Importing `cognee_lab.identity.search` runs `register()`, which:

- refuses with `RegistrationError` unless Cognee is 1.6.2 and Python is 3.12, because nothing in Cognee's range `cognee>=1.6,<1.7` pins the internals that it writes;
- refuses when `SearchType` already has an `IDENTITY` member that the lab did not add, because Cognee replaces the retriever of an existing member without a warning;
- self-tests at import the lookups by name, value and attribute, iteration, pickling, a `SearchResultPayload` with the member and the registry entry, and removes the member and the registry entry when a check fails;
- changes nothing on a second import, and after `importlib.reload` keeps the member and registers the reloaded class.

The member has limits, which probe E1 measured and the guide lists. `IDENTITY` exists only in a process that imported the lab. A pydantic model built before that import rejects it in JSON validation: Cognee's HTTP DTOs, unless the router is imported after the lab, and `SearchResultPayload.model_validate_json`. A fresh `cognee search` CLI process raises `KeyError`. Cognee's `FEELING_LUCKY` prompt does not name the member, and the router of `cognee.recall` never picks it. HTTP routes stay out of scope (U-f).

**The conformance check.** `conformance-fixture` builds DOC01 (`data/DOC01_helios1_technical_overview_v2.md`) through the lab's `add` and `cognify`. Its describer reads only DOC01's text and native chunks. It has four name rules, a hand-read table of 11 reference groups and a sentence rule for facts, and gives 23 reusable Entities, 12 variant assignments, 11 groups, 29 facts and 10 chunks. `support/conformance_check.py` searches the root through `cognee.search` with `IDENTITY`. It scores fact recall, closure symmetry, mention cases, negative controls and query resolution against the Stage 5.3 traversal and query-resolution benchmarks and the Helios manifest in `data/hidden`. It is the only reader of `data/hidden`, and a unit test fails when a module under `src/` names it. `support/conformance_baseline.json` holds each case's outcome and, for each case that does not pass, its gap. The check exits 1 when a case moves from the baseline in either direction, when a case appears or disappears, and when a gated count grows. Journey B1 runs it.

It is a conformance check, not a benchmark. The describer's rules and its table were written after their author had read the hidden answers. The check therefore measures whether the search serves a fixed description the way the benchmarks expect, and it says nothing about Describe or extraction quality. The spec review (R3) found that the first plan, to author the fixture's captured facts from the hidden manifest, would have put the answers in the description, against the roadmap's rule that hidden answers stay out of Describe inputs. A true benchmark needs a describer that never saw the answers (step 6) or an outside benchmark.

**Baseline**, measured by the assistant's subagents on the user's Mac with loopback embeddings, 54 searches in about 15 s with the fixture. The three AFRL resolution cases were added in fix round 2, and the other cases did not move:

| Measure | Passed | Failed | Unobserved |
|---|---:|---:|---:|
| `fact_recall` | 10 | 8 | 0 |
| `closure_symmetry` | 5 | 0 | 1 |
| `mentions` | 9 | 0 | 2 |
| `negative_controls` | 6 | 1 | 1 |
| `query_resolution` | 7 | 0 | 0 |

Repeated edge IDs, attribution violations and leakage violations are 0. Logical duplicates, the same fact through two members of one identity group, are 7, and the check reports them without gating. The cases that do not pass, each with its gap in the baseline:

- Recall F008 and F011 to F016 fail because the describer writes no fact for them: a lowercase common noun that no name rule makes an Entity, a sentence that names only one identity group, or a table row that names no Entity. F010 fails because DOC01 never states the manifest's words.
- QRY05 fails. With no name match the search seeds the top `Entity_name` vector hit, so the ambiguous query resolves to an arbitrary group (`RCM` under loopback embeddings).
- Closure TRV05 is unobserved, because no fact has an AFRL-group subject. TRV08 and its negative control are unobserved, because their chunk coordinates follow DOC01 v1's Stage-5 chunking; the manifest's ER005 hard negative stands in for them. ER001 is unobserved, because its group has no fact.
- QRY03 and QRY04 are an accepted gap (the user's decision of 2026-10-26). They pass when they resolve no wrong group. QRY04 passes only because it holds the full name `edge density controller`, and QRY03 resolves nothing.

Some passes prove little. F009 passes on a sentence that holds the object inside a negation, and the mention passes come from the hand-read table, not from any resolution. The [conformance guide](stage6_conformance_check.md#the-baseline) lists them.

**Process.**

1. An Opus subagent drafted the spec read-only against `main` at `399ce94` on 2026-10-26. An independent Opus reviewer returned "proceed with changes" (R1 to R8): guard the enum extension (R1), keep the hidden answers out of the describer and call the result a conformance check unless the describer is independent (R3), retry on `stale_attempt` too (R5), and raise refusals before the history row (R6). The user then decided the open questions (below).
2. An Opus subagent ran the probes E1, E2 and E5 on the user's Mac with loopback embeddings, on branch `stage5-s1-probes` at `21a74e7`, and measured the lab stores unchanged. The assistant spot-checked the summary. From E5 the assistant decided, reversibly, that seeds come only from the searched dataset's served sources, and told the user.
3. An Opus subagent built the core, the retriever, the CLI `search` and the refusals on branch `stage5-s1` (`62ef936` to `f82b1aa`).
4. `/pstack:thermos` reviewed the build. The quality review was close but not approved: the one-shot probe script should not land, and the scope and mode contract was spread over five places. The bug review found M1, the fallback that served the lab's facts for another dataset's Entity, and L1 to L4. Fix round 1 (`f4b2278` to `b904df3`) dropped the probe script and cited it at its tag (`f4b2278`), parsed scope and mode once into `SearchRequest` in `settled.py` (`357e3de`), limited the fallback to the first reusable candidate overall (`7cf4573`, M1), made `register()` safe across a reload and undid a failed self-test (`c2b3318`, L1), imported `search` in a test fixture so a refused registration fails only its own tests (`e1d7724`, L3), and tested the `stale_attempt` retry through a real `RecordStore` (`b904df3`, L4). For L2 the guide now says that every search runs `RecordStore.initialize`, since the retriever keeps no per-process cache.
5. An Opus subagent built the conformance check: the fixture (`bfe7c49`), the check and its baseline (`ae43de8`), and journey B1 with the `CLAUDE.md` routine step (`64bad48`). Per-fact writes hit Ladybug's `max_db_size` of 1 GiB, so `fixture.write_chunk_facts` now writes a batch with one write per kind.
6. A second `/pstack:thermos` reviewed `f82b1aa..64bad48`. The bug review found nothing critical, high or medium and reproduced the baseline exactly. The quality review was close. Fix round 2 (`88d8505` to `cdbb6bf`) held the `SearchRequest` invariant in the dataclass (`88d8505`), shared the Cognee version, the store closing and the member restore (`33556cf`), kept one `identity_groups` for the fixture and the check (`0a89db5`), moved the check to its own guide (`a1c97e6`), made the baseline the only record of gaps and the check the owner of the ratchet (`d3e5b6c`), required the subject in recall and added the three AFRL resolution cases so the AFRL controls cannot pass on an empty search (`b84e9be`), declared `pyyaml` in the dev group (`821d572`), and shared one root between the two native conformance tests (`4e80252`). `native-search` keeps `DATASET_NAME`, with the reason in the code.

The assistant's working notes, which are not committed, hold the spec, the probe summary, the reports and the four reviews.

**The user's decisions of 2026-10-26**, after the spec review:

1. The retrieval entry for unit 1 is the guarded enum extension (R1). If probe E1 had failed, a lab search entry outside `cognee.search` was the fallback. E1 passed.
2. A search over several datasets is refused `dataset_required` unless it covers exactly one lab dataset.
3. The Stage 5.3 benchmark moves into S1, ahead of unit 6. Only `support/conformance_check.py` reads `data/hidden`, and a test checks that no `src/` module does (R3).
4. QRY03 and QRY04 are an accepted gap, gated only on resolving no wrong group.
5. The proposed defaults are accepted: the check runs as journey B1 and a local command, not in CI; the corpus is DOC01 only; the scope values are `identity` and `identity_and_unattributed`, and the mode value is `semantic`; the CLI `retrieve` retries once on `retrieval_changed` and `stale_attempt`; the outside-benchmark prototype follows S1.
6. The user confirmed the assistant's overnight decisions: the six S3a decisions and the broader S2 citer refusal (see [Next task](#next-task-and-the-overnight-decisions-as-of-2026-10-26)).
7. The search keeps the first slice's ranking. Seeding and ranking improvements are later work, measured against the S1 conformance baseline.

**Evidence**, run by the assistant's subagents on the user's Mac with loopback embeddings:

- `verify.py journey all` on `cdbb6bf` (2026-10-26): 2022 PASS rows and 0 FAIL rows in 140 runs. S1 to S7 and B1 are new. P5 calls the embedding API and did not run.
- Unit suite on `cdbb6bf`: 699 passed.
- Integration suite on `64bad48`: 120 passed. Fix round 2 changed the search and conformance code after that run, and the 5 native search and conformance tests passed on `cdbb6bf`.
- `support/ledger_check.py` and its mutants: PASS, with `PINNED` unchanged at 9205 nodes and 9050 sequences. `retrieve.py` reads the ledger, so the routine requires it.
- `support/conformance_check.py` on `cdbb6bf`: exit 0, with no case moved from the baseline in either direction. The gate can fail: a scratch break that turned off variant expansion in `retrieve.py` failed seven cases (five closures, F009 and T003), and in fix round 2 a scratch break that kept the two AFRL names from seeding failed the two AFRL resolution cases and closure TRV05.
- `uv lock --check` passed after `pyyaml` joined the dev group (checked by the assistant).
- The probes ran on `21a74e7` (2026-10-26), with every LLM call refused unless the probe stubbed it. The lab stores were unchanged.

GitHub Actions run 40447014386 on `main` at `747a4f0` passed on 2026-10-27: 699 unit tests, the occurrence check and the chain check. No user-reviewed root for this checkpoint exists yet. The [IDENTITY search guide](stage6_identity_public_search.md#commands) and the [conformance guide](stage6_conformance_check.md#the-gate) have the commands and the expected values.

**Known limits**, from the probes and the reviews:

1. A text edit renames the original's Data row and document node from its file name (for example `glossary`) to `text_<md5 of the text>`, because `registered.write_text` ingests a string. This has held since the text changes of 2026-10-19 (`81027ca`, `08d9e98`) and predates S4. The `IDENTITY` result never uses document names, but native search contexts show the new name, and the source-aware mode needs the real one. The fix is to ingest a named file path. Closed on 2026-10-27, see [the next section](#step-5-document-names-kept-after-a-text-edit-2026-10-27).
2. Seed crowding. The search takes the top 10 `Entity_name` hits and then drops every Entity that no served source constructs. A store with many Entities in other datasets can push every lab Entity out of the top 10, and the query then returns no fact. This is inferred from the code, not measured.
3. Cognee's other search types serve withheld and failed state. S1 only warns (U1 option (a)), with probe E2's counts and journey S7. A guard for them (U1 option (b)) needs a decision.
4. The coordinates of TRV08 and its negative control follow DOC01 v1's chunking, so both stay unobserved. The manifest's ER005 hard negative stands in for them.
5. QRY05 fails on the fallback seed, the top `Entity_name` vector hit.
6. The conformance check is not a benchmark. A true benchmark needs a describer that never saw the answers (step 6) or an outside benchmark.
7. Every search runs `RecordStore.initialize` through `Publisher.configured`, which checks the lab's tables and fills the removal record from the tombstones. The retriever keeps no per-process cache, since tests and the CLI switch roots within one process.
8. Access control is refused (`access_control_on`), because the lab's ledger lives in the one shared relational database.

### Step 5, document names kept after a text edit, 2026-10-27

This is the first part of the source-aware mode. It closes S1 known limit 1. Branch `source-aware-doc-name`, commits `0c8f0ca`, `1c9790d` and `37da230`.

**Decision.** `registered.write_text` ingests the new text as an upload object whose file name is the Data row's own name and extension, instead of as a plain string. Cognee names a plain string `text_<md5>`, and its update branch writes `Data.name` on every ingest, so every text edit and every identity-snapshot rewrite renamed the Data row and the TextDocument node. Cognee's upload route stores the bytes at `<data root>/<md5>/<name>.<ext>` and keeps the name. The user asked for the work on 2026-10-27 and left the design to the assistant. The assistant chose it after a prototype on a loopback root showed the old and the new names.

**What the reviews changed.** Two independent reviews and two re-reviews ran over the branch.

- An upload's file name makes Cognee write a `_cognee.source_uri` that points at a file under the process's working directory, which does not exist. `write_text` now writes an explicit `source_uri` of `None`, which Cognee keeps. On `main` the key was removed. Both first-round reviewers found this.
- The upload route stores the original and the derived text as two files. Cognee removes the replaced original but not the replaced derived text, so each changed rewrite left the previous revision's text on disk, and `forget` could not see it. `write_text` now removes the previous derived text once no Data row references it. This also removes the one file per item that `main` left after the first rewrite. In the scenario `multi-fixture`, `revise`, `edit-text`, `forget --source doc01`, the bug reviewer counted 2 unreferenced files on `main` and 3 on the first commit. The final branch leaves 0.
- Carrying the name on the stream instead of on the file name dropped the stored file's suffix, so Cognee chose the loader from the content. The final commit uses the file name again.

**Evidence.** The assistant's subagents ran these on the user's Mac with loopback embeddings, on `37da230`:

- `uv run pytest -q -m 'not integration'`: 699 passed.
- `uv run pytest -q -m integration`: 120 passed, in 41 minutes.
- Journeys R1, R2, E1 to E4 and F1 to F20: 0 FAIL in each.
- `test_native_text_edit_replaces_chunks_evidence_and_reconciles` now checks the names by Data ID before and after the edit, the absent source URI, the stored original's suffix and that no stored file is unreferenced. The assistant's subagents showed that each check fails without its fix.

No GitHub Actions run and no `journey all` run, because this is not a checkpoint close. The source-aware mode is.

**Known limits.**

1. A crash after Cognee commits the new text and before `write_text` removes the previous derived text leaves that file. A retry reads the new location and cannot find the old one. Cognee leaves the same window for the originals it replaces.
2. A root built before this change keeps the `text_<md5>` names of its earlier edits.
3. The first add of an item still stores the caller's file as the original. Nothing changed there.

### Step 5, the source-aware mode, 2026-10-27

This is a checkpoint. Branch `source-aware-mode`, rebased onto the integration-speed commits `5af8c19` and `b3427c2`.

**Decisions.** On 2026-10-27 the assistant proposed the result shape with five questions, and the user decided them the same day:

1. The link from a fact to its document is a result field. Nothing new is written to the graph. A fact-to-document graph write, so that readers outside the lab see it, stays possible later work.
2. The flat `facts` list stays, and a `documents` list is added beside it.
3. The source-aware mode lists a fact under every document that supports it. The semantic mode keeps the evidence of the first source only, so the conformance baseline does not move.
4. Evidence chunk ranges are the finest span of a fact without a mention.
5. "Grouped delivery" is renamed grouped-by-identity delivery. It stays open, to be built as a second side list over the same flat `facts`.

**What was built.** `retrieve` collects each fact once, with one support per served original document, and returns the facts it found. `retrieve_settled` delivers them through the mode's entry in `settled.DELIVERY`. The pure functions are in `delivery.py`. `semantic` gives the old result. `source_aware` gives the evidence union with chunk ranges, and the `documents` list with each document's Data ID, name and spans. It reads Data names once, only for the returned documents. The seven other callers of `retrieve` call `semantic` themselves. The Data-name reader moved from `dataset_forget.py` to `native_copy.py`. Journey S8 drives the mode. Guide: [source-aware results](stage6_identity_public_search.md#source-aware-results).

**Process.** An Opus delegate built the mode and an Opus delegate ran the fix round, each in its own worktree. Two independent reviews ran on the first build and one on the fix round. None found a blocking defect. The fix round moved the name reader, lifted the mode choice out of `retrieve`, typed the records, added mention facts' chunk spans and added a store-free test that drives `retrieve` with two sources supporting one fact. The assistant dismissed three review items with reasons. A document is placed by its best fact's rank, which is deterministic and matches the guide. Two sources sharing one original cannot happen with today's builders, so a docstring notes it. Filling Cognee's `document_name` reference field is deferred.

**Evidence.** The assistant and its subagents ran these on the user's Mac with loopback embeddings on 2026-10-27:

- The semantic `retrieve_settled` output stayed byte-identical over 240 reads on 12 roots, before and after the fix round. The fixture commands' result files matched in structure.
- `uv run pytest -q -m 'not integration'`: 707 passed.
- `uv run python support/conformance_check.py`: 0 regressions and 0 improvements.
- `verify.py journey all`: 2032 PASS rows and 0 FAIL rows in 141 runs, with P5 skipped.
- `uv run pytest -q -m integration -n 8 --dist worksteal`: 121 passed in 551 s and in 531 s. In an earlier run, 1 test failed and 120 passed in 599 s. The failing test passed when rerun alone, and its name was not captured. Two more runs gave 121 passed in 546 s and in 548 s. So 4 of 5 parallel runs on this branch passed, and the integration-speed delegate's 9 runs had no failure. The failure is a tracked follow-up.

GitHub Actions run 40573037239 on `main` at `e804b35` passed on 2026-10-27: the `unit` job (707 unit tests and the occurrence check) and the `chains` job.

**Known limits.** The search guide lists five. The main ones are these. A fact's flat `identity` comes from its first support. `name` can be null if Cognee deletes the Data row outside the lab during the read. No fixture has a fact that two documents support, so a store-free test covers that case.

### Integration suite on 8 workers, 2026-10-27

The user asked why the integration suite had grown to about 46 minutes. Its per-test time had held at 21 to 24 s since 29 tests, and the suite now has 120 to 121. An Opus delegate measured where the time goes and tried three changes, cheapest first. Commits `5af8c19` and `b3427c2`.

- **Baseline.** One serial run took 2755 s. 96% of the time was in 610 CLI subprocesses. The CLI time split as 38% `import cognee`, 45% the operation, 14% interpreter exit and start, and 4% Python and lab imports. The fixture-building commands took 27% of the total.
- **pytest-xdist, adopted.** `-n 8 --dist worksteal` ran the suite in 546 s and 599 s, with 120 passed each time. On a 34-test subset in three interleaved rounds, worksteal at 8 workers was fastest in each round, with a median of 182 s. The medians were 262 s for 4 workers, 221 s for 6 and 220 s for 8. CPU on the 4 performance and 6 efficiency cores limits the result. Outside load from other agents moved full runs between 531 and 665 s.
- **A copied template root, rejected.** A copied root still reads its template's files. Its relational, graph and vector stores hold the template's absolute paths.
- **Cheaper CLI start, rejected.** The import cost is inside Cognee's own `__init__`. Cutting it would mean patching Cognee or not driving the real CLI.

CI still runs the unit command without `-n`. The review found two more items, both fixed. The lock file's revision had dropped to 3 and is back at 5, as commit `821d572` set. And `support/host_native_launcher.py` must run without `-n`, because its patch does not reach xdist workers. The measurement files are in the main checkout's untracked `outputs/integration_speed_20261027/`.

## Next task and the overnight decisions, as of 2026-10-26

Step 5 continues with the source-aware mode and the delivery items. The user decided on 2026-10-25 to build the semantic mode first and the source-aware mode next, and on 2026-10-26 that seeding and ranking improvements are later work, measured against the S1 conformance baseline.

1. **The source-aware mode.** `mode` `source_aware` is refused `mode_not_built` today. It adds a document node per fact, grouping by source and occurrence spans. It needs the real document names first: fix the `text_<md5>` rename ([S1 known limit 1](#step-5-s1-the-public-retriever-2026-10-26)) by ingesting a named file path in `registered.write_text`.
2. **The step-5 delivery items.** Grouped delivery, annotation states, span-scoped variants, ranking and seeding changes measured against the conformance baseline (QRY05 and seed crowding are the known cases), offline diagnostics that share the traversal's predicates, and admission of the consumed stores that enabled native paths read (lesson G14).
3. **Rebuild endpoint gaps.** Step 4 sent the endpoint gaps during a generated-source rebuild to step 5. Check whether S3a to S4 closed them, and record the answer.
4. **The outside-benchmark prototype.** The user approved it for after S1 on 2026-10-26. It is the route to the benchmark that the conformance check is not.

The scope value `identity_and_unattributed` (U3) stays refused `scope_not_built` until a spec builds it.

**The overnight decisions, confirmed.** The assistant made decisions 1 to 6 on 2026-10-26 while the user was away, and S3a is built on them. Decision 7 is from the third bug review of S2 part 2. The user confirmed all seven later on 2026-10-26, with the S1 spec decisions:

1. No rollback handler under `cognify_pipeline`. The lab keeps Cognee's pipeline name but passes no `rollback_handler`, so Cognee's inline rollback never touches lab state, and Cognee's startup recovery keeps stamped items. An errored run leaves its chunks and its stamp.
2. The stamp right after native chunking. The lab Task stamps the original before it publishes, whatever the outcome. A plain `cognee.cognify` in the short window before chunking can still extract the original. The lab's own files (`identity.json` and the seed) are stamped at `add`.
3. The native LLM extractor waits for step 6, with the other model-quality work (U-b).
4. The lab `cognify` handles lab sources only. Plain documents stay with `cognee.cognify` (U-c).
5. A lab `update` with no describer is refused (U-e). Since the S4 fix round `describe_edit` is a required argument, so the signature enforces it.
6. HTTP routes are out of scope (U-f).
7. The S2 re-add refusal of live citers stays broader than the S2 spec's wording: another source's failed or pending replacement that retired the Entity, or a forget with waiting dependents, also refuses a re-add.

The earlier default U-d, to accept Cognee's rollback of native chunks and chunk again on `reconcile`, is moot since the fix round. With no rollback handler nothing rolls the chunks back. `reconcile` of a failed first publication still chunks the original again.

## Tracked follow-ups as of 2026-10-26

On 2026-10-25 the user decided that each item below stays a documented limit. None blocks step 5. Branch `stage6-cleanups` closed and removed these items: the `remains()` guard, the fixed `text_review` producer, the `refresh-dependents` re-raise, the erasure-retry plan merge, the unused `ChunkInput` import, the cascade check's end-to-end property, B8, the re-confirm's writes outside `records.py`, and the duplicate reader filter and docstrings.

Open since 2026-10-25:

- `review.replaced_variant` still writes `variant_assignments` directly, outside `records.py`. The cleanups' guard test covers only `mention_resolutions` and `mention_groups`.
- Closed by step 5 S2 on 2026-10-25: an outside deletion of an Entity that two withheld decisions cite deadlocked their review (`missing_reasoning_input`). Journey D17 now answers them one at a time.

Open since step 5 S2 (2026-10-26) are the four known follow-ups listed under [Step 5 S2](#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26).

Open since step 5 S3a (2026-10-26) are the four known limits listed under [Step 5 S3a](#step-5-s3a-the-lab-entry-points-2026-10-26). S3b closed the first for new roots.

Open since step 5 S3b (2026-10-26) are known limits 1 and 2 listed under [Step 5 S3b](#step-5-s3b-every-builder-on-the-entry-points-2026-10-26): later sources never added after a failure on the first source, and no recovery for a registered source whose `cognify` crashed before the ledger began.

Open since step 5 S4 (2026-10-26) are known limits 1 to 4 listed under [Step 5 S4](#step-5-s4-the-lab-update-2026-10-26): the crash window between a text change's forget and its stamp, the `source_missing` stop before the `native_deleted` refusal after a native forget of the whole original, `erasure.py` importing `text_fixture.RebuiltSemantics` (step 6), and revision files written before the `expected_revision` check.

Open since step 5 S1 (2026-10-26) are known limits 1 to 8 listed under [Step 5 S1](#step-5-s1-the-public-retriever-2026-10-26): the `text_<md5>` document name after a text edit, seed crowding, Cognee's other search types serving withheld and failed state, the TRV08 coordinates, QRY05 on the fallback seed, the conformance check that is not a benchmark, `RecordStore.initialize` on every search, and the refusal under access control.

Documented limits from earlier checkpoints:

- The replace `source_missing` guard in `RecordStore.begin` is not covered by the ledger model, which sends no replace for a missing row.
- `describe_readd` assigns naming keys to removed Entities greedily, so it can refuse a re-add for which a valid assignment exists (a refusal, never a merge; no fixture reaches it). A bipartite matching would fix it.
- `check_readd_entity_ids` accepts `replaces:<uuid>` for any removed UUID, not only the Entity's own. The results are still fresh and probed, so this is looser than the guide's wording, not unsafe.
- The oracle's worlds do not cover more than one addition or reordering. A unit test pins reordering, and the captured addition fixture's general map pins two additions. Widen the bound if a later rule depends on either.

Added by Checkpoint H on 2026-10-23, from its final review and the dependencies guide's "Not in this checkpoint":

- Attestation is per producer, not per decision. A renamed or new decision may name a sibling's re-confirm producer and cite the key that producer attested, so one decision's re-confirm can cover another decision's interpretation. The record stays true about which content was seen. A per-decision attestation would close it.
- A producer's identity is its key, not its content. A revision may rewrite an old producer's configuration without changing a decision. The attestation rule still constrains it and nothing is released, but recorded provenance is not immutable.
- `classify` finds a moved span by hashing every window of the new text with the span's length: O(n·len) for a text of n code points. That is fine for a glossary. A long consumed document with many spans needs a substring search first, confirmed by digest.
- A chunk of another document has no refusal rule and always needs review; no fixture has one. Moves across documents and span-scoped variant ranges count as a change, not a remap.

Added by Checkpoint I on 2026-10-23, from its final review:

- The registered snapshot of an erasure retry is written before `begin`. It is harmless and converges on rerun.
- A dependent whose text change finishes through the erasure retry leaves its own dependents' moved ranges for `refresh-dependents`.
- Journey F9 edits root files with `python3` lines inside the journey.
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
- L1: a retry is refused when the bound set for the same document grew after admission and its old revision reads the new record. It predates the fix rounds (first commit `3ebd8bb`).
- The retire refusal is stricter than needed in one shape: a blocked dependent that cites both an intermediate and the forgotten source. The user can withdraw the dependent.
- A re-add's never-served revision lists a served revision from the earlier life. It is harmless and documented in `RemovedRecord.of`.

Added by Checkpoint K on 2026-10-24, from its reviews:

- A review drop, like an erasure, removes a recipe that only the dropped variant named. A source that cites that variant as a saved record is withheld by its changed citation, not by the missing recipe.


## Counts and timings recorded in the handoff until 2026-10-26

These paragraphs come from the handoff's resume commands and its verification section.

On branch `stage5-s1` at `cdbb6bf` (2026-10-26, step 5 S1) the unit suite gives 699 passed. On `main` at `399ce94` (2026-10-26, step 5 S4) it gave 650 passed. On `main` at `3207a72` (2026-10-26, step 5 S3b) it gave 650 passed. On `main` at `3da0d7f` (2026-10-26, step 5 S3a) it gave 646 passed. On `main` at `c711997` (2026-10-26, step 5 S2) it gave 641 passed and 108 deselected. On branch `stage6-entity-edits` at `514c0bb` (2026-10-24) it gave 560 passed and 86 deselected. On branch `stage6-cascade` at `74ec093` (2026-10-24) it gave 533 passed and 86 deselected. On branch `stage6-chains` at `2002a77` (2026-10-23) it gave 487 passed and 85 deselected. On branch `stage6-erasure` at `d6133c7` (2026-10-23) it gave 448 passed and 81 deselected. On branch `stage6-dependencies` at `12c8d30` (2026-10-23) the unit suite gives 405 passed and 67 deselected. On `main` at `5603310` (2026-10-22) it gave 269 passed and 36 deselected. On branch `stage6-group-combine` (2026-10-21) it gave 207 passed and 34 deselected. On `c3becf2` it gave 143 passed and 29 deselected. The inspected native version must be **1.6.2**. If the version differs, inspect compatibility again. Do not identify another version as the tested profile. Run focused native tests for the changed path first. The full native suite is `uv run pytest -q -m integration`. It creates fresh stores and can take minutes.

**Verify journeys.** The journeys drive the CLI through real Cognee stores in fresh roots under `outputs/verify/`. The map in `.claude/skills/verify/features/` has 102 journey blocks since step 5 S1 (2026-10-26), which added S1 to S7 and B1. Step 5 S4 added L8 to L10, step 5 S3b added L4 to L7, step 5 S3a added L1 to L3, and step 5 S2 added D17 and F22 to F28. `journey all` runs the 101 loopback blocks as 140 runs. Journey P5 calls the NVIDIA embedding API in `.env`, so it runs only with `--include-env`. Journeys use `--embedding loopback` unless a block asks for `env`. `.claude/skills/verify/SKILL.md` gives the helper commands and proof rules. [Verification skill](#verification-skill) lists each `journey all` run.

An earlier full run on 2026-10-21 took about 2 hours. The step timings suggest that macOS idle throttling caused most of it. Every step took a flat 40 s or so until `caffeinate` started, and about 4 s after. This is an inference from the timings, not a proven cause. A warm step costs about 3.6 to 6.7 s, and about 2.4 s of that is imports. An unthrottled full run is estimated at about 11 minutes.

`verify.py journey` now runs 4 journey runs at once by default (`--jobs N`; 1 with `--include-env`) and starts `caffeinate -i` on macOS. On 2026-10-21 the assistant measured `journey all` on the user's 10-core Mac, before the regrouping journeys, with 30 runs and 586 PASS rows each time: 839 s with 1 job, 250 s with 4 and 180 s with 8, with no failure that appeared only in parallel. After the regrouping journeys landed, the same 34-run set gave 695 PASS rows and 0 FAIL rows in 281 s with 4 jobs, against 917 s serially. A worker error becomes a FAIL row and Ctrl-C cancels queued runs. If a `lab_store` check fails under parallel runs, rerun with `--jobs 1` to find the journey.

**Identity-ledger check.** It runs every sequence of real `RecordStore` calls up to a depth bound, with two sources and two writers. It checks properties P1 to P6 after each step. The default depth is 5. Since the regrouping plan joined the model on 2026-10-21, depth 5 gives 3828 nodes and 3717 sequences in about 6.7 s. Before that it gave 3062 nodes. `PINNED` in `tests/test_identity_ledger_check.py` holds the current counts: 9205 nodes and 9050 sequences since Checkpoint J2 fix round 3 (8504 and 8349 from Checkpoint I), in about 15 s. Depths 6 to 8 are manual runs. `--skip-probability P --seed S` samples a deeper search, and a sampled run never reports `verified within bound`. At depth 5 the check catches all 30 scratch breaks in `support/ledger_mutants.py`: 29 as a property failure and one as `INCONCLUSIVE`. The unit suite runs each break. One more break, in `DEEP_MUTANTS`, needs depth 7. The check found no bug in the current code. The user chose a Python checker over TLA+. `.claude/skills/identity-ledger/SKILL.md` says when to run it, and `reference.md` holds the measurements.
