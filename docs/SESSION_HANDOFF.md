# Session handoff — resume here

**Updated:** 2026-10-20 (America/Detroit). **Current work:** Stage 6, accepted implementation step 4 / M3, partially complete. **Next task:** review a concrete group split/combination case. This document records the current continuation state; dated experiment writeups describe their own checkpoints.

## Objective and reading order

Build a methodology for integrating structured knowledge into Cognee through **Describe, Publish, Maintain and Retrieve**. Identity is the first worked integration. Carry demonstrated mechanisms and tests forward to other domains, such as scientific measurements, while keeping each domain's meaning and rules explicit. Scientific justification/reasoning is outside this implementation's scope.

Read this document first, then:

1. [ROADMAP.md](../ROADMAP.md): project stages and current scope.
2. [Stage-6 architecture/contract](../results/cognee_identity_stage6_handoff.md): physical representation, ownership, continuity, recovery and original six-step build order. Its dated implementation subsections are checkpoint history.
3. [R1–R6 requirements](../results/cognee_stage5_4_5_requirements_review.md): outcome constraints, not a claim of complete coverage.
4. [Latest fixture guide](stage6_identity_occurrence_addition.md), followed by the earlier guides linked below for individual commands.
5. [Integration playbook](../results/cognee_knowledge_integration_playbook.md): findings tagged with Describe/Publish/Maintain/Retrieve and transfer questions for other integrations.

The [representation decision record](../results/cognee_stage5_4_5_identity_representation_proposal.md) and [pinned native extension reference](../results/cognee_extension_architecture_reference_v1.6.2.md) explain rationale and native behavior. Do not treat their early dated “next” or “not implemented at that checkpoint” statements as current implementation status. The roadmap and this handoff identify current work; later explicit approved scope changes supersede earlier proposals.

## Code baseline and delivery status

Runtime code is in `src/cognee_lab/identity/`. Implemented code includes **captured occurrence additions and new-group publication**, following resolved fact-bearing group retirement. No split/combine, automatic Describe, dependent-source reconsideration or standard-entry-point extension has been generated. The addition update extends transition admission, captured semantic output, diagnostics, CLI commands and tests; the saved-source schema and dependencies are unchanged.

The user's Mac addition, reopened retrieval, healthy reconcile and `replace_published` failure/recovery outputs have been reviewed. The next task is the concrete group split/combination review below.

Generation began from lab checkout commit `5a179881b4314ba458ed2836fc3d7e78edae8169`; subsequent code was delivered as patches. That hash is the generation base, **not a claimed current user/GitHub HEAD**. The original checkout plus that hash alone is insufficient to resume. A complete committed checkout must contain the subsequent code and docs. No remote commit/push was performed by the generating assistant.

Delivered patch order, for provenance or reconstructing an older checkout:

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

These are delivery filenames, not required runtime files or a promise that patch archives are committed. Do not reapply patches to a checkout already containing their changes. The occurrence-removal and resolved-group-retirement code-patch SHA-256 values are respectively `d01d68c99051c4b26cb08ce8f9ed3a240b44b71d16f5076c684004bfb4f5b0c2` and `0086ae816b52cc23803e93cfc932497920d5efe8811c6040189c56c2b28fda60`.

At session start inspect `git status --short`, `git log -1 --oneline`, the files below and CLI commands. Preserve local changes. After integrating a delivered update, commit and push the relevant source/tests/schema/dependencies/docs so a fresh GitHub checkout has the complete baseline. User-local output stores and this chat's downloaded archives are not substitutes for committed source.

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

### Tests run in the generation environment

The previous resolved-retirement code checkpoint recorded **59 programmatic tests and 7 selected native sequence tests passing (66 distinct cases)**. The native selection was three resolved-retirement sequences, three preceding occurrence-removal sequences and one multi-chunk repeated-edit/reconcile/withdraw sequence. The other 19 native cases were not rerun in that checkpoint. Earlier delivery counts overlap; do not add them or claim a fresh full-suite run.

Tests used Python 3.12.14, Cognee 1.6.2, actual configured Ladybug/LanceDB/SQLite stores, deterministic loopback embeddings and no LLM. Only that native profile is demonstrated. Final code-patch application and affected-file byte equality were checked. The preceding documentation-only update did not rerun the runtime suite.

The **2026-10-20 addition checkpoint** passed **81 programmatic tests and 3 new native sequence tests (84 distinct cases)**; the other 26 native cases were not rerun. The native selection covers addition/reopen/reconcile/another prefix edit/withdrawal, plus exact forward recovery after `text_chunks` and `replace_published`. User-Mac reproduction is recorded separately below.

Native assertions used actual configured stores and fresh child processes, with a **host-only test launcher** that exits after the ordinary CLI returns and its explicit engine-close path completes, bypassing interpreter finalization. Ordinary CLI publication and reopened retrieval produced the expected three facts, but one reopened retrieval then exceeded the 300-second process-exit allowance on this Linux host. Thus the launcher results establish the tested lifecycle operations/reopen/verification, not clean ordinary interpreter teardown here. The application has no forced-exit workaround. The delivery's `TESTS.md` and `support/host_native_launcher.py` preserve this qualification and local reproduction route. The isolated profile now uses LiteLLM's bundled pricing map to avoid unrelated startup metadata fetching; the lockfile/dependencies are unchanged.

### Results verified on the user's Mac

The user ran and supplied terminal output; the assistant reviewed the returned JSON. This is independent reproduction on the user's machine, not execution there by the assistant. Verified sequences include initial publication/reconcile, multi-source withdrawal/retry, unchanged-text correction/recovery, prefix-edit/recovery, and the following latest checkpoints:

| User-local root(s) | Reviewed result |
|---|---|
| `outputs/stage6_multichunk` and `_failure` | Edit and healthy reconcile preserve complete evidence/current chunk mapping; failed doc01 withheld while doc02 survives; explicit reconcile completes revision 2 and resolves incident |
| `outputs/stage6_occurrences` and `_failure` | g01 keeps only `it` at `[46,48)`; empty unresolved g02 is removed; healthy reconcile does not resurrect it; interrupted cleanup completes with the same event resolved |
| `outputs/stage6_resolved_retirement` and `_failure` | g01/r01/local fact/evidence are removed; unresolved g02 survives; only doc02's unchanged fact returns; healthy reconcile preserves retirement; explicit recovery resolves the same event at revision 2 |
| `outputs/stage6_additions` | Addition returns three facts; g01 continues and g03 is created with its name index, accepted link, original-owned local fact and current evidence; reopened retrieval and healthy reconcile preserve results without increasing revisions or creating incidents |
| `outputs/stage6_additions_failure` | Injected `replace_published` failure withholds doc01 while doc02's unchanged fact remains available; explicit reconcile completes revision 2, restores three facts and resolves the same incident with one verified recovery attempt |

For these reviewed maintenance checkpoints, doc01 reaches saved/registered/verified revision 2 and doc02 stays at 1. Borrowed Entity fields and independent shared support survive. Successful paths produce no incidents; injected failures produce one test-labeled incident closed after verified forward completion. The latest resolved-retirement recovery was reviewed on 2026-10-19, from the run ending approximately 22:45 America/Detroit.

The addition recovery was reviewed on 2026-10-20, from the run ending approximately 10:49 America/Detroit. Incident `f93491d5-3f5a-58c0-b786-a3874c27059c` records the injected failure and a single verified recovery attempt ending `restored` at revision 2. Fresh g03 `a75636db-c46d-5261-a21e-010647bfe4f4` survives recovery with its node/name index, accepted r03 and two current evidence/marker chunks. Continuing mention IDs, doc02's full fact/evidence and source summary, and borrowed Entity fields are unchanged; retired chunks/vectors are absent.

These Mac results cover successful addition, reopen/healthy reconcile and post-publication recovery. Mac `text_chunks` failure, a subsequent prefix edit and withdrawal after addition have not yet been reviewed. Their generation-environment native tests retain the host-only-launcher qualification above; the Mac results do not establish clean ordinary Linux interpreter teardown.

Raw terminal transcripts were supplied in chat and are not asserted to be committed. This table is the durable verification summary. The roots above are user-local existing stores: reuse them for inspection only, and use new roots for new fixture creation. Dataset IDs vary by root; never substitute IDs from another run.

## Original six-step implementation sequence

This is **step 4 within Stage 6**, not project Stage 4.

| Step | Current status |
|---|---|
| 1 / M0 | Runtime forms/schema, exact chunk mapping, portable bookkeeping and capability checks implemented for the initial profile |
| 2 / M1 | Captured Task → native publication → useful fact/evidence retrieval → reconcile demonstrated |
| 3 / M2 | Multi-source ownership/withdrawal demonstrated; general exact-ID semantic conversion remains broader than the captured writer |
| 4 / M3 | Partly complete: corrections, prefix/rechunk edits, partial occurrence removal, empty unresolved and resolved fact-bearing group retirement, captured additions/new group and explicit caught-failure recovery |
| 5 / M4 | Standard Cognify/Remember/full Update B Task-transform wiring, source-removal entry-point hooks, public Retriever/SearchType, broader traversal/delivery/diagnostics not implemented |
| 6 / M5 | Seeded rules/model Describe and separate quality/consistency evaluation not implemented |

### Remaining step-4 work

1. **Occurrence/group changes:** explicit splits/combinations with fresh resulting IDs, mixed addition/removal, representation-kind changes using separate suitable Entities and broader addition cases. Captured continuing-group additions, new-group publication and unresolved/resolved removal are implemented; their fixtures do not establish general regrouping or automatic matching.
2. **Changed interpretation and semantic refresh:** edits changing a referent/definition/scope, with coordinated saved decisions and regenerated facts/evidence. Existing unchanged-text retargeting and captured same-binding edits do not establish this generally.
3. **Dependencies:** identify and reconsider affected sources that consumed another document, corpus fields or saved records; support admitted span/record remapping. Current code rejects known dependent-document text edits rather than silently propagating them. New-corpus opportunity selection is not solved by positive dependencies alone.
4. **Full source lifecycle:** coordinate original removal with generated-source retirement, generated-source rebuild and authorized endpoint reconstruction; preserve remaining owners and distinguish missing reasoning inputs from missing reconstructible output. Identity withdrawal alone keeps Data/description and original facts; it is not full source Forget.
5. **Verification/recovery coverage:** extend current revision/attempt/currentness, ownership/index/evidence and retirement checks across those operations, including incomplete/missing-plan diagnostics. Do not make a general crash-recovery framework a new prerequisite.

The next task is to **review a concrete group split/combination case**, then implement the smallest captured regrouping slice. State which old groups retire, which fresh resulting IDs and decisions replace them, and what semantic output must be regenerated; do not infer fact transfer from group continuity. The existing `occurrence_retention` mode handles removals, while `occurrence_continuity` separately maps every old occurrence to a reviewed new index and admits additions. Neither admits splits/combinations or mixed removal/addition. Reuse the whole-document rebuild/common publisher and preserve independent doc02 support. No generic Describe algorithm is a prerequisite.

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
| `text_changes.py` | Prefix/removal/addition admission, dependency/cascade guards, native whole-document Forget/ingest/chunk rebuild and retired chunk checks |
| `retrieve.py` | Bounded fixture retrieval, saved-source eligibility, scoped identity links/local mention facts and native current evidence; not a public corpus-wide retriever |
| `native.py` | Normalizers over graph/provenance/neighborhood interfaces |
| `fixture.py`, `multisource.py`, `captured_chunks.py` | Captured facts, source contexts, exact producing/evidence chunk binding, single/two-source setup and diagnostics |
| `revisions.py`, `text_fixture.py` | Captured identity correction/prefix edit, shared maintenance callbacks and transition diagnostics |
| `occurrence_fixture.py`, `occurrence_addition.py`, `resolved_retirement.py` | Captured addition/removal/retirement examples and physical absence/shared-survival checks |
| `__main__.py`, `fixture_embeddings.py` | Isolated fixture CLI/profile and deterministic local embedding service |

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

The inspected native version must be **1.6.2**. A different version needs renewed compatibility inspection; do not silently treat it as the tested profile. A full native suite is `uv run pytest -q -m integration`; it creates fresh stores and can take minutes. Run focused native files for the changed path, then broaden only as needed.

The latest happy path, with a **new** root, is:

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/stage6_resume_check
uv run python -m cognee_lab.identity add-occurrences --root outputs/stage6_resume_check --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_resume_check --source doc01
```

Expected: three facts, doc01 current at 2/2/2, doc02 unchanged at 1/1/1, stable g01 plus fresh g03 and its local fact, g02/shared support present, no recovery incident. The guide has a separate fresh-root `replace_published` failure/recovery sequence. `status` and `retrieve` inspect existing marked roots; fixture creation refuses existing directories.

## Constraints to preserve

- Use **singleton**, **identity group (variants)** and document-local mention groups; no privileged canonical member, authoritative `entity_role` field or permanent identity-group registry. Do not silently promote a mention into a reusable Entity.
- Saved descriptions and the publication ledger govern intent/currentness. Graph properties or an old recipe alone do not authorize resurrection. Existing compatible Entities are referenced/retained without ordinary-field overwrite; populated nested existing DataPoints can accidentally enter the write set.
- Original occurrence chunks own/retain markers; original producing chunks own semantic facts/evidence; generated identity Data owns identity contributions and required-endpoint retention. Attaching a fact owner alone does not protect an unretained endpoint from cascading deletion. Preserve the reused-endpoint retention fix.
- Occurrence coordinates are exact Unicode code points in the extracted document string, `[start,end)`. Validate source fingerprint, slices and complete native chunk mapping. Never choose the first repeated substring as an implicit locator. Content-derived chunk IDs can recur while positions/indexes change.
- Use configured Cognee interfaces and backend-neutral relational operations. Ladybug/LanceDB/SQLite are the tested fixture profile; no vendor-specific implementation is authorized. The old NVIDIA tokenizer patch is separate from this isolated no-API fixture.
- Pending/failed sources are withheld; independent valid sources survive. Recovery is explicitly selected forward completion of saved intent, not rollback or automatic retry. Native readers ignoring the ledger can see intermediate graph state. Hard crashes can leave a writer reservation; do not casually clear it or claim general restart recovery.
- Prefer programmatic validation/publication/traversal. Capture where rules/model judgment is required. Captured fixture decisions and deterministic embeddings establish lifecycle mechanics, not extraction/search quality or scientific support.
- A/B staging, incremental chunk reuse, comprehensive semantic replay/archives, automatic orchestration, all-alias Triplet text and universal scope/ontology frameworks are deferred. Size/density/token-overhead tooling is future evaluation work. Do not enable diagnostic Triplet/cache/optional native stages without admitting their actual lifecycle and consumed-store behavior.

After each next checkpoint update this handoff's baseline, implemented/remaining status and verification table, together with the roadmap and relevant guide/playbook findings. Preserve dates and distinguish generated-here tests, user-reported native reproduction and untested design.
