# Stage 6: the IDENTITY search type

**Guide scope:** what `cognee.search` with the lab's `IDENTITY` search type returns, how a process registers it, what a search lists as unavailable, what it refuses, what Cognee's other search types serve instead, and the conformance check that gates retrieval changes. For project status, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

Built on 2026-10-26 against Cognee 1.6.2 and Python 3.12 (step 5, unit S1). The assistant built it on the user's Mac. The values below come from loopback fixture roots that the assistant ran on the user's Mac on 2026-10-26.

## Warning: the other search types serve withheld and failed state

Only `IDENTITY` applies the ledger. Cognee's own search types read the graph, the chunk index and the triplet index as they stand, so they serve what the lab withholds: a decision withheld after an edit of its input, a failed publication's new text, and the mention labels that are never query aliases. Use `IDENTITY` for answers that the lab's saved descriptions govern.

Probe E2 measured this on 2026-10-26. An Opus subagent of the assistant ran `support/s1_probes.py` at tag `s1-probes-2026-10-26` (commit 21a74e7) on the user's Mac, with loopback embeddings and every LLM call refused unless the probe stubbed it, on `glossary-fixture --chain` roots. For the query `What does HC limit?`:

| Root | `IDENTITY` | `CHUNKS` | `GRAPH_COMPLETION` (`only_context`) | `TRIPLET_COMPLETION` (`only_context`) |
|---|---|---|---|---|
| Healthy | 1 fact, nothing unavailable | 3 chunks | 11 edges, 0 withheld facts | 11 triplets, 0 withheld facts |
| After `edit-glossary --case cosmetic` | 0 facts; r01, v01, c01 and c02 withheld | 3 chunks | 11 edges, 1 withheld fact (`it limits oscillations` from the mention `The controller; it`) | 11 triplets, 1 withheld fact |
| After a failed `edit-glossary --case insert` at `text_chunks` or `replace_published` | 0 facts; the glossary `publication_failed`, r01, v01, c01 and c02 withheld | 3 chunks, 1 of them the failed glossary's new text with the unpublished `ECRH` line | 11 edges, 1 withheld fact, 1 chunk node of the failed document | 11 triplets, 1 withheld fact, 1 chunk text of the failed document |

In every root `GRAPH_COMPLETION` reached the two mention nodes `The controller; it` and `The regulator` and printed them as graph nodes. `TRIPLET_COMPLETION` raised `NoDataError` until the probe built the triplet index with Cognee's memify `create_triplet_embeddings`, which runs an LLM connection test that the probe stubbed. The `TRIPLET_COMPLETION` columns are from after that build.

Journey S7 shows the `CHUNKS` cell of the failed insert on a `glossary-fixture` root through the CLI, with `native-search`, a plain `cognee.search` with `SearchType.CHUNKS`.

## What a search returns

`cognee.search(query, query_type=SearchType.IDENTITY, datasets=[name])` runs the lab's `retrieve_settled` (`src/cognee_lab/identity/settled.py`) over the one dataset that Cognee gives the retriever. The CLI `retrieve` runs the same function, so the two return the same result:

- `facts`: the identity-anchored facts of the dataset's served sources, each with its checked evidence chunks. The ranking is unchanged from the first slice: name-match seeds, else the top vector hit, the closure over accepted links, one-hop facts with own-chunk evidence and a word-overlap score.
- `unavailable_sources`: each source or decision that the search did not serve, with its reason ("What a search lists as unavailable").
- `seed_entity_ids`, `identity_expansion_limited`, `identity_work`, `fact_candidates_limited` and `identity_guide`, as before.
- `mode`, `scope` and `dataset_id`: added in S1. `mode` and `scope` are the values the search ran with ("Scope and mode").

Cognee returns `[result]` from a plain search. With `verbose=True`, `context_result` is the result as JSON text and `text_result` is `[result]`. No LLM runs: the completion is the result itself. Cognee logs the query in its search history with the type `IDENTITY`.

With `include_references=True`, the evidence lists each fact as a `triplet` reference and each of its checked chunks as a `segment` reference with the role `supports_assertion`. The search never returns a `graph_edge` reference. For such a reference Cognee adds the chunks that its edge sidecar lists, from every document, served or not.

Two behaviors are new in S1 and apply to the CLI `retrieve` too:

- **Seeds come only from the searched dataset's served sources.** Cognee's `Entity_name` collection holds the Entities of every dataset in the store. Probe E5 (2026-10-26) measured an Entity of another dataset that became the seed of a query and displaced the lab's seed, so the query returned no fact. Now only a reusable Entity that a served source of the searched dataset constructs can seed. A query that names no lab Entity falls back to the top-ranked reusable Entity only when a served source of the searched dataset constructs it. When another dataset's Entity ranks first, the search has no seed and returns no fact, so a query about another dataset's Entity never returns the lab's facts.
- **One more read when a writer changes the ledger during the read.** A search reads the ledger at its start and again at its end. If a writer moved a served row between the two reads (`retrieval_changed`), or began on a source that the search was failing (`stale_attempt`), the search reads once more. A second change fails the search.

## Register IDENTITY

Cognee's `SearchType` is a closed enum. Import `cognee_lab.identity.search` to add the member `IDENTITY` and register `IdentityRetriever` for it. The import fails with `RegistrationError` when it cannot do this safely:

- Cognee is not 1.6.2, or Python is not 3.12. The member is added through Python 3.12's enum internals, and the search path was inspected on Cognee 1.6.2 only.
- `SearchType` already has an `IDENTITY` member that the lab did not add. Cognee replaces the retriever of an existing member without a warning, so the lab never registers over one.
- A self-test fails. It checks the lookups by name, by value and by attribute, iteration, pickling, a `SearchResultPayload` built with the member and from its value, and the registry entry.

When the self-test fails, the import removes the member and the registry entry that it added, so `SearchType` is as it was. The module imports `cognee`, so configure the process first. A second import, or a second call of `register()`, changes nothing. A reload of the module (`importlib.reload`) keeps the member and registers the reloaded `IdentityRetriever`: the import recognises its own earlier class by module and name.

Every search opens the configured stores through `Publisher.configured`, which runs `RecordStore.initialize`: it creates the lab's ledger tables in Cognee's relational database if they are missing and records the Entities that forget tombstones prove removed (it records nothing twice), as every lab CLI command does. The retriever keeps no per-process cache of the stores, since the tests and the CLI switch roots within one process.

## Scope and mode

A search takes a scope and a mode in `retriever_specific_config`, or as `--scope` and `--mode` on the CLI `retrieve` and `search`:

| Key | Value | Behavior |
|---|---|---|
| `scope` | `identity` (default) | Identity-anchored facts only |
| `scope` | `identity_and_unattributed` | Not built. Refused with `scope_not_built` |
| `mode` | `semantic` (default) | Facts found from the saved decisions |
| `mode` | `source_aware` | Not built. Refused with `mode_not_built` |

## What a search lists as unavailable

A search lists what it withholds under `unavailable_sources`, as the CLI `retrieve` does:

- **A failed publication.** The search returns no fact of the source and one entry with `assignment_id` null, reason `publication_failed` and the open incident's `recovery_event_id`. `reconcile` restores the publication, and the next search serves its facts with nothing unavailable.
- **A withheld decision.** After `edit-glossary --case cosmetic` on a `glossary-fixture` root, the search returns no fact and lists r01 and v01 of doc01 with reason `input_changed`, the same decisions and reasons that `status` lists under `withheld_decisions` ([dependencies guide](stage6_identity_dependencies.md#a-cosmetic-change)). Both publications stay current.
- **A source deleted outside the lab.** After `native-forget --source doc02 --case data` on a `multi-fixture` root, the first search fails doc02's row, since its own chunks are gone. It lists doc02 with reason `source_missing` and the new incident, and still serves doc01's fact. `status` then lists doc02 as failed at revision 1, one open incident at stage `retrieval_validation`, and doc02 under `native_deleted` with the forget to run ([forget guide](stage6_identity_forget.md)). A later search lists doc02 with reason `publication_failed` and the same incident.

## Refusals

`IdentityRetriever` raises every refusal in its constructor. Cognee calls it after it resolves the datasets (and, with access control on, checks each dataset's graph and data), and before it logs the query. The retriever reads no lab store before it refuses. The exception type is `SearchRefused`, an `IntentError` with a `code`. It is not a Cognee `NoDataError`, so it fails the whole search instead of becoming one dataset's empty entry, and Cognee writes no search history row for it. The CLI prints `{"error": "SearchRefused", "code": ..., "message": ...}` and exits 1.

| Code | When |
|---|---|
| `dataset_required` | Cognee gives the retriever no dataset. With access control off, Cognee gives one only when the search covers exactly one dataset, so `datasets=None` is refused once the user can read two datasets. Pass `datasets=[name]`. |
| `access_control_on` | `ENABLE_BACKEND_ACCESS_CONTROL` is on. The lab's ledger lives in the one shared relational database, and the per-dataset databases of access control are not built for it. |
| `scope_not_built` | `scope` is `identity_and_unattributed`. |
| `mode_not_built` | `mode` is `source_aware`. |
| `config_invalid` | `retriever_specific_config` has a key other than `scope` and `mode`, or a value neither enum knows. The CLI rejects an unknown `--scope` or `--mode` value in its argument parser instead. |

The CLI `retrieve` refuses `scope_not_built` and `mode_not_built` the same way.

## Limits of the IDENTITY member

- **Import order.** `IDENTITY` exists only in a process that imported `cognee_lab.identity.search`. A pydantic model that validates `SearchType` from JSON and was built before that import rejects `IDENTITY`. Cognee's HTTP router DTOs are such models unless the router is imported after the lab (probe E1). HTTP routes are out of scope for the lab (U-f).
- **JSON round trips.** `SearchResultPayload.model_validate_json` rejects a payload whose search type is `IDENTITY`, because its schema was built before the member existed. Python-mode validation and `model_dump_json` work (probe E1).
- **The `cognee search` CLI.** A fresh `cognee search` process never imports the lab, so `SearchType["IDENTITY"]` raises `KeyError` there (probe E1).
- **`FEELING_LUCKY`.** Cognee's selector prompt does not name `IDENTITY`, so the LLM selection is not expected to pick it. When a stubbed selector answered `IDENTITY`, the lab retriever ran and the history row recorded `FEELING_LUCKY` (probe E1).
- **`cognee.recall`.** Its query router never picks `IDENTITY`. `recall(query_type=SearchType.IDENTITY)` bypasses the router and returns one entry whose `raw` is the result (probe E1).
- **Pinned versions.** Nothing in Cognee's dependency range (`cognee>=1.6,<1.7`) pins the enum internals that `add_member` writes. The import refuses any Cognee other than 1.6.2 and any Python other than 3.12.
- **Seed crowding.** The search takes the top 10 `Entity_name` hits and then drops every Entity that no served source constructs. A store with many Entities in other datasets can push every lab Entity out of the top 10. The query would then return no fact (inferred from the code, not measured).
- **Document names after an edit.** A text edit writes the original through Cognee's ingestion with a text payload, which renames its Data row, and so its document node, from the file name (for example `glossary`) to `text_<md5 of the text>`. This has held since the text changes of 2026-10-19 (`registered.write_text`) and is not caused by S4. Native search contexts show the new name. The IDENTITY result never uses document names.

## Commands

Use a new root for each sequence:

```bash
uv run python -m cognee_lab.identity fixture --root outputs/stage6_search_check --embedding loopback
uv run python -m cognee_lab.identity search --root outputs/stage6_search_check
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_search_check
uv run python -m cognee_lab.identity search --root outputs/stage6_search_check --all-datasets
```

`search` calls `cognee.search` with `IDENTITY` and the root's dataset, or with `datasets=None` under `--all-datasets`, and `top_k` 5, the limit of `retrieve`. It prints `search_result`, the list that Cognee returns, and `search_history`, the queries in Cognee's search history after the search.

Expected: `search_result` is one result equal to the `retrieve` output, with the accepted fact `it limits oscillations`, `mode` `semantic` and `scope` `identity`. `search_history` lists the query once with type `IDENTITY`, and twice after the `--all-datasets` search. The root has one dataset, so `--all-datasets` returns the same result.

Refusals and the stand-ins, each on a new `fixture` root:

```bash
uv run python -m cognee_lab.identity search --root <root> --scope identity_and_unattributed
uv run python -m cognee_lab.identity search --root <root> --mode source_aware
uv run python -m cognee_lab.identity native-add --root <root>
uv run python -m cognee_lab.identity search --root <root> --all-datasets
```

Expected: the first two exit 1 with `SearchRefused` and the codes `scope_not_built` and `mode_not_built`. `native-add` adds `outside_dataset` with a plain `cognee.add`, so `native_add.datasets` lists `outside_dataset` and `stage6_isolated_fixture`. The `--all-datasets` search then exits 1 with `dataset_required`. A later `search` lists only its own query in `search_history`.

`native-search` is a stand-in for a plain `cognee.search` with `SearchType.CHUNKS` on the root's dataset. It prints `native_search.chunks`, each chunk's id and text, and writes no ledger row. After a failed `edit-glossary --case insert` on a `glossary-fixture` root it returns the chunk with the unpublished `ECRH` line ("Warning: the other search types serve withheld and failed state").

## The conformance check

Added on 2026-10-26 in step 5 S1. The assistant's subagent built it and ran it on the user's Mac with loopback embeddings. The values below are from those runs.

### What it is

`conformance-fixture` builds a root from DOC01 (`data/DOC01_helios1_technical_overview_v2.md`) through the lab's `add` and `cognify`. Its describer (`src/cognee_lab/identity/conformance_fixture.py`) reads only DOC01's text and native chunks. `support/conformance_check.py` searches the root through `cognee.search` with `IDENTITY` and scores the results against the Stage 5.3 traversal and query-resolution benchmarks and the Helios manifest in `data/hidden`. The check is the only reader of `data/hidden`. The unit test `test_no_src_module_reads_the_hidden_benchmark_data` fails when a module under `src/` names it.

The describer's rules and its table of references were written by an author who had read those answers. The check therefore measures whether the search serves a fixed description the way the benchmarks expect, and it gates retrieval changes against a baseline. It is a conformance check. It does not evaluate Describe, and its numbers say nothing about extraction quality.

### The describer

- **Names.** Four rules give the reusable Entities and their variants, all scoped to DOC01:
  1. An abbreviation definition, `long form (ABBR)` where ABBR is the initials of the last words, gives both names, with ABBR a variant of the long form.
  2. A defined long form followed by "System" is a variant of the long form, for example `Neutral Beam Injection System`.
  3. A run of two or more capitalized words that does not start a sentence is a name, for example `Aurora Reconstruction Suite` and `Campaign A`.
  4. The alias statement `generally uses “Helios-1.”` makes each quoted name before the `, where` qualifier of the next sentence a variant: `Helios 1` and `H-1`. `Helios` and `the machine` come after the qualifier and are not names.
- **References.** Eleven hand-read groups (`REFERENCES`), each resolved to the Entity that its paragraph names, or inside a quotation to the one that the introducing sentence names. Examples are `The controller; It` to the Vertical Control System, `Aurora; The suite; It` to the Aurora Reconstruction Suite and `The machine` to Helios-1.
- **Facts.** In each sentence of the body, and in each table row, the first named reusable Entity or reference group is the subject. Each other named Entity outside the subject's identity group, and each quantity with a unit (`m`, `s`, `T`, `MW`, `kHz`, `MA` or `%`), is stated with it. The relation is `stated_with`, the fact text is the sentence, and the evidence is the chunks that the sentence overlaps. A subject and target pair keeps its first sentence.

On DOC01 at the default chunk budget of 512, the describer gives 23 reusable Entities, 12 variant assignments, 11 reference groups with 11 accepted resolutions, 29 facts and 10 chunks.

### The measures

A case passes, fails, or is unobserved when no search result decides it.

| Measure | Cases |
|---|---|
| `fact_recall` | Each manifest fact that DOC01 states (F001 to F016, T001, T003). The query `<subject> <predicate>` returns, in the default top 5, a fact whose text holds the object's words or the value with its unit. |
| `closure_symmetry` | Each traversal identity case (TRV01 to TRV06). Every member's name as the query returns the same nonempty set of facts, with top 100. |
| `mentions` | TRV07 and TRV08 at their chunk coordinates, and the manifest's DOC01 resolutions ER001 to ER009. A mention-anchored fact covering the span is served under the expected referent. |
| `negative_controls` | AFRL never resolves the Aurora Reconstruction Suite and the reverse, TRV08 is never served under the Vertical Control System, each hard negative of ER002, ER005 and ER007 is never served under the wrong referent, and QRY05 resolves nothing. |
| `query_resolution` | QRY01 and QRY02 resolve to their group. QRY03 and QRY04 are an accepted gap: they pass when they resolve no wrong group. |

Over every result the check also counts repeated edge IDs, evidence or identity records outside DOC01's own chunks and source, and fact endpoints that are not Entities, or a mention as a target, or a mention subject with no identity record. These three counts must stay 0. It reports logical duplicates, the same fact through two members of one identity group, and does not gate them.

### The baseline

`support/conformance_baseline.json` holds every case and, for each case that does not pass, its reason from `KNOWN_GAPS` in the check. The check made 54 searches and took about 15 s with the fixture. Measured on 2026-10-26:

| Measure | Passed | Failed | Unobserved |
|---|---:|---:|---:|
| `fact_recall` | 10 | 8 | 0 |
| `closure_symmetry` | 5 | 0 | 1 |
| `mentions` | 9 | 0 | 2 |
| `negative_controls` | 6 | 1 | 1 |
| `query_resolution` | 4 | 0 | 0 |

Repeated edge IDs, attribution violations and leakage violations were 0. Logical duplicates were 7, for example `8 MW` stated with both `neutral beam injection` and `Neutral Beam Injection System` in one result.

The known gaps:

- **Recall F008, F011 to F016.** The describer writes no fact for them. The deuterium sentences, the interferometer, Thomson scattering and the edge reflectometer name no reusable Entity, since no name rule matches a lowercase common noun. The sentences on the suite's use and on the EDC's gas feedback name only their subject's identity group. The pulse length is only in a table row that names no Entity.
- **Recall F010.** DOC01 never states `spatial magnetic measurements`, and the check matches words literally.
- **Closure TRV05 (unobserved).** No fact has an AFRL-group subject, because AFRL is named only as the target of a Helios-1 fact.
- **TRV08 and its control (unobserved).** The case's coordinates, the second `the controller` of chunk 2, follow DOC01 v1's Stage-5 chunking. Chunk 2 of DOC01 v2 holds one occurrence. The manifest's ER005 hard negative stands in for it.
- **ER001 (unobserved).** The section-1 group of `the machine` has no fact.
- **QRY05 (failed).** This is the retrieval limit. With no name match the search seeds the top `Entity_name` vector hit, so the ambiguous query resolves to an arbitrary group (`RCM` under loopback embeddings). Seeding improvements are later work, measured against this baseline.

What the passes do not show:

- Recall matches words, not predicates. F009 passes on `the probe array is not treated as an independent direct measurement of total plasma current`, which holds the object inside a negation.
- QRY04 passes because its words contain the full name `edge density controller`, which seeds by name. The search does no contextual resolution. QRY03 resolves nothing.
- The mention passes come from the hand-read table. They show that the search serves a mention-anchored fact under its referent, not that anything resolved the mention.

### The gate

The check exits 1 when a case does worse than on the baseline (passed, then unobserved, then failed), when a case appears or disappears, or when a gated count grows. It lists improvements and does not fail on them. Journey B1 fails on them, so the baseline is written again after an improvement. `--write-baseline` writes the baseline from the run and refuses while a case that does not pass has no reason in `KNOWN_GAPS`. On 2026-10-26 a scratch break that turned off variant expansion in `retrieve.py` made the check fail seven cases: five closures, F009 and T003.

Run it for a change to retrieval (`retrieve.py`, `settled.py`, `search.py`), to the conformance fixture, or to the fact writers in `fixture.py`. It is a local check and journey B1, not part of CI.

```bash
uv run python support/conformance_check.py
uv run python support/conformance_check.py --root <conformance root> --json
uv run python support/conformance_check.py --write-baseline
uv run python -m cognee_lab.identity conformance-fixture --root <new dir> --embedding loopback
```

Without `--root` the check makes a new root under `outputs/conformance/`. A conformance root takes `status`, `retrieve` and `search`. The argument parser refuses every other command.
