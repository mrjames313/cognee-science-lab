# Step 4 / M3: add occurrences and a new local group

**Guide scope:** captured additions through the existing whole-document maintenance path. Start with [SESSION_HANDOFF.md](SESSION_HANDOFF.md) for current status and evidence boundaries. Apply this incremental code/documentation patch after the documentation-handoff update and resolved-group-retirement code.

## Captured edit

Create a fresh `chunked-fixture`, then replace doc01 with:

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations. During startup, the controller remains active.

After calibration, the controller limits oscillations.
```

The string has a trailing newline. In the first paragraph, g01 retains its Entity UUID and its two old occurrences, then gains the startup reference. Unresolved g02 (`plasma`) continues unchanged. The second paragraph introduces a separate local group g03 with a fresh Entity UUID and accepted resolution r03 to the same reusable controller. Its occurrence has the same surface text as a g01 occurrence; distinct local groups retain distinct IDs. The captured paragraph grouping and resolutions are reviewed inputs, not inferred from names or offsets.

The captured semantic adapter preserves the original `it limits oscillations` fact and creates `the controller limits oscillations` from g03. These are different physical local fact edges to the shared oscillations Entity. Native original producing chunks own facts/evidence; generated identity Data owns resolution contributions and endpoint retention. Identity creation alone does not generate a fact, and this example does not exhaustively extract other statements from the edited text.

## Admission and recovery intent

`TextChange.occurrence_continuity` maps each **old group key** to an ordered list of indices in that group's **new occurrence array**. The list has one entry for every old occurrence, in old order. For this edit:

```json
{"g01": [0, 1], "g02": [0]}
```

For example, `[0, 2]` would mean old occurrence 0 continues as new occurrence 0 and old occurrence 1 continues as new occurrence 2. New index 1 is an addition. Mapping is supplied explicitly even when surface strings repeat. Exact before/after slices and fingerprints are validated programmatically. The new source description declares additional occurrences, new groups, construction recipes and resolution records. The map does not duplicate their contents.

Addition admission preserves all old groups/UUIDs, old occurrence texts, existing resolution/variant decisions and existing construction recipes. New groups require fresh UUIDs, fresh assignment IDs, construction recipes and explicit resolution states. New accepted targets must use already declared reusable recipes in this bounded mode. A new mention UUID already present in the graph is refused before writes. At least one occurrence or group must be added. Removal and addition modes cannot be combined. Splits, combinations, kind changes, new reusable identities and interpretation changes require later admission work. Unchanged-text additions from a new Describe pass are also outside this text-edit slice.

The durable replacement plan stores the map, exact intended description, old/new texts and native chunk budget. Reconcile completes that exact intent, reusing the saved new UUID rather than selecting identities again. The default prefix-insertion and explicit removal admissions retain their own boundaries. This adds no saved-source schema, role registry, model call, backend-specific write code or new coordinator.

## Run

Use a new output directory:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_additions
uv run python -m cognee_lab.identity add-occurrences \
  --root outputs/stage6_additions --source doc01 --expected-revision 1
```

Expected: doc01 current at saved/registered/verified revision 2, doc02 unchanged at revision 1, **three retrieved facts** (two local facts from doc01 and the unchanged doc02 fact), no unavailable sources and no recovery incidents. `occurrence_addition_result.json` contains the result. Review copies of the intended source JSON and revised original text are also written.

In `text_changes[0]`, check:

- `occurrence_continuity` equals the map above; `occurrence_retention` and `position_shift` are null.
- `groups.g01` has two previous occurrences and three current occurrences. Its Entity ID continues.
- `groups.g03` has no previous occurrences; `added_groups.g03` reports the new node, name index and exactly its current marker chunks.
- Retired old chunks/vectors are absent. Continuing facts use the current evidence map; `retired_groups` is empty.

The new fact has identity assignment `r03`, its new local Entity as source, the reusable controller as interpreted target, and native evidence from the current doc01 chunks. Doc02's source summary and fact/evidence, shared contributions and borrowed controller fields are preserved. Dataset IDs vary by root; compare within one run.

Reopen and reconcile:

```bash
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_additions
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_additions --source doc01
```

The same three facts and the new group ID must remain. A later captured prefix edit at expected revision 2 must preserve g03 and its fact at revision 3. Identity-source withdrawal withholds doc01's two facts while preserving doc02. It does not remove original Data or its independently owned facts/markers.

## Interrupted addition

Use another fresh root:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_additions_failure
uv run python -m cognee_lab.identity add-occurrences \
  --root outputs/stage6_additions_failure --expected-revision 1 \
  --fault-stage replace_published
# Expected injected failure.
uv run python -m cognee_lab.identity retrieve \
  --root outputs/stage6_additions_failure
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_additions_failure --source doc01
```

Before recovery, only doc02's fact returns and doc01 reports `publication_failed` with an incident ID. Reconcile completes revision 2, returns three facts and resolves that same incident with one verified recovery attempt. The native test selection also exercises `text_chunks`, before new identity materialization. This is explicit forward completion, not atomic visibility for arbitrary native readers, rollback, or automatic retry.

## Verification profile

The fixture uses Cognee 1.6.2 graph, vector, and relational interfaces. It uses deterministic loopback embeddings and captured decisions. It makes no LLM call. The isolated profile selects LiteLLM's bundled pricing map instead of its unrelated startup network refresh. A longer subprocess allowance accommodates cold native imports. The current handoff and delivery test notes distinguish ordinary CLI results from any host-only test-launcher workaround. None of that launcher is part of application persistence.

The checkpoint passed 81 programmatic tests and all three new native sequence cases. Native assertions ran with a host-only launcher after ordinary CLI output exposed a Linux interpreter-teardown timeout. This does not establish clean ordinary CLI exit on this host. The launcher exits only after CLI completion and explicit store closure and is not application code. Ordinary Mac CLI addition, reopened retrieval, healthy reconcile and `replace_published` failure/recovery were independently reproduced by the user and reviewed on 2026-10-20, as detailed below. The other 26 native cases were not rerun. See the delivery's `TESTS.md` for the exact evidence boundary.

### Reviewed Mac results

On `outputs/stage6_additions`, successful addition returns three facts with doc01 current at saved/registered/verified revision 2 and doc02 unchanged at revision 1. Reopened retrieval and healthy reconcile preserve the facts, source summaries, shared contributions and borrowed Entity fields without increasing revisions or recording incidents.

On `outputs/stage6_additions_failure`, injected `replace_published` failure withholds doc01 as `publication_failed` while doc02's unchanged fact/evidence remains available. Explicit reconcile restores the same intended revision 2 and three facts. Incident `f93491d5-3f5a-58c0-b786-a3874c27059c` ends `restored` with one verified recovery attempt. Fresh g03 `a75636db-c46d-5261-a21e-010647bfe4f4` has its node/name index, accepted r03, and complete current marker/evidence mapping across two chunks. Continuing mention IDs are preserved and retired chunks/vectors are absent.

The assistant reviewed user-supplied terminal JSON rather than executing on the Mac. Mac results for `text_chunks` failure, a later prefix edit and withdrawal after addition have not yet been reviewed. These results leave the generation-environment Linux teardown qualification above unchanged.

## Remaining work

Step 4 remains partial. Group splits/combinations, mixed addition/removal, representation-kind changes, changed interpretation and semantic refresh, dependency-aware multi-source/span/record reconsideration, and coordinated full original/generated Data lifecycle remain. Standard entry-point/public retrieval integration is step 5. Automated Describe and its separate quality evaluation are step 6.
