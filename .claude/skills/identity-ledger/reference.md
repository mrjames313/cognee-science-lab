# Identity ledger check: reference

Read [SKILL.md](SKILL.md) first. This file holds the detail behind it. It gives the harm and code for each property, the step list and the modeling choices. It also records measurements, scratch breaks, the skill proof and findings.

## Properties: harm and code

All functions are in `src/cognee_lab/identity/storage.py` unless the entry names another file.

- **P1. Withheld until complete.** Harm: retrieval serves facts from a pending, failed or half-written publication. Code: `begin` sets `pending`. `fail` sets `failed`. Only `complete` sets `verified_revision`, and only for the pending attempt at its revision. `valid_sources` in retrieve.py serves a row only when it is `current` at `verified_revision`. `PublicationRow.of` refuses a row that is not forgotten whose description does not parse as an identity description (`description_format`), which the checker reports as P1: such a row could never be served with the description its attempt began.
- **P2. Independent sources.** Harm: a failure or recovery on one source withholds, resolves or corrupts another source. Code: every row and event query in `begin`, `fail` and `complete` filters on dataset and source.
- **P3. Stale calls are refused.** Harm: a writer that works from an old read overwrites newer intent. Or a late acknowledgement marks the wrong attempt or description as verified. Code: the `stale_revision` guard in `begin`, the attempt check in `fail`, the attempt and `pending` filter in `complete`, and the description check in `assert_pending`. A guard raises before the commit, so the session rolls back.
- **P4. One writer at a time.** Harm: two writers interleave graph writes for overlapping intents. Code: `begin` takes the `Writer` row only when it has no owner. `fail` and `complete` release it only for their own attempt.
- **P5. Recovery is explicit and forward.** Harm: an operator loses track of an incident, sees two incidents for one failure, or sees the record of a resolved incident change. Or a method that does not own the saved intent rolls it back, replaces it or drops its retirement plan. One exception: since 2026-10-26 forget begins on a failed replacement with a plan of its own (`Method.erases` in the model), since a replacement whose retry would rebuild an Entity the lab removed has no other way out. Before its begin, `retirement.record_before_begin` records in the removal record what the failed plan retired, and the forget's plan from the graph deletes everything the source still owns, so no retirement is lost. Code: `admissible`, which `begin` consults under the reservation. It reads `TRANSITIONS`, keyed by row state and saved plan operation, for the methods each row admits with their revision step and the refusal for the rest, then `REQUIRED_PLANS`, whose `preserved` fields a replacement retry must keep. Since fix round 2 `admissible` also holds the description check at the saved revision (`revision_reuse`) and the final check that a new revision is exactly the next one (`revision_sequence`), which also gives the missing-row entry its refusal. A failed replacement's retry, and a reconcile of a failed publication, pass the description check with another description only when the plan's `erased_from` is the saved list plus the saved description (`RequiredPlan.supersedes`; otherwise `erased_from` is a preserved field), and then every step of that chain must be the erasure removal a forgotten row allows (`erasure_rules.check_retry_chain` over the rows `begin` reads under the reservation), and the step new in the begin lists its removed records as last served at the row's verified revision. Since checkpoint J2 fix round 3 only that new step's cited records must still be bound; a step an earlier begin admitted keeps its shape checks. A plan that names `erased_from` on any other begin is refused (`STRAY_ERASURE`). Also `begin` links a recovery attempt to the open event, `fail` reuses the open event, and `complete` resolves it with `outcome` set to the completion state (`restored` for current) and the last recovery attempt marked `verified`; `retrieve` and the fixtures report that outcome. No call removes an event row. `begin` and `complete` change only unresolved events, except that a completing forget drops the `message` of every event of the source, resolved ones included (P7). `fail` looks an event up by id without checking `resolved_at`, but its attempt guard means it reaches only the event of the row's current attempt, which is unresolved.
- **P6. Failed rows can recover.** Harm: a failure that no explicit recovery can clear withholds the source forever. Code: `begin` accepts the owning method on a failed row with the saved revision, description and plan. `assert_pending` and `complete` then accept that attempt.
- **P7. A forgotten row holds no description content.** Harm: an erased source's occurrence texts, recipe names, document excerpts or error messages stay in the ledger and in `status`. Code: `complete(state="forgotten", tombstone=...)` writes the tombstone as the description, `scrubbed_plan` as the plan and `scrubbed_event` for every recovery event of the source, in the transaction that sets the state. Since the re-add follow-ups (2026-10-23) the tombstone carries the UUIDs of the source's earlier forgotten lives. Since their fix round 1 `forget.py` builds that carry under the reservation from the row's `last_tombstone` (`Tombstone.of(..., earlier=...)`) and `complete` writes the tombstone it is given; the checker passes `Tombstone.of` without `earlier`, whose carry is empty because the model's descriptions share their UUIDs. `PublicationRow.of` refuses a forgotten row whose description is not a tombstone, or a tombstone in an older format (`forgotten_format`, through `saved_tombstone`), which the checker reports as P7.
- **P8. A source that lives again keeps its last tombstone until its next forget.** Harm: a source forgotten, re-added and forgotten again loses the UUIDs of its first life, so a later re-add or another source may take one of them back; or a forgotten row keeps a second tombstone beside its own. Code: `begin` on a forgotten row (a re-add) moves the tombstone from the description to `last_tombstone`; no other `begin` touches it; `complete(state="forgotten")` clears it in its guarded update. Added in the re-add follow-ups fix round 1 (2026-10-23).

## Steps

Each step is one call sequence that the named caller makes. The checker treats each RecordStore call as one step. The code makes that true, because each call commits once or rolls back.

| Step label | Caller | RecordStore calls |
| --- | --- | --- |
| `Wn publish Sk rev=1 expect=0 plan=publish` | `Publisher.publish`, first publication | `begin(method="publish")` |
| `Wn publish Sk rev=r+1 expect=r plan=publish` | `Publisher.readd` on a forgotten row (`readd` CLI) | `begin(method="publish")` |
| `Wn reconcile Sk rev=r expect=r plan=publish` | `Publisher.reconcile`, the `reconcile` CLI | `begin(method="reconcile")` |
| `Wn replace Sk rev=r+1 expect=r plan=replace<rR` | `replace`, a new replacement plan from revision R | `begin(method="replace")` |
| `Wn replace Sk rev=r+1 expect=r plan=text<rR` | `replace` with a `text_change` (`maintain_one`) | `begin(method="replace")` |
| `Wn replace Sk rev=r+1 expect=r plan=regroup<rR` | `replace` with a regrouping `text_change` (`split-group`, `combine-groups`, `maintain_one`) | `begin(method="replace")` |
| `Wn replace Sk rev=r expect=r plan=<saved>` | the retry branch of `replace` | `begin(method="replace")` with the saved plan |
| `Wn withdraw Sk rev=r expect=r plan=withdraw` | `withdraw`, with the saved plan on retry | `begin(method="withdraw")` |
| `Wn forget Sk rev=r expect=r plan=forget` | `forget` on a current, withdrawn or failed row, with the saved plan on retry | `begin(method="forget")` |
| `Wn forget Sk rev=1 expect=0 plan=forget` | none (refusal input): `forget` raises `source_missing` before `begin` on a missing row | `begin(method="forget")` |
| `Wn complete` | `Publisher._apply_pending`, `withdraw`, `forget` | `assert_pending()` (not for withdraw or forget), then `complete()`, which a forget passes the tombstone of the description it began. If a call refuses, the caller's `fail()` runs. A publish whose `assert_pending()` refuses stops with the reservation held. |
| `Wn complete desc=alt` | none (refusal input) | the same calls with a description other than the one begun |
| `Wn fail@stage` | the `except` blocks of the callers | `fail()` with `nodes`, `replace_saved`, `withdraw_contributions` or `forget_contributions` |
| `Wn crash` | a hard crash (docs/SESSION_HANDOFF.md, "Constraints to preserve") | none. The writer keeps the reservation. |
| `Wn repeat` | a duplicated or delayed acknowledgement | the writer's last `complete()` or `fail()` again |
| `reject Sk` | `valid_sources` | `fail(..., "retrieval_validation", ...)` with the attempt of the row as it was last seen current |

`desc=alt` marks variant 1 and `desc=served` variant 2, the erasure removals of variant 0 at the same revision that list r01 as last served at the revision before and at this revision. The plan tag after `<` names the revision that the replacement plan's `previous_description` holds. A trailing `alt` or `served` marks the changed description.

### Refusal inputs

From every row version, the intents functions also send arguments that `begin()` must refuse. A missing guard then shows as a property failure.

- The changed description at the saved revision, for reconcile, withdraw, forget and the replace retry.
- Reconcile, withdraw and forget at the saved revision plus one.
- Publish from no row at revision 2, publish at the saved revision on any row, and replace at the saved revision plus two.
- A replacement whose plan is a publish plan, and a forget whose plan is a publish plan.
- A forget on a source that has no row.
- A replace retry whose plan changes `previous_description` or adds, drops or swaps `text_change` (a `text` plan for a `regroup` plan).

## Modeling choices

- **Stale reads.** A caller reads the row without the reservation and calls `begin()` later. So a writer may call `begin()` with arguments built from any row version that the source had earlier on the path.
- **Caller pre-checks.** The checker skips the pre-checks in `Publisher.publish`, `Publisher.reconcile`, `Publisher.readd`, `replace`, `withdraw` and `forget`, because `begin()` must hold on its own. The one exception is a missing row (the next item).
- **Missing rows.** The intents functions send no reconcile, replace or withdraw step for a source that has no row. The callers never make that call:
  - `withdraw`, `forget` and `replace` read the row first and raise `source_missing` when it is missing. The forget step is sent anyway, because the missing-row entry of `TRANSITIONS` refuses it as `source_missing` and the break `forget-without-a-row` shows what its removal admits: a `forgotten` row at revision 1 for a source that never published.
  - `Publisher.publish` uses method `reconcile` only with an expected revision of 1 or more. `begin()` refuses that on a missing row as `stale_revision`.
  - No code removes a `Publication` row. So a row that a caller read once is never missing later, and a stale read cannot send these calls.

  `begin()` itself accepts reconcile and withdraw on a missing row at expected revision 0 and revision 1. The missing-row entry refuses replace and forget as `source_missing`. Because the checker does not send replace for a missing row, a break that lets that entry admit replace is not caught.
- **Stage names.** storage.py only copies `stage` into the event. So the checker uses one fault stage per method. If storage.py begins to branch on `stage`, add each stage as a separate `Finish` step.
- **Descriptions.** A description is a function of source, revision and variant. It is the fixture `tests/fixtures/identity/cognee_identity_source_example.json` with a new `identity_data_id` and `revision`. Since fix round 2 every sequence starts with a forgotten background source (`Harness.forget_background`, written to the table directly), variant 0 cites its document from r01, and variants 1 and 2 are the erasure removal of variant 0 as forget writes it, listing r01 as last served at the revision before or at this revision. Since checkpoint J2 fix round 3 a caller's erasure retry sends the variant that lists the row's verified revision (`removal`), as forget does, and also the other one, which begin must refuse as a new step (`View.early`). So a removal is the one description an erasure retry may supersede variant 0 with (`ERASURE_STEPS`), and every other change at a saved revision is refused.
- **Plans.** A plan holds only the fields that storage.py reads: `operation`, `revision`, `previous_description`, `text_change`, `erased_from` and `runtime_profile`. `text_change` is a name, `text` or `regroup`, for the one dict that the checker sends for it (`TEXT_CHANGES` in `support/ledger_model.py`). The plan tag is part of the step label, so dedupe and `--replay` tell plans apart.
- **Symmetry.** Writers that never began are interchangeable, and sources that never had a row are interchangeable. Only the first of each kind can take a first step.
- **No-op steps.** The checker checks a step that changes no row, event, reservation or checker state, but does not expand it. Every sequence after that step is also a sequence after its parent.
- **Refused steps.** When a refused call leaves the tables equal to the parent's snapshot, the checker reuses the parent's observation and does not read `rows()` and `events()` again.
- **P6 probe.** After each step that changes state, the checker looks for failed rows while the reservation is free. For each one it runs the owning method's recovery and then restores the store. The probe is not a step of the sequence.
- **Store.** The store is in-memory SQLite through aiosqlite with `StaticPool`. The session maker is `async_sessionmaker(expire_on_commit=False)`. Cognee uses the same session maker on a SQLite file with `NullPool`.

## Measurements

Measured on 2026-10-21 on the development Mac (10 cores). P = 0, 2 sources, 2 writers. `seconds` excludes interpreter startup. Runs below depth 4 are `INCONCLUSIVE`. Depth 3 reaches no withdrawn row and no recovered row.

| Depth | Result | nodes / sequences / s |
| --- | --- | --- |
| 1 | INCONCLUSIVE | 3 / 2 / 0.01 |
| 2 | INCONCLUSIVE | 21 / 19 / 0.04 |
| 3 | INCONCLUSIVE | 108 / 102 / 0.21 |
| 4 | PASS | 565 / 541 / 1.03 |
| 5 | PASS | 3062 / 2961 / 5.76 |
| 6 | PASS | 15763 / 15278 / 27.83 |
| 7 | PASS | 87700 / 85448 / 163.85 |
| 8 | PASS | 482109 / 470249 / 893.41 |

After the regrouping plan joined the step list on 2026-10-21, depth 5 gave 3828 nodes and 3717 sequences in about 6.7 s. After the forget method and the re-add joined it on 2026-10-22, depth 5 gave 5548 nodes and 5429 sequences in about 9 s. Later that day the forget on a missing row joined the step list, and depth 5 gives 5889 nodes and 5770 sequences in about 10 s; `--mutants` runs its 40 breaks in about 15 s. The depths 6 to 8 rows above predate these changes.

On 2026-10-23 (checkpoint I) forget began on withdrawn and failed-publication rows, the tombstone joined `complete`, and P7 was added. Depth 5 gave 6287 nodes and 6156 sequences in about 10.4 s; `--mutants` ran its 45 breaks in about 15 s.

Later on 2026-10-23 (checkpoint I fix round 1) the erasure retry joined the step list: a replace retry on a failed replacement that supersedes the saved description, a retry that names a description that is not saved, one that grows the list without changing the description, and one that drops the list. Depth 5 gives 6431 nodes and 6300 sequences in about 10.6 s, and `--mutants` runs its 46 breaks in about 32 s (measured by the assistant on the user's Mac). The properties moved from `ledger_check.py` to `ledger_properties.py` in the same change.

On 2026-10-23 (checkpoint I fix round 2) the store began to check the erasure-retry chain itself, and reconcile began erasure retries of failed publications. The model gained the forgotten background source, variant 1 as a real removal, a replace first attempt that writes variant 1, a misnamed supersede, and reconcile's superseding, kept and dropped `erased_from` plans. Depth 5 gives 8504 nodes and 8349 sequences in about 15 s, and depth 6 about 48000 nodes in about 95 s, because `begin` now reads and parses every row under the reservation (measured by the assistant on the user's Mac). `--mutants` runs its 49 breaks. On 2026-10-23 (checkpoint I fix round 3) `begin` reads the rows only for an erasure retry, the counts are unchanged, and `--mutants` runs 51 breaks, `supersede-drops-chain` among them, moved from the deep breaks. On 2026-10-24 (checkpoint J2 fix round 2) a new erasure-retry step must list exactly the verified revision, so the model's variant 1, which lists the revision before, is refused on a row served at its own revision: depth 5 gives 8427 nodes and 8274 sequences in about 14 s (measured by the assistant on the user's Mac), and `--mutants` runs 52 breaks. On 2026-10-24 (checkpoint J2 fix round 3) variant 1 split into variants 1 and 2, the caller sends the one that lists the verified revision, and P5 requires an accepted new step to list it: depth 5 gives 9205 nodes and 9050 sequences in about 16 s. Without the refused early listings the counts are 9026 and 8871, so 599 nodes come from the admitted in-place retry on a row served at its own revision and the sequences after it, and 179 from the refused early listings, each a no-op leaf (measured by the assistant on the user's Mac). `--mutants` runs 53 breaks.

P5 later gained two checks: no step removes a recovery event, and no step changes a resolved one. After that change, depths 6, 7 and 8 passed again with the same counts. Those runs ran in parallel, so their times are not in the table.

Sampled runs, depth 8 and 9, 2 sources, 2 writers, P = 0.5:

| Depth | Seed | Result | nodes / skipped / sequences / s |
| --- | --- | --- | --- |
| 8 | 2 | PASS | 2592 / 2601 / 2477 / 4.81 |
| 8 | 5 | PASS | 5914 / 5862 / 5595 / 12.24 |
| 8 | 6 | PASS | 9581 / 9637 / 9170 / 18.58 |
| 8 | 1, 3, 4, 7, 8 | INCONCLUSIVE (first step skipped) | 1 or 2 nodes, 0.00 to 0.02 s |
| 9 | 2 | PASS | 48111 / 47994 / 46108 / 98.77 |
| 9 | 5 | PASS | 19627 / 19498 / 18712 / 39.47 |

A checked state costs about 2 ms. Most of that time is the wait for aiosqlite's thread: about 34 thread round trips per node. Each extra depth multiplies the nodes by about 5.5. No-op steps, mostly refused calls, are 84 % to 88 % of the nodes.

The default bound is depth 5. Depth 5 is the shallowest bound that catches every break in `MUTANTS`, because several of those breaks need five steps. It does not catch the breaks in `DEEP_MUTANTS`, which need six or seven steps. The pytest file runs the default bound and every break in parallel spawn processes, in about 10 s on this machine. Depth 6 (about 30 s), depth 7 (about 3 minutes) and depth 8 (about 15 minutes) are manual bounds.

## Scratch breaks

`support/ledger_mutants.py` holds the breaks. Since 2026-10-22 a break of a `begin` guard edits one of these sites: a `TRANSITIONS` entry (the recovery choice, withdrawn, forgotten, re-add and missing-row breaks), the `lineage_row()` helper (`publish-restarts-saved-row`), the `cell_for()` lookup (`failed-row-never-recoverable`), `REQUIRED_PLANS` with its `preserved` fields (`forget-from-any-failed-row` and the two preservation breaks), a line of `admissible` (the advance guard and plan check breaks), or `begin`'s final revision check (`no-plus-one`). The assistant rewrote the breaks that day for the transition table and checked on the user's Mac that every break is caught by the same property with the same minimal sequence as main's break. The one sequence that changed in the table below is `no-stale-revision-guard`: its old entry was stale before the refactor, and main's own break gives the forget sequence now listed. For the five revision breaks (`no-advance-guard`, `advance-guard-ignores-method`, `publish-restarts-saved-row`, `readd-at-forgotten-revision` and `no-plus-one`) the assistant also ran every `begin` call of a scratch comparison (each row state with each saved plan, each method, expected revision, revision 1 to 4, description and plan) under main's break and under the new one: each pair admits exactly the same calls. `--mutants` runs each one on an in-memory copy of storage.py, at the default bound, in parallel processes. It exits non-zero if a break is missed or is caught by a property other than the one it names. These results are from depth 5, 2 sources and 2 writers on 2026-10-21, and on 2026-10-22 for the forget and re-add breaks. The sequences leave out `expect=`, `plan=publish` and `plan=withdraw` from the labels.

| Break | Property | Minimal sequence |
| --- | --- | --- |
| `begin-keeps-state` | P1 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1` |
| `complete-skips-verified-revision` | P1 | `W1 publish S1 rev=1`, `W1 complete` |
| `fail-keeps-state` | P1 | `W1 publish S1 rev=1`, `W1 complete`, `reject S1` |
| `begin-links-every-source` | P2 | `W1 publish S1 rev=1`, `W1 fail@nodes`, `W1 publish S2 rev=1` |
| `complete-resolves-every-source` | P2 | `W1 publish S1 rev=1`, `W1 complete`, `W1 publish S2 rev=1`, `reject S1`, `W1 complete` |
| `no-stale-revision-guard` | P3 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget` |
| `complete-ignores-attempt` | P3 | `W1 publish S1 rev=1`, `W1 complete`, `W1 repeat` |
| `fail-ignores-attempt` | P3 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1`, `reject S1` |
| `assert-pending-ignores-description` | P3 | `W1 publish S1 rev=1`, `W1 complete desc=alt` |
| `assert-pending-ignores-attempt` | P3 | `W1 publish S1 rev=1`, `W1 complete`, `W2 reconcile S1 rev=1`, `W1 repeat` |
| `no-writer-reservation` | P4 | `W1 publish S1 rev=1`, `W2 publish S2 rev=1` |
| `complete-keeps-reservation` | P4 | `W1 publish S1 rev=1`, `W1 complete` |
| `fail-always-new-event` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `reject S1`, `W1 reconcile S1 rev=1`, `W1 fail@nodes` |
| `no-replace-recovery-choice` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1`, `W1 complete desc=alt`, `W1 reconcile S1 rev=2` |
| `no-withdraw-recovery-choice` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 withdraw S1 rev=1`, `W1 fail@withdraw_contributions`, `W1 reconcile S1 rev=1` |
| `no-withdrawn-guard` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 withdraw S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1` |
| `forget-refuses-withdrawn` | INCONCLUSIVE | none: no forget on a withdrawn row is accepted, so `forget withdrawn` is never reached |
| `forget-refuses-failed-publication` | INCONCLUSIVE | none: no forget on a failed publication is accepted, so `forget failed publish` is never reached |
| `forget-refuses-failed-replacement` | INCONCLUSIVE | none: no forget on a failed replacement is accepted, so `forget failed replace` is never reached |
| `no-forgotten-guard` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1` |
| `publish-restarts-saved-row` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 publish S1 rev=2` |
| `no-forget-recovery-choice` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 fail@forget_contributions`, `W1 reconcile S1 rev=1` |
| `forget-on-failed-withdrawal` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 withdraw S1 rev=1`, `W1 fail@withdraw_contributions`, `W1 forget S1 rev=1 plan=forget` |
| `forget-takes-any-plan` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1` |
| `complete-keeps-description` | P7 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete` |
| `complete-keeps-plan` | P7 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete` |
| `begin-drops-last-tombstone` | P8 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete`, `W1 publish S1 rev=2` |
| `complete-keeps-messages` | P7 | `W1 publish S1 rev=1`, `W1 complete`, `reject S1`, `W1 forget S1 rev=1 plan=forget`, `W1 complete` |
| `complete-forgotten-as-withdrawn` | P1 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete` |
| `no-advance-guard` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=2` |
| `advance-guard-ignores-method` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=2` |
| `no-revision-reuse` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1 desc=alt` |
| `supersede-any-description` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1 desc=alt`, `W1 complete desc=alt`, `W1 replace S1 rev=2 plan=replace<r1+e0 desc=alt` |
| `erasure-chain-unchecked` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1 desc=alt`, `W1 complete desc=alt`, `W1 replace S1 rev=2 plan=replace<r1+e1` (since fix round 3 a retry that names the saved description and begins with it unchanged is refused before the chain check, so the first break found is the reverse step, variant 1 superseded by 0) |
| `retry-new-step-as-admitted` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1 plan=publish`, `W1 fail@nodes`, `W1 reconcile S1 rev=1 plan=publish+e0 desc=alt` |
| `erasure-outside-retry` | P5 | a reconcile of a current row with a plan that names `erased_from`, from a stale read of its failed publication |
| `reconcile-never-supersedes` | INCONCLUSIVE | never reaches `erasure retry reconcile` |
| `supersede-drops-chain` | P5 | `W1 publish S1 rev=1`, `W1 fail@nodes`, `W1 reconcile S1 rev=1 plan=publish+e0 desc=alt`, `W1 fail@nodes`, `W1 reconcile S1 rev=1 desc=alt` |
| `begin-reads-no-rows` | INCONCLUSIVE | never reaches `erasure retry reconcile`: with no forgotten row to bind to, every erasure retry is refused (`erasure_unbound`) |
| `no-plus-one` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 publish S2 rev=2` |
| `no-replace-plan-check` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2` |
| `no-replace-plan-preservation` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1`, `W1 complete desc=alt`, `W1 replace S1 rev=2 plan=text<r1` |
| `no-text-change-preservation` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1`, `W1 complete desc=alt`, `W1 replace S1 rev=2 plan=text<r1` |
| `begin-resolves-open-event` | P5 | `W1 publish S1 rev=1`, `W1 fail@nodes`, `W1 reconcile S1 rev=1` |
| `complete-deletes-open-events` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `reject S1`, `W1 reconcile S1 rev=1`, `W1 complete` |
| `begin-drops-open-event` | P5 | `W1 publish S1 rev=1`, `W1 fail@nodes`, `W1 reconcile S1 rev=1` |
| `begin-links-resolved-events` | P5 | `W1 publish S1 rev=1`, `W1 fail@nodes`, `W1 reconcile S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1` |
| `complete-always-refuses` | P6 | `W1 publish S1 rev=1`, `W1 complete` |
| `failed-row-never-recoverable` | P6 | `W1 publish S1 rev=1`, `W1 complete`, `reject S1` |
| `advance-guard-refuses-readd` | INCONCLUSIVE | none: no publish on a forgotten row is accepted, so `accepted readd` is never reached |
| `forget-without-a-row` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S2 rev=1 plan=forget` |
| `complete-misnames-outcome` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `reject S1`, `W1 withdraw S1 rev=1`, `W1 complete` |
| `begin-always-busy` | INCONCLUSIVE | none: no `begin()` is accepted, so the run is `INCONCLUSIVE` |

### Deep breaks

`DEEP_MUTANTS` in `support/ledger_mutants.py` holds breaks that only a search deeper than the default bound catches. `--mutants` and the default pytest run leave them out. The pytest file replays the minimal sequence of each one, recorded in `DEEP_SEQUENCES`. The full search is a manual command, for example:

```bash
uv run python support/ledger_check.py --mutant withdrawn-guard-admits-replace --depth 7
```

| Break | Depth | Property | Minimal sequence |
| --- | --- | --- | --- |
| `complete-keeps-last-tombstone` | 8 | P8 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete`, `W1 publish S1 rev=2`, `W1 complete`, `W1 forget S1 rev=2 plan=forget`, `W1 complete` (the recorded sequence; the depth 8 search was not run) |
| `withdrawn-guard-admits-replace` | 7 | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1`, `W1 complete`, `W1 withdraw S1 rev=2`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1` |

The withdrawn guard is the only guard that refuses the last step. That step is the retry branch of `replace`, built from a stale read of the current replacement row. Its plan is a replace plan, so the plan guard accepts it. The row is withdrawn, not failed, so the plan preservation guard does not apply. At depth 6 the search passes with the real node count (15763 nodes). At depth 7 it fails after 4032 nodes, in about 7 s. On 2026-10-22, after the forget steps joined the step list and the table refactor, the assistant measured on the user's Mac that it fails after 7938 nodes in about 13 s, with the same minimal sequence. On 2026-10-23, with forget admitted on a withdrawn row, the break's anchor is the withdrawn entry with forget in it; it fails after 8346 nodes in about 14.5 s, with the same minimal sequence.

The erasure retry break `supersede-drops-chain` lets a retry of a failed erasure retry drop the descriptions it superseded from its plan. Before fix round 2 the break made the saved arguments of a failed erasure retry stop beginning, which P6 caught at depth 6. Fix round 2 recorded it at depth 7 through replace, but its reconcile intents already let depth 5 catch it through reconcile: the assistant ran the break on the `cb5fd20` sources on 2026-10-23 and it failed at depth 5. Since fix round 3 it is in `MUTANTS` (see the table above).

### Breaks that are not caught

These breaks are not caught. They are not in `ledger_mutants.py`.

- `complete` without `Publication.revision == source.revision`. The attempt filter already binds the revision.
- `fail` that finds the row by attempt. Attempt ids are unique per source.
- `complete(state="withdrawn")` that also sets `verified_revision`. A withdrawn row is never served.

For these three, no reachable sequence separates the break from the real code. Each one gives the same node count as the real code at depth 6 (15763 nodes).

- `readd-at-forgotten-revision`, dropped on 2026-10-23: a forgotten row without its `sequence` refusal. Since the row holds a tombstone, `begin`'s description check refuses a publish at the forgotten revision (`revision_reuse`), and its final check refuses any other revision but the next, so no reachable call separates the break. For the same reason `no-forgotten-guard` now admits a new replacement on the forgotten row, which only the forgotten guard refuses.
- `forget-from-any-failed-row`, dropped on 2026-10-23: forget's `off_row` refusal. Every row entry now admits or refuses forget itself, so `admissible` never reaches it. The break `forget-on-failed-withdrawal` covers the owned rows instead; since 2026-10-26 forget begins on a failed replacement, and `forget-refuses-failed-replacement` covers that entry.
- A missing-row entry in `TRANSITIONS` that admits replace. The checker does not send replace for a missing row (see "Missing rows" in the modeling choices). The forget guard is covered by `forget-without-a-row`.

## Proof that this skill works

On 2026-10-21 an agent followed SKILL.md on scratch edits of the real `storage.py` file. Neither edit was in `ledger_mutants.py`.

1. The first edit let `replace` pass the withdrawn guard in `begin`. The check printed `PASS` with the counts from before the edit, because the default depth 5 cannot reach the break. The agent then called the break not observable, and chose another edit. That claim was wrong. A depth 7 search catches the break (see "Deep breaks").
2. The second edit removed `details.get("resolved_at") is None and` from the event search in `fail`. So `fail` can reuse a resolved event.
3. The `git diff 6f1bdba` command from SKILL.md showed the change.
4. `uv run python support/ledger_check.py` printed `FAIL` and exited with code 1, in 3.99 s. The message was `P5: S1 is failed with 0 unresolved recovery events`.
5. The minimal sequence was `W1 publish S1`, `W1 fail@nodes`, `W1 reconcile S1`, `W1 complete`, `reject S1`. Retrieval failed the recovered row and wrote the failure into the event that the reconcile had resolved.
6. The `--replay` command from the report gave the same failure.
7. After the agent restored the line, `git diff main -- src/` was empty. The check printed `PASS verified within bound` with the pinned counts (3062 nodes, 2961 sequences).

## Findings at the sync commit

None. Every property holds in the exhaustive runs up to depth 8 with 2 sources and 2 writers, and in the sampled runs at depth 9.

The code allows these behaviors, and the checker accepts them. Read them before you add a property:

- Reconcile of a current row is accepted. It withholds the source until its attempt completes.
- Withdraw of a withdrawn row is accepted.
- `fail` for the attempt of a current row is accepted. That is how `valid_sources` withholds a row that fails validation.
- The `pending_attempt` guard in `begin` is unreachable in the model. A pending row always has its writer's reservation, unless a person clears the reservation by hand.
