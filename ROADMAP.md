# Cognee Science Lab Roadmap

**Last revised:** 2026-10-27
**Project:** `cognee-science-lab`  
**Architecture baseline:** Cognee 1.6.2; Ladybug graph backend; LanceDB vector backend  
**Current work:** Stage 6 is in progress. Steps 1–2 have native fixtures. Step 3 demonstrates multi-source withdrawal. Step 4 demonstrates guarded unchanged-text identity corrections and captured prefix edits. Prefix edits use whole-document native rechunking, remapped positions and rebuilt fact evidence. The multi-chunk fixture covers split markers and fact continuations. See the [first-slice guide](docs/stage6_identity_first_slice.md), [revision guide](docs/stage6_identity_revision_replacement.md), [text-edit guide](docs/stage6_identity_text_changes.md) and [multi-chunk guide](docs/stage6_identity_multichunk.md).

The [occurrence-removal guide](docs/stage6_identity_occurrence_removal.md) records partial-group retention and empty unresolved-group retirement. The [resolved-group retirement guide](docs/stage6_identity_resolved_retirement.md) records retirement of a local resolution, fact and evidence while independent shared support survives. The [occurrence-addition guide](docs/stage6_identity_occurrence_addition.md) records captured additions and publication of a new group. The [group split guide](docs/stage6_identity_group_split.md) records a captured group split and combination with fresh group IDs. On 2026-10-21 the user approved one general occurrence map to replace the separate removal, addition and regrouping modes. Its rules are proven against an exhaustive small-world oracle, and every text change now goes through it. A captured mixed addition/removal edit publishes through it with no admission change ([mixed occurrences guide](docs/stage6_identity_mixed_occurrences.md)). "Current immediate work" records the step-4 close and where its remaining areas went. On 2026-10-22 the unchanged-text correction joined the same admission. Changed-interpretation and kind-change fixtures are demonstrated. `forget` and `readd` are demonstrated for a source nothing depends on. On 2026-10-23 the first dependencies checkpoint made a text edit of a consumed document withhold only the dependents' decisions that read what changed, until refreshed or re-confirmed ([dependencies guide](docs/stage6_identity_dependencies.md)). Later on 2026-10-23 `forget` became an erasure of any source: it leaves a tombstone of identifiers and, after a confirmed dry run, removes the dependents' decisions that cited the source ([forget guide](docs/stage6_identity_forget.md)). The re-add and tombstone follow-ups landed the same day. Checkpoint J1, also on 2026-10-23, lets a decision cite another source's decision and withholds the citing decision down the whole chain when what it cites is withheld, changed or gone ([chains guide](docs/stage6_identity_chains.md)). Checkpoint J2, on 2026-10-24, makes a forget cascade down every chain of citations, level by level, under one dry run, one token and one confirmation ([forget guide](docs/stage6_identity_forget.md#the-cascade)). Checkpoint K, also on 2026-10-24, gives reviewer paths to the readers of an edited Entity or a removed record, refuses a returning cited record key and a corpus input of a mention UUID, and runs kind changes where other sources read the changed document ([entity edits guide](docs/stage6_identity_entity_edits.md)). On 2026-10-25 a cleanups branch closed the small tracked follow-ups, two real-embedding fixtures passed on the user's Mac, and the user declared step 4 complete. The same day a discussion session with the user set the step-5 approach. The lab gets its own entry points instead of a Cognee patch, and it detects deletes made outside the lab instead of hooking them. Step 5 S2, merged on 2026-10-26, makes `status` report a source that Cognee deleted, `reconcile` refuse it and `forget` erase the lab's copy afterwards. It adds `forget-dataset` for a whole dataset and for repair, and an append-only record that keeps every removed Entity UUID from use again ([forget guide](docs/stage6_identity_forget.md#deletes-outside-the-lab)). Step 5 S3a, merged the same day at `3da0d7f`, gives the lab its own `add`, `cognify` and `remember` over Cognee's `cognify_pipeline`, builds the doc01 fixture through them and stamps the lab's files so a plain `cognee.cognify` skips them ([entry-point guide](docs/stage6_identity_standard_entry_points.md)). Step 5 S3b, merged later the same day at `3207a72`, moves every other creation command and `readd` onto them, one source at a time in publication order, and deletes the hand-built creation path. Step 5 S4, merged later the same day at `399ce94`, moves every text edit onto the lab's `update`, which rebuilds the original's chunks with Cognee's standard Tasks inside one lab Task while the identity revision stays incremental ([entry-point guide](docs/stage6_identity_standard_entry_points.md#the-labs-update)). Step 5 S1, merged the same day, adds the lab's `IDENTITY` search type to `cognee.search` and a conformance check that gates retrieval changes ([IDENTITY search guide](docs/stage6_identity_public_search.md)). **Next task:** the source-aware mode and the other step-5 delivery items. See the session handoff. Earlier investigation entries retain historical wording. [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) governs the current implementation state.

This revision reconciles the roadmap with later project decisions and `cognee_extension_architecture_reference_v1.6.2.md`. Historical graph counts and benchmark scores apply only to their recorded experimental snapshots. They do not describe the current live database. “Complete” means the exploration was sufficient to proceed. It does not mean the capability has a production implementation.

For continuation, start with [docs/SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md). It records the current state, the next task and the verification routine. The [checkpoint history](docs/stage6_checkpoint_history.md) holds each Stage 6 checkpoint's dated record. Historical revision entries below describe their own dates.

## Progress at a glance

| Stage | Status | Outcome / next work |
|---|---|---|
| 1–4 | Complete | DataPoint mechanics, native construction/retrieval, mixed open + typed observations |
| 5.1–5.2 | Complete | Identity benchmark and non-destructive support structures |
| 5.3.0–5.3.2 | Demonstrated | Unified roles, identity-aware neighborhood retrieval, query-time resolution |
| 5.3.3 | Modest scope retained | Logical fact reconciliation; general predicate ontology remains deferred |
| 5.4.1 | Complete | Overlapping ingest exposed mutation of existing Entity properties |
| 5.4.2 | Complete enough to proceed | Operational map and preferred extension seams |
| 5.4.3 | Complete enough to proceed | Native retrieval semantics; custom identity-aware Retriever direction |
| 5.4.4 | Complete enough for architecture selection | Preferred B, a small Cognify task-transform extension. On 2026-10-25 the user chose lab entry points instead (Stage 6 step 5) |
| 5.4.5 | Handoff review complete | Representation, lifecycle, retrieval, reduced recovery scope and interface-only implementation boundary reviewed |
| 6 | In progress | Steps 1 to 3 demonstrated in bounded fixtures, and step 4 complete (2026-10-25). Step 5 / M4 in progress: S2, S3a, S3b, S4 and S1 complete (2026-10-26), so the lab has its own entry points, detects deletes made outside the lab and serves `cognee.search` with its `IDENTITY` search type, gated by a conformance check. Next: the source-aware mode and the other step-5 delivery items. Step 6 (Describe, facts as records, quality evaluation) not started. See the [session handoff](docs/SESSION_HANDOFF.md#current-state) for the current state and the [checkpoint history](docs/stage6_checkpoint_history.md) for each checkpoint. |
| 7–10 | Planned | Ontology grounding, scientific structures, evolution, final synthesis |


## Project goal

Explore Cognee as a substrate for scientific/domain-specific LLM memory, with emphasis on evolving knowledge, explicit provenance, identity resolution, structured scientific semantics, and retrieval over both open-world and strongly typed representations.

The working hypothesis is that a useful architecture will combine:

- Cognee's open semantic graph, chunk, summary, vector, and provenance infrastructure;
- selected strongly typed semantic structures for high-value concepts such as identity, time, measurements, units, claims, and evidence;
- source-grounded intermediate representations rather than discarding extraction decisions;
- hierarchical context at chunk, document, and corpus/domain scopes;
- retrieval modes that distinguish semantic reasoning from provenance/explanation and graph maintenance;
- non-destructive reconciliation rather than aggressively rewriting or merging the original graph.

The current synthetic corpus is centered on the fictional Aurora Fusion Research Laboratory / Helios-1 tokamak program. Hidden manifests contain benchmark intent; source documents must not contain benchmark annotations.

---

## Architecture principles established so far

### Open semantic graph + typed overlays

Cognee's generic extraction is useful for broad semantic coverage but produces open-vocabulary relations and inconsistent identity consolidation. Typed structures should augment, not replace, that graph.

### Preserve source-grounded intermediates

Important extraction outputs should remain inspectable even when later processing succeeds or fails. Examples include mentions, abbreviation observations, definition summaries, and later claim/evidence structures.

### Identity is non-destructive

Do not physically merge equivalent Entity nodes as the default strategy. Preserve original extracted nodes and represent reconciliation explicitly.

### Singleton, identity group and mention — selected initial direction

Use **singleton** and **identity group** terminology going forward. An identity group consists of reusable variants connected by applicable variant relationships; it has no privileged canonical Entity. A singleton is an ordinary Entity outside such a group, excluding marked mentions. Historical Stage-5.3 references to canonical/variant/mention roles describe the earlier experiment.

A mention is a locally scoped reference-group Entity containing one or more exact text occurrences sharing one interpretation. It receives an explicit saved group UUID and a generated identity TextDocument → Entity has_identity_mention marker. Classification persists when no accepted resolution exists. A reusable variant Entity must not also serve as a mention.

Do not add authoritative identity fields to ordinary Entity properties. Store resolution kind, applicability and current contributions on identity edges, and retain structured assignments/original-input provenance independently in generated identity sources. Do not introduce singleton or variant markers, or a graph support node per assignment, in the initial design.

The proposal groups document-local assignments into one generated Data item per original document and uses native document-level owners to retain all required endpoints. Original-input dependency, native ownership and applicability remain distinct. See [the recorded proposal](results/cognee_stage5_4_5_identity_representation_proposal.md) for the preliminary ownership matrix, edge contents, evidence boundaries and remaining decisions.

### Project state must survive native mutation

Stage 5.4.1 showed that later Cognify can replace existing Entity properties, including experimental entity_role/graph_layer annotations. The initial direction therefore places authoritative identity state in structured generated sources and project identity relationships.

Edges are not generically protected: same-triple upserts can replace their ordinary properties, endpoint deletion removes incident relationships, and optional consolidation can remap endpoints. Identity maintenance must aggregate contributions explicitly and handle source lifecycle changes. Existing endpoint retention is attached through native source refs without rewriting ordinary Entity properties.

Logical layers and distinct IDs are not native mutation barriers. Selected operation contracts and actively consumed index/backend-reference behavior remain to be checked for this exact publication path.

### Direct semantic identity navigation

Keep direct Entity-to-Entity resolves_to relationships, with a stored resolution_kind distinguishing:

- variant: bidirectional equivalence under applicable contributions;
- mention: a directed occurrence-specific reference into a singleton or identity group.

Resolve query context before semantic activation. Follow applicable variant paths transitively; a mention may enter the group through any member. Mention links do not create equivalence groups and must not become unrestricted reverse expansion or bridges between groups.

Current contribution collections supply edge applicability. Original-document provenance does not itself determine applicability scope. Native readers and triplet text do not automatically implement these traversal rules.

### Logical graph layers

Keep semantic, source/context and provenance functions distinct without requiring a graph support node for each assignment:

| Function | Initial arrangement |
|---|---|
| Semantic graph | Ordinary Entity nodes and domain relationships |
| Identity navigation | resolves_to edges carrying variant/mention kind and current applicability contributions |
| Mention classification | Generated identity source document → Entity has_identity_mention marker |
| Durable identity/provenance | Registered generated Data sources retaining structured assignments, original-input provenance and readable descriptions |
| Original source/context | Native documents/chunks/summaries and relevant observation/definition inputs |

Earlier IdentityResolution/Mention helpers remain experimental history, not required durable forms. Final storage of observations/DefinitionSummary and transition from prototype helpers remain open. Exclude identity/source/provenance structures from normal subject-matter output; expose them when requested for explanation or maintenance.

### Retrieval modes

Planned logical retrieval modes:

1. **semantic** — Entity nodes, ordinary semantic relations, and identity navigation; support nodes excluded by default;
2. **source-aware** — semantic results plus relevant source/context nodes;
3. **explanation / provenance** — semantic results plus saved assignments, edge contributions, observations and original/generated source support;
4. **graph-management** — full support/dependency structure for maintenance, update, deletion, reconciliation, and debugging.

---

# Stage roadmap

## Stage 1 — DataPoint mechanics — COMPLETE

Goal: understand how Cognee persists custom DataPoints and how identity is generated.

Key findings:

- scalar fields become node properties;
- nested DataPoints become nodes plus graph edges named from the field;
- lists of DataPoints produce one edge per target;
- `identity_fields` drive deterministic UUID generation at object construction time;
- identical identity-field values reuse the same UUID;
- identity fields do not perform semantic alias/coreference resolution;
- Pydantic overrides of Cognee metadata require explicit type annotations.

---

## Stage 2 — Default `add -> cognify` pipeline — COMPLETE

Goal: inspect Cognee's default graph, chunks, summaries, and provenance behavior using revised DOC01.

Baseline DOC01 graph before later overlays:

- 127 nodes;
- 323 edges;
- 93 Entity;
- 21 EntityType;
- 6 TextSummary;
- 6 DocumentChunk;
- 1 TextDocument.

Important findings:

- source document -> DocumentChunk -> TextSummary -> semantic entities/relations;
- DocumentChunk preserves source text and is the main raw-text rescue path;
- default semantic extraction is open-vocabulary;
- aliases are inconsistently consolidated;
- negation may appear as predicates;
- provenance exists through more than one mechanism;
- some context-dependent unit/value inference materializes while other plausible inference does not.

---

## Stage 3 — Retrieval methods — COMPLETE

Goal: compare retrieval from chunks, lexical chunks, summaries, graph, and hybrid graph+source context.

Representative top-k=2 benchmark result:

- RAG: 6/7;
- Graph: 5/7;
- Hybrid: 6/7.

Important findings:

- graph retrieval can introduce semantic errors;
- source chunks can rescue graph omissions;
- different representations fail differently;
- graph completion uses a richer projection than triples alone;
- conversation/session contamination must be controlled during retrieval experiments.

---

## Stage 4 — Mixed semantic structure and typed overlays — COMPLETE

### 4.1 Custom graph-model boundary

A custom DataPoint graph model replaces Cognee's normal semantic Entity/EntityType/open-relation extraction while preserving document/chunk/summary infrastructure.

Key finding: a custom top-level graph model is a replacement boundary, not a simple extension point.

### 4.2 Mixed open + typed extraction

Used a `KnowledgeGraph`-derived extraction DTO containing both generic nodes/edges and typed abbreviation outputs.

Key findings:

- LLM extraction DTOs should be separated from persistence DataPoints;
- generic and typed outputs can be produced by one LLM call;
- normal Cognee persistence consumes the generic nodes/edges but ignores extra typed fields unless explicitly persisted;
- strong typing does not automatically solve normalization or identity resolution;
- local chunk extraction can recognize a form without resolving it.

### 4.3 Persistent typed overlay

Persisted `AbbreviationObservation` DataPoints after Cognify while keeping Cognee's generic graph intact.

### 4.4 Source-linked observations

Linked each observation to its actual source DocumentChunk.

Final observation set for DOC01:

- 23 AbbreviationObservation nodes;
- source-grounded `observed_in` edges;
- resolved and unresolved abbreviation-like observations preserved separately.

Key conclusion:

> Mixed open graph + typed source-grounded observations works. Canonicalization and identity resolution should remain separate later stages.

---

## Stage 5 — Identity, resolution, and semantic reconciliation — SCOPED EXPLORATION/HANDOFF COMPLETE

### 5.1 Identity benchmark and fragmentation inventory — COMPLETE

Benchmark cases cover:

- abbreviations;
- aliases;
- semantic variants;
- contextual references;
- negative/non-equivalence controls.

Major findings:

- Cognee identity consolidation is inconsistent across cases;
- VCS, EDC, and H-1 were largely consolidated;
- AFRL, NBI, and ECH retained fragmented representations;
- type compatibility and shared graph neighborhoods are useful weighted evidence but should not be hard identity rules;
- mention resolution and assertion extraction are separate processes;
- a fact may be preserved even when the mention representation is not;
- source spans and explicit resolution state are needed for better observability;
- negative evidence should be preserved rather than forcing aggressive merge decisions.

Resolution states to support include:

- resolved;
- likely equivalent;
- ambiguous;
- unresolved;
- explicitly distinct.

### 5.2 Non-destructive identity representation — COMPLETE

**Historical representation experiment:** the helper-node forms below remain measured prototype results. The 2026-10-13 initial direction does not require per-assignment IdentityResolution support nodes.

Implemented and tested:

- `IdentityResolution` helper nodes;
- `Mention` helper nodes;
- `DefinitionSummary` document context;
- source-grounded `AbbreviationObservation` evidence;
- graph-native links from resolution helpers to canonical/source entities and document scope;
- mention-to-source and resolved-mention-to-canonical links;
- observation-to-resolution `supports` links.

Final 5.2 graph baseline:

- 154 nodes;
- 365 edges;
- 23 AbbreviationObservation;
- 9 IdentityResolution;
- 2 Mention;
- 1 DefinitionSummary.

Evidence path:

```text
DocumentChunk
    ^ observed_in
AbbreviationObservation
    | supports
    v
IdentityResolution
    | canonicalizes_to
    v
Entity
```

Important conclusion:

> Identity can be represented explicitly without rewriting Cognee's original semantic graph.

Open implementation note:

Manual graph-engine edges have a thinner metadata envelope than Cognee-generated DataPoint relationships. Proper lifecycle/provenance integration is deferred to Stage 6.

### 5.3 — Unified Entity roles, direct identity navigation, and alias-aware retrieval — DEMONSTRATED

#### 5.3.0 Representation experiment — COMPLETE for the benchmark subset

**Historical terminology:** canonical/variant/mention and Entity annotations below describe the demonstration. Current design uses singleton/identity group/mention, edge metadata and saved assignments.

Implemented the logical roles `canonical`, `variant`, and `mention`, with scope independent of role. Materialized missing reusable variants and occurrence-specific mention Entities, added direct `resolves_to` links, and retained Stage-5.2 support/provenance helpers.

The resulting experimental snapshot had **160 nodes / 377 edges**. The annotations used in this experiment are not a durable storage decision: 5.4.1 later exposed their vulnerability to native Cognify writes.

Representation rules demonstrated at that time:

- canonicality was scope-relative;
- all roles may carry ordinary semantic edges;
- extraction history belongs in provenance;
- semantic applicability (`scope_kind`, `scope_anchor_id`) differs from occurrence source coordinates;
- mention identity must be anchored to a specific text-bearing representation, currently `DocumentChunk`;
- `start_char` / `end_char` are relative to that anchor; `occurrence_index` is a temporary fallback until exact spans are reliable.

The temporary `materializes_as` link between a Stage-5.2 `Mention` helper and a semantic mention Entity denotes a cross-layer projection, not domain identity. Helper naming and edge vocabulary remain subject to the production support model.

#### 5.3.1 Identity-aware neighborhood traversal — DEMONSTRATED

Starting from a known resolved Entity, traverse identity separately from ordinary semantic distance, union semantic neighborhoods, logically suppress duplicate facts, and retain original edges for attribution. Support/provenance nodes are excluded from normal semantic retrieval.

The primary NBI group is:

```text
NBI
neutral beam injection system
neutral beam injection
```

Negative controls remain load-bearing: Aurora Reconstruction Suite must not merge with AFRL/Aurora organization; unresolved controller mentions must not acquire a forced canonical resolution; helper nodes must not leak into semantic recall.

Stage-6 regression coverage should track fact recall, logical duplicate suppression, identity-hop treatment, source attribution, and helper leakage across the NBI/ECH/VCS/AFRL/H-1 benchmark groups. Do not infer that all of this is implemented in native Cognee retrieval.

#### 5.3.2 Query-time mention/entity resolution — DEMONSTRATED

Built a reusable query-resolution script/benchmark and demonstrated the end-to-end resolution + identity-aware recall path:

```text
user query
    -> detect candidate mentions
    -> generate candidate canonical Entities
    -> disambiguate using context + limited graph evidence
    -> activate resolved semantic Entities
    -> identity-aware recall
```

Recorded behavior:

- `NBI` resolves through the reusable variant mapping;
- contextual `"the controller"` resolves to the Vertical Control System or Edge Density Controller according to context;
- `"What does the controller do?"` remains ambiguous without disambiguating context;
- the Stage-5.3 query-resolution benchmark was **5/5 before overlapping DOC02 Cognify**, then **0/5 afterward** because the resolver relied on overwritten project annotations (5.4.1).

Historical mention records may supply evidence. Bare unresolved surface text must not activate every historical occurrence sharing that text.

#### 5.3.3 Relation reconciliation — LIMITED SCOPE; NO GENERAL PREDICATE ONTOLOGY

Keep logical fact reconciliation modest: equivalent Entity representations should yield a coherent logical neighborhood, while raw edges remain available for provenance. Broader verification belongs in the custom Retriever and Stage-6 regressions. The available progress record does not establish completion of a separate general relation-reconciliation implementation.

### Local reference groups selected; broader graph compaction deferred

The 2026-10-14 decision replaces the initial one-node-per-occurrence proposal with locally scoped reference groups, initially paragraph-bounded. One saved record and mention Entity can cover several exact ranges sharing one interpretation. A deliberate selection policy avoids assuming every pronoun needs an identity record; the exact selection policy remains to be specified.

This groups references during description/publication. It does not authorize merging existing native mention nodes, collapsing semantic relations or losing their source attribution. If semantic relations are attached to grouped mention nodes, occurrence-level attribution must be retained explicitly; it cannot be inferred merely from the endpoint node. Broader post-publication graph compaction remains deferred.

### 5.4 — Operational semantics, architecture, and graph evolution — REVIEW COMPLETE FOR STAGE 6

The earlier **5.4A resolution scope/timing + 5.4B graph evolution** split is superseded. Identity representation cannot be chosen independently of Cognee's construction, maintenance, retrieval, update, and deletion behavior. Scope/context questions are retained below and in Stage 6 rather than abandoned.

Representation candidates remain distinct from lifecycle approaches:

| Representation candidate | Meaning |
|---|---|
| A | Augment Cognee's semantic graph |
| B | Separate identity subgraph |
| C | Auxiliary identity structures/store |
| D | Hybrid |

These letters are **not** the lifecycle A/B alternatives in 5.4.4. No final physical representation has yet been selected.

#### 5.4.1 Incremental / overlapping-ingest baseline — COMPLETE

Added DOC02 through ordinary Cognify over the Stage-5.3 graph. This was an overlapping-ingest experiment, not a test of the native incremental `update()` engine.

| Observation | Result |
|---|---|
| Nodes | 160 → 281; +121 |
| Edges | 377 → 761; +384 |
| Pre-existing edges removed or modified | None in the recorded diff |
| Pre-existing Entity nodes with rewritten properties | 30 |
| Stage-5.3 query-resolution benchmark | 5/5 → 0/5 |
| Direct `resolves_to` topology | Survived |

Cognify rewrote Entity names/descriptions and experimental project annotations such as `entity_role` / `graph_layer`. The benchmark failure therefore exposed metadata instability even though identity edges survived.

**Established constraint:** native Cognify is not append-only for existing node properties. Do not depend on important project state surviving as mutable properties on Cognee-owned Entity nodes. Edge survival in this one experiment is not a general persistence guarantee.

#### 5.4.2 Cognee operational / extension map — COMPLETE ENOUGH TO PROCEED

Mapped construction, enrichment/reconciliation, retrieval, update/evolution, and deletion. Prefer native identity behavior where useful and extend it where needed.

| Surface | Current direction |
|---|---|
| `DataPoint` / `graph_model` | Typed representations and extraction configuration; retain the Stage-4 replacement-boundary finding |
| Tasks / custom pipelines | Extraction and construction sequencing |
| Memify / Improve custom Tasks | Replayable, idempotent maintenance and reconciliation |
| Registered custom `Retriever` / `SearchType` | Explicit project retrieval semantics |
| `GraphDBInterface` / vector interfaces | Backend-independent access |
| Native incremental Update | Constrained; avoid customizing its internals initially |
| Forget | Compatibility and cleanup concern, lower design priority |
| Private Hybrid methods, `brute_force_triplet_search`, backend-specific manipulation | Fragile dependencies to avoid |

The companion architecture reference supplies implementation detail and source anchors. In pinned 1.6.2, Improve's top-level stages are fixed; custom Memify Tasks are exposed through its triplet-enrichment stage. Supplying such Tasks does not itself establish isolation from the other built-in Improve stages.

#### 5.4.3 Retrieval semantics / extensions — COMPLETE ENOUGH TO PROCEED

| Native lane | Characterization |
|---|---|
| `RAG_COMPLETION` | Source/chunk-vector lane; reference and fallback |
| `GRAPH_COMPLETION` | Vector-selected graph evidence, ranked triplets, context rendering |
| `HYBRID_COMPLETION` | Passages plus entity/fact neighborhoods |

Cognee treats `resolves_to` as an ordinary relationship, not a built-in semantic identity operation. Some apparent native alias success was lexical redundancy rather than identity expansion.

**Direction:** register a project Retriever/SearchType that performs query-time resolution, scope-aware identity expansion, semantic-neighborhood union, and logical fact deduplication while retaining raw edges and source attribution. Keep native RAG as a comparison/fallback; do not patch `recall()` / `search()` or silently replace native retrieval types.

#### 5.4.4 Lifecycle / persistence — COMPLETE ENOUGH FOR ARCHITECTURE SELECTION

Distinguish source lifecycle from derived-knowledge maintenance. Native Update replaces source-derived state; project reconciliation must be replayable. Some customization genuinely belongs inside extraction/construction, as the graph-model experiments already showed, so post-Cognify processing alone is insufficient as a universal solution.

Compared two lifecycle approaches:

| Approach | Benefit | Maintenance cost | Decision |
|---|---|---|---|
| A — project `science_remember()` / `science_update()` wrappers | Cognee remains untouched; project controls custom sequence | Duplicates/tracks native lifecycle bookkeeping, status, pinned IDs, result and rollback behavior | Viable fallback |
| B — small Cognify task-transform extension | Native lifecycle orchestration runs a customized construction sequence | Small maintained patch at task-list seam; local Python first | **Preferred direction** |

**B is an implementation proposal, not a completed patch.** Conceptual API:

```python
cognify_task_transform: Callable[[list[Task]], list[Task]] | None = None
```

Initial contract:

1. Core `cognify()` builds native STANDARD Tasks, applies the optional transform, then forms `tasks_by_route`, computes pipeline LLM needs, and runs the native `cognify_pipeline`.
2. Transform can insert, replace, remove, or append Tasks while inheriting the configured native sequence.
3. Standard permanent-memory `remember()` forwards the argument; no replacement lifecycle is required.
4. `update()` with a non-null transform forces the existing full-rebuild path and passes the same transform into Cognify. The separate incremental updater cannot assume compatibility with arbitrary construction Tasks.
5. Preserve native data-ID resolution, `forget(memory_only=True)`, pipeline-status reset, pinned replacement Add, and native result construction. Custom Task side effects still need explicit replay/cleanup behavior; native rollback is not a blanket guarantee for arbitrary writes.
6. Initially support local Python and `CognifyRoute.STANDARD` only. Leave DLT/code/special routes native; special Remember modes do not all reach STANDARD Cognify.
7. Reject unsupported remote-callable combinations. A remote extension would need a server-side named/registered configuration.
8. Define dry-run behavior explicitly: reject transforms initially or state clearly that native estimates exclude custom costs. Inserted Tasks must respect pipeline input/output contracts.

The reviewed call paths include direct local SDK Cognify, standard Remember, full-rebuild Update, and the HTTP `/api/v1/cognify` endpoint. Incremental Update bypasses Cognify. Remote SDK Cognify forwards to the server before local Task construction, so a client-side callable is not sufficient. No additional comparable top-level lifecycle caller was identified in that review.

Keep **derived maintenance separate**: use idempotent Memify/Improve Tasks for reconciliation, normalization, and suitable semantic materialization. How maintenance is invoked after each source mutation remains part of 5.4.5/Stage 6; merely adding the Cognify transform does not wire this automatically.

#### 5.4.5 Architecture and operational invariants — HANDOFF REVIEW COMPLETE

Consolidate 5.4.1–5.4.4 into an implementable architecture. Begin with evidence of **actual Cognee mutation behavior across the whole graph**, then derive ownership rules. Do not treat desired ownership or logical graph layers as facts about existing Cognee mechanics.

##### 5.4.5.1 Cognee mutation surface — COMPLETE FOR EXPLORATION

Completed pinned Cognee 1.6.2 source inspection, graph/vector/relational baselines, isolated adapter/planner checks, public-operation clone probes, a minimal custom Claim/Measurement/Evidence fixture, and final operation × artifact synthesis. Detailed evidence and the measured/source-inspected/untested labels are retained in `cognee_stage5_4_5_1_initial_findings.md`.

Runtime coverage:

| Operation/profile | Established result |
|---|---|
| Overlapping Cognify | Existing Entity property replacement is observed; project annotations can be overwritten |
| DataPoint persistence / custom Tasks | Full property upsert differs from patch; prior relationships can remain; run/dataset context alone is insufficient ownership |
| Default Improve / direct Memify | Default triplet indexing includes support and other-dataset relationships in shared storage; direct default/empty-list Memify refreshes existing Triplets |
| Native incremental Update | Diagnostic default-model profile bypasses core Cognify, preserves unchanged chunks, and exposes evidence/index/watermark gaps |
| Project-model full rebuild | Routes through memory-only Forget, Add, and Cognify; project maintenance is not replayed automatically |
| Source and dataset Forget | Last-owner cleanup and shared survival work; unowned helpers and detached-edge Triplet orphans remain |
| Minimal scientific fixture | Explicit source binding stamps the written subtree; nested supersession also co-owns old objects; ownership removal does not restore historical values |
| Recall/Search controls | Tested graph/index/evidence state unchanged; history, operation rows, cached QA and session vectors have profile-specific writes |

Concrete measured findings:

- Baseline: 281 nodes / 761 edges; 35 project support nodes and 62 support-incident edges have no native owner; all 90 support field-vector rows exist.
- Enabled no-session Improve indexes all 761 shared graph relationships, including 62 support relationships and 286 DOC01-only relationships despite a DOC02 dataset call.
- DOC01 source or dataset deletion removes 74 nodes / 329 edges, preserves 45 shared nodes / 19 shared edges with DOC02 ownership, and leaves 35 stale helpers, 14 isolated helpers, and 43 detached-edge orphan Triplets.
- Same-dataset priming proves that enabled Improve skips after an incremental write and leaves 71 new-edge Triplets absent in the follow-up. Incremental evidence retains 93 rows naming retired chunks, including 79 rows for absent graph edges in the first Update probe.
- Full dataset Forget removes the dataset, Data row, and clone-managed source files; memory-only dataset Forget retains them and clears both Add/Cognify status entries. Both invalidate seeded attributed cached QAs/session vectors; session registry/history rows remain.
- Custom Tasks require a concrete source Data anchor for native ownership. Lifecycle ownership, assertion evidence, scalar source fields, vector attribution, and historical values are distinct contracts.
- DOC01-requested retrieval uses one DOC01 chunk plus two DOC02 chunks in this access-control-disabled shared-store configuration. Dataset labels do not establish source-confined retrieval.
- All 15 custom-fixture checks and all 25 closure-control checks passed. No repair implementation was added to finish characterization.

**Coverage boundary:** runtime probes use Ladybug/LanceDB/SQLite, access control disabled, two documents in separate datasets sharing storage. Dataset deletion includes DOC01's one-document dataset; read controls use CHUNKS/RAG_COMPLETION, a fresh session, automatic feedback off, and last-access tracking off. Session-enabled/opt-in Improve stages, other isolation/backend configurations, and broader session-invalidation paths retain their source-inspected or untested labels. The default-model incremental profile is diagnostic, not the lab's project-model production path.

The completed matrix covers semantic, project semantic, support/reconciliation, source/context, native ownership, assertion evidence, graph indexes, and session/history/accounting artifacts. No production scientific schema or physical identity representation is selected by the fixture.

**Subsequent implementation:** the reviewed model and bounded Stage-6 publication/maintenance fixtures now exist. General lifecycle coverage remains in Stage 6; it does not reopen the completed characterization. Index/backend-reference guarantees apply to stores consumed by enabled paths; unused diagnostic stores do not force immediate repair.

##### 5.4.5.2 Artifact ownership / provenance model — REVIEWED; INITIAL RUNTIME MODEL IMPLEMENTED

The six outcome requirements remain in cognee_stage5_4_5_requirements_review.md. The initial ownership choices are:

- preserve structured assignments and original-input provenance independently of materialized edges;
- group document-local assignments into a generated Data source per original document;
- use native document-level generated-source ownership initially;
- deliberately retain both existing and new Entity endpoints required by assignments, attaching refs to existing nodes without property replacement;
- distinguish original-input dependency, generated-source ownership, applicability and run attribution;
- recompute shared edge contributions when assignments are withdrawn, rather than relying on owner retention to restore properties.

The reviewed matrix is in results/cognee_identity_stage6_handoff.md. Runtime fixtures implement original-chunk markers/facts/evidence, generated-source endpoint retention and shared contribution ownership. General original-to-generated dependency/removal orchestration and expanded consumed-store admission remain Stage-6 implementation work. Cached QA/session vectors remain conditional on enabling reuse.

**Scientific reasoning boundary:** provenance and retention ownership do not establish scientific support. Scientific justification remains Stage 8; no claim/evidence inference policy is adopted here.

##### 5.4.5.3 Stable physical representation — REVIEWED; DRAFT FORMS AND PUBLISHER IMPLEMENTED

The selected initial direction uses ordinary Entity nodes, identity-group variant relationships without a privileged canonical member, local reference-group mention Entities, and explicit mention markers from the original occurrence-covering DocumentChunks. Generated identity Data owns resolution contributions and endpoint retention, not those markers.

Resolution edges store resolution_kind and current contributions. Separate singleton/variant markers and per-assignment graph support nodes are omitted. Structured assignments are sufficient to reproduce exact graph intent; ordinary LLM parsing of identity descriptions is not relied on for faithful reconstruction.

Deterministic occurrence UUIDs override Entity's default name-based identity. A custom loading Task must publish ID-based edges and intentionally attach existing endpoint refs without passing populated existing Entities through recursive persistence. calculate_chunk_graphs is a computation seam, not a complete reference-only loader/routing solution.

Implemented outputs include draft structured-source forms/serialization, explicit UUIDs, current contribution payloads, native source-bound loading and bounded lifecycle validation. General extraction/routing, dependent-source/full source lifecycle and optional endpoint consolidation/remapping remain unimplemented/admission work; prototype Stage-5 helpers are not the current runtime representation.

##### 5.4.5.4 Write / reconcile / read / update lifecycle — CONTRACT REVIEWED; PARTIAL STAGE-6 IMPLEMENTATION

The initial new/existing-endpoint publication, shared contributions, source withdrawal, selected corrections, text/chunk rebuilding and group-retirement sequences are implemented. Remaining scenario coverage and original/generated source orchestration are tracked in Stage 6 and the session handoff; the .1 investigation and architecture review are complete.

Specify which Tasks belong inside transformed Cognify and which belong in Memify/Improve; when maintenance runs; how failed or stale derived state is detected; and what a custom Retriever accepts as usable state.

| Lifecycle phase | Proposed seam | Remaining contract |
|---|---|---|
| Ingest | Native Remember/direct Cognify + proposed B transform/custom loading Task | Register/routable identity Data, deterministic publication, source ctx, existing endpoint retention |
| Reconcile | Idempotent project Tasks at the selected seam | Contribution aggregation, marker/resolution consistency, replay scope, selected native stages |
| Read | Registered custom Retriever/SearchType | Identity groups, scoped directed mentions, contribution checks, deduplication, attribution |
| Update | Project full-rebuild path with customization forwarded, then maintenance | Original/generated-source dependencies, endpoint recreation, usable-state/failure behavior |
| Delete | Native Forget plus derived-source retirement/contribution repair | Surviving inputs/owners, original dependency cleanup, indirect edge/index removal |

##### 5.4.5.5 Operational invariants and Stage-6 handoff — REVIEW COMPLETE

Reviewed invariants guiding implementation and tests:

- source text remains authoritative;
- reconciliation is non-destructive; identity-group equivalence is applicable-context-dependent, without a privileged canonical member;
- identity, provenance, and source applicability are distinct;
- query-time resolution precedes broad semantic activation;
- identity hops differ from ordinary semantic hops;
- identity markers/links and provenance structures are excluded from normal subject-matter output;
- ambiguous mentions remain ambiguous rather than being forced;
- authoritative identity state does not depend on added ordinary Entity fields; shared edge properties are deliberately maintained;
- derived structures are replayable/idempotent, with explicit invalidation;
- replay on captured assignments preserves their explicit occurrence/endpoint IDs; source changes can regenerate occurrence identities, and fresh LLM extraction need not produce identical outputs;
- logical fact deduplication preserves source attribution;
- selected built-in maintenance stages have an explicit, tested interaction contract with project structures.

Deliverables: mutation/persistence matrix, ownership matrix, architecture diagram, lifecycle contract, finalized invariants, a reusable integration findings register tagged by Describe/Publish/Maintain/Retrieve, and a Stage-6 implementation/checklist with validation criteria. Stage 5.4.5 is not complete until these decisions are grounded and written down.

#### Retained scope, timing, and evolution questions

The superseded 5.4A/5.4B topics remain work to resolve through 5.4.5 and Stage 6:

- compare local chunk resolution, document pre-pass/DefinitionSummary, ordered accumulating context, post-hoc reconciliation, and hybrid strategies;
- distinguish local, document/subdocument, corpus/domain, and broader applicability; role does not determine scope;
- reuse corpus identity knowledge without overriding stronger local evidence;
- retain separate source/scoped support for a shared semantic identity link;
- preserve a link when another surviving source still supports it;
- allow contradictions and scope-specific meanings to coexist;
- exercise DOC01-only, DOC01+DOC02, and updated/removed-DOC01 corpus states.

The current source/identity chain is: original document/chunk inputs produce saved assignments in a generated identity Data source; its TextDocument graph node anchors mention markers, and deterministic publication materializes scope-bearing resolution edges. Original-input provenance remains independent of native generated-source retention. The earlier IdentityResolution helper chain is historical, not a required representation.

---



## Stage 6 — Custom processing architecture — IN PROGRESS

Current code extends the initial validated forms/custom-Task publication/retrieval through shared-source withdrawal, guarded corrections, native whole-document rebuilds and reviewed occurrence/group retirement. Standard Cognify/Remember/Update wiring, complete maintenance/retrieval and broader sequence coverage remain. See [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) for current status and the individual guides for exact fixture scope.

Goal: move manually demonstrated representations into actual Cognee processing tasks/pipelines and ensure they participate in lifecycle/provenance behavior.

### 6.1 Explicit source/intermediate representations

Source occurrences, extraction decisions and generated registered JSON sources are implemented for captured descriptions. Publisher.replace/withdraw and the relational ledger provide guarded full-source changes, retirement and currentness; extend their supported operations rather than starting another storage API. Keep domain helpers above common mechanics and original-input provenance outside materialized graph edges. Use explicit saved local reference-group UUIDs for mention Entities, and persist classification on has_identity_mention edges rather than Entity role fields.

For mentions, move from temporary occurrence indices to exact source coordinates where possible:

```text
source document/chunk id
start_char
end_char
surface_text
```

These should remain observable even if later relation extraction fails.

### 6.2 Automatic observation and identity extraction

Build the initial Describe backend as seeded passes:

1. Pull out names and reusable-form candidates; recognize explicit abbreviation definitions and generate straightforward initial-letter candidates.
2. Use those seeds for local/lexical/vector corpus lookup and contextual semantic matching.
3. Expand to shortenings and descriptive noun phrases.
4. Resolve pronouns/contextual references using earlier results and document/section context; materialize retained local groups, including pronoun-only groups, as graph mentions.

Reuse native semantic extraction and Stage-4 typed observations as useful inputs, without requiring the old prototype observation/support classes as durable graph records. Supply exact existing-node references, necessary construction recipes for required corpus-backed endpoints, variant/mention assignments, applicability and supplied-input provenance. Save the selected source forms and use controlled publication.

Prioritize representative cases through the entire integration before refining the algorithm. Existing abbreviation/variant/controller benchmarks supply evaluation fixtures, with hidden answers excluded from Describe inputs. Add small passages for missing types. Exercise saved JSON, graph ownership/contributions, identity-aware retrieval and selected update/replay cases. Initial accuracy thresholds, comprehensive language coverage and a future trained backend are not prerequisites for the first working iteration.

On source modification, validate/regenerate group/occurrence continuity separately from reevaluating interpretation. Maintain selects older records for reconsideration, invoking Describe; exact discovery triggers remain a lifecycle decision. Keep singleton/variant identities without a privileged member, persistent mention classification and explicit relationship kind. Historical mention strings do not become reusable aliases.

### 6.3 DefinitionSummary generation and hierarchical context

Generate document-level vocabulary/context automatically rather than hand-authoring it.

Compare:

- document pre-pass;
- incremental summary/context accumulation;
- hybrid strategies;
- special handling of explicit glossary/definition sections.

### 6.4 Pipeline sequencing and lifecycle integration

Treat proposal section 15's A/B full-store staging as an optional experiment for the first iteration, not a prerequisite: construct and validate a coherent candidate generation including original source updates, saved descriptions, graph/native ownership, relational paths and active indexes; promote through a guarded active-generation selection and reader/process handoff. Begin with serialized writes to promotion-copied state. Separate prepare/execute/validate/promote from extensible failure-policy handlers; existing clone probes do not establish live-snapshot or promotion guarantees. This remains a feasibility/design item, not an implemented replacement for native lifecycle orchestration.

The guarded stored-representation API, backend-neutral relational publication ledger, revision/attempt checks, caught-failure events and explicit saved-intent retry are implemented for admitted fixture operations. Extend those mechanisms to the remaining source/dependency workflows and standard entry-point hooks; do not introduce SQLite-specific bookkeeping or claim a cross-store transaction.

Implement the lifecycle selected in 5.4.4 and finalized in 5.4.5:

- implement the small B `cognify_task_transform` patch at the native STANDARD Task-list seam;
- forward it through standard Remember and full-rebuild Update, forcing the latter when customization is active;
- keep native pipeline name, route/runtime handling, data-ID/status/result behavior;
- place extraction-time custom work within transformed Cognify;
- implement derived reconciliation as idempotent Memify/Improve Tasks with explicit replay and selection rules;
- implement a source-bound loader for explicit-ID new Entities and custom_edges, with intentional existing-endpoint ownership attachment;
- aggregate all surviving assignments for a shared edge instead of allowing separate publishers to replace each other's applicability;
- retire/regenerate generated sources after original-input changes and handle temporary endpoint loss during generated-source rebuild;
- verify metadata attached automatically by DataPoint persistence versus metadata requiring explicit graph-interface writes.

The exact Task order must follow the 5.4.5 decision. Proposal section 25 refines the first sequence: prepare text/chunks, run identity Describe, extract semantic relations with explicit bindings, then assemble/save and publish. Identity-aware extraction/conversion replaces the relevant native Task before final persistence. Maintain reuses these functions for affected inputs; original-versus-generated publication contexts and cross-batch document state must be tested.

Lifecycle validation should cover direct Cognify, standard Remember, overlapping ingest, transformed full-rebuild Update, maintenance replay, and cleanup after source removal. Test no-transform native behavior and unsupported combinations for the B patch. Verify custom side effects explicitly rather than assuming native rollback handles them.

**Requirement:** source/support/derived structures must have documented, testable lifecycle behavior. Native compatibility is preferred; a small explicit cleanup/repair path is acceptable where native Forget is insufficient. Avoid allowing rare deletion behavior to dominate the representation design.

### 6.5 Registered identity-aware retrieval

Package the Stage-5.3 proof of concept behind a custom Retriever/SearchType using Cognee graph/vector interfaces. Perform query-time resolution before scope-aware identity expansion and semantic-neighborhood union. Adapt privileged canonical selection to singleton/identity-group handling; check edge contributions, follow mention references directionally and preserve unresolved mention classification. Native retrieval does not acquire these rules automatically. Preserve provenance under logical fact deduplication and provide semantic, source-aware, explanation, and graph-management modes as warranted.

Keep RAG as a reference/fallback and control conversation/session state during comparisons. Restore and strengthen the Stage-5.3 benchmark so it remains correct after subsequent source ingestion and maintenance.

### 6.6 Replay, mutation, and lifecycle regressions

Add explicit multi-document interpretation tests: updating DOC01 preserves independent DOC02 assignments/owners and contextual traversal, while DOC02 assignments that used DOC01 context are correctly identified for reevaluation. Use input provenance in maintenance and retrieval; generated-source grouping alone does not prove independence.

Separately investigate model-assisted Describe consistency using repeated identical inputs, meaning-preserving edits, definition/referent changes and end-to-end processing. Freeze graph/chunk/candidate context for isolated Describe runs. Compare benchmark-aligned occurrences, target/group agreement, resolution status, applicability, correctness and unrelated-assignment churn. Proposal section 12 records the plan; no consistency result or stabilization policy is claimed.

Design regression suites directly from 5.4.5's operation sequences and expected outputs. Each case records its fixture, initiating operation, intermediate/failure eligibility and expected saved records, graph properties/IDs/owners, applicable traversal and consumed-index results. Use captured extraction/resolution outputs for deterministic lifecycle assertions rather than requiring fresh LLM runs to agree.

Organize coverage into description/plan checks, real-backend publication/ownership integration, and maintenance-plus-retrieval scenarios. Fault injection and replay exercise partial writes and saved-record/graph consistency. Proposal section 11 records the initial scenario matrix. This is the broader scenario inventory. The current captured subset is implemented; the session handoff and fixture guides record passing tests and gaps. The inventory is not a claim that every listed scenario has passed.

Turn the matrices/invariants into focused regression scenarios:

- re-ingest a source and rerun maintenance without duplicate derived objects;
- add an overlapping source without losing identity/reconciliation state;
- change a definition/alias and invalidate or recompute affected resolution;
- remove one source while retaining facts/links supported by another;
- preserve ambiguity and negative/non-equivalence controls;
- preserve source attribution across logical duplicates and identity closure;
- document stale-state detection/repair and differences between native incremental Update and customized full rebuild;
- store two identically named occurrences as distinct Entity IDs, with deterministic replay;
- retain mention classification after resolution removal and exclude unresolved mentions from singleton lookup;
- withdraw one contribution from a shared edge and verify remaining applicability/owners;
- retain an existing endpoint without rewriting its fields and recreate a solely generated-source-owned endpoint after rebuild;
- test or exclude optional consolidation/remapping for occurrence Entities;
- relate a new document to existing corpus singletons/groups while preserving same-surface non-equivalence;
- preserve a validated occurrence ID while reconsidering its resolution under changed document/corpus context;
- exercise declared selection of older unresolved mentions after a relevant new corpus arrival;
- reject conflicting saved-representation updates and preserve unrelated records;
- inject saved-state, graph, index and completion-recording failures; retry without regenerating unchanged interpretation or adding duplicate contributions;
- ensure superseded publication cannot mark a newer description current, and valid other-source contributions remain eligible during an affected-source failure;
- verify A/B candidate path isolation and coherent graph/saved-record/relational/vector state, and that failed candidates leave the active generation unchanged;
- reject promotion from a stale base and inject failures around generation selection/acknowledgement and adapter rebinding;
- test extensible recovery handlers without changing core coordinator behavior, including preservation of captured Describe output.

### Post-Stage-6 checkpoint

Stop and reassess the architecture before moving into stronger schemas/ontologies. Review the reusable integration findings in section 18 of cognee_extension_architecture_reference_v1.6.2.md: attach identity implementation/evidence to Describe/Publish/Maintain/Retrieve findings and identify which mechanisms are demonstrated versus identity-specific. Review:

- selected identity source/edge representation, singleton/identity-group semantics and mention classification;
- semantic/support/source graph layers and ownership/mutation contract;
- identity resolution quality;
- retrieval modes;
- update/delete behavior;
- remaining limitations of Cognee's pipeline and storage abstractions;
- B patch maintenance cost, supported routes, and local/remote portability.

This remains the agreed **check-in after Stage 6**, before proceeding to Stages 7–10.

---

## Stage 7 — JSON-schema-generated models and ontology grounding — PLANNED

Investigate whether each knowledge representation's concepts, relationship meanings and domain rules should be expressed as a domain ontology, a lightweight vocabulary/schema, or a combination. Examine how those semantics guide Describe/Publish/Maintain/Retrieve while keeping native storage IDs, ownership and lifecycle procedures explicit. This is an investigation, not a prerequisite for the current identity integration or a commitment to an ontology formalism.

Use identity examples and the activity-tagged findings register in the extension reference as concrete inputs.

Explore:

- generating DataPoint/extraction structures from JSON Schema or ontology-derived schemas;
- importing or mapping ontology concepts into Cognee-compatible representations;
- using ontology constraints/instructions without requiring the ontology to own the entire graph;
- encoding counterexamples and interpretation rules in LLM instructions;
- schema evolution across versions.

---

## Stage 8 — Scientific Claim / Measurement / Evidence model — PLANNED

Use measurements/scientific records as a second worked example of Describe/Publish/Maintain/Retrieve. Carry forward the integration findings from identity; verify which ID, publication, dependency, maintenance and retrieval mechanisms transfer before generalizing. Measurement semantics and scientific support policies need their own domain decisions.

Develop stronger scientific semantics for:

- claims versus observations;
- measurements;
- uncertainty;
- units and physical quantities;
- calibration/revision;
- experimental conditions;
- interpretation versus direct measurement;
- evidence/provenance;
- temporal validity and supersession.

This stage should build on source/provenance structures rather than conflating scientific claims with ordinary semantic Entities.

Scientific assertion justification belongs here: the representation of supporting evidence and derivations, scientific support/entailment checks, evidence weighing and confidence policies. Stage 5.4.5 establishes only that provenance/ownership alone do not provide scientific support; the earlier fixtures do not select a scientific reasoning model.

---

## Stage 9 — Schema and ontology evolution — PLANNED

Investigate:

- changing DataPoint/schema definitions over time;
- adding/removing/modifying fields and classes;
- migrations of existing graph content;
- ontology/schema versioning;
- compatibility of old and new extraction outputs;
- maintenance of derived/materialized semantic views after schema changes.

---

## Stage 10 — Project-specific ingestion architecture — PLANNED

Synthesize results into an architecture for scientific/domain-specific evolving LLM memory.

Expected concerns include:

- open-world semantic extraction;
- selected strongly typed semantic islands;
- explicit source intermediates;
- identity reconciliation;
- hierarchical document/corpus context;
- claims/measurements/evidence;
- graph evolution and truth maintenance;
- retrieval modes;
- provenance-aware explanation;
- self-hosted/open-weight model compatibility;
- extensibility to domain ontologies without requiring rigid ontology-first ingestion.

---

# Current immediate work — 2026-10-26

Current stage: **Stage 6. Accepted implementation step 4 / M3 is complete (2026-10-25). Step 5 / M4 is in progress: S2, S3a, S3b and S4 are complete (2026-10-26), S1, the public retriever, is complete (2026-10-26), and the source-aware mode is next.** Stage-5.4.5 architecture/handoff review is complete. Bounded native publication, shared-source withdrawal, correction, text/rechunk rebuild, partial occurrence removal and unresolved/resolved group-retirement checkpoints have been implemented and independently exercised by the user.

**Step 4 close.** On 2026-10-25 the user asked for the small tracked follow-ups that needed no decision. Branch `stage6-cleanups` replaced the glossary root's `elif` chain with a command table, moved the re-confirm's record writes into `records.py`, added an end-to-end property and a mutant to the cascade check, kept a saved retirement plan on an erasure-retry reconcile and fixed `forget`, `readd` and `withdraw` on a single-source root. No admission rule or retrieval result changed. A probe of an outside deletion of the cited Helios Entity found a review deadlock: each withheld decision blocks the other's replacement. The user decided how to resolve it and deferred the fix to step 5 S2 (removal). The user then ran two fixtures with real NVIDIA embeddings on their Mac: a glossary edit with two re-confirms (22 PASS, 0 FAIL) and a cascade forget with a crash and recovery (16 PASS, 0 FAIL). The user decided that the remaining tracked follow-ups stay documented limits and declared step 4 done. See "Step-4 cleanups and close — 2026-10-25" below and [the checkpoint history](docs/stage6_checkpoint_history.md#cleanups-and-step-4-close-2026-10-25).

**Where the rest of step 4 went.** Source-removal hooks, dataset Forget (T20) and endpoint gaps during a generated-source rebuild go to step 5, with the outside-deletion fix. Facts as saved records and Describe-driven corpus matching go to step 6. The verification and recovery item is closed in practice by the ledger, occurrence, chain and cascade checks, each with mutants. The [Stage-6 handoff](results/cognee_identity_stage6_handoff.md#step-4--m3-closing-summary-2026-10-25) has the closing table.

**Step 5 discussion and S2.** On 2026-10-25 the user and the assistant went through the seven step-5 work units and U1 to U6. The user chose lab `add`, `cognify`, `remember` and `update` entry points that run Cognee's standard Tasks with the lab's, with no Cognee patch. Native deletes stay unwrapped. The lab detects them, and lab `forget` is the supported delete. Step 5 S2, "deletes outside the lab", merged into `main` at `c711997` on 2026-10-26. `status` lists a source whose native copy Cognee deleted or changed, `reconcile` refuses it, and `forget` erases the lab's copy afterwards. A kept decision may keep citing an Entity deleted outside the lab, and no publication recreates it. `forget-dataset` forgets a dataset with the Data no lab source publishes, and repairs a root after a native dataset forget or prune. An append-only removal record keeps every Entity UUID a lab operation removed, and no removed UUID is used again (the user's decision of 2026-10-26). The assistant and its subagents ran `journey all` on the user's Mac with loopback embeddings: 1775 PASS and 0 FAIL in 110 runs. See "Deletes outside the lab — 2026-10-26" below and [the checkpoint history](docs/stage6_checkpoint_history.md#step-5-s2-deletes-outside-the-lab-2026-10-25-to-2026-10-26).

**Lab entry points (S3a).** Step 5 S3a merged into `main` at `3da0d7f` on 2026-10-26. `entry.py` holds the lab's `add`, `cognify` and `remember`. `cognify` runs Cognee's `run_pipeline` under the pipeline name `cognify_pipeline` with Cognee's chunking Tasks, then one lab Task that stamps the original and publishes the captured description. No lab write carries Cognee's run ID, and the run passes no rollback handler, so a failed run removes nothing and the ledger decides the recovery. The `fixture` command builds doc01 this way, and a plain `cognee.cognify` (`native-cognify`) skips every stamped file with no LLM call. The fix round after `/pstack:thermos` removed the native-copy exemption for a failed first publication, because no lab cause removes its chunks, and made `cognify` refuse more than one source until S3b tests it. The assistant's subagent ran `journey all` on the user's Mac with loopback embeddings: 1818 PASS and 0 FAIL in 115 runs. See "Lab entry points — 2026-10-26" below and [the checkpoint history](docs/stage6_checkpoint_history.md#step-5-s3a-the-lab-entry-points-2026-10-26).

**Every builder on the entry points (S3b).** Step 5 S3b merged into `main` at `3207a72` on 2026-10-26. `multi-fixture`, `chunked-fixture`, `glossary-fixture [--chain]` and `readd` now register and publish through the lab's `add` and `cognify`, and the hand-built creation path is gone. `entry.remember_in_order` adds, then cognifies, each source in publication order and stops at the first failure before the next source is added, so no original is left registered without a stamp. `cognify` takes one source, because Cognee runs the items of one run concurrently and doc03 cites doc01's published decisions. A source that was added but has no publication is refused `not_published`. `reconcile` of an already-published source still reads the chunks Cognee holds, because `cognify` would write them again before the verify. The assistant's subagent ran `journey all` on the user's Mac with loopback embeddings: 1853 PASS and 0 FAIL in 120 runs. See "Every builder on the entry points — 2026-10-26" below and [the checkpoint history](docs/stage6_checkpoint_history.md#step-5-s3b-every-builder-on-the-entry-points-2026-10-26).

**The lab update (S4).** Step 5 S4 merged into `main` at `399ce94` on 2026-10-26. `entry_update.update` edits a published source's original: one lab Task under `cognify_pipeline` calls `publisher.replace` with a `TextChange`, so the occurrence-map admission and the incremental identity revision are unchanged. Inside the text change the lab stamps the original again right after the memory-only forget, and Cognee's standard Tasks rebuild the chunks with the lab's untagged context, so a rollback or a startup recovery of the run never finds them. Every text-edit command now runs through `update`, `reconcile` of a failed edit through `replace_text`, and the hand-built edit path is gone. An edit of a natively deleted source is refused `native_deleted` with the forget hint. The fix round after `/pstack:thermos` moved the chunk builders into `native_chunks.py` and the edit half into `entry_update.py`, made `describe_edit` a required argument, and named the crash window between the forget and the stamp in the guide. The assistant's subagent ran `journey all` on the user's Mac with loopback embeddings: 1953 PASS and 0 FAIL in 131 runs. See "The lab update — 2026-10-26" below and [the checkpoint history](docs/stage6_checkpoint_history.md#step-5-s4-the-lab-update-2026-10-26).

**The public retriever (S1).** Step 5 S1 merged into `main` on 2026-10-26. Importing `cognee_lab.identity.search` adds the member `IDENTITY` to Cognee's closed `SearchType` enum and registers the lab's retriever, so `cognee.search(query, query_type=SearchType.IDENTITY, datasets=[name])` returns what the CLI `retrieve` returns, with no LLM call. The import refuses any Cognee other than 1.6.2 and any Python other than 3.12, refuses an `IDENTITY` member the lab did not add, and self-tests the member at import, removing it when a check fails. Only an Entity that a served source of the searched dataset constructs can seed a search, because probe E5 showed another dataset's Entity displacing the lab's seed. Refusals (`dataset_required`, `access_control_on`, `scope_not_built`, `mode_not_built`, `config_invalid`) fail before Cognee logs the query. The search guide warns that Cognee's other search types serve withheld and failed state. A conformance check scores `IDENTITY` searches on a DOC01 fixture against the Stage 5.3 benchmarks and fails when a case moves from its committed baseline. Its describer was written after its author read the hidden answers, so it is a conformance check, not a benchmark. Two `/pstack:thermos` rounds and their fix rounds followed. The assistant's subagents ran `journey all` on the user's Mac with loopback embeddings: 2022 PASS and 0 FAIL in 140 runs. See "The public retriever — 2026-10-26" below and [the checkpoint history](docs/stage6_checkpoint_history.md#step-5-s1-the-public-retriever-2026-10-26).

**Next task.** Build the source-aware mode, which needs the real document names after a text edit first, then the other step-5 delivery items: grouped delivery, annotation states, span-scoped variants, ranking and seeding changes measured against the conformance baseline, offline diagnostics and consumed-store admission. Check whether the endpoint gaps during a rebuild are closed. The user approved the outside-benchmark prototype for after S1 on 2026-10-26, and confirmed the assistant's reversible S3a decisions the same day. The session handoff lists the next steps.

**Step-4 history.** Every text change is admitted through one **general occurrence map**, which the user approved on 2026-10-21. It replaced three separate admission modes, one each for removal, addition and regrouping. Captured fixtures exist for removal, retirement, addition, split, combination and one mixed addition/removal edit. Facts are generated again from fresh groups, never transferred. See "General occurrence map — 2026-10-21" below for the reason and [the checkpoint history](docs/stage6_checkpoint_history.md#general-occurrence-map-approved-2026-10-21) for the rules. On 2026-10-22 the unchanged-text correction was folded into the same admission, and the rules were relaxed so an edit may introduce a new derived Entity, drop an unused one and change document-scoped variants. Four captured fixtures now show a changed interpretation to a new Entity and to unresolved, and a document's HC name turned into a local mention and back ([reinterpretation guide](docs/stage6_identity_reinterpretation.md)). A `forget` command now removes a source nothing depends on, and `readd` brings it back at the next revision with new IDs ([forget guide](docs/stage6_identity_forget.md)). A refactor of the ledger and the retiring operations, with no behavior change, followed. On 2026-10-23 the first dependencies checkpoint (step-4 item 3) replaced the refusal of a dependent-document edit: the edit withholds from retrieval only the decisions that read what changed, a moved span is refreshed automatically, and a reviewer re-confirms or replaces the rest ([dependencies guide](docs/stage6_identity_dependencies.md)). Later on 2026-10-23 Checkpoint I made `forget` always erase. It accepts a current, withdrawn or failed-first-publication source and leaves a tombstone of identifiers with no content. A forget that changes another source's decisions needs the token of its dry run, and each dependent then loses the decisions that cited the source in a removal revision ([forget guide](docs/stage6_identity_forget.md)). A small round the same day made a re-add report files that differ from the forgotten revision and made tombstones carry earlier lives' ID lists. Checkpoint J1, also on 2026-10-23, lets a resolution or variant assignment cite another source's decision as a saved record. Admission refuses a cycle between sources, and a citing decision is withheld, with no rows written, whenever what it cites is withheld, changed or gone, so a re-confirm upstream releases it on the next read ([chains guide](docs/stage6_identity_chains.md)). Checkpoint J2, on 2026-10-24, made erasure cascade down a chain. A dependent that cites a record another dependent's removal removes gets its own removal revision one level below, at its longest path. One dry run lists every level, one token covers them and one confirmation writes them in level order, resuming in order after a crash. Each removal names the records it removes and the removed records it cites, and admission binds them back to the tombstone ([forget guide](docs/stage6_identity_forget.md#the-cascade)). Four review rounds shaped it. Checkpoint K, also on 2026-10-24, answered the readers of an Entity or a saved record that changed or went. A lab command, `edit-entity`, edits a native Entity with no ledger row, and live validation withholds the decisions that cite it. A reviewer re-confirms or replaces such a decision, and `replace-citation` re-cites or drops a citer of a removed record. Admission refuses a record key that comes back while another source cites it (`record_key_reused`) and a corpus input of a mention UUID (`mention_input`). The kind changes run on a root where other sources read doc01, and their citers follow the citation rules. Every path that removes a record now goes through one removal helper ([entity edits guide](docs/stage6_identity_entity_edits.md)). Two review rounds shaped it. At that point no step-4 item was left that could start without the user.

Three tools check the demonstrated operations. The project verify skill drives the fixture CLI through real Cognee stores. The identity-ledger check runs every bounded sequence of publication-ledger calls. The occurrence check compares the admission rules with an independent oracle on every small world and breaks each rule in turn. The chain check compares the cycle rule and withholding down a chain with an oracle on every citation graph of up to four sources. Since Checkpoint J2 its cascade half checks the erasure cascade on 34,752 worlds of those graphs: levels, write order, resume, failed removals and the refusal to retire a source that holds a removal. Since Checkpoint K it also checks `record_key_reused` on 814,500 key-reuse cases, for resolution and variant keys. The session handoff records the verification routine.

Step 5 owns the standard entry points, dataset Forget, endpoint gaps during a rebuild and broader retrieval/delivery/offline diagnostics. On 2026-10-25 the user replaced the B Task-transform patch with lab entry points and the removal hooks with detection. S2 closed dataset Forget and the outside-deletion deadlock on 2026-10-26. S1 added the public retriever's semantic mode and the conformance check on 2026-10-26. Step 6 owns seeded rules/model Describe and its separate quality/consistency evaluation, Describe-driven corpus matching and, since the user's decision of 2026-10-24, facts as saved records. Step 4's changed-meaning item finished with the captured fixture writer. A/B staging, incremental chunk reuse, comprehensive replay, automatic orchestration and metrics tooling remain deferred; they are not new step-4 gates. The post-Stage-6 architecture check-in and later scientific stages remain unchanged.

## Historical revision record

Entries below retain the decisions and evidence status at their stated date. They do not override the current status above or SESSION_HANDOFF.md. References to earlier “next reviews” document the sequence that led to the accepted handoff.

## Revision record — 2026-10-27 (docs pass)

- Rewrote `docs/SESSION_HANDOFF.md` as a short resume document: the current state, the next task with the decisions made and those that need the user, one grouped list of tracked follow-ups, the code map, the commands, the verification routine and how the work is run.
- Moved the handoff's dated checkpoint history verbatim into `docs/stage6_checkpoint_history.md` and pointed every inbound link and section reference at it.
- Shortened the Stage 6 row of "Progress at a glance" to the current state and a pointer to the history, and noted in the 5.4.4 row that the user replaced the B Task-transform with lab entry points on 2026-10-25.
- Added `support/md_link_check.py`, which checks that every relative Markdown link and anchor resolves. No code under `src/` changed. On `main` at `4e7a33b` the unit suite gave 699 passed, run by the assistant on the user's Mac.

## Revision record — 2026-10-26 (step 5 S1)

- Recorded step 5 S1, the public retriever, built and reviewed on branch `stage5-s1` and merged into `main` on 2026-10-26. See "The public retriever — 2026-10-26" below.
- Recorded the user's decisions of 2026-10-26: the guarded enum extension, the refusal of a search over several datasets, the Stage 5.3 benchmark in S1 as a conformance check, QRY03 and QRY04 as an accepted gap, the proposed defaults, and the confirmation of the assistant's S3a decisions.
- Recorded eight known limits as follow-ups, among them the `text_<md5>` document name after a text edit, seed crowding, Cognee's other search types serving withheld and failed state, and the need for an independent describer or an outside benchmark.
- Set the next task: the source-aware mode and the other step-5 delivery items, then the outside-benchmark prototype.

## Revision record — 2026-10-26 (step 5 S4)

- Recorded step 5 S4, the lab's `update` with every text edit on it, built and reviewed on branch `stage5-s4-update` and merged into `main` at `399ce94` on 2026-10-26. See "The lab update — 2026-10-26" below.
- Recorded four known limits as follow-ups: the crash window between a text change's forget and its stamp, a `source_missing` stop before the `native_deleted` refusal after a native forget of the whole original, `erasure.py` importing a fixture class (step 6), and revision files written before the `expected_revision` check.
- Set the next task: spec the S1 retrieval entry, the semantic mode first.

## Revision record — 2026-10-26 (step 5 S3b)

- Recorded step 5 S3b, every creation command and `readd` on the lab's `add` and `cognify`, built and reviewed on branch `stage5-s3b-entry` and merged into `main` at `3207a72` on 2026-10-26. See "Every builder on the entry points — 2026-10-26" below.
- Recorded two known limits as follow-ups: later sources never added after a failure on the first source, and no recovery for a registered source whose `cognify` crashed before the ledger began.
- Set the next task: step 5 S4, the lab `update`.

## Revision record — 2026-10-26 (step 5 S3a)

- Recorded step 5 S3a, the lab's `add`, `cognify` and `remember` over Cognee's `cognify_pipeline`, built and reviewed on branch `stage5-s3a-entry` and merged into `main` at `3da0d7f` on 2026-10-26. See "Lab entry points — 2026-10-26" below.
- Recorded the assistant's reversible S3a decisions, which await the user's confirmation.
- Set the next task: step 5 S3b, then S4.

## Revision record — 2026-10-26 (step 5 S2)

- Recorded the step-5 discussion of 2026-10-25: lab entry points instead of the B patch, detection of native deletes instead of hooks, a lab dataset forget, and the retrieval answers to U1 to U3.
- Recorded step 5 S2, "deletes outside the lab", built and reviewed in three parts and merged into `main` at `c711997` on 2026-10-26, with the user's answers to Q1 to Q3 and the decision never to reuse a removed Entity UUID. See "Deletes outside the lab — 2026-10-26" below.
- Set the next task: step 5 S3a, the lab `add`, `cognify` and `remember` entry points, awaiting the user's confirmation of the assistant's reversible decisions.

## Revision record — 2026-10-25 (step-4 close)

- Recorded the step-4 cleanups on branch `stage6-cleanups` and the real-embedding runs the user ran on their Mac on 2026-10-25. See "Step-4 cleanups and close — 2026-10-25" below.
- Marked step 4 / M3 complete, by the user's decision of 2026-10-25, and replaced the stale list of remaining step-4 areas with where each went: step 5, step 6 or a documented limit.
- Set the next task: step 5, starting with a discussion session with the user on the seven work units and U1 to U6.

## Revision record — 2026-10-24 (entity edits K)

- Recorded Checkpoint K, the readers of a changed or retired Entity or record, built and reviewed on branch `stage6-entity-edits` on 2026-10-24. It implements the user's decisions of 2026-10-24 on kind changes and native Entity edits. See "Readers of a changed or retired Entity or record — 2026-10-24" below.
- Set the next task: none in step 4 can start without the user. Facts as saved records need a discussion, the non-identity example needs architecture planning and step 5 needs a retrieval contract.

## Revision record — 2026-10-24 (cascade J2)

- Recorded the user's decisions of 2026-10-24: a representation-kind change retires the old group and declares a fresh one; a direct edit of a native Entity withholds the decisions that depend on it (`input_changed`); facts as saved records move to step 6, with the model that produces semantic output, after a discussion with the user; the non-identity example is written in as the planned example, with no work on it now.
- Recorded Checkpoint J2, the erasure cascade down a chain, built and reviewed on branch `stage6-cascade` on 2026-10-24. See "Erase down a chain of decisions — 2026-10-24" below.
- Added "Planned non-identity example — 2026-10-24" below.
- Set the next task: Checkpoint K, the readers of a changed or retired Entity or record.

## Revision record — 2026-10-24 (chains J1)

- Recorded the user's decisions of 2026-10-23 for chains: decisions only are citable, with the citation format and chain logic generic over record type; withholding spreads down the whole chain, derived at retrieval, with the reason `input_changed`; cycles refused; erasure cascades down the chain (J2). Facts as saved records need a separate discussion with the user first. The non-identity example is deferred as later work.
- Recorded the re-add follow-ups F1 and F2, merged into `main` on 2026-10-23, and Checkpoint J1. See "Withhold down a chain of decisions — 2026-10-23" below.
- Set the next task: Checkpoint J2, the erasure cascade down a chain.

## Revision record — 2026-10-23 (erasure)

- Recorded the user's decisions for erasure: one `forget` that always erases; a tombstone of identifiers and scrubbed plans and event messages; the caller's files kept; dependents' decisions removed, not withheld, reversing the earlier lean; confirmation by a dry-run token; re-add from the caller's files; forget of any source; old formats not read.
- Recorded Checkpoint I. See "Erase a source and remove what depended on it — 2026-10-23" below.
- Set the next task: a small round for follow-ups F1 and F2, then the chains checkpoint (saved-record inputs citing decisions only, withholding and erasure down the chain, cycles refused). Facts as saved records need a discussion with the user first. The non-identity example is deferred as later work.

## Revision record — 2026-10-23 (dependencies)

- Recorded the user's decisions for dependencies: withhold affected decisions until refreshed, per decision; refresh starts in the edit; a reviewer may re-confirm; a glossary as the first example; the reasons "input changed" and "input removed". Erasure's effect on dependents is deferred, with the user leaning toward withhold by default and an explicit per-decision removal option.
- Recorded Checkpoint H. See "Withhold the decisions an edit affects — 2026-10-23" below.
- Set the next task to erasure's effect on dependents, starting with the user's decisions. Saved-record inputs and the transitive case follow.

## Revision record — 2026-10-22 (ledger refactor)

- Recorded a refactor with no behavior change: a transition table in `RecordStore.begin`, a typed publication row, one attempt frame for replace, withdraw and forget, and a consolidated ledger model, checked against main by an equivalence harness and identical mutant output.
- Set the next task to dependencies, starting with the user's decisions.

## Revision record — 2026-10-22 (forget)

- Recorded the user's decisions for `forget`: two intents (cleanup and erasure), the definition of a dependent, a kept record of the last revision so a re-add continues the numbering, and retiring the reviewed roots as history.
- Recorded Checkpoint F. See "Forget a source nothing depends on — 2026-10-22" below.
- Set the next task to a ledger refactor with no behavior change, then dependencies.

## Revision record — 2026-10-22 (changed interpretation and kind change)

- Recorded Checkpoint E: four captured fixtures for a changed interpretation and a representation-kind change. See "Changed interpretation and kind change — 2026-10-22" below.
- Recorded the user's decisions for `forget` and set it as the next task.

## Revision record — 2026-10-22 (one admission for every replacement)

- Recorded the user's decisions: relax the recipe rule, derive a new reusable Entity's UUID from source, revision and key, let a source drop an Entity it no longer uses, fold the unchanged-text correction into the general admission, allow document-scoped variant changes in text edits, and defer corpus-scoped ones to dependencies.
- Recorded Checkpoint D. See "One admission for every replacement — 2026-10-22" below and [stage6_checkpoint_history.md](docs/stage6_checkpoint_history.md#one-admission-for-every-replacement-2026-10-22).
- Set the next task to four captured fixtures, reviewed with the user first.

## Revision record — 2026-10-22 (step-4 decisions)

- Recorded the user's decisions that a changed group decision means a fresh group, and that a successor record for retired group IDs waits for dependencies or the step-5 retrieval contract. See [Step-4 decisions, 2026-10-22](docs/stage6_checkpoint_history.md#step-4-decisions-2026-10-22).
- Recorded which remaining step-4 items can be specified now and which wait for a dependency policy. Proposed order: changed interpretation, then representation-kind changes, while the user sketches a real dependent-source scenario.
- Updated the Stage-6 design handoff's step-4 list to the general occurrence map.

## Revision record — 2026-10-22 (mixed occurrence revision)

- Recorded Checkpoint C: `revise-occurrences` publishes one edit that removes, keeps and adds occurrences of a continuing group and retires another group, with no admission change.
- Set the next task to choosing the next step-4 item with the user.
- Added a CI step that runs the occurrence check at its default bound after the unit tests, with a 30-minute job timeout.
- Brought "Current immediate work" up to date with the general map, and added dated entries for the general map and the mixed revision that record why the plan changed and how the remaining step-4 work changed.

## Revision record — 2026-10-21 (general occurrence map)

- Recorded the user's approval of one general occurrence map with rules stated over occurrences and groups, and the two policy decisions: strict peel-off, and a fresh group when nothing survives.
- Recorded Checkpoint A: the general admitter and its bounded exhaustive oracle check, with no runtime behavior change.
- Recorded Checkpoint B: the old admission modes deleted, every text change admitted through the general map, saved plans read through a converter, and `journey all` unchanged at 695 PASS.
- Set the next task to the mixed addition/removal case.

## Revision record — 2026-10-11

- Replaced the stale 5.3.1 current-status marker with 5.4.5.
- Recorded demonstrated 5.3 query-time resolution and its regression under overlapping ingest.
- Replaced 5.4A/5.4B with refined 5.4.1–5.4.5, retaining scope/timing/evolution questions.
- Recorded overlapping-ingest mutation findings, native retrieval characterization, and the preferred B lifecycle extension proposal and limitations.
- Expanded 5.4.5 to investigate Cognee's actual behavior on support/reconciliation and other graph artifacts before assigning ownership or locking representation.
- Updated architecture principles and Stage-6 sequencing/retrieval/lifecycle requirements; retained the Stage-6 checkpoint and planned Stages 7–10.
- Did not mark the B patch, 5.4.5 experiments, or final representation as implemented.

## Revision record — 2026-10-12

- Marked 5.4.5.1 complete for the agreed characterization scope and moved immediate work to 5.4.5.2.
- Incorporated source/vector/relational baselines, Improve/Memify, both Update routes, watermark visibility, source/dataset deletion, custom source-bound scientific fixtures, and read/bookkeeping controls.
- Recorded shared-store retrieval scope, stale helper/evidence/index behavior, recursive ownership propagation, and cached-session cleanup versus registry/history retention.
- Retained explicit measured/source-inspected/untested boundaries; one default-model Update profile is diagnostic and the scientific classes are prototypes.
- Kept authority/provenance decisions, representation, lifecycle/invariants, the preferred B extension, and cleanup/replay/index/evidence repairs in their later substages. Stage 5.4.5 as a whole and Stage 6 remain unfinished.

### Requirements review update — 2026-10-12

- Created a persistent requirements review record for the first two principles, revised proposed wording, validation criteria, and eight pending review items.
- Added the node/relationship mutation inventory and label-versus-identity distinction to the findings report, with source-only optional deletion/rewiring/migration profiles explicitly marked.
- Stage 5.4.5.1 remains complete for its scoped characterization; 5.4.5.2 remains in review. No physical representation or operation enforcement implementation has been chosen or applied.

### Requirements scope correction — 2026-10-12

- Applied the user's boundary: provenance/ownership do not establish scientific support, with scientific justification requirements deferred to Stage 8.
- Kept 5.4.5 focused on operational authority, source/run attribution, lifecycle ownership, mechanical dependencies, source/version identity, and backend metadata/reference maintenance.
- Narrowed review item 4 accordingly; no scientific assertion/evidence or reasoning policy is being adopted now.

## Revision record — 2026-10-13

- Recorded the initial generated-source/edge representation and preliminary ownership matrix in a dedicated proposal.
- Adopted singleton and identity group terminology for current design; retained canonical terminology only as historical experiment descriptions.
- Omitted separate singleton/variant markers and per-assignment support nodes; kept an explicit persistent mention marker and distinct occurrence UUIDs.
- Selected generated-source document-level endpoint retention and contribution-bearing shared resolution edges.
- Advanced .2–.3 together without declaring their final deliverables complete; made operation walkthroughs toward .4 the immediate work.
- Updated Stage-6 implementation/regression tasks without adding stages or moving the post-Stage-6 checkpoint. Scientific support remains Stage 8.
- Recorded no implementation, combined runtime compatibility result or traversal performance benchmark.


### Integration-methodology framing update — 2026-10-13

- Recorded Describe/Publish/Maintain/Retrieve as the recurring knowledge-integration activities in extension-reference section 18.
- Added an activity-tagged findings register, including explicit representation semantics, durable descriptions independent of graph materialization, and boundary/consumed-representation verification.
- Noted the possible ontology connection as a Stage-7 investigation, with identity examples retained now and a second measurement/scientific worked example in Stage 8.
- Added findings transfer to the Stage-6 checkpoint. No new stage, universal integration framework, ontology choice or runtime result is claimed.


### Sequence-driven regression planning — 2026-10-13

- Plan test suites around each reviewed operation sequence and its expected saved-record, graph/ownership, retrieval and consumed-index results.
- Use deterministic captured inputs, isolated real-backend integration fixtures, and failure/retry cases; do not require repeated fresh LLM extraction to be identical.
- Keep test implementation in Stage 6, with design-dependent probes in .4 where needed. No tests or runtime results were added here.


### Multi-document and Describe consistency update — 2026-10-13

- Added paired independent/dependent multi-document regressions so provenance must be used in selection, retirement and retrieval.
- Added a Describe variability investigation separate from deterministic publication/lifecycle fixtures, with repeated same inputs and controlled small edits.
- Retained the distinction between stable occurrence identity and changing interpretation; no requirement for fresh LLM outputs to be identical or new acceptance policy is adopted.


### Describe corpus scope clarification — 2026-10-13

- Made corpus candidate discovery and contextual identity linkage explicit responsibilities of Describe for new and modified documents.
- Separated occurrence identity preservation from interpretation reuse; captured candidate/context inputs remain maintenance dependencies.
- Assigned older-record reconsideration to Maintain and recorded the open triggering question for newly available candidates.
- Added corresponding Stage-6 tests without selecting algorithms or automatic whole-corpus replay.


### Stored representation API and completion review — 2026-10-13

- Recorded a shared saved-description mutation API as an agreed direction, with domain-specific helpers above common guarded record operations.
- Made failure/retry coordination the next .4 review, including captured-intent retry, exact-revision completion and unaffected-contributor eligibility.
- Added API/fault-injection regression scenarios; no implementation, atomicity guarantee or newly passed tests are claimed.


### A/B staging and recovery extensibility proposal — 2026-10-13

- Added whole-store candidate-generation staging as an initial feasibility proposal, including source updates and consumed derived stores rather than copying only one identity record/subgraph.
- Distinguished validated generation selection from overwriting open database files, and record revision from corpus generation.
- Added snapshot/path/reader/promotion tests and modular recovery handlers driven by observed failures.
- Retained prior failure responses within candidates and the in-place option where needed. No live-snapshot, atomic promotion or runtime recovery implementation is claimed.


### A/B complexity boundary — 2026-10-13

- A/B is optional for the first iteration and does not block architecture handoff or basic publication/maintenance implementation.
- Keep pending-state/captured-intent retry as a viable baseline; reassess A/B against actual complexity and copying costs, and defer it if warranted.
- Preserve narrow extensibility points rather than requiring a general snapshot/promotion framework now.

### Chunkless identity-source simplification — 2026-10-14

The initial generated identity source is one authoritative JSON document registered as Cognee Data. Its TextDocument graph node anchors mention markers; original document chunks locate occurrences. Generated identity prose, generated DocumentChunks and generated chunk IDs are unnecessary initially. Publish consumes structured records through custom Tasks; calculate_chunk_graphs remains an optional chunk-processing seam rather than the required identity loading path.

Finalize the saved occurrence/relationship/construction forms and coordinator completion metadata during the current review. Stage 6 must live-test this combined chunkless source-document/marker publication, replay and source lifecycle path. This simplifies the representation without changing the six requirements or adding a new stage.

### Local reference grouping decision — 2026-10-14

Select paragraph-local reference groups with multiple exact text ranges, one saved group record and one mention Entity, combined with a deliberate reference-selection policy. This supersedes one node per pronoun/occurrence as the initial default; it is not a measured scaling result. Preserve different bindings, exact range applicability and original-source attribution. Range shifts, partial retargeting/group splits and unresolved-group continuity become explicit Stage-6 scenarios. Larger groups, detailed saved occurrences with a compact graph, edge/contribution-only positions and saved-record-only mentions remain alternatives. Proposal section 17 records the rationale and alternatives; no new stage is added. Existing semantic-edge compaction remains deferred.

### Saved interpretation records agreed — 2026-10-14

Keep local reference-group records separate from mention-resolution records. A resolution has a stable assignment ID, group reference, accepted/unresolved/ambiguous status, exact target when accepted, applicability, input references and derivation provenance. Whole-group retargeting replaces its contribution; partial retargeting first splits the group. Only accepted interpretations publish resolution edges; markers persist after withdrawal. Variant relationship records specify two reusable Entity IDs, variant kind and scope through the same contribution/provenance machinery. Proposal section 18 records these forms; exact JSON serialization, source envelope/construction placement and completion metadata remain under review.

### Construction fallback for matched Entities — 2026-10-14

Revise the initial recipe rule: retain minimal corpus-backed construction data for every required Entity the generated source is intended to create/retain, including matched existing nodes. Existing endpoints bypass construction and receive native retention attachment without field rewriting. Valid missing endpoints can be reconstructed at their saved UUID, subject to current input/assignment validity.

This closes the last-owner rebuild gap: DOC01 ownership can disappear while I02 retains an Entity; if a subsequent I02 rebuild temporarily deletes it, I02 can reconstruct from saved intent. Add that sequence to Stage-6 lifecycle tests. Recipes do not authorize resurrecting retired/invalid endpoints, restoring arbitrary native semantic edges or treating initial field values as authoritative current properties. Controlled existence-check/create coordination remains to be implemented. Proposal section 19 records the revised direction.

### Publication ledger selected — 2026-10-14

Use a project-owned SQLite ledger keyed by dataset + generated identity Data ID, with pending/current/failed state, target and last verified published revisions, current attempt ID and optional diagnostics. Keep content authoritative in JSON. Mark pending before affected supported mutations; publish/reconcile and verify required graph/index state; acknowledge only the matching current revision/attempt. Same-revision repair is supported. Retry persistence from captured saved intent.

Initially disable the pending source's identity contributions; preserve valid unaffected sources, including shared-edge contributions whose required representations remain valid. Exact hooks/guards/checks remain Stage-6 work. Native pipeline status and retrievers do not supply this behavior automatically. A/B remains optional. Proposal section 20 records the selected baseline. Initial storage/publication-state review is complete at the design level; next review covers Describe, lifecycle integration and retrieval.

### Describe grounding and decision-model goal — 2026-10-14

The user requires understanding the pinned native extraction/resolution mechanisms and representative standard approaches before choosing Describe implementation, with a longer-term decision model alternative to an LLM.

Source review distinguishes per-chunk prompt-based normalization/name IDs from optional destructive consolidation, ontology matching and local GLiNER extraction. Native GLiNER integration demonstrates a non-generative Task/callback pattern but its generic mapper does not retain exact reference ranges or solve corpus linking.

Propose replaceable mention/grouping, candidate and identity-decision backends with adapters into the saved records; do not require generated prose/JSON. Code validates spans/IDs/scope and compiles explicit publication intent. Paragraph-local groups may use wider reasoning context. Preserve actual candidate/context inputs, producer versions and decisions for replay and future training, separating proposals from validated labels. Architecture reference section 18.19 and proposal section 21 record source evidence, limited standard-method references and remaining evaluation choices. No model is selected or trained; scientific reasoning remains deferred.

### Context-only reference groups remain graph mentions — 2026-10-14

Retain pronoun/context-only local reference groups as mention nodes with has_identity_mention classification and accepted directed mention resolves_to edges. A group may contain a list of exact pronoun/contextual-reference ranges without a preferred noun phrase. Under the selected physical schema it remains an ordinary Entity with an explicit group UUID/construction recipe; its label is not a reusable alias.

This supersedes the conversational saved-only default. Grouping is the initial graph-size mitigation, while graph-visible bindings allow traversal and semantic relationships attached to mentions. Exact fact attribution and explicit mapping from native semantic extraction to group endpoints still require implementation/tests; grouping does not authorize wholesale fact transfer or physical node merging. Proposal section 22 records the clarification and rationale.

### Seeded Describe and examples-first implementation — 2026-10-14

Select staged Describe passes: (1) names/reusable-form candidates plus explicit parenthetical definitions and generated initials; (2) seeded semantic/corpus matching; (3) shortenings/descriptive references; (4) pronouns/contextual references using established referents and broader context. Local/lexical/vector candidate generation supplies these passes. Generated acronyms seed searches and do not automatically become global aliases.

Prioritize a small fixture set exercising representative reference types through Describe, saved JSON, controlled graph publication, retrieval and selected maintenance/replay. Use existing abbreviation/variant/controller benchmarks as evaluation expectations, not inference inputs; add small passages where a needed type is absent. Improve extraction/resolution after the first whole pipeline works. Comprehensive coverage, final thresholds, backtracking and a trained decision model are not initial prerequisites. Proposal section 23 records the selected order and milestone.

### Identity-aware semantic fact generation — 2026-10-14

Local-node anchoring is selected for facts expressed through contextual references. Refine the proposed pipeline: identity Describe supplies explicit mention/variant bindings to a custom semantic extraction/conversion Task before final graph persistence. That Task generates new relations from original text; the publisher materializes them. Entity creation alone does not generate facts.

Replace/adapt the native extract_graph_and_summarize portion of the STANDARD list through the selected Task extension, reusing useful native components. A project custom Task pipeline can establish the first examples while native entrypoint/routing integration is implemented. Do not require a completed ordinary native graph before all identity work. Preserve exact IDs in conversion and document-level seeds across chunk batches.

First fixtures must include newly generated semantic relations from a newly described mention/variant, not merely identity links over existing facts. Explicit variant facts can attach directly to that variant; contextual facts attach locally. Capture source bindings/provenance and semantic outputs for replay; exact durable artifact/owner sequencing remains to test. Proposal section 25 records responsibilities and implementation boundaries.

### Deferred native factual-coverage comparison — 2026-10-14

During the first Stage-6 fixtures, compare native semantic extraction with the identity-aware path. Measure shared/new/missed/misinterpreted facts, distinguish endpoint changes from new content, and inspect source/occurrence and producer provenance. Use controlled isolated/captured outputs and validated scope-aware interpretation; native and mention-anchored edges need not have identical IDs to express the same source fact. Let the findings inform extraction reuse, deduplication and provenance. This is recorded for later work, not investigated now, and does not add a prerequisite before the first pipeline example. Proposal section 26 records the comparison boundary.

### Native-first semantic relationship/provenance goal — 2026-10-14

Use ordinary Cognee Entity relationships, original-document/chunk attribution, native ownership/deletion and the configured native indexes for identity-aware semantic facts wherever possible. The identity extraction/conversion adapter chooses exact mention/variant/existing endpoint IDs; it should preserve native chunk production and evidence bookkeeping rather than introduce a separate semantic-fact representation.

Pinned-source inspection identifies concrete Stage-6 checks: exact UUID conversion; existing endpoint retention without field rewriting; custom_edges document ownership versus normal chunk ownership/evidence; exact local-group bindings beyond native coarse chunk evidence; mention classification surviving or being safely retired when the generated identity source is removed while original facts survive; configured optional Triplet indexing; and normal shared-edge/property behavior. Preserve already-existing edges' additional native source owners/evidence without unnecessary property rewrites.

Proposal section 27 and extension-reference section 18.25 record the baseline and findings. The next review should settle minimal captured semantic-output placement and the independent-source mention-lifetime case, then initial Maintain triggers/continuity and Retrieve's local-fact contract. Routing and the first real-backend fixtures remain implementation/probe work. Update the existing Stage-6 sequence suites; no new stage, full semantic-fact ledger, runtime compatibility result or native-coverage measurement is added.

### Documentation reconciliation and session handoff — 2026-10-20

Reconcile older global “not implemented” and “next review” statements with the delivered Stage-6 code, while preserving dated experiment history and distinguishing fixture-specific limits from missing general functionality. The current checkpoint is Stage-6 implementation step 4 / M3, partially complete through resolved fact-bearing group retirement; occurrence additions are next. Add [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) with the code/patch baseline, completed and remaining work, module map, resume commands and separate generation-environment/Mac verification summaries. This update changes documentation only; it adds no runtime behavior and does not rerun the runtime test suite.

### Captured occurrence additions — 2026-10-20

Extend the common maintenance path with a separate explicit old-to-new occurrence continuity mode. Preserve continuing groups and decisions, allocate a fresh local group ID despite repeated surface text, and publish its captured original-owned semantic fact/evidence. Retain the existing coordinator, saved-source schema and backend interfaces. Commands, test evidence and remaining boundaries are in [the addition guide](docs/stage6_identity_occurrence_addition.md) and current session handoff. Stage-6 step 4 remains partial; broader regrouping, meaning changes, dependencies and full source lifecycle are still pending.

### Fixture isolation and verification tooling, 2026-10-20 to 2026-10-21

Fix the repository `.env` override. Cognee loaded `.env` at import and replaced the fixture settings, so fixture roots used the `.env` embeddings and wrote raw text into the lab stores. Each root now keeps its stores inside the root and records its embedding profile, `env` or `loopback`. Fix the build backend key, so the build uses `uv_build`. Add the project verify skill. Its 20 journey blocks drive the CLI through real stores, and the assistant ran them on the user's Mac. Add a bounded exhaustive check of the identity publication ledger with seeded breaks. Run unit tests in GitHub Actions on every push, and land reviewed branches on `main` by local fast-forward merges. This work adds no Stage-6 behavior. The next task is still a concrete group split/combination case. [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) records the evidence and commands.

### Captured group split and combination — 2026-10-21

Add a separate explicit `occurrence_regrouping` admission. Each old occurrence maps to one `[new group, new index]` pair. The user approved the case before implementation. `split-group` splits g01 into fresh g04 and g05 at revision 2. `combine-groups` merges them into fresh g06 at revision 3. Retired groups, links, facts, evidence and triplets are physically removed, and facts are generated again from the fresh groups. The review added a rule that derives a fresh group UUID from the saved source, the new revision and the group key, because the record store keeps only the current revision. Add verify journeys G1 to G4 and a regrouping plan in the identity-ledger model. The user agreed a new verification routine: unit tests on every commit, the ledger check when `RecordStore` or its callers change, the changed feature's journeys on every feature change, and `journey all` once per checkpoint before the merge. The assistant's subagents ran the evidence on the user's Mac with loopback embeddings. Stage-6 step 4 remains partial. [The group split guide](docs/stage6_identity_group_split.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### General occurrence map — 2026-10-21

Replace the separate removal, addition and regrouping admissions with one general occurrence map. The assistant drafted a mixed addition/removal case as the next step-4 item. The user asked why that edit could not combine the existing operations, and whether every mix of removing and adding would need its own design. It would have. Each admission mode admitted only its own kind of change, so the plan's "mixed addition/removal" and "broader additions and regrouping" items were open-ended: each new mix, such as two additions, a split with a removal or a partial peel-off, would have been another mode to design, review and verify.

The map gives each old occurrence its new place in the new description, or marks it removed. One set of rules, stated over occurrences and groups rather than kinds of edit, decides which groups continue, retire or are fresh. The user decided two policies that logic alone does not settle: strict peel-off, and a fresh group when nothing survives. "General occurrence map, approved 2026-10-21" in [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) states the rules and the policies.

The work landed in three checkpoints. Checkpoint A added the general admitter beside the old modes, with no behavior change, and checked it against an independent oracle on every world up to three old groups, three old occurrences and one addition. Checkpoint B switched every text change to the general map, deleted the old modes, and kept a reader that converts plans saved by the old code. Checkpoint C published the mixed case as a fixture with no admission change. The assistant ran the evidence on the user's Mac with loopback embeddings. [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) records the rules, the policies and the evidence.

This changed the remaining step-4 work. Mixed addition/removal and broader additions and regrouping are no longer separate items. The rules admit them, and one mixed edit has a captured fixture. Representation-kind changes, changed interpretation, dependencies, full source lifecycle and verification/recovery coverage keep their scope. Any change to admission now also runs `support/occurrence_check.py` and its mutants. The handoff's tracked follow-ups list the open debts. Steps 5 and 6 and the later stages are unchanged.

### Mixed occurrence revision — 2026-10-22

Publish one captured doc01 edit that keeps `it`, removes `the controller` and adds a startup `the controller` to continuing g01, and retires g02. The user approved the case on 2026-10-21. It needed a describer, a command, tests and journeys, and no admission change. Its map equals the removal map, because a map states only where old occurrences went. Every captured describer is now built from one set of revision helpers. The assistant ran the evidence on the user's Mac with loopback embeddings. [The mixed occurrences guide](docs/stage6_identity_mixed_occurrences.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### One admission for every replacement — 2026-10-22

Fold the unchanged-text correction into the general occurrence map's admission, and relax two rules that dated from the first text-edit slice. The user asked whether a changed interpretation could point a group at a new Entity, and why the rule against it existed. It existed as a scope limit: the first text edit on 2026-10-19 admitted moved text only, and later slices kept the limit. The correction on unchanged text had its own, much looser admission, a fourth path of the kind lesson G22 warns about.

Now one rule set admits every replacement. With unchanged text a continuing group may change its decision in place and keeps every span; with changed text it keeps its decision, and a changed meaning is a fresh group. An edit may introduce a new reusable Entity with a derived UUID, drop one it no longer uses, and change document-scoped variants. Corpus-scoped variant changes wait for dependencies. Facts are still generated again, never transferred. The assistant ran the evidence on the user's Mac with loopback embeddings. [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) records the rules, the behavior changes and the evidence.

### Changed interpretation and kind change — 2026-10-22

Publish four captured doc01 edits through the one admission. Two text edits change what "the controller ... it" means: once to a new Backup controller Entity with a derived UUID, and once to unresolved. The old group retires, a fresh group takes the occurrences, and its fact is generated again; a query for the old Entity no longer returns it. Two edits with unchanged text change HC's representation: doc01 drops its reusable HC variant for a local mention, then references doc02's existing HC Entity and declares the variant again. The shared edge and Entity survive on doc02's claim throughout, and no duplicate HC Entity appears. These were the first rebuilds with unchanged text, and they needed no code change. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings. [The reinterpretation guide](docs/stage6_identity_reinterpretation.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### Forget a source nothing depends on — 2026-10-22

Add `forget`, which removes a current source's original document, its identity source and everything only they owned through Cognee's native document deletion, and `readd`, which publishes it again at the next revision with new IDs. The user distinguished two intents. Cleanup may refuse while other sources depend on the document. Erasure must not be blocked by dependents, and step 5 will route Cognee's own deletes here. Both agree when nothing depends on the source, so only that part is built; with dependents, `forget` refuses and lists them as a placeholder until dependencies (step-4 item 3) decide what an erasure does to them. A source depends on a document when its description lists the document's text, a span or chunk of it, or reads an Entity only that document owns. The forget guide lists what survives a forget, for the erasure decision. The legacy plan readers are deleted and the reviewed roots retired as history. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings. [The forget guide](docs/stage6_identity_forget.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### Withhold the decisions an edit affects — 2026-10-23

A text edit of a document another source read was refused, and a dependent could not be revised at all. Now the edit goes ahead. In its own attempt it classifies each input a dependent read from the edited document and records, in a table beside the ledger, which decisions read what changed. Only those decisions are withheld from retrieval, with the facts generated from their groups. A span unchanged in place stays valid. A moved span is refreshed with its new range after the edit completes. A changed span, chunk or whole text waits for a reviewer, who re-confirms the decision under a new producer or replaces it. While an edit is pending or failed, every decision citing its document is withheld, so a crash never serves a dependent stale. A changed corpus field withholds the decision that read it, not the whole source. Admission accepts other documents' texts and spans under a structural rule: content under an existing key never changes, and a decision under an old producer cites only keys that producer cited before. Four review rounds shaped that rule. `forget` still refuses a source with dependents, and saved-record inputs and the transitive case are deferred. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings, including `journey all` at 1287 PASS and 0 FAIL. [The dependencies guide](docs/stage6_identity_dependencies.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### Erase a source and remove what depended on it — 2026-10-23

`forget` refused a source with dependents, kept the forgotten description and accepted only a current source. Now it always erases, and any source can be forgotten. The ledger row keeps a tombstone of identifiers, digests and the revision, and the forget plan and the source's recovery-event messages lose their text. A forget that would change another source's decisions needs `--confirm` with the token of its `--dry-run`, which lists each decision it removes and the input that causes it. The source is erased first. Then each dependent gets a removal revision: a resolution that cited the source becomes unresolved, a variant is dropped, and a recipe only removed decisions named goes with them. A dependent whose own publication, replacement or text change had failed finishes with the removal applied to its saved revision. `readd` publishes from the caller's files, and a forgotten mention or Entity UUID never returns. Erasure is logical: the stores' soft-deleted bytes stay until they compact. Four review rounds shaped the erasure retry. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings, including `journey all` at 1439 PASS and 0 FAIL. [The forget guide](docs/stage6_identity_forget.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### Withhold down a chain of decisions — 2026-10-23

Admission refused every saved-record input, so a source could read another document but not another source's decision. Now a resolution or a variant assignment may cite a decision of another source in the same dataset. The citation pins the record's fingerprint, which a re-confirm keeps and a reviewed change breaks. When a cited decision is withheld, changed or gone, every decision down the chain is withheld too. Nothing is written: retrieval and `status` derive it from the ledger rows, the withholding table and live validation, so a release upstream releases downstream on the next read. Admission refuses a cycle between sources and a self-citation. A forget that would remove a record another source cites is refused until Checkpoint J2 builds the cascade. A bounded check compares the cycle rule and the withheld set with an oracle on every citation graph of up to four sources. One review round shaped the fence for an unfinished forget and moved the chain check onto the real live pass. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings, including `journey all` at 1519 PASS and 0 FAIL. [The chains guide](docs/stage6_identity_chains.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### Erase down a chain of decisions — 2026-10-24

Checkpoint J1 refused a forget that would remove a record another source cites (`chain_erasure_pending`). Now the forget cascades. A dependent that cites a record another dependent's removal removes, as the record was before the removal, is one level below that dependent, at its longest path, and gets one removal revision for all it loses. One dry run lists every level, one token covers them and one `--confirm` writes them in level order. A crash resumes in order from the ledger rows, with nothing new stored. Each removal producer lists the records it removes and the removed records it cites, and admission accepts a cited record only when a written removal of the same forget lists it, back to the tombstone. A citation made after a removal reads the record as it is now and is not cascaded. Removal producers are immutable. While the cascade is unfinished, the fence refuses a new citation of any record any level will remove, and `withdraw` and `forget` refuse a source holding a removal when retiring it would change what the cascade still does to any other source (`cascade_unfinished`). Four review rounds shaped the binding rule and that refusal. Each round found one more shape until the cascade check tested the invariant itself on every world. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings, including `journey all` at 1576 PASS and 0 FAIL on `74ec093`. [The forget guide](docs/stage6_identity_forget.md#the-cascade) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### Planned non-identity example — 2026-10-24

On 2026-10-24 the user wrote in the planned non-identity example. A measured value comes from a span of a datasheet, and an analysis note cites that value. A datasheet edit withholds the note's use of the value, and forgetting the datasheet removes it. This is the identity mechanism (an input span, a saved record that cites it, withholding and erasure) applied to a new domain. It needs a new source kind with its own describer, admission and fixture, so it needs architecture planning first. No work on it is scheduled now.

### Readers of a changed or retired Entity or record — 2026-10-24

Live validation already withheld a decision whose corpus input changed in the graph, but no command drove such a change and no reviewer could answer it. A citer of a removed record had no reviewer path since J1. A dropped record key could come back and be served to an old citation, and a source could read another source's mention UUID as a corpus object. Checkpoint K closes each gap. `edit-entity` is a captured stand-in for an outside writer of a native Entity; it writes no ledger row, and a revert releases its readers with no revision. One review flow reads each withholding input by its kind, so one re-confirm answers a span and an Entity together. `replace-citation --cite|--drop` answers a citer of a removed record at any chain level. Admission refuses `record_key_reused` and `mention_input`. The kind changes run on a root where other sources read doc01. Two review rounds made every path that removes a record use one helper, after reviews found a review drop that had diverged from the erasure twice. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings, including `journey all` at 1658 PASS and 0 FAIL in 101 runs on `5e0c314`. [The entity edits guide](docs/stage6_identity_entity_edits.md) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands and evidence.

### Step-4 cleanups and close — 2026-10-25

After Checkpoint K the session handoff tracked small follow-ups that needed no decision. On 2026-10-25 the user asked for them. Branch `stage6-cleanups` added a command table for the glossary root, `records.apply_reconfirm`, a raising `revisions.refresh`, a producer key per prefix edit, the saved retirement plan on an erasure-retry reconcile, the `stored_files` guard in the forget snapshot and an end-to-end property in the cascade check. It also fixed `forget`, `readd` and `withdraw` on a single-source root, which a step-5 probe found. No admission rule, saved schema or retrieval result changed.

One item became a decision. A stand-in for an outside writer that deletes the cited Helios Entity showed that the two withheld decisions citing it block each other's replacement (`missing_reasoning_input`), and the native delete left the Entity's name vector point behind. The user decided that a withheld decision may keep citing a deleted Entity while a neighbour is replaced, that a republish may not recreate an Entity deleted outside the lab, and that the fix goes to step 5 S2. Step 4 records the deadlock as a documented limit.

The user then ran two fixtures with the env embedding profile (`nvidia/nemotron-3-embed-1b`, 2048 dimensions) on their Mac: M1, a glossary edit with two re-confirms (22 PASS, 0 FAIL), and M2, a cascade forget with a crash at level 2, reconcile and re-add (16 PASS, 0 FAIL). The user decided that the remaining tracked follow-ups stay documented limits and declared step 4 done. Step 5 is next.

### Deletes outside the lab — 2026-10-26

In the step-5 discussion of 2026-10-25 the user decided to leave Cognee's own deletes unwrapped. A plain `cognee.forget` or prune therefore erases only Cognee's copy, and the lab must notice. Step 5 S2 adds that detection. `status` compares each saved source with five facets of its native copy and lists the ones that differ under `native_deleted`, including a plain incremental `cognee.update` that replaced the chunks. `reconcile` refuses such a source and names the `forget` that erases the lab's copy, and `forget` completes on it. An Entity deleted through Cognee's graph API stays absent. Kept decisions may keep citing it, the publisher skips its recipe and edges, and journey D17 answers its readers one at a time, which closes the step-4 deadlock. `forget-dataset` forgets every source of a dataset under one dry run and token, readers first, and then deletes the Data no lab source publishes (the user's Q3). The same command repairs a root after a native dataset forget or prune and sweeps orphaned `Entity_name` points.

Three bug-review rounds each found a re-add that wrote a removed Entity UUID again, because the lab rebuilt "removed by the lab" from tombstones and plans that later operations overwrite. On 2026-10-26 the user decided that a removed Entity UUID is never reused, including after a withdrawal. The assistant then replaced the reconstruction with an append-only removal record in the ledger database. The assistant and its subagents ran the evidence on the user's Mac with loopback embeddings: `journey all` gave 1775 PASS and 0 FAIL in 110 runs, the unit suite gave 641 passed, and the ledger, occurrence and chain checks passed with their mutants. [The forget guide](docs/stage6_identity_forget.md#deletes-outside-the-lab) and [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) record the commands, the decisions and the evidence.

### Lab entry points — 2026-10-26

The step-5 discussion of 2026-10-25 chose lab entry points that run Cognee's standard Tasks under Cognee's pipeline names, instead of a Cognee patch. Step 5 S3a builds the first three. `add` registers the original and the identity description and stamps the description as cognified. `cognify` runs `run_pipeline` under `cognify_pipeline` with `classify_documents`, `extract_chunks_from_documents` and `add_data_points`, then one lab Task per document that stamps the original and publishes. `remember` is `add`, then `cognify`. Only the doc01 `fixture` uses them so far. S3b moves the other builders, and S4 adds `update`.

A probe on the user's Mac found that Cognee tags only what a Task writes with the pipeline's context, and that its rollback and its startup recovery find a run's writes by that tag. The lab Task therefore writes with contexts of its own, and the run passes no rollback handler. A failed lab Task is recorded in the ledger, the run completes, and `reconcile` finishes the saved plan. Cognee's run status then shows the run as completed, so the ledger is the record of the lab's outcome. The stamp keeps a plain `cognee.cognify` from extracting the lab's files, with gaps the [entry-point guide](docs/stage6_identity_standard_entry_points.md) lists.

The review found that an exemption in the native-copy check, added for a failed first publication's chunks, hid a delete made outside the lab. With no rollback handler no lab cause removes those chunks, so the fix round removed the exemption. The assistant's subagents ran the evidence on the user's Mac on 2026-10-26 with loopback embeddings: `journey all` gave 1818 PASS and 0 FAIL in 115 runs, the unit suite gave 646 passed, and the ledger check passed with its mutants. The assistant's decisions on rollback, the stamp and the S3 defaults await the user's confirmation. [stage6_checkpoint_history.md](docs/stage6_checkpoint_history.md#step-5-s3a-the-lab-entry-points-2026-10-26) records the commands, the decisions and the evidence.

### Every builder on the entry points — 2026-10-26

S3a built doc01 through the lab's entry points, and the other creation commands and `readd` still registered their documents by hand. Step 5 S3b moves them all onto `add` and `cognify` and deletes the hand-built creation path. Each source has one builder, `add_<label>`, that registers it and returns its description, and `entry.remember_in_order` adds, then cognifies, each source in publication order. `cognify` takes one source. Cognee runs the items of one run concurrently, up to 20 at a time, and a chain root's doc03 cites doc01's published decisions, so one source per run keeps the order.

The bug review found that the build's order, every `add` first and then each `cognify`, left a source after a failed one registered without a stamp. A plain `cognee.cognify` would then extract it with the LLM, and no lab command could publish it. The fix round adds each source only after the one before it has published, and refuses a source with no publication (`not_published`) instead of crashing. The quality review's proposal to send every `reconcile` through `cognify` was dismissed: `cognify` writes the native chunks again, so the verify would no longer prove that Cognee still holds them. The assistant's subagents ran the evidence on the user's Mac on 2026-10-26 with loopback embeddings: `journey all` gave 1853 PASS and 0 FAIL in 120 runs, the unit suite gave 650 passed, 59 native tests passed, and the ledger check passed with its mutants. [stage6_checkpoint_history.md](docs/stage6_checkpoint_history.md#step-5-s3b-every-builder-on-the-entry-points-2026-10-26) records the commands, the known limits and the evidence.

### The lab update — 2026-10-26

The step-5 discussion of 2026-10-25 (unit 3) asked for a lab `update` that reuses step 4's edit path: Cognee rebuilds the whole document, and the identity revision stays incremental. Step 5 S4 builds it. `entry_update.update` refuses a source whose native copy is gone, chunks the new text in memory once, asks the caller's required `describe_edit` for the next revision and runs one lab Task under `cognify_pipeline` that calls `publisher.replace` with the text change and the caller's occurrence map. Inside the text change the per-item memory-only forget clears the original's stamp, the lab stamps it again at once, and `native_chunks.build_chunks` runs Cognee's standard Tasks nested, outside any run, with the lab's untagged context. Every text-edit command runs through `update`, and `reconcile` of a failed edit runs through `replace_text` with the saved text change.

Neither review found anything blocking. The bug review found that an edit of a natively deleted source stopped on a misleading message, and that a hard kill between the forget and the stamp leaves the original without chunks or stamp, so a plain `cognee.cognify` would extract the previous text. The fix round refuses the edit with `native_deleted` first and names the window in the guide. The quality review found `entry.py` at 511 lines with two lifecycles. The fix round moved the chunk builders into `native_chunks.py` and the edit half into `entry_update.py`, shared one `semantic_hooks`, and made the describer a required argument, so the run-time refusal `describer_missing` is gone. The assistant's subagents ran the evidence on the user's Mac on 2026-10-26 with loopback embeddings: `journey all` gave 1953 PASS and 0 FAIL in 131 runs, the unit suite gave 650 passed, 56 native tests passed, and the ledger and chain checks passed with their mutants. [stage6_checkpoint_history.md](docs/stage6_checkpoint_history.md#step-5-s4-the-lab-update-2026-10-26) records the commands, the known limits and the evidence.

### The public retriever — 2026-10-26

The user's decisions of 2026-10-25 asked for retrieval through `cognee.search` with a registered `IDENTITY` search type, the semantic mode first, evidence with no LLM completion and identity-anchored facts by default. Step 5 S1 builds it. A spec review found that a plain string cannot name a search type in Cognee 1.6.2, so the lab adds a member to the closed enum behind a version guard and an import-time self-test, and documents what the member does not reach: JSON models built before the import, a fresh `cognee search` process, the `FEELING_LUCKY` prompt and the `recall` router. The retriever and the CLI `retrieve` share `settled.retrieve_settled`, which reads once more when a writer changes the ledger during the read. The ranking is the first slice's. Seeds come only from the searched dataset's served sources, and the fallback seed only when the top reusable candidate is one of them.

The user moved the Stage 5.3 benchmark into S1 on 2026-10-26. The spec review found that authoring the fixture from the hidden manifest would put the answers in the description, against this roadmap's rule that hidden answers stay out of Describe inputs. The conformance fixture's describer reads only DOC01's text and chunks, and only `support/conformance_check.py` reads `data/hidden`. Its rules were still written after its author read the answers, so the result is a conformance check that gates retrieval changes against a committed baseline, not an evaluation. Recall passes 10 of 18 manifest facts, mostly because the describer writes no fact for the others; QRY05 fails on the fallback seed. Two `/pstack:thermos` rounds found a fallback that served the lab's facts for another dataset's Entity, a registration that a failed self-test left half done, and gap reasons kept in three places; the fix rounds closed each. The assistant's subagents ran the evidence on the user's Mac with loopback embeddings: `journey all` gave 2022 PASS and 0 FAIL in 140 runs, the unit suite gave 699 passed, the integration suite 120 passed on `64bad48`, and the ledger check and its mutants passed. [stage6_checkpoint_history.md](docs/stage6_checkpoint_history.md#step-5-s1-the-public-retriever-2026-10-26) records the baseline, the known limits and the evidence.
