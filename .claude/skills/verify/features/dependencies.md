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
$V check "$RUN" first '.sources.doc01.producers.review_r01_r2.configuration.new_digest == .glossary.hc_entry.text_sha256' 'the new fingerprint is the current entry'
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

## Notes

- The review decisions are captured fixture input. They prove the withholding, refresh and re-confirm mechanics, not Describe.
- `drive` exits 1 for an injected failure. That is the expected result; check `.error`. The exception is `refresh_interrupted` on an edit command: the edit completed, so the command exits 0 and reports `refresh_failed`.
- `status` reads the graph and the registered texts like `retrieve`, so it lists every decision retrieval withholds, live drift included (a changed corpus field, a gone foreign chunk, a span stale after a re-add). Such a decision has no row and shows `refresh_needed`, and `reconfirm` answers it. The native test `test_native_readd_after_an_interrupted_refresh_leaves_no_decision_stuck` covers the re-add case; no journey does yet.
- A review refuses with `edit_unfinished` while any document doc01 reads has a pending or failed edit, and `reconfirm` refuses a decision withheld with `input_removed`.
- Every text-change command refreshes moved spans after its edit completes, `edit-text` and the occurrence commands included.
