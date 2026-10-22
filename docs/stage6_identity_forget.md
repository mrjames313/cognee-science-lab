# Stage 6 forget: remove a source nothing depends on

**Date:** 2026-10-22, revised the same day after two reviews and a verification review. **Status:** implemented and verified by the assistant on the user's Mac with loopback embeddings. No user-reviewed fixture root exists yet.

`forget` removes one source from the two-source fixture: its original document, its generated identity source and everything only they owned. The other source keeps its own interpretation, the shared Entities it owns and the shared edge with only its contribution. `withdraw` stays separate: it retires a source's identity interpretation and keeps the document, its facts, markers and evidence. The user decided on 2026-10-22 that forget is a separate command, that a forgotten source leaves a record of its last revision so that a re-add continues at the next revision, that verification is the ledger model plus fault-stage journeys without an oracle, and that this checkpoint builds only the case where nothing depends on the source. A source that another source consumed is refused with the dependents listed. That refusal is a placeholder until step-4 item 3 decides what erasure does to dependents.

Commands, each on a `multi-fixture` root:

- `forget --source doc01|doc02 --expected-revision N` on a current source at revision N.
- `reconcile --source <doc>` finishes a failed forget, or a failed re-add.
- `readd --source <doc> --expected-revision N` publishes a forgotten source again at revision N+1.
- `multi-fixture --dependent` creates the fixture with doc02 consuming doc01, for the refusal.

## Starting point

A `multi-fixture` root holds two original documents and two identity sources in one dataset. The dataset ID differs per root. The other IDs are fixed by the fixture:

| Object | UUID |
|---|---|
| doc01 identity source | `718efce2-4251-5f6f-8318-417bb4dd3525` |
| doc01 original document | `50d5313b-0fee-5945-b1d5-5c1d37a6f880` |
| doc02 identity source | `ca84d73d-ee72-5dd2-8e33-4117bb6cac36` |
| doc02 original document | `612b911c-660f-5692-a03c-c4842f7b29c8` |
| doc01 mention g01 at revision 1 | `233cb019-3986-5864-88bc-91f334a64372` |
| doc01 unresolved mention g02 at revision 1 | `3597e9fa-0c81-5337-8d5c-c6ce33983446` |
| doc02 mention g01 | `e7ec7685-72e3-5bba-a511-e4bb49682ba4` |
| HC (reusable, declared and owned by both sources) | `9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88` |
| Helios controller A (seed document, referenced by both) | `8b4bff50-907b-56b6-bc80-3b0a7018714a` |
| doc01 private singleton at revision 1 | `fce9b214-10ab-5752-913d-3eae0dfc6b1f` |
| Shared singleton (owned by both) | `ffe587e5-f2ec-53f9-bda0-10ef80582c84` |
| oscillations (fact target, owned by both documents' chunks) | `db651b0f-9add-5889-a2c5-800f96175085` |

Both sources are current at revision 1. Each has one `limits` fact from its own chunk, and both contribute to the HC to A variant edge.

## What forget removes

Forget runs four stages under the project writer reservation, after a durable plan is saved:

1. `forget_contributions`: the dependents check runs again under the reservation, then this source's contribution payloads leave the shared identity edges, as in withdraw. Other owners' payloads and native ownership stay.
2. `forget_identity`: `cognee.forget(data_id=<identity source>, dataset_id=...)`, then the sweep described below.
3. `forget_document`: `cognee.forget(data_id=<original document>, dataset_id=...)`, then the sweep.
4. `forget_verification`: nothing of the source remains, and every survivor keeps what it owes. Then the row completes as `forgotten`.

Cognee 1.6.2's `forget(data_id=..., dataset_id=...)` without `memory_only` calls `datasets.delete_data` (`cognee/api/v1/forget/forget.py`, `cognee/api/v1/datasets/datasets.py`). On a graph that stores provenance in the graph, that path is `try_delete_data_by_graph_provenance`, which is `UnifiedStoreEngine.delete_by_document`: it collects every node and edge ref whose data ID is this item, the v1 document key and every v2 chunk key, removes those refs, and hard-deletes the nodes and edges left with no ref, with their vectors and triplet vectors (`execute_source_ref_removal`). Shared output is detached, not deleted. Then `SqlAlchemyAdapter.delete_data_entity` deletes the `Data` row and commits, and only then sweeps the `provenance_edge_evidence` rows of the item and the raw and original stored files under the root's data directory, each once no other `Data` row references it.

**The sweep.** A process that dies between that commit and the sweep leaves the evidence rows and the files behind. A retry then finds no `Data` row, and `datasets.delete_data` takes the branch for data it does not know, which deletes graph objects by data ID and sweeps nothing. So forget runs the same sweep itself after each native forget: `delete_edge_evidence(dataset_id, data_id)` and `remove_data_file_if_unreferenced(location)` for each location the plan recorded for the item. Both are idempotent, so a retry converges whatever the first attempt reached. The verification refuses while an evidence row remains, or a stored file under the data root that no other `Data` row references. Cognee stores a file under a content address (`<md5>/<file name>`, or `text_<md5>.txt`), so another item with the same bytes and name shares it, and `remove_data_file_if_unreferenced` keeps the file for that item. Before the second review the verification counted that file too, so the forget of a document whose stored file another item shared failed with `stored_files_present` on every attempt; the native test `test_native_forget_finishes_when_another_item_keeps_the_stored_file` adds a copy of doc01's text under the same file name and forgets doc01. The fault stages `forget_identity_committed` and `forget_document_committed` stand in for the death after the commit: they make Cognee's evidence sweep raise, so the `Data` row is gone and the evidence rows and files are not; the recovery event records the stage the item was in (`forget_identity` or `forget_document`). Before the sweep existed, the reconcile of that state failed forever with `Forgotten source leaves stored_files_present` (and `evidence_rows` for the document).

For doc01 that removes: the six-to-one chunk nodes and their `DocumentChunk_text` vectors, the document node, the `has_identity_mention` markers (owned by the chunk refs), the `limits` fact edge and its `contains` edges (owned by the producing chunk ref), the mention Entities g01 and g02 and their `Entity_name` vectors (owned by the identity source and the chunk refs, both gone), the private singleton (owned by the identity source only), the identity source's ownership of HC, A and the shared singleton, its `resolves_to` edge for r01, the evidence rows, the `Data` rows and the stored files of both items. It keeps, with doc02's refs: HC, A, the shared singleton, oscillations and the HC to A edge with doc02's contribution only.

## The ledger

A row has one of five states: `pending`, `current`, `failed`, `withdrawn` and `forgotten`. Forget begins on a `current` row, or on a `failed` row that holds a forget plan, with the exact saved description and a plan whose `operation` is `identity_forget`. It completes as `forgotten` and keeps the revision and the verified revision. A forgotten row accepts only a new publication (`method="publish"`) at the next revision; every other method is refused as `forgotten_source`. A publish on any other saved row is refused as `recovery_choice`, so a publication always starts a lineage, from no row or from a forgotten one. A failed forget is resumed only by forget (`recovery_choice` otherwise), and `reconcile --source <doc>` routes a failed forget to it. `RecordStore.row(source)` reads one source's row; every operation uses it.

The forget plan holds `revision`, `runtime_profile`, `original_data_id`, `stored_files` (the raw and original file locations of the document and of the identity Data, by data ID), `chunk_ids`, `identity_edges` (the triples this source contributed to) and the ownership snapshot withdraw also records: `entities` (every node the identity source or the document's refs own, with its refs, type and indexed fields) and `edges` (every edge they own, with refs and properties). A retry reuses the saved plan, because native deletion has detached or removed what a new scan would find. A failed forget whose plan predates `stored_files` is refused with `recovery_plan` before `begin`; before the second review its retry raised `KeyError` at the sweep.

Decisions taken in this checkpoint:

- **The forgotten row keeps its description.** The re-add admission compares against it (no UUID of the forgotten revision may return), `status` can say what was forgotten, the dependents check of a later forget skips it, and `retrieve` keeps its mention labels out of the alias set. Dropping it would need a nullable column and gain nothing. The description holds the occurrence texts of the mentions, so an erasure policy that must drop those too is a later decision ("What survives a forget" below).
- **Re-add is its own entry point.** `Publisher.publish` is a first publication (expected revision 0, method `publish`), `Publisher.reconcile` completes the saved revision (method `reconcile`), and `Publisher.readd` publishes a forgotten source at the next revision (method `publish`, expected revision N). The three share one `_publish`; no entry point derives its method from revisions. Before any write, `readd` runs `admit_readd` (in `admission.py`): the same dataset, identity source and document, the next revision, every mention group's UUID derived as `uuid5(identity_data_id, "mention:r{N+1}:{key}")`, unused by the forgotten revision and absent from the graph, and no Entity UUID the forget removed anywhere in the description. A reusable Entity the forget removed returns under a new UUID. When a resolution or variant names it, the UUID derives from the next revision and a key that names it, `uuid5(identity_data_id, "entity:r{N+1}:{key}")`, the rule for any new reusable Entity (the user decided this on 2026-10-22). Only an Entity nothing names, such as the private singleton, returns under `uuid5(identity_data_id, "entity:r{N+1}:replaces:{removed UUID}")`, and `check_readd_entity_ids` accepts that form only for an unnamed Entity. The fixture's `describe_readd` takes the first naming key in sorted order that no other replacement took, and refuses when every naming key is taken, so two removed Entities are never merged. Then `admit_inputs` runs: the inputs against the text and chunks, the UUID uses across saved descriptions, the fence on retiring sources, the saved revision and the Entity types. These are the checks of `preflight` that need no registered Data, so the fixture's `readd` runs them on the in-memory text and chunks before it adds anything to Cognee; a refusal leaves the stores as the forget left them.
- **Fault stages.** The four stages above and the two `_committed` ones. The first three fail after their write, the verification stage before the acknowledgement, so each retry repeats idempotent work. `readd` takes the publication stages `nodes`, `identity_edges` and `verification`.

## Dependents

Source Y depends on source X when Y's description lists X's document as a `source_text` input, or lists as a `corpus_object` input an Entity the forget of X removes. A chunk or span input names its document through a `source_text` input of the same description, so the text check covers it. An Entity another current source also owns survives a forget with its fields, so a reader of it is unaffected. Withdrawn and forgotten sources consume nothing. `retirement.py` holds the one check, `dependents()`, and the `Dependent` entry type; `reject_dependents` in `text_changes.py` calls it with no removed Entities, because a text edit keeps the document.

**Removed Entities.** The forget removes an Entity whose every recorded owner is this source (its identity source or its document's chunks) or a retiring source: one whose withdraw or forget is pending, failed, withdrawn or forgotten (`retired_sources`). A retiring owner's refs leave too, so such an Entity is not independently owned, and a reader of it refuses the forget. Before the review, only the source's own refs counted, so a reader of an Entity shared with a failed forget's source was not a dependent.

**What a re-add replaces.** A re-add replaces each Entity in `readd_removed`: the removed Entities above, computed from the rows at the re-add, and every Entity the forget plan recorded that the graph no longer holds. The rows alone are not enough. If doc02 is forgotten while doc01 still owns HC and the shared singleton, they survive doc02's forget; doc01's forget then removes them. Once doc01 is re-added its row is current again, so the rows show doc01 as a live owner of HC in doc02's plan. Before the second review, the re-add of doc02 then recreated HC and the shared singleton under their original UUIDs, owned by doc02 alone. Now HC returns in each source under its own `entity:r2:v01` UUID (doc01 `9c82875e-...`, doc02 `e7065ec7-...`) and the shared singleton under each source's `replaces:` UUID (doc01 `4b253283-...`, doc02 `0368ab03-...`). The native test `test_native_readd_replaces_what_a_later_forget_of_a_co_owner_removed` drives forget doc02, forget doc01, re-add doc01 and re-add doc02.

**The fence.** A new consumer of a source whose forget is pending or failed is refused in `preflight` with `retiring_source` and the same `details.dependents` shape. Without it, a source could publish consuming doc01's text, a chunk or a removed Entity while doc01's forget was failed, after which the reconcile of that forget was refused with `dependent_source` and doc01 stayed half-forgotten. The fence runs before `begin` and again after it, because `preflight` repeats under the reservation. Forget itself repeats its dependents check after `begin`, so a consumer that published between the pre-check and the reservation fails the forget at `forget_contributions` instead of being missed.

A refused forget exits 1 with `error`, `message` and `details.dependents`, one entry per consumed input: the dependent's `dataset_id` and `identity_data_id`, the `input_ref`, its `kind` and the `consumed` UUID.

`multi-fixture --dependent` builds the case: doc02's r01 decision lists `doc01_text` (doc01's document) and `doc01_instrument` (doc01's private singleton, `fce9b214-...`). The fixture validates both at publication, like every input.

## Forget doc01

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/<new root> --embedding loopback
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
uv run python -m cognee_lab.identity status --root outputs/<new root>
```

The forget writes `multisource_result.json`. Expected:

- `sources.doc01` has `state: forgotten`, `saved_revision` 1, `verified_revision` 1 and a `forget` report. The report is `remains()` from `forget.py`, the one that the verification requires to be all false, empty or zero (`original_data_present`, `identity_data_present`, `stored_files_present`, `document_node_present`, `chunks_present`, `chunk_vectors_present`, `evidence_rows`, `identity_contribution_present`, `owned_nodes`, `owned_edges`), plus the fixture's own fields `mention_nodes_present`, `mention_vectors_present`, `original_fact_present`, `private_singleton_present` and `private_singleton_indexed`, also all absent.
- `sources.doc02` is unchanged from the fixture result: current at 1/1/1 with its marker, fact, ownership, evidence, private singleton and unresolved mention.
- `shared_variant` has one contribution and one owner, both doc02's. `hc_entity` is present with one owner, doc02's identity source. `shared_singleton_present` and `shared_singleton_indexed` are true. `borrowed_entity` keeps its `updated_at` and `description`.
- `result.facts` holds only doc02's fact (source `e7ec7685-...`). `unavailable_sources` and `recovery_events` are empty.
- A reopened `retrieve` returns one fact and no unavailable source. `status` shows one `forgotten` publication at revision 1 with `plan.operation` `identity_forget`, one `current`, and no recovery event.
- A second `forget` and a `reconcile` of doc01 are refused with `Forgotten source accepts only a new publication at the next revision`.

Forgetting doc02 first is symmetric; the native test runs both orders.

## A dependent

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/<new root> --embedding loopback --dependent
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1
# exit 1: details.dependents lists doc01_text (source_text, 50d5313b-...) and doc01_instrument (corpus_object, fce9b214-...), both doc02's
uv run python -m cognee_lab.identity withdraw --root outputs/<new root> --source doc02
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1
```

The refusal happens before `begin`, so nothing changes: `retrieve` still returns two facts and `status` shows two current rows and no incident. After doc02 is withdrawn it consumes nothing, and the forget proceeds. doc02 keeps its original marker, fact and evidence (a withdrawal keeps them). HC, the HC to A edge and the shared singleton have no owner left and are gone. No fact returns.

The fence, from the other side: on a `--dependent` root, forget doc02, then forget doc01 with `--fault-stage forget_contributions`, then `readd --source doc02 --expected-revision 1`. The re-add is refused with `An input is a document or Entity whose forget is not finished; reconcile that forget first`, `details.dependents` names `doc01_text` and `doc01_instrument`, and nothing of doc02 is written back. `reconcile --source doc01` then finishes the forget. The native test `test_native_readd_of_a_consumer_waits_for_the_unfinished_forget` drives this.

## Interrupted forgets

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/<new root> --embedding loopback
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1 --fault-stage forget_identity
# exit 1 with recovery_event_id
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
# only doc02's fact; doc01 unavailable with publication_failed and the incident id
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

The other stages are `forget_contributions`, `forget_document`, `forget_verification`, `forget_identity_committed` and `forget_document_committed`. `status` shows the open incident with `operation: forget`, `stage` equal to the flag without `_committed`, and `origin: test/fault_injection`. `withdraw` is refused with `Retry the failed forget explicitly`, and `readd` with `Re-add needs a forgotten source`. The reconcile finishes the forget with the saved plan: doc01 is forgotten with the same empty report as the healthy run, doc02 is intact, and the same incident records `outcome: forgotten` with one verified `forget` attempt.

## Re-add

```bash
uv run python -m cognee_lab.identity readd --root outputs/<new root> --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

`readd` reads `source.txt` from the root (or `source02.txt` for doc02), checks its digest against the forgotten description, chunks it in memory with the root's budget, writes the forgotten description again at revision 2 with fresh mention UUIDs and a replacement for every reusable Entity the forget removed, and admits it (`admit_readd`, then `admit_inputs`) before any write. Then it adds the document again under the same data ID, chunks it, checks the native chunks against the admitted ones, adds the description as `identity_doc01_revision2.json` under the same identity data ID, and publishes it with `--expected-revision 1`. The captured fact is written from the new chunks.

Expected:

- `sources.doc01` is current at saved, registered and verified revision 2, with its marker, fact, ownership, evidence, unresolved mention and private singleton.
- The mention UUIDs differ from revision 1: g01 is `1384af69-23e8-5a8e-a4f4-9a8983ee2dd3` and g02 is `d9ee5111-cb06-54fd-98b8-e9913490d87d`, which are `uuid5(718efce2-..., "mention:r2:g01")` and `"mention:r2:g02"`. The private singleton, which the forget removed and nothing names, returns as `9b7f8477-b420-57e6-a343-ff73d921aa82`, which is `uuid5(718efce2-..., "entity:r2:replaces:fce9b214-10ab-5752-913d-3eae0dfc6b1f")`; the snapshot reports it as `private_singleton_entity_id`. HC, A and the shared singleton survived with doc02's refs, so the re-add references them under their UUIDs. Revision 1's `233cb019-...`, `3597e9fa-...` and `fce9b214-...` never return.
- `result.facts` holds both facts, one per current mention. `shared_variant` has two contributions and two owners, and `hc_entity` two owners. The borrowed controller is unchanged. No incident.
- A reopened `retrieve` returns both facts. `status` shows both rows current, doc01 at revision 2 with a publish plan. A healthy `reconcile` keeps all of this.
- `readd --expected-revision 2` on the current doc01 is refused with `Re-add needs a forgotten source`.

A re-add with the forgotten revision's mention UUIDs is refused as `fresh_uuid_reused`, one with mention UUIDs derived from another revision as `fresh_uuid_not_derived`, one that names a removed Entity UUID as `forgotten_uuid_reused`, one whose replacement UUID is not derived, or whose replacement of a named Entity uses the `replaces:` form, as `entity_uuid_not_derived`, one whose new UUID is already a graph node as `fresh_uuid_in_graph` or `entity_uuid_in_graph`, and one at any revision but N+1 as `revision_sequence` (unit tests in `tests/test_identity_forget.py`).

## Interrupted re-adds

```bash
uv run python -m cognee_lab.identity readd --root outputs/<new root> --source doc01 --expected-revision 1 --fault-stage nodes
# exit 1 with recovery_event_id; status shows a failed publish incident at stage nodes
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

The `nodes` stage comes before the captured facts are written. Before the review, `publish_one` passed no fact writer on a reconcile, so the reconcile of a re-add or of a first publication that failed there was refused with `Original-chunk fact ownership missing; explicitly rebuild`. Every publication now runs `write_semantics`, which skips a chunk whose fact and evidence are already in place, so the reconcile writes what the failure skipped and completes: doc01 current at revision 2 with its fact and evidence, doc02 intact, and the incident resolved with `outcome: restored`. Journey F4 and the native tests `test_native_reconcile_finishes_a_readd_that_failed_before_its_facts` and `..._a_first_publication_that_failed_before_its_facts` (the single `fixture` root with `--fault-stage nodes`) cover it.

## What survives a forget

Forget removes what the source owned from the graph, the vector index, the relational store and the data directory. It matters for an erasure intent, which step-4 item 3 decides: these are the places where a trace of the source remains, and each needs its own decision.

- **The kept description.** The forgotten row keeps the description of the last revision: the occurrence texts and spans of every mention group, the recipe names and descriptions of every Entity it declared, the text hash of the document, and the chunk IDs with their ranges. `status` prints it.
- **The forget plan.** The row's plan keeps the ownership snapshot: the `is_part_of` edges with their `edge_text`, which holds the first 80 characters of the document, the `limits` fact edge with its fact text, the contributions with their text ranges, `stored_files` (the file locations), and the refs of every owned object.
- **Recovery events.** An interrupted forget leaves its recovery event, with the identity and original data IDs, the stage, the error message and the attempts.
- **The fixture root's own files.** `source.txt`, `source02.txt`, `identity.json`, `identity02.json`, `identity_<doc>_revision<N>.json` and `multisource_result.json` lie outside the data root and are the user's own files; Cognee never touches them, and `readd` reads them.
- **Soft-deleted bytes in LanceDB.** A vector delete marks rows deleted; the bytes stay until a compaction and a cleanup of old table versions.
- **The graph and relational files.** Deleted rows and nodes remain in the file until the graph store checkpoints and SQLite runs `VACUUM`.
- **A withdrawn source cannot be forgotten.** Its document, chunks, facts, markers and evidence stay with the withdrawal, and forget refuses the withdrawn row (`withdrawn_source`). Erasing a withdrawn source is part of the same later decision.

## Scope

- Only a current source can be forgotten. A withdrawn source, and a source whose first publication failed, are refused (`withdrawn_source`, `forget_state`). Extending forget to them is a small change in the ledger and the model, left until a case needs it.
- A source with a dependent is refused, and a source cannot consume one whose forget is unfinished. Erasure that must proceed regardless of dependents, with its policy for them, is step-4 item 3.
- Re-add publishes the same document text and the same description at the next revision, with the removed Entities replaced. A re-add with other text or other decisions is a new description, which the admission rules of a replacement do not cover here.
- The dependents check sees `source_text` and `corpus_object` inputs. A `saved_record` input is not yet admitted anywhere.
- A forget whose recheck after `begin` finds a dependent fails at `forget_contributions`. That leaves a failed forget row: the source is withheld from `retrieve` with `publication_failed`, and the forget is retryable, through `forget` or `reconcile`, once the consumer no longer lists the input (withdraw it, or replace it with a description that drops the input).
- An unfinished forget can block the reconcile of a healthy consumer. A consumer may read an Entity that the forgetting source shares with a co-owner; the fence lets it publish, because the co-owner keeps the Entity. If the co-owner later withdraws, the forget would now remove that Entity, so the consumer's next `reconcile` is refused with `retiring_source`, and the forget's retry is refused with `dependent_source`. The way out is to withdraw the consumer, or to replace it with a description that drops the input; then the forget finishes.
- Two sources that both forgot a shared Entity get separate replacements on re-add, each derived from its own identity source and revision. Merging them into one Entity is matching work for Describe (step 6). This follows the user's 2026-10-22 decision that a re-add gives a removed Entity a new UUID.
- What these fixtures do not establish: the captured decisions, the fixture's dependency and the re-added description are supplied. They show the lifecycle mechanics through the real stores, not extraction or search quality.

## Code changed

- `storage.py`: the `forgotten` state, the forget guards, the publish-from-forgotten rule, the publish-starts-a-lineage rule, `RecordStore.row` and the shared guard messages (`FORGOTTEN_SOURCE`, `FAILED_FORGET`, `FAILED_REPLACEMENT`, `FORGET_STATE`, `READD_REVISION`, `STALE_REVISION`). `support/ledger_model.py` has the forget method, the re-add intent and the forget on a missing row; `support/ledger_mutants.py` has ten forget and re-add breaks. `PINNED` is 5889 nodes and 5770 sequences.
- `retirement.py` (new): `RETIRED_STATES`, `Dependent`, `consumes`, `dependents`, `retired_sources`, `removed_entities`, `readd_removed`, `refuse_retiring_inputs`, `owned_by`, `released`, the ownership snapshot, the contribution withdrawal and the survivor checks. `withdraw.py` and `forget.py` are sibling orchestrations over it.
- `forget.py`: `STAGES`, `COMMITTED_FAULTS`, `FAULT_STAGES`, `forget_plan` with `stored_files`, `stored_file_present` (a file no other `Data` row references), `refuse_dependents`, `remains`, `sweep`, `verify_forgotten` and `forget`. `__main__.py` takes the forget fault stages from `FAULT_STAGES`.
- `admission.py`: `admit_readd`, `check_removed_entity_ids`, `check_readd_entity_ids`, `replacement_entity_id` and `entity_ids_named`.
- `publish.py`: `Publisher.publish`, `reconcile`, `readd`, `admit_readd`, `admit_inputs` and `_publish`; `preflight` ends in `admit_inputs`, which holds the fence.
- `text_changes.py`: `from_plan` refuses a plan that holds `occurrence_map` next to a legacy key, with `recovery_plan`, instead of raising `TypeError`.
- `forget_fixture.py` (new): `add_dependency`, `describe_readd`, `readd` and `forget_checks`. `multisource.py` keeps the fixture, `publish_one` with an explicit operation, `private_singleton_id` and the snapshot. `fixture.py`: `write_semantics` is idempotent through `fact_written`, and the single fixture reconciles through `Publisher.reconcile`. `registered.read_texts` takes the texts of inputs that are not registered yet.

## Evidence

### Verification review fix round (2026-10-22)

The assistant (a subagent) ran these on the user's Mac on 2026-10-22 with loopback embeddings, on branch `stage6-forget` at `50c9e74`. The one commit after it changes this file only. The round answers a verification review: the re-add removed set, the shared stored file, the narrowed replacement rule, two Scope notes and the old-plan refusal.

- `uv run pytest -q -m 'not integration'`: 315 passed, 59 deselected, in 70 s.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 5889 nodes and 5770 sequences in 10 s. `--mutants` caught all 40 breaks by the property each names (exit 0). The round passes no new argument to `RecordStore`; the old-plan refusal runs before `begin`.
- `uv run python support/occurrence_check.py`: `PASS` in 101 s; `--mutants`: `PASS` in 28 s. `admission.py` changed `check_readd_entity_ids`.
- `uv run pytest -q -m integration`: 59 passed in 1232 s. The two new native tests failed before their fixes: `test_native_readd_replaces_what_a_later_forget_of_a_co_owner_removed` found doc02's re-add naming HC `9b2b4cb5-...` again, and `test_native_forget_finishes_when_another_item_keeps_the_stored_file` failed with `Forgotten source leaves stored_files_present`.
- `tests/test_identity_forget.py` (17 tests) adds the named replacement with the `replaces:` form refused for it, the unnamed replacement, two removed Entities one key names, the re-add removed set after a co-owner's later forget, and the old-plan refusal. The first, the fourth and the fifth failed before their fixes.
- Verify journeys, each with 0 FAIL rows: F1 (40 PASS, one more than before: the private singleton's `replaces:` UUID), F2 (19), F3 (20 for each of the six stages), F4 (15), W1 (32), W2 (21), W3 (19 for each of three stages), K1 (23), K2 (21), K3 (18 for each of two stages), K4 (18 for each of two stages), K5 (10), P1 (18), P2 (18), P3 (18) and P4 (12). `journey all` was not run.

### Review fix round

The assistant (a subagent) ran these on the user's Mac on 2026-10-22 with loopback embeddings, on branch `stage6-forget`. The first forget checkpoint's evidence (at `f5e581b` and `1f10476`) is in the git history of this file; the runs below are from the review fix round, on the head recorded in the handoff.

All runs below are on `835ee90`, the head of the review fix round; the one commit after it changes this file only.

- `uv run pytest -q -m 'not integration'`: 311 passed, 57 deselected, in 70 s.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 5889 nodes and 5770 sequences in 9.9 s, `accepted readd` reached 4 times. `--mutants` caught all 40 breaks by the property each names (exit 0), including the three the review added: `advance-guard-refuses-readd` as `INCONCLUSIVE`, `forget-without-a-row` by P5 in 3 steps and `complete-misnames-outcome` by P5 in 5 steps.
- `uv run python support/occurrence_check.py`: `PASS` in 100 s; `--mutants`: `PASS` in 28 s. `admission.py` gained the re-add rules.
- `uv run pytest -q -m integration`: 57 passed in 1204 s. `tests/test_identity_forget_native.py` has 12 tests: the forget and re-add in both orders (the re-added private singleton has a new UUID and HC survives), the dependent refusal followed by withdrawal and forget, the fence on a re-add while doc01's forget is failed, six fault stages with their reconcile, and the reconcile of a re-add and of a first publication that failed at `nodes`. Before their fixes, the committed-fault reconcile failed with `Forgotten source leaves stored_files_present`, the fence test saw the re-add succeed, and the two `nodes` reconciles failed with `Original-chunk fact ownership missing; explicitly rebuild`.
- `tests/test_identity_forget.py` (13 tests): the dependents check for text and for a removed Entity, removal through a retiring owner in each of its five states and through the document's chunks alone, the fence for a failed and a pending forget, the re-add derivation, the replacement of a removed reusable Entity with its refusals, and the mention UUID refusals.
- Verify journeys, each with 0 FAIL rows: F1 (39 PASS), F2 (19), F3 (20 for each of the six stages), F4 (15), W1 (32), W2 (21), W3 (19 for each of three stages), R1 (27), O2 (18 for each of two stages), P1 (18), P2 (18), P3 (18), P4 (12), K1 (23), K2 (21), K3 (18 for each of two stages), K4 (18 for each of two stages) and K5 (10). `journey all` was not run in this round; it passed with 1102 PASS and 0 FAIL on `d94a891` before it.
- The F1 run `outputs/verify/20261022T205733Z-f1` (dataset `d56263ae-115d-5146-a470-32e89409a73e`) re-added doc01 with mention `1384af69-...` and private singleton `9b7f8477-b420-57e6-a343-ff73d921aa82`. Its forget plan recorded, for the document, the stored copy under `roots/main/data/` and the fixture's own `roots/main/source.txt` as the original location; the sweep removed the first and never touches the second, which lies outside the data root. The plan's `is_part_of` edge text begins with the document's first 80 characters, as "What survives a forget" says.
- The F3 runs recorded incidents `61ade6ad-4050-514e-94bd-c36146cea920` (`forget_contributions`), `83edd4de-5580-5c5f-9089-e711a4a4c4f6` (`forget_identity`), `f4345183-018b-5a0a-866a-1939cbd27089` (`forget_document`), `1ac8a364-46fc-5ef5-8b84-a6bb5a77f6cf` (`forget_verification`), `272fd484-4134-5835-a25e-7dd05ed2c4ed` (`forget_identity_committed`, stage `forget_identity`) and `bae8498b-611d-5aa7-b475-17cdb9938e3e` (`forget_document_committed`, stage `forget_document`), each resolved with `outcome: forgotten`. The F4 run recorded `43486024-0412-5f01-9d85-5370a7103d31` at stage `nodes`, resolved with `outcome: restored`.
- Two thermo reviews ran on the first checkpoint; this round answers them. The landing playbook requires a review of this round before the merge.
