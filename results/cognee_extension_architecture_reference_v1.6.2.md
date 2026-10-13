# Cognee Extension Architecture & Lifecycle Reference

**Project context:** `cognee-science-lab`  
**Pinned Cognee version:** 1.6.2  
**Original review date:** 2026-10-10  
**Identity-design update:** 2026-10-13  
**Purpose:** Reusable reference for identity management and future Cognee integrations. This note focuses on extension boundaries, lifecycle behavior, and version-resilient design rather than one specific identity representation.

## 1. Design objective

Prefer integrations that compose with Cognee's intended abstractions and survive upgrades without maintaining a fork.

Recommended dependency order, strongest first:

1. Public memory/low-level APIs and configuration.
2. `DataPoint` / `graph_model` contracts.
3. `Task` and custom pipeline composition.
4. `memify` / `improve` custom enrichment tasks.
5. Registered custom `Retriever` / `SearchType`.
6. `GraphDBInterface` / vector-engine abstractions.
7. Selected subclass points on built-in retrievers when necessary.
8. Internal utilities/private methods only as a last resort.
9. Backend-specific Ladybug/LanceDB details only when unavoidable.

A Python function being importable is not the same as being a stable extension API.

## 2. High-level operational map

```text
remember()
    add()
    cognify()
        Task-based graph construction pipeline
    improve()                       # normally enabled
        fixed top-level stage registry
        triplet_enrichment stage
            memify()
                custom extraction_tasks / enrichment_tasks supported

recall()
    routing/session behavior
    search()
        Retriever/SearchType
            graph/vector interfaces

update()
    try chunk-level incremental update
        default extraction configuration only in 1.6.2
    otherwise full rebuild
        forget(memory_only=True)
        pinned add()                # same data_id
        cognify()

forget()
    fixed lifecycle orchestration
        graph/vector deletion
        session invalidation
        edge-evidence cleanup
        pipeline-status reset
```

The operations do **not** have symmetric extension models. Retrieval, Cognify, and Memify are substantially more composable than Update/Forget.

## 3. Retrieval extension model

### 3.1 Native retrieval characterization

- `RAG_COMPLETION`: chunk/vector retrieval. It need not understand graph identity semantics.
- `GRAPH_COMPLETION`: vector candidate discovery, graph projection/optional neighborhood retrieval, edge ranking, then context rendering.
- `HYBRID_COMPLETION`: passage retrieval plus entity/fact retrieval with graph neighborhoods.

Native graph retrieval treats custom relationships as graph relationships; it does not provide semantic identity behavior merely because an edge is named `resolves_to`.

### 3.2 GraphCompletionRetriever nesting

```text
search()/recall()
    selects GraphCompletionRetriever
        get_retrieved_objects()
            get_triplets()
                determine indexed collections / weights
                brute_force_triplet_search(...)
                    vector candidate search
                    relevant node IDs
                    graph projection / optional neighborhood
                    score + rank Edge triplets
        get_context_from_objects(...)
            resolve_edges_to_text(...)
        completion generation
```

A custom retriever can inherit most of this behavior and override only the necessary stage, or subclass `BaseRetriever` and compose Cognee's graph/vector interfaces.

### 3.3 Preferred extension seam

Cognee has an explicit custom retriever registry (`use_retriever(...)`) and community retriever packaging pattern. Prefer a **new SearchType** rather than silently overriding built-in `HYBRID_COMPLETION` or `GRAPH_COMPLETION`.

Good target:

```text
ScientificMemoryRetriever / IdentityAwareGraphRetriever
    Cognee vector engine
    Cognee GraphDBInterface
    Cognee node/edge objects
    Cognee completion/context conventions
```

Avoid:
- patching `recall()` / `search()`;
- direct Ladybug traversal;
- private Hybrid methods (observed refactoring across minor versions);
- relying on `brute_force_triplet_search` as a long-term public contract.

## 4. Cognify / initial graph construction

Cognify is strongly pipeline-oriented. The default pipeline is composed from Tasks and ultimately runs with the stable pipeline name `cognify_pipeline`.

Conceptually:

```text
cognify()
    get_default_tasks()
        classify_documents
        extract_chunks_from_documents
        extract_graph_and_summarize
        add_data_points
        extract_dlt_fk_edges
    run_pipeline(... pipeline_name="cognify_pipeline" ...)
```

Custom `DataPoint` / `graph_model` behavior and custom Tasks are first-class extension mechanisms. `run_custom_pipeline(...)` is documented for explicit sequential task control, and Cognee ships examples that replace the default Cognify task list.

**Assessment:** high-confidence, high-resilience extension surface.

## 5. Improve / Memify extension model

### 5.1 Top-level Improve stages are fixed in 1.6.2

`improve()` executes a static `DEFAULT_STAGES` registry in order. The nine stages are:

1. `feedback_weights`
2. `persist_session_qa`
3. `persist_agent_traces`
4. `extract_agent_context`
5. `distill_sessions`
6. `update_user_preferences`
7. `build_truth_subspace`
8. `triplet_enrichment`
9. `global_context_index`

There is no public dynamic `register_improve_stage(...)` hook in 1.6.2. The stage order is explicitly load-bearing.

**Conclusion:** adding a brand-new Improve stage by mutating `DEFAULT_STAGES` would be internal coupling and is not recommended.

### 5.2 The triplet-enrichment stage deliberately exposes custom Memify Tasks

`ImproveKwargs` accepts:

- `extraction_tasks`
- `enrichment_tasks`
- `data`
- `node_type`

These are passed into the existing `TripletEnrichmentStage`, which calls `memify(...)`. If custom memify Tasks are supplied, the normal graph-change watermark shortcut is intentionally bypassed because the work is semantically different from default triplet embedding.

This is a much stronger extension seam than adding a new Improve stage.

Recommended pattern for reusable graph-maintenance integrations:

```text
improve(dataset=..., extraction_tasks=[...], enrichment_tasks=[...])
    fixed Improve orchestrator
        triplet_enrichment
            memify()
                our reconciliation / normalization / scientific enrichment Tasks
```

Cognee's own engineering issue describes Memify Tasks as Task-wrapped async functions that read/write the graph and explicitly lists reconciliation/consolidation-style operations as intended graph-maintenance work.

**Assessment:** custom Memify tasks are one of the best candidate homes for identity reconciliation and future post-Cognify scientific transformations.

### 5.3 Transport caveat

The local Python API is richer than some remote/Rust HTTP surfaces. Current Rust Memify documentation states that the HTTP DTO does not expose Python's custom `extraction_tasks`, `enrichment_tasks`, `data`, `node_name`, or `node_type` surface.

Therefore distinguish:

- **Python package extension compatibility:** strong.
- **Remote Cognee server/API portability:** weaker unless the custom extension is installed/runs server-side.

This distinction should be tracked for all future integrations.

## 6. Update extension model (Cognee 1.6.2)

### 6.1 Native structure

```text
update(data_id, replacement)
    resolve/pin existing data_id
    determine whether incremental path is allowed

    if allowed:
        incremental_update(...)
            diff stored processed text vs replacement
            replace only touched chunk regions
            preserve unaffected chunks
            re-extract new/replaced chunks
    else:
        full rebuild
            forget(data_id, memory_only=True)
            reset add/cognify status as needed
            add(replacement, pinned same data_id)
            cognify(...)
```

The document `data_id` is deliberately preserved on both paths.

### 6.2 Critical restriction

In 1.6.2, chunk-level incremental update rejects:

- non-default `graph_model`;
- any `custom_prompt`;
- document metadata / `node_set` changes;
- per-call graph/vector DB config.

For custom `graph_model` or prompt, native update forces the **full rebuild** path. The code explains why: the incremental baseline does not persist enough extraction configuration to guarantee that newly extracted chunks use the same schema/prompt as old chunks.

This is a sound semantic safeguard, but it means the current incremental updater is not a general custom-pipeline extension seam.

### 6.3 ChunkPolicy is narrow

`ChunkPolicy` is explicitly replaceable, but it determines chunk replacement/reconciliation policy. It is not a hook for arbitrary graph reconciliation or post-processing Tasks.

### 6.4 Full rebuild calls built-in Cognify, not an arbitrary custom pipeline

The fallback path calls `cognify(graph_model=..., custom_prompt=...)`; it does **not** accept an arbitrary Task list.

This has an important integration consequence:

If an extension exists only as an extra custom Cognify Task, native `update()` will not automatically rerun it after a fallback rebuild.

A more lifecycle-friendly architecture is to make post-processing/reconciliation an **idempotent Memify/Improve task** that can be rerun after Cognify, rather than making it exist exclusively inside one custom Cognify pipeline.

Possible wrapper:

```text
science_update(...)
    cognee.update(...)
    cognee.improve(... custom memify tasks ...)
```

This is a small orchestration wrapper rather than a fork of Cognee update internals.

### 6.5 Remote update caveat

Pinned 1.6.2 explicitly warns that remote `PATCH /api/v1/update` has no slots for several local Python options including `graph_model`, `custom_prompt`, `chunker`, and `policy`; those are dropped and server-side configuration is used.

Again, local Python extension and remote/API extension are separate portability dimensions.

**Assessment:** Update is a moderate/weak extension surface. Prefer treating it as lifecycle orchestration around reusable transformations rather than customizing its internal incremental engine unless later requirements justify it.

## 7. What incremental update preserves/deletes

Cognee's architecture documentation describes the incremental algorithm as:

- paragraph-anchored multi-region diff;
- expand changed spans to existing chunk boundaries;
- re-chunk only affected areas using the stored chunk token budget;
- preserve unchanged chunk IDs and boundaries;
- delete replaced chunks and summaries;
- delete entities that become orphaned from all surviving chunks;
- remove affected triplet embeddings;
- run LLM graph extraction only for new chunks;
- renumber surviving chunks to keep contiguous `chunk_index`.

The key architectural idea is **chunk-scoped ownership plus orphan detection**, not indiscriminate graph replacement.

For our integrations, the unanswered practical question is how custom nodes/edges are classified with respect to that ownership. That should be tested only after deciding how custom artifacts are written/stamped.

## 8. Forget / deletion model — compatibility constraint, not design driver

Forget remains a compatibility/lifecycle concern without dictating the entire representation. The recorded identity proposal now requires explicit original-source → generated-source retirement and shared contribution repair for the admitted workflows; this is not a universal deletion framework.

For single-data `forget(memory_only=True)`, pinned 1.6.2 does:

```text
forget(data_id, memory_only=True)
    delete_data_nodes_and_edges(...)
    invalidate sessions referencing deleted graph elements
    delete relational edge_evidence for that data item
    reset pipeline_status["cognify_pipeline"] for that Data row
```

There is no custom Task/callback hook.

Cognee's graph abstraction does include provenance-aware primitives such as source-ref attachment/removal and finding nodes/edges by source ref or pipeline run. Native deletion can only manage custom artifacts coherently if those artifacts are deliberately written with compatible ownership/provenance semantics.

We should **not assume** custom identity/scientific structures are naturally deleted correctly.

Acceptable future approaches include:

- tolerate stale custom enrichment after rare Forget operations and repair/rebuild later;
- call a lightweight project-specific cleanup wrapper;
- optionally use Cognee source refs when a structure has clear document ownership;
- avoid contorting the main architecture solely to make native Forget perfect.

## 9. Custom pipeline lifecycle and pipeline status

Cognee tracks per-data pipeline completion by **pipeline name + dataset**. Standard Cognify uses the stable name:

```text
cognify_pipeline
```

and incremental loading uses those markers to skip already-completed data.

Implications:

1. A custom pipeline with a different name has independent completion semantics.
2. A custom pipeline intentionally replacing Cognify can use `pipeline_name="cognify_pipeline"` so standard Cognify-style status semantics apply; Cognee documentation/examples explicitly use this pattern for alternate Cognify extraction routes.
3. Single-data `forget(memory_only=True)` explicitly resets only the `cognify_pipeline` marker. It does not know arbitrary custom pipeline names.
4. Therefore lifecycle behavior depends not just on Tasks but also on how the custom pipeline is named and whether it is a replacement for Cognify or a separate enrichment operation.

Recommended convention:

- If replacing the Cognify task list while preserving Cognify semantics, run under `cognify_pipeline`.
- If adding a logically separate post-processing stage, keep it separate and preferably use Memify/Improve rather than disguising it as Cognify.
- Do not overload pipeline-status names merely to get deletion behavior.

## 10. General integration pattern emerging

For identity management **and future integrations**, the most upgrade-resilient architecture currently looks like:

```text
WRITE / EXTRACT
    Cognee add + cognify
        default or custom graph_model / Task pipeline

MAINTAIN / RECONCILE
    Cognee improve
        fixed stage orchestrator
            custom Memify Tasks
                idempotent graph transformations

READ
    Cognee recall/search
        registered custom Retriever/SearchType when native retrieval is insufficient
        use GraphDBInterface/vector interfaces rather than backend-specific queries

UPDATE
    Cognee update
        native incremental path where compatible
        native full rebuild where required
    then replay idempotent Memify/Improve transformations

DELETE
    native Forget where sufficient
    project-specific cleanup/repair if necessary
    lower design priority
```

This structure intentionally separates **raw extraction**, **graph maintenance/reconciliation**, and **retrieval semantics** while keeping each inside a Cognee-supported operational layer.

## 11. Extension-strength matrix

| Surface | Extension quality | Recommended use |
|---|---|---|
| `DataPoint` / `graph_model` | Strong | Domain graph structures |
| `Task` + custom pipeline | Strong | Custom extraction/orchestration |
| custom Memify Tasks | Strong | Reconciliation, consolidation, post-processing |
| `improve()` top-level stages | Fixed | Use existing triplet-enrichment/Memify seam; do not patch registry |
| custom Retriever/SearchType | Strong | Domain/identity-aware retrieval |
| `GraphDBInterface` | Strong | Backend-independent graph access |
| native incremental `update()` | Constrained | Use as provided; avoid internal customization initially |
| `ChunkPolicy` | Narrow but intentional | Chunk replacement rules only |
| `forget()` | Fixed | Compatibility/cleanup concern, not architecture driver |
| private retrieval/update internals | Fragile | Avoid |
| backend-specific Ladybug queries | Fragile | Avoid |

## 12. Design criteria for future project extensions

Evaluate every new capability against these questions:

1. **Representation:** semantic graph augmentation, secondary subgraph, auxiliary store, or hybrid?
2. **Extraction:** can it be generated via `graph_model` or a public Task pipeline?
3. **Maintenance:** can it be implemented as an idempotent Memify/Improve transformation?
4. **Retrieval:** can it be consumed via a registered custom Retriever using Cognee graph/vector interfaces?
5. **Update replay:** after a full rebuild, can the extension be deterministically recreated without patching `update()`?
6. **Ownership/provenance:** does it have source-specific ownership, corpus-level ownership, or derived-state ownership?
7. **Forget:** what cleanup is required, and how much imperfection is acceptable?
8. **Pipeline status:** is this Cognify replacement work or a logically separate pipeline?
9. **Backend independence:** does it avoid Ladybug/LanceDB-specific assumptions?
10. **Transport independence:** does it work only in local Python, or also through remote/server APIs?
11. **Version resilience:** does it depend on documented contracts or private method structure?

## 13. Immediate implications for Stage 5.4 — updated 2026-10-13

Broad mutation/persistence characterization is complete in cognee_stage5_4_5_1_initial_findings.md. Initial ownership/representation choices are recorded in cognee_stage5_4_5_identity_representation_proposal.md; current work is operation walkthroughs toward the lifecycle contract.

The selected initial direction uses registered generated identity sources, durable structured assignments, ordinary Entity nodes with explicit occurrence IDs, persistent mention markers, and contribution-bearing resolution edges. Identity groups consist of variants without a privileged canonical member. It avoids added authoritative Entity fields and does not require assignment support nodes.

- Do not require default RAG or generic graph traversal to enforce identity semantics; use the custom Retriever.
- calculate_chunk_graphs can compute deterministic graphs but is not a reference-only existing-endpoint publication contract.
- A custom source-bound loading Task must carry ID-based custom_edges, deliberately attach existing endpoint retention and preserve full contribution collections.
- Native document-level ownership is the initial retention granularity; original-input dependency and applicability remain separate.
- Keep replayable project maintenance and full-source rebuild as the initial lifecycle direction; forwarded customization is not automatic in native Update.
- Verify derived-source retirement, shared edge property repair and failure/read eligibility instead of assuming native owner cleanup handles them.

The preferred B Task-list transform remains proposed and unimplemented. This direction neither implements it nor establishes which routing/loader wiring is sufficient.

## 14. Remaining questions for controlled tests — current design

The earlier source-context, native deletion, incremental property and watermark questions now have scoped results in the characterization report. The combined new identity form is untested. Focus further checks on:

1. Publishing a new explicit-ID Entity and an ID-based edge to an existing Entity without rewriting the existing fields, while intentionally retaining both endpoints.
2. Edge-only publication and contribution collection serialization/aggregation under multiple source owners.
3. Distinct same-text mention Entities, persistent mention markers and unresolved-to-resolved replay.
4. Original-source Update/Forget triggering derived-source maintenance; generated-source full rebuild recreating solely owned endpoints and markers.
5. Failure/retry and reader eligibility across incomplete publication.
6. Default/selected native operations, consolidation/remapping admission, and graph/vector readers consuming this representation.
7. Remote deployment/transport and version-upgrade compatibility only when those profiles are admitted.

No new runtime test or traversal benchmark was run for this documentation update.

## 15. Source anchors

Pinned v1.6.2:

- Improve orchestrator: https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/improve/improve.py
- Improve stage registry: https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/registry.py
- Improve stages / TripletEnrichmentStage: https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/stages.py
- Update: https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/update/update.py
- Forget: https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/forget/forget.py

Current project documentation/examples used to understand intended extension direction:

- Cognee skill / public extension guidance: https://github.com/topoteretes/cognee/blob/main/cognee/skill.md
- Architecture guide: https://github.com/topoteretes/cognee/blob/main/CLAUDE.md
- Custom Tasks example: https://github.com/topoteretes/cognee/blob/main/examples/guides/custom_tasks_and_pipelines.py
- Examples catalog: https://github.com/topoteretes/cognee/blob/main/examples/README.md
- Community extensions: https://github.com/topoteretes/cognee-community
- Memory-transformation / Memify design issue: https://github.com/topoteretes/cognee/issues/3389

### Version note

This reference distinguishes **observed v1.6.2 behavior** from **current documentation/design direction**. Internal details should be rechecked when the project pin changes. Public DataPoint/Task/Retriever/graph-interface contracts are preferred precisely to minimize that review burden.

## 16. Custom Cognify pipeline injection patch option

### 16.1 Motivation

A project-level `science_remember()` / `science_update()` wrapper can reproduce the full-rebuild lifecycle, but it would duplicate native Update bookkeeping such as `data_id` resolution, `forget(memory_only=True)`, pipeline-status reset, pinned re-add, DLT replacement checks, chunk-budget handling, and `UpdateResult` construction.

A smaller alternative is to patch Cognee so native `remember()` and native full-rebuild `update()` can invoke a caller-customized Cognify task list while retaining native lifecycle orchestration.

### 16.2 Preferred patch shape: transform Cognify's standard Task list

Do **not** replace `cognify()` with a direct call to `run_custom_pipeline()`. `cognify()` already owns important semantics:

- extractor/runtime setup;
- ontology/config resolution;
- route selection for STANDARD vs DLT/code items;
- background/foreground pipeline execution;
- `pipeline_name="cognify_pipeline"` bookkeeping;
- `needs_llm` calculation;
- rollback/error handling;
- normal `PipelineRunInfo` return values consumed by `remember()` / `update()`.

Instead, add an SDK-local parameter conceptually like:

```python
cognify_task_transform: Callable[[list[Task]], list[Task]] | None = None
```

After Cognee builds the standard route with `get_default_tasks(...)` (or temporal/GLiNER equivalent, depending on intended scope), apply the transform before creating `tasks_by_route` and before `pipeline_needs_llm(...)` is calculated:

```text
cognify()
    build native STANDARD tasks
        classify
        chunk
        extract/summarize
        persist
        provenance / contradiction / temporal extras

    optional task transform                 <- small patch seam
        append / insert / remove / replace tasks

    tasks_by_route
        STANDARD -> transformed list
        DLT_SOURCE -> native DLT list
        CODE -> native code list
        CODE_REPO -> native repo list

    native run_pipeline(... pipeline_name="cognify_pipeline" ...)
```

A transform is preferable to supplying a complete replacement list because it inherits upstream changes to Cognee's default task sequence automatically. A closure can capture project configuration while receiving the already-configured native `Task` objects.

### 16.3 Changes required in pinned 1.6.2

**`cognify()`**

- add the optional transform/callback argument;
- apply it to the intended task route after native tasks are built;
- reject or explicitly define unsupported combinations (remote execution, dry-run estimator, non-standard routes if not supported);
- calculate `needs_llm` from the post-transform lists, which the existing code already does once `tasks_by_route` is built.

**`remember()`**

- add the argument to `RememberKwargs` / `_COGNIFY_ONLY`;
- no lifecycle rewrite is needed: `_remember_inner()` already forwards recognized Cognify-only kwargs to the single native `cognify()` call;
- native `RememberResult`, background handling, automatic Improve, operation telemetry, Add, and dataset resolution remain unchanged.

**`update()`**

- add the same optional argument;
- any non-null transform should force the full-rebuild path in 1.6.2, because the incremental engine cannot know the semantics of arbitrary custom tasks;
- pass the argument into the existing full-rebuild `cognify()` call;
- retain native `resolve_data_id`, DLT checks, `forget(memory_only=True)`, `reset_data_pipeline_status`, pinned `DataItem` re-add, chunk-size reuse, and `UpdateResult` behavior.

This is likely a small patch (tens of lines plus tests) rather than a maintained fork architecture.

### 16.4 Why this is preferable to patching Remember/Update with an arbitrary pipeline runner

If `remember()` or `update()` accepted a raw `run_custom_pipeline` function, the replacement pipeline would need to recreate Cognify-specific routing and bookkeeping and return the exact result structure those APIs expect.

Injecting at the **Task-list construction seam inside Cognify** avoids that. `remember()` and `update()` continue to call a normal Cognify operation; only the STANDARD task list changes.

### 16.5 Important limitations / design decisions

1. **Local Python only initially.** A Python callable is not serializable through Cognee's remote HTTP API. Remote use would require installing/configuring the extension server-side or defining a named pipeline registry.
2. **Incremental Update unsupported initially.** Any custom task transform should trigger full rebuild until an explicit incremental contract exists.
3. **Dry-run accounting.** Native Cognify cost estimation does not know arbitrary custom tasks; safest initial behavior is to reject `dry_run=True` when a transform is supplied, or clearly scope the estimate to native tasks only.
4. **Route scope.** For `cognee-science-lab`, modifying only `CognifyRoute.STANDARD` is sufficient. DLT/code routes should remain native unless deliberately supported later.
5. **Rollback.** Native Cognify rollback semantics are preserved for native artifacts, but side effects introduced by custom tasks may need their own idempotence/cleanup contract.
6. **Task-chain compatibility.** Inserted tasks must obey Cognee's pipeline input/output semantics; global graph-maintenance tasks may still fit better in Memify/Improve.
7. **Special Remember routes.** `content_type="code"`, skills, sessions, MemorySource imports, etc. bypass or alter the ordinary add+Cognify route and should not silently claim support for the transform.

### 16.6 Upgrade resilience

This seam appears relatively promising for a maintained patch:

- pinned 1.6.2 builds route-specific task lists and then passes a resolver into `run_pipeline`;
- current Cognee main still has the same `tasks_by_route -> resolve_cognify_tasks -> run_pipeline(... pipeline_name="cognify_pipeline")` structure;
- native `remember()` continues to have a single Cognify invocation point;
- Update implementation is more volatile across versions, but even a substantially simplified current Update still funnels rebuilding through one `cognify()` call.

Therefore the patch's conceptual anchor is stable even if exact line numbers change. It is likely easier to reapply than duplicating Update orchestration in project code.

### 16.7 Comparison of lifecycle strategies

| Strategy | Main benefit | Main cost |
|---|---|---|
| Native Cognify + post-maintenance only | No Cognee patch | Requires every project operation to be valid after standard Cognify |
| Project `science_remember` + `science_update` wrappers | Complete project control | Duplicates/depends on native lifecycle internals, especially Update bookkeeping |
| **Small Cognify task-transform patch** | Native Remember/Update lifecycle + arbitrary extraction-time ordering | Small maintained patch; local-Python-first; custom tasks force full rebuild |

**Current preferred option to evaluate further:** the small Cognify task-transform patch, because it preserves native lifecycle orchestration while removing the artificial constraint that all project customization must occur after standard Cognify.

### 16.8 Source anchors for this option

- v1.6.2 Remember: one permanent-memory `add()` followed by one `cognify()` call; recognized Cognify kwargs are routed through `_COGNIFY_ONLY`.
  - https://raw.githubusercontent.com/topoteretes/cognee/v1.6.2/cognee/api/v1/remember/remember.py
- v1.6.2 Cognify: builds native task lists, forms `tasks_by_route`, computes `needs_llm`, then invokes native `run_pipeline(... pipeline_name="cognify_pipeline" ...)`.
  - https://raw.githubusercontent.com/topoteretes/cognee/v1.6.2/cognee/api/v1/cognify/cognify.py
- v1.6.2 Update full rebuild: native `forget(memory_only=True)` -> status reset -> pinned `add()` -> single `cognify()` invocation.
  - https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/update/update.py
- Current main Cognify still uses route-specific task lists and the same Cognify pipeline-name/run-pipeline structure, supporting the patch's conceptual rebase stability.
  - https://github.com/topoteretes/cognee/blob/main/cognee/api/v1/cognify/cognify.py

## 17. Identity-source publication seams — source-inspected, 2026-10-13

The detailed representation and preliminary ownership matrix live in [the proposal](cognee_stage5_4_5_identity_representation_proposal.md); this section records the extension implications.

| Seam | What it supplies | What it does not supply automatically |
|---|---|---|
| Registered Data item | Native source lifecycle and chunks for generated identity material | A dependency cascade from the original input document |
| calculate_chunk_graphs | Deterministic replacement of standard text LLM graph extraction | Existing-node reference-only writes, custom loading, or persisted routing through Update |
| Explicit Entity id | Ordinary ID-keyed node persistence with distinct IDs for identical names | Protection from optional consolidation/remapping |
| add_data_points custom_edges + real source ctx | ID-based relationships with source-bound document ownership | Existing endpoint retention, per-assignment property merging, or chunk-to-edge evidence |
| attach_node_source_refs | Intentional retention of matched existing nodes without field replacement | Applicability or original-input provenance |
| Custom Retriever | Project-specific identity-group/mention traversal and output policy | Equivalent behavior in native retrieval/triplet indexing |

Keep computation separate from publication: callbacks can calculate intent, but the loading Task must control new-node writes, existing-node ref attachment, full edge contribution payloads and checks. Native full-rebuild Update does not accept arbitrary callback kwargs as a durable route. Determine the loader/routing sequence under the B extension during .4; the small core patch, derived-source orchestration and this combined publication workflow remain unimplemented.

No guarantees are added for every backend, optional maintenance stage, remote path or access-control configuration.

