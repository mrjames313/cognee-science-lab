# Publication and retrieval

A user creates an isolated fixture root with `fixture`, `multi-fixture` or `chunked-fixture`. The CLI publishes captured identity decisions through the real graph, vector and relational stores. The user then retrieves facts, reconciles, and reads status, each in a new process. A failed first publication hides its source until `reconcile` restores it.

Guides: `docs/stage6_identity_first_slice.md` (single and two-source fixtures, failure visibility), `docs/stage6_identity_multichunk.md` (the chunked fixture), `docs/stage6_checkpoint_history.md` ("Resolved: the repository `.env`..." for the `env` profile).

## Sub-features

- `publish-single` creates one source with one accepted local mention and one `limits` fact.
- `publish-two-source` creates two sources that share a variant edge and a singleton.
- `publish-chunked` creates two sources with a 9-token chunk budget, split markers and two-chunk fact evidence.
- `retrieve-reopen` returns the same facts from a new process.
- `reconcile-healthy` leaves a current publication unchanged.
- `status` lists publications and recovery events.
- `publish-failure` withholds a failed first publication, then restores it with `reconcile`.
- `profile-env` publishes with the embedding settings from `.env`. It calls the embedding API.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity fixture --root <new dir>` for one source.
- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>` for two sources.
- Run `uv run python -m cognee_lab.identity chunked-fixture --root <new dir>` for two multi-chunk sources.
- Run `retrieve`, `reconcile [--source doc01|doc02]` and `status` against the same root.
- Add `--fault-stage identity_edges` to a creation command to test a failed first publication.
- Add `--embedding env|loopback` to a creation command. The CLI default is `env`.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey runs in its own `RUN`. The helper builds the root path. The root does not exist yet.

**P1 single publication.** Proves `publish-single`, `retrieve-reopen`, `reconcile-healthy` and `status`. Guide: first slice, "Run it" and "Expected result".

```bash journey P1
$V drive "$RUN" main fixture -- fixture
$V check "$RUN" fixture '.result.facts | length == 1' 'one fact is published'
$V check "$RUN" fixture '.result.facts[0] | .relationship == "limits" and .text == "it limits oscillations"' 'the fact is the limits oscillations fact'
$V check "$RUN" fixture '.result.facts[0].identity | .state == "accepted" and .assignment_id == "r01"' 'the identity annotation is accepted'
$V check "$RUN" fixture '[.result.facts[0].identity.occurrences[] | [.start, .end, .text]] == [[49, 63, "The controller"], [86, 88, "it"]]' 'exact occurrence positions'
$V check "$RUN" fixture '.result.facts[0].evidence | length == 1 and .[0].chunk_index == 0 and (.[0].text | contains("it limits oscillations"))' 'original chunk evidence is returned'
$V check "$RUN" fixture '.result.seed_entity_ids[0] != .result.facts[0].identity.target_entity_id' 'the HC seed traverses to the reusable controller'
$V check "$RUN" fixture '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" fixture '.embedding.profile == "loopback"' 'the root records the loopback profile'

FACT=$(val fixture '.result.facts[0].edge_id')
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '.facts | length == 1 and .[0].edge_id == "'"$FACT"'"' 'a new process returns the same fact'
$V check "$RUN" reopen '[.facts[0].identity.occurrences[] | [.start, .end]] == [[49, 63], [86, 88]]' 'a new process returns the same positions'
$V check "$RUN" reopen '.unavailable_sources == []' 'nothing is unavailable after reopen'

$V drive "$RUN" main reconcile -- reconcile
$V check "$RUN" reconcile '.result.facts | length == 1 and .[0].edge_id == "'"$FACT"'"' 'healthy reconcile keeps the fact'
$V check "$RUN" reconcile '.recovery_events == []' 'healthy reconcile records no incident'

$V drive "$RUN" main status -- status
$V check "$RUN" status '.publications | length == 1 and (.[0] | .state == "current" and .revision == 1 and .verified_revision == 1)' 'one current publication at revision 1'
$V check "$RUN" status '.recovery_events == []' 'status shows no incident'
```

**P2 two-source publication.** Proves `publish-two-source`, `retrieve-reopen`, `reconcile-healthy` and `status`. Guide: first slice, "Two-source lifecycle fixture" table, row "Both published".

```bash journey P2
$V drive "$RUN" main fixture -- multi-fixture
$V check "$RUN" fixture '.result.facts | length == 2' 'both documents produce a fact'
$V check "$RUN" fixture '.result.facts | all(.text == "it limits oscillations")' 'both facts are limits oscillations'
$V check "$RUN" fixture '[.result.facts[].evidence[].data_id] | unique | length == 2' 'each fact has evidence from its own document'
$V check "$RUN" fixture '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 1, 1, 1], ["current", 1, 1, 1]]' 'both sources are current at 1/1/1'
$V check "$RUN" fixture '.shared_variant | (.contributions | length) == 2 and (.owners | length) == 2' 'the shared variant edge has 2 contributions and 2 owners'
$V check "$RUN" fixture '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton is present and indexed'
$V check "$RUN" fixture '.sources | all(.[]; .original_marker_present and .original_fact_present and .original_evidence_present and .private_singleton_present and .private_singleton_indexed)' 'each source has markers, fact, evidence and private singleton'
$V check "$RUN" fixture '.recovery_events == []' 'no incident'

FACTS=$(val fixture '[.result.facts[].edge_id] | sort | tojson')
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].edge_id] | sort == '"$FACTS" 'a new process returns the same two facts'
$V check "$RUN" reopen '.unavailable_sources == []' 'nothing is unavailable'

$V drive "$RUN" main rec01 -- reconcile --source doc01
$V check "$RUN" rec01 '(.result.facts | length) == 2 and .recovery_events == []' 'reconcile doc01 keeps both facts'
$V check "$RUN" rec01 '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision]) == [["current", 1, 1], ["current", 1, 1]]' 'reconcile doc01 does not change revisions'
$V drive "$RUN" main rec02 -- reconcile --source doc02
$V check "$RUN" rec02 '(.result.facts | length) == 2 and .recovery_events == []' 'reconcile doc02 keeps both facts'
$V check "$RUN" rec02 '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision]) == [["current", 1, 1], ["current", 1, 1]]' 'reconcile doc02 does not change revisions'

$V drive "$RUN" main status -- status
$V check "$RUN" status '.publications | length == 2 and all(.state == "current" and .revision == 1 and .verified_revision == 1)' 'status shows two current publications'
```

**P3 chunked publication.** Proves `publish-chunked`, `retrieve-reopen` and `reconcile-healthy`. Guide: multichunk, "Run" and the "Initial" column of the table.

```bash journey P3
$V drive "$RUN" main fixture -- chunked-fixture
$V check "$RUN" fixture '.result.facts | length == 2' 'both documents produce a fact'
$V check "$RUN" fixture '.sources.doc01.chunk_count == 6 and .sources.doc02.chunk_count == 8' 'doc01 has 6 native chunks and doc02 has 8'
$V check "$RUN" fixture '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 1, 1, 1], ["current", 1, 1, 1]]' 'both sources are current at 1/1/1'
$V check "$RUN" fixture '[.sources.doc01.chunk_mapping[] | select(.mention_marker_present) | .chunk_index] == [2, 4]' 'doc01 marker chunk indexes are 2 and 4'
$V check "$RUN" fixture '[.sources.doc01.chunk_mapping[] | select(.owns_captured_fact) | .chunk_index] == [4, 5]' 'doc01 fact owner chunk indexes are 4 and 5'
$V check "$RUN" fixture '[.sources.doc01.chunk_mapping[] | select(.evidence_present) | .chunk_index] == [4, 5]' 'doc01 fact evidence chunk indexes are 4 and 5'
$V check "$RUN" fixture '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end, .text]] == [[49, 63, "the controller"], [90, 92, "it"]]' 'doc01 occurrence positions'
$V check "$RUN" fixture '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .evidence[].chunk_index] == [4, 5]' 'the doc01 fact returns both evidence chunks'
$V check "$RUN" fixture '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton is present and indexed'
$V check "$RUN" fixture '.sources | all(.[]; .unresolved_marker_present and .unresolved_entity_present)' 'the unresolved plasma group is present in both sources'
$V check "$RUN" fixture '.recovery_events == []' 'no incident'

FACTS=$(val fixture '[.result.facts[].edge_id] | sort | tojson')
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].edge_id] | sort == '"$FACTS" 'a new process returns the same two facts'
$V check "$RUN" reopen '.unavailable_sources == []' 'nothing is unavailable'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps both facts'
$V check "$RUN" reconcile '.sources.doc01.chunk_count == 6 and .sources.doc01.saved_revision == 1 and .sources.doc01.verified_revision == 1' 'healthy reconcile keeps doc01 at revision 1 with 6 chunks'
```

**P4 failed first publication.** Proves `publish-failure`, `retrieve-reopen` and `status`. Guide: first slice, "Failure visibility and recovery". The CLI exits 1 with `recovery_event_id` in the message. Deliberate injections carry `origin: "test/fault_injection"`. The stages `nodes` and `verification` also exist. The guide gives no expected result for them beyond a refusal, so this map does not drive them.

```bash journey P4
$V drive "$RUN" main fail -- fixture --fault-stage identity_edges
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '.facts == []' 'no facts from the unfinished source'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'the source is unavailable with the incident id'

$V drive "$RUN" main before -- status
$V check "$RUN" before '.publications | length == 1 and .[0].state == "failed"' 'the publication is failed'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile
$V check "$RUN" reconcile '.result.facts | length == 1' 'reconcile restores the fact'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is resolved by one verified attempt'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns the fact and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | length == 1 and .[0].state == "current"' 'the publication is current'
```

**P5 env profile. This journey calls the embedding API named in `.env` and costs a few API calls.** Proves `profile-env`. It runs `chunked-fixture`, `add-occurrences`, `reconcile` and `retrieve` with `--embedding env`. Guide: `docs/stage6_checkpoint_history.md`, "Evidence after the fix". The handoff records the marker `nvidia/nemotron-3-embed-1b` with 2048 dimensions for this `.env`. A different `.env` model makes the marker check fail, and that is a real mismatch to report. The journey never prints or records a `.env` value. The probe scans the root and the evidence for the API key and writes only a yes or no.

```bash journey P5 env
$V drive "$RUN" main fixture -- chunked-fixture --embedding env
$V check "$RUN" fixture '.result.facts | length == 2' 'env creation returns both facts'
$V drive "$RUN" main add -- add-occurrences --source doc01 --expected-revision 1
$V check "$RUN" add '.result.facts | length == 3' 'the addition returns three facts'
$V check "$RUN" add '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'doc01 is at 2/2/2'
$V check "$RUN" add '.sources.doc02 | .saved_revision == 1 and .verified_revision == 1' 'doc02 stays at 1/1'
$V check "$RUN" add '.recovery_events == []' 'no incident'
$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '(.result.facts | length) == 3 and .recovery_events == []' 'healthy reconcile keeps three facts and no incident'
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'reconcile keeps doc01 at 2/2/2'
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 3 and .unavailable_sources == []' 'a new process returns three facts'

$V probe "$RUN" main probe
$V check "$RUN" probe '.marker == {"profile": "env", "model": "nvidia/nemotron-3-embed-1b", "dimensions": 2048}' 'the marker records the env profile'
$V check "$RUN" probe '.reopen_problem == null' 'the env file still names the model and dimensions that wrote the vectors'
$V check "$RUN" probe '.data_dir_files > 0' 'raw text is under the root data directory'
$V check "$RUN" probe '(.vector_dims | length) > 0 and ([.vector_dims[]] | unique) == [2048]' 'every vector column has 2048 dimensions'
$V check "$RUN" probe '.key_scanned == true and .key_leak == false' 'the embedding API key appears in no root file and no evidence file'
```

## Gotchas

- `fixture`, `multi-fixture` and `chunked-fixture` print Cognee log lines before the JSON. `drive` extracts the JSON. Do not `jq` the raw `.stdout`.
- `fixture` returns `.embedding`. `multi-fixture` and `chunked-fixture` do not. Read their profile with `$V probe "$RUN" main LABEL` (`.marker`).
- `status` shows `.publications[].source` as an identity-data UUID, not `doc01`.
- A fixture command refuses an existing root. To repeat a journey, start a new run.
- `P5` fails at the first step if `.env` lacks `EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS`. Creation fails before any root exists, so `doctor` cannot report it. The CLI error names the missing keys.
- An unapplied tokenizer fix does not fail `P5`. It makes Cognee fall back to an approximate tokenizer for `env` roots. `probe` records `tokenizer_fix`, and `doctor RUN` warns about it while the run still has an env root. See `patches/README.md`.
