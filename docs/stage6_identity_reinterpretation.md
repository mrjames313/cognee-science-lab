# Stage 6 changed interpretation and representation-kind changes

**Date:** 2026-10-22. **Status:** implemented and verified by the assistant on the user's Mac with loopback embeddings. No user-reviewed fixture root exists yet.

Four captured edits to doc01 change what a mention means or how HC is represented. Two are text edits that change the interpretation of a mention. Two keep the text and change whether HC is a reusable Entity or a document-local mention. All four run through the one admission of checkpoint D (`admit` and `admit_replacement`) with no change to `admission.py`. Each case is captured fixture input: a reviewer wrote the texts, the maps and the descriptions, and the process does not infer them. The user approved the four cases in outline on 2026-10-22. The rules they rely on are in "One admission for every replacement, 2026-10-22" in the [session handoff](SESSION_HANDOFF.md).

Commands (each needs `--expected-revision` and runs on doc01 of a `chunked-fixture` root):

- `reinterpret --case new-entity` and `reinterpret --case unresolved`: revision 1 to 2, changed text.
- `change-kind --direction to-mention`: revision 1 to 2, unchanged text.
- `change-kind --direction to-reusable`: revision 2 to 3, unchanged text, on the root that `to-mention` produced.

Each command writes its own result file: `reinterpretation_new_entity_result.json`, `reinterpretation_unresolved_result.json`, `kind_change_to_mention_result.json` and `kind_change_to_reusable_result.json`. Each refuses any other root, source or revision.

## Starting point

All four cases start from doc01 of a fresh `chunked-fixture`, at revision 1. Its text, with a trailing newline, is:

```text
Helios controller (HC) regulates plasma heating, the controller adjusts coil current, and it limits oscillations.
```

The groups and records are:

- g01 holds `the controller` at `[49,63)` and `it` at `[90,92)`. Its Entity UUID is `233cb019-3986-5864-88bc-91f334a64372`. Resolution r01 accepts it to the reusable Helios controller A, `8b4bff50-907b-56b6-bc80-3b0a7018714a`. The captured fact `it limits oscillations` belongs to g01.
- g02 holds `plasma` at `[33,39)` and is unresolved (r02).
- v01 is a document-scoped variant from HC (`9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88`) to A, scoped to doc01. doc01 declares the HC recipe.
- doc02 is a separate source. Its own mention group resolves to A, its own variant v01 sits on the same HC to A edge, and it declares and owns HC too. doc02 stays at revision 1 in every case.

Offsets are Unicode code points, `[start, end)`. The doc01 identity source is `718efce2-4251-5f6f-8318-417bb4dd3525`. At the `chunked-fixture` budget of 9 tokens the native chunker splits the text into six chunks, `[0,23)`, `[23,40)`, `[40,64)`, `[64,86)`, `[86,100)` and `[100,114)`.

## Changed interpretation to a new Entity

`reinterpret --case new-entity` changes `the controller` to `the backup controller`. The new text, at revision 2, is:

```text
Helios controller (HC) regulates plasma heating, the backup controller adjusts coil current, and it limits oscillations.
```

| Old occurrence | Old span | Outcome | New span |
|---|---|---|---|
| g01 `the controller` | [49,63) | Removed | None |
| g01 `it` | [90,92) | Moved to fresh g03 as occurrence 1 | [97,99) |
| g02 `plasma` | [33,39) | Continues in g02 | [33,39) |
| New `the backup controller` | None | Added as g03's occurrence 0 | [49,70) |

The map is `{"g01": [null, ["g03", 1]], "g02": [["g02", 0]]}`. The new text is seven code points longer. g01 does not continue, because its `it` moved to another group. The strict continuation rule retires it, and its decision is not carried to a continuing group. This is the user's decision of 2026-10-22: a changed meaning in a text edit is a fresh group, and a retired ID is never served with a new meaning.

- g03 is fresh. Its Entity UUID is `uuid5(identity_data_id, "mention:r2:g03")`, which is `4827dc6d-3687-56e7-8a15-96a9dc30c070`. Its recipe name is `the backup controller; it`.
- Resolution r03 accepts g03 to a new reusable Entity, the Backup controller. Its UUID is `uuid5(identity_data_id, "entity:r2:r03")`, named by the key of r03, which is `30d7405d-10a3-5a53-a8da-8c707cb12310`. Its recipe is `Backup controller`. Admission derives and probes this UUID, and the graph has no such node before the first attempt.
- g01, r01 and g01's recipe retire. g02, r02, v01, A and HC stay. v01 stays because a document-scoped variant names its document, not positions, so a text edit cannot invalidate it.
- `describe_new_entity` in `src/cognee_lab/identity/reinterpretation.py` builds the description. The producer is `stage6-captured-reinterpretation-new-entity`, policy `explicit-changed-interpretation-v1`.

The new chunks are `[0,23)`, `[23,40)`, `[40,60)`, `[60,84)`, `[84,107)` and `[107,121)`. g03 marks three chunks, because `the backup controller` at `[49,70)` crosses the boundary at 60 and `it` at `[97,99)` lies in `[84,107)`. The fact `it limits oscillations` at `[97,119)` crosses the boundary at 107, so its evidence uses two chunks. The whole-document rebuild generates the fact again from g03, with fact edge `a2ffe80a-d8b3-5362-977d-b71697de1105`. g01's fact edge, `a099f62a-d5a9-5f4c-ace8-333ee32f368e`, its evidence and its triplets are physically removed. Nothing is transferred.

Expected retrieval, observed on the user's Mac:

- The default query `What does HC limit?` and `What does Helios controller limit?` each return one fact: doc02's, source `e7ec7685-72e3-5bba-a511-e4bb49682ba4`, edge `88b34a81-ad44-594f-ba01-08e7aab7c87c`. doc01's fact is gone for the Helios controller.
- `What does Backup controller limit?` seeds the Backup controller and returns one fact: source g03, assignment r03, target the Backup controller, text `it limits oscillations`, with the occurrences `the backup controller` at `[49,70)` and `it` at `[97,99)`.
- The shared HC to A edge keeps both contributions, because v01 stays. The Backup controller is in the graph and indexed. A is unchanged.

## Changed interpretation to unresolved

`reinterpret --case unresolved` changes the clause so that nothing says what the referent is. The new text, at revision 2, is:

```text
Helios controller (HC) regulates plasma heating. A controller adjusts coil current, and it limits oscillations.
```

| Old occurrence | Old span | Outcome | New span |
|---|---|---|---|
| g01 `the controller` | [49,63) | Removed | None |
| g01 `it` | [90,92) | Moved to fresh g03 as occurrence 1 | [88,90) |
| g02 `plasma` | [33,39) | Continues in g02 | [33,39) |
| New `A controller` | None | Added as g03's occurrence 0 | [49,61) |

The map is the same as above. The new text is two code points shorter. g03 has the same derived UUID, `4827dc6d-3687-56e7-8a15-96a9dc30c070`, and its recipe name is `A controller; it`. Resolution r03 is unresolved. No new reusable Entity is declared. The producer is `stage6-captured-reinterpretation-unresolved`, built by `describe_unresolved`.

The new chunks are `[0,23)`, `[23,40)`, `[40,62)`, `[62,84)`, `[84,98)` and `[98,112)`. g03 marks two chunks, `[40,62)` and `[84,98)`. The fact at `[88,110)` crosses the boundary at 98, so its evidence uses two chunks. The fact is generated again from the unresolved g03, with the same edge ID as in the other case, because that ID derives from g03's UUID and the endpoints.

Expected retrieval: no query returns doc01's fact. The default HC query and the Helios controller query each return only doc02's fact. The fact exists in the graph, with its text and evidence, so the absence comes from retrieval's rule that only an accepted mention reaches a fact through an eligible Entity. It does not mean the fact was not written.

## Reusable to mention

`change-kind --direction to-mention` keeps the text. Revision 2 has the same text as revision 1, so the map moves nothing:

```json
{"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]]}
```

doc01 drops v01 and the HC recipe, and adds a fresh group g03 that holds `HC` at `[19,21)`.

- g03's UUID is `4827dc6d-3687-56e7-8a15-96a9dc30c070`, the same derivation as above (`mention:r2:g03`). Its recipe name is `HC (local mention)`.
- Resolution r03 accepts g03 to A, with the same inputs as r01. Because g03 resolves to A directly, doc01 no longer needs HC to reach A.
- g01 and g02 continue unchanged, with the same UUIDs, spans and decisions. No group retires.
- doc02 still declares HC and its own v01, so the shared HC to A edge survives with doc02's contribution and owner only. The HC Entity survives with doc02 as its only owner. doc01's `HC` text is now a local mention that no query treats as a name.
- The producer is `stage6-captured-kind-change-to-mention`, policy `explicit-reusable-to-mention-v1`, built by `describe_to_mention` in `src/cognee_lab/identity/kind_change.py`.

The text is unchanged, so every chunk keeps its content-derived ID. g03 marks one chunk, `[0,23)`.

Expected retrieval, observed on the user's Mac:

- The default HC query returns only doc02's fact. doc01's fact is not reached through HC, because doc01 no longer declares HC or v01.
- `What does Helios controller limit?` returns two facts: doc02's, and doc01's with the same source `233cb019-3986-5864-88bc-91f334a64372` and the same fact edge `a099f62a-d5a9-5f4c-ace8-333ee32f368e` as at revision 1. The fact is generated again from the rebuilt chunks with the same meaning.
- The shared edge has one owner and one contribution (doc02's). The HC Entity has one owner. Exactly one Entity is named HC.

## Mention to reusable

`change-kind --direction to-reusable` runs on the same root at revision 2. The text is still unchanged. The map is:

```json
{"g01": [["g01", 0], ["g01", 1]], "g02": [["g02", 0]], "g03": [null]}
```

g03 retires with its Entity, name index, marker, resolution and link. doc01 then:

- declares the HC recipe again: name `HC`, description `Abbreviated reusable form in DOC01.`, the same Entity UUID as doc02's HC.
- adds the corpus input `existing_HC`, a `corpus_object` for that UUID with selected fields `name` and `description` and the hash of their current values.
- adds v02, a document-scoped variant from HC to A, scoped to doc01. Its `input_refs` are `doc01`, `existing_A` and `existing_HC`.

Because v02 lists `existing_HC`, admission treats HC as an existing Entity that input validation proves, not as a new Entity to derive. `referenced_corpus_ids` in `admission.py` reads only inputs that some record lists. Without that listing admission refuses the description with `entity_uuid_not_derived`, which a unit test pins. Input validation reads the HC node from the graph and compares the hash, so a changed HC field fails with `input_changed`. A unit test pins that too. The variant key is v02, not v01, because v01 was dropped in revision 2 and a new variant key must not repeat an old resolution key.

Expected results, observed on the user's Mac:

- The shared HC to A edge has two contributions: doc02's (v01) and doc01's (v02, revision 3), and two owners.
- No duplicate HC Entity exists: one node named HC, with two owners.
- The default HC query returns both facts, doc02's and doc01's, with the same source and edge IDs as at revision 1.
- g03 is absent: no node, no name index, no marker.

`describe_to_reusable` refuses a root whose doc01 was not produced by `to-mention`.

## Equal texts

The two kind changes are the first runs of a `TextChange` whose before and after texts are equal. A fresh group needs a rebuild, because only a rebuild writes its markers, and the entry point `admit_replacement` refuses a retired or fresh group without a text change (`rebuild_required`). `TextChange.apply` forgets the document's memory, writes the text again, rebuilds the chunks and indexes, and the semantic writer generates the facts again. No code change was needed for equal texts. The rebuilt chunks have the same IDs as before, so `content_ids_present_in_both` equals `chunk_ids` and `retired_chunks_absent` holds vacuously. The retry path also works with equal texts. `to-mention` recovered from injected `text_removed`, `text_chunks` and `replace_published` failures, and `to-reusable` from `text_chunks` and `replace_published`, each with one verified `reconcile` attempt.

## Code changed outside the fixtures

- `captured_chunks.py`: `CAPTURED_GROUPS` became `CAPTURED`, a tuple of entries that carry their key. `lineage_groups` returns the entries that a source's producer lineage can have declared, so g03 means the addition's group, the interpretation's group or the kind change's group by lineage. Before this, a dictionary keyed by group key could name only one g03.
- `captured_revision.py`: `declare_group` takes any reviewed decision, accepted or unresolved, and copies its fields, instead of building an accepted one.
- `resolved_retirement.py`: `retirement_checks` reads the controller from the `existing_A` input instead of the v01 variant, which `to-mention` drops.
- `occurrence_fixture.py` and `__main__.py`: `VARIANT_COMMANDS` holds the commands that take an option, `--case` or `--direction`, and the CLI refuses a missing or misplaced option.

`admission.py` and the saved-source schema are unchanged.

## Run

Use a new output directory. This sequence uses loopback embeddings:

```bash
uv run python -m cognee_lab.identity chunked-fixture --root outputs/<new root> --embedding loopback
uv run python -m cognee_lab.identity reinterpret --case new-entity --root outputs/<new root> --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity retrieve --root outputs/<new root> --query "What does Backup controller limit?"
uv run python -m cognee_lab.identity reconcile --root outputs/<new root> --source doc01
```

For the other cases, replace the second command with `reinterpret --case unresolved ... --expected-revision 1` or `change-kind --direction to-mention ... --expected-revision 1`. Run `change-kind --direction to-reusable ... --expected-revision 2` on the root that `to-mention` produced. Use a separate new root for each case that starts at revision 1.

Expected for `reinterpret`: doc01 current at saved, registered and verified revision 2, doc02 at 1/1/1, no unavailable source and no incident. In `text_changes[0]`, `occurrence_map` equals the map above, `position_shift` is null, `added_groups` has exactly g03 with its node, name index and marker chunks, and `retired_groups` has exactly g01, with no Entity, index entry or marker. Retired chunks and vectors are absent. `sources.doc01.resolved_group_retirement` reports g01's mention, link, fact, marker and triplets as absent. The result adds `queries`, with the Helios controller and (for `new-entity`) Backup controller retrievals, and `g03`, with its resolution status, the regenerated fact edge, text and evidence chunk IDs, and (for `new-entity`) its target Entity.

Expected for `change-kind`: doc01 current at revision 2 (`to-mention`) or 3 (`to-reusable`), doc02 at 1/1/1. `text_changes[0]` has `text_length_delta` 0, equal `previous_text_sha256` and `text_sha256`, equal `previous_chunk_ids` and `chunk_ids`, and the map above. The result adds `queries` (the default HC query as `hc` and the Helios controller query), and `hc_entity` with its owner count and the IDs of every Entity named HC. A healthy `reconcile` keeps all of this.

## Interrupted edits

`--fault-stage replace_published` or `--fault-stage text_chunks` injects a failure into any of the four commands. doc01 is then withheld with `publication_failed` and an incident ID, and only doc02's fact is returned. The saved plan holds the reviewed map and, for a kind change, equal `previous_text` and `text`. `reconcile --source doc01` completes the saved revision and resolves the same incident with one verified attempt. The saved fresh UUIDs, including g03 and the Backup controller, are reused and not chosen again.

## Scope

Each command accepts only its captured edit on doc01 of a `chunked-fixture` root. `reinterpret` needs revision 1 and the original description. `change-kind --direction to-mention` needs revision 1. `change-kind --direction to-reusable` needs a doc01 that `to-mention` produced, at revision 2. A wrong `--expected-revision` is refused as `Saved revision changed`. Anything else is refused with a `fixture_scope` message before any write.

Still refused: a continuing group whose decision changes in a text edit, a corpus-scoped variant change in a text edit, span-scoped variants, a move to another document, and dependent sources. Admission is checked for unchanged text and changed text alike, so a retired or fresh group or an added occurrence still needs a text change.

What these fixtures do not establish: the decisions, spans and maps are supplied by the reviewer. They do not show that a model or rule can find the new referent, match HC in text, or decide that a mention changed meaning. The Backup controller is a fixture name, not an extracted entity.

## Evidence

The assistant (a subagent) ran these on the user's Mac on 2026-10-22 with loopback embeddings, on branch `stage6-reinterpretation` at `c2f17b3` for the source and tests. No file under `src/` changed afterwards.

- `uv run pytest -q -m 'not integration'`: 304 passed, 45 deselected.
- The unit tests of the four cases (`tests/test_identity_reinterpretation.py`, `tests/test_identity_kind_change.py`) admit each case's description through `admit_replacement` with the reviewed map and check the fate, the occurrences, the derived UUIDs and the captured facts. Each case also has refused wrong variants. `reinterpret` refuses an underived Backup controller (`entity_uuid_not_derived`), a Backup controller that is already a node (`entity_uuid_in_graph`), a retired key that returns with a new meaning (`fresh_key_reused`) and a continuing group whose decision changes in a text edit (`continuing_decision_changed`). `change-kind` refuses a fresh group without a text change (`rebuild_required`), an occurrence that moves while the text is unchanged (`occurrence_moved`) and an HC Entity that no record lists (`entity_uuid_not_derived`). One test pins that the HC corpus input's hash matches the HC recipe and that a changed HC field fails with `input_changed`. One pins that g03 reads the addition's, the interpretation's or the kind change's captured group by lineage.
- `uv run pytest -q -m integration`: 45 passed in 993 s, the full native suite, run beside the journeys. It includes `tests/test_identity_reinterpretation_native.py` (4 tests: healthy run, reopen and reconcile for both cases, and recovery after `text_chunks` and `replace_published`) and `tests/test_identity_kind_change_native.py` (5 tests: there and back with reopen and reconcile, scope refusals, recovery of `to-mention` after both stages, and recovery of `to-reusable` after `replace_published`).
- Verify journeys, each with 0 FAIL rows (each count includes three lab-store guard rows). New: I1 (33 PASS), I2 (22), I3 (19 for each of two stages), I4 (9), K1 (23), K2 (21), K3 (18 for each of two stages), K4 (18 for each of two stages) and K5 (10). Touched modules: R1 (27), O1 (22), O2 (18 for each of two stages), O3 (23), O4 (18 for each of two stages), O5 (27), O6 (17 for each of two stages), O7 (17), O8 (12 for each of two stages), G1 (32), G2 (20), G3 (36) and G4 (21). `journey all` was not run.
- The ledger check and `support/occurrence_check.py` were not run. No `RecordStore` caller and no part of `admission.py` changed.

The first journey runs found four wrong jq filters in the new feature file, all precedence errors where `.recovery_events` or `.unavailable_sources` sat after a pipe. They were filter errors, not code faults. The journeys and native tests passed on the first run of each command, including the equal-text `TextChange`.
