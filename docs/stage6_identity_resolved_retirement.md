# Step 4 / M3: retire a resolved, fact-bearing group

**Guide scope:** commands and limits for this captured profile. For current project status, later checkpoints, the code baseline, and verification evidence, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

This checkpoint removes every occurrence of doc01's primary resolved group. The existing whole-document rebuild and generated-retention cleanup perform the deletion. This checkpoint adds no lifecycle coordinator or source schema. Identity and semantic decisions are captured fixture input, not model inference.

## Captured edit and ownership

Use a fresh `chunked-fixture`, whose doc01 text is:

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.
```

Replace it with the following exact string, including a trailing newline:

```text
Helios controller (HC) regulates plasma heating.
```

The explicit transition is `{"g01": [], "g02": [0]}`. Both old g01 occurrences are retired, with their saved resolution r01 and the local mention Entity declaration. Unresolved g02 (`plasma`) continues at its original range `[33, 39)`. The shared HC-to-controller variant assignment and independent singleton declarations remain supported by doc01. Retirement of one group is not withdrawal of its entire identity source.

The ordinary local `limits` fact is owned by original producing chunks. Native original-memory removal deletes that source's old fact/evidence. The captured replacement has no such fact to generate. Final generated-source cleanup releases the old mention's remaining retention and its obsolete `resolves_to` contribution. The now unowned mention node and its name vector disappear. Doc02 keeps its distinct local mention/fact, both evidence chunks and its independent native retention of the shared oscillations endpoint. Existing controller properties remain unchanged.

The fixture still captures only its specified semantic fact. It does not infer or exhaustively extract other facts from the remaining regulation sentence.

## Run

Apply this incremental patch after `stage6_occurrence_removal.patch`. Extract the ZIP into the repository root and run its check/apply instructions. Choose a fresh output directory:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_resolved_retirement
uv run python -m cognee_lab.identity retire-resolved-group \
  --root outputs/stage6_resolved_retirement --source doc01 --expected-revision 1
```

Expected: doc01 remains current at saved/registered/verified revision 2. Doc02 remains revision 1. Only **doc02's fact** is retrieved. Doc01 now has three chunks, no primary mention marker or captured fact evidence, and its unresolved group remains. Neither source is unavailable and no recovery event is created. The command writes `resolved_retirement_result.json`, a review copy of the intended JSON and the replacement original text.

In `sources.doc01.resolved_group_retirement`, verify these fields are false/zero:

- `mention_entity_present`, `mention_entity_indexed`;
- `resolution_edge_present`, `fact_edge_present`, `fact_evidence_count`;
- `current_marker_present`, `fact_triplet_indexed`, `resolution_triplet_indexed`.

`shared_fact_endpoint_present`, `shared_fact_endpoint_indexed` and `shared_relationship_text_indexed` must be true. Native relationship-text vectors are shared by text, so deleting one fact must not remove the index entry used by doc02's surviving fact. Triplet vectors are checked only if their native collection exists. This checkpoint does not enable/build Triplets or claim a populated-triplet deletion experiment.

The normal source fields `original_marker_present`, `original_fact_present`, `original_fact_owned_by_chunk` and `original_evidence_present` are false for the retired primary group. Those are expected absences, not missing required output. The explicit retirement checks establish cleanup; hiding a failed source from retrieval alone is insufficient. In transition diagnostics, `evidence_uses_current_chunks: true` with an empty evidence list means no obsolete captured evidence remains for this retired group.

Reopen and reconcile:

```bash
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_resolved_retirement --source doc01
```

The retired group, link and fact must remain absent. A later identity-source withdrawal removes only its remaining generated contributions. It must preserve doc02's independent original facts/evidence and the continuing original-owned unresolved marker.

## Interrupted retirement

Use another fresh root:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_resolved_retirement_failure
uv run python -m cognee_lab.identity retire-resolved-group \
  --root outputs/stage6_resolved_retirement_failure --expected-revision 1 \
  --fault-stage replace_published
# Expected injected failure before final retention cleanup/verification.
uv run python -m cognee_lab.identity retrieve \
  --root outputs/stage6_resolved_retirement_failure
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_resolved_retirement_failure --source doc01
```

Before recovery, doc01 is withheld and doc02's fact remains available. Reconcile reuses the exact saved intended description, survivor manifest, old/new text and native chunk budget. It completes cleanup/verification at revision 2 and resolves the same incident. Native tests also cover interruption at `text_chunks`. This is forward completion, not rollback or automatic retry.

## Scope

The test is retirement of doc01's captured local group/fact while a **different physical fact edge** from doc02 survives. It does not establish every possible same-triple foreign-owner deletion case. The known primary mention ID remains a fixture diagnostic constant after its saved declaration is removed; runtime identity classification still comes from checked descriptions and actual graph markers. There is no new role registry.

Remaining step-4 work includes occurrence additions and regrouping. Changed interpretations with refreshed semantic output; dependency-aware multi-document reconsideration and span/record handling. And coordinated original/generated Data removal and rebuild cases. Automatic Describe quality is step 6; standard entry-point wiring and broader retrieval remain step 5. Incremental chunk reuse, A/B staging, automatic orchestration and comprehensive replay are not prerequisites for completing step 4.
