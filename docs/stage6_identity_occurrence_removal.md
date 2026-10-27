# Step 4 / M3: reviewed occurrence removal

**Guide scope:** commands and limits for this captured profile. For current project status, later checkpoints, the code baseline, and verification evidence, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md). The creation commands `fixture`, `multi-fixture` and `chunked-fixture` use the `.env` embedding settings by default (`--embedding env`). For an offline root with deterministic embeddings, add `--embedding loopback` to the creation command.

This checkpoint adds explicit occurrence removal to the native whole-document rebuild. It uses captured identity/semantic review, exact positions, the existing publication ledger and native Cognee 1.6.2 interfaces. It covers only part of step 4.

## Concrete example

Start from doc01 of a fresh `chunked-fixture`:

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.
```

The captured replacement text is:

```text
Helios controller (HC) regulates heating, and it limits oscillations.
```

Each string ends with a newline. The source supplies a captured review that the remaining `it` still refers to the same controller and supports the same local `limits` fact. The code does not infer this interpretation from the deletion.

The explicit retention map is `{"g01": [1], "g02": []}`. Values are ordered zero-based indices into the **previous saved revision's occurrence list**. The map applies only to this transition. Its durable change plan stores the map. These indices are not permanent occurrence IDs or a new source-schema field.

- g01 retains its second occurrence, `it`, at the supplied new document range `[46, 48)`. Its group UUID, Entity UUID, resolution-record ID, target and ordinary fact ID continue. Its first occurrence, `the controller`, is removed from the saved group and retrieval annotation.
- g02 loses its only occurrence, `plasma`. Its saved group, unresolved resolution record and Entity construction declaration are removed. Native original-memory removal retires its old markers. Removal of its generated-source retention deletes its now unowned Entity and vector. Other owners would retain an Entity; losing this source alone does not authorize deleting foreign support.
- Every replacement chunk is constructed by the native chunker with the recorded budget. The local fact is regenerated from the captured remaining span with current native ownership/evidence. This is a whole-document rebuild, not preservation of old fact materialization merely because its ID continues.
- doc02's description, local fact, chunks/evidence and shared-edge contribution remain independent. The existing reusable controller's ordinary fields are not rewritten.

## Run and inspect

Apply this checkpoint after the multi-chunk maintenance patch. Choose a new root:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_occurrences

uv run python -m cognee_lab.identity remove-occurrences \
  --root outputs/stage6_occurrences --source doc01 --expected-revision 1
```

Expected: two retrieved facts. Doc01 current at saved/registered/verified revision 2, doc02 unchanged at revision 1. Doc01's fact annotation contains only `it`. Its unresolved Entity and marker flags are false. In `text_changes`, `retired_groups.g02` reports no Entity, index entry or marker; retired chunks/vectors are absent. Evidence uses current chunks. `position_shift` is null because a deletion is not described by one global offset shift. `text_length_delta` reports the net character-count change without assigning that change to every occurrence.

The command writes `occurrence_revision_result.json`, intended identity JSON, and new original text to the isolated output root. Baseline fixture files are not authoritative after a revision. Readers use the saved current description and registered original. Healthy reconciliation must not resurrect g02:

```bash
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_occurrences --source doc01
```

## Explicit recovery

Use another fresh root:

```bash
uv run python -m cognee_lab.identity chunked-fixture \
  --root outputs/stage6_occurrences_failure
uv run python -m cognee_lab.identity remove-occurrences \
  --root outputs/stage6_occurrences_failure --expected-revision 1 \
  --fault-stage replace_published
# Expected intentional failure before final retirement/verification.
uv run python -m cognee_lab.identity retrieve \
  --root outputs/stage6_occurrences_failure
uv run python -m cognee_lab.identity reconcile \
  --root outputs/stage6_occurrences_failure --source doc01
```

The failed attempt withholds doc01. Doc02's complete fact remains available. Reconcile uses the exact saved intended revision, retention map, previous/new text and chunk budget, repeats the whole-document rebuild and completes retirement. It does not repeat identity judgment. It does not reconstruct continuity from stale spans. The system resolves the same diagnostic incident only after it verifies revision 2. Native tests also cover failure at `text_chunks`, before the fact and identity materialization are rebuilt.

## API and remaining limits

**Superseded on 2026-10-21.** The general occurrence map replaced the separate admission modes. The command now saves `TextChange.occurrence_map`, and `admit` in `src/cognee_lab/identity/admission.py` applies one rule set to every edit. See "General occurrence map, approved 2026-10-21" in [the checkpoint history](stage6_checkpoint_history.md#general-occurrence-map-approved-2026-10-21). This edit's map is `{"g01": [null, ["g01", 0]], "g02": [null]}`, and the result field `occurrence_retention` is now `occurrence_map`. The text below records this checkpoint as it was built.

`TextChange(previous_text, text, chunk_budget, occurrence_retention=...)` selects the reviewed-removal admission path. Every old group must be present in the map. Lists must contain unique, ordered, in-range integer indices (booleans are refused). Continuing groups keep their Entity/document identity and occurrence texts, with exact valid new spans. Empty lists explicitly retire the group and its resolution/declaration. Continuing assignments and other construction recipes remain unchanged. The default with no retention map preserves the existing prefix-only guard.

The remove-occurrences command accepts only its documented fresh doc01 input. It does not locate arbitrary repeated phrases or decide ambiguous continuity. It does not add occurrences, split/combine groups or retarget surviving groups. The separate retire-resolved-group command covers a resolved group with its captured local fact. General semantic extraction remains unimplemented. The common replacement API requires caller-provided semantic rebuilding and verification. Span/record dependencies, dependent-source propagation and coordinated full original/generated Data removal remain later work. No backend-specific implementation, new dependency, new schema field or native Cognee source change is included.

The subsequent [resolved-group retirement checkpoint](stage6_identity_resolved_retirement.md) adds the captured case of removing a resolved group and its original-owned local fact/evidence, preserving a different fact from doc02. It reuses this explicit retention format and coordinator.
