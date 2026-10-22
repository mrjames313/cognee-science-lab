# Identity ledger check: reference

Read [SKILL.md](SKILL.md) first. This file holds the detail behind it. It gives the harm and code for each property, the step list and the modeling choices. It also records measurements, scratch breaks, the skill proof and findings.

## Properties: harm and code

All functions are in `src/cognee_lab/identity/storage.py` unless the entry names another file.

- **P1. Withheld until complete.** Harm: retrieval serves facts from a pending, failed or half-written publication. Code: `begin` sets `pending`. `fail` sets `failed`. Only `complete` sets `verified_revision`, and only for the pending attempt at its revision. `valid_sources` in retrieve.py serves a row only when it is `current` at `verified_revision`.
- **P2. Independent sources.** Harm: a failure or recovery on one source withholds, resolves or corrupts another source. Code: every row and event query in `begin`, `fail` and `complete` filters on dataset and source.
- **P3. Stale calls are refused.** Harm: a writer that works from an old read overwrites newer intent. Or a late acknowledgement marks the wrong attempt or description as verified. Code: the `stale_revision` guard in `begin`, the attempt check in `fail`, the attempt and `pending` filter in `complete`, and the description check in `assert_pending`. A guard raises before the commit, so the session rolls back.
- **P4. One writer at a time.** Harm: two writers interleave graph writes for overlapping intents. Code: `begin` takes the `Writer` row only when it has no owner. `fail` and `complete` release it only for their own attempt.
- **P5. Recovery is explicit and forward.** Harm: an operator loses track of an incident, sees two incidents for one failure, or sees the record of a resolved incident change. Or a method that does not own the saved intent rolls it back, replaces it or drops its retirement plan. Code: the guards in `begin` (`recovery_choice`, `withdrawn_source`, `revision_reuse`, `revision_sequence`, `recovery_plan`). Also `begin` links a recovery attempt to the open event, `fail` reuses the open event, and `complete` resolves it. No call removes an event row. `begin` and `complete` change only unresolved events. `fail` looks an event up by id without checking `resolved_at`, but its attempt guard means it reaches only the event of the row's current attempt, which is unresolved.
- **P6. Failed rows can recover.** Harm: a failure that no explicit recovery can clear withholds the source forever. Code: `begin` accepts the owning method on a failed row with the saved revision, description and plan. `assert_pending` and `complete` then accept that attempt.

## Steps

Each step is one call sequence that the named caller makes. The checker treats each RecordStore call as one step. The code makes that true, because each call commits once or rolls back.

| Step label | Caller | RecordStore calls |
| --- | --- | --- |
| `Wn publish Sk rev=1 expect=0 plan=publish` | `Publisher.publish`, first publication | `begin(method="publish")` |
| `Wn publish Sk rev=r+1 expect=r plan=publish` | `Publisher.publish` on a forgotten row, the re-add (`readd` CLI) | `begin(method="publish")` |
| `Wn reconcile Sk rev=r expect=r plan=publish` | `Publisher.publish` with a saved revision, the `reconcile` CLI | `begin(method="reconcile")` |
| `Wn replace Sk rev=r+1 expect=r plan=replace<rR` | `replace`, a new replacement plan from revision R | `begin(method="replace")` |
| `Wn replace Sk rev=r+1 expect=r plan=text<rR` | `replace` with a `text_change` (`maintain_one`) | `begin(method="replace")` |
| `Wn replace Sk rev=r+1 expect=r plan=regroup<rR` | `replace` with a regrouping `text_change` (`split-group`, `combine-groups`, `maintain_one`) | `begin(method="replace")` |
| `Wn replace Sk rev=r expect=r plan=<saved>` | the retry branch of `replace` | `begin(method="replace")` with the saved plan |
| `Wn withdraw Sk rev=r expect=r plan=withdraw` | `withdraw`, with the saved plan on retry | `begin(method="withdraw")` |
| `Wn forget Sk rev=r expect=r plan=forget` | `forget`, with the saved plan on retry | `begin(method="forget")` |
| `Wn complete` | `Publisher._apply_pending`, `withdraw`, `forget` | `assert_pending()` (not for withdraw or forget), then `complete()`. If a call refuses, the caller's `fail()` runs. A publish whose `assert_pending()` refuses stops with the reservation held. |
| `Wn complete desc=alt` | none (refusal input) | the same calls with a description other than the one begun |
| `Wn fail@stage` | the `except` blocks of the callers | `fail()` with `nodes`, `replace_saved`, `withdraw_contributions` or `forget_contributions` |
| `Wn crash` | a hard crash (docs/SESSION_HANDOFF.md, "Constraints to preserve") | none. The writer keeps the reservation. |
| `Wn repeat` | a duplicated or delayed acknowledgement | the writer's last `complete()` or `fail()` again |
| `reject Sk` | `valid_sources` | `fail(..., "retrieval_validation", ...)` with the attempt of the row as it was last seen current |

`desc=alt` marks a description that changes the original text digest. The plan tag after `<` names the revision that the replacement plan's `previous_description` holds. A trailing `alt` marks the changed description.

### Refusal inputs

From every row version, the intents functions also send arguments that `begin()` must refuse. A missing guard then shows as a property failure.

- The changed description at the saved revision, for reconcile, withdraw, forget and the replace retry.
- Reconcile, withdraw and forget at the saved revision plus one.
- Publish from no row at revision 2, publish at the saved revision on any row, and replace at the saved revision plus two.
- A replacement whose plan is a publish plan, and a forget whose plan is a publish plan.
- A replace retry whose plan changes `previous_description` or adds, drops or swaps `text_change` (a `text` plan for a `regroup` plan).

## Modeling choices

- **Stale reads.** A caller reads the row without the reservation and calls `begin()` later. So a writer may call `begin()` with arguments built from any row version that the source had earlier on the path.
- **Caller pre-checks.** The checker skips the pre-checks in `Publisher.publish`, `replace` and `withdraw`, because `begin()` must hold on its own. The one exception is a missing row (the next item).
- **Missing rows.** The intents functions send no reconcile, replace or withdraw step for a source that has no row. The callers never make that call:
  - `withdraw` and `replace` read the row first and raise `source_missing` when it is missing.
  - `Publisher.publish` uses method `reconcile` only with an expected revision of 1 or more. `begin()` refuses that on a missing row as `stale_revision`.
  - No code removes a `Publication` row. So a row that a caller read once is never missing later, and a stale read cannot send these calls.

  `begin()` itself accepts reconcile and withdraw on a missing row at expected revision 0 and revision 1. Only replace has a `source_missing` guard in `begin()`. Because the checker does not send these calls, a break that removes that guard is not caught.
- **Stage names.** storage.py only copies `stage` into the event. So the checker uses one fault stage per method. If storage.py begins to branch on `stage`, add each stage as a separate `Finish` step.
- **Descriptions.** A description is a function of source, revision and variant. It is the fixture `tests/fixtures/identity/cognee_identity_source_example.json` with a new `identity_data_id` and `revision`. Variant 1 changes the original text digest.
- **Plans.** A plan holds only the fields that storage.py reads: `operation`, `revision`, `previous_description`, `text_change` and `runtime_profile`. `text_change` is a name, `text` or `regroup`, for the one dict that the checker sends for it (`TEXT_CHANGES` in `support/ledger_model.py`). The plan tag is part of the step label, so dedupe and `--replay` tell plans apart.
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

After the regrouping plan joined the step list on 2026-10-21, depth 5 gave 3828 nodes and 3717 sequences in about 6.7 s. After the forget method and the re-add joined it on 2026-10-22, depth 5 gives 5548 nodes and 5429 sequences in about 9 s, and `--mutants` runs its 37 breaks in about 15 s. The depths 6 to 8 rows above predate both changes.

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

The default bound is depth 5. Depth 5 is the shallowest bound that catches every break in `MUTANTS`, because several of those breaks need five steps. It does not catch the break in `DEEP_MUTANTS`, which needs seven steps. The pytest file runs the default bound and every break in parallel spawn processes, in about 10 s on this machine. Depth 6 (about 30 s), depth 7 (about 3 minutes) and depth 8 (about 15 minutes) are manual bounds.

## Scratch breaks

`support/ledger_mutants.py` holds the breaks. `--mutants` runs each one on an in-memory copy of storage.py, at the default bound, in parallel processes. It exits non-zero if a break is missed or is caught by a property other than the one it names. These results are from depth 5, 2 sources and 2 writers on 2026-10-21, and on 2026-10-22 for the forget and re-add breaks. The sequences leave out `expect=`, `plan=publish` and `plan=withdraw` from the labels.

| Break | Property | Minimal sequence |
| --- | --- | --- |
| `begin-keeps-state` | P1 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1` |
| `complete-skips-verified-revision` | P1 | `W1 publish S1 rev=1`, `W1 complete` |
| `fail-keeps-state` | P1 | `W1 publish S1 rev=1`, `W1 complete`, `reject S1` |
| `begin-links-every-source` | P2 | `W1 publish S1 rev=1`, `W1 fail@nodes`, `W1 publish S2 rev=1` |
| `complete-resolves-every-source` | P2 | `W1 publish S1 rev=1`, `W1 complete`, `W1 publish S2 rev=1`, `reject S1`, `W1 complete` |
| `no-stale-revision-guard` | P3 | `W1 publish S1 rev=1`, `W1 complete`, `W1 publish S1 rev=1` |
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
| `no-forgotten-guard` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete`, `W1 reconcile S1 rev=1` |
| `no-forget-recovery-choice` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 fail@forget_contributions`, `W1 reconcile S1 rev=1` |
| `forget-from-any-failed-row` | P5 | `W1 publish S1 rev=1`, `W1 fail@nodes`, `W1 forget S1 rev=1 plan=forget` |
| `forget-takes-any-plan` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=publish` |
| `publish-restarts-saved-row` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 publish S1 rev=2 expect=1` |
| `readd-at-forgotten-revision` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete`, `W1 publish S1 rev=1 expect=1` |
| `complete-forgotten-as-withdrawn` | P1 | `W1 publish S1 rev=1`, `W1 complete`, `W1 forget S1 rev=1 plan=forget`, `W1 complete` |
| `no-advance-guard` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=2` |
| `advance-guard-ignores-method` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=2` |
| `no-revision-reuse` | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 reconcile S1 rev=1 desc=alt` |
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
| `begin-always-busy` | INCONCLUSIVE | none: no `begin()` is accepted, so the run is `INCONCLUSIVE` |

### Deep breaks

`DEEP_MUTANTS` in `support/ledger_mutants.py` holds breaks that only a search deeper than the default bound catches. `--mutants` and the default pytest run leave them out. The pytest file replays the minimal sequence of each one, recorded in `DEEP_SEQUENCES`. The full search is a manual command, for example:

```bash
uv run python support/ledger_check.py --mutant withdrawn-guard-admits-replace --depth 7
```

| Break | Depth | Property | Minimal sequence |
| --- | --- | --- | --- |
| `withdrawn-guard-admits-replace` | 7 | P5 | `W1 publish S1 rev=1`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1`, `W1 complete`, `W1 withdraw S1 rev=2`, `W1 complete`, `W1 replace S1 rev=2 plan=replace<r1` |

The withdrawn guard is the only guard that refuses the last step. That step is the retry branch of `replace`, built from a stale read of the current replacement row. Its plan is a replace plan, so the plan guard accepts it. The row is withdrawn, not failed, so the plan preservation guard does not apply. At depth 6 the search passes with the real node count (15763 nodes). At depth 7 it fails after 4032 nodes, in about 7 s.

### Breaks that are not caught

These breaks are not caught. They are not in `ledger_mutants.py`.

- `complete` without `Publication.revision == source.revision`. The attempt filter already binds the revision.
- `fail` that finds the row by attempt. Attempt ids are unique per source.
- `complete(state="withdrawn")` that also sets `verified_revision`. A withdrawn row is never served.

For these three, no reachable sequence separates the break from the real code. Each one gives the same node count as the real code at depth 6 (15763 nodes).

- `begin` without its `source_missing` guard. The checker does not send replace for a missing row (see "Missing rows" in the modeling choices).

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
