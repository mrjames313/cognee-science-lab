# Occurrence changes

A user changes which text spans belong to doc01's mention groups on a `chunked-fixture` root. `remove-occurrences` drops an occurrence and retires an empty unresolved group. `retire-resolved-group` retires a resolved group with its local fact. `add-occurrences` adds an occurrence to a continuing group and publishes a new local group. `revise-occurrences` removes, keeps and adds occurrences in one edit. Each command guards on the saved revision, rebuilds doc01 from the captured replacement text, and leaves doc02 at revision 1. An interrupted run withholds doc01 until `reconcile` finishes it.

Guides: `docs/stage6_identity_occurrence_removal.md`, `docs/stage6_identity_resolved_retirement.md`, `docs/stage6_identity_occurrence_addition.md`, `docs/stage6_identity_mixed_occurrences.md`. The state after a user's Mac run is in `docs/stage6_checkpoint_history.md`, "Results verified on the user's Mac".

## Sub-features

- `remove-partial` keeps one occurrence of g01 and retires the empty unresolved group g02.
- `remove-fault` recovers from an injected failure during a removal.
- `retire-resolved` retires g01, its resolution, its local fact and its evidence. It keeps g02 and doc02's fact.
- `retire-fault` recovers from an injected failure during a retirement.
- `add-continuing` adds an occurrence to g01 and a new group g03 with its own local fact.
- `add-follow-up` runs a later prefix edit and a withdrawal after an addition.
- `add-fault` recovers from an injected failure during an addition.
- `mix` removes, keeps and adds occurrences of g01 in one edit and retires g02.
- `mix-fault` recovers from an injected failure during the mixed edit.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity chunked-fixture --root <new dir>`.
- Run `remove-occurrences`, `retire-resolved-group`, `add-occurrences` or `revise-occurrences` with `--root <dir> --source doc01 --expected-revision 1`.
- Add `--fault-stage replace_published` or `--fault-stage text_chunks` to inject a failure.
- Run `retrieve`, `status` and `reconcile --source doc01` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new `chunked-fixture` root. Both sources are current at revision 1.
- The fixture's doc01 text is `Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.` with a trailing newline.

**O1 remove an occurrence.** Proves `remove-partial`. Guide: occurrence removal, "Concrete example" and "Run and inspect". The occurrence map is `{"g01": [null, ["g01", 0]], "g02": [null]}`. The guide says g01 keeps only `it` at `[46, 48)` with its Entity UUID, resolution target and fact ID. It says g02 is retired with no Entity, index entry or marker. It says `position_shift` is null and a healthy `reconcile` does not bring g02 back.

```bash journey O1
$V drive "$RUN" main fixture -- chunked-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
D02=$(val fixture '.sources.doc02.identity_data_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
FACT01=$(val fixture '.sources.doc01.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main remove -- remove-occurrences --source doc01 --expected-revision 1
$V check "$RUN" remove '(.result.facts | length) == 2' 'two facts are retrieved'
$V check "$RUN" remove '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" remove '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end, .text]] == [[46, 48, "it"]]' 'the doc01 annotation contains only it at [46,48)'
$V check "$RUN" remove '.sources.doc01.mention_entity_id == "'"$M01"'" and .sources.doc01.resolution_target_entity_id == "'"$T01"'"' 'g01 keeps its Entity UUID and resolution target'
$V check "$RUN" remove '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT01"'"]' 'the g01 fact ID continues'
$V check "$RUN" remove '.sources.doc01 | .unresolved_marker_present == false and .unresolved_entity_present == false' 'the unresolved Entity and marker flags are false'
$V check "$RUN" remove '.text_changes[0].retired_groups.g02 | .entity_present == false and .entity_indexed == false and .marker_present == false' 'g02 has no Entity, index entry or marker'
$V check "$RUN" remove '.text_changes[0].occurrence_map == {"g01": [null, ["g01", 0]], "g02": [null]}' 'the occurrence map is the reviewed removal'
$V check "$RUN" remove '.text_changes[0] | .position_shift == null and (.text_length_delta | type) == "number" and .text_length_delta < 0' 'the shift is null and the text shrinks'
$V check "$RUN" remove '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .mention_ids_preserved' 'retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" remove '.sources.doc02 | .original_fact_present and .original_evidence_present and .unresolved_marker_present and .unresolved_entity_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact, evidence and unresolved group are unchanged'
$V check "$RUN" remove '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" remove '.shared_variant.contributions | map(.identity_data_id) | contains(["'"$D02"'"])' 'doc02 still contributes to the shared variant edge'
$V check "$RUN" remove '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'
$V check "$RUN" remove '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2 and .unresolved_marker_present == false and .unresolved_entity_present == false' 'healthy reconcile keeps doc01 at 2/2/2 and does not bring g02 back'
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps two facts and records no incident'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns two facts'
$V check "$RUN" reopen '[.facts[] | select(.identity.identity_data_id == "'"$D01"'") | .identity.occurrences[] | [.start, .end, .text]] == [[46, 48, "it"]]' 'a new process returns only it for doc01'
```

**O2 remove fault and recovery.** Proves `remove-fault`. Guide: occurrence removal, "Explicit recovery". The fence lists the stages (`replace_published` and `text_chunks`). The runner runs each stage in its own run. The guide gives the `replace_published` sequence. It says native tests also cover `text_chunks`. The guide says doc01 is withheld and doc02's complete fact stays available. It says `reconcile` completes retirement and resolves the same incident only after revision 2 verifies.

```bash journey O2 stages=replace_published,text_chunks
$V drive "$RUN" main fixture -- chunked-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')

$V drive "$RUN" main fail -- remove-occurrences --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"] and (.facts[0].evidence | length) == 2' 'only the complete doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '(.result.facts | length) == 2' 'two facts are returned'
$V check "$RUN" reconcile '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end, .text]] == [[46, 48, "it"]]' 'the doc01 annotation contains only it at [46,48)'
$V check "$RUN" reconcile '.text_changes[0].retired_groups.g02 | .entity_present == false and .entity_indexed == false and .marker_present == false' 'g02 is retired'
$V check "$RUN" reconcile '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'retired chunks and vectors are absent'
$V check "$RUN" reconcile '.sources.doc01 | .unresolved_marker_present == false and .unresolved_entity_present == false' 'the unresolved Entity and marker are gone'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns two facts and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

**O3 retire a resolved group.** Proves `retire-resolved`. Guide: resolved retirement, "Run" and "Scope". The replacement text is `Helios controller (HC) regulates plasma heating.` and the occurrence map is `{"g01": [null, null], "g02": [["g02", 0]]}`. The guide says only doc02's fact is retrieved. It says doc01 has three chunks and no primary marker, fact or evidence, and g02 continues at `[33, 39)`. It lists the retirement fields that must be false or zero and the shared fields that must be true. A later withdrawal keeps doc02's facts and doc01's unresolved marker.

```bash journey O3
$V drive "$RUN" main fixture -- chunked-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')

$V drive "$RUN" main retire -- retire-resolved-group --source doc01 --expected-revision 1
$V check "$RUN" retire '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc02.mention_entity_id]' 'only the doc02 fact is retrieved'
$V check "$RUN" retire '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" retire '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" retire '.sources.doc01.chunk_count == 3' 'doc01 has three chunks'
$V check "$RUN" retire '.text_changes[0].occurrence_map == {"g01": [null, null], "g02": [["g02", 0]]}' 'the occurrence map is the reviewed retirement'
$V check "$RUN" retire '.text_changes[0].groups.g02.occurrences | map([.start, .end]) == [[33, 39]]' 'g02 continues at [33,39)'
$V check "$RUN" retire '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .evidence_chunk_ids == []' 'retired chunks and vectors are absent and no obsolete evidence remains'
$V check "$RUN" retire '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .mention_entity_indexed, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed, .resolution_triplet_indexed] | all(. == false)' 'the retired mention, resolution link, fact, marker and triplets are absent'
$V check "$RUN" retire '.sources.doc01.resolved_group_retirement.fact_evidence_count == 0' 'no fact evidence remains'
$V check "$RUN" retire '.sources.doc01.resolved_group_retirement | [.shared_fact_endpoint_present, .shared_fact_endpoint_indexed, .shared_relationship_text_indexed] | all' 'the shared endpoint and relationship text stay indexed'
$V check "$RUN" retire '.sources.doc01 | [.original_marker_present, .original_fact_present, .original_fact_owned_by_chunk, .original_evidence_present] | all(. == false)' 'the primary marker, fact, ownership and evidence are absent'
$V check "$RUN" retire '.sources.doc01.unresolved_marker_present and .sources.doc01.unresolved_entity_present' 'the unresolved g02 group survives'
$V check "$RUN" retire '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" retire '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'healthy reconcile keeps doc01 at 2/2/2'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .resolution_edge_present, .fact_edge_present, .current_marker_present] | all(. == false)' 'the retired group, link and fact stay absent'
$V check "$RUN" reconcile '(.result.facts | length) == 1 and .recovery_events == []' 'healthy reconcile returns one fact and records no incident'

$V drive "$RUN" main wd -- withdraw --source doc01
$V check "$RUN" wd '.sources.doc01.state == "withdrawn" and .sources.doc01.unresolved_marker_present' 'withdrawal keeps the continuing unresolved marker'
$V check "$RUN" wd '.sources.doc02 | .state == "current" and .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'withdrawal keeps doc02 fact and evidence'
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].source_id] == ["'"$M02"'"] and .unavailable_sources == []' 'a new process returns only the doc02 fact'
```

**O4 retire fault and recovery.** Proves `retire-fault`. Guide: resolved retirement, "Interrupted retirement". The fence lists the stages (`replace_published` and `text_chunks`). The runner runs each stage in its own run. The guide says doc01 is withheld and doc02's fact stays available. It says `reconcile` completes cleanup at revision 2 and resolves the same incident.

```bash journey O4 stages=replace_published,text_chunks
$V drive "$RUN" main fixture -- chunked-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')

$V drive "$RUN" main fail -- retire-resolved-group --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '[.result.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | [.mention_entity_present, .mention_entity_indexed, .resolution_edge_present, .fact_edge_present, .current_marker_present, .fact_triplet_indexed, .resolution_triplet_indexed] | all(. == false)' 'the retired mention, link, fact and marker are absent'
$V check "$RUN" reconcile '.sources.doc01.resolved_group_retirement | [.shared_fact_endpoint_present, .shared_fact_endpoint_indexed, .shared_relationship_text_indexed] | all' 'the shared endpoint and relationship text stay indexed'
$V check "$RUN" reconcile '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'retired chunks and vectors are absent'
$V check "$RUN" reconcile '.sources.doc01.unresolved_marker_present and .sources.doc01.unresolved_entity_present' 'the unresolved g02 group survives'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].source_id] == ["'"$M02"'"] and .unavailable_sources == []' 'a new process returns only the doc02 fact and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

**O5 add occurrences, then edit and withdraw.** Proves `add-continuing` and `add-follow-up`. Guide: occurrence addition, "Captured edit", "Run" and "Reopen and reconcile". The occurrence map is `{"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]}`. The guide says three facts, doc01 at 2/2/2, doc02 at 1/1/1, no unavailable source and no incident. It says g01 keeps its Entity ID and goes from two occurrences to three. It says g03 is new with its Entity, name index, accepted resolution `r03`, and current marker chunks. The handoff records two marker chunks for g03. The guide says a later prefix edit at expected revision 2 keeps g03 and its fact at revision 3. It says withdrawal withholds doc01's two facts and keeps doc02.

```bash journey O5
$V drive "$RUN" main fixture -- chunked-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
EV02=$(val fixture '.sources.doc02.fact_evidence_chunk_ids | tojson')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main add -- add-occurrences --source doc01 --expected-revision 1
G3=$(val add '.text_changes[0].added_groups.g03.entity_id')
$V check "$RUN" add '(.result.facts | length) == 3' 'three facts are retrieved'
$V check "$RUN" add '[.result.facts[].text] | sort == ["it limits oscillations", "it limits oscillations", "the controller limits oscillations"]' 'two local facts from doc01 and the unchanged doc02 fact'
$V check "$RUN" add '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" add '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" add '.text_changes[0] | .occurrence_map == {"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]} and .position_shift == null' 'the occurrence map is the reviewed addition and the shift is null'
$V check "$RUN" add '.text_changes[0].groups.g01 | (.previous_occurrences | length) == 2 and (.occurrences | length) == 3 and .entity_id == "'"$M01"'"' 'g01 goes from two to three occurrences and keeps its Entity ID'
$V check "$RUN" add '.text_changes[0].groups.g03 | (.previous_occurrences | length) == 0 and (.occurrences | length) == 1' 'g03 has no previous occurrence and one current occurrence'
$V check "$RUN" add '.text_changes[0].added_groups.g03 | .entity_present and .entity_indexed and (.marker_chunk_ids | length) == 2' 'g03 has its node, name index and two current marker chunks'
$V check "$RUN" add '.text_changes[0] | .retired_groups == {} and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .mention_ids_preserved' 'no group is retired, retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" add '. as $r | [$r.result.facts[] | select(.identity.assignment_id == "r03") | [.source_id, .identity.target_entity_id]] == [[$r.text_changes[0].added_groups.g03.entity_id, $r.borrowed_entity.id]]' 'the new fact is r03 from the g03 Entity to the reusable controller'
$V check "$RUN" add '.text_changes[0].chunk_ids as $c | [.result.facts[] | select(.identity.assignment_id == "r03") | .evidence[].chunk_id] | length > 0 and all(. as $e | $c | index($e) != null)' 'the new fact evidence uses current doc01 chunks'
$V check "$RUN" add '.sources.doc02 | .original_fact_present and .original_evidence_present and .fact_evidence_chunk_ids == '"$EV02" 'doc02 fact and evidence are unchanged'
$V check "$RUN" add '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" add '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 3 and .unavailable_sources == []' 'a new process returns three facts'
$V check "$RUN" reopen 'any(.facts[]; .source_id == "'"$G3"'" and .identity.assignment_id == "r03")' 'a new process returns the g03 fact'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '(.result.facts | length) == 3 and .recovery_events == []' 'healthy reconcile keeps three facts and records no incident'
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'healthy reconcile does not change revisions'
$V check "$RUN" reconcile 'any(.result.facts[]; .source_id == "'"$G3"'" and .identity.assignment_id == "r03")' 'the g03 fact remains'

$V drive "$RUN" main edit -- edit-text --source doc01 --expected-revision 2
$V check "$RUN" edit '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[3, 3, 3], [1, 1, 1]]' 'the prefix edit reaches revision 3 for doc01'
$V check "$RUN" edit '.text_changes[0] | .groups.g03.entity_id == "'"$G3"'" and .position_shift == 10 and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'the edit keeps g03 and verifies evidence against the new chunks'
$V check "$RUN" edit '(.result.facts | length) == 3 and any(.result.facts[]; .source_id == "'"$G3"'" and .identity.assignment_id == "r03")' 'three facts remain, including the g03 fact'

$V drive "$RUN" main wd -- withdraw --source doc01
$V check "$RUN" wd '.sources.doc01 | .state == "withdrawn" and .original_marker_present and .original_fact_present and .original_evidence_present' 'withdrawal keeps the original-owned marker, fact and evidence'
$V drive "$RUN" main final -- retrieve
$V check "$RUN" final '[.facts[].source_id] == ["'"$M02"'"] and .unavailable_sources == []' 'a new process returns only the doc02 fact'
```

**O6 add fault and recovery.** Proves `add-fault`. Guide: occurrence addition, "Interrupted addition". The fence lists the stages (`replace_published` and `text_chunks`). The runner runs each stage in its own run. The guide says only doc02's fact returns and doc01 reports `publication_failed` with an incident ID. It says `reconcile` completes revision 2, returns three facts and resolves the same incident with one verified recovery attempt.

```bash journey O6 stages=replace_published,text_chunks
$V drive "$RUN" main fixture -- chunked-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')

$V drive "$RUN" main fail -- add-occurrences --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")] | length == 1 and (.[0] | .revision == 2 and .verified_revision == 1)' 'doc01 is failed at revision 2 with last verified revision 1'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '(.result.facts | length) == 3' 'three facts are returned'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '.text_changes[0] | .groups.g01.entity_id == "'"$M01"'" and (.groups.g01.occurrences | length) == 3 and (.added_groups.g03 | .entity_present and .entity_indexed and (.marker_chunk_ids | length) == 2)' 'g01 continues with three occurrences and g03 has its node, index and two marker chunks'
$V check "$RUN" reconcile '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'retired chunks and vectors are absent'
$V check "$RUN" reconcile 'any(.result.facts[]; .identity.assignment_id == "r03")' 'the g03 fact is returned'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 3 and .unavailable_sources == []' 'a new process returns three facts and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | all(.state == "current") and ([.[].revision] | sort) == [1, 2]' 'both publications are current at revisions 1 and 2'
$V check "$RUN" after '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

**O7 remove, keep and add in one edit.** Proves `mix`. Guide: mixed occurrences, "Captured edit" and "Run". The occurrence map is `{"g01": [null, ["g01", 0]], "g02": [null]}`, the same map as removal. The guide says g01 keeps its Entity UUID, resolution target and fact ID, and its occurrences become `it` at `[46, 48)` and the added `the controller` at `[86, 100)`. g01 marks two chunks and its fact uses one of them, because the added occurrence lies in a chunk with no fact evidence. It says g02 retires with no Entity, index entry or marker, no group is added, and a healthy `reconcile` keeps all of this.

```bash journey O7
$V drive "$RUN" main fixture -- chunked-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
M01=$(val fixture '.sources.doc01.mention_entity_id')
T01=$(val fixture '.sources.doc01.resolution_target_entity_id')
FACT01=$(val fixture '.sources.doc01.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')
FACT02=$(val fixture '.sources.doc02.identity_data_id as $d | .result.facts[] | select(.identity.identity_data_id == $d) | .edge_id')

$V drive "$RUN" main mix -- revise-occurrences --source doc01 --expected-revision 1
$V check "$RUN" mix '(.result.facts | length) == 2' 'two facts are retrieved'
$V check "$RUN" mix '[.sources.doc01, .sources.doc02] | map([.saved_revision, .verified_revision, .registered_revision]) == [[2, 2, 2], [1, 1, 1]]' 'doc01 is at 2/2/2 and doc02 stays at 1/1/1'
$V check "$RUN" mix '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end, .text]] == [[46, 48, "it"], [86, 100, "the controller"]]' 'the doc01 annotation has the kept it and the added the controller'
$V check "$RUN" mix '.sources.doc01.mention_entity_id == "'"$M01"'" and .sources.doc01.resolution_target_entity_id == "'"$T01"'"' 'g01 keeps its Entity UUID and resolution target'
$V check "$RUN" mix '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT01"'"]' 'the g01 fact ID continues'
$V check "$RUN" mix '.text_changes[0] | .occurrence_map == {"g01": [null, ["g01", 0]], "g02": [null]} and .added_groups == {} and .position_shift == null' 'the occurrence map is the reviewed one, no group is added and the shift is null'
$V check "$RUN" mix '.text_changes[0].retired_groups.g02 | .entity_present == false and .entity_indexed == false and .marker_present == false' 'g02 has no Entity, index entry or marker'
$V check "$RUN" mix '.sources.doc01 | (.mention_marker_chunk_ids | length) == 2 and (.fact_evidence_chunk_ids | length) == 1 and (.fact_evidence_chunk_ids - .mention_marker_chunk_ids) == []' 'g01 marks two chunks and its fact uses one of them'
$V check "$RUN" mix '.text_changes[0] | .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks and .mention_ids_preserved' 'retired chunks and vectors are absent and evidence uses current chunks'
$V check "$RUN" mix '.sources.doc02.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .edge_id] == ["'"$FACT02"'"]' 'the doc02 fact is unchanged'
$V check "$RUN" mix '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2 and .unresolved_marker_present == false and .unresolved_entity_present == false' 'healthy reconcile keeps doc01 at 2/2/2 and does not bring g02 back'
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps two facts and records no incident'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[] | select(.identity.identity_data_id == "'"$D01"'") | .identity.occurrences[] | [.start, .end, .text]] == [[46, 48, "it"], [86, 100, "the controller"]]' 'a new process returns both doc01 occurrences'
```

**O8 mixed fault and recovery.** Proves `mix-fault`. Guide: mixed occurrences, "Interrupted edit". The fence lists the stages (`replace_published` and `text_chunks`). The runner runs each stage in its own run. The guide says doc01 is withheld and doc02's fact stays available, and the saved plan holds the reviewed map. It says `reconcile` completes revision 2 and resolves the same incident with one verified attempt.

```bash journey O8 stages=replace_published,text_chunks
$V drive "$RUN" main fixture -- chunked-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')

$V drive "$RUN" main fail -- revise-occurrences --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed")][0].plan.text_change.occurrence_map == {"g01": [null, ["g01", 0]], "g02": [null]}' 'the saved plan holds the reviewed map'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2 for doc01 and leaves doc02 at revision 1'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolving_revision == 2 and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is restored at revision 2 by one verified attempt'
$V check "$RUN" reconcile '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end, .text]] == [[46, 48, "it"], [86, 100, "the controller"]]' 'the doc01 annotation has both occurrences'
$V check "$RUN" reconcile '.text_changes[0].retired_groups.g02 | .entity_present == false and .entity_indexed == false and .marker_present == false' 'g02 is retired'

$V drive "$RUN" main after -- status
$V check "$RUN" after '(.publications | all(.state == "current")) and (.recovery_events | all(.resolved_at != null))' 'both publications are current and no incident stays open'
```

## Gotchas

- The four commands accept only their captured doc01 edit. They do not locate arbitrary phrases or infer which occurrences continue. See "Not yet supported" in the README.
- The occurrence maps are checked exactly. A map from a different guide version fails the check, and that is a real mismatch.
- `position_shift` is null for removal, retirement, addition and the mixed edit. A deletion has no single global shift.
- After a successful retirement, the primary mention ID stays in `resolved_group_retirement` as a diagnostic constant. Its absence checks are the proof, not the ID.
- `O5` runs `edit-text` at expected revision 2 on a root that already has an addition. The guide documents this sequence. If it is refused, report the refusal text.
- Only doc02's fact survives a retirement. Do not expect doc01 facts from `retrieve` until a later addition publishes new ones.
- Run `retrieve` after each maintenance step in a new process. The step's own JSON comes from the process that wrote the change.
