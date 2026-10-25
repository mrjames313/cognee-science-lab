# Stage 6 entity edits: readers of a changed or retired Entity or record

**Date:** 2026-10-24. **Status:** checkpoint K, implemented, reviewed in two fix rounds and verified by the assistant and its subagents on the user's Mac with loopback embeddings, on branch `stage6-entity-edits`. The final `journey all` gave 1658 PASS and 0 FAIL in 101 runs. No user-reviewed fixture root exists yet. See [Evidence](#evidence).

Checkpoint K answers one question: what happens to the readers of an Entity or a saved record that changed or went. Before it, live validation already withheld a decision whose corpus input changed in the graph, but no command drove such a change, and no reviewer could answer it. A citer of a removed record (journey D9's c02) had no reviewer path at all, a dropped record key could come back and be served to an old citation, and a source could read another source's mention UUID as a corpus object.

## User decisions this checkpoint implements

From `.audit/chains.todo.md`, 2026-10-24:

1. **A representation-kind change retires the old group and declares a fresh one** (decision 5). There is no in-place kind change.
2. **A direct edit of a native Entity withholds the decisions that depend on it** (decision 6), with reason `input_changed`, as a text edit of a consumed document does.
3. **Facts as saved records are step 6** (decision 7), not this checkpoint.
4. **The non-identity example is not worked on** (decision 8).

Defaults the orchestrator reported to the user before the work:

- Admission refuses a corpus input that names a mention UUID (`mention_input`). A source that depends on a mention cites the mention's resolution instead.
- A dropped record key cannot come back while another source cites it (`record_key_reused`).
- `replace-citation --cite|--drop` is the reviewer path for a citer of a removed record.
- Citers of a retired record stay withheld `input_removed` until a reviewer answers them. There is no successor record and no remap analogue for an Entity edit. Scoped variants stay refused.
- `cognify` cannot overwrite an Entity the lab declares, because Cognee derives an extracted Entity's ID another way. The overwrite concern applies only to a Cognee-extracted Entity that a decision cites.

Behaviour changes from the fix rounds, also reported to the user:

- A `replace-decision` of a variant whose input went drops the variant as an erasure drops it, with the recipes only it named.
- An erasure, like `--drop`, strips only the citing resolutions' own groups, not every group that cites the removed record.
- A glossary replacement row with no `text_change` resumes as a plain replacement.

## What changes for users

- `edit-entity --case description|unselected|revert` edits the Helios controller Entity that doc01 reads as a corpus input (`existing_A`), on a glossary root, chain roots included. It writes no ledger row and no recovery event.
- `reconfirm` answers a decision withheld by an Entity edit: it cites the Entity as it reads now under a new key. One re-confirm answers a decision withheld by inputs of several kinds.
- `replace-decision --decision r01` answers an Entity edit too: g01 becomes unresolved on the Entity as it reads now.
- `replace-citation --source <label> --decision <key> (--cite <source>:<record> | --drop)` answers a decision withheld by a saved record it cites, removed or changed.
- `change-kind-to-mention` and `change-kind-to-reusable` run on a glossary root, where other sources read doc01. Their result lists the other sources' decisions they leave withheld.
- `cite-record --citation entity|mention` drives the two corpus-object readers through the CLI.
- New refusals: `record_key_reused`, `mention_input`, `entity_field_protected`. The `input_removed` refusal of `reconfirm` now names `replace-citation` for a removed citation.

## The data shapes

No saved schema changed. `RecordStore`, `TRANSITIONS`, the ledger model and the withholding table are unchanged.

- **A review's producer** (`review.review_producer`) records `old_digests` (old input key to digest) and `new_digests` (new input key to digest) for every input kind. `new_digests` names only inputs the written revision keeps, so a variant the review drops names none (fix round 2). Before this checkpoint a glossary-span re-confirm recorded a single `new_digest`; journey D3 and the dependencies native test now read `new_digests`.
- **What a reviewer reads** (`review.Now`): each input key that withholds the decision, mapped to its new key and the input as it is now, or to None when the input is gone or the reviewer drops it.
- **The review table** (`review.AS_NOW`) maps an input kind to how a review reads that input as it is now: `SavedRecordInput` to `record_now` (the citation of the record as its source holds it now, through `records.current_record`, which `--cite` and `cite-record` also use), `TextSpanInput` to `span_now` (the glossary's HC entry in the registered text that live validation reads), `CorpusObjectInput` to `corpus_now` (the same Entity and selected fields, with the digest of their values now). Each gives None when its input is gone. The new key is `<old key>_r<revision>`.
- **The replacement table** (`review.REPLACEMENTS`) is the captured policy: a resolution to `unresolved_in_place`, a variant to `replaced_variant`. A record type without an entry is refused (`fixture_scope`), and an import-time check holds its keys within `records.REGISTRY`.
- **`records.apply_removal(payload, source, keys, ref_map, producer_key)`** removes records as their type says (`RecordKind.removed`) and rewires the parts that hold those records' inputs (`RecordKind.stripped`) by a ref map: an input that changed maps to its new key, one that went or is dropped maps to None. Other records and their parts keep citing what they cite. The erasure's removal revision, `--drop`, the in-place replacement and the replacement of a decision whose input went all use it. After it, each of them drops the recipes that only the removed records named, unless a saved source reads that Entity as a corpus input (`erasure_rules.drop_unnamed_recipes`, fix round 2).
- **`validation.selected_digest(node, item)`** is the one digest of a corpus input's selected fields. Live validation and the corpus re-confirm both use it.
- **`records.names_record(item, source, key)`** is the one test of whether a citation names a record key of a source. `RemovedRecord.reads` builds on it and `chains.check_record_key_reuse` uses it.

Nothing outside `records.REGISTRY` names a record type's fields in the new code; the re-confirm (`revisions.reconfirmed`, on `main` before this checkpoint) still did. Since 2026-10-25 it writes through `records.apply_reconfirm`. `review.replaced_variant` still writes `variant_assignments` itself (a tracked follow-up). One flow answers the three review commands (`review.review`): the gate (`review_gate`, with `refuse_command` deciding whether the command answers the decision's inputs), what the reviewer reads now, then the intended revision (`intended_revision`).

## The edit

`edit-entity` (`entity_edit.py`) is a captured stand-in for a writer outside the lab. It calls Cognee's own `graph.update_node`, which merges a patch into the node's property blob.

| Case | What it writes | Effect |
|---|---|---|
| `description` | `description` of the Helios controller Entity, a field `existing_A` selects | r01 and v01 withheld `input_changed`, `refresh_needed`; c01 and c02 `upstream_withheld` |
| `unselected` | `lab_note`, a property no corpus input selects | nothing withheld |
| `revert` | the values the first `description` edit replaced, saved in `entity_edit_original.json` in the root | everything released with no revision |

It refuses `id`, `name` and `type` (`entity_field_protected`): Cognee keeps them as native columns outside the blob. It refuses a `description` edit of an Entity that has no `description` (`fixture_scope`), since a revert could not take an added field away, and saves `entity_edit_original.json` only once the edit is made. It finds doc01's input by the Helios controller's Entity ID, so a re-read under another key still counts. It has no fault stage. Its JSON adds `entity_edit` with the fields written, the pinned digest and the digest of the selected fields before and after, beside the usual snapshot with `withheld_decisions`.

Live validation finds the edit at the next read: `validation.input_failure` digests the selected fields and compares them with the pinned digest. `is_foreign` holds a corpus object foreign, so the edit withholds the decisions that cite it and never fails the source. Nothing is written: a revert releases on the next read.

## Re-confirm

`reconfirm` reads every input that withholds the decision through `AS_NOW` and writes one revision that cites each as it is now, under a producer new in the revision. A decision withheld by the glossary span and the Entity together is re-confirmed on both (journey D15). `input_removed` is still never re-confirmed: a missing Entity or selected field raises `input_removed`, and the gate refuses a removed input before it.

## Replace

`replace-decision --decision r01` leaves g01 unresolved in place. The resolution and its group cite each withholding input as it is now, whatever its kind. An input that went (an Entity that Cognee or another writer deleted outside `forget`, or the glossary document gone) is stripped from the decision instead, as an erasure strips it: a resolution stays, unresolved, and a variant goes (fix round 1), with each recipe that only it named and no saved source reads as a corpus input (fix round 2). A resolution whose every input went says "went" in its explanation. `replace-decision --decision v01` has a captured replacement only when the glossary span alone withholds v01, because the "Hybrid coil" meaning comes from the glossary; an Entity edit refuses it (`fixture_scope`). A decision withheld by a saved record is refused by `replace-decision` with a pointer to `replace-citation`.

## Replace a citation

`replace-citation` answers a decision whose withholding inputs are all saved records, at any chain level, through the same gates as `review_gate`:

- `--cite <source>:<record>` re-cites the decision on that record as its source holds it now, under the key `<source>_<record>_r<revision>`. The decision's reviewed fields stay, so its own citers release with it. It needs exactly one withholding citation.
- `--drop` removes the decision as an erasure would: a variant goes and a resolution stays, unresolved in place. A recipe that only the dropped decision named goes too, unless a saved source reads it as a corpus input. Only the dropped decision and its own group stop citing the record; another resolution whose group cites it keeps citing it under its own producer (fix round 1). Uncited inputs are dropped.

Either names a producer new in the revision (implementation `replaced`) whose configuration records the withholding it answers and the digests. Admission runs as it does for any revision: `check_reconfirmations`, `check_foreign_inputs` and `check_record_citations` admit the new citation and refuse a stale or wrong one.

## Record keys stay single-meaning

**Invariant.** A record key that another source cites names one record of its source for as long as that citation lasts.

A citation pins its record by key and fingerprint. A variant that comes back under its old key with the same reviewed fields has the same fingerprint, so the old citation would read it as served again, with no review. The fresh-key rules compared only with the previous revision.

`chains.check_record_key_reuse` refuses (`record_key_reused`) a record key that this revision adds while another source that is not retired still cites that key at this source. `chains.new_record_keys` gives the added keys: every key of a first publication or a re-add, and on a replacement the keys the current revision lacks. Only a first attempt checks, as `check_record_citations` does, so a retry is never refused forever. It runs in `Publisher.admit_inputs` beside `check_record_citations`, because it reads the ledger rows.

The chain check proves it on every acyclic citation graph of up to four sources, with each source holding `d` and `v`, having dropped `d` (rekeyed) or `v` (rekeyed_v), pending or withdrawn: a revision that declares the dropped key again is refused exactly when another source that is not retired cites it. Mutants: the check skipped (as if only the revision before counted), only served citers counted, and only resolution keys looked for (fix round 1, so the variant key has a lever too).

## No reader of a mention UUID

**Invariant.** A corpus input names a reusable Entity, never a mention group's Entity.

A mention UUID is document-local and fresh at its declaration, and a retiring or regrouping edit removes it with no review of its readers. A source that read it as a corpus object would be withheld `input_removed` with no reviewer path, and the UUID never returns. Refusing the reader makes that state unreachable; extending `text_changes.reject_sole_owned_readers` to mentions would have blocked every changed-meaning edit, regrouping and plain edit whenever another source read the mention.

`admission.check_mention_inputs` refuses (`mention_input`) a corpus input whose Entity is a mention UUID of any saved source: every other source's latest description and tombstones, this source's saved revision (so a group this revision retires counts) and the tombstone of its own forgotten lives (`last_tombstone`, fix round 1), and the candidate itself (`admission.mention_ids`, over `publish.saved_lives`). It runs in every admission of a publication (`Publisher.admit_inputs`).

The occurrence check calls it before `admit`, with another source's mention UUID added. Its rows: a corpus input of the continuing group's mention, of a retired group's mention and of another source's mention, each refused, and one of a reusable Entity, admitted. Mutants: the rule skipped, and only the candidate's own groups counted.

## Kind changes with readers

`change-kind-to-mention` and `change-kind-to-reusable` on a glossary root (`chain_kind_change.py`) change the first fixture's doc01, which has one group, g01, with unchanged text. To mention is `kind_change.describe_to_mention` with the root's groups and text and no producer stamp; to reusable has its own describer, which declares the HC variant through `kind_change.declare_hc_variant` as the chunked fixture's does (fix round 2):

- To mention: v01 and the HC recipe go, and a fresh g09, `HC` at [19, 21), resolves to the Helios controller as r09. r01 is unchanged, so c01 is untouched.
- To reusable: g09 retires, the HC recipe returns, the corpus input `existing_HC` reads the HC Entity, and a document-scoped variant names it under v01, the key the first change dropped.

The readers follow the rules above and the existing ones:

| Reader | What happens | Journey |
|---|---|---|
| doc03's c02 cited v01 | withheld `input_removed`; `reconfirm` refused; `replace-citation --cite doc01:r09` releases it | K6 |
| c02 still cites v01 when doc01 tries to bring v01 back | `record_key_reused` | K6 |
| doc03 reads an HC doc01 alone owns as a corpus object (`cite-record --citation entity`) | the kind change refuses `dependent_source` before any write (existing rule, first journey) | K7 |
| no reader, doc01 alone owns HC (a glossary root without doc03) | the HC Entity, its node and its name index leave the graph | K7 |
| doc03 tries to read doc01's g01 mention as a corpus object (`cite-record --citation mention`) | `mention_input` | K8 |

To reusable needs the HC Entity in the graph. On a chain root doc03 co-owns HC, so it stays through the first change. On a root where doc01 alone owns HC and nothing reads it, to mention takes HC out of the graph, and to reusable is then refused.

The result adds `dependents_withheld`, the other sources' decisions that the completed revision leaves withheld, read from the same live pass as `status`, and `hc_entity`. A failed kind change withholds doc03's decisions with `edit_unfinished`, and `reconcile --source doc01` finishes it through the text-change rebuild (journey K9).

## J2 overlaps, checked on `a4cc0d5`

- A kind change keeps the source's removal producers: the describers start from `captured_revision.begin_revision`, which copies the old producers, and `check_removal_producers_kept` admits them.
- A kind change of a source whose forget or cascade is unfinished meets the fence (`retiring_source`): `Publisher.admit_inputs` runs `refuse_retiring_inputs` for every revision.
- A citation that a kind change made `input_removed` does not hold a later forget's cascade unfinished: the cascade binds a removed record by key, fingerprint and last served revision (`RemovedRecord.reads`), and a citation of a key already gone matches no removal. Unit test `test_a_citation_a_kind_change_removed_does_not_hold_a_later_cascade`.
- An Entity edit between a dry run and its confirmation leaves the token unchanged, and a decision the edit withholds does not block a forget: the impact, its token and the write order read the ledger rows only. Unit test `test_an_entity_edit_changes_neither_the_forget_token_nor_its_write_order`.
- `record_key_reused` shares `names_record` with `RemovedRecord.reads`.

## Commands

From the repository root, with a new root each time:

```bash
uv run python -m cognee_lab.identity glossary-fixture --chain --root outputs/stage6_entity_check --embedding loopback
uv run python -m cognee_lab.identity edit-entity --root outputs/stage6_entity_check --case description
uv run python -m cognee_lab.identity reconfirm --root outputs/stage6_entity_check --source doc01 --decision r01 --expected-revision 1
uv run python -m cognee_lab.identity reconfirm --root outputs/stage6_entity_check --source doc01 --decision v01 --expected-revision 2
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_entity_check
```

Expected: after the edit, r01 and v01 are withheld for review and c01 and c02 with `upstream_withheld`; after both re-confirms nothing is withheld, doc01 is at revision 3 and doc03 at revision 1.

Journeys D12 to D17 in `.claude/skills/verify/features/dependencies.md` and K6 to K9 in `reinterpretation.md` cover this checkpoint.

## Choices the assistant made

Each is reversible.

- **The span re-confirm's producer records `new_digests`**, as the saved-record one did, not `new_digest`. One shape for every kind.
- **`replace-decision --decision r01`** works on any resolution, not only r01, and its explanation names the inputs that changed.
- **`--drop` on a resolution leaves it unresolved in place**, as an erasure removal does (the registry's `removed` hook); a variant goes.
- **`record_key_reused` matches the key in any record type**, since a key names one record in a source across every type, and checks a first publication and a re-add too.
- **`mention_input` counts the source's own saved revision**, so a corpus input of a group the same revision retires is refused.
- **The glossary root's to-reusable has its own describer**, because the first fixture's doc01 has one group and another text; to mention shares `kind_change.py`'s (fix round 1). `change-kind-to-reusable` there names HC under v01, to drive `record_key_reused`.
- **`edit-entity` finds the Entity by its ID**, the Helios controller's, and reports the first input that reads it (fix round 1; before, by the key name `existing_A`).
- **A decision whose input went is stripped by `replace-decision`**, a variant dropped as an erasure drops it, rather than refused (fix round 1). Since fix round 2 the review also drops the recipes that only the dropped decision named, through the erasure's own rule.

## Not in this checkpoint

- Facts as saved records (decision 7) and the non-identity example (decision 8).
- An edit of `name` on a Cognee-extracted Entity. `cognify` cannot rewrite a lab-declared Entity, whose ID derivation differs from Cognee's; it could rewrite only an extracted Entity that a decision cites, which no fixture does. Such a rewrite of a selected field would be an edit and withhold.
- A successor record, a remap analogue for Entity edits and scoped variants.
- A journey for a decision withheld by removed glossary text. Only `forget` removes the glossary. Step 5 S2 added the corpus-node case, journey D17 ([Outside deletion, built in step 5 S2](#outside-deletion-built-in-step-5-s2)).

## Outside deletion, probed 2026-10-25

The step-4 cleanups asked for a stand-in that deletes the Helios controller Entity through Cognee's own graph API, writing no ledger row, the way `edit-entity` edits it. A journey D17 would then answer r01 and v01. The brief said to prototype first. The assistant's subagent ran the probe on the user's Mac on 2026-10-25 with loopback embeddings, in `outputs/verify/20261025T144616Z-item4-delete-probe/` in the cleanups worktree.

- The delete withholds r01 and v01 (`input_removed`) and, down the chain, c01 and c02 (`upstream_withheld`). `reconfirm` is refused, and retrieval serves 0 facts.
- `replace-decision` on r01 and on v01 are both refused `missing_reasoning_input`, because the other withheld decision still cites `existing_A`. Neither can be answered first.
- `graph.delete_node` removed the node and its edges but left its `Entity_name` vector point.

The user decided on 2026-10-25:

1. A withheld decision may keep citing a deleted Entity while a neighbouring decision is replaced (relax `admission.check_corpus_inputs_exist` for citers already withheld).
2. A republish may not recreate an Entity deleted outside the lab. A replacement picks a new target or leaves the mention unresolved.
3. Step 4 records the deadlock as a documented limit. The fix, journey D17 and the orphaned vector point go to step 5 S2 (removal).

No stand-in was committed. The glossary text removal was left out, because only `forget` removes the glossary.

## Outside deletion, built in step 5 S2

Built 2026-10-25 by the assistant on the user's Mac with loopback embeddings (module `outside_deletion.py`).

`edit-entity --case delete` deletes the Helios controller through `graph.delete_node`, as an outside writer would. It writes no ledger row, has no `revert`, and reports `node_present: false` and `name_point_present: true`. An Entity counts as deleted outside the lab when a served source's description, or the publishing source's last verified one, names it as a corpus input or a reusable recipe, its node is absent, and no lab operation removed it (`outside_deletion.lab_removed`). Lab removals are what each forget removed and each forgotten life's mention UUIDs, every reusable Entity of a forgotten life except those its forget found served and did not remove (the tombstone's `served_entity_ids`, which later lives carry), what a replacement planned to retire, and the recipes of a source that is not served, which a withdrawal or a failed attempt may have removed. A served source's recipe is never a lab removal: no lab operation removes it while that source is served, so a withdrawn co-owner leaves the Entity deleted outside the lab when it is gone.

- **A kept decision may keep citing it, and no publication recreates it.** `outside_deletion.left_absent` runs one rule per such Entity that the source names. Each part that cites or names it must be as in the source's last verified description: a record with its attribution, its producer's definition and the inputs it cites, an unresolved group, and the Entity's recipe. The last verified description is a replacement's `previous_description` while it is pending or failed, otherwise the row's own when the ledger served it (`holds_served`); a first publication and an erasure retry have none. A new or changed part that cites the Entity as a corpus input is refused `missing_reasoning_input`, as is any citer of an Entity a lab operation removed (`admission.check_corpus_inputs_exist`). Any other new or changed part, a new or changed recipe included, is refused `entity_recreation`. For kept ones the publisher leaves the Entity absent by design: it skips the recipe, the identity edges with that endpoint and their contributions, in the write and in its verification (`publish.written`). Cognee's `add_edges` silently drops an edge whose endpoint is gone and makes no stub node (prototype, 2026-10-25), so an unskipped edge would have failed verification. A prototype with the relaxation alone let `replace-decision --decision r01` recreate Helios from doc01's recipe, which the user's decision 2 forbids.
- **A re-add naming it is refused** (`entity_recreation`, the default for the user's question Q2): a reusable Entity of a forgotten life whose node is absent and that no lab operation removed, which the caller's files still name. A source withdrawn before its forget removed its own Entities, so its re-add may name them again.

Journey D17 runs the decisions one at a time: r01 and v01 are withheld `input_removed` and c01 and c02 `upstream_withheld`; `reconfirm` is refused; `replace-decision --decision r01` leaves g01 unresolved at revision 2 while v01 stays withheld and Helios stays absent; `replace-decision --decision v01` drops the variant and the Helios recipe at revision 3. doc03 then answers c01 and c02 with its own review. A retrieve for "Helios controller" serves nothing through the orphaned `Entity_name` point, since the retriever resolves vector hits through the graph. The orphaned point itself stays as documented residue until a sweep lands with the dataset forget (blocked on the user's question Q3).

Native tests in `tests/test_identity_outside_deletion_native.py` cover the D17 sequence, a failed replacement's retry with Helios absent (`--fault-stage replace_verification`, then `reconcile`) and the re-add refusal; unit tests in `tests/test_identity_outside_deletion.py` cover each lab removal path and the refusals.

## Evidence

**Checkpoint K runs.** The assistant and its subagents ran `.claude/skills/verify/scripts/verify.py journey all` on the user's Mac on 2026-10-24 with loopback embeddings, on branch `stage6-entity-edits`. P5 calls the embedding API and did not run. The map has 75 journey blocks, and `journey all` runs the 74 loopback blocks as 101 runs.

- On `40d7d20` (the implementation, before its rebase onto `main` at `9c6f16e` as `3237563`): 1658 PASS and 0 FAIL in 101 runs.
- On `94d54bb` (after fix round 1): 1658 PASS and 0 FAIL in 101 runs.
- On `5e0c314` (after fix round 2): 1658 PASS and 0 FAIL in 101 runs. The next commit, `514c0bb`, only rewraps the `entity_edit.py` docstring. The unit suite gave 560 passed on `514c0bb`.

**Reviews.** Each round was a `/pstack:thermos` pair (bug and quality).

- The first bug review of `40d7d20` found one medium item, a decision withheld by a removed corpus input with no working reviewer path, three low ones and a note for this guide. The quality review found that the branch needed a rebase, that the review drop repeated the erasure's removal, and that new code named decision fields outside `records.py`. Fix round 1 answered each ([Fix round 1](#fix-round-1-2026-10-24)).
- Both re-reviews of `94d54bb` found the branch merge-ready. The bug review raised two probed low items: a review producer that named an input the revision drops, and a recipe left behind after a review drop. Fix round 2 answered them with the quality items ([Fix round 2](#fix-round-2-2026-10-24)).
- Both re-reviews of round 2 found the branch merge-ready, with no blockers. The quality review left two small items, tracked in the handoff: `erasure_rules.corpus_readers` repeats the reader filter of the Erasures builder, and three review docstrings restate `drop_unnamed_recipes`.

**The implementation.** Run by the assistant (a subagent) on the user's Mac on 2026-10-24 with loopback embeddings, on branch `stage6-entity-edits`.

- `uv run pytest -q -m 'not integration'`: 552 passed, 86 deselected, on `2243a35` (533 passed on `a4cc0d5`).
- `uv run python support/occurrence_check.py`: PASS on all 540,045 fate worlds with the new rows (130 s). `--mutants`: every break caught, including `allow_mention_inputs` and `mention_inputs_of_the_candidate_only` (97 s).
- `uv run python support/chain_check.py`: PASS, 0 disagreements on 543 acyclic graphs, 16,384 cycle cases, 2,224,128 withholding worlds, 278,016 key-reuse cases and 34,752 cascade worlds (505 s). `--mutants`: every break caught, including `key_reuse_unchecked` and `key_reuse_served_citers` (36 s).
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, `PINNED` unchanged at 9205 nodes and 9050 sequences. `RecordStore` is unchanged; `Publisher.admit_inputs` only gained two refusals before `begin`. `--mutants`: every break caught.
- Verify journeys, 0 FAIL rows each (each count includes three lab-store guard rows): D1 to D11 191 PASS in 15 runs, the new D12 to D16 44 PASS in 5 runs, E1 to E4 125 PASS in 7 runs, F1 to F20 420 PASS in 27 runs, G1 to G4 109 PASS in 4 runs, K1 to K5 126 PASS in 7 runs, and the new K6 to K9 38 PASS in 5 runs. `journey all` was not run.
- `uv run pytest -q -m integration` on the native files for dependencies, chains, forget, erasure retry, kind change and the shared native file (which holds the original Entity-edit test): 57 passed, 1 deselected, in 1339 s, run beside the journeys. This checkpoint adds no native file; journeys D12 to D16 and K6 to K9 drive its paths through the real stores.

The values in this guide come from these runs: the keys, digests and refusal messages from D12 to D16 and K6 to K9.

### Fix round 1 (2026-10-24)

Run by the assistant (a subagent) on the user's Mac with loopback embeddings, on branch `stage6-entity-edits` rebased onto `main` at `9c6f16e` (the chain check as its own CI job).

- Each bug got a test that failed on the code before the fix: the review of a decision whose corpus input or glossary span went (`input_removed` from `corpus_now`; a missing glossary info file from `span_now`), the drop that stripped a sibling's group (`review.dropped` left g2 with `['doc']`, shown by a scratch script on the old code), `edit-entity` on an Entity without `description` (`KeyError`), the input found by key name, and a re-added source reading its own forgotten mention (no refusal).
- `uv run pytest -q -m 'not integration'`: 559 passed, 86 deselected; each commit was gated on the unit suite over its own staged tree.
- `uv run python support/occurrence_check.py`: PASS on 540,045 worlds (148 s). `--mutants`: PASS (105 s). The erasure removal now rewires only the citing records' own groups; no world disagreed.
- `uv run python support/chain_check.py`: PASS, 0 disagreements on 543 acyclic graphs, 16,384 cycle cases, 2,224,128 withholding worlds, 814,500 key-reuse cases (278,016 before `rekeyed_v`) and 34,752 cascade worlds (692 s). `--mutants`: PASS, `key_reuse_resolutions_only` caught (40 s).
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, `PINNED` unchanged at 9205 nodes and 9050 sequences. `--mutants`: PASS. `RecordStore` is unchanged; the erasure rules that `check_retry_chain` reaches now read `RecordKind.removed` and `stripped` through the ref map.
- Verify journeys D1 to D16, E1 to E4, F1 to F20, G1 to G4 and K1 to K9: 70 runs, 1053 PASS, 0 FAIL (D 235 in 20 runs, E 125 in 7, F 420 in 27, G 109 in 4, K 164 in 12). `journey all` was not run.
- `uv run pytest -q -m integration` on the native files for dependencies, chains, forget, erasure retry, kind change and the shared native file: 57 passed, 1 deselected, in 1243 s.
- Open from the review: the glossary driver's command `elif` chain stays; a command table needs one handler signature across ten commands in four modules, which is more than this round's scope. `revisions.reconfirmed` still writes resolution and group fields outside `records.py`.

### Fix round 2 (2026-10-24)

Run by the assistant (a subagent) on the user's Mac with loopback embeddings, on branch `stage6-entity-edits` at `f763831`.

- Each bug got a test that failed on the code before the fix. A `replace-decision` of v01 with one input gone and one changed recorded `existing_A_r2` in `new_digests`, though the revision dropped that input. A review that dropped a variant kept the HC recipe that only the variant named, on both the input-gone path and `--drop`. A resolution whose every input went said "changed or went". The glossary root's to-reusable accepted another text; it now goes through `require_root`.
- Quality follow-ups. `kind_change.declare_hc_variant` now builds both to-reusable variants. `records.current_record` and `forget_fixture.write_revision` moved, so `change_kind` imports at module level. The glossary reconcile resumes every text change through one arm. `intended_revision` now owns the removal branch.
- `uv run pytest -q -m 'not integration'`: 560 passed, 86 deselected. Each commit was gated on the unit suite.
- `uv run python support/occurrence_check.py`: PASS on 540,045 worlds (178 s). `--mutants`: PASS (142 s).
- `uv run python support/chain_check.py`: PASS, 0 disagreements on 543 acyclic graphs, 2,224,128 withholding worlds, 814,500 key-reuse cases and 34,752 cascade worlds (561 s). `--mutants`: PASS (38 s).
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, `PINNED` unchanged at 9205 nodes and 9050 sequences. `--mutants`: PASS. `RecordStore` is unchanged. The erasure's removal revision now drops recipes through `erasure_rules.drop_unnamed_recipes`, with the same rule as before.
- Verify journeys D1 to D16, E1 to E4, F1 to F20, G1 to G4 and K1 to K9: 70 runs, 1053 PASS, 0 FAIL (D 235 in 20 runs, E 125 in 7, F 420 in 27, G 109 in 4, K 164 in 12). `journey all` was not run.
- `uv run pytest -q -m integration` on the native files for dependencies, chains, forget, erasure retry, kind change and the shared native file: 57 passed, 1 deselected, in 1443 s.
- Still open, tracked outside K: a command table for `glossary_fixture.run` (B8), and `revisions.reconfirmed` still writes resolution and group fields outside `records.py`. Branch `stage6-cleanups` closed both on 2026-10-25.
