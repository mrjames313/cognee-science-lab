# Reinterpretation

A user changes what a mention in doc01 means, or changes how doc01 represents HC, on a `chunked-fixture` root. `reinterpret` edits the text so that g01's mention changes its referent. g01 retires and a fresh group g03 takes the new meaning, either a new reusable Backup controller (`--case new-entity`) or no referent at all (`--case unresolved`). The fact `it limits oscillations` is generated again from g03. `change-kind` leaves the text unchanged. `--direction to-mention` drops doc01's HC declaration and its HC variant v01 and makes HC a document-local mention group g03 that resolves to the Helios controller. `--direction to-reusable` then retires g03, declares HC again, reads doc02's existing HC Entity through a corpus input and names it in a new variant v02. Each command guards on the saved revision, rebuilds doc01, and leaves doc02 at revision 1. An interrupted run withholds doc01 until `reconcile` finishes it. The kind changes are the first runs of a `TextChange` whose before and after texts are equal.

Guide: `docs/stage6_identity_reinterpretation.md`. The approved cases are in `docs/SESSION_HANDOFF.md`, "One admission for every replacement, 2026-10-22".

## Sub-features

- `reinterpret-new-entity` retires g01, creates g03 with the derived Backup controller as its target and regenerates the fact from g03. The Helios controller no longer reaches doc01's fact and the Backup controller does.
- `reinterpret-unresolved` retires g01 and creates an unresolved g03 that holds the regenerated fact. No query reaches that fact.
- `reinterpret-fault` recovers from an injected failure during a changed interpretation.
- `reinterpret-scope` refuses every call that is not the captured case on a fresh root.
- `kind-to-mention` makes HC a mention group with unchanged text. The shared HC edge keeps doc02's contribution only, and the HC Entity stays because doc02 owns it.
- `kind-to-reusable` retires the mention group and names doc02's HC Entity again. The shared HC edge has both contributions, no second HC Entity exists, and an HC query reaches doc01's fact again.
- `kind-fault` recovers from an injected failure during either kind change.
- `kind-scope` refuses a kind change on the wrong root or revision.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity chunked-fixture --root <new dir>`.
- Run `reinterpret --case new-entity|unresolved --root <dir> --source doc01 --expected-revision 1`.
- Run `change-kind --direction to-mention --root <dir> --source doc01 --expected-revision 1`, then `change-kind --direction to-reusable ... --expected-revision 2` on the same root.
- Add `--fault-stage replace_published` or `--fault-stage text_chunks` to inject a failure.
- Run `retrieve` (with `--query "What does Backup controller limit?"` for the Backup controller), `status` and `reconcile --source doc01` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new `chunked-fixture` root. Both sources are current at revision 1. The kind-change journeys that run `to-reusable` run `to-mention` first, so doc01 is at revision 2 before it.
- The fixture's doc01 text is `Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.` with a trailing newline. Both kind changes keep that text.
- The fixture's doc01 identity ID is fixed, so the fresh IDs are the same in every run: g03 is `4827dc6d-3687-56e7-8a15-96a9dc30c070` and the Backup controller is `30d7405d-10a3-5a53-a8da-8c707cb12310`. HC is `9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88`.

**I1 reinterpret to a new Entity.** Proves `reinterpret-new-entity`. Guide: reinterpretation, "Changed interpretation to a new Entity". The new text is `Helios controller (HC) regulates plasma heating, the backup controller adjusts coil current, and it limits oscillations.` The occurrence map is `{"g01": [null, ["g03", 1]], "g02": [["g02", 0]]}`. The guide gives g03 as `the backup controller` at `[49, 70)` and `it` at `[97, 99)`, with the ID `uuid5(identity_data_id, "mention:r2:g03")`. It gives the Backup controller as `uuid5(identity_data_id, "entity:r2:r03")`, named by r03. The guide says g01 retires with its Entity, name index, markers, resolution and old fact, and g02 continues at `[33, 39)`. It says g03 has a node, a name index and three marker chunks, because the new mention crosses a chunk boundary and the fact crosses another. It says g03 has the regenerated fact with two evidence chunks. It says a Helios controller query and the default HC query return only doc02's fact, and a Backup controller query returns exactly the g03 fact as r03 with the Backup controller as target. It says the Backup controller is indexed and the Helios controller node is unchanged.

```bash journey I1
$V drive "$RUN" main fixture -- chunked-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main reinterpret -- reinterpret --case new-entity --source doc01 --expected-revision 1
G3=4827dc6d-3687-56e7-8a15-96a9dc30c070
BK=30d7405d-10a3-5a53-a8da-8c707cb12310
$V check "$RUN" reinterpret '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" reinterpret '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" reinterpret '.text_changes[0] | .occurrence_map == {"g01": [null, ["g03", 1]], "g02": [["g02", 0]]} and .position_shift == null and .text_length_delta == 7' 'the occurrence map is the reviewed one and the text grows by seven code points'
$V check "$RUN" reinterpret '.text_changes[0].added_groups | keys == ["g03"] and .g03.entity_id == "'"$G3"'"' 'g03 is the only fresh group and its ID derives from the source, revision 2 and key'
$V check "$RUN" reinterpret '.text_changes[0].groups.g03 | .previous_occurrences == [] and .occurrences == [{"start": 49, "end": 70, "text": "the backup controller"}, {"start": 97, "end": 99, "text": "it"}]' 'g03 holds the reviewed occurrences and has no previous ones'
$V check "$RUN" reinterpret '.text_changes[0].added_groups.g03 | .entity_present and .entity_indexed and (.marker_chunk_ids | length) == 3' 'g03 has its node, name index and three marker chunks'
$V check "$RUN" reinterpret '.text_changes[0].retired_groups | keys == ["g01"] and .g01.entity_id == "'"$M01"'" and (.g01 | [.entity_present, .entity_indexed, .marker_present] | all(. == false)) and (.g01.previous_occurrences | length) == 2' 'g01 retires with its Entity, name index and markers'
$V check "$RUN" reinterpret '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .mention_entity_indexed, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed, .resolution_triplet_indexed] | all(. == false)' 'the old mention, link, fact, marker and triplets are physically absent'
$V check "$RUN" reinterpret '.sources.doc01.resolved_group_retirement | .fact_evidence_count == 0 and .mention_entity_id == "'"$M01"'"' 'no evidence remains for the old g01 fact'
$V check "$RUN" reinterpret '.sources.doc01.resolved_group_retirement | [.shared_fact_endpoint_present, .shared_fact_endpoint_indexed, .shared_relationship_text_indexed] | all' 'the shared endpoint and relationship text stay indexed'
$V check "$RUN" reinterpret '.text_changes[0].groups.g02 | .occurrences == .previous_occurrences and .marker_chunk_ids == .previous_marker_chunk_ids' 'g02 continues'
$V check "$RUN" reinterpret '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" reinterpret '.sources.doc01.unresolved_marker_present and .sources.doc01.unresolved_entity_present' 'the unresolved g02 group survives'
$V check "$RUN" reinterpret '.g03 | .resolution_status == "accepted" and .mention_entity_id == "'"$G3"'" and .target_entity_id == "'"$BK"'" and .target_present and .target_indexed' 'r03 accepts g03 to the derived Backup controller, which has a node and a name index'
$V check "$RUN" reinterpret '.g03 | .fact_present and .fact_text == "it limits oscillations" and (.evidence_chunk_ids | length) == 2' 'the fact is generated again from g03 with two evidence chunks'
$V check "$RUN" reinterpret '.text_changes[0].chunk_ids as $c | .g03.evidence_chunk_ids | all(. as $e | $c | index($e) != null)' 'the g03 fact evidence uses current doc01 chunks'
$V check "$RUN" reinterpret '[.result.facts[].source_id] == ["'"$M02"'"]' 'the default HC query returns only the doc02 fact'
$V check "$RUN" reinterpret '[.queries.helios_controller.facts[].source_id] == ["'"$M02"'"] and (.queries.helios_controller.facts | map(.source_id) | index("'"$M01"'") == null and index("'"$G3"'") == null)' 'the Helios controller no longer reaches the doc01 fact'
$V check "$RUN" reinterpret '.queries.backup_controller | .seed_entity_ids == ["'"$BK"'"] and (.facts | length) == 1 and (.facts[0] | .source_id == "'"$G3"'" and .identity.assignment_id == "r03" and .identity.target_entity_id == "'"$BK"'" and .text == "it limits oscillations")' 'the Backup controller returns the g03 fact as r03'
$V check "$RUN" reinterpret '.queries.backup_controller.facts[0].identity.occurrences == [{"start": 49, "end": 70, "text": "the backup controller"}, {"start": 97, "end": 99, "text": "it"}]' 'the retrieved annotation holds both g03 occurrences'
$V check "$RUN" reinterpret '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" reinterpret '.queries.helios_controller.facts[0].edge_id == "'"$FACT02"'"' 'the doc02 fact is unchanged'
$V check "$RUN" reinterpret '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed Helios controller fields are unchanged'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].source_id] == ["'"$M02"'"] and .unavailable_sources == []' 'a new process returns only the doc02 fact for HC'
$V drive "$RUN" main reopen_backup -- retrieve --query "What does Backup controller limit?"
$V check "$RUN" reopen_backup '[.facts[] | [.source_id, .identity.assignment_id]] == [["'"$G3"'", "r03"]] and .unavailable_sources == []' 'a new process returns the g03 fact for the Backup controller'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '([.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision])) == [[2, 2, 2], [1, 1, 1]] and .recovery_events == []' 'healthy reconcile keeps the revisions and records no incident'
$V check "$RUN" reconcile '[.result.facts[].source_id] == ["'"$M02"'"]' 'healthy reconcile does not bring the old g01 fact back'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .resolution_edge_present, .fact_edge_present, .current_marker_present] | all(. == false)' 'the retired group, link and fact stay absent'

$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '[.publications[] | select(.revision == 2)][0].description | fromjson | (.mention_resolutions | keys | sort) == ["r02", "r03"] and .mention_resolutions.r03.target_entity_id == "'"$BK"'" and (.entity_constructions["'"$BK"'"].name == "Backup controller")' 'the saved description holds r03 to the Backup controller recipe and no r01'
```

**I2 reinterpret to unresolved.** Proves `reinterpret-unresolved`. Guide: reinterpretation, "Changed interpretation to unresolved". The new text is `Helios controller (HC) regulates plasma heating. A controller adjusts coil current, and it limits oscillations.` The map is the same as I1. The guide gives g03 as `A controller` at `[49, 61)` and `it` at `[88, 90)`, with the same derived ID, and r03 as unresolved. It says g01 retires as in I1. It says g03's fact is generated again with two evidence chunks and two marker chunks, and no query returns it: the Helios controller and the default HC query return only doc02's fact. It says no new Entity is declared.

```bash journey I2
$V drive "$RUN" main fixture -- chunked-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main reinterpret -- reinterpret --case unresolved --source doc01 --expected-revision 1
G3=4827dc6d-3687-56e7-8a15-96a9dc30c070
$V check "$RUN" reinterpret '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" reinterpret '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" reinterpret '.text_changes[0] | .occurrence_map == {"g01": [null, ["g03", 1]], "g02": [["g02", 0]]} and .position_shift == null and .text_length_delta == -2' 'the occurrence map is the reviewed one and the text shrinks by two code points'
$V check "$RUN" reinterpret '.text_changes[0].groups.g03 | .previous_occurrences == [] and .occurrences == [{"start": 49, "end": 61, "text": "A controller"}, {"start": 88, "end": 90, "text": "it"}]' 'g03 holds the reviewed occurrences and has no previous ones'
$V check "$RUN" reinterpret '.text_changes[0].added_groups | keys == ["g03"] and .g03.entity_id == "'"$G3"'" and .g03.entity_present and .g03.entity_indexed and (.g03.marker_chunk_ids | length) == 2' 'g03 is the only fresh group, with its derived ID, node, name index and two marker chunks'
$V check "$RUN" reinterpret '.text_changes[0].retired_groups | keys == ["g01"] and .g01.entity_id == "'"$M01"'" and (.g01 | [.entity_present, .entity_indexed, .marker_present] | all(. == false))' 'g01 retires with its Entity, name index and markers'
$V check "$RUN" reinterpret '.sources.doc01.resolved_group_retirement | ([.mention_entity_present, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed, .resolution_triplet_indexed] | all(. == false)) and .fact_evidence_count == 0' 'the old g01 mention, link, fact, marker, triplets and evidence are physically absent'
$V check "$RUN" reinterpret '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" reinterpret '.g03 | .resolution_status == "unresolved" and .mention_entity_id == "'"$G3"'" and has("target_entity_id") == false' 'g03 is unresolved and has no target'
$V check "$RUN" reinterpret '.g03 | .fact_present and .fact_text == "it limits oscillations" and (.evidence_chunk_ids | length) == 2' 'the fact is generated again from the unresolved g03 with two evidence chunks'
$V check "$RUN" reinterpret '.text_changes[0].chunk_ids as $c | .g03.evidence_chunk_ids | all(. as $e | $c | index($e) != null)' 'the g03 fact evidence uses current doc01 chunks'
$V check "$RUN" reinterpret '[.result.facts[].source_id] == ["'"$M02"'"]' 'the default HC query returns only the doc02 fact'
$V check "$RUN" reinterpret '[.queries.helios_controller.facts[].source_id] == ["'"$M02"'"] and (.queries.helios_controller.facts | map(.source_id) | index("'"$M01"'") == null and index("'"$G3"'") == null)' 'the Helios controller does not reach the doc01 fact'
$V check "$RUN" reinterpret '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" reinterpret '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed Helios controller fields are unchanged'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].source_id] == ["'"$M02"'"] and .unavailable_sources == []' 'a new process returns only the doc02 fact'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '([.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision])) == [[2, 2, 2], [1, 1, 1]] and .recovery_events == []' 'healthy reconcile keeps the revisions and records no incident'
$V check "$RUN" reconcile '[.result.facts[].source_id] == ["'"$M02"'"]' 'healthy reconcile does not bring the old g01 fact back'

$V drive "$RUN" main after -- status
$V check "$RUN" after '[.publications[] | select(.revision == 2)][0].description | fromjson | (.mention_resolutions | keys | sort) == ["r02", "r03"] and .mention_resolutions.r03.status == "unresolved" and (.entity_constructions | length) == 6' 'the saved description holds r03 unresolved and declares no new reusable Entity'
```

**I3 reinterpret fault and recovery.** Proves `reinterpret-fault`. Guide: reinterpretation, "Interrupted edits". The fence lists the stages (`replace_published` and `text_chunks`). The runner runs each stage in its own run. The guide says only doc02's fact returns and doc01 reports `publication_failed` with an incident ID, and the saved plan holds the reviewed map. It says `reconcile` completes revision 2, gives the same g03 and Backup controller IDs, and resolves the same incident with one verified attempt. The Backup controller query then returns the g03 fact.

```bash journey I3 stages=replace_published,text_chunks
$V drive "$RUN" main fixture -- chunked-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
G3=4827dc6d-3687-56e7-8a15-96a9dc30c070
BK=30d7405d-10a3-5a53-a8da-8c707cb12310

$V drive "$RUN" main fail -- reinterpret --case new-entity --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '[.publications[] | select(.state == "failed")][0].plan.text_change.occurrence_map == {"g01": [null, ["g03", 1]], "g02": [["g02", 0]]}' 'the saved plan holds the reviewed map'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'
$V check "$RUN" before '[.publications[] | select(.state == "failed")][0].description | fromjson | .mention_groups.g03.entity_id == "'"$G3"'" and .mention_resolutions.r03.target_entity_id == "'"$BK"'"' 'the saved description holds the derived g03 and Backup controller IDs'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '.text_changes[0].added_groups.g03 | .entity_id == "'"$G3"'" and .entity_present and .entity_indexed and (.marker_chunk_ids | length) == 3' 'g03 has its saved ID, node, name index and three marker chunks'
$V check "$RUN" reconcile '.text_changes[0] | .retired_groups.g01.entity_id == "'"$M01"'" and (.retired_groups.g01 | [.entity_present, .entity_indexed, .marker_present] | all(. == false)) and .retired_chunks_absent and .retired_chunk_vectors_absent' 'g01 and the retired chunks are absent'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed] | all(. == false)' 'the old g01 fact is physically absent'
$V check "$RUN" reconcile '[.result.facts[].source_id] == ["'"$M02"'"]' 'the default HC query returns only the doc02 fact'

$V drive "$RUN" main backup -- retrieve --query "What does Backup controller limit?"
$V check "$RUN" backup '[.facts[] | [.source_id, .identity.assignment_id, .identity.target_entity_id]] == [["'"$G3"'", "r03", "'"$BK"'"]] and .unavailable_sources == []' 'the Backup controller returns the g03 fact'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

**I4 reinterpret scope.** Proves `reinterpret-scope`. Guide: reinterpretation, "Scope". `reinterpret` applies only the captured edit to doc01 of a fresh `chunked-fixture`. The guide says a wrong revision guard is refused as a stale revision, a second case after a first is refused with the scope message, doc02 is refused, and none of the refusals change the saved revisions.

```bash journey I4
$V drive "$RUN" main fixture -- chunked-fixture

$V drive "$RUN" main stale -- reinterpret --case new-entity --source doc01 --expected-revision 2
$V check "$RUN" stale '.error == "IntentError" and (.message | test("Saved revision changed"))' 'a wrong revision guard is refused'
$V drive "$RUN" main other -- reinterpret --case new-entity --source doc02 --expected-revision 1
$V check "$RUN" other '.error == "IntentError" and (.message | test("requires doc01 of a chunked-fixture"))' 'doc02 is refused'
$V drive "$RUN" main first -- reinterpret --case unresolved --source doc01 --expected-revision 1
$V check "$RUN" first '.sources.doc01.saved_revision == 2' 'the captured case applies once'
$V drive "$RUN" main second -- reinterpret --case new-entity --source doc01 --expected-revision 2
$V check "$RUN" second '.error == "IntentError" and (.message | test("Changed interpretation requires doc01 of a fresh chunked-fixture"))' 'a second case on the same root is refused'
$V drive "$RUN" main repeat -- reinterpret --case unresolved --source doc01 --expected-revision 1
$V check "$RUN" repeat '.error == "IntentError" and (.message | test("Saved revision changed"))' 'the same case again is refused'
$V drive "$RUN" main after -- status
$V check "$RUN" after '(.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]) and .recovery_events == []' 'the refusals left both publications current at revisions 1 and 2 with no incident'
```

**K1 reusable to mention.** Proves `kind-to-mention`. Guide: reinterpretation, "Reusable to mention". The text stays `Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.` The occurrence map is `{"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]}`. The guide says doc01 drops v01 and the HC recipe, and the fresh group g03 holds `HC` at `[19, 21)` and resolves to the Helios controller as r03. It gives g03 as `uuid5(identity_data_id, "mention:r2:g03")` and says g01 and g02 continue unchanged. It says the rebuild keeps every chunk ID, because equal texts chunk the same way. It says the shared HC edge keeps doc02's contribution and owner only, the HC Entity stays with doc02 as its only owner and no second HC Entity exists. It says the default HC query returns only doc02's fact, and the Helios controller query returns both facts as at revision 1, with doc01's fact regenerated under the same fact ID.

```bash journey K1
$V drive "$RUN" main fixture -- chunked-fixture
D02=$(val fixture '.sources.doc02.identity_data_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
FACT01=$(val fixture '.sources.doc01.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')
HC=9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88
G3=4827dc6d-3687-56e7-8a15-96a9dc30c070

$V drive "$RUN" main mention -- change-kind --direction to-mention --source doc01 --expected-revision 1
$V check "$RUN" mention '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" mention '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" mention '.text_changes[0] | .occurrence_map == {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]} and .position_shift == null and .text_length_delta == 0 and .previous_text_sha256 == .text_sha256' 'the occurrence map is the reviewed one and the text is unchanged'
$V check "$RUN" mention '.text_changes[0] | .previous_chunk_ids == .chunk_ids and .content_ids_present_in_both == .chunk_ids and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .mention_ids_preserved' 'the rebuild keeps every chunk ID and evidence uses current chunks'
$V check "$RUN" mention '.text_changes[0].added_groups | keys == ["g03"] and .g03.entity_id == "'"$G3"'" and .g03.entity_present and .g03.entity_indexed and (.g03.marker_chunk_ids | length) == 1' 'g03 is the only fresh group, with its derived ID, node, name index and one marker chunk'
$V check "$RUN" mention '.text_changes[0].groups.g03 | .previous_occurrences == [] and .occurrences == [{"start": 19, "end": 21, "text": "HC"}]' 'g03 holds HC at [19,21)'
$V check "$RUN" mention '.text_changes[0].retired_groups == {} and (.text_changes[0].groups | keys == ["g01", "g02", "g03"])' 'no group is retired'
$V check "$RUN" mention '.sources.doc01 | .mention_entity_id == "'"$M01"'" and .resolution_target_entity_id == "'"$T01"'" and .original_marker_present and .original_fact_owned_by_chunk and .original_evidence_present' 'g01 keeps its Entity UUID, target, marker, fact and evidence'
$V check "$RUN" mention '.sources.doc01.identity_data_id as $d | [.queries.helios_controller.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT01"'"]' 'the g01 fact ID continues'
$V check "$RUN" mention '.shared_variant | .present and (.owners | length) == 1 and ([.contributions[].identity_data_id] == ["'"$D02"'"])' 'the shared HC edge keeps doc02 as its only owner and contribution'
$V check "$RUN" mention '.hc_entity | .id == "'"$HC"'" and .present and .indexed and .owner_count == 1 and .entity_ids_named_hc == ["'"$HC"'"]' 'the HC Entity stays with doc02 as its only owner, and no second HC Entity exists'
$V check "$RUN" mention '[.result.facts[].source_id] == ["'"$M02"'"] and ([.queries.hc.facts[].source_id] == ["'"$M02"'"])' 'the HC query no longer reaches the doc01 fact'
$V check "$RUN" mention '[.queries.helios_controller.facts[] | [.source_id, .edge_id]] | sort == ([["'"$M01"'", "'"$FACT01"'"], ["'"$M02"'", "'"$FACT02"'"]] | sort)' 'the Helios controller query returns both facts under their old IDs'
$V check "$RUN" mention '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" mention '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed Helios controller fields are unchanged'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].source_id] == ["'"$M02"'"] and .unavailable_sources == []' 'a new process returns only the doc02 fact for HC'
$V drive "$RUN" main reopen_helios -- retrieve --query "What does Helios controller limit?"
$V check "$RUN" reopen_helios '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts for the Helios controller'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '([.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision])) == [[2, 2, 2], [1, 1, 1]] and .recovery_events == []' 'healthy reconcile keeps the revisions and records no incident'
$V check "$RUN" reconcile '.shared_variant | (.owners | length) == 1 and ([.contributions[].identity_data_id] == ["'"$D02"'"])' 'healthy reconcile does not bring the doc01 HC contribution back'

$V drive "$RUN" main after -- status
$V check "$RUN" after '[.publications[] | select(.revision == 2)][0].description | fromjson | .variant_assignments == {} and (.entity_constructions | has("'"$HC"'") | not) and .mention_resolutions.r03.target_entity_id == "'"$T01"'" and .mention_resolutions.r03.status == "accepted"' 'the saved description has no variant and no HC recipe, and r03 accepts g03 to the Helios controller'
```

**K2 mention to reusable.** Proves `kind-to-reusable`. Guide: reinterpretation, "Mention to reusable". The journey runs the K1 command first, and K1 covers it. The text is unchanged and the map is `{"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]], "g03": [null]}`. The guide says g03 retires with its Entity, name index, marker, resolution and link. It says doc01 declares the HC recipe again and reads doc02's HC Entity through the corpus input `existing_HC`, which the new variant v02 lists in `input_refs`, so the Entity is validated and not derived. It says v02 is document-scoped to doc01 from HC to the Helios controller. It says the shared HC edge has contributions from doc01 (v02) and doc02, one HC Entity with two owners remains, and the HC query reaches both facts again as at revision 1, under the same fact IDs.

```bash journey K2
$V drive "$RUN" main fixture -- chunked-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
D02=$(val fixture '.sources.doc02.identity_data_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
BASE=$(val fixture '.result.facts | map([.source_id, .edge_id]) | sort | tojson')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')
HC=9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88
G3=4827dc6d-3687-56e7-8a15-96a9dc30c070

$V drive "$RUN" main mention -- change-kind --direction to-mention --source doc01 --expected-revision 1
$V check "$RUN" mention '.sources.doc01.saved_revision == 2' 'the first kind change reaches revision 2'

$V drive "$RUN" main reusable -- change-kind --direction to-reusable --source doc01 --expected-revision 2
$V check "$RUN" reusable '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 3, 3, 3], ["current", 1, 1, 1]]' 'doc01 is at 3/3/3 and doc02 stays at 1/1/1'
$V check "$RUN" reusable '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" reusable '.text_changes[0] | .occurrence_map == {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]], "g03": [null]} and .position_shift == null and .text_length_delta == 0 and .previous_text_sha256 == .text_sha256' 'the occurrence map is the reviewed one and the text is unchanged'
$V check "$RUN" reusable '.text_changes[0] | .previous_chunk_ids == .chunk_ids and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .mention_ids_preserved' 'the rebuild keeps every chunk ID and evidence uses current chunks'
$V check "$RUN" reusable '.text_changes[0] | .added_groups == {} and (.retired_groups | keys == ["g03"]) and .retired_groups.g03.entity_id == "'"$G3"'" and (.retired_groups.g03 | [.entity_present, .entity_indexed, .marker_present] | all(. == false)) and (.groups | keys == ["g01", "g02"])' 'g03 retires with its Entity, name index and marker, and no group is fresh'
$V check "$RUN" reusable '.sources.doc01 | .mention_entity_id == "'"$M01"'" and .resolution_target_entity_id == "'"$T01"'" and .original_marker_present and .original_fact_owned_by_chunk and .original_evidence_present' 'g01 keeps its Entity UUID, target, marker, fact and evidence'
$V check "$RUN" reusable '.shared_variant | .present and (.owners | length) == 2 and ([.contributions[] | [.identity_data_id, .assignment_id]] | sort) == ([["'"$D01"'", "v02"], ["'"$D02"'", "v01"]] | sort)' 'the shared HC edge has doc01 as v02 and doc02 as v01, and two owners'
$V check "$RUN" reusable '.hc_entity | .id == "'"$HC"'" and .present and .indexed and .owner_count == 2 and .entity_ids_named_hc == ["'"$HC"'"]' 'one HC Entity remains and both documents own it'
$V check "$RUN" reusable '[.result.facts[] | [.source_id, .edge_id]] | sort == '"$BASE" 'the HC query returns the same two facts as revision 1'
$V check "$RUN" reusable '[.queries.hc.facts[] | [.source_id, .edge_id]] | sort == '"$BASE" 'the HC query reaches doc01 again'
$V check "$RUN" reusable '[.queries.helios_controller.facts[] | [.source_id, .edge_id]] | sort == '"$BASE" 'the Helios controller returns the same two facts'
$V check "$RUN" reusable '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" reusable '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed Helios controller fields are unchanged'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[] | [.source_id, .edge_id]] | sort == '"$BASE" 'a new process returns the same two facts for HC'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '([.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision])) == [[3, 3, 3], [1, 1, 1]] and .recovery_events == []' 'healthy reconcile keeps the revisions and records no incident'
$V check "$RUN" reconcile '[.result.facts[] | [.source_id, .edge_id]] | sort == '"$BASE" 'healthy reconcile keeps the two facts'

$V drive "$RUN" main after -- status
$V check "$RUN" after '[.publications[] | select(.revision == 3)][0].description | fromjson | (.variant_assignments | keys) == ["v02"] and .variant_assignments.v02.applicability == {"kind": "document", "document_ref": "doc01"} and (.variant_assignments.v02.input_refs | index("existing_HC") != null) and .inputs.existing_HC.kind == "corpus_object" and .inputs.existing_HC.entity_id == "'"$HC"'" and (.mention_groups | keys) == ["g01", "g02"] and (.entity_constructions | has("'"$HC"'"))' 'the saved description names HC in v02 through the listed existing_HC input, declares the HC recipe and has no g03'
```

**K3 to-mention fault and recovery.** Proves `kind-fault` for the first kind change. Guide: reinterpretation, "Interrupted edits". The fence lists the stages (`replace_published` and `text_chunks`). The runner runs each stage in its own run. The guide says only doc02's fact returns and doc01 reports `publication_failed` with an incident ID, and the saved plan holds the reviewed map with equal previous and current texts. It says `reconcile` completes revision 2 with the saved g03 ID and resolves the same incident with one verified attempt. After recovery the shared HC edge has doc02's contribution only and the Helios controller query returns two facts.

```bash journey K3 stages=replace_published,text_chunks
$V drive "$RUN" main fixture -- chunked-fixture
D02=$(val fixture '.sources.doc02.identity_data_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
HC=9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88
G3=4827dc6d-3687-56e7-8a15-96a9dc30c070

$V drive "$RUN" main fail -- change-kind --direction to-mention --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '[.publications[] | select(.state == "failed")][0].plan.text_change | .occurrence_map == {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]} and .previous_text == .text' 'the saved plan holds the reviewed map and equal texts'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '.text_changes[0].added_groups.g03 | .entity_id == "'"$G3"'" and .entity_present and .entity_indexed and (.marker_chunk_ids | length) == 1' 'g03 has its saved ID, node, name index and marker chunk'
$V check "$RUN" reconcile '.text_changes[0] | .previous_chunk_ids == .chunk_ids and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'the chunks are the same and evidence uses them'
$V check "$RUN" reconcile '.shared_variant | (.owners | length) == 1 and ([.contributions[].identity_data_id] == ["'"$D02"'"])' 'the shared HC edge keeps doc02 as its only owner and contribution'
$V check "$RUN" reconcile '[.result.facts[].source_id] == ["'"$M02"'"]' 'the default HC query returns only the doc02 fact'

$V drive "$RUN" main helios -- retrieve --query "What does Helios controller limit?"
$V check "$RUN" helios '(.facts | length) == 2 and .unavailable_sources == []' 'the Helios controller returns both facts'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

**K4 to-reusable fault and recovery.** Proves `kind-fault` for the second kind change. Guide: reinterpretation, "Interrupted edits". The fence lists the stages (`replace_published` and `text_chunks`). The journey runs the K1 command first. The guide says doc01 is withheld at revision 3 with the incident ID while doc02's fact returns, and the saved plan holds the reviewed map with `g03` mapped to null. It says `reconcile` completes revision 3 with one HC Entity, the doc01 contribution v02 on the shared HC edge and a restored HC query.

```bash journey K4 stages=replace_published,text_chunks
$V drive "$RUN" main fixture -- chunked-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
D02=$(val fixture '.sources.doc02.identity_data_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
BASE=$(val fixture '.result.facts | map([.source_id, .edge_id]) | sort | tojson')
HC=9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88

$V drive "$RUN" main mention -- change-kind --direction to-mention --source doc01 --expected-revision 1
$V check "$RUN" mention '.sources.doc01.saved_revision == 2' 'the first kind change reaches revision 2'

$V drive "$RUN" main fail -- change-kind --direction to-reusable --expected-revision 2 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 3 and .verified_revision == 2)' 'doc01 is failed at revision 3 with last verified revision 2'
$V check "$RUN" before '[.publications[] | select(.state == "failed")][0].plan.text_change | .occurrence_map == {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]], "g03": [null]} and .previous_text == .text' 'the saved plan holds the reviewed map and equal texts'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 3, 3, 3], ["current", 1, 1, 1]]' 'reconcile completes revision 3 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 3 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 3 by one verified attempt'
$V check "$RUN" reconcile '.text_changes[0].retired_groups.g03 | [.entity_present, .entity_indexed, .marker_present] | all(. == false)' 'g03 is retired'
$V check "$RUN" reconcile '.shared_variant | (.owners | length) == 2 and ([.contributions[] | [.identity_data_id, .assignment_id]] | sort) == ([["'"$D01"'", "v02"], ["'"$D02"'", "v01"]] | sort)' 'the shared HC edge has doc01 as v02 and doc02 as v01'
$V check "$RUN" reconcile '[.result.facts[] | [.source_id, .edge_id]] | sort == '"$BASE" 'the HC query returns the same two facts as revision 1'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '([.facts[] | [.source_id, .edge_id]] | sort) == '"$BASE"' and .unavailable_sources == []' 'a new process returns the same two facts for HC'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 3]' 'both publications are current at revisions 1 and 3'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

**K5 kind-change scope.** Proves `kind-scope`. Guide: reinterpretation, "Scope". `change-kind` applies only to doc01 of a fresh `chunked-fixture` at revision 1 for `to-mention`, and only to a doc01 that `to-mention` produced at revision 2 for `to-reusable`. The guide says `to-reusable` on a fresh root is refused with the scope message, a repeat of `to-mention` is refused, a wrong revision guard is refused, and none of the refusals changes the saved revisions.

```bash journey K5
$V drive "$RUN" main fixture -- chunked-fixture

$V drive "$RUN" main early -- change-kind --direction to-reusable --source doc01 --expected-revision 1
$V check "$RUN" early '.error == "IntentError" and (.message | test("requires doc01 produced by to-mention"))' 'to-reusable is refused on a fresh root'
$V drive "$RUN" main other -- change-kind --direction to-mention --source doc02 --expected-revision 1
$V check "$RUN" other '.error == "IntentError" and (.message | test("requires doc01 of a chunked-fixture"))' 'doc02 is refused'
$V drive "$RUN" main first -- change-kind --direction to-mention --source doc01 --expected-revision 1
$V check "$RUN" first '.sources.doc01.saved_revision == 2' 'to-mention applies once'
$V drive "$RUN" main again -- change-kind --direction to-mention --source doc01 --expected-revision 2
$V check "$RUN" again '.error == "IntentError" and (.message | test("Reusable to mention requires doc01 of a fresh chunked-fixture"))' 'a repeat of to-mention is refused'
$V drive "$RUN" main stale -- change-kind --direction to-reusable --source doc01 --expected-revision 1
$V check "$RUN" stale '.error == "IntentError" and (.message | test("Saved revision changed"))' 'a wrong revision guard is refused'
$V drive "$RUN" main reinterpret -- reinterpret --case new-entity --source doc01 --expected-revision 2
$V check "$RUN" reinterpret '.error == "IntentError" and (.message | test("Changed interpretation requires doc01 of a fresh chunked-fixture"))' 'reinterpret is refused on a kind-change root'
$V drive "$RUN" main after -- status
$V check "$RUN" after '(.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]) and .recovery_events == []' 'the refusals left both publications current at revisions 1 and 2 with no incident'
```

## Gotchas

- The commands accept only their captured doc01 edits. They do not locate phrases, infer a map or match groups. See "Not yet supported" in the README.
- `reinterpret` changes the text, so each case grows or shrinks it and moves `it`. The kind changes keep the text and the chunk IDs. A changed `text_length_delta` or chunk ID in a kind change is a real mismatch.
- The default `retrieve` query asks about HC. After `to-mention` it returns only doc02's fact, and that is the expected result. Ask about the Helios controller or the Backup controller with `--query`, as the journeys do.
- After `reinterpret`, `.sources.doc01.mention_entity_id` names the retired g01, because the snapshot keeps that fixture constant. Read g03 from `.g03` and `.text_changes[0].added_groups`.
- An unresolved g03 holds a real fact in the graph but no query returns it. `.g03.fact_present` is the proof, and the absence from `retrieve` is the second half of it.
