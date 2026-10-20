# Stage 5.4.5.1 — Mutation and persistence characterization

**Characterization dates:** 2026-10-11–12  
**Design/source clarification added:** 2026-10-13  
**Lab checkout:** `4c0cca741a40277229fd2e0a781ac0d4e399a8d3`  
**Inspected Cognee:** tag `v1.6.2`, commit `ba3631f2ed363a6ea50d649c34c56885af6b36fe`  
**Status:** COMPLETE for the agreed characterization scope. Source inspection and the scoped runtime batches cover persistence, overlapping ingestion, default Improve/Memify, custom Tasks/source context, incremental and full-rebuild Update, source/dataset Forget, a minimal scientific fixture, and Recall/Search bookkeeping. The operation × artifact synthesis is complete. The subsequent Stage-5.4.5 architecture/handoff review is complete; current implementation is Stage 6, partial step 4. This file retains the pinned investigation results and their original evidence boundaries. Later runtime fixtures do not retroactively repair or rerun those experiments. See [SESSION_HANDOFF.md](../docs/SESSION_HANDOFF.md).

## Design handoff update — 2026-10-13

The selected initial direction is recorded in [cognee_stage5_4_5_identity_representation_proposal.md](cognee_stage5_4_5_identity_representation_proposal.md). Current terminology is singleton, identity group (consisting of variants), and occurrence-specific mention. Historical canonical/variant/mention annotations and helper nodes in the measurements below describe the tested prototype, not the selected durable schema.

The proposal stores structured assignments and original-input provenance independently in generated identity Data sources, initially one per original document's local assignments. Native document-level refs retain all required endpoints; project edges carry mention classification, resolution kind and shared applicability contributions. No graph support node per assignment is required. No combined publication/lifecycle or performance validation is claimed. Broad .1 characterization remains complete.

## Scientific reasoning scope clarification — 2026-10-12

Native lifecycle ownership and source/operation provenance do not, by themselves, establish scientific support for an assertion. Requirements for modeling or evaluating scientific justification are deferred to the later scientific Claim/Measurement/Evidence stage.

These findings characterize native source/edge-evidence metadata, persistence, ownership, reference integrity and lifecycle mechanics. They do not require scientific evidence schemas, reasoning rules, semantic support validation, confidence/truth policies, or scientific contradiction resolution. Prototype scientific-class observations remain measured results; their scientific semantics are deferred.

## Evidence boundaries

This investigation combines the committed lab code, pinned upstream source, uploaded graph/delta/retrieval artifacts, live storage snapshots, an isolated adapter/planner fixture, and user-executed public Improve, direct Memify, full public Forget, public Update, custom scientific-fixture/source-context probes, and dataset-deletion/Recall/Search controls on copies of local storage. The Improve probe also invoked Memify through its default triplet stage. New 5.4.5 lifecycle probes ran against isolated fixtures or cloned stores; the historical overlapping-ingest delta is existing lab evidence. Update's default-model incremental candidate is a diagnostic profile; it does not preserve the lab's MixedKnowledgeGraph extraction configuration.

The embedded visualization provides graph properties and edge information, with presentation-added fields. It is not a native database backup. In particular, it omits Ladybug's separate source-ref/run-provenance columns, vector collections, and relational operation/evidence rows.

Findings are labeled:
- **Observed artifact:** directly present in uploaded output.
- **Source-inspected:** implemented code path, not a new runtime experiment.
- **Offline function check:** upstream pure text-selection functions executed on exported data, with explicitly supplied field maps.
- **Measured runtime:** uploaded results from the user-executed isolated fixture or storage-clone probe; distinct from source inspection and forecasts.
- **Pending runtime:** requires controlled database execution.

## 1. Recovered graph baseline

### Live provenance follow-up (2026-10-11)

The uploaded `stage5_4_5_before.json`, captured at 18:59:56 UTC, confirms Cognee 1.6.2 with graph metadata `delete_mode=graph_native` and `provenance_version=1`. The configured shared graph has the same 281 node IDs and 761 edge identities as the HTML, with all 761 embedded edge-property records unchanged. Node presentation fields differ as expected; HTML must not be treated as an exact raw node-property export.

All 281 nodes and 761 edges have corresponding native provenance snapshots. All 35 support objects have empty source-ref, dataset, run, and run-ref arrays. All 62 support-incident edges are similarly unowned. Four semantic overlay Entities are also unowned: `Helios 1`, `H-1`, and two occurrence-scoped `the controller` entities. All 10 Entity-to-Entity `resolves_to` links are unowned. Overall, 242 nodes and 689 edges have at least one source ref; 39 nodes and 72 edges have none.

Ownership is independent of vector eligibility: all support objects expose native `indexed_fields`, but this snapshot does not establish that corresponding vector rows exist.

The two source documents carry distinct dataset IDs. The later relational snapshot resolves the names: the Stage 4 source-linked script ingested DOC01 into `helios_stage4_source_linked`, while the DOC02 script ingested into `helios_stage2`:

| Document | Native dataset UUID | Native data UUID |
|---|---|---|
| DOC01 | `c0e2ff53-9ea8-5752-941a-04502805bc5c` | `d49200c9-3f11-44f0-976e-b3daba720957` |
| DOC02 | `88e9627a-9304-5637-aff3-a561c0d93daa` | `a6e0a1a3-6d19-4bb9-adfe-d021a71942da` |

45 nodes (30 Entities and 15 EntityTypes) and 19 edges carry both dataset IDs. This is observed cross-dataset sharing in the configured shared graph. Both datasets belong to owner `2a6ee4bf-bedf-48f8-829c-bba2f1c6e6c2`. The relational data rows agree with the graph ownership anchors and have no legacy aliases. **Correction to the earlier experimental framing:** the overlapping DOC02 ingestion crossed two datasets sharing physical graph storage; it was not an overlapping-ingest test confined to one dataset. The property-replacement observation is unchanged, but logical-dataset isolation was not provided by this configured shared graph.

**Offline deletion forecast:** matching every document and chunk ref for the chosen dataset/data pair, applying the pinned planner's last-owner rule, and then accounting for Ladybug detach-delete predicts:

| Target | Nodes directly deleted | Matched nodes surviving other owners | Edges directly selected for deletion | Additional edges lost by detach | Total edge loss |
|---|---:|---:|---:|---:|---:|
| DOC01 | 74 | 45 | 286 | 43 | 329 |
| DOC02 | 123 | 45 | 384 | 2 | 386 |

For DOC01, 39 of the 43 additional detached edges touch support objects; the other four are semantic identity links. All 35 support objects survive native source-ref selection but each has at least one scalar reference to a deleted node: 25 `source_chunk_id`, nine `scope_document_id`, one `source_document_id`, with four also carrying a stale `source_entity_id`. All 35 lose at least one support-incident edge. For DOC02, the additional two detached edges are semantic identity links, and no support object is directly affected by endpoint deletion.

This table was originally a graph-snapshot forecast. The later public Forget clone experiment matches both predicted graph deletion counts exactly and measures additional vector/relational cleanup behavior below. The table describes whole-document deletion; distinct Update outcomes are recorded later. Shared Entity survival also does not imply reconstruction of pre-DOC02 descriptions or role properties: source ownership tracks object retention, not a per-source history of property values.

### Isolated adapter/planner experiment — measured results

The uploaded `results.json` records Cognee 1.6.2, isolated fixture directory `outputs/stage5_4_5_fixture_90gaq7h7`, and ten passing checks. The embedded snapshots independently confirm:

| Check | Measured behavior |
|---|---|
| Property patch | Preserved `sentinel` and `patch_a` while adding `patch_b` |
| Full same-ID upsert | Removed all three patch-only properties |
| Unstamped upsert on an owned node | Preserved the existing native source ref |
| Single-owner removal | Deleted the owned node and property-probe node |
| First removal from shared node | Kept it with only owner B's source ref |
| Unowned helper | Survived with its scalar `source_document_id` unchanged |
| Link to deleted owned node | Detached, despite the edge having no native owner |
| Link to surviving shared node | Remained after owner A removal |
| Last-owner removal | Deleted the shared node |
| Helper after last removal | Survived as an isolated node with zero edges |

The fixture shrank from four nodes/three edges to two nodes/one edge after owner A removal, and one node/zero edges after owner B removal. These are live Ladybug adapter and source-ref planner results, not public Forget/Update/Improve integration results.

The vector recording stub observed a collection check for `Triplet_text` (reported absent) and an orphan EdgeType cleanup request for `EdgeType_relationship_name`. No real vector store or embedding engine was used. Native graph refs surviving the property replacement demonstrates directly that provenance retention and preservation of semantic/support fields are separate contracts.

### Vector and relational baseline — measured results

The uploaded `stage5_4_5_storage_before.json` matches the input graph snapshot SHA-256 and records a baseline at 19:20:26 UTC. All selected vector/relational reads succeeded. These are graph-associated IDs, not an enumeration of every stored collection or orphan vector row.

| Collection / group | Expected associated IDs | Present |
|---|---:|---:|
| AbbreviationObservation: three field collections | 69 | 69 |
| IdentityResolution: two field collections | 18 | 18 |
| Mention_surface_text | 2 | 2 |
| DefinitionSummary_definitions_text | 1 | 1 |
| Entity_name | 174 | 174 |
| EntityType_name | 44 | 44 |
| DocumentChunk_text | 13 | 13 |
| TextSummary_text | 13 | 13 |
| TextDocument_name | 2 | 2 |
| EdgeType_relationship_name | 750 | 708 |
| Triplet_text | 761 | Collection absent |

All returned vectors have 2,048 dimensions. All 90 project support field-vector rows are present even though their source ownership is empty. The four unowned semantic overlay Entities also have name vectors. Scalar UUID source-chunk fields on observations are embedded in their own collection, which is a representation/indexing choice rather than native ownership.

EdgeType points are shared by normalized relationship text, not one point per edge. 23 support-incident edges (the abbreviation `observed_in` links) have corresponding text vectors; the other 39 do not. All ten semantic `resolves_to` links also lack their expected EdgeType text point. The 42 missing unique text IDs cover these 49 edge instances; some texts/IDs are shared, so counts must not be equated blindly. This mirrors the lab's mixture of DataPoint persistence and direct edge writes. Presence of a vector does not establish retrieval in a particular lane.

Relational evidence has 495 rows covering 490 unique graph edge IDs: 241 extracted-evidence rows and 254 structural-evidence rows. None touches a support endpoint. All evidence rows name `extract_chunks_from_documents` as `source_task`; this is the recorded provenance label, not proof of the exact causal extraction subroutine. Eight captured pipeline rows represent the started/completed states of Add and Cognify for the two documents. No Improve or Memify row appears in this selected baseline.

The public-operation probe, `scripts/stage5_4_5_improve_clone.py`, cold-copies local Ladybug/SQLite/LanceDB storage into a unique outputs directory and launches a fresh process whose database paths must all be within the copy. It compares dataset-only Improve as configured, enabled triplet embedding, an unchanged repeat, and a direct property patch followed by another Improve. The enabled phase uses real embeddings through the configured provider. No sessions or opt-in truth/global-context stages are supplied. Its successful runtime results are recorded below.

### Public Improve on cloned storage — measured results

The uploaded `improve_results.json` and `storage_after.json` record the successful clone `outputs/stage5_4_5_improve_4x_7zk13`, operating on `helios_stage2` (DOC02's dataset UUID). The successful operation ran at approximately 19:49 UTC on October 11. All reported phases finished without errors.

| Phase | Triplet enrichment | Captured graph/provenance effect |
|---|---|---|
| As configured (`triplet_embedding=false`) | Skipped: `triplet_embedding_disabled` | No changes |
| Enabled (`triplet_embedding=true`) | Completed, 15,220 ms | No changes |
| Unchanged repeat | `already_completed`: `no_writes_since_last_improve` | No changes |
| After direct helper property patch | `already_completed`: `no_writes_since_last_improve` | No additional changes |

The first seven stages skipped because no session IDs were supplied; global-context indexing skipped because its opt-in was disabled. The deliberate `lab_probe_sentinel=direct-write` patch affected IdentityResolution `9917c8b4-065f-5930-b207-5d3384481c7d`. The final graph diff contains only that patched node: no node/edge additions or removals, no changed edges, and no additional changed nodes. The native-node snapshot also reports that same node as changed because it includes the property blob; this is not evidence that the patch changed ownership refs.

`Triplet_text` changed from absent in the uploaded baseline to 761/761 graph-associated IDs present, with 2,048-dimensional vectors. IDs were independently recomputed using the pinned upstream `generate_node_id(source_id + relationship_name + target_id)` and match all 761 expected edge identities exactly.

| Native edge ownership in the baseline | Associated triplet vectors present |
|---|---:|
| DOC01 dataset only | 286 / 286 |
| DOC02 dataset only | 384 / 384 |
| Shared by both datasets | 19 / 19 |
| No native source ownership | 72 / 72 |
| Support-incident subset of unowned edges | 62 / 62 |

The support row is a subset, not an additional category. The remaining ten unowned edges are semantic Entity-to-Entity identity links. Support-related payloads include actual observation, identity-resolution, mention, and definition-summary content. Thus the earlier offline eligibility result is now backed by measured persistence: these helper relationships were embedded into the common Triplet collection. This is not a post-Improve retrieval experiment and does not establish which vectors a particular query will return.

**Measured scope:** although the public call names DOC02's dataset, this access-control-disabled configuration exposes shared physical graph storage. It indexed DOC01-only edges and unowned support edges too. Dataset selection therefore did not restrict triplet indexing to that dataset's source-owned artifacts in this experiment. No claim is made about access-control-enabled or physically isolated dataset storage.

Every pre-existing associated vector record in the other 13 collections is exactly equal to the uploaded pre-probe baseline, including payload, vector dimensions, and vector hash. `EdgeType_relationship_name` remains 708/750 expected unique text IDs; triplet indexing did not repair its missing rows. The 761 new Triplet payloads have empty `belongs_to_set` and null source-pipeline, source-task, source-user, source-chunk, and document fields. Indexing did not add graph source ownership or support assertion evidence.

Relational datasets, data rows, and all 495 edge-evidence rows are unchanged. Pipeline/operation records increased from eight to fourteen: four Improve operation rows and the started/completed rows of one Memify pipeline. The enabled operation carries the completed triplet-enrichment watermark and its child Memify run completed successfully. Repeat operations record `already_completed`; the disabled call records a `noop` outcome. Token counters of zero are not a measurement of embedding-provider usage or cost.

**Measured invalidation limit:** the direct property patch was visible in the graph snapshot, yet did not cause enrichment to rerun. The pinned source explains why: the gate checks recognized completed pipeline records, not graph content. This particular sentinel is not an indexed field, so the experiment establishes missed invalidation after a direct property write; it does not demonstrate a stale semantic embedding after an indexed-text change. Project maintenance that changes embeddable content through direct adapters needs an explicit reindexing/invalidation contract.

**Comparison boundary:** `storage_after.json` is compared with the earlier uploaded original-storage baseline, rather than the unuploaded `storage_before.json` captured inside the successful clone. The clone's before/after graph diffs are present in the results file. All 13 pre-existing associated vector collections and non-operation relational rows agree exactly across the available storage snapshots, supporting the comparison. These are targeted reads, not complete collection inventories or transactional snapshots.

**Probe corrections:** the first attempt stopped at the clone path guard because Cognee's dotenv loading overrode subprocess paths; supplying an empty dedicated `COGNEE_ENV_FILE` fixed precedence. A subsequent attempt failed because the composable storage exporter explicitly closed the cached LanceDB adapter before Improve. Removing that close fixed adapter reuse. Neither failed attempt is counted as a completed Improve mutation experiment; the successful fresh-clone run supplies the results above.

### Direct Memify: default, empty lists, and explicit no-op Tasks — measured results

The uploaded `memify_results.json` records three independent copies of the successful Improve clone `outputs/stage5_4_5_improve_4x_7zk13`. Each copied database retained the same graph and the 761 existing triplet vectors. In each copy, a preliminary Improve call reported `already_completed` with reason `no_writes_since_last_improve`. That call was recorded before the per-case baseline capture, so its operation row is not part of the subsequent Memify diff.

Every Memify call used DOC02's dataset UUID, `triplet_embedding=true`, blocking execution, and the truthy synthetic input `[{"lab_probe": "input-only"}]`. Default Task arguments were omitted in the default case; both lists were `[]` in the empty case; both lists contained explicit deterministic no-op Tasks in the no-op case. The default case ran twice sequentially. All four calls completed successfully.

| Case / phase | Changed Triplet records | Changed vector hashes | Changed triplet texts | Pipeline duration |
|---|---:|---:|---:|---:|
| Default, first call | 761 / 761 | 602 / 761 | 0 | 13.302 s |
| Default, repeated call | 761 / 761 | 631 / 761 | 0 | 13.293 s |
| Empty extraction and enrichment lists | 761 / 761 | 609 / 761 | 0 | 14.248 s |
| Explicit no-op extraction and enrichment | 0 / 761 | 0 / 761 | 0 | 0.068 s |

Durations come from the relational pipeline start/end times and exclude storage snapshot reads. The repeated default diff compares against the first default run's output; the other first-call diffs compare against their own cloned baseline. No triplet IDs were added or removed in any case. A changed record means the complete captured row differs; this includes payload metadata as well as the vector hash. The changed-hash counts establish that many repeated embeddings were not bit-identical even though the text was unchanged. Hashes alone do not quantify cosine distance, numeric error, semantic drift, or retrieval effects, and the result does not identify the cause of the numeric variation.

All four calls left the captured ordinary graph properties and native graph-provenance snapshots unchanged. Every associated record in the other 13 vector collections remained unchanged. Dataset rows, data rows, and all 495 edge-evidence rows remained unchanged. Each Memify invocation added two relational rows: pipeline started and pipeline completed. Thus explicit no-op Tasks preserve the measured graph/index/evidence state, but the public operation still writes lifecycle telemetry.

The no-op callback log confirms that extraction and enrichment each received the same synthetic input and returned it unchanged. Native default/empty-list runs nevertheless rewrote all existing graph-associated Triplet records, rather than indexing only the synthetic item. Combined with the inspected `get_triplet_datapoints` implementation, this is measured evidence that supplying `data` does not confine a Task which independently reads the graph engine. The uploaded summary does not contain raw per-row before/after payloads; it records the probe's comparison counts and relational additions.

**Confirmed contracts:**

- Direct default Memify does not use Improve's completion watermark to skip its triplet work; both default invocations ran.
- Empty extraction and enrichment lists select native defaults; they do not disable those stages.
- Explicit non-empty no-op lists replace both native stages in this tested profile.
- Default Memify performed index refresh, with no measured domain-graph reconciliation or source-ownership repair.
- Dataset/input selection is not an enforced read boundary for Tasks that scan the shared engine independently.

**Source-inspected consequence, not a further runtime result:** Improve's recognized-write list includes completed `memify_pipeline` runs without checking whether their Tasks changed graph content. A subsequent Improve can therefore conservatively invalidate its watermark after even a no-op Memify pipeline. This probe checked the gate before Memify, not again afterward.

### Full public Forget: DOC01 and DOC02 on independent clones — measured results

The uploaded `forget_results.json` records successful calls to `cognee.forget(dataset_id=..., data_id=..., memory_only=False)` for each source document on a separate copy of the successful Improve baseline. Each clone started with 281 nodes, 761 graph edges, 761 associated Triplet vectors, two data rows, and 495 edge-evidence rows. Before deletion, the probe copied both documents' referenced raw/original files and rebound their locations in the copied relational database. This tests full data-item Forget with file cleanup rather than memory-only Forget. Source-file preparation occurred before baseline capture.

| Measured outcome | Forget DOC01 | Forget DOC02 |
|---|---:|---:|
| Graph nodes deleted | 74 | 123 |
| Graph edges deleted, including detach loss | 329 | 386 |
| Graph remaining: nodes / edges | 207 / 432 | 158 / 375 |
| Shared nodes retained with the other dataset as sole owner | 45 | 45 |
| Shared edges retained; native provenance changed | 19 | 19 |
| Triplet vectors removed | 286 | 384 |
| Triplet vectors remaining | 475 | 377 |
| Deleted-edge triplet vectors still present | 43 | 2 |
| Missing triplet vectors for surviving edges | 0 | 0 |
| Indexed vectors left for deleted nodes | 0 | 0 |
| Support objects retained | 35 | 35 |
| Support objects with references to deleted nodes | 35 | 0 |
| Support objects isolated after deletion | 14 | 0 |
| Edge-evidence rows removed | 218 | 277 |
| Data rows removed | 1 | 1 |
| Dataset rows removed | 0 | 0 |

The graph deletion counts exactly match the earlier source-ref/last-owner/detach forecast. No surviving ordinary node or edge properties changed. Native snapshots show changes for the 45 shared nodes and 19 shared edges, consistent with removal of the targeted owner's provenance while retaining the other owner. Shared object values are retained as currently stored; the operation did not restore earlier per-source property versions.

**Measured support lifecycle gap:** DOC01 deletion leaves all 35 support objects alive with stale references: 25 `source_chunk_id`, nine `scope_document_id`, and one `source_document_id`; four objects additionally retain a deleted `source_entity_id`. It removes 39 support-incident graph edges. Thirteen AbbreviationObservation objects and the DefinitionSummary become isolated, while the other helpers retain some topology despite losing source links. All 90 existing support field-vector records remain unchanged. DOC02 deletion leaves the support objects' references and topology unaffected in this baseline, because those helpers were built for DOC01.

**Measured detached-edge vector cleanup gap:** the 43 stale DOC01 triplet vectors correspond to 39 support-incident edges and four semantic identity edges that were unowned but lost when an endpoint was deleted. The two stale DOC02 triplets correspond to semantic Entity-to-Entity `resolves_to` links. Every stale triplet's baseline graph edge had no native source ownership. Source-owned edge vectors were removed, but vectors for incident unowned edges lost through detach-delete were not. This confirms a cleanup distinction beyond graph survival: graph deletion alone did not eliminate all indexed representations of removed relationships.

The pinned planner explains the mechanism: it deletes Triplet IDs for source-ref-selected last-owner edges before graph deletion, then calls `delete_nodes`, which can detach additional incident edges. Its edge cleanup list does not include those additional unowned edge identities. A project cleanup contract or a native implementation fix must cover such incident-edge vectors; marking or stamping support objects alone would not address unowned semantic identity links automatically. This statement identifies the measured failure and source mechanism; no repair or post-deletion retrieval experiment was performed.

Node-vector cleanup succeeded for all captured index fields of hard-deleted nodes. All surviving-edge Triplet IDs remained present. EdgeType vectors fell from 708 to 426 for DOC01 and to 328 for DOC02, with 282 and 380 removed respectively; surviving captured records were unchanged. These counts alone do not prove exhaustive orphan cleanup in EdgeType collections because the report contains aggregate diffs, not post-deletion per-text usage reconciliation.

Relational evidence removal equals every baseline evidence row attributed to the chosen source: 218 for DOC01 or 277 for DOC02. The other document's evidence count remains. Each case removed one data row, preserved both dataset rows, and added two succeeded operation records (`delete`, nested under `forget`, plus the outer `forget`). Historical operation rows were retained. A success status therefore coexists with the measured helper and detached-triplet cleanup gaps.

Each case removed the selected document's two copied source files while preserving the other document's two copies. The original files' hashes were unchanged in both cases. Since the probe rebound all file locations into its managed data directory, this result establishes cleanup of those clone-managed copies; it does not assert that ordinary Forget deletes a user's external original corpus file. The pinned file cleanup implementation deliberately preserves locations outside its configured data root.

**Coverage boundaries:** vector reads after deletion used the pre-deletion graph snapshot's candidate IDs and both original dataset scopes, so orphan vectors and evidence were not hidden by querying only surviving graph objects. This is targeted associated-ID coverage, not a full collection inventory. The probe used a fresh isolated session cache; session invalidation was not measured. Native after-state evidence in the upload includes node owner arrays and graph/native diff identities, rather than complete raw snapshots of all changed provenance fields. Maintenance replay remains untested; public Update was subsequently measured below.

### Public Update: incremental candidate versus project-model rebuild — measured results

The uploaded `update_results.json` records two successful public Update calls on independent copies of the same Improve baseline. Both replace DOC01 with the same markdown edit: its two `10 kHz` VCS references become `12 kHz`. Source files were copied and rebound inside each clone before baseline capture. Both retained DOC01's data UUID and name, published a raw text file within the clone containing zero old-rate and two new-rate occurrences, and preserved all original source-file hashes. The published content hash is the same in both cases.

| Outcome | Default-model native candidate | MixedKnowledgeGraph project profile |
|---|---:|---:|
| Returned status | `incremental` | `full_rebuild` |
| Fallback reason | None | `custom_extraction_config` |
| Core Cognify calls observed through Update's call seam | 0 | 1 |
| Memory-only Forget checkpoint | None | One |
| DOC01 chunks before / after | 6 / 6 | 6 / 6 |
| Old chunk IDs absent afterward | 2 | 2 |
| New chunk IDs afterward | 2 | 2 |
| Four other chunk IDs | Preserved; properties unchanged | Deleted at checkpoint, then recreated; properties changed |
| Nodes added / removed / changed | 11 / 22 / 30 | 45 / 33 / 84 |
| Edges added / removed / changed | 55 / 108 / 18 | 203 / 222 / 121 |
| Final graph: nodes / edges | 270 / 708 | 293 / 742 |
| Support objects retained | 35 | 35 |
| Support objects with stale source-chunk IDs | 10 | 10 |
| Isolated support objects | 6 | 14 |
| Deleted-edge Triplet vectors still present | 10 | 43 |
| Current graph edges without Triplet vectors | 55 | 310 |
| Evidence rows removed / added | 0 / 0 | 218 / 233 |

The default-model result reports two changed regions, two chunks deleted, two added, four kept, zero reused/reindexed, and six total. Its four retained chunks and their captured vectors are unchanged. The 30 changed ordinary nodes consist of 22 Entities, seven EntityTypes, and the TextDocument, demonstrating that a bounded chunk edit can still rewrite semantic objects shared with other chunks/documents. Among the baseline's 45 cross-dataset shared nodes, 44 retain both dataset owners; one EntityType (`dataset`) loses DOC01 ownership and remains owned by DOC02.

**Configuration boundary:** the native candidate omitted a custom model and prompt. It tests the default path's behavior on the lab baseline, rather than a configuration-preserving update of the original MixedKnowledgeGraph extraction. Passing MixedKnowledgeGraph with `chunk_level_diff=True` produces the measured rebuild fallback because 1.6.2 permits chunk-level updates only with the default graph model and prompt. This is a public API constraint, not a failure of source-ref provenance.

The project rebuild called core Cognify once with MixedKnowledgeGraph, no custom prompt, and the recorded 1,000-token chunk budget. A read-only wrapper captured the state after its real `forget(memory_only=True)` returned and before the pinned Add/Cognify rebuild continued. At that checkpoint, 74 nodes and 329 edges were removed, leaving 207 nodes/432 edges, all 35 helpers had stale source/semantic references, and 43 detached-edge Triplet vectors remained. This matches the graph deletion mechanics measured in full Forget while preserving the relational data row.

All six old DOC01 chunks were removed at the checkpoint. Four were subsequently recreated with the same content-derived UUIDs, while the two changed chunks received the same two new IDs found in the incremental run. Consequently, final UUID overlap alone would misclassify a full rebuild as partial preservation. All four recreated chunk property snapshots changed, and all four chunk-vector records were refreshed. Their four TextSummary vectors were also refreshed with changed text. Among the original 45 shared nodes, 39 again have both owners after reconstruction; six remain DOC02-only. The rebuild's extraction/model differences and LLM variability mean exact graph counts are observations of these runs, not deterministic branch guarantees.

**Project maintenance was not replayed in either case.** All 35 helper objects and their 90 field-vector records remain unchanged. In the incremental run, ten AbbreviationObservation objects retain IDs of the two deleted chunks; six observations become isolated and ten associated deleted-edge Triplet vectors remain. In the rebuild, the same ten observations have stale chunk IDs after reconstruction, but 14 helpers are isolated (13 observations and the DefinitionSummary). All 39 support-incident links lost at retirement remain absent; recreating their endpoint IDs did not recreate those links. The surviving 43 orphan Triplets cover 39 support links and four semantic identity links. Current graph lookup, project source anchoring, and stored indexed representations therefore require separate maintenance contracts.

**Triplet indexing profile:** both workers retained the configured `triplet_embedding=false`. They started with Triplet vectors generated by an earlier enabled Improve, then Update deleted some old Triplets without generating replacements. This explains the missing current-edge Triplet coverage and must not be labeled a failed enabled-indexing test. The incremental run retains 663 Triplets: 653 for current graph edges plus ten for deleted helper edges, with all 55 added edges lacking Triplets. The rebuild retains 475: 432 for current edges plus 43 for deleted edges; 203 added edges and 107 restored old-identity edges lack Triplets. Existing retained Triplet records were unchanged even where graph edge properties changed; consistency of their text with the reconstructed graph was not measured. Explicit post-update enrichment and orphan cleanup are separate requirements.

Node-vector cleanup again leaves no captured vectors for nodes absent after Update. New/retained Entity, EntityType, EdgeType, source, and summary indexes were written as reported in the upload. After-state vector candidates were the union of old and new graph IDs, index fields, relationship texts, and dataset scopes, so old orphan vectors were retained in the scan. These remain associated-ID comparisons rather than full collection inventories.

### Incremental evidence maintenance gap — measured and source-inspected

The incremental run left all 495 baseline edge-evidence rows exactly unchanged, with zero additions or removals. Independently matching the two removed chunk IDs against the baseline evidence finds **93 rows still pointing to retired chunks**. Matching removed graph edge identities finds **79 rows still describing absent graph edges**; these are a subset of the 93, not additional rows. The data row still exists, so a lookup's Data-row existence check alone cannot remove this stale evidence from consideration. This probe does not establish which rows a particular retrieval/provenance query would return.

Pinned source explains the coverage difference: incremental Update directly calls `extract_graph_and_summarize` and retires chunk source refs through `delete_chunks_incremental`/the unified planner. That path does not invoke the document Task's relational evidence capture or a chunk-scoped evidence sweep. The current upload independently confirms that neither refresh nor cleanup occurred. Source-ref ownership updates are not equivalent to assertion-evidence maintenance.

The full rebuild swept all 218 old DOC01 evidence rows at memory-only retirement and captured 233 replacement rows (114 extracted, 119 structural), all attributed to DOC01. No replacement evidence row points to the two retired chunk IDs. DOC02's 277 evidence rows remain, giving 510 total after reconstruction. This profile also added five lifecycle rows: the memory-only Forget operation and started/completed Add and Cognify rows. Incremental Update added two `incremental_update_pipeline` rows. Both preserve two datasets and two data rows. The narrow Data snapshot projection does not include content hashes/locations; the separate published-text read establishes those changes despite an unchanged projected Data row.

### Incremental watermark visibility — corrected setup and measured results

The measured incremental operation records its completed run as `incremental_update_pipeline`, which is absent from pinned Improve's `WRITE_PIPELINE_NAMES`. The list contains `cognify_pipeline`; its comment says incremental Update attributes there, but that is the data-item status key, not the completed run's pipeline name. **General source inference:** when the updated dataset already has a completed enrichment watermark, this run-name mismatch can leave its incremental write invisible to the gate. The rebuild's completed `cognify_pipeline` run is recognized.

**Correction to the original follow-up setup:** the earlier successful Improve enriched DOC02's dataset (`88e9627a-...`), whereas the first Update calls targeted DOC01's dataset (`c0e2ff53-...`). Watermarks are dataset-scoped even though default triplet extraction reads the shared physical graph. DOC01 therefore had no prior completed enrichment watermark in that copied history, so calling Improve immediately on those first Update clones would have run for lack of a watermark rather than tested missed invalidation. The previous wording suggesting an existing same-dataset watermark was incorrect. The corrected same-dataset experiment below resolves this limitation.

The uploaded `watermark_results.json`, produced by `stage5_4_5_update_watermark.py`, records successful repetitions of both Update profiles from fresh copies of the original Improve baseline. In each copy it first completed enabled Improve for DOC01, restored `triplet_embedding=false` for Update, ran the same two-occurrence VCS edit, then called enabled Improve for DOC01 again. Prime and post-Update results explicitly name the same DOC01 dataset UUID. The priming guard confirmed no graph/provenance mutation. The project rebuild provides the recognized-write control.

| Measured post-Update behavior | Default-model incremental Update | Project-model full rebuild |
|---|---:|---:|
| DOC01 priming enrichment | Completed | Completed |
| Update result | `incremental` | `full_rebuild` |
| Subsequent triplet-enrichment stage | `already_completed` | `completed` |
| Skip reason | `no_writes_since_last_improve` | None |
| Current graph edges | 716 | 760 |
| Current-edge Triplets present after Improve | 645 | 760 |
| Current-edge Triplets missing after Improve | 71 | 0 |
| Indexed Triplets without current graph edges | 10 | 43 |
| Associated Triplet records after Improve | 655 | 803 |
| Triplet records added / removed by post-Update Improve | 0 / 0 | 328 / 0 |
| Existing Triplet records changed by post-Update Improve | 0 | 432 |

**Measured gate failure:** the incremental run changed the graph (13 nodes added, 18 removed, 30 changed; 71 edges added, 116 removed, 15 changed), replaced two chunks and kept four, and recorded a completed `incremental_update_pipeline`. Enabled Improve nevertheless skipped its enrichment stage as `already_completed`. All captured vectors were unchanged by that call, leaving all 71 added edges without Triplet vectors and ten deleted-edge Triplets still present. The API's overall Improve result was `completed`; that status is not an assurance that its indexing stage ran or current-edge coverage is complete.

**Measured positive control:** the rebuild recorded a recognized completed Cognify run. Subsequent enabled Improve ran its enrichment stage, added all 328 missing current-edge Triplet records, and refreshed 432 existing current-edge records. It achieved 760/760 current-edge coverage, but removed no Triplet records: the 43 orphan vectors survived, giving 803 associated records. Of the 432 refreshed records, 358 vector hashes changed while their texts remained unchanged. Hashes do not measure the magnitude or retrieval effect of those numeric differences.

Both post-Update Improve calls left the captured graph/provenance, all other associated vector collections, projected dataset/data rows, and edge-evidence rows unchanged. The skipped case added one Improve operation record; the running case added its Improve record and two child Memify pipeline rows. Priming and both Update profiles retained the original source-file hashes. Exact re-extracted graph counts differ from the first Update experiment because LLM extraction was repeated; the branch outcomes, retained-chunk behavior, and indexing decisions are measured separately within each new clone.

**Confirmed lifecycle distinction:** a missed change signal prevents index refresh, and successful index refresh still does not prune orphan vectors or replay project maintenance/evidence cleanup. These need explicit contracts. The source-level pipeline-name mismatch now has matching public-runtime evidence; no fix to the gate or data was applied by this characterization probe. Post-update retrieval behavior remains untested.

**First Update experiment limits:** result durations (23.928 s versus 48.965 s) are not a clean performance comparison: different extraction schemas were used, and the rebuild included extra checkpoint reads inside Update's elapsed time. Those first runs performed no helper replay, vector repair, provenance-sidecar repair, post-update retrieval, unchanged-content Update, or session invalidation experiment. The subsequent watermark probe measured enabled native enrichment, as described above. The core Cognify/Forget wrappers forwarded the real native calls and added read-only checkpoints; they did not replace native writes.

The October 10 visualization contains 281 nodes and 761 edges.

| Node type | Count |
|---|---:|
| Entity | 174 |
| EntityType | 44 |
| DocumentChunk | 13 |
| TextSummary | 13 |
| TextDocument | 2 |
| AbbreviationObservation | 23 |
| IdentityResolution | 9 |
| Mention | 2 |
| DefinitionSummary | 1 |

There are 35 project support/context objects across the last four types, and 62 edges touching at least one of those objects.

| Support-incident relationship | Count |
|---|---:|
| observed_in | 25 |
| supports | 10 |
| canonicalizes_to | 9 |
| source_representation | 5 |
| scoped_to | 9 |
| materializes_as | 2 |
| resolves_to | 1 |
| summarizes_definitions_for | 1 |

The graph also contains 10 Entity-to-Entity `resolves_to` edges. The support-level Mention-to-Entity `resolves_to` is a separate relationship use and must not be included blindly in semantic identity closure.

**Observed artifact:** only 23 of the 62 support-incident edges have an `edge_object_id` in the exported edge properties. None of the 35 project objects is marked `is_internal`; all show null `source_pipeline` and `source_task`.

These null properties do not establish absence of native source-ref provenance, because those columns are not in this export. The committed write paths provide additional evidence below.

### Custom Tasks, source context, and scientific fixture — measured results

The uploaded `custom_results.json` records the clone `outputs/stage5_4_5_custom_38qae6n7/fixture`, derived from the successful Improve baseline. All five explicit custom Memify runs completed, both memory-only Forget calls returned success, and all 15 reported checks passed. Independent analysis of the snapshots additionally verifies subtree ownership, relationship retention after upsert, field-vector removal, and exact fixture Triplet coverage.

This is a minimal capability/lifecycle fixture using `ProbeClaim`, `ProbeMeasurement`, and `ProbeEvidence`, with name-based identity and explicit indexed fields. It uses real field and Triplet embeddings, explicit nonempty extraction/enrichment Task lists, and no LLM extraction. Scientific revision logic is implemented by the custom Task; it is not native scientific reconciliation. The source documents belong to two different datasets sharing physical storage with access control disabled.

#### Source context and ownership

Three distinct Claim/Measurement/Evidence triads were persisted:

| Write profile | Fixture nodes / edges | Native source ownership |
|---|---:|---|
| Direct `add_data_points`, no ctx | 3 / 3 | None |
| Custom Memify Task forwarding its injected ctx, raw dict input | 3 / 3 | None |
| Custom Memify Task explicitly replacing ctx.data_item with the real DOC01 Data row | 3 / 3 | DOC01 document ref and pipeline-run attachments on all three nodes and all three edges |

The incoming Task contexts contain a real dataset and pipeline-run ID, but the dict input supplies no source-data ID. Only explicit binding to the concrete Data row establishes the required source anchor. The two unanchored triads still carry scalar `source_document_id` values on their Claims and Evidence nodes; those fields do not create native ownership. This converts the earlier source-inspected context contract into measured runtime behavior for this custom Task profile.

The bound fixture has document-level refs, not chunk-level refs: no DocumentChunk is included. Its field-vector payloads still have null source-pipeline, source-task, source-user, document, and chunk fields. Native graph ownership and vector payload attribution are separate in this tested writer path. The Tasks return their raw input rather than the written DataPoints; this is not a test of every possible pipeline provenance-stamping profile.

#### Patch, full upsert, and relationship retention

The targeted graph patch changes the owned Claim to `status=reviewed` and adds `lab_patch=kept`, preserving its proposition, source-document scalar, and native owner. The fresh same-ID DataPoint upsert then removes the patch-only property, restores the default `status=asserted`, and writes `source_document_id=null`, while preserving the existing native DOC01 ref.

That fresh object has no populated Measurement/Evidence relations, yet the existing three owned-subtree edges remain. Thus replacing the node property blob does not mean replacing its incident relationship set. The upsert rewrites the Claim's field-vector payload metadata; the direct non-indexed patch leaves its captured payload unchanged. This probe records vector IDs and payloads, not numeric vector hashes, and does not test indexed-text invalidation.

#### Explicit supersession and recursive ownership propagation

The DOC02-bound writer creates a new Claim and Evidence, updates the same-ID shared Measurement from 10 to 12 kHz, sets the old Claim's status to `superseded`, and persists an explicit `new Claim → supersedes → old Claim` edge. Those operations are coded in the Task.

Because `supersedes` contains the old Claim as a nested DataPoint, graph expansion also traverses and rewrites the old Claim, old Evidence, shared Measurement, and their three relationships. **All three original nodes and their three edges become co-owned by DOC01 and DOC02.** The two new nodes and four new relationships have DOC02 ownership only. This is broader than attaching a second owner solely to the Measurement.

The old Claim's proposition and old Evidence's text still assert 10 kHz, while the Measurement they reference now holds 12 kHz. This is the intentionally permissive fixture's stored state, not automatic consistency checking or preservation of an immutable historical observation. Scalar source-document fields on the old Claim/Evidence continue naming DOC01 even after their native ownership becomes shared.

**Operational implication:** distinguish source-attribution records from lifecycle ownership; a nested reference participates in the writer's traversal rather than automatically remaining read-only. The fixture's overwritten values expose a mechanical persistence/history limit. Decisions about immutable scientific observations, scientific revision/evidence semantics, and their justification are deferred to Stage 8.

#### Memory-only source removal and targeted index cleanup

| Phase | Whole graph nodes / edges | Fixture nodes / edges | Fixture field-vector rows | Present fixture Triplets | Source evidence rows |
|---|---:|---:|---:|---:|---:|
| Baseline | 281 / 761 | 0 / 0 | 0 | 0 | 495 |
| Three triads seeded | 290 / 770 | 9 / 9 | 9 | 9 | 495 |
| After patch and after full upsert, each | 290 / 770 | 9 / 9 | 9 | 9 | 495 |
| Revision/shared state | 292 / 774 | 11 / 13 | 11 | 13 | 495 |
| After DOC01 memory-only Forget | 218 / 445 | 11 / 13 | 11 | 13 | 277 |
| After DOC02 memory-only Forget | 45 / 18 | 6 / 6 | 6 | 6 | 0 |

Removing DOC01 strips its native refs/run attachments from the shared original triad, leaving DOC02 ownership. All eleven fixture nodes and thirteen fixture relationships survive. The shared Measurement remains 12 kHz; ownership removal does not restore its prior 10 kHz value or undo the explicitly written supersession state.

Removing DOC02 next deletes all five anchored fixture nodes, their five field-vector rows, and all seven anchored fixture relationships and corresponding Triplet rows. Both unanchored triads survive, with six nodes, six relationships, six field-vector rows, and six Triplet rows.

Recomputed Triplet identities exactly match the present fixture relationship set in every captured phase: **zero missing or orphan fixture Triplets**. This does not reverse the earlier detached-edge orphan finding. Here all removed fixture relationships are owned and selected by provenance; the problematic earlier relationships disappeared through detach-delete of endpoints. This report captures targeted fixture Triplet IDs across all phases, not a full post-Forget collection inventory.

Typed `ProbeEvidence` nodes and their relationships produce **zero relational edge-evidence rows** in every phase. The total source evidence count stays 495 through custom writes, drops by 218 after DOC01 removal, and drops by the remaining 277 after DOC02 removal. A custom Evidence node plus document-bound ctx does not automatically create DocumentChunk-grounded assertion evidence.

**Coverage boundary:** measured lifecycle and persistence capability for a small explicit schema, shared physical graph, and custom Tasks. No production scientific representation, project-helper migration, maintenance replay, contradiction policy, immutable revision system, or general index-repair mechanism has been implemented.

### Dataset-wide Forget and Recall/Search bookkeeping — measured results

The uploaded `controls_results.json` records three independent copies under `outputs/stage5_4_5_controls_6i_8rit3`: `dataset_full`, `dataset_memory`, and `reads`. All cases completed without errors and all **25 reported checks passed** (8 + 8 + 9). Analysis independently confirms identical deletion graph effects, shared-owner retention, the orphan-vector counts, unchanged read-path graph/index diffs, and stable session QA vectors after session read/feedback.

Each clone uses isolated SQLite session cache, `caching=true`, `auto_feedback=false`, `usage_logging=false`, `session_search_mode=concurrent`, and `ENABLE_LAST_ACCESSED=false`. Full/memory dataset deletion operates on DOC01's dataset, which contains one Data row in this baseline. The dataset test is not an exhaustive multi-document dataset deletion experiment.

#### Full versus memory-only dataset deletion

Both deletion calls use `cognee.forget(dataset_id=DOC01_dataset, memory_only=...)` **without data_id**. Each deletion clone first copies/rebinds both documents' raw/original file references into its managed data directory and seeds one synthetic cached QA per dataset, using explicitly dataset-bound SessionManagers. Seeding creates two QA vectors and session lifecycle records before the per-case baseline. It does not alter the graph.

| Effect | Full dataset Forget | Memory-only dataset Forget |
|---|---|---|
| Graph/provenance | Deletes 74 nodes and 329 edges; leaves 207 nodes / 432 edges | Identical |
| Shared objects | 45 nodes and 19 edges survive with DOC02 ownership only | Identical |
| Target dataset and Data row | Removed; other dataset/Data row retained | Both retained |
| Target pipeline_status | Target Data row removed | Both dataset entries cleared: add_pipeline and cognify_pipeline become empty maps |
| Rebound DOC01 raw/original file copies | Removed | Retained |
| Rebound DOC02 file copies | Retained | Retained |
| Original source files | All hashes unchanged | All hashes unchanged |
| Relational edge evidence | 218 DOC01 rows removed; 277 DOC02 rows remain | Identical |
| Seeded DOC01 cached QA and QA vector | Removed | Removed |
| Seeded DOC02 cached QA and QA vector | Retained | Retained |
| Session lifecycle registry rows | Both records unchanged | Both records unchanged |
| Query/result history | 15 query rows / 15 result rows unchanged | Identical |
| Operation bookkeeping | One succeeded Forget row added | Identical |

The pipeline-status reset is an important distinction from the pinned single-data memory-only source path, which resets Cognify status only. Dataset-wide memory-only Forget clears the target dataset entry across the recorded pipeline statuses in this experiment.

Both modes remove the same graph-associated vectors: 51 Entity names, 10 EntityType names, six chunks, six summaries, one document name, 282 EdgeType records, and 286 Triplets. No vector for a deleted node remains. The remaining 475 Triplets comprise 432 current graph relationships plus **43 orphan Triplets** for detached unowned relationships; no surviving graph relationship lacks its Triplet. All 35 project support nodes survive with stale scalar node references, 14 are isolated, and their 90 field-vector rows remain unchanged.

Thus dataset-wide deletion does not sweep unowned helpers or fix the previously measured detach-delete Triplet gap. Cached session invalidation succeeds for the seeded dataset-attributed QAs and their session vectors, while the SessionRecord registry rows remain. Do not equate deleting cached session content with deleting all session lifecycle/accounting records. This does not test contamination chains, agent traces, every cache backend, or single-document targeted QA invalidation.

#### Raw Search, context-only Recall, answer, session read, and explicit feedback

All five read/control phases preserve the complete captured graph properties, edges, native provenance, all **14 baseline graph-associated vector collections**, dataset/Data records, and all 495 edge-evidence rows. Query embedding and answer generation do not re-index the stored graph in this profile. The generated-answer phase does create a separate session QA vector.

The supplementary bookkeeping capture queries whole relational tables and follows all QA IDs seen in the fresh probe session. These reads are necessary because graph-associated storage capture alone neither enumerates session QA vectors nor includes operation rows whose dataset_id is null.

| Phase | Added query/result history | Added operation rows | Cached QA count after phase | Session QA vector count after phase |
|---|---:|---:|---:|---:|
| Baseline | — | — | 0 | 0 |
| Search CHUNKS | 1 query + 1 result | 1 Search | 0 | 0 |
| Recall RAG_COMPLETION, only_context=True | 1 query + 1 result | 1 Recall | 0 | 0 |
| Recall RAG_COMPLETION answer | 1 query + 1 result | 1 Recall | 1 | 1 |
| Recall scope=session | 0 | 1 Recall | 1 | 1 |
| Explicit SessionManager.add_feedback | 0 | 0 | 1 | 1 |

Whole-table counts go from 15 to 18 queries, 15 to 18 results, and 29 to 33 PipelineRun rows. The Search operation row carries DOC01's dataset UUID; all three Recall operation rows carry null dataset_id despite graph Recall receiving an explicit dataset and session. Graph Recall's query/result history rows do carry DOC01's dataset UUID. The earlier graph-scoped exporter sees only the dataset-attributed Search operation addition, so its empty Recall operation diff must not be read as absence of a write.

The raw CHUNKS search stores a 10,178-character result value in search history; the context-only Recall stores 7,806 characters; the generated answer is stored as a 91-character string representation. These are the values actually captured by the history path. Raw search and context-only Recall create no cached QA.

Answer generation adds one dataset-attributed running SessionRecord and one SessionModelUsage row. The recorded answer operation/model usage contains 1,976 input and 21 output tokens for `openai/gpt-5.6-luna`. The SessionRecord itself retains zero aggregate token counters in this capture. Operation/model usage and lifecycle aggregate fields are not assumed to be interchangeable accounting views. Token-zero query-only rows do not establish embedding-provider usage or cost.

The cached QA stores the question and answer, empty context text, and three used chunk IDs. Its 2,048-dimensional `SessionQAVector_text` row carries the user/session scope tag. Session-only Recall returns that existing QA with source=session, writes a Recall operation row, and adds no query/result history or QA. The explicit feedback update sets score=4 and synthetic feedback text, with `memify_metadata.feedback_weights_applied=false`; the QA vector record/hash stays exactly unchanged. No graph feedback weight changes occur. Feedback ingestion is distinct from a later Improve feedback-application stage, which was not run.

#### Dataset labels versus retrieval scope

The graph calls request DOC01's dataset UUID, but the raw chunk result and the generated QA's used IDs contain **one DOC01-owned chunk and two DOC02-owned chunks**. The mapping was independently checked against the live native provenance baseline:

| Retrieved chunk | Native source dataset |
|---|---|
| `0f202b91-2fe5-5035-8e2d-8b603c99aeab` | DOC01 |
| `924e156d-1865-5dcb-a1a9-9977fab8477c` | DOC02 |
| `c5eda29e-c84b-5f53-a89e-54bcc54c53aa` | DOC02 |

The response/history/session attribution names DOC01 while the retrieved content crosses datasets. In the present access-control-disabled shared-store configuration, requested/recorded dataset identity is **not proof of source-confined retrieval**. This extends the earlier shared Improve indexing observation to the read path. It does not characterize access-control-enabled isolation.

The generated answer says the EDC rate is not specified in the supplied context. Neither the raw top-three results nor context-only response contains the literal strings 10 kHz or 12 kHz. The session-read control successfully replays that answer; this batch establishes bookkeeping and provenance behavior, not a positive sampling-rate retrieval benchmark.

## 2. Overlapping-ingest mutation is now verified against the actual delta

The uploaded DOC02 report confirms:

- 160 → 281 nodes.
- 377 → 761 edges.
- 121 new node IDs; 384 new edge identities.
- Zero removed nodes, removed edges, or changed edge property records.
- 30 existing nodes changed; every one was an Entity.

Changed-property incidence:

| Property | Number of changed Entities |
|---|---:|
| description | 30 |
| relations | 16 |
| entity_role | 9 |
| graph_layer | 9 |
| name | 2 |
| source_pipeline | 2 |
| source_task | 2 |

The exported post-ingest graph has 166 Entities without a role, 6 variant-role Entities, and 2 mention-role Entities. It has **zero Entities still marked canonical**.

The committed `stage5_query_resolution.py` selects canonical candidates through `entity_role == "canonical"`, and `stage5_identity_recall.py` similarly relies on role properties. The topology-derived repair previously discussed is not implemented in these inspected functions.

This gives a concrete causal explanation for the documented 5/5 → 0/5 benchmark regression. The uploaded delta itself is not a query-benchmark rerun.

## 3. Persistence: replacement versus patching

### 3.1 Normal persistence is an upsert, not a protected append

**Source-inspected:** `GraphDBInterface` defines writes as ID/edge-identity upserts with property replacement on match. Ladybug `add_nodes()` explicitly assigns the incoming serialized JSON property blob to the existing node, along with incoming name/type.

This is not specific to Entity. A rewritten `IdentityResolution`, observation, DefinitionSummary, or future Claim with the same ID can also replace stored properties if written through the same mechanism.

A project-owned type avoids being selected by some native extractors; it does not make the persistence primitive non-mutating or field-preserving.

### 3.2 Partial updates exist but have a different contract

Ladybug's optional `update_node(id, values)` reads existing properties, merges the supplied patch, and writes the merged blob. Native preference maintenance uses that seam where available, with a full-node-upsert fallback on adapters that do not implement it.

Therefore distinguish:
- full object upsert;
- property patch;
- special-purpose weight/truth-state updates;
- provenance attachment/removal.

“Cognee modifies a node” is insufficiently precise for the ownership matrix.

### 3.3 Automatic provenance requires source lifecycle context

`add_data_points(..., ctx=...)` derives automatic source ownership from a concrete user, dataset, and data-item ID. A pipeline run alone is insufficient. Plain Memify graph input generally has no source-data ID, so merely putting a write inside Memify does not automatically give it document ownership.

When appropriate context exists, Cognee can attach:
- document-level source refs;
- chunk-level source refs for recognized chunk-produced output;
- pipeline-run/source attachments for rollback;
- relational provenance on the legacy-ledger path.

Chunk ownership follows Cognee's model traversal/production records. A scalar field named `source_chunk_id` is not equivalent to native ownership stamping.

The lab scripts currently write observations, identity helpers, and semantic overlay nodes through `add_data_points()` **without ctx**. Several support/identity links are written directly through `add_edges()` without explicit source-ref/run arguments.

**Source-path inference, now backed by live evidence:** those existing lab writes do not receive automatic native source ownership through this mechanism; baseline snapshots confirm empty native refs. The custom fixture separately measures that run/dataset ctx alone remains unanchored, while explicit binding to a concrete Data row stamps document ownership.

### 3.4 Ownership provenance and assertion evidence are separate

`capture_graph_provenance()` for relational edge evidence requires context and reachable DocumentChunk objects, and honors the edge-evidence feature flag. A support-only maintenance batch is not automatically a source-grounded assertion-evidence batch.

Consequently, DataPoint persistence, native deletion ownership, producing-run provenance, and existing backend edge-evidence records must not be treated as interchangeable. Their metadata/reference lifecycle is in scope here. Neither native ownership nor an evidence-record presence establishes scientific support; scientific justification modeling/evaluation is deferred to Stage 8.

### 3.5 Operation selection, topology, deletion, and identity — review clarification (2026-10-12)

This clarification supports requirements review items 1 and 2. It adds source-inspected operation distinctions; **no new runtime probe was run**. Stage 5.4.5.1 remains complete for its agreed characterization scope, rather than becoming a claim of exhaustive live coverage.

Standard text Cognify processes selected source data and persists the DataPoint graph produced by that run. Existing nodes are upsert candidates when their IDs appear in that graph. This is an operational selection rule; the exact write set depends on extraction output and nested traversal, not a prediction that a node is “likely” to be mentioned. Optional Tasks, alternate ingestion routes, rollback and migration paths must be considered separately.

**Edge-write distinction:** the direct Ladybug batch writer matches on source ID, target ID, and relationship name and replaces the ordinary edge property blob on a match. Standard KnowledgeGraph extraction's `find_existing_edge_identities`/`attach_new_edges_to_data_points` path deliberately excludes already-stored extracted relationships from fresh relation attachments, with separate ownership handling. Do not infer that every standard Cognify overlap rewrites every existing extracted edge's properties merely because the low-level writer can do so. Source/context structural edges use their own construction/write paths.

**Primitive distinction:** Ladybug `add_nodes` is a full batch upsert, including native name/type columns. The singular `add_node` uses ON CREATE SET without the same ON MATCH replacement. Likewise `update_node` patches the ordinary JSON blob; it is not a generic native-column/ID rename contract.

| Operation/profile | Nodes | Relationships | Evidence / support boundary |
|---|---|---|---|
| Successful standard text Cognify | Upserts objects produced by source extraction at matching IDs; ordinary extraction has no general deletion sweep | Adds new extracted triples; existing extracted triples are deliberately omitted from new relation attachments, with applicable ownership handling; structural writes have their own paths | M overlapping-ingest changes; S exact extraction path. Failure rollback, migrations, code/DLT routes and optional Tasks are separate profiles |
| add_data_points → Ladybug add_nodes | Full property/name/type replacement at matching IDs; omitted properties may disappear | Emitted same-triple edges replace ordinary property blobs; omitted relationships remain | M property replacement and relationship retention; S edge/name/type write behavior |
| Ladybug add_node (singular) | Creates by ID with ON CREATE SET; does not perform the batch method's ON MATCH property replacement | Not a relationship-set reconciliation method | S. Primitive names alone do not establish identical semantics |
| Native incremental Update | Retires replaced chunks and last-owner artifacts; surviving shared nodes retained; fresh objects can upsert existing IDs | Deletes retired-owner edges, detaches incident edges of deleted nodes, writes replacement output | M diagnostic default-model profile |
| Full-rebuild Update | Memory-only Forget then Add/Cognify; source Data ID retained; graph objects may disappear/reappear | Source-owned relationships retired/rebuilt; endpoint deletion can detach project edges | M project-model profile; project maintenance replay absent |
| Source/dataset Forget, full or memory-only | Provenance selection and last-owner deletion in tested graph-native mode | Selected edge deletion plus detach-delete of all incident edges of deleted endpoints | M. Native refs select retention, not scientific validity |
| No-session default Improve / direct default Memify, tested profile | Captured graph nodes unchanged | Captured graph edges unchanged; Triplet vectors indexed/refreshed | M; does not cover every session/opt-in stage |
| Contradiction / functional temporal Tasks | Not a general node-deletion pass | Add contradiction edges or tag superseded assertions in touched neighborhoods | S optional profiles |
| Entity consolidation | Rebuilds selected canonical Entity; physically deletes duplicate nodes | Creates repointed edges on canonical IDs, then detach-deletes duplicates' old edges | S optional pipeline, not default Memify; not run in lab probes; reference/native-provenance continuity unresolved |
| Global-context rebuild | Deletes old context bucket/summary nodes and associated vectors | Rebuilds index topology; bucket deletion detaches incident edges | S opt-in Improve profile |
| Preference maintenance / feedback / truth-state profiles | Selected special-purpose field/state writes | Preference maintenance can remove prefers edges; feedback updates edge weights | S; selection/configuration is stage-specific |
| Code / DLT Cognify routes | Can retire stale source-derived nodes | Can retire stale edges or delete source memory before re-emission | S specialized routes; separate from standard text extraction |
| Failed Cognify / startup recovery rollback | Removes run-owned artifacts according to rollback/provenance plan | Removes run-owned edges and relationships incident to deleted nodes | S failure/recovery profiles; not a general restoration of prior field values |
| Version migrations | Can create nodes under new IDs and delete recognized old identities | Remap endpoints and derived reference/index state | S version/storage-dependent; no dedicated lab migration probe |
| Skill deletion / graph prune or reset | Explicit selected deletion or store clearing | Incident edges cascade or graph is cleared | S administrative/specialized profiles; outside the normal construction tests |
| Recall/Search controls | Captured graph and native provenance unchanged | Captured graph relationships unchanged | M specified read profiles only; history/session/index bookkeeping still occurs |

#### Three meanings of rename

1. **Stored-name change with fixed ID:** the batch upsert writes `n.name = node.name` on match. Supplying an existing ID with a different name can change the stored label without changing edge endpoint IDs. This capability is source-inspected, not a dedicated rename experiment; affected text/index representations need a declared refresh contract.
2. **Changed identity input:** a name-based model derives a new ID when the revised name changes the normalized identity value. Persistence then writes a different node; it does not automatically remove the prior node or migrate its relationships. Identity normalization can also make distinct display spellings share an ID, so changed spelling alone does not prove changed identity.
3. **Identity remapping/merging:** migrations and explicit consolidation can create/repoint/delete graph structures. The namespace migration recognizes particular old ID schemes and rekeys associated stores; consolidation maps duplicate nodes to selected canonicals. They have distinct selectors and cannot be covered by a blanket promise that all native operations are non-destructive.

The earlier high-level summary did not highlight optional destructive consolidation and migration rekeying. They are now explicit source-inspected profiles. Their available implementation is not evidence that the project has enabled or accepted them. Existing non-destructive identity policy and operation support decisions still govern their use.

**Requirements record:** `cognee_stage5_4_5_requirements_review.md` separates user-accepted principles from proposed revised wording, records the operation contract register, and leaves review items 3–10 pending. These requirements are design work; no enforcement, preservation wrapper, reindexing repair, consolidation, or rename implementation is claimed.

## 4. What default Improve actually does

“Default Improve” needs an explicit call profile.

For a call like:

```python
await cognee.improve(dataset="helios_stage2")
```

with no session IDs, custom Tasks, or opt-in flags:

| Stage | Gate / scope | Mutation implications |
|---|---|---|
| feedback_weights | Skipped: no session IDs | No feedback update from this stage in this profile |
| persist_session_qa | Skipped: no session IDs | No session-derived construction |
| persist_agent_traces | Skipped: no session IDs | No trace-derived construction |
| extract_agent_context | Skipped: no session IDs | No profile-lesson extraction |
| distill_sessions | Skipped: no session IDs | No session-learning construction |
| update_user_preferences | Skipped: no session IDs | No preference-subgraph changes |
| build_truth_subspace | Session-gated and opt-in | No truth-state construction |
| triplet_enrichment | Config/watermark dependent | Reads graph triplets; writes vector indexes |
| global_context_index | Opt-in, off by default | No global summaries by default |

This profile was first established by source inspection and is now measured for the no-session, no-opt-in clone call above. The broader stage descriptions remain source-inspected. Stage gates can fail open; operation logging, initialization, and error handling are separate from domain-graph mutation.

### 4.1 Default triplet enrichment is not semantic-layer-only

The default pair is:
1. `get_triplet_datapoints`.
2. `index_data_points`.

Ladybug's triplet query enumerates graph edges without an Entity-only or project-layer restriction.

The triplet processor excludes internal-marked endpoints and skips empty embeddable content; it does **not** exclude `IdentityResolution`, `AbbreviationObservation`, `Mention`, DefinitionSummary, or `graph_layer="support"` as such.

Embeddable text comes from loaded DataPoint classes' index fields plus relationship text. The type-to-field map depends on classes loaded into the process, not simply on metadata found on each stored node. Relationship `edge_text` can keep a support triplet eligible even if the custom class is not loaded.

**Offline function check:** the inspected upstream pure text-construction functions were run against the embedded graph, under two hypothetical field maps (project types available versus omitted). All 761 exported edges passed in both scenarios, including all 62 support-incident edges. The later public Improve clone experiment confirms persistence of those 761 triplet vectors, including all 62 support-incident relationships. Post-enrichment retrieval inclusion remains untested.

Direct marking as `is_internal` is an available native exclusion mechanism, but it also affects other retrieval/projection paths. Whether that is appropriate for project provenance objects remains a design decision; do not apply it yet.

### 4.2 Direct writes may not invalidate the enrichment watermark

The default Improve change check reads recognized completed pipeline runs; it does not compare graph contents.

A manual adapter write outside a recognized pipeline may therefore fail to trigger default re-enrichment after a previous watermark. Custom Memify Tasks bypass the ordinary default-work watermark, but that does not automatically rebuild all indexes after their own writes.

The architecture needs an explicit index-maintenance contract.

### 4.3 Task-list empty values do not mean “disable”

In `memify()`, unresolved/empty extraction or enrichment lists fall back to defaults independently.

For example, supplying `enrichment_tasks=[]` does not by itself suppress default enrichment. An isolated custom no-op probe must specify both intended Task stages and inputs explicitly rather than rely on empty lists.

Default Improve passes a nonempty sentinel to avoid unnecessary full-graph projection for its own streaming triplet path. Custom Tasks can receive a projected graph, but a Task that independently reads the engine is not confined by that input projection.

## 5. Other Improve profiles can mutate broader structures

| Enabled behavior | Selection mechanism | Actual implemented writes / relevance |
|---|---|---|
| Feedback weights | Node/edge IDs recorded as used by rated session answers | Updates `feedback_weight`; setters do not enforce semantic Entity-only selection. Project objects can be affected if their IDs are included |
| Session-QA persistence | Unpersisted session windows | Add + Cognify into the dataset; overlapping native Entity writes are possible |
| Trace persistence | Unpersisted trace windows | Add + Cognify into the dataset |
| Agent-context extraction | Eligible trace/session windows | Agent-profile lesson updates; session/profile path, not arbitrary identity reconciliation |
| Session distillation | Gated session guidance | Generates learning documents and calls Add + Cognify |
| User preferences | Rated turns and used node IDs | Creates/patches preference state, adds/removes `prefers` edges to used nodes; not a blanket rewrite of target semantic properties |
| Truth subspace | Session-learning anchors; all DocumentChunk nodes for projection | Writes chunk truth-state fields and vector centroids; support types are not its projection targets |
| Global context | TextSummary / GlobalContextSummary; Entity connectivity for graph bucketing | Creates/updates summaries and structural index edges; can delete old bucket nodes/vectors during rebuild |

The global-context input loader is type-selective. DefinitionSummary is not selected merely because its name contains “Summary.” Dataset-level global-context artifacts use an explicit synthetic data anchor; this is an implemented example of derived-state provenance different from source-document ownership.

Custom Tasks remain capable of explicitly modifying any selected graph object through supported writes. The logical three-layer architecture is not a native access-control boundary.

## 6. Correction to the earlier Cognify caller inventory

The earlier inventory was incomplete. In addition to standard Remember, full-rebuild Update, direct SDK, HTTP and CLI calls, pinned 1.6.2 contains real internal callers in:

- `tasks/memify/cognify_session.py`.
- `tasks/memify/cognify_agent_trace_feedback.py`.
- `modules/session_distillation/distill.py`.
- `api/v1/sync/sync.py`.
- `modules/integrations/slack/history.py`.
- `api/v1/responses/dispatch_function.py`.

Session/trace/distillation paths are especially relevant because Improve can initiate them.

**Consequence for lifecycle B:** placing the seam in core Cognify still intercepts its construction when configured, but a per-call transform passed only by Remember/Update will not be supplied by these other callers automatically.

Before implementation choose whether:
- project customization is caller-supplied and unsupported callers explicitly remain native;
- a dataset/project transform is resolved centrally inside Cognify;
- session-derived or integration content is kept in separate datasets.

This is an open coverage/configuration decision, not a reason to abandon the core Task-list seam.

## 7. Update and deletion: implemented ownership mechanics

Native incremental Update:
- builds fresh chunks through its own extraction/summarization path;
- persists with a PipelineContext;
- retires replaced chunk ownership;
- rehydrates or repositions surviving chunks;
- bypasses core Cognify.

Fresh native extraction can upsert shared Entities and their properties. Project changes to arbitrary construction Tasks still require the proposed full-rebuild rule until an explicit incremental contract exists.

On graph-provenance-enabled storage, native document/chunk deletion selects artifacts by native source refs, not by arbitrary `source_document_id` properties or support-link traversal. Multiple owners preserve an artifact until its last owner is removed. Vector cleanup uses known node index fields and edge/triplet identities.

Important limits:
- an unstamped helper is not automatically discovered solely through its scalar source ID;
- deleting an owned semantic/source node can detach its incident project edges, even if those edges were not directly selected by source ref;
- a surviving helper can consequently retain stale IDs or lose topology;
- source-ref cleanup is not project truth maintenance or automatic recomputation of a shared identity decision;
- full-rebuild Update needs explicit maintenance replay;
- dataset-wide behavior also depends on provenance mode, ownership scope, and storage isolation.

Public Forget and both Update profiles now confirm these mechanisms for the lab's present unstamped/shared structures. The measured Update runs additionally distinguish true chunk preservation from recreation, confirm the custom-model rebuild gate, and expose incremental evidence maintenance gaps. Maintenance replay and index repair were not implemented/tested in these legacy-helper probes. Later Stage-6 captured source/identity rebuild and cleanup fixtures are recorded separately; they do not establish repair of this historical helper graph.

## 8. Consolidated operation × artifact matrix

Legend: **O** uploaded-artifact observation; **S** source-inspected; **M** measured runtime; **P** pending live verification. This table describes mutation mechanisms, not desired ownership.

| Operation/profile | Semantic objects | Reconciliation/support | Source/context | Index/provenance state |
|---|---|---|---|---|
| Overlapping Cognify | O: 30 Entity property rewrites; identity links survived | O: no changed/removed existing support objects in delta | O: additional source structures | M: post-ingest native refs/vectors/evidence captured; no pre-ingest storage comparison |
| DataPoint persistence | M: same-ID property replacement; prior relations retained | M: same primitive on custom Claim/Measurement/Evidence types | M: scalar source ID can be replaced while native owner persists | M: field/Triplet rows persisted; native ownership requires concrete source context |
| Dataset-only default Improve | M: no graph property changes in tested profile | M: all 62 support-incident triplets indexed; graph helpers unchanged | M: shared graph includes DOC01-only edges despite DOC02 dataset call | M: 761 Triplet vectors present; repeat/direct-patch calls skipped; operation records added |
| Optional consolidation / migrations | S: canonical reconstruction, duplicate deletion, or recognized ID rekeying | S: incident project links may be repointed or detached | S: specialized selection and reference migration rules | S: derived/reference/native-ownership continuity must be established per profile; no lab runtime probe |
| Session-enabled Improve | S: nested Cognify and feedback mutations possible | S: feedback by used IDs; arbitrary support rewrite not blanket behavior | S: session-derived sources; optional truth/global context | S: weights, preferences, session/run metadata, indexes |
| Direct default / empty-list Memify | M: captured semantic graph unchanged | M: graph helpers unchanged; their triplet indexes refreshed as part of all 761 records | M: supplied synthetic input did not confine native graph reads | M: repeats refreshed all Triplet records despite prior Improve completion; other indexes/evidence unchanged |
| Explicit no-op Memify Tasks | M: unchanged | M: unchanged | M: synthetic input passed unchanged through both Tasks | M: captured vectors/evidence unchanged; started/completed pipeline rows still added |
| Custom Memify Tasks | M: explicit Claim patch, full upsert, revision/status writes | M: nested Measurement/Evidence and supersession topology persisted; traversal co-owns old subtree | M: raw-input ctx unanchored; explicitly bound Data row stamps document refs | M: fixture field/Triplet coverage and last-owner cleanup; no automatic relational evidence |
| Default-model incremental Update | M: 30 existing node property changes; chunk-scoped ownership updated | M: 35 helpers unchanged, ten stale chunk refs, six isolated | M: two chunks replaced, four preserved unchanged; data_id stable | M: ten orphan Triplets; 93 stale-chunk evidence rows retained; same-dataset enabled Improve missed the write and left 71 new-edge Triplets absent in the follow-up |
| Project-model full-rebuild Update | M: memory-only Forget + pinned Add + MixedKnowledgeGraph Cognify; broader rewrites | M: helpers not replayed; ten stale chunk refs, 14 isolated, 43 orphan Triplets | M: all old chunks retired; four UUIDs recreated; data_id stable | M: old source evidence swept and recaptured; Triplet rebuild disabled; P project replay/index repair |
| Full Forget(source), shared graph-native mode | M: owner-based node/edge removal and shared survival; ordinary surviving values unchanged | M: DOC01 helpers survive with stale refs, 14 isolated; DOC02 support unchanged | M: targeted data row and rebound clone-managed file copies removed | M: deleted-node vectors and source evidence removed; 43 / 2 detached-edge Triplets remain; P single-document targeted session invalidation |
| Dataset-wide Forget, full or memory-only, DOC01 | M: same 74-node/329-edge removal and shared retention in both modes | M: 35 helpers survive stale; 14 isolated; 43 orphan Triplets | M: full removes dataset/Data/files; memory-only retains them and resets both statuses | M: source evidence and attributed cached QA/QA vector swept; lifecycle registry/history retained |
| Recall/Search controls | M: ordinary graph/native provenance unchanged in all five phases | M: no graph/helper mutation; selection is lane-specific | M: requested DOC01 retrieval includes two DOC02 chunks in shared storage | M: 14 graph index collections/evidence unchanged; history/operations/session QA/vector written by profile; feedback stored without weight application |

## 9. Completed characterization and Stage 5.4.5.2 handoff

**Stage 5.4.5.1 is complete for the agreed exploration scope.** The final controls supply the missing dataset-deletion and read/bookkeeping profiles, and the operation × artifact matrix above consolidates observed, measured, source-inspected, and pending evidence. Completion does not mean every Cognee branch/backend/configuration has a live test, or that any repair has been implemented.

### The resulting operational contract

| Established behavior | Evidence and consequence for ownership design |
|---|---|
| Same-ID persistence replaces semantic properties; patches merge | M: adapter and custom Task fixtures; O: overlapping-ingest Entity rewrites. Native ownership survives a context-free upsert, while project semantic fields can be overwritten. |
| Relationship retention differs from property replacement | M: a fresh Claim with no populated nested relations retains its previously stored edges. Full object upsert is not a full neighborhood replacement. |
| Source grounding requires an actual data anchor | M: run/dataset ctx with raw dict is unowned; explicitly bound Data ctx stamps the entire written graph walk. Scalar source IDs are not deletion ownership. |
| Ownership, source attribution, and version history are separate | M: recursive supersession write co-owns the old subtree; source removal does not restore values; typed Evidence nodes do not create backend edge-evidence rows. Scientific support evaluation is deferred. |
| Default maintenance has broad index scope | M: no-session Improve indexes all 761 shared graph relationships including support; default/empty-list Memify refreshes them. S: session/opt-in Improve has distinct selectors/write paths. |
| Update construction routes are materially different | M: eligible default-model incremental path preserves four chunks and bypasses core Cognify; project-model profile rebuilds through Cognify. Project maintenance is not automatically replayed. |
| Native graph cleanup follows owners, not project dependency meaning | M: first owner removal preserves shared artifacts; last owner removes them; unowned project helpers persist with stale refs. Dataset-wide deletion has the same limitation. |
| Index/evidence maintenance has independent failure modes | M: 43 detached-edge orphan Triplets; incremental stale evidence; same-dataset Improve gate misses an incremental write and leaves 71 new-edge Triplets absent in the follow-up. A successful rebuild does not prune old orphans. |
| Read operations have durable side effects | M: graph/index/evidence unchanged in tested profiles, while history/operation rows, session QA and QA vectors are written. Feedback storage does not apply graph weights. |
| Dataset attribution does not establish read/write isolation | M: shared-store Improve includes other-dataset edges; DOC01-requested retrieval includes two DOC02 chunks. Response/history labels must not substitute for artifact provenance. |

### Concrete decisions handed to 5.4.5.2 and later substages

1. Assign a creator and mutable authority for every semantic, identity/support, source/context, native ownership, assertion-evidence, graph-index, and session-derived artifact. Define how project fields survive native full upserts.
2. Distinguish per-source observations from shared derived decisions. Specify native document/chunk refs, direct-write attachment rules, dependency/evidence links, and shared last-support behavior separately.
3. Define reference-versus-write semantics for nested DataPoints and operational source/version identity so traversal does not silently rewrite or restamp referenced state. The scientific Claim/Measurement/Evidence identity, revision and justification model remains Stage 8 work.
4. Assign ownership for index invalidation and rebuilding, including direct writes, incremental pipeline visibility, support-index selection, detached-edge orphan detection, and evidence retirement/re-capture.
5. Define maintenance replay after rebuild and support invalidation after update/deletion. Idempotence, failure/status reporting, and usable-state checks belong in the lifecycle/invariant design.
6. Decide how dataset/project scope is enforced in the chosen deployment: physical/context isolation, source-aware selectors, and evidence attribution must agree with intended retrieval semantics.
7. Treat cached QA, session vectors, lifecycle records, query/result history, and operation records as distinct artifact classes with explicit retention/invalidation contracts.

These were the characterization's design inputs. The 2026-10-13 companion proposal now records initial .2–.3 choices and a preliminary ownership matrix, without declaring their deliverables final or implementing repairs. .4 specifies operation lifecycle; .5 finalizes invariants and the Stage-6 handoff.

### Explicit runtime boundaries

- Tested runtime: Cognee 1.6.2, Ladybug/LanceDB/SQLite, access control disabled, two documents in different datasets sharing physical graph storage. Probe paths/configuration are guarded; original source-file hashes remain unchanged.
- Dataset-wide deletion was tested for DOC01's one-document dataset, in full and memory-only modes. Shared cross-dataset artifacts and one seeded attributed session per dataset were included.
- Read controls use CHUNKS and pinned RAG_COMPLETION, a fresh explicit session, automatic feedback off, last-access tracking off, and one explicit synthetic feedback update.
- Session-enabled/opt-in Improve stages, global-context rebuilding, automatic feedback analysis, last-access tracking enabled, single-document contamination-chain invalidation, every retrieval lane, other backends, and access-control-enabled isolation remain source-inspected or untested as labeled.
- Scientific classes are minimal fixtures. Production Claim/Measurement/Evidence modeling, ontology reasoning, immutable history, general contradiction handling, and project identity reconciliation are later work.
- At this characterization checkpoint, no indexed-text direct invalidation or cleanup/replay/index/evidence repair was implemented. Later Stage-6 bounded rebuild/retirement results are separate; general repairs and the preferred Cognify B extension remain incomplete. The diagnostic default-model incremental profile does not replace the lab's project-model construction.
- Captures are sequential and targeted, not transactional full-store inventories. Graph-associated ID reads deliberately use pre-deletion scopes to avoid hiding deleted-node/edge leftovers; fixture/session probes track all IDs they observed.

### Evidence inventory

| Evidence group | Uploaded runtime/artifact files |
|---|---|
| Graph, ingest, retrieval context | stage5_graph.html; stage5_4_doc02_delta.json; stage5_4_native_retrieval_probe.json; stage5_4_5_before.json |
| Adapter and storage baseline | results.json; stage5_4_5_storage_before.json |
| Improve and direct Memify | improve_results.json; storage_after.json; memify_results.json |
| Source deletion and Update | forget_results.json; update_results.json; watermark_results.json |
| Custom scientific/source-context fixture | custom_results.json |
| Dataset deletion and read/bookkeeping closure | controls_results.json |

Pinned upstream source and locally checked probe orchestration support interpretation; actual database/provider behavior comes from the user's uploaded runs. No additional 5.4.5.1 experiment is required before moving to the ownership/provenance design.

## Review clarification — Triplet retrieval, ownership, and watermarks (2026-10-12)

This clarification is based on pinned-source inspection and the existing uploaded experiments. No new runtime experiment was performed, and 5.4.5.1's completed status is unchanged.

### Triplet representations and routing

- S: a graph triplet is one source/relationship/target combination. The index-only Triplet DataPoint contains a deterministic ID, endpoint IDs, and assembled text; its normal vector collection is Triplet_text.
- S: graph persistence can build batch-local Triplets through add_data_points(embed_triplets=True); standard Cognify passes its triplet_embedding configuration. Default Memify/Improve can stream eligible graph relationships afterward; explicit create_triplet_embeddings supplies its own extraction and indexing Tasks. Building vectors does not select a retrieval mode.
- S: the built-in search factory maps TripletRetriever only to TRIPLET_COMPLETION. The generic session-completion wrapper supports that already selected class, rather than independently selecting it. No other built-in invoking composition was found in the pinned production code.
- S: search defaults to HYBRID_COMPLETION. Recall's rule-based router does not select TRIPLET_COMPLETION and falls back to hybrid. Explicit FEELING_LUCKY uses a separate LLM selector whose validation accepts the enum, although its bundled prompt does not advertise it. Explicit SDK/API selection or custom application use remains possible.
- S: TripletRetriever searches Triplet_text and constructs context from stored payload text without checking each underlying edge's current existence. Stored orphan rows can therefore remain search candidates; the experiments did not establish that a particular query returned them.
- S: native HybridRetriever searches chunks, Entity_name and EdgeType_relationship_name, then obtains Entity neighborhoods; it does not invoke TripletRetriever or search Triplet_text as its dedicated relationship lane.
- S: GraphCompletionRetriever discovers collections from loaded DataPoint subclasses and can therefore query Triplet_text. However, its node-distance mapper matches result IDs to graph node IDs; ordinary Triplet IDs identify relationship representations, and the path does not use their from_node_id/to_node_id payloads to score the endpoints or edge. Collection discovery alone does not establish useful Triplet-vector integration. Runtime impact of this mismatch remains untested.
- S: TripletSearchContextProvider uses graph relationship ranking through brute_force_triplet_search; its name does not imply use of TripletRetriever.
- M scope: the Stage-5.4 native retrieval probe used RAG, graph and hybrid completion; the closure controls used CHUNKS/RAG_COMPLETION. Neither evaluated TRIPLET_COMPLETION answer quality or alias recall.

### Entity resolution and indexed names

- S: the native Entity indexes its name field. Triplet text assembly consumes selected endpoint fields and relationship text; it does not walk resolves_to or project IdentityResolution records to collect alternate names.
- Existing lab policy: reusable canonical/variant forms are distinct from historical occurrence-specific mentions. Document-local abbreviations and generic descriptions must not become universal aliases merely through previous resolution.
- Open design options: resolve queries before retrieval, index scoped aliases pointing to canonical Entity IDs, and/or augment Triplet endpoint text with applicable reusable forms. Query-time resolution was suggested as a foundation, with alias-expanded Triplet text conditional on adopting that retrieval path; this is a design suggestion, not an accepted requirement or implementation.
- If alias-expanded Triplet text is later adopted, changing an applicable alias creates an index dependency on affected incident Triplets. Existing lifecycle requirements would cover that chosen representation; no mandate to expand every Triplet with every name is added.

### Native ownership and watermark clarification

- S/M: source references govern retention in the lab's graph-provenance mode. Document-scoped keys identify dataset/Data; chunk-scoped keys additionally identify a chunk. Their v1/v2 format labels are scope formats, not source-content revisions. Source/run attachments separately support rollback attribution. Other profiles may use a relational ledger.
- M: removing one owner retained shared artifacts, removing the last anchored owner deleted them, and ordinary properties were not rolled back. Unowned helpers and scalar references were not automatically discovered as dependencies; endpoint deletion could detach additional relationships.
- S: the default unscoped Improve Triplet stage derives a dataset watermark from a successful operation's triplet_enrichment run_info stamp. It compares recognized completed writer runs' created_at with the stamped stage start time, excluding that operation's own child runs. No usable stamp or an indeterminate check causes enrichment to run; custom Tasks or node_name scope bypass this default gate.
- S: this gate reads pipeline history, not graph content, index coverage, or fingerprints. The recognized-writer list omits incremental_update_pipeline, despite incremental Update using that run-record name. Direct graph writes or writes recorded only for another dataset are not inherently detected for the checked dataset.
- M: the incremental follow-up returned already_completed/no_writes_since_last_improve and left 71 new-edge Triplets missing. Direct default Memify bypassed the Improve watermark and refreshed records. The earlier direct sentinel patch demonstrated a missed graph-write signal, but the sentinel was not an indexed field, so that experiment did not itself establish a stale embedding.
- These mechanisms establish retention and work-avoidance behavior, not scientific support or a complete graph/index consistency guarantee.

## Representation seam clarification — source-inspected, 2026-10-13

These observations motivate the new proposal; they are not additional measured probe outcomes.

| Mechanism | Source-inspected behavior | Design consequence |
|---|---|---|
| Explicit Entity UUID | DataPoint.__init__ derives identity fields only when no id was supplied | Two Entities named "the controller" can use distinct occurrence UUIDs; ordinary name-derived identity need not collapse them |
| Existing lab mention IDs | stage5_entity_layer.py constructs UUID5 occurrence IDs and passes id to Entity | The ID mechanism is already represented in committed code; replacing role fields with marker edges remains new work |
| calculate_chunk_graphs | Standard text extraction can invoke a supplied sync/async callback, then integrate its returned graphs | Compute exact identity intent, but do not mistake generic graph conversion for reference-only persistence |
| Generic graph integration | Endpoints must be represented in the returned graph; generic node identifiers are not arbitrary stored Entity UUID references | Returning an existing Entity can cause an upsert; absent graph endpoints can skip edges |
| add_data_points custom_edges | ID tuples can be written while omitting an existing target DataPoint; ctx binds custom edge ownership at document level | Use a source-bound custom loading Task; verify endpoints exist and edge/refs persist |
| attach_node_source_refs | Attaches retention refs to matched existing node IDs separately from ordinary property replacement | Intentional generated-source ownership can retain existing endpoints without rewriting fields |
| Ladybug edge upsert | MERGE by source, relationship_name and target; ON MATCH replaces serialized ordinary properties | Contribution arrays are project-maintained; native provenance folding does not merge applicability records |

Default custom-edge publication does not automatically create chunk-to-edge evidence. Owning a relationship does not own its endpoints. Original-source Forget does not automatically retire a separate generated identity Data source. Full rebuild can delete solely owned endpoints before recreating them; exact lifecycle/read eligibility must be specified.

Source-only compatibility limits remain: generic conversion is not a reference-only loader, callback routing is not automatically replayed by native Update, optional consolidation may merge/remap occurrence Entities, and native retrieval/triplet text does not enforce the proposed identity traversal. The preferred B task-transform extension remains unimplemented.

**Targeted follow-ups:** new-node → existing-node and edge-only publication; marker/explicit UUID replay; contribution property round-trip/withdrawal; endpoint-only retention; original/generated-source Update/Forget; failure/retry; selected index readers. These are design-dependent checks within .4/Stage 6, not a claim that the new form is already tested.

## Source anchors

Pinned source inspected in this pass:

- [Graph interface and upsert contract](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/graph/graph_db_interface.py)
- [Ladybug write/read implementations](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/graph/ladybug/adapter.py)
- [DataPoint persistence](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/storage/add_data_points.py)
- [Chunk ownership](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/storage/chunk_ownership.py)
- [Improve stage gates](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/stage.py)
- [Improve stages](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/stages.py)
- [Enrichment watermark](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/graph_changes.py)
- [Memify](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/memify/memify.py)
- [Default Memify Tasks](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/memify_pipelines/memify_default_tasks.py)
- [Triplet selector](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/memify/get_triplet_datapoints.py)
- [Internal-node marker](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/engine/models/InternalDataPoint.py)
- [Ownership deletion planner](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/unified/provenance_delete_planner.py)
- [Relational edge-evidence capture](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/provenance/edge_evidence/capture.py)
Additional pinned source paths supporting the closure controls:

- [Public Forget profiles](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/forget/forget.py)
- [Dataset-wide deletion](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/datasets/datasets.py)
- [Public Recall](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/recall/recall.py)
- [Search history](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/search/operations/log_search_history.py)
- [Session QA and feedback](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/session/session_manager.py)
- [Session QA vectors](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/session/session_embeddings.py)
- [Session invalidation](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/session_lifecycle/invalidate_sessions.py)
Review clarification source anchors:

- [Existing extracted-edge selection and ownership](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/graph/utils/retrieve_existing_edges.py)
- [New edge attachment](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/graph/utils/expand_with_nodes_and_edges.py)
- [Optional entity consolidation](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/memify/consolidate_entities.py)
- [Default Memify Task selection](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/memify_pipelines/memify_default_tasks.py)
- [Migration identity remapping](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/migrations/versions/namespace_entity_type_node_ids.py)
- [Cognify rollback](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/cognify/rollback.py)
Source anchors for the Triplet-routing clarification:

- [Retriever factory](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/search/methods/get_search_type_retriever_instance.py)
- [Recall query router](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/recall/query_router.py)
- [TripletRetriever](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/retrieval/triplet_retriever.py)
- [Graph collection discovery](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/retrieval/graph_completion_retriever.py)
- [Graph ID distance mapping](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/graph/cognee_graph/CogneeGraph.py)
- [Hybrid retrieval](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/retrieval/hybrid_retriever.py)
- [Native Entity indexed fields](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/engine/models/Entity.py)
- [Improve watermark implementation](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/graph_changes.py)
- [Incremental Update run naming](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/update/incremental.py)
