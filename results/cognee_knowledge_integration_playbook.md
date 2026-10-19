# Building a source-backed knowledge integration in Cognee

### Separate the test profile from implementation dependencies

The initial Ladybug/LanceDB/SQLite combination is a tested configuration, not a requirement to generate backend-specific integration code. Use Cognee's configured graph/vector factories and interface methods and its configured relational engine/session layer. Keep project ledger/event models and operations backend-neutral; no direct SQLite database, adapter-client calls, backend-specific queries, file-layout dependencies or backend-name branches in domain logic. Missing provenance/index/serialization/concurrency capabilities are explicit compatibility gaps, not reasons to bypass the abstraction. A shared interface does not prove every adapter implements the required behavior; qualify demonstrated compatibility by the actually tested configuration. Carry this boundary into subsequent integrations.

**Consolidated:** 2026-10-15 (America/Detroit).  
**Baseline examined:** Cognee 1.6.2, commit `ba3631f2ed363a6ea50d649c34c56885af6b36fe`; the lab uses Ladybug/LanceDB/SQLite.  
**Status:** reusable design process and implementation checklist, derived from the identity investigation. The new identity workflow is not yet implemented end to end. Measurement examples below are illustrative, not a selected scientific schema.

## 1. What carries over to the next integration

A useful integration consists of an explicit saved knowledge description, a graph projection linked to the existing corpus, source-bound lifecycle procedures, and retrieval that interprets the projection correctly. An overlay is a logical collection of structures and rules; it need not be a separate database, a new node for every record, or a new node class for every concept.

Keep four activities together:

| Activity | Reusable responsibility | Identity example | Possible measurement example |
|---|---|---|---|
| Describe | Interpret inputs, find corpus matches and save explicit creation/link intent | Occurrence groups, existing Entity UUIDs, variant/mention assignments | A value with quantity, unit, conditions and links to an existing instrument/sample/facility |
| Publish | Materialize supplied intent through validated, source-bound writes | New explicit-ID Entities, original-chunk markers, resolution contributions | Measurement structures and declared relationships to existing corpus objects |
| Maintain | Handle changed inputs, retirement, shared ownership, replay and consumed stores | Update source-specific assignments and rebuild valid materialization | Replace/retract/reinterpret records after source or calibration changes under a selected policy |
| Retrieve | Select eligible structures and expose their meaning and evidence | Scoped identity traversal, original facts and local binding annotations | Select measurements under requested quantity/condition/unit rules and preserve source attribution |

Domain interpretation belongs in the domain adapter. Native persistence behavior, ownership attachment and failure coordination are separate concerns. A common lifecycle does not make identity equivalence rules appropriate for measurements.

## 2. The reusable package to produce each time

Copy this checklist and complete it for the new knowledge type. Reuse existing native investigations where the version/backend/profile match; probe the differences.

| Deliverable | Questions to answer | Completion evidence |
|---|---|---|
| Meaning and invariants | What do the records/edges mean? Which combinations are valid? | Domain rules and counterexamples, separately from wire field names |
| Saved-description contract | Which facts/decisions are authoritative? Which exact existing objects are referenced? | Versioned schema, one valid example and rejected invalid examples |
| Publication/ownership matrix | Who creates, retains, rewrites and deletes every object/edge? | Actual native refs and properties checked in a small fixture |
| Input/continuity policy | What identifies an occurrence/record across source edits? Which supplied inputs can invalidate it? | Same-input replay and source-edit examples |
| Operation contract | What happens on add, overlap, update, source removal, rebuild and retry? | Before/after sequence matrix with partial-failure expectations |
| Consumed-store manifest | Which graph/vector/evidence/session stores are really queried? | Runtime configuration and returned-ID/content checks |
| Retrieval contract | How are candidates interpreted, limited, ranked and rendered? | Correct, ambiguous, unavailable, empty and limited cases |
| Model boundary | Which steps are code, lookup/scoring or semantic judgment? | Replaceable model/rule adapters and deterministic orchestration fixtures |
| Diagnostic contract | What structural failures/cost limits can be detected without semantic judgment? | Shared checks/counters and explicit scan coverage |
| Reuse report | Which mechanisms worked, where, and with which limits? | Implementation/source reference plus passing test or explicit untested label |

The current worked handoff is [cognee_identity_stage6_handoff.md](cognee_identity_stage6_handoff.md), with a draft JSON schema and example. Reuse the structure, not the identity-specific field list.

## 3. Lessons register with activity and transfer checks

**D:** Describe; **P:** Publish; **M:** Maintain; **R:** Retrieve. The architecture reference's section 18 remains the detailed evidence register. The following is the consolidated checklist for reuse.

| ID | General lesson/process | Activities | Current basis | What the next integration must verify |
|---|---|---|---|---|
| G01 | Explicit IDs and continuity rules are separate from display names and current offsets | D, P, M, R | Explicit-ID precedence is source-inspected; grouped continuity is selected design | Define identity for repeated equal-valued measurements and source revisions |
| G02 | Reference, retention and ordinary property persistence are different actions | D, P, M | Recursive overwrite/co-ownership observed; native ref attachment inspected | Link existing instrument/facility nodes without rewriting them |
| G03 | A saved description specifies exact graph intent; Publish executes declared rules | D, P, M | Selected design; custom Task/persistence seams inspected | Define edges/endpoints/aggregation explicitly instead of asking Publish to infer meaning |
| G04 | Native source ownership retains objects but does not aggregate application properties | D, P, M, R | Shared retention observed; upsert replacement inspected | Decide whether native shared-edge semantics suffice for values/qualifiers |
| G05 | Original evidence, generated-source ownership and producer attribution are distinct | D, P, M, R | Native mechanics inspected; combined identity path untested | State the original measurement evidence and ownership for generated structures separately |
| G06 | A generated registered Data item does not automatically follow its original input's lifecycle | D, P, M | Original/generated separation inspected | Map original inputs to generated measurement sources and retire/refresh them explicitly |
| G07 | Actual supplied context and selection changes define operational dependencies | D, M, R | Selected dependency/locator policy | Capture calibration, unit definitions and corpus context actually supplied; handle newly inserted context |
| G08 | Saved meaning and graph materialization have separate failure points | P, M, R | Selected ledger/minimal change-plan protocol; full replay deferred | Reuse publication guards; diagnostic recovery events must not become a parallel currentness registry |
| G09 | Reconcile valid saved intent; explicitly reconsider when regeneration is required | D, P, M | Initial explicit recovery; comprehensive captured replay deferred | Distinguish restoring a projection from regenerating uncaptured interpretation; measure actual recovery needs before adding automation |
| G10 | Rebuild recipes are minimal creation seeds, not historical property snapshots | D, P, M | Exact-ID creation/ref semantics inspected; combined replay untested | Ensure required borrowed endpoints can be retained/recreated without stale resurrection |
| G11 | Retrieval consumes domain rules; native graph search does not acquire them automatically | D, P, R | Earlier identity retrieval demonstrated; new traversal unimplemented | Define measurement-specific conditions, units and update eligibility |
| G12 | One interpretation annotation should drive object, context and answer rendering | D, M, R | Selected identity delivery policy | Reuse the mechanism where helpful; choose measurement-specific meanings rather than copying identity states blindly |
| G13 | Deduplicate repeated artifacts; preserve distinct statements/evidence unless equivalence is explicitly defined | P, M, R | Native ID/evidence helpers inspected; grouped presentation selected | Do not collapse distinct experimental runs merely because their values match |
| G14 | Only actually consumed derived stores need integration guarantees | P, M, R | Stale index/evidence behavior characterized; R5 | Check explicit and generic vector collection discovery, source evidence and enabled caches |
| G15 | Bounded traversal and offline diagnostics should share predicates and counters | P, M, R | Selected design, unimplemented | Add measurement-specific structural/cost diagnostics without a second traversal implementation |
| G16 | Compact whole-source maintenance is a useful initial boundary | D, P, M | Selected identity document-level maintenance | Choose measurement source granularity; do not assume one source per document is universal |
| G17 | Provenance/ownership does not establish scientific support or correctness | D, P, M, R | Explicit scope boundary | Scientific justification/uncertainty/entailment need their own domain work |
| G18 | Test operation sequences and model quality separately | D, P, M, R | Existing characterization plus planned integration suites | Use captured decisions for lifecycle assertions; independently evaluate interpretation quality and consumer comprehension |

These are mechanisms and questions to reuse. A source-inspected primitive is not evidence that the new combined pipeline works. Record backend/configuration and evidence status when upgrading a row to demonstrated reuse.

## 4. Reuse boundaries in code

Prefer small shared functions/adapters once the identity fixture demonstrates them:

| Candidate shared boundary | Domain adapter supplies | Common mechanics supply |
|---|---|---|
| Read/guard/save description | Record/schema validation and domain invariants | Expected-revision check, atomic local replacement, changed/retired identifiers |
| Compile publication intent | Exact desired objects/relationships and domain aggregation rules | Explicit create/reference/retain/write actions and source-context dispatch |
| Publish/verify attempt | Expected domain graph/index outcomes | Minimal change plan, native ref APIs, revision/attempt guards, explicit recovery and diagnostic event records; exact replay only when supported |
| Select known dependents | Domain input identifiers/selection policy | Initially scan saved input references and invalidate affected sources |
| Reconcile selected sources | What still-valid intent means | Reuse the controlled publisher; no new semantic model call |
| Retrieve/render | Eligibility, direction, normalization and interpretation meanings | Artifact deduplication, evidence references, bounded work and compact rendering support |

Do not require a plugin registry, universal graph-description language, generalized dependency engine or new ontology runtime for the first identity implementation. Preserve clean inputs/outputs and a small working example. Extract a broader abstraction when a second integration shows which assumptions actually transfer.

## 5. The implementation loop

1. Write one tiny source fixture and its intended structured description. Include an existing corpus endpoint and one new object/relationship.
2. Publish with captured decisions. Inspect graph IDs/properties, native source ownership and the consumed vector/evidence stores.
3. Retrieve one useful fact with its original evidence and domain interpretation. Check the receiving model's meaning separately.
4. Add overlap, changed input, source removal and failed publication to the same fixture.
5. Record the native mismatch and the smallest adapter/patch needed. Turn the sequence into a regression case before generalizing it.
6. Add representative domain examples through the full pipeline, then improve extraction quality and efficiency.
7. Update this checklist/register with implementation location, tested version/profile, limitations and remaining domain-specific decisions.

The reusable regression skeleton is: initial sources -> operation -> expected saved records -> expected graph/owners -> consumed-index checks -> retrieval eligibility/output -> injected failure -> unavailable partial result/recovery event -> explicit valid-intent reconciliation or labeled reconsideration. The identity handoff supplies concrete case IDs. This sequence can be copied for measurements with different domain assertions.

### Recovery evidence before recovery automation (P, M, R)

Start with explicit recovery, a minimal durable change plan and publication guards; add complete output capture or stepwise replay only when justified. Record recovery-required incidents with source/attempt/revision, discovery time, failed stage/reason, runtime profile, selected recovery method and verified outcome. Preserve a compact event history after temporary artifacts are cleaned. Link repeated observations/recovery attempts rather than counting every restart as a new incident; distinguish injected test cases from runtime failures. The event history is diagnostic, while the ledger remains the publication-eligibility authority. Surface event IDs in failures and provide a small listing/export. Use frequency, repeated causes, method success and detection-to-restoration time to prioritize later recovery work. Abrupt crashes are recorded when pending state is next inspected; no background service is a prerequisite.

### Future size and overhead evaluation (D, P, M, R)

Carry a lightweight programmatic size report into subsequent integrations. Measure serialized UTF-8 bytes and record counts by source/section, shared-input and producer reference reuse, materialized graph objects/relationships and contributions per relationship, and retained minimal-plan/failure-artifact bytes/counts (semantic-capture sizes only when implemented). Report totals plus per-source distributions and growth relative to source size or domain occurrence count. Reuse existing retrieval annotation/evidence token measurements where applicable. Domain-specific counts will differ for measurements and identity; serialized bytes, sharing and retained capture overhead are common concerns.

This is a future measurement need, not another initial runtime requirement. Start with a report/export rather than a monitoring framework; use observed costs to justify grouping, sharing, cleanup or later budgets. No permanent capture archive or automatic compaction is implied.

## 6. Measurements as the next worked example

The proposed measurement-source -> graph-overlay -> existing-corpus-links structure is a strong candidate. A structured registered source can carry a measurement description; a custom publisher can link exact instrument/sample/facility UUIDs; maintenance can coordinate source changes; retrieval can interpret the selected representation.

Before implementing it, answer the domain questions that identity cannot settle:

- What identifies a measurement: acquisition event, source statement, result, processed estimate or some combination?
- How do value, unit, quantity, uncertainty, time and experimental conditions relate? Which distinctions need graph nodes versus properties?
- Does a calibration change alter an original observation, create a revised estimate, or change only interpretation? What remains directly retrievable?
- When are two records duplicate extractions versus distinct observations with equal values?
- Which references are semantic links and which are operational dependencies? Source citation alone is not proof of scientific support.

Reuse the ownership/ref attachment, saved-intent publication and test process where validated. Choose measurement-specific schemas and retrieval rules during Stage 8. A formal ontology is a Stage-7 investigation, not a prerequisite imposed by this playbook.

## 7. How the next integration should become faster

Start from the artifact checklist and known pinned native seams instead of repeating the full Cognee writer investigation. Fill in the domain differences, run the smallest overlap/update/remove/retry fixture, and reuse the verified mechanics. Keep a short compatibility delta when changing Cognee/backend/profile.

At the post-Stage-6 checkpoint, attach actual identity code/tests to G01–G18 and mark each as demonstrated, partial, rejected or still untested. The first measurement fixture then tests those reusable candidates rather than assuming them. This is the evidence for a reusable package; a documentation analogy alone is insufficient.

No measurement schema, scientific reasoning model, generic runtime framework or additional project stage is selected by this consolidation.

## First implementation evidence — 2026-10-17

The first identity fixture uses configured native graph/vector/relational interfaces, captured decisions and local deterministic embeddings. Its focused/native tests exercise publication, original-source evidence, explicit reconciliation and recovery visibility. This is partial evidence for the reusable lessons rather than completion of all lifecycle/retrieval requirements. See ../docs/stage6_identity_first_slice.md for commands and limits.

A concrete interface lesson: verify actual read shapes/direction as well as method availability. The legacy get_edges result differed from its interface annotation on the tested path. The integration uses get_edge_delete_data and iter_bounded_neighborhood through the common interfaces, without backend-specific queries.
