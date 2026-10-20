# Step 4 / M3: native multi-chunk maintenance

**Guide scope:** commands and limits for this captured profile. For current project status, later checkpoints, the code baseline, and verification evidence, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

This checkpoint adds a captured multi-chunk fixture to the text-replacement path. It exercises a grouped mention across chunks, a single occurrence split across a boundary, a fact whose literal text spans two chunks, changed boundaries, repeated edits, native evidence indexes, and explicit recovery. Decisions and fact spans are captured test input. This is not a general extraction or coreference algorithm.

## Run

Apply this incremental patch after the source-text changes patch. Use a fresh root:

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/stage6_multichunk
uv run python -m cognee_lab.identity edit-text --root outputs/stage6_multichunk --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_multichunk --source doc01
```

The new profile uses native TextChunker with a deliberately small budget of 9 tokens. The original doc01 is:

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.
```

The text ends with a newline. Doc02 has the same opening plus the existing startup sentence. Doc01 initially has six native chunks. Doc02 has eight. Each source has its own local mention group, identity contribution and original-owned fact. The unresolved plasma group and independent singleton support remain present.

The edit prepends exactly `Δ review: `: 10 Unicode code points, 11 UTF-8 bytes. The fixture supplies a captured review of unchanged interpretation. It does not infer that arbitrary new preceding text is irrelevant.

| doc01 observation | Initial | After first edit |
|---|---|---|
| Saved / verified / registered identity revision | 1 / 1 / 1 | 2 / 2 / 2 |
| Native chunk count | 6 | 6, with changed boundaries |
| “the controller” | [49,63) | [59,73), crossing chunks 2 and 3 |
| “it” | [90,92) | [100,102) |
| Group's marker chunk indexes | 2, 4 | 2, 3, 4 |
| Captured fact's owner/evidence chunk indexes | 4, 5 | 4, 5, with updated supporting content/mapping |
| Group Entity ID / fact edge ID / referent | Existing | Preserved |
| Doc02 revision and fact/evidence | Revision 1 | Unchanged |

The table uses zero-based indices. A boundary change can leave the total chunk count unchanged. Content-derived IDs can also recur when a chunk's text is unchanged. That does not establish that its position or index is unchanged.

`multisource_result.json` contains the initial or reconciliation summary. `text_revision_result.json` contains the edit summary and `text_changes` diagnostics. Source summaries now expose the complete `chunk_mapping`, `mention_marker_chunk_ids` and `fact_evidence_chunk_ids`. Each mapping entry reports actual marker presence, ownership of the captured fact and evidence presence, so the diagnostic distinguishes expectations from stored graph/provenance observations. A later healthy reconcile replaces its completed mutation plan. The historical edit result remains the transition record.

## Marker location and fact provenance are different sets

`has_identity_mention` belongs only on native chunks overlapping the stored occurrence ranges. A group can have occurrences in several chunks, and a single occurrence can require markers on both sides of a boundary.

The captured fact is the exact literal span `it limits oscillations`, starting at the group's explicitly stored `it` occurrence. The fixture computes its supporting chunks from the checked complete text/map. This fixture knowledge is not an assertion that a generic extractor can identify support spans mechanically.

The fact writer attaches native ownership to the edge and both endpoints for every producing chunk, writes native contains/production bookkeeping, and captures edge evidence through Cognee's existing per-chunk buffer/persistence interfaces. It does not make every mention-marker chunk an owner of every fact. Verification requires the exact original-document fact owner set and exact current `(chunk_id, chunk_index)` evidence set, plus all expected chunk vectors.

The final oscillations chunk supports the fact but contains no mention occurrence. Previously, the fixture retriever discarded evidence outside mention-marker chunks. That behavior would truncate this fact.

The retriever now requires at least one checked supporting chunk to overlap the group. It also preserves the complete checked native-owned evidence for the fact, including its continuation chunk. These checks apply to current-version evidence in the bounded fixture route. They do not add a public fact-source filter or request parameter.

Conversely, the earlier “the controller” occurrence supplies an identity marker but is not provenance for this particular captured `it limits oscillations` fact. The native tests assert both distinctions, including absence of markers and fact ownership where they do not belong.

## Preserve construction policy and current evidence

Healthy reconciliation and edits read the chunk budget from native `DocumentChunk.max_chunk_tokens` through the graph interface. Missing or inconsistent construction metadata is refused. The edit's existing durable TextChange plan retains that budget for recovery even if the original chunks have been removed. No schema field or parallel role registry was added.

The full-document replacement strategy remains unchanged: save guarded intent, remove original memory/evidence through native Forget, ingest under the same original Data ID, rebuild chunks, write captured facts and identity materialization, verify, acknowledge. This is still a complete source rebuild, even when a newly constructed chunk has the same content-derived ID as an earlier chunk. Native incremental reuse is not implemented.

The native happy-path test applies the prefix again at expected revision 2. The second edit reaches revision 3, creates seven doc01 chunks and shifts indexes of some content IDs that reappear. Verification checks evidence indexes against the new native chunks, not only UUID membership. Doc02 remains at revision 1. Subsequent identity withdrawal preserves the original-owned facts, evidence and mention markers under the current chunk mapping.

## Interrupted rebuild

Use another new root:

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/stage6_multichunk_failure
uv run python -m cognee_lab.identity edit-text --root outputs/stage6_multichunk_failure --expected-revision 1 --fault-stage text_chunks
# Expected injected failure.
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_multichunk_failure
uv run python -m cognee_lab.identity status --root outputs/stage6_multichunk_failure
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_multichunk_failure --source doc01
```

Before recovery, doc01 is failed and withheld. Doc02's fact remains available with both evidence chunks. Explicit reconciliation uses the saved budget/transition, repeats the whole-document rebuild, restores doc01 at 2 / 2 / 2 and resolves the same incident. Native tests cover interruption after chunk storage and after fact/identity graph publication. Existing earlier text-replacement failure boundaries remain regressions.

## Scope and next work

This checkpoint demonstrates native multi-chunk storage, provenance, and maintenance with one captured fact per document. The prefix profile does not evaluate LLM extraction or changed interpretations. Later removal/retirement profiles cover selected group-membership changes.

For this checkpoint, additions/regrouping, span-specific aliases, dependent-source reconsideration, generic source removal, and standard Task-transform wiring remain outside scope. It introduces no backend-specific graph queries, provider code, schema changes, or new dependencies. Native runtime evidence applies only to Cognee 1.6.2 with the configured stores.

The original six-step build order is unchanged. Step 4 has native chunk-boundary/evidence coverage and subsequent captured removal/retirement cases. Additions/regrouping, changed interpretations and dependency/source lifecycle remain. Carry forward the distinction between occurrence location, consumed context and fact-producing provenance when building measurement or other structured overlays.

The subsequent [reviewed removal checkpoint](stage6_identity_occurrence_removal.md) supplies explicit survivor indices and new exact spans for partial-group continuity and empty unresolved-group retirement. It retains this native rebuild/recovery path. The prefix profile above remains unchanged.
