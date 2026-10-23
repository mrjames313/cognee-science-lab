# Integration design snapshot, 2026-10-23

**Date:** 2026-10-23. **Status:** a discussion snapshot, not a decision record. The user and the assistant held the discussion on 2026-10-22 and 2026-10-23. The assistant wrote this document. **Code baseline:** `main` at `012d8a6` (Checkpoint H, dependencies). Another agent was changing identity code on branch `one-admission` at the time, so some code facts below may change.

This snapshot records the design discussion about reworking [the integration playbook](../results/cognee_knowledge_integration_playbook.md) into general integration principles. It uses a new framing of activities and procedures. The other project documents still use the older Describe, Publish, Maintain and Retrieve framing. They were deliberately left unchanged. The user and the assistant will revisit this snapshot once the current code work ends, and use the lessons from that code to shape the rewrite.

Evidence labels used below:

- **Measured.** The assistant ran it on the user's Mac on 2026-10-22, with loopback embeddings, in a scratch fixture root outside the repository.
- **Code.** Read from the source at the baseline commit, or from the pinned Cognee 1.6.2 source in `.venv`. A path is given.
- **Docs.** Taken from a project document. A path is given.
- **Inferred** or **guess.** Reasoning that nothing has checked.
- **Decided** marks a point the user agreed to. **Proposed** marks an assistant recommendation that the user has not accepted yet. **Open** marks a question nobody has settled.

## 1. The integration class

The user wants the principles to apply to any integration with four parts.

1. **External knowledge** is brought into Cognee. It is usually not in graph form yet.
2. **Procedures** manage how that knowledge is applied to the Cognee sources.
3. **An overlay** is a supplementary subgraph that is overlaid on, or linked to, the source-backed **native graph**.
4. **Retrieval procedures** take the overlay into account.

The principles will be tested against four integrations (decided):

| Integration | Status | Shape |
|---|---|---|
| Identity | Built through Checkpoint H | Reviewer judgments about corpus mentions, published as mention Entities and `resolves_to` edges |
| Scientific measurements | Next. Dry run only (section 10) | Records from instruments or papers, linked to Cognee instrument and sample Entities, plus retrievable knowledge about each physical quantity |
| LLM wiki | After measurements. Dry run only (section 10) | Structured markdown pages that an LLM writes from investigations and experiments. The pages are Cognee sources, with structured processing on top. They are not external knowledge. |
| Scientific or engineering knowledge layer | After the wiki. Not discussed yet | Knowledge loaded from a textbook, for example |

## 2. How the snapshot was made

1. The assistant read the playbook in full. Four read-only survey agents read about 10,000 lines of the other project documents (the roadmap and Stage 4, the extension reference and requirements review, Stages 1 to 3 and 5, and the Stage-6 contract and representation proposal). Section 11 summarizes what they found.
2. The user and the assistant built the ownership model, the vocabulary and the activity model in discussion (sections 3 to 9).
3. The assistant checked claims against the identity code and the pinned Cognee source as the discussion went. One correction came from the user. The assistant had called `retrieve.py` the project's retrieval path. Its docstring says it is a fixture probe (section 9). The lesson, now a working rule, is to read a module's docstring and find its callers before describing what it is for.
4. The assistant built one scratch multi-source fixture root (`multi-fixture --embedding loopback`) and listed its stores with a read-only script. Section 6 gives the results.

## 3. Vocabulary

Decided: use Cognee's own class and table names for native products, so a reader can search the code for them. Use "overlay" for the supplementary subgraph and "native graph" for the source-backed graph. "Ledger" names the container, the publication table. "Publication state" names its eligibility part.

### Native products (Cognee 1.6.2)

| Name | What it is | Identity example |
|---|---|---|
| Dataset | A `datasets` row. A named collection of Data items. Each Data item belongs to exactly one dataset through the `dataset_id` column on `data` (measured). Pipelines, search, permissions and identity's ledger keys all work per dataset. | `stage6_isolated_fixture` |
| Data item | A `data` row that registers one input | doc01, the generated identity source |
| Raw content | The bytes stored at the Data item's `raw_data_location` | doc01's text |
| Document node | A `TextDocument` graph node. It has the same UUID as its Data item (code, `classify_documents.py:169`). | doc01's document |
| Chunk | A `DocumentChunk` graph node. Its text is also embedded. Its ID is derived from its content. | doc01's chunks |
| Summary | A `TextSummary` node | None in the fixture |
| Entity | An `Entity` node, typed by an `EntityType` node. Its ID is derived from its normalized name (`identity_fields=["name"]`). | "Helios controller", "HC" |
| Other node types | `NodeSet` | |
| Edge | A graph relationship with a property bag | `limits` |
| Source reference | Native ownership metadata on a node or edge (`source_ref_keys` and related fields). Native deletion follows it. | A chunk owns a fact edge |
| Vector entry | One row in a vector collection. The collections are `Entity_name`, `EntityType_name`, `DocumentChunk_text`, `TextSummary_text`, `TextDocument_name`, `EdgeType_relationship_name` and `Triplet_text`. | An `Entity_name` row |
| Edge evidence | A `provenance_edge_evidence` row. It records which chunk and Data item produced an edge. | 8 rows in the fixture (measured) |
| Pipeline status | `pipeline_runs` and `task_runs` rows. Update, Forget and Improve read them. | |
| Session QA cache | Cognee's store of earlier answers. Recall can reuse them. | |

The requirements review calls the Data ID and the TextDocument ID "distinct identifiers" (`results/cognee_stage5_4_5_requirements_review.md:24`). That is inaccurate. They are two objects in two stores that share one ID value. The rewrite should fix it.

### Integration products

| Name | What it is | Identity example |
|---|---|---|
| External input | Knowledge in the form it arrives from outside Cognee, stored unchanged | None. Identity has no stored external input. |
| Saved description | The authoritative, revisioned set of interpreted records | `IdentitySource` |
| Record | One unit in the saved description | A mention group, resolution or variant assignment |
| Producer | Who or what made a record: method (`rules`, `llm`, `decision_model` or `captured_fixture`), implementation, version, configuration and run | A captured describer |
| Transition plan | Saved intent for one maintenance step, kept so a crash can be completed forward | Old and new text, continuity map |
| Publication state | Per-unit state, revision, verified revision and attempt | The ledger row's state columns |
| Writer reservation | A per-dataset lock that admits one writer | `lab_identity_writers` |
| Recovery event | A diagnostic record of a failure and its recovery | `lab_identity_recovery_events` |
| Withholding | One decision withheld from retrieval because an input it read changed | `lab_identity_withholdings` |
| Generated source | Role. A Data item the integration writes, so overlay objects have an owner the integration controls. | The `identity` Data item |
| Original source | Role. A Data item whose content came from outside the integration. | doc01 |
| Overlay node, overlay edge | Graph objects whose content the integration decides | Mention Entities, `resolves_to`, markers, local facts |
| Owner attribute | A source reference the integration adds to a Cognee-owned object, without writing its fields | Retention of a resolved corpus Entity |

### What "source" means

The project uses "source" in three ways. This causes confusion.

1. In Cognee, a **source** is a Data item that graph objects are attributed to through source references.
2. The project calls a Data item an **original source** or a **generated source** depending on who wrote its content.
3. The ledger's `source` column names the **unit of publication**. In identity it happens to be the generated source's ID.

Proposed: reserve "source" for Cognee's meaning. Keep "original" and "generated" as roles of a Data item. Call the third meaning the **publication unit**.

## 4. The ownership model

Decided: classify every product into one of three classes.

| Class | Meaning | What the spec must say |
|---|---|---|
| Cognee-owned | Cognee decides the content and controls its lifecycle | Which native step creates it, which steps rewrite or delete it, and which integration products depend on it |
| Integration-owned | The integration decides the content and only integration code writes it | Schema, authority rule, revision rule and where it is stored |
| Hybrid | The integration decides the content, but it sits in a Cognee container that native operations can rewrite or delete | Who decides the content, which native operations can damage it, and the integration's guard against each one |

Refinements agreed in discussion:

- **Classify containers and attributes, not content.** The same content can sit in two containers of different classes. A class boundary can also run through one object. A Cognee-owned corpus Entity can carry one integration-owned owner attribute.
- **Integration-owned is only as safe as its container.** A Cognee whole-store operation reaches everything in a store, whoever wrote it. `prune.prune_system(metadata=True)` calls the relational adapter's `delete_database`, which removes the whole relational database (code, `SqlAlchemyAdapter.py:709`). The identity tables live in that database. The public default, `metadata=False`, wipes only the graph and vector stores, so the ledger survives but reports units as published whose graph objects no longer exist. So the rule is this. An integration-owned product changes only through integration code, plus the whole-store Cognee operations that reach its container. The spec must name those operations.
- **One container per content, unless there is a good reason** (decided). Identity keeps its saved description in two containers (section 12). The user thinks this complicates identity a fair bit, but it may help maintenance. It is a case study for later.
- **A hybrid can borrow a Cognee owner on purpose.** Identity's markers and local facts are owned by the original chunks, so native deletion of the original removes them correctly. The cost is that any native rebuild that changes chunk IDs drops them too. That is one reason identity rebuilds a whole document itself.
- **Integration-owned products often hold snapshots of Cognee-owned ones.** The saved description records text, chunk ranges and hashes. It stays valid only while the Cognee product still matches. That dependency is what change detection checks.

Ownership through source references drives most of the hybrid design. The ledger, transition plan and publication protocol drive most of the rest. The user wants that machinery reusable across integrations, not redesigned for each one (decided as a goal).

## 5. Where the integration's pieces live

### In Cognee containers (hybrid)

| Piece | Cognee container | Native owner |
|---|---|---|
| Generated source | A Data item and its raw file. Identity's are registered as `txt`, `text/plain`, though they hold JSON (measured). | Itself |
| Mention Entities, `resolves_to` edges | Graph nodes and edges, written with exact UUIDs through `add_data_points` | The generated source, which is the pipeline context at write time (code, `publish.py`) |
| Markers (`has_identity_mention`), local facts, fact evidence | Graph edges and nodes, edge evidence rows | The original chunks (borrowed) |
| Owner attribute on a corpus Entity | A source reference on a Cognee-owned node | The generated source |
| Vector entries for overlay nodes | `Entity_name` rows | Follows the node |
| Shared vector entries | `EdgeType_relationship_name` rows keyed by text. One entry can serve both a native edge and an overlay edge (measured, section 6). | Follows the sharing |

### In new tables inside Cognee's relational database (integration-owned)

| Table | Holds | Code |
|---|---|---|
| `lab_identity_publications` (the ledger) | Key (dataset, source). Columns `revision`, `verified_revision`, `state`, `attempt`, `description` (the saved description, full JSON) and `plan` (the transition plan, JSON). | `storage.py`, class `Publication` |
| `lab_identity_writers` | One writer reservation per dataset (`owner`) | `storage.py`, class `Writer` |
| `lab_identity_recovery_events` | Failure and recovery diagnostics per dataset, source and attempt | `storage.py`, class `RecoveryEvent` |
| `lab_identity_withholdings` | One row per withheld decision and input. Key (dataset, dependent source, assignment, input key), with the edited source and revision, reason, status (`remap` or `refresh_needed`), old and new digests, and the new range of a moved span. | `withholding.py`. Added in Checkpoint H (docs, `docs/stage6_identity_dependencies.md`). |

Ledger states are `pending`, `current`, `failed`, `withdrawn` and `forgotten` (code, `storage.py`). A unit is eligible for retrieval only when its state is `current` and its revision equals its verified revision. Since Checkpoint H, eligibility also works per decision. A withholding, or a pending or failed text change of a consumed document, withholds the decisions that read it.

All four tables are reachable by `prune_system(metadata=True)` (inferred from the prune code path above, not run).

### Possible future stores (open)

- A single backend database for all measurement records, holding singletons, tables and so on. The user called this very preliminary.
- A wiki section map and section continuity map.
- Wiki page provenance (which investigation produced a page, and with what inputs).

## 6. Identity inventory (measured)

The assistant built a multi-source fixture root (two documents) and listed its stores. The single-document fixture is the same minus the `02` items.

**Data items.** One dataset, five Data items.

| Data item | Role | Content | Chunked and in the graph | Owns natively |
|---|---|---|---|---|
| `source` | Original source (doc01) | Fixture text | Yes. A document node and chunks. | Its chunks, the markers and local facts on them, the `oscillations` fact endpoint |
| `source02` | Original source (doc02) | Fixture text | Yes | The same, for doc02 |
| `seed` | Original source standing in for the corpus | One sentence | No document node or chunks | The corpus Entity "Helios controller" |
| `identity` | Generated source for doc01 | `IdentitySource` JSON | No, chunkless by design | Mention Entities, `resolves_to` edges, retention of the corpus Entity |
| `identity02` | Generated source for doc02 | `IdentitySource` JSON | No | The same, for doc02 |

**Vector store.** Four collections, 17 entries.

| Collection | Entries | Contents |
|---|---|---|
| `TextDocument_name` | 2 | The two original documents |
| `DocumentChunk_text` | 2 | One chunk per original document |
| `Entity_name` | 10 | "Helios controller" (corpus), "oscillations" (fact endpoint), "HC" (reusable variant), "The controller; it" (one mention per document), and the multi-source records "Shared calibrator", "doc01 instrument", "doc02 instrument" and "local reference" (one per document) |
| `EdgeType_relationship_name` | 3 | Two "chunk is part of document" entries, and one "it limits oscillations" entry shared by both documents' local facts, because the key is the text |

Measured absences:

- No `TextSummary_text` or `Triplet_text` entries, because nothing ran `cognify`.
- No vector entries for the generated sources.
- No vector entries for overlay edges. `resolves_to` and `has_identity_mention` exist only in the graph. Native vector search can find mention Entities by name, but reaches overlay edges only through graph expansion.

**The fixture never runs `cognify`.** It chunks the originals itself with Cognee's `TextChunker`, writes the chunks with `add_data_points`, writes the corpus Entity under the `seed` Data item and writes the captured facts itself (code, `fixture.py:38-60` and setup). So every product called Cognee-owned in identity is integration code standing in for `cognify`. That is fine for lifecycle tests. No identity fixture yet shows real `cognify` output and the overlay side by side.

## 7. Identity products by column

The columns are product, class, write paths, lifecycle owner, depends on and retrieval. Retrieval is one column that answers two questions (decided). Does native retrieval (`cognee.search`) read the product? Does it need custom integration handling? The native-visibility entries come from the extension reference and were not checked against a fixture (the user said a check was not needed yet).

| Product | Class | Write paths | Lifecycle owner | Depends on | Retrieval |
|---|---|---|---|---|---|
| Original Data item and raw content | Cognee | Cognee: add, update, forget, prune. Integration: text edits through `ingest_data`, identity `forget` | Cognee | | Native reads it as chunk text. Custom: evidence spans must come from the current text. |
| Chunks, document node | Cognee | Cognee: cognify, update, forget. Integration: the fixture's chunking and identity's whole-document rebuild | The original Data item | Text, chunk budget | Native reads them. Custom: only the chunk map the ledger revision recorded counts as current evidence. |
| Extracted Entities and edges, edge evidence | Cognee, plus one owner attribute on resolved targets | Cognee: cognify, update, forget, consolidate. Integration: adds the owner attribute | Chunks | Chunks | Native reads them. Custom: none beyond normal use. |
| Saved description, ledger copy | Integration (authority) | Integration. Cognee: prune with metadata | | Snapshots of the rows above, by hash | Native does not read it. Custom: open. The fixture probe reads it to interpret edges. Real retrieval might instead rely on edge contributions. |
| Saved description, Data copy | Hybrid | Integration: `write_registered`. Cognee: forget, re-add, prune | Itself | Must equal the ledger copy | Native would read it only if it were chunked and indexed. It is chunkless, so expected not read. Custom: none. |
| Publication state, writer reservation, recovery events, transition plan | Integration | Integration. Cognee: prune with metadata | | The ledger copy | Native does not read it, so native search ignores eligibility. Custom: required. Every integration reader must withhold units that are not `current` and verified. |
| Withholdings | Integration | Integration (text edits, refresh, reconfirm, replace-decision). Cognee: prune with metadata | | Digests of consumed inputs | Native does not read them. Custom: required. Withheld decisions are not served. |
| Mention Entities, `resolves_to` edges, their vectors | Hybrid | Integration: `add_data_points`, targeted delete. Cognee: forget, consolidate | The generated source | The ledger copy | Native reads them as plain Entities and relationships, uninterpreted, whatever the eligibility. Custom: required. That covers mention scoping, direction rules and not treating mention labels as aliases. |
| Markers, local facts, fact evidence | Hybrid | Integration: the publisher. Cognee: forget or rebuild of the original | The original chunks (borrowed) | The ledger copy, chunks | Native reads facts and evidence as ordinary edges, and markers as plain edges. Custom: annotate the binding and return complete evidence fragments. |

Every hybrid row says "native reads it, uninterpreted". So each hybrid product needs a decision about native visibility. The choices are to tolerate it, hide the product from native readers, or shape it so native readers handle it correctly (proposed as a decision point). Eligibility is a custom-only guarantee. Until a registered retriever exists, ordinary `cognee.search` can return structures from a unit the ledger is withholding (docs, `results/cognee_extension_architecture_reference_v1.6.2.md:906`, unchecked).

### Identity coupling: who starts each change

| Change | Initiator | Response today |
|---|---|---|
| Text edit of an original through identity (`edit-text` and the occurrence commands) | Identity | The command carries the new text, the new description and the continuity map. Identity writes the text into the original Data item, rebuilds the chunks and republishes. Demonstrated. |
| Text edit of a document another source read (Checkpoint H) | Identity | The edit withholds only the dependents' decisions that read what changed. A refresh then runs. A moved span is re-ranged automatically. Anything needing judgment becomes "refresh needed" for a reviewer. Demonstrated. |
| Identity `forget` of a source nothing depends on (Checkpoint F) | Identity | Native document deletion removes the original and the generated source and everything only they owned. The ledger row ends `forgotten`. A source with dependents is refused. Demonstrated. |
| Cognee `cognify`, `update` or `forget` on the dataset by another caller | Cognee or another caller | Readers detect drift through hashes and chunk-map checks and refuse to serve the unit. Nothing else responds. Native forget of an original leaves the generated source behind (G06). Step 5 plans to route Cognee's own deletes to identity. |
| `prune` | Cognee or another caller | Either no ledger, or a ledger that points at nothing. Not handled. |

## 8. Trade-offs behind each column

This is a first sketch. The user asked for these to be written up in full later.

| Column | Main trade-off |
|---|---|
| Container | A Cognee store gives native ownership, indexing and deletion, but whole-store operations can reach it. An outside store, such as the single measurement backend, is safe from prune but invisible to native retrieval unless something projects it. |
| Class | A hybrid gets native behaviour for free but needs a guard for each native operation that can damage it. An integration-owned product needs no guard but gets no native help. |
| Authority | Exactly one copy may decide. Every other copy is a projection that is either checked or regenerated. |
| Write paths | Every Cognee operation listed needs a guard, a detector or an accepted risk. |
| Lifecycle owner | Borrowing a Cognee owner gives correct native deletion but loses the structure on a native rebuild. A generated source survives rebuilds but must be retired explicitly. Every integration will face this choice. |
| Depends on | Hash-checked snapshots detect change cheaply but say nothing about meaning. Each dependency needs a response: block, withhold, or re-derive. Identity chose withhold-until-refreshed per decision (Checkpoint H). |
| Retrieval | Everything read at query time needs an eligibility rule. Otherwise retrieval can serve a half-updated product. Each hybrid also needs a native-visibility decision. |
| Initiator | When the integration starts a change, the change and its response share one intent. When Cognee or an author starts it, the integration needs detection, a staleness window and a response policy. |

## 9. Activities and procedures

The playbook's four activities (Describe, Publish, Maintain and Retrieve, `results/cognee_knowledge_integration_playbook.md:39-44`) fall short in five ways.

1. Maintain is a different kind of thing. The others turn some products into others. Maintain is a sequence of those activities over time, set off by a change. Every identity maintenance step writes the same products as Publish, through the same publisher.
2. Admission has no home. Identity's largest rule set, `admit` in `admission.py`, is deterministic code separate from judgment. It is proved against a small-world oracle (`support/occurrence_check.py`, 540,045 fate worlds at Checkpoint H). The playbook splits it between "save" in Describe and "validate" in Publish.
3. Nothing covers receiving external input. Identity has none, so the gap never showed.
4. Nothing covers detecting change.
5. Cognee's own activities are invisible, though their reruns are what trigger maintenance.

Proposed: separate **activities**, which transform products, from **procedures**, which sequence activities in response to a trigger. The user said the direction is right.

### Activities

| Activity | Owner | Reads | Writes | Identity code |
|---|---|---|---|---|
| Ingest | Cognee (`add`, `cognify`) | Original sources | Data items, raw content, the native graph, vector entries, edge evidence | The fixture stands in for `cognify` (section 6) |
| Import | Integration | External input | External input, stored unchanged | None |
| Describe | Integration (a reviewer, a model or rules) | Raw content, chunks and Entities, and any external input | Proposed records (transient) | The captured describers (`captured_*.py`). Automatic Describe is step 6, unbuilt. |
| Admit | Integration (common machinery) | Proposed records, the previous saved description | The saved description revision, the transition plan, publication state `pending` | `admission.py`, `replace.py` (`admit_replacement`), `storage.py` |
| Publish | Integration (common machinery, with a domain plan) | The transition plan and the saved description | The generated source, the overlay, owner attributes. It then verifies and sets publication state to `current`. | `publish.py`, `registered.py`, `stages.py` (`run_attempt`) |
| Detect | Integration | Data item hashes, chunk maps and other native state, against the fingerprints in the saved description | A change trigger, a withholding, or an unavailable unit | Read-time checks in `retrieve.py` (`valid_sources`, `live_held`). Edit-time classification in `withholding.py`. |
| Retrieve | Integration (custom), beside native retrieval | The native graph, the overlay, publication state, withholdings | Nothing the integration owns. Native search writes its own bookkeeping, such as query history and the session cache. | Only the fixture probe, `retrieve.py`. The registered retriever (step 5, M4) is unbuilt. |

Notes on the activities:

- **Import does no interpretation.** It only stores the external input unchanged, so Describe can be rerun and every record can point back to exactly what it came from. All interpretation happens in Describe. Examples are an instrument CSV, a table of measurement records, or an authoring agent's record of which investigation produced a wiki page. The user confirmed this reading and asked to keep Import as-is for now.
- **Describe reads chunks, not just "the native graph".** Identity's records cite chunk IDs and ranges, group occurrences are offsets in the raw content, and resolutions target Entity UUIDs.
- **Why Publish writes the generated source.** Identity's publisher writes or updates the generated Data item (`write_registered`) before writing the overlay objects it owns. If the generated source only needs to exist as an owner (section 12), creating it may belong to a unit's first publication only.
- **Detect is not yet a separate step in identity.** Identity detects drift that another caller caused only at read and reconcile time, and its reaction is to refuse the unit or withhold the decision. Edits identity makes itself carry their own response.

### Procedures

| Procedure | Trigger and initiator | Sequence | Identity status |
|---|---|---|---|
| Initial publication | A new source or a new import | Describe, Admit, Publish | Built |
| Change response | A changed source or input, started by the integration or detected | Detect, Describe, Admit, Publish (with retirement) | Built for changes identity starts. The path from detection to response is unbuilt for changes another caller makes. |
| Dependency response | A changed input that another unit's records read | Detect (classify each input), withhold, then refresh. Mechanical re-checks run at once. Judgment goes to a reviewer, later to Describe. | Built in Checkpoint H for span, chunk, whole-text and corpus-Entity inputs. Saved-record inputs and transitive withholding are not built. |
| Recovery | An unfinished publication | Publish from the saved plan, with no Describe and no Admit | Built (`reconcile`) |
| Withdrawal | A unit removed from the overlay, keeping the original | Admit the withdrawal, then Publish the removals | Built (`withdraw.py`) |
| Forget | A source removed entirely | Admit the forget, then native deletion, then complete | Built for a source nothing depends on (`forget.py`). Erasure with dependents is the next task (docs, `docs/SESSION_HANDOFF.md`, "Next task"). |

Recovery stays separate from reconsideration. Recovery skips Describe. Reconsideration repeats it. Admit and Publish are the common machinery (guarded saves, revisions, attempts, eligibility, recovery). Describe and the domain part of the publish plan are what each integration supplies.

### Revision and transition plan (proposed)

Today the ledger row holds the full current revision in `description`. The `plan` column holds the operation, the target revision number, a full copy of the previous description (`previous_description`), the runtime profile and, for text edits, the text change (code, `replace.py`). A retry of a failed replacement must keep the failed plan's `previous_description` and `text_change` unchanged (code, `storage.py`, the `preserved` plan fields), because the retry still has to retire what the failed attempt planned to retire. So the plan already names its target by number. It copies the previous description only because the store keeps just the current revision. That is a third copy of description content.

The user asked whether the revision could become part of the transition plan. The assistant recommends the opposite.

- Make the saved description a store of immutable revisions.
- Have the transition plan reference its from-revision and to-revision, by number and hash, and carry only what exists for the transition alone (continuity map, old and new text, chunk budget).
- Publish reads the plan and the revisions it names. Recovery replays the plan.

The reason is that the current revision outlives its plan. Retrieval and the next Admit need it after the plan is finished. Under this model each content lives in exactly one place.

### Register tags (open)

The D, P, M and R tags appear in this playbook's register and evidence tables, in `ROADMAP.md` (the framing and the post-Stage-6 checkpoint) and in `docs/SESSION_HANDOFF.md`. Changing them touches all three. One option is to keep the old tags as dated history and use activity tags going forward, keeping "M" for lessons about change over time. Whether the new register replaces the extension reference's section-18 register is undecided.

### Retrieval: native and custom

In Cognee terms, retrieval is `cognee.search` with a SearchType. A retriever builds the context and usually an LLM completes an answer. Identity's `retrieve.py` is not that. Its module docstring reads "Small fixture retriever; native requests/registration follow in the next milestone." Its callers are the CLI, the fixture commands, the tests and the verify journeys. It seeds from `Entity_name`, ranks facts by word overlap and returns JSON. Its job is to check that what was published is reachable, annotated correctly and withheld when it should be. Real retrieval is a registered project Retriever and SearchType (step 5, M4), unbuilt (docs, `results/cognee_identity_stage6_handoff.md`). The contract requires every reader that serves identity results to honour ledger eligibility. The probe is the only reader so far.

## 10. Dry runs for the next integrations (guesses)

### LLM wiki

The pages are Cognee sources. The integration adds structured processing on top, so the wiki's origin is "structure derived by rules", and describing a page is mostly deterministic parsing. One part is genuinely external. That is the record of which investigation or experiment produced a page, with what inputs. Cognee cannot derive it from the text. For an LLM-written page it is probably the most valuable integration-owned product.

| Product | Class | Write paths | Lifecycle owner | Depends on | Retrieval |
|---|---|---|---|---|---|
| Page markdown, its Data item | Cognee | The LLM author through add and update. Integration: perhaps a format gate before add. | Cognee | | Native reads it |
| Section-aligned chunks | Cognee | cognify (with a custom chunker), update | The page Data item | Page text, chunker | Native reads them |
| Extracted Entities and edges | Cognee | cognify, update | Chunks | | Native reads them |
| Parsed structure (section map with type, heading, range, hash; front matter; outbound links) | Integration | A deterministic parser | | One page version | Custom: section types, links, hierarchy |
| Page provenance (investigation or experiment, agent run, inputs used, what it supersedes) | Integration, external input | The authoring pipeline | | | Custom: trust and explanation |
| Overlay (page and section nodes, parent and child edges, section-to-chunk anchors, page links, derived-from edges) | Hybrid | The integration publisher. Cognee: forget, update | The page Data item (borrowed), or a generated source per page | Parsed structure | Native reads it uninterpreted. Custom: hierarchy traversal. |

**Section-aligned chunks with existing functionality.** Partly possible (code, pinned 1.6.2).

- `cognify` takes a `chunker` argument and accepts any `Chunker` subclass. That is the supported seam.
- The built-in chunkers are `TextChunker` (the default, which batches paragraphs up to a token budget), `LangchainChunker` (overlapping, so it cannot tile a document), `CsvChunker` and `JsonListChunker`. None splits on markdown headings.
- So section alignment needs one small custom `Chunker` subclass. A section longer than the token budget must still be split.
- The `Chunker` base class says a document can be updated incrementally only by the chunker that built it (`modules/chunking/Chunker.py`). Whether a custom chunker keeps incremental `update` available is unchecked and needs a probe.
- Chunk IDs come from content, so an edited section always gets a new chunk and new evidence rows.
- Incremental `update` is rejected when a custom graph model or prompt is used (docs, extension reference). Structure processing should therefore run as a separate publish after `cognify`, not inside it. Otherwise every page edit forces a full rebuild, which matters with constant edits.

**Hierarchy.** The user wants a hierarchical knowledge structure. A section's chunk describes the major content of each subsection, and the subsections go into more detail. Traversal and retrieval should use that. Native chunks are flat. A `DocumentChunk` links to its document, not to a parent chunk, and native retrievers rank chunks independently. So the hierarchy must be overlay. A guess at the work, roughly in increasing size:

1. The chunker. Small, through an existing seam.
2. The section-tree overlay. Moderate. Much of identity's publisher and ledger could carry over. The format already puts each subsection's summary in its parent section's text, so the parent chunk is the summary and nothing needs generating.
3. Section continuity across edits. Moderate. The user said section IDs persist "within reason" but not always, so a continuity map keyed by section ID is still needed, plus a rule for sections whose ID did not survive.
4. A custom retriever that walks the hierarchy, descending from an overview into detail or climbing from a matched detail to its context. The largest unknown.

Section nodes and parent edges would also appear in native `GRAPH_COMPLETION`, uninterpreted.

**Change response is the wiki's central unbuilt mechanism.** The LLM author edits pages through Cognee, and the integration must react. Identity has the response procedure but not the path from detection to response. Because describing a page is a parse, the wiki's response can run automatically. Whether a page's overlay is withheld between an edit and its republish is "probably, undecided" (user). With constant edits, that window is always open somewhere in the wiki. If the LLM writes pages using Cognee retrieval, retrieval output feeds back into the sources, so provenance must say which pages are generated.

### Scientific measurements

| Product | Class | Write paths | Lifecycle owner | Depends on | Retrieval |
|---|---|---|---|---|---|
| External input (instrument file, CSV, a table from a paper) | Integration. Hybrid if registered as Data | Import | | | Custom: attribution |
| Measurement records (observation ID, quantity, value, unit, uncertainty, conditions, time, instrument and sample UUIDs, producer, inputs) | Integration (authority) | Describe | | Input, referenced Entities, quantity knowledge | Custom |
| Physical-quantity knowledge | Integration, external input. Possibly wiki pages (below) | Import, or the wiki path | | | Both. It must be retrievable. |
| Overlay (measurement nodes, value and qualifier structure, edges to instruments, samples and quantities) | Hybrid | The integration publisher | A generated source per batch | Records | Native reads it uninterpreted. Custom: required. |
| Instrument, sample and facility Entities | Cognee, plus an owner attribute | Cognee: cognify upsert, consolidate. Integration: retention | Corpus chunks plus the overlay's retention | | Native reads them |
| Ledger, plans | Integration | Integration | | | Custom: eligibility |

**Physical-quantity knowledge** (user request). "Calibration and unit definitions" becomes retrievable knowledge about each physical quantity behind a unit: its meaning, common contexts, common ranges (perhaps per context), how it is useful and should be interpreted, and what is known about measuring it. This is a small textbook-style knowledge layer, revised rarely and applied across the corpus. One option links all three integrations (guess). Each quantity could be a wiki-format page with fixed sections, reusing the wiki machinery, with measurement records linked to the quantity's node. The ranges per context might also be extracted as structured data, so a value can be checked against them. That would make the wiki the base for the other two, which is a sequencing question for later.

Other points:

- Two equal values from different sources stay distinct observations, so observation identity includes the source (docs, `results/stage_four.md`).
- Instrument and sample UUIDs come from normalized names. If the corpus spells "Helios-1" as "Helios 1", it gets a different Entity. Measurements inherit identity's problem space, which is one reason identity comes first.
- Qualifiers are not first-class in the default graph. They are folded into `edge_text` (docs, `results/stage_five.md`), so measurement qualifiers need properties, typed relations or reified claims.
- Links mean "measured by", not "same as". Stage 5's retrieval rules that traverse links both ways or merge endpoints do not apply.
- Where measurements come from is open. The user's preliminary idea is a single backend database for all measurement records (section 5).

### Scientific or engineering knowledge layer

Not discussed yet. It is listed here as a planned test only. The assistant noted earlier that it is close to the opposite of identity. It comes from one source, is revised rarely (by edition) and applies across the whole corpus, so Entity name identity, `consolidate_entities` and referencing without rewriting become the key mechanics. It overlaps with the Stage-7 ontology work.

### What the dry runs teach about the tables

- The coupling table needs an initiator column (decided).
- Each integration-owned product needs an origin. The values seen so far are external input, judgments about the sources (identity) and structure derived by rules (the wiki).
- The lifecycle-owner choice recurs in all three. It belongs among the main decision points.
- History needs differ. Identity keeps only the current revision. The wiki has page versions and supersession. Measurements have calibration revisions.

## 11. Material from the document surveys

The surveys found that most of what a principles document needs already exists in the project, scattered across four places. The playbook covers the Stage-6 publish and maintain design well. It barely touches Cognee mechanics, and its retrieval section is three one-line lessons. Under the decided scope, a Cognee mechanics fact goes into the rewrite only if it touches a product or step row.

**Cognee mechanics that touch a product or step** (docs, Stages 1 to 5, the extension reference and the 5.4.5.1 findings):

- `add` only ingests. After `add` the graph has 0 nodes. `cognify` creates the document node, chunks, summaries and Entities.
- DataPoint IDs. Without `identity_fields` the ID is random. With them it is deterministic but aliases are not resolved. `index_fields` (what is embedded) is independent of `identity_fields`.
- Nested DataPoint fields create child nodes and edges named after the field. Nested persistence rewrites and co-owns the referenced objects.
- A same-ID upsert replaces properties. Re-cognifying rewrote properties on 30 existing Entities and the resolver went from 5/5 to 0/5 while every edge survived. So durable overlay state must not live as properties on Cognee-owned nodes, and surviving topology is not working behaviour.
- Ownership needs a concrete Data anchor. A scalar source ID, dataset label or run ID is not an ownership reference. An edge's owners do not retain its endpoints.
- Deleting an endpoint detaches unowned edges and orphans their Triplets. Native forget of an original does not retire generated sources.
- Incremental `update` is chunk-diff based and is rejected with a custom graph model or prompt. A full rebuild calls built-in `cognify`, so a task defined only in a custom pipeline is not replayed. Forget resets only the `cognify_pipeline` marker.
- Improve and Memify are not scoped. They index the whole shared graph. Improve's watermark can miss incremental runs. A row count or collection existence is not proof of coverage.
- `consolidate_entities` physically merges and deletes Entities, and explicit IDs are not protected from it.
- Two provenance channels exist. Graph-side source references, and the relational `provenance_edge_evidence` table. Evidence means "this chunk caused this edge", not "this chunk contains the sentence". The channels can disagree.
- Manual graph edges carry a thinner metadata envelope than DataPoint edges, so overlay edges should go through the DataPoint path.
- Dataset labels do not confine retrieval. Reads write bookkeeping (history, session QA). The session QA cache can serve stale answers built from retired overlay content.
- What each native retriever reads. `CHUNKS` and `SUMMARIES` read chunks or summaries. `RAG_COMPLETION` reads chunk text. `GRAPH_COMPLETION` projects the graph, including chunk and summary nodes, so a few nodes can still give a large prompt. Native retrieval gives `resolves_to` no meaning.
- The retriever seam is `use_retriever`, or a `BaseRetriever` subclass over the graph and vector interfaces. Do not patch built-in search.
- External non-graph knowledge can be registered as Data and published by a custom task without chunks. Keep three things apart: the authoritative description, the native ownership anchor and any optional retrieval text.

**Retrieval design from Stage 5** (docs, `results/stage_five.md`): resolve the query reference first. Expand only along overlay links, combine the neighbourhoods of the source nodes the overlay links, group repeated facts while keeping the raw edges as support, and return source-attributed context. Keep support and provenance nodes out of ordinary recall but reachable for explanation. Ship it as a registered retriever with native retrieval as the fallback. These rules depend on what an overlay link means. Two-way traversal and endpoint merging work for "same as" and fail for "measured by", so the meaning of each link is an explicit integrator decision.

**The biggest structural issue.** Identity's design assumes the external knowledge is a set of judgments about a corpus document. Original chunks own the markers, each original gets one generated source, and maintenance selected whole documents (Checkpoint H has since made the unit of withholding one decision). The integration class is broader. A measurement table or an instrument registry has its own origin and revisions, and it is applied to corpus sources rather than derived from them. So the principles must keep two relations apart. The first is where the knowledge came from and how it changes. The second is which corpus objects it applies to, and what happens to that link when either side changes.

**About twenty decision points for each integration** came out of the Stage-6 survey. The main ones are the unit each generated source covers, who owns derived facts, whether a shared edge combines contributions or the last writer wins, the continuity rules and successor records, the dependency policy, and what each overlay link means.

**Corrections the rewrite should make anyway:**

- Two registers disagree. The playbook has G01 to G22. Section 18 of the extension reference has a different 13 rows, and the roadmap points there (`ROADMAP.md:685`).
- The playbook still says "G01–G18" (`results/cognee_knowledge_integration_playbook.md:195`).
- G04 presents contribution aggregation as general. The proposal says ordinary facts keep native behaviour.
- The retrieval rows read as demonstrated. Only a fixture probe exists.
- The playbook lacks the 2026-10-22 decision that a changed meaning retires a record, and the Checkpoint F and H decisions.
- The extension reference marks some of its early guidance as superseded, and some of its "proposed" headings are stale. Material taken from it needs its labels checked.
- The requirements review's "distinct identifiers" wording (section 3).

## 12. Where identity's code departs from the model

These came from reading the code, not the docs. Each one should become either a principle or a deliberate exception with its reason.

1. **The saved description is in two containers** (case study). The ledger row's `description` is the authority. Every reader parses it, then requires the registered Data copy to equal it exactly, and refuses the unit with `generated_source_changed` on any difference. It never repairs one from the other. The Data item's real job is to be the native owner of the mention Entities and `resolves_to` edges. The open question is whether it needs the full content or only needs to exist.
2. **The transition plan copies the previous description.** That is a third copy (section 9).
3. **History is short.** The store keeps only the current revision. Earlier judgments are gone once the next revision completes.
4. **Judgments have no form before they are saved.** The captured describers build `IdentitySource` directly in Python. Measurements will differ, because what arrives is not the interpreted record.
5. **The fixture bypasses `cognify`.** No fixture shows real native output beside the overlay.
6. **Detection of another caller's changes happens only at read time.** Nothing responds to it.
7. **There is no registered retriever.** Native search ignores eligibility and withholdings.
8. **The ledger lives where `prune` reaches it.** Nothing handles a pruned store.

## 13. Decisions and open questions

**Decided by the user:**

- Split the playbook into a principles document and a dated evidence log. Dated history stays required.
- Test the principles against identity, measurements, the LLM wiki and the textbook layer.
- The Cognee mechanics section covers only mechanics that touch a product or step.
- Specify data products and processing steps, separated by ownership, in three classes. Classify containers and attributes, not content.
- Keep the same content in more than one container only for a good reason.
- One retrieval column that states native visibility and custom handling.
- Add an initiator column, and write up the trade-offs behind every column.
- The naming in section 3, except the proposed "publication unit" and the narrowed "source".
- Make the ledger, transition plan and publication machinery reusable.
- Import does no interpretation. Keep it as-is for now.
- Ground the rewrite in lessons from the actual code.

**Proposed by the assistant, not yet accepted:**

- Separate activities from procedures, with Ingest, Import, Describe, Admit, Publish, Detect and Retrieve as the activities.
- "Admit" as the name of the admission activity.
- Reserve "source" for Cognee's meaning and add "publication unit".
- Immutable revisions, with plans that reference them.
- A native-visibility decision for every hybrid product.
- Physical-quantity knowledge as wiki-format pages.

**Open:**

- Whether the new register replaces the extension reference's section-18 register.
- How to change the D, P, M and R tags across documents.
- Where measurements come from, and whether one backend database stores them.
- Whether a wiki page's overlay is withheld between an edit and its republish.
- Whether a custom chunker keeps incremental `update` available.
- Whether native search really returns overlay products uninterpreted and ignores eligibility. Expected from the extension reference, not run.
- The textbook layer's design.

## 14. Purpose census (method only)

This section records how to test the observation in TODO item 1, so the test can be repeated. The user asked on 2026-10-23 not to record its numbers until the code is more stable. The assistant ran it once on `012d8a6`, and the result is not recorded here.

**The question.** How much of the identity integration exists because sources change after publication, and how much of that is driven by provenance?

**The script.** `scripts/purpose_census.py`, run from the repository root with `uv run python scripts/purpose_census.py` (add `-v` for counts per module). It reads only the working tree and `git log`.

**Measure 1: code lines by primary purpose.** Every line of `src/cognee_lab/identity/` gets one label. A module has a default label, and named functions, methods or nested functions override it. The labels are judgments made from each function's docstring and callers, not from its name. The core categories are these:

- `P`, provenance checks. Recording or checking what a record came from: inputs, digests, chunk binding, the registered copy, and native state still matching what was recorded.
- `C.own`, change response by native ownership. Withdraw, forget, re-add and the retirement shared between them.
- `C.dep`, change response by recorded inputs. Withholding, refresh, re-confirm and foreign-input attestation.
- `C.cont`, revision continuity. The occurrence map, group fate, recipe and variant rules, and the replace orchestration.
- `C.text`, the native rebuild for a new text.
- `L`, the ledger and crash recovery.
- `B`, publishing one revision's overlay.
- `Q`, the retrieval probe.
- `M`, the record model.

CLI and environment code (`F`) and scenario fixtures (`S.first`, `S.change`) are counted outside the core. "Provenance-driven" means `P`, `C.own` and `C.dep` together. "Change response" means every `C.*` label.

**Measure 2: tests.** Test functions are split into files that exercise only first publication or infrastructure, and files that exercise a change. The script lists the first group by name.

**Measure 3: verify journeys.** Journeys in the `publication-and-retrieval` feature count as first publication. All the rest count as change. Journeys whose title names a fault, failure or interruption are also counted as recovery.

**Measure 4: git churn.** Lines added plus lines deleted in each identity module over the history of `HEAD`, grouped by the module's default label.

**Also check by hand.**

- Which ledger methods, states and transition entries a world without change would still need (`TRANSITIONS` in `storage.py`).
- What the review findings of each checkpoint were about (`docs/SESSION_HANDOFF.md`).
- How many fixture guides in `docs/` describe a change.

**Known limits to report with any result.**

- Describe and real retrieval are not built, so the total understates two activities.
- The project scheduled maintenance first, so effort partly reflects the plan.
- Continuity rules are specific to identity, and they count as change response but not as provenance.
- Some costs come from design choices: the two description copies, whole-document rebuilds and the fixture standing in for `cognify`.
- A label is one person's judgment. When a module is new or renamed, the script reports it as unclassified, and someone must label it before the numbers mean anything.

## 15. TODO

1. **Pressure-test the provenance observation** (user, 2026-10-23). The method is in section 14. A large share of identity's integration work seems to go into managing provenance and making the right updates when the underlying source documents change. Check that observation against the code: measure how much of identity's code, tests and checkpoints is about provenance and change response, as opposed to judgment, publishing or retrieval. Then look for common approaches, or even a framework, that the next integrations could reuse. Candidates already visible are input fingerprints, continuity maps, per-decision withholding, forward recovery from saved plans and the owner choice between borrowed and generated sources.
2. **Compare with Cognee's default provenance** (user, 2026-10-23). List what Cognee records and does by default: source references and the deletion that follows them, `provenance_edge_evidence`, pipeline status, content-derived chunk IDs, incremental `update`'s chunk diff, and Forget's cascade. For each identity provenance mechanism, say whether Cognee already covers it, covers it partly, or does not cover it, and why identity needed its own.
3. Build the mapping from each activity and procedure to the identity code, tests and journeys, as the evidence column for the rewrite. Do it after the current code work lands.
4. Write up the per-column trade-offs in full.
5. Work through the hierarchical wiki in more depth.
6. Dig into the two-description-copies case study (section 12).
7. Revise the playbook, the roadmap pointer and the handoff to the new framing, once the user approves edits to them.
