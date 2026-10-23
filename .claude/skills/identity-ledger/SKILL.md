---
name: identity-ledger
description: Bounded exhaustive check of the Stage 6 identity publication ledger (RecordStore in src/cognee_lab/identity/storage.py). Use it when a change touches RecordStore begin, fail, complete, assert_pending, rows or events. Also use it for changes to the writer reservation, recovery events or the retrieval eligibility test in retrieve.py. Use it when publish, replace, withdraw or a text change pass new arguments to RecordStore. Use it when a new maintenance operation (for example group split or combination) calls RecordStore.
---

# Identity ledger check

`support/ledger_check.py` drives the real `RecordStore` on a fresh in-memory SQLite store. It runs every sequence of ledger steps up to a depth bound, with two sources and two writers. After every step it checks seven properties:

- **P1. Withheld until complete.** A source is served exactly when its last accepted attempt completed as current, with that attempt's revision and description. A completed withdrawal or forget leaves the row in that state.
- **P2. Independent sources.** A step on one source never changes another source's row or recovery events.
- **P3. Stale calls are refused.** A stale expected revision, an acknowledgement for an ended or replaced attempt, or one for a description that was not begun, is refused. A refusal changes nothing.
- **P4. One writer at a time.** At most one attempt is open, and the reservation names exactly that attempt.
- **P5. Recovery is explicit and forward.** Revisions go up by one, only through a first publish, a replacement of a current row or a new publication of a forgotten row. Each method begins only on the row states its `Method` entry names. Only the method that owns a saved intent resumes it. A retry keeps the saved plan and description, except that an erasure retry of a failed replacement or publication begins with another description at the saved revision and adds the saved one to the plan's `erased_from`, which later retries keep, and each step of that chain is the erasure removal of the step before. No other begin names `erased_from`. Each failure has one recovery event, and only its completion resolves it, recording the completion state as its outcome (`restored` for current) and marking the last recovery attempt `verified`. No step removes an event, and no step changes a resolved event, except that completing a forget drops the messages of the forgotten source's events.
- **P6. Failed rows can recover.** From a failed row and a free reservation, the method that owns the saved plan, called with the saved arguments, is accepted and completes.
- **P7. A forgotten row holds no description content.** Its description is the tombstone of the description its forget began, its plan keeps only identifier fields with no edge property, and no recovery event of the source keeps a message.

Each property is a function `p1_...` to `p7_...` in `support/ledger_properties.py`; `ledger_check.py` holds the harness, the search and the report. The docstring of each function states the property. The harm of each break, the code that makes each promise, and all measurements are in [reference.md](reference.md).

## Does your change touch the checked code?

Run the check when your diff touches any of these.

| File | Function | What the checker depends on |
| --- | --- | --- |
| `storage.py` | `RecordStore.begin`, `fail`, `complete`, `assert_pending`, `rows`, `events`, the three tables, `TRANSITIONS`, `REQUIRED_PLANS`, `cell_for`, `admissible`, `erased_from`, `superseding_plan`, `erasure_chain`, `PublicationRow`, `scrubbed_plan` and `scrubbed_event`; `erasure_rules.check_retry_chain`, which `admissible` calls | All of it. The checker calls the six `RecordStore` methods and nothing else. It exercises the transition table only through `begin`, which consults `admissible` and `cell_for`, and it does not import the table. |
| `stages.py` | `run_attempt`, `saved_row` | The frame of replace, withdraw and forget: `begin`, the stages, `complete(state=...)` and the `fail` with its stage. |
| `retrieve.py` | `is_served`, `live_held`, `valid_sources` | The eligibility condition in `is_served`, copied as `served()`. Also the `fail()` call in `valid_sources` on a row whose own input fails the shared live-validation pass `live_held` (the `reject` step). Since checkpoint H (2026-10-23) only an own input's failure calls `fail()`; a foreign input's drift withholds decisions and calls no `RecordStore` method. |
| `publish.py` | `Publisher.publish`, `Publisher.reconcile`, `Publisher.readd`, `Publisher._publish`, `Publisher.superseded`, `Publisher._apply_pending` | The three entry points and the method and expected revision each passes to `begin()`, `assert_pending()` before the `try` block, and the `complete()` or `fail()` that ends the attempt. |
| `replace.py` | `replace`, `REPLACE` | The replacement arguments, the retry with the saved plan, the erasure retry that supersedes the saved description (`plan["erased_from"]`), `plan["text_change"]`, and the stages. The stages `withhold_dependents` and `withholding_cleanup` (checkpoint H) write only the withholding table in `withholding.py`, which is outside the six checked methods. |
| `withdraw.py` | `withdraw`, `WITHDRAW` | The withdrawal arguments, the reuse of a saved withdrawal plan, and the completion state `withdrawn`. |
| `forget.py` | `forget`, `FORGET` | The forget arguments, the rows it begins on (current, withdrawn, failed publication, failed forget), the reuse of a saved forget plan, the completion state `forgotten` and the tombstone its verification stage sets through `Run.completion`. The dependents' removal revisions after it go through `erasure.removal_writer`, by the row's `failed_attempt`: `replace_one`, `text_fixture.rebuild` or `finish_publication`; for a failed replacement, text change or publication the removal is an erasure retry. |
| `text_fixture.py` | `rebuild` (and `maintain_one` and `erasure.write_text_change`, which call it) | It calls `replace` with a `text_change`. The checker sends that plan shape. |
| `text_changes.py` | `TextChange` | Its fields, saved by `asdict()`. `TEXT_CHANGE` in the checker copies them. |
| `revisions.py` | `replace_one`, `finish_publication` | `replace_one` calls `replace` without a `text_change`; `finish_publication` calls `Publisher.reconcile`, an erasure retry when the description differs from the saved one. |

All paths are under `src/cognee_lab/identity/`. The test `test_served_copies_the_retrieval_eligibility_test` fails if the eligibility condition in `is_served` changes.

**Sync commit:** `ae64aed`. On 2026-10-23 (checkpoint I fix round 3) the assistant changed the checker with the code it describes: `admissible` and `replace` and `Publisher.superseded` share `storage.superseding_plan` for the `erased_from` a retry plans, which the model mirrors as `superseding_plan` in its reconcile and replace intents; `check_retry_chain` lost its `first` flag; `begin` reads every row only when `erasure_chain` says the chain check runs, which the new break `begin-reads-no-rows` (INCONCLUSIVE) covers. The break `supersede-drops-chain` moved from `DEEP_MUTANTS` to `MUTANTS`: depth 5 catches it through reconcile, as it already did at `cb5fd20`. A retry that names the saved description but begins with it unchanged is now refused as `recovery_plan` before the chain check, which refused it as `revision_reuse` before. `Publisher._publish` now retires what a superseded description wrote, with no new `RecordStore` call or argument. The step list is unchanged and `PINNED` stays at 8504 nodes and 8349 sequences. Before that, at `cb5fd20`, on 2026-10-23 (checkpoint I fix round 2) the assistant changed the checker with the code it describes: `admissible` now holds the description check and the next-revision check, keeps `erased_from` as a preserved field with one alternative (`RequiredPlan.supersedes`: the saved list plus the saved description), checks every step of the erasure-retry chain against the rows `begin` reads under the reservation (`erasure_rules.check_retry_chain`), refuses `erased_from` on any other begin, and admits reconcile's erasure retry of a failed publication. The model starts every sequence with a forgotten background source, makes variant 1 the erasure removal of variant 0, and adds a replace first attempt that writes variant 1, a misnamed supersede and reconcile's `erased_from` plans; P5 requires each chain step to be the removal (`ERASURE_STEP`). New breaks: `erasure-chain-unchecked`, `erasure-outside-retry` and `reconcile-never-supersedes`; `supersede-drops-chain` is now a P5 break at depth 7. `PINNED` moved to 8504 nodes and 8349 sequences. Before that, at `8b109d0`, on 2026-10-23 (checkpoint I fix round 1) the assistant changed the checker with the code it describes: `begin` lets a failed replacement's retry supersede the saved description when its plan's `erased_from` adds it (`supersedes`), which `Plan.erased`, `Method.supersedes`, the four new replace intents and P5 model, with `REACHABLE` gaining `erasure retry`. `PublicationRow` now parses a row once (`description` or `tombstone`), so the checker reads rows through `saved_json`, and `rows()` refuses a non-forgotten row whose description does not parse (`description_format`), which the checker reports as P1. The properties moved to `support/ledger_properties.py`. `PINNED` moved to 6431 nodes and 6300 sequences. Before that, at `1c782c1`, on 2026-10-23 (checkpoint I) the assistant changed the checker with the code it describes: `forget` begins on withdrawn and failed-publication rows (`METHODS` and `TRANSITIONS`), `complete` takes the forget's tombstone and scrubs the plan and the source's event messages, P5 allows that scrub, and P7 checks it. `forget.py` passes the tombstone through `Run.completion`; the dependents' removal revisions after the forget call `replace` through `replace_one`, a path the checker already sends. `PINNED` moved to 6287 nodes and 6156 sequences. Before that, at `3814515`, on 2026-10-23 (fix round 1) the assistant read the changes since `4681f60` to `retrieve.py`, `publish.py`, `replace.py`, `text_fixture.py` and `revisions.py`: `valid_sources` still calls `fail()` only for an own input's failure, with the eligibility line unchanged; `admit_inputs` gains a graph check that refuses before `begin()`; the stage `replace_dependents` is renamed `withhold_dependents`; and `maintain_one` now runs `replace_one`, an ordinary replacement without a text change, after its own attempt completes. No new `RecordStore` call or argument, and `PINNED` is unchanged. Before that, at `4681f60`, the assistant read the checkpoint H changes to `retrieve.py`, `publish.py`, `replace.py`, `text_changes.py`, `text_fixture.py` and `revisions.py` against `METHODS`: no new `RecordStore` call or argument, two replacement stages that write only the withholding table, and a `reject` step that now covers a narrower set of failures. The checker still describes the code, and `PINNED` is unchanged. Before that, at `82b954e` on 2026-10-22, the checker described the covered code after the no-behavior-change ledger refactor and its review fixes: the transition table, `cell_for()` and `admissible()` in `begin`, `begin`'s final check that a new revision is exactly the next one, the typed `PublicationRow`, and the stage runner in `stages.py`. To see whether the check needs another look, run this command:

```bash
git diff ae64aed -- src/cognee_lab/identity/{storage,stages,retrieve,publish,replace,withdraw,forget,text_fixture,text_changes,revisions,erasure_rules}.py
```

If the diff touches a function in the table, read the changed lines against `METHODS` and the intents functions in `support/ledger_model.py`. `METHODS` restates the transition table in the checker's own terms on purpose: the check must not read `TRANSITIONS`, or it would check the table against itself. Move the sync commit only after you read that the checker still describes the code. A passing check is not enough, because a passing check can describe old code.

## Run it

```bash
uv run python support/ledger_check.py                    # depth 5, about 15 s
uv run python support/ledger_check.py --depth 6          # about 95 s
uv run python support/ledger_check.py --depth 7          # about 3 minutes before fix round 2, longer since (not remeasured); depth 8 took about 15
uv run python support/ledger_check.py --mutants          # every scratch break, about 8 s
uv run python support/ledger_check.py --mutant withdrawn-guard-admits-replace --depth 7   # a deep break, FAIL P5, about 13 s
uv run pytest -q tests/test_identity_ledger_check.py     # default bound and every break, about 10 s
```

- The exit code is 0 for `PASS`, 1 for `FAIL` and 2 for `INCONCLUSIVE`.
- Only a `PASS` run with P = 0 prints `verified within bound`. A run with `--skip-probability P` prints `sampled (P=..., seed=...)`. The same seed gives the same search.
- `--skip-probability P` skips each candidate step at each node independently, the first step included. The skip removes the subtree under that step.
- `INCONCLUSIVE` means the search never reached one of the outcomes in `REACHABLE`. These are a row in each state, an accepted call of each step kind, a publish accepted on a forgotten row (the re-add), and a failed row that completes as current again. The report names the missing outcomes.
- The symmetry rule leaves one first step that `begin()` accepts, `W1 publish S1 rev=1`. At P = 0.5 about half the seeds skip it, and then the run reaches nothing and is `INCONCLUSIVE`. Use another seed.
- A `FAIL` report gives the property, a minimal sequence, the state before and after the last step, and a `--replay` command. `--replay` prints the rows, events and reservation after every step. It runs every step it names, also the steps after a step that changes nothing. It refuses `--skip-probability`.
- Labels name attempts by writer and count. `W1#2` is the second attempt that writer 1 began.
- The test pins the node and sequence counts of the default run. A change to the step list changes them. Update `PINNED` on purpose and say so in the commit.

## Real bug or modeling error?

When the check fails on code that you did not mean to change, replay the reported sequence. Then decide:

1. Map each step to its caller in `METHODS` (`support/ledger_model.py`). If no caller can make that call with those arguments, even from a stale read, the checker is wrong. Fix the intents function or `Harness.apply`, and record why.
2. Some steps send arguments that `begin()` or `assert_pending()` must refuse. The intents functions name them. A failure on such a step is a missing guard, not a modeling error.
3. If a caller can make the call, read the property's code pointer in reference.md. If the code changed that promise on purpose, update the property function and reference.md. Say so in the commit.
4. Otherwise the failure is a real bug. Report the minimal sequence in code terms. Do not weaken the property. Do not change product code unless the user asks.

A traceback that is not a property failure is a checker error.

## Add an operation

Group split and group combination reach the store as the text-change path. `maintain_one` in `text_fixture.py` calls `replace` with a `text_change`. That reaches the store as method `replace` with `plan["text_change"]`. The checker sends it as `plan=text<rN` with `TEXT_CHANGE`, and a regrouping map as `plan=regroup<rN` with `TEXT_REGROUP`. Both hold the one `occurrence_map` field that `TextChange` saves. `storage.py` never reads the map, so neither combination nor the general occurrence map needed a model change, and `PINNED` stayed at 3828 nodes and 3717 sequences. `Plan.change` is `None`, `"text"` or `"regroup"`, and `TEXT_CHANGES` maps each name to its dict.

A later operation of the same shape needs one change in `support/ledger_model.py`. Add its `text_change` dict to `TEXT_CHANGES` under a new name and add the name to `Plan.change`. The tag prefix, `Plan.as_dict`, `Plan.of`, the new-plan loop and the retry swaps all follow `TEXT_CHANGES`. A new field in `TextChange` goes into every dict there, because `asdict(TextChange)` saves all fields. If the operation adds a plan field that storage.py reads, add the field to `Plan` too. The step list changes, so update `PINNED`.

The model has one attempt per writer, and `--sources` accepts only 1 or 2. An operation that writes more than one source in one attempt needs more than a change to `op_source()` and P2. It needs a new attempt shape in `Attempt` and `Harness.apply`, and a higher `--sources` limit in `parse()`.

For any other operation, follow every step. Steps 1 to 3 change `support/ledger_model.py`, and steps 4 to 6 change `support/ledger_check.py`.

1. Write an intents function. Build each `Begin` from a `View` the way the caller builds it from `rows()`. Add the arguments that `begin()` must refuse.
2. Add a `Method` to `METHODS`. Set every field, with a comment that names the caller.
3. If the plan has a new shape, extend `Plan`. Change `operation`, `tag`, `as_dict` and `of`.
4. `Harness.apply` reads the table. Add a `case` only if the caller's calls differ from begin, optional `assert_pending`, then `complete` or `fail`.
5. P5 (`begin_rules`) reads `begins`, `recovers`, `owns_recovery`, `owns_terminal` (through `Method.owns`), `requires_plan` and `preserved_on_retry`. P6 reads `recovers`. `REACHABLE` adds the new method.
6. If the operation writes more than one source, read the paragraph above the steps.
7. In storage.py, add the method to the `TRANSITIONS` entries that admit it, with its revision step, and to `REQUIRED_PLANS` if it needs a plan of its own, with the plan fields a retry keeps in `preserved`. An entry for a saved row that admits a method at the next revision needs a `sequence` refusal; `tests/test_identity_storage.py` checks this and that every entry answers every method. For each new entry or guard, add a break to `MUTANTS` in `support/ledger_mutants.py`. Run `--mutants`. If only a deeper search catches the break, add it to `DEEP_MUTANTS` and its sequence to `DEEP_SEQUENCES` in the test file.
8. Update the coverage table, `PINNED`, reference.md and the sync commit.

## Scope

- **Checked:** every sequence up to depth 5 (default and pytest). Depth 5 catches every break in `MUTANTS`. It does not catch the breaks in `DEEP_MUTANTS`. Manual runs passed up to depth 8 on 2026-10-21. The runs use 1 or 2 sources and 1 or 2 writers in one dataset.
- **Not checked:** graph and vector writes, `rows()` across datasets, the CLI, more than two writers or sources, and SQLite or driver failures. Each RecordStore call runs to its end before the next step.
- **Modeling choices:** these are in reference.md. They cover stale reads, skipped caller pre-checks, missing rows, one fault stage per method, descriptions, symmetry and no-op steps.
