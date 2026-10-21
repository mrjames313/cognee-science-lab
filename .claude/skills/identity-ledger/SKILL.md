---
name: identity-ledger
description: Bounded exhaustive check of the Stage 6 identity publication ledger (RecordStore in src/cognee_lab/identity/storage.py). Use it when a change touches RecordStore begin, fail, complete, assert_pending, rows or events. Also use it for changes to the writer reservation, recovery events or the retrieval eligibility test in retrieve.py. Use it when a new maintenance operation (for example group split or combination) calls RecordStore.
---

# Identity ledger check

`support/ledger_check.py` drives the real `RecordStore` on a fresh in-memory SQLite store. It runs every sequence of ledger operations up to a depth bound, with two sources and two writers. After every step it checks five properties. The slow Cognee graph and vector writes are out of scope. The checker treats the store work of one maintenance operation as one step that succeeds or fails.

## Does your change touch the checked code?

The check covers these files and functions. Run it when your diff touches any of them.

| File | Function or lines | What the checker depends on |
| --- | --- | --- |
| `src/cognee_lab/identity/storage.py` | `RecordStore.begin`, `fail`, `complete`, `assert_pending`, `rows`, `events`, and the `Publication`, `Writer`, `RecoveryEvent` tables | All of it. The checker calls these functions and nothing else. |
| `src/cognee_lab/identity/retrieve.py` | line 21, in `valid_sources` | The eligibility test. The checker copies it as `served()`. |
| `src/cognee_lab/identity/retrieve.py` | lines 88-91, in `valid_sources` | Retrieval calls `fail()` on a current row that fails its input checks. This is the `reject` step. |
| `src/cognee_lab/identity/publish.py` | `Publisher.publish` (lines 289-311), `_apply_pending` (lines 340, 495-516) | The publish and reconcile arguments to `begin()`, the `assert_pending()` call outside the `try` block, and the `complete()` or `fail()` that ends the attempt. |
| `src/cognee_lab/identity/replace.py` | `replace` (lines 99-131, 213-219, 344-392) | The replace arguments: a new plan, or the saved plan on retry. Also the stage that `fail()` records. |
| `src/cognee_lab/identity/withdraw.py` | `withdraw` (lines 42-90, 213-234) | The withdraw arguments: the saved plan is reused on retry. Also the `complete(state="withdrawn")` and `fail()` calls. |

**Sync commit:** `6f1bdba`. On 2026-10-21 the checker described the covered code at this commit. To see whether the check needs another look, run this command:

```bash
git diff 6f1bdba -- src/cognee_lab/identity/storage.py src/cognee_lab/identity/retrieve.py src/cognee_lab/identity/publish.py src/cognee_lab/identity/replace.py src/cognee_lab/identity/withdraw.py
```

If the diff touches the functions in the table, read the changed lines against the step list below. Move the sync commit forward only when the checker still describes the code at the new commit. Rerunning the check is not enough, because a passing check can describe old code.

## Run it

```bash
uv run python support/ledger_check.py                     # depth 5, about 2.5 s
uv run python support/ledger_check.py --depth 7           # manual run, about 50 s
uv run python support/ledger_check.py --depth 8           # manual run, minutes (see Measurements)
uv run python support/ledger_check.py --depth 9 --skip-probability 0.5 --seed 2
uv run python support/ledger_check.py --mutants           # every scratch break must be caught
uv run pytest -q tests/test_identity_ledger_check.py      # default bound plus every scratch break, about 5 s
```

- `--sources 1|2` and `--writers 1|2` set the actors. The default is 2 and 2.
- `--skip-probability P` (0 <= P < 1) skips each candidate step at each node with probability P. The skip removes the whole subtree under that step. `--seed S` seeds the generator. The same command gives the same search.
- Only P = 0 prints `PASS verified within bound`. A run with P > 0 prints `sampled (P=..., seed=...)`. A sampled pass is evidence, not a bound.
- The search starts with one candidate step (`W1 publish S1`), because of the symmetry rule below. If P skips that step, the run checks nothing. The checker then prints `INCONCLUSIVE` and exits with code 2. Choose another seed. At P = 0.5, seeds 1, 3, 4 and 7 skip the first step.
- Each run prints `nodes` (checked states), `skipped` (steps that P removed), `noops`, `sequences` (explored paths that end), and `seconds`.
- The checker shrinks a failure to its shortest length. The report gives the property, the depth bound, P, the seed and the numbered steps. It also gives the rows before and after the last step, and a `--replay` command that reruns exactly those steps.
- The unit suite (`uv run pytest -q -m 'not integration'`) runs `tests/test_identity_ledger_check.py`. That file runs the default bound and all scratch breaks.

## Properties

Each property is a plain sentence, then the harm if it breaks, then the code that makes the promise.

**P1. Withheld until complete.** A source is served (state `current` and `revision == verified_revision`) exactly when its last accepted attempt completed as current, at that attempt's revision and description. Harm: retrieval serves facts from a pending, failed or half-written publication. Code: `begin` sets `pending` (storage.py:231). `fail` sets `failed` (storage.py:265). Only `complete` sets `verified_revision`, and only for the pending attempt at its revision (storage.py:348-366). Retrieval tests eligibility at retrieve.py:21.

**P2. Independent sources.** A step on one source never changes another source's row or recovery events. Harm: one source's failure or recovery withholds, resolves or corrupts an unrelated valid source. Code: every row and event query filters on dataset and source (storage.py:153, 236-240, 262, 270-275, 351-358, 376-379).

**P3. Stale calls are refused, and a refusal changes nothing.** A `begin()` with an expected revision other than the saved one is refused. A `complete()` or `fail()` for an attempt that ended, or that a later `begin()` replaced, is refused. A refused call leaves rows, events and the reservation unchanged. Harm: a writer that works from an old read overwrites newer intent, or a late acknowledgement marks the wrong attempt. Code: storage.py:153-156 (stale revision), 262-264 (stale fail), 352-366 (stale complete). A guard raises before the commit, so the session rolls back (storage.py:143-255).

**P4. One writer at a time.** At most one attempt is open, and the reservation owner is exactly that attempt, or no owner when no attempt is open. Harm: two writers interleave graph writes for overlapping intents. Code: `begin` takes the reservation only when no owner exists (storage.py:144-152). `fail` and `complete` release it only for their own attempt (storage.py:333-340, 367-374).

**P5. Recovery is explicit and forward.** These rules apply together:

- A revision never goes back.
- A revision goes up by exactly one, and only through a first publish or a replacement of a current row.
- A failed replacement resumes only through replace. A failed withdrawal resumes only through withdraw. A withdrawn source restarts only through withdraw.
- A failed row has exactly one unresolved recovery event. A pending row has at most one. A current or withdrawn row has none.
- Only the completing attempt resolves an event, and a resolved event stays resolved.

Harm: an operator loses track of an incident or sees two incidents for one failure. Or a method that does not own the saved intent rolls it back or replaces it. Code: storage.py:157-227 (method and revision guards), 233-252 (a recovery attempt links to the open event), 266-287 and 321-332 (fail reuses the open event), 375-392 (complete resolves it).

## What the checker runs (true to the code)

Each step below is one call sequence that the named caller makes. A step that the checker treats as indivisible is indivisible in the code, because each RecordStore call commits once or rolls back.

| Step label | Code it mirrors | RecordStore calls |
| --- | --- | --- |
| `Wn publish Sk rev=1 expect=0` | publish.py:298-304, first publication | `begin(method="publish")` |
| `Wn reconcile Sk rev=r expect=r` | publish.py:298-304 with a saved revision, the `reconcile` CLI | `begin(method="reconcile")` |
| `Wn replace Sk rev=r+1 expect=r` | replace.py:120-131, 213-219 | `begin(method="replace")` with a new replacement plan |
| `Wn replace Sk rev=r expect=r` | replace.py:100-118 retry | `begin(method="replace")` with the saved plan |
| `Wn withdraw Sk rev=r expect=r` | withdraw.py:47-90 | `begin(method="withdraw")`, with the saved plan on retry |
| `Wn complete` | publish.py:340 and 499, withdraw.py:217 | `assert_pending()` (not for withdraw), then `complete()`. If a call refuses, the caller's `fail()` runs (publish.py:503, replace.py:383, withdraw.py:225). A publish whose `assert_pending()` refuses stops with the reservation held, because publish.py:340 is outside the `try` block. |
| `Wn fail@stage` | the `except` blocks at publish.py:501, replace.py:379, withdraw.py:223 | `fail()` with `nodes`, `replace_saved` or `withdraw_contributions` |
| `Wn crash` | a hard crash (docs/SESSION_HANDOFF.md, "Constraints to preserve") | none. The writer keeps the reservation. |
| `Wn repeat` | a duplicated or delayed acknowledgement, for example the second `fail()` in replace.py:383 after `recovery_record_failed` | the writer's last `complete()` or `fail()` again |
| `reject Sk` | retrieve.py:88-91 | `fail(..., "retrieval_validation", ...)` with the attempt of the row as it was last seen current |

Read these modeling choices before you trust a result:

- **Stale reads.** A caller reads the row without the reservation and calls `begin()` later. So each writer may call `begin()` with arguments built from any row version that the source had earlier on the path.
- **Caller pre-checks.** The checker skips the caller pre-checks (publish.py:274-282, replace.py:88-125, withdraw.py:42-45). The reason is that `begin()` must hold on its own.
- **Stage names.** storage.py only copies `stage` into the event (storage.py:309-320). So the checker uses one fault stage per method. If storage.py begins to branch on `stage`, add each stage as a separate `Finish` step.
- **Descriptions.** A description is a function of source and revision. It is the fixture `tests/fixtures/identity/cognee_identity_source_example.json` with a new `identity_data_id` and `revision`.
- **Symmetry.** Writers that never began are interchangeable, and sources that never had a row are interchangeable. Only the first of each kind can take a first step.
- **No-op steps.** The checker checks a step that changes no row, event, reservation or checker state, but does not expand it. Every sequence after that step is also a sequence after its parent, and the search already covers the parent.
- **Store.** The store is in-memory SQLite through aiosqlite with `StaticPool` and `async_sessionmaker(expire_on_commit=False)`. Cognee uses the same session maker on a SQLite file with `NullPool`.

## Real bug or modeling error?

When the check fails on code that you did not mean to change, replay the reported sequence. Then decide:

1. Map each step to the caller in the step table. If no caller can make that call with those arguments, even from a stale read, the checker is wrong. Fix the checker (`intents()`, `candidates()` or `Harness.apply()`) and record why.
2. If a caller can make the call, read the property's code pointer. If the code no longer makes that promise on purpose, the property changed. Update the property in this file and in `check()`, and say so in the commit.
3. Otherwise the failure is a real bug. Report the minimal sequence in code terms. Do not weaken the property, and do not change product code unless the user asks.

A Python exception that is not a `Violation` (a traceback) is a checker error, not a property failure.

## Able to fail

`MUTANTS` in `support/ledger_check.py` holds scratch breaks of storage.py. `--mutants` applies each break to an in-memory copy of the file, so the working tree stays unchanged. Every break must be caught by the property named for it. If a break no longer matches storage.py, the run stops and names the break. Update the break text when you change the guarded code. These results are from depth 5, 2 sources and 2 writers on 2026-10-21:

| Break | Property | Shortest failing sequence |
| --- | --- | --- |
| `begin-keeps-state`: begin does not set `pending` on an existing row | P1 | publish S1, complete, reconcile S1 |
| `complete-skips-verified-revision` | P1 | publish S1, complete |
| `fail-keeps-state`: fail does not set `failed` | P1 | publish S1, complete, reject S1 |
| `begin-links-every-source`: recovery-attempt query without the source filter | P2 | publish S1, fail, publish S2 |
| `complete-resolves-every-source` | P2 | publish S1, fail, publish S2, complete |
| `no-stale-revision-guard` | P3 | publish S1, complete, publish S1 from the read before the row existed |
| `complete-ignores-attempt`: no attempt or pending filter in complete | P3 | publish S1, complete, repeat |
| `fail-ignores-attempt` | P3 | publish S1, complete, reconcile S1, reject S1 |
| `no-writer-reservation` | P4 | W1 publish S1, W2 publish S2 |
| `complete-keeps-reservation` | P4 | publish S1, complete |
| `fail-always-new-event`: fail never reuses the open event | P5 | publish S1, fail, reconcile S1, fail |
| `no-replace-recovery-choice`: reconcile may resume a failed replace | P5 | publish S1, complete, replace S1, fail, reconcile S1 |
| `no-withdrawn-guard` | P5 | publish S1, complete, withdraw S1, complete, reconcile S1 |

These breaks would not be caught, because no reachable sequence separates them from the real code. They are not in `MUTANTS`:

- Removing `Publication.revision == source.revision` from `complete()`. The attempt filter already binds the revision.
- Choosing the row by attempt in `fail()`. Attempt ids are unique per source.

## Findings at the sync commit

None. Every property holds in the exhaustive run at depth 8 with 2 sources and 2 writers. The sampled runs at depth 9 and 10 (P = 0.5) also pass. See Measurements.

These behaviors are allowed by the code and the checker accepts them. Read them before you add a property:

- Reconcile of a current row is accepted. It withholds the source until its attempt completes.
- Withdraw of a withdrawn row is accepted.
- The `pending_attempt` guard (storage.py:157-161) is unreachable in the model. A pending row always has its writer's reservation, unless a person clears the reservation by hand.

## Add an operation (next: group split or combination)

1. Read how the new caller builds its `begin()` arguments, which plan `operation` it saves, and which `complete()` state and `fail()` stages it uses.
2. Add a `Begin` intent for it in `intents()`. Build the arguments from a `view` the way the caller builds them from `rows()`. Add its method to `FAIL_STAGE` and `ACK_STAGE`.
3. If the method needs new handling in `Harness.apply()` (for example, no `assert_pending()` call or a new completion state), add a `case` that mirrors the caller line by line. Cite the lines.
4. If you add a guard for the operation to storage.py, add the rule to `check()` under the property it serves. Then add a break to `MUTANTS`. Run `--mutants` and make sure that the check catches the break.
5. Add the new file and functions to the coverage table, rerun the measurements, and move the sync commit.

## Scope

- **Checked:** every sequence up to depth 5 (pytest and default) or depth 8 (manual). The runs use 1 or 2 sources and 1 or 2 writers in one dataset. Revisions grow only as far as the depth allows.
- **Not checked:** graph and vector writes, `rows()` across datasets, text changes (`text_change` plans) and the CLI. Also not checked: more than two writers or sources, interleaving inside one RecordStore call, and SQLite or driver failures. Each RecordStore call runs to its end before the next step.
- **Copied, not called:** `served()` copies retrieve.py:21. If that line changes, change `served()`.

## Measurements

Measured on 2026-10-21 on the development Mac. P = 0, 2 writers, `seconds` excludes interpreter startup.

| Depth | 1 source: nodes / sequences / s | 2 sources: nodes / sequences / s |
| --- | --- | --- |
| 1 | 2 / 1 / 0.01 | 2 / 1 / 0.01 |
| 2 | 9 / 7 / 0.02 | 10 / 8 / 0.02 |
| 3 | 32 / 27 / 0.08 | 38 / 33 / 0.09 |
| 4 | 140 / 123 / 0.29 | 208 / 187 / 0.41 |
| 5 | 518 / 461 / 1.08 | 917 / 837 / 2.32 |
| 6 | 1725 / 1546 / 3.34 | 4638 / 4268 / 10.36 |
| 7 | 5752 / 5191 / 11.63 | 22378 / 20769 / 48.07 |
| 8 | 17677 / 16006 / 37.54 | 115652 / 107742 / 238.08 |

Sampled runs with 2 sources and 2 writers:

| Depth | P | Seed | Result | nodes / skipped / sequences / s |
| --- | --- | --- | --- | --- |
| 9 | 0.5 | 2 | PASS | 5551 / 5631 / 4793 / 11.92 |
| 9 | 0.5 | 5 | PASS | 5731 / 5676 / 5004 / 12.20 |
| 9 | 0.5 | 6 | PASS | 837 / 883 / 741 / 1.63 |
| 9 | 0.5 | 1, 3, 4, 7 | INCONCLUSIVE (first step skipped) | 1 / 1 / 1 / 0.00 |
| 10 | 0.5 | 2 | PASS | 7374 / 7421 / 6331 / 15.74 |
| 9 | 0.3 | 2 | stopped by hand after more than 10 minutes | none |

A checked state costs about 2.3 ms, mostly aiosqlite thread round trips. Each extra depth multiplies the states by about 4.5 with 2 sources. The default bound is depth 5 because the pytest file must stay well under 10 s. Depth 5 catches every break in `MUTANTS`.
