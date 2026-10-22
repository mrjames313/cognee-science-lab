# Source lifecycle: forget and re-add

A user forgets one source of a two-source fixture. The source's original document, its generated identity source and everything only they owned leave the stores. The other source keeps its own interpretation, the shared Entities it owns, and the shared edge with only its contribution. A source that another source consumed is refused, with the dependents listed. An interrupted forget withholds the source until `reconcile` finishes it. A forgotten source can be added again, and it continues at the next revision with new derived UUIDs.

Guide: `docs/stage6_identity_forget.md`.

## Sub-features

- `forget-healthy` forgets doc01 and leaves doc02 intact.
- `forget-status` shows the forgotten row in `status` and keeps it out of `retrieve`.
- `forget-refuses-dependents` refuses a forget while another current source consumed the document or an Entity only it owns, and lists them.
- `forget-after-withdrawal` forgets a source once its dependent is withdrawn.
- `forget-fault` fails a forget at an injected stage, withholds the source, then finishes it with `reconcile`.
- `readd` publishes a forgotten source again at the next revision with new UUIDs for its mentions and for every Entity the forget removed.
- `readd-fence` refuses a re-add that would consume a source whose forget is unfinished (native test `test_native_readd_of_a_consumer_waits_for_the_unfinished_forget`).
- `readd-fault` fails a re-add at an injected stage, withholds the source, then finishes it with `reconcile`, which writes the captured facts the failure skipped.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>`. Add `--dependent` to make doc02 consume doc01's text and private singleton.
- Run `uv run python -m cognee_lab.identity forget --root <dir> --source doc01 --expected-revision 1`.
- Add `--fault-stage forget_contributions|forget_identity|forget_document|forget_verification|forget_identity_committed|forget_document_committed` to inject a failure, then run `reconcile --source doc01`. The two `_committed` stages fail after Cognee committed the Data delete and before it swept the item's evidence rows and stored files.
- Add `--fault-stage nodes|identity_edges|verification` to `readd` to fail the re-add, then run `reconcile --source doc01`.
- Run `uv run python -m cognee_lab.identity readd --root <dir> --source doc01 --expected-revision 1` on a root whose doc01 is forgotten.
- Run `retrieve` and `status` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new `multi-fixture` root. Forget changes the root for good.
- The fixture's two sources are current at revision 1 before the forget.

**F1 forget doc01, then add it again.** Proves `forget-healthy`, `forget-status` and `readd`. Guide: "Forget doc01" and "Re-add" give every value. After the forget, doc01's `forget` report is all absent, doc02's entry is unchanged, the shared variant edge keeps one contribution and one owner from doc02, the HC Entity keeps one owner, the shared singleton and the borrowed controller survive, and only doc02's fact returns. `status` shows doc01 `forgotten` at revision 1 with a forget plan, and `retrieve` lists no unavailable source. A second forget and a reconcile are refused. The re-add publishes doc01 at revision 2 with a mention UUID and a private singleton UUID that differ from revision 1 (the forget removed both, and no removed UUID returns), restores both facts, both contributions and both HC owners, and a second re-add is refused.

```bash journey F1
$V drive "$RUN" main fixture -- multi-fixture
$V check "$RUN" fixture '.shared_variant | (.contributions | length) == 2 and (.owners | length) == 2' 'both sources contribute to the shared variant edge'
$V check "$RUN" fixture '(.result.facts | length) == 2' 'both facts are retrievable before the forget'
$V check "$RUN" fixture '.hc_entity.present and (.hc_entity.owners | length) == 2' 'the HC Entity has two owners'
M01=$(val fixture '.sources.doc01.mention_entity_id')
PS01=$(val fixture '.sources.doc01.private_singleton_entity_id')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state] == ["forgotten", "current"]' 'doc01 is forgotten and doc02 is current'
$V check "$RUN" forget '.sources.doc01 | .saved_revision == 1 and .verified_revision == 1' 'the forgotten row keeps revision 1'
$V check "$RUN" forget '.sources.doc01.forget | .original_data_present == false and .identity_data_present == false and .stored_files_present == [] and .document_node_present == false' 'the original and identity Data, the stored files and the document node are gone'
$V check "$RUN" forget '.sources.doc01.forget | .chunks_present == [] and .chunk_vectors_present == [] and .mention_nodes_present == [] and .mention_vectors_present == []' 'chunks, chunk vectors, mention nodes and mention vectors are gone'
$V check "$RUN" forget '.sources.doc01.forget | .original_fact_present == false and .evidence_rows == 0 and .private_singleton_present == false and .private_singleton_indexed == false' 'the fact, its evidence rows and the private singleton are gone'
$V check "$RUN" forget '.sources.doc01.forget | .identity_contribution_present == false and .owned_nodes == 0 and .owned_edges == 0' 'no contribution and no owned graph object remain'
$V check "$RUN" forget '.shared_variant | (.contributions | length) == 1 and (.owners | length) == 1' 'one shared contribution and one owner remain'
$V check "$RUN" forget '.sources.doc02.identity_data_id as $d | $d != null and .shared_variant.contributions[0].identity_data_id == $d' 'the remaining contribution belongs to doc02'
$V check "$RUN" forget '.hc_entity.present and (.hc_entity.owners | length) == 1' 'the HC Entity survives with one owner'
$V check "$RUN" forget '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton stays present and indexed'
$V check "$RUN" forget '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'
$V check "$RUN" forget '.sources.doc02 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present and .private_singleton_present and .unresolved_entity_present' 'doc02 keeps its marker, fact, ownership, evidence, singleton and unresolved mention'
$V check "$RUN" forget '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc02.mention_entity_id]' 'only the doc02 fact is returned'
$V check "$RUN" forget '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'

$V drive "$RUN" main ret1 -- retrieve
$V check "$RUN" ret1 '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns one fact and reports no unavailable source'
$V drive "$RUN" main status1 -- status
$V check "$RUN" status1 '[.publications[].state] | sort == ["current", "forgotten"]' 'status shows one forgotten and one current publication'
$V check "$RUN" status1 '.publications[] | select(.state == "forgotten") | .revision == 1 and .verified_revision == 1 and .plan.operation == "identity_forget"' 'the forgotten row keeps revision 1 and its forget plan'
$V check "$RUN" status1 '.recovery_events == []' 'no incident'

$V drive "$RUN" main again -- forget --source doc01 --expected-revision 1
$V check "$RUN" again '.error == "IntentError" and (.message | contains("Forgotten source"))' 'a second forget is refused'
$V drive "$RUN" main rec-blocked -- reconcile --source doc01
$V check "$RUN" rec-blocked '.error == "IntentError" and (.message | contains("Forgotten source"))' 'reconcile of a forgotten source is refused'

$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '.sources.doc01 | .state == "current" and .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2 and .registered_matches_saved' 'doc01 is current again at revision 2'
$V check "$RUN" readd '.sources.doc01.mention_entity_id != "'"$M01"'" and (.sources.doc01.mention_entity_id | length) == 36' 'the re-added mention has a new UUID'
$V check "$RUN" readd '.sources.doc01.private_singleton_entity_id != "'"$PS01"'" and (.sources.doc01.private_singleton_entity_id | length) == 36' 'the private singleton the forget removed returns under a new UUID'
$V check "$RUN" readd '.sources.doc01 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present and .unresolved_marker_present and .unresolved_entity_present and .private_singleton_present and .private_singleton_indexed' 'doc01 has its marker, fact, evidence, unresolved mention and singleton again'
$V check "$RUN" readd '(.result.facts | length) == 2 and ([.result.facts[].source_id] | sort) == ([.sources.doc01.mention_entity_id, .sources.doc02.mention_entity_id] | sort)' 'both facts return, one per current mention'
$V check "$RUN" readd '.shared_variant | (.contributions | length) == 2 and (.owners | length) == 2' 'both sources contribute to the shared variant edge again'
$V check "$RUN" readd '.hc_entity.present and (.hc_entity.owners | length) == 2' 'the HC Entity has two owners again'
$V check "$RUN" readd '.borrowed_entity.updated_at == '"$BU"' and .borrowed_entity.description == "'"$BD"'"' 'the borrowed controller fields are unchanged'
$V check "$RUN" readd '.recovery_events == []' 'no incident'

$V drive "$RUN" main ret2 -- retrieve
$V check "$RUN" ret2 '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts'
$V drive "$RUN" main status2 -- status
$V check "$RUN" status2 '.publications | length == 2 and all(.state == "current")' 'both publications are current'
$V check "$RUN" status2 '[.publications[] | select(.revision == 2)] | length == 1 and .[0].verified_revision == 2 and .[0].plan.operation == "identity_publish"' 'the re-added source is at verified revision 2 with a publish plan'
$V drive "$RUN" main readd-again -- readd --source doc01 --expected-revision 2
$V check "$RUN" readd-again '.error == "IntentError" and (.message | contains("Re-add needs a forgotten source"))' 'a current source cannot be re-added'
```

**F2 a dependent refuses the forget until it is withdrawn.** Proves `forget-refuses-dependents` and `forget-after-withdrawal`. Guide: "A dependent". With `--dependent`, doc02's r01 decision lists doc01's text and doc01's private singleton as inputs. The forget is refused before any write, with both inputs in `details.dependents`. Nothing changes. After doc02 is withdrawn it consumes nothing, so the forget proceeds. doc02 keeps its original fact and evidence, the HC Entity and shared singleton have no owner left, and no fact returns.

```bash journey F2
$V drive "$RUN" main fixture -- multi-fixture --dependent
$V check "$RUN" fixture '[.sources.doc01.state, .sources.doc02.state] == ["current", "current"] and (.result.facts | length) == 2' 'both sources are current with two facts'
D02=$(val fixture '.sources.doc02.identity_data_id')
D01=$(val fixture '.sources.doc01.identity_data_id')
O01=$(val fixture '.result.facts[] | select(.identity.identity_data_id == "'"$D01"'") | .evidence[0].data_id')

$V drive "$RUN" main refused -- forget --source doc01 --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | contains("reconsider the dependents"))' 'the forget is refused because of a dependent'
$V check "$RUN" refused '.details.dependents | length == 2 and all(.identity_data_id == "'"$D02"'")' 'both dependents are doc02 inputs'
$V check "$RUN" refused '[.details.dependents[] | [.input_ref, .kind]] | sort == [["doc01_instrument", "corpus_object"], ["doc01_text", "source_text"]]' 'doc02 consumed the text and the private singleton'
$V check "$RUN" refused '[.details.dependents[] | select(.kind == "source_text") | .consumed] == ["'"$O01"'"]' 'the consumed text is doc01 original document'

$V drive "$RUN" main unchanged -- retrieve
$V check "$RUN" unchanged '(.facts | length) == 2 and .unavailable_sources == []' 'a refused forget changes nothing'
$V drive "$RUN" main before -- status
$V check "$RUN" before '.publications | length == 2 and all(.state == "current")' 'both publications stay current'
$V check "$RUN" before '.recovery_events == []' 'a refusal is not an incident'

$V drive "$RUN" main wd02 -- withdraw --source doc02
$V check "$RUN" wd02 '[.sources.doc01.state, .sources.doc02.state] == ["current", "withdrawn"]' 'doc02 is withdrawn'

$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state] == ["forgotten", "withdrawn"]' 'doc01 is forgotten once its dependent is withdrawn'
$V check "$RUN" forget '.sources.doc01.forget | .original_data_present == false and .identity_data_present == false and .chunks_present == [] and .mention_nodes_present == [] and .original_fact_present == false and .evidence_rows == 0 and .owned_nodes == 0 and .owned_edges == 0' 'nothing of doc01 remains'
$V check "$RUN" forget '.sources.doc02 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present' 'the withdrawn doc02 keeps its original marker, fact, ownership and evidence'
$V check "$RUN" forget '.hc_entity.present == false and .shared_variant.present == false' 'the HC Entity and the shared edge have no owner left'
$V check "$RUN" forget '.shared_singleton_present == false and .shared_singleton_indexed == false' 'the shared singleton is gone'
$V check "$RUN" forget '.result.facts == [] and .result.unavailable_sources == [] and .recovery_events == []' 'no fact, no unavailable source, no incident'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '.facts == [] and .unavailable_sources == []' 'a new process returns nothing and reports no unavailable source'
```

**F3 forget fault and reconcile.** Proves `forget-fault`. Guide: "Interrupted forgets". The fence lists the four stages. The runner runs each in its own run. The command fails with an injected error and a recovery event. `retrieve` returns only doc02's fact and lists doc01 as unavailable with the incident. `status` shows the open forget incident at that stage. `withdraw` and `readd` are refused while the forget is incomplete. `reconcile --source doc01` finishes the forget: doc01 is forgotten with nothing left, doc02 is intact, and the same incident records `outcome: forgotten` with one verified forget attempt.

```bash journey F3 stages=forget_contributions,forget_identity,forget_document,forget_verification,forget_identity_committed,forget_document_committed
$V drive "$RUN" main fixture -- multi-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')

$V drive "$RUN" main fail -- forget --source doc01 --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'

$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[].state] | sort == ["current", "failed"]' 'doc01 is failed and doc02 is current'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .operation == "forget" and .stage == ("'"$STAGE"'" | sub("_committed$"; "")) and .origin == "test/fault_injection" and .resolved_at == null)' 'one open forget incident at the stage the fault interrupted'

$V drive "$RUN" main blocked -- withdraw --source doc01
$V check "$RUN" blocked '.error == "IntentError" and (.message | contains("Retry the failed forget explicitly"))' 'withdraw is refused while the forget is incomplete'
$V drive "$RUN" main blocked2 -- readd --source doc01 --expected-revision 1
$V check "$RUN" blocked2 '.error == "IntentError" and (.message | contains("Re-add needs a forgotten source"))' 'readd is refused while the forget is incomplete'

$V drive "$RUN" main rec -- reconcile --source doc01
$V check "$RUN" rec '[.sources.doc01.state, .sources.doc02.state] == ["forgotten", "current"]' 'reconcile finishes the forget'
$V check "$RUN" rec '.sources.doc01.forget | .original_data_present == false and .identity_data_present == false and .stored_files_present == [] and .document_node_present == false and .chunks_present == [] and .chunk_vectors_present == [] and .mention_nodes_present == [] and .mention_vectors_present == [] and .original_fact_present == false and .evidence_rows == 0 and .private_singleton_present == false and .identity_contribution_present == false and .owned_nodes == 0 and .owned_edges == 0' 'nothing of doc01 remains'
$V check "$RUN" rec '.sources.doc02 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present and .private_singleton_present and .unresolved_entity_present' 'doc02 is intact'
$V check "$RUN" rec '. as $r | [$r.result.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" rec '.shared_variant | (.contributions | length) == 1 and (.owners | length) == 1' 'one shared contribution and one owner remain'
$V check "$RUN" rec '.hc_entity.present and (.hc_entity.owners | length) == 1' 'the HC Entity survives with one owner'
$V check "$RUN" rec '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "forgotten" and .resolved_at != null and .recovery_attempts[-1].method == "forget" and .recovery_attempts[-1].outcome == "verified")' 'the same incident records outcome forgotten with one verified forget attempt'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '(.facts | length) == 1 and .unavailable_sources == []' 'a finished forget is not unavailable'
$V drive "$RUN" main final -- status
$V check "$RUN" final '[.publications[].state] | sort == ["current", "forgotten"]' 'doc01 is forgotten and doc02 is current'
$V check "$RUN" final '.recovery_events | length == 1 and all(.resolved_at != null)' 'no incident stays open'
```

**F4 re-add fault and reconcile.** Proves `readd-fault`. Guide: "Interrupted re-adds". doc01 is forgotten, then re-added with `--fault-stage nodes`, which fails before the captured facts are written. `retrieve` lists doc01 as unavailable. `reconcile --source doc01` finishes the re-add: it writes the missing facts, doc01 is current at revision 2 with its fact and evidence, doc02 is intact, and the incident records `outcome: restored`.

```bash journey F4
$V drive "$RUN" main fixture -- multi-fixture
M02=$(val fixture '.sources.doc02.mention_entity_id')
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state] == ["forgotten", "current"]' 'doc01 is forgotten'

$V drive "$RUN" main fail -- readd --source doc01 --expected-revision 1 --fault-stage nodes
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '[.facts[].source_id] == ["'"$M02"'"]' 'only the doc02 fact is returned'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'doc01 is unavailable with the incident id'
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[].state] | sort == ["current", "failed"]' 'doc01 is failed and doc02 is current'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .operation == "publish" and .stage == "nodes" and .resolved_at == null)' 'one open publish incident at the nodes stage'

$V drive "$RUN" main rec -- reconcile --source doc01
$V check "$RUN" rec '.sources.doc01 | .state == "current" and .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'reconcile finishes the re-add at revision 2'
$V check "$RUN" rec '.sources.doc01 | .original_marker_present and .original_fact_present and .original_fact_owned_by_chunk and .original_evidence_present and .private_singleton_present' 'the reconcile wrote the missing fact and evidence'
$V check "$RUN" rec '.sources.doc02 | .original_marker_present and .original_fact_present and .original_evidence_present and .private_singleton_present' 'doc02 is intact'
$V check "$RUN" rec '(.result.facts | length) == 2 and .result.unavailable_sources == []' 'both facts return and nothing is unavailable'
$V check "$RUN" rec '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolved_at != null and .recovery_attempts[-1].outcome == "verified")' 'the same incident records outcome restored with one verified attempt'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '(.facts | length) == 2 and .unavailable_sources == []' 'a new process returns both facts'
```

## Gotchas

- Forget needs `--expected-revision`. Withdraw does not.
- A forgotten source leaves its row in `status`, with its last revision and description. `retrieve` neither returns it nor lists it as unavailable.
- Only a current source can be forgotten. A withdrawn source, or a source whose first publication failed, is refused.
- `forget` refuses a source that another current source consumed. Withdraw or forget the dependent first. This refusal is a placeholder until step-4 item 3 decides what erasure does to dependents.
- `drive` exits 1 for the injected failure, the refused forget and the refused `readd`. That is the expected result. Check `.error`, and `.details` for the dependents.
- `readd` works only on a forgotten source and publishes at the forgotten revision plus one. It reads `source.txt` or `source02.txt` from the root, so do not change those files.
- Only one open forget incident per source is expected. Do not stack two faults in one root.
