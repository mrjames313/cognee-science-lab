# Cognee Science Lab Roadmap

**Last revised:** 2026-10-13  
**Project:** `cognee-science-lab`  
**Architecture baseline:** Cognee 1.6.2; Ladybug graph backend; LanceDB vector backend  
**Current work:** Stage 5.4.5.2–.3 — initial ownership and identity representation direction recorded; next, operation walkthroughs toward the 5.4.5.4 lifecycle contract. Stage 5.4.5.1 characterization remains complete. Schema/routing, lifecycle validation, final invariants and Stage-6 implementation remain pending.

This revision reconciles the previously saved roadmap with the later project discussion and the companion `cognee_extension_architecture_reference_v1.6.2.md`. Historical graph counts and benchmark scores describe particular experimental snapshots, not an assertion about the current live database. “Complete” refers to the exploration needed to proceed; it does not imply production implementation.

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
| 5.4.4 | Complete enough for architecture selection | Prefer B: small Cognify task-transform extension; implementation pending |
| 5.4.5 | In progress | .1 complete; .2–.3 initial ownership/representation proposal recorded; operation walkthroughs, lifecycle and handoff next |
| 6 | Planned | Implement the chosen processing/retrieval architecture, then reassess |
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

A mention is a distinct occurrence Entity. It receives an explicit deterministic occurrence UUID and a generated identity DocumentChunk → Entity has_identity_mention marker. Classification persists when no accepted resolution exists. A reusable variant Entity must not also serve as a mention.

Do not add authoritative identity fields to ordinary Entity properties. Store resolution kind, applicability and current contributions on identity edges, and retain structured assignments/original-input provenance independently in generated identity sources. Do not introduce singleton or variant markers, or a graph support node per assignment, in the initial design.

The proposal groups document-local assignments into one generated Data item per original document and uses native document-level owners to retain all required endpoints. Original-input dependency, native ownership and applicability remain distinct. See [the recorded proposal](cognee_stage5_4_5_identity_representation_proposal.md) for the preliminary ownership matrix, edge contents, evidence boundaries and remaining decisions.

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
| Mention classification | Generated identity chunk → Entity has_identity_mention marker |
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

## Stage 5 — Identity, resolution, and semantic reconciliation — IN PROGRESS

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

### Deferred optimization — mention clustering / compaction

Do **not** implement mention clustering yet. Occurrence-level mention Entities currently provide straightforward relation provenance: a semantic edge attached to a mention is automatically tied to the source occurrence represented by that mention.

A future mention cluster is only useful if semantic relations can be collapsed without losing occurrence-level provenance. Its resolved target would be a singleton or identity group under the current terminology. Compaction remains deferred until ownership/provenance and update/delete semantics are clear.

Until evidence shows mention fan-out is a real problem, prefer simple retrieval/indexing mitigations over a model rewrite. Revisit clustering only after relation/assertion provenance is explicit enough to preserve source support under compaction.

### 5.4 — Operational semantics, architecture, and graph evolution — IN PROGRESS

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

#### 5.4.5 Architecture and operational invariants — IN PROGRESS; INITIAL REPRESENTATION RECORDED

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

**Handoff:** design identity storage/source binding and maintenance next. Helper cleanup and replay remain required for the selected identity workflows. Index/backend-reference consistency applies to stores consumed by enabled retrieval/provenance paths; unused diagnostic stores do not force immediate repair. These are later implementation obligations, not unfinished characterization tasks.

##### 5.4.5.2 Artifact ownership / provenance model — INITIAL CHOICES RECORDED

The six outcome requirements remain in cognee_stage5_4_5_requirements_review.md. The initial ownership choices are:

- preserve structured assignments and original-input provenance independently of materialized edges;
- group document-local assignments into a generated Data source per original document;
- use native document-level generated-source ownership initially;
- deliberately retain both existing and new Entity endpoints required by assignments, attaching refs to existing nodes without property replacement;
- distinguish original-input dependency, generated-source ownership, applicability and run attribution;
- recompute shared edge contributions when assignments are withdrawn, rather than relying on owner retention to restore properties.

The preliminary matrix is in cognee_stage5_4_5_identity_representation_proposal.md. Complete the original-source → generated-source dependency/lifecycle mapping and actively consumed index/backend-reference ownership before declaring .2 finished. Cached QA/session vectors remain conditional on enabling reuse.

**Scientific reasoning boundary:** provenance and retention ownership do not establish scientific support. Scientific justification remains Stage 8; no claim/evidence inference policy is adopted here.

##### 5.4.5.3 Stable physical representation — INITIAL DIRECTION SELECTED

The selected initial direction uses ordinary Entity nodes, identity-group variant relationships without a privileged canonical member, occurrence-specific mention Entities, and explicit mention markers from native generated identity chunks.

Resolution edges store resolution_kind and current contributions. Separate singleton/variant markers and per-assignment graph support nodes are omitted. Structured assignments are sufficient to reproduce exact graph intent; ordinary LLM parsing of identity descriptions is not relied on for faithful reconstruction.

Deterministic occurrence UUIDs override Entity's default name-based identity. A custom loading Task must publish ID-based edges and intentionally attach existing endpoint refs without passing populated existing Entities through recursive persistence. calculate_chunk_graphs is a computation seam, not a complete reference-only loader/routing solution.

Remaining outputs: structured-source serialization and stable IDs, exact edge schemas/scope conventions, loader/routing, treatment of current prototype helpers, and compatibility with operations that delete/remap endpoints. No combined runtime validation is claimed.

##### 5.4.5.4 Write / reconcile / read / update lifecycle — OPERATION WALKTHROUGHS NEXT

Start with one generated source publishing a new Entity and an edge to an existing Entity. Then cover edge-only publication, unresolved-to-resolved mentions, overlapping contributions, original-source Update/Forget, generated-source rebuild, failure/retry and selected native endpoint mutation. These are design-dependent follow-ups, not a restart of the completed .1 characterization.

Specify which Tasks belong inside transformed Cognify and which belong in Memify/Improve; when maintenance runs; how failed or stale derived state is detected; and what a custom Retriever accepts as usable state.

| Lifecycle phase | Proposed seam | Remaining contract |
|---|---|---|
| Ingest | Native Remember/direct Cognify + proposed B transform/custom loading Task | Register/routable identity Data, deterministic publication, source ctx, existing endpoint retention |
| Reconcile | Idempotent project Tasks at the selected seam | Contribution aggregation, marker/resolution consistency, replay scope, selected native stages |
| Read | Registered custom Retriever/SearchType | Identity groups, scoped directed mentions, contribution checks, deduplication, attribution |
| Update | Project full-rebuild path with customization forwarded, then maintenance | Original/generated-source dependencies, endpoint recreation, usable-state/failure behavior |
| Delete | Native Forget plus derived-source retirement/contribution repair | Surviving inputs/owners, original dependency cleanup, indirect edge/index removal |

##### 5.4.5.5 Operational invariants and Stage-6 handoff

Candidate invariants to finalize from evidence:

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

Deliverables: mutation/persistence matrix, ownership matrix, architecture diagram, lifecycle contract, finalized invariants, and a Stage-6 implementation/checklist with validation criteria. Stage 5.4.5 is not complete until these decisions are grounded and written down.

#### Retained scope, timing, and evolution questions

The superseded 5.4A/5.4B topics remain work to resolve through 5.4.5 and Stage 6:

- compare local chunk resolution, document pre-pass/DefinitionSummary, ordered accumulating context, post-hoc reconciliation, and hybrid strategies;
- distinguish local, document/subdocument, corpus/domain, and broader applicability; role does not determine scope;
- reuse corpus identity knowledge without overriding stronger local evidence;
- retain separate source/scoped support for a shared semantic identity link;
- preserve a link when another surviving source still supports it;
- allow contradictions and scope-specific meanings to coexist;
- exercise DOC01-only, DOC01+DOC02, and updated/removed-DOC01 corpus states.

The current source/identity chain is: original document/chunk inputs produce saved assignments in a generated identity Data source; its native chunks anchor mention markers, and deterministic publication materializes scope-bearing resolution edges. Original-input provenance remains independent of native generated-source retention. The earlier IdentityResolution helper chain is historical, not a required representation.

---



## Stage 6 — Custom processing architecture — PLANNED

Goal: move manually demonstrated representations into actual Cognee processing tasks/pipelines and ensure they participate in lifecycle/provenance behavior.

### 6.1 Explicit source/intermediate representations

Retain source occurrences and extraction decisions explicitly. Implement durable generated identity sources initially grouped per original document; preserve structured assignments and original-input provenance outside materialized graph edges. Use explicit deterministic occurrence UUIDs for mention Entities, and persist classification on has_identity_mention edges rather than Entity role fields.

For mentions, move from temporary occurrence indices to exact source coordinates where possible:

```text
source document/chunk id
start_char
end_char
surface_text
```

These should remain observable even if later relation extraction fails.

### 6.2 Automatic observation and identity extraction

Integrate Stage-4 typed extraction directly into the pipeline:

```text
chunk
    -> generic semantic graph
    -> AbbreviationObservation / other typed observations
    -> mention candidates
```

Then resolve observations/occurrences against existing identity context, save structured assignments, and publish exact mention markers and contribution-bearing resolves_to links. Treat singleton identities and variant groups without privileging one member. Roles are stored as explicit mention classification and relationship kind; historical mention strings do not become reusable aliases.

### 6.3 DefinitionSummary generation and hierarchical context

Generate document-level vocabulary/context automatically rather than hand-authoring it.

Compare:

- document pre-pass;
- incremental summary/context accumulation;
- hybrid strategies;
- special handling of explicit glossary/definition sections.

### 6.4 Pipeline sequencing and lifecycle integration

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

The exact Task order must follow the 5.4.5 decision. A likely division is document vocabulary/context + mixed generic/typed extraction inside construction, followed by source-grounded identity reconciliation and selected semantic materialization as maintenance. Do not force every transformation into one pipeline.

Lifecycle validation should cover direct Cognify, standard Remember, overlapping ingest, transformed full-rebuild Update, maintenance replay, and cleanup after source removal. Test no-transform native behavior and unsupported combinations for the B patch. Verify custom side effects explicitly rather than assuming native rollback handles them.

**Requirement:** source/support/derived structures must have documented, testable lifecycle behavior. Native compatibility is preferred; a small explicit cleanup/repair path is acceptable where native Forget is insufficient. Avoid allowing rare deletion behavior to dominate the representation design.

### 6.5 Registered identity-aware retrieval

Package the Stage-5.3 proof of concept behind a custom Retriever/SearchType using Cognee graph/vector interfaces. Perform query-time resolution before scope-aware identity expansion and semantic-neighborhood union. Adapt privileged canonical selection to singleton/identity-group handling; check edge contributions, follow mention references directionally and preserve unresolved mention classification. Native retrieval does not acquire these rules automatically. Preserve provenance under logical fact deduplication and provide semantic, source-aware, explanation, and graph-management modes as warranted.

Keep RAG as a reference/fallback and control conversation/session state during comparisons. Restore and strengthen the Stage-5.3 benchmark so it remains correct after subsequent source ingestion and maintenance.

### 6.6 Replay, mutation, and lifecycle regressions

Turn 5.4.5's matrices/invariants into focused regression scenarios:

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
- test or exclude optional consolidation/remapping for occurrence Entities.

### Post-Stage-6 checkpoint

Stop and reassess the architecture before moving into stronger schemas/ontologies. Review:

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

Explore:

- generating DataPoint/extraction structures from JSON Schema or ontology-derived schemas;
- importing or mapping ontology concepts into Cognee-compatible representations;
- using ontology constraints/instructions without requiring the ontology to own the entire graph;
- encoding counterexamples and interpretation rules in LLM instructions;
- schema evolution across versions.

---

## Stage 8 — Scientific Claim / Measurement / Evidence model — PLANNED

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

# Current immediate work

Current stage: **5.4.5**. Initial ownership and representation choices for **.2–.3** are recorded; the next activity is the operation-by-operation lifecycle walkthrough toward **.4**.

The chosen direction is documented in cognee_stage5_4_5_identity_representation_proposal.md. Neither .2 nor .3 is marked complete: schema, source dependency handling, loader/routing and the consumed-index matrix still need finalization. The preferred B Cognify extension remains unimplemented.

Immediate sequence:

1. Walk through a generated identity source publishing a new Entity and a relationship to an existing Entity, including exact persistence/ownership operations.
2. Cover edge-only publication, unresolved/resolved mentions and shared contribution aggregation.
3. Cover original/generated-source Update/Forget, full rebuild, endpoint mutation and failure/retry; schedule targeted checks where this design relies on untested behavior.
4. Finalize the schema/ownership matrix, supported operation contracts, active retrieval/index list and .5 invariants/Stage-6 handoff.
5. Implement Stage 6; preserve the architecture check-in afterward.
6. Keep mention compaction, a general predicate ontology and scientific reasoning deferred to their existing stages.

**Stage impact:** no new stages or renumbering. The proposal narrows the choices in .2–.3 and specifies Stage-6 source/loader/retriever work. Broad .1 characterization is complete; combined publication behavior and performance remain unvalidated.



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

