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
- `forget-dependent-failed-publication` applies the removal to a dependent's failed first publication in its saved revision, and the publication finishes with it. Before that the dependent's own `reconcile` cannot finish, and nothing of it is served. What the failed attempt wrote for a decision the removal drops goes with it: a dropped Entity's node and name vector, and its identity-edge contribution.
- `forget-any-source` forgets a withdrawn source and a source whose first publication failed.
- `forget-fault` fails a forget at an injected stage, withholds the source, then finishes it with `reconcile`.
- `readd` publishes a forgotten source again at the next revision with new UUIDs for its mentions and for every Entity the forget removed: a named one derives from a key that names it, an unnamed one from the removed UUID.
- `readd-changed-files` re-adds from the caller's text and identity files when they changed, and refuses when they disagree.
- `readd-difference` reports, without refusing, whether the re-add's text and reviewed decisions differ from the forgotten revision's (`differs_from_forgotten`), by the tombstone's digests.
- `forget-again` forgets a re-added source again: the new tombstone carries the mention UUIDs of the earlier forgotten life, and a later re-add that names one is refused.
- `readd-fence` refuses a re-add that would consume a source whose forget is unfinished (native test `test_native_readd_of_a_consumer_waits_for_the_unfinished_forget`).
- `readd-fault` fails a re-add at an injected stage, withholds the source, then finishes it with `reconcile`, which writes the captured facts the failure skipped.
- `forget-glossary` forgets the glossary that doc01 read: doc01's r01 is unresolved, v01 and HC go, and the glossary comes back from its files without the decisions.
- `forget-cascade` forgets the glossary on a `--chain` root: the dry run lists doc01 at level 1 and doc03, which cites r01 and v01, at level 2, and one token removes both levels in order.
- `forget-cascade-token` refuses a token once a new citation of a record the forget removes adds a level (`impact_changed`); a citation pinned at an older fingerprint is not part of the cascade.
- `forget-cascade-interrupted` fails a level-2 removal after level 1 is written; `reconcile` on the forgotten source finishes it, and `readd` waits until it does.
- `forget-cascade-blocked` lists a level-2 dependent whose withdrawal failed as blocked; its removal waits.
- `forget-single-source` forgets, re-adds and withdraws doc01 on a single-source `fixture` root, which has no two-source manifest; each command exits 0 with its one source's report.
- `native-deleted` lists, in `status`, a source whose native copy a delete outside the lab took (`native-forget`), with the facets it misses and the `forget` that erases the lab's copy; `reconcile` refuses it and `forget` erases it (native tests in `tests/test_identity_native_deletes_native.py` cover the dataset forget, the prune and a dependent).
- `reset` shows what is left after `prune_system(metadata=True)`, which deletes the lab's ledger with Cognee's relational database: no row and no tombstone, so nothing to repair.
- `readd-outside-deleted` refuses a re-add whose files name an Entity deleted outside the lab while a saved source still cites or builds it, naming each such source with its dataset and state; once each is forgotten or replaced without it, the re-add builds the Entity under a derived UUID and never writes the old one.
- `forget-dataset` forgets every source of the root's dataset, readers first, each through the lab's `forget`, then deletes item by item the Data no lab source publishes (the seed), which its dry run lists under `other_data`; it always needs the dry run's token, which covers that list, and a rerun has nothing to do.
- `forget-dataset-repair` turns every row a native dataset forget or Cognee's default prune left behind into a tombstone (`status` lists them under `native_deleted` first), deletes a surviving Data row of the seed, and lets a re-add rebuild an absent Entity under a derived UUID.
- `forget-dataset-crash` fails the dataset forget at an injected stage (`first:<forget stage>`, `last:<forget stage>` or `dataset_cleanup`); the old token is refused (`impact_changed`), and a new dry run and confirmation finish it, a crashed source's forget resuming through forget's own retry.
- `forget-cascade-retire-refused` refuses a withdrawal or forget of a source that holds a removal while the cascade below it is unfinished (`cascade_unfinished`); once `forget` on the forgotten source finishes the cascade, the withdrawal goes ahead.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>`. Add `--dependent` to make doc02 consume doc01's text and private singleton.
- Run `forget --root <dir> --source doc01 --expected-revision 1 --dry-run` for the report and token, then `forget --root <dir> --source doc01 --expected-revision 1 --confirm <token>`. A forget with no dependent needs no token.
- Add `--fault-stage forget_impact|forget_contributions|forget_identity|forget_document|forget_verification|forget_identity_committed|forget_document_committed` to inject a failure, then run `reconcile --source doc01`. The two `_committed` stages fail after Cognee committed the Data delete and before it swept the item's evidence rows and stored files.
- Run `forget-dataset --root <dir> --dry-run` for the dataset report and token, then `forget-dataset --root <dir> --confirm <token>`. Add `--fault-stage first:<stage>` or `last:<stage>` (a forget stage, applied to the first or last source in the order) or `dataset_cleanup` (after every forget, before the other Data is deleted).
- Add `--fault-stage forget_dependents` (before the first removal revision) or `forget_dependent_revision` (inside it: at `replace_registered` for a replacement, at `nodes` for a failed publication) to interrupt a dependent's removal after the forget completed, then run `reconcile --source doc01`. `forget_cascade_revision` fails only the removals below level 1, after level 1 is written.
- On a `glossary-fixture --chain` root, `forget --source glossary` cascades to doc03 at level 2; `withdraw --source doc03` also works there.
- Add `--fault-stage nodes|identity_edges|verification` to `readd` to fail the re-add, then run `reconcile --source doc01`.
- Run `uv run python -m cognee_lab.identity readd --root <dir> --source doc01 --expected-revision 1` on a root whose doc01 is forgotten.
- On a `fixture` root, `forget`, `readd` and `withdraw` take `--source doc01`.
- Run `retrieve` and `status` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new root. Forget changes the root for good.
- The fixture's two sources are current at revision 1 before the forget.

**F1 forget doc01, then add it again.** Proves `forget-healthy`, `forget-status`, `readd` and `readd-difference`. Guide: "Forget doc01", "The tombstone" and "Re-add" give every value. Nothing depends on doc01, so the forget needs no token. After the forget, doc01's `forget` report is all absent, doc02's entry is unchanged, the shared variant edge keeps one contribution and one owner from doc02, the HC Entity keeps one owner, the shared singleton and the borrowed controller survive, and only doc02's fact returns. `status` shows doc01 `forgotten` at revision 1 whose description is a tombstone holding the revision 1 mention UUID and no occurrence text, and whose forget plan keeps no edge property and no runtime profile. `retrieve` lists no unavailable source. A second forget and a reconcile are refused. The re-add reports neither other text nor other decisions, since the caller's files are the ones published at revision 1. It publishes doc01 at revision 2 with a mention UUID and a private singleton UUID that differ from revision 1 (the forget removed both, and no removed UUID returns). No resolution or variant names the private singleton, so its replacement is `uuid5(doc01 identity, "entity:r2:replaces:<removed UUID>")`, `9b7f8477-...`. The re-add restores both facts, both contributions and both HC owners, and a second re-add is refused.

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
$V check "$RUN" readd '.differs_from_forgotten == {"text": false, "decisions": false}' 'the re-add reports the same text and decisions as the forgotten revision'
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
$V check "$RUN" forget '.forget.dependents_revised == [{"identity_data_id": "'"$D02"'", "revision": 2, "level": 1}] and .dependents_failed == null' 'doc02 was revised at revision 2, at level 1'
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

**F9 re-add from the caller's changed files.** Proves `readd-changed-files` and `readd-difference`. Guide: "Re-add". doc01 is forgotten. The user appends a sentence to `source.txt`; the re-add refuses, since the identity file still states the old digest. Once `identity.json` states the new digest, the re-add publishes doc01 at revision 2 with the new text, its fact and both facts in the result, and reports other text with the same decisions.

```bash journey F9
$V drive "$RUN" main fixture -- multi-fixture
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
python3 -c 'import pathlib, sys; p = pathlib.Path(sys.argv[1]) / "source.txt"; p.write_text(p.read_text().rstrip("\n") + " HC was serviced.\n")' "$RUN/roots/main"
$V drive "$RUN" main refused -- readd --source doc01 --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | contains("text file and identity file disagree"))' 'a text that the identity file does not state is refused'
python3 -c 'import hashlib, json, pathlib, sys; r = pathlib.Path(sys.argv[1]); i = json.loads((r / "identity.json").read_text()); i["inputs"]["doc01"]["text_sha256"] = hashlib.sha256((r / "source.txt").read_bytes()).hexdigest(); (r / "identity.json").write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '.sources.doc01 | .state == "current" and .verified_revision == 2 and .registered_matches_saved and .original_fact_present' 'doc01 is current at revision 2 from the changed files'
$V check "$RUN" readd '.differs_from_forgotten == {"text": true, "decisions": false}' 'the re-add reports other text and the same decisions'
$V check "$RUN" readd '(.result.facts | length) == 2 and .recovery_events == []' 'both facts return and no incident'
```

**F10 forget the glossary doc01 read.** Proves `forget-glossary`. Guide: "The glossary". doc01's r01 and v01 cite the glossary's HC entry. The dry run lists r01 unresolved and v01 dropped, both citing `glossary_hc`; HC goes, since only v01 named it, and the Helios controller stays, since doc01 still reads it as `existing_A`. With the token the glossary is forgotten and doc01 goes to revision 2 with r01 alone, unresolved; neither query returns a fact. The glossary comes back from its files at revision 2, with the forgotten text and decisions, and doc01's removed decisions do not come back.

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
$V check "$RUN" readd '.differs_from_forgotten == {"text": false, "decisions": false}' 'the glossary files hold the forgotten text and decisions'
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

**F14 a failed publication's erasure retry retires what it wrote.** Proves `forget-dependent-failed-publication`. Guide: "A dependent that is pending or failed". doc01's first publication fails at `identity_edges`, after HC's node, its name vector and the HC edge with v01's contribution are written, while v01 reads the glossary's HC entry. The glossary's dry run lists doc01 at revision 1, failed and not blocked, with HC as its one dropped Entity. With the token the glossary is forgotten and doc01's publication finishes with the removal: doc01 is current at revision 1 with r01 alone, under the removal producer. HC leaves the name index with the rest of what the failed attempt wrote for it, so the HC query seeds it neither in the forget's result nor in a fresh `retrieve`, and every incident is resolved. The native test `test_native_an_erasure_retry_of_a_failed_publication_retires_what_it_wrote` also reads HC's node and the edge's contributions.

```bash journey F14
$V drive "$RUN" main fixture -- glossary-fixture --source doc01 --fault-stage identity_edges
$V check "$RUN" fixture '.error == "IntentError" and (.message | contains("after identity edges"))' 'doc01 first publication failed after its identity edges'
$V drive "$RUN" main dry -- forget --source glossary --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '[.dependents[] | [.state, .revision, .blocked, .dropped_entities]] == [["failed", 1, false, ["9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"]]]' 'doc01 is listed failed at revision 1, not blocked, and HC would go'
$V drive "$RUN" main forget -- forget --source glossary --expected-revision 1 --confirm "$T"
$V check "$RUN" forget '.dependents_failed == null and [.sources.glossary.state, .sources.doc01.state, .sources.doc01.saved_revision] == ["forgotten", "current", 1]' 'the glossary is forgotten and doc01 finishes at revision 1'
$V check "$RUN" forget '(.sources.doc01.decisions | keys) == ["r01"] and (.sources.doc01.decisions.r01.producer_ref | startswith("forget_"))' 'doc01 keeps only r01, under the removal producer'
$V check "$RUN" forget '(.result.seed_entity_ids | index("9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88")) == null and .result.unavailable_sources == []' 'the HC query no longer seeds HC'
$V check "$RUN" forget '[.recovery_events[] | .resolved_at != null] | all' 'every incident is resolved'
$V drive "$RUN" main again -- retrieve
$V check "$RUN" again '(.seed_entity_ids | index("9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88")) == null and .unavailable_sources == []' 'a fresh retrieve does not seed HC either'
```

**F15 forget a re-added source again.** Proves `forget-again` and `readd-difference`. Guide: "Re-add" and "The tombstone". doc01 is forgotten at revision 1 and re-added from changed text at revision 2, which reports other text and the same decisions. Forgotten again at revision 2, its tombstone holds the revision 2 mention UUIDs under `mention_ids`, the two revision 1 ones under `earlier_mention_ids`, and the revision 1 private singleton, which the first forget removed, under `earlier_entity_ids`. The user adds a corpus input naming the revision 1 mention UUID to `identity.json`: the re-add is refused as `forgotten_uuid_reused` and writes nothing. Without that input and with r01 unresolved, the re-add publishes doc01 at revision 3 under a third mention UUID and reports the same text as revision 2 and other decisions. `identity.json` still names the private singleton by its revision 1 UUID, which the graph no longer holds, so the re-add replaces it under a third UUID too ("What a re-add replaces").

```bash journey F15
$V drive "$RUN" main fixture -- multi-fixture
M01=$(val fixture '.sources.doc01.mention_entity_id')
PS01=$(val fixture '.sources.doc01.private_singleton_entity_id')
$V drive "$RUN" main forget1 -- forget --source doc01 --expected-revision 1
python3 -c 'import hashlib, json, pathlib, sys; r = pathlib.Path(sys.argv[1]); t = r / "source.txt"; t.write_text(t.read_text().rstrip("\n") + " HC was serviced.\n"); i = json.loads((r / "identity.json").read_text()); i["inputs"]["doc01"]["text_sha256"] = hashlib.sha256(t.read_bytes()).hexdigest(); (r / "identity.json").write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main readd1 -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd1 '.sources.doc01 | .state == "current" and .saved_revision == 2 and .verified_revision == 2' 'doc01 is current at revision 2 from the changed text'
$V check "$RUN" readd1 '.differs_from_forgotten == {"text": true, "decisions": false}' 'the re-add reports other text and the same decisions'
M02=$(val readd1 '.sources.doc01.mention_entity_id')
PS02=$(val readd1 '.sources.doc01.private_singleton_entity_id')

$V drive "$RUN" main forget2 -- forget --source doc01 --expected-revision 2
$V check "$RUN" forget2 '.sources.doc01 | .state == "forgotten" and .saved_revision == 2' 'doc01 is forgotten again at revision 2'
$V drive "$RUN" main status2 -- status
$V check "$RUN" status2 '.publications[] | select(.state == "forgotten") | .description | fromjson | .revision == 2 and .mention_ids.g01 == "'"$M02"'" and (.earlier_mention_ids | length) == 2 and (.earlier_mention_ids | index("'"$M01"'")) != null and (.earlier_mention_ids | index("'"$M02"'")) == null' 'the second tombstone carries the revision 1 mention UUIDs and holds the revision 2 ones under mention_ids'
$V check "$RUN" status2 '.publications[] | select(.state == "forgotten") | .description | fromjson | .earlier_entity_ids == ["'"$PS01"'"] and (.decisions_sha256 | length) == 64' 'the private singleton the first forget removed is carried, with the decisions digest'

python3 -c 'import json, pathlib, sys; p = pathlib.Path(sys.argv[1]) / "identity.json"; i = json.loads(p.read_text()); i["inputs"]["back"] = dict(kind="corpus_object", dataset_id=i["dataset_id"], entity_id=sys.argv[2], selected_fields=["name"], content_sha256="0" * 64); p.write_text(json.dumps(i))' "$RUN/roots/main" "$M01"
$V drive "$RUN" main refused -- readd --source doc01 --expected-revision 2
$V check "$RUN" refused '.error == "IntentError" and (.message | contains("does not recreate a mention or Entity UUID"))' 'a re-add naming the revision 1 mention UUID is refused'
$V drive "$RUN" main status3 -- status
$V check "$RUN" status3 '[.publications[] | select(.state == "forgotten") | .revision] == [2] and .recovery_events == []' 'the refused re-add wrote nothing'

python3 -c 'import json, pathlib, sys; p = pathlib.Path(sys.argv[1]) / "identity.json"; i = json.loads(p.read_text()); del i["inputs"]["back"]; r = i["mention_resolutions"]["r01"]; del r["target_entity_id"]; r["status"] = "unresolved"; p.write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main readd2 -- readd --source doc01 --expected-revision 2
$V check "$RUN" readd2 '.sources.doc01 | .state == "current" and .saved_revision == 3 and .verified_revision == 3 and .decisions.r01.status == "unresolved"' 'doc01 is current at revision 3 with r01 unresolved'
$V check "$RUN" readd2 '.sources.doc01.mention_entity_id as $m | ($m | length) == 36 and $m != "'"$M01"'" and $m != "'"$M02"'"' 'the third life has a third mention UUID'
$V check "$RUN" readd2 '.sources.doc01 | .private_singleton_entity_id as $s | ($s | length) == 36 and $s != "'"$PS01"'" and $s != "'"$PS02"'" and .private_singleton_present' 'the private singleton returns under a third UUID'
$V check "$RUN" readd2 '.differs_from_forgotten == {"text": false, "decisions": true}' 'the re-add reports the revision 2 text and other decisions'
```

**F16 a forget cascades down a two-level chain with one confirmation.** Proves `forget-cascade`. Guide: "The cascade" in the forget guide and "Forget of a cited source" in the chains guide. On a `--chain` root the glossary's forget reaches doc01, whose r01 and v01 cite the HC entry, at level 1, and doc03, whose c01 and c02 cite r01 and v01, at level 2. The dry run lists both levels; doc03's cited records are exactly the records doc01's removal lists, each with its revision 1 fingerprint and `last_revision` 1. Without the token the forget is refused with the two-level report. One token covers both levels: doc01 goes to revision 2 at level 1, then doc03 to revision 2 at level 2, each under its removal producer, and doc03's producer cites what doc01's lists. Nothing is withheld afterwards and nothing is left for the forget.

```bash journey F16
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main dry -- forget --source glossary --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '.levels == [{"level": 1, "dependents": ["718efce2-4251-5f6f-8318-417bb4dd3525"]}, {"level": 2, "dependents": ["bbbc442e-0647-552e-bb54-071604d213fa"]}] and .counts.levels == 2 and .counts.decisions == 4' 'the dry run lists doc01 at level 1 and doc03 at level 2'
$V check "$RUN" dry '[.dependents[] | [.level, [.decisions[] | [.assignment, .outcome, .citing[0].input_ref]]]] == [[1, [["r01", "unresolved", "glossary_hc"], ["v01", "dropped", "glossary_hc"]]], [2, [["c01", "unresolved", "doc01_r01"], ["c02", "dropped", "doc01_v01"]]]]' 'r01 and v01 go for the HC entry, c01 and c02 for r01 and v01'
$V check "$RUN" dry '.dependents[1].cited_records == .dependents[0].removed_records and [.dependents[0].removed_records[] | [.record_id, .content_sha256, .last_revision]] == [["r01", "1d2e89138501ae78c356a9d46cc9f49f6a4535928cb10f81c356fbd4b4e67c85", 1], ["v01", "6a89916921b8c21be7689812bd0e7032b7ce38162bc701222a0e23db18446aff", 1]]' 'doc03 cites the records doc01 loses, as they are at revision 1'
$V drive "$RUN" main refused -- forget --source glossary --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | contains("--confirm")) and .details.token == "'"$T"'" and .details.counts.levels == 2' 'without the token the forget is refused with the two-level report'

$V drive "$RUN" main forget -- forget --source glossary --expected-revision 1 --confirm "$T"
$V check "$RUN" forget '.dependents_failed == null and [.forget.dependents_revised[] | [.identity_data_id, .revision, .level]] == [["718efce2-4251-5f6f-8318-417bb4dd3525", 2, 1], ["bbbc442e-0647-552e-bb54-071604d213fa", 2, 2]]' 'one confirmation writes doc01 revision 2 at level 1, then doc03 revision 2 at level 2'
$V check "$RUN" forget '(.sources.doc01.decisions | keys) == ["r01"] and .sources.doc01.decisions.r01.status == "unresolved" and (.sources.doc03.decisions | keys) == ["c01"] and .sources.doc03.decisions.c01 == {"input_refs": ["doc03"], "producer_ref": "forget_16e89187-1559-5f97-b957-d86f46315407_r2", "status": "unresolved"} and .sources.doc03.records == {}' 'both levels lose their decisions and doc03 cites nothing of doc01'
$V check "$RUN" forget '.sources.doc03.producers["forget_16e89187-1559-5f97-b957-d86f46315407_r2"].configuration.cited_records == .sources.doc01.producers["forget_16e89187-1559-5f97-b957-d86f46315407_r2"].configuration.removed_records and .sources.doc01.producers["forget_16e89187-1559-5f97-b957-d86f46315407_r2"].configuration.cited_records == []' 'doc03 removal producer cites what the level-1 producer lists'
$V check "$RUN" forget '.result.facts == [] and .result.unavailable_sources == []' 'no fact returns and nothing is unavailable'
$V drive "$RUN" main status -- status
$V check "$RUN" status '.withheld_decisions == [] and [.publications[] | [.revision, .state]] == [[1, "forgotten"], [2, "current"], [2, "current"]] and .recovery_events == []' 'nothing is withheld; doc01 and doc03 are current at revision 2'
$V drive "$RUN" main rec -- reconcile --source glossary
$V check "$RUN" rec '.error == "IntentError" and (.message | contains("Forgotten source"))' 'nothing is left for the forget'
```

**F17 a token is refused when a new level appears.** Proves `forget-cascade-token`. Guide: "The cascade". After a cosmetic glossary edit, the reviewer makes r01 unresolved in place and replaces v01 by v02. doc03's c01 still pins r01's accepted fingerprint and c02 cites v01, which is gone, so neither reads a record the glossary's forget removes: the dry run lists one level. doc03's re-confirm of c01 cites r01 as it is now, unresolved, which the forget does remove, so doc03 becomes a level-2 dependent and the old token is refused with `impact_changed` and a report of two levels. The new token removes r01 and v02 from doc01 and c01 from doc03. c02 still cites v01, which the reviewer took away before the forget, so it stays withheld with `input_removed`.

```bash journey F17
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main edit -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V drive "$RUN" main r01 -- replace-decision --source doc01 --decision r01 --expected-revision 1
$V drive "$RUN" main v01 -- replace-decision --source doc01 --decision v01 --expected-revision 2
$V check "$RUN" v01 '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["c01", "input_changed", "refresh_needed"], ["c02", "input_removed", "refresh_needed"]]' 'c01 pins an older fingerprint of r01 and c02 a record that is gone'
$V drive "$RUN" main dry1 -- forget --source glossary --expected-revision 2 --dry-run
T1=$(val dry1 '.token')
$V check "$RUN" dry1 '.levels == [{"level": 1, "dependents": ["718efce2-4251-5f6f-8318-417bb4dd3525"]}] and [.dependents[0].decisions[] | [.assignment, .outcome]] == [["r01", "unresolved"], ["v02", "dropped"]]' 'one level: doc03 reads nothing the forget removes'

$V drive "$RUN" main c01 -- reconfirm --source doc03 --decision c01 --expected-revision 1
$V check "$RUN" c01 '.sources.doc03.saved_revision == 2 and .sources.doc03.records.doc01_r01_r2.representation_revision == 3' 'doc03 re-cites r01 as it is now'
$V drive "$RUN" main stale -- forget --source glossary --expected-revision 2 --confirm "$T1"
$V check "$RUN" stale '.error == "IntentError" and (.message | startswith("The impact changed")) and .details.token != "'"$T1"'"' 'the old token is refused'
$V check "$RUN" stale '[.details.levels[] | .level] == [1, 2] and [.details.dependents[1].decisions[] | [.assignment, .citing[0].input_ref]] == [["c01", "doc01_r01_r2"]]' 'the refusal reports doc03 at level 2 for its new citation'
$V drive "$RUN" main unchanged -- status
$V check "$RUN" unchanged '[.publications[] | [.revision, .state]] == [[2, "current"], [3, "current"], [2, "current"]] and .recovery_events == []' 'the refused forget wrote nothing'

$V drive "$RUN" main dry2 -- forget --source glossary --expected-revision 2 --dry-run
T2=$(val dry2 '.token')
$V drive "$RUN" main forget -- forget --source glossary --expected-revision 2 --confirm "$T2"
$V check "$RUN" forget '.dependents_failed == null and [.forget.dependents_revised[] | [.revision, .level]] == [[4, 1], [3, 2]]' 'doc01 revision 4 at level 1 and doc03 revision 3 at level 2'
$V check "$RUN" forget '(.sources.doc01.decisions | keys) == ["r01"] and .sources.doc03.decisions.c01.status == "unresolved" and (.sources.doc03.records | keys) == ["doc01_v01"]' 'r01 stays unresolved alone, c01 is unresolved and only the citation of v01 remains'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["c02", "input_removed", "refresh_needed"]]' 'c02 waits for its own review, as before the forget'
```

**F18 a crash at a level-2 removal resumes, and the re-add waits for it.** Proves `forget-cascade-interrupted`. Guide: "The cascade". With `--fault-stage forget_cascade_revision` the glossary is forgotten and doc01's level-1 removal is written, then doc03's level-2 removal fails at `replace_registered`: doc03 is failed at revision 2 and unavailable. The re-add of the glossary is refused while doc03 is unrevised, and the dry run of the forgotten glossary lists doc03 as unfinished. `reconcile --source glossary` finishes doc03's removal from its saved revision, with no new doc01 revision, and resolves its incident. The re-add then publishes the glossary at revision 2 and brings back none of the removed decisions.

```bash journey F18
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main dry -- forget --source glossary --expected-revision 1 --dry-run
T=$(val dry '.token')
$V drive "$RUN" main forget -- forget --source glossary --expected-revision 1 --confirm "$T" --fault-stage forget_cascade_revision
$V check "$RUN" forget '.dependents_failed.code == "recovery_required" and (.dependents_failed.message | contains("Injected failure at replace_registered"))' 'the level-2 removal fails'
$V check "$RUN" forget '[.forget.dependents_revised[] | [.identity_data_id, .revision, .level]] == [["718efce2-4251-5f6f-8318-417bb4dd3525", 2, 1]] and [.sources.glossary.state, .sources.doc01.state, .sources.doc03.state, .sources.doc03.saved_revision] == ["forgotten", "current", "failed", 2]' 'level 1 is written and doc03 is failed at its removal revision'
$V check "$RUN" forget '[.result.unavailable_sources[] | [.identity_data_id, .reason]] == [["bbbc442e-0647-552e-bb54-071604d213fa", "publication_failed"]]' 'doc03 is unavailable while its removal is unfinished'
$V drive "$RUN" main readd -- readd --source glossary --expected-revision 1
$V check "$RUN" readd '.error == "IntentError" and (.message | contains("has not revised every dependent yet")) and .details.dependents == ["bbbc442e-0647-552e-bb54-071604d213fa"]' 'the re-add waits for the unfinished cascade'
$V drive "$RUN" main left -- forget --source glossary --expected-revision 1 --dry-run
$V check "$RUN" left '.forgotten and .unfinished == ["bbbc442e-0647-552e-bb54-071604d213fa"]' 'the forgotten glossary lists doc03 as unfinished'

$V drive "$RUN" main rec -- reconcile --source glossary
$V check "$RUN" rec '.dependents_failed == null and [.forget.dependents_revised[] | [.identity_data_id, .revision, .level]] == [["bbbc442e-0647-552e-bb54-071604d213fa", 2, 2]] and .sources.doc01.saved_revision == 2' 'reconcile finishes doc03 at level 2 and leaves doc01 alone'
$V check "$RUN" rec '.sources.doc03 | .state == "current" and .verified_revision == 2 and (.decisions | keys) == ["c01"] and .decisions.c01.status == "unresolved" and .records == {}' 'doc03 finishes its removal revision'
$V check "$RUN" rec '[.recovery_events[] | [.outcome, (.resolved_at != null)]] == [["restored", true]] and .result.unavailable_sources == []' 'the incident is resolved and nothing is unavailable'
$V drive "$RUN" main readd2 -- readd --source glossary --expected-revision 1
$V check "$RUN" readd2 '[.sources.glossary.state, .sources.glossary.saved_revision] == ["current", 2] and (.sources.doc01.decisions | keys) == ["r01"] and (.sources.doc03.decisions | keys) == ["c01"]' 'the glossary is back at revision 2 and the removed decisions stay removed'
```

**F19 a blocked level-2 dependent waits.** Proves `forget-cascade-blocked`. Guide: "The cascade". doc03's withdrawal fails, so doc03 is a blocked dependent at level 2: the dry run marks it `blocked` and the token covers it. The forget writes doc01's level-1 removal, and doc03 waits with `dependent_unfinished` (the command exits 1). Running the forget again still waits, and the re-add is refused. Then doc03's withdrawal finishes: doc01's removal dropped an Entity and an edge they shared, so the survivor check owes doc01 only what it still writes (fix round 1). doc03 is withdrawn, its incident resolved, the cascade has nothing left and the re-add publishes the glossary again.

```bash journey F19
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main wdfail -- withdraw --source doc03 --fault-stage withdraw_contributions
$V check "$RUN" wdfail '.error == "IntentError" and (.message | contains("Injected failure"))' 'doc03 withdrawal failed'
$V drive "$RUN" main dry -- forget --source glossary --expected-revision 1 --dry-run
T=$(val dry '.token')
$V check "$RUN" dry '[.dependents[] | [.identity_data_id, .level, .state, .blocked]] == [["718efce2-4251-5f6f-8318-417bb4dd3525", 1, "current", false], ["bbbc442e-0647-552e-bb54-071604d213fa", 2, "failed", true]] and .counts.blocked == 1' 'doc03 is a blocked dependent at level 2'
$V drive "$RUN" main forget -- forget --source glossary --expected-revision 1 --confirm "$T"
$V check "$RUN" forget '.dependents_failed.code == "dependent_unfinished" and [.sources.glossary.state, .sources.doc01.saved_revision, .sources.doc03.state] == ["forgotten", 2, "failed"]' 'the forget completed, level 1 is written and doc03 waits'
$V check "$RUN" forget '[.forget.dependents_waiting[] | [.identity_data_id, .operation, .level]] == [["bbbc442e-0647-552e-bb54-071604d213fa", "identity_withdraw", 2]]' 'doc03 is listed as waiting for its withdrawal'
$V drive "$RUN" main again -- forget --source glossary --expected-revision 1
$V check "$RUN" again '.dependents_failed.code == "dependent_unfinished" and .forget.dependents_revised == []' 'a second run still waits for doc03'
$V drive "$RUN" main readd -- readd --source glossary --expected-revision 1
$V check "$RUN" readd '.error == "IntentError" and .details.dependents == ["bbbc442e-0647-552e-bb54-071604d213fa"]' 'the re-add waits for doc03'
$V drive "$RUN" main withdraw -- withdraw --source doc03
$V check "$RUN" withdraw '.sources.doc03.state == "withdrawn" and .sources.doc01.state == "current" and [.recovery_events[] | .outcome] == ["withdrawn"]' 'doc03 withdrawal finishes after doc01 removal'
$V drive "$RUN" main readd2 -- readd --source glossary --expected-revision 1
$V check "$RUN" readd2 '[.sources.glossary.state, .sources.glossary.saved_revision, .sources.doc03.state] == ["current", 2, "withdrawn"]' 'with doc03 withdrawn the cascade is done and the re-add publishes'
```

**F20 a source holding a removal is not retired before the cascade below it finishes.** Proves `forget-cascade-retire-refused`. Guide: "The cascade". With `--fault-stage forget_cascade_revision` doc01's level-1 removal is written and doc03's level-2 removal fails. Withdrawing doc01 is refused (`cascade_unfinished`), and so is forgetting it: doc03's removal binds to the removal doc01 holds, so retiring doc01 first would leave doc03 citing what the forget removed while the forget reports finished (fix round 2). Neither refusal writes anything. `forget` on the glossary again finishes doc03, and the withdrawal of doc01 then goes ahead.

```bash journey F20
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main dry -- forget --source glossary --expected-revision 1 --dry-run
T=$(val dry '.token')
$V drive "$RUN" main forget -- forget --source glossary --expected-revision 1 --confirm "$T" --fault-stage forget_cascade_revision
$V check "$RUN" forget '[.sources.glossary.state, .sources.doc01.state, .sources.doc01.saved_revision, .sources.doc03.state] == ["forgotten", "current", 2, "failed"]' 'level 1 is written and doc03 failed at level 2'
$V drive "$RUN" main wd -- withdraw --source doc01
$V check "$RUN" wd '.error == "IntentError" and (.message | startswith("This source holds a removal of a forget whose cascade is not finished")) and .details.unfinished == ["bbbc442e-0647-552e-bb54-071604d213fa"]' 'withdrawing doc01 is refused while doc03 is unfinished'
$V drive "$RUN" main fg -- forget --source doc01 --expected-revision 2
$V check "$RUN" fg '.error == "IntentError" and (.message | startswith("This source holds a removal")) and .details.forgotten == "16e89187-1559-5f97-b957-d86f46315407"' 'forgetting doc01 is refused too, naming the glossary'
$V drive "$RUN" main still -- status
$V check "$RUN" still '[.publications[] | [.revision, .state]] == [[1, "forgotten"], [2, "current"], [2, "failed"]]' 'the refusals wrote nothing'
$V drive "$RUN" main again -- forget --source glossary --expected-revision 1
$V check "$RUN" again '.dependents_failed == null and [.forget.dependents_revised[] | [.identity_data_id, .level]] == [["bbbc442e-0647-552e-bb54-071604d213fa", 2]] and .sources.doc03.state == "current"' 'forget on the glossary again finishes doc03'
$V drive "$RUN" main wd2 -- withdraw --source doc01
$V check "$RUN" wd2 '[.sources.doc01.state, .sources.doc03.state] == ["withdrawn", "current"]' 'with the cascade finished doc01 withdraws'
```

**F21 a single-source root forgets, re-adds and withdraws.** Proves `forget-single-source`. Guide: "Commands". A `fixture` root holds doc01 alone and no `multi-fixture-info.json`. The forget exits 0 with doc01 forgotten at revision 1, no dependent and no fact. The re-add publishes doc01 at revision 2 and its `limits` fact returns. The withdrawal of the re-added revision 2 exits 0 and serves no fact.

```bash journey F21
$V drive "$RUN" main fixture -- fixture
$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
$V check "$RUN" dry '.dry_run and .confirmation_required == false and .dependents == []' 'the dry run finds no dependent'
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '[.publications[] | [.state, .revision]] == [["forgotten", 1]] and .forget.dependents_revised == [] and .dependents_failed == null' 'doc01 is forgotten at revision 1 with no dependent'
$V check "$RUN" forget '.result.facts == [] and .result.unavailable_sources == [] and .recovery_events == []' 'nothing is served and no incident is open'
$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '[.publications[] | [.state, .revision]] == [["current", 2]] and ([.result.facts[].relationship] | index("limits") != null)' 'doc01 is current at revision 2 and its fact returns'
$V drive "$RUN" main wd -- withdraw --source doc01
$V check "$RUN" wd '[.publications[] | [.state, .revision]] == [["withdrawn", 2]] and .result.facts == []' 'the re-added doc01 withdraws'
```

**F22 a delete outside the lab, then the lab's forget.** Proves `native-deleted`. Guide: "Deletes outside the lab". On a `fixture` root `status` lists nothing under `native_deleted`. `native-forget --case data` deletes doc01's original through `cognee.forget` and writes no ledger row: doc01 stays `current` at revision 1. `status` then lists doc01 with `missing` `original_data`, `document_node`, `chunks` and `stored_files` (the guide's table) and `next` `forget --source doc01 --expected-revision 1`. `reconcile` is refused with the guide's `native_deleted` message, naming the same forget, and writes nothing. That `forget` exits 0, leaves doc01 `forgotten` at revision 1 with no dependent, and `status` lists nothing under `native_deleted`.

```bash journey F22
$V drive "$RUN" main fixture -- fixture
$V drive "$RUN" main before -- status
$V check "$RUN" before '.native_deleted == []' 'a fresh root lists nothing deleted outside the lab'
$V drive "$RUN" main native -- native-forget --source doc01 --case data
$V check "$RUN" native '.native_forget.case == "data" and .native_forget.source == "doc01"' 'Cognee forgot doc01 outside the lab'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.state, .revision]] == [["current", 1]]' 'the delete wrote no ledger row'
$V check "$RUN" status '[.native_deleted[] | [.state, .revision, .missing, .next]] == [["current", 1, ["original_data", "document_node", "chunks", "stored_files"], "forget --source doc01 --expected-revision 1"]]' 'status lists doc01 as deleted outside the lab and names forget'
$V drive "$RUN" main rec -- reconcile --source doc01
$V check "$RUN" rec '.error == "IntentError" and (.message | startswith("The native copy of doc01 is gone or changed outside the lab")) and .details.next == "forget --source doc01 --expected-revision 1"' 'reconcile refuses doc01 and names forget'
$V drive "$RUN" main after -- status
$V check "$RUN" after '[.publications[] | [.state, .revision]] == [["current", 1]] and .recovery_events == []' 'the refusal wrote nothing'
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '[.publications[] | [.state, .revision]] == [["forgotten", 1]] and .dependents_failed == null and .forget.dependents_revised == []' 'the lab forget erases doc01'
$V drive "$RUN" main gone -- status
$V check "$RUN" gone '.native_deleted == [] and ([.recovery_events[] | select(.resolved_at == null)] | length) == 0' 'status lists nothing deleted outside the lab and no open incident'
```

**F27 a full reset leaves nothing to repair.** Proves `reset`. Guide: `docs/stage6_identity_forget.md`, "Reset". On a `fixture` root `native-forget --case reset` runs `prune_data()` and `prune_system(metadata=True)`, which deletes Cognee's relational database and the lab's ledger in it. `status` lists no publication, no incident, no withholding and nothing deleted outside the lab: no row and no tombstone remains. `retrieve` serves nothing and lists no unavailable source. `forget`, `readd` and `forget-dataset` are refused with the guide's messages, and `reconcile` is refused (`stores_reset`) saying the stores were reset or never set up and the root must be created again as a new fixture.

```bash journey F27
$V drive "$RUN" main fixture -- fixture
$V drive "$RUN" main reset -- native-forget --source doc01 --case reset
$V check "$RUN" reset '.native_forget.case == "reset"' 'Cognee reset its stores'
$V drive "$RUN" main status -- status
$V check "$RUN" status '.publications == [] and .recovery_events == [] and .withholdings == [] and .native_deleted == []' 'no row, no tombstone and no incident remain'
$V drive "$RUN" main ask -- retrieve
$V check "$RUN" ask '.facts == [] and .unavailable_sources == []' 'nothing is served and nothing is listed unavailable'
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '.error == "IntentError" and .message == "No saved publication to forget"' 'forget finds no saved publication'
$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '.error == "IntentError" and .message == "Re-add needs a forgotten source"' 'readd finds no tombstone'
$V drive "$RUN" main dataset -- forget-dataset --dry-run
$V check "$RUN" dataset '.error == "IntentError" and (.message | startswith("The root holds no saved source"))' 'forget-dataset finds nothing to forget'
$V drive "$RUN" main rec -- reconcile --source doc01
$V check "$RUN" rec '.error == "IntentError" and (.message | startswith("Cognee'"'"'s stores were reset")) and (.message | endswith("Create the root as a new fixture"))' 'reconcile refuses a reset root and names the rebuild'
```

**F28 a re-add after an Entity is deleted outside the lab.** Proves `readd-outside-deleted`. Guide: `docs/stage6_identity_entity_edits.md`, "A re-add naming it waits for its citers". On a `glossary-fixture --chain` root, `edit-entity --case delete` deletes Helios, which doc01 and doc03 both build. doc03 is forgotten with no dependent. Its re-add is refused while doc01, `current`, still names Helios: the message names doc01's identity source, its dataset and its state and says to forget or replace it, and `details.citers` lists it. doc01 is forgotten, with no dependent since doc03 is forgotten. The user drops doc03's citations of doc01's records from `doc03_identity.json` (a re-add may not cite a forgotten source's records), and doc03's re-add publishes revision 2 with its Helios recipe under a derived UUID. The user drops doc01's corpus input of Helios from `identity.json`, since a re-add may not cite a removed Entity, and doc01's re-add publishes revision 2 the same way. No description names the old Helios UUID and no fact reaches it. The two re-adds derive two different UUIDs for the one Helios they built before (case 10 of the user's review, pre-existing: `replacement_entity_id` and `fresh_entity_id` key on the identity source).

```bash journey F28
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main del -- edit-entity --case delete
$V check "$RUN" del '.entity_edit | .case == "delete" and .node_present == false' 'Helios is deleted outside the lab'
H=$(val del '.entity_edit.entity_id')
D01=$(val fixture '.sources.doc01.identity_data_id')
$V drive "$RUN" main f3 -- forget --source doc03 --expected-revision 1
$V check "$RUN" f3 '[.sources.doc03.state, .sources.doc01.state] == ["forgotten", "current"] and .forget.dependents_revised == []' 'doc03 is forgotten with no dependent'
$V drive "$RUN" main refused -- readd --source doc03 --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | startswith("A re-add does not recreate a removed Entity while a saved source still cites or builds it: '"$H"' by '"$D01"' in dataset ")) and (.message | endswith("(current). Forget those sources, or replace their decisions without the Entity, then re-add"))' 'the re-add is refused naming doc01, its dataset and its state'
$V check "$RUN" refused '[.details.citers[] | [.entity_id, .identity_data_id, .state]] == [["'"$H"'", "'"$D01"'", "current"]] and (.details.citers[0].dataset_id | length) > 0' 'the details list doc01 as the live citer'
$V drive "$RUN" main still -- status
$V check "$RUN" still '[.publications[] | [.revision, .state]] == [[1, "current"], [1, "current"], [1, "forgotten"]] and .recovery_events == []' 'the refusal wrote nothing'
$V drive "$RUN" main f1 -- forget --source doc01 --expected-revision 1
$V check "$RUN" f1 '[.sources.doc01.state, .sources.doc03.state] == ["forgotten", "forgotten"] and .forget.dependents_revised == []' 'doc01, the live citer, is forgotten'
python3 -c 'import json, pathlib, sys; p = pathlib.Path(sys.argv[1]) / "doc03_identity.json"; i = json.loads(p.read_text()); [i["inputs"].pop(k) for k in ("doc01_r01", "doc01_v01")]; [r.__setitem__("input_refs", [k for k in r["input_refs"] if not k.startswith("doc01_")]) for r in [*i["mention_resolutions"].values(), *i["variant_assignments"].values()]]; p.write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main r3 -- readd --source doc03 --expected-revision 1
$V check "$RUN" r3 '[.sources.doc03.state, .sources.doc03.saved_revision, .sources.doc03.verified_revision] == ["current", 2, 2]' 'with no live citer doc03 is re-added at revision 2'
python3 -c 'import json, pathlib, sys; p = pathlib.Path(sys.argv[1]) / "identity.json"; i = json.loads(p.read_text()); i["inputs"].pop("existing_A"); [r.__setitem__("input_refs", [k for k in r["input_refs"] if k != "existing_A"]) for r in [*i["mention_resolutions"].values(), *i["variant_assignments"].values()]]; p.write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main r1 -- readd --source doc01 --expected-revision 1
$V check "$RUN" r1 '[.sources.doc01.state, .sources.doc01.saved_revision, .sources.doc01.verified_revision] == ["current", 2, 2]' 'doc01 is re-added at revision 2'
$V drive "$RUN" main status -- status
$V check "$RUN" status '([.publications[] | .description // "" | contains("'"$H"'")] | any | not) and .recovery_events == [] and .native_deleted == []' 'no description names the old Helios UUID and no incident is open'
$V check "$RUN" status '[.publications[] | select(.description != null) | .description | fromjson | select(.revision == 2) | [.entity_constructions | to_entries[] | select(.value.name == "Helios controller") | .key]] | (map(length) == [1, 1]) and (.[0][0] != .[1][0]) and all(.[][]; . != "'"$H"'")' 'each re-add built Helios under its own derived UUID (case 10)'
$V drive "$RUN" main ask -- retrieve --query "Helios controller"
$V check "$RUN" ask '(.facts | tojson | contains("'"$H"'")) | not' 'no fact reaches the old Helios UUID'
```

**F23 a native dataset forget, repaired by forget-dataset.** Proves `forget-dataset-repair`. Guide: `docs/stage6_identity_forget.md`, "Repair after a delete outside the lab". On a `glossary-fixture --chain` root `native-forget --case dataset` calls `cognee.forget(dataset=...)`. `status` lists all three sources with all five facets missing. The dry run takes them in the reader order with no dependent, lists no other Data (the seed went with the dataset) and no orphaned name point. The confirmed run forgets all three. Nothing of them was in the graph to remove, so no forget lists a removed Entity. The removal record lists only the forgotten mention UUIDs, which `initialize` fills from the tombstones each time (2026-10-26), and not Helios: the delete outside the lab, not the lab, took it. `status` then lists nothing deleted outside the lab, and a second dry run has nothing to do. The glossary is re-added, and once the user drops doc01's corpus input of Helios from `identity.json`, doc01 too: the re-add builds Helios under a derived UUID, since Helios is absent and no saved source cites it (the user's Q2 remedy), in the same dataset (prototype, 2026-10-25: Cognee recreates the dataset under its ID).

```bash journey F23
$V drive "$RUN" main fixture -- glossary-fixture --chain
H=8b4bff50-907b-56b6-bc80-3b0a7018714a
$V drive "$RUN" main native -- native-forget --case dataset
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.native_deleted[] | [.state, .revision, .missing]] == [["current", 1, ["original_data", "identity_data", "document_node", "chunks", "stored_files"]], ["current", 1, ["original_data", "identity_data", "document_node", "chunks", "stored_files"]], ["current", 1, ["original_data", "identity_data", "document_node", "chunks", "stored_files"]]]' 'status lists the three sources as deleted outside the lab'
$V drive "$RUN" main dry -- forget-dataset --dry-run
$V check "$RUN" dry '[.sources[] | [.label, .order]] == [["glossary", 2], ["doc01", 1], ["doc03", 0]] and all(.sources[]; .dependents == [])' 'the dry run takes the three in the reader order'
$V check "$RUN" dry '([.other_data[].name] == []) and .orphan_name_points == [] and .pending == []' 'the dry run lists no other Data'
T=$(val dry '.token')
$V drive "$RUN" main go -- forget-dataset --confirm "$T"
$V check "$RUN" go '[.forgotten[] | .label] == ["doc03", "doc01", "glossary"] and (.other_data_deleted | length) == 0 and .dependents_failed == null' 'the dataset forget repairs every row'
$V check "$RUN" go '[.forgotten[] | select(.label == "doc01") | .tombstone.removed_entity_ids | index("'"$H"'")] == [null]' 'the doc01 forget lists Helios as removed by none'
$V drive "$RUN" main after -- status
$V check "$RUN" after '[.publications[] | [.state, .revision]] == [["forgotten", 1], ["forgotten", 1], ["forgotten", 1]] and .native_deleted == [] and ([.recovery_events[] | select(.resolved_at == null)] | length) == 0' 'every row is a tombstone, none is listed and no incident is open'
$V check "$RUN" after '.removed_entities as $r | ([.publications[].description | fromjson | ((.mention_ids | to_entries[].value), .earlier_mention_ids[], .removed_entity_ids[])] | unique) == ($r | keys) and ([$r[]] | unique) == ["identity_forget"] and ($r | has("'"$H"'") | not)' 'the removal record lists only the mention UUIDs of the tombstones, filled at initialize, and not Helios'
$V drive "$RUN" main dry2 -- forget-dataset --dry-run
$V check "$RUN" dry2 'all(.sources[]; .order == null) and .other_data == []' 'a second dry run has nothing to do'
$V drive "$RUN" main rg -- readd --source glossary --expected-revision 1
$V check "$RUN" rg '[.sources.glossary.state, .sources.glossary.saved_revision] == ["current", 2]' 'the glossary is re-added at revision 2'
python3 -c 'import json, pathlib, sys; p = pathlib.Path(sys.argv[1]) / "identity.json"; i = json.loads(p.read_text()); i["inputs"].pop("existing_A"); [r.__setitem__("input_refs", [k for k in r["input_refs"] if k != "existing_A"]) for r in [*i["mention_resolutions"].values(), *i["variant_assignments"].values()]]; p.write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main r1 -- readd --source doc01 --expected-revision 1
$V check "$RUN" r1 '[.sources.doc01.state, .sources.doc01.saved_revision] == ["current", 2]' 'doc01 is re-added at revision 2'
$V drive "$RUN" main end -- status
$V check "$RUN" end '[.publications[] | select(.state == "current") | .description | fromjson | select(.revision == 2) | .entity_constructions | to_entries[] | select(.value.name == "Helios controller") | .key] | length == 1 and all(.[]; . != "'"$H"'")' 'doc01 builds Helios under a derived UUID'
$V check "$RUN" end '([.publications[] | select(.state == "current") | .description | contains("'"$H"'")] | any | not) and ([.publications[] | .dataset] | unique | length) == 1' 'no description names the old UUID and the dataset ID is kept'
```

**F24 Cognee's default prune, repaired by forget-dataset.** Proves `forget-dataset-repair`. Guide: `docs/stage6_identity_forget.md`, "Repair after a delete outside the lab". `native-forget --case prune` runs `prune_data()` and `prune_system()` with its defaults, which keep the relational database. `status` lists all three sources missing `document_node`, `chunks` and `stored_files`; their Data rows survive. The dry run takes them in the reader order and lists the seed's surviving Data row under `other_data`. The confirmed run forgets all three and deletes the seed's row although its file is gone (prototype, 2026-10-25: Cognee's Data delete and the sweep accept a missing file). Then as in F23: nothing is listed, a second dry run has nothing to do, and the re-adds build Helios under a derived UUID in the same dataset.

```bash journey F24
$V drive "$RUN" main fixture -- glossary-fixture --chain
H=8b4bff50-907b-56b6-bc80-3b0a7018714a
$V drive "$RUN" main native -- native-forget --case prune
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.native_deleted[] | [.state, .revision, .missing]] == [["current", 1, ["document_node", "chunks", "stored_files"]], ["current", 1, ["document_node", "chunks", "stored_files"]], ["current", 1, ["document_node", "chunks", "stored_files"]]]' 'status lists the three sources as deleted outside the lab'
$V drive "$RUN" main dry -- forget-dataset --dry-run
$V check "$RUN" dry '[.sources[] | [.label, .order]] == [["glossary", 2], ["doc01", 1], ["doc03", 0]] and all(.sources[]; .dependents == [])' 'the dry run takes the three in the reader order'
$V check "$RUN" dry '([.other_data[].name] == ["seed"]) and .orphan_name_points == [] and .pending == []' 'the dry run lists the surviving Data row of the seed'
T=$(val dry '.token')
$V drive "$RUN" main go -- forget-dataset --confirm "$T"
$V check "$RUN" go '[.forgotten[] | .label] == ["doc03", "doc01", "glossary"] and (.other_data_deleted | length) == 1 and .dependents_failed == null' 'the dataset forget repairs every row'
$V check "$RUN" go '[.forgotten[] | select(.label == "doc01") | .tombstone.removed_entity_ids | index("'"$H"'")] == [null]' 'the doc01 forget lists Helios as removed by none'
$V drive "$RUN" main after -- status
$V check "$RUN" after '[.publications[] | [.state, .revision]] == [["forgotten", 1], ["forgotten", 1], ["forgotten", 1]] and .native_deleted == [] and ([.recovery_events[] | select(.resolved_at == null)] | length) == 0' 'every row is a tombstone, none is listed and no incident is open'
$V check "$RUN" after '.removed_entities as $r | ([.publications[].description | fromjson | ((.mention_ids | to_entries[].value), .earlier_mention_ids[], .removed_entity_ids[])] | unique) == ($r | keys) and ([$r[]] | unique) == ["identity_forget"] and ($r | has("'"$H"'") | not)' 'the removal record lists only the mention UUIDs of the tombstones, filled at initialize, and not Helios'
$V drive "$RUN" main dry2 -- forget-dataset --dry-run
$V check "$RUN" dry2 'all(.sources[]; .order == null) and .other_data == []' 'a second dry run has nothing to do'
$V drive "$RUN" main rg -- readd --source glossary --expected-revision 1
$V check "$RUN" rg '[.sources.glossary.state, .sources.glossary.saved_revision] == ["current", 2]' 'the glossary is re-added at revision 2'
python3 -c 'import json, pathlib, sys; p = pathlib.Path(sys.argv[1]) / "identity.json"; i = json.loads(p.read_text()); i["inputs"].pop("existing_A"); [r.__setitem__("input_refs", [k for k in r["input_refs"] if k != "existing_A"]) for r in [*i["mention_resolutions"].values(), *i["variant_assignments"].values()]]; p.write_text(json.dumps(i))' "$RUN/roots/main"
$V drive "$RUN" main r1 -- readd --source doc01 --expected-revision 1
$V check "$RUN" r1 '[.sources.doc01.state, .sources.doc01.saved_revision] == ["current", 2]' 'doc01 is re-added at revision 2'
$V drive "$RUN" main end -- status
$V check "$RUN" end '[.publications[] | select(.state == "current") | .description | fromjson | select(.revision == 2) | .entity_constructions | to_entries[] | select(.value.name == "Helios controller") | .key] | length == 1 and all(.[]; . != "'"$H"'")' 'doc01 builds Helios under a derived UUID'
$V check "$RUN" end '([.publications[] | select(.state == "current") | .description | contains("'"$H"'")] | any | not) and ([.publications[] | .dataset] | unique | length) == 1' 'no description names the old UUID and the dataset ID is kept'
```

**F25 forget the dataset of a live chain root.** Proves `forget-dataset`. Guide: `docs/stage6_identity_forget.md`, "Forget a dataset". `forget-dataset` without `--confirm` is refused and names the dry run. The dry run orders doc03, which cites doc01's records, before doc01, which reads the glossary, before the glossary (`order` 0, 1, 2), lists no pending row and no dependent outside the dataset, and lists the seed under `other_data`. The confirmed run forgets the three in that order with no removal revision (each source's readers are forgotten before it) and deletes the seed. Every row is `forgotten` at revision 1 with no incident, and no fact is served. A second dry run has no step and no other Data, and its confirmation does nothing. The glossary is then re-added from its files at revision 2 in the same dataset: the Dataset row and its ID survive (prototype, 2026-10-25).

```bash journey F25
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main noconf -- forget-dataset
$V check "$RUN" noconf '.error == "IntentError" and (.message | startswith("forget-dataset needs the dry run")) and .details.dry_run' 'forget-dataset without a token is refused with the report'
$V drive "$RUN" main dry -- forget-dataset --dry-run
$V check "$RUN" dry '[.sources[] | [.label, .state, .revision, .order]] == [["glossary", "current", 1, 2], ["doc01", "current", 1, 1], ["doc03", "current", 1, 0]]' 'readers come before what they read'
$V check "$RUN" dry '.pending == [] and ([.other_data[].name] == ["seed"]) and (.token | length) == 64 and (.removed_entities | length) > 0' 'the dry run lists the seed as other Data'
$V check "$RUN" dry 'all(.sources[]; .native_copy | to_entries | all(.value)) and all(.sources[]; .dependents == [])' 'each native copy is whole and no step revises another source'
T=$(val dry '.token')
SEED=$(val dry '.other_data[0].data_id')
D=$(val dry '.dataset_id')
$V drive "$RUN" main go -- forget-dataset --confirm "$T"
$V check "$RUN" go '[.forgotten[] | .label] == ["doc03", "doc01", "glossary"] and all(.forgotten[]; .dependents_revised == [] and .tombstone.kind == "identity_source_tombstone") and .other_data_deleted == ["'"$SEED"'"] and .dependents_failed == null' 'the three are forgotten in order and the seed is deleted'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.state, .revision]] == [["forgotten", 1], ["forgotten", 1], ["forgotten", 1]] and .recovery_events == [] and .native_deleted == []' 'every row is a tombstone and no incident is open'
$V drive "$RUN" main ask -- retrieve
$V check "$RUN" ask '.facts == []' 'nothing is served'
$V drive "$RUN" main dry2 -- forget-dataset --dry-run
$V check "$RUN" dry2 'all(.sources[]; .order == null) and .other_data == [] and .removed_entities == []' 'a second dry run has nothing to do'
T2=$(val dry2 '.token')
$V drive "$RUN" main go2 -- forget-dataset --confirm "$T2"
$V check "$RUN" go2 '.forgotten == [] and .other_data_deleted == []' 'its confirmation does nothing'
$V drive "$RUN" main readd -- readd --source glossary --expected-revision 1
$V check "$RUN" readd '[.sources.glossary.state, .sources.glossary.saved_revision] == ["current", 2]' 'the glossary is re-added at revision 2'
$V drive "$RUN" main after -- status
$V check "$RUN" after '([.publications[] | .dataset] | unique | length) == 1 and .publications[0].dataset == "'"$D"'"' 'the re-add keeps the dataset ID'
```

**F26 a dataset forget that crashes, then a new dry run.** Proves `forget-dataset-crash`. Guide: `docs/stage6_identity_forget.md`, "Forget a dataset". On root `main`, `--fault-stage dataset_cleanup` fails after the three forgets completed and before the seed is deleted. A rerun with the old token is refused `impact_changed`. A new dry run has no step and lists only the seed, and its confirmation deletes it. On root `first`, `--fault-stage first:forget_identity` fails doc03's forget, the first step: doc03 is `failed` with an open forget incident and the other two are untouched. The old token is refused. A new dry run lists doc03 `failed` at order 0, and its confirmation resumes doc03's forget through forget's own retry and finishes the rest.

```bash journey F26
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main dry -- forget-dataset --dry-run
T=$(val dry '.token')
$V drive "$RUN" main crash -- forget-dataset --confirm "$T" --fault-stage dataset_cleanup
$V check "$RUN" crash '.error == "IntentError" and .message == "Injected failure before the dataset cleanup"' 'the cleanup crashes'
$V drive "$RUN" main old -- forget-dataset --confirm "$T"
$V check "$RUN" old '.error == "IntentError" and (.message | startswith("The impact changed since the token was issued"))' 'the old token is refused'
$V drive "$RUN" main dry2 -- forget-dataset --dry-run
$V check "$RUN" dry2 'all(.sources[]; .state == "forgotten" and .order == null) and ([.other_data[].name] == ["seed"])' 'the new dry run lists only the seed'
T2=$(val dry2 '.token')
$V drive "$RUN" main go -- forget-dataset --confirm "$T2"
$V check "$RUN" go '.forgotten == [] and (.other_data_deleted | length) == 1 and .dependents_failed == null' 'its confirmation deletes the seed'

$V drive "$RUN" first fixture1 -- glossary-fixture --chain
$V drive "$RUN" first fdry -- forget-dataset --dry-run
F=$(val fdry '.token')
$V drive "$RUN" first fcrash -- forget-dataset --confirm "$F" --fault-stage first:forget_identity
$V check "$RUN" fcrash '.error == "IntentError" and (.message | contains("forget_identity"))' 'the first forget fails at forget_identity'
$V drive "$RUN" first fstatus -- status
$V check "$RUN" fstatus '[.publications[] | .state] == ["current", "current", "failed"] and ([.recovery_events[] | select(.resolved_at == null)] | length) == 1' 'doc03 failed with an open incident; the others are untouched'
$V drive "$RUN" first fold -- forget-dataset --confirm "$F"
$V check "$RUN" fold '.error == "IntentError" and (.message | startswith("The impact changed since the token was issued"))' 'the old token is refused'
$V drive "$RUN" first fdry2 -- forget-dataset --dry-run
$V check "$RUN" fdry2 '[.sources[] | [.label, .state, .order]] == [["glossary", "current", 2], ["doc01", "current", 1], ["doc03", "failed", 0]]' 'the new dry run resumes doc03 first'
F2=$(val fdry2 '.token')
$V drive "$RUN" first fgo -- forget-dataset --confirm "$F2"
$V check "$RUN" fgo '[.forgotten[] | .label] == ["doc03", "doc01", "glossary"] and (.other_data_deleted | length) == 1' 'the confirmation finishes the dataset forget'
$V drive "$RUN" first fdone -- status
$V check "$RUN" fdone '([.publications[] | .state] | unique) == ["forgotten"] and ([.recovery_events[] | select(.resolved_at == null)] | length) == 0' 'every row is forgotten and the incident is resolved'
```

## Gotchas

- Forget needs `--expected-revision`. Withdraw does not.
- A forgotten source leaves its row in `status`: its last revision, a tombstone in place of its description, and a plan that keeps identifiers only. `retrieve` neither returns it nor lists it as unavailable.
- Any source can be forgotten: current, withdrawn, one whose publication failed, or one whose replacement failed (since 2026-10-26). A failed withdrawal is finished by withdraw first. A dependent's failed replacement or publication is not blocked: the forget applies the removal to its saved revision.
- A forget's dry run lists `levels`; each dependent has its `level`, the records its removal removes (`removed_records`) and the removed records of other dependents it cites (`cited_records`). Removal revisions are written in level order, and a removal waits (`waits_for`) behind a blocked one whose records it cites.
- A forget that removes another source's decisions needs `--confirm <token>` from its dry run. A dry run writes nothing and returns before any result file is written. The token changes when the set of affected decisions changes, including a dependent that becomes blocked, changes state or moves to another revision.
- `drive` exits 1 for an injected failure, a refused forget, a refused `readd` and a forget whose dependent removal stopped. That is the expected result. Check `.error`, `.details` or `.dependents_failed`.
- `readd` reports `differs_from_forgotten` with `text` and `decisions`, compared with the forgotten revision, not with the caller's earlier files. It never refuses for a difference.
- `readd` works only on a forgotten source and publishes at the forgotten revision plus one. It reads `source.txt` and `identity.json` from the root (`source02.txt` and `identity02.json` for doc02, `glossary.txt` and `glossary_identity.json` for the glossary): the caller's own files, which a forget lists and never deletes.
- Only one open forget incident per source is expected. Do not stack two faults in one root.
