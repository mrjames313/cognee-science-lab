# Cognee Science Lab Roadmap

**Last revised:** 2026-10-11  
**Project:** `cognee-science-lab`  
**Architecture baseline:** Cognee 1.6.2; Ladybug graph backend; LanceDB vector backend  
**Current work:** Stage 5.4.5 — architecture and operational invariants, beginning with graph-wide mutation/persistence characterization. Experiments have not yet started.

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
| 5.4.5 | Current; planned investigation | Mutation matrix → ownership → physical representation → lifecycle → invariants |
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

### Unified Entity roles — demonstrated logical model; physical storage still open

The Stage-5.3 experiment uses one `Entity` concept with three roles. These logical distinctions remain useful, but their durable physical representation is a Stage-5.4.5 decision:

- `canonical` — the preferred semantic representation within an applicable resolution scope;
- `variant` — a reusable non-canonical representation whose interpretation may apply generally within a declared scope;
- `mention` — an occurrence-specific representation whose interpretation depends on the context of that source occurrence.

Role and scope are independent. Canonicality is scope-relative rather than inherently global. Any Entity role may participate in ordinary semantic relation edges.

The earlier distinction between `lexical_variant` and `extracted_variant` is intentionally collapsed into `variant`; how an Entity entered the graph belongs in provenance rather than in its semantic role.

Semantic scope and source location are distinct concepts. The following describes logical metadata, not a requirement to place these fields on Cognee-owned nodes:

```text
entity_role: canonical | variant | mention

scope_kind: global | corpus | document | subdocument | chunk | occurrence
scope_anchor_id: optional anchor for semantic applicability

source_document_id / source_chunk_id / start_char / end_char:
    source coordinates for occurrence-level Entities
```

A mention's exact source coordinates are relative to a specific text-bearing anchor, currently the `DocumentChunk`. `occurrence_index` remains only a temporary/fallback disambiguator until exact spans are reliably available.

### Project state must survive native mutation

Stage 5.4.1 showed that later Cognify can rewrite properties on existing Cognee-owned Entity nodes, including experimental `entity_role` / `graph_layer` annotations. Important project state cannot depend on those mutable properties remaining intact. Separate project-owned metadata, dedicated identity structures, and a hybrid representation remain candidates until Stage 5.4.5 characterizes the broader mutation surface.

Logical layer boundaries are design intent, not native mutation barriers. The selection and write behavior of each built-in operation must be established for support, source, and reconciliation structures as well as semantic Entities.

### Direct semantic identity navigation

The semantic layer should move toward direct Entity-to-Entity identity links:

```text
variant --resolves_to--> canonical
mention --resolves_to--> canonical
```

`resolves_to` is stored directionally from a non-canonical representation toward a canonical representation, but semantic identity is logically navigable in both directions. Retrieval should not equate bidirectionality with blindly expanding every reverse edge; query-time resolution and retrieval ranking/indexing determine which identity-related representations are activated.

### Logical graph layers

The experiments distinguish three logical layers within one physical graph. Stage 5.4.5 will select their durable physical arrangement:

```text
SEMANTIC LAYER
    Entity
    ordinary semantic relations
    resolves_to

SUPPORT / PROVENANCE LAYER
    IdentityResolution
    AbbreviationObservation
    mention-resolution support records
    future evidence/conflict/invalidation structures

SOURCE / CONTEXT LAYER
    TextDocument
    DocumentChunk
    TextSummary
    DefinitionSummary
```

Helper/support nodes exist primarily for graph construction, provenance, debugging, explanation, update/invalidation, and truth maintenance. They should not automatically participate in ordinary semantic retrieval.

### Retrieval modes

Planned logical retrieval modes:

1. **semantic** — Entity nodes, ordinary semantic relations, and identity navigation; support nodes excluded by default;
2. **source-aware** — semantic results plus relevant source/context nodes;
3. **explanation / provenance** — semantic results plus IdentityResolution, observations, evidence, and source support;
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

Implemented the logical roles `canonical`, `variant`, and `mention`, with scope independent of role. Materialized missing reusable variants and occurrence-specific mention Entities, added direct `resolves_to` links, and retained Stage-5.2 support/provenance helpers.

The resulting experimental snapshot had **160 nodes / 377 edges**. The annotations used in this experiment are not a durable storage decision: 5.4.1 later exposed their vulnerability to native Cognify writes.

Representation rules retained:

- canonicality is scope-relative;
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

A future cluster such as `(surface form, resolved canonical Entity)` is only useful if semantic relations can be collapsed without losing occurrence-level provenance. That likely requires a stronger relation/assertion provenance abstraction, for example a materialized semantic relation plus a support object linking one or more source occurrences to that assertion.

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

#### 5.4.5 Architecture and operational invariants — CURRENT; INVESTIGATION PLANNED

Consolidate 5.4.1–5.4.4 into an implementable architecture. Begin with evidence of **actual Cognee mutation behavior across the whole graph**, then derive ownership rules. Do not treat desired ownership or logical graph layers as facts about existing Cognee mechanics.

##### 5.4.5.1 Cognee mutation surface

Build an operation × artifact matrix using source inspection and controlled before/after experiments. Separate built-in behavior from behavior selected by custom Tasks, and label each conclusion as observed, source-inspected, inferred, or untested, with version/backend and write path recorded.

Operations to characterize:

- Cognify, including overlapping ingest;
- `add_data_points()` and normal graph/vector persistence, including reuse of existing IDs;
- default Improve stages;
- Memify and custom extraction/enrichment Tasks, both directly and through Improve;
- native incremental Update and native full-rebuild Update;
- `forget(memory_only=True)`, single-data deletion, and dataset deletion;
- Recall/Search as a read-path control, distinguishing graph/index changes from session, feedback, or other bookkeeping writes.

| Artifact class | Representative structures |
|---|---|
| Cognee semantic | Entity, EntityType, ordinary semantic edges |
| Project semantic | Canonical/variant/mention representations, `resolves_to` |
| Support/reconciliation | IdentityResolution, AbbreviationObservation, mention-resolution records |
| Source/context | TextDocument, DocumentChunk, TextSummary, DefinitionSummary |
| Provenance/ownership | Source refs, pipeline-run metadata, support/dependency links, edge evidence |
| Derived indexes | Node/triplet embeddings, vector collections, global-context indexes |
| Future scientific structures | Representative Claim/Measurement/Evidence and conflict/supersession probes; no full scientific model required yet |

For each cell establish whether the operation creates, reuses/merges by ID, updates properties, adds/removes edges, deletes, traverses indirectly, re-indexes, or ignores the artifact. Identify selection criteria and differences caused by source refs, shared support, node type, and pipeline-run ownership.

**Improve-specific question:** which built-in stages select or mutate non-semantic reconciliation/support structures, and how? Custom Tasks can select and write arbitrary graph structures through the graph interface; their capability does not tell us what default Improve actually does. Determine the read/write scope of each relevant built-in stage and any resulting index or materialization effects.

Controlled experiment plan:

1. Create a small fixture with one representative from each logical layer, shared and source-local support, and distinguishable sentinel properties/edges. Record its persistence path and provenance stamping.
2. Capture nodes/properties, edges/metadata, source refs, pipeline-run records, relational evidence/status, and vector/index state.
3. Run each operation from an equivalent isolated/reset baseline: second-document Cognify; default Improve; read/no-op custom Task; targeted custom mutation; incremental Update; full rebuild; Forget; deletion controls. A Task no-op is not assumed to make its enclosing Improve run a no-op.
4. Compare snapshots and report changes and selection mechanisms. Record incremental/fallback eligibility so an Update test cannot silently measure the wrong branch. Keep session/conversation state controlled.
5. Test custom artifacts written through DataPoint persistence versus graph-interface writes, with/without compatible source/run metadata, and verify survival/removal when one of multiple supporting sources disappears.

Reuse the 5.4.1 diff as existing evidence. Do not run destructive probes against the sole working benchmark graph. Forget remains lower priority than construction, maintenance, and Update, but must have a documented compatibility/repair contract.

##### 5.4.5.2 Artifact ownership / provenance model

For each artifact record creator, mutable authority, source support, source-local versus shared/derived ownership, native mutation exposure, re-Cognify survival, rebuild/replay behavior, and removal/invalidation when support disappears. Source references and pipeline-run membership must be understood operationally rather than treated as interchangeable labels.

Required output: an ownership matrix grounded in 5.4.5.1, including support/reconciliation structures and indexes, not only Entity nodes.

##### 5.4.5.3 Stable physical representation

Choose among representation A/B/C/D using the mutation evidence. Resolve whether logical canonical/variant/mention roles remain ordinary Cognee Entities with separately owned metadata, move into dedicated project structures, or use a hybrid with selected semantic links materialized into Cognee's graph.

Preserve useful native identity behavior. Retain scope-relative canonicality, non-destructive reconciliation, and distinct semantic/support/source layers. No representation is locked yet.

##### 5.4.5.4 Write / reconcile / read / update lifecycle

Specify which Tasks belong inside transformed Cognify and which belong in Memify/Improve; when maintenance runs; how failed or stale derived state is detected; and what a custom Retriever accepts as usable state.

| Lifecycle phase | Proposed seam | Remaining contract |
|---|---|---|
| Ingest | Native Remember/direct Cognify + B transform | Construction Tasks, special-route behavior, provenance |
| Reconcile | Idempotent custom Memify/Improve Tasks | Selection, replay scope, interaction with default stages |
| Read | Registered custom Retriever/SearchType | Resolution, identity expansion, layer filtering, deduplication, attribution |
| Update | Native full rebuild when transform supplied, then maintenance | Equivalent derived state, shared support, status/failure behavior |
| Delete | Native Forget where sufficient, cleanup/repair where required | Removal/invalidation of source-dependent versus shared artifacts |

##### 5.4.5.5 Operational invariants and Stage-6 handoff

Candidate invariants to finalize from evidence:

- source text remains authoritative;
- reconciliation is non-destructive and canonicality is scope-relative;
- identity, provenance, and source applicability are distinct;
- query-time resolution precedes broad semantic activation;
- identity hops differ from ordinary semantic hops;
- support nodes are excluded from normal semantic recall;
- ambiguous mentions remain ambiguous rather than being forced;
- project state does not depend on mutable Cognee-owned properties;
- derived structures are replayable/idempotent, with explicit invalidation;
- rebuild + maintenance reproduces equivalent logical derived state, without requiring identical LLM outputs or node UUIDs;
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

Desired support chain remains:

```text
source document/chunk
    -> observation/mention evidence
    -> IdentityResolution
    -> semantic resolves_to relationship
```

This supplies a basis for update/truth maintenance without committing to a full truth-maintenance system now.

---

## Stage 6 — Custom processing architecture — PLANNED

Goal: move manually demonstrated representations into actual Cognee processing tasks/pipelines and ensure they participate in lifecycle/provenance behavior.

### 6.1 Explicit source/intermediate representations

Retain source occurrences and extraction decisions explicitly.

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

Then:

```text
observations + existing document/corpus context
    -> identity resolver
    -> IdentityResolution
    -> materialized semantic resolves_to links
```

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
- verify metadata attached automatically by DataPoint persistence versus metadata requiring explicit graph-interface writes.

The exact Task order must follow the 5.4.5 decision. A likely division is document vocabulary/context + mixed generic/typed extraction inside construction, followed by source-grounded identity reconciliation and selected semantic materialization as maintenance. Do not force every transformation into one pipeline.

Lifecycle validation should cover direct Cognify, standard Remember, overlapping ingest, transformed full-rebuild Update, maintenance replay, and cleanup after source removal. Test no-transform native behavior and unsupported combinations for the B patch. Verify custom side effects explicitly rather than assuming native rollback handles them.

**Requirement:** source/support/derived structures must have documented, testable lifecycle behavior. Native compatibility is preferred; a small explicit cleanup/repair path is acceptable where native Forget is insufficient. Avoid allowing rare deletion behavior to dominate the representation design.

### 6.5 Registered identity-aware retrieval

Package the Stage-5.3 proof of concept behind a custom Retriever/SearchType using Cognee graph/vector interfaces. Perform query-time resolution before scope-aware identity expansion and semantic-neighborhood union. Preserve provenance under logical fact deduplication and provide semantic, source-aware, explanation, and graph-management modes as warranted.

Keep RAG as a reference/fallback and control conversation/session state during comparisons. Restore and strengthen the Stage-5.3 benchmark so it remains correct after subsequent source ingestion and maintenance.

### 6.6 Replay, mutation, and lifecycle regressions

Turn 5.4.5's matrices/invariants into focused regression scenarios:

- re-ingest a source and rerun maintenance without duplicate derived objects;
- add an overlapping source without losing identity/reconciliation state;
- change a definition/alias and invalidate or recompute affected resolution;
- remove one source while retaining facts/links supported by another;
- preserve ambiguity and negative/non-equivalence controls;
- preserve source attribution across logical duplicates and identity closure;
- document stale-state detection/repair and differences between native incremental Update and customized full rebuild.

### Post-Stage-6 checkpoint

Stop and reassess the architecture before moving into stronger schemas/ontologies. Review:

- selected physical identity representation and logical Entity roles;
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

This stage should build on the support/provenance layer rather than conflating claims with canonical semantic entities.

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

Current stage: **5.4.5**. Immediate next subphase: **5.4.5.1 Cognee mutation surface**.

5.4.1–5.4.4 are complete enough to proceed. B is the preferred lifecycle integration direction; its implementation and the final physical identity representation are still pending. The expanded mutation investigation has been agreed but not executed.

Immediate sequence:

1. Finish this bookkeeping revision; use the companion architecture reference for detailed code/extension context.
2. Characterize built-in mutation/selectivity across semantic, support/reconciliation, source, provenance, and index artifacts, starting with persistence, Cognify, and default Improve/Memify.
3. Run controlled lifecycle probes with isolated/reset baselines and compare graph plus index/evidence/status state.
4. Derive ownership rules and choose the stable physical identity representation.
5. Specify extraction-time versus maintenance Tasks, custom retrieval behavior, update replay, and cleanup/repair contracts.
6. Finalize operational invariants and Stage-6 requirements; implement Stage 6 only after this handoff.
7. Keep mention compaction and a general predicate ontology deferred; retain the post-Stage-6 architecture check-in.

## Revision record — 2026-10-11

- Replaced the stale 5.3.1 current-status marker with 5.4.5.
- Recorded demonstrated 5.3 query-time resolution and its regression under overlapping ingest.
- Replaced 5.4A/5.4B with refined 5.4.1–5.4.5, retaining scope/timing/evolution questions.
- Recorded overlapping-ingest mutation findings, native retrieval characterization, and the preferred B lifecycle extension proposal and limitations.
- Expanded 5.4.5 to investigate Cognee's actual behavior on support/reconciliation and other graph artifacts before assigning ownership or locking representation.
- Updated architecture principles and Stage-6 sequencing/retrieval/lifecycle requirements; retained the Stage-6 checkpoint and planned Stages 7–10.
- Did not mark the B patch, 5.4.5 experiments, or final representation as implemented.
