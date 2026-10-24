# Stage 6 entity edits: readers of a changed or retired Entity or record

**Date:** 2026-10-24. **Status:** checkpoint K, implemented and verified by the assistant on the user's Mac with loopback embeddings, on branch `stage6-entity-edits`. No user-reviewed fixture root exists yet. See [Evidence](#evidence).

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

## What changes for users

- `edit-entity --case description|unselected|revert` edits the Helios controller Entity that doc01's corpus input `existing_A` names, on a glossary root, chain roots included. It writes no ledger row and no recovery event.
- `reconfirm` answers a decision withheld by an Entity edit: it cites the Entity as it reads now under a new key. One re-confirm answers a decision withheld by inputs of several kinds.
- `replace-decision --decision r01` answers an Entity edit too: g01 becomes unresolved on the Entity as it reads now.
- `replace-citation --source <label> --decision <key> (--cite <source>:<record> | --drop)` answers a decision withheld by a saved record it cites, removed or changed.
- `change-kind-to-mention` and `change-kind-to-reusable` run on a glossary root, where other sources read doc01. Their result lists the other sources' decisions they leave withheld.
- `cite-record --citation entity|mention` drives the two corpus-object readers through the CLI.
- New refusals: `record_key_reused`, `mention_input`, `entity_field_protected`. The `input_removed` refusal of `reconfirm` now names `replace-citation` for a removed citation.

## The data shapes

No saved schema changed. `RecordStore`, `TRANSITIONS`, the ledger model and the withholding table are unchanged.

- **A review's producer** (`review.review_producer`) records `old_digests` (old input key to digest) and `new_digests` (new input key to digest) for every input kind. Before this checkpoint a glossary-span re-confirm recorded a single `new_digest`; journey D3 and the dependencies native test now read `new_digests`.
- **The review table** (`review.AS_NOW`) maps an input kind to how a review reads that input as it is now: `SavedRecordInput` to `record_now` (the citation of the record as its source holds it now), `TextSpanInput` to `span_now` (the glossary's HC entry as the glossary reads now), `CorpusObjectInput` to `corpus_now` (the same Entity and selected fields, with the digest of their values now). The new key is `<old key>_r<revision>`.
- **The replacement table** (`review.REPLACEMENTS`) maps a record type to its captured replacement: a resolution to `unresolved_in_place`, a variant to `replaced_variant`.
- **`validation.selected_digest(node, item)`** is the one digest of a corpus input's selected fields. Live validation and the corpus re-confirm both use it.
- **`records.names_record(item, source, key)`** is the one test of whether a citation names a record key of a source. `RemovedRecord.reads` builds on it and `chains.check_record_key_reuse` uses it.

Nothing outside `records.REGISTRY` names a record type's fields in the new code. `replace-citation --drop` removes a decision through the registry's `removed` and `stripped` hooks, as an erasure does.

## The edit

`edit-entity` (`entity_edit.py`) is a captured stand-in for a writer outside the lab. It calls Cognee's own `graph.update_node`, which merges a patch into the node's property blob.

| Case | What it writes | Effect |
|---|---|---|
| `description` | `description` of the Helios controller Entity, a field `existing_A` selects | r01 and v01 withheld `input_changed`, `refresh_needed`; c01 and c02 `upstream_withheld` |
| `unselected` | `lab_note`, a property no corpus input selects | nothing withheld |
| `revert` | the values the first `description` edit replaced, saved in `entity_edit_original.json` in the root | everything released with no revision |

It refuses `id`, `name` and `type` (`entity_field_protected`): Cognee keeps them as native columns outside the blob. It has no fault stage. Its JSON adds `entity_edit` with the fields written, the pinned digest and the digest of the selected fields before and after, beside the usual snapshot with `withheld_decisions`.

Live validation finds the edit at the next read: `validation.input_failure` digests the selected fields and compares them with the pinned digest. `is_foreign` holds a corpus object foreign, so the edit withholds the decisions that cite it and never fails the source. Nothing is written: a revert releases on the next read.

## Re-confirm

`reconfirm` reads every input that withholds the decision through `AS_NOW` and writes one revision that cites each as it is now, under a producer new in the revision. A decision withheld by the glossary span and the Entity together is re-confirmed on both (journey D15). `input_removed` is still never re-confirmed: a missing Entity or selected field raises `input_removed`, and the gate refuses a removed input before it.

## Replace

`replace-decision --decision r01` leaves g01 unresolved in place. The resolution and its group cite each withholding input as it is now, whatever its kind. `replace-decision --decision v01` has a captured replacement only when the glossary span alone withholds v01, because the "Hybrid coil" meaning comes from the glossary; an Entity edit refuses it (`fixture_scope`). A decision withheld by a saved record is refused by `replace-decision` with a pointer to `replace-citation`.

## Replace a citation

`replace-citation` answers a decision whose withholding inputs are all saved records, at any chain level, through the same gates as `review_gate`:

- `--cite <source>:<record>` re-cites the decision on that record as its source holds it now, under the key `<source>_<record>_r<revision>`. The decision's reviewed fields stay, so its own citers release with it. It needs exactly one withholding citation.
- `--drop` removes the decision as an erasure would: a variant goes and a resolution stays, unresolved in place. Uncited inputs are dropped.

Either names a producer new in the revision (implementation `replaced`) whose configuration records the withholding it answers and the digests. Admission runs as it does for any revision: `check_reconfirmations`, `check_foreign_inputs` and `check_record_citations` admit the new citation and refuse a stale or wrong one.

## Record keys stay single-meaning

**Invariant.** A record key that another source cites names one record of its source for as long as that citation lasts.

A citation pins its record by key and fingerprint. A variant that comes back under its old key with the same reviewed fields has the same fingerprint, so the old citation would read it as served again, with no review. The fresh-key rules compared only with the previous revision.

`chains.check_record_key_reuse` refuses (`record_key_reused`) a record key that this revision adds while another source that is not retired still cites that key at this source. `chains.new_record_keys` gives the added keys: every key of a first publication or a re-add, and on a replacement the keys the current revision lacks. Only a first attempt checks, as `check_record_citations` does, so a retry is never refused forever. It runs in `Publisher.admit_inputs` beside `check_record_citations`, because it reads the ledger rows.

The chain check proves it on every acyclic citation graph of up to four sources, with each source holding `d`, having dropped it, pending or withdrawn: a revision that declares `d` again is refused exactly when it had dropped `d` and another source that is not retired cites it. Mutants: the check skipped (as if only the revision before counted), and only served citers counted.

## No reader of a mention UUID

**Invariant.** A corpus input names a reusable Entity, never a mention group's Entity.

A mention UUID is document-local and fresh at its declaration, and a retiring or regrouping edit removes it with no review of its readers. A source that read it as a corpus object would be withheld `input_removed` with no reviewer path, and the UUID never returns. Refusing the reader makes that state unreachable; extending `text_changes.reject_sole_owned_readers` to mentions would have blocked every changed-meaning edit, regrouping and plain edit whenever another source read the mention.

`admission.check_mention_inputs` refuses (`mention_input`) a corpus input whose Entity is a mention UUID of any saved source: every other source's latest description and tombstones, this source's saved revision (so a group this revision retires counts) and the candidate itself (`admission.mention_ids`). It runs in every admission of a publication (`Publisher.admit_inputs`).

The occurrence check calls it before `admit`, with another source's mention UUID added. Its rows: a corpus input of the continuing group's mention, of a retired group's mention and of another source's mention, each refused, and one of a reusable Entity, admitted. Mutants: the rule skipped, and only the candidate's own groups counted.

## Kind changes with readers

`change-kind-to-mention` and `change-kind-to-reusable` on a glossary root (`chain_kind_change.py`) change the first fixture's doc01, which has one group, g01, with unchanged text:

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

Journeys D12 to D16 in `.claude/skills/verify/features/dependencies.md` and K6 to K9 in `reinterpretation.md` cover this checkpoint.

## Choices the assistant made

Each is reversible.

- **The span re-confirm's producer records `new_digests`**, as the saved-record one did, not `new_digest`. One shape for every kind.
- **`replace-decision --decision r01`** works on any resolution, not only r01, and its explanation names the inputs that changed.
- **`--drop` on a resolution leaves it unresolved in place**, as an erasure removal does (the registry's `removed` hook); a variant goes.
- **`record_key_reused` matches the key in any record type**, since a key names one record in a source across every type, and checks a first publication and a re-add too.
- **`mention_input` counts the source's own saved revision**, so a corpus input of a group the same revision retires is refused.
- **The glossary root's kind change has its own describers**, because the first fixture's doc01 has one group and another text; it reuses the producers and the building blocks of `kind_change.py`. `change-kind-to-reusable` there names HC under v01, to drive `record_key_reused`.
- **`edit-entity` finds the Entity through `existing_A`, or after its re-confirms through the latest `existing_A_r<revision>`.**

## Not in this checkpoint

- Facts as saved records (decision 7) and the non-identity example (decision 8).
- An edit of `name` on a Cognee-extracted Entity. `cognify` cannot rewrite a lab-declared Entity, whose ID derivation differs from Cognee's; it could rewrite only an extracted Entity that a decision cites, which no fixture does. Such a rewrite of a selected field would be an edit and withhold.
- A successor record, a remap analogue for Entity edits and scoped variants.
- A reviewer path for a decision withheld by a removed corpus node. It is unreachable through the CLI: a sole-owned Entity under a reader is refused and a mention reader is refused.

## Evidence

Run by the assistant on the user's Mac on 2026-10-24 with loopback embeddings, on branch `stage6-entity-edits`.

- `uv run pytest -q -m 'not integration'`: 552 passed, 86 deselected, on `2243a35` (533 passed on `a4cc0d5`).
- `uv run python support/occurrence_check.py`: PASS on all 540,045 fate worlds with the new rows (130 s). `--mutants`: every break caught, including `allow_mention_inputs` and `mention_inputs_of_the_candidate_only` (97 s).
- `uv run python support/chain_check.py`: PASS, 0 disagreements on 543 acyclic graphs, 16,384 cycle cases, 2,224,128 withholding worlds, 278,016 key-reuse cases and 34,752 cascade worlds (505 s). `--mutants`: every break caught, including `key_reuse_unchecked` and `key_reuse_served_citers` (36 s).
- `uv run python support/ledger_check.py`: PASS, verified within bound at depth 5, `PINNED` unchanged at 9205 nodes and 9050 sequences. `RecordStore` is unchanged; `Publisher.admit_inputs` only gained two refusals before `begin`. `--mutants`: every break caught.
- Verify journeys, 0 FAIL rows each (each count includes three lab-store guard rows): D1 to D11 191 PASS in 15 runs, the new D12 to D16 44 PASS in 5 runs, E1 to E4 125 PASS in 7 runs, F1 to F20 420 PASS in 27 runs, G1 to G4 109 PASS in 4 runs, K1 to K5 126 PASS in 7 runs, and the new K6 to K9 38 PASS in 5 runs. `journey all` was not run.
- `uv run pytest -q -m integration` on the native files for dependencies, chains, forget, erasure retry, kind change and the shared native file (which holds the original Entity-edit test): 57 passed, 1 deselected, in 1339 s, run beside the journeys. This checkpoint adds no native file; journeys D12 to D16 and K6 to K9 drive its paths through the real stores.

The values in this guide come from these runs: the keys, digests and refusal messages from D12 to D16 and K6 to K9.
