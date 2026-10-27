# Stage 6: the conformance check of the IDENTITY search

**Guide scope:** the conformance fixture built from DOC01, the check that scores `IDENTITY` searches on it against the Stage 5.3 benchmarks, its committed baseline and its gate. What a search returns and refuses is in the [IDENTITY search guide](stage6_identity_public_search.md). For project status, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

Added on 2026-10-26 in step 5 S1. The assistant's subagent built it and ran it on the user's Mac with loopback embeddings. The values below are from those runs.

## What it is

`conformance-fixture` builds a root from DOC01 (`data/DOC01_helios1_technical_overview_v2.md`) through the lab's `add` and `cognify`. Its describer (`src/cognee_lab/identity/conformance_fixture.py`) reads only DOC01's text and native chunks. `support/conformance_check.py` searches the root through `cognee.search` with `IDENTITY` and scores the results against the Stage 5.3 traversal and query-resolution benchmarks and the Helios manifest in `data/hidden`. The check is the only reader of `data/hidden`. The unit test `test_no_src_module_reads_the_hidden_benchmark_data` fails when a module under `src/` names it.

The describer's rules and its table of references were written by an author who had read those answers. The check therefore measures whether the search serves a fixed description the way the benchmarks expect, and it gates retrieval changes against a baseline. It is a conformance check. It does not evaluate Describe, and its numbers say nothing about extraction quality.

## The describer

- **Names.** Four rules give the reusable Entities and their variants, all scoped to DOC01:
  1. An abbreviation definition, `long form (ABBR)` where ABBR is the initials of the last words, gives both names, with ABBR a variant of the long form.
  2. A defined long form followed by "System" is a variant of the long form, for example `Neutral Beam Injection System`.
  3. A run of two or more capitalized words that does not start a sentence is a name, for example `Aurora Reconstruction Suite` and `Campaign A`.
  4. The alias statement `generally uses “Helios-1.”` makes each quoted name before the `, where` qualifier of the next sentence a variant: `Helios 1` and `H-1`. `Helios` and `the machine` come after the qualifier and are not names.
- **References.** Eleven hand-read groups (`REFERENCES`), each resolved to the Entity that its paragraph names, or inside a quotation to the one that the introducing sentence names. Examples are `The controller; It` to the Vertical Control System, `Aurora; The suite; It` to the Aurora Reconstruction Suite and `The machine` to Helios-1.
- **Facts.** In each sentence of the body, and in each table row, the first named reusable Entity or reference group is the subject. Each other named Entity outside the subject's identity group, and each quantity with a unit (`m`, `s`, `T`, `MW`, `kHz`, `MA` or `%`), is stated with it. The relation is `stated_with`, the fact text is the sentence, and the evidence is the chunks that the sentence overlaps. A subject and target pair keeps its first sentence.

On DOC01 at the default chunk budget of 512, the describer gives 23 reusable Entities, 12 variant assignments, 11 reference groups with 11 accepted resolutions, 29 facts and 10 chunks.

## The measures

A case passes, fails, or is unobserved when no search result decides it.

| Measure | Cases |
|---|---|
| `fact_recall` | Each manifest fact that DOC01 states (F001 to F016, T001, T003). The query `<subject> <predicate>` returns, in the default top 5, a fact whose text holds the object's words or the value with its unit. |
| `closure_symmetry` | Each traversal identity case (TRV01 to TRV06). Every member's name as the query returns the same nonempty set of facts, with top 100. |
| `mentions` | TRV07 and TRV08 at their chunk coordinates, and the manifest's DOC01 resolutions ER001 to ER009. A mention-anchored fact covering the span is served under the expected referent. |
| `negative_controls` | AFRL never resolves the Aurora Reconstruction Suite and the reverse, TRV08 is never served under the Vertical Control System, the referent of TRV07, the resolved case at the same surface in the same chunk, each hard negative of ER002, ER005 and ER007 is never served under the wrong referent, and QRY05 resolves nothing. |
| `query_resolution` | QRY01 and QRY02 resolve to their group. QRY03 and QRY04 are an accepted gap: they pass when they resolve no wrong group. |

Over every result the check also counts repeated edge IDs, evidence or identity records outside DOC01's own chunks and source, and fact endpoints that are not Entities, or a mention as a target, or a mention subject with no identity record. These three counts must stay 0. It reports logical duplicates, the same fact through two members of one identity group, and does not gate them.

## The baseline

`support/conformance_baseline.json` holds every case with its measure and its outcome (`passed`, `unobserved` or `failed`), the counts, and for each case that does not pass its `gap`, the reason it does not pass. The baseline is the only record of the gaps. The check made 54 searches and took about 15 s with the fixture. Measured on 2026-10-26:

| Measure | Passed | Failed | Unobserved |
|---|---:|---:|---:|
| `fact_recall` | 10 | 8 | 0 |
| `closure_symmetry` | 5 | 0 | 1 |
| `mentions` | 9 | 0 | 2 |
| `negative_controls` | 6 | 1 | 1 |
| `query_resolution` | 4 | 0 | 0 |

Repeated edge IDs, attribution violations and leakage violations were 0. Logical duplicates were 7, for example `8 MW` stated with both `neutral beam injection` and `Neutral Beam Injection System` in one result.

The cases that do not pass, each with its gap in the baseline:

- Failed: recall F008, F010 to F016, and QRY05. QRY05 is the retrieval limit: with no name match the search seeds the top `Entity_name` vector hit, so the ambiguous query resolves to an arbitrary group (`RCM` under loopback embeddings). Seeding improvements are later work, measured against this baseline.
- Unobserved: closure TRV05, TRV08 and its control, and ER001.

What the passes do not show:

- Recall matches words, not predicates. F009 passes on `the probe array is not treated as an independent direct measurement of total plasma current`, which holds the object inside a negation.
- QRY04 passes because its words contain the full name `edge density controller`, which seeds by name. The search does no contextual resolution. QRY03 resolves nothing.
- The mention passes come from the hand-read table. They show that the search serves a mention-anchored fact under its referent, not that anything resolved the mention.

## The gate

The check owns the ratchet. It exits 1 when a case does worse than on the baseline (passed, then unobserved, then failed), when a case appears or disappears, when a gated count grows, and when a case does better than on the baseline. On an improvement it prints `baseline is stale, rerun with --write-baseline`. Journey B1 checks only the exit status. On 2026-10-26 a scratch break that turned off variant expansion in `retrieve.py` made the check fail seven cases: five closures, F009 and T003.

`--write-baseline` makes a new root (it refuses `--root`), prints how the run moved from the old baseline, and then writes the new baseline, carrying each gap from the old one. It refuses, and writes nothing, when a case that does not pass has no gap, when a case that passes still has one, or when a gated count is not 0. To record a gap, or delete one, edit the `gap` of that case in the baseline and run `--write-baseline` again. For a case that is new to the baseline, add an entry that holds only its `gap`.

Run it for a change to retrieval (`retrieve.py`, `settled.py`, `search.py`), to the conformance fixture, or to the fact writers in `fixture.py`. It is a local check and journey B1, not part of CI.

```bash
uv run python support/conformance_check.py
uv run python support/conformance_check.py --root <conformance root> --json
uv run python support/conformance_check.py --write-baseline
uv run python -m cognee_lab.identity conformance-fixture --root <new dir> --embedding loopback
```

Without `--root` the check makes a new root under `outputs/conformance/`. A conformance root takes `status`, `retrieve` and `search`. The argument parser refuses every other command.
