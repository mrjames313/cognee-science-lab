# Revision and text edits

A user changes a published identity source in two ways. `revise` corrects doc01's identity decisions and leaves the text alone. `edit-text` inserts a captured prefix into doc01's text, rebuilds doc01's native chunks, and moves every occurrence by the prefix length. Both commands need the current saved revision. Both advance doc01 from revision 1 to 2 and leave doc02 at revision 1. An interrupted run withholds doc01 until `reconcile` finishes it.

Guides: `docs/stage6_identity_revision_replacement.md` (`revise`), `docs/stage6_identity_text_changes.md` (`edit-text` on `multi-fixture`), `docs/stage6_identity_multichunk.md` (`edit-text` on `chunked-fixture`).

## Sub-features

- `revise-correction` retargets doc01's accepted mention to a revised controller.
- `revise-stale` rejects a stale expected revision before it changes anything.
- `revise-fault` recovers from an injected failure at each documented `replace_*` stage.
- `edit-prefix` inserts the prefix on one chunk and remaps occurrences exactly.
- `edit-multichunk` repeats the edit on many chunks, with split markers and two-chunk fact evidence.
- `edit-fault` recovers from an injected failure at each documented `text_*` stage.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>`, then `revise --root <dir> --source doc01 --expected-revision 1`.
- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>`, then `edit-text --root <dir> --source doc01 --expected-revision 1`.
- Run `uv run python -m cognee_lab.identity chunked-fixture --root <new dir>`, then `edit-text` with the same arguments.
- Add `--fault-stage <stage>` to inject a failure. Then run `retrieve`, `status` and `reconcile --source doc01`.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new root. Both commands refuse a stale `--expected-revision`.
- The fixture's sources are current at revision 1 before the first edit.

**R1 revise, stale retry and reconcile.** Guide: revision replacement, the "Run the captured correction" table. The guide says doc01's mention keeps its UUID, fact and evidence. It says the old shared variant contribution and the private singleton are removed. Doc02 keeps its own interpretation. The `revise` command also queries the revised controller and returns doc01's fact alone. A repeated `revise` at revision 1 is stale.

```bash journey R1
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run revise)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- multi-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
D02=$(val fixture '.sources.doc02.identity_data_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
FACT01=$(val fixture '.sources.doc01.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV01=$(val fixture '.sources.doc01.fact_evidence_chunk_ids | tojson')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
T02=$(val fixture '.sources.doc02.resolution_target_entity_id')

$V drive "$RUN" main revise -- revise --source doc01 --expected-revision 1
$V check "$RUN" revise '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" revise '.sources.doc01.registered_matches_saved and .sources.doc01.state == "current"' 'doc01 registered snapshot matches the saved record'
$V check "$RUN" revise '.sources.doc01.resolution_target_entity_id != "'"$T01"'" and .sources.doc02.resolution_target_entity_id == "'"$T02"'"' 'doc01 targets the revised controller and doc02 keeps the original'
$V check "$RUN" revise '(.result.facts | length) == 2' 'the default query returns both facts'
$V check "$RUN" revise '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .source_id] == ["'"$M01"'"]' 'the doc01 fact keeps the same local mention UUID'
$V check "$RUN" revise '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT01"'"]' 'the doc01 fact keeps the same edge ID'
$V check "$RUN" revise '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end]] == [[49, 63], [86, 88]]' 'doc01 occurrence positions are unchanged'
$V check "$RUN" revise '.sources.doc01.fact_evidence_chunk_ids == '"$EV01"' and .sources.doc02.fact_evidence_chunk_ids == '"$EV02" 'original evidence is unchanged in both sources'
$V check "$RUN" revise '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" revise '.shared_variant.contributions | map(.identity_data_id) == ["'"$D02"'"]' 'only doc02 still contributes to the old shared variant edge'
$V check "$RUN" revise '.sources.doc01 | .private_singleton_present == false and .private_singleton_indexed == false' 'the doc01 private singleton and its name vector are removed'
$V check "$RUN" revise '.sources.doc02 | .private_singleton_present and .private_singleton_indexed' 'the doc02 private singleton survives'
$V check "$RUN" revise '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton survives'
$V check "$RUN" revise '(.corrected_entity_result.facts | length) == 1 and .corrected_entity_result.facts[0].source_id == "'"$M01"'"' 'the revised controller query returns the doc01 fact alone'
$V check "$RUN" revise '.recovery_events == []' 'no incident'

$V drive "$RUN" main stale -- revise --source doc01 --expected-revision 1
$V check "$RUN" stale '.error == "IntentError"' 'a stale expected revision is rejected'
$V drive "$RUN" main afterstale -- status
$V check "$RUN" afterstale '[.publications[].revision] | sort == [1, 2]' 'the stale call changed no revision'
$V check "$RUN" afterstale '.publications | all(.state == "current") and (. | length) == 2' 'both publications are still current'

RT=$(val revise '.sources.doc01.resolution_target_entity_id')
$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'healthy reconcile keeps doc01 at 2/2/2'
$V check "$RUN" reconcile '.sources.doc01.resolution_target_entity_id == "'"$RT"'"' 'healthy reconcile keeps the corrected target'
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps both facts and records no incident'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts'
$V check "$RUN" reopen '[.facts[] | select(.identity.identity_data_id == "'"$D01"'") | .identity.target_entity_id] == ["'"$RT"'"]' 'a new process returns the doc01 fact with the corrected target'
$V check "$RUN" reopen '[.facts[] | select(.identity.identity_data_id != "'"$D01"'") | .identity.target_entity_id] == ["'"$T02"'"]' 'a new process returns the doc02 fact with the original target'
$V cleanup "$RUN"
```

**R2 revise fault and recovery.** Guide: revision replacement, "Interrupted replacement and explicit recovery". Run the block once per stage, each in its own run, with `STAGE` set to `replace_saved`, `replace_registered`, `replace_published` and `replace_retired`. The guide says that every stage leaves revision 2 failed with last verified revision 1. The guide also says `retrieve` withholds doc01 and keeps doc02, and `reconcile` completes revision 2 with outcome `restored`. The stage `replace_verification` exists, and the guide does not list it as covered, so this map does not drive it.

```bash journey R2
STAGE=${STAGE:-replace_saved}
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run "revise-fault-$STAGE")
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- multi-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')

$V drive "$RUN" main fail -- revise --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'

$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '[.publications[] | select(.state == "current")] | length == 1 and (.[0] | .revision == 1 and .verified_revision == 1)' 'doc02 is current at revision 1'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .operation == "replace" and .intended_revision == 2 and .last_verified_revision == 1 and .origin == "test/fault_injection" and .resolved_at == null)' 'one open replace incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.sources.doc01.resolution_target_entity_id != "'"$T01"'"' 'doc01 targets the revised controller, not revision 1'
$V check "$RUN" reconcile '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .source_id] == ["'"$M01"'"]' 'the doc01 fact keeps the same local mention UUID'
$V check "$RUN" reconcile '(.result.facts | length) == 2' 'both facts are returned'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '.shared_variant.contributions | length == 1' 'doc01 no longer contributes to the old shared variant edge'
$V check "$RUN" reconcile '.sources.doc01 | .private_singleton_present == false and .private_singleton_indexed == false' 'the obsolete doc01 singleton and its name vector are removed'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events | all(.resolved_at != null)' 'no incident stays open'
$V cleanup "$RUN"
```

**E1 prefix edit on one chunk.** Guide: text changes, the table under "Run on a fresh two-source fixture". The prefix has 48 Unicode code points. The guide says doc01 keeps its Data ID, group Entity IDs, fact ID and resolution target. It says doc01's chunk and fingerprint are new and its evidence is rebuilt. Doc02 is unchanged.

```bash journey E1
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run edit-text-prefix)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- multi-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
T02=$(val fixture '.sources.doc02.resolution_target_entity_id')
FACT01=$(val fixture '.sources.doc01.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV01=$(val fixture '.sources.doc01.fact_evidence_chunk_ids | tojson')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
DATA01=$(val fixture '.sources.doc01.identity_data_id as $d | .shared_variant.contributions[] | select(.identity_data_id == $d) | .applicability.data_id')

$V drive "$RUN" main edit -- edit-text --source doc01 --expected-revision 1
$V check "$RUN" edit '.text_changes | length == 1 and .[0].position_shift == 48' 'the prefix shifts occurrences by 48 code points'
$V check "$RUN" edit '.text_changes[0].groups | [.g01.occurrences[] | [.start, .end]] == [[97, 111], [134, 136]] and [.g02.occurrences[] | [.start, .end]] == [[81, 87]]' 'the controller, it and plasma move to [97,111), [134,136) and [81,87)'
$V check "$RUN" edit '.text_changes[0] | .text_sha256 != .previous_text_sha256 and .chunk_ids != .previous_chunk_ids' 'doc01 has a new text fingerprint and new native chunk IDs'
$V check "$RUN" edit '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .mention_ids_preserved' 'retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" edit '.text_changes[0].original_data_id == "'"$DATA01"'"' 'the original Data ID is unchanged'
$V check "$RUN" edit '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" edit '.sources.doc01 | .mention_entity_id == "'"$M01"'" and .resolution_target_entity_id == "'"$T01"'"' 'the doc01 group Entity and resolution target are preserved'
$V check "$RUN" edit '(.result.facts | length) == 2' 'both facts are returned'
$V check "$RUN" edit '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT01"'"]' 'the doc01 fact ID is preserved'
$V check "$RUN" edit '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end]] == [[97, 111], [134, 136]]' 'the returned doc01 annotation has the new positions'
$V check "$RUN" edit '.sources.doc01 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present' 'doc01 marker, fact, ownership and evidence are rebuilt'
$V check "$RUN" edit '.sources.doc01.fact_evidence_chunk_ids == .text_changes[0].evidence_chunk_ids and .sources.doc01.fact_evidence_chunk_ids != '"$EV01" 'doc01 evidence moved to the new chunk'
$V check "$RUN" edit '.sources.doc02.fact_evidence_chunk_ids == '"$EV02"' and .sources.doc02.resolution_target_entity_id == "'"$T02"'"' 'doc02 evidence and interpretation are unchanged'
$V check "$RUN" edit '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" edit '.recovery_events == []' 'no incident'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'healthy reconcile keeps doc01 at 2/2/2'
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps both facts and records no incident'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts'
$V check "$RUN" reopen '[.facts[] | select(.identity.identity_data_id == "'"$D01"'") | .identity.occurrences[] | [.start, .end]] == [[97, 111], [134, 136]]' 'a new process returns the new doc01 positions'
$V cleanup "$RUN"
```

**E2 prefix edit on many chunks, repeated.** Guide: multichunk, the table with the "Initial" and "After first edit" columns. The prefix has 10 code points. The guide says the second edit at expected revision 2 reaches revision 3 with seven doc01 chunks. It says a later withdrawal preserves original-owned facts, evidence and markers under the current chunk mapping.

```bash journey E2
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run edit-text-multichunk)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- chunked-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
FACT01=$(val fixture '.sources.doc01.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')

$V drive "$RUN" main edit1 -- edit-text --source doc01 --expected-revision 1
$V check "$RUN" edit1 '.text_changes[0].position_shift == 10' 'the prefix shifts occurrences by 10 code points'
$V check "$RUN" edit1 '.text_changes[0].groups.g01.occurrences | map([.start, .end, .text]) == [[59, 73, "the controller"], [100, 102, "it"]]' 'the controller moves to [59,73) and it moves to [100,102)'
$V check "$RUN" edit1 '.sources.doc01.chunk_count == 6' 'doc01 still has 6 chunks, with changed boundaries'
$V check "$RUN" edit1 '[.sources.doc01.chunk_mapping[] | select(.mention_marker_present) | .chunk_index] == [2, 3, 4]' 'the group marker chunk indexes are 2, 3 and 4'
$V check "$RUN" edit1 '[.sources.doc01.chunk_mapping[] | select(.owns_captured_fact) | .chunk_index] == [4, 5] and [.sources.doc01.chunk_mapping[] | select(.evidence_present) | .chunk_index] == [4, 5]' 'the fact owner and evidence chunk indexes are 4 and 5'
$V check "$RUN" edit1 '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .mention_ids_preserved' 'retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" edit1 '.sources.doc01 | .mention_entity_id == "'"$M01"'" and .resolution_target_entity_id == "'"$T01"'"' 'the group Entity and referent are preserved'
$V check "$RUN" edit1 '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT01"'"]' 'the fact edge ID is preserved'
$V check "$RUN" edit1 '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" edit1 '.sources.doc02 | .chunk_count == 8 and .fact_evidence_chunk_ids == '"$EV02" 'doc02 chunks and evidence are unchanged'
$V check "$RUN" edit1 '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" edit1 '.recovery_events == []' 'no incident'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'healthy reconcile keeps doc01 at 2/2/2'
$V check "$RUN" reconcile '[.sources.doc01.chunk_mapping[] | select(.mention_marker_present) | .chunk_index] == [2, 3, 4]' 'healthy reconcile keeps the marker chunk indexes'
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps both facts and records no incident'

$V drive "$RUN" main edit2 -- edit-text --source doc01 --expected-revision 2
$V check "$RUN" edit2 '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[3, 3, 3], [1, 1, 1]]' 'doc01 reaches revision 3 and doc02 stays at 1'
$V check "$RUN" edit2 '.sources.doc01.chunk_count == 7' 'doc01 has 7 chunks after the second edit'
$V check "$RUN" edit2 '.text_changes[0] | .position_shift == 10 and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'the second edit shifts by 10 and verifies evidence against the new chunks'
$V check "$RUN" edit2 '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT01"'"]' 'the fact edge ID is preserved'
$V check "$RUN" edit2 '.sources.doc02 | .chunk_count == 8 and .fact_evidence_chunk_ids == '"$EV02" 'doc02 chunks and evidence are unchanged'

MK=$(val edit2 '.sources.doc01.mention_marker_chunk_ids | tojson')
FE=$(val edit2 '.sources.doc01.fact_evidence_chunk_ids | tojson')
$V drive "$RUN" main wd -- withdraw --source doc01
$V check "$RUN" wd '.sources.doc01 | .state == "withdrawn" and .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present' 'withdrawal keeps the original-owned marker, fact and evidence'
$V check "$RUN" wd '.sources.doc01.mention_marker_chunk_ids == '"$MK"' and .sources.doc01.fact_evidence_chunk_ids == '"$FE" 'the markers and evidence still map to the current chunks'
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns only the doc02 fact'
$V cleanup "$RUN"
```

**E3 prefix edit fault and recovery.** Guide: text changes, "Interrupted edit and recovery". Run the block once per stage, each in its own run, with `STAGE` set to `text_removed`, `text_registered`, `text_chunks` and `replace_published`. The guide says doc01 is failed and withheld while `retrieve` returns doc02 only. It says `reconcile` repeats the native rebuild, completes revision 2 and records `resolving_revision: 2` with `outcome: restored`.

```bash journey E3
STAGE=${STAGE:-text_registered}
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run "edit-text-fault-$STAGE")
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- multi-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
EV01=$(val fixture '.sources.doc01.fact_evidence_chunk_ids | tojson')

$V drive "$RUN" main fail -- edit-text --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'

$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .operation == "replace" and .intended_revision == 2 and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '(.result.facts | length) == 2' 'both facts are returned'
$V check "$RUN" reconcile '.sources.doc01.mention_entity_id == "'"$M01"'"' 'the doc01 group Entity is preserved'
$V check "$RUN" reconcile '[.result.facts[] | select(.identity.identity_data_id == "'"$D01"'") | .identity.occurrences[] | [.start, .end]] == [[97, 111], [134, 136]]' 'the doc01 fact carries the edited positions'
$V check "$RUN" reconcile '.sources.doc01 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present and .fact_evidence_chunk_ids != '"$EV01" 'doc01 evidence is rebuilt under the new chunk'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V cleanup "$RUN"
```

**E4 multi-chunk edit fault and recovery.** Guide: multichunk, "Interrupted rebuild". The guide says doc02's fact stays available with both evidence chunks. It says `reconcile` restores doc01 at 2/2/2 and resolves the same incident.

```bash journey E4
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run edit-text-multichunk-fault)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- chunked-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')

$V drive "$RUN" main fail -- edit-text --expected-revision 1 --fault-stage text_chunks
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"] and (.facts[0].evidence | length) == 2' 'only the doc02 fact is returned, with both evidence chunks'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'

$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile restores doc01 at 2/2/2 and leaves doc02 at 1/1/1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null)' 'the same incident is restored at revision 2'
$V check "$RUN" reconcile '[.sources.doc01.chunk_mapping[] | select(.mention_marker_present) | .chunk_index] == [2, 3, 4]' 'the rebuilt marker chunk indexes are 2, 3 and 4'
$V check "$RUN" reconcile '[.sources.doc01.chunk_mapping[] | select(.evidence_present) | .chunk_index] == [4, 5]' 'the rebuilt evidence chunk indexes are 4 and 5'
$V check "$RUN" reconcile '(.result.facts | length) == 2' 'both facts are returned'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts and nothing is unavailable'
$V cleanup "$RUN"
```

## Gotchas

- `revise` has no `text_changes`. It returns `corrected_entity_result` instead. `edit-text` returns `text_changes` and no `corrected_entity_result`.
- A repeated `revise` or `edit-text` with the old `--expected-revision` is stale. Use `reconcile` to check a current revision.
- `--fault-stage` must match the command. `revise` takes `replace_*`. `edit-text` takes `text_*` or `replace_*`.
- The `replace_published` stage records its incident under a stage named `replacement_cleanup`. Do not assert the incident `stage` field against the flag value.
- A boundary change can leave the chunk count unchanged. Equal content-derived chunk IDs do not prove equal positions. Check chunk indexes, not only IDs.
- The edit result files (`revision_result.json`, `text_revision_result.json`) are the transition record. A later healthy `reconcile` does not repeat them. Read `text_changes` from the `edit` step.
- `edit-text` applies only the captured prefix. It does not infer that arbitrary new text is irrelevant. See "Not yet supported" in the README.
- The captured fixture proves lifecycle mechanics. It does not prove that the correction or the edit is semantically right.
