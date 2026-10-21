# Multi-source withdrawal

A user withdraws one identity source from a two-source fixture. The source stops contributing identity interpretation. The other source keeps its own interpretation and the shared support that it owns. The original documents, their markers, facts and evidence stay in place. An interrupted withdrawal hides the source until the user repeats `withdraw`.

Guide: `docs/stage6_identity_first_slice.md`, sections "Two-source lifecycle fixture" and "Withdrawal implementation and failures".

## Sub-features

- `withdraw-first` withdraws doc01, then doc02.
- `withdraw-reverse` withdraws doc02, then doc01.
- `withdraw-repeat` repeats a withdrawal, including after the other source is withdrawn.
- `withdraw-fault` fails a withdrawal at an injected stage, withholds the source, then retries.
- `withdraw-reconcile-guard` rejects `reconcile` while a withdrawal is incomplete.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>`.
- Run `uv run python -m cognee_lab.identity withdraw --root <dir> --source doc01|doc02`.
- Add `--fault-stage withdraw_contributions|withdraw_owners|withdraw_verification` to inject a failure.
- Run `retrieve`, `status` and `reconcile --source doc02` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new `multi-fixture` root. Withdrawal changes the root for good.
- The fixture's two sources are current at revision 1 before the first withdrawal.

**W1 withdraw doc01, then doc02.** Guide: the "Two-source lifecycle fixture" table. The table says that withdrawing doc01 leaves 1 shared contribution and 1 owner, both from doc02. Withdrawing doc02 leaves no variant edge and no shared singleton. Original markers, mention nodes, facts, ownership and evidence remain after each step. The guide also says that repeated withdrawal works and that `reconcile --source doc02` checks the second source before it retires.

```bash journey W1
$V drive "$RUN" main fixture -- multi-fixture
$V check "$RUN" fixture '.shared_variant | (.contributions | length) == 2 and (.owners | length) == 2' 'both sources contribute to the shared variant edge'
$V check "$RUN" fixture '(.result.facts | length) == 2' 'both facts are retrievable before withdrawal'
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main wd01 -- withdraw --source doc01
$V check "$RUN" wd01 '[.sources.doc01.state, .sources.doc02.state] == ["withdrawn", "current"]' 'doc01 is withdrawn and doc02 is current'
$V check "$RUN" wd01 '.shared_variant | (.contributions | length) == 1 and (.owners | length) == 1' 'one shared contribution and one owner remain'
$V check "$RUN" wd01 '.sources.doc02.identity_data_id as $d | $d != null and .shared_variant.contributions[0].identity_data_id == $d' 'the remaining contribution belongs to doc02'
$V check "$RUN" wd01 '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton stays present and indexed'
$V check "$RUN" wd01 '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc02.mention_entity_id]' 'only the doc02 fact is returned'
$V check "$RUN" wd01 '.sources.doc01 | .private_singleton_present == false and .private_singleton_indexed == false' 'the doc01 private singleton and its name vector are removed'
$V check "$RUN" wd01 '.sources.doc02 | .private_singleton_present and .private_singleton_indexed' 'the doc02 private singleton survives'
$V check "$RUN" wd01 '.sources.doc01 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present' 'doc01 original marker, fact, ownership and evidence remain'
$V check "$RUN" wd01 '.sources.doc01 | .unresolved_marker_present and .unresolved_entity_present' 'the doc01 unresolved mention survives'
$V check "$RUN" wd01 '.sources.doc01 | .saved_revision == 1 and .verified_revision == 1' 'withdrawal keeps the last published revision'
$V check "$RUN" wd01 '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'
$V check "$RUN" wd01 '.recovery_events == []' 'no incident'

$V drive "$RUN" main ret1 -- retrieve
$V check "$RUN" ret1 '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns one fact and reports no unavailable source'

$V drive "$RUN" main wd01-again -- withdraw --source doc01
$V check "$RUN" wd01-again '.sources.doc01.state == "withdrawn" and .sources.doc02.state == "current"' 'repeating the withdrawal changes nothing'

$V drive "$RUN" main rec02 -- reconcile --source doc02
$V check "$RUN" rec02 '.sources.doc02 | .state == "current" and .saved_revision == 1 and .verified_revision == 1' 'reconcile finds doc02 current'
$V check "$RUN" rec02 '.sources.doc01.state == "withdrawn"' 'reconcile does not reactivate doc01'
$V check "$RUN" rec02 '(.result.facts | length) == 1' 'reconcile returns the one doc02 fact'

$V drive "$RUN" main wd02 -- withdraw --source doc02
$V check "$RUN" wd02 '[.sources.doc01.state, .sources.doc02.state] == ["withdrawn", "withdrawn"]' 'both sources are withdrawn'
$V check "$RUN" wd02 '.shared_variant.present == false' 'no physical variant edge remains'
$V check "$RUN" wd02 '.shared_singleton_present == false and .shared_singleton_indexed == false' 'the shared singleton is absent from the graph and the name index'
$V check "$RUN" wd02 '.result.facts == []' 'no fact is returned'
$V check "$RUN" wd02 '.sources | all(.[]; .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present)' 'original markers, facts, ownership and evidence remain in both sources'
$V check "$RUN" wd02 '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'

$V drive "$RUN" main wd01-last -- withdraw --source doc01
$V check "$RUN" wd01-last '[.sources.doc01.state, .sources.doc02.state] == ["withdrawn", "withdrawn"]' 'repeating doc01 after doc02 changes nothing'

$V drive "$RUN" main ret2 -- retrieve
$V check "$RUN" ret2 '.facts == [] and .unavailable_sources == []' 'a new process returns no facts and no unavailable source'
$V drive "$RUN" main status -- status
$V check "$RUN" status '.publications | length == 2 and all(.state == "withdrawn" and .verified_revision == 1)' 'both publications are withdrawn at their last published revision'
$V check "$RUN" status '.recovery_events == []' 'no incident'
```

**W2 withdraw doc02, then doc01.** Guide: "Use a fresh root to try the reverse removal order", and the native test matrix "covers both removal orders". The guide's table states the doc01-first values. The values below are the same table with the two sources swapped, which is an inference from symmetry.

```bash journey W2
$V drive "$RUN" main fixture -- multi-fixture
$V check "$RUN" fixture '.shared_variant | (.contributions | length) == 2 and (.owners | length) == 2' 'both sources contribute to the shared variant edge'

$V drive "$RUN" main wd02 -- withdraw --source doc02
$V check "$RUN" wd02 '[.sources.doc01.state, .sources.doc02.state] == ["current", "withdrawn"]' 'doc02 is withdrawn and doc01 is current'
$V check "$RUN" wd02 '.shared_variant | (.contributions | length) == 1 and (.owners | length) == 1' 'one shared contribution and one owner remain'
$V check "$RUN" wd02 '.sources.doc01.identity_data_id as $d | $d != null and .shared_variant.contributions[0].identity_data_id == $d' 'the remaining contribution belongs to doc01'
$V check "$RUN" wd02 '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton stays present and indexed'
$V check "$RUN" wd02 '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc01.mention_entity_id]' 'only the doc01 fact is returned'
$V check "$RUN" wd02 '.sources.doc02 | .private_singleton_present == false and .private_singleton_indexed == false' 'the doc02 private singleton and its name vector are removed'
$V check "$RUN" wd02 '.sources.doc01 | .private_singleton_present and .private_singleton_indexed' 'the doc01 private singleton survives'
$V check "$RUN" wd02 '.sources.doc02 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present' 'doc02 original marker, fact, ownership and evidence remain'
$V check "$RUN" wd02 '.recovery_events == []' 'no incident'

$V drive "$RUN" main ret1 -- retrieve
$V check "$RUN" ret1 '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns one fact and reports no unavailable source'

$V drive "$RUN" main wd01 -- withdraw --source doc01
$V check "$RUN" wd01 '[.sources.doc01.state, .sources.doc02.state] == ["withdrawn", "withdrawn"]' 'both sources are withdrawn'
$V check "$RUN" wd01 '.shared_variant.present == false' 'no physical variant edge remains'
$V check "$RUN" wd01 '.shared_singleton_present == false and .shared_singleton_indexed == false' 'the shared singleton is absent from the graph and the name index'
$V check "$RUN" wd01 '.result.facts == []' 'no fact is returned'
$V check "$RUN" wd01 '.sources | all(.[]; .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present)' 'original markers, facts, ownership and evidence remain in both sources'

$V drive "$RUN" main ret2 -- retrieve
$V check "$RUN" ret2 '.facts == [] and .unavailable_sources == []' 'a new process returns no facts and no unavailable source'
$V drive "$RUN" main status -- status
$V check "$RUN" status '.publications | length == 2 and all(.state == "withdrawn" and .verified_revision == 1)' 'both publications are withdrawn'
```

**W3 withdrawal fault and retry.** Guide: "Withdrawal implementation and failures". Run the block once per stage, each in its own run, with `STAGE` set to `withdraw_contributions`, `withdraw_owners` and `withdraw_verification`. The guide expects the following results.

- The command fails with an injected error and a recovery event.
- `retrieve` returns only doc02's fact, and doc01 appears in `unavailable_sources`.
- Publication `reconcile` is rejected while the withdrawal is incomplete.
- A retry records `outcome: withdrawn` on the same event.
- After the retry, the deliberate retirement is absent from `unavailable_sources`.

```bash journey W3 stages=withdraw_contributions,withdraw_owners,withdraw_verification
$V drive "$RUN" main fixture -- multi-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')

$V drive "$RUN" main fail -- withdraw --source doc01 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'

$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[].state] | sort == ["current", "failed"]' 'doc01 is failed and doc02 is current'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .operation == "withdraw" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open withdraw incident labeled as fault injection'

$V drive "$RUN" main blocked -- reconcile --source doc01
$V check "$RUN" blocked '.error == "IntentError" and (.message | contains("Retry the failed withdrawal explicitly"))' 'reconcile is rejected with the retry instruction while the withdrawal is incomplete'

$V drive "$RUN" main retry -- withdraw --source doc01
$V check "$RUN" retry '[.sources.doc01.state, .sources.doc02.state] == ["withdrawn", "current"]' 'the retry withdraws doc01 and leaves doc02 current'
$V check "$RUN" retry '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "withdrawn" and .resolved_at != null)' 'the same incident records outcome withdrawn'
$V check "$RUN" retry '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc02.mention_entity_id]' 'only the doc02 fact is returned'
$V check "$RUN" retry '.shared_variant | (.contributions | length) == 1 and (.owners | length) == 1' 'one shared contribution and one owner remain'
$V check "$RUN" retry '.sources.doc02.identity_data_id as $d | $d != null and .shared_variant.contributions[0].identity_data_id == $d' 'the remaining contribution belongs to doc02'
$V check "$RUN" retry '.sources.doc01 | .private_singleton_present == false and .private_singleton_indexed == false' 'the doc01 private singleton and its name vector are removed'
$V check "$RUN" retry '.sources.doc01 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present' 'doc01 original marker, fact, ownership and evidence remain'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '(.facts | length) == 1 and .unavailable_sources == []' 'a deliberate retirement is not unavailable'
$V drive "$RUN" main final -- status
$V check "$RUN" final '[.publications[].state] | sort == ["current", "withdrawn"]' 'doc01 is withdrawn and doc02 is current'
$V check "$RUN" final '.recovery_events | length > 0 and all(.resolved_at != null)' 'no incident stays open'
```

## Gotchas

- Withdrawal keeps the registered Data items and the saved description. It is not a Forget. Do not expect original facts to disappear.
- `retrieve` after a withdrawal omits the withdrawn source's identity interpretation, not its original text.
- A failed withdrawal shows `state: "failed"` with the last published revision, not the next one. A withdrawal never advances the revision.
- `drive` exits 1 for the injected failure and for the rejected `reconcile`. That is the expected result. Check `.error`.
- `reconcile --source doc01` before any withdrawal is healthy. The `blocked` step runs only while the withdrawal is incomplete.
- The guide states the doc01-first table only. The doc02-first values in `W2` and the stage-independent expectations in `W3` follow the same table and the native test matrix. If a stage differs, report it.
- Only one open withdrawal incident per source is expected. Do not stack two faults in one root.
