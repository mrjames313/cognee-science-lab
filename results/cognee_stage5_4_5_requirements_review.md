# Stage 5.4.5 — Requirements after scope audit

**Status reconciled:** 2026-10-20 (America/Detroit); outcome requirements unchanged from the reviewed scope.
**Project:** cognee-science-lab  
**Baseline:** Cognee 1.6.2, Ladybug/LanceDB/SQLite, access control disabled, shared physical graph.  
**Status:** Six outcome requirements retained. Architecture review is complete and draft runtime forms plus bounded Stage-6 publication/maintenance/retrieval fixtures exist. These do not establish complete R1–R6 coverage. [SESSION_HANDOFF.md](../docs/SESSION_HANDOFF.md) records current implementation and verification status; this document defines outcomes.

## What this document requires

The target is the lab's identity-processing extension: ingest source text, retain observations, resolve names and mentions, retrieve semantic relationships through the resulting identities, and keep those records usable after source changes.

The initial implementation target is standard text Cognify/Remember, overlapping ingest, project maintenance, project-model full-rebuild Update, source/dataset Forget, and the custom identity-aware retrieval path. These are target workflows, not a claim that every native entry point is integrated; bounded custom-Task fixtures already exist. Native incremental Update is a characterized diagnostic path; enabling it for the project requires demonstrating the same outcomes as the supported update workflow.

The requirements apply to those workflows in the pinned lab configuration. They do not promise compatibility with all Cognee operations, optional stages, migrations, backends, or access-control configurations. Adding another workflow requires checking the records and outputs it can affect, not specifying every possible mutation in the SDK.

The detailed measured/source-inspected findings remain in **cognee_stage5_4_5_1_initial_findings.md**. Findings describe existing behavior; the requirements below describe the behavior the lab extension needs.

## Concrete terms

| Term | Meaning in this document |
|---|---|
| Identity record | Saved observations/assignments, original-input provenance, mention classification and applicability, and materialized identity relationships. Prototype class names do not prescribe the durable form. The initial representation uses structured generated identity sources, mention marker edges and contribution-bearing resolves_to edges. |
| Resolution record | A saved assignment identifying exact Entity endpoints, variant versus mention relationship kind, applicability and original-input provenance. A mention resolves to a singleton or member of an identity group; no privileged canonical Entity is required. |
| Source locator | The Data item that supplied the text and, where necessary, its DocumentChunk and occurrence coordinates. A graph TextDocument ID and the relational Data ID are distinct identifiers. |
| Contributor | A source observation or other retained input actually used to produce a resolution record or a materialized resolves_to relationship. This is an operational dependency, not a judgment of scientific support. |
| Active representation | A vector collection, backend edge-evidence store, or other derived representation consumed by an enabled lab retrieval/provenance path. A collection is not inactive merely because its dedicated SearchType is unused: generic collection discovery must also be checked. |
| Identity maintenance | The lab Tasks that create, replace or remove assignments, generated identity sources, mention markers and materialized identity links from retained inputs, including recomputation of shared edge contributions. |
| Singleton / identity group / variant | A singleton is an ordinary Entity outside an applicable variant group, excluding marked mentions. An identity group consists of variants connected by applicable equivalence relationships; no member is privileged. A mention is an occurrence-specific Entity with explicit stored classification. |
| Current record | A record eligible for use by the resolver after the latest completed maintenance for its source inputs. It is not a claim that its interpretation is scientifically correct. |

The phrase **project decision** is removed. It previously referred to stored resolution results, not a general category of application, scientific, or architectural decisions.

## R1 — Preserve identity records during supported writes

Native semantic-node upserts in the supported workflows must not erase the authoritative mention classification, identity assignments, applicability or resolution data the lab resolver uses. These values must either survive those writes or be regenerated from retained inputs before the resolver uses them again.

Identity maintenance must leave the original semantic Entity nodes available; it must not physically merge or delete them merely because they resolve to the same identity.

A maintenance writer must identify the records and relationships it is replacing. It must leave unrelated identity records and relationships unchanged. An absent relationship in an incoming DataPoint must not be treated as removed unless the writer explicitly removes it.

**Why needed:** overlapping Cognify overwrote Entity annotations; same-ID full upsert removed patch-only fields while retaining existing relationships. Separate node types and ownership refs did not establish general protection.

**Acceptance check:** with captured extraction inputs fixed, re-Cognify an overlapping source and rerun maintenance. The intended identity records remain or are reconstructed; unrelated identity records remain unchanged; original Entity IDs remain; the intended identity relationship set has no leftover replaced edges or duplicate additions.

**Initial architecture choice:** authoritative state is saved independently in generated identity sources; graph publication uses mention markers and contribution-bearing identity edges without added authoritative Entity fields. R1 specifies preservation/reconstruction outcomes, not a mandate for those particular physical forms. See [the proposal](cognee_stage5_4_5_identity_representation_proposal.md).

## R2 — Tie source-dependent identity records to their actual inputs

A source-dependent identity record must identify the Data item and text-bearing locator used to produce it. The writer must reject missing or inconsistent required source identifiers. Chunk-local observations must identify their chunk; document-derived summaries or resolutions may identify the document rather than an arbitrary chunk.

Where native Forget is relied on to remove a record, its writer must attach the required native source references and check that the expected node and relationship references were persisted. A scalar source_document_id, dataset label, or producing run ID alone is insufficient. If another representation is chosen, the lab must retain an explicit source-to-record mapping and perform the equivalent cleanup required by R4.

Writing a new record that references an existing Entity or identity record must not inadvertently rewrite that referenced object's properties or add source owners to it. The writer must distinguish reference-only use, intentional retention-owner attachment and object persistence. The selected proposal intentionally attaches the generated source's node ownership to required existing endpoints without rewriting their ordinary properties. Producing-run attribution is retained where the persistence path provides it; a run ID is not a source owner.

Source-dependent locators must either identify a checked content revision/fingerprint or be invalidated and regenerated when that source changes. Stable Data or node IDs alone do not exempt a record from that handling. No archive of every source revision is required.

**Why needed:** injected dataset/run context with raw input produced unowned fixtures. Binding the real Data item attached ownership. Nested persistence rewrote and co-owned previously existing objects. Update retained Data IDs and sometimes recreated prior chunk IDs.

**Acceptance check:** persist a source-bound observation and resolution, then inspect the actual stored source IDs/refs. Reference an existing Entity without changing its properties or unintentionally changing its owner set; separately verify that deliberate retention attachment adds only the expected native refs. Missing anchors fail rather than creating a silently untracked source record. Update the same Data item and verify prior-content locators are not reused without regeneration or validation.

## R3 — Apply identity mappings to the right query context

The resolver must distinguish reusable singleton/variant names from occurrence-specific mention strings. Mention classification must remain explicit when a mention has no usable resolution, so it cannot be treated as a singleton merely because its resolution edge is absent. A resolved historical mention must not become a reusable alias solely because that occurrence was resolved.

A document-, chunk-, or occurrence-local mapping may be used only with matching query context. A query without enough context to select one Entity must return ambiguous or unresolved rather than activate all historical targets for the same surface string. Resolution must precede identity-based semantic-neighborhood expansion. Applicable variant links establish bidirectional equivalence; mention links are scoped references and must not act as equivalence bridges or unrestricted reverse expansion paths.

The lab's normal semantic output must exclude helper records and must not present resolves_to or has_identity_mention links as subject-matter facts. It must retain the original relationship/endpoint identifiers needed to recover source attribution when facts are combined or deduplicated. Explanation output may expose the helper records separately.

A local interpretation may select a shared Entity for a wider corpus search. The mapping's applicability does not require dataset-confined retrieval afterward.

**Why needed:** these are existing Stage-5.3 behavior goals, supported by the query-resolution and end-to-end recall demonstrations. They are not deductions from the two-document isolation test.

**Acceptance check:** exercise a reusable abbreviation, a context-resolved generic mention, an ambiguous mention, and conflicting local meanings. Verify target IDs and statuses, no semantic expansion on unresolved/ambiguous results, and exclusion of helper/identity-only relationships from semantic output. Verify the same locally resolved Entity can be used in explicitly corpus-wide recall.

**Initial architecture choice:** mention markers retain original occurrence context; resolution edges carry an explicit kind and current contributions. An edge is applicable when at least one current contribution matches context. Exact serialization, resolver scoring, conflict handling and explanation formatting remain open; no general scope hierarchy is required before defining the implemented cases.

## R4 — Reconcile identity records after source Update or Forget

For each supported source Update or Forget, the lab must find affected identity records using their source locators and contributor mappings. This includes stored IDs pointing to removed/replaced objects and identity relationships lost when an endpoint is deleted. In the selected proposal, the generated identity Data items' dependency on their original sources must be tracked explicitly: native Forget of the original does not automatically retire those generated items.

After Update, required extraction and identity-maintenance Tasks must run for the changed source inputs. The initial project path may use full rebuild followed by maintenance. If native incremental Update bypasses those Tasks, it cannot substitute for that path without equivalent project processing.

After Forget, remove source-local records for the retired source. Recompute shared resolution records and generated identity links from their remaining contributors, or mark/remove them so the resolver cannot use them as current. Retain a shared generated link only when the remaining inputs reproduce it; retire it when no contributors remain. Native owner retention alone does not recompute a shared edge's applicability/property collection. Do not delete semantic endpoints that native ownership still retains for other sources.

If maintenance fails, the affected identity records must be unavailable to the resolver until a successful rerun. The workflow must report source reconstruction and identity-maintenance completion separately. Retrying maintenance on the same captured inputs must not add duplicate records or relationships. Equality of fresh LLM outputs across runs is not required.

**Why needed:** both Update routes left stale helper references; source Forget retained all unowned helpers and detached some links. Native owner removal did not restore old property values or recompute identity records.

**Acceptance check:** run the captured DOC01-only, DOC01+DOC02, changed-DOC01 and removed-DOC01 cases. Confirm source-local cleanup, correct shared retention/recomputation, no usable dangling locators, and no duplicate derived records on replay. Interrupt maintenance and confirm affected records are unavailable; rerun to restore usable records.

**Scope limit:** explicit contributor mappings for these identity structures are required. A general dependency engine for arbitrary future artifact classes, automatic value rollback, and immutable graph history are not required.

## R5 — Keep consumed indexes and backend references consistent

For each active representation, the enabled lab path must identify the objects/fields it expects to consume. After a supported write or source change, that representation must cover the intended current objects, reflect changed indexed content, and exclude retired objects and relationships.

Cleanup must account for relationships removed indirectly by endpoint deletion, not just those directly selected by source ownership. Backend edge-evidence rows, when used for provenance or retrieval, must resolve to the intended current source/chunk/edge, or be unavailable to that current lookup.

Completion must be checked against the intended records and their referenced objects. A successful Improve call, native watermark, collection existence, or row count alone cannot establish this result. If repair is incomplete, the affected retrieval path must exclude the records or remain unavailable.

**Why needed:** source deletion left orphan Triplet rows; incremental Update retained stale chunk/edge-evidence refs; Improve missed the incremental run and left missing Triplets. These findings show why consumed stores need checks, not why every store must always be repaired.

**Acceptance check:** for each enabled representation, change indexed text at the same object ID, remove a relationship by endpoint deletion, and add a relationship. Verify refreshed content, no retired record returned, and expected new coverage. For an enabled evidence lookup, replace its source chunk and verify retired refs are excluded.

**Scope limit:** Triplet_text repair is required if an admitted path consumes it. It is not a prerequisite merely because diagnostic Improve created the collection. Leaving it unused requires confirming that enabled retrievers, including generic collection discovery, do not query it. The same condition applies to backend evidence features. R5 does not require fixing Cognee's global watermark implementation if explicit lab refresh/checks achieve the result.

## R6 — Prevent reuse of stale cached answers when session reuse is enabled

If the lab enables answer reuse across source changes, a reusable QA must retain the used-object/source information needed to invalidate it. Requested dataset attribution alone is insufficient when its answer used other datasets' objects.

After an Update or Forget, cached answers that used affected inputs and their searchable session representations must be invalidated or excluded from reuse. If fine-grained invalidation is unavailable, clearing the relevant cache or disabling reuse for those workflows is sufficient.

Any enabled feedback-application stage must be treated as a writer under R1–R5. Merely storing a rating or feedback text must not be reported as applying graph weights or preferences.

**Why needed:** generated answers created a separate QA/vector store; session-only Recall reused it. Dataset deletion cleared seeded attributed QA/vector records but retained history and registry rows. QA attribution named DOC01 although used IDs included DOC02.

**Acceptance check:** cache an answer, change/remove a contributing source, and verify that session recall cannot return it as current. Check QA/vector invalidation separately from history/registry retention. With feedback application disabled, verify storing a rating does not report a graph-weight update.

**Scope limit:** this requirement is conditional on session reuse/feedback application. Long-term audit retention, comprehensive conversation dependency chains, usage/cost accounting, and retention rules for every bookkeeping table are outside the current implementation requirements.

## Audit of the previous ten items

| Previous item | Disposition | What is actually retained |
|---|---|---|
| 1. Mutation authority/preservation | Narrowed into R1 | Preserve the named identity data in the selected workflows; no policy for every persistent field. |
| 2. Universal operation/mutation contracts | R1/R4 behavior retained; inventory stays in findings | Explicit replacement/removal of identity relationships and indirect deletion effects; no exhaustive SDK admission framework. |
| 3. Source anchoring | Retained as R2 | Real source locators, verified cleanup bindings, and reference-versus-write semantics. |
| 4. Ownership/applicability/version identity | Split into R2–R4 | Current text binding, resolver eligibility and shared contributor removal; no generalized version archive or applicability hierarchy. |
| 5. Selection/index eligibility | R3/R5 | The custom resolver's output and the stores its enabled paths consume; no layer policy for every native search mode. |
| 6. Update/replay | R4 | Execute required project Tasks, invalidate on failure and replay without duplicates; no requirement to implement native incremental compatibility now. |
| 7. Shared retention/dependencies | R4 | Explicit inputs for identity records/links; no arbitrary transitive dependency engine. |
| 8. Independent index/evidence lifecycle | R5 | Repair/check actively consumed representations; unused diagnostic stores can remain out of scope. |
| 9. Read/session/history side effects | Conditional R6; observations stay in findings | Prevent stale QA reuse and separate stored feedback from applied feedback; no full history/accounting lifecycle program. |
| 10. Operational scope/isolation | R2/R3 plus deployment notes | Actual source attribution and identity-context checks; no universal scope framework or new dataset-isolation requirement. |

## Findings, choices and work that are not requirements

**Keep as findings:** native writer inventories; the recognized watermark pipeline names; Memify empty-list fallback; cross-dataset native retrieval/indexing; graph-native versus ledger provenance; optional consolidation/migrations; read/history/accounting effects. They guide implementation and targeted tests but do not become independent obligations to modify Cognee.

**Keep as architecture choices:** generated identity sources grouped per original document, native document-level retention for required endpoints, explicit mention marker edges, contribution-bearing resolution edges and occurrence UUIDs. These are recorded in the companion proposal rather than promoted to new universal requirements. Draft JSON/relational storage, custom-Task placement, explicit rebuild sequencing and a bounded consumed-store profile are implemented. Standard routing, expanded lifecycle and broader retrieval/store admission remain work. These choices must produce R1–R6's outcomes.

**Do not add now:** all-alias expansion of Triplet text; a new support-layer framework; universal dataset isolation; a history/version-control system; general rollback; production accounting/audit policy; scientific Claim/Measurement/Evidence reasoning. Native provenance and retention ownership do not establish scientific support. Scientific modeling/evaluation remains Stage 8.

## Recorded initial representation and remaining decisions

The selected direction is recorded in [cognee_stage5_4_5_identity_representation_proposal.md](cognee_stage5_4_5_identity_representation_proposal.md). It uses singleton and identity group terminology, no privileged canonical member, unique occurrence Entity IDs, a persistent mention marker, resolution kinds and shared edge contributions, with durable assignments/provenance outside the materialized graph.

| Decision | Current direction / remaining concrete output |
|---|---|
| Authoritative identity storage | Registered JSON plus relational descriptions, explicit source/record UUIDs and guarded publish/replace/withdraw entry points are implemented. The schema is a draft; automatic Describe/initial-key generation is later work. No per-assignment support node is required. |
| Source and contributor binding | One generated source per original document's local assignments; native document-level owners retain both endpoints. Complete the ownership/index matrix and original-source → generated-source dependency handling. |
| Mention representation | Explicit group UUIDs and original occurrence-chunk has_identity_mention edges preserve classification. Document-relative Unicode [start,end) ranges/native chunk mapping are implemented; additions/regrouping remain. |
| Shared identity links | Source-specific contribution aggregation, scope payloads, guarded replacement and withdrawal are implemented. Native owner cleanup does not merge custom properties; preserve application aggregation. |
| Maintenance sequence | Walk through publication, overlapping ingest, original/generated-source Update/Forget, rebuild gaps and failure/retry. Define loader/routing and how the resolver excludes incomplete maintenance. |
| Enabled retrieval paths | Adapt custom traversal for identity groups, directed scoped mentions and contribution eligibility; identify consumed collections and evidence lookups. Native readers do not enforce this model automatically. |
| Session behavior | Decide QA reuse and feedback application; define invalidation/clear behavior if enabled. |

The Stage-5.4.5 architecture/handoff review is complete. Runtime generalization and remaining operation coverage are Stage-6 work, currently partial step 4. No stage is added or renumbered.

## Evidence and validation status

The audit used the current roadmap, the completed 5.4.5.1 findings, and the lab's existing models and Stage-5.3 resolver code. The 2026-10-13 update records the subsequent representation discussion and source-inspected extension/ID behavior; it adds no runtime result. The measured scope remains the pinned two-document lab configuration; source-inspected or untested branches are not promoted to guarantees.

Key implementation references:

- [Lab identity models](https://github.com/mrjames313/cognee-science-lab/blob/main/src/cognee_lab/models.py)
- [Query resolution demonstration](https://github.com/mrjames313/cognee-science-lab/blob/main/scripts/stage5_query_resolution.py)
- [Identity-aware semantic recall demonstration](https://github.com/mrjames313/cognee-science-lab/blob/main/scripts/stage5_end_to_end_recall.py)
- [Pinned DataPoint persistence](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/storage/add_data_points.py)
- [Pinned source-removal planner](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/unified/provenance_delete_planner.py)
- [Pinned Improve watermark](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/graph_changes.py)

The listed acceptance checks are future implementation checks. None was run as part of rewriting this document. The previous ten-item text remains in earlier versions; its measured evidence remains in the findings report.
