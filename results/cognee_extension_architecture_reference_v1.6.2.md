# Cognee Extension Architecture & Lifecycle Reference

**Project context:** `cognee-science-lab`.

**Pinned Cognee version:** 1.6.2.

**Original review date:** 2026-10-10.

**Identity-design update:** 2026-10-13.

**Editorial revision:** 2026-10-20. STE-flavored technical prose.

**Purpose:** Record extension interfaces, lifecycle behavior and design guidance for identity and future knowledge integrations.

[SESSION_HANDOFF.md](../docs/SESSION_HANDOFF.md) records the current code baseline, verification limits and next task. The [Stage-6 contract](cognee_identity_stage6_handoff.md) defines selected behavior and the implementation sequence. This reference preserves findings for the inspected version and dated design evolution. A historical limit does not negate later bounded fixture evidence.

Sections 1–12 characterize interfaces and early architectural options. Section 16 records the preferred B Task-transform extension. Sections 17–18 distinguish the later identity design from earlier options. Source inspection, selected design and runtime evidence provide different levels of support.

## 1. Design objective

Prefer integrations that use Cognee's intended abstractions and can survive upgrades without a maintained fork.

The recommended dependency order is:

1. Public memory/low-level APIs and configuration.
2. `DataPoint` and `graph_model` contracts.
3. `Task` and custom pipeline composition.
4. Custom enrichment Tasks through `memify` or `improve`.
5. Registered custom `Retriever` and `SearchType`.
6. `GraphDBInterface` and vector interfaces.
7. Selected subclass interfaces on built-in retrievers when needed.
8. Internal utilities and private methods as a last resort.

Backend-specific implementation belongs inside native adapters. Project integrations use configured interfaces and explicitly reject unsupported capabilities. Inspecting an adapter does not authorize a project fallback specific to that vendor. An importable Python function is not necessarily a stable extension API.

## 2. High-level operational map

The following map describes the inspected native operations:

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

These operations expose different extension mechanisms. Retrieval, Cognify and Memify offer more composition options than Update and Forget. The diagram's normal Remember/Improve path is native behavior. The initial identity profile does not invoke Improve/Memify automatically.

## 3. Retrieval extension model

### 3.1 Native retrieval characterization

| Retrieval type | Inspected behavior |
|---|---|
| `RAG_COMPLETION` | Retrieve chunk/vector content. This path need not interpret graph identity. |
| `GRAPH_COMPLETION` | Discover vector candidates, project the graph, optionally retrieve neighborhoods, rank edges and render context. |
| `HYBRID_COMPLETION` | Combine passages with entity/fact retrieval and graph neighborhoods. |

Native retrieval treats custom edges as ordinary graph relationships. Naming an edge `resolves_to` does not supply identity interpretation.

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

A custom retriever may inherit this behavior and override selected stages. Alternatively, it may subclass `BaseRetriever` and compose graph/vector interfaces directly.

### 3.3 Preferred extension seam

Cognee provides the `use_retriever(...)` registry and a community packaging pattern. Prefer a new SearchType. Do not silently replace built-in `HYBRID_COMPLETION` or `GRAPH_COMPLETION` behavior.

A candidate integration uses the following components:

```text
ScientificMemoryRetriever / IdentityAwareGraphRetriever
    Cognee vector engine
    Cognee GraphDBInterface
    Cognee node/edge objects
    Cognee completion/context conventions
```

Avoid these dependencies:

- Patches to `recall()` or `search()`.
- Direct Ladybug traversal.
- Private Hybrid methods, which changed across inspected minor versions.
- Treating `brute_force_triplet_search` as a stable public contract.

## 4. Cognify / initial graph construction

Cognify builds a pipeline from Tasks and uses the stable pipeline name `cognify_pipeline`.

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

Custom `DataPoint`, `graph_model` and Tasks provide explicit extension mechanisms. Documented `run_custom_pipeline(...)` examples specify sequential Tasks and replace the default Cognify list.

**Assessment:** Task composition provides a comparatively strong extension interface. This assessment does not guarantee compatibility with every future Cognee version.

## 5. Improve / Memify extension model

### 5.1 Top-level Improve stages are fixed in 1.6.2

`improve()` executes the static `DEFAULT_STAGES` registry in order:

1. `feedback_weights`
2. `persist_session_qa`
3. `persist_agent_traces`
4. `extract_agent_context`
5. `distill_sessions`
6. `update_user_preferences`
7. `build_truth_subspace`
8. `triplet_enrichment`
9. `global_context_index`

Version 1.6.2 has no public `register_improve_stage(...)` hook. Stage order affects execution semantics. Adding a stage by changing `DEFAULT_STAGES` creates an internal dependency. The project does not recommend that approach.

### 5.2 The triplet-enrichment stage deliberately exposes custom Memify Tasks

`ImproveKwargs` accepts:

- `extraction_tasks`
- `enrichment_tasks`
- `data`
- `node_type`

`TripletEnrichmentStage` passes these arguments to `memify(...)`. Custom Memify Tasks bypass the normal graph-change watermark shortcut. They perform different work from default Triplet embedding.

The exposed Task arguments provide a stronger extension interface than changing the stage registry. A candidate maintenance path is:

```text
improve(dataset=..., extraction_tasks=[...], enrichment_tasks=[...])
    fixed Improve orchestrator
        triplet_enrichment
            memify()
                our reconciliation / normalization / scientific enrichment Tasks
```

Cognee's engineering issue describes Memify Tasks as wrapped async functions that read and write the graph. It identifies reconciliation and consolidation as intended maintenance work.

**Assessment:** Custom Memify Tasks are a candidate interface for identity reconciliation and later transformations after Cognify. Passing custom Tasks does not establish isolation from other Improve stages. Each enabled maintenance profile still needs mutation and consumed-store checks.

### 5.3 Transport caveat

The local Python API exposes options absent from some remote/Rust HTTP interfaces. The Rust Memify documentation examined during this review omits these Python arguments from its HTTP DTO:

- `extraction_tasks` and `enrichment_tasks`.
- `data`.
- `node_name` and `node_type`.

Distinguish local Python extension support from remote deployment support. Remote use may require an extension installed and configured on the server. Track both compatibility dimensions in future integrations. This dated source review does not establish the current remote API surface.

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

Both paths preserve the document's `data_id`.

### 6.2 Critical restriction

Version 1.6.2 rejects incremental Update with:

- A non-default `graph_model`.
- Any `custom_prompt`.
- Changes to document metadata or `node_set`.
- Per-call graph/vector database configuration.

A custom graph model or prompt forces full rebuild. The incremental baseline does not retain enough extraction configuration to guarantee the same schema/prompt for replacement chunks. Consequently, this updater is not a general extension interface for custom pipelines.

### 6.3 ChunkPolicy is narrow

A replaceable `ChunkPolicy` controls chunk replacement and reconciliation. It does not provide arbitrary graph reconciliation or post-processing Tasks.

### 6.4 Full rebuild calls built-in Cognify, not an arbitrary custom pipeline

The fallback calls `cognify(graph_model=..., custom_prompt=...)`. It accepts no arbitrary Task list. Native Update therefore does not automatically replay an extra Task defined only in a separate custom Cognify pipeline.

An idempotent Memify/Improve Task can provide replayable post-processing. An early wrapper option was:

```text
science_update(...)
    cognee.update(...)
    cognee.improve(... custom memify tasks ...)
```

This wrapper composes operations without forking Update internals. It does not handle every extraction-time customization. Section 16 records the later preferred Task-transform extension for that need. Suitable derived maintenance remains separate.

### 6.5 Remote update caveat

In pinned 1.6.2, remote `PATCH /api/v1/update` cannot carry several local Python options:

- `graph_model` and `custom_prompt`.
- `chunker` and `policy`.

The remote path drops those values and uses server configuration. Local Python support does not imply equivalent remote support.

**Assessment:** Update provides a constrained extension interface. Initially, compose lifecycle operations around reusable transformations. Avoid customizing the incremental engine unless later requirements justify it.

## 7. What incremental update preserves/deletes

The architecture documentation examined during the review describes this algorithm:

1. Compare changed regions using paragraph anchors.
2. Expand changed spans to existing chunk boundaries.
3. Rechunk affected regions with the stored token budget.
4. Preserve unchanged chunk IDs and boundaries.
5. Delete replaced chunks and summaries.
6. Delete Entities orphaned from all surviving chunks.
7. Remove affected Triplet embeddings.
8. Run LLM graph extraction on new chunks only.
9. Renumber surviving chunks to maintain contiguous `chunk_index` values.

The architectural mechanism combines chunk ownership with orphan detection. This description is not evidence that every vector/evidence cleanup succeeds. Diagnostic mutation probes record gaps in [the characterization report](cognee_stage5_4_5_1_initial_findings.md).

Custom artifact behavior depends on actual writes and provenance stamps. Later Stage-6 fixtures verify selected ownership and full-rebuild cases. They do not admit native incremental Update for the project profile.

## 8. Forget / deletion model — compatibility constraint, not design driver

Forget constrains lifecycle compatibility but does not determine the whole representation. The selected identity contract requires coordinated original/generated-source retirement and shared-contribution repair for admitted workflows. It does not require a universal deletion framework.

For single-data memory-only Forget, pinned 1.6.2 performs:

```text
forget(data_id, memory_only=True)
    delete_data_nodes_and_edges(...)
    invalidate sessions referencing deleted graph elements
    delete relational edge_evidence for that data item
    reset pipeline_status["cognify_pipeline"] for that Data row
```

This orchestration has no custom Task/callback hook.

The graph interface provides provenance-aware primitives. They attach/remove source references and find objects by source or pipeline run. Native deletion manages custom output coherently only when its ownership and provenance match the intended lifecycle. Custom structures do not acquire correct cleanup automatically.

The early review considered several alternatives:

- Tolerate stale enrichment after rare Forget operations and repair it later.
- Add a small project cleanup wrapper.
- Attach native source references where document ownership is appropriate.
- Avoid redesigning the representation solely for perfect native Forget behavior.

These historical alternatives are not a blanket policy for current readers. The selected contract requires stale or incomplete affected output to remain unavailable until handled. Native deletion primitives and bounded wrappers remain relevant mechanisms. Full original/generated Data lifecycle coordination remains incomplete.

## 9. Custom pipeline lifecycle and pipeline status

Cognee tracks per-Data pipeline completion by pipeline name and dataset. Standard Cognify uses:

```text
cognify_pipeline
```

Incremental loading uses these markers to skip completed Data items.

| Situation | Consequence |
|---|---|
| A custom pipeline uses another name. | Its completion state is independent. |
| A custom pipeline replaces Cognify and uses `pipeline_name="cognify_pipeline"`. | Standard Cognify-style status semantics can apply. Inspected documentation/examples use this pattern. |
| Single-data `forget(memory_only=True)` runs. | It resets only the `cognify_pipeline` marker. It does not recognize arbitrary custom names. |

Lifecycle behavior therefore depends on both Tasks and pipeline naming. Apply these conventions:

1. Run a Cognify replacement under `cognify_pipeline` when preserving Cognify semantics.
2. Keep a separate post-processing activity distinct, preferably through Memify/Improve where suitable.
3. Do not reuse pipeline names solely to obtain deletion behavior.

## 10. General integration pattern emerging

The original review proposed the following separation:

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

This diagram records an early pattern. It separates extraction, maintenance and retrieval within Cognee's operational layers. Its incremental-update and automatic Improve paths do not define the admitted identity profile.

Later decisions refine the pattern:

- Section 16 selects a proposed Task-transform interface for extraction-time ordering.
- The project initially uses full-document rebuilding for customized updates.
- Maintenance paths require explicit admission before automatic invocation.
- Coordinated source removal and unavailable-state handling are part of the lifecycle contract.

## 11. Extension-strength matrix

These assessments compare the inspected interfaces. They do not guarantee behavior across untested versions or configurations.

| Surface | Extension quality | Recommended use |
|---|---|---|
| `DataPoint` / `graph_model` | Strong. | Represent domain structures. |
| `Task` and custom pipeline | Strong. | Compose extraction and orchestration. |
| Custom Memify Tasks | Strong. | Reconcile, consolidate and process derived structures. |
| `improve()` top-level stages | Fixed. | Use the existing Triplet-enrichment/Memify interface. Do not change the registry. |
| Custom Retriever/SearchType | Strong. | Implement domain-specific retrieval rules. |
| `GraphDBInterface` | Strong. | Access the graph independently of a backend. |
| Native incremental `update()` | Constrained. | Use its supported behavior. Avoid internal customization initially. |
| `ChunkPolicy` | Narrow and explicit. | Control chunk replacement only. |
| `forget()` | Fixed. | Coordinate compatibility and cleanup without making deletion dictate the representation. |
| Private retrieval/update internals | Fragile. | Avoid. |
| Backend-specific Ladybug queries | Fragile. | Avoid. |

## 12. Design criteria for future project extensions

Evaluate each capability against these questions:

1. **Representation:** Does it augment the semantic graph, create a secondary subgraph, use an auxiliary store, or combine these forms?
2. **Extraction:** Can a graph model or public Task pipeline generate it?
3. **Maintenance:** Can an idempotent Memify/Improve transformation maintain it?
4. **Retrieval:** Can a registered custom Retriever consume it through graph/vector interfaces?
5. **Replay after Update:** Can a full rebuild recreate the extension deterministically without changing Update internals?
6. **Ownership/provenance:** Does retention belong to a source, the corpus, or derived state?
7. **Forget:** Which cleanup is required, and which imperfections can the selected operation contract tolerate?
8. **Pipeline status:** Does the work replace Cognify or form a separate pipeline?
9. **Backend independence:** Does it avoid Ladybug/LanceDB-specific assumptions?
10. **Transport independence:** Does it support local Python, remote/server use, or both?
11. **Version resilience:** Does it depend on documented contracts or private implementation structure?

## 13. Immediate implications for Stage 5.4 — updated 2026-10-13

**Historical context:** This section records implications from the 2026-10-13 design review. The mutation characterization is complete in [the findings report](cognee_stage5_4_5_1_initial_findings.md). [The representation proposal](cognee_stage5_4_5_identity_representation_proposal.md) records ownership choices and rationale. The operation walkthroughs anticipated at this date are complete. Current work is partial Stage-6 implementation, as recorded in the session handoff.

The selected initial direction uses:

- Registered generated identity sources and durable structured assignments.
- Ordinary Entity nodes with explicit local group UUIDs.
- Persistent mention markers.
- Resolution edges with current contributions.
- Identity groups without a privileged canonical member.

Added ordinary Entity fields do not provide authoritative identity state. The design does not require a support node per assignment.

Apply these integration rules:

1. Use a custom Retriever to enforce identity rules.
2. Treat `calculate_chunk_graphs` as graph computation, not an existing-endpoint publication contract.
3. Publish ID-based `custom_edges` through a loading Task bound to an actual source.
4. Retain existing endpoints explicitly without ordinary-field writes.
5. Preserve complete contribution collections on shared edges.
6. Keep native document ownership separate from original-input dependency and applicability.
7. Make maintenance replayable after full-source rebuilds.
8. Verify generated-source retirement, contribution repair and reader eligibility explicitly.

Native Update does not forward customization automatically. The B Task-list transform remains proposed and unimplemented. Routing and standard-entry-point integration still require implementation and verification. Selected source-bound publication and maintenance paths now have native fixtures.

## 14. Original controlled-test inventory and current coverage

The characterization report contains scoped results for source context, deletion, incremental properties and watermarks. The dated source review did not execute the combined identity design.

Later Stage-6 fixtures demonstrate bounded cases from items 1, 2 and 5 below. They also cover selected marker, retirement and rebuild cases from items 3 and 4. This inventory does not imply that every item remains unstarted or that every case passed.

1. Publish an explicit-ID Entity and an ID-based edge to an existing Entity.
   Retain both endpoints without rewriting the existing fields.
2. Publish edges with contributions from several owners.
   Verify collection serialization and aggregation.
3. Store distinct mentions with equal text.
   Verify persistent classification and unresolved-to-resolved replay.
4. Coordinate original-source Update/Forget with generated-source maintenance.
   Verify recreation of solely owned endpoints and markers during generated-source rebuilds.
5. Interrupt publication.
   Verify explicit retry and reader eligibility.
6. Admit selected native operations and readers.
   Check optional consolidation/remapping and consumed graph/vector representations.
7. Check remote transport and version upgrades only when those profiles are admitted.

The [session handoff](../docs/SESSION_HANDOFF.md) records implemented cases and remaining coverage. Broader lifecycle, native-entry-point and retrieval integration remain partial or unimplemented. This editorial revision ran no new runtime test or traversal benchmark.

## 15. Source anchors

The following sources refer to pinned v1.6.2:

- [Improve orchestrator](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/improve/improve.py).
- [Improve stage registry](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/registry.py).
- [Improve stages / TripletEnrichmentStage](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/stages.py).
- [Update](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/update/update.py).
- [Forget](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/forget/forget.py).

The original review also used the following documentation and design sources:

- [Cognee skill / public extension guidance](https://github.com/topoteretes/cognee/blob/main/cognee/skill.md).
- [Architecture guide](https://github.com/topoteretes/cognee/blob/main/CLAUDE.md).
- [Custom Tasks example](https://github.com/topoteretes/cognee/blob/main/examples/guides/custom_tasks_and_pipelines.py).
- [Examples catalog](https://github.com/topoteretes/cognee/blob/main/examples/README.md).
- [Community extensions](https://github.com/topoteretes/cognee-community).
- [Memify design issue](https://github.com/topoteretes/cognee/issues/3389).

### Version note

Pinned source findings and unpinned documentation provide different evidence. Links to `main` can change after review. They do not establish present-day compatibility.

Reinspect internal dependencies when the project changes its Cognee pin. Prefer public DataPoint, Task, Retriever and graph-interface contracts to reduce that review burden.

## 16. Custom Cognify pipeline injection patch option

### 16.1 Motivation

A `science_remember()` or `science_update()` wrapper can compose a full rebuild. However, it duplicates native lifecycle bookkeeping:

- Resolve and preserve `data_id`.
- Call `forget(memory_only=True)` and reset pipeline status.
- Re-add under the pinned ID.
- Check DLT replacement rules and preserve the chunk budget.
- Construct the native `UpdateResult`.

A smaller proposed extension lets native Remember and full-rebuild Update invoke a customized Cognify Task list. Native operations retain lifecycle orchestration.

### 16.2 Preferred patch shape: transform Cognify's standard Task list

Do not replace Cognify with a direct `run_custom_pipeline()` call. Cognify already manages:

- Extractor/runtime setup and ontology/configuration resolution.
- STANDARD, DLT and code route selection.
- Background/foreground execution.
- `pipeline_name="cognify_pipeline"` status.
- `needs_llm` calculation.
- Native rollback and error handling.
- `PipelineRunInfo` results consumed by Remember and Update.

The conceptual SDK-local parameter is:

```python
cognify_task_transform: Callable[[list[Task]], list[Task]] | None = None
```

Apply the transform after native Task construction with `get_default_tasks(...)` or an explicitly supported equivalent. Apply it before `tasks_by_route` assembly and `pipeline_needs_llm(...)` calculation.

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

A transform receives configured native Tasks. It can retain upstream changes to the default sequence instead of replacing that sequence with a complete project-maintained list. A closure can supply project configuration.

The intended initial scope is STANDARD. Temporal/GLiNER equivalents require deliberate scope selection rather than assumed support.

### 16.3 Changes required in pinned 1.6.2

For `cognify()`:

1. Add the optional transform argument.
2. Apply it to the supported route after native Task construction.
3. Reject unsupported remote, dry-run or route combinations, or define their behavior explicitly.
4. Calculate `needs_llm` from transformed lists.

For `remember()`:

1. Add the argument to `RememberKwargs` and `_COGNIFY_ONLY`.
2. Preserve the existing `_remember_inner()` forwarding to its single Cognify call.
3. Preserve `RememberResult`, background handling, native Improve behavior, telemetry, Add and dataset resolution.

For `update()`:

1. Add the same optional argument.
2. Force full rebuild when the transform is non-null.
3. Forward it to the existing full-rebuild Cognify call.
4. Preserve `resolve_data_id`, DLT checks, `forget(memory_only=True)` and `reset_data_pipeline_status`.
5. Preserve pinned `DataItem` re-add, chunk-size reuse and `UpdateResult` behavior.

Arbitrary Tasks do not imply compatibility with the incremental engine. The original review estimated tens of lines plus tests for this patch. That estimate is tentative. No implementation establishes its actual size or maintenance cost.

### 16.4 Why this is preferable to patching Remember/Update with an arbitrary pipeline runner

A replacement `run_custom_pipeline` runner would need Cognify routing, bookkeeping and exact API result structures. A transform changes Tasks inside Cognify while preserving that orchestration. Remember and Update continue to invoke ordinary Cognify.

### 16.5 Important limitations / design decisions

1. **Local Python.** Python callables do not serialize through the remote HTTP API. Remote deployment requires server installation/configuration or a named pipeline registry.
2. **Incremental Update.** Customized Task lists initially require full rebuild. Incremental support needs an explicit future contract.
3. **Dry-run accounting.** Native estimation does not account for arbitrary Tasks. The early options were rejecting `dry_run=True` or explicitly limiting estimates to native work. Reject unsupported combinations in the initial supported route.
4. **Route scope.** Modify only `CognifyRoute.STANDARD` initially. Leave DLT/code routes native unless separately admitted.
5. **Rollback.** Preserve native rollback for native artifacts. Custom side effects may need separate idempotence and cleanup rules.
6. **Task-chain compatibility.** Inserted Tasks must satisfy pipeline input/output contracts. Global maintenance may fit Memify/Improve better.
7. **Special Remember routes.** `content_type="code"`, skills, sessions and MemorySource imports may bypass or alter ordinary Add+Cognify. Do not imply transform support for those paths.

### 16.6 Upgrade resilience

The original review found several reasons to evaluate this interface:

- Pinned 1.6.2 builds route-specific Tasks and passes a resolver to `run_pipeline`.
- The inspected `main` also used `tasks_by_route -> resolve_cognify_tasks -> run_pipeline(... pipeline_name="cognify_pipeline")`.
- Native Remember used one Cognify invocation point.
- The inspected Update versions differed, but their rebuild paths still invoked Cognify.

These observations suggest a reusable conceptual patch location. They do not guarantee stability across later versions. Reapplying this patch may be easier than duplicating Update orchestration, but that comparison remains an assessment.

### 16.7 Comparison of lifecycle strategies

| Strategy | Main benefit | Main cost |
|---|---|---|
| Native Cognify followed by maintenance | Avoids a Cognee patch. | Every project operation must remain valid after standard Cognify. |
| Project `science_remember` and `science_update` wrappers | Gives the project complete orchestration control. | Duplicates or depends on native lifecycle internals, especially Update bookkeeping. |
| Small Cognify Task-transform patch | Preserves native Remember/Update orchestration while allowing extraction-time ordering. | Requires a maintained patch. Initial support is local Python with full-rebuild customized Update. |

The preferred direction is the small Task-transform patch. It permits extraction-time customization while preserving native lifecycle orchestration. The patch remains unimplemented.

### 16.8 Source anchors for this option

The source review identified these call paths:

- [v1.6.2 Remember](https://raw.githubusercontent.com/topoteretes/cognee/v1.6.2/cognee/api/v1/remember/remember.py) calls permanent-memory `add()` and then Cognify. `_COGNIFY_ONLY` routes recognized arguments.
- [v1.6.2 Cognify](https://raw.githubusercontent.com/topoteretes/cognee/v1.6.2/cognee/api/v1/cognify/cognify.py) constructs Tasks, route maps and LLM requirements before native pipeline execution. It invokes `run_pipeline(... pipeline_name="cognify_pipeline" ...)`.
- [v1.6.2 Update](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/update/update.py) rebuilds through memory-only Forget, status reset, pinned Add and Cognify.
- [The inspected main Cognify path](https://github.com/topoteretes/cognee/blob/main/cognee/api/v1/cognify/cognify.py) retained route-specific Tasks and pipeline naming. This is dated evidence rather than a fresh compatibility check.

## 17. Identity-source publication seams — source-inspected, 2026-10-13

[The proposal](cognee_stage5_4_5_identity_representation_proposal.md) records representation choices and the preliminary ownership matrix. This section records their extension implications.

| Seam | What it supplies | What it does not supply automatically |
|---|---|---|
| Registered Data item | Native source lifecycle. A TextDocument anchor can exist without generated identity chunks. | Dependency cascade from the original document. |
| calculate_chunk_graphs | Deterministic replacement for standard text LLM graph extraction. | Controlled references to existing nodes, custom loading or preserved Update routing. |
| Explicit Entity id | ID-keyed persistence and distinct IDs for equal names. | Protection from optional consolidation/remapping. |
| add_data_points custom_edges + real source ctx | ID-based edges with document ownership. | Existing-endpoint retention, assignment-property aggregation or chunk-to-edge evidence. |
| attach_node_source_refs | Deliberate retention of existing nodes without field replacement. | Applicability or original-input provenance. |
| Custom Retriever | Identity-group/mention traversal and project output rules. | Equivalent behavior in native retrieval or Triplet indexing. |

Separate computation from publication. A callback can compute intent. The loading Task controls new-node writes, existing-node references, complete contribution payloads and verification.

Native full-rebuild Update does not preserve arbitrary callback arguments as a durable project route. The initial identity source uses custom Tasks directly without generated chunks. `calculate_chunk_graphs` remains optional for chunk-based extensions.

Bounded native fixtures now exercise the direct custom-Task loader. The B patch and standard-entry-point integration remain incomplete. Broader original/generated-source orchestration also remains incomplete. These are implementation tasks rather than another Stage-5.4 design review.

Evidence does not extend automatically to other backends, optional stages, remote deployment or access-control configurations.

## 18. Reusable knowledge integration methodology and findings — 2026-10-13

The project develops a method for representing selected information as graph knowledge that Cognee can maintain and retrieve. Identity is the first worked integration.

| Activity | Concrete responsibility |
|---|---|
| Describe | Interpret inputs under defined domain rules. Save explicit knowledge, references, applicability and provenance. Identity Describe produces the durable identity source. |
| Publish | Materialize supplied intent with exact IDs, controlled references, writes and retention. Verify persistence. A loading Task completes publication after any graph computation. |
| Maintain | Respond to changed inputs or graph state. Coordinate assignments, shared retention, retirement, replay, consumed stores and failure eligibility. |
| Retrieve | Interpret eligible structures in query context. Return useful content with attribution, appropriate traversal and ambiguity handling. |

### 18.1 Representation meaning and rules: possible ontology connection

Domain concepts, relationship meanings and validity rules may constitute a small ontology. Identity examples include local mentions, reusable variants, scoped equivalence and directed reference.

A graph schema also specifies encoding and validation. Storage IDs, retention references, publication procedures and eligibility require operational rules. Calling the package an ontology does not supply those procedures.

Investigate whether vocabulary/schema, formal ontology or a combination best expresses the domain. Assess how that representation could guide generation, publication, validation and retrieval. Keep domain meaning separate from native persistence and lifecycle behavior. This investigation does not require adopting a formalism or inference engine now.

Stage 7 is the primary ontology/schema investigation. Retain identity examples for the post-Stage-6 review and Stage-8 scientific/measurement work. Scientific justification policies remain deferred.

### 18.2 Reusable integration findings register

Activities identify where findings apply. They do not identify the implementing API. Maintain includes consumed indexes/references and enabled answer reuse. Several findings span all four activities.

| Concrete lesson / cross-cutting finding | Reusable integration finding | Activities | Evidence / design status |
|---|---|---|---|
| Equal-text bindings need explicit IDs. | Define identity independently of display names. Several references with one validated local binding may share an ID. | Describe, Publish, Maintain, Retrieve | Source inspection establishes explicit-ID precedence. Bounded custom-Task fixtures verify selected construction. Broader extraction/conversion remains incomplete. |
| Reference, retention and rewrite are separate actions. | Distinguish existing-node references, deliberate ownership and ordinary-property writes. | Describe, Publish, Maintain | Fixtures characterize recursive rewrite/co-ownership. Stage-6 tests verify existing-node retention without ordinary-field overwrite. |
| Describe specifies creation, references and intended edges. | Save explicit intent. Publish executes declared persistence, aggregation and programmatic rules. | Describe, Publish, Maintain | Draft IdentitySource and controlled publication exist. No universal graph language is selected. |
| Shared ownership does not merge application properties. | Define aggregation/replacement rules and preserve applicability of surviving assignments. | Describe, Publish, Maintain, Retrieve | Source inspection and fixtures characterize native retention/upserts. Stage-6 tests verify contribution aggregation, replacement and withdrawal. |
| Generated sources depend on original inputs. | Record original-to-generated dependencies and define retirement/regeneration. | Describe, Publish, Maintain | Bounded text rebuild and snapshot coordination exist. Dependent-source propagation and full Data removal remain incomplete. |
| Mentions and variants need different traversal rules. | Define relationship interpretation and context eligibility explicitly. | Describe, Publish, Retrieve | Document-context fixture traversal exists. Broader corpus traversal and delivery remain incomplete. |
| Classification can survive resolution changes. | Preserve local Entity IDs and markers independently of accepted links. Replace or withdraw resolution contributions explicitly. | Describe, Publish, Maintain, Retrieve | Captured retarget/removal/reconcile/recovery tests pass. General changed-meaning reconsideration remains incomplete. |
| Maintain owns lifecycle changes. | Detect changes, select affected records and coordinate replacement, retirement and reconstruction. Reuse Publish's write routines. | Publish, Maintain | Fixture maintenance uses Publisher.replace/withdraw and TextChange. Broader affected-source selection remains incomplete. |
| Maintain controls propagation into saved records. | Distinguish accepted source/interpretation changes from native drift, remapping and missing materialization. | Describe, Maintain | Selected responsibility. Automatic graph-to-source synchronization is not implemented. |
| Multi-document behavior must use provenance. | Select affected assignments and preserve independent sources using actual inputs/contributors. Document grouping does not establish independence. | Describe, Maintain, Retrieve | Input checks and known dependent-edit refusal exist. Propagation/reconsideration of external-context dependencies remains incomplete. |
| Describe links document identities to the corpus. | Discover candidates and save exact reuse/create/link intent. Preserve occurrence identity separately from interpretation. Maintain may reconsider older records after new opportunities. | Describe, Maintain, Retrieve | Scope and test direction are selected. General candidate algorithms, reconsideration triggers and stability policy remain unimplemented. |
| Meaning and rules must be explicit. | Define concepts, relationships, valid combinations and context. Assess ontology, schema and operational-rule boundaries. | Describe, Publish, Maintain, Retrieve | Methodological finding and investigation topic. No ontology formalism is selected. |
| Saved descriptions survive graph reconstruction. | Retain sufficient structured inputs, endpoint references and provenance for valid rebuilds and dependency handling. | Describe, Publish, Maintain, Retrieve | Portable storage and selected rebuild/recovery fixtures exist. Broader dependency and explanation behavior remain incomplete. |
| Verify boundaries and consumed representations. | Check supplied intent, writes, lifecycle outcomes, retrieval meaning and actually consumed stores. | Describe, Publish, Maintain, Retrieve | Bounded fixture evidence exists. Complete package coverage and transfer to another domain remain unverified. |

The final three findings concern domain meaning, durable description and boundary verification. They do not add universal requirements. The register combines selected design with explicitly scoped evidence.

### 18.3 Carrying findings to the next knowledge type

For each implemented identity sequence, record its concrete solution and reusable finding. Retain these details:

- Pinned native mechanism and applicable activities.
- Evidence status and tested conditions.
- Required extension and unresolved limitations.

Update findings as evidence changes. During Stage 6, link implementations and targeted tests to each relevant finding. At the checkpoint, distinguish demonstrated common mechanics from identity-specific assumptions.

Use the register as questions for Stage 7 and the Stage-8 measurement example. Measurements can reuse Describe, Publish, Maintain and Retrieve without inheriting identity equivalence rules. A second integration must establish which mechanisms transfer.

No generic plugin runtime or universal ontology framework is selected now. The 2026-10-13 methodology update added neither runtime results nor a new project stage. Later reviews completed the architecture contract. Current implementation and verification appear in the session handoff.

### 18.4 Explicit descriptions and bounded publication — refinement, 2026-10-13

Describe specifies intended edges, exact endpoint references, construction data, relationship meaning, applicability and retention. It distinguishes an existing same-name object from a new object to create. Publish must not infer that distinction.

Publish validates and persists declared intent. It handles stable-ID replay, endpoint retention, contribution aggregation, selected programmatic steps and verification of stored results. Each assignment supplies its contribution. Publish assembles the current shared-edge collection rather than copying a stale property snapshot.

Specify programmatic behavior in the publisher/Task configuration and recovery path. Do not make generic publication perform another identity judgment. The runtime now implements identity-specific serialized forms and bounded publication. A general language of operations and dispatch of named rules remain broader work.

This refinement applies to Describe, Publish and Maintain. At this date, it preceded the walkthrough of edges between two existing endpoints. That walkthrough is no longer the next task.

### 18.5 Publish and Maintain responsibilities — clarification, 2026-10-13

Publish materializes a supplied description. It handles initial insertion, integration with existing endpoints and explicitly requested replay. It applies declared creation, reference and retention rules. It does not independently discover lifecycle changes.

Maintain coordinates later changes:

- Detect changed or retired inputs.
- Select affected records.
- Recompute interpretations and shared contributions.
- Replace or withdraw output.
- Coordinate original/generated-source lifecycles.
- Manage eligibility and failure handling.

Maintain may invoke Describe and reuse Publish's persistence routines. Classify work by responsibility rather than by the low-level function that writes the graph. Initial shared-edge insertion belongs to Publish. Contributor retirement primarily belongs to Maintain.

A mention Entity and its marker can persist while Maintain changes or withdraws its resolution. Rebuilding a generated source may recreate required objects at saved IDs. Original occurrence changes still require validation or regeneration. Automatic matching across source revisions is not established. Omission from incoming objects does not retire old relationships.

This clarification does not select a separate maintenance engine or establish atomicity.

### 18.6 Saved-record propagation under Maintain — clarification, 2026-10-13

Maintain manages both saved knowledge and materialization. It decides which changes update records and which require repair, remapping or temporary invalidation.

Update a saved description after accepted interpretation changes, resolution withdrawal or validated original-input changes. A missing edge, overwritten description or temporarily absent endpoint does not automatically establish a knowledge change.

A known ID migration may justify a validated reference update. Unexplained endpoint loss does not justify a same-name substitute. Original text and coordinates come from checked source input. Accepted targets, applicability and producer attribution come from identity processing.

Interpretation changes preserve continuing occurrence identity. Changed occurrences require validation or regeneration. Saved-record updates can succeed while graph writes fail. Preserve intended state for retry and withhold affected retrieval until required materialization agrees with current intent.

Current admitted paths use portable revision/attempt guards, minimal plans and explicit caught-failure handling. They do not provide a transaction across stores. Proposal section 2.3 records occurrence policy. This policy requires neither an archive nor automatic copying from graph properties into saved records.

### 18.7 Operation sequences as regression scenarios — 2026-10-13

Use each reviewed sequence and expected result to define a regression scenario. Retain the following:

- Initial fixture and initiating operation.
- Expected saved records and exact graph IDs/properties.
- Native owners, retrieval eligibility and applicability.
- Consumed-store checks and failure/recovery results.

Proposal section 11 records the original matrix. Roadmap section 6.6 carries the broader implementation plan. The Stage-6 contract provides concrete case IDs.

Use captured decisions for deterministic lifecycle tests. Use isolated actual stores and source contexts for persistence tests. Test maintenance/retrieval together and inject failures. Evaluate interpretation quality separately.

A programmatic/native subset passes. The session handoff identifies coverage without claiming every planned case or model-quality evaluation.

Shared-source withdrawal adds four specific checks:

1. Native owner survival does not remove obsolete contribution properties.
2. Retiring X need not change independently valid assignment Y.
3. Repair must not reattach a retired source.
4. A retained edge without accepted current contributions is not a usable identity relationship.

### 18.8 Multi-document preservation and Describe variability — 2026-10-13

Updating a document must preserve independently supported interpretations from other documents, including those sharing Entity IDs. Use input and contributor provenance in selection, retirement, aggregation and retrieval. Merely storing provenance or retaining the shared node is insufficient.

Reevaluate records that received changed document, candidate or assignment context. Grouping records by generated source does not isolate dependencies. Record the context supplied to Describe. Do not claim to identify an LLM's causal use of each snippet.

Input references and content checks permit conservative invalidation and reproducible tests. Native Entity property changes do not authorize rewriting saved source interpretations.

Proposal section 12 separates these investigations:

- Independent and dependent multi-document changes.
- Repeated identical Describe inputs.
- Edits that preserve meaning and edits that change meaning.
- End-to-end processing variability.

Freeze candidate graphs, chunks and context for isolated Describe tests. Compare corresponding occurrences, exact targets, benchmark groups, statuses, applicability and unrelated changes. Evaluate correctness separately from agreement.

No consistency result, stabilization policy or automatic acceptance threshold is established by this design entry.

### 18.9 Describe includes corpus identity resolution — clarification, 2026-10-13

Describe identifies document forms/occurrences and relates them to eligible corpus singletons and identity groups. It selects exact existing references, required new objects, variant/mention assignments, applicability and unresolved outcomes. Publish executes that supplied intent.

Candidate discovery need not scan every Entity. A document-local inventory alone does not satisfy the selected scope.

For source modifications, validate occurrence continuity separately from interpretation reuse. Unchanged IDs do not justify ignoring changed document or corpus context. Preserve independent interpretations and record external inputs for maintenance selection.

Linking a new document to existing identities belongs to Describe. Selecting older unresolved/ambiguous records after a new corpus opportunity belongs to Maintain. Maintain can invoke Describe for those selected documents.

Positive dependencies cannot record previously absent candidates. Opportunity-selection triggers therefore remain open. They are not supplied automatically by input references.

Proposal section 2.4 records this scope and its tests. General corpus-resolution algorithms, exhaustive candidate coverage and automatic corpus-wide reconsideration remain unimplemented.

### 18.10 Shared stored-representation mutation interface — agreed direction

Use a shared interface to read and apply guarded saved-description changes. It supports explicit source replacement/retirement and changed-ID reporting. Domain helpers enforce meaning. Storage persists intent.

Distinguish resolution withdrawal, occurrence retirement, representation revision and original-input revision. Maintain coordinates explicit graph publication.

Current runtime storage combines registered Data, relational records and guarded Publisher publish/replace/withdraw operations for admitted paths. A generic fine-grained record-edit API remains broader work. Illustrative interface names in this reference are not native Cognee APIs.

### 18.11 Saved-state/publication failure coordination — proposed next review

**Historical heading:** This protocol awaited review when first recorded. Current admitted paths implement the reviewed protocol.

Proposal sections 13–14 record storage and completion coordination. Save intended descriptions, reconcile required materialization, verify it and acknowledge the exact current revision. Failed or superseded attempts cannot acknowledge currentness.

Reuse saved decisions during publication retry. Rerunning Describe may change interpretation and is a separate operation. Preserve eligible shared contributors while excluding pending or retired contributions, subject to required object/index validity.

Saved-state and graph writes are separate failure boundaries. The portable ledger and controlled publisher implement the protocol for admitted operations. They provide neither a cross-store transaction nor historical-property rollback. Broader dependencies, source orchestration and standard entry points remain incomplete.

### 18.12 A/B generation staging and extensible recovery — proposed, 2026-10-13

**Status:** Optional feasibility work. The initial implementation uses guarded state and explicit forward recovery instead.

The proposal evaluates a coherent candidate generation containing graph, saved descriptions, source files, relational/provenance state and consumed vector/evidence state. Apply and validate changes in the candidate before selecting it as active. Stage original-source changes too. Shared endpoints and indexes prevent assuming an isolated one-source copy.

Clone probes demonstrate isolated subprocess operations. They do not establish coherent live snapshots or promotion. A Ladybug checkpoint makes previous graph writes durable. It does not synchronize SQLite, LanceDB and source records.

Before any staging implementation:

1. Audit path rebinding and native bookkeeping that occurs during reads.
2. Serialize writes while constructing the candidate copy.
3. Flush required handles.
4. Close required handles.
5. Reopen readers/processes against the selected generation.
6. Avoid copying over open live files.

Keep preparation, execution, validation, promotion and recovery policy separate. Retain candidate/base IDs, revisions, intent, phase/error and validation evidence. Extend retry, repair, rebuild and rejection handlers as actual failure classes become known.

A failed candidate leaves A selected. Interrupted or superseded promotion requires checking the actual generation selector. Proposal section 15 and roadmap sections 6.4/6.6 record feasibility tests.

This proposal establishes neither native multi-store transactions nor a measured promotion result. It requires no general version archive. Generation labels A/B differ from the B Cognify patch option.

### 18.13 A/B complexity boundary — 2026-10-13

A/B staging is optional and does not block the first iteration or Stage-6 handoff. Measure copying, shared-store scope, path/adapter rebinding, native bookkeeping, promotion, storage and time costs. Defer staging when those costs exceed its initial benefit.

Guarded pending state and captured-intent retry remain the baseline. Keep execution, validation and recovery policy separate enough to permit later staging. No general snapshot framework or concurrent-generation service is selected.

### 18.14 Structured sources and optional prose/chunks — accepted identity simplification, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Identity uses structured JSON registered as generated Cognee Data. Custom Tasks consume those records directly. Generated identity prose/chunks remain unnecessary until a retrieval or model consumer needs them. Render explanations on demand and retain substantive explanations where useful.

**Superseded marker choice:** The 2026-10-14 proposal used the generated TextDocument as the mention-marker anchor. The later contract uses original occurrence-covering DocumentChunks. Generated identity Data owns contributions and required-endpoint retention. Its TextDocument remains a source anchor but does not anchor mention markers.

The inspected source establishes these primitives:

- The text loader accepts JSON.
- Classification maps JSON to TextDocument and uses Data.id as document ID.
- `add_data_points` accepts ordinary DataPoints and ID-based edges under a source context without requiring generated chunks.

Add registration alone does not publish a semantic graph. At the dated source review, the combined chunkless workflow had no live test. Later Stage-6 fixtures verify bounded direct custom-Task publication. `calculate_chunk_graphs` remains optional for chunk-based processing.

Separate the authoritative description, native source/ownership anchor and optional retrieval text. A text-bearing source anchor does not require another LLM parse or generated chunks. Later knowledge types must assess their own retrieval needs.

Pinned 1.6.2 source anchors are:

- `cognee/infrastructure/loaders/core/text_loader.py`
- `cognee/tasks/documents/classify_documents.py`
- `cognee/modules/data/processing/document_types/Document.py`
- `cognee/tasks/storage/add_data_points.py`

### 18.15 Reference grouping and graph materialization granularity — initial decision, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Initially, paragraph-local groups collect exact references with one interpretation into a saved group and mention Entity. Classification and accepted resolution remain separate relationships. A deliberate selection policy avoids materializing every pronoun by default.

Grouping can reduce potential object counts. No scaling measurement is established. Distinguish input references, saved records and graph objects when choosing granularity.

Compact groups require member positions, exact applicability and explicit split/combination rules. A group endpoint does not attribute every incident fact to one occurrence. Context passages inform interpretation without defining blanket resolution scope.

This decision supersedes the earlier one-occurrence-per-node default. Alternatives remain detailed records with a compact graph, property/contribution references, saved-record-only mentions and wider contexts. Broader semantic-edge compaction is not selected.

Proposal section 17 records rationale, alternatives and scenarios. Other domains should reuse the granularity/cost analysis without automatically adopting paragraph grouping.

### 18.16 Saved interpretation separated from captured references — agreed direction, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Keep local reference groups separate from interpretation records. A mention resolution identifies its group, accepted target, state, applicability, supplied inputs and producer. A stable assignment ID also identifies the published contribution. Unresolved/ambiguous records may retain candidates without accepted graph edges.

The source envelope supplies source identity and revision. Whole-group retargeting changes the resolution. Partial retargeting first splits the group. Withdrawal does not automatically retire references or classification.

Variant records use the shared assignment/provenance machinery. They identify two exact reusable endpoints and explicit applicability without referring to a mention group.

Object identity, captured inputs and interpretation can have different lifecycles. The shared mutation interface must preserve those distinctions. Proposal section 18 contains the agreed forms. Runtime models and exported schema now implement draft serialization. These records are not graph support nodes.

### 18.17 Durable construction fallback for borrowed corpus endpoints — revised proposal, 2026-10-14

**Applies to:** Describe, Publish, Maintain.

Existing references and current ownership do not guarantee future reconstruction. A generated source may become an endpoint's last owner. Rebuilding that source may temporarily delete the endpoint.

Store minimal construction recipes for every required corpus-backed endpoint, including existing endpoints. Existing-node publication attaches references without ordinary-field writes. Valid missing output can be reconstructed at the saved UUID.

Recipe availability does not establish permission to reconstruct. Retired inputs and invalid assignments require maintenance. Recipes provide initial fields rather than complete relationships or current property authority. Different recipes need no merge while the Entity exists.

Supported writer coordination must prevent create-if-missing from becoming an unintended upsert of an existing node. Proposal section 19 records the policy. Bounded Stage-6 fixtures now demonstrate exact-ID creation/reference and captured recovery. Full generated-source last-owner rebuild coverage remains broader work.

Carry the last-owner sequence into later integration tests. Distinguish expected missing materialization from an unexpected missing reasoning input.

### 18.18 Publication state separate from saved knowledge — agreed initial design, 2026-10-14

**Applies to:** Publish, Maintain and Retrieve. Describe supplies captured intent.

**Superseded storage choice:** The original proposal named a project-owned SQLite ledger. The later portability decision requires backend-neutral relational models through Cognee's configured engine/session layer. SQLite remains part of the tested configuration only.

The current ledger key comprises dataset and generated Data ID. It records pending/current/failed/withdrawn state, intended and verified revisions, current attempt and diagnostic references. Saved JSON remains authoritative for knowledge.

Mark affected sources unavailable before supported mutations. Publish and verify required graph/index state. Acknowledge only the matching saved revision and attempt. A new attempt may repair unchanged valid intent without creating a new description revision.

Preserve unaffected contributions only while their required objects and indexes remain valid. Native lifecycle status and retrieval do not enforce this project protocol automatically. Supported Tasks/wrappers and the custom reader must participate explicitly.

Portable guards and admitted publication paths now exist. Broader mutation hooks and dependency coordination remain incomplete. The ledger does not provide a cross-store transaction. A/B remains optional.

Other domains may reuse the distinction between saved meaning and verified materialization. They still select their own required representations and affected sets. Proposal section 20 records the original decision and regression boundaries.

### 18.19 Describe baseline: native behavior, representative approaches and model-neutral decisions — source review, 2026-10-14

**Applies to:** Describe, Publish and Maintain. Retrieve consumes resulting applicability and provenance.

**Evidence:** Cognee 1.6.2 source inspection at commit `ba3631f2ed363a6ea50d649c34c56885af6b36fe`. This review added no accuracy test or adopted model. A replaceable decision-model backend remains a longer-term goal alongside LLM-based processing.

#### Native mechanisms actually found

| Mechanism | What the inspected code does | Implication for this project |
|---|---|---|
| Default Cognify | Classify, chunk, call extract_graph_and_summarize, then add_data_points. Optional stages add provenance or contradiction processing. | Reuse Tasks and persistence. The default list has no separate coreference/corpus linker. |
| extract_graph_from_data + extract_content_graph | Extract structured graphs per chunk using chunk.text and prompt/model. Accept precomputed graphs through calculate_chunk_graphs. | Default coreference occurs within generative extraction rather than explicit span/cluster decisions. |
| Default graph prompt | Request the most complete identifier when aliases/pronouns denote one entity. | Prompt instructions do not establish coreference accuracy or saved occurrence provenance. |
| Generic KnowledgeGraph | Store Node ID/name/type/description and relationship endpoints/text. Omit explicit mention ranges, coreference clusters and scored corpus candidates. | Normalized graphs alone do not supply precise source/reference records. |
| Entity construction | Usually use Entity.id_for(name). Repeated equal-name Nodes with distinct graph-local IDs within one graph receive chunk/ordinal-scoped IDs. A batch dictionary reuses constructed IDs. | Deterministic matching permits reuse but does not decide contextual equivalence. Equal names do not always collapse. |
| Chunk contains/provenance | Link chunks to constructed Entities and record semantic edge identities/text. | This provides coarse grounding rather than exact pronoun spans or local-group bindings. |
| Optional consolidate_entities_pipeline | Embed names. Group normalized matches or thresholded similarity through union-find with type guards. Choose a representative, redirect edges, combine descriptions and delete duplicates/vectors. | Physical consolidation differs from scoped non-destructive identity and contextual pronoun resolution. Exclude or adapt this path. |
| Optional ontology resolver | Normalize matched classes/individuals to ontology names and attach ontology structure. | Ontology matching differs from general corpus candidate ranking. |
| Optional extractor='gliner_demo' | Supply local entity/relation extraction as precomputed KnowledgeGraphs. Tasks use needs_llm=False. | This demonstrates a non-generative integration pattern. It is not a complete corpus linker/coreference system. |
| GLiNER generic mapper | Request spans/confidence and use positions to select detections. Discard positions in generic Nodes and deduplicate by type/name. Match relation endpoints through normalized strings or unambiguous containment. | Adapt before this information loss when exact ranges/bindings are required. Do not infer discarded positions from final Nodes. |

Default per-chunk extraction does not explicitly supply a corpus candidate catalogue to its LLM call. Later existing-edge lookup checks storage/retention identities. It does not disambiguate entity candidates. Optional resolvers and callbacks may add behavior. These findings apply to the inspected default and named optional paths.

#### Representative established approaches (limited review)

Coreference finds textual mentions and groups those with the same referent. Discriminative systems score spans/antecedents or assign mentions to evolving clusters. Maverick demonstrates learned mention detection and clustering without a general-purpose autoregressive LLM. Its ACL 2024 results do not establish accuracy on this scientific corpus.

- [Maverick paper](https://aclanthology.org/2024.acl-long.722/).
- [Method](https://arxiv.org/html/2407.21489v1).
- [Authors' implementation](https://github.com/SapienzaNLP/maverick-coref).

Entity linking maps mention/context to catalogue identities. BLINK first encodes contexts and entity descriptions independently to retrieve candidates. It then encodes each candidate jointly with context to rank candidates. This separates candidate coverage from selection quality. It does not directly implement the project's dynamic groups, applicability or uncertainty policy.

- [BLINK paper](https://aclanthology.org/2020.emnlp-main.519/).
- [Authors' implementation](https://github.com/facebookresearch/BLINK).

These examples illustrate architecture patterns. They are neither a 2026 leaderboard nor an exhaustive survey or installation recommendation. Scoped identity and lifecycle behavior still need project logic.

#### Proposed implementation-neutral Describe boundary

Use replaceable inference functions for mention detection/grouping, candidate retrieval and identity decisions. Implementations may use LLMs, discriminative encoders/rankers/classifiers, rules or combinations. They need not emit prose, prompt text or JSON directly.

Adapters normalize backend outputs. Programmatic assembly and validation produce saved records and publication intent. A joint backend may perform several conceptual steps. Three separate models or passes are not required.

Inputs include:

- Exact source text/version and paragraph/section context.
- Grounded mention spans and groups.
- Eligible candidate Entity/group references, names, descriptions and source information.
- Relevant previous records for maintenance.

Outputs may include:

- Token/character spans and grouping assignments.
- Candidate/action IDs and optional scores.
- Accepted, unresolved or ambiguous decisions.

For existing candidates, map finite candidate keys to exact UUIDs in code. For new identities, allocate IDs and assemble minimal corpus-backed recipes in code. Validate token offsets against document coordinates, reference keys, applicability and role exclusions. Supply revisions, contributions and ownership instructions programmatically.

Do not substitute same-name endpoints silently. Do not infer a decision absent from backend output.

The design selects no mandatory natural-language explanation, fixed threshold, calibration or universal feature vector. Scores from different models are not necessarily comparable. Preserve producer/model/version/configuration, supplied candidates/context and normalized decisions.

Candidate discovery remains replaceable. A scorer cannot select a correct target absent from its candidates.

Paragraphs define initial storage/grouping granularity. They do not bound reasoning context. A document-level coreference backend may produce wider clusters. An adapter may project validated references into paragraph-local groups while retaining exact ranges and wider input dependencies.

This separation avoids insufficient context for pronouns. It also prevents treating document-level coreference clusters as global variant equivalence.

For future training and evaluation, retain supplied alternatives and distinguish proposals from validated labels or benchmark truth. Evaluate candidate recall, mention/group quality, final linking/abstention and consistency separately. No training pipeline or label-correctness guarantee exists now. Document-held-out evaluation and review-derived labels remain possible later work.

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

Retain selected pronoun/context-only groups as graph mention Entities. Store exact ranges and stable UUIDs. Preserve source markers independently of accepted scoped `resolves_to` edges. A group requires no preferred noun phrase.

Use ordinary Entities and relationship-based classification. Common words do not become global aliases. No separate support-node class is required.

This decision supersedes the earlier saved-only default. Grouped nodes keep bindings available to traversal and provide local fact endpoints with potentially fewer objects. Durable records remain necessary for provenance and recovery. Discovering a binding should not require reparsing its passage.

Semantic facts need exact endpoint binding and original-source attribution. Native extraction does not automatically select the saved group UUID. Partial retargeting must not move unrelated facts. Mention references retain directional meaning.

Proposal section 22 records the contract and scenarios. Captured fixtures now demonstrate selected local facts and bindings. Automatic grouping and broader interpretation quality remain unimplemented.

### 18.21 Seeded description and representative full-pipeline fixtures — selected direction, 2026-10-14

**Applies to:** Describe. End-to-end fixtures also exercise Publish, Maintain and Retrieve.

The selected pass order is:

1. Discover names and reusable-form candidates.
2. Recognize explicit abbreviation definitions and generate initial-letter candidates.
3. Use those seeds for semantic and corpus matching.
4. Extend matching to shortenings and descriptive references.
5. Resolve pronouns/contextual references using established referents and sufficient context.

Earlier results inform later passes. Candidate providers and inference backends remain replaceable. Conceptual passes need not correspond individually to model calls or graph writes.

Parenthetical patterns and initials provide initial candidates. Pattern evidence, proposed interpretations and published applicability remain distinct. Initials alone do not establish a reusable relationship. Handle collisions and local-only meanings explicitly.

First demonstrate a small set of each relevant type, with selected negative, ambiguous and lifecycle cases. Improve linguistic coverage afterward. Hidden benchmark answers remain evaluation data rather than inference inputs. Captured decisions isolate persistence tests from Describe quality.

Proposal section 23 and roadmap section 6.2 record this direction. Native Tasks/extraction may supply useful inputs. This design entry adopts no model and establishes no accuracy result. Automated Describe remains step-6 work.

### 18.22 Routing discriminator and fact-endpoint binding — investigation, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

The source review investigated generated-source routing and local fact placement. It established the following:

1. JSON maps to TextDocument/STANDARD. Content kind and `external_metadata` do not independently control Cognify routing.
2. Routing uses each item's persisted `system_metadata`, extension and classification. The dataset runner accepts a Task resolver. Cognify supplies native routing policy.
3. A uniform STANDARD transform does not distinguish identity JSON from ordinary text.
4. Re-add replaces route metadata from current content/item, including absent metadata. Preserve or regenerate an identity discriminator across admitted rebuilds and reloads.
5. Loader-result stamps provide a native precedent for routing metadata.
6. A custom publication pipeline isolates its own writes but does not govern later standard Cognify/Update automatically.
7. Dataset orchestration includes reentrant locks. Nesting alone establishes neither a deadlock nor correct context/rollback behavior.
8. Native extraction/evidence stores endpoints, edge identities, source chunks/runs and optional edge text. It does not store exact subject/object reference spans.
9. The optional best-effort audit ledger does not replace exact occurrence evidence.

Validate routing with mixed-source, restart and update probes before claiming standard-entry-point support. Current custom Tasks do not establish that broader integration.

Contextual facts need explicit binding to local groups. Storing facts on M and storing them directly on reusable A have different retargeting and contribution costs. Reuse native extracted graphs only with grounded, unambiguous mappings. Name matching or blanket endpoint rewrites across a chunk are unsafe.

This investigation treated completed-native-graph-then-Describe ordering as provisional. Section 18.23 records the later selected ordering before final persistence. Proposal section 24 retains routing evidence, alternatives and the small probe. This work selects neither universal fact rewriting nor a scientific-support schema.

Pinned source paths include:

- `modules/cognify/routing.py`
- `tasks/documents/classify_documents.py`
- `tasks/ingestion/ingest_data.py`
- `api/v1/update/update.py`
- `api/v1/cognify/cognify.py`
- `modules/pipelines/operations/pipeline.py` and `run_tasks.py`
- `modules/graph/utils/expand_with_nodes_and_edges.py`
- `shared/data_models.py`
- `modules/provenance/edge_evidence/models.py` and `buffer.py`
- `tasks/provenance/record_provenance.py`

### 18.23 Custom identity-aware relation extraction before persistence — clarification, 2026-10-14

**Applies to:** Describe and Publish. Maintain reuses extraction on affected inputs. Retrieve consumes the result.

A relation-extraction Task generates facts from original text plus explicit identity bindings. Identity processing establishes local groups and reusable forms. Conversion maps endpoint keys to exact IDs. Publish writes supplied relationships. Creating an Entity or resolution link does not generate semantic facts.

Use the STANDARD sequence: classify, chunk, extract_graph_and_summarize, add_data_points. Insert identity preparation and replace/adapt extraction/conversion before persistence. Reuse summarization and storage where compatible.

Custom Tasks can demonstrate the sequence in a project pipeline. Standard Cognify/Remember/Update integration and per-item identity-JSON routing remain extension work.

A calculation callback alone does not preserve arbitrary Node IDs as Entity UUIDs. The generic converter normally derives Entity IDs from names. Bind mention, variant and existing-object keys explicitly. Attach references deliberately and publish ID-based edges. Preserve document context across streamed chunk batches.

Contextual facts attach to M, which references its reusable target. Explicit variant facts may attach to the variant itself. Generate relations from source passages. Do not copy all group facts onto a new alias.

Preserve original-source provenance. The initial captured fixtures provide bounded writers and recovery checks. Complete semantic-output capture and exact replay remain deferred under the later recovery scope.

Proposal section 25 records anchoring, Task responsibilities and examples. This decision supersedes mandatory native-graph-first ordering. It concerns ordinary source-grounded extraction rather than scientific-support reasoning. The dated design entry itself added no runtime result.

### 18.24 Native factual coverage versus binding/provenance improvements — deferred measurement, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Native extraction may already produce facts needed by the identity-aware path. A future controlled comparison should distinguish:

- Shared, new, missing or misinterpreted factual content.
- Endpoint binding and qualifiers/applicability.
- Original-source attribution and producer/run lineage.
- Duplicate representations of one source statement.

Use isolated/captured comparisons and validated identity mappings. Raw edge-ID equality alone does not establish equal meaning. Results can guide native extraction reuse, deduplication and provenance design.

Proposal section 26 records this deferred comparison. It adds no implementation gate, result or scientific-support rule. This editorial stage does not run the comparison.

### 18.25 Preserve native semantic fact representation and provenance — goal and compatibility findings, 2026-10-14

**Applies to:** Describe, Publish, Maintain, Retrieve.

Use Cognee's ordinary fact relationships, original-source attribution, native ownership/deletion and configured indexing where compatible. Identity changes endpoint selection. It does not alone justify a separate fact/provenance framework.

In pinned 1.6.2, conversion records each chunk's produced edge identities and extracted evidence before deduplication. `add_data_points` derives chunk owners from those records and reachable DocumentChunks. Existing facts may gain new owners/evidence without an edge rewrite.

Edge-evidence capture defaults on, subject to configuration. It records source Data, chunk, run and edge. It does not record exact subject/object mention bindings. The independent hash-chained audit ledger remains optional and best-effort.

Original producing chunks remain baseline owners/evidence sources for ordinary semantic facts, including mention- and variant-anchored facts. Generated identity Data owns its identity contributions. Original source, producer, applicability and retention are distinct.

| Finding | Activities | Integration consequence |
|---|---|---|
| Conversion selects stored Entity UUIDs. Copying graph-local Node.id is insufficient. | Describe, Publish | Bind saved mention/variant/existing keys to exact IDs before persistence. |
| Populated existing DataPoints may enter native upserts. | Publish, Maintain | Preserve original chunk attribution without unnecessary ordinary-field writes. |
| custom_edges uses a separate document-owned path. | Publish, Maintain | Preserve native produced-edge and evidence records. Custom edges do not automatically supply chunk relationship/evidence semantics. |
| Native evidence omits exact local-group endpoint/range bindings. | Describe, Maintain | Retain required captured bindings for splits/recovery. Use native provenance for ordinary attribution. |
| Original chunks can retain M/facts independently of generated Data. | Publish, Maintain, Retrieve | Preserve mention classification across source lifetimes. The later design assigns markers to original chunks and explicitly retains their mention endpoints. |
| ID-only edges may miss optional Triplet embeddings when endpoints are absent from the current batch. | Publish, Maintain, Retrieve | Verify each consumed derived index separately from graph success. |
| A physical source/name/target edge has one ordinary property bag and may have several owners. | Describe, Publish, Maintain, Retrieve | Begin with native fact behavior. Extend only for demonstrated losses. Identity contributions do not automatically generalize to all facts. |

The earlier review left marker ownership undecided. Later original-chunk markers and endpoint retention supersede that uncertainty. Captured fixtures now verify original-owned facts/evidence, exact-ID references and mention survival after generated-source withdrawal.

Proposal section 27 retains the inspected baseline and planned sequences. General semantic conversion and dependency lifecycle remain incomplete. Native-versus-custom extraction coverage remains a deferred experiment. The original source review itself added no runtime evidence.
