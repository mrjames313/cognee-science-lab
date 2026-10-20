# Building a source-backed knowledge integration in Cognee

**Consolidated:** 2026-10-15 (America/Detroit).

**Editorial revision:** 2026-10-20. STE-flavored technical prose.

**Inspected baseline:** Cognee 1.6.2, commit `ba3631f2ed363a6ea50d649c34c56885af6b36fe`.

**Test configuration:** Ladybug, LanceDB and SQLite.

**Current status (2026-10-20):** This playbook records a reusable process and bounded identity evidence through captured occurrence additions. Fixtures exercise supplied decisions through Publish/Maintain and Retrieve. Automatic Describe, full source/dependency lifecycle, standard entry points and general retrieval remain incomplete.

Measurement examples illustrate transfer questions. They do not select a scientific schema. [SESSION_HANDOFF.md](../docs/SESSION_HANDOFF.md) records current code and verification. The [Stage-6 contract](cognee_identity_stage6_handoff.md) defines identity behavior and the implementation plan. Dated evidence below describes each checkpoint.

### Separate the test profile from implementation dependencies

The tested provider combination does not authorize backend-specific integration code. Use Cognee's configured graph/vector factories, their interfaces and the configured relational engine/session layer. Keep project ledger/event models and operations backend-neutral.

Do not depend on:

- A separate SQLite database.
- Adapter-client calls or backend-specific queries.
- Storage-file layouts.
- Backend-name branches in domain logic.

Report missing provenance, indexing, serialization or concurrency capabilities as compatibility gaps. Do not bypass the abstraction. A common interface does not establish equivalent adapter behavior. Qualify results by their tested configuration. Carry this rule into subsequent integrations.

## 1. What carries over to the next integration

An integration combines four components:

1. An explicit saved knowledge description.
2. A graph projection linked to the existing corpus.
3. Procedures bound to actual source lifecycles.
4. Retrieval that interprets the projection correctly.

An overlay is a logical collection of structures and rules. It need not use another database, one node per record, or one node class per concept.

| Activity | Reusable responsibility | Identity example | Possible measurement example |
|---|---|---|---|
| Describe | Interpret inputs, find corpus matches and save creation/link intent. | Local groups, existing Entity UUIDs and variant/mention assignments. | Value, quantity, unit, conditions and existing instrument/sample/facility links. |
| Publish | Validate and materialize supplied intent under actual source contexts. | Exact-ID Entities, original-chunk markers and resolution contributions. | Measurement structures and declared links to corpus objects. |
| Maintain | Coordinate changed inputs, retirement, shared ownership, recovery and consumed stores. | Replace source-specific assignments and rebuild valid materialization. | Replace, retract or reinterpret records after source/calibration changes under selected rules. |
| Retrieve | Select eligible structures and expose their meaning/evidence. | Scoped identity traversal, original facts and local binding annotations. | Select by quantity, condition and unit while retaining attribution. |

The domain adapter defines interpretation. Native persistence, ownership attachment and failure coordination are separate mechanics. Shared lifecycle procedures do not make identity equivalence appropriate for measurements.

## 2. The reusable package to produce each time

Complete this checklist for each knowledge type. Reuse native investigations when version, backend and profile match. Probe the differences.

| Deliverable | Questions to answer | Completion evidence |
|---|---|---|
| Meaning and invariants | What do records/edges mean? Which combinations are valid? | Domain rules and counterexamples separate from serialized field names. |
| Saved-description contract | Which decisions are authoritative? Which exact existing objects are referenced? | Versioned schema, valid example and rejected invalid examples. |
| Publication/ownership matrix | Who creates, retains, rewrites and deletes each object/edge? | Actual native references and properties in a small fixture. |
| Input/continuity policy | What identifies records across edits? Which supplied inputs can invalidate them? | Repeated-input and source-edit examples. |
| Operation contract | What happens during add, overlap, update, removal, rebuild and retry? | Before/after sequences and partial-failure expectations. |
| Consumed-store manifest | Which graph, vector, evidence and session stores do enabled readers query? | Runtime configuration and returned-ID/content checks. |
| Retrieval contract | How does retrieval interpret, limit, rank and render candidates? | Correct, ambiguous, unavailable, empty and limited cases. |
| Model boundary | Which operations use code, lookup/scoring or semantic judgment? | Replaceable inference/rule adapters and deterministic orchestration fixtures. |
| Diagnostic contract | Which structures and cost limits can code inspect without semantic judgment? | Shared checks/counters and explicit coverage. |
| Reuse report | Which mechanisms worked, under which conditions and limits? | Source/implementation references and passing tests, or explicit untested status. |

The [identity contract](cognee_identity_stage6_handoff.md), draft schema and example provide the current worked structure. Reuse that structure without copying identity-specific fields into another domain.

## 3. Lessons register with activity and transfer checks

**D:** Describe. **P:** Publish. **M:** Maintain. **R:** Retrieve.

The [extension reference](cognee_extension_architecture_reference_v1.6.2.md), section 18, contains detailed evidence and design history. This register consolidates reuse questions. An activity label identifies responsibility, not an API.

| ID | General lesson/process | Activities | Current basis | What the next integration must verify |
|---|---|---|---|---|
| G01 | Separate explicit IDs and continuity from names and offsets. | D, P, M, R | Native fixtures cover exact-ID creation/reference and captured shifts, removals and additions. Broader regrouping remains incomplete. Addition evidence retains the launcher qualification described below. | Define identity for repeated equal-valued measurements and source revisions. |
| G02 | Reference, retention and property persistence are distinct. | D, P, M | Characterization covers recursive overwrite/co-ownership. Native fixtures verify retention without ordinary-field overwrite. | Link existing instrument/facility nodes without rewriting them. |
| G03 | Save exact intent and execute declared publication rules. | D, P, M | Captured corrections and recovery use the common publisher without fresh inference. | Specify endpoints, edges and aggregation explicitly. Do not require Publish to infer meaning. |
| G04 | Native ownership does not aggregate application properties. | D, P, M, R | Two-source tests cover aggregation, both withdrawal orders, surviving owners and last-owner deletion. | Decide whether native shared-edge properties suffice for values and qualifiers. |
| G05 | Evidence, generated ownership and producer attribution are distinct. | D, P, M, R | Original facts, markers and evidence survive generated-source withdrawal in fixtures. Marked endpoints require explicit original retention. | Specify evidence and endpoint retention separately from generated structure ownership. |
| G06 | Generated registered Data does not automatically follow its original input. | D, P, M | Generated-output withdrawal exists. Coordinated original/generated Data deletion remains incomplete. | Map original inputs to generated sources and coordinate retirement/refresh. |
| G07 | Actual supplied context and selection changes define dependencies. | D, M, R | Fingerprints, spans and current chunk maps have checks. Text-change preflight refuses known dependent edits pending propagation. | Capture supplied calibration, unit definitions and corpus context. Handle inserted context. |
| G08 | Saved meaning and graph writes have separate failure boundaries. | P, M, R | Native revision tests interrupt saved-record, registered-Data, graph and retirement writes. The ledger withholds unfinished sources. | Reuse publication guards. Keep diagnostic incidents separate from eligibility authority. |
| G09 | Reconcile valid intent and explicitly reconsider when output requires regeneration. | D, P, M | Replacement recovery completes the exact saved revision/retirement plan. Comprehensive replay remains deferred. | Distinguish forward completion from new interpretation. Measure recovery needs before automation. |
| G10 | Recipes are creation seeds rather than historical property snapshots. | D, P, M | Native creation/reference and captured retries work. Unexpected reasoning-input loss does not authorize reconstruction from an old recipe alone. | Retain/recreate required borrowed endpoints without restoring stale intent. |
| G11 | Retrieval needs explicit domain rules. | D, P, R | The fixture reader interprets document-scoped contributions. Public corpus traversal/delivery remains incomplete. | Define measurement conditions, units and eligibility after updates. |
| G12 | One interpretation contract should govern object, context and answer rendering. | D, M, R | Selected identity delivery design. | Choose domain-specific meanings. Do not copy identity states without analysis. |
| G13 | Deduplicate repeated artifacts while retaining distinct statements/evidence. | P, M, R | Source inspection covers native ID/evidence helpers. Grouped presentation remains a selected design. | Preserve distinct experimental runs even when their values match. |
| G14 | Guarantees apply to derived stores consumed by enabled paths. | P, M, R | Characterization found stale index/evidence behavior. R5 defines the boundary. | Check explicit and generic collection discovery, evidence and enabled caches. |
| G15 | Traversal and offline diagnostics should share predicates/counters. | P, M, R | Selected design. Offline diagnostics remain unimplemented. | Add domain-specific diagnostics without duplicating traversal. |
| G16 | Whole-source maintenance can provide a bounded initial policy. | D, P, M | Identity selects document-level maintenance. | Choose suitable measurement source granularity. One source per document is not universal. |
| G17 | Provenance/ownership does not establish scientific support or correctness. | D, P, M, R | Explicit scope boundary. | Address scientific justification, uncertainty and entailment in separate domain work. |
| G18 | Evaluate operation sequences and model quality separately. | D, P, M, R | Captured lifecycle tests cover withdrawal orders and interrupted retries. Model quality remains separate. | Use captured decisions for lifecycle tests. Evaluate interpretation and consumer comprehension independently. |

Source inspection of a primitive does not establish a complete integration. Record version/configuration and evidence status before describing a mechanism as demonstrated reuse.

The addition checkpoint's native assertions used a host-only launcher after ordinary Linux CLI output exposed an interpreter-teardown timeout. Application code has no forced-exit workaround. Those results do not establish clean ordinary Linux teardown.

The user separately reproduced ordinary Mac addition, reopened retrieval, healthy reconcile and `replace_published` recovery. Mac `text_chunks` failure, a later prefix edit and withdrawal after addition remain unreviewed. The session handoff records the exact evidence boundary.

## 4. Reuse boundaries in code

Prefer small shared functions after fixtures establish their behavior.

| Candidate shared boundary | Domain adapter supplies | Common mechanics supply |
|---|---|---|
| Read/guard/save description | Schema checks and domain invariants. | Expected-revision checks and atomic replacement within the saved-description storage boundary. Return changed/retired identifiers. |
| Compile publication intent | Desired objects, relationships and aggregation rules. | Explicit create/reference/retain/write actions and source-context dispatch. |
| Publish/verify attempt | Expected domain graph/index results. | Minimal plan, native references, revision/attempt guards, explicit recovery and events. Exact replay applies only where supported. |
| Select known dependents | Input identities and selection policy. | Initially scan saved input references and invalidate affected sources. |
| Reconcile selected sources | Rules for still-valid intent. | Reuse the controlled publisher without fresh semantic judgment. |
| Retrieve/render | Eligibility, direction, normalization and interpretation meaning. | Deduplicate artifacts, retain evidence references, bound work and render compactly. |

Atomic replacement in one saved-state store does not make graph, files and indexes transactional together. The table identifies reusable candidates rather than a completed generic runtime.

The first identity implementation needs no plugin registry, universal graph language, generalized dependency engine or ontology runtime. Keep explicit inputs/outputs and a small working example. Extract broader abstractions when another integration demonstrates what transfers.

## 5. The implementation loop

1. Write a small source fixture and intended structured description.
2. Include an existing corpus endpoint and one new object/relationship.
3. Publish captured decisions.
4. Inspect IDs/properties, native owners and consumed vector/evidence stores.
5. Retrieve one useful fact with original evidence and domain interpretation.
6. Evaluate consumer understanding separately.
7. Add overlap, changed input, removal and failure cases.
8. Record mismatches and the smallest required adapter or patch.
9. Turn each demonstrated sequence into a regression before generalization.
10. Add representative domain examples through the complete pipeline.
11. Improve extraction quality and efficiency afterward.
12. Update the register with implementation location, tested version/profile, limitations and remaining decisions.

The regression structure is:

| Stage | Retained observations |
|---|---|
| Initial sources and operation | Fixture and initiating command. |
| Saved result | Expected records and revisions. |
| Materialization | Graph, owners and consumed indexes. |
| Delivery | Eligibility, interpretation and evidence. |
| Injected failure | Partial state, withheld results and recovery event. |
| Explicit recovery | Valid-intent reconciliation or labeled reconsideration, with verified outcome. |

The identity contract supplies concrete scenario IDs. Copy the sequence structure for measurements while replacing the domain assertions.

### Recovery evidence before recovery automation (P, M, R)

Start with explicit recovery, a minimal durable plan and publication guards. Add complete output capture or execution-step replay only when justified.

Record source, attempt, revision, discovery time, failed stage/reason, runtime profile, selected method and verified outcome. Preserve compact event history after temporary-artifact cleanup. Link repeated observations and recovery attempts to the same incident. Distinguish injected tests from runtime failures.

The ledger determines publication eligibility. Events supply diagnostics. Include incident IDs in failure output and provide simple listing/export.

Use observed frequency, repeated causes, recovery success and detection-to-restoration time to prioritize later work. Exclude injected tests from runtime prioritization.

Caught failures currently record events immediately. Later inspection should also record abandoned pending attempts after hard crashes. That broader recovery remains incomplete. An abandoned writer reservation can still block progress. The initial design requires no background service.

### Future size and overhead evaluation (D, P, M, R)

Plan a lightweight report for subsequent integrations. Measure:

- Serialized UTF-8 bytes and record counts by source/section.
- Shared-input and producer-reference reuse.
- Graph objects, relationships and contributions per relationship.
- Minimal-plan and retained failure-artifact counts/bytes.
- Semantic-capture sizes only when that feature exists.

Report totals, per-source distributions and growth relative to source size or domain occurrence count. Reuse the planned retrieval annotation/evidence token study where applicable. Domain-specific counts vary. Bytes, sharing and retained recovery overhead remain common measures.

This is future evaluation work rather than an initial runtime requirement. Begin with report/export. Use measured costs to assess grouping, sharing, cleanup and later budgets. The proposal adds no monitoring framework, permanent capture archive or automatic compaction.

## 6. Measurements as the next worked example

A measurement source can describe an overlay linked to existing corpus objects. A custom publisher can reference exact instrument, sample and facility UUIDs. Maintain can coordinate source changes. Retrieve can apply measurement-specific interpretation.

Resolve these domain questions before implementation:

1. What identifies a measurement: acquisition event, source statement, result, processed estimate, or a combination?
2. How do value, unit, quantity, uncertainty, time and conditions relate?
3. Which distinctions require nodes rather than properties?
4. Does calibration change the original observation, create a revised estimate, or change interpretation?
5. Which versions remain directly retrievable?
6. When are records duplicate extractions rather than distinct equal-valued observations?
7. Which references are semantic relationships and which are operational dependencies?

A citation alone does not establish scientific support. Reuse ownership, controlled publication and tests only where demonstrated. Stage 8 selects measurement schemas and retrieval rules. Formal ontology remains a Stage-7 investigation rather than a prerequisite from this playbook.

## 7. How the next integration should become faster

Begin with the checklist and known native interfaces instead of repeating the entire writer investigation. Identify domain differences. Run the smallest overlap, update, removal and retry fixtures. Reuse verified mechanics.

Record a short compatibility delta when changing Cognee, backend or runtime profile. At the post-Stage-6 checkpoint, link actual code/tests to G01–G18. Label each demonstrated, partial, rejected or untested.

The first measurement fixture must test these reusable candidates. An analogy in documentation does not establish a reusable package. This playbook selects no measurement schema, scientific reasoning model, generic runtime framework or additional project stage.

## First implementation evidence — 2026-10-17

The initial fixture uses configured native graph/vector/relational interfaces, captured decisions and local deterministic embeddings. Tests cover publication, original evidence, explicit reconciliation and recovery visibility. They provide partial evidence rather than complete lifecycle or retrieval coverage. The [first-slice guide](../docs/stage6_identity_first_slice.md) records commands and limits.

One interface finding concerns actual read results. Legacy `get_edges` returned shape/direction different from its interface annotation on the tested path. The project uses `get_edge_delete_data` and `iter_bounded_neighborhood` through common interfaces. It adds no backend-specific query.

## Multi-source lifecycle evidence — 2026-10-17

| Finding | Activities | Reusable process and identity evidence | Measurement transfer |
|---|---|---|---|
| Ownership removal and application-payload retirement differ. | P, M, R | Remove the selected contribution before native reference deletion. Test both removal orders for two sources sharing one physical edge. | Retire one contribution or qualifier without deleting another source's retained value. |
| An independently owned edge needs retained endpoints. | P, M | Original chunks explicitly retain marked mentions, including unresolved groups without facts. | Preserve evidence/measurement edges when the generated overlay ceases to own an endpoint. |
| Destructive retries need saved retirement keys and current survivor obligations. | M | Save the plan before mutation. Preserve it after failure. Account for another source legitimately retired before retry. | Retain retirement intent without demanding preservation of subsequently retired contributions. |
| Diagnostics must expose already-withheld sources. | M, R | Return failed/pending state and incident IDs. Deliberate withdrawal is inactive rather than failed. | Expose incomplete publication without using event history as another eligibility registry. |

Reuse configured `UnifiedStoreEngine` source-reference deletion and portable ledger mechanics. Keep contribution matching and marker rules in the identity adapter.

The CLI explicitly closes supported engine handles. Handle closure alone does not establish clean interpreter teardown. The addition profile's later Linux timeout and host-only-launcher qualification remain applicable to that evidence. Partial fixtures establish neither all-backend behavior nor scientific interpretation.

Measure cleanup cost as the corpus grows. The pinned source-reference deletion path can scan the graph during orphaned EdgeType cleanup. Small fixtures establish retention behavior, not corpus-scale latency or bounded internal work. Carry that measurement question forward without adding backend-specific cleanup code now.

## Revision replacement evidence — 2026-10-19

| Finding | Activities | Concrete identity process/evidence | Transfer to measurements and other integrations |
|---|---|---|---|
| Registered Data snapshots participate in coordinated publication. | P, M, R | Guard-save intended JSON. Update the same Data ID through ingest_data. Verify managed content/hashes before acknowledging currentness. | Keep saved descriptions and registered sources coherent. Do not change a managed file without updating native metadata. |
| Add, ingestion and full Update have different behavior. | P, M | Pinned high-level Add rejects changed documents. Lower-level ingestion refreshes generated Data without graph extraction, using an actual source context and explicit ID. | Select the operation by inspected behavior rather than its name. |
| New output precedes obsolete-retention cleanup under one eligibility guard. | P, M, R | The common publisher creates/references endpoints. Targeted native removal retires only obsolete contributions/declarations. | Preserve other experiments' owners and qualifiers during correction. |
| Recovery follows saved intended meaning, including retirement. | M | Previous descriptions and retirement keys survive failure. Reconcile completes revision 2 rather than restoring 1 or choosing another interpretation. | Save enough intent to retire obsolete values as well as publish replacements. |
| Attribution follows the revised record. | D, P, M | Corrected assignments receive a new producer entry. Unchanged groups retain theirs. | Preserve extraction attribution when correcting only unit interpretation, calibration links or derived relationships. |
| Local fact stability and interpretation stability need separate checks. | D, M, R | Fact UUIDs, endpoints and evidence remain local during captured retargeting. An explicit verifier checks this example. | Decide which outputs remain valid after reinterpretation and which require regeneration. |

These partial M3 results use captured decisions and the initial native profile. The reusable mechanism combines guarded intent, native ownership/index handling and verified recovery. Grouping, equivalence and document applicability remain identity-specific.

Ledger readers withhold failed/pending sources. Arbitrary native readers do not gain atomic visibility. The next checkpoint adds a bounded original-text rebuild. General edits, dependencies, full removal and generic extraction remain broader work.

## Source-text maintenance evidence — 2026-10-19

| Finding | Activities | Identity process/evidence | Transfer to measurements and other integrations |
|---|---|---|---|
| Edge ownership does not retain endpoints independently. | P, M | A custom writer omitted a second source's endpoint owner. Native removal could cascade into that source's fact. Explicit retention, refusal guards and survival checks address the gap. | Retain every required value/unit/instrument endpoint. Test removal of the first producer as well as overlay withdrawal. |
| Coordinates belong to an exact source version. | D, P, M, R | A Unicode prefix shifts occurrences by 48 characters. Native chunk ID/hash, markers and evidence change while reviewed local identities continue. | Rebuild spans, table references and evidence after edits. A retained record ID does not validate old coordinates. |
| A saved transition supports bounded forward recovery. | P, M, R | Save intent and exact old/new text before memory-only Forget. Retry repeats native rebuilding and verifies current output. | Retain sufficient input/construction intent before introducing stepwise replay or A/B stores. |
| Position remapping differs from semantic reconsideration. | D, M | Captured review supplies unchanged interpretation. Code checks ranges and publication. Preflight refuses dependent-source changes pending reconsideration support. | A shifted span may remain mechanically mappable while changed methods, calibration or qualifiers need judgment. |
| Complete-source rebuild is an initial policy with measurable costs. | P, M | Edits and caught-failure retries rebuild one original document. The current plan retains old/new text. | Measure scans, plan size and extraction cost before incremental reuse, compression or shared capture. |
| Current evidence requires materialization checks. | M, R | Tests verify cleanup/recapture. Delivery also checks the current chunk map and native fact owner. | A surviving evidence row does not establish attribution to the active source revision. |

These native-interface results use captured decisions. They do not turn prefix mapping into Describe, establish scientific support or implement automatic dependent-source propagation.

Reuse the four activity boundaries, endpoint checklist and sequence tests. Supply domain-specific meaning and reconsideration rules. Size reports, generic multi-chunk extraction and arbitrary-change selection remain later work. The following checkpoint demonstrates selected multi-chunk materialization rather than a generic extractor.

## Multi-chunk maintenance evidence — 2026-10-19

| Finding | Activities | Identity process/evidence | Transfer to measurements and other overlays |
|---|---|---|---|
| Marker locations and fact provenance can use different chunks. | D, P, M, R | One edited group uses three marker chunks. A fact uses two producing/evidence chunks, including an unmarked continuation. Tests check presence and required absence. | Preserve units/qualifiers beyond a reference chunk. Do not treat every context chunk as evidence. |
| Content identity does not establish current position/index. | D, M, R | Content-derived chunk IDs can recur after edits while ranges/indexes move. The writer recaptures evidence against current `(chunk_id, chunk_index)`. | Separate versioned location/table mappings from stable value or content IDs. |
| Rebuild policy must survive destructive writes. | P, M | Reconcile reads native max_chunk_tokens. The saved transition retains the budget when chunks are absent. Reconcile refuses missing/inconsistent metadata. | Save parser/segmentation settings before removal. Do not silently use a default policy during recovery. |
| Retrieval must retain complete admitted evidence fragments. | P, M, R | Marker-only filtering would truncate a fact. Delivery retains checked continuation evidence after finding occurrence-overlapping evidence. | Return needed units/qualifiers rather than truncating interpretation at marker boundaries. |

Captured fact spans and reviewed decisions establish these findings. They do not solve automatic span selection, semantic reconsideration, generic extraction or scientific justification. Reuse the mechanics and tests while retaining domain-specific extraction in the adapter.

## Reviewed occurrence removal — 2026-10-19

| Finding | Activities | Identity process/evidence | Transfer to measurements and other overlays |
|---|---|---|---|
| Continuing identity and continuing positions require separate decisions. | D, M, R | A survivor manifest maps previous indices to exact new spans. g01 retains its UUID/binding after one reference disappears. Slice checks do not establish semantic continuity. | Retain a logical ID across moved text/rows only under an explicit domain continuity decision. |
| Empty records require explicit retirement. | D, P, M | g02 loses its group, resolution and declaration. Native removal and generated-retention cleanup delete unowned nodes/vectors/markers. Tests require absence. | Retire removed observations' declarations/materialization while preserving other owners. |
| Net text-length change is not a remapping policy. | D, M, R | The manifest supplies every continuing span. Diagnostics expose `position_shift: null` and separate `text_length_delta`. | Do not apply one inferred offset to all rows or sections after deletion. |
| Recovery needs transition input as well as output. | P, M | The plan retains occurrence retention, old/new text, previous description and chunk budget. Explicit retry completes the same revision. | Save continuity and retirement inputs before deletion. Do not infer them from missing graph state. |

This example uses captured decisions and one surviving fact. It establishes neither general matching nor arbitrary-edit interpretation or scientific justification. Measurement adapters can reuse guarded replacement, rebuilding and recovery while defining their own continuity and retirement rules.

## Retirement of a fact-bearing group — 2026-10-19

| Finding | Activities | Identity process/evidence | Transfer to measurements and other overlays |
|---|---|---|---|
| Empty retrieval does not prove physical cleanup. | P, M, R | Verify absence of g01's node/vector, resolution, local fact, old evidence and markers. Failed-publication withholding is a separate ledger behavior. | Verify obsolete materialization/evidence removal rather than hiding it in one query. |
| Index lifetime follows the index key's sharing granularity. | P, M, R | Doc01's edge disappears while doc02 retains the shared relationship-text entry and endpoint vector. Optional per-edge Triplet entries use different keys. | Preserve shared units, predicates and vocabulary vectors. Check actual index keys and cleanup rules. |
| Explicit retirement differs from missing required output. | D, P, M | Current intent omits g01/r01 and its construction declaration. Healthy reconcile does not recreate them from history or baseline files. | Do not recreate retired observations from obsolete recipes or recovery snapshots. |
| Empty semantic output still requires valid intent and inputs. | D, P, M | The revised text lacks the captured fact span. Chunk-map and survivor verification still run without primary semantic output. | Distinguish valid empty replacement from skipped processing or invalid input. |

This case reuses guarded whole-document rebuilding and explicit forward recovery. It does not establish extraction accuracy, scientific support, populated-Triplet deletion or every foreign-owner case on the same triple. Reuse ownership/index-key checks and assertions of both presence and absence.

## Reviewed occurrence additions — 2026-10-20

| Finding | Activities | Identity process/evidence | Transfer to measurements and other overlays |
|---|---|---|---|
| Continuity maps retained records while new records require declarations. | D, P, M | A separate old-to-new index map preserves groups. Intended JSON declares additions. Validation rejects implicit retirement/retargeting. | Preserve existing observation IDs explicitly when inserting rows/readings. Equal values or nearby offsets do not establish continuity. |
| Equal display text does not establish local identity. | D, P, M, R | A continuing group's new reference and a fresh group both say `the controller`. They use distinct UUIDs and exact spans. | Separate equal labels/values from observation identity. |
| New objects require semantic output and provenance checks. | D, P, M, R | The new group declares a binding and a separate local fact from original text. Existing writers/publishers materialize that output. | Declaring a measurement does not generate value/unit/qualifier relationships. Specify conversion and producing-source ownership. |
| Recovery must reuse newly allocated IDs. | P, M | The saved description and continuity map preserve the new group UUID through interruption and forward completion. | Persist new IDs before writes. Retry the same observation rather than allocating a duplicate. |

This bounded addition uses the common guarded whole-document rebuild. Lifecycle tests verify materialization. Paragraph grouping, reference selection and identity judgment remain adapter inputs. This case adds no generic framework or scientific-support rule.

The [addition guide](../docs/stage6_identity_occurrence_addition.md) and [session handoff](../docs/SESSION_HANDOFF.md) record execution evidence and remaining scope. The launcher and Mac-verification qualifications stated above apply. They do not establish untested recovery paths or clean ordinary Linux teardown.
