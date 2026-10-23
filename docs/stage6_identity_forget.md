# Stage 6 forget: erase a source and remove what depended on it

**Date:** 2026-10-23 (checkpoint I). **Status:** implemented and verified by the assistant on the user's Mac with loopback embeddings. No user-reviewed fixture root exists yet. The [history note](#history) at the end records what checkpoint F built on 2026-10-22 and what this checkpoint changed.

`forget` erases one source: its original document, its generated identity source and everything only they owned. The ledger row keeps a tombstone of identifiers and no content. Other sources keep their own interpretations, the shared Entities they own and the shared edges with only their contributions. When another source based a decision on the forgotten source, the forget removes that decision too, in a revision of that source, after the caller confirms the forget's impact. `withdraw` stays separate: it retires a source's identity interpretation and keeps the document, its facts, markers and evidence.

The user decided on 2026-10-23:

1. There is one command, `forget`, and it always erases. There is no restorable forget.
2. After verification, the forgotten row keeps only identifiers: IDs, digests, the revision and when it was forgotten. Occurrence texts, recipe names and descriptions, and every excerpt go. The forget plan keeps IDs, refs and ranges and loses every text field. Recovery-event messages go; IDs, stage and attempts stay.
3. Fixture input files are the caller's own inputs. A forget lists them in its report and its dry run, and never deletes them.
4. Dependents are removed, not withheld. A dependent decision is a resolution, with its group, or a variant assignment whose inputs cite the forgotten source: its document's text, a span or chunk of it, or an Entity the forget removes. Its removal is a new revision of the dependent.
5. A forget that affects no other source runs at once. A forget that would change another source's decisions needs `--confirm <token>`, the token of its dry run. Thresholds for what is significant belong to the caller, never to the code.
6. `readd` stays, as a fresh publication from the caller's files at the next revision.
7. Any source can be forgotten: current, withdrawn, or one whose first publication failed.
8. Old formats are not read: a forgotten row that still holds its description is refused. Development roots that hold one are regenerated. The reviewed roots under `outputs/stage6_*` are never touched.
9. Withholding stays for text edits (checkpoint H), where the input still exists and may be re-confirmed.
10. Saved-record inputs, chains of dependents and the non-identity example are deferred to the next checkpoint.

A review of the spec (2026-10-23, verdict proceed) fixed the order, the token, the admission rule and the tombstone shape; those resolutions are built as stated below.

## Commands

On a `multi-fixture` root, and on a `glossary-fixture` root for `doc01` or `glossary`:

- `forget --source <doc> --expected-revision N --dry-run` reports what the forget would do and the token to confirm. It writes nothing, and it returns before any result file is written.
- `forget --source <doc> --expected-revision N` forgets a source nothing depends on.
- `forget --source <doc> --expected-revision N --confirm <token>` forgets a source whose forget removes other sources' decisions.
- `reconcile --source <doc>` finishes a failed forget, the unfinished removals of a completed forget, or a failed re-add.
- `readd --source <doc> --expected-revision N` publishes a forgotten source again at revision N+1 from the caller's files.
- `multi-fixture --dependent` creates the two-source fixture with doc02 reading doc01.

The CLI routes `reconcile`, `forget` and `readd` by the fixture kind that the root marker `stage6-fixture.json` records under `fixture` (the creation command). A root made before this checkpoint has no fixture kind, and those three commands refuse it with `Root predates fixture kinds; regenerate it`.

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

Both sources are current at revision 1. Each has one `limits` fact from its own chunk, and both contribute to the HC to A variant edge. The [dependencies guide](stage6_identity_dependencies.md#the-glossary-fixture) gives the glossary fixture's IDs.

## The order of a forget

Forget erases the source first, then revises its dependents. The writer reservation forbids nesting one attempt in another, so the two parts run one after the other:

1. **Before `begin`.** The forget computes its impact from the saved descriptions and the forget plan, and checks the token. A refusal writes nothing.
2. **One attempt on the source, under one reservation.** `begin` saves the plan with the token and the dependents' identity IDs. Five stages follow:
   1. `forget_impact` computes the impact again from the saved plan and the rows, and refuses with `impact_changed` when its token differs from the saved one.
   2. `forget_contributions` removes this source's contribution payloads from the shared identity edges, as withdraw does, and deletes the withholding rows that this source holds as a dependent or that its edits wrote for others.
   3. `forget_identity` runs `cognee.forget(data_id=<identity source>, dataset_id=...)`, then the sweep.
   4. `forget_document` runs `cognee.forget(data_id=<original document>, dataset_id=...)`, then the sweep.
   5. `forget_verification` checks that nothing of the source remains and that every survivor keeps what it owes. Then `complete(state="forgotten", tombstone=...)` writes the tombstone, the scrubbed plan and the scrubbed recovery events in the same transaction as the state change.
3. **Each dependent's removal revision, each under its own reservation**, through `replace_one`, the unchanged-text replacement that the refresh after a text edit also uses.

Whether a dependent is done is derived from the rows, with no new ledger state: a dependent is unfinished while a saved source that is not retired still cites the tombstone's document or one of its removed Entities, or while its removal revision is failed. `forget` or `reconcile` on a forgotten source resumes the unfinished dependents without a new attempt on the source, and refuses with `Forgotten source accepts only a new publication at the next revision` when none is left. A dependent failure is reported beside the completed forget, as `dependents_failed`, and the command exits 1. Until the removal completes, checkpoint H's live validation withholds every decision that still cites the forgotten document or a removed Entity with `input_removed`. `readd` refuses while any dependent is unfinished (`dependents_unfinished`).

A crash here means a caught failure or an injected fault stage. A hard kill can leave the writer reservation held, as before.

Cognee 1.6.2's `forget(data_id=..., dataset_id=...)` without `memory_only` calls `datasets.delete_data`. On a graph that stores provenance in the graph, that path is `UnifiedStoreEngine.delete_by_document`: it collects every node and edge ref whose data ID is this item, the v1 document key and every v2 chunk key, removes those refs, and hard-deletes the nodes and edges left with no ref, with their vectors and triplet vectors. Shared output is detached, not deleted. Then `SqlAlchemyAdapter.delete_data_entity` deletes the `Data` row and commits, and only then sweeps the item's `provenance_edge_evidence` rows and its stored files, each once no other `Data` row references it.

**The sweep.** A process that dies between that commit and the sweep leaves the evidence rows and the files behind, and a retry finds no `Data` row and sweeps nothing. So forget runs the same sweep itself after each native forget: `delete_edge_evidence(dataset_id, data_id)` and `remove_data_file_if_unreferenced(location)` for each location the plan recorded. Both are idempotent. The verification refuses while an evidence row remains, or a stored file under the data root that no other `Data` row references. The fault stages `forget_identity_committed` and `forget_document_committed` stand in for the death after the commit.

## The tombstone

The forgotten row's `description` column holds a tombstone, JSON with `kind: "identity_source_tombstone"`:

| Field | Holds |
|---|---|
| `dataset_id`, `identity_data_id`, `original_data_id` | Who the source was |
| `revision` | The last revision, so a re-add continues at the next one |
| `text_sha256`, `description_sha256` | The digests of the document and of the forgotten description |
| `mention_ids` | The last revision's mention UUIDs by group key |
| `entity_ids` | The last revision's reusable Entity UUIDs |
| `removed_entity_ids` | The Entities the forget removed |
| `impact_token` | The confirmed token, or null when the forget affected no other source |
| `forgotten_at` | When the forget completed |

The plan keeps, by whitelist, `operation`, `revision`, `origin`, `method`, `original_data_id`, `stored_files`, `chunk_ids`, `identity_edges`, `entities` (refs, type and indexed fields) and `edges` (source, target, relation and refs). Every edge property goes: the `is_part_of` edge text that quoted the document's first 80 characters, the fact texts and the contributions. Every recovery event of the source loses `message`, its own and each attempt's, resolved events included; the ledger check's P5 allows that one change to a resolved event. IDs, stage, reason code, origin and attempts stay.

`RecordStore.rows()` refuses a forgotten row whose description is not a tombstone with `forgotten_format`.

Readers of a forgotten row read the tombstone: `stages.saved_row` skips the description check, `retrieve` leaves its mentions out of the alias set, `validate_uses` counts its mention and reusable UUIDs, `admit_readd` checks against it, and both fixtures' `current_sources` fall back to the root's identity file. `retirement.py` takes a `SourceIds` (dataset, identity source, document) from a description or a tombstone.

## Impact, dry run and token

`erasure.impact` computes, from the saved descriptions and the forget plan's ownership snapshot and never from the live graph, each dependent and what its removal revision would do:

- Each decision it removes, with the input that causes it: `input_ref`, `kind` and the `consumed` UUID (the document for a text, span or chunk; the Entity for a corpus object). A resolution becomes unresolved; a variant is dropped.
- `dropped_entities`: the reusable recipes that a removed decision named and no remaining decision names. Other owners keep the Entity, because the replacement only retires this source's declaration.
- `kept_entities`: such recipes that stay because a saved source still lists the Entity as a corpus input. A third source counts, and so does the dependent itself; dropping its last declaration could take the Entity out of the graph under a reader.
- `unlinked_mentions`: the mentions whose facts lose their identity link.
- `dropped_inputs`: the inputs nothing cites any more.
- `blocked`: the dependent's own attempt is pending or failed. Such a dependent does not block the forget; its removal waits (`dependent_unfinished`) until its own method finishes it, and a rerun of `forget` or `reconcile` then removes it.

The token is `object_digest` over the source's dataset, identity ID and revision, the removed Entity IDs, and per dependent its identity ID, assignment keys, each decision's citing inputs, kind and outcome, its dropped Entity IDs and its blocked flag. `forget` checks it before `begin` and again in `forget_impact`. Without a token, a forget with dependents is refused with `confirmation_required`, and a stale token with `impact_changed`; both carry the dry-run report in `details`. A retry of a failed forget without a token keeps the impact its first attempt confirmed.

The dry run returns the impact and:

- `counts`: dependents, blocked dependents, decisions, unresolved, dropped, dropped Entities and facts that lose their identity link.
- `scrubbed`: what the tombstone drops: the occurrences, recipes and explanations of the description, the plan's edges with properties, and the source's recovery-event messages.
- `residue`: what erasure leaves physically. LanceDB marks deleted vector rows and keeps their bytes until a compaction and a cleanup of old table versions. The graph store and SQLite keep deleted rows in their files until a checkpoint and `VACUUM`. Erasure is logical.
- `caller_files`: the root files that hold the source's own inputs and the commands' results (`source.txt`, `identity.json`, `identity_doc01_revision*.json` and `multisource_result.json` for doc01, for example). They are listed, never deleted.
- `token`.

## The removal revision

`erasure.removal_revision` writes the dependent's next revision with unchanged text:

- A resolution citing what the forget removed becomes `unresolved` in place: the same key and group, its input refs without the erased keys (the original document when nothing else remains), and a producer new in the revision.
- A variant citing it is dropped, with this dependent's contribution to that edge.
- Groups lose the erased input keys, with the same fallback.
- A recipe goes as `dropped_entities` above says.
- Inputs nothing cites any more are dropped.

The producer is `forget_<forgotten identity ID>_r<revision>`: method `captured_fixture`, implementation `removed by forget`, and a configuration that names `forgotten_identity_data_id`, `forgotten_document_id`, `removed_entity_ids` and `impact_token`.

**Admission.** The occurrence admission admits a removal revision through one new rule, `check_erasure_removals`, after rule 5. A revision that introduces a producer with that implementation is an erasure removal and nothing else. `check_erasure_complete` requires every old decision citing the configured document, a span or chunk of it, or a configured Entity, to be removed as above, and no erased input to remain. `check_erasure_confined` requires every other decision, group, input, recipe and producer to be unchanged, apart from uncited inputs that go, the one producer added, and recipes that only removed decisions named. A configuration that names the dependent's own document, or is malformed, is refused with `erasure_configuration`. `check_scoped_variants` lets an erasure removal drop a corpus- or span-scoped variant that cites what the forget removed, which it refuses otherwise. With changed text an erasure removal is refused (`erasure_unrelated`), since its groups differ. The token is checked outside admission.

`support/erasure_worlds.py` holds fifteen rule 6 rows for the occurrence check, each stated for a text edit and for unchanged text, on steady worlds (every group continues and nothing is new): five admitted removals (a continuing resolution citing a span, citing a removed Entity, its group stripped too, a document-scoped and a corpus-scoped variant dropped with HC) and ten refusals (a kept variant, a kept resolution, a resolution unresolved under its old producer, a bystander unresolved, an unnamed recipe dropped, an erased input kept, a decision added, another document configured, the span left in a group, and a corpus-scoped variant dropped without a removal producer). `support/occurrence_mutants.py` gains four breaks: the rule absent (`allow_any_erasure`), a partial removal (`erase_partially`), a removal beyond what was forgotten (`erase_beyond_the_forgotten`), and a scoped-variant drop without the removal producer (`drop_scoped_variants_freely`).

## The ledger

A row has one of five states: `pending`, `current`, `failed`, `withdrawn` and `forgotten`. Forget begins on a `current` row, a `withdrawn` row, a `failed` row whose plan is a publication (a first publication, a reconcile or a re-add), or a `failed` row that holds a forget plan, which only forget resumes. A failed replacement or withdrawal is refused, since only its own method resumes it. Forget completes as `forgotten` with the tombstone. A forgotten row accepts only a new publication at the next revision; every other method is refused as `forgotten_source`. Every begin at the forgotten revision is also refused by the description check, since no description equals a tombstone.

`support/ledger_model.py` lets forget begin on current, failed and withdrawn rows; withdraw and forget now share the withdrawn row (`Method.terminals`). The checker passes the tombstone to `complete`. A seventh property, P7, states that a forgotten row holds no description content: its description is the tombstone of the description its forget began, its plan keeps only identifier fields with no edge property, and no recovery event of the source keeps a message. `PINNED` moves from 5889 nodes and 5770 sequences to 6287 and 6156, because forget now begins on withdrawn and failed-publication rows. `REACHABLE` gains a forget on a withdrawn row and on a failed publication.

## Forget doc01

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/<new root> --embedding loopback
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1 --dry-run
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
uv run python -m cognee_lab.identity status --root outputs/<new root>
```

The dry run finds no dependent (`confirmation_required: false`) and lists g01, g02 and the private singleton as removed Entities. The forget writes `multisource_result.json`. Expected:

- `sources.doc01` has `state: forgotten`, `saved_revision` 1, `verified_revision` 1 and a `forget` report. The report is `remains()` from `forget.py`, which the verification requires to be all false, empty or zero (`original_data_present`, `identity_data_present`, `stored_files_present`, `document_node_present`, `chunks_present`, `chunk_vectors_present`, `evidence_rows`, `identity_contribution_present`, `owned_nodes`, `owned_edges`), plus the fixture's fields `mention_nodes_present`, `mention_vectors_present`, `removed_entities_present`, `original_fact_present`, `private_singleton_present` and `private_singleton_indexed`, also all absent, and `removed_entities`.
- `forget.dependents_revised` is empty and `dependents_failed` is null.
- `sources.doc02` is unchanged: current at 1/1/1 with its marker, fact, ownership, evidence, private singleton and unresolved mention.
- `shared_variant` has one contribution and one owner, both doc02's. `hc_entity` is present with one owner. The shared singleton stays present and indexed. `borrowed_entity` keeps its `updated_at` and `description`.
- `result.facts` holds only doc02's fact. `unavailable_sources` and `recovery_events` are empty.
- `status` shows one `forgotten` row at revision 1 with `plan.operation` `identity_forget`. Its description is a tombstone whose `mention_ids.g01` is `233cb019-...`; the row holds no occurrence text, its plan no `runtime_profile` and no edge property.
- A second `forget` and a `reconcile` of doc01 are refused with `Forgotten source accepts only a new publication at the next revision`.

Forgetting doc02 first is symmetric; the native test runs both orders.

## A dependent

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/<new root> --embedding loopback --dependent
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1 --dry-run
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1
# exit 1: confirmation_required, with the dry-run report in details
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1 --confirm <token>
```

doc02's r01 lists `doc01_text` (doc01's document) and `doc01_instrument` (doc01's private singleton `fce9b214-...`, which the forget removes). The dry run lists doc02 as the one dependent, not blocked, with r01 `unresolved` citing `doc01_instrument` (`corpus_object`) and `doc01_text` (`source_text`, doc01's document); `unlinked_mentions` is doc02's g01 mention `e7ec7685-...`; `dropped_inputs` are those two keys and `dropped_entities` is empty, since doc02's v01 still names the Helios controller. Without the token the forget is refused before any write: two facts, two current rows, no incident. With it:

- doc01 is forgotten with the same empty report as above.
- `forget.dependents_revised` is `[{identity_data_id: ca84d73d-..., revision: 2}]`.
- doc02 is current at revision 2. r01 is `unresolved` under producer `forget_718efce2-4251-5f6f-8318-417bb4dd3525_r2` with input refs `doc01` and `existing_A`; v01 is unchanged; `doc01_text` and `doc01_instrument` are gone. doc02's local fact and evidence stay.
- `result.facts` is empty: the HC query reaches the Helios controller through doc02's v01, and no accepted link leads from there to doc02's mention any more.
- A re-add of doc01 brings back doc01's fact. doc02's r01 stays unresolved: a re-add never resurrects a removed decision.

## Confirmation

The token changes whenever the affected-decision set changes. On a `--dependent` root, forget doc02 first; doc01's dry run then finds no dependent. Re-add doc02: its caller file reads doc01 again, so doc01's forget with the first token is refused with `impact_changed` before any write, and its report lists doc02 with a new token, which is accepted.

## Interrupted removals

```bash
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1 --confirm <token> --fault-stage forget_dependents
# exit 1; doc01 forgotten, dependents_failed injected_failure
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
# doc02's r01 unavailable with input_removed
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

`forget_dependents` stops after the forget completed and before the first removal revision begins, as a process that dies there leaves it. doc02 stays current at revision 1 and still cites doc01, so retrieval and `status` withhold r01 with `input_removed`. `forget_dependent_revision` fails the removal revision at `replace_registered`: doc02 is failed and withheld whole with `publication_failed`, and its replace incident opens. Either way the command exits 1, `readd` of doc01 is refused with `dependents_unfinished`, and `reconcile --source doc01` (or `forget` again) finishes the removal: doc02 current at revision 2 with r01 unresolved, nothing unavailable, every incident resolved.

## A dependent that is pending or failed

On a `--dependent` root, `withdraw --source doc02 --fault-stage withdraw_contributions` leaves doc02 failed. doc01's dry run marks doc02 `blocked`, and its token covers that. The forget completes; doc02's removal waits with `dependents_failed.code` `dependent_unfinished` and doc02 under `forget.dependents_waiting`, and the command exits 1. Once `withdraw --source doc02` finishes the withdrawal, doc02 reads nothing, and `reconcile --source doc01` has nothing left to do.

## Any source

- A withdrawn source keeps its document, chunks, facts, markers and evidence. `forget` removes them: on a `multi-fixture` root, withdraw doc02, then forget it; the report is all absent and doc01's fact still returns.
- A source whose first publication failed is forgotten as it stands: `multi-fixture --source doc02 --fault-stage nodes`, then forget doc02. Its incident is resolved with `outcome: forgotten` and no message.

## The glossary

On a `glossary-fixture` root, doc01's r01 and v01 cite the glossary's HC entry as the span `glossary_hc`. The dry run of the glossary's forget lists r01 `unresolved` and v01 `dropped`, both citing `glossary_hc` (`text_span`, the glossary document `8c6f6b13-...`). HC (`9b2b4cb5-...`) is dropped, since only v01 named it and doc01 owned it alone; the Helios controller (`8b4bff50-...`) is kept, since doc01 still reads it as `existing_A`. `glossary` and `glossary_hc` are dropped. With the token the glossary is forgotten and doc01 goes to revision 2 with r01 alone, unresolved under `forget_16e89187-1559-5f97-b957-d86f46315407_r2`; neither the HC query nor the Helios controller query returns a fact. `readd --source glossary --expected-revision 1` brings the glossary back at revision 2 from `glossary.txt` and `glossary_identity.json`, with its HC entry at [10, 62); doc01's removed decisions stay removed.

## Interrupted forgets

```bash
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source doc01 --expected-revision 1 --fault-stage forget_identity
# exit 1 with recovery_event_id
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

The stages are `forget_impact`, `forget_contributions`, `forget_identity`, `forget_document`, `forget_verification`, `forget_identity_committed` and `forget_document_committed`. While the forget is failed, `retrieve` returns only doc02's fact and lists doc01 as unavailable with `publication_failed` and the incident ID; `status` shows the open incident with `operation: forget`, `stage` equal to the flag without `_committed`, and `origin: test/fault_injection`. `withdraw` is refused with `Retry the failed forget explicitly`, and `readd` with `Re-add needs a forgotten source`. The reconcile finishes the forget with the saved plan: doc01 is forgotten with the same empty report as the healthy run, doc02 is intact, and the same incident records `outcome: forgotten` with one verified `forget` attempt, its reason code, and no message.

## Re-add

```bash
uv run python -m cognee_lab.identity readd --root outputs/<new root> --source doc01 --expected-revision 1
```

`readd` reads the caller's files from the root: `source.txt` and `identity.json` for doc01 (`source02.txt` and `identity02.json` for doc02, `glossary.txt` and `glossary_identity.json` for the glossary). The text must have the digest the identity file states (`source_changed` otherwise). It chunks the text in memory, writes the identity file's description at the forgotten revision plus one with fresh mention UUIDs and a replacement for every reusable Entity the forget removed, and admits it before any write: `admit_readd` against the tombstone, then `admit_inputs`. Then it adds the document again under the same data ID, checks the native chunks against the admitted ones, adds the description as `identity_<doc>_revision<N>.json` under the same identity data ID, and publishes it.

The re-add is admitted like a first publication apart from two rules: the next revision, and no mention or Entity UUID that the tombstone records or that the forget removed. Data IDs, the identity ID and chunk IDs return. A new group's UUID is `uuid5(identity_data_id, "mention:r{N+1}:{key}")`. A reusable Entity the forget removed returns under a new UUID: from the next revision and a key that names it, `uuid5(identity_data_id, "entity:r{N+1}:{key}")`, or, for an Entity nothing names, `uuid5(identity_data_id, "entity:r{N+1}:replaces:{removed UUID}")`. The re-add may bring other text or other decisions; the comparison with the forgotten description is gone, since the tombstone keeps none.

For doc01 after the healthy forget: doc01 is current at saved, registered and verified revision 2 with its marker, fact, ownership, evidence, unresolved mention and private singleton. g01 is `1384af69-23e8-5a8e-a4f4-9a8983ee2dd3` and g02 `d9ee5111-cb06-54fd-98b8-e9913490d87d`; the private singleton, which nothing names, returns as `9b7f8477-b420-57e6-a343-ff73d921aa82`. HC, A and the shared singleton survived with doc02's refs, so the re-add references them under their UUIDs. Both facts return, the shared variant has two contributions and two owners, and HC two owners. A second `readd` is refused with `Re-add needs a forgotten source`.

With changed files: append ` HC was serviced.` to `source.txt`, and the re-add is refused with `The caller's text file and identity file disagree`; set `inputs.doc01.text_sha256` in `identity.json` to the new text's digest, and the re-add publishes doc01 at revision 2 with the new text, its fact, and both facts in the result.

A re-add with the forgotten revision's mention UUIDs is refused as `fresh_uuid_reused`, one with mention UUIDs derived from another revision as `fresh_uuid_not_derived`, one that names a removed Entity UUID as `forgotten_uuid_reused`, one whose replacement UUID is not derived, or whose replacement of a named Entity uses the `replaces:` form, as `entity_uuid_not_derived`, one whose new UUID is already a graph node as `fresh_uuid_in_graph` or `entity_uuid_in_graph`, and one at any revision but N+1 as `revision_sequence` (unit tests in `tests/test_identity_forget.py`).

**What a re-add replaces.** A re-add replaces each Entity that `readd_removed` returns: the Entities whose every recorded owner in the plan snapshot is this source or a retiring one, computed from the rows at the re-add, and every Entity the plan recorded that the graph no longer holds. The rows alone are not enough: if doc02 is forgotten while doc01 still owns HC, HC survives; doc01's forget then removes it, and doc01's re-add makes its row current again. The native test `test_native_readd_replaces_what_a_later_forget_of_a_co_owner_removed` drives forget doc02, forget doc01, re-add doc01 and re-add doc02.

**The fence.** A new consumer of a source whose forget is pending or failed is refused in `preflight` with `retiring_source`, before `begin` and again after it. The native test `test_native_readd_of_a_consumer_waits_for_the_unfinished_forget` re-adds doc02 while doc01's forget is failed.

## Interrupted re-adds

`readd --fault-stage nodes` fails before the captured facts are written. `reconcile --source <doc>` runs `write_semantics`, which skips a chunk whose fact and evidence are in place, so it writes what the failure skipped and completes at revision 2, with the incident resolved as `restored`.

## Scope

- A forget removes a dependent's decisions that cite the forgotten source directly. A decision that depends on another source's removed decision, through a saved record, is not followed: saved-record inputs are not admitted yet (next checkpoint).
- The tombstone keeps the last revision's mention and reusable UUIDs only. A source forgotten, re-added and forgotten again keeps the UUIDs of its last revision; earlier revisions' UUIDs are covered by the derivation rules, not by the tombstone. This single-revision gap is as in checkpoint F and is a tracked follow-up.
- A re-add starts from the caller's identity file as written. When the forgotten revision was later than that file, the re-add publishes the file's decisions, not the forgotten revision's.
- Erasure is logical: soft-deleted vector bytes and free database pages stay until the stores compact them (`residue` in the dry run).
- The forget plan keeps `stored_files`, the locations of the stored copies and of the caller's file, so that the completed forget's report can show the files are gone. A location names a file; it quotes no content.
- Two sources that both forgot a shared Entity get separate replacements on re-add, each derived from its own identity source and revision.
- What these fixtures do not establish: the captured decisions, the fixture's dependency and the re-added descriptions are supplied. They show the lifecycle mechanics through the real stores, not extraction or search quality.

## Code changed

- `models.py`: `Tombstone`, with `Tombstone.of(source, ...)` and `used_entity_ids`.
- `storage.py`: `complete(..., tombstone=...)`, `scrubbed_plan`, `scrubbed_event`, `FORGOTTEN_PLAN_FIELDS`, `PublicationRow.tombstone`, the `forgotten_format` refusal, forget admitted on `("withdrawn", None)` and `("failed", None)`, and the new `FORGET_STATE` message.
- `stages.py`: `Run.completion`, the keyword arguments a stage sets for `complete`; `saved_row` returns a forgotten row without the description check.
- `erasure.py` (new): `impact`, `Impact.token`, `removal_revision`, `removal_producer`, `unfinished`, `report` and `remove_dependents`.
- `forget.py`: the stage `forget_impact`, `DEPENDENT_FAULTS`, `preview` (the dry run), `confirmed`, `clear_withholdings`, `resumes`, `plan_for`; `refuse_dependents` is gone.
- `admission.py`: `ERASURE_IMPLEMENTATION`, `erasure_of`, `erased_inputs`, `erased_decisions`, `check_erasure_removals` with `check_erasure_complete` and `check_erasure_confined`, the gate in `check_scoped_variants`, and `admit_readd` against a tombstone.
- `retirement.py`: `SourceIds` and `source_ids`; `consumes`, `owned_by` and the functions that use them take either a description or a tombstone. `dependents` and `reject_sole_owned_readers` stay for text edits.
- `publish.py` and `validation.py`: `admit_readd` refuses unfinished dependents; `validate_uses` counts tombstones.
- `forget_fixture.py`: `forget_command`, `reconcile_forget`, `caller_files`, `describe_readd` and `readd` from the caller's files, `forget_checks` from a tombstone. `multisource.py` and `glossary_fixture.py` route `forget`, `readd` and `reconcile` through them.
- `environment.py` and `__main__.py`: the fixture kind in the root marker and routing by it; `--dry-run`, `--confirm`, the two dependent fault stages, and exit 1 when `dependents_failed` is set.

## History

**2026-10-22, checkpoint F.** `forget` removed a current source that nothing depended on, and refused a source with dependents (`dependent_source`, listing them) as a placeholder for step-4 item 3. The forgotten row kept its description: the re-add admission compared against it, and `status` printed it. The forget plan kept the full ownership snapshot, with edge texts and fact texts. A withdrawn source and a failed first publication could not be forgotten. A re-add published the forgotten description again and refused other text (`source_changed`). Its evidence: 315 unit tests, 59 native tests, the ledger check at 5889 nodes and 5770 sequences with 40 breaks caught, and `journey all` with 1159 PASS on `5f5dd37`. The guide of that checkpoint is in the git history of this file.

**2026-10-23, checkpoint I.** This guide. The user's decisions above replaced the refusal with erasure: the tombstone and scrubs, confirmation by token, the removal of dependents' decisions, forget of any source, and re-add from the caller's files.

## Evidence

The assistant (a subagent) ran these on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-erasure`. The code is at `94de39c`; the commit after it changes documents and skill files only.

- `uv run pytest -q -m 'not integration'`: 431 passed, 76 deselected, in about 120 s. New: `tests/test_identity_erasure.py` (15 tests: the impact and its token, the removal revision and its admission, the refusals of an incomplete or overreaching removal, what stays unfinished, the tombstone and the scrubbed plan) and the fixture-kind test in `tests/test_identity_environment.py`. `tests/test_identity_storage.py` now completes a forget with a tombstone, checks the scrubbed plan and event message, begins a forget on a withdrawn row and on a failed first publication, and refuses an old-format forgotten row.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 6287 nodes and 6156 sequences. `--mutants` caught all 45 breaks by the property each names (exit 0), among them the seven new ones: `complete-keeps-description`, `complete-keeps-plan` and `complete-keeps-messages` by P7, `forget-on-failed-replacement` and `forget-on-failed-withdrawal` by P5, and `forget-refuses-withdrawn` and `forget-refuses-failed-publication` as `INCONCLUSIVE`. The deep break `withdrawn-guard-admits-replace` fails at depth 7 after 8346 nodes with its recorded sequence.
- `uv run python support/occurrence_check.py`: `PASS` with 540045 worlds in 123 s, each rule 6 row checked 54 times. `--mutants`: `PASS`, all 35 breaks caught, in 60 s.
- `uv run pytest -q -m integration`: 76 passed in 1806 s. `tests/test_identity_forget_native.py` has 23 tests; the file alone passed in 512 s before the last refactor commit, which renames one function and names the stale-token refusal once.
- Verify journeys, each with 0 FAIL rows, on `94de39c`: F1 (45 PASS), F2 (28), F3 (21 for each of seven stages), F4 (15), F5 (10), F6 (13 for each of two stages), F7 (8), F8 (8), F9 (6), F10 (12) and F11 (9). Every journey whose root takes `forget`, `readd` or `reconcile` also passed, on `94de39c`: D1 to D6 (128 PASS), P1 to P4 (66), W1 and W3 (89), R1 and R2 (107), E1 to E4 (125), O1 to O8 (219), G1 to G4 (109), I1 to I3 (94) and K1 to K4 (116). `journey all` was not run; the landing playbook runs it before the merge.
- A by-hand run on a `glossary-fixture` root failed doc01's forget at `forget_document` and finished it with `reconcile --source doc01`, through the glossary driver: doc01 forgotten, the incident resolved as `forgotten` with no message.
