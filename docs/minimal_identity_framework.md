# A minimal identity resolution framework on Cognee

A proposal for review. This document stands alone. It assumes you know Cognee basics (add, cognify, search, datasets, Data items, DataPoints, the graph, vector and relational stores) and nothing else.

## 1. What this document is

This is a design for a small identity resolution layer on Cognee 1.6.2, for someone building it from scratch in another project. It is derived from a reference implementation, which is the only evidence this document has. The reference implementation is a laboratory project on Cognee 1.6.2 that built identity resolution over 18 days, from its first design decision on 2026-10-11 to its last measurement on 2026-10-29. Two people appear throughout. The user is the person who commissioned the reference implementation and made its decisions. The assistant is the agent that built it under the user's direction. The reference implementation never ran a language model inside its tests. Every identity judgment in it is a captured fixture input, the corpora are small (two to four documents, six to ten chunks each), and every number below comes from its code, its test runs or its measurements. Appendix A says who measured what, when, and at which commit. The body keeps the design.

After the terms (section 2) and the Cognee behaviours the design rests on (section 3), the body has four parts. Sections 4 to 7 inventory the decisions the reference implementation made and measure what each cost. Section 8 lays out a few coherent designs from simplest upward. Section 9 proposes one on the simple side, says what it drops and how each dropped function can return. Section 10 lists the questions only the user can answer.

The user who commissioned this marked nothing as must-keep. One recorded requirement is respected throughout. A delete has two intents. Cleanup means "no longer needed" and may refuse while other sources depend on the source. Erasure means "must go" (privacy, legal, licence, a fabricated source) and must never be blocked by dependents. Section 9.6 says what the proposal does with each.

## 2. Terms

Every term below is used in the sense given here and in no other.

| Term | Meaning |
|---|---|
| Source | One original document registered as a Cognee Data item in a dataset. |
| Entity | Cognee's extracted graph node type. Cognify creates one per distinct normalized name. Its ID is derived from the name (`Entity.id_for(name)`). |
| Reusable Entity | An Entity that stands for a thing by name and can be referred to from any document. Cognee's own Entities are reusable. |
| Singleton | A reusable Entity that belongs to no identity group. |
| Variant | A reusable Entity that an identity judgment declares equivalent to another reusable Entity. `AFRL` and `Aurora Fusion Research Laboratory` are variants of each other. |
| Identity group | The set of reusable Entities connected by variant relationships. It has no privileged or canonical member. |
| Scope | Where a variant relationship holds. Corpus scope means everywhere. Document scope means inside one source only. The proposal has corpus scope only. |
| Mention | One occurrence, or a few adjacent occurrences sharing one interpretation, of a reference inside one document that is not a reusable name. "the controller" or "it". |
| Occurrence | An exact text range `[start, end)` in a source, in Unicode code points. |
| Resolution | The judgment that a mention refers to a specific reusable Entity (accepted), to none that can be named (unresolved), or to more than one candidate (ambiguous). |
| Decision | One identity judgment inside a description. A variant pair, a mention resolution, or a fact. |
| Describe | The step that reads a source and produces its identity judgments. It may be rules, a language model, or a person. The reference implementation only has captured describers. |
| Description | The structured output of Describe for one source, saved as JSON. Also called the saved intent. |
| Publish | Writing a description's judgments into Cognee's graph and vector stores as nodes and edges. |
| Overlay | The nodes and edges that Publish adds beside Cognee's own graph. |
| Ledger | A project-owned relational table that records, per source, which description revision is published and whether that publication finished. |
| Revision | A counter per source. Each new description for the same source gets the next revision. |
| Ownership | Cognee's mechanism for deciding what a delete removes. Every node and edge carries ownership keys naming the Data items, or chunks, that wrote it. A delete removes an object when its last owner goes. Section 3 explains the keys. |
| Anchor | In the proposal, a small Data item registered per published revision so that the overlay has an owner of its own. It holds no description. |
| Sentinel | In the proposal, one graph node per published revision, owned by the anchor, whose presence shows that the overlay is still in the stores. |
| Served | A source whose ledger row is `current` and whose stores still hold what the row describes. Retrieval reads only served sources. |
| Reconcile | Running a source's last operation again from its ledger row until the stores match the row. For a `pending`, `failed` or `current` row that is Publish's steps 3 to 6 from the row's own description. For a `forgotten` row it is Forget. |
| Generated source | The reference implementation's practice of registering each full description as its own Cognee Data item, so the overlay has a native owner. |
| Contribution | In the reference implementation, a per-source entry on a shared identity edge that records which source asserted it and in what scope. |
| Withholding | Excluding a judgment from retrieval because an input it read has changed or gone, until a reviewer confirms or replaces it. |
| Re-confirm | A reviewer's statement that a withheld judgment still holds. |
| Attestation | The record of who re-confirmed a judgment, keyed by the producer that made it. |
| Citation | A judgment in one source naming a judgment in another source as an input. |
| Cascade | The removal of citing judgments, level by level, when the cited source is erased. |
| Cleanup | The delete intent "no longer needed". It may refuse while dependents exist. |
| Erasure | The delete intent "must go". It must never be blocked by dependents. |
| Tombstone | What the ledger keeps after a source is forgotten. In the reference implementation, identifiers only. In the proposal, the ledger row with its description and hash set to null. It keeps the dataset, the source ID, the revision counter and the timestamp. |
| Sweep | In the proposal, step 6 of Publish. It removes every anchor of a source below the row's revision by `cognee.forget`. Reconcile runs it again. |
| Seed | The first node or nodes a retrieval starts from, before any expansion. |
| Closure | The set of Entities reached from a seed over `variant_of` edges, plus the mention nodes that resolve into it. |
| Status, Resolve, Retrieve | Operations of the proposal, defined in section 9.3. Status reports each row and its facets. Resolve returns the closure for a query. Retrieve returns the closure with its facts. |
| Graph provenance | Cognee's mode in which ownership keys live in columns of the graph store. Cognee turns it on for a graph that was empty at its first write. Section 3 explains the consequence. |
| Pipeline context | The object Cognee's Tasks receive. It names the user, the dataset, the Data item and, inside a pipeline run, the run ID. Ownership keys are derived from it. |
| Task | One step of a Cognee pipeline such as cognify. Cognee runs the Tasks of a pipeline in order over each Data item. |
| Native test | In this document, a test that runs against real Cognee stores, as opposed to a unit test with fakes. |
| Fact | A relation between two graph nodes with the text that supports it. The reference implementation anchors a mention's facts on the mention node. |
| Left absent | A publish result entry naming an edge that was not written because its endpoint node did not exist. |
| Settled read | In the reference implementation, a retrieval that re-reads the ledger at its end and starts again if a writer changed it meanwhile. |
| Native copy | What Cognee still holds of a source after a delete made outside the framework. |
| Refusal code | A short string a command returns instead of acting, such as `native_changed`. The reference implementation has 109 distinct codes. |
| Ladybug | Cognee's default embedded graph database. Cognee's graph adapter for it merges edges on (from, to, relationship name). |
| Triplet vectors | Vector points Cognee's optional Improve step writes per edge into a `Triplet_text` collection, so that native search can find edges by text. |
| Journey | In the reference implementation, a scripted end-to-end run of its command line against real stores, with assertions. A verification artifact. |
| Oracle | A brute-force enumeration of small worlds (two to four sources) that checks every rule outcome. A verification artifact. |
| Mutant | A seeded bug that a checker must catch, to prove the checker can fail. |
| Fault stage | A named point inside an operation where the reference implementation can inject a failure to test recovery. |

Sections 4 to 7 inventory the reference implementation and use its own vocabulary. File names such as `admission.py` are modules of the reference implementation under `src/cognee_lab/identity/`. The terms below belong to the reference implementation only. The proposal has none of them.

| Term | Meaning in the reference implementation |
|---|---|
| Admission | The step between Describe and Publish that decides, for an edit, which old mention groups continue and which retire. |
| Occurrence map | Admission's input. A map from each old occurrence to its new group, or to null when it is gone. |
| Group key | The stable key a description gives a mention group, used to match it across revisions. |
| Peel-off | The admission rule that lets a group continue only with its key and all of its surviving occurrences, and retires it otherwise. |
| Withdraw | Removing a source's identity interpretation while keeping its document, facts and markers. |
| Fingerprint | A digest of an input (a text span, a saved record, a corpus object) stored with the decision that read it. |
| Recipe | The stored instructions for creating one Entity, kept for every Entity a source needs. |
| Producer | The program or person that made a decision, recorded with a method and a version. |
| Plan | A row saved before a destructive write that holds everything forward recovery needs to finish the operation. |
| Attempt token | A per-attempt identifier written into the ledger so a retry can tell its own partial writes from another attempt's. |
| Writer reservation | A row that one writer holds per dataset so that two publishes do not interleave. |
| Marker edge | The `has_identity_mention` edge from a chunk to a mention node. |
| Retirement snapshot | The list of ownership keys a removal will detach, saved in the plan before the removal starts. |
| Fence | A refusal that stops a publish from consuming a source whose removal is half done. |
| Scrub whitelist | The list of ledger columns a forget is allowed to leave on the tombstone. |
| Dry-run token | A value a forget preview returns, which the real forget must present, so that the caller confirms exactly the impact it saw. |
| Removal revision | The new revision a dependent source gets when a cascade removes its citing decisions. |
| Helper node, helper edge | A graph object the overlay writes for its own bookkeeping, as opposed to an Entity or a fact. |
| Evidence rows | Cognee's relational rows that tie an edge to the chunk text that supports it. |
| Census | The script that labels each line of the reference implementation by purpose. Section 5 reports its output. |
| Churn | Lines added plus lines removed over the project's history, by module. |
| Checkpoint | A merge to the reference implementation's `main` branch after a reviewed block of work. |
| Conformance describer | The rule-based producer the reference implementation wrote for one fixture document, used as a regression gate. |
| Manifest | The hidden list of correct answers for a fixture document, which no describer may read. |
| Loopback embeddings | A deterministic local embedding used in tests instead of an embedding API. |
| Improve, Memify | Optional Cognee steps after cognify. Improve writes triplet vectors. Memify runs further enrichment passes. The reference implementation left both off. |

## 3. Cognee behaviour that drives the design

How ownership works in Cognee 1.6.2, because the proposal rests on it. When `add_data_points` writes nodes and edges with a pipeline context that names a dataset and a Data item, each node and edge gets an ownership key. Output a chunk produced gets a chunk-scoped key, `source_ref:v2:{dataset}:{data}:{chunk}`. Output no chunk produced, such as the document node, gets a document-scoped key, `source_ref:v1:{dataset}:{data}`. A write that runs with a Data item's context and no chunks stamps everything with that item's v1 key. Keys accumulate. Writing an object that exists adds the new owner and keeps the old ones. `attach_node_source_refs` and `attach_edge_source_refs` add a key to existing objects without a property write. `delete_by_source_ref(key)` deletes every object that key alone owns, detaches the key from objects with other owners, and deletes the vector points of the deleted nodes and edges. `cognee.forget(data_id)` does that for every key of one Data item, v1 and v2, and then removes the Data row and its stored file. All of this was read in the Cognee source for this document (Appendix A).

Two more facts about the keys shape the proposal. First, Cognee stores the keys in graph columns only for a graph that was empty at its first `add_data_points` and was marked for graph provenance then (`infrastructure/databases/provenance/markers.py:48-73`). A graph that already held data keeps ownership in relational ledger rows, and the graph reads below return no keys for it. Second, the ordinary reads `get_node` and `get_edges` return `id`, `name`, `type` and `properties` and nothing else (`ladybug/adapter.py:2219-2244` and `:2132-2180`). The keys live in separate columns (`adapter.py:73-83`). Reading them takes `get_node_delete_data(node_ids)` and `get_edge_delete_data(edges)`, which return the keys of the listed objects in batches of 2,000 per query (`adapter.py:1523-1608`), or `find_nodes_by_source_ref(key)` and `find_edges_by_source_ref(key)`, which scan the whole store per key (`adapter.py:1610-1633`). All four are `GraphDBInterface` methods whose default implementation raises `UnsupportedProvenanceCapability` (`graph_db_interface.py:326-430`). Ladybug implements them. They are not part of `cognee.*`.

Each row below is a behaviour of Cognee 1.6.2 that the reference implementation measured or hit. Each one costs something to coexist with. Section 6 ranks them by that cost.

| ID | Behaviour | Measured evidence |
|---|---|---|
| CB1 | An Entity's ID is derived from its normalized name. Different surface strings give different nodes, so aliases and acronyms fragment. | In a 98-Entity document, `afrl` and `aurora fusion research laboratory` were separate nodes, as were three forms of `neutral beam injection`. |
| CB2 | Writing a DataPoint whose ID already exists replaces the whole property blob. Omitted properties vanish. Edges stay. | Ingesting a second overlapping document rewrote properties on 30 existing Entities (description on 30, custom role fields on 9). An identity resolver that read those fields went from 5 of 5 benchmark passes to 0 of 5. |
| CB3 | Extraction is stochastic and chunk-local. The same document gives different Entity counts across runs. | 88, 93 and 98 Entities across three runs of one document. |
| CB4 | Native retrieval gives a custom edge such as `resolves_to` no meaning. Graph completion can walk into the wrong neighbourhood. | For "the controller" a graph-completion answer entered the wrong system's neighbourhood. Raw text retrieval rescued it. |
| CB5 | `SearchType` is a closed enum. A plain string cannot name a search type. | The reference implementation adds an `IDENTITY` member through Python 3.12 enum internals, behind a pin to exactly Cognee 1.6.2 and Python 3.12, with an import-time self-test and rollback. |
| CB6 | Deletion follows ownership keys. Deleting a Data item removes nodes and edges whose last owner it was. Deleting a node detaches all its edges, owned or not. Objects nothing owns are left behind. | Deleting one document removed 74 nodes and 329 edges, kept 45 shared nodes, and left 35 stale helper nodes, 14 isolated nodes and 43 orphan triplet vectors. |
| CB7 | A Data delete is not atomic across stores. Cognee commits the Data row, then sweeps evidence rows and stored files. A graph-API node delete leaves the node's name vector behind. | A review of the reference implementation's first forget found the commit-before-sweep gap. A `graph.delete_node` left the `Entity_name` point. |
| CB8 | There is no cross-store transaction. Graph, vector, relational and file writes each commit on their own. | Stated by the reference implementation at every checkpoint. It is why the ledger exists. |
| CB9 | Ownership attaches only when a write carries a concrete Data item context. A pipeline run tags only what a Task writes with the pipeline context. Rollback and startup recovery find writes by run ID. | A rollback that removes a chunk removes every edge ending at it, including custom ones. |
| CB10 | `cognify`, `update`, `remember` and the delete paths take no Task list and have no hook. Incremental `update` is refused for any custom model, prompt or chunker, and never runs custom Tasks. A full-rebuild update gives every chunk a new ID. | The first incremental update probe left 93 evidence rows naming retired chunks and 71 new edges absent from the triplet index. |
| CB11 | Plain `cognee.cognify` sends every registered Data item not marked processed to the language model, including a project's own files. A project marks its own file processed with `mark_data_processed`. | 12 LLM calls to a closed port for unmarked project files. |
| CB12 | DocumentChunk stores no document start and end offsets. Chunk IDs derive from content and can recur after an edit while positions move. | The reference implementation maps spans with `chunk_offsets` over the standard non-overlapping chunker. |
| CB13 | `add_edges` silently drops an edge whose endpoint node is missing. | Found when a republish tried to recreate a deleted Entity's edges. |
| CB14 | The `Entity_name` vector collection is shared across datasets. With access control off, the dataset argument does not confine search. | Another dataset's Entity displaced a seed in a retrieval probe. |
| CB15 | Cognee loads an env file at first import with `override=True`. | A fixture meant to use loopback embeddings used 2048-dimension API embeddings and wrote into the lab's own store. Harness cost only. |
| CB16 | `prune_system(metadata=True)` deletes the relational database, including any project table in it. The default call is `prune_system(graph=True, vector=True, metadata=False)`. It wipes the graph and vector stores, keeps every Data row with its hash, and does not reset any item's processed mark, so a later plain `cognify` skips the item. | Read in the source. The reference implementation treats a metadata prune as a reset, not a repair, and built a repair command for the default prune. |
| CB17 | `cognee.forget(dataset=..., data_id=..., memory_only=True)` deletes one item's graph and vector objects, keeps its Data row and file, and clears its processed mark. | Read in the source. The reference implementation uses it inside every text edit. |
| CB18 | `cognee.add` of new content mints a random Data ID. `cognee.update(data_id, ...)` keeps the ID and rebuilds the chunks. A caller may pin an ID with `DataItem(data=..., data_id=...)`. | Read in the source. The reference implementation pins every ID it registers. |
| CB19 | Ladybug merges an edge on (from, to, relationship name) and overwrites its properties on every write. Two writers of the same edge keep one edge with the last writer's properties and both owners. | Read in the source. The reference implementation refuses a publish whose edge kind differs from the existing edge's kind. |

## 4. Decision inventory

Decisions are grouped by area. Each row gives the choice, the alternatives it beat, the reason, and what it cost and bought. Appendix A dates each decision and says who made it. Line counts are measured at one commit (Appendix A) unless the row says otherwise.

### 4.1 Representation

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Identity is a non-destructive overlay. Cognee's Entities are never merged or rewritten. | Physical merge. A stricter replacement graph. Cognee's optional destructive consolidation. | Cognee's identity was partly right (3 of 6 cases) and partly wrong. Merging destroys the evidence for why two nodes existed, and some merges would be wrong. | Every equivalence needs its own stored record and edges, and a read path that expands the group at query time. | Reversible judgments. No loss of source evidence. |
| No identity state in Entity properties. No `entity_role` field, no canonical member. | Role fields on a subclass of Entity (the earlier prototype). One support node per assignment. | CB2. The prototype's role fields were overwritten by the next ingest and the resolver stopped working while every edge survived. | Authority must live outside the graph. This forces the saved description and the ledger. | Identity survives later cognify runs. |
| One edge type `resolves_to` with `resolution_kind` in {variant, mention}. Variant is read as bidirectional and transitive. Mention is directed and never bridges two groups. | Two edge types. Treating a historical mention as an alias. | A benchmark query "what does the controller do" must stay ambiguous even though an earlier document resolved "the controller" once. | Closure rules written in a custom retriever (eight rules). | Scoped references that never become global aliases. |
| A mention is one document-local Entity node per local reference group, with several exact ranges, instead of one node per occurrence. | One node per occurrence. Saved-record-only mentions. Larger section groups. | Pronoun volume. No measured saving was claimed. | Split and combination rules, range validation, and the problem that a relation on a group node does not identify one occurrence. | Fewer graph objects (not measured). |
| Mention markers are `has_identity_mention` edges from the original DocumentChunk to the mention node. No singleton or variant markers. | Marker from the generated source's document node. | Removing or rebuilding the generated source must not delete the marker, and an unresolved mention must stay classified as a mention. | Only chunks covering an occurrence own markers. Testing found that the chunk's key must also sit on the mention node, or withdrawing the generated source deletes the node and cascades into the marker. | Unresolved mentions keep their classification. |
| Explicit UUIDs for every object the overlay creates, derived as `uuid5(generated source Data ID, "kind:r{revision}:{key}")`. | Key-only derivation. Cognee's name-derived IDs. | A key that returned at a later revision re-derived a retired UUID, and the store keeps only the current revision so it could not tell. | Admission must advance exactly one revision per step. | No retired ID returns with a new meaning. |
| Shared identity edges carry a contribution list (assignment, source, scope) and `resolution_kind` once. | Last-publisher-wins, which the user permitted. Parallel edges per source, which Ladybug cannot store (CB19). | Publication order should not change scope. Native Forget does not recompute custom properties. | O(k) checks per visited edge. Withdrawal must remove the payload before native key deletion. Retirement snapshots in every plan. | A shared edge survives when one source goes with the survivor's scope intact. |
| Variant topology is free. No spanning tree, no density limit, cycles allowed. | Pruning redundant paths. | Removing an apparently redundant edge can discard a source's contribution. | Traversal needs visited-state tracking and bounds. | No pruning logic. |

### 4.2 Saved form

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| The description is one JSON document per source with sections inputs, producers, entity constructions, mention groups, mention resolutions, variant assignments. | Readable identity prose that cognify would extract. One source per assignment. | Ordinary LLM parsing is not trusted to reconstruct the graph faithfully. CB3. | A schema in Pydantic (the Python validation library Cognee uses), cross-record checks beyond JSON Schema, and canonical JSON hashing per RFC 8785 (a fixed serialization, so equal documents hash equal). `models.py` 363 lines, `validation.py` 339. | Publication is replayable from saved intent without a model call. |
| The description is registered as a Cognee Data item (the generated source), never chunked, so that it is the native owner of the overlay. | Keep it only in the ledger. | Native Forget and ownership then apply to the overlay. | Two copies of the description (section 9.5). A processed mark so plain cognify skips the file (CB11). Each revision rewrites the Data item through `ingest_data`, which once renamed the item after its text hash until the write was changed to a named upload. | The overlay has a native owner distinct from the original. |
| Occurrences are document-relative code-point ranges bound to a text fingerprint, mapped to chunks with `chunk_offsets`. First-substring matching is forbidden. | Byte offsets. Chunk-local offsets. A quoted span with first-match. | CB12. Repeated substrings are common in technical text. | Mapping recomputed after any text change. Overlapping chunkers unsupported. | Exact, checkable locators. |
| Construction recipes for every Entity the source needs, including existing ones it only references. Recipes are seeds, not snapshots. | Recipes only for Entities the source created. | A last-owner sequence. Document A creates an Entity, source B retains it, A's update drops its ownership, a rebuild of B deletes the Entity temporarily and must bring it back. | UUID-use validation, a view built by scanning descriptions, and the rule that an old recipe never recreates an Entity deleted outside the lab. | A rebuild does not orphan shared Entities. |
| Per-decision input references with fingerprints (source text, span, corpus object, saved record). Producers recorded with method and version. | No input record. | Needed before any dependency response can exist. | 907 lines of provenance checks (8.2% of core). JSON grows with inputs. | Dependency withholding, citations and erasure impact all read these. |

### 4.3 Ledger and crash recovery

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| A project-owned relational table keyed by dataset and source. States pending, current, failed, withdrawn, forgotten. Intended and verified revision, attempt token, the description, a plan. It is the sole authority for retrieval eligibility. | Cognee's pipeline status. A/B whole-store generations. A separate SQLite file. | CB8. Cognee's run status shows `cognify_pipeline` completed after a project Task failed. | 3 tables, 16 columns, 5 states, 9 transitions, 19 refusal codes. `storage.py` 788 lines, `stages.py` 110. Proof tooling 2,326 lines, 2.3 times the ledger area's 995 lines. | Retrieval withholds an unfinished source while others stay usable. A retry needs no model call. |
| Recovery is explicit forward completion from a saved plan, never rollback. No step replay, no automatic retry, no background scanner. | Complete semantic capture and exact replay. A/B staging. | Files, ledger and graph share no transaction. Retirement intent must be saved before destructive writes, never reconstructed from missing graph state. | Plans carry old and new text, chunk budget, previous description and retirement keys. Fault injection at each stage. Publish has 3 fault stages, withdraw 3, replace 9, forget 10. | Forward completion to the exact saved revision. |
| A writer reservation per dataset by portable conditional update. | File locks. Database-specific locks. | Backend portability rule. | 1 table. A hard crash can leave the reservation held (documented, not fixed). | One writer per source set. |
| Recovery events table. | Logs. | Record real recovery needs to decide later what to automate. | 1 table, dedup logic, scrub on forget. No automation was ever built from it. | Diagnostics. |
| Verification by a bounded exhaustive Python checker with seeded mutants, not TLA+ (a model-checking language). | TLA+. | Preference. | The ledger check enumerates every call sequence to depth 5. 9,205 nodes and 9,050 sequences in about 15 s. 53 of 53 mutants caught. | Confidence that the ledger rules are complete over small worlds. |

### 4.4 Change response, text edits

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Whole-document rebuild on every edit. Cognee re-chunks the document. The identity revision stays incremental through an occurrence map. | Native incremental update. Partial refresh. | CB10. Native incremental update never runs custom Tasks and replaces the chunks the markers sit on. | Every chunk gets a new ID per edit. Markers, facts and evidence are regenerated. `admission.py` 702 lines. 32 refusal codes in this area, the most of any. | Any mix of keep, remove, add and regroup in one edit without a bespoke mode. |
| One general admission over a map "old occurrence to new group or null". Three edit modes were deleted. | A mode per kind of edit. A separate small-correction path. | A mixed edit fit no mode. A looser side path let unreviewed changes in. | 25 named rules in order. Oracle over 540,045 small worlds plus 27,102 corruptions, 31 of 31 mutants caught. | New edit shapes cost a fixture, not a code path. |
| Strict peel-off. A group continues only with its key, all its survivors, at least one, and no foreign occurrence. A changed referent, kind or interpretation retires the group and declares a fresh one with new UUIDs. | Continue the larger part. In-place change of meaning. | A served ID never carries a different meaning. | Facts regenerated per fresh group. Span-scoped variants refused in edits. | Stable meaning of IDs. |

### 4.5 Change response, ownership, forget, erasure

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Ownership split. Original chunks own markers and facts. The generated source owns resolution contributions and endpoint retention. | Everything under one owner. | Native Forget of the original must take the facts with it, and must not take the shared identity edges. | A coordinated forget, `attach_node_source_refs` retention, a preflight that refuses unsafe endpoint cascades. A test bug where a reused endpoint lacked the second source's key and the first source's removal cascaded into the second's fact. | Removal of one source cannot kill another's fact. |
| Withdraw is separate from forget. Withdraw retires a source's identity interpretation and keeps the original, facts, markers and evidence. | One delete. | A source can leave the overlay without losing its facts. | `withdraw.py` 131 lines, a `withdrawn` state, 3 fault stages. | Reversible participation. |
| Forget is logical erasure to a tombstone of identifiers. Dependents are removed, not withheld. A forget that changes other sources needs a dry-run token. | The first forget, which refused while dependents existed. Withhold dependents. A restorable forget. | The user's Cleanup versus Erasure separation. Erasure must not be blocked. | Tombstone model, scrub whitelist, removal revisions per dependent, erasure retry for a failed dependent, a fence `retiring_source` that refuses a publish consuming a half-forgotten source, 10 fault stages. Forget family 2,907 lines (26.1% of core), 26 refusal codes, 102 tests. | A source that must go, goes, and its dependents lose exactly what cited it. |
| Erasure cascades down citation chains under one token, in levels. | An interim refusal while a chain exists. | Chains were built. A cited source may need erasing. | `erasure.py` 749 and `erasure_rules.py` 654 lines. Cascade check over 34,752 worlds, 23 of 23 mutants. Four review rounds each found a new chain shape until the invariant "retiring a source never changes what an unfinished cascade does to another source" was checked on every world. 25 commits. | Transitive erasure. |
| A removed Entity UUID is never reused. Append-only table. | Reconstruct "removed by the lab" from tombstones and plans. | Three review rounds each found a re-add that wrote a removed UUID again, because later operations overwrite the plan row. | 1 table, 5 columns, about 409 lines across re-add paths. | No resurrected IDs under stale readers. |
| Dataset delete is the sum of per-source forgets plus a listed remainder. `cognee.forget(dataset=...)` is never called. | Native dataset forget. | Native dataset forget deletes whatever the dataset holds at that moment with no hook. | `dataset_forget.py` 345 lines. | A confirmation token that covers exactly what goes. |

### 4.6 Deletes made outside the lab

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Do not wrap or hook Cognee's deletes. Detect afterwards by comparing five facets of each source's native copy. `reconcile` refuses `native_deleted`. `forget` works on a gone source. | A delete wrapper (returns only if erasure from plain Cognee calls becomes a requirement). | CB10 gives no hook. | `native_copy.py` 174, `outside_deletion.py` 296, call sites, orphan vector sweep. About 690 lines, 43 tests, 7 journeys. | The ledger cannot silently disagree with Cognee. |
| An Entity deleted outside the lab stays absent. A publication never recreates it. A re-add naming it is refused while a saved source still cites it. | Recreate silently. | A reader would see a different Entity under the same UUID. Also CB13. | Deadlock found and fixed. Two withheld decisions citing the deleted Entity blocked each other's replacement. | No usable dangling references. |

The five facets are the original's Data row, the generated source's Data row, the original's document node, the original's chunks, and the stored files. Each exists because one native operation removes exactly that facet. A native forget takes the Data row and document node. A dataset forget takes both Data rows and the graph. The default prune keeps the Data rows but takes the graph and the stored files. An incremental update keeps the Data row and replaces the chunks. Section 9.10 says which facets the proposal keeps.

### 4.7 Dependencies and citations

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| A text edit of a consumed document withholds only the dependent decisions that read what changed. Withholding rows are written in the edit's own attempt. Moved spans are found by length and digest. | Block the edit. Withhold the whole dependent. Serve with a stale flag. | Too coarse. | Table of 12 columns. `withholding.py` 473, `review.py` 368. Four fix rounds. Three reviews each found a new bypass of the re-confirm rule until it was stated as an invariant. | An edit never silently serves a stale dependent. |
| A decision may cite another source's decision as a saved record, pinned by a fingerprint. Withholding spreads down the chain at read time with no stored mark. Cycles are refused per source. | Revision pins (would withhold on every upstream revision). A dependency index. | Fingerprints change only when reviewed content changes. | `chains.py` 234, `records.py` 446. Chain check over 2,224,128 worlds and 814,500 key-reuse cases. Its own CI job of about 200 s. Mutual citation between two sources is refused even when no decision cycle exists. | A derived conclusion cannot stay served after its input changed or was erased. |

### 4.8 Entry points and retrieval

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Lab `add`, `cognify`, `remember`, `update` run Cognee's standard Tasks under the pipeline name `cognify_pipeline` plus one lab Task. No Cognee patch. | A small Cognee patch adding a Task-transform hook (preferred at first, dropped). Plain Cognee calls plus a separate publish function. | A patch needs maintenance across versions. | `entry.py` 329, `entry_update.py` 201, `native_chunks.py` 70. A processed mark on every managed file. One source per run because Cognee runs a run's items concurrently. Named crash windows between clearing and restoring the mark. | No fork. Publication under Cognee's own pipeline name. |
| Retrieval through `cognee.search` with an added `IDENTITY` enum member. Evidence only, no LLM. | A plain library function. Patching `recall` or `search`. | Uniform entry for callers. | CB5. 102 lines of registration code, a version pin to exactly Cognee 1.6.2 and Python 3.12, limits (schemas built before import, a fresh `cognee search` process) and the area's 4 refusal codes (section 5.2, area 9). | One call surface. |
| Retrieval resolves the query before expanding, seeds only from the searched dataset's served sources, re-reads the ledger at start and end (a settled read), and dedupes only repeated physical edges. | Resolve after recall. Fold identity into the index. | CB4, CB14. | `retrieve.py` 463, `settled.py` 121, `delivery.py` 187. A conformance check against a committed baseline. Recall 10 of 18 manifest facts. The describer had seen the answers, so this is not a benchmark. | Identity closure that native modes cannot do. |
| Native search types stay unguarded. The documentation warns. | A guard. | Undecided. | A measured limit. `GRAPH_COMPLETION` served a withheld fact. `CHUNKS` served a failed publication's text. | Nothing. It is an accepted hole. |
| Improve, Memify, the answer cache and feedback stay disabled. | Default Improve. | Default Improve indexed all 761 edges including 62 helper edges into triplet vectors. | A profile that must stay disabled. | No triplet lifecycle, no cache invalidation. |

### 4.9 Dead ends

Approaches the reference implementation tried and then removed. Each one is a trap a fresh build can skip.

| Tried | What went wrong | Replaced by |
|---|---|---|
| A custom top-level `graph_model` as the extractor | Replaced Cognee's whole semantic layer. Persisted 3 of 8 recognized abbreviations. Typed output constrains shape, not recall. | Typed overlays beside the default graph |
| A DataPoint as the LLM output type | Persistence fields leaked into structured output and broke it. | Plain Pydantic output converted deterministically |
| Identity role fields on Entity (`entity_role`, `graph_layer`) | Overwritten by the next overlapping ingest (CB2). | Markers, edges and a saved description |
| One graph support node per assignment | Superseded before build. | Contributions on edges |
| One mention node per occurrence | Volume. | Local reference groups |
| The generated source's document node as the marker anchor | Rebuilding the generated source deleted markers. | The original chunk as anchor |
| Key-only derivation of fresh group UUIDs | Re-derived a retired UUID when a key returned. | Revision in the derivation |
| Three admission modes for three kinds of edit | A mixed edit fit none. | One occurrence map |
| A separate admission for unchanged-text corrections | Let unreviewed changes in. | Folded into the one admission |
| Forget that refuses while dependents exist | Blocked erasure. | Erasure with cascade |
| Whole-document refusal of an edit while any source reads it | Too coarse. | Per-decision withholding |
| Reconstructing "removed by the lab" from tombstones and plans | Later operations overwrite the plan row. Three review rounds. | Append-only removed-UUID table |
| A Cognee patch adding a Task-transform hook | Maintenance across versions. | Entry points under `cognify_pipeline` |
| A/B whole-store candidate generations | No cross-store snapshot exists. Copy over open files. Reader re-binding. | Pending state plus forward recovery |
| Register every source first, then cognify each | A failure left a source registered with no processed mark, exposed to plain cognify. | Add then cognify per source |
| A rollback exemption for a rollback that could no longer happen | Hid a delete made outside the lab. | Removed |
| Authoring the conformance describer from the hidden answers | Would have made the check a tautology. | Describer reads only the document. The check is a regression gate, not a benchmark |
| Ingesting a description rewrite as a plain string | Cognee named the Data row and document node `text_<md5>` on every rewrite. | A named upload object |

## 5. Complexity register

### 5.1 Where the reference implementation's lines are

The package `src/cognee_lab/identity` has 16,672 lines in 62 files. Core (excluding CLI, environment and scenario fixtures) is 11,121. Proof tooling in `support/` is 7,364 lines. Tests are 452 `def test_` functions in 59 files, 15,738 lines. pytest collects 827 cases from them, 707 unit and 120 integration, because 37 of the files parametrize. 103 verify journeys. 109 distinct refusal codes. 5 relational tables with 33 columns. 439 commits. Labels per line come from a census script that classifies by module docstring and caller, so the split below is one person's judgment.

| Purpose label | Lines | Share of core |
|---|---|---|
| Change: retirement by native ownership (withdraw, forget, re-add) | 3,114 | 28.0% |
| Change: dependency on recorded inputs (withholding, refresh) | 1,654 | 14.9% |
| Change: revision continuity and replace orchestration | 1,242 | 11.2% |
| Change: native rebuild for a new text | 475 | 4.3% |
| Ledger and crash recovery | 995 | 8.9% |
| Provenance checks | 907 | 8.2% |
| Record model and self-consistency | 924 | 8.3% |
| Publish one revision's overlay | 904 | 8.1% |
| Retrieval | 906 | 8.1% |

Change response is 6,485 lines, 58.3% of core. 329 of 452 tests (72.8%) and 79 of 103 journeys exercise a change after publication. 32 journeys are fault or recovery journeys. First publication and retrieval together are 1,810 lines, 16.3% of core. That pair is not a complete design. A build with no change response still needs the ledger, the record model and some provenance, which sit in other labels.

### 5.2 Per function

Data cost counts stores, tables, columns, node and edge types and copies. Implementation cost counts lines, rules, refusal codes, tests and proof checks. Each number is measured unless marked estimate. The area split is a judgment, and it is a different cut from the purpose labels of section 5.1. Section 5.3 reconciles the two where they differ. Later sections cite these rows by number.

| Area | Function | Data cost | Implementation cost (measured) | Notes |
|---|---|---|---|---|
| 1 | Identity core (groups, mentions, variants, publish, resolve) | Graph: mention Entity nodes, `resolves_to` edges with `resolution_kind`, `has_identity_mention` marker edges. Vector: mention names enter `Entity_name`. No table. | 505 lines, 14 codes, 13 tests, 5 journeys. Plus the model, `models.py` 363. | The smallest area. `publish.py` is 755 lines. The census labels 427 of them as publish and the rest as ownership, provenance, contributions and ledger calls. |
| 2 | Valid writes and provenance (fingerprints, inputs, producers, recipes, chunk mapping) | In the description: inputs with digests, producers, recipes per Entity, exact ranges. No table. | 1,831 lines (16.5%), 16 codes, 12 dedicated tests. `records.py` 446, `validation.py` 339, `native_copy.py` 174. | Most of it exists so that dependency and erasure can be computed later. Without those, what remains is the schema, the text fingerprint and chunk mapping, about 400 lines (estimate). |
| 3 | Ledger and crash recovery | 3 tables, 16 columns (publications 9, writers 2, recovery events 5). States 5, transitions 9. The plan column holds a third copy of the previous description during a replace. | 995 lines (8.9%), 19 codes, 21 tests, 32 fault or recovery journeys. Proof 2,326 lines. Depth-5 check 9,205 nodes in about 15 s. 53 mutants. | A world with publish and reconcile only needs 3 states and 4 transitions (counted from the transition table). Forget adds one state and the re-add transition. |
| 4 | Text-edit continuity (occurrence map, admission, fresh groups) | Plan carries `occurrence_map`, old and new text, chunk budget. Revision-scoped UUIDs. | 1,516 lines (13.6%), 32 codes, 99 tests, 31 journeys. Proof 2,673 lines of which 1,328 are dependency and erasure worlds. Oracle 540,045 worlds. | The alternative, edit equals forget plus re-add, has no admission rules at all. |
| 5 | Ownership (withdraw, forget, erasure, cascade, re-add, dataset forget, removed UUIDs) | 1 table (removed entities, 5 columns), 1 column (`last_tombstone`), states withdrawn and forgotten, tombstone model 96 lines, contributions on every shared edge, retirement snapshots in plans. | 3,114 lines (28.0%), 31 codes, 102 tests, 26 journeys (23 forget, 3 withdraw). Forget has 10 fault stages. Proof 1,616 lines (cascade). Churn 7,770 lines, the largest category. | Forget family alone 2,907 lines. Review-found bugs cluster here (section 5.4). |
| 6 | Deletes made outside the lab | None. Five-facet comparison at read time. | About 690 lines (6.2%), 5 codes, 43 tests, 7 journeys. | Exists because CB10 gives no hook and the design keeps a ledger that can disagree with Cognee. |
| 7 | Dependencies and citations with withholding | 1 table (withholdings, 12 columns). Saved-record inputs with fingerprints. Records registry. | 1,654 lines (14.9%), 17 codes, 83 tests, 17 journeys. Proof 1,264 lines. Chain check 2,224,128 worlds, about 200 s, its own CI job. | Review churn was highest here relative to size (four fix rounds for one rule). |
| 8 | Entry points and native rebuild | A processed mark per managed file. One run per source. | 971 lines including the CLI, 2 codes, 13 tests, 10 journeys. | Named crash windows. Cognee's run status no longer reflects outcome. |
| 9 | Retrieval and public search | None beyond ledger reads. The `IDENTITY` enum member. | 906 lines (8.1%), 4 codes, 53 tests, 9 journeys. Conformance check 641 lines plus a 543-line fixture. Registration code 102 lines. | The version pin is the cost that compounds with upgrades. |
| 10 | LLM-driven Describe | A producer record (method, implementation, version, configuration). A context policy. Candidate providers. | Not built. Estimate only. The reference implementation's rule-based conformance describer is 543 lines for one document. | Everything above was built against captured describers, so the register understates Describe by an unknown amount. |

The three costliest functions by lines are area 5, ownership and forget, at 3,114 lines (28.0%), area 2, valid writes and provenance, at 1,831 (16.5%), and area 7, dependencies and citations, at 1,654 (14.9%). Area 4, text-edit continuity, is a close fourth at 1,516 (13.6%).

### 5.3 Measure limits

Labels are one person's judgment from docstrings and callers. Churn reflects build order (maintenance was built before Describe and real retrieval). Describe is unbuilt, so the register says nothing about the cost of the step that produces every description. Tests and journeys are counted by file name, so a file that covers two areas is counted once. The oracle and mutant counts prove that the checks can fail, not that the rules are right beyond small worlds (two to four sources, depth 5). No scaling measurement exists for any of it. Contributions per edge, traversal cost and plan size were never measured.

Three figures for "text" look inconsistent and are three different cuts. 475 lines is the census label "native rebuild for a new text". 636 lines is the module sum behind section 6 rank 4, which adds `native_chunks.py` and the text-writing parts of `registered.py` to that label. 1,516 lines is area 4, continuity across an edit, which is the admission rule set and has nothing to do with the rebuild.

Four more pairs differ between the 5.1 labels and the 5.2 areas, for the same reason. The census labels lines, and an area counts whole modules.

- Area 1's 505 lines are the 427 publish-labelled lines of `publish.py` plus 78 lines attributed to resolve by judgment, which the census does not separate. The 5.1 label "Publish one revision's overlay" is 904 because it also holds `entry.py` 329, `native_chunks.py` 70, `native.py` 41 and small parts of three other modules, which the areas count under 8 and 7.
- Area 4's 1,516 lines are 274 more than the 5.1 label "revision continuity" at 1,242. The census assigns 134 lines of `admission.py`, 47 of `replace.py` and 68 of `revisions.py` to other labels, 249 lines. The remaining 25 are not reconciled.
- The forget-related cost has three figures. The forget family of modules is 2,907 lines. Area 5 is 3,114, which adds `withdraw.py` 131 and the re-add paths. Section 6 rank 1 attributes about 2,830 of those to Data delete, leaving out withdraw. Rank 1 and area 5 both count 102 tests, because tests are counted by file and the forget files cover withdraw too.
- The cascade is about 1,462 lines by attribution. Its two modules, `erasure.py` 749 and `erasure_rules.py` 654, are 1,403 by census. The rest is the cascade's calls in `forget.py` and `publish.py`, attributed by judgment.

The area rows of 5.2 sum to 12,182 lines, above the 11,121 core, because area 8 includes the 734 lines of command line and environment that core excludes and because about 330 lines sit in two areas. The refusal codes by area sum to 140 against 109 distinct codes, because 31 codes are used in two areas.

### 5.4 Review-found bug classes as a complexity signal

Each class is a place where the design had more states than its author's model. All were found by independent review of the reference implementation over one week.

| Class | Where | Rounds |
|---|---|---|
| A re-add wrote a removed UUID again | forget, re-add, withdraw | 3 consecutive rounds, fixed by the append-only table |
| A patched comparison instead of a stated invariant | re-confirm attestation; erasure cascade shapes | 3 bypass shapes; 4 cascade shapes including a diamond |
| A second copy of a removal routine with different side effects | review drop versus erasure | 2 |
| A failed attempt's partial writes not removed by erasure | erasure retry | 1 high severity, reproduced |
| A looser side path bypassing strict admission | unchanged-text correction | 1, path deleted |
| A guard left behind after the hazard it guarded was removed | rollback exemption hid an outside delete | 1 |
| Endpoint ownership missed on a reused endpoint | the fact writer, at first publication | 1 |
| Stale or unfinished state read as current | acknowledge guards in review; the seed fallback in retrieval | several |

Six of eight classes are in change response. The endpoint ownership bug is in first publication. The seed fallback bug is in retrieval.

### 5.5 Verification cost

The reference implementation's proof apparatus is a cost of its own and it grew with every function. Appendix A says who ran each measurement and when.

| Layer | Size and time |
|---|---|
| Unit tests | 143 at the first checkpoint, 707 at the last measured one |
| Integration tests against real stores | 29 tests in 605 s at the first checkpoint. 120 tests in about 46 min serial, 546 s on 8 workers, at the last. 96% of the time is CLI subprocesses, 38% of each is `import cognee`. |
| Verify journeys through the CLI | 20 blocks and 500 assertions at the first checkpoint. 103 blocks, 141 runs, 2,032 PASS rows at the last. |
| Ledger check | depth 5, 9,205 nodes, about 15 s with forget in the model (6.7 s before forget was added, section 7.2). Depth 6 about 95 s. 53 mutants. |
| Occurrence check | 540,045 worlds plus 27,102 corruptions, 95 to 100 s. 31 mutants. |
| Chain check | 2,224,128 withholding worlds, about 200 s, its own CI job. Cascade half 34,752 worlds, 258 to 343 s. |
| Conformance check | 641 lines against a committed baseline, local only. |
| Two real-embedding journey runs | 22 PASS and 16 PASS with 2048-dimension API embeddings. |

Each checker has seeded mutants because a review once found that a break failed only at depth 7 while depth 5 passed. The lesson the reference implementation records is that a guard that exists only because two functions coexist needs an enumerating check to be trusted, and that check is itself a maintenance item.

## 6. Cognee functions ranked by the cost of coexisting with them

Rank is by reference-implementation lines that exist because the Cognee function exists or behaves as it does, plus the tests and journeys those lines carry. Attribution is a judgment.

| Rank | Cognee function or behaviour | Lab lines because of it | Tests | Journeys | Can a minimal design avoid it |
|---|---|---|---|---|---|
| 1 | Data delete (`cognee.forget(data_id)`) and what is built on it: forget, cascade, tombstone, re-add, removed UUIDs, dataset forget (CB6, CB7) | About 2,830 core (25.4%), plus 1,616 proof | 102 | 23 | Mostly. See section 9.6. Keep a forget that removes one source's overlay and ledger row. Drop dependents, cascade, tombstone content rules, dataset forget. |
| 2 | Deletes made outside the lab: native forget, prune, incremental update, graph-API node delete (CB6, CB7, CB10, CB16, CB17) | About 490 core, 690 with call sites | 43 | 7 | Mostly. Three existence checks at read time, and a forget that accepts a gone source. |
| 3 | Ownership keys and the delete planner (`delete_by_source_ref`, `attach_node_source_refs`) | About 500 | shared | 3 | Partly. Ownership is the cheapest way to make deletes clean up the overlay. The proposal uses it as its only removal mechanism. Contributions and retirement snapshots go. |
| 4 | Text rebuild (no in-place edit; `forget(memory_only)`, `ingest_data`, re-chunk) (CB10, CB12) | 636 by module sum (the census label gives 475, section 5.3) | 13 | 6 | Yes, if an edit is a native update plus a republish. |
| 5 | Add and ingestion with pinned Data IDs, and the processed mark so plain cognify skips project files (CB11, CB18) | About 515 | 21 | 10 | Partly. The proposal registers one small Data item per revision and marks it. The per-revision rewrite of a full description goes. |
| 6 | `cognee.search` and the closed `SearchType` enum (CB5) | 102 registration lines of the 261-line `search.py` | 16 | 9 | Yes, with a library function. |
| 7 | Chunkers and `chunk_offsets` (CB12) | About 120 | 6 | 2 | No. Any exact occurrence needs it. |
| 8 | Post-delete sweep and the shared file store (CB7) | 110, counted inside rank 1 | shared | 1 | Partly. Cognee's own forget runs the sweep. The proposal accepts Cognee's gap. |
| 9 | `add_edges` dropping an edge to a missing endpoint (CB13) | About 60 | shared | 2 | No. Check endpoints before writing. |
| 10 | Edge evidence tables | About 100 | shared | 0 | Yes, by writing the evidence range as a property on the fact edge. |
| 11 | Relational engine shared with Cognee and `prune_system(metadata=True)` (CB16) | About 25 | 2 | 2 | Yes, by putting the ledger in its own database or accepting reset. |
| 12 | `cognee.cognify` itself (LLM extraction) | 0 direct | 2 | 2 | Not applicable. The overlay sits beside its output. |

Delete-related rows 1, 2 and 8 together are about 3,320 core lines (29.9% of core) after removing row 8, which the census counts inside row 1. Added without that correction they are 3,430. They carry 145 tests (32%), 30 journeys (29%, one journey shared between rows 1 and 8) and 1,616 proof lines. The largest single driver inside them is the cascade to citing sources (about 1,462 lines), which exists only because forget and citations coexist.

Not in the table because the reference implementation avoided them at zero cost by leaving them off: Improve and Memify (default Improve indexes helper edges into triplet vectors), the answer cache and feedback (would require cache invalidation on every change). Access control was left off too. With it on, Cognee may keep per-dataset stores, which would change where the ledger lives. Nobody checked this. Section 9.13 lists it as an open limit.

## 7. How costs compound

### 7.1 Candidate functions

| Code | Function |
|---|---|
| A | Identity core (groups, mentions, variants, publish, resolve) |
| B | Valid writes and provenance (fingerprints, inputs, recipes) |
| C | Crash-safe publication (ledger with forward recovery) |
| D | Text-edit continuity (identity kept across an edit) |
| E | Forget and erasure |
| F | Deletes made outside the lab |
| G | Cross-source citations with withholding |
| H | Public search (`IDENTITY` search type) |
| I | LLM-driven Describe (planned, not built) |
| J | Pipeline entry points (lab add, cognify, update under `cognify_pipeline`) |

### 7.2 Pairwise matrix

Each cell names what exists only because both functions are present, with its measured size where the reference implementation separates it, otherwise an estimate. "none" means the pair adds nothing beyond the two functions alone. Rows and columns are symmetric. Read the upper triangle. The cells overlap. A line counted in A x D is often also inside D x G or inside the triples of section 7.3, so the cells do not sum to the change-response total. The cells name mechanisms of the reference implementation. A reader who only wants the shape can read section 7.3 instead.

| | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| **A** | Recipes for every Entity, inputs per decision (the schema, about 450 lines) | Pending state excludes a source; eligibility per source in the retriever (about 60 lines) | Explicit revision-scoped UUIDs, group keys, occurrence map (about 1,500 lines, the whole of area 4) | Ownership split, endpoint retention, contributions (about 500 lines) | Endpoint checks before edges, left absent (about 60 lines) | Mention UUIDs unreachable from other sources, a record registry (about 300 lines) | Scope filter over the shared `Entity_name` index (about 100 lines) | Producer record; validation that proposals carry exact UUIDs (estimate, small) | Processed mark, one source per run (about 100 lines) |
| **B** | | Plans keep inputs before destructive writes (small) | Input classification unchanged, moved or changed by digest (about 100 lines) | Impact computed from saved inputs, never the live graph (about 100 lines) | Five-facet native copy comparison (174 lines) | Fingerprint pins, immutable content under a cited key, attestation per producer (about 500 lines) | none | Producer version and configuration recorded per decision (estimate, small) | none |
| **C** | | | Plan holds old and new text and chunk budget; three text boundaries; plan format converters (about 250 lines) | 10 forget fault stages, erasure retry, a `supersedes` link from a removal revision to the forgotten row, tombstone in the same transaction, ledger check slowed from 6.7 s to 15 s (about 350 lines plus 209 proof) | Ledger outlives a native delete, so detection and `native_deleted` refusals exist (about 200 lines) | Withholding rows written in the edit's own attempt; a derived rule that withholds while an edit is unfinished (about 150 lines) | Settled reads (121 lines) | none | Cognee's run status shows completed for a lab failure; the ledger is the only outcome record; no rollback handler (about 100 lines plus documented windows) |
| **D** | | | | Removed UUIDs never reused across re-add and edit; a refusal when a record key returns (about 400 lines) | Edit of a natively deleted source must be refused first (about 40 lines) | Withholding of only the decisions that read what moved; re-confirm rules; the largest review churn (about 1,400 lines, most of area 7) | none | Regrouping becomes unpredictable, so continuity rules must tolerate a describer that groups differently each time (estimate, unknown) | Re-mark after a per-item forget; a hard-kill window (about 50 lines) |
| **E** | | | | | Forget must complete on a source whose native copy is gone; orphan vector sweep; dataset forget repair (about 350 lines) | The cascade in levels, one token, removal producers bound to the tombstone, fences (about 1,462 lines plus 1,616 proof, 34 tests, 13 journeys, 25 commits) | Retrieval re-validates on every query (about 140 lines) | none | Forget inside a pipeline run that passes no rollback (small) |
| **F** | | | | | | Deadlock between two withheld citers of a deleted Entity; per-decision answers; no recreation (about 300 lines) | Search fails a natively deleted source on first read (about 40 lines) | none | Missing chunk means outside delete; an exemption was removed after it hid one (about 30 lines) |
| **G** | | | | | | | Withheld set compared at start and end of a search (about 40 lines) | Producer attestation becomes model-version attestation (estimate, unknown) | Sources must publish in citation order, one per run (about 60 lines) |
| **H** | | | | | | | | none | none |
| **I** | | | | | | | | | The `needs_llm` Task flag and the closed LLM port no longer apply (estimate, small) |

### 7.3 The triples that matter

Three combinations account for about half of the reference implementation's change-response code before overlap is removed (1,462 plus 1,400 plus 409 is 3,271 of 6,485). The rest is spread across the pairs above.

Forget with citations and the ledger (E, G, C). Erasure must remove each citing decision as a new revision of its source, the removal must bind back to the forgotten row, a dependent whose own attempt failed must still converge, and all of this must resume after a crash at any level. This is the cascade, about 1,462 core lines, 10 fault stages, a 34,752-world checker and four review rounds. The forget family is 2,907 lines, so the cascade is about half of it. The other half, `forget.py` 549, `withdraw.py` 131, `dataset_forget.py` 345 and the shared retirement code, is what forget costs with no citations in the system.

Text edits with citations and provenance (D, G, B). An edit must classify each cited input as unchanged, moved or changed by digest, withhold exactly the decisions that read what changed, and let a reviewer re-confirm without reopening every citation. The re-confirm rule took three review rounds to state as an invariant. About 1,400 lines and a 2,224,128-world checker. Continuity alone, `admission.py`, is 702 lines.

Forget with re-add and continuity (E, D, A). A re-added or edited source must never publish a UUID that a removed object used, and the ledger keeps only the current revision, so the history had to be made append-only. About 409 lines, three review rounds, and the user's "never reuse" decision.

The mechanism in all three is the same. This paragraph is reasoning, not measurement. Citations and continuity both make an identifier mean something to a reader outside the source that created it. Once that is true, every removal and every edit must ask who else holds the identifier, and the answer is a traversal whose correctness the reference implementation could only establish by enumeration.

### 7.4 What a language-model Describe adds

Describe is the one candidate function nobody has built, so this is reasoning, not measurement.

On its own, a model Describe costs prompts, a context policy (which paragraphs, headings and corpus candidates the model sees), candidate providers for lexical and vector lookup, validation that turns the model's proposals into exact keys and ranges, and an evaluation against a manifest the model never saw. The reference implementation's rule-based describer for one document is 543 lines, and the reference records that a describer written after reading the answers is not a benchmark.

With the saved description, it adds nothing. The saved description exists because extraction is stochastic (CB3). A model Describe is the case that design was made for. Replay never calls the model.

With text-edit continuity, it adds an unknown amount. Continuity rules decide whether a group continues by comparing old and new occurrences and keys. A rule describer gives the same keys for the same text. A model describer may group the same pronouns differently on each run, so a small edit can look like a regrouping of the whole document, retiring every mention UUID. The reference implementation never ran this combination. It is the strongest reason the proposal drops continuity rather than the citations alone.

With citations, it turns producer attestation into model attestation. A re-confirm by "the same producer" must mean the same model, version and configuration, or the attestation rule has no content. The reference records that producer identity is its key, not its content, as a known looseness.

With forget, crash safety and outside deletes, it adds nothing.

## 8. The design space

Four coherent shapes, from simplest upward. Each names what it supports and what it costs. Costs for shapes 0 to 2 are estimates derived from the measured areas of section 5. Shape 3 is measured.

### Shape 0. Prompt-side normalization, no overlay

Pass a per-document glossary into Cognee's extraction prompt so that aliases are normalized before Entities are named. Use native search. Accept residual fragmentation.

It supports better native identity for documents that define their own abbreviations. It costs a prompt and a glossary loader, under 100 lines (estimate). It loses any identity across documents, any mention resolution, any record of why two nodes are the same, and reproducibility, because CB3 makes every run different. The reference implementation did not test it.

### Shape 1. Derived overlay from a ledger, owned by a per-revision anchor (the proposal)

Describe produces one saved description per source. A ledger row holds it with a revision and a state. Publish registers one small anchor Data item for the revision, writes the overlay under the anchor's ownership with explicit IDs, and then removes the previous revision's anchor, which takes every object only that revision owned. The overlay is a derived index of the ledger's current descriptions and can always be recomputed from them. Forget removes the anchors, removes the document under Erasure, and leaves a tombstone row with its description and hash set to null. An edit is a native update plus a republish. Retrieval is a library function that reads the ledger for eligibility, walks the identity edges that a served anchor owns, and serves Cognee's own facts only from served sources. No citations, no contributions, no plans, no description copy outside the ledger, no enum member, no pipeline Task.

It supports identity groups, mentions with exact occurrences, mention-anchored facts, crash safety by idempotent republish, forget of one source, and detection of outside deletes. It costs about 1,300 to 2,000 lines plus a producer and tests (estimate, section 9.8). It loses identity continuity across edits, cross-source citations, withdraw separate from forget, and `cognee.search` uniformity. It needs a graph that stores provenance (section 3) and reads ownership keys through Ladybug adapter methods pinned to Cognee 1.6.2 (section 9.10).

### Shape 2. Shape 1 plus continuity

Adds the occurrence map and admission so an edit keeps continuing groups, a withdraw state, settled reads, and the `IDENTITY` search type.

It supports edits that keep mention and group UUIDs, withdraw, and uniform search. It costs about 4,000 to 5,000 lines (estimate from measured areas 4 and 9 of section 5.2 and the withdraw parts of area 5) plus the occurrence oracle (2,673 lines measured). It loses citations and the erasure cascade.

### Shape 3. The reference implementation

Everything in shape 2 plus a full description copy as the generated source, per-decision inputs, cross-source citations with withholding and chains, erasure with cascade, removed-UUID history, five-facet outside-delete detection, dataset forget and pipeline entry points. Measured at 16,672 package lines, 7,364 proof lines, 15,738 test lines, 109 refusal codes, 5 tables.

### A variant of shape 1 with no forget at all

Sources are append-only. To remove one, rebuild the store from the remaining sources. This removes even the tombstone. It is viable while the corpus is small enough to rebuild in minutes and no erasure requirement exists. It is not the proposal because the user named erasure as a real intent, and a rebuild-the-world forget cannot say what it erased.

## 9. The proposal

Shape 1. The rest of this section is its specification.

### 9.1 Principles that shape it

The overlay is derived, never authoritative. The ledger's current descriptions are the truth. The graph and vector stores are an index built from them. Every operation is "make the index match the ledger for this source", so every operation is idempotent and a retry after a crash converges.

Every overlay object has an owner of its own, and removal is only ever by owner. The framework never lists what to remove. It registers one small Data item per published revision, the anchor, writes everything under the anchor's ownership key, and removes a revision by removing its anchor through `cognee.forget`. Cognee's own reference counting then deletes what only that revision owned and keeps what another revision or another source also owns. There is no removal plan, no manifest and no diff over descriptions.

No identifier the framework mints means anything outside the source and revision that created it. Mention UUIDs embed the source and the revision. Reusable Entities use Cognee's own name-derived IDs, so a name means the same thing to every source and no source can mint an Entity that another source depends on by UUID. No citations, no continuity across edits. This is what keeps forget and edits local to one source.

### 9.2 Data model

Stores. Cognee's graph store, Cognee's vector store, one project table, and one small Data item per published revision. The table lives in Cognee's configured relational database by default, through its session layer. Put it in a separate database if you need it to survive `prune_system(metadata=True)` (CB16).

The ledger. One table, `identity_publications`.

| Column | Type | Meaning |
|---|---|---|
| dataset | uuid, key | Cognee dataset ID |
| source | uuid, key | Cognee Data ID of the original document |
| revision | int | The revision this row describes. Increases by one per publish of the same source. |
| state | enum | `pending`, `current`, `failed`, `forgotten` |
| description | json or null | The saved description. Null on a forgotten row. |
| source_hash | text or null | Cognee's `raw_content_hash` of the original at Describe time. Null on a forgotten row. |
| updated_at | timestamp | |

That is 7 columns against the 9 of the reference implementation's publications table, and one table against its five with 33 columns. There is no plan column, no attempt token, no writer table, no events table, no withholdings table, no removed-entities table. Four states against five. Nine transitions, the same count as the reference implementation's: none to `pending` (first publish), `pending` to `current` (verified), `pending` to `failed` (caught error), `current` to `pending` (republish at revision plus one), `failed` to `pending` (republish at revision plus one), `forgotten` to `pending` (re-add at revision plus one), and `pending` to `forgotten`, `current` to `forgotten` and `failed` to `forgotten` (forget). There is no `pending` to `pending` transition. Publish on a `pending` row refuses `not_current`. A corrected description for a source whose last publish died goes through Reconcile first, which ends in `current` or `failed`, and then through Publish.

The anchor. For each publish at revision `r` of source `S`, the framework registers a Data item with the pinned ID `uuid5(S, "anchor:r{r}")` in the same dataset (CB18). Its content is one line naming the source and the revision, so that its content hash is unique and its stored file is shared with nothing. It is registered as a named upload, `identity-{S}-r{r}.txt`, so that Cognee does not name it after its hash, and so that one listing of the dataset's Data rows (`get_dataset_data`) finds every anchor by name. At once after registration it is marked processed with `mark_data_processed`, so that a plain `cognee.cognify` skips it (CB11). It is never cognified, so it has no document node and no chunks. Its only purpose is its ownership key, `source_ref:v1:{dataset}:{anchor}`. The ledger does not store the anchor ID because it derives from the row.

The description. One JSON document per source.

| Section | Content |
|---|---|
| `producer` | method (`rules`, `llm`, `manual`), implementation, version, configuration digest |
| `text_hash` | a hash of the extracted document text the ranges address. The framework reads that text the way Cognee's `TextDocument.read` does, by opening the Data row's `raw_data_location` as UTF-8 text (`document_types/TextDocument.py:11-24`). Not the raw bytes. |
| `entities` | every reusable Entity this source needs, by name, with an optional type. Validation stores each name normalised with Cognee's `generate_node_name` (lower case, apostrophes removed, `engine/utils/generate_node_name.py`), which is how cognify stores names. Its ID is `Entity.id_for(name)`, Cognee's own derivation. Publish creates it if it is missing, including an Entity deleted outside the framework (section 9.9), and retains it if it exists. There is no separate "references" list and no recipe beyond the name. |
| `variants` | pairs of entity names with a kind (`abbreviation`, `spelling`, `alias`). Corpus scope only. The kind stays in the description. It is not written to the edge. |
| `mention_groups` | key, occurrences as `[start, end)` code-point ranges, surface text, status (`accepted`, `unresolved`, `ambiguous`), target entity name if accepted, candidate names if ambiguous. UUID `uuid5(S, "mention:r{r}:{key}")`. |
| `facts` | optional. Subject mention key, predicate, object entity name, supporting occurrence range. The subject is always a mention. The object is always a reusable Entity. A value such as a year is an Entity named `2024`, as Cognee's own extraction would make it. |

Occurrence ranges are exact code points in the extracted text. They are bound to `text_hash`. They are mapped to chunks at publish time with Cognee's `chunk_offsets` over the standard chunker (CB12). First-substring matching is not used.

Graph. Three node types and four edge types.

| Object | Type | ID | Owner keys |
|---|---|---|---|
| Reusable Entity | Cognee `Entity` | `Entity.id_for(name)` | Its creating chunks' keys if Cognee made it. Plus the anchor key of every revision that names it. |
| Mention node | A framework DataPoint type `Mention` with `index_fields` empty, so it writes no vector point | `uuid5(S, "mention:r{r}:{key}")` | The anchor key only |
| Sentinel | A framework DataPoint type `IdentityRevision` with properties source and revision, `index_fields` empty | `uuid5(anchor, "sentinel")`, not the anchor ID, because a cognify of the anchor would write a TextDocument at the anchor ID (`tasks/documents/classify_documents.py:169`) and Ladybug merges nodes on ID | The anchor key only |
| `variant_of` | Entity to Entity, no properties the framework reads | | The anchor key of every revision that asserts the pair |
| `resolves_to` | Mention to Entity | | The anchor key only |
| `has_identity_mention` | DocumentChunk to Mention | | The anchor key only |
| fact predicate | Mention to Entity, properties `evidence_start`, `evidence_end`, `chunk_id` | | The anchor key only |

Every write runs with a pipeline context whose Data item is the anchor. The framework builds a `PipelineContext(user, data_item=anchor row, dataset, pipeline_name)` with no run ID, as the reference implementation's `registered.context_for` does in 20 lines, and passes it to `add_data_points(nodes, ctx=...)` outside any pipeline run. `add_data_points` then stamps each node with the anchor's v1 key. An Entity that exists already is not rewritten (CB2). The framework calls `attach_node_source_refs([id], [anchor key])` on it, which adds an owner and touches no property.

Three rules keep the writes off Cognee's properties. `add_data_points` receives only `Mention`, `IdentityRevision` and `Entity` objects, and none of them has a field that holds another DataPoint. A `Mention` that held its Entity or its chunk as a field would make `get_graph_from_model` emit those as nodes too (`add_data_points.py:110-126`), and `add_nodes` would rewrite their property blobs (CB2). Every edge is written as an ID tuple through `graph_engine.add_edges(ensure_default_edge_properties(edges), source_ref_key=anchor key)`, which stamps the key and runs no embedding. The `custom_edges` path of `add_data_points` would embed each distinct relationship name into the `EdgeType_relationship_name` collection as well (`add_data_points.py:348-366`, `index_graph_edges.py`), one embedding call per name. A missing Entity is created with `description=""`, because `Entity.description` is a required string with no default (`engine/models/Entity.py:11`).

A `variant_of` edge is written from the name that sorts first to the name that sorts second, after normalisation. Two sources that assert the same pair then write the same physical edge, which is what gives it two owners (CB19). Readers walk it in both directions.

A mention node carries only the anchor key. The reference implementation also put the chunk's key on each mention node, so that withdrawing identity alone would not delete the node and cascade into the chunk-owned marker. The proposal has no withdraw. Removing a revision is meant to take the mention node and its marker edge together, and ownership by the anchor alone does exactly that.

There is no contribution list on edges. A `variant_of` edge between two Entities that two sources both assert is one edge with two anchor owners (CB19). It has no property that one writer could overwrite for the other, because the kind stays in the description. Scope is corpus-wide for every variant, so there is nothing a last publisher could change. The user permitted last-publisher-wins as a simplification. The proposal removes the thing that could have been won.

A `variant_of` edge or a `resolves_to` edge can never merge onto a Cognee-extracted edge, because Cognee never writes those relationship names. A fact edge can never merge onto a Cognee-extracted edge, because its subject is a mention node, which Cognee never creates. That is why facts are anchored on mentions and why a fact between two reusable Entities is left to Cognee's extraction.

### 9.3 Operations

Describe. Any producer that reads the extracted document text and returns a description. The framework validates it and refuses otherwise. The reference implementation's seeded passes (explicit abbreviation definitions, exact and normalized name matches, initial-letter candidates, pronouns by nearest compatible antecedent) are a reasonable rule producer to start with. A language model producer must return keys, names and ranges, not prose. Keep the hidden benchmark answers out of any producer's inputs.

Publish(source, description). Steps, in this order. Nothing is written before step 1 passes, so a refused republish leaves the serving revision untouched.

1. Validate. Schema. Every range inside the text and matching its surface. No duplicate keys. Every target and object name listed in `entities`. The row is not `pending` (refusal `not_current`). The Data row exists and its `raw_content_hash` equals the hash recorded at Describe time. The extracted text's hash equals `text_hash`. Occurrences map to chunks that tile the text. Then resolve each name in `entities` to one node. The node at `Entity.id_for(name)` is the answer when it exists. When it does not, read the source's chunks' neighbours (`get_edges` per chunk, one query each) for an Entity with that name under another ID. Cognify gives a chunk-scoped ID, `Entity.id_for(name, chunk, ordinal)`, when one chunk's extraction held two nodes with the same name (`modules/graph/utils/expand_with_nodes_and_edges.py:71-106`). A name found only under a chunk-scoped ID, or under more than one ID, is refused `ambiguous_entity`, because the overlay would otherwise create a second node with that name, with none of Cognee's edges on it. A name found nowhere is created at step 4. The check covers this source's chunks only. Refusals `invalid_description`, `not_current`, `source_changed`, `chunk_mapping`, `ambiguous_entity`.
2. Write the ledger row `pending` at revision `r+1` with the description. From this moment retrieval excludes the source until step 5 succeeds. A republish makes its source unavailable for the duration of the publish. The proposal accepts that instead of tracking two served revisions.
3. Register the anchor for `r+1` with its pinned ID if it is missing. Then call `mark_data_processed` whether or not it was missing. The mark is a plain upsert of the row's status (`modules/data/methods/publish_updated_data.py:134-145`), so a retry re-marks an anchor that a crash or a memory-only forget left unmarked.
4. Write under the anchor's context. The sentinel node. Entities that are missing, by name. Retention on Entities that exist. Mention nodes. `variant_of`, `resolves_to`, `has_identity_mention` and fact edges. Check both endpoints of every edge before writing it (CB13). An edge with a missing endpoint is skipped and reported as left absent.
5. Read back every ID written. Flip the row to `current`. On any exception, flip to `failed` with the error in the result.
6. Sweep. List the dataset's Data rows once (`get_dataset_data`). For every row named `identity-{S}-r{k}.txt` with `k` below `r+1`, call `cognee.forget(data_id=anchor, dataset_id=dataset)`. `forget` with `data_id` and no dataset raises (`api/v1/forget/forget.py:158-165`). That removes every object only revision `k` owned, detaches `k` from shared objects, deletes the vector points of removed nodes, and removes the anchor's Data row and file. If the row vanished between the listing and the call, Cognee's not-found branch still runs the graph delete for that ID and returns success (`api/v1/datasets/datasets.py:259-273`). A never-cognified anchor takes the normal branch and removes exactly what its key owns (`datasets.py:282-307`). The one error the sweep handles is a dataset that no longer exists, which `_resolve_dataset_id` raises as `ValueError` and `delete_data` as `UnauthorizedDataAccessError` (`forget.py:467-475`, `datasets.py:234-240`). The dataset's graph and Data rows went with it, so the sweep counts that as done. With access control off, which is the only mode this document covers, no other condition raises those errors.

Reconcile(source). For a `pending`, `failed` or `current` row, run steps 3 to 6 again from the row's description and revision. Every write is an upsert at an explicit ID and the anchor already exists, so the second run converges to the state a first run that never failed would have left. On a `current` row, Reconcile re-marks the anchor, rewrites the same IDs, flips nothing, and finishes a sweep that a crash cut short. That is also the remedy for a `current` row whose sentinel is gone. For a `forgotten` row, Reconcile runs Forget again.

Forget(source, keep_document=false). Flip the row to `forgotten`, set `description` and `source_hash` to null, keep the revision. Then sweep every anchor named `identity-{S}-r*.txt` in the Data listing, as in step 6, with no revision bound. Then, unless `keep_document` is set, call `cognee.forget(data_id=source, dataset_id=dataset)`. A Data row that is already gone takes Cognee's not-found branch and counts as done. A dataset that is gone ends the sweep and the native delete as done. Every step is idempotent. The tombstone row keeps the revision so that a re-add of the same Data ID continues at revision plus one. It keeps no fingerprint of the erased bytes.

Erasure is Forget with `keep_document` false, and the native delete is mandatory in it. Cleanup may set `keep_document` to remove the identity overlay and keep the document in Cognee. In neither case does anything block, because no source depends on another (section 9.6).

Re-add is Publish at the next revision. For a Data item that was forgotten and added again through `cognee.add`, the Data ID is new (CB18), so the re-add is a new source at revision 1 and the tombstone plays no part. The tombstone matters only when the Data ID stays the same, through `cognee.update` or a pinned re-add.

Edit. There is no edit operation. To change a document's text, call `cognee.update(data_id, new_text)`, which keeps the Data ID and rebuilds the chunks (CB18, CB10), then Describe the new text and Publish at revision plus one. Between the update and the publish, Status reports the row as `native_changed` because the hash moved, and retrieval excludes it. The old revision's marker edges went with the old chunks (CB6). Its mention nodes and its other edges wait for the sweep at step 6. Every mention UUID the old revision created is retired. Facts anchored on old mention nodes go with them. The other path, forget the source and `cognee.add` the new text, gives a new Data ID and a new source. Both are correct. The update path keeps the ID that callers outside the framework may hold.

Status(dataset). For each row, report state and revision, then three facets, each one lookup. The original's Data row exists with the row's `source_hash`. The original's document node exists in the graph (its ID is the Data ID). The sentinel node of the row's revision exists. A `current` row that fails any facet is reported `native_changed`, and retrieval treats it as not current. The remedy is Reconcile when only the sentinel is gone, or Forget, or Forget then Publish. Then list the dataset's Data rows named `identity-*` once. An anchor whose source has no row, whose row is `forgotten`, or whose revision differs from its row's revision is reported `unswept`. The remedy is Reconcile of that source. This is how a sweep that a crash cut short is found, because nothing else runs it until the next Publish or Forget of the same source.

Resolve(query, dataset) and Retrieve(query, dataset). A library function, not a search type.

1. Read the ledger. The served set is the `current` rows that pass the three Status facets. The served keys are their anchors' ownership keys, and the served Data IDs are their source IDs.
2. Seed, in this order. The query is normalised with `generate_node_name` first, and so are the names and surfaces it is compared with, because that is how cognify stores names. First, an exact match of the query against the names in the served sources' `entities` lists. If none, an exact match against the served sources' mention surfaces. A match here returns `ambiguous` with no expansion and stops, whatever the mention group's status is. An accepted mention resolves inside its own document. Its surface is not a corpus-wide name, so the framework does not treat it as one (invariant 6). If neither, the top vector hit in `Entity_name` restricted to the IDs of the served sources' entities (CB14).
3. Closure. Follow `variant_of` edges in both directions transitively. Collect mention nodes whose `resolves_to` edge points into the group. Admit an edge or a mention node only if its ownership keys contain a served key. The keys are read in batches with `get_edge_delete_data` and `get_node_delete_data` (section 3), one query per 2,000 objects per expansion step. It keeps a pending, failed, forgotten or natively changed source's objects out of the closure, and it keeps another dataset's objects out (CB14), because the key names the dataset. Never follow a mention edge outward from a mention into a second group.
4. Facts. One hop from every member. Cognee's own edges from the Entities are admitted only when one of their ownership keys names the searched dataset and a served Data ID. Cognify stamps its edges with chunk-scoped keys, `source_ref:v2:{dataset}:{data}:{chunk}`, so the key says which document's chunk wrote the edge, and `parse_source_ref_key` reads it (`provenance/source_refs.py`). Without this filter, an Entity such as `afrl` carries edges from every dataset that mentions it, because Entity IDs are name-derived and the graph is shared (CB14), and it carries edges from unpublished, pending, failed and forgotten documents. The served fact edges from the mention nodes are admitted by anchor key. Return each fact once per physical edge with its evidence range, its chunk, its source document, and the identity binding that admitted it. A fact whose evidence chunk no longer exists is returned with the range and `chunk_missing`. Dedupe only repeated physical edges. A document in the dataset that was never published is not served by Retrieve. Native search serves it.
5. States. `accepted`, `unresolved`, `ambiguous`, `unavailable`. Empty evidence is not a state.

At startup, the framework calls `stores_provenance_in_graph(graph_engine)` (`provenance/markers.py:24`) and refuses `no_graph_provenance` if it returns false. On such a graph the key reads return nothing, and step 3 would admit nothing.

### 9.4 Removal by ownership, and what a crash leaves

Every removal in the proposal is `cognee.forget` of an anchor. Cognee finds the objects by the anchor's keys, deletes those with no other owner together with their vector points, and detaches the key from the rest. The framework never computes which objects to remove and never reads a description to find them. A shared `variant_of` edge survives while any other revision or source owns it. A retained Entity survives while any chunk or anchor owns it. An object only this revision wrote goes.

Failure walk-through. The table takes a process death after each step of Publish and Forget and says what the stores hold and what the retry does. This is the whole crash-safety argument of the proposal. There is no plan, no attempt token and no fault-stage machinery behind it.

| Death after | Ledger | Graph and vector | Retrieval | Retry |
|---|---|---|---|---|
| Publish step 1 (validation) | unchanged | unchanged | serves revision r | Publish again |
| Publish step 2 (row pending) | `pending` at r+1 | revision r's overlay intact under anchor r | excludes the source | Reconcile runs steps 3 to 6 |
| Publish step 3 (anchor registered, perhaps not yet marked) | `pending` | anchor r+1 exists, nothing written under it | excludes the source | Reconcile marks it again and continues. A plain cognify in the window would extract the anchor's one line (CB11) and write a TextDocument at the anchor's ID, which is why the sentinel has an ID of its own. The sweep of the next revision removes whatever that wrote, because it carries the anchor's keys. |
| Publish step 4 (partial write) | `pending` | some r+1 objects present, all under anchor r+1; revision r intact | excludes the source | Reconcile upserts the same IDs. Duplicates are impossible because IDs are explicit. |
| Publish step 5 (verified, flipped) | `current` at r+1 | both revisions' objects present | serves r+1 only, because the closure admits only anchor r+1's objects | Reconcile sweeps anchor r. Status lists anchor r as `unswept` until then. Until then revision r's unshared objects sit unserved in the stores, where a native graph walk can still reach them (limit 6). This matters when the edit removed sensitive text, so run Status after a publish that did not return. |
| Publish step 6, mid-sweep | `current` | some of revision r's objects gone | serves r+1 | Reconcile sweeps again. Removal by anchor is idempotent. |
| Publish, exception at step 4 or 5 | `failed` at r+1 | partial r+1 under anchor r+1; revision r intact | excludes the source | Reconcile retries r+1 under the same anchor. Or Publish a corrected description at r+2, whose sweep removes anchors r and r+1. |
| Forget step 1 (row flipped, description and hash null) | `forgotten` | every revision's overlay intact | excludes the source | Forget again. The anchors are found by name in the Data listing. Nothing needs the description. |
| Forget step 2 (some anchors gone) | `forgotten` | some revisions removed | excludes the source | Forget again. |
| Forget step 3 (native delete of the original) | `forgotten` | Cognee's own delete is non-atomic (CB7). Evidence rows or files may remain. | excludes the source | Call `cognee.forget` again, or run Cognee's own cleanup. This is Cognee's gap, not the framework's. |

Why the order of Forget does not matter. The reference implementation had to save retirement intent before any destructive write, because its removal read a plan. The proposal's removal reads only the source ID, which names the anchors in the Data listing. The description and the hash are nulled first because erasure wants the content and its fingerprint out of the project's records at the first step, and nothing later needs them.

Concurrency. The proposal assumes one writer per dataset at a time, by policy, not by a lock table. A plain `cognee.cognify` of the dataset is also a writer. The policy has no detector. Two concurrent publishes of two sources cannot remove each other's objects, because each removes only its own anchors, but the sweep of one can run while the other attaches retention to a shared Entity, and Ladybug's merge resolves that per statement. Nobody has tested that interleaving. A reservation row is the next step if the rule cannot be kept.

### 9.5 The two description copies

The reference implementation holds each description twice. The ledger row is the authority. A registered Data item holds a byte-identical copy so that it can be the native owner of the overlay. Readers compare the two and refuse `generated_source_changed` on any difference at 10 sites in 4 modules. A plan column holds a third copy during a replace. The user asked whether this earns its complexity.

A design that keeps one copy by writing the overlay under the original document's own context does not work. A write under the original's context stamps the overlay with the original's v1 key, the same key the document node carries. Removing identity by that key would delete the document node, and retrieval could not tell the overlay of a served revision from the overlay of a failed one. The reference implementation registered a generated source because the overlay needs an owner that is not the original.

The proposal separates the two things the generated source did. Being an owner takes a Data item. Holding the description does not. The anchor is a Data item with one line of content and no description. The ledger holds the only copy. That removes the second copy, the per-revision `ingest_data` rewrite of a full description, the hash renaming trap, the stale derived file sweep, and all 10 comparison sites. The plan column is gone because recovery is republish, not replay, so the third copy is gone too.

What the anchor still costs. One `cognee.add` with a pinned ID and one `mark_data_processed` per publish, one Data listing per sweep, about 80 to 120 lines in the framework (estimate). One extra Data row per served source, which appears in dataset listings. A window between registration and the processed mark in which a plain `cognee.cognify` would send one line to the language model (CB11). The reference implementation's crash windows around its mark are the same shape. The proposal keeps the window short by marking at once after registration and by re-marking on every Reconcile.

What is lost. A full description copy inside Cognee's file store, readable by Cognee's own file tools. Nothing in the reference implementation read it for anything but the comparison.

### 9.6 What forget relaxes, and what the reader loses

The reference implementation's forget does nine things. The proposal keeps four.

| Function of forget | Reference | Proposal | What the reader loses |
|---|---|---|---|
| Remove one source's overlay and leave shared objects | yes | yes, by removing the source's anchors | nothing |
| Erase content from the project's own records (tombstone keeps identifiers only) | yes | yes. The row keeps the dataset, the source ID, the revision and the timestamp. The description and the content hash are null. | nothing |
| Work on a source deleted outside the framework | yes | yes. A missing Data row and a missing dataset both count as done (section 9.3). | nothing |
| Refuse while dependents exist (Cleanup) | removed | no, and not needed. No judgment in one source reads another source's judgment. | nothing today. If citations are added later, Cleanup needs a dependents check. |
| Remove or withhold dependents (Erasure not blocked) | yes, cascade in levels with a token | not applicable. Nothing can cite a source. | nothing today. |
| Dry run with a token bound to the impact | yes | no. The impact of a forget is always one source's objects. | A preview. It can be added as a read of the anchors' owned objects. |
| Never reuse a removed UUID | yes, append-only table | yes, by revision in the mention UUID and a kept revision counter. Entities use name-derived IDs, so an Entity "returning" under its ID is the same name, not a new meaning. | nothing |
| Dataset forget with a token covering non-project Data | yes | no. Forget each source, then call `cognee.forget(dataset=...)` yourself. | A single confirmation covering everything in the dataset. |
| Physical erasure | no, logical only, residue listed | no, logical only | the same. Soft deletes in LanceDB (Cognee's default vector store) and SQLite free pages keep bytes until compaction in both designs. |

Cleanup versus Erasure. In the proposal both intents are one operation with one flag, because no source's description can name another source's judgment, so there is nothing to refuse for and nothing to cascade into. This matches the reference implementation's own observation that both intents agree when nothing depends on the source. Erasure always removes the document. Cleanup may keep it. Erasure is not total. What Erasure of source A leaves behind is exactly this.

- Every reusable Entity that another current source also names stays, with its name, its `Entity_name` vector point, and its `description` property as whatever writer last set it. If Cognee extracted the Entity from A's chunks, that property came from A's text, and Cognee's own native forget of A leaves it too when another document's chunks share the Entity (CB6). The overlay adds one case of its own. An Entity that only A's chunks created, and that B's description names, would go with A under Cognee alone. Under the overlay it survives, held by B's anchor, with A's description text and A's name embedding on it. The framework writes `description=""` on an Entity it creates itself, so an Entity the overlay created carries no text of A's.
- Every `variant_of` edge that another current source also asserts stays, under the other source's anchor.
- Logical residue in the stores until compaction.
- The tombstone row. Dataset, source ID, revision and timestamp.
- One telemetry event per `cognee.forget` call, which carries the Data ID and is sent before the delete (`forget.py:92-102`), for each anchor and for the original, unless `TELEMETRY_DISABLED` is set in the environment (`shared/utils.py:400`).
- Cognee's own non-atomic gap (CB7), which a second `cognee.forget` or Cognee's cleanup closes.

Cleanup with `keep_document` leaves more. A's document node, chunks, extracted Entities, edges and vectors stay in Cognee. Retrieve does not serve them, because step 4 admits Cognee's edges only from served sources and A's row is `forgotten`. Native search does serve them.

The day citations are added, forget must grow a dependents check (Cleanup refuses, Erasure cascades), and that is the moment the cost of section 7.3 arrives. That is a design change, not a feature flag.

### 9.7 Invariants the proposal keeps

1. The served overlay for a dataset equals the union of what its served rows' current revisions publish, up to edges left absent because an endpoint was missing. Any operation that stops midway leaves a row not `current` or an unswept anchor, which Status reports, and Reconcile of that source restores the invariant.
2. No UUID the framework mints is ever published with a different meaning. Mention UUIDs embed the source, the revision and the key, and revisions never repeat per source. Entity IDs are Cognee's name-derived IDs and mean their name.
3. Retrieval serves only sources whose row is `current` and whose three facets hold. It admits an overlay object only if a served anchor owns it, and a Cognee-extracted edge only if a served source's chunk in the searched dataset owns it.
4. No identity state lives in a property of a Cognee-created node or edge (CB2, CB19).
5. The only Data items the framework writes are anchors, one per published revision, each marked processed, each holding no description.
6. A mention edge never bridges two groups, and a mention's surface text never seeds a reusable lookup.

### 9.8 Size estimate

Estimate, built bottom-up from named components. Each row names the reference implementation module it was derived from and what was removed or added. Tests, a command line and a producer are separate.

| Component | Estimate | Derived from |
|---|---|---|
| Description model and validation | 250 to 350 lines | `models.py` 363 and `validation.py` 339, minus inputs, producer lists, recipes, citation checks and the occurrence map. Plus the `text_hash` check. |
| Chunk mapping | 50 to 80 | `native_chunks.chunk_text` (about 20 lines) and `validation.map_chunks` (22) |
| Ledger | 100 to 150 | `storage.py` 788 minus plans, attempts, writers, events, tombstone carry and most of its 19 refusal constants |
| Pipeline context and the three DataPoint types | 40 to 70 | `registered.context_for` (20 lines) plus three Pydantic classes with empty `index_fields` |
| Extracted text read for `text_hash` | 10 to 20 | the `TextDocument.read` pattern over `raw_data_location` |
| Anchor (register, mark, derive, list, sweep, missing dataset) | 80 to 120 | `registered.stamp` and `stamped` (22) plus an `add` call, a derivation, one `get_dataset_data` listing and a loop over the anchors it names |
| Publish and reconcile (entity lookup, sentinel, entities, retention, mentions, edges, facts with evidence properties, endpoint checks, read-back) | 380 to 550 | the 427 census-labelled publish lines of `publish.py` minus contributions and edge-kind collision checks, plus the 56-line fact writer of `fixture.py` minus its edge evidence capture and triplet indexing, plus the chunk-neighbour lookup behind `ambiguous_entity` (30 to 50, estimate) |
| Forget and Status | 130 to 200 | `forget.py` 549 reduced to the anchor loop and the native delete. Three facet lookups instead of `native_copy.py` 174. The `unswept` listing. |
| Resolve and retrieve | 300 to 420 | the 320 census-labelled retrieval lines of `retrieve.py` minus withholding and live drift, plus the batched key reads, the native-edge filter by dataset and Data ID, the startup provenance check and the `chunk_missing` case |
| Total | 1,340 to 1,960 lines | Against 11,121 core lines measured |

Call it 1,300 to 2,000 lines. A rule producer of the reference implementation's kind is about 550 lines for one document type (measured, 543). A command line adds whatever it exposes. About 10 refusal codes are enough (`invalid_description`, `source_changed`, `chunk_mapping`, `unknown_target`, `ambiguous_entity`, `not_current`, `native_changed`, `dataset_required`, `anchor_failed`, `no_graph_provenance`), against 109 measured. Left absent, `chunk_missing` and `unswept` are result fields, not refusals. Tests are one unit file per component and one native test per operation against real stores, perhaps 60 to 80 test functions (estimate). The 35 native tests of section 9.12 each start real stores. The reference implementation's first 29 integration tests took 605 s (section 5.5), so expect about 10 minutes per serial run of the native tests (estimate). No bounded exhaustive checker is planned, because there is no admission rule set and the ledger has four states and nine transitions. The failure walk-through of section 9.4 is small enough to test by one injected death per row.

### 9.9 What is dropped, what a user loses, and how each returns

| Dropped | What the user loses | How it returns without redesign | Which minimal choice keeps the door open |
|---|---|---|---|
| Identity continuity across edits | After an edit, every mention UUID and every fact anchored on one is new. Anything outside the framework that held a mention UUID (a notebook, a cache) must refresh. Group membership is re-derived by Describe, so a rule describer gives the same groups and a model describer may not. | Add an admission step between Describe and Publish that takes an occurrence map from old to new groups and lets a continuing group keep its UUID. The description already has group keys and revision-scoped UUIDs, which is exactly what the reference implementation's admission reads. | Keys on groups. Revision in the UUID. A tombstone revision counter. |
| Cross-source citations with withholding | A glossary document cannot be named as the reason a second document resolved an abbreviation, so an edit to the glossary does not withhold anything downstream. | Add `inputs` to each decision with a fingerprint, a withholdings table and a live validation pass in Retrieve. Then forget needs a dependents check (section 9.6). | The producer record and `text_hash` are the first two input kinds. Adding more input kinds is additive to the schema. |
| Contributions on shared edges | Two sources that assert the same variant pair with different kinds or scopes cannot be told apart in the graph. The kinds are in the descriptions. | Add a scope property and a per-source list when scoped variants are needed. | The description keeps the kind per source. Variant scope was the only thing contributions protected. |
| Withdraw separate from forget | Removing a source's identity interpretation while keeping its document is Forget with `keep_document`. That also removes the facts, and Retrieve stops serving the document's native facts because its row is `forgotten`. | Add a `withdrawn` state that removes the anchors and keeps the row. If facts must survive a withdraw, give facts a second owner, the chunk's key, as the reference implementation did. | The anchor is the only owner of identity objects. |
| Crash plans and fault stages | During a publish, the previous revision is unserved until the new one is current. | Add a second revision column if a source must stay served while it is republished. | The old anchor stays until the sweep, so the old overlay is intact throughout. |
| A full description copy as the generated source | See section 9.5. | Write the description into the anchor's content when a copy inside Cognee's file store is wanted. | The anchor is a Data item already. |
| `IDENTITY` search type | Callers call a function, not `cognee.search`. | Register the retriever with the enum extension when uniform entry matters more than the version pin. | Retrieve is already a function with the retriever's signature. |
| Pipeline entry points | `cognee.cognify` on a dataset does not publish identity. The caller calls Publish after it. | Wrap `cognee.cognify` and Publish in one function. Running Publish as a Task inside `cognify_pipeline` is possible but inherits CB9. | Publish takes a source and a description and nothing else. |
| Dataset forget | The caller forgets each source then calls Cognee. | A loop. | Forget is per source and idempotent. |
| Outside-delete defense beyond detection | A graph-API delete of a referenced Entity takes its `resolves_to` and `variant_of` edges with it, because Ladybug's `delete_node` and `delete_nodes` are `DETACH DELETE` (`ladybug/adapter.py:1272`, `:1288`). The mention nodes stay with no `resolves_to` edge, so the closure never reaches them. No Status facet changes, so nothing reports the delete. The next Publish or Reconcile of any source that names the Entity recreates it with an empty description. The reference implementation refused to recreate (section 4.6). The proposal recreates, and says so as limit 13. | Add a per-source list of Entity IDs seen at Publish and report a missing one at Status, if an outside delete must stay deleted. | Left absent already exists on Publish. |
| Edge evidence tables | Native modes do not see the chunk behind a framework fact. | Call Cognee's edge evidence capture in the fact writer. | The fact edge already carries the range and the chunk ID. |
| LLM Describe | Nothing is lost that was ever built. | A producer with method `llm`. | The producer record. Keys, names and ranges as the contract. |

### 9.10 Patch, entry points, or public calls plus adapter internals

Public calls plus named adapter internals pinned to Cognee 1.6.2. The framework calls `cognee.add` and `cognee.cognify` on the original as a user would, then calls its own Publish. It calls `cognee.add` for the anchor, `cognee.forget(data_id, dataset_id)` for an anchor it sweeps, and the same call for the original under Erasure. It never patches Cognee, never adds an enum member, never runs a Task under `cognify_pipeline`, and never registers a file that holds content it needs back.

It also calls these internals, none of which is part of `cognee.*`. Writes: `PipelineContext` built by hand, `add_data_points(nodes, ctx=...)`, `graph_engine.add_edges(..., source_ref_key=...)`, `ensure_default_edge_properties`, `attach_node_source_refs`, `mark_data_processed` and `reset_data_pipeline_status`. Reads: `get_dataset_data`, `get_node`, `get_edges`, `get_node_delete_data`, `get_edge_delete_data`, `stores_provenance_in_graph`, `parse_source_ref_key` and `Entity.id_for`. The four provenance reads are `GraphDBInterface` methods that only a provenance-capable adapter implements (section 3). The reference implementation used the same write internals. The round-1 rejection of explicit-ID removal "because it needs internal Cognee APIs" was the wrong reason, since the anchor design needs internals of the same kind. The right reason is that explicit-ID removal would make the framework list what to remove, and it would still need a per-revision owner key for the retrieval filter. The anchor gives both to Cognee's reference counting.

What the internals cost. Each one is a name to check on every Cognee upgrade. The key reads cost one query per 2,000 objects per closure step and one `get_edges` per chunk at Publish. The graph must store provenance, which Cognee decides at the graph's first write, so an existing graph that predates graph provenance cannot host the overlay without a rebuild. The framework refuses `no_graph_provenance` at startup rather than serving an empty closure.

Why not a patch. The reference implementation designed one (a Task-transform hook, estimated at tens of lines plus tests) and dropped it because it must be maintained across Cognee versions and the pinned runtime had to stay as is.

Why not entry points under `cognify_pipeline`. They cost about 600 lines, a processed mark with documented crash windows on the original, one source per run, and the loss of Cognee's run status as an outcome record (CB9, CB11). They bought the ability to run identity under Cognee's pipeline name, which the proposal does not need.

What plain usage costs. A caller who runs `cognee.update`, `cognee.forget`, the default `prune_system` or a memory-only forget directly leaves a ledger row behind. Status catches each one with its three facets. The hash catches an update. The document node catches a native forget of the original and a memory-only forget of it. The sentinel catches the default prune and a memory-only forget of the anchor. Retrieval excludes the row, and Reconcile or Forget cleans it. The one case with no detector at read time is a re-chunking of the original with the same bytes, for example a cognify with a different chunk size. The document node, the hash and the sentinel all hold, the marker edges went with the old chunks, and Retrieve reports each affected fact as `chunk_missing` instead of serving a wrong answer. There is no silent wrong answer in these cases, only a source that drops out or a fact that loses its evidence until someone acts.

After the default prune, the originals need a cognify before any Reconcile can map chunks. Cognee keeps their processed marks across that prune (CB16), so a plain cognify skips them. Call `reset_data_pipeline_status(data_id, dataset_id)` (`publish_updated_data.py:148`) on each original, then a plain `cognee.cognify`. Do not use `cognee.cognify(..., incremental_loading=False)`. `cognify` takes datasets, not Data items (`api/v1/cognify/cognify.py:110-134`), and the processed mark is the only thing that keeps anchors out of extraction (`run_tasks_data_item.py:197-209`), so that call would send every anchor's one line to the language model and write a TextDocument per anchor. The sweep of each anchor removes such a document, since it carries the anchor's keys. That is Cognee's behaviour, and the proposal only names it.

The reference implementation accepted the same policy and then spent about 690 lines detecting five facets. The proposal detects three, because its overlay has no second Data item holding content and no stored file it reads back. The two facets dropped are the generated source's Data row, which has no counterpart, and the stored files, which the framework never reads after publish.

### 9.11 A worked example

One document, three sentences, registered as Data item `D1` in dataset `S`. Keys and names stand in for UUIDs in the listings below.

> The Aurora Fusion Research Laboratory (AFRL) operates Helios-1. The controller regulates the vertical position of the plasma. It was commissioned in 2024.

The text is 154 code points. Cognify creates Entities for `aurora fusion research laboratory`, `afrl`, `helios-1`, `plasma` and perhaps `controller`, each with a name-derived ID (CB1). It does not know that `afrl` is the laboratory, and "It" is nothing.

Describe, with the rule producer, returns this description (abbreviated).

```
producer: {method: rules, implementation: seeded-v1, version: 1}
text_hash: <sha256 of the 154 code points>
entities:
  - {name: "aurora fusion research laboratory"}
  - {name: "afrl"}
  - {name: "controller"}
  - {name: "2024"}
variants:
  - {a: "afrl", b: "aurora fusion research laboratory", kind: abbreviation}
mention_groups:
  - {key: g1, occurrences: [[64, 78]], surface: "The controller", status: accepted, target: "controller"}
  - {key: g2, occurrences: [[126, 128]], surface: "It", status: accepted, target: "controller"}
facts:
  - {subject: g2, predicate: commissioned_in, object: "2024", range: [126, 154]}
```

The ranges were computed with Python over the quoted text. `text[64:78]` is `The controller`, `text[126:128]` is `It`, and `text[126:154]` is the third sentence. The entity names are already in `generate_node_name` form, lower case. The explicit-abbreviation rule produced the variant from the parenthesis. The pronoun rule bound "It" to the nearest compatible antecedent, the controller. Whether that is right is Describe's quality, which the framework records but does not judge. If cognify did not create a `controller` or a `2024` Entity, Publish creates it at `Entity.id_for(name)`, which is the ID cognify uses unless one chunk extracted two nodes of that name. Step 1 checks the chunk's neighbours for that case and would refuse `ambiguous_entity`.

Publish registers anchor `A1` for revision 1, marks it processed, and writes under `A1`'s context. The sentinel node with ID `uuid5(A1, "sentinel")`. Any missing Entity by name, with an empty description. `A1`'s key attached to the four named Entities. Two mention nodes `uuid5(D1, "mention:r1:g1")` and `uuid5(D1, "mention:r1:g2")`. One `variant_of` edge between `afrl` and the laboratory. Two `resolves_to` edges into the controller Entity. Two `has_identity_mention` edges from the chunk that covers positions 64 and 126 (one chunk, for a text this short). One `commissioned_in` edge from the `g2` mention node to the `2024` Entity with `evidence_start` 126, `evidence_end` 154 and the chunk ID. The ledger row for `(S, D1)` is `current` at revision 1.

Retrieve("AFRL", S) normalises the query to `afrl`, seeds `afrl` by exact name, closes over the `variant_of` edge to the laboratory, finds no mention into that group, and returns the laboratory's native facts (it operates Helios-1) with chunk evidence. Each of those edges passes step 4 because its chunk-scoped key names dataset `S` and Data ID `D1`. Retrieve("the controller", S) normalises to `the controller`, matches no entity name, matches the surface of `g1`, and returns `ambiguous` with no expansion. That `g1` is `accepted` does not change the answer. The acceptance says what "the controller" means inside `D1`. A query is not inside `D1`, and a document-local surface never seeds a corpus-wide lookup (invariant 6). Retrieve("controller", S) seeds the controller Entity, collects mentions `g1` and `g2` through their served `resolves_to` edges, and returns the regulates fact from Cognee's own extraction and the commissioned fact from the `g2` mention node, each with the binding that admitted it. If a second dataset held a document that also named `afrl`, that document's edges would sit on the same `afrl` node and step 4 would drop them, because their keys name the other dataset.

An edit that changes the second sentence makes the caller run `cognee.update(D1, new text)`, Describe the new text, and Publish at revision 2. Publish registers anchor `A2`, writes `uuid5(D1, "mention:r2:...")` mention nodes and the new edges, flips the row to `current` at revision 2, and sweeps `A1`. The sweep deletes the two revision 1 mention nodes, their `resolves_to` and fact edges, and revision 1's sentinel, detaches `A1` from the four Entities, and deletes the `variant_of` edge if revision 2 did not assert it again. A second document `D2` that also defines AFRL publishes the same `variant_of` pair under its own anchor. The edge then has two owners, and forgetting either source leaves it.

### 9.12 What to verify in the minimal build

Five checks prove the invariants of section 9.7 and nothing else needs proving.

1. Idempotence. For each row of the failure walk-through, inject an exception at the boundary, run the retry, and assert that the stores equal a clean run's stores. One native test per row, 10 tests. Include the death mid-sweep, the death between the flip and the sweep followed by Status and Reconcile, and the republish after a `failed` row.
2. Removal by owner. Two sources sharing an Entity and a `variant_of` edge. Forget each in each order and assert the shared objects survive with the survivor's anchor and the private ones go, including the mention nodes and their marker edges. Then republish one source at a new revision and assert the old revision's private objects go and the shared ones keep both owners. Then forget a source whose dataset was deleted with `cognee.forget(dataset=...)` and assert the tombstone. Seven native tests.
3. Eligibility. A `pending`, a `failed`, a `forgotten` and a `native_changed` source each disappear from Retrieve, and a `current` one appears. Then seed from a served source whose group a pending source also joined, and assert the pending source's edge and mention are not in the closure. Then put a document that names `afrl` in a second dataset and assert that none of its edges appear in a Retrieve of the first dataset. Seven tests.
4. Detection. After `cognee.update`, after a memory-only forget of the original, after a memory-only forget of the anchor, and after the default prune, Status reports `native_changed`. After a cognify of an unmarked anchor, Reconcile re-marks it and the sweep removes the extracted document. Five native tests.
5. Retrieval rules. The worked example's three queries, plus one negative control (a name that contains another name is not a variant), one two-group case (a mention into group A must not pull in group B), and one `ambiguous_entity` refusal for a name that cognify gave a chunk-scoped ID. Six tests.

Keep every identity judgment in these tests as captured input. Test Describe's quality separately, against a manifest its producer never read.

### 9.13 Limits the proposal states up front

Each of these is a choice, with the section that explains it.

1. One writer per dataset at a time, by policy, with no detector. A plain cognify counts as a writer (9.4).
2. A source is unavailable to retrieval while it is being republished (9.3, step 2).
3. Variant scope is corpus-wide, and a variant's kind lives in the description, not the graph (9.2).
4. An edit retires every mention UUID the old revision created (9.3).
5. Erasure is logical. Deleted bytes stay in the stores until compaction. A shared Entity's name and last-written description property stay while another source names it (9.6).
6. Cognee's native search types ignore the ledger. They can serve a pending, failed or forgotten source's chunks, an unswept revision's mention nodes, and a graph walk from an Entity can step onto a mention node named "It" through its `resolves_to` edge. Mention nodes and sentinels write no vector point, so they do not enter `Entity_name`, and overlay edges go through `add_edges` directly, so no relationship name of the overlay enters `EdgeType_relationship_name`. Only Retrieve applies eligibility (9.3, CB4).
7. A delete or update made through Cognee's own API is detected at the next read, not prevented. A re-chunking with the same bytes is not detected by Status and shows as `chunk_missing` on affected facts (9.10).
8. Between a publish and its sweep, the previous revision's unshared objects sit in the stores unserved (9.4).
9. One extra Data item per served source appears in the dataset, named `identity-{source}-r{n}.txt` (9.2).
10. After the default prune, the originals must have their processed marks reset and be cognified again before Reconcile can run (9.10).
11. Access control on was never tested. The ledger's placement and the shared `Entity_name` index may both change under it (section 6).
12. Nothing in one source can depend on a judgment in another source (9.1). This is the limit that keeps all the others cheap.
13. An Entity deleted through the graph API outside the framework is recreated, with an empty description, by the next Publish or Reconcile of any source that names it, and nothing reports the delete in between (9.9). If the delete was made for privacy, remove the name from every description that names it before the next Publish.
14. The overlay needs a graph that stores provenance, and it reads ownership keys through Ladybug adapter methods that are not part of `cognee.*` (section 3, 9.10). Each is a name to check on upgrade.
15. Retrieve serves Cognee's own facts only from published sources. A document in the dataset that was never published, or whose publication is not `current`, contributes no facts to Retrieve (9.3, step 4).
16. A name that cognify gave a chunk-scoped ID in this source's chunks cannot be named in a description (`ambiguous_entity`, 9.3, step 1). The check does not see chunk-scoped nodes in other documents' chunks, so the overlay can create a second node of the same name beside one of those.

## 10. Open questions for the user

1. Ledger placement. In Cognee's relational database (one session layer, lost on `prune_system(metadata=True)`) or a separate database (survives reset, needs its own connection)?
2. Describe for the first build. Rules only, or rules plus a model from the start? The answer decides whether edits re-derive the same groups.
3. Is corpus-wide variant scope acceptable for the first build? Document-scoped variants are what contributions protected.
4. Facts. Should the minimal design carry mention-anchored facts at all, or leave facts to Cognee's extraction and only expand identity at query time? Dropping facts removes the fact writer and the evidence properties.
5. Is a dry-run preview of Forget wanted on day one? It is a read of what the source's anchors own.
6. Do you want the no-forget variant (append-only, rebuild to remove) evaluated as a prototype before committing to shape 1?
7. Must a source stay served while it is republished? That costs a second revision column and a two-key closure filter during the publish.
8. Will access control be on in the target project? If so, the ledger placement and the seed step need a check nobody has run.

## Appendix A. Where the evidence comes from

The reference implementation is the `cognee-science-lab` project, designed from 2026-10-11 and built over 2026-10-14 to 2026-10-29 on Cognee 1.6.2 by an assistant (an agent) under a user's direction. "User" below means the person who commissioned it. "Assistant" means the agent that built it. Line counts were taken on 2026-10-29 at commit `d94a90e`, which has the same `src/`, `tests/` and `support/` trees as its `main` at `cc62b4b`. The Cognee behaviour rows of section 3 marked "read in the source", and every Cognee file and line cited in sections 3 and 9, were read in the installed Cognee 1.6.2 package on 2026-10-29 for this document, in `tasks/storage/add_data_points.py`, `tasks/storage/index_graph_edges.py`, `tasks/storage/index_data_points.py`, `tasks/documents/classify_documents.py`, `infrastructure/databases/provenance/source_refs.py`, `infrastructure/databases/provenance/markers.py`, `infrastructure/databases/unified/unified_store_engine.py`, `infrastructure/databases/unified/provenance_delete_planner.py`, `infrastructure/databases/graph/graph_db_interface.py`, `infrastructure/databases/graph/ladybug/adapter.py`, `api/v1/forget/forget.py`, `api/v1/datasets/datasets.py`, `api/v1/cognify/cognify.py`, `api/v1/prune/prune.py`, `modules/data/deletion/prune_system.py`, `modules/data/methods/publish_updated_data.py`, `modules/data/methods/get_dataset_data.py`, `modules/data/processing/document_types/TextDocument.py`, `modules/graph/utils/expand_with_nodes_and_edges.py`, `modules/ingestion/identify.py`, `tasks/ingestion/data_item.py`, `modules/engine/models/Entity.py`, `modules/engine/utils/generate_node_name.py`, `modules/pipelines/operations/run_tasks_data_item.py` and `shared/utils.py`.

Dated decisions behind section 4, all by the user unless stated.

| Date | Decision |
|---|---|
| 2026-10-11 | Identity is a non-destructive overlay (assistant with the user). A Cognee patch was the preferred entry point at this time. |
| 2026-10-13 | No identity state in Entity properties. Contributions on shared edges, with last-publisher-wins permitted as a simplification. A/B whole-store generations deferred. |
| 2026-10-14 | A mention is one node per local reference group. Explicit UUIDs. The description as one JSON document, registered as a generated source. The ledger. |
| 2026-10-15 | Markers from the original chunk. Occurrences as code-point ranges. Whole-document rebuild on edit. The ownership split. |
| 2026-10-17 | Free variant topology. Per-decision inputs. Forward recovery from a plan. The writer reservation and the recovery events table. Withdraw separate from forget. Improve, Memify, the cache and feedback disabled. |
| 2026-10-21 | Revision in the UUID derivation, after a review. One general admission over an occurrence map. Strict peel-off (to 2026-10-24). Verification by a bounded exhaustive checker, not TLA+. |
| 2026-10-22 | Cleanup separated from Erasure. The two description copies questioned. A forgotten source keeps its last revision. |
| 2026-10-23 | Forget as logical erasure with dependents removed, not withheld. Per-decision withholding. Citations as saved records pinned by fingerprint (to 2026-10-24). |
| 2026-10-24 | Erasure cascades down citation chains under one token. |
| 2026-10-25 | Entry points under `cognify_pipeline`, no patch. Do not wrap Cognee's deletes. An Entity deleted outside the lab stays absent. Dataset delete as the sum of per-source forgets. Retrieval through `cognee.search` with an `IDENTITY` member (to 2026-10-26). |
| 2026-10-26 | A removed Entity UUID is never reused (after the assistant tested the premise). Native search types stay unguarded. The conformance describer reads only the document. |
| 2026-10-27 | Description rewrites ingested as named uploads, after a prototype showed the hash-named rows. |

Dated measurements behind sections 3, 5 and 6. All run on the user's Mac with deterministic loopback embeddings unless stated.

| Date | Measurement | Who ran it |
|---|---|---|
| 2026-10 (second stage of the project) | 98-Entity document with fragmented aliases (CB1). 88, 93 and 98 Entities across three runs (CB3). | assistant |
| 2026-10-11 | 30 Entities rewritten on an overlapping ingest. Resolver 5 of 5 to 0 of 5 (CB2). | assistant |
| 2026-10 (third stage) | Graph completion entered the wrong neighbourhood for "the controller" (CB4). | assistant |
| 2026-10 (baseline run) | One document delete removed 74 nodes and 329 edges, kept 45, left 35 stale, 14 isolated and 43 orphan vectors (CB6). | assistant |
| 2026-10-20 | Env file override wrote API embeddings into the lab store (CB15). 29 integration tests in 605 s. 20 journey blocks and 500 assertions. 143 unit tests. | assistant |
| 2026-10-22 | The commit-before-sweep gap found in the first forget's review (CB7). | a review of the reference implementation |
| 2026-10-23 | Occurrence check, 540,045 worlds, 31 mutants. | assistant |
| 2026-10-24 | Chain check, 2,224,128 worlds, about 200 s. Cascade check, 34,752 worlds. | assistant |
| 2026-10-25 | A `graph.delete_node` left the `Entity_name` point (CB7). Two real-embedding journey runs, 22 PASS and 16 PASS. | assistant; the user ran the real-embedding journeys |
| 2026-10-26 | Rollback removed custom edges with the chunk (CB9). 12 LLM calls to a closed port (CB11). `add_edges` dropped edges to a deleted Entity (CB13). Another dataset's Entity displaced a seed (CB14). Ledger check depth 5, 9,205 nodes, 53 mutants. Recall 10 of 18 manifest facts. 699 unit tests. | assistant |
| 2026-10-27 | 120 integration tests in about 46 min serial and 546 s on 8 workers. 103 journey blocks, 141 runs, 2,032 PASS rows. 707 unit tests. | assistant |
| 2026-10-29 | Every line count, test count, column count and refusal-code count in sections 4 to 6, at `d94a90e`, by a census script that labels lines by module docstring and caller. | assistant, for this document |

Review-found bug classes in section 5.4 come from independent reviews of the reference implementation between 2026-10-21 and 2026-10-27. The 10 comparison sites in 4 modules of section 9.5 were counted on 2026-10-29. The worked example's offsets in section 9.11 were computed with Python on 2026-10-29 for this document.
