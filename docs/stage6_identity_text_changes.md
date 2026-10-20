# Step 4 / M3: source-text edits with a whole-document rebuild

**Guide scope:** commands and limits for this captured profile. For current project status, subsequent checkpoints, code baseline and verification evidence, start with [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

This checkpoint extends guarded identity revision replacement to a captured prefix insertion in doc01. It uses Cognee 1.6.2 through configured interfaces, with no LLM calls or backend-specific storage code. It is a bounded maintenance demonstration, not completion of step 4 or standard Update wiring.

## Run on a fresh two-source fixture

Apply this patch after the revision-replacement checkpoint. Use a new root so both documents have the corrected captured fact-endpoint ownership:

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/stage6_text_changes
uv run python -m cognee_lab.identity edit-text --root outputs/stage6_text_changes --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_text_changes --source doc01
```

The inserted prefix is exactly:

```text
Revision note: Δ calibration schedule updated.

```

There are two newline characters after the sentence. The prefix has 48 Unicode code points and 49 UTF-8 bytes. Positions remain document-relative Unicode [start,end) offsets. The fixture supplies a captured review that the interpretation and local fact remain the same; no algorithm infers that a prefix is semantically irrelevant.

| Observation | Before | After |
|---|---|---|
| doc01 saved / verified / registered identity revision | 1 / 1 / 1 | 2 / 2 / 2 |
| doc02 revisions | 1 / 1 / 1 | 1 / 1 / 1 |
| doc01 original Data ID | Existing ID | Same ID |
| doc01 “The controller” | [49,63) | [97,111) |
| doc01 “it” | [86,88) | [134,136) |
| doc01 unresolved “plasma” group | [33,39) | [81,87) |
| doc01 chunk ID and text fingerprint | Previous content | New native content-derived chunk ID and fingerprint |
| doc01 group Entity IDs / ordinary fact ID / resolution target | Existing values | Preserved by the supplied reviewed intent |
| doc01 evidence and original ownership | Previous chunk | Rebuilt under the new original chunk |
| doc02 fact, evidence, owner and identity interpretation | Existing values | Preserved |

The edit command writes `text_revision_result.json`; reconcile writes `multisource_result.json`. The edit result and immediate failed-edit recovery result include `text_changes` diagnostics with old/new positions, chunk IDs and hashes, retired chunk graph/vector checks and current evidence checks. `identity_doc01_text_revision2.json` and `source_doc01_revision2.txt` are review copies. The initial `source.txt` and `identity.json` remain baseline fixture inputs. Current operations read the saved ledger description and native registered original text, rather than treating those baseline files as current. A later healthy reconcile replaces the completed mutation plan with its own publication plan, so historical transition diagnostics remain in the saved edit-result file rather than being duplicated indefinitely in every subsequent status result.

## Describe, Publish and Maintain responsibilities

The captured Describe step supplies the complete new IdentitySource: exact text fingerprint, every new native chunk and document range, remapped occurrence lists and chunk references, reviewed assignment decisions and producer attribution. The fixture changes producer attribution to `text_review` for the groups and decisions that were reviewed against the edited document. Unresolved groups are remapped too. The existing model already requires chunk ranges to cover every occurrence, including an occurrence crossing a boundary.

`TextChange(previous_text, text, chunk_budget=512)` describes the exact original-text transition. Pass it to `Publisher.replace` with the intended next source, prepared native chunks, real generated-source context, expected saved revision, and explicit `semantic_writer` / `verify_semantics` callbacks. These callbacks receive no automatic identity or scientific reasoning. The fixture supplies captured fact generation and verifies the independently supported doc02 fact as well as the rebuilt doc01 fact.

The default prefix-mode admission is deliberately narrow: one original plain-text Data item; a nonempty prefix insertion; stable group IDs, occurrence texts, group membership, assignments and construction recipes; exact shifted ranges; native TextChunker output and exact tiling. An explicit occurrence-retention manifest now admits the documented removal/retirement modes through the same API. Additions/regrouping, changed interpretation, span-scoped variant remapping, span/record dependencies and additional consumed documents remain outside these modes. A dependent saved identity source referencing the edited original is refused before mutation; automatic reconsideration of that source is not implemented.

Maintain uses a full rebuild of this original document, even if an incremental update could preserve some chunks. The original default fixture still fits in one native chunk. The later [multi-chunk checkpoint](stage6_identity_multichunk.md) adds a native small-budget profile, split occurrence markers and two-chunk captured fact evidence. General multi-chunk semantic extraction and interpretation remain unevaluated.

## Native write sequence

1. Validate the prior current publication and expected revision, native registered original/hash, reviewed next intent and exact old/new occurrence mapping. Prepare the new chunks in memory with native TextChunker. Check graph-provenance deletion capabilities, dependent sources and unsafe endpoint cascades.
2. Save the next identity description as pending before any destructive original-memory change. Its durable replacement plan contains the previous description plus exact previous/new text and chunk budget. Preserve the last verified revision. Recovery must reuse the exact saved text transition as well as the same intended record.
3. Call native `cognee.forget(data_id=..., dataset_id=..., memory_only=True)`. It removes the selected original document's native ownership/memory and document evidence; the relational Data row remains. Independently owned graph objects should survive according to native ownership.
4. Use native `ingest_data` under the same explicit original Data ID to store the new text and maintain native file locations, hashes and size. Recreate native Document/DocumentChunk graph structures and indexes using `add_data_points`.
5. Update the registered generated identity JSON under its existing Data ID. Run the common identity publisher and the supplied semantic writer. Rebuild facts/evidence from the new chunk context, attach new original-owned mention markers and replace versioned identity contributions.
6. Verify required semantic output and independent-source survival, current occurrence/chunk mapping, native ownership, registered snapshot agreement, removal of retired chunk graph/vectors, and absence of old document evidence in the captured fact. Only then acknowledge the matching revision/attempt as current.

This composes native removal, ingestion, chunking, storage and provenance Tasks. It does not call or modify the high-level `cognee.update` pipeline: the default update path would also select/run native extraction. Standard task-transform wiring remains step 5. Existing compatible Entity fields are referenced without ordinary-property overwrite.

### Ownership finding

The first development run exposed a bug in our captured fact writer: when doc02 reused the existing oscillations endpoint, it did not attach doc02's original-chunk source ref to that endpoint. Native doc01 memory removal correctly considered that endpoint unowned, deleted it, and cascaded into doc02's incident fact despite that fact's independent owner. The fixture writer now explicitly retains compatible reused endpoints for each producing chunk. The edit preflight also refuses an endpoint deletion when a bounded neighborhood check finds an incident edge with an owner that would survive; it does not silently repair missing provenance. A limit hit refuses the operation instead of assuming deletion is safe.

Owning a fact is not sufficient to keep its endpoints alive. This is a custom-write integration obligation, not evidence of a native deletion bug. The endpoint issue was not exercised by previous generated-identity withdrawal tests, because those withdrawals intentionally retained original semantic memory.

## Interrupted edit and recovery

Use another fresh root:

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/stage6_text_failure
uv run python -m cognee_lab.identity edit-text --root outputs/stage6_text_failure --expected-revision 1 --fault-stage text_registered
# Expected injected failure.
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_text_failure
uv run python -m cognee_lab.identity status --root outputs/stage6_text_failure
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_text_failure --source doc01
```

| Interruption | Original native state | Identity publication |
|---|---|---|
| text_removed | Prior text row remains; original memory/evidence removed | Saved next revision failed; prior verified revision retained |
| text_registered | New text registered; its chunks/facts not rebuilt yet | Failed and withheld |
| text_chunks | New native chunk structures/indexes written | Failed and withheld |
| replace_published | New chunks, captured facts, markers and identity links written; final cleanup/verification incomplete | Failed and withheld |

The integration retriever should return doc02 alone while doc01 is failed. Reconcile loads the exact saved text transition, accepts only previous/new registered original text, repeats native memory removal/rebuild and completes the saved revision without a new Describe decision. It links the verified retry to the same incident and records `resolving_revision: 2`. `outcome: restored` means the intended revision is usable; no rollback to revision 1 occurred.

Rebuilding the whole document again on a caught-failure retry keeps the first implementation simple and removes partially rebuilt evidence before recapturing it. There is no resumable substep scheduler, A/B graph copy, automatic retry or abrupt-crash writer abandonment. Native readers that ignore the integration ledger can still observe partial state.

## Verification and remaining work

Tests cover Unicode/document positions, stale offsets despite a current hash, changed interpretation admission, split occurrence coverage, dependent-source refusal, unsafe endpoint cascades, the real native edit/reopen/reconcile/withdraw sequence, doc02 preservation, and caught failures at all four boundaries above. Previous publication, withdrawal and unchanged-text revision tests remain regressions. The initial backend profile is still the only native profile exercised; code uses configured interfaces.

Remaining step-4 work includes occurrence additions/regrouping, changed interpretations with refreshed semantic output, supported span/record and dependent-source maintenance, and coordinated original/generated Data removal/rebuild cases. Captured occurrence removal and resolved fact retirement are implemented in subsequent guides. General semantic conversion remains broader than the captured writer; incremental chunk reuse is deferred, not a step-4 completion gate. Decision-model/LLM Describe quality remains a separate later evaluation. Saved previous/new text increases recovery-plan size; the existing planned size/metrics work should measure that overhead before introducing compression, shared blobs or a larger replay framework.

Subsequent checkpoint: [reviewed occurrence removal](stage6_identity_occurrence_removal.md) now admits explicitly selected survivors and retires empty unresolved groups. This does not extend the prefix fixture into an automatic arbitrary-edit Describe algorithm.
