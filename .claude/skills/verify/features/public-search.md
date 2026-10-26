# Public search

A user searches a root through Cognee's own `cognee.search` with the lab's `IDENTITY` search type. Since step 5 S1 the CLI `search` registers `IDENTITY` (`cognee_lab.identity.search`) and calls `cognee.search` as a user would. The search returns what the CLI `retrieve` returns, lists the same unavailable sources and withheld decisions, makes no LLM call and is logged in Cognee's search history as `IDENTITY`.

Guide: `docs/stage6_identity_public_search.md` ("What a search returns", "Scope and mode", "What a search lists as unavailable", "Commands").

## Sub-features

- `search-equals-retrieve` returns, through `cognee.search`, exactly the result of the CLI `retrieve`, with `mode`, `scope` and `dataset_id`, and logs the query as `IDENTITY`.
- `search-failed` lists a failed first publication as unavailable with its incident, and serves its fact again after `reconcile`.
- `search-withheld` lists the decisions a glossary edit withholds, as `status` lists them.
- `search-native-deleted` fails a source deleted outside the lab on the first search, with a `retrieval_validation` incident, and keeps serving the other source.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity fixture --root <new dir> --embedding loopback`, then `search` and `retrieve` against the same root.
- Add `--all-datasets` to `search` to search every dataset (`datasets=None`).
- Add `--scope` or `--mode` to `search` or `retrieve`.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey runs in its own `RUN`. The helper builds the root path.

**S1 search returns what retrieve returns.** Proves `search-equals-retrieve`. Guide: "What a search returns" and "Commands". `search` returns one result with `mode` `semantic`, `scope` `identity` and the root's dataset, holding the accepted `limits` fact of the first slice guide ("Expected result"). `search_history` lists the query once with type `IDENTITY`. `retrieve` in a new process returns the same result, field for field. `search --all-datasets` returns it too, since the root has one dataset, and the history then lists two queries.

```bash journey S1
$V drive "$RUN" main fixture -- fixture
$V drive "$RUN" main search -- search
$V check "$RUN" search '.search_result | length == 1 and (.[0] | .mode == "semantic" and .scope == "identity" and (.dataset_id | test("^[0-9a-f-]{36}$")))' 'one result in the default scope and mode, for one dataset'
$V check "$RUN" search '[.search_result[0].facts[] | [.relationship, .text, .identity.state]] == [["limits", "it limits oscillations", "accepted"]] and .search_result[0].unavailable_sources == []' 'search serves the accepted limits fact'
$V check "$RUN" search '.search_history == [{"query_type": "IDENTITY", "text": "What does HC limit?"}]' 'Cognee logs the query as IDENTITY'
$V drive "$RUN" main retrieve -- retrieve
RET=$(val retrieve 'tojson')
$V check "$RUN" search '.search_result == [('"$(jq -n --arg s "$RET" '$s')"' | fromjson)]' 'search returns exactly what retrieve returns'
$V drive "$RUN" main all -- search --all-datasets
$V check "$RUN" all '.search_result == [('"$(jq -n --arg s "$RET" '$s')"' | fromjson)] and (.search_history | length) == 2' 'with one dataset, datasets=None returns the same result'
```

**S2 a failed publication, then reconcile.** Proves `search-failed`. Guide: "What a search lists as unavailable". A failed first publication at `identity_edges` exits 1 with `recovery_event_id`, as in the first slice guide ("Failure visibility and recovery"). `search` returns no fact and lists the source with `assignment_id` null, reason `publication_failed` and that incident. `reconcile` restores the fact. The next `search` serves `it limits oscillations` with nothing unavailable, and `status` lists the publication as current with the incident resolved, outcome `restored`.

```bash journey S2
$V drive "$RUN" main fail -- fixture --fault-stage identity_edges
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')
$V drive "$RUN" main withheld -- search
$V check "$RUN" withheld '.search_result[0].facts == [] and [.search_result[0].unavailable_sources[] | [.assignment_id, .reason, .recovery_event_id]] == [[null, "publication_failed", "'"$EID"'"]]' 'search serves nothing of the failed source and names its incident'
$V drive "$RUN" main reconcile -- reconcile
$V drive "$RUN" main search -- search
$V check "$RUN" search '[.search_result[0].facts[].text] == ["it limits oscillations"] and .search_result[0].unavailable_sources == []' 'after reconcile search serves the fact'
$V check "$RUN" search '[.search_history[].query_type] == ["IDENTITY", "IDENTITY"]' 'both searches are logged'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.state, .revision, .verified_revision]] == [["current", 1, 1]] and (.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolved_at != null))' 'the publication is current and its incident resolved'
```

**S3 withheld decisions, as status lists them.** Proves `search-withheld`. Guide: "What a search lists as unavailable", with the dependencies guide ("A cosmetic change"). On a `glossary-fixture` root `search` first serves the fact. After `edit-glossary --case cosmetic`, `search` returns no fact and lists r01 and v01 with `input_changed` and no incident. `status` lists the same decisions with the same reasons under `withheld_decisions`, both publications current and no incident.

```bash journey S3
$V drive "$RUN" main fixture -- glossary-fixture
$V drive "$RUN" main before -- search
$V check "$RUN" before '[.search_result[0].facts[].text] == ["it limits oscillations"] and .search_result[0].unavailable_sources == []' 'search serves the fact before the edit'
$V drive "$RUN" main edit -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V drive "$RUN" main search -- search
$V check "$RUN" search '.search_result[0].facts == [] and [.search_result[0].unavailable_sources[] | [.assignment_id, .reason, .recovery_event_id]] == [["r01", "input_changed", null], ["v01", "input_changed", null]]' 'search withholds r01 and v01'
WITHHELD=$(val search '[.search_result[0].unavailable_sources[] | [.identity_data_id, .assignment_id, .reason]] | tojson')
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.withheld_decisions[] | [.identity_data_id, .assignment_id, .reason]] == ('"$(jq -n --arg s "$WITHHELD" '$s')"' | fromjson)' 'status lists the decisions search withholds'
$V check "$RUN" status 'all(.publications[]; .state == "current") and (.publications | length) == 2 and .recovery_events == []' 'both publications stay current with no incident'
```

**S4 a source deleted outside the lab.** Proves `search-native-deleted`. Guide: "What a search lists as unavailable", with the forget guide ("Deletes outside the lab"). On a `multi-fixture` root `search` serves both documents' facts. `native-forget --source doc02 --case data` deletes doc02's original outside the lab. The next `search` still serves doc01's fact and lists doc02 with `assignment_id` null, reason `source_missing` and a new incident. `status` lists doc02 as failed at revision 1, one open incident at stage `retrieval_validation`, and doc02 under `native_deleted` with `next` `forget --source doc02 --expected-revision 1`. A second `search` lists doc02 with `publication_failed` and the same incident.

```bash journey S4
$V drive "$RUN" main fixture -- multi-fixture
$V drive "$RUN" main before -- search
$V check "$RUN" before '.search_result[0].facts | length == 2' 'search serves both documents before the delete'
$V drive "$RUN" main native -- native-forget --source doc02 --case data
$V drive "$RUN" main search -- search
$V check "$RUN" search '[.search_result[0].facts[].text] == ["it limits oscillations"] and (.search_result[0].unavailable_sources | length == 1 and (.[0] | .assignment_id == null and .reason == "source_missing" and (.recovery_event_id | test("^[0-9a-f-]{36}$"))))' 'search keeps doc01 and fails doc02 with an incident'
EID=$(val search '.search_result[0].unavailable_sources[0].recovery_event_id')
DOC02=$(val search '.search_result[0].unavailable_sources[0].identity_data_id')
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | select(.source == "'"$DOC02"'") | [.state, .revision]] == [["failed", 1]] and ([.publications[] | select(.source != "'"$DOC02"'") | .state] == ["current"])' 'doc02 is failed and doc01 stays current'
$V check "$RUN" status '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .stage == "retrieval_validation" and .resolved_at == null)' 'one open incident at retrieval_validation'
$V check "$RUN" status '[.native_deleted[] | [.identity_data_id, .next]] == [["'"$DOC02"'", "forget --source doc02 --expected-revision 1"]]' 'status lists doc02 as deleted outside the lab'
$V drive "$RUN" main again -- search
$V check "$RUN" again '[.search_result[0].unavailable_sources[] | [.identity_data_id, .reason, .recovery_event_id]] == [["'"$DOC02"'", "publication_failed", "'"$EID"'"]] and (.search_result[0].facts | length) == 1' 'a later search lists the failed publication with the same incident'
```

## Gotchas

- `search` prints `search_result`, the list `cognee.search` returns, so read facts at `.search_result[0].facts`. `retrieve` prints the result itself.
- `search_history` holds every query Cognee logged in the root, so a check on its length counts the run's earlier searches too.
