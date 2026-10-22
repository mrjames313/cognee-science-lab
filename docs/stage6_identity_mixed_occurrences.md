# Stage 6 mixed occurrence revision

**Date:** 2026-10-22. **Status:** implemented and verified by the assistant on the user's Mac with loopback embeddings. No user-reviewed fixture root exists yet.

One edit to doc01 removes an occurrence, keeps an occurrence and adds an occurrence in the same group, and retires another group. Before the general occurrence map, each admission mode admitted only one kind of change, so this edit had no admission path. The general map admits it with no change to admission code. The case is captured fixture input: a reviewer wrote the map and the description; the process does not infer them.

The user approved the case on 2026-10-21. The rules it relies on are in "General occurrence map, approved 2026-10-21" in the [session handoff](SESSION_HANDOFF.md).

## Captured edit

Before, at revision 1 (the `chunked-fixture` doc01 text):

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.
```

After, at revision 2:

```text
Helios controller (HC) regulates heating, and it limits oscillations. During startup, the controller remains active.
```

Both texts end with a newline. Positions are Unicode code points, `[start, end)`.

| Old occurrence | Old span | Outcome | New span |
|---|---|---|---|
| g01 `the controller` | [49,63) | Removed | None |
| g01 `it` | [90,92) | Kept as g01's occurrence 0 | [46,48) |
| g02 `plasma` | [33,39) | Removed; g02 retires | None |
| New `the controller` (startup) | None | Added as g01's occurrence 1 | [86,100) |

The reviewed map is:

```json
{"g01": [null, ["g01", 0]], "g02": [null]}
```

It is the same map as the [occurrence removal](stage6_identity_occurrence_removal.md) case. The map states only where old occurrences went. The addition is the new occurrence that no old occurrence maps to, so the two edits differ only in their new descriptions.

## Decisions and identities

- g01 continues. It keeps its key, its Entity UUID `233cb019-3986-5864-88bc-91f334a64372`, its accepted resolution r01 to the reusable Helios controller and its recipe. It receives its one surviving occurrence and nothing from g02, so the strict continuation rule holds.
- g02 retires with its unresolved resolution r02 and its recipe.
- No group is fresh, so no new UUID is derived. The document-scoped HC variant assignment is unchanged.
- `describe_mixed` in `src/cognee_lab/identity/occurrence_fixture.py` builds the description. It shares `keep_g01_retire_g02` with `describe_removal`; the two differ in text, occurrences and producer (`stage6-captured-occurrence-revision`, policy `explicit-occurrence-map-v1`). Every captured describer is built from the helpers in `captured_revision.py`.

## Facts and evidence

At the `chunked-fixture` budget the native chunker splits the new text into four chunks, at 33, 56 and 90. g01's markers are on chunks 2, 3 and 4: `it` lies in chunk 2, and the added `the controller` at [86,100) crosses from chunk 3 into chunk 4. The whole-document rebuild generates the captured fact `it limits oscillations` again from g01's `it` occurrence at [46,68), with evidence in chunks 2 and 3 only. This is the first fixture where a continuing group's marker chunks and fact chunks differ. The fact edge ID stays the same, because it derives from g01's unchanged mention UUID and the same endpoints. Its evidence moves to the new chunks, and the old chunks and their vectors are retired. doc02's fact and evidence are untouched. Nothing is transferred.

## Run

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/<new root> --embedding loopback
uv run python -m cognee_lab.identity revise-occurrences --root outputs/<new root> --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/<new root>
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

Expected: two retrieved facts. doc01 is current at saved, registered and verified revision 2, and doc02 stays at revision 1. doc01's fact annotation has `it` at [46,48) and `the controller` at [86,100). `occurrence_mix_result.json` holds the result. In `text_changes[0]`, `occurrence_map` equals the map above, `added_groups` is empty, `position_shift` is null, `retired_groups.g02` reports no Entity, index entry or marker, and retired chunks and vectors are absent. A healthy `reconcile` keeps all of this.

## Interrupted edit

`--fault-stage replace_published` or `--fault-stage text_chunks` injects a failure. doc01 is then withheld with `publication_failed` and an incident ID, and only doc02's fact is returned. The saved plan holds the reviewed map. `reconcile --source doc01` completes revision 2 and resolves the same incident with one verified attempt.

## Evidence

The assistant ran these on the user's Mac on 2026-10-21 and 2026-10-22 with loopback embeddings:

- `tests/test_identity_mixed.py`: admission gives g01 continuing, g02 retired and no fresh group. With the four-chunk split, g01 marks three chunks and its fact uses two. Three wrong maps are refused: one where nothing of g01 survives (`fresh_key_reused`, the user's fresh-group policy), one that keeps g02, and one that maps `the controller` onto `it`.
- `tests/test_identity_mixed_native.py`: 2 passed (healthy run with reopen and reconcile, and recovery after `replace_published`). It shares its checks with the removal test and adds the marker and fact-chunk counts.
- Verify journeys O7 (18 checks) and O8 (12 checks for each of two fault stages): 0 FAIL. Each count includes three lab-store guard checks.

## Scope

`revise-occurrences` accepts only this captured doc01 edit on a fresh `chunked-fixture` root. It does not locate phrases or infer a map. Changed meaning, a change of representation kind, moves across documents, span-scoped variants and dependent sources stay refused.
