# Step 4 / M3: split a group and combine the parts

**Guide scope:** a captured group split and a captured group combination through the existing whole-document maintenance path. Start with [SESSION_HANDOFF.md](SESSION_HANDOFF.md) for current status and evidence boundaries. The creation commands `fixture`, `multi-fixture` and `chunked-fixture` use the `.env` embedding settings by default (`--embedding env`). For an offline root with deterministic embeddings, add `--embedding loopback` to the creation command. The user approved this case on 2026-10-21, before implementation.

## Captured edits

Both commands start from doc01 of a fresh `chunked-fixture`. Its text, with a trailing newline, is:

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.
```

At revision 1, g01 holds `the controller` at `[49,63)` and `it` at `[90,92)`, with accepted resolution r01 to the reusable Helios controller. Unresolved g02 holds `plasma` at `[33,39)`. The captured fact `it limits oscillations` belongs to g01.

### Split, revision 1 to 2

`split-group` replaces doc01 with two paragraphs. The string has a trailing newline:

```text
Helios controller (HC) regulates plasma heating, and the controller adjusts coil current.

During calibration, it limits oscillations.
```

The paragraph break splits g01 into two fresh local groups:

- g04 holds `the controller` at `[53,67)`. Resolution r04 accepts it to the same reusable controller.
- g05 holds `it` at `[111,113)`. Resolution r05 accepts it to the same reusable controller.

g02 continues with its UUID at `[33,39)`. g01 retires, together with r01, its construction recipe, its node and name index, its markers, and its local fact edge, evidence and triplets. These are physically removed, not only hidden from retrieval.

The captured semantic adapter generates `it limits oscillations` again from g05 and the current chunks. It does not transfer the old g01 fact edge. g04 gets no fact. Two distinct groups that resolve to one reusable Entity stay distinct local groups.

### Combination, revision 2 to 3

`combine-groups` runs on the same root after the split. It rejoins the paragraphs. The string has a trailing newline:

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and during calibration it limits oscillations.
```

g04 and g05 merge into one fresh group g06, which holds `the controller` at `[49,63)` and `it` at `[109,111)`. Resolution r06 accepts g06 to the reusable controller, with the recipe name `the controller; it`. g04, g05, r04, r05 and g05's fact retire. The fact `it limits oscillations` is generated again from g06. g01 is never resurrected, although g06 has the same occurrence texts that g01 had. g02 continues unchanged.

The paragraph grouping and the resolutions are reviewed inputs. The process does not infer them from names or offsets. `describe_split` and `describe_combination` in `src/cognee_lab/identity/group_regrouping.py` build the two intended descriptions. `combine-groups` refuses a root where doc01 was not produced by `split-group`.

## Admission and recovery intent

**Superseded on 2026-10-21.** The general occurrence map replaced the separate admission modes. The command now saves `TextChange.occurrence_map`, and `admit` in `src/cognee_lab/identity/admission.py` applies one rule set to every edit. See "General occurrence map, approved 2026-10-21" in [the checkpoint history](stage6_checkpoint_history.md#general-occurrence-map-approved-2026-10-21). The split and combination maps below are unchanged as general maps. The general rules drop "at least one group must retire" and "in order", and the result field `occurrence_regrouping` is now `occurrence_map`. The text below records this checkpoint as it was built.

`TextChange.occurrence_regrouping` maps each **old group key** to a list of `[new group key, new occurrence index]` pairs. The list has one pair for each old occurrence, in old order. The split map is:

```json
{"g01": [["g04", 0], ["g05", 0]], "g02": [["g02", 0]]}
```

The combination map is:

```json
{"g04": [["g06", 0]], "g05": [["g06", 1]], "g02": [["g02", 0]]}
```

`admit_occurrence_regrouping` in `src/cognee_lab/identity/text_changes.py` applies these rules:

- The map names every old group. Every old occurrence maps to exactly one new occurrence, and every new occurrence has exactly one origin.
- A group continues only when it keeps its key and receives exactly its own occurrences, in order. Every other old group retires, and every other new group is fresh. At least one group must retire.
- Each old occurrence text matches its old slice and the text of the new occurrence it maps to. Each new occurrence matches its exact slice of the new text.
- A continuing group keeps its Entity UUID and document reference.
- Continuing resolutions, variant assignments and recipes stay unchanged. Only the retired groups' own resolutions and recipes leave. Each fresh group declares exactly one new resolution.
- The source revision is the old revision plus one.
- Each fresh group's Entity UUID follows the fresh-ID rule below. Before the first attempt, preflight also refuses a fresh UUID that already exists in the graph.

`TextChange.mode` selects one of the transition modes: prefix shift, `occurrence_retention`, `occurrence_continuity` or `occurrence_regrouping`. It refuses a change that sets more than one. A regrouping cannot also add or remove occurrences.

The durable replacement plan stores the map, the exact intended description, the old and new texts and the native chunk budget. Reconcile completes that exact intent and reuses the saved fresh UUIDs. It does not select identities again. The change adds no saved-source schema, model call, backend-specific write code or new coordinator.

### Fresh-ID rule

A fresh group's Entity UUID is `uuid5(identity_data_id, f"mention:r{revision}:{key}")`, where `revision` is the new revision. `check_revision_scoped_ids` enforces it in `TextChange.preflight` on the first attempt of an addition or a regrouping, next to the check that the UUID is not already in the graph. `check_unused_entity_ids` refuses a fresh UUID that the old description still uses, in admission, on every attempt. A regrouping also refuses a fresh group that reuses an old group's key, so a reader can tell from the key that a group is new. `check_next_revision` makes both admissions refuse a source revision other than the old revision plus one.

The rule includes the revision because the record store keeps only the current revision of each source. The first implementation derived the UUID from the source and the key only. During the 2026-10-21 review, a reviewer showed that a key that returns re-derives a retired UUID. A revision-4 source that reused key g04 was admitted and had to reuse g04's retired UUID. With the revision in the derivation, no (source, revision, key) repeats. `RecordStore.begin` refuses a changed description at a used revision, and each step advances one revision.

For the fixture's doc01 identity source `718efce2-4251-5f6f-8318-417bb4dd3525`, the UUIDs are:

| Group | Revision | Key-only UUID (before the fix) | Current UUID |
|---|---|---|---|
| g03 (addition) | 2 | `a75636db-c46d-5261-a21e-010647bfe4f4` | `4827dc6d-3687-56e7-8a15-96a9dc30c070` |
| g04 | 2 | `7b93ccfe-fe9d-5126-b484-1b1c5eb39f6e` | `b584813e-92d6-5eb4-b330-cbb0414866cf` |
| g05 | 2 | `e6307cfe-012a-53c4-abf7-30dc1d8d904d` | `2de73cc9-c7ff-5e83-b1e7-a189bedb1d37` |
| g06 | 3 | `3bda245c-19be-5f6e-b722-3785f6bc9447` | `da6e1b3e-2e1e-570b-893d-9fe8996abe83` |

The user reviewed the case with the key-only values. Roots made before this change keep their old IDs as history. Only the first attempt chooses a fresh UUID. A retry or reconcile completes the saved plan, so it skips the derivation check, and a failed addition or split saved under the key-only rule can still be completed. Unit tests show that such a saved addition and such a saved split pass every admission check a retry repeats. No such root was found to run it on. One limit applies to a root split before the change. If its combination fails and is then retried, the fixture's retirement checks look for revision-scoped g04 and g05 UUIDs that the root never had, so those checks pass without testing anything. The publisher still retires the right Entities, because it retires the recipes that the old description has and the new one does not.

### Retired fixture groups

The fixture decides that a captured group has retired from the source's lineage, not its revision. `CAPTURED_GROUPS` names the producer implementation of the fixture edit that creates each group. A group has retired only when that producer is in the source's `producers` map and the source no longer declares the group. Before this fix the table held a retiring revision. A root that retired g01 and then edited its text reached revision 3 without a split, and reported g04 and g05 as retired. Every absence check passed because the groups had never existed (GitHub issue #1).

## Run

Use a new output directory. This sequence uses loopback embeddings:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_group_split --embedding loopback
uv run python -m cognee_lab.identity split-group \
  --root outputs/stage6_group_split --source doc01 --expected-revision 1
```

Expected after the split: doc01 current at saved/registered/verified revision 2/2/2, doc02 unchanged at 1/1/1, **two retrieved facts**, no unavailable sources and no recovery incidents. The two facts are doc01's fact generated again from g05 and doc02's unchanged fact. `group_split_result.json` contains the result.

In `text_changes[0]`, check:

- `occurrence_regrouping` equals the split map. `occurrence_retention`, `occurrence_continuity` and `position_shift` are null.
- `added_groups` has exactly g04 and g05, with the current UUIDs from the table. Each has its node, name index and current marker chunks.
- `retired_groups` has exactly g01. Its Entity, name index and markers are absent.
- `groups.g02` keeps its occurrence and marker chunks. Retired old chunks and vectors are absent. Evidence uses the current chunks.

`sources.doc01.resolved_group_retirement` reports g01's mention, resolution link, fact, marker and triplets as absent, with no fact evidence. The shared oscillations Entity and its relationship-text index stay. The doc01 fact has source g05, assignment r05 and the reusable controller as its interpreted target.

Then combine on the same root:

```bash
uv run python -m cognee_lab.identity combine-groups \
  --root outputs/stage6_group_split --source doc01 --expected-revision 2
```

Expected after the combination: doc01 current at 3/3/3, doc02 unchanged at 1/1/1, two retrieved facts and no incidents. `group_combination_result.json` contains the result. `added_groups` has only g06, with UUID `da6e1b3e-2e1e-570b-893d-9fe8996abe83`. `retired_groups` has exactly g04 and g05. `sources.doc01.combined_group_retirement` reports their mentions, links, facts, markers and triplets as absent. `resolved_group_retirement` still reports g01 as absent. The doc01 fact has source g06, assignment r06 and both occurrences.

Reopen and reconcile:

```bash
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_group_split
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_group_split --source doc01
```

The same two facts must remain. A healthy reconcile does not change revisions, records no incident and does not recreate a retired group. Dataset IDs vary by root. Compare values within one run.

## Interrupted split or combination

Use a fresh root for each sequence. For the split:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_group_split_failure --embedding loopback
uv run python -m cognee_lab.identity split-group \
  --root outputs/stage6_group_split_failure --expected-revision 1 \
  --fault-stage replace_published
# Expected injected failure.
uv run python -m cognee_lab.identity retrieve \
  --root outputs/stage6_group_split_failure
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_group_split_failure --source doc01
```

Before recovery, only doc02's fact returns, and doc01 reports `publication_failed` with an incident ID. `status` shows doc01 failed at revision 2 with verified revision 1, and the saved plan holds the split map. Reconcile completes revision 2 with the saved g04 and g05 UUIDs, returns two facts and resolves the same incident with one verified recovery attempt.

For the combination, run a healthy `split-group` first. Then run `combine-groups --expected-revision 2 --fault-stage replace_published`, `retrieve` and `reconcile --source doc01`. Reconcile completes revision 3 with the saved g06 UUID and restores the exact saved intent in the same way. The retired g04 and g05 facts stay absent.

This is explicit forward completion. It is not atomic visibility for arbitrary native readers, rollback or automatic retry.

## Verification profile and evidence

The fixture uses Cognee 1.6.2 graph, vector and relational interfaces. The tests and journeys use deterministic loopback embeddings and captured decisions. They make no LLM call.

The assistant's subagents ran these checks on the user's Mac on 2026-10-21, with loopback embeddings:

- `uv run pytest -q -m 'not integration'`: 207 passed and 34 deselected. On `main` before this branch, the suite gave 143 passed and 29 deselected.
- `uv run python support/ledger_check.py`: PASS at depth 5, with 3828 nodes and 3717 sequences. The ledger model now sends the regrouping plan as a second text change, so `PINNED` moved on purpose from 3062 nodes and 2961 sequences. The `Plan.text` field is now `Plan.change`.
- A focused integration run of the split, combination, addition and resolved-retirement native tests: 11 passed in 236 s.
- Verify journeys G1 (32 PASS rows), G2 (20), G3 (36) and G4 (21), with 0 FAIL rows. `.claude/skills/verify/features/group-regrouping.md` holds them.
- Verify journeys O5 (27 PASS rows), O6 `replace_published` (17) and O6 `text_chunks` (17), with 0 FAIL rows. These recheck the addition after the fresh-ID change.

A `/pstack:thermos` review with two reviewers found the fresh-ID gap (medium severity, not reachable through the current commands) and duplicated code. The branch fixes all findings. [The checkpoint history](stage6_checkpoint_history.md#verification-skill) records the full `journey all` result for this checkpoint.

## Remaining work

Step 4 remains partial. This example proves one captured split and one captured combination of a resolved group. It does not establish general regrouping, automatic matching or fact transfer. Mixed addition and removal, representation-kind changes, changed interpretation and semantic refresh, dependency-aware reconsideration and the full original and generated Data lifecycle remain. Standard entry-point and public retrieval integration is step 5. Automated Describe and its separate quality evaluation are step 6.
