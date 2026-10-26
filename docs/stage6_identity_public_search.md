# Stage 6: the IDENTITY search type

**Guide scope:** what `cognee.search` with the lab's `IDENTITY` search type returns, how a process registers it, and what a search lists as unavailable. For project status, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

Built on 2026-10-26 against Cognee 1.6.2 and Python 3.12 (step 5, unit S1). The assistant built it on the user's Mac. The values below come from loopback fixture roots that the assistant ran on the user's Mac on 2026-10-26.

## What a search returns

`cognee.search(query, query_type=SearchType.IDENTITY, datasets=[name])` runs the lab's `retrieve_settled` (`src/cognee_lab/identity/retrieve.py`) over the one dataset that Cognee gives the retriever. The CLI `retrieve` runs the same function, so the two return the same result:

- `facts`: the identity-anchored facts of the dataset's served sources, each with its checked evidence chunks. The ranking is unchanged from the first slice: name-match seeds, else the top vector hit, the closure over accepted links, one-hop facts with own-chunk evidence and a word-overlap score.
- `unavailable_sources`: each source or decision that the search did not serve, with its reason ("What a search lists as unavailable").
- `seed_entity_ids`, `identity_expansion_limited`, `identity_work`, `fact_candidates_limited` and `identity_guide`, as before.
- `mode`, `scope` and `dataset_id`: added in S1. `mode` and `scope` are the values the search ran with ("Scope and mode").

Cognee returns `[result]` from a plain search. With `verbose=True`, `context_result` is the result as JSON text and `text_result` is `[result]`. No LLM runs: the completion is the result itself. Cognee logs the query in its search history with the type `IDENTITY`.

With `include_references=True`, the evidence lists each fact as a `triplet` reference and each of its checked chunks as a `segment` reference with the role `supports_assertion`. The search never returns a `graph_edge` reference. For such a reference Cognee adds the chunks that its edge sidecar lists, from every document, served or not.

Two behaviors are new in S1 and apply to the CLI `retrieve` too:

- **Seeds come only from the searched dataset's served sources.** Cognee's `Entity_name` collection holds the Entities of every dataset in the store. Probe E5 (2026-10-26) measured an Entity of another dataset that became the seed of a query and displaced the lab's seed, so the query returned no fact. Now only a reusable Entity that a served source of the searched dataset constructs can seed. A query that names no lab Entity falls back to the top-ranked lab Entity.
- **One more read when a writer changes the ledger during the read.** A search reads the ledger at its start and again at its end. If a writer moved a served row between the two reads (`retrieval_changed`), or began on a source that the search was failing (`stale_attempt`), the search reads once more. A second change fails the search.

## Register IDENTITY

Cognee's `SearchType` is a closed enum. Import `cognee_lab.identity.search` to add the member `IDENTITY` and register `IdentityRetriever` for it. The import fails with `RegistrationError` when it cannot do this safely:

- Cognee is not 1.6.2, or Python is not 3.12. The member is added through Python 3.12's enum internals, and the search path was inspected on Cognee 1.6.2 only.
- `SearchType` already has an `IDENTITY` member that the lab did not add. Cognee replaces the retriever of an existing member without a warning, so the lab never registers over one.
- A self-test fails. It checks the lookups by name, by value and by attribute, iteration, pickling, a `SearchResultPayload` built with the member and from its value, and the registry entry.

The module imports `cognee`, so configure the process first. A second import, or a second call of `register()`, changes nothing.

The first search in a process opens the configured stores through `Publisher.configured`. That creates the lab's ledger tables in Cognee's relational database if they are missing, as every lab CLI command does.

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
