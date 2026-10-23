# Stage 6 dependencies: withhold the decisions an edit affects

**Date:** 2026-10-23. **Status:** checkpoint H, implemented and verified by the assistant on the user's Mac with loopback embeddings. No user-reviewed fixture root exists yet.

A source can read another document: a glossary entry, a protocol, a calibration record. Before this checkpoint, a text edit of a document that another saved source read was refused (`dependent_source`), and the dependent could not be revised at all, because admission accepted one text per description and refused span inputs. Now the edit goes ahead. It withholds from retrieval only the decisions that read what changed, and only until they are refreshed.

The user decided this on 2026-10-22 and 2026-10-23:

1. When a consumed input changes, affected dependents are withheld from retrieval until refreshed. They are not blocked, and they are not served with a stale flag. The unit is one decision: only decisions whose inputs cite the changed input are withheld, with the facts generated from their groups. Refresh starts at once: the edit records the withholding before it completes, mechanical re-checks run at once, and anything that needs judgment becomes a "refresh needed" item. Today a reviewer clears it; once Describe exists (step 6) the same trigger runs Describe.
2. Erasure's effect on dependents is not in this checkpoint. `forget` still refuses a source with dependents.
3. A reviewer may re-confirm a withheld decision. A re-confirm records the new fingerprint and who confirmed it; no IDs change. The table of outcomes by input kind is below.
4. The first example is a glossary.
5. Users see the reasons "input changed" (`input_changed`) and "input removed" (`input_removed`), never "input forgotten".

These decisions supersede the design handoff's "callers select whole documents" ([Stage-6 handoff](../results/cognee_identity_stage6_handoff.md)): the unit of withholding is one decision, not one document.

| Input the decision read | What changed | Outcome in this checkpoint |
|---|---|---|
| A span of another document | Its text unchanged in place | Valid automatically |
| A span | Its text found exactly once elsewhere in the new text | Moved: withheld until the refresh writes its new range, then valid |
| A span | Its text changed, or now appears more than once | Needs review; may be re-confirmed |
| A chunk of another document | Any edit | Needs review (no fingerprint; renumbered) |
| The whole text of another document | Any change | Needs review; may be re-confirmed |
| An existing Entity (corpus input) | A field the decision read | Withheld at retrieval with `input_changed`; may be re-confirmed |
| An existing Entity | Only fields the decision did not read | Valid automatically |
| An existing Entity | Gone | Withheld with `input_removed` |
| A saved record of another source | Not supported yet | Admission refuses saved-record inputs |
| Something depending on a withheld decision | Deferred | Needs saved-record inputs; see "Not in this checkpoint" |

## The data shapes

- **A withholding row** (table `lab_identity_withholdings`, module `withholding.py`): one decision of a dependent withheld because one input it read changed. Key (dataset, dependent source, assignment, input key). Fields: the edited source (`consumed`) and its revision (`edit_revision`), `reason`, `status` (`remap` or `refresh_needed`), `old_digest`, `new_digest`, and for a moved span its `new_start` and `new_end`. Keying by input lets a later checkpoint chain withholdings through saved records.
- **The classification of one input** (`Classified`): what an edit did to one input that a dependent read from the edited document: `unchanged`, `moved` (with the new range) or `changed`, with the old and new digest. A span's text is found in the new text by its length and digest, never by slicing an earlier text, so a retry of an edit, or an edit after a move that was not refreshed yet, classifies the same way as a first attempt.
- **The withheld-decision set**: source, then assignment, then (reason, status, the input keys that withhold it). `withheld_decisions(rows, table)` merges the rows that still apply with a rule derived from the ledger: while a consumed source's text change is pending or failed, every decision citing that document is withheld with `input_changed` and status `edit_unfinished`. Validation callers read it as their skip set. `withheld_now(publisher, rows)` adds what live validation finds (below); `retrieve`, `status` and the reviewer commands read that full set, so they agree.

The table lives beside the ledger, not in `RecordStore`. `RecordStore`, the ledger model, `TRANSITIONS` and the ledger check's `PINNED` counts are unchanged. Withholding writes no recovery events.

## How an edit withholds

1. **The edit's own attempt.** A text change runs the stage `withhold_dependents` after `replace_saved` and before `text_removal`. It reads every current dependent of the edited document, classifies each input the dependent read from it against the new text, and replaces the rows of each such input in one transaction. An unchanged input has its rows deleted. The stage is idempotent: a retry, or a later edit, recomputes the rows.
2. **Durability.** From `begin` to completion the edited source's row is pending or failed with a saved text change, and the derived rule withholds every decision citing its document. So a crash before the rows are written never serves a dependent stale, and a failed edit keeps its dependents withheld until `reconcile` finishes it. After completion only the rows apply.
3. **The refresh.** After the edit completes, the same command runs `refresh_dependents`. Every text-change command does: `edit-glossary`, `edit-text`, the occurrence commands and a `reconcile` that completes a text change (through `text_fixture.maintain_one` and `glossary_fixture.change_glossary`). Each current dependent with a moved span gets an ordinary unchanged-text replacement: the next revision, with the span's new range, the same digest and no decision or producer change. The writer reservation forbids nesting this inside the edit. A moved decision stays withheld until that revision completes. A dependent whose refresh revision failed is resumed by the next run of `refresh-dependents` (or by `reconcile`). Recovery is forward only: while `remap` rows apply to a dependent, `refresh_dependents` completes whatever replacement of that dependent failed, a reviewer's re-confirm included, with its saved revision, not only a refresh revision. A span moved by an edit that is still unfinished waits for that edit.
4. **Cleanup.** Every replacement runs the stage `withholding_cleanup` before publication. A row carries forward across a dependent's revisions until its input validates, or the decision no longer cites the input, or the decision is gone. Rows of a withdrawn or forgotten source are ignored, and a re-add clears them.

Each refreshed dependent gains a revision with no decision change. In the fixture, the insertion takes doc01 from revision 1 to 2.

## Validation per input

`validate_inputs` now classifies each input. An own input that fails (the document's own text, a chunk of it, an occurrence) still raises and fails the source. A foreign input, meaning another document's text, span or chunk, or a corpus object, is returned with `input_changed` or `input_removed`, and `withheld_by` maps it to the decisions that cite it. A resolution is one unit with its group, so it cites its group's inputs too; a variant is withheld on its own and cites its scope's document. A decision citing several inputs is valid only when all of them are.

- A foreign text is digest-checked only when a decision that is not withheld cites it directly. A text reached only as a span's document is read, not digest-checked, so a change elsewhere in the glossary leaves the span valid.
- The inputs of withheld decisions are not checked at all (the skip set). Admission, publication verification and retrieval all pass it.
- `valid_sources` no longer fails a source for foreign drift. A changed corpus field that a decision read is found here, at retrieval, per decision; no new trigger watches native Entity edits.
- Admission keeps one hard rule on corpus objects: every corpus input a decision lists names an Entity in the graph (`check_corpus_inputs_exist`, `missing_reasoning_input`). `referenced_corpus_ids` relies on it to exempt an existing Entity from the derived-UUID rule, so a missing one is refused, not withheld. Retrieval and publication verification withhold its decisions with `input_removed` instead.
- `read_texts` leaves out another document whose Data item is gone, so its span reads as `input_removed`.

## Admission: other documents' inputs (rule 5)

`check_source_identity` used to accept exactly one text per description and refuse span and saved-record inputs. These rules replace that, after the variant rules and before the changed-text rules:

| Rule | Code | Admits or refuses |
|---|---|---|
| `check_input_kinds` | `not_admitted` | A text input other than the original is a different document of the same dataset. Span inputs are admitted. Saved-record inputs are refused. |
| `check_foreign_inputs` | `foreign_input_changed` | Another document's input, or a corpus object, that both descriptions hold under one key keeps its kind, document and digest. Only a span's range may change, with its digest unchanged: a pure move. A changed input takes a new key. An uncited key may be dropped. |
| `check_reconfirmations` | `reconfirm_unattested` | A resolution or variant that keeps its reviewed fields but cites other foreign inputs, its group's included, names a producer new in this revision. Losing, replacing or adding a foreign key all count. |

The occurrence check's `DECISIONS` table gains 17 rows for rule 5, each stated for a text edit and for unchanged text, and `support/occurrence_mutants.py` gains four breaks: one per rule, and `reconfirm_by_own_refs`, which reads a decision's own `input_refs` without its group's.

`TextChange.preflight` compares only the edited text; the fixture drivers supply other documents' texts from `read_texts`.

## A text edit no longer refuses its dependents

`reject_dependents` is gone from `text_changes.py`. One refusal stays, as `reject_sole_owned_readers`: a text edit that drops a reusable recipe which only the edited source owns, while another source reads that Entity as a corpus object, is refused with `dependent_source`, because the Entity would leave the graph. Forget keeps its own dependents refusal.

## Retrieval and status

- A withheld resolution is served like an unresolved one: its local fact stays in the graph, and no identity query reaches it. A withheld variant is skipped in identity expansion. Facts attached directly to a reusable Entity do not depend on a decision and stay served.
- `unavailable_sources` keeps one list. Each entry gains `assignment_id`: `null` for a whole source, or the withheld decision, with its `reason`. A withheld decision has `recovery_event_id` `null`.
- The final consistency recheck also compares the withheld-decision set; a change during the read raises `retrieval_changed`.
- `status` lists `withholdings` (the rows that still apply), `withheld_decisions` (the set retrieval applies, with status and `input_refs`) and `refresh_needed` (the decisions a reviewer must answer). It reads the graph and the registered texts, like retrieval: a decision withheld only by live validation (a changed corpus field, a foreign chunk that is gone, a span that is stale after a re-add or at a first publish) has no row, and appears with status `refresh_needed`.
- When several inputs withhold one decision, it shows `edit_unfinished` over `refresh_needed` over `remap`, and `input_removed` over `input_changed`.

## The glossary fixture

`glossary-fixture --root <new dir>` creates one dataset with doc01 and a glossary, both published at revision 1.

| Object | UUID |
|---|---|
| doc01 identity source | `718efce2-4251-5f6f-8318-417bb4dd3525` |
| doc01 original document | `50d5313b-0fee-5945-b1d5-5c1d37a6f880` |
| glossary identity source | `16e89187-1559-5f97-b957-d86f46315407` |
| glossary original document | `8c6f6b13-ea82-5a5f-a557-3c0be4808b61` |
| doc01 mention g01 | `233cb019-3986-5864-88bc-91f334a64372` |
| Helios controller (seed document, corpus input `existing_A`) | `8b4bff50-907b-56b6-bc80-3b0a7018714a` |
| HC | `9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88` |

The glossary text at revision 1 (84 code points, digest `dde5da8f01aeea8b0d79d22a3a9897aff9fb4015e9756ee5e440551e92a64c3e`):

```text
Glossary

HC: Helios controller, the plasma heating regulator.
RF: radio frequency.
```

The glossary's description has no groups and no decisions, and a complete chunk map: one chunk at the 512-token budget, [0, 84), `215ded10-e96c-59e0-af44-38d65951bd07` at revision 1. doc01's description is the standard doc01 with two more inputs: `glossary`, the glossary's text, and `glossary_hc`, the HC entry as a span at [10, 62), digest `d867939748ac2edeb4521a439cd7ff1d96d4e26bf8cccabb0a49b4bf10b4d66f`. Both r01 (g01 `The controller`, `it` to the Helios controller) and v01 (HC to the Helios controller, doc01 scope) list `["doc01", "existing_A", "glossary_hc"]`. Neither cites the glossary text directly.

The HC query ("What does HC limit?") returns the `it limits oscillations` fact through v01 and r01. The Helios controller query returns it through r01.

## The four edits

Each `edit-glossary --source glossary --case <case> --expected-revision N` edits the current glossary text, so the cases can follow one another. A case refuses with `fixture_shape` when its text is missing.

### A change elsewhere

`--case elsewhere` replaces `RF: radio frequency.` with `RF: radio-frequency heating.`. The span is unchanged in place, so nothing is withheld and doc01 stays at revision 1. The glossary text digest changed, but no decision cites the text directly.

### An insertion before the entry

`--case insert` inserts `ECRH: electron cyclotron resonance heating.` and a line break (44 code points) before the HC entry. The entry's text is found once, at [54, 106). The edit writes two `remap` rows (r01 and v01), and its refresh writes doc01 revision 2 with `glossary_hc` at [54, 106) and the same digest. The cleanup stage deletes both rows, so nothing stays withheld. The glossary text input in doc01 keeps its revision-1 digest: an existing foreign input keeps its digest, and no decision reads the text directly.

### A cosmetic change

`--case cosmetic` changes `plasma heating` to `plasma-heating` inside the entry. The span's text changed, so the edit writes two `refresh_needed` rows with old digest `d8679397...` and new digest `98df70d0ec0d2d79a639fd1e462355807c98bbc93ee2e03a3f02620fcd660c27`, the digest of what is now at [10, 62). Both queries return no fact, and `retrieve` lists r01 and v01 as unavailable with `input_changed`.

A review (`reconfirm` or `replace-decision`) works from the set retrieval applies, so it also answers a decision that only live validation withholds. It refuses while any document doc01 reads has an edit that is pending or failed (`edit_unfinished`), so the reviewer attests committed text, and `reconfirm` refuses a decision withheld with `input_removed`: a removed input is replaced, never re-confirmed.

`reconfirm --decision r01 --expected-revision 1` re-confirms r01 on the current entry, copy-on-write: doc01 revision 2 adds the input `glossary_hc_r2` (the entry at [10, 62), digest `98df70d0ec0d2d79a639fd1e462355807c98bbc93ee2e03a3f02620fcd660c27`), r01 cites it, and r01 names the new producer `review_r01_r2`: method `captured_fixture`, implementation `re-confirmed`, configuration with `confirmed_by`, the withholding it answers, the old digests and the new digest. v01 still cites `glossary_hc` and stays withheld, so the Helios controller query returns the fact and the HC query does not. `reconfirm --decision v01 --expected-revision 2` gives v01 `glossary_hc_r3` under `review_v01_r3`; `glossary_hc` is no longer cited and is dropped. Nothing is withheld.

A `human_review` producer method is a later schema change; until then a re-confirm uses `captured_fixture` with implementation `re-confirmed`.

### A substantive change

`--case substantive` replaces the entry with `HC: hybrid coil, the auxiliary magnet winding.` at [10, 56), digest `136a2c4fb64680e0e8b982bea26414f7c4d6c96a2f5cb78fd5662fe963f6e2cf`. Both decisions need review. `replace-decision --decision v01 --expected-revision 1` drops v01 and adds v02: HC to a new "Hybrid coil" Entity, `769245ce-d23e-5154-a35a-fb8ecd2860e2`, which is `uuid5(doc01 identity, "entity:r2:v02")`. v02 cites `["doc01", "glossary_hc_r2"]` under producer `review_v01_r2` (implementation `replaced`). r01 stays withheld until `reconfirm --decision r01 --expected-revision 2`. Then the HC query returns no fact, because HC now names the hybrid coil, and the Helios controller query returns the r01 fact.

## A failed edit

`edit-glossary ... --fault-stage <stage>` fails the edit with a recovery event. While the glossary is failed, `retrieve` lists the glossary (`publication_failed`, `assignment_id` `null`) and r01 and v01 (`input_changed`) as unavailable, and `status` shows both decisions as `edit_unfinished`. Before `withhold_dependents` has run there are no rows; the derived rule alone withholds them. `reconcile --source glossary` completes the edit, refreshes doc01 to revision 2 and resolves the incident as `restored`.

## An interrupted refresh

`edit-glossary --case insert ... --fault-stage refresh_interrupted` completes the glossary edit, then fails doc01's refresh revision at `replace_registered`. doc01 is failed and unavailable as a whole source, and the two `remap` rows keep [54, 106). `refresh-dependents` resumes doc01's saved revision 2; its cleanup deletes the rows and the incident is `restored`.

## A re-add after an interrupted refresh

Glossary roots take `forget` and `readd` for doc01. In the native test, the insertion's refresh is interrupted and finished, doc01 is forgotten, the entry moves again, and doc01 is re-added with the range it had. No edit classified that move, and the re-add clears doc01's rows. Live validation finds the stale span: `retrieve`, `status` and `reconfirm` all see r01 and v01 as `input_changed` with status `refresh_needed`, and two re-confirms release them. The move is not remapped automatically, because only an edit's own attempt classifies a move.

## Commands

From the repository root, with a new root each time:

```bash
uv run python -m cognee_lab.identity glossary-fixture --root outputs/stage6_glossary_check --embedding loopback
uv run python -m cognee_lab.identity edit-glossary --root outputs/stage6_glossary_check --source glossary --case cosmetic --expected-revision 1
uv run python -m cognee_lab.identity status --root outputs/stage6_glossary_check
uv run python -m cognee_lab.identity reconfirm --root outputs/stage6_glossary_check --decision r01 --expected-revision 1
uv run python -m cognee_lab.identity reconfirm --root outputs/stage6_glossary_check --decision v01 --expected-revision 2
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_glossary_check
```

Expected: after the edit, `status` lists two `refresh_needed` items (r01, v01) and no recovery event; after both re-confirms, doc01 is current at 3/3/3, nothing is withheld, and `retrieve` returns one fact through r01. Each glossary command writes `glossary_result.json` and prints the same document: `sources` (revision triple, `glossary_spans`, `decisions`, `producers`), `glossary` (text and HC entry), `withholdings`, `withheld_decisions`, `refresh_needed`, `refreshed`, `result` (the HC query), `helios` (the Helios controller query) and `recovery_events`.

## Behavior changes

- A text edit of a document another source read is admitted. Before, it was refused with `dependent_source`.
- A changed or missing corpus field that a decision read withholds that decision, not the source. Before, retrieval failed the whole source and wrote a recovery event (`input_changed`, `missing_reasoning_input`); now no event is written and the reason is `input_changed` or `input_removed`.
- `unavailable_sources` entries gain `assignment_id`; `status` gains three lists.
- Admission accepts other documents' texts and spans under rule 5.
- Replacement has two more stages, `withhold_dependents` (text changes only, a fault stage) and `withholding_cleanup`.

## Not in this checkpoint

- The transitive case. A decision that depends on another source's withheld decision needs saved-record inputs, which no source can declare yet. Rows are keyed by input so chains can be added.
- Erasure's effect on dependents (user decision 2).
- A trigger for native Entity edits. Corpus-field drift is found when retrieval or a revision validates the dependent.
- Remapping for moves across documents and span-scoped variant ranges; both count as a change.
- A chunk of another document has no refusal rule. It needs review through the generic classification; the fixture has none.
- The CLI picks the glossary driver for `reconcile`, `forget` and `readd` by the root's `glossary-fixture-info.json` file. A fixture-kind field in the root marker would replace that check; it is a separate cleanup.

## Choices the assistant made

The spec left these open or worded them two ways. Each is reversible.

- **The foreign text digest after a move.** Review resolution 9 says the refresh revision has a "refreshed digest"; resolution 5 says an existing foreign input keeps its digest. The refresh keeps the glossary text input's old digest and changes only the span's range, because resolution 5 is the admission rule and resolution 3 says a text reached only as a span's document is not digest-checked. A decision that cites the text directly is re-confirmed under a new key, like a span.
- **Uncited keys.** "Uncited input keys are dropped" is read as permission, not a refusal: admission lets an old key disappear, and the re-confirm and replacement describers drop the key nothing cites any more. A refusal would have changed an existing occurrence-check row (a corpus input that nothing lists, admitted on a retry).
- **The re-confirm rule** checks a resolution's and a variant's own `input_refs`. The re-confirm describer also moves the resolution's group to the new key, so the unit stays consistent.
- **An edit with equal texts** changes no input: a chunk is classified as changed only when the text changed.
- **A foreign chunk that is gone** reads as `input_changed`, not `input_removed`: rechunking replaces it, and "removed" is kept for a document that is gone.
- **Statuses.** The derived rule's entries have status `edit_unfinished`. When several inputs withhold one decision, it shows `edit_unfinished` over `refresh_needed` over `remap`, and `input_removed` over `input_changed`. Fix round 1 moved `edit_unfinished` above `refresh_needed`: a review must wait for the edit.
- **Live drift needs review.** A decision withheld only by live validation gets status `refresh_needed`, even when its span merely moved; `refresh_dependents` remaps only what an edit's own attempt classified.
- **A review waits for every document doc01 reads**, not only the one its decision cites, and `replace-decision` waits too, because it also attests the current entry.
- **Validation never fails for foreign drift**, also at admission and publication verification, with one exception: admission refuses a listed corpus input whose Entity is missing. A drifted input that no row records is still withheld at retrieval, so the rows are the durable record and live validation is the backstop.
- **The refresh resumes a failed replacement.** `refresh-dependents` retries a dependent that is failed with a saved replacement while `remap` rows still apply to it, whichever command saved it; `reconcile` does the same.
- **The fault `refresh_interrupted`** is a fixture-only fault stage for `edit-glossary` and `refresh-dependents`. It fails doc01's refresh revision at `replace_registered`.
- **The fixture's doc01** is the single-document `fixture` description (no g02), plus the two glossary inputs. r01 and v01 keep `existing_A`.

## Evidence

Run by the assistant on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-dependencies`. Every source file is as at `4681f60`; later commits change only documentation.

- `uv run pytest -q -m 'not integration'`: 389 passed, 64 deselected.
- `uv run python support/occurrence_check.py`: PASS on all 540,045 fate worlds, with the 13 new `DECISIONS` rows each checked on every admitted world that allows it (116 s). `--mutants`: PASS, all 28 breaks caught, including `allow_any_input_kinds`, `allow_changed_foreign_inputs` and `allow_unattested_reconfirms`.
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, with `PINNED` unchanged at 5889 nodes and 5770 sequences. `--mutants`: all 40 breaks caught as before.
- `uv run pytest -q -m integration`: 64 passed in 1366 s, including the five tests in `tests/test_identity_dependencies_native.py` (the four cases in sequence with both re-confirms and the replaced variant, a failed edit at `replace_saved`, `withhold_dependents` and `text_chunks`, and an interrupted refresh) and the changed corpus-field test in `tests/test_identity_native.py`.
- Journeys D1 to D6 in `.claude/skills/verify/features/dependencies.md`: 127 PASS and 0 FAIL in 10 runs (D5 runs five fault stages). Each count includes three lab-store guard rows.
- Every other loopback journey, run one ID at a time (P1 to P4, W1 to W3, R1, R2, E1 to E4, O1 to O8, G1 to G4, I1 to I4, K1 to K5, F1 to F4): 1159 PASS and 0 FAIL in 58 runs, the same totals as the last `journey all` before this checkpoint. `journey all` itself was not run.

Fix round 1, run by the assistant on the user's Mac on 2026-10-23 with loopback embeddings, every source file as at `3814515`:

- `uv run pytest -q -m 'not integration'`: 396 passed, 67 deselected.
- `uv run python support/occurrence_check.py`: PASS (103 s), with four more `DECISIONS` rows for unattested foreign-input changes. `--mutants`: PASS, all 29 breaks caught, including `reconfirm_by_own_refs`.
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, `PINNED` unchanged at 5889 nodes and 5770 sequences. `--mutants`: all 40 breaks caught.
- `uv run pytest -q -m integration tests/test_identity_dependencies_native.py tests/test_identity_native.py`: 19 passed in 416 s, including three new tests: the re-add after an interrupted refresh, a review waiting for an unfinished edit, and the generic `edit-text` path withholding a dependent's decision.
- Journeys D1 to D6: 127 PASS and 0 FAIL in 10 runs. R1, R2, O1, O2 and E1 to E4, for the refresh now run by `maintain_one`: 290 PASS and 0 FAIL in 16 runs. `journey all` was not run.

The values in this guide come from these runs: the spans and digests from D1 to D4, the glossary chunk from D1's `glossary_identity.json`, and the Hybrid coil UUID from D4's `identity_doc01_revision2.json`.
