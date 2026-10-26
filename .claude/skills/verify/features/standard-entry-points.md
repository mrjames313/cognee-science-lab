# Standard entry points

A user builds a `fixture` root, which since step 5 S3a goes through the lab's `remember`: Cognee's own `cognify_pipeline` chunks doc01 with its standard Tasks, then a lab Task publishes the identity description. The lab stamps every file it manages as cognified, so a plain `cognee.cognify` outside the lab skips them and makes no LLM call. A failed first publication keeps its chunks and its stamps, and `reconcile` finishes it.

Guide: `docs/stage6_identity_standard_entry_points.md` ("Commands", "A failure", "Warning: a plain Cognee call bypasses the identity layer"), with `docs/stage6_identity_first_slice.md` for the published fact.

## Sub-features

- `entry-remember` builds doc01 through `remember` and stamps the original, the description and the seed.
- `native-cognify-skips` runs a plain `cognee.cognify()` (`native-cognify`), which skips every stamped item and leaves the publication and its fact unchanged.
- `entry-publish-fault` fails the first publication inside the lab Task at a publish stage. The CLI exits 1 with the recovery event, the stamps stay, and `reconcile` finishes the saved plan.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity fixture --root <new dir> --embedding loopback`.
- Run `native-cognify` against the same root as a stand-in for a plain `cognee.cognify()`.
- Add `--fault-stage nodes|identity_edges|verification` to `fixture` for a failed first publication.

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
