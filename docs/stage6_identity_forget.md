# Stage 6 forget: remove a source nothing depends on

**Date:** 2026-10-22. **Status:** implemented and verified by the assistant on the user's Mac with loopback embeddings. No user-reviewed fixture root exists yet.

`forget` removes one source from the two-source fixture: its original document, its generated identity source and everything only they owned. The other source keeps its own interpretation, the shared Entities it owns and the shared edge with only its contribution. `withdraw` stays separate: it retires a source's identity interpretation and keeps the document, its facts, markers and evidence. The user decided on 2026-10-22 that forget is a separate command, that a forgotten source leaves a record of its last revision so that a re-add continues at the next revision, that verification is the ledger model plus fault-stage journeys without an oracle, and that this checkpoint builds only the case where nothing depends on the source. A source that another source consumed is refused with the dependents listed. That refusal is a placeholder until step-4 item 3 decides what erasure does to dependents.

Commands, each on a `multi-fixture` root:

- `forget --source doc01|doc02 --expected-revision N` on a current source at revision N.
- `reconcile --source <doc>` finishes a failed forget.
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
| doc01 private singleton | `fce9b214-10ab-5752-913d-3eae0dfc6b1f` |
| Shared singleton (owned by both) | `ffe587e5-f2ec-53f9-bda0-10ef80582c84` |
| oscillations (fact target, owned by both documents' chunks) | `db651b0f-9add-5889-a2c5-800f96175085` |

Both sources are current at revision 1. Each has one `limits` fact from its own chunk, and both contribute to the HC to A variant edge.

## What forget removes

Forget runs four stages under the project writer reservation, after a durable plan is saved:

1. `forget_contributions`: this source's contribution payloads leave the shared identity edges, as in withdraw. Other owners' payloads and native ownership stay.
2. `forget_identity`: `cognee.forget(data_id=<identity source>, dataset_id=...)`.
3. `forget_document`: `cognee.forget(data_id=<original document>, dataset_id=...)`.
4. `forget_verification`: nothing of the source remains, and every survivor keeps what it owes. Then the row completes as `forgotten`.

Cognee 1.6.2's `forget(data_id=..., dataset_id=...)` without `memory_only` calls `datasets.delete_data` (`cognee/api/v1/forget/forget.py`, `cognee/api/v1/datasets/datasets.py`). On a graph that stores provenance in the graph, that path is `try_delete_data_by_graph_provenance`, which is `UnifiedStoreEngine.delete_by_document`: it collects every node and edge ref whose data ID is this item, the v1 document key and every v2 chunk key, removes those refs, and hard-deletes the nodes and edges left with no ref, with their vectors and triplet vectors (`execute_source_ref_removal`). Shared output is detached, not deleted. Then `delete_data` removes the `Data` row, the stored file under the root's data directory when no other row references it, and the `provenance_edge_evidence` rows of the item. A second call on a missing item finds nothing to delete and succeeds, which is what the retry relies on.

For doc01 that removes: the six-to-one chunk nodes and their `DocumentChunk_text` vectors, the document node, the `has_identity_mention` markers (owned by the chunk refs), the `limits` fact edge and its `contains` edges (owned by the producing chunk ref), the mention Entities g01 and g02 and their `Entity_name` vectors (owned by the identity source and the chunk refs, both gone), the private singleton (owned by the identity source only), the identity source's ownership of HC, A and the shared singleton, its `resolves_to` edge for r01, and the evidence rows and Data rows of both items. It keeps, with doc02's refs: HC, A, the shared singleton, oscillations and the HC to A edge with doc02's contribution only.

## The ledger

A row has one of five states: `pending`, `current`, `failed`, `withdrawn` and `forgotten`. Forget begins on a `current` row, or on a `failed` row that holds a forget plan, with the exact saved description and a plan whose `operation` is `identity_forget`. It completes as `forgotten` and keeps the revision and the verified revision. A forgotten row accepts only a new publication (`method="publish"`) at the next revision; every other method is refused as `forgotten_source`. A publish on any other saved row is refused as `recovery_choice`, so a publication always starts a lineage, from no row or from a forgotten one. A failed forget is resumed only by forget (`recovery_choice` otherwise), and `reconcile --source <doc>` routes a failed forget to it.

The forget plan holds `revision`, `runtime_profile`, `original_data_id`, `raw_data_location`, `chunk_ids`, `identity_edges` (the triples this source contributed to) and the ownership snapshot withdraw also records: `entities` (every node the identity source or the document's refs own, with its refs, type and indexed fields) and `edges` (every edge they own, with refs and properties). A retry reuses the saved plan, because native deletion has detached or removed what a new scan would find.

Decisions taken in this checkpoint:

- **The forgotten row keeps its description.** The re-add admission compares against it (no UUID of the forgotten revision may return), `status` can say what was forgotten, the dependents check of a later forget skips it, and `retrieve` keeps its mention labels out of the alias set. Dropping it would need a nullable column and gain nothing. The description holds the occurrence texts of the mentions, so an erasure policy that must drop those too is a later decision.
- **Re-add is a publication.** `Publisher.publish` chooses `method="publish"` when the description's revision is the expected revision plus one, and `reconcile` otherwise. The ledger admits publish only from no row or a forgotten row. Before the publish, `admit_readd` requires the same dataset, identity source and document, the next revision, and every mention group's UUID derived as `uuid5(identity_data_id, "mention:r{N+1}:{key}")`, unused by the forgotten revision and absent from the graph. A new reusable Entity must derive too. The admission rules are the ones a replacement uses for a fresh group; only the fresh-key rule does not apply, because a re-add keeps its keys.
- **Fault stages.** The four stages above. The first three fail after their write, the last before the acknowledgement, so each retry repeats idempotent work.
- **`status` and `retrieve`.** `status` shows the row as `forgotten` at its revision with the forget plan. `retrieve` neither returns a forgotten source nor lists it as unavailable, as for a withdrawn one. A failed forget is unavailable with `publication_failed` and its incident ID.

## Dependents

Source Y depends on source X when Y's description lists X's document as a `source_text` input, or lists as a `corpus_object` input an Entity whose every recorded owner is X (its identity source or its document's chunks). A chunk or span input names its document through a `source_text` input of the same description, so the text check covers it. An Entity another source also owns survives a forget with its fields, so a reader of it is unaffected. Withdrawn and forgotten sources consume nothing. `dependents()` in `validation.py` is the one check; `reject_dependents` in `text_changes.py` calls it with no sole-owned Entities, because a text edit keeps the document.

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

- `sources.doc01` has `state: forgotten`, `saved_revision` 1, `verified_revision` 1 and a `forget` report in which `original_data_present`, `identity_data_present`, `raw_file_present`, `document_node_present`, `original_fact_present`, `private_singleton_present`, `private_singleton_indexed` and `identity_contribution_present` are false, `chunks_present`, `chunk_vectors_present`, `mention_nodes_present` and `mention_vectors_present` are empty, and `evidence_rows`, `owned_nodes` and `owned_edges` are 0.
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

## Interrupted forgets

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/<new root> --embedding loopback
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1 --fault-stage forget_identity
# exit 1 with recovery_event_id
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
# only doc02's fact; doc01 unavailable with publication_failed and the incident id
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

The other stages are `forget_contributions`, `forget_document` and `forget_verification`. `status` shows the open incident with `operation: forget`, `stage` equal to the flag and `origin: test/fault_injection`. `withdraw` is refused with `Retry the failed forget explicitly`, and `readd` with `Re-add needs a forgotten source`. The reconcile finishes the forget with the saved plan: doc01 is forgotten with the same empty report as the healthy run, doc02 is intact, and the same incident records `outcome: forgotten` with one verified `forget` attempt. The run of 2026-10-22 on the development root recorded incident `48e9d36e-a458-5adf-8f89-dd54df0a459b` for the `forget_identity` stage.

## Re-add

```bash
uv run python -m cognee_lab.identity readd --root outputs/<new root> --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

`readd` reads `source.txt` from the root (or `source02.txt` for doc02), checks its digest against the forgotten description, adds the document again under the same data ID, chunks it with the root's budget, writes the forgotten description again at revision 2 as `identity_doc01_revision2.json` with fresh mention UUIDs, adds it under the same identity data ID, and publishes it with `--expected-revision 1`. The captured fact is written again from the new chunks.

Expected:

- `sources.doc01` is current at saved, registered and verified revision 2, with its marker, fact, ownership, evidence, unresolved mention and private singleton.
- The mention UUIDs differ from revision 1: g01 is `1384af69-23e8-5a8e-a4f4-9a8983ee2dd3` and g02 is `d9ee5111-cb06-54fd-98b8-e9913490d87d`, which are `uuid5(718efce2-..., "mention:r2:g01")` and `"mention:r2:g02"`. Revision 1's `233cb019-...` and `3597e9fa-...` never return.
- `result.facts` holds both facts, one per current mention. `shared_variant` has two contributions and two owners, and `hc_entity` two owners. The borrowed controller is unchanged. No incident.
- A reopened `retrieve` returns both facts. `status` shows both rows current, doc01 at revision 2 with a publish plan. A healthy `reconcile` keeps all of this.
- `readd --expected-revision 2` on the current doc01 is refused with `Re-add needs a forgotten source`.

A re-add with the forgotten revision's UUIDs is refused as `fresh_uuid_reused`, one with UUIDs derived from another revision as `fresh_uuid_not_derived`, one whose UUID is already a graph node as `fresh_uuid_in_graph`, and one at any revision but N+1 as `revision_sequence` (unit tests in `tests/test_identity_forget.py`).

## Scope

- Only a current source can be forgotten. A withdrawn source, and a source whose first publication failed, are refused (`withdrawn_source`, `forget_state`). Extending forget to them is a small change in the ledger and the model, left until a case needs it.
- A source with a dependent is refused. Erasure that must proceed regardless of dependents, with its policy for them, is step-4 item 3.
- Re-add publishes the same document text and the same description at the next revision. A re-add with other text or other decisions is a new description, which the admission rules of a replacement do not cover here.
- The dependents check sees `source_text` and `corpus_object` inputs. A `saved_record` input is not yet admitted anywhere.
- What these fixtures do not establish: the captured decisions, the fixture's dependency and the re-added description are supplied. They show the lifecycle mechanics through the real stores, not extraction or search quality.

## Code changed

- `storage.py`: the `forgotten` state, the forget guards, the publish-from-forgotten rule and the publish-starts-a-lineage rule. `support/ledger_model.py` gains the forget method, the re-add intent, `begins_from` and `owns_forgotten`; `support/ledger_mutants.py` gains seven breaks. `PINNED` is 5548 nodes and 5429 sequences.
- `forget.py`: `forget`, `forget_plan`, `sole_owned`, `verify_forgotten` and `admit_readd`. `withdraw.py` now exports the ownership snapshot, the contribution withdrawal, `retired_sources` and the survivor checks that both operations use; withdraw's behavior is unchanged, except that a forgotten source and its document no longer oblige survival in a later withdraw's verification.
- `validation.py`: `dependents` and `IntentError.details`. `text_changes.py`: `reject_dependents` calls it, and the legacy plan readers are deleted.
- `publish.py`: `Publisher.forget`, the method choice, `admit_readd` before a re-add, and the failed-forget refusal. `retrieve.py`: a forgotten row is not unavailable, and `read_texts` in `registered.py` reads every text input for validation and for publication.
- `multisource.py`: `forget`, `readd`, `--dependent`, `describe_readd`, `forget_checks` and `hc_entity` in the snapshot. `__main__.py`: the commands, the flag and the four fault stages.

## Evidence

The assistant (a subagent) ran these on the user's Mac on 2026-10-22 with loopback embeddings, on branch `stage6-forget`. The source and tests are at `f5e581b`; `1f10476` differs from it by one refusal message only. The UUIDs above come from these runs.

- `uv run pytest -q -m 'not integration'`: 300 passed, 52 deselected, in 77 s, on the final head. One earlier run on `1f10476` failed `test_saved_replacement_is_guarded_and_retried_without_new_intent` on a refusal message only; the message now names replacement.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 5548 nodes and 5429 sequences in 11.6 s. `--mutants` caught all 36 property breaks by the property each names, and `begin-always-busy` was `INCONCLUSIVE` as expected (37 breaks). `support/occurrence_check.py` was not run, because `admission.py` is unchanged.
- `tests/test_identity_forget.py` (6 tests): the dependents check for text and for a sole-owned Entity, with withdrawn and forgotten readers skipped; sole ownership from plan refs; the retired-source set; the re-add derivation; and the refusals `fresh_uuid_reused`, `revision_sequence`, `fresh_uuid_not_derived`, `source_changed` and `fresh_uuid_in_graph`. `tests/test_identity_storage.py` gains the ledger path: forget refused without a forget plan, failed and retried, `forgotten` at revision 1, every other method refused on the forgotten row, re-add at revision 2, and forget refused on a failed first publication and on a withdrawn source.
- `uv run pytest -q -m integration tests/test_identity_forget_native.py`: 7 tests. The forget and re-add in both orders, the dependent refusal followed by withdrawal and forget, and the four fault stages with their reconcile. The first run gave 5 passed and 2 failed; the 2 failures were the refusal messages of a second forget and of a reconcile on a forgotten row, which the fix in `1f10476` corrected. The rerun of those 2 tests passed in 80 s; the other 5 passed in the first run (153 s for all 7).
- `uv run pytest -q -m integration tests/test_identity_native.py tests/test_identity_text_native.py`, the native files that drive publish, withdraw, replace, retrieve and the text changes: 17 passed, 1 deselected (the non-integration backend-access test), in 384 s. This run started on `1f10476` and the message change of `f5e581b` landed while it ran; no test in these files asserts that message.
- Verify journeys, each with 0 FAIL rows (each count includes three lab-store guard rows): F1 (38 PASS), F2 (19), F3 (20 for each of the four stages), W1 (32), W2 (21), W3 (19 for each of three stages), R1 (27), O2 (18 for each of two stages) and P4 (12). The first F1 run had the same 2 message failures as the native test and passed after the fix. `journey all` was not run.
- The F1 run `outputs/verify/20261022T190004Z-f1` re-added doc01 with mention `1384af69-23e8-5a8e-a4f4-9a8983ee2dd3` in dataset `d4f996ca-f1c4-50ed-a43d-67c2ecdc83ef`. The F3 runs recorded incidents `0cbebc04-3c77-593a-b68e-041aa35104c7` (`forget_contributions`), `c4b9c093-b0d1-5742-a349-ed7d23b08c1e` (`forget_identity`), `03ec6605-80fa-53ca-a18e-b6456fc7ce78` (`forget_document`) and `0aa67256-6224-52cf-aa28-9cd034ddf16a` (`forget_verification`), each resolved with `outcome: forgotten`.
- Two thermo reviews have not run on this branch yet. The landing playbook requires them before the merge.
