# Source lifecycle: forget, erasure of dependents, and re-add

A user forgets one source. The source's original document, its generated identity source and everything only they owned leave the stores, and its ledger row keeps only a tombstone of identifiers. The other source keeps its own interpretation, the shared Entities it owns, and the shared edge with only its contribution. A forget that removes another source's decisions needs the dry run's token: then it erases the source and writes each dependent's removal revision, which unresolves a resolution or drops a variant that read the forgotten source. An interrupted forget withholds the source until `reconcile` finishes it, and an interrupted removal resumes the same way. Any source can be forgotten: current, withdrawn, or one whose first publication failed. A forgotten source can be added again from the caller's files, and it continues at the next revision with new derived UUIDs.

Guide: `docs/stage6_identity_forget.md`.

## Sub-features

- `forget-healthy` forgets doc01 and leaves doc02 intact.
- `forget-status` shows the forgotten row in `status` as a tombstone with a scrubbed plan, and keeps it out of `retrieve`.
- `forget-dry-run` reports, before any write, each dependent decision a forget would remove, the input that causes it, and the token.
- `forget-confirmation` refuses a forget that removes another source's decisions without the token, and refuses a token whose impact changed (`impact_changed`).
- `forget-removes-dependents` erases the source, then unresolves or drops each dependent decision in a revision of the dependent; the dependent's local fact stays and no identity query reaches it.
- `forget-dependent-interrupted` stops after the forget completed and before or inside a dependent's removal revision; `reconcile` or `forget` on the forgotten source resumes it, and `readd` waits.
- `forget-dependent-blocked` lists a dependent whose own withdrawal failed as blocked; its removal waits until that attempt finishes.
- `forget-dependent-failed-replacement` applies the removal to a dependent's failed replacement in its saved revision, and the replacement finishes with it; nothing is left unfinished.
- `forget-dependent-failed-publication` applies the removal to a dependent's failed first publication in its saved revision, and the publication finishes with it. Before that the dependent's own `reconcile` cannot finish, and nothing of it is served.
- `forget-any-source` forgets a withdrawn source and a source whose first publication failed.
- `forget-fault` fails a forget at an injected stage, withholds the source, then finishes it with `reconcile`.
- `readd` publishes a forgotten source again at the next revision with new UUIDs for its mentions and for every Entity the forget removed: a named one derives from a key that names it, an unnamed one from the removed UUID.
- `readd-changed-files` re-adds from the caller's text and identity files when they changed, and refuses when they disagree.
- `readd-fence` refuses a re-add that would consume a source whose forget is unfinished (native test `test_native_readd_of_a_consumer_waits_for_the_unfinished_forget`).
- `readd-fault` fails a re-add at an injected stage, withholds the source, then finishes it with `reconcile`, which writes the captured facts the failure skipped.
- `forget-glossary` forgets the glossary that doc01 read: doc01's r01 is unresolved, v01 and HC go, and the glossary comes back from its files without the decisions.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>`. Add `--dependent` to make doc02 consume doc01's text and private singleton.
- Run `forget --root <dir> --source doc01 --expected-revision 1 --dry-run` for the report and token, then `forget --root <dir> --source doc01 --expected-revision 1 --confirm <token>`. A forget with no dependent needs no token.
- Add `--fault-stage forget_impact|forget_contributions|forget_identity|forget_document|forget_verification|forget_identity_committed|forget_document_committed` to inject a failure, then run `reconcile --source doc01`. The two `_committed` stages fail after Cognee committed the Data delete and before it swept the item's evidence rows and stored files.
- Add `--fault-stage forget_dependents` (before the first removal revision) or `forget_dependent_revision` (inside it: at `replace_registered` for a replacement, at `nodes` for a failed publication) to interrupt a dependent's removal after the forget completed, then run `reconcile --source doc01`.
- Add `--fault-stage nodes|identity_edges|verification` to `readd` to fail the re-add, then run `reconcile --source doc01`.
- Run `uv run python -m cognee_lab.identity readd --root <dir> --source doc01 --expected-revision 1` on a root whose doc01 is forgotten.
- Run `retrieve` and `status` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new root. Forget changes the root for good.
- The fixture's two sources are current at revision 1 before the forget.

**F1 forget doc01, then add it again.** Proves `forget-healthy`, `forget-status` and `readd`. Guide: "Forget doc01", "The tombstone" and "Re-add" give every value. Nothing depends on doc01, so the forget needs no token. After the forget, doc01's `forget` report is all absent, doc02's entry is unchanged, the shared variant edge keeps one contribution and one owner from doc02, the HC Entity keeps one owner, the shared singleton and the borrowed controller survive, and only doc02's fact returns. `status` shows doc01 `forgotten` at revision 1 whose description is a tombstone holding the revision 1 mention UUID and no occurrence text, and whose forget plan keeps no edge property and no runtime profile. `retrieve` lists no unavailable source. A second forget and a reconcile are refused. The re-add publishes doc01 at revision 2 with a mention UUID and a private singleton UUID that differ from revision 1 (the forget removed both, and no removed UUID returns). No resolution or variant names the private singleton, so its replacement is `uuid5(doc01 identity, "entity:r2:replaces:<removed UUID>")`, `9b7f8477-...`. The re-add restores both facts, both contributions and both HC owners, and a second re-add is refused.

```bash journey F1
$V drive "$RUN" main fixture -- multi-fixture
$V check "$RUN" fixture '.shared_variant | (.contributions | length) == 2 and (.owners | length) == 2' 'both sources contribute to the shared variant edge'
$V check "$RUN" fixture '(.result.facts | length) == 2' 'both facts are retrievable before the forget'
$V check "$RUN" fixture '.hc_entity.present and (.hc_entity.owners | length) == 2' 'the HC Entity has two owners'
M01=$(val fixture '.sources.doc01.mention_entity_id')
PS01=$(val fixture '.sources.doc01.private_singleton_entity_id')
BU=$(val fixture '.borrowed_entity.updated_at')
BD=$(val fixture '.borrowed_entity.description')

$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
$V check "$RUN" dry '.dry_run and .confirmation_required == false and .dependents == [] and (.token | length) == 64' 'the dry run finds no dependent'
$V check "$RUN" dry '.removed_entities | index("'"$M01"'") != null and index("'"$PS01"'") != null' 'the dry run lists the mention and the private singleton as removed'

$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state] == ["forgotten", "current"]' 'doc01 is forgotten and doc02 is current'
$V check "$RUN" forget '.sources.doc01 | .saved_revision == 1 and .verified_revision == 1' 'the forgotten row keeps revision 1'
$V check "$RUN" forget '.sources.doc01.forget | .original_data_present == false and .identity_data_present == false and .stored_files_present == [] and .document_node_present == false' 'the original and identity Data, the stored files and the document node are gone'
$V check "$RUN" forget '.sources.doc01.forget | .chunks_present == [] and .chunk_vectors_present == [] and .mention_nodes_present == [] and .mention_vectors_present == []' 'chunks, chunk vectors, mention nodes and mention vectors are gone'
$V check "$RUN" forget '.sources.doc01.forget | .original_fact_present == false and .evidence_rows == 0 and .private_singleton_present == false and .private_singleton_indexed == false and .removed_entities_present == []' 'the fact, its evidence rows, the private singleton and every removed Entity are gone'
$V check "$RUN" forget '.sources.doc01.forget | .identity_contribution_present == false and .owned_nodes == 0 and .owned_edges == 0' 'no contribution and no owned graph object remain'
$V check "$RUN" forget '.forget.dependents_revised == [] and .dependents_failed == null' 'no dependent was revised'
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
$V check "$RUN" status1 '.publications[] | select(.state == "forgotten") | .description | fromjson | .kind == "identity_source_tombstone" and .revision == 1 and .mention_ids.g01 == "'"$M01"'"' 'the forgotten row holds a tombstone with the revision 1 mention UUID'
$V check "$RUN" status1 '.publications[] | select(.state == "forgotten") | (tostring | contains("The controller") | not) and (.plan | has("runtime_profile") | not) and all(.plan.edges[]; has("properties") | not)' 'the forgotten row keeps no occurrence text, no runtime profile and no edge property'
$V check "$RUN" status1 '.recovery_events == []' 'no incident'

$V drive "$RUN" main again -- forget --source doc01 --expected-revision 1
$V check "$RUN" again '.error == "IntentError" and (.message | contains("Forgotten source"))' 'a second forget is refused'
$V drive "$RUN" main rec-blocked -- reconcile --source doc01
$V check "$RUN" rec-blocked '.error == "IntentError" and (.message | contains("Forgotten source"))' 'reconcile of a forgotten source is refused'

$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '.sources.doc01 | .state == "current" and .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2 and .registered_matches_saved' 'doc01 is current again at revision 2'
$V check "$RUN" readd '.sources.doc01.mention_entity_id != "'"$M01"'" and (.sources.doc01.mention_entity_id | length) == 36' 'the re-added mention has a new UUID'
$V check "$RUN" readd '.sources.doc01.private_singleton_entity_id != "'"$PS01"'" and (.sources.doc01.private_singleton_entity_id | length) == 36' 'the private singleton the forget removed returns under a new UUID'
$V check "$RUN" readd '.sources.doc01.private_singleton_entity_id == "9b7f8477-b420-57e6-a343-ff73d921aa82"' 'nothing names the private singleton, so its UUID derives from the removed one'
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

**F2 a forget removes a dependent's decision once confirmed.** Proves `forget-dry-run`, `forget-confirmation` and `forget-removes-dependents`. Guide: "A dependent". With `--dependent`, doc02's r01 lists doc01's text and doc01's private singleton as inputs. The dry run lists r01 as unresolved, citing `doc01_text` (`source_text`, doc01's document) and `doc01_instrument` (`corpus_object`, the private singleton), and names doc02's g01 mention as the fact that loses its identity link. Without the token the forget is refused before any write, with the same report in `details`. With the token doc01 is forgotten and doc02 gets revision 2: r01 is unresolved under producer `forget_<doc01 identity>_r2` with inputs `doc01` and `existing_A`, and `doc01_text` and `doc01_instrument` are gone. doc02's local fact stays, and no fact returns for the HC query. A re-add of doc01 brings back doc01's fact, not doc02's decision.

```bash journey F2
$V drive "$RUN" main fixture -- multi-fixture --dependent
$V check "$RUN" fixture '[.sources.doc01.state, .sources.doc02.state] == ["current", "current"] and (.result.facts | length) == 2' 'both sources are current with two facts'
D02=$(val fixture '.sources.doc02.identity_data_id')
D01=$(val fixture '.sources.doc01.identity_data_id')
M02=$(val fixture '.sources.doc02.mention_entity_id')
O01=$(val fixture '.result.facts[] | select(.identity.identity_data_id == "'"$D01"'") | .evidence[0].data_id')

$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '.confirmation_required and (.dependents | length) == 1 and .dependents[0].identity_data_id == "'"$D02"'" and .dependents[0].blocked == false' 'the dry run lists doc02 as the one dependent'
$V check "$RUN" dry '.dependents[0].decisions | length == 1 and .[0].assignment == "r01" and .[0].outcome == "unresolved"' 'r01 would become unresolved'
$V check "$RUN" dry '[.dependents[0].decisions[0].citing[] | [.input_ref, .kind]] | sort == [["doc01_instrument", "corpus_object"], ["doc01_text", "source_text"]]' 'r01 cites doc01 text and private singleton'
$V check "$RUN" dry '[.dependents[0].decisions[0].citing[] | select(.kind == "source_text") | .consumed] == ["'"$O01"'"]' 'the consumed text is doc01 original document'
$V check "$RUN" dry '.dependents[0].unlinked_mentions == ["'"$M02"'"] and .counts.unlinked_facts == 1' 'doc02 g01 fact loses its identity link'
$V check "$RUN" dry '.dependents[0].dropped_inputs == ["doc01_instrument", "doc01_text"] and .dependents[0].dropped_entities == []' 'the two inputs go and no Entity does'
$V check "$RUN" dry '(.caller_files | length) > 0 and all(.caller_files[]; contains("/roots/main/"))' 'the dry run lists the caller files it leaves'

$V drive "$RUN" main refused -- forget --source doc01 --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | startswith("This forget removes other sources"))' 'the forget is refused without the token'
$V check "$RUN" refused '.details.token == "'"$T"'" and (.details.dependents | length) == 1' 'the refusal carries the dry-run report'
$V drive "$RUN" main unchanged -- retrieve
$V check "$RUN" unchanged '(.facts | length) == 2 and .unavailable_sources == []' 'a refused forget changes nothing'
$V drive "$RUN" main before -- status
$V check "$RUN" before '.publications | length == 2 and all(.state == "current")' 'both publications stay current'
$V check "$RUN" before '.recovery_events == []' 'a refusal is not an incident'

$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1 --confirm "$T"
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state] == ["forgotten", "current"]' 'doc01 is forgotten and doc02 is current'
$V check "$RUN" forget '.sources.doc01.forget | .original_data_present == false and .identity_data_present == false and .chunks_present == [] and .mention_nodes_present == [] and .original_fact_present == false and .evidence_rows == 0 and .owned_nodes == 0 and .owned_edges == 0 and .private_singleton_present == false' 'nothing of doc01 remains'
$V check "$RUN" forget '.forget.dependents_revised == [{"identity_data_id": "'"$D02"'", "revision": 2}] and .dependents_failed == null' 'doc02 was revised at revision 2'
$V check "$RUN" forget '.sources.doc02 | .saved_revision == 2 and .verified_revision == 2 and .registered_matches_saved' 'doc02 is current at revision 2'
$V check "$RUN" forget '.sources.doc02.decisions.r01 | .status == "unresolved" and .producer_ref == "forget_'"$D01"'_r2" and .input_refs == ["doc01", "existing_A"]' 'r01 is unresolved under the removal producer'
$V check "$RUN" forget '.sources.doc02.decisions.v01.status == "accepted" and (.sources.doc02.input_keys | index("doc01_text") == null and index("doc01_instrument") == null)' 'v01 stays and doc01 inputs are gone'
$V check "$RUN" forget '.sources.doc02 | .original_fact_present and .original_evidence_present and .original_marker_present' 'doc02 keeps its local fact and evidence'
$V check "$RUN" forget '.result.facts == [] and .result.unavailable_sources == [] and .recovery_events == []' 'no fact reaches doc02 mention, nothing is unavailable, no incident'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '.facts == [] and .unavailable_sources == []' 'a new process returns nothing and reports no unavailable source'
$V drive "$RUN" main again -- forget --source doc01 --expected-revision 1
$V check "$RUN" again '.error == "IntentError" and (.message | contains("Forgotten source"))' 'nothing is left to finish, so a second forget is refused'

$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '.sources.doc01.state == "current" and .sources.doc02.decisions.r01.status == "unresolved"' 'the re-add does not bring back the removed decision'
$V check "$RUN" readd '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc01.mention_entity_id]' 'only doc01 fact returns'
```

**F3 forget fault and reconcile.** Proves `forget-fault`. Guide: "Interrupted forgets". The fence lists the seven stages. The runner runs each in its own run. The command fails with an injected error and a recovery event. `retrieve` returns only doc02's fact and lists doc01 as unavailable with the incident. `status` shows the open forget incident at that stage. `withdraw` and `readd` are refused while the forget is incomplete. `reconcile --source doc01` finishes the forget: doc01 is forgotten with nothing left, doc02 is intact, and the same incident records `outcome: forgotten` with one verified forget attempt and no message.

```bash journey F3 stages=forget_impact,forget_contributions,forget_identity,forget_document,forget_verification,forget_identity_committed,forget_document_committed
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
$V check "$RUN" rec '.recovery_events[0] | .message == null and all(.recovery_attempts[]; .message == null) and .reason_code == "injected_failure"' 'the forgotten source incident keeps its code and loses its message'

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

**F5 a token whose impact changed is refused.** Proves `forget-confirmation`. Guide: "Confirmation". On a `--dependent` root doc02 is forgotten, so the dry run of doc01's forget finds no dependent. doc02's re-add reads doc01 again from its caller file, so the token no longer matches: the forget is refused with `impact_changed` before any write, and its report lists doc02 with a new token. The new token is accepted.

```bash journey F5
$V drive "$RUN" main fixture -- multi-fixture --dependent
$V drive "$RUN" main f02 -- forget --source doc02 --expected-revision 1
$V check "$RUN" f02 '.sources.doc02.state == "forgotten" and .forget.dependents_revised == []' 'doc02 is forgotten and nothing depended on it'
$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '.confirmation_required == false and .dependents == []' 'no dependent while doc02 is forgotten'
$V drive "$RUN" main readd02 -- readd --source doc02 --expected-revision 1
$V check "$RUN" readd02 '.sources.doc02.state == "current" and (.sources.doc02.decisions.r01.input_refs | index("doc01_text") != null)' 'the re-added doc02 reads doc01 again'

$V drive "$RUN" main stale -- forget --source doc01 --expected-revision 1 --confirm "$T"
$V check "$RUN" stale '.error == "IntentError" and (.message | startswith("The impact changed"))' 'the old token is refused'
$V check "$RUN" stale '.details.token != "'"$T"'" and (.details.dependents | length) == 1' 'the refusal reports the new dependent and a new token'
T2=$(val stale '.details.token')
$V drive "$RUN" main unchanged -- status
$V check "$RUN" unchanged '[.publications[].state] == ["current", "current"] and .recovery_events == []' 'the refused forget wrote nothing'

$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1 --confirm "$T2"
$V check "$RUN" forget '.sources.doc01.state == "forgotten" and .sources.doc02.decisions.r01.status == "unresolved"' 'the new token is accepted and doc02 r01 is removed'
```

**F6 an interrupted removal resumes through reconcile.** Proves `forget-dependent-interrupted`. Guide: "Interrupted removals". The forget of doc01 completes, then its dependent's removal is interrupted. With `forget_dependents` it stops before doc02's removal revision begins: doc02 stays current at revision 1, and retrieval withholds r01 with `input_removed`, which `status` also lists. With `forget_dependent_revision` the removal revision fails: doc02 is failed and withheld whole. The command exits 1 and reports the failure beside the completed forget. A re-add of doc01 waits. `reconcile --source doc01` finishes the removal: doc02 is current at revision 2 with r01 unresolved, and nothing is unavailable.

```bash journey F6 stages=forget_dependents,forget_dependent_revision
$V drive "$RUN" main fixture -- multi-fixture --dependent
$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
T=$(val dry '.token')

$V drive "$RUN" main stopped -- forget --source doc01 --expected-revision 1 --confirm "$T" --fault-stage "$STAGE"
$V check "$RUN" stopped '.sources.doc01.state == "forgotten" and .dependents_failed != null and .forget.dependents_revised == []' 'the forget completed and the removal stopped'
$V check "$RUN" stopped '.dependents_failed.code | IN("injected_failure", "recovery_required")' 'the failure is the injected one'
$V drive "$RUN" main gap -- retrieve
$V check "$RUN" gap '.facts == [] and (.unavailable_sources | length) == 1' 'no fact returns and one entry is unavailable'
$V check "$RUN" gap '.unavailable_sources[0] | (.assignment_id == "r01" and .reason == "input_removed") or (.assignment_id == null and .reason == "publication_failed")' 'r01 is withheld as input_removed, or doc02 whole as failed'
$V drive "$RUN" main waiting -- readd --source doc01 --expected-revision 1
$V check "$RUN" waiting '.error == "IntentError" and (.message | contains("has not revised every dependent"))' 'a re-add waits for the removal'

$V drive "$RUN" main rec -- reconcile --source doc01
$V check "$RUN" rec '.forget.dependents_revised | length == 1 and .[0].revision == 2' 'reconcile writes doc02 removal revision'
$V check "$RUN" rec '.dependents_failed == null and .sources.doc02.state == "current" and .sources.doc02.verified_revision == 2' 'doc02 is current at revision 2'
$V check "$RUN" rec '.sources.doc02.decisions.r01.status == "unresolved" and (.sources.doc02.input_keys | index("doc01_text") == null)' 'r01 is unresolved and doc01 text input is gone'
$V check "$RUN" rec '.result.unavailable_sources == [] and all(.recovery_events[]; .resolved_at != null)' 'nothing is unavailable and no incident stays open'
$V drive "$RUN" main final -- status
$V check "$RUN" final '.withheld_decisions == [] and .refresh_needed == []' 'nothing stays withheld'
```

**F7 forget a withdrawn source.** Proves `forget-any-source`. Guide: "Any source". doc02 is withdrawn, which keeps its document, facts, markers and evidence. The forget removes them: doc02 is forgotten with nothing left, and doc01 keeps its fact.

```bash journey F7
$V drive "$RUN" main fixture -- multi-fixture
$V drive "$RUN" main wd -- withdraw --source doc02
$V check "$RUN" wd '.sources.doc02.state == "withdrawn" and .sources.doc02.original_fact_present' 'the withdrawn doc02 keeps its fact'
$V drive "$RUN" main forget -- forget --source doc02 --expected-revision 1
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state] == ["current", "forgotten"]' 'the withdrawn doc02 is forgotten'
$V check "$RUN" forget '.sources.doc02.forget | .original_data_present == false and .identity_data_present == false and .chunks_present == [] and .original_fact_present == false and .evidence_rows == 0 and .owned_nodes == 0 and .owned_edges == 0 and .removed_entities_present == []' 'nothing of doc02 remains'
$V check "$RUN" forget '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc01.mention_entity_id]' 'doc01 fact still returns'
$V check "$RUN" forget '.recovery_events == []' 'no incident'
```

**F8 forget a source whose first publication failed.** Proves `forget-any-source`. Guide: "Any source". doc02's first publication fails at `nodes`; the forget removes what it wrote. doc02 is forgotten, its incident is resolved with `outcome: forgotten` and no message, and doc01 keeps its fact.

```bash journey F8
$V drive "$RUN" main fixture -- multi-fixture --source doc02 --fault-stage nodes
$V check "$RUN" fixture '.error == "IntentError" and (.message | test("recovery_event_id="))' 'doc02 first publication failed'
$V drive "$RUN" main forget -- forget --source doc02 --expected-revision 1
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state] == ["current", "forgotten"]' 'doc02 is forgotten'
$V check "$RUN" forget '.sources.doc02.forget | .original_data_present == false and .identity_data_present == false and .chunks_present == [] and .mention_nodes_present == [] and .owned_nodes == 0 and .owned_edges == 0' 'nothing of doc02 remains'
$V check "$RUN" forget '.recovery_events | length == 1 and (.[0] | .outcome == "forgotten" and .resolved_at != null and .message == null and .stage == "nodes")' 'the incident is resolved as forgotten and keeps no message'
$V check "$RUN" forget '. as $r | [$r.result.facts[].source_id] == [$r.sources.doc01.mention_entity_id]' 'doc01 fact still returns'
```

**F9 re-add from the caller's changed files.** Proves `readd-changed-files`. Guide: "Re-add". doc01 is forgotten. The user appends a sentence to `source.txt`; the re-add refuses, since the identity file still states the old digest. Once `identity.json` states the new digest, the re-add publishes doc01 at revision 2 with the new text, its fact and both facts in the result.

```bash journey F9
$V drive "$RUN" main fixture -- multi-fixture
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
python3 -c 'import pathlib, sys; p = pathlib.Path(sys.argv[1]) / "source.txt"; p.write_text(p.read_text().rstrip("\n") + " HC was serviced.\n")' "$RUN/roots/main"
$V drive "$RUN" main refused -- readd --source doc01 --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | contains("text file and identity file disagree"))' 'a text that the identity file does not state is refused'
python3 -c 'import hashlib, json, pathlib, sys; r = pathlib.Path(sys.argv[1]); i = json.loads((r / "identity.json").read_text()); i["inputs"]["doc01"]["text_sha256"] = hashlib.sha256((r / "source.txt").read_bytes()).hexdigest(); (r / "identity.json").write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '.sources.doc01 | .state == "current" and .verified_revision == 2 and .registered_matches_saved and .original_fact_present' 'doc01 is current at revision 2 from the changed files'
$V check "$RUN" readd '(.result.facts | length) == 2 and .recovery_events == []' 'both facts return and no incident'
```

**F10 forget the glossary doc01 read.** Proves `forget-glossary`. Guide: "The glossary". doc01's r01 and v01 cite the glossary's HC entry. The dry run lists r01 unresolved and v01 dropped, both citing `glossary_hc`; HC goes, since only v01 named it, and the Helios controller stays, since doc01 still reads it as `existing_A`. With the token the glossary is forgotten and doc01 goes to revision 2 with r01 alone, unresolved; neither query returns a fact. The glossary comes back from its files at revision 2, and the removed decisions do not.

```bash journey F10
$V drive "$RUN" main fixture -- glossary-fixture
D01=$(val fixture '.sources.doc01.identity_data_id')
$V drive "$RUN" main dry -- forget --source glossary --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '[.dependents[0].decisions[] | [.assignment, .outcome, .citing[0].input_ref]] == [["r01", "unresolved", "glossary_hc"], ["v01", "dropped", "glossary_hc"]]' 'r01 would be unresolved and v01 dropped'
$V check "$RUN" dry '.dependents[0].dropped_entities == ["9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"] and .dependents[0].kept_entities == ["8b4bff50-907b-56b6-bc80-3b0a7018714a"]' 'HC goes and the Helios controller stays'
$V check "$RUN" dry '.dependents[0].dropped_inputs == ["glossary", "glossary_hc"]' 'the glossary inputs go'
$V drive "$RUN" main forget -- forget --source glossary --expected-revision 1 --confirm "$T"
$V check "$RUN" forget '[.sources.glossary.state, .sources.doc01.state, .sources.doc01.saved_revision] == ["forgotten", "current", 2]' 'the glossary is forgotten and doc01 is at revision 2'
$V check "$RUN" forget '(.sources.doc01.decisions | keys) == ["r01"] and .sources.doc01.decisions.r01.producer_ref == "forget_16e89187-1559-5f97-b957-d86f46315407_r2"' 'doc01 keeps only r01, under the removal producer'
$V check "$RUN" forget '.sources.doc01.glossary_spans == {} and .glossary.text == null' 'doc01 reads nothing of the glossary, which has no text left'
$V check "$RUN" forget '.result.facts == [] and .helios.facts == [] and .result.unavailable_sources == []' 'neither query returns a fact and nothing is unavailable'
$V drive "$RUN" main readd -- readd --source glossary --expected-revision 1
$V check "$RUN" readd '.sources.glossary.state == "current" and .sources.glossary.saved_revision == 2 and .glossary.hc_entry.start == 10' 'the glossary is back at revision 2 from its files'
$V check "$RUN" readd '(.sources.doc01.decisions | keys) == ["r01"] and .helios.facts == []' 'the removed decisions stay removed'
```

**F11 a dependent with an unfinished attempt waits.** Proves `forget-dependent-blocked`. Guide: "A dependent that is pending or failed". doc02's withdrawal fails, so doc02 is a blocked dependent: the dry run marks it `blocked` and the token covers it. The forget completes; doc02's removal waits with `dependent_unfinished`, and the command exits 1. Once doc02's withdrawal finishes it reads nothing, so `reconcile --source doc01` has nothing left and is refused.

```bash journey F11
$V drive "$RUN" main fixture -- multi-fixture --dependent
$V drive "$RUN" main wdfail -- withdraw --source doc02 --fault-stage withdraw_contributions
$V check "$RUN" wdfail '.error == "IntentError"' 'doc02 withdrawal failed'
$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '[.dependents[] | [.state, .blocked]] == [["failed", true]] and .counts.blocked == 1' 'doc02 is a blocked dependent'
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1 --confirm "$T"
$V check "$RUN" forget '.sources.doc01.state == "forgotten" and .dependents_failed.code == "dependent_unfinished"' 'the forget completed and the removal waits'
$V check "$RUN" forget '[.forget.dependents_waiting[] | .state] == ["failed"]' 'doc02 is listed as waiting'
$V drive "$RUN" main wd -- withdraw --source doc02
$V check "$RUN" wd '.sources.doc02.state == "withdrawn"' 'doc02 withdrawal finishes'
$V drive "$RUN" main rec -- reconcile --source doc01
$V check "$RUN" rec '.error == "IntentError" and (.message | contains("Forgotten source"))' 'nothing is left for the forget'
```

**F12 a failed refresh takes the removal in its saved revision.** Proves `forget-dependent-failed-replacement`. Guide: "A dependent that is pending or failed". An insert in the glossary completes, and doc01's refresh fails at `replace_registered`: doc01 is failed at revision 2, citing the glossary at the new range, and only replace resumes it. The glossary's dry run lists doc01 at revision 2, failed and not blocked. With the token the glossary is forgotten and doc01's replacement finishes with the removal applied to its saved revision: doc01 is current at revision 2 with r01 alone, under the removal producer, reading nothing of the glossary. Nothing is left, so `reconcile --source glossary` is refused, and the glossary comes back at revision 3.

```bash journey F12
$V drive "$RUN" main fixture -- glossary-fixture
$V drive "$RUN" main edit -- edit-glossary --source glossary --case insert --expected-revision 1 --fault-stage refresh_interrupted
$V check "$RUN" edit '.sources.doc01.state == "failed" and .refresh_failed.code == "recovery_required"' 'doc01 refresh failed after the glossary edit'
$V drive "$RUN" main dry -- forget --source glossary --expected-revision 2 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '[.dependents[] | [.state, .revision, .blocked]] == [["failed", 2, false]]' 'doc01 is listed at its failed revision, not blocked'
$V drive "$RUN" main forget -- forget --source glossary --expected-revision 2 --confirm "$T"
$V check "$RUN" forget '.dependents_failed == null and [.sources.glossary.state, .sources.doc01.state, .sources.doc01.saved_revision] == ["forgotten", "current", 2]' 'the glossary is forgotten and doc01 finishes at revision 2'
$V check "$RUN" forget '(.sources.doc01.decisions | keys) == ["r01"] and (.sources.doc01.decisions.r01.producer_ref | startswith("forget_")) and .sources.doc01.glossary_spans == {}' 'doc01 keeps only r01, under the removal producer, and reads nothing of the glossary'
$V drive "$RUN" main rec -- reconcile --source glossary
$V check "$RUN" rec '.error == "IntentError" and (.message | contains("Forgotten source"))' 'nothing is left for the forget'
$V drive "$RUN" main readd -- readd --source glossary --expected-revision 2
$V check "$RUN" readd '.sources.glossary.state == "current" and .sources.glossary.saved_revision == 3 and (.sources.doc01.decisions | keys) == ["r01"]' 'the glossary is back at revision 3 and the removed decisions stay removed'
```

**F13 a failed first publication takes the removal in its saved revision.** Proves `forget-dependent-failed-publication`. Guide: "A dependent that is pending or failed". doc02's first publication fails at `nodes` while doc02 reads doc01's text. The dry run lists doc02 at revision 1, failed and not blocked. The forget of doc01 completes and is interrupted before the removal: doc02 is still failed, its own `reconcile` cannot finish, since its saved revision cites a document that is no longer registered, and no fact returns. `reconcile --source doc01` applies the removal to doc02's saved revision and finishes the publication with it: doc02 is current at revision 1 with r01 unresolved under the removal producer; its local fact stays, no identity query reaches it, and every incident is resolved.

```bash journey F13
$V drive "$RUN" main fixture -- multi-fixture --dependent --source doc02 --fault-stage nodes
$V check "$RUN" fixture '.error == "IntentError"' 'doc02 first publication failed'
$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '[.dependents[] | [.state, .revision, .blocked]] == [["failed", 1, false]]' 'doc02 is listed at its failed revision, not blocked'
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1 --confirm "$T" --fault-stage forget_dependents
$V check "$RUN" forget '[.sources.doc01.state, .sources.doc02.state, .dependents_failed.code] == ["forgotten", "failed", "injected_failure"]' 'the forget completed and the removal was interrupted'
$V check "$RUN" forget '.result.facts == []' 'nothing of doc02 is served'
$V drive "$RUN" main own -- reconcile --source doc02
$V check "$RUN" own '.error == "IntentError" and (.message | contains("Original Data item is not registered"))' 'doc02 cannot finish its saved revision while it cites the forgotten document'
$V drive "$RUN" main rec -- reconcile --source doc01
$V check "$RUN" rec '.dependents_failed == null and .sources.doc02.state == "current" and .sources.doc02.saved_revision == 1' 'doc02 finishes its publication at revision 1'
$V check "$RUN" rec '.sources.doc02.resolution_status == "unresolved" and (.sources.doc02.decisions.r01.producer_ref | startswith("forget_"))' 'r01 is unresolved under the removal producer'
$V check "$RUN" rec '.sources.doc02.original_fact_present and .result.facts == [] and .result.unavailable_sources == []' 'the doc02 local fact stays and no identity query reaches it'
$V check "$RUN" rec '[.recovery_events[] | .resolved_at != null] | all' 'every incident is resolved'
$V drive "$RUN" main again -- reconcile --source doc01
$V check "$RUN" again '.error == "IntentError" and (.message | contains("Forgotten source"))' 'nothing is left for the forget'
```

## Gotchas

- Forget needs `--expected-revision`. Withdraw does not.
- A forgotten source leaves its row in `status`: its last revision, a tombstone in place of its description, and a plan that keeps identifiers only. `retrieve` neither returns it nor lists it as unavailable.
- Any source can be forgotten: current, withdrawn, or one whose first publication failed. A failed replacement or withdrawal is finished by its own method first. A dependent's failed replacement or publication is not blocked: the forget applies the removal to its saved revision.
- A forget that removes another source's decisions needs `--confirm <token>` from its dry run. A dry run writes nothing and returns before any result file is written. The token changes when the set of affected decisions changes, including a dependent that becomes blocked, changes state or moves to another revision.
- `drive` exits 1 for an injected failure, a refused forget, a refused `readd` and a forget whose dependent removal stopped. That is the expected result. Check `.error`, `.details` or `.dependents_failed`.
- `readd` works only on a forgotten source and publishes at the forgotten revision plus one. It reads `source.txt` and `identity.json` from the root (`source02.txt` and `identity02.json` for doc02, `glossary.txt` and `glossary_identity.json` for the glossary): the caller's own files, which a forget lists and never deletes.
- Only one open forget incident per source is expected. Do not stack two faults in one root.
