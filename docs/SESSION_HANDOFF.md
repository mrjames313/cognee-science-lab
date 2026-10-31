# Session handoff

**Updated:** 2026-10-29 (America/Detroit).

The project is in Stage 6, implementation step 5 / M4. Step 4 / M3 closed on 2026-10-25. Step 5's checkpoints S2, S3a, S3b, S4 and S1 merged into `main` on 2026-10-26, and GitHub Actions passed on the S1 docs commit `747a4f0` on 2026-10-27. On 2026-10-27 a text edit stopped renaming the original's document, and the source-aware mode was built and merged. GitHub Actions passed on `e804b35` ([the history](stage6_checkpoint_history.md#step-5-the-source-aware-mode-2026-10-27)). The record of that pass, `fdda56e`, was pushed on 2026-10-29, and GitHub Actions passed on it (run 40923453227, `unit` and `chains`).

**Next task.** Build the other step-5 delivery items, starting with grouped-by-identity delivery. [Next task](#next-task) has the detail.

**Paused on 2026-10-29.** The user paused step 5 for a short detour after the source-aware checkpoint. Nothing is in flight. `main` is pushed, no other branch or worktree exists, and grouped-by-identity delivery has no spec or code yet. To resume, run [the resume commands](#resume-and-verification-commands), then start [Next task](#next-task) item 1 with a proposal for the user. The assistant's local notes in `.audit/` are not committed. `.audit/step5-source-aware-spec.md` holds the source-aware proposal and the user's decisions, which this document and [the history](stage6_checkpoint_history.md#step-5-the-source-aware-mode-2026-10-27) also record.

**The detour, 2026-10-29.** The user asked for a stand-alone design of a minimal identity resolution framework on Cognee, for a fresh build in another project. It is [minimal_identity_framework.md](minimal_identity_framework.md). It inventories this project's identity decisions, measures what each function costs and how costs compound, and proposes ledger-only identity with query-time expansion (about 750 to 1,150 lines, estimate), with Shape 1v's read-time view for graph-completion search and an anchor-owned graph overlay as the upgrade. Its section 10 records the user's answers of 2026-10-31 and the one question still open (the spelling hint). On 2026-10-31 the assistant ran its alignment experiment with real extraction (Claude Haiku 5.5, 80 LLM calls), recorded in [the alignment experiment](../results/minimal_identity_alignment_experiment.md). `pyproject.toml` now asks for `cognee[anthropic]`, and `support/secret_guard.py` runs as the local pre-commit hook. The assistant drafted it with subagents on the user's Mac and it went through five review rounds. No code under `src/` changed. `scripts/purpose_census.py` now labels the step-5 search modules. Step 5 resumes from [Next task](#next-task) when the user says so.

The dated history of every checkpoint is in [the Stage 6 checkpoint history](stage6_checkpoint_history.md). This document says what is true now.

## Objective and reading order

The project develops a method to integrate structured knowledge into Cognee. The method has four operations: **Describe, Publish, Maintain and Retrieve**. Identity is the first worked example. Use the demonstrated mechanisms and tests when you examine other domains, among them scientific measurements. Keep each domain's meaning and rules explicit. This implementation gives no scientific justification and no scientific reasoning.

Read this document first, then:

1. [ROADMAP.md](../ROADMAP.md) for the project stages and the current scope.
2. [The Stage-6 architecture and contract](../results/cognee_identity_stage6_handoff.md) for the physical representation, ownership, continuity, recovery and the original six-step build order. Its dated subsections are history. Its step-5 list in §11 predates the user's step-5 decisions of 2026-10-25.
3. [The R1 to R6 requirements](../results/cognee_stage5_4_5_requirements_review.md). They are outcome constraints, not a claim of complete coverage.
4. The guides for the current work. For S1, the [IDENTITY search guide](stage6_identity_public_search.md) and the [conformance check guide](stage6_conformance_check.md). For S3a, S3b and S4, the [entry-point guide](stage6_identity_standard_entry_points.md). For S2, the forget guide from [deletes outside the lab](stage6_identity_forget.md#deletes-outside-the-lab) on. For step 4, the [entity edits guide](stage6_identity_entity_edits.md), the [cascade](stage6_identity_forget.md#the-cascade) and the [chains guide](stage6_identity_chains.md). [Completed functionality and evidence](stage6_checkpoint_history.md#completed-functionality-and-evidence) links the guide of every earlier checkpoint.
5. [The integration playbook](../results/cognee_knowledge_integration_playbook.md) for findings tagged Describe, Publish, Maintain or Retrieve, and the transfer questions for other integrations.

The [representation decision record](../results/cognee_stage5_4_5_identity_representation_proposal.md) and the [pinned native extension reference](../results/cognee_extension_architecture_reference_v1.6.2.md) explain the rationale and the native behavior. Their early dated "next" and "not implemented" statements are not current status. This handoff and the roadmap give the current status, and a later approved scope change overrides an earlier proposal.

## Current state

Runtime code is in `src/cognee_lab/identity/`, against Cognee 1.6.2 and Python 3.12. "Implemented" means a bounded, deterministic fixture through the real configured stores (Ladybug, LanceDB and SQLite). Identity and semantic judgments are captured fixture input, and nobody has evaluated their quality. The last user-reviewed fixture roots are from the 2026-10-20 addition checkpoint, and on 2026-10-25 the user ran two real-embedding journeys for the step-4 close. The assistant and its subagents verified every later checkpoint on the user's Mac with loopback embeddings.

**Step 4, identity maintenance (complete 2026-10-25).** Every text change and the unchanged-text correction go through one general occurrence map (`admission.admit`), which covers kept, removed, added, split and combined occurrences. It refuses a changed resolution or meaning, a change of representation kind, a move to another document and span-scoped variants. A text edit of a document that another source reads withholds only the dependents' decisions that read what changed, until a reviewer re-confirms or replaces them. A decision may cite another source's decision, and withholding spreads down the chain. `forget` erases a source of any state to a tombstone and, after a confirmed dry run, removes every level of dependent decisions that cite it. `edit-entity`, `reconfirm`, `replace-decision` and `replace-citation` cover the readers of an edited Entity or a removed record. Guides: [dependencies](stage6_identity_dependencies.md), [chains](stage6_identity_chains.md), [forget](stage6_identity_forget.md) and [entity edits](stage6_identity_entity_edits.md). History: [step-4 sections](stage6_checkpoint_history.md#original-six-step-implementation-sequence) and [the step-4 close](stage6_checkpoint_history.md#cleanups-and-step-4-close-2026-10-25).

**S2, deletes outside the lab.** `status` lists a source whose native copy Cognee deleted or changed (`native_deleted`). `reconcile` and the edit commands refuse it, and `forget` erases the lab's copy afterwards. A kept decision may keep citing an Entity deleted outside the lab, and no publication recreates it (`entity_recreation`). `forget-dataset` forgets a root's whole dataset under one dry run and token, and repairs a root after a native dataset forget or prune. The append-only table `lab_identity_removed_entities` keeps every Entity UUID a lab operation removed, and no removed UUID is used again. Guide: [forget, deletes outside the lab](stage6_identity_forget.md#deletes-outside-the-lab). History: [Step 5 S2](stage6_checkpoint_history.md#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26).

**S3a and S3b, the lab entry points.** `entry.py` holds the lab's `add`, `cognify` and `remember`. `cognify` runs Cognee's chunking Tasks and one lab publication Task under the pipeline name `cognify_pipeline`, with no rollback handler and no LLM. The lab stamps each file it manages as cognified, so a plain `cognee.cognify` with its defaults skips it. Every creation command and `readd` adds, then cognifies, one source at a time in publication order (`entry.remember_in_order`). A source that was added but never published is refused `not_published`. The fixture environment points the LLM at a closed port, so a leaked LLM call fails at once. Guide: [entry points](stage6_identity_standard_entry_points.md). History: [S3a](stage6_checkpoint_history.md#step-5-s3a-the-lab-entry-points-2026-10-26) and [S3b](stage6_checkpoint_history.md#step-5-s3b-every-builder-on-the-entry-points-2026-10-26).

**S4, the lab update.** Every text edit goes through `entry_update.update`, and `reconcile` of a failed text change through `entry_update.replace_text`. Both run one lab Task under `cognify_pipeline` that calls `publisher.replace` with a `TextChange`, so admission and the incremental identity revision are unchanged. Cognee's standard Tasks rebuild the original's chunks inside the text change (`native_chunks.build_chunks`). Guide: [the lab's update](stage6_identity_standard_entry_points.md#the-labs-update). History: [Step 5 S4](stage6_checkpoint_history.md#step-5-s4-the-lab-update-2026-10-26).

**S1, public search and the conformance check.** Importing `search.py` adds the member `IDENTITY` to Cognee's `SearchType` and registers `IdentityRetriever`, so `cognee.search` with `IDENTITY` and one dataset returns what the CLI `retrieve` returns, with no LLM call. Both run `settled.retrieve_settled`. The import refuses any Cognee other than 1.6.2 and any Python other than 3.12. Only an Entity that a served source of the searched dataset constructs can seed a search. Both modes, `semantic` and `source_aware`, are built. Only `scope` `identity` is built. `support/conformance_check.py` scores `IDENTITY` searches on a DOC01 root against the Stage 5.3 benchmarks and fails when a case moves from `support/conformance_baseline.json`. It is a conformance check, not a benchmark, because the describer's author had read the hidden answers. Cognee's other search types do not check eligibility, and the search guide warns about them. Guides: [IDENTITY search](stage6_identity_public_search.md) and [conformance check](stage6_conformance_check.md). History: [Step 5 S1](stage6_checkpoint_history.md#step-5-s1-the-public-retriever-2026-10-26).

**The source-aware mode.** `mode` `source_aware` delivers the facts that the semantic search found in a second way. A fact that several served sources support keeps the evidence of each, each evidence item carries its chunk's range in the document, and a `documents` list names each supporting original by its Data ID and name with the spans of the facts it supports. `retrieve` returns the facts it found, and `retrieve_settled` delivers them through the mode's entry in `settled.DELIVERY` (`delivery.py`). The semantic result is unchanged. Nothing new is written to the graph. Guide: [source-aware results](stage6_identity_public_search.md#source-aware-results). History: [the source-aware mode](stage6_checkpoint_history.md#step-5-the-source-aware-mode-2026-10-27).

**Not built.** Automatic Describe, facts as citable records, Describe-driven corpus matching and model-quality evaluation belong to step 6. The six-step status table is in [the history](stage6_checkpoint_history.md#original-six-step-implementation-sequence).

## Next task

Step 5 continues. Work in this order.

1. **The other step-5 delivery items.**
   - Grouped-by-identity delivery: a second side list over the same flat `facts`, one entry per resolved referent, the way `documents` is one entry per document. The user named it on 2026-10-27; "grouped delivery" in older documents means this.
   - The full set of annotation states.
   - Span-scoped variants, which the occurrence map refuses today.
   - Ranking and seeding changes, each measured against the conformance baseline. QRY05 on the fallback seed and seed crowding are the known cases.
   - Offline diagnostics that share the traversal's predicates.
   - Admission of the consumed stores that each enabled native path reads (playbook lesson G14).
2. **Rebuild endpoint gaps.** Step 4 sent the endpoint gaps during a generated-source rebuild to step 5. Check whether S3a to S4 closed them, and record the answer.
3. **The outside-benchmark prototype.** The user approved it on 2026-10-26 for after S1. It is the route to a real benchmark, which the conformance check is not.

**Decisions already made.** These come from the user's step-5 discussion of 2026-10-25 and the S1 decisions of 2026-10-26, recorded in [the S2 history](stage6_checkpoint_history.md#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26) and [the S1 history](stage6_checkpoint_history.md#step-5-s1-the-public-retriever-2026-10-26).

- The semantic mode first, then the source-aware mode.
- The source-aware result shape, decided on 2026-10-27: a result field and no graph write (a fact-to-document graph write stays possible later work), the flat `facts` plus `documents`, a fact listed under every supporting document while the semantic mode keeps its behaviour, evidence chunk ranges as the finest span of a fact without a mention, and grouped-by-identity delivery as a separate later list.
- The identity search returns evidence only, with no LLM answer (U2).
- A function argument selects the scope. Identity-anchored facts are the default, and unattributed native hits are an opt-in (U3). The opt-in scope `identity_and_unattributed` stays refused `scope_not_built` until a spec builds it.
- Cognee's other search types get a warning only, for now (U1 option (a)).
- The search keeps the first slice's ranking. Seeding and ranking improvements are later work, measured against the S1 conformance baseline.
- The conformance corpus is DOC01 only, and the check runs as journey B1 and a local command, not in CI. QRY03 and QRY04 are an accepted gap, gated only on resolving no wrong group.
- A search over several datasets is refused `dataset_required` unless it covers exactly one lab dataset.
- No Cognee patch. The lab has its own entry points, and native deletes stay unwrapped and detected.
- The seven overnight decisions, confirmed on 2026-10-26 ([the decisions](stage6_checkpoint_history.md#next-task-and-the-overnight-decisions-as-of-2026-10-26)):
  1. No rollback handler under `cognify_pipeline`.
  2. The stamp comes right after native chunking.
  3. The native LLM extractor waits for step 6.
  4. The lab `cognify` handles lab sources only.
  5. A lab `update` with no describer is refused.
  6. HTTP routes are out of scope.
  7. The broad S2 refusal of a re-add with live citers stays.

**Decisions that need the user.**

- A guard for Cognee's other search types (U1 option (b)).
- The long-term retrieval entry. On 2026-10-25 the user called the registered `IDENTITY` search type a first step only.
- Which outside benchmark the prototype uses. No recorded decision names one.

## Tracked follow-ups and known limits

On 2026-10-25 the user decided that the step-4 follow-ups stay documented limits, and none blocks step 5. Each later checkpoint added its known limits. This list drops the items marked closed. The source of each item is in brackets, and the history keeps the full text: [step 4](stage6_checkpoint_history.md#tracked-follow-ups-as-of-2026-10-26), [S2](stage6_checkpoint_history.md#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26), [S3a](stage6_checkpoint_history.md#step-5-s3a-the-lab-entry-points-2026-10-26), [S3b](stage6_checkpoint_history.md#step-5-s3b-every-builder-on-the-entry-points-2026-10-26), [S4](stage6_checkpoint_history.md#step-5-s4-the-lab-update-2026-10-26) and [S1](stage6_checkpoint_history.md#step-5-s1-the-public-retriever-2026-10-26).

**Search and conformance.**

- Seed crowding. Other datasets' Entities can push every lab Entity out of the top 10 `Entity_name` hits, so a query returns no fact. Inferred from the code, not measured. [S1 limit 2]
- Cognee's other search types serve withheld and failed state. A guard needs the user's decision. [S1 limit 3]
- TRV08 and its negative control stay unobserved, because their coordinates follow DOC01 v1's chunking. [S1 limit 4]
- QRY05 fails on the fallback seed, the top `Entity_name` vector hit. [S1 limit 5]
- The conformance check is not a benchmark. A true benchmark needs a describer that never saw the answers (step 6) or an outside benchmark. [S1 limit 6]
- Every search runs `RecordStore.initialize`, because the retriever keeps no per-process cache. [S1 limit 7]
- A search with access control on is refused `access_control_on`, because the ledger lives in the one shared relational database. [S1 limit 8]

- One integration test failed once in 5 runs of `-n 8 --dist worksteal` on 2026-10-27, and it passed when rerun alone. The assistant lost its name. pytest printed its `FAILED` line, but the assistant's capture kept only the last lines. If it recurs, record the name and the traceback, and rerun it under `-n 8` to see whether it is parallel-only. [source-aware checkpoint]

**Entry points and the lab update.**

- When every chunk of a source is gone, `cognify` chunks again at the default budget of 512. A partial chunk loss gives a misleading message. [S3a limit 2]
- Short unstamped windows remain before native chunking, and between a forget or a changed-text ingest and the stamp after it. [S3a limit 3]
- With `ENABLE_BACKEND_ACCESS_CONTROL=true`, nested Cognee calls in the lab Task could block a one-slot dataset queue. Untested. [S3a limit 4]
- A first publication that fails on the first source leaves the later sources never added, and no command adds them. [S3b limit 1]
- A registered source whose `cognify` crashed before the ledger began is refused `not_published`, and no command recovers it. [S3b limit 2]
- A hard kill between a text change's per-item forget and its stamp leaves the original without chunks or stamp, and the row `pending`. [S4 limit 1]
- An edit after a native forget of the whole original stops with `source_missing` before the `native_deleted` refusal. [S4 limit 2]
- `erasure.py` imports the fixture class `text_fixture.RebuiltSemantics`. Step 6. [S4 limit 3]
- A describer writes the revision files before `replace` checks `expected_revision`. [S4 limit 4]

**Deletes outside the lab, re-add and tombstones.**

- Two forgotten co-owners re-added separately each derive their own replacement UUID, so one Entity becomes two (journey F28). [S2 follow-up 1]
- A failed first publication whose recipe builds an Entity deleted outside the lab, which no served source names, recreates it on `reconcile`. [S2 follow-up 2]
- A withdrawal between a forget's plan and its `begin`. Inferred safe from the append-once record, not probed again. [S2 follow-up 3]
- `reconcile` on a reset root refuses `stores_reset` and does not publish the root files again. [S2 follow-up 4]
- `describe_readd` assigns naming keys to removed Entities greedily, so it can refuse a re-add that has a valid assignment. [step 4]
- `check_readd_entity_ids` accepts `replaces:<uuid>` for any removed UUID, not only the Entity's own. [step 4]
- No record keeps every UUID a source used at every revision. [re-add follow-ups]
- The ledger check cannot see a dropped tombstone carry, because `forget.py` builds it outside the checked `RecordStore` methods. [re-add follow-ups]
- A re-add that renames a decision key reports other decisions even when the outcomes match. [re-add follow-ups]
- `describe_readd` does not rename a removed UUID in `candidate_entity_ids`. [re-add follow-ups]
- After a second forget, the tombstone lacks the Entities each earlier forget removed, so a rejected removal from the first life is refused again on retry. [J2]
- A re-add's never-served revision lists a served revision from the earlier life. Harmless. [J2]

**Erasure and cascade.**

- The registered snapshot of an erasure retry is written before `begin`. Harmless, and it converges on rerun. [I]
- A dependent whose text change finishes through the erasure retry leaves its own dependents' moved ranges for `refresh-dependents`. [I]
- A retry is refused when the bound set for the same document grew after admission and its old revision reads the new record. [J2 L1]
- The retire refusal is stricter than needed for a blocked dependent that cites both an intermediate and the forgotten source. [J2]
- A review drop, like an erasure, removes a recipe that only the dropped variant named. A citer of that variant is withheld by its changed citation. [K]

**Dependencies, chains and review.**

- `review.replaced_variant` writes `variant_assignments` directly, outside `records.py`. [cleanups, 2026-10-25]
- Attestation is per producer, not per decision. [H]
- A producer's identity is its key, not its content, so recorded provenance is not immutable. [H]
- `classify` finds a moved span in O(n·len). A long consumed document needs a substring search first. [H]
- A chunk of another document has no refusal rule and always needs review. A move across documents and a span-scoped variant range count as a change. [H]
- A replacement that adds a self-citation or a cross-dataset citation under an old producer is refused `reconfirm_unattested`, not the more specific code. [J1]
- `withheld_decisions` and `held_by` assume decision records until facts become saved records (step 6). [J1]
- The record checks run only before the writer reservation. Live withholding catches a later drift. [J1]
- doc03 has no captured facts, so its withholding shows only in `status` and the withheld lists. [J1]
- The CLI prints a refusal's message, not its code. Journeys check messages, and unit tests check codes. [J1]

**Proof checks and tooling.**

- The ledger model sends no replace for a missing row, so it does not cover the `source_missing` guard in `RecordStore.begin`. [step 4]
- The ledger break `forget-refuses-failed-replacement` is `INCONCLUSIVE`, and only the `REACHABLE` count catches it. [S2 evidence]
- The occurrence oracle's worlds cover at most one addition and no reordering. [step 4]
- Journey F9 edits root files with `python3` lines inside the journey. [I]
- The ledger check takes about 15 s at depth 5 and about 95 s at depth 6. [I]

## Code map

Paths are relative to `src/cognee_lab/identity/`.

| Module | Responsibility |
|---|---|
| `models.py`, `schema.py` | Runtime saved forms and the generated draft JSON Schema |
| `validation.py` | SHA-256 and JCS fingerprints, exact slices, native chunk tiling, input and cross-source UUID checks |
| `digests.py` | `object_digest`, shared by `records.py` and `validation.py` with no package import |
| `decisions.py` | Queries over a description's reviewed decisions (`naming_keys`), shared by `models.Tombstone` and the erasure rules |
| `storage.py` | `RecordStore`: the publication and event tables, the begin transitions (`TRANSITIONS`, `admissible`), `PublicationRow` with `is_served` and `holds_served`, expected-revision, attempt and writer guards. Mixes in `removal_record.RemovalRecord` |
| `removal_record.py` | The append-only table `lab_identity_removed_entities`: `record_removed`, `removed`, `removal_report`, `record_tombstone_removals` |
| `stages.py` | `run_attempt`, the one attempt frame for replace, withdraw and forget |
| `registered.py` | Data ingestion and readback, registered snapshot checks, `context_for` (untagged write context), `stamp` and `stamped` (the cognified mark), `write_text` |
| `publish.py` | `Publisher`: node creation and retention, markers, identity contributions, verification, `admit_inputs` (citation, key-reuse, mention-input and removed-recipe refusals), `saved_lives`, `refuse_natively_deleted` |
| `replace.py`, `withdraw.py`, `forget.py` | Guarded replacement, withdrawal and forget. `admit_replacement` is the one admission call site. `forget.delete_data` is shared with `forget-dataset` |
| `admission.py` | What a reviewed replacement may claim: `parse_occurrence_map`, `identity_map`, `admit` returning a `GroupFate`, `check_absent_from_graph`, `check_mention_inputs`, `check_corpus_inputs_exist`, `check_no_removed_recipes` |
| `text_changes.py` | `TextChange` with its typed `occurrence_map`, `preflight`, `apply` (forget, stamp, rebuild chunks), `reject_sole_owned_readers`, `reject_unsafe_cascades` |
| `dependency.py` | `citations` and `Target`, the one dependency predicate for erasure, withholding and the retiring-source fence |
| `records.py` | The saved-record registry `REGISTRY` of `RecordKind`s with their hooks, `record_digest`, `RemovedRecord`, `apply_removal`, `apply_reconfirm`, `write_parts`, `current_record`, `names_record` |
| `chains.py` | Citation rules (`check_citation_scope`, `check_record_citations`, `check_citation_cycles`, `check_record_key_reuse`), `upstream_closure` and `live_pass`, the one live pass that retrieval, `status` and the chain check run |
| `withholding.py` | `WithholdingStore`, `classify`, the edit stage `withhold_dependents`, `withheld_decisions`, `record_reader`, `unfinished`, `held_by` |
| `erasure.py` | What a forget does to its dependents: `cascade` by level, `impact` and its token, `removal_revision`, `removal_producer`, `finish_dependents`, `refuse_retiring_inputs`, `refuse_unfinished_cascade` |
| `erasure_rules.py` | Admission rules for an erasure removal and a re-add (`admit_readd`), `drop_unnamed_recipes`, `corpus_readers`. Imports nothing from `admission.py` |
| `retirement.py` | Shared retirement primitives: ownership snapshots, contributions, `dependents`, survivor checks, `record_removals` |
| `native_copy.py` | What Cognee still holds of a saved source (`NativeCopy`), `natively_deleted` for `status`, `refuse_reset` (`stores_reset`) |
| `outside_deletion.py` | Entities deleted outside the lab: `lab_removed`, `left_absent`, `live_citers`, `check_readd`, `sweep_orphans` |
| `dataset_forget.py` | `forget-dataset`: readers-first order, dry run and token, each source's `forget`, then non-lab Data, then the orphan sweep |
| `entry.py` | The lab's `add`, `cognify`, `remember` and `remember_in_order`. `cognify` runs `run_pipeline` as `cognify_pipeline` with the standard Tasks and the lab Task `identity_publish`. `semantic_hooks` is shared with reconcile and the update |
| `entry_update.py` | The lab's `update` and `replace_text`, both through one lab Task `identity_update`. `NoFacts` writes and verifies a source with no captured facts |
| `native_chunks.py` | `WHOLE_DOCUMENT`, `chunk_text` (in memory), `standard_tasks` and `build_chunks` with Cognee's own chunker |
| `retrieve.py` | Bounded retrieval: saved-source eligibility, `live_drift`, `select_seed_entities` (`skip`, `allowed`), identity links, local facts and current evidence. `LIMIT` defaults to 5. Not a corpus-wide retriever |
| `settled.py` | `SearchScope`, `SearchMode`, the frozen `SearchRequest` (with the not-built refusals), `SearchRefused` and `retrieve_settled`, shared by `retrieve` and `IDENTITY`. Importing it changes nothing in Cognee |
| `search.py` | Importing it runs `register()`: the version guard, the `IDENTITY` member with its self-test and rollback, and `IdentityRetriever`. `searched` and `search_history` serve the CLI and tests |
| `native.py` | Normalizers over the graph, provenance and neighborhood interfaces |
| `native_cognify.py`, `native_forget.py`, `native_search.py`, `entity_edit.py` | Captured stand-ins for plain Cognee calls outside the lab (`native-cognify`, `native-forget`, `native-add`, `native-search`, `edit-entity`). None writes a ledger row |
| `fixture.py`, `multisource.py`, `captured_chunks.py` | Captured facts and contexts, chunk binding, the per-source builders `add_<label>`, `seed_corpus`, `write_chunk_facts`, `reconcile_publication`, `not_published`, `fixture_files`, `CAPTURED_GROUPS` |
| `glossary_fixture.py`, `chain_fixture.py`, `chain_kind_change.py` | The glossary root (and doc03 with `--chain`), its command table (`OWN_COMMANDS`, `SHARED_COMMANDS`), the glossary edits, `cite-record` cases and the chain-root kind changes |
| `review.py` | The reviewer flow for `reconfirm`, `replace-decision` and `replace-citation`: `review_gate`, `Now`, `review_producer`, `intended_revision`, `REPLACEMENTS` |
| `revisions.py`, `text_fixture.py` | Captured correction and prefix edit, `refresh` and `refresh_dependents`, `RebuiltSemantics`, `edit_one`, `maintain_one`, `then_refresh`, `record_revision` |
| `occurrence_fixture.py`, `occurrence_addition.py`, `resolved_retirement.py`, `group_regrouping.py`, `reinterpretation.py`, `kind_change.py` | The captured edits: additions, removals, the mixed edit, retirement, split and combination, changed interpretation and kind changes. `COMMANDS` in `occurrence_fixture.py` maps each occurrence command to its text, describer and map |
| `captured_revision.py`, `captured_text.py` | Shared describer building blocks (`require_root`, `begin_revision`, `retire_group`, `declare_group`, `occurrence`, `stamp_producer`) and the original doc01 text `BEFORE` |
| `forget_fixture.py` | The forget, re-add and dependent-fixture drivers, `readd_plan`, `write_revision`, `CALLER_FILES` |
| `conformance_fixture.py` | `conformance-fixture`: DOC01 described by name rules, the hand-read `REFERENCES` table and a sentence rule. A conformance root takes only `status`, `retrieve` and `search` |
| `__main__.py` | CLI arguments, the `--embedding` reopen checks and command dispatch |
| `environment.py`, `fixture.env`, `fixture_embeddings.py` | Root marker, per-root embedding profile, store isolation, `CLOSED_LLM_ENDPOINT`, `COGNEE_VERSION`, `CREATION_COMMANDS`, `close_stores`. `fixture.env` holds only comments. `fixture_embeddings.py` is the loopback embedding service |

The proof checks live in `support/`. `ledger_check.py` runs the ledger model with the eight properties in `ledger_properties.py`. `occurrence_check.py` compares admission with an oracle over `occurrence_worlds.py` and `erasure_worlds.py`. `chain_check.py` checks the cycle rule, withholding down the chain and `record_key_reused` over `chain_worlds.py`, and runs `cascade_check.py` over `cascade_worlds.py`. `conformance_check.py` scores a conformance root against `conformance_baseline.json`, and it is the only reader of `data/hidden`. `md_link_check.py` checks that every relative Markdown link and anchor resolves. Tests live in `tests/test_identity*.py` and `tests/test_conformance_check.py`. Original forms and texts are in `tests/fixtures/identity/`, and the exported schema is `schemas/cognee_identity_source_schema_draft.json`. The captured adapters' IDs and phrases are not a generic extraction layer.

## Resume and verification commands

At session start, inspect the checkout and keep any local changes:

```bash
git status --short
git log -1 --oneline
uv sync --group dev
uv run python -c "import cognee; print(cognee.__version__)"
uv run pytest -q -m 'not integration'
```

The Cognee version must be **1.6.2**. If it differs, check compatibility again before you call it the tested profile. On `main` at `e804b35` the unit suite gave 707 passed on 2026-10-27, run by the assistant on the user's Mac. [The history](stage6_checkpoint_history.md#counts-and-timings-recorded-in-the-handoff-until-2026-10-26) keeps the earlier counts.

A happy path in a **new** root:

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/stage6_resume_check --embedding loopback
uv run python -m cognee_lab.identity revise-occurrences --root outputs/stage6_resume_check --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_resume_check
uv run python -m cognee_lab.identity search --root outputs/stage6_resume_check
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_resume_check --source doc01
```

Expected: `retrieve` returns two facts. `search` prints a `search_result` whose one element equals the `retrieve` output, and one `IDENTITY` row in `search_history`. doc01 is at 2/2/2 and doc02 at 1/1/1, g01 continues with `it` at [46,48) and `the controller` at [86,100), g02 is retired, and no recovery incident exists. The assistant ran this sequence on the user's Mac on 2026-10-27, on `4e7a33b` with loopback embeddings. It saw the two facts, the equal `search` result, the revisions and no recovery event, and did not check the offsets. The [mixed occurrences guide](stage6_identity_mixed_occurrences.md) has the values and the failure recovery. The [dependencies](stage6_identity_dependencies.md#commands), [chains](stage6_identity_chains.md#commands), [IDENTITY search](stage6_identity_public_search.md#commands) and [conformance](stage6_conformance_check.md#the-gate) guides have their own sequences.

Fixture creation refuses an existing directory. Without `--embedding loopback`, creation uses the default `env` profile, which calls the embedding endpoint that `.env` names. Later commands read the profile from the root marker. A root made before the `.env` fix of 2026-10-20 opens only for `status` and `retrieve`. pytest always uses loopback.

## Verification and landing

The user agreed this routine on 2026-10-21. `CLAUDE.md` holds the same steps.

1. **Unit tests on every commit.** `uv run pytest -q -m 'not integration'` uses loopback embeddings and runs the ledger check at its default depth and the occurrence check on small worlds. GitHub Actions (`.github/workflows/unit-tests.yml`) runs the unit suite and `support/occurrence_check.py` in the `unit` job, and `support/chain_check.py` in its own `chains` job with a 45-minute limit. CI runs after a push, so it does not replace the local checks.
2. **Proof checks for the riskiest code.** For `RecordStore` or its callers, run `uv run python support/ledger_check.py`. For `admission.py`, run `support/occurrence_check.py` with and without `--mutants`. For `admission.py`, `records.py`, `chains.py`, `withholding.py` or `erasure.py`, also run `support/chain_check.py` with and without `--mutants`.
3. **The conformance check for retrieval changes.** For `retrieve.py`, `settled.py`, `search.py`, `conformance_fixture.py` or the fact writers in `fixture.py`, run `uv run python support/conformance_check.py` and journey B1. A case that moves in either direction fails the check. It is local, not in CI.
4. **The changed feature's journeys.** Run `.claude/skills/verify/scripts/verify.py journey <ID>` for each journey in the changed feature's file under `.claude/skills/verify/features/`.
5. **`verify.py journey all` once per checkpoint**, before the merge to `main`.
6. **The integration suite**, `uv run pytest -q -m integration -n 8 --dist worksteal`, only on a local machine. Run the focused native tests for the changed path first. On 2026-10-27 the whole suite took 9 to 10 minutes with 8 workers and about 46 minutes in one process.

**Verify journeys.** The journeys drive the CLI through real Cognee stores in fresh roots under `outputs/verify/`. The feature map has 103 journey blocks. `journey all` runs the 102 loopback blocks as 141 runs, 4 at a time by default (`--jobs N`). Journey P5 calls the NVIDIA embedding API, so it runs only with `--include-env`. The last full run, on the `source-aware-mode` branch on 2026-10-27, gave 2032 PASS rows and 0 FAIL rows in 141 runs. `.claude/skills/verify/SKILL.md` gives the commands and the proof rules. If a `lab_store` check fails under parallel runs, rerun with `--jobs 1`.

**Identity-ledger check.** It runs every sequence of real `RecordStore` calls up to depth 5, with two sources and two writers. `PINNED` in `tests/test_identity_ledger_check.py` holds 9205 nodes and 9050 sequences. `--mutants` runs the scratch breaks in `support/ledger_mutants.py`. `.claude/skills/identity-ledger/SKILL.md` says when to run it.

**Land a branch** with [the landing playbook](../.agents/playbooks/landing-on-main.md). Work on a branch off `main`, review it with `/pstack:thermos`, run the unit suite (and `journey all` at a checkpoint), and merge with `git merge --ff-only`. Do not open a pull request. Push `main` after each checkpoint merges, and check CI. After the merge, remove the worktree and delete the branch as `CLAUDE.md` describes.

## How the work is run

Each step-5 checkpoint followed this routine, which the user agreed:

1. A subagent drafts the spec read-only against `main`.
2. An independent reviewer checks the spec.
3. Implementation starts only when the spec answers every review concern. Questions that only the user can settle go to the user first. Probes on the user's Mac settle questions that an experiment can answer.
4. A subagent builds the checkpoint on its own branch.
5. `/pstack:thermos` runs a bug review and a quality review. Fix rounds follow until neither finds anything blocking. Each bug fix comes with a test that failed first.
6. `verify.py journey all` passes on the final head.
7. The branch merges into `main` with `git merge --ff-only`. Push `main` and check that GitHub Actions passes (the user's standing rule since 2026-10-27).
8. Update the checkpoint docs, then run `uv run python support/md_link_check.py`:
   - this handoff;
   - [ROADMAP.md](../ROADMAP.md);
   - the checkpoint's guide under `docs/`;
   - a dated section in [the integration playbook](../results/cognee_knowledge_integration_playbook.md);
   - a dated section in [the checkpoint history](stage6_checkpoint_history.md).

   Keep dated history. Say who ran each result and where: the user, or the assistant on the user's Mac. Keep apart tests run here, the user's own runs and untested design.

The user's model and escalation rules for subagents live in the user's private configuration, not in this repository. Follow them as the session gives them.

Local working notes (specs, reviews, probe summaries, build reports and todo lists) live in `.audit/` at the repository root. `.git/info/exclude` keeps that directory out of git, so the notes exist only on the user's Mac. The history cites them as "the assistant's working notes".

The user works in auto mode. A user auto-mode rule allows deletion under `outputs/`, and the user approves each other deletion. The user prefers the NVIDIA embeddings in `.env` for real fixture runs, and loopback for pytest and verify journeys.

## Constraints to preserve

- Use **singleton**, **identity group (variants)** and document-local mention groups. No privileged canonical member, no authoritative `entity_role` field and no permanent identity-group registry. Do not silently promote a mention into a reusable Entity.
- Saved descriptions and the publication ledger govern intent and currentness. Graph properties or an old recipe alone do not authorize resurrection. Existing compatible Entities are referenced and retained without overwriting ordinary fields. Populated nested existing DataPoints can enter the write set by accident.
- Original occurrence chunks own the markers. Original producing chunks own semantic facts and evidence. Generated identity Data owns identity contributions and required-endpoint retention. A fact owner alone does not protect an unretained endpoint from cascading deletion. Keep the reused-endpoint retention fix.
- Occurrence coordinates are exact Unicode code points in the extracted document string, `[start,end)`. Validate the source fingerprint, the slices and the complete native chunk mapping. Never take the first repeated substring as an implicit locator. Content-derived chunk IDs can recur while positions and indexes change.
- Use configured Cognee interfaces and backend-neutral relational operations. Ladybug, LanceDB and SQLite are the tested fixture profile, and no vendor-specific code is authorized. Every fixture root keeps its stores inside the root. The `loopback` profile calls no external API.
- Pending and failed sources are withheld, and independent valid sources survive. Recovery is explicitly selected forward completion of saved intent, not rollback or automatic retry. Native readers that ignore the ledger can see intermediate graph state. A hard crash can leave a writer reservation. Do not clear it casually or claim general restart recovery.
- Prefer programmatic validation, publication and traversal. Capture where rules or model judgment are needed. Captured fixture decisions establish lifecycle mechanics, not extraction quality, search quality or scientific support.
- A/B staging, incremental chunk reuse, comprehensive semantic replay and archives, automatic orchestration, all-alias Triplet text and universal scope or ontology frameworks are deferred. Size, density and token-overhead tooling is future evaluation work. Do not enable a diagnostic Triplet, cache or optional native stage without admitting its lifecycle and consumed-store behavior.
