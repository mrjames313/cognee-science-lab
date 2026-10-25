# Dependencies: a glossary that doc01 read

A user edits a glossary that another source read. doc01's resolution r01 and its HC variant v01 cite the glossary's HC entry as a span. The edit withholds only the decisions that read what changed, and only until they are refreshed. A change elsewhere in the glossary leaves both decisions valid. An insertion before the entry moves the span, and the same command writes doc01's next revision with the new range. A change to the entry withholds both decisions for review; a reviewer re-confirms each, or replaces one. A failed edit withholds every decision citing the glossary until `reconcile` finishes it. An interrupted refresh finishes when it runs again.

Guide: `docs/stage6_identity_dependencies.md`.

## Sub-features

- `glossary-fixture` creates a root with a published glossary (no groups) and doc01 citing its HC entry.
- `edit-elsewhere` leaves the span in place: nothing is withheld and doc01 keeps its revision.
- `edit-moves-span` moves the span: the edit's command refreshes doc01 with the new range and no decision change.
- `edit-needs-review` withholds r01 and v01 with reason `input_changed` and status `refresh_needed`, lists them as unavailable in `retrieve` and in `status`.
- `reconfirm` re-confirms one withheld decision on a new input key under a new producer; the other stays withheld until it is re-confirmed too.
- `replace-decision` replaces the withheld v01 with a new variant v02 for the entry's new meaning.
- `failed-edit` withholds every decision citing the glossary while its edit is failed, then `reconcile` completes the edit and the refresh.
- `interrupted-refresh` leaves doc01 failed when its refresh revision fails; `refresh-dependents` finishes it.
- Glossary roots also take `forget` and `readd` for either source; journey F10 in `source-lifecycle.md` forgets the glossary.

## How to get to it (user POV)

- Run `uv run python -m cognee_lab.identity glossary-fixture --root <new dir>`.
- Run `edit-glossary --root <dir> --source glossary --case elsewhere|insert|cosmetic|substantive --expected-revision N`.
- Run `reconfirm --root <dir> --decision r01|v01 --expected-revision N` or `replace-decision --root <dir> --decision v01 --expected-revision N` for a decision that needs review.
- Add `--fault-stage replace_saved|withhold_dependents|text_removed|text_registered|text_chunks|replace_registered|replace_published|replace_retired|replace_verification` to `edit-glossary` to fail the edit, then run `reconcile --source glossary`.
- Add `--fault-stage refresh_interrupted` to `edit-glossary` to fail doc01's refresh revision after the edit completed, then run `refresh-dependents`.
- Run `retrieve` and `status` against the same root.

## Driving it with verify.py

Preconditions:

- `$V doctor` reports `"ok": true`.
- Each journey uses a new run and a new `glossary-fixture` root.
- The fixture's two sources are current at revision 1 before the first edit.

**D1 a change elsewhere leaves both decisions valid.** Proves `glossary-fixture` and `edit-elsewhere`. Guide: "The glossary fixture" and "A change elsewhere". doc01's span `glossary_hc` is [10, 62). The edit changes the RF entry; the glossary goes to revision 2, the span validates in place, nothing is withheld and doc01 stays at revision 1. The HC query returns the r01 fact before and after.

```bash journey D1
$V drive "$RUN" main fixture -- glossary-fixture
$V check "$RUN" fixture '[.sources.doc01.state, .sources.glossary.state] == ["current", "current"]' 'both sources are current'
$V check "$RUN" fixture '.sources.doc01.glossary_spans.glossary_hc | .start == 10 and .end == 62 and .text_sha256 == "d867939748ac2edeb4521a439cd7ff1d96d4e26bf8cccabb0a49b4bf10b4d66f"' 'doc01 reads the HC entry at [10, 62)'
$V check "$RUN" fixture '.sources.doc01.decisions | .r01.input_refs == ["doc01", "existing_A", "glossary_hc"] and .v01.input_refs == ["doc01", "existing_A", "glossary_hc"]' 'r01 and v01 cite the span'
$V check "$RUN" fixture '.sources.glossary.decisions == {} and .sources.glossary.identity_data_id == "16e89187-1559-5f97-b957-d86f46315407"' 'the glossary declares no decision'
$V check "$RUN" fixture '[.result.facts[].identity.assignment_id] == ["r01"] and .withheld_decisions == [] and .withholdings == []' 'one fact through r01 and nothing withheld'

$V drive "$RUN" main edit -- edit-glossary --source glossary --case elsewhere --expected-revision 1
$V check "$RUN" edit '.sources.glossary | .saved_revision == 2 and .registered_revision == 2 and .verified_revision == 2' 'the glossary is at revision 2'
$V check "$RUN" edit '.sources.doc01 | .saved_revision == 1 and .verified_revision == 1 and .glossary_spans.glossary_hc.start == 10' 'doc01 keeps revision 1 and the span in place'
$V check "$RUN" edit '.glossary.text | contains("RF: radio-frequency heating.")' 'the RF entry changed'
$V check "$RUN" edit '.withholdings == [] and .withheld_decisions == [] and .refreshed == []' 'nothing is withheld or refreshed'
$V check "$RUN" edit '[.result.facts[].identity.assignment_id] == ["r01"] and .result.unavailable_sources == [] and .recovery_events == []' 'the r01 fact is still served'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns the fact'
$V drive "$RUN" main status -- status
$V check "$RUN" status '.withholdings == [] and .withheld_decisions == [] and .refresh_needed == []' 'status lists no withholding'
```

**D2 an insertion moves the span and the refresh writes it.** Proves `edit-moves-span`. Guide: "An insertion before the entry". The ECRH line (44 code points) goes in before the HC entry, so the span's text is found once at [54, 106). The same command writes doc01 revision 2 with that range, the same digest and the same decisions and producers. Nothing stays withheld.

```bash journey D2
$V drive "$RUN" main fixture -- glossary-fixture
$V check "$RUN" fixture '.sources.doc01.glossary_spans.glossary_hc.start == 10' 'the span starts at 10'

$V drive "$RUN" main edit -- edit-glossary --source glossary --case insert --expected-revision 1
$V check "$RUN" edit '.sources.glossary.saved_revision == 2 and .sources.glossary.verified_revision == 2' 'the glossary is at revision 2'
$V check "$RUN" edit '.sources.doc01 | .saved_revision == 2 and .registered_revision == 2 and .verified_revision == 2 and .registered_matches_saved' 'doc01 gained revision 2'
$V check "$RUN" edit '.sources.doc01.glossary_spans.glossary_hc | .start == 54 and .end == 106 and .text_sha256 == "d867939748ac2edeb4521a439cd7ff1d96d4e26bf8cccabb0a49b4bf10b4d66f"' 'the span moved to [54, 106) with its digest'
$V check "$RUN" edit '.glossary.hc_entry | .start == 54 and .end == 106' 'the HC entry is at [54, 106)'
$V check "$RUN" edit '.refreshed | length == 1 and .[0].revision == 2 and .[0].inputs.glossary_hc == {"start": 54, "end": 106}' 'the refresh wrote the new range'
$V check "$RUN" edit '(.sources.doc01.producers | keys) == ["fixture"] and .sources.doc01.decisions.r01.producer_ref == "fixture"' 'no producer or decision changed'
$V check "$RUN" edit '.withholdings == [] and .withheld_decisions == []' 'nothing stays withheld'
$V check "$RUN" edit '[.result.facts[].identity.assignment_id] == ["r01"] and .recovery_events == []' 'the r01 fact is served and no incident'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns the fact'
```

**D3 a cosmetic change needs review, then two re-confirms.** Proves `edit-needs-review` and `reconfirm`. Guide: "A cosmetic change". "plasma heating" becomes "plasma-heating" inside the entry, so the span's text changed. r01 and v01 are withheld with `input_changed` and `refresh_needed`, the old digest is the fixture's, and neither query returns a fact. The first re-confirm gives r01 the new key `glossary_hc_r2` under producer `review_r01_r2` (implementation `re-confirmed`); v01 stays withheld, so the Helios controller query returns the fact and the HC query does not. The second re-confirm gives v01 `glossary_hc_r3`, drops the uncited `glossary_hc`, and releases everything.

```bash journey D3
$V drive "$RUN" main fixture -- glossary-fixture

$V drive "$RUN" main edit -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V check "$RUN" edit '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["r01", "input_changed", "refresh_needed"], ["v01", "input_changed", "refresh_needed"]]' 'r01 and v01 need review'
$V check "$RUN" edit '[.withholdings[] | .old_digest] == ["d867939748ac2edeb4521a439cd7ff1d96d4e26bf8cccabb0a49b4bf10b4d66f", "d867939748ac2edeb4521a439cd7ff1d96d4e26bf8cccabb0a49b4bf10b4d66f"] and all(.withholdings[]; .input_ref == "glossary_hc")' 'each row records the old digest of glossary_hc'
$V check "$RUN" edit '.sources.doc01.saved_revision == 1 and .refreshed == []' 'doc01 waits for review'
$V check "$RUN" edit '.result.facts == [] and .helios.facts == []' 'neither query returns the fact'
$V check "$RUN" edit '[.result.unavailable_sources[] | [.assignment_id, .reason]] == [["r01", "input_changed"], ["v01", "input_changed"]]' 'retrieve lists both decisions as unavailable'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.refresh_needed[].assignment_id] == ["r01", "v01"] and .recovery_events == [] and all(.publications[]; .state == "current")' 'status lists two refresh items and no incident'

$V drive "$RUN" main first -- reconfirm --decision r01 --expected-revision 1
$V check "$RUN" first '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .decisions.r01.input_refs[-1] == "glossary_hc_r2" and .decisions.v01.input_refs[-1] == "glossary_hc"' 'r01 cites the new key and v01 the old one'
$V check "$RUN" first '.sources.doc01.producers.review_r01_r2 | .implementation == "re-confirmed" and .configuration.confirmed_by == "captured fixture reviewer"' 'the re-confirm names its producer and who confirmed'
$V check "$RUN" first '.sources.doc01.producers.review_r01_r2.configuration.new_digests.glossary_hc_r2 == .glossary.hc_entry.text_sha256' 'the new fingerprint is the current entry'
$V check "$RUN" first '[.withheld_decisions[].assignment_id] == ["v01"]' 'only v01 stays withheld'
$V check "$RUN" first '[.helios.facts[].identity.assignment_id] == ["r01"] and .result.facts == []' 'the Helios controller query returns the fact; the HC query does not'

$V drive "$RUN" main second -- reconfirm --decision v01 --expected-revision 2
$V check "$RUN" second '.sources.doc01 | .saved_revision == 3 and (.glossary_spans | keys) == ["glossary_hc_r2", "glossary_hc_r3"]' 'v01 cites glossary_hc_r3 and glossary_hc is dropped'
$V check "$RUN" second '.withholdings == [] and .withheld_decisions == []' 'nothing is withheld'
$V check "$RUN" second '[.result.facts[].identity.assignment_id] == ["r01"] and .recovery_events == []' 'the HC query returns the fact again'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '(.facts | length) == 1 and .unavailable_sources == []' 'a new process returns the fact'
```

**D4 a substantive change: the reviewer replaces v01.** Proves `edit-needs-review` and `replace-decision`. Guide: "A substantive change". HC now means a hybrid coil. The reviewer replaces v01 with v02 (HC to a new "Hybrid coil" Entity) citing the new entry under producer `review_v01_r2` (implementation `replaced`), and re-confirms r01. The HC query then returns no fact, and the Helios controller query returns the r01 fact.

```bash journey D4
$V drive "$RUN" main fixture -- glossary-fixture

$V drive "$RUN" main edit -- edit-glossary --source glossary --case substantive --expected-revision 1
$V check "$RUN" edit '.glossary.hc_entry | .text == "HC: hybrid coil, the auxiliary magnet winding." and .start == 10 and .end == 56' 'the HC entry has a new meaning'
$V check "$RUN" edit '[.withheld_decisions[].assignment_id] == ["r01", "v01"] and all(.withheld_decisions[]; .status == "refresh_needed")' 'both decisions need review'

$V drive "$RUN" main replace -- replace-decision --decision v01 --expected-revision 1
$V check "$RUN" replace '.sources.doc01 | .saved_revision == 2 and (.decisions | keys) == ["r01", "v02"] and .decisions.v02.input_refs == ["doc01", "glossary_hc_r2"]' 'v02 replaces v01 and cites the new entry'
$V check "$RUN" replace '.sources.doc01.producers.review_v01_r2.implementation == "replaced"' 'the replacement names its producer'
$V check "$RUN" replace '[.withheld_decisions[].assignment_id] == ["r01"]' 'r01 still needs review'

$V drive "$RUN" main confirm -- reconfirm --decision r01 --expected-revision 2
$V check "$RUN" confirm '.sources.doc01.saved_revision == 3 and .withholdings == [] and .withheld_decisions == []' 'nothing is withheld'
$V check "$RUN" confirm '.result.facts == [] and [.helios.facts[].identity.assignment_id] == ["r01"]' 'HC no longer reaches the controller fact; the Helios controller query does'
$V check "$RUN" confirm '.recovery_events == []' 'no incident'
```

**D5 a failed edit withholds every citing decision until reconcile.** Proves `failed-edit`. Guide: "A failed edit". The fence lists five stages, before and after the rows are written and before and after the text changes. Each fails the insertion with a recovery event. While the glossary is failed, `retrieve` lists it and both of doc01's decisions as unavailable, and `status` shows both as `edit_unfinished`. `reconcile --source glossary` completes the edit, refreshes doc01 to revision 2 and resolves the incident as `restored`.

```bash journey D5 stages=replace_saved,withhold_dependents,text_removed,text_chunks,replace_published
$V drive "$RUN" main fixture -- glossary-fixture

$V drive "$RUN" main fail -- edit-glossary --source glossary --case insert --expected-revision 1 --fault-stage "$STAGE"
$V check "$RUN" fail '.error == "IntentError" and (.message | test("recovery_event_id=[0-9a-f-]{36}"))' 'the injected failure names a recovery event'

$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '.facts == [] and [.unavailable_sources[] | [.assignment_id, .reason]] == [[null, "publication_failed"], ["r01", "input_changed"], ["v01", "input_changed"]]' 'the glossary and both citing decisions are unavailable'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.withheld_decisions[] | [.assignment_id, .status]] == [["r01", "edit_unfinished"], ["v01", "edit_unfinished"]]' 'both decisions wait for the edit'
$V check "$RUN" status '.recovery_events | length == 1 and .[0].resolved_at == null and .[0].origin == "test/fault_injection"' 'one open incident'

$V drive "$RUN" main rec -- reconcile --source glossary
$V check "$RUN" rec '.sources.glossary | .state == "current" and .saved_revision == 2 and .verified_revision == 2' 'the edit completes'
$V check "$RUN" rec '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .glossary_spans.glossary_hc.start == 54' 'doc01 is refreshed with the moved span'
$V check "$RUN" rec '.withholdings == [] and .withheld_decisions == []' 'nothing stays withheld'
$V check "$RUN" rec '[.result.facts[].identity.assignment_id] == ["r01"] and .result.unavailable_sources == []' 'the fact is served'
$V check "$RUN" rec '.recovery_events | length == 1 and .[0].outcome == "restored" and .[0].resolved_at != null' 'the incident is restored'
```

**D6 an interrupted refresh finishes when it runs again.** Proves `interrupted-refresh`. Guide: "An interrupted refresh". The glossary edit completes, then doc01's refresh revision fails at `replace_registered`. The command exits 0: it reports the completed edit and, beside it, `refresh_failed`. doc01 is failed and unavailable as a whole source, and the two `remap` rows keep the new range. `refresh-dependents` resumes doc01's saved revision 2, which releases both decisions and resolves the incident as `restored`.

```bash journey D6
$V drive "$RUN" main fixture -- glossary-fixture

$V drive "$RUN" main fail -- edit-glossary --source glossary --case insert --expected-revision 1 --fault-stage refresh_interrupted
$V check "$RUN" fail '.sources.glossary | .state == "current" and .verified_revision == 2' 'the glossary edit completes'
$V check "$RUN" fail '.refreshed == [] and (.refresh_failed.message | contains("Injected failure at replace_registered"))' 'the refresh failure is reported beside the edit'

$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.revision, .state]] | sort == [[2, "current"], [2, "failed"]]' 'the glossary is current at 2 and doc01 failed at 2'
$V check "$RUN" status '[.withholdings[] | [.assignment, .status, .new_start, .new_end]] == [["r01", "remap", 54, 106], ["v01", "remap", 54, 106]]' 'two remap rows hold the new range'
$V drive "$RUN" main withheld -- retrieve
$V check "$RUN" withheld '.facts == [] and [.unavailable_sources[] | [.assignment_id, .reason]] == [[null, "publication_failed"]]' 'doc01 is unavailable as a whole source'

$V drive "$RUN" main refresh -- refresh-dependents
$V check "$RUN" refresh '.sources.doc01 | .state == "current" and .saved_revision == 2 and .verified_revision == 2 and .glossary_spans.glossary_hc.start == 54' 'doc01 revision 2 completes'
$V check "$RUN" refresh '.withholdings == [] and [.result.facts[].identity.assignment_id] == ["r01"]' 'nothing is withheld and the fact is served'
$V check "$RUN" refresh '.recovery_events | length == 1 and .[0].outcome == "restored"' 'the incident is restored'
```

## Chains: doc03 cites doc01's decisions

`glossary-fixture --chain` adds doc03 to the root. Its resolution c01 cites doc01's r01 and its HC variant c02 cites doc01's v01, each as a saved record pinned by its fingerprint. Guide: `docs/stage6_identity_chains.md`.

- `chain-hold`: an edit that withholds r01 and v01 withholds c01 and c02 down the chain, with `input_changed` and the derived status `upstream_withheld`; no reviewer answers them.
- `upstream-reconfirm`: re-confirming r01 and v01 keeps their fingerprints, so c01 and c02 are released with no doc03 revision.
- `key-replacement`: replacing v01 by v02 removes the record c02 cites, so c02 shows `input_removed` and cannot be re-confirmed.
- `in-place-replacement`: `replace-decision --decision r01` leaves g01 unresolved in place, so c01's record changed and doc03's reviewer re-confirms c01 on it.
- `admission-refusals`: `cite-record` tries a cycle, a self-citation, a missing record, a stale revision and a wrong fingerprint, and each is refused before anything is written.
- `chain-erasure`: a forget of the glossary cascades to doc03 at level 2 (journeys F16 to F19 in `source-lifecycle.md`); a forget of doc01 removes doc03's direct citations.
- `upstream-unfinished`: a failed revision of doc01 withholds c01 and c02 with `edit_unfinished`, and doc03's review waits for `reconcile`.

Run `reconfirm` and `replace-decision` with `--source doc03` for doc03's decisions, and `cite-record --source doc01|doc03 --citation cycle|self|missing|stale|digest --expected-revision N` for the refused citations. `cycle` cites from doc01; the others cite from doc03.

**D7 an edit withholds down the chain.** Proves `chain-hold`. Guide: "The chain fixture" and "Withholding down a chain". The cosmetic edit withholds r01 and v01 for review, and c01 and c02 with `upstream_withheld`. `retrieve` lists all four, `refresh_needed` lists only doc01's two, and doc03's re-confirm of c01 is refused because c01 waits for r01.

```bash journey D7
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V check "$RUN" fixture '.sources | [.doc01.state, .glossary.state, .doc03.state] == ["current", "current", "current"]' 'three sources are current'
$V check "$RUN" fixture '.sources.doc03.identity_data_id == "bbbc442e-0647-552e-bb54-071604d213fa" and .sources.doc03.saved_revision == 1' 'doc03 is published at revision 1'
$V check "$RUN" fixture '.sources.doc03.decisions | .c01.input_refs == ["doc03", "doc01_r01"] and .c02.input_refs == ["doc03", "doc01_v01"]' 'c01 and c02 cite doc01 records'
$V check "$RUN" fixture '.sources.doc03.records | .doc01_r01.record_type == "mention_resolution" and .doc01_r01.record_id == "r01" and .doc01_r01.representation_revision == 1 and .doc01_v01.record_type == "variant_assignment" and .doc01_v01.record_id == "v01"' 'each citation names its record type, key and revision'
$V check "$RUN" fixture '.withheld_decisions == [] and [.result.facts[].identity.assignment_id] == ["r01"]' 'nothing is withheld'

$V drive "$RUN" main edit -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V check "$RUN" edit '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["r01", "input_changed", "refresh_needed"], ["v01", "input_changed", "refresh_needed"], ["c01", "input_changed", "upstream_withheld"], ["c02", "input_changed", "upstream_withheld"]]' 'the edit withholds both levels'
$V check "$RUN" edit '[.withheld_decisions[] | select(.assignment_id == "c01" or .assignment_id == "c02") | .input_refs] == [["doc01_r01"], ["doc01_v01"]]' 'c01 and c02 are held by their citations'
$V check "$RUN" edit '[.refresh_needed[].assignment_id] == ["r01", "v01"]' 'only doc01 decisions await a reviewer'
$V check "$RUN" edit '.withholdings | length == 2' 'only the two doc01 rows are written'
$V check "$RUN" edit '.sources.doc03 | .saved_revision == 1 and .verified_revision == 1' 'doc03 is not revised'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '[.unavailable_sources[] | [.assignment_id, .reason]] == [["r01", "input_changed"], ["v01", "input_changed"], ["c01", "input_changed"], ["c02", "input_changed"]]' 'a new process withholds the same four decisions'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.withheld_decisions[] | .status] == ["refresh_needed", "refresh_needed", "upstream_withheld", "upstream_withheld"]' 'status agrees with retrieval'

$V drive "$RUN" main refused -- reconfirm --source doc03 --decision c01 --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | contains("waits for a record it cites"))' 'c01 cannot be re-confirmed while r01 is withheld'
```

**D8 an upstream re-confirm releases the chain with no doc03 revision.** Proves `upstream-reconfirm`. Guide: "What a citation pins". Re-confirming r01 releases c01, and re-confirming v01 releases c02. doc03 stays at revision 1 with its revision-1 citations.

```bash journey D8
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main edit -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V check "$RUN" edit '.withheld_decisions | length == 4' 'four decisions are withheld'

$V drive "$RUN" main r01 -- reconfirm --source doc01 --decision r01 --expected-revision 1
$V check "$RUN" r01 '[.withheld_decisions[] | [.assignment_id, .status]] == [["v01", "refresh_needed"], ["c02", "upstream_withheld"]]' 're-confirming r01 releases r01 and c01'

$V drive "$RUN" main v01 -- reconfirm --source doc01 --decision v01 --expected-revision 2
$V check "$RUN" v01 '.withheld_decisions == [] and .withholdings == []' 'nothing is withheld'
$V check "$RUN" v01 '.sources.doc01 | .saved_revision == 3 and .verified_revision == 3' 'doc01 is at revision 3'
$V check "$RUN" v01 '.sources.doc03 | .saved_revision == 1 and .verified_revision == 1 and .records.doc01_r01.representation_revision == 1' 'doc03 keeps revision 1 and its citations'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '.unavailable_sources == [] and [.facts[].identity.assignment_id] == ["r01"]' 'a new process serves everything'
```

**D9 a replacement under a new key removes the cited record.** Proves `key-replacement`. Guide: "Replacements upstream". The substantive edit withholds both levels. Replacing v01 by v02 takes v01 out of doc01, so c02 shows `input_removed` and needs review, and doc03's re-confirm of c02 is refused. Re-confirming r01 releases c01.

```bash journey D9
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main edit -- edit-glossary --source glossary --case substantive --expected-revision 1
$V check "$RUN" edit '[.withheld_decisions[] | .status] == ["refresh_needed", "refresh_needed", "upstream_withheld", "upstream_withheld"]' 'both levels are withheld'

$V drive "$RUN" main replace -- replace-decision --source doc01 --decision v01 --expected-revision 1
$V check "$RUN" replace '.sources.doc01.decisions | has("v02") and (has("v01") | not)' 'doc01 replaced v01 by v02'
$V check "$RUN" replace '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["r01", "input_changed", "refresh_needed"], ["c01", "input_changed", "upstream_withheld"], ["c02", "input_removed", "refresh_needed"]]' 'c02 cites a record that is gone'

$V drive "$RUN" main refused -- reconfirm --source doc03 --decision c02 --expected-revision 1
$V check "$RUN" refused '.error == "IntentError" and (.message | contains("never re-confirmed"))' 'a removed record is never re-confirmed'

$V drive "$RUN" main r01 -- reconfirm --source doc01 --decision r01 --expected-revision 2
$V check "$RUN" r01 '[.withheld_decisions[] | [.assignment_id, .reason]] == [["c02", "input_removed"]]' 're-confirming r01 releases c01; c02 stays withheld'
$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '[.unavailable_sources[] | [.assignment_id, .reason]] == [["c02", "input_removed"]]' 'a new process withholds only c02'
```

**D10 an in-place replacement upstream needs doc03's own review.** Proves `in-place-replacement`. Guide: "Replacements upstream". `replace-decision --decision r01` leaves g01 unresolved under the same key, which changes r01's fingerprint: c01 needs review, with `input_changed`. After v01's re-confirm releases c02, doc03's re-confirm cites r01 as it is now under a new key and producer, and nothing is withheld.

```bash journey D10
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main edit -- edit-glossary --source glossary --case cosmetic --expected-revision 1

$V drive "$RUN" main replace -- replace-decision --source doc01 --decision r01 --expected-revision 1
$V check "$RUN" replace '.sources.doc01.decisions.r01 | .status == "unresolved" and .input_refs == ["doc01", "existing_A", "glossary_hc_r2"] and .producer_ref == "review_r01_r2"' 'r01 is unresolved in place'
$V check "$RUN" replace '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["v01", "input_changed", "refresh_needed"], ["c01", "input_changed", "refresh_needed"], ["c02", "input_changed", "upstream_withheld"]]' 'c01 needs review of the changed record'

$V drive "$RUN" main v01 -- reconfirm --source doc01 --decision v01 --expected-revision 2
$V check "$RUN" v01 '[.withheld_decisions[] | .assignment_id] == ["c01"]' 'only c01 is withheld'

$V drive "$RUN" main c01 -- reconfirm --source doc03 --decision c01 --expected-revision 1
$V check "$RUN" c01 '.sources.doc03 | .saved_revision == 2 and .verified_revision == 2 and .decisions.c01.input_refs == ["doc03", "doc01_r01_r2"] and .decisions.c01.producer_ref == "review_c01_r2"' 'doc03 re-confirmed c01 on a new citation'
$V check "$RUN" c01 '.sources.doc03.records | .doc01_r01_r2.representation_revision == 3 and (has("doc01_r01") | not)' 'the citation pins doc01 revision 3 and the old one is dropped'
$V check "$RUN" c01 '.sources.doc03.producers.review_c01_r2 | .implementation == "re-confirmed" and (.configuration.new_digests.doc01_r01_r2 | length == 64)' 'the producer records the new fingerprint'
$V check "$RUN" c01 '.withheld_decisions == [] and .recovery_events == []' 'nothing is withheld'
$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '.unavailable_sources == []' 'a new process serves everything'
```

**D11 refused citations, the erasure of a cited source and an unfinished upstream.** Proves `admission-refusals`, `chain-erasure` and `upstream-unfinished`. Guide: "Admission of a citation", "Forget of a cited source" and "An unfinished upstream". Each refused citation leaves every source at revision 1. The glossary's dry run lists doc03 at level 2, since its removal would unresolve r01 and drop v01, which doc03 cites. doc01's dry run lists doc03 as a dependent whose c01 becomes unresolved and c02 goes, and the confirmed forget writes doc03 revision 2. On a second root a failed doc01 re-confirm withholds c01 and c02 with `edit_unfinished`, doc03's review waits, and `reconcile` releases c01.

```bash journey D11
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main cycle -- cite-record --source doc01 --citation cycle --expected-revision 1
$V check "$RUN" cycle '.message | contains("leads back here")' 'a citation that closes a cycle is refused'
$V drive "$RUN" main self -- cite-record --source doc03 --citation self --expected-revision 1
$V check "$RUN" self '.message | contains("does not cite its own saved records")' 'a self-citation is refused'
$V drive "$RUN" main missing -- cite-record --source doc03 --citation missing --expected-revision 1
$V check "$RUN" missing '.message | contains("No such saved record")' 'a missing record is refused'
$V drive "$RUN" main stale -- cite-record --source doc03 --citation stale --expected-revision 1
$V check "$RUN" stale '.message | contains("current revision")' 'a stale revision is refused'
$V drive "$RUN" main digest -- cite-record --source doc03 --citation digest --expected-revision 1
$V check "$RUN" digest '.message | contains("fingerprint differs")' 'a wrong fingerprint is refused'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | [.revision, .state]] == [[1, "current"], [1, "current"], [1, "current"]] and .recovery_events == []' 'nothing was written'

$V drive "$RUN" main gloss -- forget --source glossary --expected-revision 1 --dry-run
$V check "$RUN" gloss '[.levels[] | .level] == [1, 2] and [.dependents[1].cited_records[] | .record_id] == ["r01", "v01"]' 'the glossary forget cascades to doc03 for r01 and v01'
$V drive "$RUN" main dry -- forget --source doc01 --expected-revision 1 --dry-run
$V check "$RUN" dry '[.dependents[] | .identity_data_id] == ["bbbc442e-0647-552e-bb54-071604d213fa"]' 'doc03 is the one dependent'
$V check "$RUN" dry '[.dependents[0].decisions[] | [.assignment, .outcome, .citing[0].kind]] == [["c01", "unresolved", "saved_record"], ["c02", "dropped", "saved_record"]]' 'c01 becomes unresolved and c02 goes'
TOKEN=$(val dry '.token')
$V drive "$RUN" main forget -- forget --source doc01 --expected-revision 1 --confirm "$TOKEN"
$V check "$RUN" forget '.sources.doc01.state == "forgotten" and .dependents_failed == null' 'doc01 is forgotten'
$V check "$RUN" forget '.sources.doc03 | .saved_revision == 2 and .verified_revision == 2 and .decisions.c01.status == "unresolved" and (.decisions | has("c02") | not) and .records == {}' 'doc03 revision 2 removes its citations'

$V drive "$RUN" fault fixture2 -- glossary-fixture --chain
$V drive "$RUN" fault edit2 -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V drive "$RUN" fault fail -- reconfirm --source doc01 --decision r01 --expected-revision 1 --fault-stage replace_registered
$V check "$RUN" fail '.message | contains("Injected failure at replace_registered")' 'the doc01 re-confirm fails'
$V drive "$RUN" fault status2 -- status
$V check "$RUN" status2 '[.withheld_decisions[] | select(.assignment_id == "c01" or .assignment_id == "c02") | .status] == ["edit_unfinished", "edit_unfinished"]' 'c01 and c02 wait for the unfinished doc01'
$V drive "$RUN" fault waits -- reconfirm --source doc03 --decision c01 --expected-revision 1
$V check "$RUN" waits '.message | contains("whose records this source cites")' 'doc03 review waits for doc01'
$V drive "$RUN" fault done -- reconcile --source doc01
$V check "$RUN" done '[.withheld_decisions[] | [.assignment_id, .status]] == [["v01", "refresh_needed"], ["c02", "upstream_withheld"]] and (.recovery_events | length == 1 and .[0].outcome == "restored")' 'reconcile releases r01 and c01'
```

### Entity edits and removed citations (checkpoint K)

Guide: `docs/stage6_identity_entity_edits.md`.

- `entity-edit`: `edit-entity --case description` changes a field doc01's `existing_A` selects, through Cognee's own `update_node`, with no ledger row. r01 and v01 are withheld with `input_changed` and `refresh_needed`, c01 and c02 with `upstream_withheld`. `unselected` withholds nothing and `revert` releases everything with no revision.
- `corpus-review`: `reconfirm` cites the Entity as it reads now under `existing_A_r<rev>`; `replace-decision --decision r01` leaves g01 unresolved on it; v01 has no captured replacement for an Entity edit.
- `mixed-review`: one re-confirm answers a decision withheld by the glossary span and the Entity together.
- `replace-citation`: `--cite doc01:v02` re-cites doc03's c02 on v02 under a new key and producer; `--drop` removes c02.
- `entity-delete` (step 5 S2): `edit-entity --case delete` deletes the Entity doc01 reads through `graph.delete_node`, with no ledger row. A kept, withheld decision may keep citing it while a neighbour is replaced, and no publication recreates it (`entity_recreation` for a changed decision that names it).

**D12 an outside Entity edit withholds its readers down the chain until it is reverted.** Proves `entity-edit`. Guide: "The edit". `unselected` leaves every digest as pinned. `description` changes the selected digest, withholds both levels and writes no row, revision or incident; `retrieve` in a new process agrees. `revert` brings the digest back and releases everything at revision 1, with the fact served again.

```bash journey D12
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main unselected -- edit-entity --case unselected
$V check "$RUN" unselected '.entity_edit | .before_sha256 == .pinned_sha256 and .after_sha256 == .pinned_sha256 and .fields == ["lab_note"]' 'an unselected field leaves the selected digest as pinned'
$V check "$RUN" unselected '.withheld_decisions == []' 'nothing is withheld'

$V drive "$RUN" main edit -- edit-entity --case description
$V check "$RUN" edit '.entity_edit | .before_sha256 == .pinned_sha256 and .after_sha256 != .pinned_sha256 and .input_ref == "existing_A"' 'the selected digest changed'
$V check "$RUN" edit '[.withheld_decisions[] | [.assignment_id, .reason, .status, .input_refs]] == [["r01", "input_changed", "refresh_needed", ["existing_A"]], ["v01", "input_changed", "refresh_needed", ["existing_A"]], ["c01", "input_changed", "upstream_withheld", ["doc01_r01"]], ["c02", "input_changed", "upstream_withheld", ["doc01_v01"]]]' 'both levels are withheld for the Entity input'
$V check "$RUN" edit '.withholdings == [] and .recovery_events == [] and ([.sources[] | [.state, .saved_revision]] | unique) == [["current", 1]]' 'no row, no revision and no incident'

$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '.facts == [] and [.unavailable_sources[] | [.assignment_id, .reason]] == [["r01", "input_changed"], ["v01", "input_changed"], ["c01", "input_changed"], ["c02", "input_changed"]]' 'a new process withholds the same four decisions'

$V drive "$RUN" main revert -- edit-entity --case revert
$V check "$RUN" revert '.entity_edit.after_sha256 == .entity_edit.pinned_sha256 and .withheld_decisions == []' 'the revert releases everything'
$V check "$RUN" revert '.sources.doc01.saved_revision == 1 and [.result.facts[].identity.assignment_id] == ["r01"]' 'no revision, and the fact is served again'
```

**D13 re-confirms on the Entity as it reads now.** Proves `corpus-review`. Guide: "Re-confirm". r01's re-confirm cites `existing_A_r2`, whose digest is the edit's after digest, and releases c01 with no doc03 revision. v01's re-confirm releases the rest and drops the uncited `existing_A`.

```bash journey D13
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main edit -- edit-entity --case description
AFTER=$(val edit '.entity_edit.after_sha256')

$V drive "$RUN" main r01 -- reconfirm --source doc01 --decision r01 --expected-revision 1
$V check "$RUN" r01 '.sources.doc01.decisions.r01.input_refs == ["doc01", "existing_A_r2", "glossary_hc"] and .sources.doc01.decisions.r01.producer_ref == "review_r01_r2"' 'r01 cites the Entity under a new key'
$V check "$RUN" r01 ".sources.doc01.producers.review_r01_r2.configuration | .new_digests.existing_A_r2 == \"$AFTER\" and .old_digests.existing_A != \"$AFTER\"" 'the new digest is the edited Entity'
$V check "$RUN" r01 '[.withheld_decisions[] | [.assignment_id, .status]] == [["v01", "refresh_needed"], ["c02", "upstream_withheld"]] and .sources.doc03.saved_revision == 1' 'r01 and c01 are released with no doc03 revision'

$V drive "$RUN" main v01 -- reconfirm --source doc01 --decision v01 --expected-revision 2
$V check "$RUN" v01 '.sources.doc01.decisions.v01.input_refs == ["doc01", "existing_A_r3", "glossary_hc"] and .withheld_decisions == []' 'v01 is re-confirmed and nothing is withheld'
$V check "$RUN" v01 '.sources.doc01 | .saved_revision == 3 and .verified_revision == 3' 'doc01 is at revision 3'
$V drive "$RUN" main after -- retrieve
$V check "$RUN" after '.unavailable_sources == [] and [.facts[].identity.assignment_id] == ["r01"]' 'a new process serves everything'
```

**D14 an Entity edit answered by an in-place replacement.** Proves `corpus-review`. Guide: "Replace". `replace-decision --decision r01` leaves g01 unresolved on the Entity as it reads now, which changes r01's fingerprint, so c01 needs doc03's own review, which releases it. v01 has no captured replacement for an Entity edit.

```bash journey D14
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main edit -- edit-entity --case description

$V drive "$RUN" main replace -- replace-decision --source doc01 --decision r01 --expected-revision 1
$V check "$RUN" replace '.sources.doc01.decisions.r01 | .status == "unresolved" and .input_refs == ["doc01", "existing_A_r2", "glossary_hc"] and .producer_ref == "review_r01_r2"' 'r01 is unresolved on the Entity as it reads now'
$V check "$RUN" replace '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["v01", "input_changed", "refresh_needed"], ["c01", "input_changed", "refresh_needed"], ["c02", "input_changed", "upstream_withheld"]]' 'c01 needs its own review'

$V drive "$RUN" main v01 -- replace-decision --source doc01 --decision v01 --expected-revision 2
$V check "$RUN" v01 '.error == "IntentError" and (.message | contains("Only v01 withheld by the glossary span"))' 'v01 has no captured replacement for an Entity edit'

$V drive "$RUN" main c01 -- reconfirm --source doc03 --decision c01 --expected-revision 1
$V check "$RUN" c01 '.sources.doc03.decisions.c01.input_refs == ["doc03", "doc01_r01_r2"] and [.withheld_decisions[] | .assignment_id] == ["v01", "c02"]' 'doc03 re-confirms c01 on r01 as it is now'
```

**D15 one re-confirm answers the glossary span and the Entity together.** Proves `mixed-review`. Guide: "Re-confirm". The cosmetic glossary edit and the Entity edit both withhold r01 and v01. One re-confirm of r01 cites both inputs as they are now in revision 2.

```bash journey D15
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main gloss -- edit-glossary --source glossary --case cosmetic --expected-revision 1
$V drive "$RUN" main edit -- edit-entity --case description
$V check "$RUN" edit '[.withheld_decisions[] | select(.assignment_id == "r01") | .input_refs] == [["existing_A", "glossary_hc"]]' 'r01 is withheld by both inputs'

$V drive "$RUN" main r01 -- reconfirm --source doc01 --decision r01 --expected-revision 1
$V check "$RUN" r01 '.sources.doc01.decisions.r01.input_refs == ["doc01", "existing_A_r2", "glossary_hc_r2"]' 'one revision cites both inputs as they are now'
$V check "$RUN" r01 '.sources.doc01.producers.review_r01_r2.configuration | (.old_digests | keys) == ["existing_A", "glossary_hc"] and (.new_digests | keys) == ["existing_A_r2", "glossary_hc_r2"]' 'the producer records both digests'
$V check "$RUN" r01 '[.withheld_decisions[] | [.assignment_id, .status]] == [["v01", "refresh_needed"], ["c02", "upstream_withheld"]]' 'r01 and c01 are released'
```

**D16 replace-citation answers a removed citation.** Proves `replace-citation`. Guide: "Replace a citation". After D9's replacement of v01 by v02, `reconfirm` of c02 is refused and names `replace-citation`, and `replace-decision` is refused too. `replace-citation --cite doc01:v02` re-cites c02 on v02 as it is now under `doc01_v02_r2`, with a producer new in the revision, and releases c02. On a second root `--drop` removes c02.

```bash journey D16
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main edit -- edit-glossary --source glossary --case substantive --expected-revision 1
$V drive "$RUN" main replace -- replace-decision --source doc01 --decision v01 --expected-revision 1
$V drive "$RUN" main refused -- reconfirm --source doc03 --decision c02 --expected-revision 1
$V check "$RUN" refused '.message | contains("never re-confirmed") and contains("replace-citation")' 'the refusal names replace-citation'
$V drive "$RUN" main decision -- replace-decision --source doc03 --decision c02 --expected-revision 1
$V check "$RUN" decision '.message | contains("replaced with replace-citation")' 'replace-decision points to replace-citation'

$V drive "$RUN" main cite -- replace-citation --source doc03 --decision c02 --cite doc01:v02 --expected-revision 1
$V check "$RUN" cite '.sources.doc03 | .saved_revision == 2 and .verified_revision == 2 and .decisions.c02.input_refs == ["doc03", "doc01_v02_r2"] and .decisions.c02.producer_ref == "review_c02_r2"' 'c02 cites v02 under a new key'
$V check "$RUN" cite '.sources.doc03 | .records.doc01_v02_r2.representation_revision == 2 and (.records | has("doc01_v01") | not) and .producers.review_c02_r2.implementation == "replaced"' 'the citation pins doc01 revision 2 under a replaced producer'
$V check "$RUN" cite '[.withheld_decisions[] | [.assignment_id, .status]] == [["r01", "refresh_needed"], ["c01", "upstream_withheld"]] and .recovery_events == []' 'c02 is released'

$V drive "$RUN" drop fixture2 -- glossary-fixture --chain
$V drive "$RUN" drop edit2 -- edit-glossary --source glossary --case substantive --expected-revision 1
$V drive "$RUN" drop replace2 -- replace-decision --source doc01 --decision v01 --expected-revision 1
$V drive "$RUN" drop dropped -- replace-citation --source doc03 --decision c02 --drop --expected-revision 1
$V check "$RUN" dropped '.sources.doc03 | .saved_revision == 2 and (.decisions | keys) == ["c01"] and (.records | keys) == ["doc01_r01"]' 'c02 and its citation are gone'
$V check "$RUN" dropped '[.withheld_decisions[] | .assignment_id] == ["r01", "c01"]' 'only the r01 chain is withheld'
```

**D17 an Entity deleted outside the lab is answered one decision at a time.** Proves `entity-delete`. Guide: entity edits, "Outside deletion". `edit-entity --case delete` deletes the Helios controller (`8b4bff50-...`) through `graph.delete_node` and writes no row, revision or incident; its `Entity_name` point stays. r01 and v01 are withheld `input_removed`, and c01 and c02 `upstream_withheld` (reason `input_changed`, as for any upstream). `reconfirm` of r01 is refused. `replace-decision --decision r01` leaves g01 unresolved without `existing_A` at revision 2, while v01, kept, still cites it and stays withheld and c01 needs doc03's own review, as in D14; Helios stays absent, so a second delete is refused. `replace-decision --decision v01` drops the variant and the Helios recipe at revision 3, and no description cites `existing_A`; doc03 is left with its own review of c01 and c02 (`replace-citation`). A retrieve for "Helios controller" never reaches Helios through its orphaned name point.

```bash journey D17
$V drive "$RUN" main fixture -- glossary-fixture --chain
$V drive "$RUN" main del -- edit-entity --case delete
$V check "$RUN" del '.entity_edit | .case == "delete" and .entity_id == "8b4bff50-907b-56b6-bc80-3b0a7018714a" and .input_ref == "existing_A" and .node_present == false and .name_point_present == true' 'the Entity is gone and its name point stays'
$V check "$RUN" del '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["r01", "input_removed", "refresh_needed"], ["v01", "input_removed", "refresh_needed"], ["c01", "input_changed", "upstream_withheld"], ["c02", "input_changed", "upstream_withheld"]]' 'both levels are withheld for the removed Entity'
$V check "$RUN" del '.withholdings == [] and .recovery_events == [] and ([.sources[] | [.state, .saved_revision]] | unique) == [["current", 1]]' 'no row, no revision and no incident'

$V drive "$RUN" main reconfirm -- reconfirm --source doc01 --decision r01 --expected-revision 1
$V check "$RUN" reconfirm '.error == "IntentError" and (.message | startswith("A removed input is never re-confirmed"))' 'a removed input is never re-confirmed'

$V drive "$RUN" main r01 -- replace-decision --source doc01 --decision r01 --expected-revision 1
$V check "$RUN" r01 '.sources.doc01 | .saved_revision == 2 and .verified_revision == 2 and .decisions.r01.status == "unresolved" and (.decisions.r01.input_refs | index("existing_A") == null) and (.decisions.v01.input_refs | index("existing_A") != null)' 'r01 is unresolved without the input; v01 still cites it'
$V check "$RUN" r01 '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["v01", "input_removed", "refresh_needed"], ["c01", "input_changed", "refresh_needed"], ["c02", "input_changed", "upstream_withheld"]] and .recovery_events == []' 'v01 stays withheld, c01 needs its own review and no incident is open'
$V drive "$RUN" main again -- edit-entity --case delete
$V check "$RUN" again '.error == "IntentError" and .message == "No such Entity: 8b4bff50-907b-56b6-bc80-3b0a7018714a"' 'the replacement did not recreate Helios'

$V drive "$RUN" main v01 -- replace-decision --source doc01 --decision v01 --expected-revision 2
$V check "$RUN" v01 '.sources.doc01 | .saved_revision == 3 and .verified_revision == 3 and (.decisions | has("v01") | not)' 'v01 is dropped at revision 3'
$V drive "$RUN" main status -- status
$V check "$RUN" status '[.publications[] | .description | fromjson | select(.revision == 3) | [(.entity_constructions | has("8b4bff50-907b-56b6-bc80-3b0a7018714a")), (.inputs | has("existing_A"))]] == [[false, false]]' 'the Helios recipe and the input are gone'
$V check "$RUN" status '[.withheld_decisions[] | [.assignment_id, .reason, .status]] == [["c01", "input_changed", "refresh_needed"], ["c02", "input_removed", "refresh_needed"]] and .recovery_events == []' 'only doc03 waits for its own review'

$V drive "$RUN" main ask -- retrieve --query "Helios controller"
$V check "$RUN" ask '(.facts | tojson | contains("8b4bff50-907b-56b6-bc80-3b0a7018714a")) | not' 'the orphaned name point seeds nothing'
```

## Notes

- The review decisions are captured fixture input. They prove the withholding, refresh and re-confirm mechanics, not Describe.
- `drive` exits 1 for an injected failure. That is the expected result; check `.error`. The exception is `refresh_interrupted` on an edit command: the edit completed, so the command exits 0 and reports `refresh_failed`.
- `status` reads the graph and the registered texts like `retrieve`, so it lists every decision retrieval withholds, live drift included (a changed corpus field, a gone foreign chunk, a span stale after a re-add). Such a decision has no row and shows `refresh_needed`, and `reconfirm` answers it. The native test `test_native_readd_after_an_interrupted_refresh_leaves_no_decision_stuck` covers the re-add case; no journey does yet.
- A review refuses with `edit_unfinished` while any document the reviewed source reads has a pending or failed edit, or any source whose records it cites has a pending or failed attempt. `reconfirm` refuses a decision withheld with `input_removed`, and every review refuses one withheld with `upstream_withheld`.
- The CLI prints a refusal's message, not its code, so the chain journeys check the message. The unit tests in `tests/test_identity_chains.py` check the codes.
- Every text-change command refreshes moved spans after its edit completes, `edit-text` and the occurrence commands included.
