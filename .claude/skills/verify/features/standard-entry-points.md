# Standard entry points

A user builds a root with any creation command. Since step 5 S3a, `fixture` goes through the lab's `remember`: Cognee's own `cognify_pipeline` chunks doc01 with its standard Tasks, then a lab Task publishes the identity description. Since S3b, every creation command runs the lab's `add`, then its `cognify`, for each source in publication order (`remember_in_order`, which is `remember` per source), so a failed source stops the run before the next source is added, and `readd` goes through `add` and `cognify` too. The lab stamps every file it manages as cognified, so a plain `cognee.cognify` outside the lab skips them and makes no LLM call. A failed first publication keeps its chunks and its stamps, and `reconcile` finishes it. Since S4 every text edit goes through the lab's `update`: one lab Task under `cognify_pipeline` replaces the original, rebuilds its chunks with the standard Tasks and keeps every file stamped.

Guide: `docs/stage6_identity_standard_entry_points.md` ("Commands", "A failure", "The lab's update", "Warning: a plain Cognee call bypasses the identity layer"), with `docs/stage6_identity_first_slice.md` for the published fact.

## Sub-features

- `entry-remember` builds doc01 through `add`, then `cognify`, and stamps the original, the description and the seed.
- `native-cognify-skips` runs a plain `cognee.cognify()` (`native-cognify`), which skips every stamped item and leaves the publication and its fact unchanged.
- `entry-publish-fault` fails the first publication inside the lab Task at a publish stage. The CLI exits 1 with the recovery event, the stamps stay, and `reconcile` finishes the saved plan.
- `entry-every-root` builds the two-source, chunked and chain roots through `add`, then `cognify`, per source in order, and stamps every file on each.
- `entry-readd` re-adds a forgotten source through `add` and `cognify`, which stamp its files.
- `entry-update` edits doc01's text through the lab's `update`, and every file stays stamped.
- `entry-update-fault` fails the update at each replacement stage. The stamps stay, `text_removed` included, and `reconcile` finishes the saved text change.
- `native-cognify-after-update` runs a plain `cognee.cognify()` after a kind change, a glossary edit and an occurrence addition, and it skips every item.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity fixture --root <new dir> --embedding loopback`.
- Run `native-cognify` against the same root as a stand-in for a plain `cognee.cognify()`.
- Add `--fault-stage nodes|identity_edges|verification` to `fixture` for a failed first publication, or with `--source` to another creation command.
- Run `multi-fixture`, `chunked-fixture` or `glossary-fixture --chain`, then `native-cognify`, for the other root kinds.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey runs in its own `RUN`. The helper builds the root path.

**L1 remember builds doc01.** Proves `entry-remember`. Guide: "Commands". The fixture publishes the one `limits` fact of the first slice guide ("Expected result"), with no incident, and `cognify_stamps` has `original`, `identity` and `seed` each `true`. `status` lists one current publication at revision 1, verified at 1.

```bash journey L1
$V drive "$RUN" main fixture -- fixture
$V check "$RUN" fixture '.result.facts | length == 1 and (.[0] | .relationship == "limits" and .text == "it limits oscillations" and .identity.state == "accepted")' 'remember publishes the accepted limits fact'
$V check "$RUN" fixture '.cognify_stamps == {"original": true, "identity": true, "seed": true}' 'the original, the description and the seed are stamped'
$V check "$RUN" fixture '.recovery_events == [] and .result.unavailable_sources == []' 'no incident and nothing unavailable'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.state, .revision, .verified_revision]] == [["current", 1, 1]] and .native_deleted == []' 'one current publication at revision 1'
```

**L2 a plain cognify skips the lab's files.** Proves `native-cognify-skips`. Guide: "Commands". `native-cognify` exits 0 and reports each of the three Data items as `PipelineRunAlreadyCompleted`. The fixture environment points the LLM at a closed port, so an extraction would have failed the command. `retrieve` in a new process returns the same fact edge, and `status` still lists one current publication at revision 1 with no incident.

```bash journey L2
$V drive "$RUN" main fixture -- fixture
FACT=$(val fixture '.result.facts[0].edge_id')
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 3 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips all three stamped items'
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '.facts | length == 1 and .[0].edge_id == "'"$FACT"'"' 'the same fact is served after the plain cognify'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.state, .revision, .verified_revision]] == [["current", 1, 1]] and .recovery_events == []' 'the plain cognify changed no publication'
```

**L3 a failed first publication inside the lab Task.** Proves `entry-publish-fault`. Guide: "A failure". The command exits 1 with `recovery_event_id`, as in the first slice guide ("Failure visibility and recovery"). `status` lists the publication as failed with one open incident at the injected stage, labeled `test/fault_injection`, and nothing under `native_deleted`. `native-cognify` still skips all three items, so the stamps survived the failure. `reconcile` restores the fact and resolves the same incident with outcome `restored`, and `status` lists the publication as current.

```bash journey L3 stages=nodes,identity_edges,verification
$V drive "$RUN" main fail -- fixture --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | [.state, .revision]] == [["failed", 1]] and .native_deleted == []' 'the publication is failed and nothing is listed as deleted'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .stage == "'"$STAGE"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident at the injected stage'
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 3 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'the stamps survived the failure'
$V drive "$RUN" main reconcile -- reconcile
$V check "$RUN" reconcile '(.result.facts | length) == 1 and .cognify_stamps == {"original": true, "identity": true, "seed": true}' 'reconcile restores the fact and keeps the stamps'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolved_at != null)' 'the same incident is resolved'
$V drive "$RUN" main after -- status
$V check "$RUN" after '[.publications[] | [.state, .revision, .verified_revision]] == [["current", 1, 1]]' 'the publication is current'
```

**L4 every creation command publishes through the lab's cognify.** Proves `entry-every-root`. Guide: "Which commands use them". Each two-source root registers both sources through `add` and runs `cognify` once per source, in order. Both sources are current at revision 1 with no incident. `native-cognify` then reports each of the five Data items (the seed, and each source's original and description) as `PipelineRunAlreadyCompleted`, so the lab stamped every file on the root, and `retrieve` in a new process serves the same facts.

```bash journey L4 stages=multi-fixture,chunked-fixture
$V drive "$RUN" main fixture -- "$STAGE"
$V check "$RUN" fixture '[.sources.doc01.state, .sources.doc02.state] == ["current", "current"] and [.sources.doc01.verified_revision, .sources.doc02.verified_revision] == [1, 1] and .recovery_events == []' 'both sources are current at revision 1 with no incident'
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 5 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips all five stamped items'
FACTS=$(val fixture '[.result.facts[].edge_id] | sort')
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '([.facts[].edge_id] | sort) == '"$FACTS" 'the same facts are served after the plain cognify'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.state, .revision, .verified_revision]] == [["current", 1, 1], ["current", 1, 1]] and .recovery_events == [] and .native_deleted == []' 'the plain cognify changed neither publication'
```

**L5 a chain root, and a source with no captured facts.** Proves `entry-every-root`. Guide: "Which commands use them". `glossary-fixture --chain` registers the glossary, doc01 and doc03 and publishes them in citation order, one `cognify` each. The glossary and doc03 have no captured facts. doc03's first publication fails at `nodes`. The glossary and doc01 are current, and `native-cognify` skips all seven Data items, doc03's among them. `reconcile --source doc03` finishes doc03 through the lab's cognify and resolves the incident.

```bash journey L5
$V drive "$RUN" main fail -- glossary-fixture --chain --source doc03 --fault-stage nodes
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'doc03 first publication failed'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 7 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips all seven stamped items'
$V drive "$RUN" main reconcile -- reconcile --source doc03
$V check "$RUN" reconcile '[.sources.glossary.state, .sources.doc01.state, .sources.doc03.state] == ["current", "current", "current"] and .sources.doc03.verified_revision == 1' 'every source is current'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolved_at != null)' 'the same incident is resolved'
$V check "$RUN" reconcile '([.result.facts[].relationship] | index("limits")) != null and .withholdings == []' 'doc01 fact returns and nothing is withheld'
```

**L6 a failed first publication on a two-source root.** Proves `entry-publish-fault` on a root with more sources. Guide: "A failure". doc02's first publication fails at `identity_edges`, after doc01 published. The stamps stay, so `native-cognify` skips all five items. `reconcile --source doc02` runs the lab's cognify again and restores doc02's fact.

```bash journey L6
$V drive "$RUN" main fail -- multi-fixture --source doc02 --fault-stage identity_edges
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'doc02 first publication failed'
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 5 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'the stamps survived the failure'
$V drive "$RUN" main reconcile -- reconcile --source doc02
$V check "$RUN" reconcile '[.sources.doc01.state, .sources.doc02.state] == ["current", "current"] and .sources.doc02.original_fact_present and .sources.doc02.original_evidence_present' 'doc02 is current with its fact and evidence'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .stage == "identity_edges" and .outcome == "restored" and .resolved_at != null)' 'the incident is resolved'
```

**L7 a re-add registers and stamps through the lab's add.** Proves `entry-readd`. Guide: "Which commands use them". doc01 is forgotten, then re-added from the caller's files at revision 2. `native-cognify` then skips all five Data items, the re-added original and description among them.

```bash journey L7
$V drive "$RUN" main fixture -- multi-fixture
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1
$V check "$RUN" forget '.sources.doc01.state == "forgotten"' 'doc01 is forgotten'
$V drive "$RUN" main readd -- readd --source doc01 --expected-revision 1
$V check "$RUN" readd '[.sources.doc01.state, .sources.doc01.saved_revision, .sources.doc01.verified_revision] == ["current", 2, 2] and .sources.doc01.original_fact_present' 'doc01 is re-added at revision 2 with its fact'
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 5 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips the re-added files too'
```

**L8 a text edit through the lab's update.** Proves `entry-update`. Guide: "The lab's update". `edit-text` on doc01 of a two-source root runs one lab Task under `cognify_pipeline`. doc01 reaches revision 2 with the edited positions, doc02 stays at revision 1, and no incident is recorded. `native-cognify` then skips all five Data items, so the edited original and the new description were stamped again. `retrieve` in a new process serves the same two facts.

```bash journey L8
$V drive "$RUN" main fixture -- multi-fixture
$V drive "$RUN" main edit -- edit-text --source doc01 --expected-revision 1
$V check "$RUN" edit '([.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision])) == [["current", 2, 2, 2], ["current", 1, 1, 1]] and .recovery_events == []' 'doc01 is current at revision 2, doc02 stays at 1, and no incident'
$V check "$RUN" edit '.text_changes[0] | .position_shift == 48 and .retired_chunks_absent and .retired_chunk_vectors_absent and .evidence_uses_current_chunks' 'the standard Tasks rebuilt the chunks and the evidence uses them'
FACTS=$(val edit '[.result.facts[].edge_id] | sort')
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 5 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips all five items after the update'
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '([.facts[].edge_id] | sort) == '"$FACTS"' and .unavailable_sources == []' 'the same facts are served after the plain cognify'
$V check "$RUN" reopen '[.facts[].identity.occurrences | map([.start, .end])] | any(. == [[97, 111], [134, 136]])' 'doc01 is served at its edited positions'
$V drive "$RUN" main status -- status
$V check "$RUN" status '([.publications[] | [.state, .revision, .verified_revision]] | sort) == [["current", 1, 1], ["current", 2, 2]] and .native_deleted == []' 'both publications are current and nothing is listed as deleted'
```

**L9 a failed update at every replacement stage.** Proves `entry-update-fault`. Guide: "The lab's update". `edit-text` fails inside the lab Task at each replacement stage. The command exits 1 with `recovery_event_id`. doc01 is failed at revision 2, verified at 1, and nothing is listed under `native_deleted`. `native-cognify` skips all five items at every stage, `text_removed` among them, where the memory-only forget has cleared the original's mark and the lab stamped it again before the stage ended. `reconcile` finishes the saved text change through the same lab Task, resolves the incident with outcome `restored`, and the items stay stamped.

```bash journey L9 stages=replace_saved,withhold_dependents,replace_registered,replace_published,replace_retired,replace_verification,text_removed,text_registered,text_chunks
$V drive "$RUN" main fixture -- multi-fixture
$V drive "$RUN" main fail -- edit-text --source doc01 --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')
$V drive "$RUN" main before -- status
$V check "$RUN" before '[.publications[] | select(.state == "failed") | [.revision, .verified_revision]] == [[2, 1]] and .native_deleted == []' 'doc01 is failed at revision 2 and nothing is listed as deleted'
$V drive "$RUN" main native -- native-cognify
$V check "$RUN" native '.native_cognify.items | length == 5 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'every item is still stamped after the failure'
$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 2, 2, 2], ["current", 1, 1, 1]]' 'reconcile completes revision 2'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolved_at != null)' 'the same incident is restored'
$V drive "$RUN" main after -- native-cognify
$V check "$RUN" after '.native_cognify.items | length == 5 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'every item is stamped after the reconcile'
```

**L10 a plain cognify after the other updates.** Proves `native-cognify-after-update`. Guide: "The lab's update". On a chain root, doc01's kind change and then a glossary edit (no captured facts) each go through the lab's update, and on a chunked root an occurrence addition does. After each, `native-cognify` skips every Data item, and the facts it served before the plain call are served after it.

```bash journey L10
$V drive "$RUN" chain fixture -- glossary-fixture --chain
$V drive "$RUN" chain kind -- change-kind-to-mention --source doc01 --expected-revision 1
$V check "$RUN" kind '.sources.doc01 | [.state, .saved_revision, .verified_revision] == ["current", 2, 2]' 'the kind change reaches revision 2'
$V drive "$RUN" chain native1 -- native-cognify
$V check "$RUN" native1 '.native_cognify.items | length == 7 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips all seven items after the kind change'
$V drive "$RUN" chain glossary -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V check "$RUN" glossary '.sources.glossary | [.state, .saved_revision, .verified_revision] == ["current", 2, 2]' 'the glossary edit reaches revision 2'
FACTS=$(val glossary '[.result.facts[].edge_id] | sort')
$V drive "$RUN" chain native2 -- native-cognify
$V check "$RUN" native2 '.native_cognify.items | length == 7 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips all seven items after the glossary edit'
$V drive "$RUN" chain reopen -- retrieve
$V check "$RUN" reopen '([.facts[].edge_id] | sort) == '"$FACTS" 'the same facts are served after the plain cognify'
$V drive "$RUN" chunked fixture2 -- chunked-fixture
$V drive "$RUN" chunked add -- add-occurrences --source doc01 --expected-revision 1
$V check "$RUN" add '.sources.doc01 | [.state, .saved_revision, .verified_revision] == ["current", 2, 2]' 'the occurrence addition reaches revision 2'
$V drive "$RUN" chunked native3 -- native-cognify
$V check "$RUN" native3 '.native_cognify.items | length == 5 and ([.[]] | unique) == ["PipelineRunAlreadyCompleted"]' 'cognify skips all five items after the occurrence addition'
```
