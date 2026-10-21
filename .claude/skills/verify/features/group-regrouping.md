# Group regrouping

A user splits one of doc01's mention groups on a `chunked-fixture` root, then combines the two halves again. `split-group` replaces doc01 with a text where the old group g01 divides into two fresh groups: g04 (`the controller`) and g05 (`it`). The old group retires with its Entity, markers, resolution and local fact. Both fresh groups resolve to the same reusable controller. The fact `it limits oscillations` is regenerated for g05 from the current chunks, not transferred. `combine-groups` then runs on the same root at revision 2 and replaces doc01 with a text where both halves share one paragraph. g04 and g05 retire and a fresh group g06 holds both occurrences. The fact is regenerated again for g06, and g01 is never brought back. Each command guards on the saved revision, rebuilds doc01 from the captured replacement text, and leaves doc02 at revision 1. An interrupted run withholds doc01 until `reconcile` finishes it.

Guide: `docs/stage6_identity_group_split.md` covers both commands. The reviewed case is in `docs/SESSION_HANDOFF.md`, "Remaining step-4 work".

## Sub-features

- `split-group` retires g01, creates g04 and g05 with IDs from the saved source, regenerates the fact for g05, and continues g02 and doc02 unchanged.
- `split-fault` recovers from an injected failure during a split and keeps the saved fresh IDs.
- `combine-groups` runs after a split, retires g04 and g05, creates g06 with an ID from the saved source, regenerates the fact for g06, and continues g02 and doc02 unchanged.
- `combine-fault` recovers from an injected failure during a combination and keeps the saved g06 ID.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity chunked-fixture --root <new dir>`.
- Run `split-group --root <dir> --source doc01 --expected-revision 1`.
- Run `combine-groups --root <dir> --source doc01 --expected-revision 2` on the same root after the split.
- Add `--fault-stage replace_published` to either command to inject a failure.
- Run `retrieve`, `status` and `reconcile --source doc01` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new `chunked-fixture` root. Both sources are current at revision 1. `G3` and `G4` split first, so doc01 is at revision 2 before the combination.
- The fixture's doc01 text is `Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.` with a trailing newline.

**G1 split a group.** Proves `split-group`. The reviewed map is `{"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}`. The new text is `Helios controller (HC) regulates plasma heating, and the controller adjusts coil current.`, a blank line, and `During calibration, it limits oscillations.` The case gives `the controller` at `[53, 67)` for g04 and `it` at `[111, 113)` for g05. It gives each fresh ID as `uuid5(identity_data_id, "mention:<key>")`. The fixture's doc01 identity ID is fixed, so g04 is `7b93ccfe-fe9d-5126-b484-1b1c5eb39f6e` and g05 is `e6307cfe-012a-53c4-abf7-30dc1d8d904d`. The case says g01 retires with its Entity, name index, markers, resolution and old fact. It says g02 continues with the same UUID at `[33, 39)`, and g04 gets no fact. It says g05 gets a regenerated fact `it limits oscillations` with assignment `r05`. It says two facts are retrieved, the new g05 fact and doc02's unchanged fact. The shared oscillations Entity and relationship text index stay.

```bash journey G1
$V drive "$RUN" main fixture -- chunked-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main split -- split-group --source doc01 --expected-revision 1
G4=$(val split '.text_changes[0].added_groups.g04.entity_id')
G5=$(val split '.text_changes[0].added_groups.g05.entity_id')
$V check "$RUN" split '(.result.facts | length) == 2' 'two facts are retrieved'
$V check "$RUN" split '[.result.facts[].text] == ["it limits oscillations", "it limits oscillations"]' 'the regenerated g05 fact and the unchanged doc02 fact'
$V check "$RUN" split '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" split '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" split '.text_changes[0] | .occurrence_regrouping == {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]} and .occurrence_retention == null and .occurrence_continuity == null and .position_shift == null' 'the regrouping map is the reviewed one and the shift is null'
$V check "$RUN" split '.text_changes[0].added_groups | keys == ["g04", "g05"] and .g04.entity_id == "7b93ccfe-fe9d-5126-b484-1b1c5eb39f6e" and .g05.entity_id == "e6307cfe-012a-53c4-abf7-30dc1d8d904d"' 'the fresh IDs derive from the saved source and group keys'
$V check "$RUN" split '.text_changes[0].added_groups | [.g04, .g05] | all(.entity_present and .entity_indexed and (.marker_chunk_ids | length) > 0)' 'g04 and g05 have their nodes, name indexes and current marker chunks'
$V check "$RUN" split '.text_changes[0].groups | (.g04.occurrences | map([.start, .end])) == [[53, 67]] and (.g05.occurrences | map([.start, .end])) == [[111, 113]] and .g04.previous_occurrences == [] and .g05.previous_occurrences == []' 'the fresh groups hold the reviewed occurrences and have no previous ones'
$V check "$RUN" split '.text_changes[0].retired_groups | keys == ["g01"] and .g01.entity_id == "'"$M01"'" and (.g01 | [.entity_present, .entity_indexed, .marker_present] | all(. == false)) and (.g01.previous_occurrences | length) == 2' 'g01 retires with its Entity, name index and markers'
$V check "$RUN" split '.text_changes[0].groups.g02 | .occurrences == .previous_occurrences and .marker_chunk_ids == .previous_marker_chunk_ids' 'g02 continues at [33,39) on the same chunk'
$V check "$RUN" split '.text_changes[0] | .mention_ids_preserved and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'g02 keeps its ID, retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" split '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .mention_entity_indexed, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed, .resolution_triplet_indexed] | all(. == false)' 'the old mention, resolution link, fact, marker and triplets are physically absent'
$V check "$RUN" split '.sources.doc01.resolved_group_retirement | .fact_evidence_count == 0 and .mention_entity_id == "'"$M01"'"' 'no evidence remains for the old g01 fact'
$V check "$RUN" split '.sources.doc01.resolved_group_retirement | [.shared_fact_endpoint_present, .shared_fact_endpoint_indexed, .shared_relationship_text_indexed] | all' 'the shared endpoint and relationship text stay indexed'
$V check "$RUN" split '.sources.doc01.unresolved_marker_present and .sources.doc01.unresolved_entity_present' 'the unresolved g02 group survives'
$V check "$RUN" split '. as $r | .sources.doc01.identity_data_id as $d | [$r.result.facts[] | select(.identity.identity_data_id == $d) | [.source_id, .identity.assignment_id, .identity.target_entity_id, .relationship]] == [["'"$G5"'", "r05", "'"$T01"'", "limits"]]' 'doc01 has one fact, from g05 as r05 to the reusable controller'
$V check "$RUN" split '[.result.facts[].source_id] | index("'"$G4"'") == null and index("'"$M01"'") == null' 'g04 has no fact and the old g01 fact is gone'
$V check "$RUN" split '.text_changes[0].chunk_ids as $c | .sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .evidence[].chunk_id] | length > 0 and all(. as $e | $c | index($e) != null)' 'the g05 fact evidence uses current doc01 chunks'
$V check "$RUN" split '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" split '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" split '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns two facts'
$V check "$RUN" reopen 'any(.facts[]; .source_id == "'"$G5"'" and .identity.assignment_id == "r05")' 'a new process returns the g05 fact'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps two facts and records no incident'
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'healthy reconcile does not change revisions'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .resolution_edge_present, .fact_edge_present, .current_marker_present] | all(. == false)' 'the retired group, link and fact stay absent'
$V check "$RUN" reconcile 'any(.result.facts[]; .source_id == "'"$G5"'" and .identity.assignment_id == "r05")' 'the g05 fact remains'

$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events == []' 'no incident was recorded'
```

**G2 split fault and recovery.** Proves `split-fault`. The fence lists the stage `replace_published`. The case says only doc02's fact returns and doc01 reports `publication_failed` with an incident ID. It says `reconcile` completes revision 2 with the saved fresh IDs, returns two facts, and resolves the same incident with one verified recovery attempt.

```bash journey G2 stages=replace_published
$V drive "$RUN" main fixture -- chunked-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')

$V drive "$RUN" main fail -- split-group --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '[.publications[] | select(.state == "failed")][0].plan.text_change.occurrence_regrouping == {"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}' 'the saved plan holds the reviewed regrouping map'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'
SAVED=$(val before '[.publications[] | select(.state == "failed")][0].description | fromjson | [.mention_groups.g04.entity_id, .mention_groups.g05.entity_id] | tojson')

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '(.result.facts | length) == 2' 'two facts are returned'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '[.text_changes[0].added_groups.g04.entity_id, .text_changes[0].added_groups.g05.entity_id] == '"$SAVED" 'the fresh group IDs are the saved ones'
$V check "$RUN" reconcile '.text_changes[0].added_groups | [.g04, .g05] | all(.entity_present and .entity_indexed and (.marker_chunk_ids | length) > 0)' 'g04 and g05 have their nodes, name indexes and marker chunks'
$V check "$RUN" reconcile '.text_changes[0] | .retired_groups.g01.entity_id == "'"$M01"'" and (.retired_groups.g01 | [.entity_present, .entity_indexed, .marker_present] | all(. == false)) and .retired_chunks_absent and .retired_chunk_vectors_absent' 'g01 and the retired chunks are absent'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed] | all(. == false)' 'the old g01 fact is physically absent'
$V check "$RUN" reconcile 'any(.result.facts[]; .identity.assignment_id == "r05")' 'the g05 fact is returned'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns two facts and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

**G3 combine groups.** Proves `combine-groups`. The journey splits first with the G1 command, which is covered there. The reviewed map is `{"g04": [["g06", 0]], "g05": [["g06", 1]], "g02": [["g02", 0]]}`. The new text is `Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and during calibration it limits oscillations.` with a trailing newline. The case gives `the controller` at `[49, 63)` and `it` at `[109, 111)` for g06, and g06's ID is `uuid5(identity_data_id, "mention:g06")`, so `3bda245c-19be-5f6e-b722-3785f6bc9447`. It resolves as `r06` to the reusable controller, with recipe name `the controller; it`. The case says g04 and g05 retire with their Entities, name indexes, markers, resolutions and the old g05 fact, evidence and triplets. It says g01 stays absent. It says g02 continues with the same UUID at `[33, 39)`. It says the fact `it limits oscillations` is regenerated for g06 from the current chunks, and two facts are retrieved, g06's and doc02's unchanged one. The shared oscillations Entity and relationship text index stay. The "two facts" count is the guide's reading of the split and the combination together, and the check below reports the real count.

```bash journey G3
$V drive "$RUN" main fixture -- chunked-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main split -- split-group --source doc01 --expected-revision 1
G4=$(val split '.text_changes[0].added_groups.g04.entity_id')
G5=$(val split '.text_changes[0].added_groups.g05.entity_id')
$V check "$RUN" split '[.sources.doc01.saved_revision, .sources.doc02.saved_revision] == [2, 1]' 'the split put doc01 at revision 2'

$V drive "$RUN" main combine -- combine-groups --source doc01 --expected-revision 2
G6=$(val combine '.text_changes[0].added_groups.g06.entity_id')
$V check "$RUN" combine '(.result.facts | length) == 2' 'two facts are retrieved'
$V check "$RUN" combine '[.result.facts[].text] == ["it limits oscillations", "it limits oscillations"]' 'the regenerated g06 fact and the unchanged doc02 fact'
$V check "$RUN" combine '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[3, 3, 3], [1, 1, 1]]' 'doc01 is at 3/3/3 and doc02 stays at 1/1/1'
$V check "$RUN" combine '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" combine '.text_changes[0] | .occurrence_regrouping == {"g04": [["g06", 0]], "g05": [["g06", 1]], "g02": [["g02", 0]]} and .occurrence_retention == null and .occurrence_continuity == null and .position_shift == null' 'the regrouping map is the reviewed one and the shift is null'
$V check "$RUN" combine '.text_changes[0].added_groups | keys == ["g06"] and .g06.entity_id == "3bda245c-19be-5f6e-b722-3785f6bc9447"' 'g06 is the only new group and its ID derives from the saved source'
$V check "$RUN" combine '.text_changes[0].added_groups.g06 | .entity_present and .entity_indexed and (.marker_chunk_ids | length) > 0' 'g06 has its node, name index and current marker chunk'
$V check "$RUN" combine '.text_changes[0].groups | (.g06.occurrences | map([.start, .end, .text])) == [[49, 63, "the controller"], [109, 111, "it"]] and .g06.previous_occurrences == []' 'g06 holds the two reviewed occurrences and has no previous ones'
$V check "$RUN" combine '.text_changes[0].retired_groups | keys == ["g04", "g05"] and .g04.entity_id == "'"$G4"'" and .g05.entity_id == "'"$G5"'" and ([.g04, .g05] | all(. as $g | [$g.entity_present, $g.entity_indexed, $g.marker_present] | all(. == false)))' 'g04 and g05 retire with their Entities, name indexes and markers'
$V check "$RUN" combine '.text_changes[0].groups.g02 | .occurrences == .previous_occurrences and .marker_chunk_ids != null and ([.occurrences[] | [.start, .end]] == [[33, 39]])' 'g02 continues at [33,39)'
$V check "$RUN" combine '.text_changes[0] | .mention_ids_preserved and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'g02 keeps its ID, retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" combine '.sources.doc01.combined_group_retirement | keys == ["g04", "g05"] and .g04.mention_entity_id == "'"$G4"'" and .g05.mention_entity_id == "'"$G5"'"' 'the combination reports checks for exactly g04 and g05'
$V check "$RUN" combine '.sources.doc01.combined_group_retirement | [.g04, .g05] | all(. as $c | [$c.mention_entity_present, $c.mention_entity_indexed, $c.resolution_edge_present, $c.fact_edge_present, $c.current_marker_present, $c.fact_triplet_indexed, $c.resolution_triplet_indexed] | all(. == false))' 'the old g04 and g05 mentions, resolution links, facts, markers and triplets are physically absent'
$V check "$RUN" combine '.sources.doc01.combined_group_retirement | [.g04, .g05] | all(.fact_evidence_count == 0)' 'no evidence remains for the old g04 and g05 facts'
$V check "$RUN" combine '.sources.doc01.combined_group_retirement | [.g04, .g05] | all(. as $c | [$c.shared_fact_endpoint_present, $c.shared_fact_endpoint_indexed, $c.shared_relationship_text_indexed] | all)' 'the shared endpoint and relationship text stay indexed'
$V check "$RUN" combine '.sources.doc01.resolved_group_retirement | .mention_entity_id == "'"$M01"'" and ([.mention_entity_present, .mention_entity_indexed, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed, .resolution_triplet_indexed] | all(. == false)) and .fact_evidence_count == 0' 'g01 stays absent and is not resurrected'
$V check "$RUN" combine '.sources.doc01.unresolved_marker_present and .sources.doc01.unresolved_entity_present' 'the unresolved g02 group survives'
$V check "$RUN" combine '. as $r | .sources.doc01.identity_data_id as $d | [$r.result.facts[] | select(.identity.identity_data_id == $d) | [.source_id, .identity.assignment_id, .identity.target_entity_id, .relationship]] == [["'"$G6"'", "r06", "'"$T01"'", "limits"]]' 'doc01 has one fact, from g06 as r06 to the reusable controller'
$V check "$RUN" combine '.result.facts[] | select(.source_id == "'"$G6"'") | [.identity.occurrences[].text] == ["the controller", "it"]' 'the g06 fact names both occurrences'
$V check "$RUN" combine '[.result.facts[].source_id] | (index("'"$G4"'") == null) and (index("'"$G5"'") == null) and (index("'"$M01"'") == null)' 'the old g01, g04 and g05 facts are gone'
$V check "$RUN" combine '.text_changes[0].chunk_ids as $c | .sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .evidence[].chunk_id] | length > 0 and all(. as $e | $c | index($e) != null)' 'the g06 fact evidence uses current doc01 chunks'
$V check "$RUN" combine '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" combine '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" combine '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns two facts'
$V check "$RUN" reopen 'any(.facts[]; .source_id == "'"$G6"'" and .identity.assignment_id == "r06")' 'a new process returns the g06 fact'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps two facts and records no incident'
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[3, 3, 3], [1, 1, 1]]' 'healthy reconcile does not change revisions'
$V check "$RUN" reconcile '.sources.doc01.combined_group_retirement | [.g04, .g05] | all(. as $c | [$c.mention_entity_present, $c.resolution_edge_present, $c.fact_edge_present, $c.current_marker_present] | all(. == false))' 'the retired groups, links and facts stay absent'
$V check "$RUN" reconcile 'any(.result.facts[]; .source_id == "'"$G6"'" and .identity.assignment_id == "r06")' 'the g06 fact remains'

$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 3]' 'both publications are current at revisions 1 and 3'
$V check "$RUN" after '.recovery_events == []' 'no incident was recorded'
```

**G4 combine fault and recovery.** Proves `combine-fault`. The fence lists the stage `replace_published`. The split runs healthy first. The case says only doc02's fact returns and doc01 reports `publication_failed` with an incident ID. It says `reconcile` completes revision 3 with the saved g06 ID, returns two facts, and resolves the same incident with one verified recovery attempt. It says the retired g04 and g05 facts stay absent.

```bash journey G4 stages=replace_published
$V drive "$RUN" main fixture -- chunked-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
$V drive "$RUN" main split -- split-group --source doc01 --expected-revision 1
G4=$(val split '.text_changes[0].added_groups.g04.entity_id')
G5=$(val split '.text_changes[0].added_groups.g05.entity_id')

$V drive "$RUN" main fail -- combine-groups --expected-revision 2 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 3 and .verified_revision == 2)' 'doc01 is failed at revision 3 with last verified revision 2'
$V check "$RUN" before '[.publications[] | select(.state == "failed")][0].plan.text_change.occurrence_regrouping == {"g04": [["g06", 0]], "g05": [["g06", 1]], "g02": [["g02", 0]]}' 'the saved plan holds the reviewed combination map'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'
SAVED=$(val before '[.publications[] | select(.state == "failed")][0].description | fromjson | .mention_groups.g06.entity_id')

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 3, 3, 3], ["current", 1, 1, 1]]' 'reconcile completes revision 3 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '(.result.facts | length) == 2' 'two facts are returned'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 3 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 3 by one verified attempt'
$V check "$RUN" reconcile '.text_changes[0].added_groups.g06.entity_id == "'"$SAVED"'" and .text_changes[0].added_groups.g06.entity_id == "3bda245c-19be-5f6e-b722-3785f6bc9447"' 'the g06 ID is the saved one'
$V check "$RUN" reconcile '.text_changes[0].added_groups.g06 | .entity_present and .entity_indexed and (.marker_chunk_ids | length) > 0' 'g06 has its node, name index and marker chunk'
$V check "$RUN" reconcile '.text_changes[0] | .retired_groups.g04.entity_id == "'"$G4"'" and .retired_groups.g05.entity_id == "'"$G5"'" and ([.retired_groups.g04, .retired_groups.g05] | all(. as $g | [$g.entity_present, $g.entity_indexed, $g.marker_present] | all(. == false))) and .retired_chunks_absent and .retired_chunk_vectors_absent' 'g04, g05 and the retired chunks are absent'
$V check "$RUN" reconcile '.sources.doc01.combined_group_retirement | [.g04, .g05] | all(. as $c | ([$c.mention_entity_present, $c.resolution_edge_present, $c.fact_edge_present, $c.current_marker_present, $c.fact_triplet_indexed] | all(. == false)) and $c.fact_evidence_count == 0)' 'the old g04 and g05 facts are physically absent'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | .mention_entity_id == "'"$M01"'" and ([.mention_entity_present, .fact_edge_present] | all(. == false))' 'g01 stays absent'
$V check "$RUN" reconcile 'any(.result.facts[]; .source_id == "'"$SAVED"'" and .identity.assignment_id == "r06")' 'the g06 fact is returned'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns two facts and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 3]' 'both publications are current at revisions 1 and 3'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

## Gotchas

- `split-group` and `combine-groups` accept only their captured doc01 edits. They do not locate arbitrary phrases or infer groups. See "Not yet supported" in the README.
- `combine-groups` refuses any root where doc01 was not produced by `split-group`, with an `IntentError` that says it requires `split-group`. Run the split first and pass `--expected-revision 2`.
- The regrouping map is checked exactly. A map from a different guide version fails the check, and that is a real mismatch.
- After a successful split or combination, the old g01 mention ID stays in `resolved_group_retirement` as a diagnostic constant. Its absence checks are the proof, not the ID. After a combination, `combined_group_retirement` holds the same checks for g04 and g05.
- A healthy `reconcile` after a split or combination drops `text_changes` from the output. The `G1` and `G3` reconcile checks read `.sources` and `.result`.
- Run `retrieve` after the split or combination in a new process. The command's own JSON comes from the process that wrote the change.
