# Cognee Extension Architecture & Lifecycle Reference

**Project context:** `cognee-science-lab`  
**Pinned Cognee version:** 1.6.2  
**Original review date:** 2026-10-10  
**Identity-design update:** 2026-10-13  
**Current implementation pointer (2026-10-20):** [SESSION_HANDOFF.md](../docs/SESSION_HANDOFF.md) records the delivered baseline, tests/Mac reproduction and next task. This reference retains pinned source findings and dated design evolution; historical evidence limits do not negate later bounded runtime fixtures.

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
9. Keep backend-specific implementation inside native adapters; project integrations use configured interfaces and refuse unsupported capabilities. Source inspection of an adapter does not authorize a vendor-specific project fallback.

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

The selected initial direction uses registered generated identity sources, durable structured assignments, ordinary Entity nodes with explicit local reference-group IDs, persistent mention markers, and contribution-bearing resolution edges. Identity groups consist of variants without a privileged canonical member. It avoids added authoritative Entity fields and does not require assignment support nodes.

- Do not require default RAG or generic graph traversal to enforce identity semantics; use the custom Retriever.
- calculate_chunk_graphs can compute deterministic graphs but is not a reference-only existing-endpoint publication contract.
- A custom source-bound loading Task must carry ID-based custom_edges, deliberately attach existing endpoint retention and preserve full contribution collections.
- Native document-level ownership is the initial retention granularity; original-input dependency and applicability remain separate.
- Keep replayable project maintenance and full-source rebuild as the initial lifecycle direction; forwarded customization is not automatic in native Update.
- Verify derived-source retirement, shared edge property repair and failure/read eligibility instead of assuming native owner cleanup handles them.

The preferred B Task-list transform remains proposed and unimplemented. This direction neither implements it nor establishes which routing/loader wiring is sufficient.

## 14. Original controlled-test inventory and current coverage

The earlier source-context, native deletion, incremental property and watermark questions now have scoped results in the characterization report. The new identity form was not runtime-validated by this dated source review. Later Stage-6 fixtures demonstrate bounded cases from items 1, 2 and 5 below, plus selected marker, retirement and rebuild cases from items 3 and 4. This is the original test inventory, not a list of wholly unstarted work; the [session handoff](../docs/SESSION_HANDOFF.md) separates implemented cases from the remaining coverage. Broader lifecycle, native-entry-point and retrieval integration remain partial or unimplemented, and item 7 applies only when those profiles are admitted.

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
| Registered Data item | Native source lifecycle; a TextDocument graph anchor can be published without generated identity chunks | A dependency cascade from the original input document |
| calculate_chunk_graphs | Deterministic replacement of standard text LLM graph extraction | Existing-node reference-only writes, custom loading, or persisted routing through Update |
| Explicit Entity id | Ordinary ID-keyed node persistence with distinct IDs for identical names | Protection from optional consolidation/remapping |
| add_data_points custom_edges + real source ctx | ID-based relationships with source-bound document ownership | Existing endpoint retention, per-assignment property merging, or chunk-to-edge evidence |
| attach_node_source_refs | Intentional retention of matched existing nodes without field replacement | Applicability or original-input provenance |
| Custom Retriever | Project-specific identity-group/mention traversal and output policy | Equivalent behavior in native retrieval/triplet indexing |

Keep computation separate from publication: callbacks can calculate intent, but the loading Task must control new-node writes, existing-node ref attachment, full edge contribution payloads and checks. Native full-rebuild Update does not accept arbitrary callback kwargs as a durable route. The initial chunkless identity-source path uses custom Tasks directly; calculate_chunk_graphs remains an optional seam for chunk-based extensions. The reviewed direct custom-Task loader/source binding now has native fixtures. The B core patch and standard-entry-point/derived-source orchestration remain unimplemented; they are later implementation work, not another .4 design review.

No guarantees are added for every backend, optional maintenance stage, remote path or access-control configuration.

## 18. Reusable knowledge integration methodology and findings — 2026-10-13

The project is developing a methodology for turning selected information into graph-structured knowledge that Cognee, with selected extensions, can maintain and use over time. Identity is the first worked example. The recurring activities are:

| Activity | Concrete responsibility |
|---|---|
| Describe | Interpret source information using a defined representation and save a structured description of the intended knowledge, references, applicability and provenance. For identity, this produces the durable identity source. |
| Publish | Integrate that description into existing graph structures using exact IDs, controlled reference/write/retention actions and verified persistence. calculate_chunk_graphs is a computation seam; a source-bound loading Task completes publication. |
| Maintain | Keep assignments, graph structures and consumed derived representations current after input or graph changes; define shared retention, retirement, replay and failure eligibility. |
| Retrieve | Interpret the structures under the right query context and expose useful knowledge with attribution, appropriate traversal and ambiguity handling. |

### 18.1 Representation meaning and rules: possible ontology connection

The concepts, relationship meanings and domain rules can constitute a small domain ontology. For identity, examples include occurrence-specific mentions, reusable variants, scoped equivalence and directed reference. A graph schema additionally describes how these concepts are encoded and validated. Storage IDs, native retention refs, publication/update procedures and operational eligibility also need explicit integration rules; calling the whole package an ontology does not supply those procedures.

**Investigation topic, not a new prerequisite:** determine whether a lightweight vocabulary/schema, a formal ontology, or a combination best expresses the selected domain concepts and constraints. Investigate how that description could guide structured knowledge generation, graph publication, validation and retrieval. Separate domain semantics from Cognee persistence/lifecycle behavior. Do not adopt a formalism or inference engine merely from this framing.

Stage 7 is the primary ontology/schema investigation point. Capture concrete identity examples now, carry them through the post-Stage-6 review, and use them to assess later measurement/scientific structures in Stage 8. Scientific justification policies remain deferred.

### 18.2 Reusable integration findings register

The Activities column identifies where each finding is directly relevant, not the Task or API that implements it. Maintain includes the lifecycle of actively consumed indexes/backend references and enabled answer reuse. Several findings cross activity boundaries.

| Concrete lesson / cross-cutting finding | Reusable integration finding | Activities | Evidence / design status |
|---|---|---|---|
| Distinct same-text local bindings need explicit IDs | Define object identity explicitly; a display name need not be a deduplication key. Several validated references in one local binding may share an ID. | Describe, Publish, Maintain, Retrieve | Explicit-ID precedence and prototype occurrence construction are source-inspected; the later bounded custom-Task workflow is native-tested; broader extraction/conversion is not established. |
| Referencing, retaining and rewriting an endpoint are separate actions | A publication plan must distinguish existing-node references, intentional retention ownership and property writes. | Describe, Publish, Maintain | Recursive rewrite/co-ownership is measured in fixtures; safe existing-node reference/retention without ordinary-field overwrite is now native-tested in the Stage-6 fixtures. |
| Describe must distinguish what to create from what to reference, including intended edges | Save explicit graph intent; keep domain interpretation in Describe while Publish executes declared persistence/aggregation rules and selected programmatic steps. | Describe, Publish, Maintain | Draft IdentitySource records and controlled publication of explicit intent are implemented; no universal graph language is claimed. |
| Shared native ownership does not merge application metadata | Define aggregation or replacement semantics for shared structures, then keep applicability consistent with surviving assignments. | Describe, Publish, Maintain, Retrieve | Native shared retention is measured; ordinary edge replacement is source-inspected. Source-specific contribution aggregation/replacement/withdrawal is implemented and native-tested in Stage 6. |
| Generated identity sources depend on original inputs | Retain explicit original-to-derived dependencies and define retirement/regeneration after input changes. | Describe, Publish, Maintain | Bounded original-text rebuild/generated-snapshot coordination is implemented; dependent-source propagation and full Data-removal orchestration remain incomplete. |
| Mention references and variant equivalence require different traversal | Define relationship interpretation and context eligibility, and implement retrieval that honors them. | Describe, Publish, Retrieve | Contribution-aware document-context group/mention fixture traversal is implemented; broader corpus traversal/delivery remains incomplete. |
| Occurrence identity and classification can persist while its resolution changes | Preserve an occurrence-specific Entity ID and mention marker independently of accepted resolution; replace or withdraw resolution relationships explicitly. | Describe, Publish, Maintain, Retrieve | Captured retarget/removal/reconcile/recovery and ledger-based reader eligibility are native-tested; general changed-meaning reconsideration remains incomplete. |
| Lifecycle modifications primarily belong to Maintain | Maintain owns change detection, affected-set selection and replacement/retirement/reconstruction; it may reuse Publish's controlled persistence primitives. | Publish, Maintain | Fixture Maintain uses common Publisher.replace/withdraw and TextChange; broader affected-source selection is not implemented. |
| Maintain must decide what propagates into saved records | Separate validated source changes and accepted interpretation changes from native property drift, remapping and materialization failures; update durable descriptions only under the declared policy. | Describe, Maintain | Responsibility/design clarification; no automatic graph-to-source synchronization is implemented. |
| Multi-document interpretations require operational use of input provenance | Use dependencies to select affected assignments and preserve independent sources; document grouping alone does not establish independence. | Describe, Maintain, Retrieve | Input validation and known dependent-edit refusal are implemented; external-context propagation/reconsideration remains incomplete. |
| Describe relates document identities to eligible corpus identities | Candidate discovery and contextual interpretation produce exact reuse/create/link intent; occurrence-ID preservation is separate from interpretation reuse. New corpus arrivals can make earlier unresolved records worth reconsidering under Maintain. | Describe, Maintain, Retrieve | Intended scope and test refinement; candidate algorithms, reconsideration triggers and stability policy remain unimplemented. |
| Make representation meaning and rules explicit | Define concepts, relationship meanings, valid combinations and context. Investigate which parts constitute a domain ontology and which are schemas or operational rules. | Describe, Publish, Maintain, Retrieve | Cross-cutting design finding and investigation topic; no ontology formalism is selected. |
| Preserve durable descriptions independently of graph materialization | Save sufficient structured input, endpoint references and provenance to rebuild the intended graph and maintain source dependencies. | Describe, Publish, Maintain, Retrieve | Selected initial architecture; storage layout and combined rebuild/explanation behavior remain unvalidated. |
| Verify every integration boundary and consumed derived representation | Check description fidelity, publication effects, lifecycle results, retrieval interpretation and the graph/vector/evidence/cache representations actually consumed. | Describe, Publish, Maintain, Retrieve | Methodological finding. Existing scoped results are retained; validation of the new package remains future work. |

The three final rows make explicit the additional cross-cutting concerns: representation semantics, durable description versus materialization, and verification. They are architectural/methodological findings, not newly measured runtime results or an expanded list of universal requirements.

### 18.3 Carrying findings to the next knowledge type

For each remaining identity operation walkthrough, record the concrete identity solution and the reusable finding it establishes. Retain the pinned mechanism, applicable activities, evidence status, tested conditions, extension needed and unresolved limitations. Amend existing findings as evidence changes rather than treating this initial table as final.

During Stage 6, attach implementation and targeted validation results to the relevant findings. At the post-Stage-6 checkpoint, distinguish demonstrated reusable mechanisms from identity-specific assumptions. Use the register as starting questions for Stage 7's ontology/schema investigation and Stage 8's measurement/scientific worked example.

The recurring activities can transfer to measurements: describe values/units/context, publish measurement records linked to existing instruments/facilities, maintain revisions/calibrations and retrieve under conditions. Their domain rules are not copied from identity equivalence. A second worked example should determine which mechanisms generalize; no generic plugin/package runtime or universal ontology framework is being implemented now.

This dated design update itself added no runtime result, stage or renumbering. Subsequent .4/.5 review is complete and bounded Stage-6 runtime evidence is recorded in the session handoff; operation walkthroughs are no longer the immediate task.

### 18.4 Explicit descriptions and bounded publication — refinement, 2026-10-13

Describe specifies graph intent, including the edges to publish, exact endpoint references, new-node construction information, relationship interpretation/applicability and retention intent. It must not leave Publish to guess whether a same-name Entity is an existing object to link or a new object to create.

Publish performs validation and persistence mechanics, including stable-ID replay, intentional endpoint retention, contribution aggregation, selected programmatic steps and read-back verification. The assignment supplies its own intended contribution; the publisher assembles the complete current shared-edge payload rather than treating the description as a stale database snapshot.

Some behavior will be programmatic. Make that behavior explicit in the selected publisher/Task configuration and replay path. Do not silently turn generic publication into another round of domain inference. Exact serialized operation forms and how named publication rules are dispatched remain to be decided.

This refinement applies to Describe, Publish and Maintain and has been added to the findings register. It adds no implementation or runtime result; the next operation walkthrough considers two existing endpoints.

### 18.5 Publish and Maintain responsibilities — clarification, 2026-10-13

Publish primarily materializes a supplied description into the graph, including initial insertion, integration with existing endpoints and explicitly requested replay. It must understand declared creation/reference/retention intent and apply controlled writes, but it does not independently discover or decide lifecycle changes.

Maintain primarily handles later changes: detection of changed or retired inputs, selection of affected records, recomputation of interpretations and shared contributions, explicit withdrawal/replacement, original/generated-source lifecycle orchestration, and usable-state/failure handling. It can invoke Describe again to regenerate a description and reuse Publish's persistence routines to apply the resulting plan.

The same low-level create/update/delete/ref-attachment code may serve both activities. Classify the finding by the responsibility involved, rather than by the function that happens to write the graph. Initial shared-edge integration involves Publish; recomputing that edge after contributor retirement primarily involves Maintain.

The accepted mention walkthrough illustrates this distinction: occurrence Entity identity and its marker can persist while Maintain changes or withdraws its accepted resolution. A generated-source full rebuild may physically recreate them at the recorded IDs. Changing the original occurrence still requires validation/regeneration; no automatic cross-revision occurrence tracking is promised. Incoming-object omission does not remove obsolete relationships, so retirement must remain explicit.

This clarification adds no separate maintenance engine, implementation, atomicity guarantee or runtime result.

### 18.6 Saved-record propagation under Maintain — clarification, 2026-10-13

Maintain must decide which changes update the durable occurrence/assignment description and which call for graph repair, explicit remapping or temporary invalidation. It manages both the saved knowledge state and its materialization.

Update the saved description when identity processing accepts a changed interpretation, withdraws a resolution, or validates changed original inputs. Do not automatically infer a knowledge change from a missing edge, an overwritten Entity description or a temporarily absent endpoint. A known ID migration may justify a validated reference update; an unexplained missing endpoint does not justify choosing a same-name substitute.

Captured occurrence information and derived interpretation have different update sources: original text/coordinates come from verified original input; accepted target/applicability/derivation information comes from identity processing. Interpretation changes preserve occurrence identity, while source-occurrence changes require validation/regeneration.

Saved-record modification can succeed while graph publication fails. Preserve the intended state for retry and keep affected retrieval unavailable until the current description and required graph materialization agree. The current runtime implements portable status/revision/attempt guards, minimal plans and explicit caught-failure coordination for admitted paths; it does not provide a cross-store transaction.

The detailed occurrence policy is in proposal section 2.3. The reusable finding is tagged Describe and Maintain; resulting graph writes use Publish's shared routines. This policy does not require an archive, indiscriminate graph-to-source copying or a universal reaction to every Cognee mutation.

### 18.7 Operation sequences as regression scenarios — 2026-10-13

Each reviewed sequence and expected output is also input to a planned test suite. Capture initial fixture, initiating operation, saved-record result, graph IDs/properties/native refs, retrieval eligibility/applicability, active derived-store checks, failure points and replay result. Proposal section 11 contains the scenario matrix; roadmap 6.6 carries implementation.

Use deterministic captured extraction/identity decisions for lifecycle tests, actual isolated backend/source contexts for persistence integration, and end-to-end maintenance/retrieval plus failure-injection cases. Separate interpretation-quality benchmarks from orchestration assertions. This is the broader test design; a captured native/programmatic subset is now implemented and passing. Current coverage is recorded in SESSION_HANDOFF.md, without claiming all planned cases or model-quality evaluation.

The accepted shared-source withdrawal adds concrete checks to existing findings: native owner survival does not remove obsolete contribution properties; surviving assignment Y need not change when X is retired; source-bound repair must not reattach the retired source; and a retained physical edge with no accepted contributions must not be treated as a current identity relationship.

### 18.8 Multi-document preservation and Describe variability — 2026-10-13

Updating one document must preserve other documents' independently supported interpretations, even when they share Entity IDs. Use input/contributor provenance in selection, retirement, shared-edge aggregation and contextual retrieval; simply storing it or preserving the shared node is insufficient. Other sources' records must be reevaluated when they actually consumed changed document/candidate/assignment context. Generated-source grouping is not dependency isolation.

Record supplied Describe context as operational inputs; do not pretend to determine an LLM's causal use of each snippet. Context references/content validation support conservative invalidation and reproducible experiments. Ordinary native Entity field changes do not themselves authorize overwriting saved source-specific interpretations.

Proposal section 12 specifies independent/dependent multi-document regressions and Describe consistency investigations: repeated identical inputs, meaning-preserving edits, meaning-changing edits and an end-to-end profile. Freeze candidate graphs/chunks/context first to distinguish model variability from upstream extraction variability. Compare corresponding occurrences, exact targets and fixed benchmark identity groups, statuses, scope and unrelated changes; assess correctness separately from agreement.

These investigations extend the activity-tagged findings and Stage-6 validation plan. No Describe consistency measurement or stabilization/automatic-acceptance policy is selected by this documentation update.

### 18.9 Describe includes corpus identity resolution — clarification, 2026-10-13

Describe identifies document forms/occurrences and relates them to relevant current corpus singletons and identity groups. It chooses the proposed exact existing references, necessary new nodes, variant/mention relationships, applicability and unresolved outcomes. Publish executes this declared graph intent. Candidate retrieval need not scan every Entity, but a purely document-local inventory is insufficient.

On modification, occurrence-ID validation/regeneration and interpretation reevaluation are separate operations. Unchanged occurrence IDs do not justify skipping changed document/corpus context. Preserve independent other-source interpretations; record supplied external context and use it for maintenance selection.

A new document's links to existing identities belong to Describe. Selecting older unresolved/ambiguous assignments for reconsideration after new corpus knowledge arrives belongs to Maintain, which can invoke Describe. Previously absent candidates are not captured by positive dependency links; trigger/selection design remains open rather than assuming those links cover all updates.

Proposal section 2.4 records the full scope and corresponding test cases. No corpus-resolution implementation, exhaustive-candidate guarantee or automatic whole-corpus replay is claimed.

### 18.10 Shared stored-representation mutation interface — agreed direction

Add a shared interface for reading and applying guarded changes to saved descriptions/records, explicit source-level replacement/retirement and change reporting. Domain helpers enforce meaning; generic storage persists intent. Distinguish interpretation withdrawal, occurrence retirement, representation revision and original-input revision. Keep graph publication explicit and coordinated by Maintain. The project runtime now supplies registered/relational storage and guarded Publisher publish/replace/withdraw operations for admitted paths. A generic fine-grained record-edit API remains broader work; illustrative names here are not native Cognee APIs.

### 18.11 Saved-state/publication failure coordination — proposed next review

Proposal sections 13–14 record the accepted storage-interface direction and a proposed per-affected-source completion protocol. Commit intended description, reconcile graph/active indexes, verify and acknowledge the exact current revision. Acknowledge neither failed nor superseded publication as current. Reuse saved decisions during graph retry; regenerating Describe can introduce a new interpretation and is a separate action.

On shared structures, preserve eligible surviving contributors while excluding pending/retired ones, subject to required object/index validity. Recording saved state and graph state are separate failure boundaries; no automatic cross-store transaction or historical-property rollback is promised. The reviewed protocol is implemented for supported fixture operations through the portable ledger and controlled publisher. General source/dependency orchestration and standard hooks remain; no cross-store transaction is claimed.

### 18.12 A/B generation staging and extensible recovery — proposed, 2026-10-13

Evaluate a coherent full-store candidate generation for the initial lab: copy the active graph/saved descriptions and required source, relational/provenance and vector/evidence state; execute all changes in the candidate; validate; then select the candidate as active. Original source updates must also be staged. Shared endpoints and native indexes prevent assuming an isolated one-source graph copy.

Existing clone probes establish isolated subprocess operation execution, not coherent live snapshot or promotion semantics. Ladybug checkpoint makes prior graph writes durable but does not synchronize SQLite/LanceDB/source records. Audit path rebinding and native read-side bookkeeping. First serialize writes to promotion-copied state, flush/close handles and reopen readers/processes against the selected generation; do not copy over open live files.

Keep preparation, execution, validation, promotion and recovery policy separate. Retain candidate/base identifiers, description revisions, captured intent, phase/error and validation evidence. Extend retry/repair/rebuild/reject handlers as real failure classes are observed. A failed candidate leaves active A selected; interrupted/superseded promotion requires actual-selector checks.

Proposal section 15 and roadmap 6.4/6.6 contain the pending feasibility/test work. This is not native Cognee multi-store transaction support, a measured promotion result or a required general version archive. A/B generation labels do not refer to the earlier option B Cognify patch.

### 18.13 A/B complexity boundary — 2026-10-13

A/B staging is optional for the first iteration and is not a Stage-6 handoff prerequisite. Track its practical complexity as basic publication and maintenance are implemented: coherent copying, shared-store scope, source-path/adapter rebinding, native bookkeeping, promotion and storage/time costs. Defer it if that work outweighs its initial benefit.

Keep the pending-state/captured-intent retry approach as a viable baseline and retain narrow separation of execution, validation and recovery policy so staging can be added later. No general snapshot framework or mandatory concurrent-generation service is selected.

### 18.14 Structured sources and optional prose/chunks — accepted identity simplification, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

For identity, one authoritative JSON document is registered as a generated Cognee Data item. Publish consumes structured records through custom Tasks and publishes its TextDocument graph node as the mention-marker anchor. Original DocumentChunks remain source occurrence locators. Generated identity prose/chunks are unnecessary until a specific retrieval or LLM consumer requires them; render explanations on demand and retain substantive explanations only where useful.

Source inspection supports the parts: the text loader accepts JSON, document classification maps JSON to TextDocument and uses Data.id as its document ID, and add_data_points accepts ordinary DataPoints plus ID-based custom edges under a source context without requiring chunks. add registration alone is not semantic graph publication. The combined chunkless identity workflow is not live-tested. calculate_chunk_graphs remains a valid computation seam for chunk-based processing; it is not required for this direct custom-Task path.

General lesson: separate the authoritative structured description, the native source/ownership graph anchor, and optional textual retrieval material. A text-bearing anchor does not imply the description must be parsed again by an LLM or split into chunks. Carry this distinction to later knowledge types without assuming their retrieval needs match identity's.

Source anchors: cognee/infrastructure/loaders/core/text_loader.py; cognee/tasks/documents/classify_documents.py; cognee/modules/data/processing/document_types/Document.py; cognee/tasks/storage/add_data_points.py, at the pinned Cognee 1.6.2 checkout.

### 18.15 Reference grouping and graph materialization granularity — initial decision, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Identity initially uses paragraph-local reference groups: multiple exact ranges sharing one interpretation feed one saved record and mention Entity, marker and resolution. A deliberate selection policy avoids assuming all pronouns must be materialized. This reduces potential object counts while retaining the Entity/resolves_to integration; no scaling measurement is claimed.

Separate input reference granularity, saved-record granularity and graph object granularity. More compact objects require retained member positions, range-level applicability and a defined split/merge maintenance policy. A grouped mention endpoint alone cannot attribute every incident semantic edge to a single occurrence. Context passages inform interpretation but are not blanket resolution scope.

The previous one-occurrence-per-node recommendation is superseded for the initial identity design. Detailed individual records with compact graph, property/contribution-based references, saved-record-only mentions and wider contexts remain alternatives; broader semantic-edge compaction is not selected. Proposal section 17 records decision/rationale/options and validation scenarios. Carry this granularity/cost distinction forward to other knowledge types without assuming they should share identity's grouping unit.

### 18.16 Saved interpretation separated from captured references — agreed direction, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Keep captured local reference groups separate from their interpretation records. Mention-resolution records identify the group, exact accepted target, status, applicability, supplied inputs and producing process; a stable record ID also identifies the published contribution. Unresolved/ambiguous records can retain candidates without accepted graph edges. The source envelope supplies source identity/revision.

Retarget an entire group by changing its resolution; retarget some occurrences by splitting the group first. Withdrawal does not automatically retire captured references or classification. Variant relationship records share assignment/provenance machinery with two exact reusable endpoints and explicit applicability, without a mention-group reference.

General lesson: source object identity, captured inputs and derived interpretation can have different lifecycles. A shared mutation API must preserve those distinctions while coordinating materialization. Proposal section 18 contains the agreed identity forms; these are structured records, not graph support nodes, and draft serialization is now implemented in the Stage-6 runtime models/exported schema.

### 18.17 Durable construction fallback for borrowed corpus endpoints — revised proposal, 2026-10-14

**Applies to:** Describe, Publish, Maintain.

An existing endpoint reference plus current native ownership does not guarantee future replay. A generated source can become its last owner after another source is removed; rebuilding that generated source can temporarily delete the endpoint. Store minimal corpus-backed construction recipes for required endpoints even when they already exist. Existing-node publication bypasses construction and attaches refs; valid missing-node publication reconstructs exact IDs from saved intent.

Distinguish recipe availability from permission to reconstruct: retired inputs or invalid assignments require maintenance rather than blind resurrection. The recipe supplies initial node fields, not complete semantic relationships or current property authority. Different source recipes need no merge when the Entity already exists. Supported writer coordination must prevent the native upsert path from turning create-if-missing into unintended replacement.

Identity's last-owner lifecycle sequence belongs in Stage-6 tests and should carry forward as a replay lesson for other knowledge types. Proposal section 19 captures the initial policy; no implementation or new live result is claimed.

### 18.18 Publication state separate from saved knowledge — agreed initial design, 2026-10-14

**Applies to:** Publish, Maintain, Retrieve; Describe supplies captured intent consumed by the protocol.

Identity selects a small project-owned SQLite ledger keyed by dataset + generated source Data ID. It tracks pending/current/failed, target/published revisions, current attempt and optional diagnostic references. JSON remains authoritative for knowledge. Invalidate before affected supported writes; publish and verify required graph/index structures; acknowledge only the still-current saved revision and attempt. A repair can apply unchanged saved knowledge in a new attempt.

Initially withhold the pending source's identity contributions and preserve unaffected contributions only where their required shared objects/indexes remain valid. Native lifecycle/status/retrieval do not automatically participate: integrate supported wrappers/Tasks and the custom identity reader explicitly. SQLite coordination is not a cross-store transaction; guards, invalidation hooks and validation still require implementation. A/B remains optional.

Carry forward the distinction between durable interpretation and verified materialization. Other knowledge types can reuse the shared interface/protocol while selecting their own required representations and affected sets. Proposal section 20 records the agreed identity baseline and regression boundaries.

### 18.19 Describe baseline: native behavior, representative approaches and model-neutral decisions — source review, 2026-10-14

**Applies to:** Describe, Publish, Maintain; Retrieve consumes resulting scope/provenance.

**Evidence:** source-inspected Cognee 1.6.2 checkout at ba3631f2ed363a6ea50d649c34c56885af6b36fe. No new runtime accuracy test or model adoption. The user requests grounding in existing code and standard approaches, and a longer-term decision-model alternative to an LLM. The latter is a design goal; the boundaries below are recommendations for the next review.

#### Native mechanisms actually found

| Mechanism | What the inspected code does | Implication for this project |
|---|---|---|
| Default Cognify | Classify documents, chunk, extract_graph_and_summarize, then add_data_points; optional provenance/contradiction stages | Reuse Task/persistence infrastructure; the default list does not include a separate coreference/corpus entity-linker |
| extract_graph_from_data + extract_content_graph | Calls structured LLM extraction for each chunk, passing chunk.text and prompt/model; can accept precomputed graphs through calculate_chunk_graphs | Coreference is initially folded into generative graph extraction rather than explicit span/cluster decisions |
| Default graph prompt | Instructs the model to use the most complete identifier when aliases/pronouns refer to one entity | A request for normalization is not measured coreference correctness, nor saved occurrence provenance |
| Generic KnowledgeGraph | Node ID/name/type/description plus relationship endpoints/text; no explicit mention ranges, coreference clusters or scored existing-corpus candidate list | Normalized extracted graphs alone do not supply the planned precise source/reference records |
| Entity construction | Usually Entity.id_for(name); repeated same-name nodes with different graph-local IDs within one extracted graph instead get chunk/ordinal-scoped IDs; shared batch dictionary reuses constructed Entity IDs | Deterministic ID matching supports reuse but does not decide contextual equivalence; do not say all same-name nodes always collapse |
| Chunk contains/provenance | Links chunks to constructed Entities and records extracted semantic edge identities/text | Useful coarse source grounding; not exact pronoun spans or a local reference-group binding |
| Optional consolidate_entities_pipeline | Loads Entity graph data; embeds names; groups normalized-name matches or thresholded name-vector similarity via union-find, with type guards; merge picks a representative, redirects edges, unions descriptions and deletes duplicates/vectors | A separate physical consolidation path, not the selected scoped/non-destructive identity design or contextual pronoun resolver; keep excluded/adapted |
| Optional ontology resolver | Canonicalizes matched extracted classes/individuals to ontology names and attaches ontology structure | Ontology vocabulary/individual matching is distinct from general corpus candidate ranking |
| Optional extractor='gliner_demo' | Local GLiNER entity/relation extraction supplies precomputed KnowledgeGraphs through the callback and Tasks marked needs_llm=False | An existing non-generative extraction integration pattern; not a ready-made corpus linker/coreference system |
| GLiNER generic mapper | Runtime requests spans/confidence; mapper uses positions to choose competing detections, then discards them from generic Nodes and deduplicates by type/name; relation endpoints match normalized strings or unambiguous containment | To preserve our ranges/bindings, adapt before this lossy mapping rather than infer them from final graph nodes |

Default extraction does not explicitly pass an existing-corpus candidate catalogue into its normal per-chunk LLM call. Existing-edge lookup later checks edge identities for storage/retention; it is not entity candidate disambiguation. Optional resolver/custom callbacks may add behavior, so this characterization is bounded to the inspected default and named optional paths.

#### Representative established approaches (limited review)

Coreference detects textual mentions and groups those sharing a referent. Discriminative systems score spans/antecedents or assign mentions to evolving clusters. Maverick (ACL 2024) illustrates learned mention detection and clustering without a general-purpose autoregressive LLM. These results do not establish scientific-corpus accuracy. [Paper](https://aclanthology.org/2024.acl-long.722/), [method](https://arxiv.org/html/2407.21489v1), [authors' implementation](https://github.com/SapienzaNLP/maverick-coref).

Entity linking maps a mention/context to catalogue identities. BLINK illustrates two stages: independently encode context/entity descriptions to retrieve candidates, then jointly encode each candidate with context to rank them. This separates candidate coverage from selection quality. It does not directly implement our dynamic singleton/group scope or uncertainty policy. [Paper](https://aclanthology.org/2020.emnlp-main.519/), [authors' implementation](https://github.com/facebookresearch/BLINK).

These are representative architecture patterns, not a 2026 leaderboard, exhaustive survey, pretrained-model recommendation or installation request. Our non-destructive, scoped corpus identities and lifecycle maintenance still need project logic.

#### Proposed implementation-neutral Describe boundary

Use replaceable inference functions for mention detection/grouping, candidate retrieval and identity decision. They may be backed by an LLM, discriminative encoder/ranker/classifier, rules or a combination; do not require a trained backend to emit prose, prompt text or JSON directly. An adapter normalizes native outputs, and deterministic assembly/validation produces the saved record forms and explicit publication intent.

Inputs include exact source text/version and paragraph/section context, grounded mention spans/groups, eligible candidate Entity/group references plus names/descriptions/source information, and relevant prior records for maintenance. A joint backend can perform several steps; the conceptual split is not a requirement for three separate models or passes.

Outputs can include token/character spans, grouping assignments, candidate/action IDs, optional scores and accepted/unresolved/ambiguous decisions. For existing candidates, use a finite candidate key mapped by code to exact UUIDs; for new identities, code allocates the ID and assembles the minimal corpus-backed recipe. Code validates native token offsets against original document coordinates, reference keys, scope and role exclusions, and supplies revisions/contributions/ownership instructions. It must not silently substitute a same-name endpoint or infer a decision that was not produced.

No mandatory natural-language justification, fixed score threshold, calibration or universal feature vector is selected. Scores from different models are not assumed comparable. Preserve producer/model/version/configuration and the actual supplied candidate set/context plus normalized decisions. Candidate retrieval is also replaceable; a downstream scorer cannot select a correct target excluded from its candidates.

Paragraph bounds are the initial storage/grouping unit, not the maximum reasoning context. A coreference backend may use document-level context and output wider clusters; an adapter can project validated references into paragraph-local groups, retaining exact ranges and broader supplied-input dependencies. This avoids forcing a decision model to resolve a pronoun with insufficient context or treating its whole-document cluster as global variant equivalence.

For eventual training/evaluation, retain actual candidates (including alternatives) and distinguish model proposals from validated labels/benchmark truth. Candidate recall, mention/grouping quality, final linking/abstention and replay consistency should be evaluated separately. No training pipeline or label correctness guarantee is implemented now; document-held-out evaluation and review-derived labels are possible later.

#### Pinned source anchors

- [Cognify default Task list](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/cognify/cognify.py)
- [Per-chunk extraction and callback integration](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/graph/extract_graph_from_data.py)
- [Structured LLM invocation](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/llm/extraction/knowledge_graph/extract_content_graph.py)
- [Default coreference instructions](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/llm/prompts/generate_graph_prompt.txt)
- [Generic graph schema](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/shared/data_models.py)
- [Entity ID construction and chunk contains links](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/graph/utils/expand_with_nodes_and_edges.py)
- [Optional duplicate detection/physical merge](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/memify/consolidate_entities.py)
- [Consolidation pipeline entry point](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/memify_pipelines/consolidate_entities.py)
- [Local extractor Task integration](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/graph/gliner_demo/tasks.py)
- [GLiNER span handling and graph mapping](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/graph/gliner_demo/mapping.py)
- [Ontology individual/name canonicalization](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/ontology/construct_data_points_and_edges_with_ontology.py)

### 18.20 Graph-visible contextual bindings — selected clarification, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Identity retains pronoun/context-only local groups as graph mention nodes with exact saved ranges, stable UUIDs, source markers and accepted scoped mention resolves_to edges. A preferred noun phrase is not required. Use the existing ordinary Entity + relationship classification representation; do not create global aliases for common words or introduce a distinct graph support node.

The saved-only default proposed in conversation is superseded. Grouped nodes reduce object counts while keeping bindings available to graph traversal and providing endpoints for domain facts. Durable records remain necessary for replay/provenance; discovery of a binding should not require parsing its source passage.

Semantic edges on group nodes need explicit integration and exact original-source attribution. Native graph extraction does not automatically target the group's explicit UUID, and partial group retargeting must not move unrelated facts. Preserve directed mention semantics rather than turning local references into variant equivalence. Proposal section 22 records the identity-specific contract and planned cases; no new runtime evidence is claimed.

### 18.21 Seeded description and representative full-pipeline fixtures — selected direction, 2026-10-14

**Applies to:** Describe; fixture milestone spans Describe, Publish, Maintain, Retrieve.

The user selects seed discovery before downstream contextual decisions: names/proposed reusable forms, explicit abbreviation definitions and generated initials first; then seeded semantic matching, shortenings and finally pronouns/contextual references. Earlier results inform later passes. Candidate providers and inference backends remain replaceable; conceptual passes need not map one-to-one to model calls or graph writes.

Parenthetical patterns and initial-letter candidates provide practical first seeds. Keep pattern evidence, proposed interpretations and published applicability distinct: an initials match does not automatically establish a reusable identity relationship. Scope/collisions and local-only descriptions still need handling.

The initial goal is a working integration demonstrated by a small set of each relevant type plus selected negative/ambiguous and lifecycle cases. Defer comprehensive linguistic coverage and algorithm perfection. Hidden benchmark answers remain evaluation fixtures rather than inputs to inference; captured decisions can isolate persistence tests from Describe accuracy. Carry forward this representative end-to-end milestone approach to later knowledge-integration packages.

Proposal section 23 and roadmap 6.2 contain the initial order and fixture direction. Existing native Tasks/extraction may supply inputs; no new model, first-backend implementation or live accuracy result is claimed.

### 18.22 Routing discriminator and fact-endpoint binding — investigation, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

The user requests further investigation of generated-source routing and discussion of local semantic fact placement. Source inspection establishes:

1. JSON maps to TextDocument/STANDARD; content kind and external_metadata do not themselves control Cognify routing.
2. Native routing is per item, based on persisted system_metadata/extension and document classification. The dataset runner accepts a Task resolver; Cognify supplies built-in-route policy. A uniform STANDARD Task transform alone does not distinguish identity JSON from ordinary text.
3. Re-add replaces system route metadata from current content/item, including none. A valid identity discriminator needs regeneration/preservation on admitted Update/rebuild and reload. Existing loader-result stamps are a useful native precedent.
4. A custom publication pipeline can isolate writes but does not alone guard a later standard Cognify/Update. Investigate resolver integration and validate with mixed-source/restart/update probes before choosing the final patch.
5. Dataset orchestration includes reentrant lock handling. Do not assume nesting deadlocks, or that it is otherwise automatically correct across contexts/rollback.
6. Native extraction/edge evidence preserves graph endpoints, edge identities, source chunks/runs and optional generated edge text, not exact subject/object reference spans. The best-effort audit ledger is not mandatory exact occurrence evidence.

The user's graph-visible mention groups need explicit fact-to-group endpoint binding when contextual semantic facts attach there. Local-M fact storage and direct-A storage have different retargeting/source-contribution costs. Native graphs can be reused where mappings are grounded and unambiguous; same-name or chunk-level blanket rewrites are unsafe.

The prior native-complete-then-Describe order remains provisional. Source-aware extraction/conversion before final semantic persistence may be needed. Do not adopt a universal fact rewrite or a new scientific support schema in this review. Proposal section 24 records the evidence, options, small routing probe and retrieval implications.

Pinned anchors: modules/cognify/routing.py; tasks/documents/classify_documents.py; tasks/ingestion/ingest_data.py; api/v1/update/update.py; api/v1/cognify/cognify.py; modules/pipelines/operations/pipeline.py and run_tasks.py; modules/graph/utils/expand_with_nodes_and_edges.py; shared/data_models.py; modules/provenance/edge_evidence/models.py and buffer.py; tasks/provenance/record_provenance.py.

### 18.23 Custom identity-aware relation extraction before persistence — clarification, 2026-10-14

**Applies to:** Describe, Publish; Maintain reuses it on affected inputs and Retrieve consumes the graph.

The user accepts local-node anchoring for contextual facts and asks who generates new facts after mention/variant discovery. Assign text-grounded semantic generation to an identity-aware relation-extraction Task consuming original text plus explicit identity bindings. Identity Tasks establish local groups/reusable forms; assembly maps endpoint keys to IDs; Publish writes supplied relationships. Node creation or resolves_to publication does not trigger semantic extraction by itself.

The native STANDARD seam is appropriate: classify -> chunk -> extract_graph_and_summarize -> add_data_points. Insert identity preparation and replace/adapt graph extraction/conversion before final persistence. Reuse summarization/storage where their contracts fit. A custom Task list works in a project pipeline; native Cognify/Remember/Update integration and per-item identity JSON routing remain extension work.

A calculation callback alone does not preserve arbitrary extracted Node IDs as Entity UUIDs: the generic converter normally derives IDs from names. Bind known mention/variant/existing endpoint keys in an identity-aware converter and use deliberate reference attachment plus ID-based edges. Make document-level context available across native streaming chunk batches.

For contextual text, facts attach to M and M references its reusable target. For explicit variant text, facts may attach to the variant node. Extract new relationships from source passages, rather than copying all known group facts to a new alias. Preserve original-source provenance and capture outputs for retries; exact semantic-output storage/ownership sequencing remains an integration detail. The previous completed-native-graph-first order is superseded as a mandatory sequence.

Proposal section 25 records the agreed anchoring, recommended Task split, example and unresolved integration details. This is ordinary source-grounded relation extraction, not the later scientific-support phase. No implementation or new runtime validation is claimed.

### 18.24 Native factual coverage versus binding/provenance improvements — deferred measurement, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

The user notes that native LLM extraction may already generate facts needed by the custom identity-aware process. Measure overlap and differences on the initial Stage-6 examples before assuming all custom output is newly discovered knowledge. Distinguish factual coverage from endpoint binding, qualifiers/scope and original-source attribution. Preserve producer/run lineage separately from original source statements; repeated extraction can produce duplicate representations of one statement.

Use controlled isolated/captured comparisons and validated identity/scope mappings, not raw graph-edge identity alone. Results can guide native extraction reuse/adaptation, duplicate handling and provenance design. No experiment or further investigation is requested now; no new result, scientific-support rule or implementation gate is asserted. Proposal section 26 contains the deferred comparison.

### 18.25 Preserve native semantic fact representation and provenance — goal and compatibility findings, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Start with the user's goal of using Cognee's normal relationship representation, source attribution, native ownership/deletion and configured indexing for ordinary facts generated through identity-aware extraction. Identity changes how exact endpoints are chosen; it does not by itself justify a separate semantic-fact graph/provenance framework.

In pinned 1.6.2, native conversion records each original chunk's produced relationship identities and extracted-edge evidence before deduplication. add_data_points derives chunk owner refs from that record and reachable DocumentChunks; already-existing facts gain the new chunk's ownership/evidence without necessarily rewriting the edge. Edge-evidence capture defaults on, subject to configuration. It records source Data/chunk/run/edge, not exact subject/object mention bindings. The independent hash-chained audit ledger remains opt-in/best-effort.

Keep original document chunks as the baseline owners/evidence sources for semantic facts, including facts whose endpoints are locally grouped mentions or newly declared variants. Generated identity Data remains the owner of its identity assignments; original source, producer/run, applicability and retention are distinct.

| Finding | Activities | Integration consequence |
|---|---|---|
| Stored Entity UUIDs are selected during conversion, not by blindly copying graph-local Node.id | Describe, Publish | Bind saved mention/variant/existing keys to exact IDs before normal persistence. |
| Nested existing DataPoints can enter ordinary node upserts | Publish, Maintain | Reference/retention adapter must preserve chunk attribution without unnecessary field rewriting. |
| custom_edges is a separate document-owned write path | Publish, Maintain | It is not a drop-in equivalent of extracted chunk relationships/evidence. Preserve native produced-edge and evidence bookkeeping. |
| Native evidence lacks exact local-group endpoint/range bindings | Describe, Maintain | Keep minimal captured extraction bindings for replay/splits; use native provenance for ordinary source attribution. |
| Original chunks may retain M/facts after its generated source's marker is removed | Publish, Maintain, Retrieve | Explicitly test independent source lifetimes and settle classification/repair before admitting that sequence. No marker ownership change is chosen yet. |
| ID-only edges can miss optional Triplet embeddings when endpoints are absent from the current node batch | Publish, Maintain, Retrieve | Verify configured derived indexes independently of graph success. |
| One physical source/name/target edge can have several owners but one ordinary property bag | Describe, Publish, Maintain, Retrieve | Begin with native ordinary-fact behavior; add a focused extension only for a demonstrated loss. Identity contribution collections do not automatically generalize to every fact. |

Proposal section 27 records the native baseline, source-inspected seams and planned real-backend sequences. Later captured fixtures implement original-owned semantic output/evidence, safe exact-ID references and mention retention across generated-source withdrawal. General semantic conversion/dependency lifecycle remain incomplete. This dated source review itself added no runtime result; the native-versus-custom extraction coverage experiment remains deferred.
