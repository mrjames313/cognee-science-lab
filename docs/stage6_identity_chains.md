# Stage 6 chains: decisions that cite other sources' decisions

**Date:** 2026-10-23. **Status:** checkpoint J1, implemented and verified by the assistant on the user's Mac with loopback embeddings, then revised in fix round 1 the same day (see [Fix round 1](#fix-round-1)) and found merge-ready by a final review (see [Checkpoint runs](#checkpoint-runs)). No user-reviewed fixture root exists yet. Checkpoint J2 (2026-10-24) built erasure down a chain; see [Forget of a cited source](#forget-of-a-cited-source) and the [forget guide](stage6_identity_forget.md#the-cascade).

Before this checkpoint a source could read another document (a glossary entry, a protocol) but not another source's saved decision. Admission refused every saved-record input. Now a resolution or a variant assignment may cite a resolution or a variant assignment of another source in the same dataset. When the cited decision is withheld, changed or gone, the citing decision is withheld too, and the withholding spreads down the whole chain of citations.

The user decided this on 2026-10-23:

1. Citable records are decisions only: mention resolutions and variant assignments. The citation format and the chain logic stay generic over record type, so another type needs no redesign. Facts are not citable yet; they need a separate discussion, because they overlap the semantic-output item. Native Cognee edges stay outside withholding.
2. Withholding spreads down the whole chain. It is derived when retrieval runs, with no new rows, and the reason shown is the existing `input_changed`. A re-confirm upstream releases downstream. A replacement upstream changes the cited record, so downstream needs its own review. Admission refuses cycles.
3. Erasure cascades down the chain in dependency order, with one dry run, one token and one confirmation for every level. Checkpoint J2 built this (see [Forget of a cited source](#forget-of-a-cited-source)); J1 had an interim refusal.
4. The non-identity example is deferred.

A reviewer checked the spec against these decisions and the code before implementation and gave the verdict "proceed", with 16 resolutions. The first split the work into J1 (citations, admission, cycles, withholding down the chain, the reviewer commands, the chain fixture and its checks) and J2 (the erasure cascade).

| Input the decision read | What changed | Outcome |
|---|---|---|
| A saved record of another source | Re-confirmed upstream (only inputs and producer changed) | Valid automatically: the fingerprint holds |
| A saved record | Changed in place (a reviewed field, or a resolution made unresolved) | Withheld, `input_changed`, `refresh_needed`; may be re-confirmed |
| A saved record | Its key is gone from the cited source (a group retired, or a replacement under a new key) | Withheld, `input_removed`, `refresh_needed`; never re-confirmed |
| A saved record | The cited source has a pending or failed attempt, is current but not verified, or its own input fails live validation | Withheld, `input_changed`, `edit_unfinished` |
| A saved record | The cited source is withdrawn or forgotten | Withheld, `input_removed`, `refresh_needed` |
| A saved record | The cited decision is withheld | Withheld, `input_changed`, `upstream_withheld`; releases when the cited decision does |

## The data shapes

- **A citation** (`models.SavedRecordInput`): `dataset_id`, `identity_data_id`, `record_type` (`mention_resolution` or `variant_assignment`), `record_id` (the decision key, unique across both maps within a source), `representation_revision` and `content_sha256`. The revision is the cited source's revision when the citation was made. It is provenance, not a validity test.
- **The record registry** (`records.py`, `REGISTRY`): each record type maps to the attribute of a description that holds its records, its fingerprint projection, and `held(entries, description, key)`, which says whether one of its records is withheld given its source's withheld decisions (for a decision: its key is in them). Admission, validation and withholding read records only through it, and the closure asks `held` rather than looking up a decision key. An import-time check refuses a registry whose types differ from `models.RecordType`. Adding facts later is one registry entry plus, in J2, its removal shape. Since J2 fix round 1 the entry also answers the input keys a record cites (`inputs`, which `validation.decision_inputs` folds over), the name of what an erasure leaves (`outcome`), the other parts of a description that hold its records' inputs, with erased keys stripped (`stripped`: a resolution's groups), and the mentions whose facts lose their link (`unlinked`). The erasure code reads no decision status and strips no group by name.
- **A fingerprint** (`records.record_digest`): the SHA-256 of the RFC 8785 JCS form of `{record_type, reviewed fields}`. Reviewed fields are everything but `producer_ref`, `input_refs` and `explanation` (`records.reviewed_decisions`, moved there from `admission.py`). A resolution's fingerprint also names its group's mention UUID (`group_entity_id`). Mention UUIDs are revision-scoped and never reused, so a key and a group key that come back later with the same target give a different fingerprint for a different mention. A continuing group keeps its UUID, so a re-confirm and a span move keep the fingerprint.
- **The source graph** (`chains.source_graph`): an edge from A to B when A cites any record of B. It holds the latest saved description of every source that is not retired (current, pending and failed), with the candidate in place of its own.
- **The withheld-decision set** is the one from checkpoint H, with one more status. `upstream_withheld` (a cited record is withheld) is derived only. It is never written to the withholding table, whose `status` column (`String(16)`) it does not fit. When several causes withhold one decision it shows `edit_unfinished` over `upstream_withheld` over `refresh_needed` over `remap`, and `input_removed` over `input_changed`.

`RecordStore`, `TRANSITIONS`, the ledger model and the withholding table are unchanged.

## Admission of a citation

| Rule | Where | Code | Admits or refuses |
|---|---|---|---|
| `chains.check_citation_scope` | `Publisher.admit_inputs`, which every path runs (a first publication, a re-add, a replacement's preflight) | `not_admitted`, `self_citation` | A cited record is of the same dataset, and of another source. A source's own decisions already relate through its groups and inputs, and a citation of its own record would pin the revision being written. |
| `check_foreign_inputs` (rule 5) | `admit` | `foreign_input_changed` | A saved record is a foreign input. An existing key keeps its content, pinned revision included. A changed citation takes a new key. |
| `check_reconfirmations` (rule 5) | `admit` | `reconfirm_unattested` | A decision under an old producer cannot add, drop or swap a saved-record citation; a producer new in the revision can. |
| `chains.check_record_citations` | `admit_inputs`, first attempt only | `record_source_unavailable`, `record_missing`, `record_stale`, `record_digest` | A citation the old revision lacked names a served source, a record under its type, that source's current revision and the record's fingerprint, in that order. |
| `chains.check_citation_cycles` | `admit_inputs` | `citation_cycle` | The source graph stays acyclic. |

The first-attempt rows checks follow `chains.new_citations`: every citation of a first publication or a re-add, and on a replacement the keys the current revision lacks. A retry or a reconcile reuses its saved intent and checks none, so a record that drifted since the attempt began is admitted and withheld, as an existing key is. Otherwise `record_digest` would refuse the retry forever.

Citing a record that is withheld now is admitted, and the citing decision is withheld at once. Admission does no live read; withholding down the chain is the backstop.

The cycle check runs once, in `admit_inputs`, before `begin`. A failed attempt's citation is already an edge of the graph, so its retry cannot be refused for a cycle. The shared writer reservation serializes writers. The check is per source, not per decision: it also refuses some shapes that are acyclic decision by decision, such as A's r1 citing B's v1 while B's r2 cites A's v2, and every mutual citation between two sources.

Every `validate_inputs` caller passes the saved-record reader (`withholding.record_reader`): retrieval's live pass, `admit_inputs`, the publication's verification stage and the replacement's withholding cleanup. Validation no longer compares the pinned revision; the fingerprint decides.

## Withholding down a chain

The reader (`withholding.record_reader`) answers for one cited record from the ledger rows with a reason and a status, or None. A withdrawn, forgotten or missing source gives `input_removed` and `refresh_needed`. A cited source that is unfinished gives `input_changed` and `edit_unfinished`, checked before the record, so a pending upstream never shows `input_removed`. A key the current revision lacks gives `input_removed`, another fingerprint `input_changed`, both `refresh_needed`.

"Unfinished" is one rule, `withholding.unfinished`: the cited row is not retired and not served (an attempt pending or failed, or current with its verified revision behind its saved one), or its own input failed live validation. The derived rule in `withholding.withheld_decisions`, the reader and the review gate all use it. So while a cited source is unfinished, every decision citing one of its records is withheld with `input_changed` and `edit_unfinished`, and no reviewer is offered a review it cannot complete. Admission and publication verification read the withheld-decision set as their skip set.

Retrieval and `status` share one live pass, `chains.live_pass(rows, withheld, drift_of)`. Retrieval passes `retrieve.live_drift`; the chain check passes a drift built from the reader, so the check runs the real pass.

1. `drift_of` validates each served source with the reader. It returns the foreign inputs that fail, with their reasons, or raises the IntentError of an own input that fails.
2. If a source failed, the reader is rebuilt with the failed sources, so a decision citing a record of one is unfinished like one citing a pending source. The next call sees that source as failed, so the entry does not change.
3. `withholding.held_by` combines each source's entries of the withheld-decision set with its drift (`refresh_needed`) and the reader's answer for each saved record it cites, with that answer's status.
4. `chains.upstream_closure` withholds each decision that cites a withheld record of another served, valid source, with `input_changed` and `upstream_withheld`, and repeats until nothing changes. Whether the cited record is withheld is its type's `held`. This reaches the same set as one pass in the topological order of the source graph, and it ends on a cycle that a race could leave.

Nothing is written. When the cited decision is released, the citing one is released on the next read. `refresh_needed` lists only decisions a reviewer can answer, so it never lists an `upstream_withheld` one. A text edit's withholding still names only the document (`Target(doc)`), so a text edit of a cited source writes no rows for its citers.

## Reviewer commands

- `reconfirm --source doc03 --decision c01` re-confirms a decision withheld because a saved record it cites changed. The next revision cites the record as it is now under a new key (`doc01_r01_r2`) and names a producer new in the revision (`review_c01_r2`, implementation `re-confirmed`, with the withholding it answers and the old and new fingerprints).
- `reconfirm` refuses a decision withheld with `input_removed`, as before, and every review refuses a decision withheld with `upstream_withheld` (code `upstream_withheld`): it waits for the record above it.
- The review gate (`review.review_gate`) refuses (`edit_unfinished`) while any document the reviewed source reads has a pending or failed edit, while any source whose records it cites is unfinished, or while the decision's own entry is `edit_unfinished` (a cited source whose own input fails live validation).
- `replace-decision --decision r01` replaces r01 in place: g01 becomes unresolved under the same key, citing the HC entry as it is now. It changes r01's fingerprint, so a decision citing r01 needs its own review. `replace-decision --decision v01` keeps its checkpoint-H meaning (v01 dropped, v02 added), which removes the record a decision citing v01 read.
- `refresh-dependents` does nothing for saved records: there is no remap, and a refresh revision keeps the fingerprints, so its citers stay valid.

## Forget of a cited source

A source that cites the forgotten source's records is a level-1 dependent (`dependency.Target.sources`), like one that reads its document. Its removal revision makes a citing resolution unresolved and drops a citing variant, under the removal producer, and the erasure rules admit it: `erasure_rules.Erasures.sources` maps each forgotten document to its identity source from the ledger, so `erasure_of` erases that source's records with its document.

**The cascade (checkpoint J2, 2026-10-24).** A decision that cites a record a removal removes, as that record was before the removal, is a dependent one level below, and so on down the chain. Each dependent has one removal revision at its longest path. One dry run lists every level, one token covers them, and one confirmation writes them in level order. The removal producer lists the records it removes (`removed_records`) and the removed records it cites (`cited_records`), and admission binds the cited ones inductively back to the tombstone. A removed record carries its pre-removal fingerprint and the last revision that held it, so only a citation made before the removal is cascaded. The [forget guide](stage6_identity_forget.md#the-cascade) states the rules. Before J2, `erasure.impact_checked` refused such a forget with `chain_erasure_pending`; it is gone.

The fence (`erasure.refuse_retiring_inputs`) refuses, with `retiring_source`:

- a description that reads the document, a removed Entity or a saved record of a source whose forget is pending or failed;
- a citation of any record that a removal revision of a forget not finished will remove, at any level: one pending or failed (by its saved plan) or one completed with dependents left (`erasure.under_way`), as the record is now. The fence simulates the cascade from the rows, so once a forget is confirmed what it removes can only shrink (review resolution 13). J1 covered level 1 only.

## The chain fixture

`glossary-fixture --chain --root <new dir>` creates the glossary root and adds doc03, published after doc01 so that its citations pin doc01's revision 1.

| Object | Value |
|---|---|
| doc03 identity source | `bbbc442e-0647-552e-bb54-071604d213fa` |
| doc03 original document | `ddded294-0cca-5867-944a-a426362d5638` |
| doc03 mention g31 (`The regulator`, [16, 29)) | `143d0568-16d0-5d16-87e5-f1851c69247e`, `uuid5(doc03 identity, "mention:r1:g31")` |
| r01's fingerprint at revision 1 | `1d2e89138501ae78c356a9d46cc9f49f6a4535928cb10f81c356fbd4b4e67c85` |
| v01's fingerprint at revision 1 | `6a89916921b8c21be7689812bd0e7032b7ce38162bc701222a0e23db18446aff` |

doc03's text (61 code points, digest `a34ab653d1dd8d0fb78bd5b197d9267711282570bbf596be7a49d6abff3eb09d`) is:

```text
Operations log

The regulator kept HC stable during the run.
```

c01 resolves g31 to the Helios controller and lists `["doc03", "doc01_r01"]`. c02 says HC is the Helios controller within doc03 and lists `["doc03", "doc01_v01"]`. doc03 declares recipes for both reusable Entities and has no captured facts, so the HC and Helios controller queries return doc01's fact only; `retrieve` and `status` show doc03's decisions in `unavailable_sources` and `withheld_decisions`. The glossary's HC entry, doc01's r01 and v01, and doc03's c01 and c02 make three levels.

Each glossary command's result gains, per source, `records` (the saved-record inputs) and each decision's `status`.

`cite-record --source doc01|doc03 --citation <case> --expected-revision N` writes the next revision of the citing source with one new citation under a new producer (`chain_fixture.cite`), and admission refuses it:

| Case | Citing source | What it cites | Refusal |
|---|---|---|---|
| `cycle` | doc01 (v01) | doc03's c02 | `citation_cycle` |
| `self` | doc03 (c01) | doc03's c02 | `self_citation` |
| `missing` | doc03 (c01) | doc01's `r99` | `record_missing` |
| `stale` | doc03 (c01) | doc01's r01 at the next revision | `record_stale` |
| `digest` | doc03 (c01) | doc01's r01 with another fingerprint | `record_digest` |

The CLI prints a refusal's message, not its code, so the journeys check messages and the unit tests check codes.

## Commands

From the repository root, with a new root each time:

```bash
uv run python -m cognee_lab.identity glossary-fixture --chain --root outputs/stage6_chain_check --embedding loopback
uv run python -m cognee_lab.identity edit-glossary --root outputs/stage6_chain_check --source glossary --case cosmetic --expected-revision 1
uv run python -m cognee_lab.identity status --root outputs/stage6_chain_check
uv run python -m cognee_lab.identity reconfirm --root outputs/stage6_chain_check --decision r01 --expected-revision 1
uv run python -m cognee_lab.identity reconfirm --root outputs/stage6_chain_check --decision v01 --expected-revision 2
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_chain_check
```

Expected: after the edit, `status` withholds r01 and v01 (`refresh_needed`) and c01 and c02 (`upstream_withheld`), and `refresh_needed` lists only r01 and v01. After both re-confirms nothing is withheld and doc03 is still at revision 1.

Journeys D7 to D11 in `.claude/skills/verify/features/dependencies.md` cover the chain hold, the release by an upstream re-confirm with no doc03 revision, the replacement under a new key, the in-place replacement with doc03's re-confirm, and the refused citations with the glossary's two-level dry run, the level-1 removal and an unfinished upstream. Journeys F16 to F19 in `source-lifecycle.md` cover the cascade (J2).

## The checks

- **`support/chain_check.py`**, bounded exhaustive. On every citation graph of up to four sources (`support/chain_worlds.py`: each source has a resolution `d` and a variant `v`; a source that cites another cites its `d` from its `d` and its `v` from its `v`), it checks that admission refuses a source's citations if and only if a path of citations leads back to it (16,384 cases on four sources), and, on each of the 543 acyclic graphs with every source in each of eight states (ok, held by a table row on `d`, both decisions replaced in place, `d` rekeyed, pending, unverified, withdrawn, own input invalid), that the withheld-decision set equals an oracle written from the user's decisions: reason, status and withholding inputs per decision (2,224,128 worlds). The held and rekeyed states touch `d` only, so the check shows withholding follows the decision, not the source. The code under test is `check_citation_cycles`, `record_reader`, `withheld_decisions` and `live_pass` itself; only `retrieve.live_drift` is replaced, by a drift built from the reader that raises for an invalid source. `--mutants` breaks the cycle check, the closure (one level instead of the whole chain) and the reader (a removed record read as changed), and each must fail. CI runs it at four sources (about 200 s since fix round 1, up from 67 s, for the eighth state and the variant); the unit suite runs three sources and every mutant.
- **The occurrence check** calls `chains.check_citation_scope` before `admit`, as a replacement's preflight does, and patches it in `chains` for its mutant. It gains nine rule-5 rows in `support/dependency_worlds.py` (self-citation; another dataset; a new citation under a new and under the old producer; a dropped citation under the old and under a new producer; a changed digest and a changed revision under an old key; a continuing group citing a saved record) and three rule-6 rows in `support/erasure_worlds.py` (a removal that unresolves a resolution or drops a variant citing the forgotten source's record, admitted; one that keeps the citing resolution, refused). The old row "saved-record input", refused as `not_admitted`, now refuses as `self_citation`, since its citation named the citing source. Two mutants: saved records not foreign, and self-citation allowed.
- **The cascade half of `support/chain_check.py`** (J2, `support/cascade_check.py` over `support/cascade_worlds.py`). With s0 forgotten and every other source ok, blocked (a failed withdrawal), drifted (its `d` cites at an older fingerprint) or reconciled (served, then a reconcile at the same revision failed; fix round 1), on every acyclic graph of up to four sources (34,752 worlds since fix round 1, 14,661 before), it checks the dry run's levels, removed decisions and cited records against an oracle written from the user's decisions; that the token tells apart any two different cascades; that admission admits each removal written in the cascade's order and refuses (`erasure_unbound`) a removal below level 1 before its upstream is written, or below a removal written out of order; that the cascade read again after each write plans the same revisions; that what is left waits for a blocked removal; that a removal below level 1, saved by a failed attempt, resumes at its level and leaves the cascade once its upstream withdraws, with no reader raising (fix round 1); and that no new citation the fence, the record checks and the cycle check admit, while the forget is pending or after any write, adds a removal outside the confirmed token. Its seven mutants: a one-level cascade, the steps in source order, a gate without induction, a level-1 fence, a removed record read at any fingerprint, and since fix round 1 a removal in place that takes the revision before as last served, and a removal that binds though a record it cites has no remover. Each mutant replaces every module binding of what it breaks.
- **Unit tests** in `tests/test_identity_chains.py` pin the fingerprint, the admission codes, the reader, the derived rule, the closure and the small-bound chain check. **Native tests** in `tests/test_identity_chains_native.py` drive the chain, the replacements, the refusals with the level-1 removal, and an unfinished upstream through the real stores.

## Choices the assistant made

The spec left these open or worded them two ways. Each is reversible.

- **The closure is a fixpoint, not a topological pass.** It gives the same set on an acyclic graph and does not loop on a cycle a race could leave. The chain check's one-level mutant shows it spreads further than one citation.
- **Only the live pass applies the closure.** `withholding.withheld_decisions` (the rows and the derived rules) stays direct, so admission's skip set and retrieval's consistency recheck read no closure. Retrieval and `status` both run `chains.live_pass`, so they agree.
- **An unverified cited source** (current, but its verified revision behind its saved one) is unfinished, `input_changed` and `edit_unfinished`, like a pending one. Before fix round 1 it showed `refresh_needed` and offered a review that `record_source_unavailable` then refused.
- **The review gate waits for every source the reviewed source cites**, not only the one its decision cites, as checkpoint H waits for every document doc01 reads.
- **`cite-record`** is a fixture command for the refused citations, so the journeys drive admission through the CLI.
- **The original fixture's captured groups belong to its lineage.** `captured_chunks.CAPTURED_GROUPS` names the original fixture's producer (`identity-handoff-example`) as g01's creator instead of none. Before, every source without a g01 counted g01 as retired, so an unchanged-text replacement of doc03 failed its semantic verification; the glossary avoided it only by passing no verifier.
- **A source's citation of a record of the forgotten source counts as reading it** for the fence and for `erasure.unfinished`, so a level-1 removal finishes like any other.
- **Record checks run before the reservation only** (review finding L1, dismissed). `check_record_citations` reads the rows in `admit_inputs`, before `begin`, and not again under the writer reservation. A record that drifts between the check and `begin` is caught by live withholding: the citation fails the reader at the next retrieval and its decision is withheld, as any drift is. A retry must reuse its saved intent, so a later recheck could only refuse a retry forever (resolution 5).
- **Removals stay decision-shaped** (J1). `erasure.removed_records` and `impact_checked` named a removed record by its decision key. Since J2 a removed record is a `records.RemovedRecord` (source, type, key, fingerprint, last revision), and each record type says how it is removed (`RecordKind.removed`).

## Not in this checkpoint

- The erasure cascade was J2, built on 2026-10-24.
- Facts as citable records (user decision 1).
- A citation's `representation_revision` is not checked after the first attempt, by design. Nothing records which revision a re-confirm saw beyond the new citation's pin.
- Per-decision acyclicity. The source-level rule refuses mutual citation between two sources even when no decision cycle exists.

## Evidence

Run by the assistant on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-chains`; every source file as at `134e046`.

- `uv run pytest -q -m 'not integration'`: 482 passed, 85 deselected.
- `uv run python support/chain_check.py`: PASS, 0 disagreements on 543 acyclic graphs, 16,384 cycle cases and 1,303,743 withholding worlds (67 s). `--mutants`: all three breaks caught.
- `uv run python support/occurrence_check.py`: PASS on all 540,045 fate worlds, with the new decision rows (119 s). `--mutants`: every break caught, including `saved_records_not_foreign` and `allow_self_citation`.
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, `PINNED` unchanged at 8504 nodes and 8349 sequences; `RecordStore` is unchanged. `--mutants`: every break caught.
- `uv run pytest -q -m integration tests/test_identity_chains_native.py`: 4 passed (96 s). With `tests/test_identity_dependencies_native.py` in an earlier run of the same code: 8 passed. `tests/test_identity_forget_native.py` with `tests/test_identity_erasure_retry_native.py`: 28 passed (592 s).
- Journeys D7 to D11: D7 16, D8 9, D9 9, D10 11 and D11 18 PASS rows, 0 FAIL. D1 to D6: 128 PASS rows, 0 FAIL, the same total as at checkpoint H. G1 to G4: 109 PASS rows, 0 FAIL. F1 to F15, for the erasure changes: 363 PASS rows in 27 runs, 0 FAIL. Each count includes three lab-store guard rows per run. `journey all` was not run.

The values in this guide come from these runs: doc03's UUIDs and fingerprints from D7's `doc03_identity.json`.

## Fix round 1

A review of the checkpoint on 2026-10-23 raised two bugs and eight quality items. The assistant fixed them on the user's Mac the same day, on branch `stage6-chains`, with loopback embeddings.

- **M1, fixed** (`95ae5b7`). A forget whose level-1 removals were not all written let a new source cite a dependent's record that the removal then removed. The fence now refuses it, and the resume path of a completed forget runs the interim refusal too. Unit tests cover a pending, a failed and a completed forget.
- **L2, fixed** (`89ff8d3`). An unverified cited source showed `refresh_needed` and offered a review the reviewer could not complete. It is now unfinished (`edit_unfinished`), by the one rule in `withholding.unfinished`.
- **L1, dismissed.** Record checks run before the reservation only; see [Choices the assistant made](#choices-the-assistant-made).
- **Quality** (`89ff8d3`, `3a7e757`). The closure asks each record type's `held` hook; the live pass is `chains.live_pass`, which the chain check runs; the reader and `held_by` live in `withholding.py`, `is_served` is `PublicationRow.is_served` and `cited_row` serves both record lookups; the duplicate unfinished steps and the unused `withheld_by` are gone; `review.py` holds the reviewer commands and `cite-record` is one call; `check_citation_scope` runs once; the interim refusal is one function, `impact_checked`; `retirement.consumes` takes a `Target`.

Evidence, run by the assistant on the user's Mac on 2026-10-23, every source file as at the fix round's last commit:

- `uv run pytest -q -m 'not integration'`: 487 passed, 85 deselected.
- `uv run python support/chain_check.py`: PASS, 0 disagreements on 543 acyclic graphs, 16,384 cycle cases and 2,224,128 withholding worlds (200 s). `--mutants`: all three breaks caught.
- `uv run python support/occurrence_check.py`: PASS (119 s). `--mutants`: every break caught.
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, `PINNED` unchanged at 8504 nodes and 8349 sequences. `--mutants`: every break caught.
- `uv run pytest -q -m integration tests/test_identity_chains_native.py tests/test_identity_dependencies_native.py tests/test_identity_forget_native.py`: 36 passed and 1 failed (891 s). The failure was the fence's new refusal message, which dropped the words a native test checks; the message was restored and that test passed alone.
- Journeys, 41 runs, 0 FAIL: D1 to D6 128 PASS rows, D7 to D11 63, G1 to G4 109, F1 to F15 363 in 27 runs, the same totals as before the round. `journey all` was not run.

## Checkpoint runs

Run by the assistant and its subagents on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-chains`.

- `verify.py journey all`: 1519 PASS and 0 FAIL in 86 runs on `637bfcc`, and again on `8167c25`. P5 calls the embedding API and was skipped.
- `uv run pytest -q -m integration tests/test_identity_chains_native.py tests/test_identity_dependencies_native.py tests/test_identity_forget_native.py`: 37 passed (837 s) on `8167c25`, after the fence's message was restored.
- `support/occurrence_check.py` now holds 33 rule-5 rows and 23 rule-6 rows in all.
- A final targeted review of `8167c25` found the branch merge-ready. `2002a77` changed the fence's remedy to "run forget on that source again first" and corrected the citation-scope comment in `support/occurrence_check.py`.
- `uv run pytest -q -m 'not integration'` on `2002a77`: 487 passed, 85 deselected.

## Checkpoint J2

The assistant (a subagent) ran these on the user's Mac on 2026-10-24 with loopback embeddings, on branch `stage6-cascade`. The [forget guide](stage6_identity_forget.md#evidence) has the full list.

- `uv run python support/chain_check.py`: `PASS`, with the cascade half on 14,661 worlds (312 s for both halves). `--mutants`: all eight breaks caught.
- `uv run pytest -q -m 'not integration'`: 503 passed, 87 deselected.
- Journeys D7 to D11: 63 PASS rows, 0 FAIL. F16 to F19: 46 PASS rows, 0 FAIL.

## Checkpoint J2 fix round 1

A review of checkpoint J2 raised two probed bugs, a low one, a Checkpoint I defect the cascade made reachable, and eight quality items. The assistant (a subagent) fixed them on the user's Mac on 2026-10-24, on branch `stage6-cascade`, with loopback embeddings. The [forget guide](stage6_identity_forget.md#evidence) lists each fix with its commit. For chains:

- A removed record's `last_revision` is its last served revision, from the ledger's verified revision. A reconcile of a served row that failed at the same revision no longer drops that row's citers from the cascade.
- A failed removal revision whose upstream retired leaves the cascade, as a citer of a withdrawn intermediate does. Its own retry stays refused (`erasure_unbound`); for a failed replacement or text change that is open, since a way out changes the binding rule.
- The record registry carries every record-type fact the erasure reads.

Evidence: `support/chain_check.py` `PASS` with 34,752 cascade worlds in 389 s, `--mutants` all ten breaks caught; 511 unit tests passed; journeys D7 to D11 63 PASS rows and F16 to F19 48, 0 FAIL. The forget guide has the full list.
