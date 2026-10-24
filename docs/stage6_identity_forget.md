# Stage 6 forget: erase a source and remove what depended on it

**Date:** 2026-10-23 (checkpoint I); 2026-10-24 (checkpoint J2, [the cascade](#the-cascade)). **Status:** implemented and verified by the assistant on the user's Mac with loopback embeddings. No user-reviewed fixture root exists yet. The [history note](#history) at the end records what checkpoint F built on 2026-10-22 and what the later checkpoints changed.

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
10. Saved-record inputs, chains of dependents and the non-identity example are deferred to the next checkpoint. (Checkpoint J1 added saved-record inputs. On 2026-10-23 the user decided that erasure cascades down a chain in dependency order, with one dry run, one token and one confirmation for every level; checkpoint J2 builds it, in [The cascade](#the-cascade).)

A review of the spec (2026-10-23, verdict proceed) fixed the order, the token, the admission rule and the tombstone shape; those resolutions are built as stated below.

## Commands

On a `multi-fixture` root, and on a `glossary-fixture` root for `doc01` or `glossary` (and `doc03` on a `--chain` root):

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
3. **Each dependent's removal revision, each under its own reservation**, through `replace_one`, the unchanged-text replacement that the refresh after a text edit also uses. A dependent whose own replacement failed takes the removal in its saved revision instead: the removal is applied to that saved description at the same revision, and the failed replacement finishes with it (an erasure retry, below).

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
| `decisions_sha256` | The digest of the forgotten revision's reviewed decisions, with every UUID the source owns named by its group key or by its roles in the decisions (see "Re-add") |
| `mention_ids` | The last revision's mention UUIDs by group key |
| `entity_ids` | The last revision's reusable Entity UUIDs |
| `earlier_mention_ids`, `earlier_entity_ids` | The mention and reusable Entity UUIDs of the source's earlier forgotten lives, apart from a reusable Entity the last revision names again; empty on a first forget |
| `removed_entity_ids` | The Entities the forget removed |
| `impact_token` | The confirmed token, or null when the forget affected no other source |
| `forgotten_at` | When the forget completed |

The plan keeps, by whitelist, `operation`, `revision`, `origin`, `method`, `original_data_id`, `stored_files`, `chunk_ids`, `identity_edges`, `entities` (refs, type and indexed fields) and `edges` (source, target, relation and refs). Every edge property goes: the `is_part_of` edge text that quoted the document's first 80 characters, the fact texts and the contributions. Every recovery event of the source loses `message`, its own and each attempt's, resolved events included; the ledger check's P5 allows that one change to a resolved event. IDs, stage, reason code, origin and attempts stay.

`RecordStore.rows()` refuses a forgotten row whose description is not a tombstone, or is a tombstone in an older format, with `forgotten_format`.

**Old roots.** A root made before the re-add follow-ups is not read (user decision 8). Its ledger table has no `last_tombstone` column, which `create_all` does not add, so `RecordStore.initialize()` compares each ledger table's columns with the store's and refuses with `ledger_format`: `This root's ledger lacks columns this version reads; regenerate this development root`. A tombstone without `decisions_sha256` and the `earlier_*` lists is refused as `forgotten_format`, with `A forgotten row in an older format is not read; regenerate this development root`. Every command prints the refusal as `{"error": "IntentError", ...}` and exits 1. Regenerate the root; never point a command at the reviewed roots under `outputs/stage6_*`.

**Carried forward.** When a re-add begins on a forgotten row, `begin` moves the tombstone from the description to the row's `last_tombstone` column, and the column keeps it, through failures and retries, until the source is forgotten again (`PublicationRow.last_tombstone`). That forget builds its tombstone under the writer reservation from the row's `last_tombstone` (`Tombstone.of(..., earlier=...)` in `forget.py`): the earlier tombstone's mention and reusable UUIDs, its own and its earlier ones, go into the new tombstone's `earlier_*` lists. `complete(state="forgotten")` writes the tombstone it is given as the description and clears `last_tombstone`, so a forgotten row holds one tombstone. Each tombstone thus holds every mention and reusable UUID of every forgotten life, without content (`Tombstone.all_mention_ids`, keyed by group where the last revision had one, and `Tombstone.all_reusable_ids`). UUIDs an edit retired in the middle of a life are not recorded; a per-source table of every UUID at every revision is a tracked follow-up.

Readers of a forgotten row read the tombstone: `stages.saved_row` skips the description check, `retrieve` leaves its mentions out of the alias set, `validate_uses` counts its mention and reusable UUIDs of every forgotten life, and also those of a re-added source's `last_tombstone`, so each forgotten life counts once, `admit_readd` checks against it, and both fixtures' `current_sources` fall back to the root's identity file. `retirement.py` takes a `SourceIds` (dataset, identity source, document) from a description or a tombstone.

## Impact, dry run and token

`erasure.impact` computes, from the saved descriptions and the forget plan's ownership snapshot and never from the live graph, each dependent and what its removal revision would do:

- Each decision it removes, with its `record_type` and the input that causes it: `input_ref`, `kind` and the `consumed` UUID (the document for a text, span or chunk; the Entity for a corpus object; the cited identity source for a saved record). A resolution becomes unresolved; a variant is dropped.
- `level`, `removed_records` and `cited_records` (since checkpoint J2): the dependent's place in the cascade, the records its removal removes and the removed records of other dependents it cites. See [The cascade](#the-cascade).
- `dropped_entities`: the reusable recipes that a removed decision named and no remaining decision names. Other owners keep the Entity, because the replacement only retires this source's declaration.
- `kept_entities`: such recipes that stay because a saved source still lists the Entity as a corpus input. A third source counts, and so does the dependent itself; dropping its last declaration could take the Entity out of the graph under a reader.
- `unlinked_mentions`: the mentions whose facts lose their identity link.
- `dropped_inputs`: the inputs nothing cites any more.
- `blocked`: the dependent's own attempt is pending, or failed and not a replacement (a failed withdrawal or publication). Such a dependent does not block the forget; its removal waits (`dependent_unfinished`) until its own method finishes it, and a rerun of `forget` or `reconcile` then removes it. A failed replacement is not blocked: its removal applies to its saved revision.

The token is `object_digest` over the source's dataset, identity ID and revision, the removed Entity IDs, and per dependent its identity ID, its revision, its state, its level, assignment keys, each decision's citing inputs, record type and outcome, its dropped Entity IDs, its removed and cited records and its blocked flag. The dependent's revision and state are in it (the state since fix round 2) so that the token changes whenever anything the report shows could change, even when the decisions it would remove stay the same. `forget` checks it before `begin` and again in `forget_impact`. Without a token, a forget with dependents is refused with `confirmation_required`, and a stale token with `impact_changed`; both carry the dry-run report in `details`. A retry of a failed forget without a token keeps the impact its first attempt confirmed.

The dry run returns the impact and:

- `levels`: each level with its dependents, in order.
- `counts`: dependents, levels, blocked dependents, decisions, unresolved, dropped, dropped Entities and facts that lose their identity link.
- `scrubbed`: what the tombstone drops: the occurrences, recipes and explanations of the description, the plan's edges with properties, and the source's recovery-event messages.
- `residue`: what erasure leaves physically. LanceDB marks deleted vector rows and keeps their bytes until a compaction and a cleanup of old table versions. The graph store and SQLite keep deleted rows in their files until a checkpoint and `VACUUM`. Erasure is logical.
- `caller_files`: the root files that hold the source's own inputs and the commands' results (`source.txt`, `identity.json`, `identity_doc01_revision*.json` and `multisource_result.json` for doc01, for example). They are listed, never deleted. The fixture side (`forget_fixture.py`) adds them to the dry run, to a refusal's report and to the forget's result; `forget`, `preview` and `erasure.report` know nothing of files.
- `token`.

## The removal revision

`erasure.cascade` lists each dependent's removal revision (`removal_revision`) with what it does, in level order; `impact` reports them and `finish_dependents` writes them. A current dependent takes its next revision with unchanged text:

- A resolution citing what the forget removed becomes `unresolved` in place: the same key and group, its input refs without the erased keys (the original document when nothing else remains), and a producer new in the revision.
- A variant citing it is dropped, with this dependent's contribution to that edge.
- Since checkpoint J2 each record type says how it is removed (`records.REGISTRY`, the hook `removed`), and `removal_revision` and `check_erasure_complete` both ask it.
- Groups lose the erased input keys, with the same fallback.
- A recipe goes as `dropped_entities` above says.
- Inputs nothing cites any more are dropped.

The producer is `forget_<forgotten identity ID>_r<revision>`: method `captured_fixture`, implementation `removed by forget`, and a configuration that names `forgotten_identity_data_id`, `forgotten_document_id`, `removed_entity_ids`, `impact_token` and, since checkpoint J2, `removed_records` and `cited_records` (see [The cascade](#the-cascade)).

**Erasure retry.** A dependent whose replacement or publication failed keeps a saved revision that only its own retry finishes, and that revision may cite the forgotten document, which can never be registered again. `finish_dependents` applies the removal to that saved description at the same revision and sends it as that retry. `erasure.removal_writer` picks the writer from the row's `failed_attempt` (publish, replace, text_change, withdraw or forget): a pending row and a failed withdrawal or forget wait, the rest write.

- A failed replacement retries through `replace_one`. `replace()` accepts a retry whose description differs from the saved one only as an erasure retry: its plan's `erased_from` gains the saved description (`storage.superseding_plan`), it builds the chain of the previous revision, the superseded descriptions and the new one once, admission checks the replacement's own step as the first attempt did, and `erasure_rules.check_retry_chain` checks each later step as an erasure removal of the one before. Both run again in the `replace_saved` stage. It adds what the superseded revision declared or wrote to the retirement plan.
- A failed text change retries with its saved text change through `text_fixture.rebuild`, which brings the writer and verifier that text change needs. No command leaves a dependent with a failed text change; `test_native_a_failed_text_change_takes_the_removal` makes one through the Publisher API, failed before any write and after its writes.
- A failed first publication, reconcile or re-add finishes through `finish_publication`, which registers the removal's description and calls `Publisher.reconcile` with it. `Publisher.superseded` keeps the saved `erased_from` and adds the saved description when the description differs (`superseding_plan`). A reconcile whose plan carries `erased_from` plans the retirement of the superseded descriptions (`replace.plan_retirement`) and runs the replacement's cleanup after its writes (`replace.retire` and `verify_retired`): the recipes, nodes, name vectors and identity-edge contributions the failed attempt wrote and the removal no longer declares go. `finish_publication` registers the removal's description before `begin`; a refusal leaves that snapshot written, and a rerun converges on it.

Each step of the chain must cite what its forget removed (`erasure_empty`), name exactly the Entities that forget removed (`erasure_unbound`) and keep the dataset, identity source and document (`erasure_unrelated`). `RecordStore.begin` enforces the same chain under the writer reservation, against the forgotten rows it reads there (see "The ledger").

## The cascade

Checkpoint J2, built 2026-10-24 from the user's decision of 2026-10-23: erasure cascades down a chain of citations in dependency order, one dry run and one token cover every level, and one confirmation covers all of it. The decisions of Checkpoint I still hold: dependents are removed, not withheld; a dependent never blocks the forget; a pending or failed dependent waits and resumes.

**Levels.** A dependent at level 1 reads the forgotten source directly: its document, a removed Entity or any of its saved records. A dependent that cites a record another dependent's removal removes is one level below that dependent, at its longest path: its level is one more than the deepest removal it cites. Each dependent gets one removal revision for everything it loses, at that level.

**A removed record** (`records.RemovedRecord`) names its source, record type and key, the fingerprint it had before the removal and `last_revision`, the last served revision of its source that held it: the removal's old revision, capped at the row's verified revision (`PublicationRow.verified_revision`, fix round 1). A citation pins a served record, so a removal in place of a failed attempt's saved revision lists the revision before when that revision was never served, and the same revision when a reconcile of a served row failed there. Before fix round 1 it always took the revision before, so the citers of a served row whose reconcile had failed dropped out of the cascade. A citation reads a removed record when it pins that fingerprint at that revision or before. So:

- a citation pinned at an older fingerprint is not part of the cascade (review resolution 12); live withholding holds it, as it did before;
- a citation made after the removal reads the record as it is now and keeps nothing unfinished, even if the record later returns to its old fingerprint.

**The cascade from the rows.** `erasure.cascade` finds every removal the forget still has to write, from the saved rows, to one fixpoint that starts from the records written removals removed (`erasure_rules.bound_removals`). A failed removal revision joins when a bound removal removes every record it cites, and a saved source that reads the forgotten source, or a record a bound removal removes as it was, joins with one removal revision for all it reads. Levels come from one function, `erasure_rules.levels`, which `bound_removals` shares. The removal revisions are built once, after the fixpoint. A failed removal revision whose cited records no bound removal lists any more, because the source that removed them was withdrawn or its withdrawal failed, leaves the cascade, as a citer of a withdrawn intermediate does (fix round 1; before it, every reader of the cascade raised `KeyError`). The steps come in level order, then by source. `impact`, `remaining`, `unfinished` and `finish_dependents` all read it, so a resume after a crash continues where the rows say it stopped. Nothing new is stored in the ledger.

**The token and the dry run.** The token covers every level: each dependent's level and the records it removes and cites are in it. The dry run lists `levels`, each with its dependents, and `counts.levels`. One `--confirm <token>` covers the whole cascade.

**Writing it.** `finish_dependents` writes the removal revisions in level order, each under its own writer reservation, in the order `erasure.ready` gives. A blocked dependent waits (`dependent_unfinished`), and so does every removal below it that cites a record it removes (`waits_for` in `dependents_waiting`): those records are not removed yet, and the removals below bind only to written ones. The first failure stops the pass and is reported beside the completed forget. `forget` or `reconcile` on the forgotten source resumes, and `readd` waits while any level is unfinished. The fault stage `forget_cascade_revision` fails each removal revision below level 1, once level 1 is written.

**The inductive gate.** The removal producer's configuration lists `removed_records`, exactly the records its revision removes as the old revision held them (`check_erasure_records`), and `cited_records`, the removed records of other dependents it cites (empty at level 1). Admission (`erasure_of`) accepts the cited records only when each one is bound and they are exactly the bound ones the old revision reads. A record is bound when a written removal producer for the same forget lists it, and that producer is bound in turn: it names the forgotten document and exactly the Entities that forget removed, and every record it cites is bound. The binding reaches back to the tombstone, so a removal written out of order binds nothing below it. A producer counts as written unless the row's own pending or failed attempt introduced it; producers are immutable, so a later revision still carries it. The revision that introduced a producer is told by its key, so admission refuses a removal producer under any key but `forget_<forgotten identity ID>_r<revision>` (`erasure_configuration`, fix round 1). Admission checks `removed_records` against the row's verified revision; a step in place may also list the revision before, since a retry checks the chain again after it was served at that revision.

**Targets only shrink after confirmation** (review resolution 13). The fence (`erasure.refuse_retiring_inputs`) simulates the cascade from the rows for every forget not finished (`under_way`) and refuses, with `retiring_source`, a new citation of any record any level will remove, as that record is now. A citation of a removed record as it is after its removal is admitted. `support/cascade_check.py` checks that no citation the fence, the record checks and the cycle check admit, while the forget is pending or after any removal is written, adds a removal outside the confirmed token.

**Removal producers are immutable** (review resolution 14). `check_removal_producers_kept`, which `admit` runs on every revision, refuses a later revision that drops or changes a removal producer (`removal_producer_changed`): the removals below it read what it removed from its configuration.

On a `glossary-fixture --chain` root:

```bash
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source glossary --expected-revision 1 --dry-run
# levels: doc01 (718efce2-...) at 1, doc03 (bbbc442e-...) at 2
uv run python -m cognee_lab.identity forget --root outputs/<new root> --source glossary --expected-revision 1 --confirm <token>
```

The dry run lists doc01 at level 1 (r01 unresolved and v01 dropped, citing `glossary_hc`) and doc03 at level 2 (c01 unresolved and c02 dropped, citing `doc01_r01` and `doc01_v01`). doc03's `cited_records` are doc01's `removed_records`: r01 with fingerprint `1d2e8913...` and v01 with `6a899169...`, each with `last_revision` 1. With the token the glossary is forgotten, doc01 goes to revision 2 at level 1, then doc03 to revision 2 at level 2, with c01 alone, unresolved, citing only `doc03`. HC goes from both, since no remaining decision of either names it. Nothing is withheld afterwards. Journeys F16 to F19 in `.claude/skills/verify/features/source-lifecycle.md` cover the two-level forget, a token refused when a new level appears, a crash at the level-2 removal with its resume and the re-add that waits for it, and a blocked level-2 dependent.

## The ledger

A row has one of five states: `pending`, `current`, `failed`, `withdrawn` and `forgotten`. Forget begins on a `current` row, a `withdrawn` row, a `failed` row whose plan is a publication (a first publication, a reconcile or a re-add), or a `failed` row that holds a forget plan, which only forget resumes. A failed replacement or withdrawal is refused, since only its own method resumes it. A failed replacement's retry, and a reconcile of a failed publication, may begin with another description at the saved revision only as an erasure retry, whose plan adds the saved description to `erased_from` (see "The removal revision"). `admissible()` holds this as a preserved plan field with one alternative (`RequiredPlan.supersedes`), and it checks every step of the chain against the forgotten rows that `begin` reads under the reservation (`check_retry_chain`). A plan that names superseded revisions on any other begin is refused (`recovery_plan`), and reconcile now requires a publication plan. Forget completes as `forgotten` with the tombstone. A forgotten row accepts only a new publication at the next revision; every other method is refused as `forgotten_source`. Every begin at the forgotten revision is also refused by the description check, since no description equals a tombstone.

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

- `sources.doc01` has `state: forgotten`, `saved_revision` 1, `verified_revision` 1 and a `forget` report. The report is `remains()` from `forget.py`, which the verification requires to be all false, empty or zero (`original_data_present`, `identity_data_present`, `stored_files_present`, `document_node_present`, `chunks_present`, `chunk_vectors_present`, `evidence_rows`, `identity_contribution_present`, `owned_nodes`, `owned_edges`; `identity_contribution_present` reads every identity edge and owned edge the plan records, fields the scrubbed plan keeps, so the check after the forget covers the same edges as the forget's own check), plus the fixture's fields `mention_nodes_present`, `mention_vectors_present`, `removed_entities_present`, `original_fact_present`, `private_singleton_present` and `private_singleton_indexed`, also all absent, and `removed_entities`.
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

A failed replacement is different: only `replace` resumes it, and its saved revision may cite the forgotten document, which can never be registered again. On a `glossary-fixture` root, `edit-glossary --source glossary --case insert --expected-revision 1 --fault-stage refresh_interrupted` leaves doc01's refresh failed at revision 2, citing the glossary at the new range. The glossary's dry run lists doc01 as `failed` at revision 2 and not blocked. With the token the glossary is forgotten and doc01's failed replacement finishes with the removal applied to its saved revision: doc01 is current at revision 2 with r01 alone, unresolved under the removal producer, and cites nothing of the glossary. Nothing is unfinished, so `reconcile --source glossary` is refused as a forgotten source, and `readd --source glossary --expected-revision 2` brings the glossary back (`test_native_a_failed_refresh_takes_the_removal_in_its_saved_revision`).

A dependent whose own first publication failed is not blocked either. On a `--dependent` root, `multi-fixture --dependent --source doc02 --fault-stage nodes` leaves doc02 failed at revision 1, citing doc01's text. doc01's dry run lists doc02 as `failed` at revision 1 and not blocked. While the removal waits, doc02's own `reconcile` cannot finish, since its saved revision cites a document that is no longer registered, and nothing of doc02 is served. The forget, or `reconcile --source doc01` after an interruption, applies the removal to doc02's saved revision and finishes the publication with it: doc02 is current at revision 1 with r01 unresolved under the removal producer, its local fact stays and no identity query reaches it (journey F13, `test_native_a_failed_first_publication_takes_the_removal_in_its_saved_revision`).

A failed first publication may have written its nodes and identity edges before it failed. On a `glossary-fixture` root, `glossary-fixture --source doc01 --fault-stage identity_edges` fails doc01 after HC's node, its name vector and the HC to Helios controller edge with v01's contribution are written. The glossary's dry run lists doc01 as `failed` at revision 1, with HC as its one dropped Entity. With the token the glossary is forgotten and doc01's publication finishes with the removal: doc01 is current at revision 1 with r01 alone, HC's node and name vector are gone, the edge holds no contribution of doc01, and the HC query no longer seeds HC (journey F14, `test_native_an_erasure_retry_of_a_failed_publication_retires_what_it_wrote`).

A pending dependent waits until its attempt ends; it then is current, or a failed row, and the cases above apply.

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

`readd` reads the caller's files from the root: `source.txt` and `identity.json` for doc01 (`source02.txt` and `identity02.json` for doc02, `glossary.txt` and `glossary_identity.json` for the glossary). The text must have the digest the identity file states (`source_changed` otherwise). It chunks the text in memory, writes the identity file's description at the forgotten revision plus one with fresh mention UUIDs and a replacement for every reusable Entity the forget removed, in each role it plays (resolution target or candidate, variant endpoint), and admits it before any write: `admit_readd` against the tombstone, then `admit_inputs`. Then it adds the document again under the same data ID, checks the native chunks against the admitted ones, adds the description as `identity_<doc>_revision<N>.json` under the same identity data ID, and publishes it.

The re-add is admitted like a first publication apart from two rules: the next revision, and no mention or Entity UUID that the tombstone records or that the forget removed. Data IDs, the identity ID and chunk IDs return. A new group's UUID is `uuid5(identity_data_id, "mention:r{N+1}:{key}")`. A reusable Entity the forget removed returns under a new UUID: from the next revision and a key that names it, `uuid5(identity_data_id, "entity:r{N+1}:{key}")`, or, for an Entity nothing names, `uuid5(identity_data_id, "entity:r{N+1}:replaces:{removed UUID}")`. The re-add may bring other text or other decisions. A forgotten mention UUID of any earlier life is forbidden like one of the last revision: as a group's UUID (`fresh_uuid_reused`) and in any other role (`forgotten_uuid_reused`). A reusable Entity of any forgotten life that no forget removed and the graph still holds returns under its own UUID, as one of the last revision does: a third life whose files name an Entity of the first life, which the second life's files dropped, reuses it (`readd_ids` subtracts `Tombstone.all_reusable_ids`; fix round 1).

**What a re-add reports.** The result of `readd` holds `differs_from_forgotten`: `text` is true when the caller's text digest differs from the tombstone's `text_sha256`, and `decisions` is true when the re-add's decisions digest differs from `decisions_sha256`. It is a report and never refuses. The decisions digest (`decisions.decisions_digest`) leaves out what every re-add changes: the revision, and the UUIDs of the source's own groups and recipes, since the re-add derives new ones. It names a mention by its group key and a reusable Entity of the source by its roles (`decisions.roles`): each decision that names it, by key, with the part it plays there, an accepted resolution's `target`, an open resolution's `candidate`, or a variant's `source` or `target`. An Entity nothing names takes the empty list. Each recipe is digested under its Entity's roles, so a variant whose endpoints are swapped, or an open resolution whose candidate is exchanged for another Entity of the source, is a decision change (fix round 2; before it, both endpoints of a variant took the same name and candidates were not counted). Two Entities with the same roles and the same recipe are told apart by nothing, which is right: exchanging them changes no decision. Over those names it digests each group's occurrences, each resolution by key (group, status, target, candidates), each variant by key (endpoints and applicability) and each recipe (name and description). An occurrence counts by its surface text and its place in the order of all the source's occurrences, not by its offsets: a text shift, as a prefix edit makes, is no decision change, while an occurrence dropped from a group, moved to another group, or exchanged with another group's occurrence of the same text is one. The digest leaves out producers, inputs and explanations, which record how and where a decision was made. A span-scoped variant's ranges count as offsets, so a shifted range is a decision change: the description holds no surface text for a range, and a text edit does not remap span-scoped variants either (`span_variant_in_text_edit`). The comparison is with the forgotten revision, which can be later than the caller's file: a source forgotten after a removal revision reports other decisions when the caller's file still holds the removed ones.

For doc01 after the healthy forget: doc01 is current at saved, registered and verified revision 2 with its marker, fact, ownership, evidence, unresolved mention and private singleton. g01 is `1384af69-23e8-5a8e-a4f4-9a8983ee2dd3` and g02 `d9ee5111-cb06-54fd-98b8-e9913490d87d`; the private singleton, which nothing names, returns as `9b7f8477-b420-57e6-a343-ff73d921aa82`. HC, A and the shared singleton survived with doc02's refs, so the re-add references them under their UUIDs. Both facts return, the shared variant has two contributions and two owners, and HC two owners. A second `readd` is refused with `Re-add needs a forgotten source`.

With changed files: append ` HC was serviced.` to `source.txt`, and the re-add is refused with `The caller's text file and identity file disagree`; set `inputs.doc01.text_sha256` in `identity.json` to the new text's digest, and the re-add publishes doc01 at revision 2 with the new text, its fact, and both facts in the result. It reports `differs_from_forgotten` `{"text": true, "decisions": false}`; the plain re-add reports both false.

**Forgotten again.** After that re-add, `forget --source doc01 --expected-revision 2` leaves a tombstone at revision 2 whose `mention_ids.g01` is the revision 2 mention UUID and whose `earlier_mention_ids` is the revision 1 one. A corpus input in `identity.json` that names the revision 1 mention UUID makes the next re-add refuse with `forgotten_uuid_reused` before any write. Without it, and with r01 unresolved in the file, `readd --source doc01 --expected-revision 2` publishes doc01 at revision 3 under a third mention UUID and reports `{"text": false, "decisions": true}`: the text is the revision 2 text, and r01 changed (journey F15).

A re-add with the forgotten revision's mention UUIDs is refused as `fresh_uuid_reused`, one with mention UUIDs derived from another revision as `fresh_uuid_not_derived`, one that names a removed Entity UUID, or a forgotten mention UUID of any forgotten life in any role (as a recipe, a target, a variant endpoint or a corpus input, even when the forget's plan never held its node because the publication failed early), as `forgotten_uuid_reused`, one whose replacement UUID is not derived, or whose replacement of a named Entity uses the `replaces:` form, as `entity_uuid_not_derived`, one whose new UUID is already a graph node as `fresh_uuid_in_graph` or `entity_uuid_in_graph`, and one at any revision but N+1 as `revision_sequence` (unit tests in `tests/test_identity_forget.py`).

**What a re-add replaces.** A re-add replaces each Entity that `readd_removed` returns: the Entities whose every recorded owner in the plan snapshot is this source or a retiring one, computed from the rows at the re-add, every Entity the plan recorded that the graph no longer holds, and every reusable Entity of an earlier forgotten life (`earlier_entity_ids`) that the graph no longer holds. The last case matters when the caller's file still names an Entity by the UUID an earlier forget removed: a second re-add from the original files replaces it again, from the next revision, instead of refusing it as underived (journey F15, `test_a_second_readd_replaces_what_the_first_forget_removed`). The rows alone are not enough: if doc02 is forgotten while doc01 still owns HC, HC survives; doc01's forget then removes it, and doc01's re-add makes its row current again. The native test `test_native_readd_replaces_what_a_later_forget_of_a_co_owner_removed` drives forget doc02, forget doc01, re-add doc01 and re-add doc02.

**The fence.** A new consumer of a source whose forget is pending or failed is refused in `preflight` with `retiring_source`, before `begin` and again after it. The native test `test_native_readd_of_a_consumer_waits_for_the_unfinished_forget` re-adds doc02 while doc01's forget is failed.

## Interrupted re-adds

`readd --fault-stage nodes` fails before the captured facts are written. `reconcile --source <doc>` runs `write_semantics`, which skips a chunk whose fact and evidence are in place, so it writes what the failure skipped and completes at revision 2, with the incident resolved as `restored`.

## Scope

- A forget removes a dependent's decisions that cite the forgotten source and, since checkpoint J2, down every chain of saved-record citations, each decision that cites a removed record as it was ([The cascade](#the-cascade)).
- Removing a resolution that was already unresolved keeps its fingerprint. A citation of it made before the removal is still removed, since the removal lists the record; one made after it is not (checkpoint J2, a reversible choice).
- The cascade reads saved sources that are not retired. When an intermediate dependent is withdrawn before its removal is written, a decision that cites its records is no longer part of the cascade; live withholding holds it with `input_removed`, as for any withdrawn upstream (checkpoint J1). A failed removal revision whose upstream is withdrawn, or whose upstream's withdrawal failed, leaves the cascade the same way (fix round 1). Its own retry then stays refused (`erasure_unbound`), since admission binds its cited records to written removals: a failed publication can still be withdrawn or forgotten, but a failed replacement or text change has no way out. That is open; a way out needs a change to the binding rule, which is the user's call.
- A withdrawal or forget resumes with the plan its first attempt saved, which records the refs and contributions other owners held then. Since fix round 1 its survivor check owes another identity source only what that source still writes now (`retirement.current_claims`): its declared Entity keys, its identity edges and its contributions. Before it, when another dependent's removal revision dropped an Entity, edge or contribution they shared, the resume failed (`Independent Entity ownership was lost`). Journey F19 now finishes doc03's withdrawal after doc01's removal and re-adds the glossary.
- The tombstone keeps the last revision's mention and reusable UUIDs and, since the re-add follow-ups, those of each earlier forgotten life. UUIDs that an edit retired in the middle of a life are not kept; the derivation rules cover them. A per-source table of every UUID at every revision is a tracked follow-up.
- The decisions digest names a reusable Entity by its roles in the decisions, which name it by key. A re-add that renames decision keys therefore reports other decisions, even when the outcomes match.
- A re-add starts from the caller's identity file as written. When the forgotten revision was later than that file, the re-add publishes the file's decisions, not the forgotten revision's.
- A dependent whose own first publication or reconcile failed while its description cites the forgotten document cannot finish its own reconcile, which needs that document registered. The forget finishes that publication with the removal applied (fix round 2; open as of fix round 1).
- A dependent's failed text change finishes with the removal through `text_fixture.rebuild`, the fixtures' text writer, as a failed replacement finishes through `replace_one`. Its own dependents' moved ranges then wait for `refresh-dependents`.
- An erasure step's readers are read again under the dependent's reservation. A source that began reading a recipe the removal drops between admission and that recheck makes the removal attempt fail before any write, and the failed removal revision stays failed while the source reads the recipe.
- Erasure is logical: soft-deleted vector bytes and free database pages stay until the stores compact them (`residue` in the dry run).
- The forget plan keeps `stored_files`, the locations of the stored copies and of the caller's file, so that the completed forget's report can show the files are gone. A location names a file; it quotes no content.
- Two sources that both forgot a shared Entity get separate replacements on re-add, each derived from its own identity source and revision.
- What these fixtures do not establish: the captured decisions, the fixture's dependency and the re-added descriptions are supplied. They show the lifecycle mechanics through the real stores, not extraction or search quality.

## Code changed

- `models.py`: `Tombstone`, with `Tombstone.of(source, ...)` and `used_entity_ids`.
- `storage.py`: `complete(..., tombstone=...)`, `scrubbed_plan`, `scrubbed_event`, `FORGOTTEN_PLAN_FIELDS`, `PublicationRow.tombstone`, the `forgotten_format` refusal, forget admitted on `("withdrawn", None)` and `("failed", None)`, and the new `FORGET_STATE` message.
- `stages.py`: `Run.completion`, the keyword arguments a stage sets for `complete`; `saved_row` returns a forgotten row without the description check.
- `erasure.py` (new): `impact`, `Impact.token`, `revisions` with `removal_revision`, `removal_producer`, `unfinished`, `report` and `finish_dependents`.
- `forget.py`: the stage `forget_impact`, `DEPENDENT_FAULTS`, `preview` (the dry run), `confirmed`, `clear_withholdings`, `resumes`, `plan_for`; `refuse_dependents` is gone.
- `erasure_rules.py` (new in fix round 1, moved out of `admission.py`): `ERASURE_IMPLEMENTATION`, `Erasure`, `Erasures` with `erasures_of`, `citations` (the one dependency predicate; in fix round 2 it moved with `Citation` to `dependency.py`, and `Erasure` became `dependency.Target`), `erasure_of`, `check_erasure_removals` with `check_erasure_complete`, `check_erasure_confined` and `check_dropped_unread`, `check_erasure_retry`, and `admit_readd` against a tombstone. `admission.py` keeps the gate in `check_scoped_variants` and calls the removal rules in its rule order.
- `retirement.py`: `SourceIds` and `source_ids`; `consumes` (the refusal-details view of `citations`), `owned_by` and the functions that use them take either a description or a tombstone. `dependents` and `reject_sole_owned_readers` stay for text edits. `contribution_triples` reads only fields the scrubbed plan keeps.
- `publish.py` and `validation.py`: `admit_readd` refuses unfinished dependents; `validate_uses` counts tombstones.
- `forget_fixture.py`: `CALLER_FILES`, `forget_dry_run`, `forget_command`, `reconcile_forget`, `caller_files`, `describe_readd` and `readd` from the caller's files, `forget_checks` from SourceIds and mention UUIDs. `multisource.py` and `glossary_fixture.py` route `forget`, `readd` and `reconcile` through them.
- `storage.py` (fix round 1): `PublicationRow` parses a row once into `description` or `tombstone`; `begin` admits an erasure retry (`supersedes`).
- `replace.py` (fix round 1): the erasure retry (`erased_from`, `plan_retirement`) and the ledger-bound erasure admission with its reader recheck in `replace_saved`.
- Fix round 2: `erasure_rules.check_retry_chain` and `check_erasure_cites`; `storage.admissible` takes the description and every row, folds `erased_from` into `RequiredPlan.preserved` and checks the chain; `REQUIRED_PLANS["reconcile"]`; `erasure.write_removal` and `finish_dependents(publisher, tombstone, rows, fault, rebuild_text)`; `revisions.finish_publication`; `Publisher.superseded`; `text_fixture.rebuild` split from `maintain_one`; `forget.split_fault`, with `DEPENDENT_FAULTS` a tuple of stage names; `forget.resume_dependents` is gone; `dependency.py` holds the one dependency predicate.
- Fix round 3: `Publisher._publish` retires what a superseded description wrote, through `replace.retire` and `verify_retired`, split out of `replace()`; `storage.superseding_plan`, used by `replace`, `Publisher.superseded` and `admissible`; `storage.erasure_chain`, so that `begin` reads every row only for an erasure retry; `PublicationRow.failed_attempt`; `erasure.removal_writer` with `write_replacement`, `write_text_change` and `write_publication` replaces `write_removal`; `finish_dependents(publisher, tombstone, rows, fault)` and `forget` lose `rebuild_text`; `check_retry_chain(chain, erasures)` loses `first`.
- `environment.py` and `__main__.py`: the fixture kind in the root marker and routing by it; `--dry-run`, `--confirm`, the two dependent fault stages, and exit 1 when `dependents_failed` is set.
- Checkpoint J2 (2026-10-24): `records.RemovedRecord`, `RecordKind.removed` and `without_erased`; `dependency.Target.records` and `read_records`; `erasure.cascade` and `Step` replace `revisions` and `dependents_of`, `DependentImpact` gains `level`, `removed_records` and `cited_records`, `Removal.kind` became `record_type`, `removal_producer` lists `removed_records` and `cited_records`, `finish_dependents` writes in level order with `waits_for`, and `impact_checked` (the J1 interim refusal `chain_erasure_pending`) is gone; `erasure_rules.producer_key`, `RemovalClaim`, `removal_claim`, `written_claims`, `bound_removals`, `Erasures.records`, `Erasure`, `check_erasure_records` and `check_removal_producers_kept`, which `admission.admit` runs; `forget.DEPENDENT_FAULTS` gains `forget_cascade_revision`; `withdraw` on a glossary root routes to the glossary driver.

- Re-add follow-ups (2026-10-23): `models.Tombstone` gains `decisions_sha256`, `earlier_mention_ids`, `earlier_entity_ids`, `carrying` and `forgotten_mention_ids`; `validation.decisions_digest` and `uses_of`; `erasure_rules.differs_from_forgotten`, and `check_removed_entity_ids` reads every forgotten life; `storage.Publication.last_tombstone` and `PublicationRow.last_tombstone`, written by `complete`; `Publisher.admit_inputs` counts a re-added source's `last_tombstone`; `retirement.readd_removed` adds the reusable Entities of earlier forgotten lives that the graph no longer holds; `forget_fixture.readd` returns the report, which both drivers print.
- Re-add follow-ups fix round 2 (2026-10-23): `decisions.roles` names a reusable Entity in `decisions_digest` by its role in each decision; `forget_fixture.describe_readd` renames a removed Entity among an open resolution's candidates too, where before the re-add kept the removed UUID and `admit_readd` refused it as `forgotten_uuid_reused`. `tests/test_identity_decisions.py` applies each single decision change to three descriptions and asserts the digest changes, and each change it must ignore and asserts it does not.
- Re-add follow-ups fix round 1 (2026-10-23): `decisions.py` (new) holds `decisions_digest`, which now counts each group's occurrences, and `naming_keys`, moved out of `validation.py`; `Tombstone.of(..., earlier=...)` replaces `Tombstone.carrying`, and `all_mention_ids` and `all_reusable_ids` replace `forgotten_mention_ids`; `forget.py` builds the carried tombstone from the row's `last_tombstone`; `storage.begin` moves a forgotten row's tombstone to `last_tombstone` on a re-add, and `complete` writes the given tombstone and clears it; `storage.saved_tombstone`, `saved_columns` and the `ledger_format` refusal in `initialize`; `erasure_rules.readd_ids` reads every forgotten life.

## History

**2026-10-22, checkpoint F.** `forget` removed a current source that nothing depended on, and refused a source with dependents (`dependent_source`, listing them) as a placeholder for step-4 item 3. The forgotten row kept its description: the re-add admission compared against it, and `status` printed it. The forget plan kept the full ownership snapshot, with edge texts and fact texts. A withdrawn source and a failed first publication could not be forgotten. A re-add published the forgotten description again and refused other text (`source_changed`). Its evidence: 315 unit tests, 59 native tests, the ledger check at 5889 nodes and 5770 sequences with 40 breaks caught, and `journey all` with 1159 PASS on `5f5dd37`. The guide of that checkpoint is in the git history of this file.

**2026-10-23, checkpoint I.** This guide. The user's decisions above replaced the refusal with erasure: the tombstone and scrubs, confirmation by token, the removal of dependents' decisions, forget of any source, and re-add from the caller's files.

**2026-10-23, checkpoint I fix round 1.** A review found that a dependent whose own replacement had failed could never converge: its retry needed the forgotten document registered, and forget and reconcile only waited for it. The removal now applies to the failed replacement's saved revision (the erasure retry). A removal producer is bound to a forgotten row in the ledger, a removal never drops a recipe another saved source reads, a re-add never names a forgotten mention UUID in any role, and the token covers each dependent's revision. The erasure and re-add rules moved to `erasure_rules.py`, a row is parsed once, and forget's dependents rest on one predicate (`citations`) and one generator (`revisions`).

**2026-10-23, checkpoint I fix round 2.** A second review found that a dependent's failed first publication still only waited, that a dependent's failed text change could never retry (its retry needs the text change's writer, which `replace_one` never passed), that the store accepted any description at a failed replacement's saved revision, and that an erasure step could remove nothing or only part of what its forget removed. A failed publication now finishes with the removal applied to its saved revision, a failed text change does when the caller supplies its writer, the store checks every step of the erasure-retry chain against the forgotten rows, and each step must remove exactly what its forget took.

**2026-10-23, checkpoint I fix round 3.** A final review found that an erasure retry of a failed first publication left what the failed attempt wrote for the superseded description: on a glossary root whose doc01 failed at `identity_edges`, forgetting the glossary left HC's node, its name vector and the HC edge with v01's contribution, and the HC query still seeded HC. Once the description no longer named them, nothing could remove them. A reconcile that supersedes a description now retires what it wrote, as a replacement's erasure retry already did. The text writer of a failed text change is imported like the other writers, so a forget never leaves such a dependent waiting.

**2026-10-23, re-add follow-ups F1 and F2.** The user decided both on 2026-10-23. A re-add reports, without refusing, whether its text and its decisions differ from the forgotten revision, by digests the tombstone keeps; no content returns to the tombstone. A source forgotten again keeps the UUIDs of its earlier forgotten lives in its tombstone.

**2026-10-23, re-add follow-ups fix round 1.** A review found that the decisions digest missed a regrouping with unchanged text, that the ledger check could not see `last_tombstone`, that a root from before the follow-ups failed with a raw sqlite error, and that a third life refused an earlier life's Entity still in the graph. The digest now counts occurrences, the ledger check has P8, old roots are refused by name, and every forgotten life's reusable Entities may return. A forgotten row now holds its tombstone once: `last_tombstone` lives only on a row re-added since, and `forget.py`, not `complete`, builds the carried tombstone.

**2026-10-24, checkpoint J2.** The user decided on 2026-10-23 that erasure cascades down a chain of citations. Until then a forget that would remove a record another source cites was refused (`chain_erasure_pending`, checkpoint J1). The refusal is gone: the cascade removes each level in order under one token ([The cascade](#the-cascade)).

## Evidence

**Checkpoint J2 fix round 1.** A review of checkpoint J2 raised two probed bugs (M1, M2), a low one, the Checkpoint I survivor defect now reachable, and eight quality items. The assistant (a subagent) fixed them on the user's Mac on 2026-10-24 with loopback embeddings, on branch `stage6-cascade`. Each bug's test failed before its fix.

- M1 (`d154aa2`): a removed record's last revision comes from the ledger's verified revision (`test_a_failed_reconcile_of_a_served_row_keeps_its_citers_in_the_cascade`). The first try checked every step of a retry chain against the current verified revision; the ledger check failed P6 (a completed erasure retry, served and then rejected, could not recover), so a step in place may also list the revision before.
- M2 (`0878c5b`): a failed removal whose upstream retired leaves the cascade (`test_a_failed_removal_whose_upstream_retired_leaves_the_cascade`, withdrawn and failed-withdrawal upstream). The one fixpoint and the shared level function close quality items 8 and 9.
- Low (`f322d99`): the canonical producer key, with an occurrence-check row and the mutant `erasure_under_any_key`.
- Survivor check (`1158e8b`): `retirement.current_claims`; journey F19 extended.
- Quality (`aa41b21`, `76e4483`): the record registry answers inputs, outcome, stripped parts and unlinked mentions; `erasure.ready`; mutants patch every binding; registry lookups in the cascade worlds; the producer-configuration assertion replaced by what the written removal binds. The slowest cascade-mutant unit test takes 5 s.
- Lever (`98565a1`): the cascade worlds gain the reconciled state and the retired-upstream check, with the mutants `removed_before_served` and `unbound_retries`.
- `uv run pytest -q -m 'not integration'`: 511 passed, 86 deselected (exit 0).
- `uv run python support/occurrence_check.py`: `PASS` on 540,045 worlds; `--mutants`: `PASS`, `erasure_under_any_key` among the breaks caught.
- `uv run python support/chain_check.py`: `PASS`, 0 disagreements, with 34,752 cascade worlds (depth 0: 12,800, 1: 10,816, 2: 8,064, 3: 3,072) and the withholding half unchanged, in 389 s (312 s before the round). `--mutants`: all ten breaks caught in 22 s.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with `PINNED` unchanged at 8504 nodes and 8349 sequences. `--mutants`: all 52 breaks caught (exit 0).
- `uv run pytest -q -m integration tests/test_identity_forget_native.py tests/test_identity_chains_native.py tests/test_identity_erasure_retry_native.py tests/test_identity_dependencies_native.py`: 41 passed in 1006 s, run while the journeys ran.
- Journeys F1 to F19, D1 to D11 and G1 to G4, one at a time: 711 PASS rows, 0 FAIL (F19 now 11, up from 9). `journey all` was not run.

**Checkpoint J2.** The assistant (a subagent) ran these on the user's Mac on 2026-10-24 with loopback embeddings, on branch `stage6-cascade`: the cascade at `3ebd8bb`, the chain check at `104fefa` and the test and journey updates at `6ba8caf` and `7ff6c9f`. The native tests, the checks and the journeys partly ran concurrently, so their times are inflated.

- `uv run pytest -q -m 'not integration'`: 497 passed, 87 deselected on `3ebd8bb`; 503 passed, 87 deselected with the chain check's tests (exit 0 each).
- `uv run python support/occurrence_check.py`: `PASS` on 540,045 worlds, with nine new rule-6 rows (a removal citing an upstream removed record; one that does not name it, names it at another fingerprint, names it pinned after its removal, or keeps the citer; one that lists no removed record; an earlier removal producer kept, widened and dropped). `--mutants`: `PASS`, with the new breaks `trust_cited_records`, `erasure_records_unchecked` and `removal_producers_mutable` caught.
- `uv run python support/chain_check.py`: `PASS`, 0 disagreements on 543 acyclic graphs, 16,384 cycle cases, 2,224,128 withholding worlds and 14,661 cascade worlds (cascade depth 0: 5,400, 1: 4,563, 2: 3,402, 3: 1,296), in 312 s. `--mutants`: all eight breaks caught, the five cascade ones among them, in 12 s.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with `PINNED` unchanged at 8504 nodes and 8349 sequences. `--mutants`: all 52 breaks caught (exit 0).
- `uv run pytest -q -m integration tests/test_identity_forget_native.py tests/test_identity_chains_native.py tests/test_identity_erasure_retry_native.py tests/test_identity_dependencies_native.py`: 40 passed and 2 failed in 953 s on `3ebd8bb`. Both failures were test expectations: a revised dependent now reports its `level`, and the interrupted-removal test was parametrized over every dependent fault, the new one included, which never fires on its one-level fixture. After `6ba8caf` the three affected cases passed (87 s). New: `test_native_chain_cascade_resumes_a_failed_level_two_removal`.
- Verify journeys, each with 0 FAIL rows: F1 to F15 (363 PASS, the same total as before), F16 (13, new), F17 (12, new), F18 (12, new), F19 (9, new), D1 to D6 (128), D7 to D11 (63; D11 now checks the glossary's two-level dry run) and G1 to G4 (109); 709 PASS in all. F2 failed one check on its first run, an exact match on `dependents_revised` that lacked the new `level`; `7ff6c9f` updated the check and F2 then gave 28 PASS. `journey all` was not run.

**Re-add follow-ups fix round 1.** The assistant (a subagent) ran these on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-readd-followups` at `284340f`. The checks, the native tests and the journeys ran concurrently, so their times are inflated; the journeys ran with only this guide, the handoff and the ledger skill changed in the working tree.

- Before each fix its new test failed: `test_a_readd_reports_other_grouping_and_not_a_text_shift` (a dropped occurrence reported the same decisions), `test_a_third_life_reuses_an_earlier_life_entity_still_in_the_graph` (`entity_uuid_not_derived`) and `test_a_ledger_from_before_the_readd_follow_ups_is_refused` (no refusal on initialize). The reviewer's probe, dropping g01's `it`, now reports another digest.
- `uv run pytest -q -m 'not integration'`: 458 passed, 81 deselected (exit 0).
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with `PINNED` unchanged at 8504 nodes and 8349 sequences. `--mutants` caught all 52 breaks (exit 0), among them `begin-drops-last-tombstone` by P8 in 5 steps. The deep break `complete-keeps-last-tombstone` fails P8 on its recorded 8-step sequence (`tests/test_identity_ledger_check.py`, 62 passed).
- `support/occurrence_check.py` (`admission.py` changed one import): PASS on 540,045 worlds; `--mutants` PASS.
- `uv run pytest -q -m integration tests/test_identity_forget_native.py`: 25 passed in 553 s.
- Verify journeys, each with 0 FAIL rows: F1 (46 PASS), F2 (28), F3 (147 over seven stages), F4 (15), F5 (10), F6 (26 over two stages), F7 (8), F8 (8), F9 (7), F10 (13), F11 (9), F12 (9), F13 (13), F14 (10) and F15 (14); 363 PASS in all. `journey all` was not run in this round.

**Re-add follow-ups F1 and F2.** The assistant (a subagent) ran these on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-readd-followups`: the code at `a601fcf` (both follow-ups) and `ea23c39` (the second re-add's replacement of an earlier life's removed Entity). Fix round 1 changed what this evidence describes; its own evidence is below.

- Before the fixes, against `98ecaca`, the four new tests failed (no report, no carry, no `last_tombstone`). Six hand mutations of the new code (no carry in `complete`, the re-add rule or `validate_uses` reading the last life only, admission ignoring `last_tombstone`, Entities named by UUID or recipes left out of the decisions digest) each failed a new test. `test_a_second_readd_replaces_what_the_first_forget_removed` failed at `a601fcf` and passes at `ea23c39`; journey F15 found that defect, with `entity_uuid_not_derived` on the second re-add.
- `uv run pytest -q -m 'not integration'`: 452 passed at `a601fcf` and 453 at `ea23c39`, 81 deselected (exit 0 each).
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with `PINNED` unchanged at 8504 nodes and 8349 sequences. `--mutants` caught all 51 breaks (exit 0). The model's descriptions share their UUIDs across revisions, so P7 checks the new digest but not the carry; `test_a_second_forget_carries_the_first_tombstone_forward` checked the carry (replaced in fix round 1).
- `support/occurrence_check.py` was not run: `admission.py` did not change.
- `uv run pytest -q -m integration tests/test_identity_forget_native.py`: 25 passed in 537 s at `ea23c39` (also 25 passed at `a601fcf`).
- Verify journeys, each with 0 FAIL rows: F1 (46 PASS), F2 (28), F3 (147 over seven stages), F4 (15), F5 (10), F6 (26 over two stages), F7 (8), F8 (8), F9 (7), F10 (13), F11 (9), F12 (9), F13 (13) and F14 (10) on `a601fcf` (during the later of these runs the `readd_removed` change of `ea23c39` was already in the working tree; it adds nothing to a source without an earlier forgotten life), and F15 (14, new) on `ea23c39`. F1, F9 and F10 gained the `differs_from_forgotten` check. `journey all` was not run in this round.

**Fix round 3.** The assistant (a subagent) ran these on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-erasure` at `ae64aed` unless stated. The native tests, the checks and the journeys ran concurrently, so their times are inflated.

- Before the fix, at `af7218a`, `test_native_an_erasure_retry_of_a_failed_publication_retires_what_it_wrote` failed: the HC query still seeded HC. A probe of the same root found HC's node, its `Entity_name` vector and the HC edge with doc01's v01 contribution.
- `uv run pytest -q -m 'not integration'`: 447 passed at `28d61b9`, 448 passed at `ae64aed` and at `8e045aa` (exit 0 each).
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 8504 nodes and 8349 sequences, and at depth 6 with 56089 nodes and 55126 sequences. `--mutants` caught all 51 breaks by the property each names (exit 0), at `8e045aa`. `withdrawn-guard-admits-replace` fails at depth 7 by P5. `supersede-drops-chain` fails at depth 5 by P5, on these sources and on the `cb5fd20` sources, so it moved to the default breaks.
- `uv run python support/occurrence_check.py`: `PASS`; `--mutants`: `PASS`.
- `uv run pytest -q -m integration tests/test_identity_forget_native.py tests/test_identity_dependencies_native.py tests/test_identity_erasure_retry_native.py`: 36 passed in 905 s. New: `test_native_an_erasure_retry_of_a_failed_publication_retires_what_it_wrote`, and `test_native_a_failed_text_change_takes_the_removal` for a text change that failed before any write and after its writes.
- Verify journeys, each with 0 FAIL rows: F1 (45 PASS), F2 (28), F3 (147 over seven stages), F4 (15), F5 (10), F6 (26 over two stages), F7 (8), F8 (8), F9 (6), F10 (12), F11 (9), F12 (9), F13 (13), F14 (10, new), D1 to D6 (128) and G1 to G4 (109); 583 PASS in all. `journey all` was not run in this round; it ran at the checkpoint, below.

**Fix round 2.** The assistant (a subagent) ran these on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-erasure` at `cb5fd20`. The unit suite ran before each of the three code commits; the native tests, checks and journeys ran concurrently, so their times are inflated.

- `uv run pytest -q -m 'not integration'`: 447 passed, 79 deselected (exit 0 before `eae2b34` and `cb5fd20`; 445 before `e2a8c93`).
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 8504 nodes and 8349 sequences, and at depth 6 with 56089 nodes and 55126 sequences. `--mutants` caught all 49 breaks by the property each names (exit 0). The deep breaks fail at depth 7: `supersede-drops-chain` by P5 (a reconcile retry that drops `erased_from`) and `withdrawn-guard-admits-replace` by P5.
- `uv run python support/occurrence_check.py`: `PASS`; `--mutants`: `PASS`, with the new break `erase_nothing` caught.
- `uv run pytest -q -m integration tests/test_identity_forget_native.py tests/test_identity_dependencies_native.py`: 34 passed in 856 s. New: `test_native_a_failed_first_publication_takes_the_removal_in_its_saved_revision` and `test_native_a_failed_text_change_takes_the_removal_with_its_writer`.
- Verify journeys, each with 0 FAIL rows: F1 (45 PASS), F2 (28), F3 (147 over seven stages), F4 (15), F5 (10), F6 (26 over two stages), F7 (8), F8 (8), F9 (6), F10 (12), F11 (9), F12 (9), F13 (13, new), D1 to D6 (128) and G1 to G4 (109); 573 PASS in all. `journey all` was not run in this round; it ran at the checkpoint, below.

**Fix round 1.** The assistant (a subagent) ran these on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-erasure` at `8b109d0` unless stated:

- `uv run pytest -q -m 'not integration'`: 439 passed, 77 deselected.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 6431 nodes and 6300 sequences, and at depth 6 with 38470 nodes and 37733 sequences. `--mutants` caught every break (exit 0); the deep break `supersede-drops-chain` fails at depth 6 by P6.
- `uv run python support/occurrence_check.py`: `PASS` in 113 s; `--mutants`: `PASS` in 59 s, with the new breaks `erase_unbound` and `drop_read_recipes` caught.
- `uv run pytest -q -m integration tests/test_identity_forget_native.py tests/test_identity_dependencies_native.py`: 32 passed in 710 s (also 32 passed at `cd7f486`). New: `test_native_a_failed_refresh_takes_the_removal_in_its_saved_revision`.
- Verify journeys, each with 0 FAIL rows: F1 (45 PASS), F2 (28), F3 (147 over seven stages), F4 (15), F5 (10), F6 (26 over two stages), F7 (8), F8 (8), F9 (6), F10 (12), F11 (9), F12 (9, new), D1 to D6 (128) and G1 to G4 (109). `journey all` was not run in this round; it ran at the checkpoint, below.

**Checkpoint I.**

The assistant (a subagent) ran these on the user's Mac on 2026-10-23 with loopback embeddings, on branch `stage6-erasure`. The code is at `94de39c`; the commit after it changes documents and skill files only.

- `uv run pytest -q -m 'not integration'`: 431 passed, 76 deselected, in about 120 s. New: `tests/test_identity_erasure.py` (15 tests: the impact and its token, the removal revision and its admission, the refusals of an incomplete or overreaching removal, what stays unfinished, the tombstone and the scrubbed plan) and the fixture-kind test in `tests/test_identity_environment.py`. `tests/test_identity_storage.py` now completes a forget with a tombstone, checks the scrubbed plan and event message, begins a forget on a withdrawn row and on a failed first publication, and refuses an old-format forgotten row.
- `uv run python support/ledger_check.py`: `PASS verified within bound` at depth 5 with 6287 nodes and 6156 sequences. `--mutants` caught all 45 breaks by the property each names (exit 0), among them the seven new ones: `complete-keeps-description`, `complete-keeps-plan` and `complete-keeps-messages` by P7, `forget-on-failed-replacement` and `forget-on-failed-withdrawal` by P5, and `forget-refuses-withdrawn` and `forget-refuses-failed-publication` as `INCONCLUSIVE`. The deep break `withdrawn-guard-admits-replace` fails at depth 7 after 8346 nodes with its recorded sequence.
- `uv run python support/occurrence_check.py`: `PASS` with 540045 worlds in 123 s, each rule 6 row checked 54 times. `--mutants`: `PASS`, all 35 breaks caught, in 60 s.
- `uv run pytest -q -m integration`: 76 passed in 1806 s. `tests/test_identity_forget_native.py` has 23 tests; the file alone passed in 512 s before the last refactor commit, which renames one function and names the stale-token refusal once.
- Verify journeys, each with 0 FAIL rows, on `94de39c`: F1 (45 PASS), F2 (28), F3 (21 for each of seven stages), F4 (15), F5 (10), F6 (13 for each of two stages), F7 (8), F8 (8), F9 (6), F10 (12) and F11 (9). Every journey whose root takes `forget`, `readd` or `reconcile` also passed, on `94de39c`: D1 to D6 (128 PASS), P1 to P4 (66), W1 and W3 (89), R1 and R2 (107), E1 to E4 (125), O1 to O8 (219), G1 to G4 (109), I1 to I3 (94) and K1 to K4 (116). `journey all` was not run in this round; it ran at the checkpoint, below.
- A by-hand run on a `glossary-fixture` root failed doc01's forget at `forget_document` and finished it with `reconcile --source doc01`, through the glossary driver: doc01 forgotten, the incident resolved as `forgotten` with no message.

**Checkpoint runs.** The assistant and its subagents ran `.claude/skills/verify/scripts/verify.py journey all` on the user's Mac on 2026-10-23 with loopback embeddings. P5 calls the embedding API and did not run.

- On `d94b0a3` (after checkpoint I): 1407 PASS and 0 FAIL. The full integration suite's 76 passed in 1806 s above ran on this commit; its source files are as at `94de39c`.
- On `686dc16` (after fix round 1): 1416 PASS and 0 FAIL.
- On `af7218a` (after fix round 2): 1429 PASS and 0 FAIL.
- On `d6133c7` (after fix round 3): 1439 PASS and 0 FAIL in 80 runs, the 54 loopback journey blocks. The unit suite gave 448 passed on this code.
