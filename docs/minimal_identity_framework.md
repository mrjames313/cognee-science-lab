# A minimal identity resolution framework on Cognee

A proposal for review. This document stands alone. It assumes you know Cognee basics (add, cognify, search, datasets, Data items, DataPoints, the graph, vector and relational stores) and nothing else.

## Technical design summary

The framework keeps identity in a table it owns and applies it when it reads. It adds nothing to Cognee's stores. The optional spelling hint would shape what cognify writes, but the framework writes none of it. Cognee keeps building its own graph from the documents, and the framework reads that graph. The one change it ever makes there is Erasure's delete of a document, through Cognee's own `cognee.forget`.

```
  Cognee Data item (the document) --> Describe --> description (JSON)
                                                        |
                                                        v
                                  Publish: validate, write one row
                                                        |
                                                        v
  +------------------------------------------------------------+
  | Ledger: one row per source                                 |
  | state (current, erasing, forgotten), revision, description |
  +------------------------------------------------------------+
        |                       |                       |
        v                       v                       v
     Retrieve                Status                  Forget
        |                       |                       |
        | reads                 | reads                 | Erasure
        v                       v                       v deletes
  +------------------------------------------------------------+
  | Cognee: Data rows, chunks, Entities, edges, vectors        |
  | built by cognee.add, cognify and update; holds no identity |
  +------------------------------------------------------------+
```

There are two stores. The ledger is a project table and is the truth. Cognee's stores hold the documents and Cognee's own extraction. The operations are these.

| Operation | What it does |
|---|---|
| Describe | Reads one document's text and returns its description. That is its entities by name, variant pairs such as `AFRL` and its full name, mention groups such as "the controller" with exact character ranges and a resolution, and optional facts about a mention. Rules, a model or a person can do it. |
| Publish | Checks the description against the document as it is now, then writes it as the source's next revision in one row write. The write lands only if the row has not changed since it was read. |
| Forget | Cleanup drops the identity and keeps the document. Erasure drops both. Neither ever refuses. |
| Status | Says whether each published row is still backed by its document, by comparing the document's content hash. |
| Resolve and Retrieve | Answer a query with identity applied. Resolve returns the identity group. Retrieve adds the facts. |

How they hang together.

- **Publishing.** A document enters Cognee the ordinary way, through `cognee.add`. `cognee.cognify` extracts it, and Describe reads its stored text. An optional spelling hint can pass the description's names into cognify's prompt, at the cost of running Describe first. Publish then checks that the stored text is the text Describe read and adds the identity to the ledger. A crash leaves either the old revision or the new one.
- **Reading.** Retrieve reads every published row whose document still matches. It finds the entity the query names. It builds that entity's group from the rows' variant pairs, in memory, and returns the group's mentions and their facts from the rows. It then aligns the group's names with the Entities Cognee extracted, reports how each name aligned, and adds Cognee's own facts about the aligned Entities, keeping only those that Cognee extracted from this dataset's published documents. Every Cognee edge records which document wrote it, which is what makes that filter possible. Identity and Cognee's facts meet only here, at query time.
- **Changing a document.** `cognee.update` keeps the document's ID and rebuilds its chunks. Status reports the row as changed until a new description is published, and Retrieve leaves it out meanwhile.
- **Removing a document.** Cleanup is one row write. Erasure marks the row `erasing`, deletes the document through Cognee, finishes Cognee's own clean-up, and marks the row `forgotten`. A crash before that last write leaves an `erasing` row, which Status reports and the next Forget finishes.

One rule holds it together. No source's description can name another source's judgment, and entities are plain names. So every write touches one row, nothing can depend on a source, and Erasure never has anything to refuse for or cascade into.

What it gives up. `cognee.search` and native graph walks see no identity, because identity lives only in the ledger. Cognee's facts reach Retrieve only through alignment, which can miss a name or match it wrongly, and Retrieve reports every miss and every uncertain match. Section 8 gives two ways to put it back. A view built at read time copies the graph, adds identity to the copy and leaves the live graph alone (Shape 1v, unbuilt). Graph-completion search is in scope, so the first build includes that view's in-memory route. A written overlay keeps identity inside Cognee's graph (Shape 2). Continuity across edits and citations between sources are separate losses, which Shapes 3 and 4 add back.

## 1. What this document is

This is a design for a small identity resolution layer on Cognee 1.6.2, for someone building it from scratch in another project. The layer writes identity into one table the project owns and nothing into Cognee. `cognee.search` and native graph walks see no identity. Only the layer's own Retrieve applies it. It is derived from a reference implementation, which is the only evidence this document has. The reference implementation is a laboratory project on Cognee 1.6.2 that built identity resolution over 18 days, from its first design decision on 2026-10-11 to its last measurement on 2026-10-29. Two people appear throughout. The user is the person who commissioned the reference implementation and made its decisions. The assistant is the agent that built it under the user's direction. The reference implementation never ran a language model inside its tests. Every identity judgment in it is a captured fixture input, the corpora are small (two to four documents, six to ten chunks each), and every number below comes from its code, its test runs or its measurements. Appendix A says who measured what, when, and at which commit.

The technical design summary above is the short version of the proposal. Two reading paths cover the rest. A reader who wants only the design reads sections 2, 3, 8, 9 and 10. Section 2 gives the terms, section 3 the Cognee behaviours the design rests on, section 8 the design space, section 9 the proposal and section 10 the questions only the user can answer. A reader who wants the evidence also reads sections 4 to 7, which inventory the decisions the reference implementation made, measure what each cost, rank the Cognee functions by the cost of coexisting with them, and show how costs compound. Section 9 points into them wherever a choice rests on a measurement.

The user who commissioned this marked nothing as must-keep. One recorded requirement is respected throughout. A delete has two intents. Cleanup means "no longer needed" and may refuse while other sources depend on the source. Erasure means "must go" (privacy, legal, licence, a fabricated source) and must never be blocked by dependents. Section 9.5 says what the proposal does with each.

## 2. Terms

Every term below is used in the sense given here and in no other. Terms the proposal introduces for itself (served, seed, closure, spelling hint, alignment, tombstone, anchor, sentinel, sweep) are defined where section 9 first uses them.

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
| Describe | The step that reads a source and produces its identity judgments. It may be rules, a language model, or a person. |
| Description | The structured output of Describe for one source, saved as JSON. |
| Publish | Making a description the one that retrieval serves for its source. In the reference implementation this writes nodes and edges into Cognee's stores. In the proposal it writes one ledger row. |
| Forget | Removing a source's identity from what retrieval serves, and under Erasure removing the source from Cognee too. |
| Overlay | Nodes and edges that identity adds beside Cognee's own graph. The reference implementation has one. The proposal has none. |
| Ledger | A project-owned relational table that records, per source, which description revision is published and in what state. |
| Revision | A counter per source. Each new description for the same source gets the next revision. |
| Ownership | Cognee's mechanism for deciding what a delete removes. Every node and edge carries ownership keys naming the Data items, or chunks, that wrote it. A delete removes an object when its last owner goes. Section 3 explains the keys. |
| Graph provenance | Cognee's mode in which ownership keys live in columns of the graph store. Cognee turns it on for a graph that was empty at its first write. |
| Pipeline context | The object Cognee's Tasks receive. It names the user, the dataset, the Data item and, inside a pipeline run, the run ID. Ownership keys are derived from it. |
| Task | One step of a Cognee pipeline such as cognify. Cognee runs the Tasks of a pipeline in order over each Data item. |
| Fact | A relation between two things with the text that supports it. Cognee extracts facts as edges between Entities. A description may carry facts whose subject is a mention. |
| Cleanup | The delete intent "no longer needed". It may refuse while dependents exist. |
| Erasure | The delete intent "must go". It must never be blocked by dependents. |
| Refusal code | A short string a command returns instead of acting, such as `source_changed`. |
| Ladybug | Cognee's default embedded graph database. Its adapter merges edges on (from, to, relationship name). |
| Native test | In this document, a test that runs against real Cognee stores, as opposed to a unit test with fakes. |

Sections 4 to 7 inventory the reference implementation and use its own vocabulary. File names such as `admission.py` are modules of the reference implementation under `src/cognee_lab/identity/`. The terms below belong to the reference implementation only. The proposal has none of them.

| Term | Meaning in the reference implementation |
|---|---|
| Generated source | Registering each full description as its own Cognee Data item, so the overlay has a native owner. |
| Contribution | A per-source entry on a shared identity edge that records which source asserted it and in what scope. |
| Citation | A judgment in one source naming a judgment in another source as an input. |
| Withholding | Excluding a judgment from retrieval because an input it read has changed or gone, until a reviewer confirms or replaces it. |
| Re-confirm | A reviewer's statement that a withheld judgment still holds. |
| Attestation | The record of who re-confirmed a judgment, keyed by the producer that made it. |
| Cascade | The removal of citing judgments, level by level, when the cited source is erased. |
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
| Settled read | A retrieval that re-reads the ledger at its end and starts again if a writer changed it meanwhile. |
| Marker edge | The `has_identity_mention` edge from a chunk to a mention node. |
| Retirement snapshot | The list of ownership keys a removal will detach, saved in the plan before the removal starts. |
| Fence | A refusal that stops a publish from consuming a source whose removal is half done. |
| Scrub whitelist | The list of ledger columns a forget is allowed to leave on the tombstone. |
| Dry-run token | A value a forget preview returns, which the real forget must present, so that the caller confirms exactly the impact it saw. |
| Removal revision | The new revision a dependent source gets when a cascade removes its citing decisions. |
| Native copy | What Cognee still holds of a source after a delete made outside the framework. |
| Left absent | A publish result entry naming an edge that was not written because its endpoint node did not exist. |
| Helper node, helper edge | A graph object the overlay writes for its own bookkeeping, as opposed to an Entity or a fact. |
| Evidence rows | Cognee's relational rows that tie an edge to the chunk text that supports it. |
| Triplet vectors | Vector points Cognee's optional Improve step writes per edge, so that native search can find edges by text. |
| Improve, Memify | Optional Cognee steps after cognify. Improve writes triplet vectors. Memify runs further enrichment passes. The reference implementation left both off. |
| Census | The script that labels each line of the reference implementation by purpose. Section 5 reports its output. |
| Churn | Lines added plus lines removed over the project's history, by module. |
| Checkpoint | A merge to the reference implementation's `main` branch after a reviewed block of work. |
| Conformance describer | The rule-based producer the reference implementation wrote for one fixture document, used as a regression gate. |
| Manifest | The hidden list of correct answers for a fixture document, which no describer may read. |
| Loopback embeddings | A deterministic local embedding used in tests instead of an embedding API. |
| Journey | A scripted end-to-end run of the command line against real stores, with assertions. |
| Oracle | A brute-force enumeration of small worlds (two to four sources) that checks every rule outcome. |
| Mutant | A seeded bug that a checker must catch, to prove the checker can fail. |
| Fault stage | A named point inside an operation where a failure can be injected to test recovery. |

## 3. Cognee behaviour that drives the design

How ownership works in Cognee 1.6.2. When `add_data_points` writes nodes and edges with a pipeline context that names a dataset and a Data item, each node and edge gets an ownership key. Output a chunk produced gets a chunk-scoped key, `source_ref:v2:{dataset}:{data}:{chunk}`. Output no chunk produced, such as the document node, gets a document-scoped key, `source_ref:v1:{dataset}:{data}`. Keys accumulate. Writing an object that exists adds the new owner and keeps the old ones. `delete_by_source_ref(key)` deletes every object that key alone owns, detaches the key from objects with other owners, and deletes the vector points of the deleted nodes and edges. `cognee.forget(data_id=..., dataset_id=...)` does that for every key of one Data item, v1 and v2, and then removes the Data row and its stored file. The call takes keyword arguments only and raises without a dataset. All of this was read in the Cognee source for this document (Appendix A).

Where the keys live matters to any reader of them. Cognee stores the keys in graph columns only for a graph that was empty at its first `add_data_points` and was marked for graph provenance then (`infrastructure/databases/provenance/markers.py:48-73`). A graph that already held data keeps ownership in relational rows, and the graph reads below return no keys for it. The ordinary reads return no keys either. `get_node` returns `id`, `name`, `type` and `properties`. `get_edges(node_id)` matches edges in either direction and returns a tuple of (the queried node, relationship name, the other node) with no edge properties and no direction (`ladybug/adapter.py:2132-2178`). The keys sit in separate columns (`adapter.py:73-83`). Reading them takes `get_node_delete_data(node_ids)` and `get_edge_delete_data(edges)`, which return the keys of the listed objects in batches of 2,000 per query (`adapter.py:1523-1608`). Both are `GraphDBInterface` methods whose default implementation raises `UnsupportedProvenanceCapability` (`graph_db_interface.py:326-430`). Ladybug implements them. They are not part of `cognee.*`. The proposal reads keys at one place, Retrieve step 4 (section 9.3). Its upgrade, Shape 2, writes them as well (section 9.10).

Each row below is a behaviour of Cognee 1.6.2 that the reference implementation measured, hit, or read in the source for this document. Each one costs something to coexist with. Section 6 ranks them by that cost.

| ID | Behaviour | Measured evidence |
|---|---|---|
| CB1 | An Entity's ID is derived from its normalized name. Different surface strings give different nodes, so aliases and acronyms fragment. | In a 98-Entity document, `afrl` and `aurora fusion research laboratory` were separate nodes, as were three forms of `neutral beam injection`. |
| CB2 | Writing a DataPoint whose ID already exists replaces the whole property blob. Omitted properties vanish. Edges stay. | Ingesting a second overlapping document rewrote properties on 30 existing Entities (description on 30, custom role fields on 9). An identity resolver that read those fields went from 5 of 5 benchmark passes to 0 of 5. |
| CB3 | Extraction is stochastic and chunk-local. The same document gives different Entity counts across runs. | 88, 93 and 98 Entities across three runs of one document. |
| CB4 | Native retrieval gives a custom edge such as `resolves_to` no meaning. Graph completion can walk into the wrong neighbourhood. | For "the controller" a graph-completion answer entered the wrong system's neighbourhood. Raw text retrieval rescued it. |
| CB5 | `SearchType` is a closed enum. A plain string cannot name a search type. | The reference implementation adds an `IDENTITY` member through Python 3.12 enum internals, behind a pin to exactly Cognee 1.6.2 and Python 3.12, with an import-time self-test and rollback. |
| CB6 | Deletion follows ownership keys. Deleting a Data item removes nodes and edges whose last owner it was. Deleting a node detaches all its edges, owned or not. Objects nothing owns are left behind. | Deleting one document removed 74 nodes and 329 edges, kept 45 shared nodes, and left 35 stale helper nodes, 14 isolated nodes and 43 orphan triplet vectors. |
| CB7 | A Data delete is not atomic across stores. Cognee commits the Data row, then sweeps evidence rows and stored files. A graph-API node delete leaves the node's name vector behind. | The commit-before-sweep gap was found in review of the reference implementation's first forget. A `graph.delete_node` left the `Entity_name` point. |
| CB8 | There is no cross-store transaction. Graph, vector, relational and file writes each commit on their own. | Stated by the reference implementation at every checkpoint. It is why the ledger exists. |
| CB9 | Ownership attaches only when a write carries a concrete Data item context. A pipeline run tags only what a Task writes with the pipeline context. Rollback and startup recovery find writes by run ID. | A rollback that removes a chunk removes every edge ending at it, including custom ones. |
| CB10 | `cognify`, `update`, `remember` and the delete paths take no Task list and have no hook. Incremental `update` is refused for any custom model, prompt or chunker, and never runs custom Tasks. A full-rebuild update gives every chunk a new ID. | The first incremental update probe left 93 evidence rows naming retired chunks and 71 new edges absent from the triplet index. |
| CB11 | Plain `cognee.cognify` sends every registered Data item not marked processed to the language model, including a project's own files. A project marks its own file processed with `mark_data_processed`. | 12 LLM calls to a closed port for unmarked project files. On 2026-10-31 a cognify right after one add extracted only the new document's chunks, in every run (Appendix A). |
| CB12 | DocumentChunk stores no document start and end offsets. Chunk IDs derive from content and can recur after an edit while positions move. | The reference implementation maps spans with `chunk_offsets` over the standard non-overlapping chunker. |
| CB13 | `add_edges` silently drops an edge whose endpoint node is missing. | Found when a republish tried to recreate a deleted Entity's edges. |
| CB14 | The `Entity_name` vector collection is shared across datasets. With access control off, the dataset argument does not confine search. | Another dataset's Entity displaced a seed in a retrieval probe. |
| CB15 | Cognee loads an env file at first import with `override=True`. | A fixture meant to use loopback embeddings used 2048-dimension API embeddings and wrote into the lab's own store. Harness cost only. |
| CB16 | `prune_system(metadata=True)` deletes the relational database, including any project table in it. The default call is `prune_system(graph=True, vector=True, metadata=False)`. It wipes the graph and vector stores, keeps every Data row with its hash, and does not reset any item's processed mark, so a later plain `cognify` skips the item. | Read in the source. The reference implementation treats a metadata prune as a reset, not a repair, and built a repair command for the default prune. Observed on 2026-10-31 (Appendix A). After the default prune both Data rows stayed marked processed, the graph was empty, and a plain cognify made no LLM call and left it empty. |
| CB17 | `cognee.forget(data_id=..., dataset_id=..., memory_only=True)` deletes one item's graph and vector objects, keeps its Data row and file, and clears its processed mark. | Read in the source. The reference implementation uses it inside every text edit. Observed on 2026-10-31 (Appendix A). The Data row stayed, its mark was cleared, its document node went and the other document's stayed, and a plain cognify restored the node and the mark. |
| CB18 | `cognee.add` of new content mints a random Data ID. `cognee.update(data_id, data, dataset_id)` keeps the ID and rebuilds the chunks. A caller may pin an ID with `DataItem(data=..., data_id=...)`. | Read in the source. The reference implementation pins every ID it registers. |
| CB19 | Ladybug merges an edge on (from, to, relationship name) and overwrites its properties on every write. Two writers of the same edge keep one edge with the last writer's properties and both owners. | Read in the source. The reference implementation refuses a publish whose edge kind differs from the existing edge's kind. |
| CB20 | `cognify(custom_prompt=...)` replaces the whole extraction system prompt, and cognify sends it with every chunk's extraction call. `cognee.update` takes `custom_prompt` too, and any custom prompt makes the update take its full rebuild. | Read in the source on 2026-10-31 (`infrastructure/llm/extraction/knowledge_graph/extract_content_graph.py:21-22`, `tasks/graph/extract_graph_from_data.py:221-228`, `api/v1/update/update.py:338-375`). Observed on 2026-10-31 (Appendix A). The hint reached every graph-extraction call and no summary call, and a hinted update reported `full_rebuild` with reason `custom_extraction_config`, kept the Data ID and changed the hash. |
| CB21 | `cognify(config={"ontology_config": {"ontology_resolver": ...}})` takes any `BaseOntologyResolver`. After extraction, Cognee renames each node the resolver matches to the matched canonical name, and merges nodes that match one canonical name. `cognee.update` takes no resolver. It reads only an RDF-file ontology from the environment, which matches on each entry's URI name and has no aliases. The RDF resolver matches a name to the URI names with fuzzy `difflib` matching at a 0.8 cutoff. | Read in the source on 2026-10-31 (`modules/ontology/get_default_ontology_resolver.py:20-37`, `:79-101`, `modules/ontology/construct_data_points_and_edges_with_ontology.py:132-213`, `api/v1/update/incremental.py:312-325`, `modules/ontology/rdf_xml/RDFLibOntologyResolver.py:215-261`, `modules/ontology/matching_strategies.py:21-50`, `modules/ontology/base_ontology_resolver.py:10-17`). Never run. |

## 4. Decision inventory

Decisions are grouped by area. Each row gives the choice, the alternatives it beat, the reason, and what it cost and bought. Appendix A dates each decision and says who made it. Line counts are whole-file counts at one commit (Appendix A). Bugs that reviews or tests found in these areas are listed once, in section 5.3.

### 4.1 Representation

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Identity is a non-destructive overlay. Cognee's Entities are never merged or rewritten. | Physical merge. A stricter replacement graph. Cognee's optional destructive consolidation. | Cognee's identity was partly right (3 of 6 cases) and partly wrong. Merging destroys the evidence for why two nodes existed, and some merges would be wrong. | Every equivalence needs its own stored record and edges, and a read path that expands the group at query time. | Reversible judgments. No loss of source evidence. |
| No identity state in Entity properties. No `entity_role` field, no canonical member. | Role fields on a subclass of Entity (the earlier prototype). One support node per assignment. | CB2. The prototype's role fields were overwritten by the next ingest and the resolver stopped working while every edge survived. | Authority must live outside the graph. This forces the saved description and the ledger. | Identity survives later cognify runs. |
| One edge type `resolves_to` with `resolution_kind` in {variant, mention}. Variant is read as bidirectional and transitive. Mention is directed and never bridges two groups. | Two edge types. Treating a historical mention as an alias. | A benchmark query "what does the controller do" must stay ambiguous even though an earlier document resolved "the controller" once. | Closure rules written in a custom retriever (eight rules). | Scoped references that never become global aliases. |
| A mention is one document-local Entity node per local reference group, with several exact ranges, instead of one node per occurrence. | One node per occurrence. Saved-record-only mentions. Larger section groups. | Pronoun volume. No measured saving was claimed. | Split and combination rules, range validation, and the problem that a relation on a group node does not identify one occurrence. | Fewer graph objects (not measured). |
| Mention markers are `has_identity_mention` edges from the original DocumentChunk to the mention node. No singleton or variant markers. | Marker from the generated source's document node. | Removing or rebuilding the generated source must not delete the marker, and an unresolved mention must stay classified as a mention. | Only chunks covering an occurrence own markers. The mention node must carry the chunk's key as well (section 5.3). | Unresolved mentions keep their classification. |
| Explicit UUIDs for every object the overlay creates, derived as `uuid5(generated source Data ID, "kind:r{revision}:{key}")`. | Key-only derivation. Cognee's name-derived IDs. | A key that returned at a later revision re-derived a retired UUID, and the store keeps only the current revision so it could not tell. | Admission must advance exactly one revision per step. | No retired ID returns with a new meaning. |
| Shared identity edges carry a contribution list (assignment, source, scope) and `resolution_kind` once. | Last-publisher-wins, which the user permitted. Parallel edges per source, which Ladybug cannot store (CB19). | Publication order should not change scope. Native Forget does not recompute custom properties. | O(k) checks per visited edge. Withdrawal must remove the payload before native key deletion. Retirement snapshots in every plan. | A shared edge survives when one source goes with the survivor's scope intact. |
| Variant topology is free. No spanning tree, no density limit, cycles allowed. | Pruning redundant paths. | Removing an apparently redundant edge can discard a source's contribution. | Traversal needs visited-state tracking and bounds. | No pruning logic. |

### 4.2 Saved form

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| The description is one JSON document per source with sections inputs, producers, entity constructions, mention groups, mention resolutions, variant assignments. | Readable identity prose that cognify would extract. One source per assignment. | Ordinary LLM parsing is not trusted to reconstruct the graph faithfully. CB3. | A schema in Pydantic (the Python validation library Cognee uses), cross-record checks beyond JSON Schema, and canonical JSON hashing per RFC 8785 (a fixed serialization, so equal documents hash equal). `models.py` 363 lines, `validation.py` 339. | Publication is replayable from saved intent without a model call. |
| The description is registered as a Cognee Data item (the generated source), never chunked, so that it is the native owner of the overlay. | Keep it only in the ledger. | Native Forget and ownership then apply to the overlay. | Two copies of the description, compared at 10 sites in 4 modules. A processed mark so plain cognify skips the file (CB11). Each revision rewrites the Data item through `ingest_data` as a named upload (section 4.9). | The overlay has a native owner distinct from the original. |
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
| Ownership split. Original chunks own markers and facts. The generated source owns resolution contributions and endpoint retention. | Everything under one owner. | Native Forget of the original must take the facts with it, and must not take the shared identity edges. | A coordinated forget, `attach_node_source_refs` retention, a preflight that refuses unsafe endpoint cascades. | Removal of one source cannot kill another's fact. |
| Withdraw is separate from forget. Withdraw retires a source's identity interpretation and keeps the original, facts, markers and evidence. | One delete. | A source can leave the overlay without losing its facts. | `withdraw.py` 131 lines, a `withdrawn` state, 3 fault stages. | Reversible participation. |
| Forget is logical erasure to a tombstone of identifiers. Dependents are removed, not withheld. A forget that changes other sources needs a dry-run token. | The first forget, which refused while dependents existed. Withhold dependents. A restorable forget. | The user's Cleanup versus Erasure separation. Erasure must not be blocked. | Tombstone model, scrub whitelist, removal revisions per dependent, erasure retry for a failed dependent, a fence `retiring_source` that refuses a publish consuming a half-forgotten source, 10 fault stages. Forget family 2,907 lines (26.1% of core), 26 refusal codes, 102 tests. | A source that must go, goes, and its dependents lose exactly what cited it. |
| Erasure cascades down citation chains under one token, in levels. | An interim refusal while a chain exists. | Chains were built. A cited source may need erasing. | `erasure.py` 749 and `erasure_rules.py` 663 lines. Cascade check over 34,752 worlds, 23 of 23 mutants. The invariant "retiring a source never changes what an unfinished cascade does to another source" is checked on every world. 25 commits. | Transitive erasure. |
| A removed Entity UUID is never reused. Append-only table. | Reconstruct "removed by the lab" from tombstones and plans. | Later operations overwrite the plan row, so the reconstruction kept failing (section 5.3). | 1 table, 5 columns, about 409 lines across re-add paths. | No resurrected IDs under stale readers. |
| Dataset delete is the sum of per-source forgets plus a listed remainder. `cognee.forget(dataset=...)` is never called. | Native dataset forget. | Native dataset forget deletes whatever the dataset holds at that moment with no hook. | `dataset_forget.py` 345 lines. | A confirmation token that covers exactly what goes. |

### 4.6 Deletes made outside the lab

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Do not wrap or hook Cognee's deletes. Detect afterwards by comparing five facets of each source's native copy. `reconcile` refuses `native_deleted`. `forget` works on a gone source. | A delete wrapper (returns only if erasure from plain Cognee calls becomes a requirement). | CB10 gives no hook. | `native_copy.py` 174, `outside_deletion.py` 296, call sites, orphan vector sweep. About 690 lines, 43 tests, 7 journeys. | The ledger cannot silently disagree with Cognee. |
| An Entity deleted outside the lab stays absent. A publication never recreates it. A re-add naming it is refused while a saved source still cites it. | Recreate silently. | A reader would see a different Entity under the same UUID. Also CB13. | A deadlock between two withheld citers of the deleted Entity (section 5.3). | No usable dangling references. |

The five facets are the original's Data row, the generated source's Data row, the original's document node, the original's chunks, and the stored files. Each exists because one native operation removes exactly that facet. A native forget takes the Data row and document node. A dataset forget takes both Data rows and the graph. The default prune keeps the Data rows but takes the graph and the stored files. An incremental update keeps the Data row and replaces the chunks. The proposal keeps one facet (section 9.3, Status).

### 4.7 Dependencies and citations

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| A text edit of a consumed document withholds only the dependent decisions that read what changed. Withholding rows are written in the edit's own attempt. Moved spans are found by length and digest. | Block the edit. Withhold the whole dependent. Serve with a stale flag. | Too coarse. | Table of 12 columns. `withholding.py` 473, `review.py` 397. Three bypasses of the re-confirm rule (section 5.3). | An edit never silently serves a stale dependent. |
| A decision may cite another source's decision as a saved record, pinned by a fingerprint. Withholding spreads down the chain at read time with no stored mark. Cycles are refused per source. | Revision pins (would withhold on every upstream revision). A dependency index. | Fingerprints change only when reviewed content changes. | `chains.py` 234, `records.py` 446. Chain check over 2,224,128 worlds and 814,500 key-reuse cases. Its own CI job of about 200 s. Mutual citation between two sources is refused even when no decision cycle exists. | A derived conclusion cannot stay served after its input changed or was erased. |

### 4.8 Entry points and retrieval

| Decision | Alternatives | Why | Cost | Buys |
|---|---|---|---|---|
| Lab `add`, `cognify`, `remember`, `update` run Cognee's standard Tasks under the pipeline name `cognify_pipeline` plus one lab Task. No Cognee patch. | A small Cognee patch adding a Task-transform hook (preferred at first, dropped). Plain Cognee calls plus a separate publish function. | A patch needs maintenance across versions. | `entry.py` 329, `entry_update.py` 201, `native_chunks.py` 70. A processed mark on every managed file. One source per run because Cognee runs a run's items concurrently. Named crash windows between clearing and restoring the mark. | No fork. Publication under Cognee's own pipeline name. |
| Retrieval through `cognee.search` with an added `IDENTITY` enum member. Evidence only, no LLM. | A plain library function. Patching `recall` or `search`. | Uniform entry for callers. | CB5. 102 lines of registration code, a version pin to exactly Cognee 1.6.2 and Python 3.12, limits (schemas built before import, a fresh `cognee search` process) and the area's 4 refusal codes (section 5.1, area 9). | One call surface. |
| Retrieval resolves the query before expanding, seeds only from the searched dataset's served sources, re-reads the ledger at start and end (a settled read), and dedupes only repeated physical edges. | Resolve after recall. Fold identity into the index. | CB4, CB14. | `retrieve.py` 463, `settled.py` 121, `delivery.py` 187. A conformance check against a committed baseline. Recall 10 of 18 manifest facts. The describer had seen the answers, so this is not a benchmark. | Identity closure that native modes cannot do. |
| Native search types stay unguarded. The documentation warns. | A guard. | Undecided. | A measured limit. `GRAPH_COMPLETION` served a withheld fact. `CHUNKS` served a failed publication's text. | Nothing. It is an accepted hole. |
| Improve, Memify, the answer cache and feedback stay disabled. | Default Improve. | Default Improve indexed all 761 edges including 62 helper edges into triplet vectors. | A profile that must stay disabled. | No triplet lifecycle, no cache invalidation. |

### 4.9 Dead ends

Approaches the reference implementation tried and then removed, and that no other section records. Each one is a trap a fresh build can skip.

| Tried | What went wrong | Replaced by |
|---|---|---|
| A custom top-level `graph_model` as the extractor | Replaced Cognee's whole semantic layer. Persisted 3 of 8 recognized abbreviations. Typed output constrains shape, not recall. | Typed overlays beside the default graph |
| A DataPoint as the LLM output type | Persistence fields leaked into structured output and broke it. | Plain Pydantic output converted deterministically |
| Register every source first, then cognify each | A failure left a source registered with no processed mark, exposed to plain cognify. | Add then cognify per source |
| A rollback exemption for a rollback that could no longer happen | Hid a delete made outside the lab. | Removed |
| Authoring the conformance describer from the hidden answers | Would have made the check a tautology. | Describer reads only the document. The check is a regression gate, not a benchmark |
| Ingesting a description rewrite as a plain string | Cognee named the Data row and document node `text_<md5>` on every rewrite. | A named upload object |

## 5. Complexity register

### 5.1 Per function

The package `src/cognee_lab/identity` has 16,672 lines in 60 files. Core, which excludes the command line, environment and scenario fixtures, is 11,121 lines. Proof tooling in `support/` is 7,364 lines. Tests are 452 `def test_` functions in 59 files, 15,738 lines. pytest collects 828 cases from them, 707 unit and 121 integration, because 37 of the files parametrize. There are 103 verify journeys, 109 distinct refusal codes, 5 relational tables with 33 columns and 439 commits. A census script labels each line by module docstring and caller. Change response is 6,485 lines, 58.3% of core. 329 of 452 tests (72.8%) and 79 of 103 journeys exercise a change after publication. 32 journeys are fault or recovery journeys. First publication and retrieval together are 1,810 lines, 16.3% of core, and that pair is not a complete design, because a build with no change response still needs the ledger, the record model and some provenance.

The ten areas below are the one taxonomy this document uses. Sections 6, 7 and 9 cite them by number. Data cost counts stores, tables, columns, node and edge types and copies. Implementation cost counts lines, rules, refusal codes, tests and proof checks. Each number is measured unless marked estimate. The area split is a judgment, and an area counts whole modules where the census labels lines, so the census column names the label where the two coincide and says so where they do not.

| Area | Function | Data cost | Implementation cost (measured) | Census label | Notes |
|---|---|---|---|---|---|
| 1 | Identity core (groups, mentions, variants, publish, resolve) | Graph: mention Entity nodes, `resolves_to` edges with `resolution_kind`, `has_identity_mention` marker edges. Vector: mention names enter `Entity_name`. No table. | 505 lines, 14 codes, 13 tests, 5 journeys. Plus the model, `models.py` 363. | 427 publish-labelled lines of `publish.py` plus 78 attributed to resolve by judgment. The label "publish one revision's overlay" is 904 because it also holds `entry.py` 329, `native_chunks.py` 70 and `native.py` 41, counted here under area 8. | The smallest area. `publish.py` is 755 lines. |
| 2 | Valid writes and provenance (fingerprints, inputs, producers, recipes, chunk mapping) | In the description: inputs with digests, producers, recipes per Entity, exact ranges. No table. | 1,831 lines (16.5%), 16 codes, 12 dedicated tests. `records.py` 446, `validation.py` 339, `native_copy.py` 174. | Provenance checks 907 plus record model 924. | Most of it exists so that dependency and erasure can be computed later. Without those, what remains is the schema, the text fingerprint and chunk mapping, about 400 lines (estimate). |
| 3 | Ledger and crash recovery | 3 tables, 16 columns (publications 9, writers 2, recovery events 5). States 5, transitions 9. The plan column holds a third copy of the previous description during a replace. | 995 lines (8.9%), 19 codes, 21 tests, 32 fault or recovery journeys. Proof 2,326 lines. Depth-5 check 9,205 nodes in about 15 s. 53 mutants. | Ledger and crash recovery 995. | A world with publish and reconcile only needs 3 states and 4 transitions (counted from the transition table). Forget adds one state and the re-add transition. |
| 4 | Text-edit continuity (occurrence map, admission, fresh groups) | Plan carries `occurrence_map`, old and new text, chunk budget. Revision-scoped UUIDs. | 1,516 lines (13.6%), 32 codes, 99 tests, 31 journeys. Proof 2,673 lines of which 1,328 are dependency and erasure worlds. Oracle 540,045 worlds. | Revision continuity 1,242, plus 249 lines of `admission.py`, `replace.py` and `revisions.py` the census labels for other purposes. 25 lines are not reconciled. | The alternative, edit equals forget plus re-add, has no admission rules at all. |
| 5 | Ownership (withdraw, forget, erasure, cascade, re-add, dataset forget, removed UUIDs) | 1 table (removed entities, 5 columns), 1 column (`last_tombstone`), states withdrawn and forgotten, tombstone model 96 lines, contributions on every shared edge, retirement snapshots in plans. | 3,114 lines (28.0%), 31 codes, 102 tests, 26 journeys (23 forget, 3 withdraw). Forget has 10 fault stages. Proof 1,616 lines (cascade). Churn 7,770 lines, the largest category. | Retirement by native ownership 3,114. | Forget family alone 2,907 lines, of which the cascade (`erasure.py` 749 and `erasure_rules.py` 654 by census, about 1,462 with its call sites) is about half. Review-found bugs cluster here (section 5.3). |
| 6 | Deletes made outside the lab | None. Five-facet comparison at read time. | About 690 lines (6.2%), 5 codes, 43 tests, 7 journeys. | No single label. `outside_deletion.py` 296 and `native_copy.py` 174 are split across the dependency, ownership and provenance labels. | Exists because CB10 gives no hook and the design keeps a ledger that can disagree with Cognee. |
| 7 | Dependencies and citations with withholding | 1 table (withholdings, 12 columns). Saved-record inputs with fingerprints. Records registry. | 1,654 lines (14.9%), 17 codes, 83 tests, 17 journeys. Proof 1,264 lines. Chain check 2,224,128 worlds, about 200 s, its own CI job. | Dependency on recorded inputs 1,654. | Review churn was highest here relative to size. |
| 8 | Entry points and native rebuild | A processed mark per managed file. One run per source. | 971 lines including the CLI, 2 codes, 13 tests, 10 journeys. | Native rebuild for a new text 475, plus the entry modules the census labels as publish, plus the 734 command line and environment lines that core excludes. | Named crash windows. Cognee's run status no longer reflects outcome. |
| 9 | Retrieval and the public search | None beyond ledger reads. The `IDENTITY` enum member. | 906 lines (8.1%), 4 codes, 53 tests, 9 journeys. Conformance check 641 lines plus a 543-line fixture. Registration code 102 lines. | Retrieval and the public IDENTITY search 906. | The version pin is the cost that compounds with upgrades. |
| 10 | LLM-driven Describe | A producer record (method, implementation, version, configuration). A context policy. Candidate providers. | Not built. Estimate only. The reference implementation's rule-based conformance describer is 543 lines for one document. | None. | Everything above was built against captured describers, so the register understates Describe by an unknown amount. |

The three costliest areas by lines are area 5 at 3,114 (28.0%), area 2 at 1,831 (16.5%) and area 7 at 1,654 (14.9%). Area 4 is a close fourth at 1,516 (13.6%).

### 5.2 Measure limits

Labels are one person's judgment from docstrings and callers. Churn reflects build order (maintenance was built before Describe and real retrieval). Describe is unbuilt, so the register says nothing about the cost of the step that produces every description. Tests and journeys are counted by file name, so a file that covers two areas is counted once. The oracle and mutant counts prove that the checks can fail, not that the rules are right beyond small worlds (two to four sources, depth 5). No scaling measurement exists for any of it. Contributions per edge, traversal cost and plan size were never measured.

Three figures need a rule to read. Section 4 gives whole-file line counts. The census labels fewer lines for two of those files, `erasure_rules.py` 654 of 663 and `review.py` 368 of 397, and section 5.1 and section 7 use the census figures. Forget has three figures. The forget family of modules is 2,907 lines. Area 5 is 3,114, which adds `withdraw.py` 131 and the re-add paths. Section 6 rank 1 attributes about 2,830 of those to Cognee's Data delete, leaving out withdraw. Rank 1 and area 5 both count 102 tests, because tests are counted by file and the forget files cover withdraw too. The area rows sum to 12,182 lines, above the 11,121 core, because area 8 includes the 734 command line and environment lines and because about 330 lines sit in two areas. The refusal codes by area sum to 140 against 109 distinct codes, because 31 codes are used in two areas.

### 5.3 Bug classes found after the code was written

Each class is a place where the design had more states than its author's model. Independent reviews of the reference implementation over one week found most of them. This section is the one home for these findings. Sections 4 and 7 point here.

| Class | Where | Rounds |
|---|---|---|
| A re-add wrote a removed UUID again | forget, re-add, withdraw | 3 consecutive rounds, fixed by the append-only table |
| A patched comparison instead of a stated invariant | re-confirm attestation; erasure cascade shapes | 3 bypass shapes; 4 cascade shapes including a diamond, each found by a new review round until the invariant was checked on every world |
| A second copy of a removal routine with different side effects | review drop versus erasure | 2 |
| A failed attempt's partial writes not removed by erasure | erasure retry | 1 high severity, reproduced |
| A looser side path bypassing strict admission | unchanged-text correction | 1, path deleted |
| A guard left behind after the hazard it guarded was removed | rollback exemption hid an outside delete | 1 |
| Endpoint or node ownership missed | the fact writer, where a reused endpoint lacked the second source's key and the first source's removal cascaded into the second's fact; the mention node, which needed the chunk's key or a withdraw of the generated source cascaded into the marker | 1 each, found in testing |
| Two withheld citers of a deleted Entity blocked each other's replacement | outside delete with citations | 1 |
| Stale or unfinished state read as current | acknowledge guards in review; the seed fallback in retrieval | several |

Seven of nine classes are in change response. The endpoint ownership bug is in first publication. The seed fallback bug is in retrieval. One more finding shaped the checkers rather than the code. A review found a break that failed only at depth 7 while depth 5 passed, which is why every checker carries seeded mutants.

### 5.4 Verification cost

The reference implementation's proof apparatus is a cost of its own and it grew with every function. Appendix A says who ran each measurement and when.

| Layer | Size and time |
|---|---|
| Unit tests | 143 at the first checkpoint, 707 at the last measured one |
| Integration tests against real stores | 29 tests in 605 s at the first checkpoint. 120 tests in about 46 min serial, 546 s on 8 workers, in the timing run of 2026-10-27. 121 are collected at `d94a90e`. 96% of the time is CLI subprocesses, 38% of each is `import cognee`. |
| Verify journeys through the CLI | 20 blocks and 500 assertions at the first checkpoint. 103 blocks, 141 runs, 2,032 PASS rows at the last. |
| Ledger check | depth 5, 9,205 nodes, about 15 s with forget in the model, 6.7 s before forget was added. Depth 6 about 95 s. 53 mutants. |
| Occurrence check | 540,045 worlds plus 27,102 corruptions, 95 to 100 s. 31 mutants. |
| Chain check | 2,224,128 withholding worlds, about 200 s, its own CI job. Cascade half 34,752 worlds, 258 to 343 s. |
| Conformance check | 641 lines against a committed baseline, local only. |
| Two real-embedding journey runs | 22 PASS and 16 PASS with 2048-dimension API embeddings. |

The lesson the reference implementation records is that a guard that exists only because two functions coexist needs an enumerating check to be trusted, and that check is itself a maintenance item.

## 6. Cognee functions ranked by the cost of coexisting with them

Rank is by reference-implementation lines that exist because the Cognee function exists or behaves as it does, plus the tests and journeys those lines carry. Attribution is a judgment. The last column says what the proposal does about each and where.

| Rank | Cognee function or behaviour | Lab lines because of it | Tests | Journeys | In the proposal |
|---|---|---|---|---|---|
| 1 | Data delete (`cognee.forget(data_id=..., dataset_id=...)`) and what is built on it: forget, cascade, tombstone, re-add, removed UUIDs, dataset forget (CB6, CB7) | About 2,830 core (25.4%), plus 1,616 proof | 102 | 23 | A row flip, one native call and a retry sweep (9.5) |
| 2 | Deletes made outside the lab: native forget, prune, incremental update, graph-API node delete (CB6, CB7, CB10, CB16, CB17) | About 490 core, 690 with call sites | 43 | 7 | One facet at read time (9.3, Status) |
| 3 | Ownership keys and the delete planner (`delete_by_source_ref`, `attach_node_source_refs`) | About 500 | shared | 3 | Read once, in Retrieve step 4. Written only in Shape 2 (9.10) |
| 4 | Text rebuild (no in-place edit; `forget(memory_only)`, `ingest_data`, re-chunk) (CB10, CB12) | 475, the census label for native rebuild | 13 | 6 | `cognee.update` then republish (9.3, Edit) |
| 5 | Add and ingestion with pinned Data IDs, and the processed mark so plain cognify skips project files (CB11, CB18) | About 515 | 21 | 10 | Not used. Shape 2 registers one anchor per revision (9.10) |
| 6 | `cognee.search` and the closed `SearchType` enum (CB5) | 102 registration lines of the 261-line `search.py` | 16 | 9 | A library function (9.3) |
| 7 | Chunkers and `chunk_offsets` (CB12) | About 120 | 6 | 2 | Not used. Occurrences are document ranges (9.2). Shape 2 needs it |
| 8 | Post-delete sweep and the shared file store (CB7) | 110, counted inside rank 1 | shared | 1 | Accepted as Cognee's gap (9.4) |
| 9 | `add_edges` dropping an edge to a missing endpoint (CB13) | About 60 | shared | 2 | Not used. Shape 2 checks endpoints (9.10) |
| 10 | Edge evidence tables | About 100 | shared | 0 | Not used. Evidence is a range in the description (9.2) |
| 11 | Relational engine shared with Cognee and `prune_system(metadata=True)` (CB16) | About 25 | 2 | 2 | Ledger placement is open question 1 |
| 12 | `cognee.cognify` itself (LLM extraction) | 0 direct | 2 | 2 | Not applicable |

Ranks 1 and 2 are the delete-related rows. Together they hold about 3,320 core lines (2,830 plus 490), 29.9% of core. Rank 8's 110 lines are already inside rank 1. The two rows carry 145 tests (32%), 30 journeys (29%, one journey shared between ranks 1 and 8) and 1,616 proof lines. The largest single driver inside them is the cascade to citing sources (about 1,462 lines), which exists only because forget and citations coexist.

The reference implementation left Improve and Memify (default Improve indexes helper edges into triplet vectors), the answer cache and feedback (cache invalidation on every change) off at zero cost, so they are not in the table. Access control was left off too. With it on, Cognee may keep per-dataset stores, which would change where the ledger lives. Nobody checked this. Section 9.13 lists it as an open limit.

## 7. How costs compound

### 7.1 Pairs of areas

Each line names what exists only because both areas of section 5.1 are present, with its measured size where the reference implementation separates it, otherwise an estimate. The lines overlap. A line counted in 1 and 4 is often also inside 4 and 7 or inside the triples of section 7.2, so the sizes do not sum to the change-response total. Pairs of 100 lines or more are listed one per line, largest first.

- Areas 1 and 4. Explicit revision-scoped UUIDs, group keys, the occurrence map. About 1,500 lines, the whole of area 4.
- Areas 5 and 7. The cascade in levels under one token, removal producers bound to the tombstone, fences. About 1,462 lines plus 1,616 proof, 34 tests, 13 journeys, 25 commits.
- Areas 4 and 7. Withholding of only the decisions that read what moved, re-confirm rules. About 1,400 lines, most of area 7.
- Areas 1 and 5. The ownership split, endpoint retention, contributions. About 500 lines.
- Areas 2 and 7. Fingerprint pins, immutable content under a cited key, attestation per producer. About 500 lines.
- Areas 1 and 2. Recipes for every Entity, inputs per decision. About 450 lines, the schema.
- Areas 4 and 5. Removed UUIDs never reused across re-add and edit, a refusal when a record key returns. About 400 lines.
- Areas 3 and 5. Ten forget fault stages, erasure retry, a `supersedes` link from a removal revision to the forgotten row, the tombstone in the same transaction, the ledger check slowed from 6.7 s to 15 s. About 350 lines plus 209 proof.
- Areas 5 and 6. Forget must complete on a source whose native copy is gone, an orphan vector sweep, dataset forget repair. About 350 lines.
- Areas 1 and 7. Mention UUIDs unreachable from other sources, a record registry. About 300 lines.
- Areas 6 and 7. The deadlock between two withheld citers of a deleted Entity, per-decision answers, no recreation. About 300 lines.
- Areas 3 and 4. The plan holds old and new text and the chunk budget, three text boundaries, plan format converters. About 250 lines.
- Areas 3 and 6. The ledger outlives a native delete, so detection and `native_deleted` refusals exist. About 200 lines.
- Areas 2 and 6. The five-facet native copy comparison. 174 lines.
- Areas 3 and 7. Withholding rows written in the edit's own attempt, a rule that withholds while an edit is unfinished. About 150 lines.
- Areas 5 and 9. Retrieval re-validates on every query. About 140 lines.
- Areas 3 and 9. Settled reads. 121 lines.
- Areas 1 and 8. The processed mark, one source per run. About 100 lines.
- Areas 1 and 9. The scope filter over the shared `Entity_name` index. About 100 lines.
- Areas 2 and 4. Input classification as unchanged, moved or changed by digest. About 100 lines.
- Areas 2 and 5. Impact computed from saved inputs, never the live graph. About 100 lines.
- Areas 3 and 8. Cognee's run status shows completed for a lab failure, so the ledger is the only outcome record and there is no rollback handler. About 100 lines plus documented windows.
- Areas 4 and 10, and 7 and 10. Continuity and citations with a model Describe. Unknown. Section 7.3.

Pairs under 100 lines: 1 and 3 (about 60), 1 and 6 (about 60), 7 and 8 (about 60), 4 and 8 (about 50), 4 and 6 (about 40), 6 and 9 (about 40), 7 and 9 (about 40), 6 and 8 (about 30), and the small or unmeasured pairs 1 and 10, 2 and 3, 2 and 10, 5 and 8, 8 and 10. Pairs that add nothing beyond the two areas alone: 2 and 8, 2 and 9, 3 and 10, 4 and 9, 5 and 10, 6 and 10, 8 and 9, 9 and 10.

### 7.2 The triples that matter

Three combinations account for about half of the reference implementation's change-response code before overlap is removed (1,462 plus 1,400 plus 409 is 3,271 of 6,485). The rest is spread across the pairs above.

Forget with citations and the ledger (areas 5, 7 and 3). Erasure must remove each citing decision as a new revision of its source, the removal must bind back to the forgotten row, a dependent whose own attempt failed must still converge, and all of this must resume after a crash at any level. This is the cascade, about 1,462 core lines, 10 fault stages, a 34,752-world checker and four review rounds. The forget family is 2,907 lines, so the cascade is about half of it. The other half, `forget.py` 549, `withdraw.py` 131, `dataset_forget.py` 345 and the shared retirement code, is what forget costs with no citations in the system.

Text edits with citations and provenance (areas 4, 7 and 2). An edit must classify each cited input as unchanged, moved or changed by digest, withhold exactly the decisions that read what changed, and let a reviewer re-confirm without reopening every citation. About 1,400 lines and a 2,224,128-world checker. Continuity alone, `admission.py`, is 702 lines.

Forget with re-add and continuity (areas 5, 4 and 1). A re-added or edited source must never publish a UUID that a removed object used, and the ledger keeps only the current revision, so the history had to be made append-only. About 409 lines and the user's "never reuse" decision.

The mechanism in all three is the same. This paragraph is reasoning, not measurement. Citations and continuity both make an identifier mean something to a reader outside the source that created it. Once that is true, every removal and every edit must ask who else holds the identifier, and the answer is a traversal whose correctness the reference implementation could only establish by enumeration.

### 7.3 What a language-model Describe adds

Describe is the one area nobody has built, so this is reasoning, not measurement.

On its own, a model Describe costs prompts, a context policy (which paragraphs, headings and corpus candidates the model sees), candidate providers for lexical and vector lookup, validation that turns the model's proposals into exact keys and ranges, and an evaluation against a manifest the model never saw. The reference implementation's rule-based describer for one document is 543 lines, and the reference records that a describer written after reading the answers is not a benchmark.

With the saved description, it adds nothing. The saved description exists because extraction is stochastic (CB3). A model Describe is the case that design was made for. Replay never calls the model.

With text-edit continuity, it adds an unknown amount. Continuity rules decide whether a group continues by comparing old and new occurrences and keys. A rule describer gives the same keys for the same text. A model describer may group the same pronouns differently on each run, so a small edit can look like a regrouping of the whole document, retiring every mention UUID. The reference implementation never ran this combination. It is the strongest reason the proposal drops continuity rather than the citations alone.

With citations, it turns producer attestation into model attestation. A re-confirm by "the same producer" must mean the same model, version and configuration, or the attestation rule has no content. The reference records that producer identity is its key, not its content, as a known looseness.

With forget, crash safety and outside deletes, it adds nothing.

## 8. The design space

Six coherent shapes, from simplest upward. Each names what it supports and what it costs. Costs for shapes 0 to 3 are estimates derived from the measured areas of section 5.1. The cost of Shape 1v is a guess. Shape 4 is measured.

### Shape 0. Prompt-side normalization, no identity layer

Pass a per-document glossary into Cognee's extraction prompt so that aliases are normalized before Entities are named. Use native search. Accept residual fragmentation.

It supports better native identity for documents that define their own abbreviations. It costs a prompt and a glossary loader, under 100 lines (estimate). It loses any identity across documents, any mention resolution, any record of why two nodes are the same, and reproducibility, because CB3 makes every run different. The reference implementation did not test it. The proposal reuses its mechanism as a spelling hint, not as identity (section 9.3).

### Shape 1. Ledger-only identity with query-time expansion (the proposal)

Describe produces one saved description per source. A ledger row holds it with a revision and a state. Publish is one relational write. Nothing is written to Cognee's graph, vector or file stores. Retrieve reads the served descriptions, computes the identity closure from their variant pairs and mention groups in memory, and reads Cognee's graph only to align the closure's names with Cognee's Entities and collect Cognee's own facts about them, filtered by ownership key to the served sources. Forget flips the row and, under Erasure, calls Cognee's own delete on the document. An edit is a native update plus a republish.

It supports identity groups, mentions with exact occurrences, resolution states, facts carried in the description and served beside Cognee's, forget and erasure of one source, and detection of a changed or deleted original. It costs about 750 to 1,150 lines plus a producer and tests (estimate, section 9.7). It also costs the graph and chunk reads that alignment makes on every query. The optional spelling hint adds a pinned copy of Cognee's prompt, one cognify per document and a writer policy that only quality rests on. It loses identity in the graph. A native graph walk, and any other reader of Cognee's graph, sees Cognee's fragmented Entities with no `variant_of` edges, no mention nodes and no mention-anchored facts. An Entity that cognify did not extract and a description names, such as a year, exists only in the ledger. It loses continuity across edits and citations, as every shape below Shape 3 does, and `cognee.search` uniformity, which Shape 1v adds back for graph-completion search and Shape 3 adds back with its own search type.

### Shape 1v. Shape 1 plus an identity view built at read time

Added on 2026-10-31. Its claims come from reading the Cognee 1.6.2 source. It has not been built or measured.

The live graph stays as Cognee built it. When a reader needs identity inside the graph, a view builder copies the graph, adds identity from the served descriptions, and runs the reader against the copy. The most recent copy is cached while the ledger version and the graph version both still match it, so repeated reads of unchanged data reuse it, and any change drops it. Nothing in Cognee's stores has to be kept consistent with the ledger, because nothing is written there. Appendix B gives the rules.

It supports identity in Cognee's graph-completion search, through a retriever that hands Cognee the cached copy. With backend access control off, it can support every search type, through a copy of the graph database. It costs a view build after every change to either version (projection, overlay copy and clone took under 15 ms on graphs of 63 to 78 nodes, without the ownership filter, and are unmeasured at scale), memory or disk for the copy, Retrieve's ownership filter on every copied edge, an added search type (the enum change of CB5), a per-query clone of the cached copy, and dropping the cached copy on any change, at once on Erasure. Estimate 400 to 700 lines for the in-memory route, a guess with no bottom-up breakdown. Shape 1 is coupled to Cognee by its reads and its prompt copy (section 9.9). Shape 1v adds a search type, which pins the framework to one Cognee and Python version. Against Shape 2 it loses identity for a reader that walks the live graph.

### Shape 2. Shape 1 plus a derived overlay owned by a per-revision anchor

Publish also registers one small Data item per revision, the anchor, writes mention nodes, `variant_of`, `resolves_to`, marker and fact edges under the anchor's ownership key, and removes the previous revision by `cognee.forget` of its anchor. The ledger stays the truth and the overlay is an index of it. Section 9.10 gives the rules.

It adds identity and facts to the live graph, where native graph walks and other graph readers see them. Shape 1v gives graph-completion search the same without writing anything, so Shape 2 is for a reader that must walk the live graph itself. It costs about 1,400 to 2,100 lines (estimate, section 9.7), a graph that stores provenance, five Cognee write internals pinned to 1.6.2, two more ledger states, a removal step that a crash can cut short, and nine more limits (section 9.10). The framework itself never reads the overlay. Retrieve computes the closure from the ledger in both shapes.

### Shape 3. Shape 2 plus continuity

Adds the occurrence map and admission so an edit keeps continuing groups, a withdraw state, settled reads, and the `IDENTITY` search type.

It supports edits that keep mention and group UUIDs, withdraw, and uniform search. It costs about 4,000 to 5,000 lines (estimate from measured areas 4 and 9 of section 5.1 and the withdraw parts of area 5) plus the occurrence oracle (2,673 lines measured). It loses citations and the erasure cascade.

### Shape 4. The reference implementation

Everything in shape 3 plus a full description copy as the generated source, per-decision inputs, cross-source citations with withholding and chains, erasure with cascade, removed-UUID history, five-facet outside-delete detection, dataset forget and pipeline entry points. Measured in section 5.1.

### A variant of shape 1 with no forget at all

Sources are append-only. To remove one, rebuild the ledger from the remaining sources. It is viable while no erasure requirement exists. An edit still publishes the next revision, so a variant pair that the new text no longer supports leaves the closure at the next read, unless another source still asserts it. It is not the proposal because the user named erasure as a real intent, and Shape 1's forget is already one row flip and one Cognee call.

### Why Shape 1 and not Shape 2

The reference implementation wrote identity into the graph because its retrieval walked the graph. Once the closure is computed from the served descriptions, which is the only way to make "the ledger is the truth" literally true, the framework never reads its own overlay. The overlay is then write-only for the framework. Its only readers are native graph walks, which give custom edges no meaning (CB4), and any other consumer of Cognee's graph the user may have. Everything the overlay needs, the ownership writes, a marker node per revision, the removal of the previous revision, a repair operation, the provenance-write internals and a ten-row crash walk-through, exists to keep that write-only index consistent. The user asked for the less complex side, so the index goes. For the day something outside Retrieve must see identity, Shape 1v builds it at read time and Shape 2 writes it. Open question 4 is that day's question.

## 9. The proposal

Shape 1. The rest of this section is its specification. Identity lives only in the project's ledger. Cognee's search and graph see none of it, and Retrieve is the one reader that applies it. Graph-completion search is in scope for the first build (open question 4), so the first build adds Shape 1v's in-memory route (Appendix B) on top of this specification. Nothing below changes for it.

### 9.1 Principles that shape it

The ledger is the only thing the framework writes. Its current descriptions are the truth, and Retrieve computes identity from them at query time. There is no index to keep consistent, so Publish is one relational transaction, and a retry after a crash is the same call again.

Cognee's stores are read, never written. The framework calls `cognee.add`, `cognee.cognify`, `cognee.update` and `cognee.forget` on the original document as any user would. It writes no node, edge, vector point or Data item of its own. Nothing it does can be undone by a cognify. The optional spelling hint, off by default, would shape what cognify writes, but the framework writes none of it, and nothing Retrieve serves depends on the hint having been used. The one thing it takes away from Cognee is a document under Erasure, through `cognee.forget`.

No identifier the framework mints means anything outside the source and revision that created it. Mention IDs embed the source and the revision. Reusable Entities are named, and the name is the identity, so a name means the same thing to every source and no source can mint an Entity that another source depends on by ID. No citations, no continuity across edits. This is what keeps forget and edits local to one source.

### 9.2 Data model

Stores. Cognee's relational database holds one project table, through Cognee's session layer. Put it in a separate database if you need it to survive `prune_system(metadata=True)` (CB16).

The ledger. One table, `identity_publications`.

| Column | Type | Meaning |
|---|---|---|
| dataset | uuid, key | Cognee dataset ID |
| source | uuid, key | Cognee Data ID of the original document |
| revision | int | The revision this row describes. Increases by one per publish of the same source. |
| state | enum | `current`, `erasing`, `forgotten` |
| description | json or null | The saved description. Null on an `erasing` or `forgotten` row. |
| source_hash | text or null | Cognee's `raw_content_hash` of the original, which Publish step 1 records once the stored text matches `text_hash`. Null on an `erasing` or `forgotten` row. |
| stored_files | json or null | The Data row's `raw_data_location` and `original_data_location`, two paths and no content. Set by Erasure step 1, nulled by Erasure step 3. Null otherwise. |
| updated_at | timestamp | |

That is 8 columns against the reference implementation's 5 tables with 33 columns, 3 states against 5, and 6 transitions against 9. The transitions are none to `current` (first publish), `current` to `current` at revision plus one (republish), `forgotten` to `current` at revision plus one (re-add), `current` to `forgotten` (Cleanup), `current` to `erasing` (Erasure step 1) and `erasing` to `forgotten` (Erasure step 3). Every transition is a compare-and-set on the row's state and revision, and the first publish is an insert on the key. There is no `pending` or `failed` state, because Publish writes nothing before its one row write, and no plan, attempt token, writer table, events table, withholdings table or removed-entities table. A forgotten row is the tombstone. It keeps the dataset, the source ID, the revision counter and the timestamp. Its description and hash are null. An `erasing` row is a tombstone whose native delete has not finished. It keeps the two file paths until step 3 confirms the files gone.

The description. One JSON document per source.

| Section | Content |
|---|---|
| `producer` | method (for example `rules`, `llm`, `decision_model`, `manual`, or a combination), implementation, version, configuration digest |
| `text_hash` | the hash of the extracted document text that Describe read. It binds the ranges to that text. The framework reads that text the way Cognee's `TextDocument.read` does, by opening the Data row's `raw_data_location` as UTF-8 text. Not the raw bytes. |
| `entities` | every reusable Entity this source names, by name, with an optional type. Validation normalises each name with Cognee's `generate_node_name` (lower case, apostrophes removed), which is how cognify stores names. A name is the whole identity. The framework stores no ID for it and creates nothing in the graph. |
| `variants` | pairs of entity names with a kind (`abbreviation`, `spelling`, `alias`). Corpus scope only. |
| `mention_groups` | key, occurrences as `[start, end)` code-point ranges, surface text, status (`accepted`, `unresolved`, `ambiguous`), target entity name if accepted, candidate names if ambiguous. Retrieve reports each group under the ID `uuid5(S, "mention:r{r}:{key}")`, so an ID a caller holds is unique to one source and revision. |
| `facts` | optional. Subject mention key, predicate, object entity name, supporting occurrence range. The subject is always a mention. The object is always a reusable Entity. A value such as a year is an Entity named `2024`, as Cognee's own extraction would name it. |

Occurrence ranges are exact code points in the extracted text and are bound to `text_hash`. They are never mapped to chunks, because nothing is written on a chunk. First-substring matching is not used.

### 9.3 Operations

Describe. Any producer that reads the extracted document text and returns a description. The framework validates it and refuses otherwise. The reference implementation's seeded passes (explicit abbreviation definitions, exact and normalized name matches, initial-letter candidates, pronouns by nearest compatible antecedent) are a reasonable rule producer to start with. The specification leaves the producer open. A rule set, a language model, a smaller and cheaper decision model that classifies candidate pairs and mentions, a person, or a combination of them can each produce the description, and the producer record says which one did. Any producer that is not rules must return keys, names and ranges, not prose. Keep the hidden benchmark answers out of any producer's inputs.

The order. Without the spelling hint, Describe may run before or after cognify. With it, Describe runs before cognify, because the hint comes from the description. Publish runs last, because only then does the Data row hold the text the description addresses. A new document goes through `cognee.add`, then Describe of the stored extracted text, which the Data row's `raw_data_location` holds once the add returns, then `cognee.cognify(datasets=[dataset], custom_prompt=hint)`, or a plain cognify without the hint, then Publish. An edit goes through `cognee.update(data_id, new_text, dataset_id, chunk_level_diff=False)`, then Describe of the stored text, then Publish. With the hint, Describe of the caller's new text comes first and the update also passes `custom_prompt=hint`. Every edit takes Cognee's full rebuild, because the incremental path leaves evidence rows naming retired chunks and new edges missing from the triplet index (CB10), which graph-completion search reads. Only ingestion writes the Data row's text and hash, so Publish step 1 checks the description against the text Cognee stored. If a loader stored different text from what the caller passed, Publish refuses `source_changed`, and the remedy is Describe again from the stored text and Publish.

The spelling hint. The prompt the framework passes to cognify as `custom_prompt`. It is a copy of Cognee's configured graph-extraction prompt, the file that `graph_prompt_path` names in Cognee's LLM configuration (default `generate_graph_prompt.txt`), pinned to the Cognee version, with one section appended. That section lists the description's entity names in the spelling Describe chose, and asks the model to use a listed spelling only when the text in front of it refers to that entity. It lists no variant pairs and no mentions. It gives spellings, never merges. Cognify sends the prompt with every chunk (CB20), so a hint is per document, and that takes one cognify per document. The hint is not deterministic (CB3). Nothing depends on it. The ledger never reads it, alignment never trusts it, and a build can drop it without changing any other rule. It is meant to raise the share of names that align exactly. In the measurement it did in two runs, and in the third it left three names with links only to chunks that do not name them. Section 9.12 gives the measurement, which found it not worth its costs on the test corpus, so it is off by default.

How far the hint reaches. Cognify processes every item of the dataset that is not marked processed (CB11). Under the writer policy (section 9.4), a cognify right after one add sees only that document. It also reaches any other item that is not marked processed, such as an item after a memory-only forget (CB17), every item after `reset_data_pipeline_status` following a prune (CB16), and an item whose earlier cognify failed. A hinted update's full rebuild runs cognify over the whole dataset (CB20), so it reaches the same items. Each such item is extracted with another document's names in its prompt. A cognify without the hint, by another caller or after a prune, is correct too. In every case the cost is quality only. Alignment matches fewer names exactly and falls back more often, and the support check rejects a node the hint planted in a chunk that never names it.

Publish(source, description). Two steps.

1. Validate. The Data row exists. Read the stored extracted text from its `raw_data_location`. The text's hash equals `text_hash`, or Publish refuses `source_changed`. Schema. Every range inside that text and matching its surface. No duplicate keys. Every target and object name listed in `entities`. Then take the Data row's `raw_content_hash` as the row's `source_hash`. Refusals `invalid_description` and `source_changed`.
2. Write the row `current` at revision `r+1` with the description and the hash, as a compare-and-set on the state and the revision read in step 1. A `current` row at `r` becomes `current` at `r+1`. A `forgotten` row at `r` becomes `current` at `r+1`, which is the re-add. No row is an insert on the key `(dataset, source)` at revision 1. If the row moved meanwhile, or the insert finds a row, refuse `revision_conflict`. An `erasing` row refuses `erasure_unfinished`, so a Publish can never write an erased document's description back. Until this write lands, retrieval serves revision `r`. After it, retrieval serves `r+1`. There is no moment at which the source is unavailable.

Forget(source, keep_document=false). Cleanup, with `keep_document` set, is one step. Compare-and-set the row from `current` to `forgotten`, set `description` and `source_hash` to null, keep the revision. Erasure has three steps.

1. Read the Data row's `raw_data_location` and `original_data_location`. Compare-and-set the row from `current` to `erasing`, set `description` and `source_hash` to null, keep the revision, and save the two paths in `stored_files`.
2. Call `cognee.forget(data_id=source, dataset_id=dataset)`. A Data row that is already gone takes Cognee's not-found branch, which removes the graph and vector objects and returns success. A dataset that is gone raises, and counts as done too, because its Data rows went with it.
3. Run the two sweeps that Cognee's own delete runs after its commit (CB7). Call `delete_edge_evidence(dataset, source)` and `remove_data_file_if_unreferenced` on each saved path. Then compare-and-set the row from `erasing` to `forgotten` and null `stored_files`.

A Forget on a `forgotten` row does nothing. A Forget on an `erasing` row runs steps 2 and 3 again, whatever the flag says, because an Erasure that started must finish. Erasure is Forget with `keep_document` false, and the native delete is mandatory in it. Cleanup may set `keep_document` to remove the identity and keep the document in Cognee. Neither blocks, because no source's description can name another source's judgment (section 9.5).

Re-add is Publish at the next revision. For a Data item that was forgotten and added again through `cognee.add`, the Data ID is new (CB18), so the re-add is a new source at revision 1 and the tombstone plays no part. The tombstone matters only when the Data ID stays the same, through `cognee.update` or a pinned re-add.

Edit. There is no edit operation. To change a document's text, follow the edit order above. Call `cognee.update(data_id, new_text, dataset_id, chunk_level_diff=False)`, which keeps the Data ID and rebuilds the chunks (CB18, CB10), then Describe and Publish at revision plus one. Between the update and the publish, Status reports the row as `native_changed` because the hash moved, and retrieval excludes it. Every mention ID the old revision reported is retired, because the revision is in the derivation. The other path, forget the source and `cognee.add` the new text, gives a new Data ID and a new source. Both are correct. The update path keeps the ID that callers outside the framework may hold.

Status(dataset). For each row, report state and revision, then one facet. The original's Data row exists with the row's `source_hash`. A `current` row that fails it is reported `native_changed`, and retrieval treats it as not current. The remedy is Publish after a Describe of the new text, or Forget. An `erasing` row is reported `erasure_unfinished`. The remedy is Forget again. Status also reports whether the original's document node exists in the graph (its ID is the Data ID). That facet does not change eligibility. It says whether Retrieve step 4 will find native facts for the source.

Resolve(query, dataset) and Retrieve(query, dataset). A library function, not a search type. Resolve runs steps 1 to 3. Retrieve runs all five.

1. Read the ledger. The served set is the `current` rows whose facet holds.
2. Seed. The seed is the Entity the closure starts from, chosen in this order. The query is normalised with `generate_node_name` first, and so are the names and surfaces it is compared with. First, an exact match of the query against the names in the served sources' `entities` lists. If none, an exact match against the served sources' mention surfaces. A match here returns `ambiguous` with no expansion and stops, whatever the mention group's status is. An accepted mention resolves inside its own document. Its surface is not a corpus-wide name, so the framework does not treat it as one (invariant 5). If neither, the query is `unresolved`. There is no vector fallback in the first build. In the measurement, the nearest `Entity_name` hit for a described name that was not aligned exactly was a wrong Entity 27 times in 33, for long names as well as abbreviations (Appendix A). A project that needs natural-language entry adds a fallback and measures it on its own queries first.
3. Closure, from the ledger alone. Union the `variants` pairs of every served description into groups. The closure is the seed's group. The closure's mentions are every served mention group whose target is in the closure. Never follow a mention into a second group. A forgotten or natively changed source's pairs are not in the union, because only served descriptions are read. No store is touched.
4. Facts, from two places. From the ledger, every served fact whose subject mention is in the closure, with its range and, while the Data row's `raw_data_location` is readable, the text it addresses. After `prune_data` the file is gone and the fact says `text: unavailable`. From Cognee, `get_edges` on each node that alignment (below) admits for a name in the closure. Drop the edges whose relationship name is `contains`, `is_a`, `is_part_of` or `belongs_to_set`. They are Cognee's structure, from a chunk to an Entity or from an Entity to its type, not facts. Shape 2 adds its own `resolves_to` and `has_identity_mention` to that list. Stop after 200 edges per node and say `native_facts: truncated`, as the reference implementation does. Each remaining tuple is submitted in both orientations to `get_edge_delete_data`, in batches of 2,000, because `get_edges` reports no direction and the key read matches only the stored one. An edge is admitted when one of its keys names the searched dataset and a served Data ID, read with `parse_source_ref_key`. Without this filter an Entity such as `afrl` carries edges from every dataset that mentions it (CB14) and from unpublished and forgotten documents. Return each fact once per physical edge with its source document, the identity binding that admitted it, and how its node aligned. Dedupe only repeated physical edges. A ledger fact and a Cognee edge can describe the same sentence. Both are returned, each with its origin, and neither wins (limit 8). On a graph that does not store provenance, which `stores_provenance_in_graph` reports, step 4 serves the ledger's facts only and says `native_facts: unavailable` in the result.
5. States. `accepted`, `unresolved`, `ambiguous`, `unavailable`. Empty evidence is not a state.

Alignment. The step that finds, for each name in the closure, the Cognee nodes whose facts step 4 may serve.

Why alignment. Describe and cognify both read the document, and they meet at one point, the Entity name. Retrieve reads Cognee's facts from the node whose ID derives from a name (CB1), so a description's name and cognify's name for the same thing must be lined up. Four ways were weighed.

- **Constrain Describe to cognify's names.** Rejected, because it makes cognify, the stochastic extractor (CB3), the authority on names.
- **An ontology resolver (CB21).** Rejected for two reasons. A variant pair becomes a merge inside Cognee's nodes, so publishing or forgetting a pair needs a re-cognify of every document that names either side, and nothing records which source caused a merge. And a corpus-wide resolver cannot resolve a document-local mention. `cognee.update` cannot take the resolver either, so an edit becomes a memory-only forget, a pinned re-add that keeps the ID (CB18) and a cognify with the resolver. It fits only an append-only corpus that is rebuilt to change, and it needs a probe before anything relies on it.
- **Align at read time by vector similarity over `Entity_name`.** Rejected after measurement. For 27 of 33 names that did not align exactly, the nearest hit was a wrong Entity, and the right node ranked as low as 37th, so no distance threshold separated right from wrong (Appendix A).
- **Align at read time by exact and lexical rules (chosen).** Neither extractor constrains the other. Alignment is derived at each read from the ledger and the graph, so a re-cognify needs nothing but the next read, and every outcome is reported. Every cognify spelling the exact rule missed in the measurement was the name with its abbreviation in parentheses, which the lexical rule covers. Another corpus may show other variant patterns. Each would become a further lexical rule, tested before use.

The same reason keeps the optional spelling hint to spellings. A prompt that told the model to write `AFRL` as the laboratory would put a variant pair inside Cognee's nodes, where Forget cannot take it back.

A candidate is a node that the exact pass or a lexical rule names for a closure name. Each closure name ends with one of four outcomes, and Retrieve returns it per name.

- `exact`. An exact candidate passed the support check.
- `lexical`. No exact candidate passed, and a lexical candidate did. Its facts are served with the label and never merged silently.
- `unsupported`. Candidates existed and none passed.
- `unaligned`. There were no candidates.

A chunk-scoped node is one that cognify did not place at `Entity.id_for(name)`. When one chunk's extraction holds two nodes with the same name, cognify gives them IDs from `Entity.id_for(name, chunk_id, ordinal)` instead (`modules/graph/utils/expand_with_nodes_and_edges.py:72-112`).

The passes, for one name.

1. Exact. The candidate is the node at `Entity.id_for(name)`, if it exists.
2. Support check, on each candidate. Alignment reads the candidate's `get_edges`, keeps its `contains` edges and reads their ownership keys with `get_edge_delete_data`. It does this itself, before and apart from step 4, which drops `contains` edges and applies the 200-edge cap to facts. It reads `contains` edges until one supports the candidate, which needs no cap, because it stops at the first support. A `contains` edge supports the candidate when it comes from a chunk of a served source in the searched dataset, and that chunk's text contains, as a whole word and case-folded the way `generate_node_name` does, one of these.
   - Any name in the closure.
   - For a lexical candidate, its own name, and its base and its parenthetical when it has one. A chunk that writes "Magnetic Probe Array (MPA)" holds both parts, though not always the literal string.

   Mention surfaces are not used. They are document-local (invariant 5), and a pronoun such as `It` would pass everywhere. The check rejects a node that extraction linked to a chunk that never names it, which the measurement saw the hint do in every run.
3. Lexical. It runs whenever no exact candidate passes the support check. It looks at the Entities that a `contains` edge reaches from a chunk of a served source whose description lists a name in the closure. It skips every closure member's own exact node, which aligns under that member's name. An Entity is a lexical candidate when its name equals a name in the closure, which is how a chunk-scoped node is found, or when its name, with one trailing parenthetical removed, equals a name in the closure, or when that parenthetical does. So `magnetic probe array (mpa)` is a candidate for both `magnetic probe array` and `mpa`. An Entity whose name, base or parenthetical a description in the ledger lists outside the closure, served or not, is never a candidate. Support-check each candidate, and keep every supported one.

When one physical edge is reached through two alignments, Retrieve reports it once with the stronger label, `exact` over `lexical`. Alignment writes nothing and keeps nothing between queries. Its reads per closure name are one `get_edges` on the exact node and the `contains`-key reads up to the first support. When the lexical pass runs, it adds one `get_edges` on each such source's document node to list its chunks, one `get_edges` per chunk, one `get_node` per chunk checked, and the support reads for each match. Shape 1v builds alignment into its view and caches it with the view (Appendix B).

Evidence for the rules above, all read in the Cognee 1.6.2 source. Publish step 1 reads the Data row's `raw_content_hash` and `raw_data_location` (`modules/data/processing/document_types/TextDocument.py:11-24`), and only ingestion writes them (`tasks/ingestion/ingest_data.py:448-497`) and normalises names with `modules/engine/utils/generate_node_name.py`. Erasure step 2 rests on `cognee.forget` taking keyword arguments only (`api/v1/forget/forget.py:22-30`), the not-found branch that runs `delete_data_nodes_and_edges` and returns success (`api/v1/datasets/datasets.py:259-273`), and the raises for a missing dataset (`forget.py:467-475`, `datasets.py:234-240`). Erasure step 3 copies the tail of `delete_data_entity`, which commits the Data row delete and then calls `delete_edge_evidence` and `remove_data_file_if_unreferenced` on both paths (`infrastructure/databases/relational/sqlalchemy/SqlAlchemyAdapter.py:419-438`). The file removal skips a path outside Cognee's data root and a path another Data row still references (`SqlAlchemyAdapter.py:440-484`). The evidence rows hold IDs, a chunk index and a relationship name, and no text (`modules/provenance/edge_evidence/models.py:17-45`). `prune_data` removes everything under the data root (`modules/data/deletion/prune_data.py:6-11`). Alignment's `contains` edges and the chunk `text` it reads come from `expand_with_nodes_and_edges.py:115-131` and `modules/chunking/models/DocumentChunk.py`. Its distance is the `_distance` that LanceDB, Cognee's default vector store, returns as each hit's score (`infrastructure/databases/vector/lancedb/LanceDBAdapter.py:1069-1074`). The configured prompt path is `graph_prompt_path` in `infrastructure/llm/config.py:165`, read by `extract_content_graph.py:21-25` when no custom prompt is passed. The hinted update's cognify runs over the dataset (`api/v1/update/update.py:309-321`). Step 4's dropped edges come from `expand_with_nodes_and_edges.py:115-131` (`contains`) and `modules/engine/models/Entity.py:7-10` (`is_a`), and the filter set and the cap copy the reference implementation's `retrieve.py:344-357` and `native.py:29-37`. Edit rests on `cognee.update(data_id, data, dataset_id)` keeping the ID (`api/v1/update/update.py:28-31`). Step 4 rests on `get_edges` matching an undirected pattern (`ladybug/adapter.py:2132-2178`), `get_edge_delete_data` matching a directed one by (source, target, name) (`adapter.py:1565-1608`, `provenance/delete_data.py:6-11`), `parse_source_ref_key` (`provenance/source_refs.py`), `stores_provenance_in_graph` (`provenance/markers.py:24`) and `Entity.id_for` (`modules/engine/models/Entity.py:18-21`).

### 9.4 What a crash leaves

Publish is one relational transaction after validation, so a process death leaves either revision `r` or revision `r+1` and nothing between. Cleanup is one transaction too. Erasure has three steps. The table takes a death after each and says what the stores hold. There is no plan, no attempt token and no fault-stage machinery behind it.

| Death after | Ledger | Cognee's stores | Retrieval | Retry |
|---|---|---|---|---|
| Publish step 1 | unchanged | unchanged | serves `r` | Publish again |
| Publish step 2 | `current` at `r+1` | unchanged | serves `r+1` | nothing to do |
| Cleanup | `forgotten` | the document intact | excludes the source | nothing to do |
| Erasure step 1 | `erasing`, with the two paths | the document intact | excludes the source | Forget again. Status reports `erasure_unfinished` until then. |
| Erasure step 2 | `erasing` | Cognee's delete may have committed the Data row and died before its sweeps (CB7). The evidence rows and the stored files can remain. | excludes the source | Forget again. `cognee.forget` takes the not-found branch and removes the graph and vector objects. Step 3 removes the rest. |
| Erasure step 3 | `forgotten` | swept | excludes the source | nothing to do |

The row is flipped before the native delete because Erasure wants the content and its fingerprint out of the project's records at the first step, and nothing later needs them but the two paths. The `erasing` state exists because without it a death after step 1 would look like a finished Cleanup, and nobody would learn that the document was still in Cognee. The retry removes the graph and vector objects, the evidence rows, and each stored file under Cognee's data root that no other Data row references. It cannot remove a stored original outside the data root, which is the user's own file and which Cognee never removes either, a file that another Data row with the same content still references, or bytes that stay in the stores until compaction.

Concurrency. The only object two operations can share is the ledger row, and every transition is a compare-and-set on its state and revision. Two publishes of one source cannot both land. A Publish that races a Forget refuses `revision_conflict` or `erasure_unfinished`. Two first publishes meet at the key insert. A plain cognify of the dataset changes what Retrieve step 4 reads, and each query reads it afresh. No reservation, no lock and no settled read.

The writer policy, which applies only with the spelling hint. One writer at a time adds and cognifies in a dataset. A breach costs only the exact-alignment rate, because one document's cognify can then run with another document's hint, or with none. Correctness holds, because the support check guards alignment and the ledger never depends on the hint.

### 9.5 Forget, and what Erasure leaves behind

The reference implementation's forget does nine things. The proposal keeps four.

| Function of forget | Reference | Proposal | What the reader loses |
|---|---|---|---|
| Remove one source's identity and leave what other sources share | yes, by ownership | yes. The closure is recomputed from the remaining rows on the next query. | nothing |
| Erase content from the project's own records | yes, tombstone of identifiers | yes. The row keeps the dataset, the source ID, the revision, the timestamp and, until the native delete has finished, two file paths. | nothing |
| Work on a source deleted outside the framework | yes | yes. A missing Data row and a missing dataset both count as done. | nothing |
| Refuse while dependents exist (Cleanup) | removed | not needed. No judgment in one source reads another source's judgment. | nothing today. If citations are added later, Cleanup needs a dependents check. |
| Remove or withhold dependents (Erasure not blocked) | yes, cascade in levels with a token | not applicable. Nothing can cite a source. | nothing today. |
| Dry run with a token bound to the impact | yes | no. The impact is always one source's row and, under Erasure, one document. | a preview. |
| Never reuse a removed UUID | yes, append-only table | yes, by revision in the mention ID and a kept revision counter. Entities are names. | nothing |
| Dataset forget with a token covering non-project Data | yes | no. Forget each source, then call `cognee.forget(dataset_id=...)` yourself. | a single confirmation covering everything in the dataset. |
| Physical erasure | no, logical only, residue listed | no, logical only | the same. Soft deletes in LanceDB (Cognee's default vector store) and SQLite free pages keep bytes until compaction in both designs. |

Cleanup versus Erasure. Both intents are one operation with one flag, because nothing depends on a source, so there is nothing to refuse for and nothing to cascade into. This matches the reference implementation's own observation that both intents agree when nothing depends on the source. Erasure always removes the document. Erasure is not total. This is what Erasure of source A leaves behind.

- Every reusable Entity that another document's chunks also created stays in Cognee, with its name, its `Entity_name` vector point, and its `description` property as whatever writer last set it. If Cognee extracted the Entity from A's chunks, that property came from A's text. This is Cognee's own forget behaviour (CB6). The framework holds nothing in the graph, so it adds no residue of its own.
- Every edge between two such Entities that another document's chunks also wrote stays, with the `edge_text` of its last writer (CB19). That text can be the sentence Cognee's model wrote from A's text. The `EdgeType` vector point for that text stays while any surviving edge uses it (`provenance_delete_planner.py:181-224`).
- Every variant pair and mention that another current source's description asserts stays, in that source's row.
- Logical residue in the stores until compaction.
- Under Shape 1v, a cached identity view held by another process, until that process next checks its versions (Appendix B).
- The tombstone row. Dataset, source ID, revision and timestamp. The two file paths are nulled by step 3.
- One telemetry event for the `cognee.forget` call, which carries the Data ID and is sent before the delete (`forget.py:92-102`), unless `TELEMETRY_DISABLED` is set in the environment (`shared/utils.py:400`).
- Whatever a death inside Cognee's own delete left (CB7), until Forget runs again. Section 9.4 says what the retry removes and what it cannot.

Cleanup with `keep_document` leaves more. A's document node, chunks, extracted Entities, edges and vectors stay in Cognee. Retrieve does not serve them, because step 4 admits Cognee's edges only from served sources and A's row is `forgotten`. Native search does serve them.

The day citations are added, forget must grow a dependents check (Cleanup refuses, Erasure cascades), and that is the moment the cost of section 7.2 arrives. That is a design change, not a feature flag.

### 9.6 Invariants the proposal keeps

1. What Retrieve serves for a dataset is a function of its served rows and of Cognee's graph at query time, and of nothing else. No operation leaves a state that needs repair without a row that says so. An unfinished Erasure is an `erasing` row, which Status reports and Forget finishes.
2. No ID the framework reports is ever reported with a different meaning. Mention IDs embed the source, the revision and the key, and revisions never repeat per source, because every row write is a compare-and-set on the state and revision and a forget keeps the counter. Entities are names.
3. Retrieve serves identity only from rows that are `current` and whose facet holds, and a Cognee-extracted edge only if one of its ownership keys names the searched dataset and a served source.
4. The framework adds nothing to Cognee's stores. No node, edge, vector point, Data item or property (CB2, CB19). Its one write through an internal is Erasure step 3, which removes only what `cognee.forget` would have removed.
5. A mention never bridges two groups, and a mention's surface text never seeds a reusable lookup.
6. A Cognee fact is served only from a node that alignment admitted, with that node's alignment outcome, and every closure name's outcome is reported.

### 9.7 Size estimate

Estimate, built bottom-up from named components. Each row names the reference implementation module it was derived from and what was removed. Tests, a command line and a producer are separate. The second column is Shape 2, which adds to every row it touches (section 9.10).

| Component | Shape 1 | Shape 2 | Derived from |
|---|---|---|---|
| Description model and validation | 200 to 300 lines | 250 to 350 | `models.py` 363 and `validation.py` 339, minus inputs, producer lists, recipes, citation checks and the occurrence map. Plus the `text_hash` check. Shape 2 adds chunk mapping, 50 to 80. |
| Extracted text read | 10 to 20 | 10 to 20 | the `TextDocument.read` pattern over `raw_data_location` |
| Ledger | 80 to 120 | 110 to 160 | `storage.py` 788 reduced to one table, the compare-and-set, the key insert and 4 refusal constants. Shape 2 adds `pending` and `failed`. |
| Publish | 40 to 80 | 540 to 820 | validation calls and one row write. Nothing of `publish.py` 755 remains, since nothing is written to the graph. Shape 2 keeps those 40 to 80 and adds the anchor (80 to 120), the pipeline context and DataPoint types (40 to 70) and the overlay writes with reconcile (380 to 550, the 427 publish-labelled lines of `publish.py` minus contributions, plus the 56-line fact writer of `fixture.py`). |
| Forget and Status | 70 to 110 | 150 to 220 | `forget.py` 549 reduced to the row flips, one native call and the step 3 sweep. One facet lookup instead of `native_copy.py` 174. Shape 2 adds the anchor sweep, the sentinel facet and the `unswept` listing. |
| Resolve and Retrieve | 300 to 450 | 300 to 450 | the 320 census-labelled retrieval lines of `retrieve.py` minus withholding and live drift, with the graph walk replaced by a union over the served descriptions' pairs, plus the native-edge filter, the structural-edge drop, the 200-edge cap and the provenance check. Alignment adds 70 to 120, a guess, since the reference implementation has no alignment. The same in both shapes, since neither reads the overlay. |
| Spelling hint (optional) | 30 to 60 | 30 to 60 | a template over a pinned copy of Cognee's configured graph prompt, which is not counted. A guess. |
| Total | 730 to 1,140 | 1,390 to 2,080 | Against 11,121 core lines measured |

Call Shape 1 750 to 1,150 lines and Shape 2 1,400 to 2,100. A rule producer of the reference implementation's kind is about 550 lines for one document type (measured, 543). A command line adds whatever it exposes. Four refusal codes are enough for Shape 1 (`invalid_description`, `source_changed`, `revision_conflict`, `erasure_unfinished`), against 109 measured. `native_changed`, `native_facts: unavailable`, `native_facts: truncated` and `text: unavailable` are result fields, not refusals. Tests are one unit file per component and one native test per operation against real stores, perhaps 40 to 60 test functions (estimate), of which about 20 are native (section 9.12). The reference implementation's first 29 integration tests took 605 s (section 5.4), about 21 s each, so expect about 7 minutes per serial run of the native tests (estimate). No bounded exhaustive checker is planned, because there is no admission rule set and the ledger has three states and six transitions.

### 9.8 What is dropped, what a user loses, and how each returns

This is the one list of what the proposal drops. Each row says what the user loses, how it returns without redesign, and which minimal choice keeps the door open.

| Dropped | What the user loses | How it returns | Which minimal choice keeps the door open |
|---|---|---|---|
| Identity in the graph (Shapes 1v and 2) | A native graph walk, and any other reader of Cognee's graph, sees fragmented Entities with no `variant_of` edges, no mention nodes and no mention-anchored facts. An Entity cognify did not extract exists only in the ledger. | Shape 1v (Appendix B) for graph-completion search, with nothing written. Shape 2 (section 9.10) for a reader of the live graph, where Publish gains the anchor and the overlay writes. The ledger and Retrieve change in neither. | The description already names everything the overlay would write. |
| A description copy inside Cognee | A full description readable by Cognee's own file tools. Nothing in the reference implementation read its copy for anything but a comparison at 10 sites. | Write the description into Shape 2's anchor content. | The ledger holds the one copy. A Data item exists to be an owner, not to hold a description. |
| Identity continuity across edits | After an edit, every mention ID and every fact anchored on one is new. Anything outside the framework that held a mention ID must refresh. Group membership is re-derived by Describe, so a rule describer gives the same groups and a model describer may not. | Add an admission step between Describe and Publish that takes an occurrence map from old to new groups and lets a continuing group keep its ID. | Keys on groups. Revision in the ID. A tombstone revision counter. |
| Cross-source citations with withholding | A glossary document cannot be named as the reason a second document resolved an abbreviation, so an edit to the glossary withholds nothing downstream. | Add `inputs` to each decision with a fingerprint, a withholdings table and a live validation pass in Retrieve. Then forget needs a dependents check (section 9.5). | The producer record and `text_hash` are the first two input kinds. More input kinds are additive to the schema. |
| Contributions and variant scope | Two sources that assert the same pair with different kinds are two pairs in two descriptions, and no variant is document-scoped. | Add a scope field to the variant pair and honour it in step 3. | Step 3 unions pairs without reading kinds, so a scope field changes step 3 and nothing else. |
| Withdraw separate from forget | Removing a source's identity while keeping its document is Forget with `keep_document`. Retrieve then stops serving the document's native facts because its row is `forgotten`. | Add a `withdrawn` state that keeps the row and serves native facts without identity. | One table, one row per source. |
| `IDENTITY` search type | Callers call a function, not `cognee.search`. | Register the retriever with the enum extension when uniform entry matters more than the version pin. | Retrieve is already a function with the retriever's signature. |
| Pipeline entry points | `cognee.cognify` on a dataset does not publish identity. The caller calls Publish after it. | Wrap `cognee.cognify` and Publish in one function. | Publish takes a source and a description and nothing else. |
| Dataset forget | The caller forgets each source then calls Cognee. | A loop. | Forget is per source and idempotent. |
| Outside-delete defense beyond detection | A graph-API delete of an Entity, a memory-only forget or the default prune removes Cognee's facts for a source. Identity is served throughout, because none of it is in the graph. Nothing reports the delete except the document-node report in Status. | Not needed for identity. For facts, cognify the source again. | The framework holds nothing a graph delete can reach. |
| Edge evidence tables | Native modes do not see the text behind a description fact. | Shape 2 writes the fact edge with its range as properties. | The fact carries its range in the description. |
| LLM Describe | Nothing is lost that was ever built. | A producer with method `llm`. | The producer record. Keys, names and ranges as the contract. |

### 9.9 Public calls, and the adapter internals Retrieve reads

The framework calls `cognee.add`, `cognee.cognify`, `cognee.update` and `cognee.forget` on the original as a user would. It never patches Cognee, never adds an enum member, never runs a Task under `cognify_pipeline` and never registers a Data item. It writes through internals in one place, Erasure step 3, which calls `delete_edge_evidence` and `remove_data_file_if_unreferenced`, the two sweeps Cognee's own delete runs after its commit.

It reads through internals, none of which is part of `cognee.*`. The Data row's `raw_content_hash`, `raw_data_location` and `original_data_location` through Cognee's relational session and `Data` model. `generate_node_name` and `Entity.id_for` for normalisation. `get_node` on the Data ID for Status's document-node report. `get_edges`, `get_edge_delete_data`, `parse_source_ref_key` and `stores_provenance_in_graph` in Retrieve step 4 and in alignment's support check, and `get_node` on chunks for alignment. Each name is a thing to check on every Cognee upgrade, and `get_edge_delete_data` is a provenance method that only a provenance-capable adapter implements (section 3). The cost is bounded in two ways. Every one of them is a read, so a changed name breaks a query and never corrupts a store. And every one of them is in step 4 or alignment, so a build that does not need native facts beside identity can drop both and read nothing of Cognee's but the Data row. Retrieve reads no vector index. The spelling hint is a third coupling, a copy of Cognee's configured graph prompt to refresh on every upgrade, and it can be dropped on its own because nothing depends on it. Shape 2 adds five write internals (`PipelineContext`, `add_data_points` with a context, `add_edges` with a key, `attach_node_source_refs`, `mark_data_processed`), one more read (`get_dataset_data`) and a hard requirement that the graph stores provenance. The ledger-only shape removes all of the writes, and its one hard-coupled read is `get_edge_delete_data`.

Why not a patch. The reference implementation designed one (a Task-transform hook, estimated at tens of lines plus tests) and dropped it because it must be maintained across Cognee versions. Why not entry points under `cognify_pipeline`. They cost about 600 lines, a processed mark with documented crash windows on the original, one source per run, and the loss of Cognee's run status as an outcome record (CB9, CB11). They bought the ability to run identity under Cognee's pipeline name, which the proposal does not need.

What plain usage costs. A caller who runs `cognee.update`, `cognee.forget`, the default `prune_system` or a memory-only forget directly leaves a ledger row behind. An update moves the hash, so Status reports `native_changed` and retrieval excludes the row until a republish. A native forget of the original removes the Data row, with the same result, and Forget cleans the row. A memory-only forget or the default prune keeps the Data row and the hash, so identity stays served, and Cognee's facts are absent until the original is cognified again. Cognee keeps the processed mark across the default prune (CB16), so that takes `reset_data_pipeline_status(data_id, dataset_id)` per original and then a plain `cognee.cognify`. `cognee.prune.prune_data()` removes every stored file and keeps the Data rows with their hashes, so the facet holds and identity stays served, but a ledger fact's text, a new Describe and a re-cognify all need the file. Retrieve says `text: unavailable` for the fact. The remedy is outside the framework. Restore the files or add the documents again. A re-chunking with the same bytes changes nothing the framework reads. There is no silent wrong answer in any of these cases.

### 9.10 The upgrade to Shape 2

Shape 2 keeps everything above and adds a derived overlay. These are its rules, condensed. Terms it introduces are defined here.

The anchor. For each publish at revision `r` of source `S`, Publish registers a Data item with the pinned ID `uuid5(S, "anchor:r{r}")` in the same dataset (CB18), as a named upload `identity-{S}-r{r}.txt` whose content is one line naming the source and the revision, and marks it processed at once (CB11). It is never cognified. Its only purpose is its ownership key, `source_ref:v1:{dataset}:{anchor}`. Every overlay write runs with a pipeline context whose Data item is the anchor, built by hand with no run ID and passed to `add_data_points(nodes, ctx=...)` outside any pipeline run, and every edge goes through `graph_engine.add_edges(..., source_ref_key=anchor key)`, which runs no embedding. The sentinel is one node per revision, a framework DataPoint `IdentityRevision` at `uuid5(anchor, "sentinel")`, whose presence shows that the revision's overlay is in the stores. Its ID is not the anchor's, because a stray cognify of the anchor would write a TextDocument at the anchor's ID.

The overlay. Mention nodes, a framework DataPoint `Mention` with empty `index_fields` so it writes no vector point, at `uuid5(S, "mention:r{r}:{key}")`. Missing Entities created at `Entity.id_for(name)` with `description=""`, since `Entity.description` is a required string. `attach_node_source_refs` on Entities that exist, which adds an owner and touches no property (CB2). `variant_of` edges written from the name that sorts first to the name that sorts second, so two sources write one physical edge with two owners (CB19), with no property the framework reads. `resolves_to` edges from mention to Entity. `has_identity_mention` edges from the covering DocumentChunk, found with `chunk_offsets` (CB12). Fact edges from mention to Entity with the range and the chunk ID as properties. No DataPoint holds another DataPoint as a field, or `add_data_points` would rewrite the nested one's properties. Both endpoints of every edge are checked before it is written (CB13), and a skipped edge is reported as left absent.

Publish gains steps. After validation, write the row `pending` at `r+1`. Register and mark the anchor. Write the overlay. Read back every ID and flip to `current`, or to `failed` on an exception. Then sweep. The sweep lists the dataset's Data rows once with `get_dataset_data`, and for every anchor of `S` below `r+1` call `cognee.forget(data_id=anchor, dataset_id=dataset)`, which removes what only that revision owned, detaches it from shared objects, deletes the removed nodes' vector points and removes the anchor. A source is unavailable to retrieval from the `pending` write until the flip. Reconcile(source) runs the steps after the row write again from the row's description. Every write is an upsert at an explicit ID, so a second run converges, and it finishes a sweep that a crash cut short. Forget sweeps every anchor of the source, with no revision bound, before the native delete. Status gains a sentinel facet and lists the `identity-*` Data rows once to report an anchor whose revision differs from its row's as `unswept`.

What a crash leaves, in one paragraph. A death before the flip leaves a `pending` or `failed` row and a partial overlay under the new anchor, which retrieval excludes and Reconcile completes. A death between the flip and the end of the sweep leaves revision `r`'s unshared objects in the stores, unserved but reachable by a native graph walk, until Reconcile sweeps them, and Status reports the anchor `unswept` until then. The reference implementation's forward recovery from a plan is not needed because removal reads only the anchor's key.

A name whose node cognify gave a chunk-scoped ID, because one chunk's extraction held two nodes with that name, gets a second node at `Entity.id_for(name)` with none of Cognee's edges on it. Shape 2 accepts that and states it as a limit, rather than reading every chunk's neighbours at Publish to refuse it, because that check costs one query per chunk and still misses the same name in another document's chunks.

What Shape 2 costs beyond Shape 1. About 660 to 940 lines (section 9.7). Five write internals, one more read and the provenance-capable graph (section 9.9). Two more ledger states and five more transitions. A window between the anchor's registration and its mark in which a plain cognify would send one line to the language model. And these limits. One writer per dataset at a time, by policy with no detector, since the sweep of one publish can interleave with another's retention attach. Here the policy is a correctness requirement, where Shape 1's writer policy is a quality one (section 9.4). A source is unavailable while it is republished. Between a publish and its sweep, the previous revision's unshared objects sit unserved in the stores. One extra Data item per served source appears in the dataset. A native graph walk can step from an Entity onto a mention node named "It". After the default prune, the anchors' extracted documents must be swept and the originals cognified again before Reconcile can map chunks. An Entity deleted through the graph API is recreated with an empty description by the next Publish of any source that names it. The chunk-scoped name case above. Every overlay object is reachable by `delete_by_source_ref` only if the graph stored provenance at its first write.

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

The ranges were computed with Python over the quoted text. `text[64:78]` is `The controller`, `text[126:128]` is `It`, and `text[126:154]` is the third sentence. The entity names are already in `generate_node_name` form, lower case. The explicit-abbreviation rule produced the variant from the parenthesis. The pronoun rule bound "It" to the nearest compatible antecedent, the controller. Whether that is right is Describe's quality, which the framework records but does not judge.

Publish validates the description against the Data row's hash and the extracted text, and writes the row for `(S, D1)` as `current` at revision 1. Nothing else happens. Cognee's graph is as cognify left it.

Retrieve("AFRL", S) normalises the query to `afrl`, seeds `afrl` by exact name, and unions the served variant pairs into a group of `afrl` and the laboratory. No served mention targets that group. Alignment finds both names `exact`, and both are supported by the first sentence's chunk. Step 4 reads `get_edges` on both nodes and admits the laboratory's native fact (it operates Helios-1), because one of that edge's keys names dataset `S` and Data ID `D1`. Retrieve("the controller", S) normalises to `the controller`, matches no entity name, matches the surface of `g1`, and returns `ambiguous` with no expansion. That `g1` is `accepted` does not change the answer. The acceptance says what "the controller" means inside `D1`. A query is not inside `D1`, and a document-local surface never seeds a corpus-wide lookup (invariant 5). Retrieve("controller", S) seeds the controller, collects mentions `g1` and `g2` from the description, returns the commissioned fact from the ledger with its range and the text of the third sentence, and returns the regulates fact from Cognee's own extraction if alignment admits a node for `controller`, each with the binding that admitted it. If cognify made no `controller` node, or stored a spelling no lexical rule covers, such as `the controller`, Retrieve reports `controller` as `unaligned`. Had cognify stored the laboratory as `aurora fusion research laboratory (afrl)`, as the first sentence writes it, the lexical pass would align both `afrl` and the laboratory to that node, supported by that sentence, and serve its facts labelled `lexical`. If a second dataset held a document that also named `afrl`, that document's edges would sit on the same `afrl` node and step 4 would drop them, because their keys name the other dataset.

An edit that changes the second sentence makes the caller run `cognee.update(D1, new text, S, chunk_level_diff=False)`, Describe the stored text, and Publish at revision 2, which checks the stored text against the new `text_hash`. The row now holds the new description, and Retrieve reports the mentions under `uuid5(D1, "mention:r2:...")`. A second document `D2` that also defines AFRL publishes the same pair in its own row. Step 3 unions the two, and forgetting either source leaves the pair in the other's row.

### 9.12 What to verify in the minimal build

Six checks prove the invariants of section 9.6 and nothing else needs proving. Steps 1 to 3 of Retrieve read no store, so most of the retrieval rules are unit tests over descriptions.

1. Forget and retry. Forget again after Erasure step 1 with the document still present. Forget again after a death between Cognee's commit and its sweeps, staged by deleting the Data row by hand and leaving the file. Forget on a source whose Data row is gone. Forget on a source whose dataset was deleted with `cognee.forget(dataset_id=...)`. Each ends with the tombstone, no file under Cognee's data root, and no raise. Four native tests.
2. Eligibility. A `forgotten` source and a source whose hash moved under `cognee.update` disappear from Retrieve, and a `current` one appears. A document that names `afrl` in a second dataset contributes no edge to a Retrieve of the first. Erasure of a source leaves no fact of it in Retrieve. Cleanup with `keep_document` leaves none in Retrieve and leaves the document to native search. Five native tests. A Publish whose step 1 read the row before a Forget flipped it refuses, under both intents. One unit test over the ledger.
3. Detection. After a memory-only forget of the original and after the default prune, Status reports the document node absent, identity is still served, and no native fact is returned until the source is cognified again. Two native tests.
4. Retrieval rules. The worked example's three queries, one negative control (a name that contains another name is not a variant), one two-group case (a mention into group A must not pull in group B), one case where two sources assert one pair and one source is forgotten, and one ledger fact and one native edge for the same sentence returned together with their origins. A query that names no served entity or surface returns `unresolved`. Eight unit tests over descriptions.
5. Alignment, against real stores. An exact name. A cognify spelling `Name (ABBR)` found by the lexical pass for both the name and the abbreviation, and labelled, including one whose chunk writes the two parts but not the literal string. A group member's exact node, which is not counted as a lexical match for its partner. A chunk-scoped name found the same way. A name whose only containing chunk lacks its text, reported `unsupported`. A name with no node, reported `unaligned`. Another group's name that matches lexically, which the exclusion rejects. A short name or a mention surface that a substring check would have passed, which the whole-word check rejects. Eight native tests.
6. Edits. An edit through `cognee.update(..., chunk_level_diff=False)` reports `full_rebuild`, keeps the Data ID, and leaves no evidence row naming a retired chunk. One native test, since no measurement ran an unhinted full-rebuild update.

Keep every identity judgment in these tests as captured input. Test Describe's quality separately, against a manifest its producer never read.

The spelling hint was measured on 2026-10-31 (Appendix A), over three runs with it and four without, on two documents. With the hint, 20, 20 and 17 of 20 names aligned `exact`, and the model linked 7 names per run to chunks whose text holds no name of the group as a whole word. A paraphrase counts, so some of these links may be real. In one run three abbreviations had only such links and came out `unsupported`. Without the hint, 8 to 15 names aligned `exact`, the lexical pass aligned the rest of the names that had a node, and every `unaligned` name was an abbreviation cognify never extracted, whose long form aligned. No group lost its node in any run. So the hint bought nothing there. It stays optional, off by default, until a corpus with other variant patterns shows that it helps.

The runs need real language-model extraction.

### 9.13 Limits the proposal states up front

By choice, with the section that explains each.

1. Nothing in one source can depend on a judgment in another source (9.1). This is the limit that keeps all the others cheap.
2. Identity is not in the graph. Native search and graph walks see Cognee's fragmented Entities, and an Entity cognify did not extract exists only in the ledger (8, Shape 1).
3. Variant scope is corpus-wide, and a variant's kind lives in the description (9.2).
4. An edit retires every mention ID the old revision reported (9.3).
5. Retrieve serves Cognee's own facts only from published sources. A document in the dataset that was never published, or whose row is not `current`, contributes no native facts (9.3, step 4).
6. Native facts depend on alignment. A cognify spelling that neither the exact pass nor a lexical rule covers is reported `unaligned`, and its facts are not served. The lexical rules were measured on one corpus and one naming pattern. A query that names no served entity or surface is `unresolved`, because there is no vector fallback. Every outcome is reported, and a name with no admitted node contributes no native facts (9.3, alignment).
7. Retrieve step 4 reads ownership keys through Ladybug adapter methods that are not part of `cognee.*`, and serves no native facts on a graph that does not store provenance (9.9).
8. A ledger fact and a Cognee edge about the same sentence are both served, each with its origin. The framework ranks neither, and it cannot correct a native fact about a reusable Entity, because a ledger fact's subject is always a mention (9.3, step 4).
9. The optional spelling hint takes one cognify per document (CB20). Its copy of Cognee's prompt must be refreshed on each Cognee upgrade. It relies on one writer at a time adding and cognifying in a dataset, and it reaches any item not marked processed, not only the document it was written for. A breach of the policy, and a hint that reaches another item, cost quality only (9.3, 9.4).

Cognee behaviour the proposal inherits.

10. Erasure is logical. Deleted bytes stay in the stores until compaction. A shared Entity's name and last-written description property, and a shared edge's last-written `edge_text`, stay while another document's chunks created them (9.5, CB6, CB19).
11. A death inside Cognee's own delete leaves the stored files and the evidence rows until Forget runs again, and a stored original outside Cognee's data root is never removed (9.4, CB7).
12. Cognee's native search types ignore the ledger. They can serve a forgotten source's chunks and facts (CB4). Only Retrieve applies eligibility.
13. A delete or update made through Cognee's own API is detected at the next read, not prevented (9.9). `prune_data` is not detected at all, because the facet still holds. Only a ledger fact's text goes missing (9.9).
14. After the default prune, the originals keep their processed marks and must have them reset before a plain cognify rebuilds Cognee's facts (9.9, CB16).
15. Access control on was never tested. The ledger's placement and which graph Retrieve reads may both change under it (section 6).

## 10. Open questions for the user

1. Ledger placement. Decided, as an implementation choice. The design requires only that the ledger survive anything the project treats as a repair. It may be lost in anything the project treats as a reset. Cognee's relational database meets that if `prune_system(metadata=True)` counts as a reset (CB16). A separate database meets it too.
2. Describe for the first build. Decided to stay open. The design takes any producer through the producer record, including a cheaper decision model, and the specification names none. A deterministic producer re-derives the same groups after an edit, and a model may not.
3. Variant scope. Decided. Corpus-wide scope is acceptable for the first build.
4. Identity inside Cognee's graph. Decided. Graph-completion search is in scope, so the first build is Shape 1 plus Shape 1v's in-memory route (Appendix B). Prototype its view build time on a real dataset first. Its physical-copy route works only with backend access control off (question 6). Shape 2 and its written overlay (section 9.10) are for a reader that must walk the live graph itself.
5. The no-forget variant. Kept as an option, and not a significant decision. It forbids removing a source, not editing one, so it saves only Erasure's three steps and the `erasing` state.
6. Access control. Decided for now. Start with whichever is easiest, which is backend access control off, set explicitly (`ENABLE_BACKEND_ACCESS_CONTROL=false`), as the reference implementation ran. The rest of this question applies when the project turns it on. Will access control be on in the target project? If so, the ledger placement and Retrieve's graph reads need a check nobody has run, and Shape 1v loses its physical-copy route, because `cognee.search` then sets each dataset's own graph database itself.
7. The spelling hint. Measured on 2026-10-31 (section 9.12). With the lexical pass it bought nothing on the test corpus and linked names to chunks that do not name them in every run, so the recommendation is to build without it and keep it as an option. Do you accept that, or keep it on by default? The replacement of vector similarity by the lexical pass waits on the same answer.

## Appendix A. Where the evidence comes from

The reference implementation is the `cognee-science-lab` project, designed from 2026-10-11 and built over 2026-10-14 to 2026-10-29 on Cognee 1.6.2 by an assistant (an agent) under a user's direction. "User" below means the person who commissioned it. "Assistant" means the agent that built it. Line counts were taken on 2026-10-29 at commit `d94a90e`, which has the same `src/`, `tests/` and `support/` trees as its `main` at `cc62b4b`. The census was regenerated at `16a0a79` after the source-aware search test was relabelled as mixed, which changed only the test split (first 106, mixed 17, change 329). The Cognee behaviour rows of section 3 marked "read in the source", and every Cognee file and line cited in sections 3 and 9, were read in the installed Cognee 1.6.2 package on 2026-10-29 for this document, in `tasks/storage/add_data_points.py`, `tasks/storage/index_graph_edges.py`, `tasks/storage/index_data_points.py`, `tasks/documents/classify_documents.py`, `infrastructure/databases/provenance/source_refs.py`, `infrastructure/databases/provenance/markers.py`, `infrastructure/databases/provenance/delete_data.py`, `infrastructure/databases/unified/unified_store_engine.py`, `infrastructure/databases/unified/provenance_delete_planner.py`, `infrastructure/databases/graph/graph_db_interface.py`, `infrastructure/databases/graph/ladybug/adapter.py`, `infrastructure/databases/vector/vector_db_interface.py`, `infrastructure/databases/relational/sqlalchemy/SqlAlchemyAdapter.py`, `modules/provenance/edge_evidence/models.py`, `modules/provenance/edge_evidence/cleanup.py`, `modules/data/deletion/prune_data.py`, `api/v1/forget/forget.py`, `api/v1/update/update.py`, `api/v1/datasets/datasets.py`, `api/v1/cognify/cognify.py`, `api/v1/prune/prune.py`, `modules/data/deletion/prune_system.py`, `modules/data/methods/publish_updated_data.py`, `modules/data/methods/get_dataset_data.py`, `modules/data/processing/document_types/TextDocument.py`, `modules/graph/utils/expand_with_nodes_and_edges.py`, `modules/ingestion/identify.py`, `tasks/ingestion/data_item.py`, `modules/engine/models/Entity.py`, `modules/engine/utils/generate_node_name.py`, `modules/pipelines/operations/run_tasks_data_item.py` and `shared/utils.py`. CB20, CB21, the spelling hint and the alignment rules were read on 2026-10-31, also in `infrastructure/llm/extraction/knowledge_graph/extract_content_graph.py`, `tasks/graph/extract_graph_from_data.py`, `api/v1/update/incremental.py`, `modules/ontology/*` (including `rdf_xml/RDFLibOntologyResolver.py` and `matching_strategies.py`), `modules/chunking/models/DocumentChunk.py`, `tasks/ingestion/ingest_data.py`, `infrastructure/llm/config.py` and `infrastructure/databases/vector/lancedb/LanceDBAdapter.py`. Appendix B's files were read on 2026-10-31 too, in `modules/graph/cognee_graph/CogneeGraph.py`, `modules/graph/cognee_graph/CogneeGraphElements.py`, `modules/retrieval/utils/brute_force_triplet_search.py`, `modules/retrieval/graph_completion_retriever.py`, `infrastructure/databases/graph/config.py`, `modules/search/methods/search.py` and `context_global_variables.py`.

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
| 2026-10-31 | The cache rule for Shape 1v. Keep only the most recent view per dataset, and only while both versions match it. |
| 2026-10-31 | Describe's names meet cognify's by read-time alignment, with Describe's names passed to cognify as a spelling hint. |
| 2026-10-31 | Ledger placement is an implementation choice, under the repair-versus-reset rule of open question 1. |
| 2026-10-31 | Corpus-wide variant scope is accepted for the first build. |
| 2026-10-31 | The Describe producer stays open. Rules, a language model, a cheaper decision model, a person or a combination can each plug in. |
| 2026-10-31 | Graph-completion search is in scope, so the first build adds Shape 1v's in-memory route. |
| 2026-10-31 | No-forget stays an option and is not a significant decision. |
| 2026-10-31 | The first build starts with backend access control off, because it is the easiest. |
| 2026-10-31 | Alignment's vector similar pass replaced by the lexical pass, and the spelling hint made optional and off by default, after the measurement below (assistant, pending the user's acceptance, open question 7). |

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
| 2026-10-29 | Every line count, test count, column count and refusal-code count in sections 4 to 6, at `d94a90e`, by a census script that labels lines by module docstring and caller. pytest collection of 828 cases, 707 unit and 121 integration, at `d94a90e`. 60 files and 16,672 lines by `find` and `wc`. | assistant, for this document |
| 2026-10-31 | The alignment experiment: Claude Haiku 5.5 extraction and the configured real embedding model, DOC01 and DOC02 of the Helios corpus (2 chunks each), three runs with the spelling hint and four without, aligned by the exact and lexical rules of section 9.3. With the hint, 20, 20 and 17 of 20 names `exact`, and 7 names per run linked to chunks whose text holds no name of the group. Without it, 8 to 15 `exact`, 11 names `lexical` onto 7 nodes in the one run where cognify wrote `Name (ABBR)`, and every `unaligned` name an abbreviation cognify never extracted, in the three runs whose graphs survive. Every group kept an aligned node in every run. Of 33 names not aligned `exact`, the nearest `Entity_name` hit was a wrong Entity for 27 (at 0.059 to 0.165), the name's own unsupported exact node for 3 and a group member for 3. The lexical nodes ranked 2nd to 37th (at 0.247 to 0.478). Shape 1v's projection, overlay copy and clone took under 15 ms on graphs of 63 to 78 nodes, without the ownership filter. CB11, CB16, CB17 and CB20 observed as stated. 106 LLM calls in all. | assistant |

Bug classes in section 5.3 come from independent reviews of the reference implementation between 2026-10-21 and 2026-10-27, and from its own tests. The 10 comparison sites in 4 modules of section 4.2 were counted on 2026-10-29. The worked example's offsets in section 9.11 were computed with Python on 2026-10-29 for this document.

## Appendix B. The identity view built at read time

The rules for Shape 1v. Added on 2026-10-31 from the Cognee 1.6.2 source, with every path below relative to the installed `cognee` package. Unbuilt. Its in-memory projection, overlay copy and clone were timed on small graphs on 2026-10-31, without the ownership filter (Appendix A).

**What the view contains.** The builder starts from Cognee's graph and keeps only the edges Retrieve would serve. It drops step 4's structural edges and `made_from`, which links a chunk summary to its chunk and never touches an Entity. With access control off, Cognee has one graph for every dataset, and Entity IDs are names shared across datasets (CB14). So the builder runs Retrieve step 4's ownership filter on every edge it keeps, admitting an edge only when one of its keys names the searched dataset and a served source. It then adds, for each identity group, a `variant_of` edge between members, and copies each member's admitted edges onto every other member, so a query that lands on any name reaches the whole group's facts. It adds each served mention-anchored fact as an edge from the mention's target Entity. A fact whose object Entity cognify never extracted, such as `2024`, needs a node made for the view. Neither that node nor any added edge has a vector, so Cognee's ranking scores them at its default distance penalty. Copying edges keeps every node ID as Cognee made it, which keeps Cognee's vector hits mapping onto the right nodes. Merging each group into one node would need an alias map, because a hit is mapped onto a node by ID and a later hit overwrites an earlier one instead of keeping the best score (`modules/graph/cognee_graph/CogneeGraph.py:349-380`, `CogneeGraphElements.py:69-77`).

**Alignment.** The builder aligns each group's names exactly as Retrieve does (section 9.3) and copies edges only from admitted nodes. An edge copied from a `lexical` node carries the label. Alignment is part of the build, so the cache rule below covers it, and a re-cognify that renames a node moves the graph version and drops the view.

**Duplicates.** Cognee ranks every edge in the fragment and keeps the best `top_k`, 5 by default (`CogneeGraph.py:516`). A fact copied onto N members becomes N edges with the same text and the same score, which can fill the whole result. The view returns at most one copy per original edge, by its `edge_object_id`, and every copy points at the original.

**The in-memory route.** Graph-completion search projects the graph into an in-memory `CogneeGraph` for each query (`modules/retrieval/utils/brute_force_triplet_search.py:49-116`). With the retriever's default `wide_search_top_k` of 100, that projection holds only edges touching the query's vector hits, not the whole graph (`graph_completion_retriever.py:66`, `brute_force_triplet_search.py:155-158`). `brute_force_triplet_search` accepts a ready-made fragment as `memory_fragment` (`:223-250`), and `GraphCompletionRetriever` never passes one (`graph_completion_retriever.py:206-221`). A subclass that passes the cached view needs four things.
- A search type of its own. `SearchType` is a closed enum (CB5), so this is the version-pinned enum change the reference implementation made, or a replacement of a built-in member for every caller.
- An `__init__` that absorbs the keyword arguments Cognee passes to a registered retriever (`user`, `dataset`, `only_context` and others), which `GraphCompletionRetriever` does not accept.
- Its own `node_type`, `node_name` and neighbourhood filters, because passing a fragment skips the projection that applies them (`brute_force_triplet_search.py:154-171`).
- A clone of the cached view per query. Cognee writes per-query state onto the fragment. `apply_personal_weights` sets weights it never clears (`CogneeGraph.py:414-426`), so one user's preferences would bias the next user's query on a shared view. Feedback and importance weights are read when the view is built and stay fixed until it is rebuilt.

**The physical-copy route.** Cognee picks its graph database from the `graph_db_config` context variable before the global configuration (`infrastructure/databases/graph/config.py:199-207`). A task can copy the graph database, write the view's edges into the copy, set that variable and run any search type unmodified. It works only with backend access control off. With it on, which is Cognee's default, `cognee.search` sets each dataset's own database in that variable for each dataset it searches and overwrites the task's value (`modules/search/methods/search.py:329-334`, `context_global_variables.py:338-348`). The task must reset the variable by its token afterwards. Cognee's own setter leaves it set on purpose, and a later `cognee.forget` in the same context would delete from the copy instead of the live graph. Copying an embedded database while it is open needs a consistent snapshot, which is unchecked. The vector store stays the original.

**The version keys.** The ledger version is derived, for example from the dataset's row count and its latest `updated_at`, so that no shared counter row turns every write into two. Cognee keeps no single graph version, but Ladybug stamps `updated_at` on every node and edge it writes (`infrastructure/databases/graph/ladybug/adapter.py:1034-1046`, `:2068-2069`, `:2101-2105`), and Data and Dataset rows carry `updated_at`. The graph version is then the latest such stamp plus a count of the dataset's Data rows, because a delete leaves no stamp. The builder reads both versions before and after it builds, and caches the view only if neither moved. That keeps a view built during a cognify or a Forget out of the cache.

**The cache.** The builder keeps one view per dataset, the most recent, and only while it is valid. A view is valid while the ledger version and the graph version both equal the versions it was built from. On any mismatch it is dropped, never kept, so no old view outlives a change. The user set this rule on 2026-10-31.

**Erasure.** A Forget changes the ledger version, so the dataset's view is no longer valid. Forget drops it at once rather than waiting for the next read, and deletes the copy if it is on disk, before Erasure counts as done. An in-memory view lives in one process. A Forget in one process cannot drop a view held by another, so either every process shares one cache that Forget can reach, or the other process drops its view at its next version check and Erasure is complete only then. Section 9.5 lists that window as residue.

**The pattern beyond identity.** Wherever project data is worth seeing inside Cognee's graph but keeping it consistent there costs too much, the project can keep the data as the authority in its own table, leave Cognee's stores native, and build the joined view when a reader needs it, keyed on both versions. The trade is write-time consistency work for read-time build cost and cache eviction.
