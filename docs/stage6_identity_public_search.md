# Stage 6: the IDENTITY search type

**Guide scope:** what `cognee.search` with the lab's `IDENTITY` search type returns, how a process registers it, what a search lists as unavailable, what it refuses, and what Cognee's other search types serve instead. The conformance check that gates retrieval changes has [its own guide](stage6_conformance_check.md). For project status, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

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

The conformance check, which gates retrieval changes against a committed baseline, has its own guide: [stage6_conformance_check.md](stage6_conformance_check.md).
