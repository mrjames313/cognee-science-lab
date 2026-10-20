# Publication and retrieval

A user creates an isolated fixture root with `fixture`, `multi-fixture` or `chunked-fixture`. The CLI publishes captured identity decisions through the real graph, vector and relational stores. The user then retrieves facts, reconciles, and reads status, each in a new process. A failed first publication hides its source until `reconcile` restores it.

Guides: `docs/stage6_identity_first_slice.md` (single and two-source fixtures, failure visibility), `docs/stage6_identity_multichunk.md` (the chunked fixture), `docs/SESSION_HANDOFF.md` ("Resolved: the repository `.env`..." for the `env` profile).

## Sub-features

- `publish-single` creates one source with one accepted local mention and one `limits` fact.
- `publish-two-source` creates two sources that share a variant edge and a singleton.
- `publish-chunked` creates two sources with a 9-token chunk budget, split markers and two-chunk fact evidence.
- `retrieve-reopen` returns the same facts from a new process.
- `reconcile-healthy` leaves a current publication unchanged.
- `status` lists publications and recovery events.
- `publish-failure` withholds a failed first publication, then restores it with `reconcile`.
- `profile-env` publishes with the embedding settings from `.env`. It calls the embedding API.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity fixture --root <new dir>` for one source.
- Run `uv run python -m cognee_lab.identity multi-fixture --root <new dir>` for two sources.
- Run `uv run python -m cognee_lab.identity chunked-fixture --root <new dir>` for two multi-chunk sources.
- Run `retrieve`, `reconcile [--source doc01|doc02]` and `status` against the same root.
- Add `--fault-stage identity_edges` to a creation command to test a failed first publication.
- Add `--embedding env|loopback` to a creation command. The CLI default is `env`.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey runs in its own `RUN`. The helper builds the root path. The root does not exist yet.
- Journeys `P1` to `P4` use the helper's loopback default. They need no network and no `.env`.

**P1 single publication.** Guide: first slice, "Run it" and "Expected result".

```bash journey P1
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run single-publication)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- fixture
$V check "$RUN" fixture '.result.facts | length == 1' 'one fact is published'
$V check "$RUN" fixture '.result.facts[0] | .relationship == "limits" and .text == "it limits oscillations"' 'the fact is the limits oscillations fact'
$V check "$RUN" fixture '.result.facts[0].identity | .state == "accepted" and .assignment_id == "r01"' 'the identity annotation is accepted'
$V check "$RUN" fixture '[.result.facts[0].identity.occurrences[] | [.start, .end, .text]] == [[49, 63, "The controller"], [86, 88, "it"]]' 'exact occurrence positions'
$V check "$RUN" fixture '.result.facts[0].evidence | length == 1 and .[0].chunk_index == 0 and (.[0].text | contains("it limits oscillations"))' 'original chunk evidence is returned'
$V check "$RUN" fixture '.result.seed_entity_ids[0] != .result.facts[0].identity.target_entity_id' 'the HC seed traverses to the reusable controller'
$V check "$RUN" fixture '.result.unavailable_sources == [] and .recovery_events == []' 'no unavailable source and no incident'
$V check "$RUN" fixture '.embedding.profile == "loopback"' 'the root records the loopback profile'

FACT=$(val fixture '.result.facts[0].edge_id')
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '.facts | length == 1 and .[0].edge_id == "'"$FACT"'"' 'a new process returns the same fact'
$V check "$RUN" reopen '[.facts[0].identity.occurrences[] | [.start, .end]] == [[49, 63], [86, 88]]' 'a new process returns the same positions'
$V check "$RUN" reopen '.unavailable_sources == []' 'nothing is unavailable after reopen'

$V drive "$RUN" main reconcile -- reconcile
$V check "$RUN" reconcile '.result.facts | length == 1 and .[0].edge_id == "'"$FACT"'"' 'healthy reconcile keeps the fact'
$V check "$RUN" reconcile '.recovery_events == []' 'healthy reconcile records no incident'

$V drive "$RUN" main status -- status
$V check "$RUN" status '.publications | length == 1 and (.[0] | .state == "current" and .revision == 1 and .verified_revision == 1)' 'one current publication at revision 1'
$V check "$RUN" status '.recovery_events == []' 'status shows no incident'
$V cleanup "$RUN"
```

**P2 two-source publication.** Guide: first slice, "Two-source lifecycle fixture" table, row "Both published".

```bash journey P2
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run two-source-publication)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- multi-fixture
$V check "$RUN" fixture '.result.facts | length == 2' 'both documents produce a fact'
$V check "$RUN" fixture '.result.facts | all(.text == "it limits oscillations")' 'both facts are limits oscillations'
$V check "$RUN" fixture '[.result.facts[].evidence[].data_id] | unique | length == 2' 'each fact has evidence from its own document'
$V check "$RUN" fixture '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 1, 1, 1], ["current", 1, 1, 1]]' 'both sources are current at 1/1/1'
$V check "$RUN" fixture '.shared_variant | (.contributions | length) == 2 and (.owners | length) == 2' 'the shared variant edge has 2 contributions and 2 owners'
$V check "$RUN" fixture '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton is present and indexed'
$V check "$RUN" fixture '.sources | all(.[]; .original_marker_present and .original_fact_present and .original_evidence_present and .private_singleton_present and .private_singleton_indexed)' 'each source has markers, fact, evidence and private singleton'
$V check "$RUN" fixture '.recovery_events == []' 'no incident'

FACTS=$(val fixture '[.result.facts[].edge_id] | sort | tojson')
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].edge_id] | sort == '"$FACTS" 'a new process returns the same two facts'
$V check "$RUN" reopen '.unavailable_sources == []' 'nothing is unavailable'

$V drive "$RUN" main rec01 -- reconcile --source doc01
$V check "$RUN" rec01 '(.result.facts | length) == 2 and .recovery_events == []' 'reconcile doc01 keeps both facts'
$V check "$RUN" rec01 '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision]) == [["current", 1, 1], ["current", 1, 1]]' 'reconcile doc01 does not change revisions'
$V drive "$RUN" main rec02 -- reconcile --source doc02
$V check "$RUN" rec02 '(.result.facts | length) == 2 and .recovery_events == []' 'reconcile doc02 keeps both facts'
$V check "$RUN" rec02 '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision]) == [["current", 1, 1], ["current", 1, 1]]' 'reconcile doc02 does not change revisions'

$V drive "$RUN" main status -- status
$V check "$RUN" status '.publications | length == 2 and all(.state == "current" and .revision == 1 and .verified_revision == 1)' 'status shows two current publications'
$V cleanup "$RUN"
```

**P3 chunked publication.** Guide: multichunk, "Run" and the "Initial" column of the table.

```bash journey P3
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run chunked-publication)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fixture -- chunked-fixture
$V check "$RUN" fixture '.result.facts | length == 2' 'both documents produce a fact'
$V check "$RUN" fixture '.sources.doc01.chunk_count == 6 and .sources.doc02.chunk_count == 8' 'doc01 has 6 native chunks and doc02 has 8'
$V check "$RUN" fixture '[.sources.doc01, .sources.doc02] | map([.state, .saved_revision, .verified_revision, .registered_revision]) == [["current", 1, 1, 1], ["current", 1, 1, 1]]' 'both sources are current at 1/1/1'
$V check "$RUN" fixture '[.sources.doc01.chunk_mapping[] | select(.mention_marker_present) | .chunk_index] == [2, 4]' 'doc01 marker chunk indexes are 2 and 4'
$V check "$RUN" fixture '[.sources.doc01.chunk_mapping[] | select(.owns_captured_fact) | .chunk_index] == [4, 5]' 'doc01 fact owner chunk indexes are 4 and 5'
$V check "$RUN" fixture '[.sources.doc01.chunk_mapping[] | select(.evidence_present) | .chunk_index] == [4, 5]' 'doc01 fact evidence chunk indexes are 4 and 5'
$V check "$RUN" fixture '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .identity.occurrences[] | [.start, .end, .text]] == [[49, 63, "the controller"], [90, 92, "it"]]' 'doc01 occurrence positions'
$V check "$RUN" fixture '.sources.doc01.identity_data_id as $d | [.result.facts[] | select(.identity.identity_data_id == $d) | .evidence[].chunk_index] == [4, 5]' 'the doc01 fact returns both evidence chunks'
$V check "$RUN" fixture '.shared_singleton_present and .shared_singleton_indexed' 'the shared singleton is present and indexed'
$V check "$RUN" fixture '.sources | all(.[]; .unresolved_marker_present and .unresolved_entity_present)' 'the unresolved plasma group is present in both sources'
$V check "$RUN" fixture '.recovery_events == []' 'no incident'

FACTS=$(val fixture '[.result.facts[].edge_id] | sort | tojson')
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '[.facts[].edge_id] | sort == '"$FACTS" 'a new process returns the same two facts'
$V check "$RUN" reopen '.unavailable_sources == []' 'nothing is unavailable'

$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '(.result.facts | length) == 2 and .recovery_events == []' 'healthy reconcile keeps both facts'
$V check "$RUN" reconcile '.sources.doc01.chunk_count == 6 and .sources.doc01.saved_revision == 1 and .sources.doc01.verified_revision == 1' 'healthy reconcile keeps doc01 at revision 1 with 6 chunks'
$V cleanup "$RUN"
```

**P4 failed first publication.** Guide: first slice, "Failure visibility and recovery". The CLI exits 1 with `recovery_event_id` in the message. Deliberate injections carry `origin: "test/fault_injection"`. The stages `nodes` and `verification` also exist. The guide gives no expected result for them beyond a refusal, so this map does not drive them.

```bash journey P4
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run failed-first-publication)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }

$V drive "$RUN" main fail -- fixture --fault-stage identity_edges
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'
EID=$(val fail '.message | capture("recovery_event_id=(?<id>[0-9a-f-]+)") | .id')

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '.facts == []' 'no facts from the unfinished source'
$V check "$RUN" withheld '.unavailable_sources | length == 1 and (.[0] | .reason == "publication_failed" and .recovery_event_id == "'"$EID"'")' 'the source is unavailable with the incident id'

$V drive "$RUN" main before -- status
$V check "$RUN" before '.publications | length == 1 and .[0].state == "failed"' 'the publication is failed'
$V check "$RUN" before '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .origin == "test/fault_injection" and .resolved_at == null)' 'one open incident labeled as fault injection'

$V drive "$RUN" main reconcile -- reconcile
$V check "$RUN" reconcile '.result.facts | length == 1' 'reconcile restores the fact'
$V check "$RUN" reconcile '.recovery_events | length == 1 and (.[0] | .recovery_event_id == "'"$EID"'" and .outcome == "restored" and .resolved_at != null and (.recovery_attempts | length) == 1 and .recovery_attempts[0].outcome == "verified")' 'the same incident is resolved by one verified attempt'

$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns the fact and nothing is unavailable'
$V drive "$RUN" main after -- status
$V check "$RUN" after '.publications | length == 1 and .[0].state == "current"' 'the publication is current'
$V cleanup "$RUN"
```

**P5 env profile. This journey calls the embedding API named in `.env` and costs a few API calls.** It runs `chunked-fixture`, `add-occurrences`, `reconcile` and `retrieve` with `--embedding env`. Guide: `docs/SESSION_HANDOFF.md`, "Evidence after the fix". The handoff records the marker `nvidia/nemotron-3-embed-1b` with 2048 dimensions for this `.env`. A different `.env` model makes the marker check fail, and that is a real mismatch to report. The journey prints key names only. It never prints a `.env` value.

```bash journey P5
V=.claude/skills/verify/scripts/verify.py
RUN=$($V new-run env-profile)
val() { jq -r "$2" "$RUN"/evidence/[0-9][0-9]-"$1".json; }
LAB_FILES=$(ls .cognee_data | wc -l)
LAB_DB=$(stat -f %Sm .cognee_system/databases/cognee_db)

$V drive "$RUN" main fixture -- chunked-fixture --embedding env
$V check "$RUN" fixture '.result.facts | length == 2' 'env creation returns both facts'
$V drive "$RUN" main add -- add-occurrences --source doc01 --expected-revision 1
$V check "$RUN" add '.result.facts | length == 3' 'the addition returns three facts'
$V check "$RUN" add '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'doc01 is at 2/2/2'
$V check "$RUN" add '.sources.doc02 | .saved_revision == 1 and .verified_revision == 1' 'doc02 stays at 1/1'
$V check "$RUN" add '.recovery_events == []' 'no incident'
$V drive "$RUN" main reconcile -- reconcile --source doc01
$V check "$RUN" reconcile '(.result.facts | length) == 3 and .recovery_events == []' 'healthy reconcile keeps three facts and no incident'
$V check "$RUN" reconcile '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .registered_revision == 2' 'reconcile keeps doc01 at 2/2/2'
$V drive "$RUN" main reopen -- retrieve
$V check "$RUN" reopen '(.facts | length) == 3 and .unavailable_sources == []' 'a new process returns three facts'

$V doctor "$RUN" > "$RUN/evidence/doctor.json"
jq -e '.ok and .root_embeddings.main == {"profile": "env", "model": "nvidia/nemotron-3-embed-1b", "dimensions": 2048}' "$RUN/evidence/doctor.json" && echo "PASS marker records the env profile"
jq '{ok, warnings, env_embedding_file, env_embedding_keys_set, tokenizer_fix}' "$RUN/evidence/doctor.json"
test -n "$(ls -A "$RUN"/roots/main/data 2>/dev/null)" && echo "PASS raw text is under the root data directory"
uv run python -W ignore - "$RUN/roots/main" <<'EOF'
import sys
from pathlib import Path
import lancedb
from dotenv import dotenv_values

root = Path(sys.argv[1])
db = lancedb.connect(str(root / "vector"))
sizes = {
    name: db.open_table(name).schema.field("vector").type.list_size
    for name in db.table_names()
}
key = (dotenv_values(".env").get("EMBEDDING_API_KEY") or "").encode()
leaked = bool(key) and any(
    key in path.read_bytes() for path in root.rglob("*") if path.is_file()
)
ok = bool(sizes) and set(sizes.values()) == {2048} and not leaked
print(("PASS" if ok else "FAIL"), "vector dimensions", sorted(set(sizes.values())), "api key in root", leaked)
EOF
test "$(ls .cognee_data | wc -l)" = "$LAB_FILES" && echo "PASS lab .cognee_data file count is unchanged" || echo "FAIL lab .cognee_data changed"
test "$(stat -f %Sm .cognee_system/databases/cognee_db)" = "$LAB_DB" && echo "PASS lab cognee_db mtime is unchanged" || echo "FAIL lab cognee_db changed"
$V cleanup "$RUN"
```

## Gotchas

- `fixture`, `multi-fixture` and `chunked-fixture` print Cognee log lines before the JSON. `drive` extracts the JSON. Do not `jq` the raw `.stdout`.
- `fixture` returns `.embedding`. `multi-fixture` and `chunked-fixture` do not. Read their profile from `$V doctor "$RUN"` (`root_embeddings`).
- `status` shows `.publications[].source` as an identity-data UUID, not `doc01`.
- The CLI default is `--embedding env`. `drive` adds `loopback` only when the line passes no `--embedding`. A hand-typed command without the flag calls the embedding API.
- A fixture command refuses an existing root. To repeat a journey, start a new run.
- `P5` fails at the first step if `.env` lacks `EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS`. Creation then leaves no root. `doctor` reports the key names that are missing.
- An unapplied tokenizer fix does not fail `P5`. It makes Cognee fall back to an approximate tokenizer for `env` roots. `doctor` reports this as a warning with `tokenizer_fix: "not applied"`. See `patches/README.md`.
- The loopback profile proves storage and index mechanics. It does not prove embedding quality or search quality.
