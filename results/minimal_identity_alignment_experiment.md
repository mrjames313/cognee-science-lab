# Minimal identity framework: the alignment experiment

Run by the assistant on the user's Mac on 2026-10-31, at the user's request. It used Cognee 1.6.2, Claude Haiku 5.5 (`claude-haiku-5-5`) for extraction, and the embedding model that `.env` names, whose name and dimension count every root's `stage6-fixture.json` records.

It answers open question 7 of [the minimal identity framework](../docs/minimal_identity_framework.md): does the spelling hint earn its place, and how should alignment find a cognify spelling that is not an exact match? It also times Shape 1v's in-memory view, and checks four Cognee behaviours (CB11, CB16, CB17, CB20) that the design had read in the source but never run.

The harness is [`scripts/align_experiment.py`](../scripts/align_experiment.py). The raw roots are under `outputs/minimal-align-20261031-1256/`, which is not committed. Every table below comes from `report` on that directory, and the last section reproduces its whole output.

## Method

**Corpus and description.**
- **The documents.** DOC01 and DOC02 of the Helios corpus (`data/DOC01_helios1_technical_overview.md`, `data/DOC02_campaign_A_high_current.md`). Cognee's chunker made 2 chunks of each.
- **The describer.** The lab's rule describer, `reusable_names` in `src/cognee_lab/identity/conformance_fixture.py`, run over each document's stored text. It gives 20 distinct names across the two documents, in 10 variant groups. Its author had read the conformance answers, so it is a fixed description, not a test of Describe.

**Conditions.** Seven fresh isolated roots:
- three with the spelling hint, `hint-1` to `hint-3`;
- four without it, `nohint-1` to `nohint-3` and `checks`. `checks` was measured first and then used for the behaviour checks.

Each root adds DOC01, cognifies it, then does the same for DOC02. With the hint, cognify gets Cognee's configured graph prompt plus a section listing that document's names.

**Alignment.** `align()` runs the framework's rules (section 9.3) on each of the 20 names:
1. **Exact.** The node at `Entity.id_for(name)`.
2. **Lexical.** The other Entities that a chunk of the name's documents `contains` and whose name matches, unless their name, base or parenthetical belongs to another group. A name matches when it equals a group name, or when it equals one once a trailing parenthetical is stripped, or when its parenthetical does. So `magnetic probe array (mpa)` matches `magnetic probe array` and `mpa`. A group member's own exact node is excluded, because it aligns under its own name.
3. **Support.** Every candidate is support-checked. A `contains` chunk must hold, as a whole word, a name of the group or the candidate's base or parenthetical.

The outcome is `exact`, `lexical`, `unsupported` (candidates, none supported) or `unaligned` (no candidate).

**Vector ranking.** For each name, `vector_ranks()` records where the lexical nodes and the group's own nodes rank in the top 100 `Entity_name` hits, and the best hit that is neither.

**Planted links.** A planted link joins a chunk to the exact node of a described name, where the chunk's text holds no name of that group. The whole-word test counts a paraphrase such as "the reconstruction" as planted too.

**The view.** Cognee's `get_memory_fragment` projects the whole graph. Each name's aligned nodes (its exact node, or its lexical nodes when the outcome is `lexical`) have their own non-structural edges copied once onto the other aligned members of the group, and the result is deep-copied once. The ownership filter that Appendix B of the framework requires is not applied, so this times projection, overlay copy and clone only.

**Checks.** These ran on the `checks` root, after its measurement was written:
1. A hinted `cognee.update` of DOC01 to its v2 text.
2. `cognee.forget(memory_only=True)` of DOC02, then a plain cognify.
3. The default `cognee.prune.prune_system()`, then a plain cognify.

**Cost.** 106 LLM calls, counted at Cognee's `LLMGateway`:
- 63 for the seven roots, 9 each: one connectivity call, then 2 graph extractions and 2 summaries per document;
- 8 more for the checks;
- 9 for a smoke run whose root was deleted;
- 26 for two earlier attempts at a checks root, which are superseded and not used. The first attempt (9 calls) stopped at a harness bug, because `cognee.update` rejects an open file handle. The second (17 calls) ran its checks on the measured root itself and lost the measurement.

`analyze` re-measured the earlier roots with the final rules, which costs embedding calls only.

## Results

### Alignment outcomes

| Run | Hint | exact | lexical | unsupported | unaligned | Planted links (names) | Entities |
|---|---|---|---|---|---|---|---|
| hint-1 | yes | 20 | 0 | 0 | 0 | 7 (7) | 50 |
| hint-2 | yes | 20 | 0 | 0 | 0 | 8 (7) | 38 |
| hint-3 | yes | 17 | 0 | 3 | 0 | 7 (7) | 40 |
| nohint-1 | no | 15 | 0 | 0 | 5 | 0 (0) | 43 |
| nohint-2 | no | 14 | 0 | 0 | 6 | 0 (0) | 42 |
| nohint-3 | no | 8 | 11 | 0 | 1 | 0 (0) | 38 |
| checks | no | 13 | 0 | 0 | 7 | 0 (0) | 42 |

**With the hint.**
- **Exact alignment.** Every name aligned `exact` in two runs, and 17 of 20 in the third.
- **Where the planted links land.** The hint goes with every chunk, and in every run the model linked 7 names to chunks whose text holds none of the group's names as a whole word. A paraphrase counts as planted, so some of these links may be real. `aurora reconstruction suite` is planted in every run, and DOC01's second chunk refers to it nearby. All of those links are on DOC01's second chunk, apart from one on DOC02's second chunk in `hint-2`.
- **The 3 `unsupported` names in `hint-3`.** `mpa`, `pcps` and `rcm` had nodes there, but only on the planted chunk, so the support check rejected them. Their long forms aligned `exact`, so each group still had a node.

**Without the hint.**
- **Every `unaligned` name was an abbreviation cognify never extracted,** in the three runs whose graphs survive. The Entity names of `nohint-1`, `nohint-2` and `nohint-3` contain no node for them. Nearby names exist, such as `rcm plasma current estimate`. The `checks` root's graph was pruned by its checks, so its 7 cannot be inspected. Its group's long form aligned `exact`, so no group lost its node.
- **In `nohint-3`, cognify named the long forms with the abbreviation in parentheses.** The lexical pass aligned all 11 such names, each supported, and admitted nothing outside a group.

Across all seven runs, every group had at least one aligned node.

### The vector index does not find what the lexical pass finds

There are 33 names not aligned `exact` across the runs. For 27 of them, the top `Entity_name` hit was a wrong Entity, at distances 0.059 to 0.165. For 3, it was the name's own exact node, which failed the support check: `mpa`, `pcps` and `rcm`, in `hint-3`. For the last 3, it was a group member: `electron cyclotron heating system`, `neutral beam injection system` and `rogowski current monitor`, in `nohint-3`.

- **Where the right nodes ranked.** The 11 lexically aligned names map onto 7 distinct nodes, which ranked 2nd to 37th, at distances 0.247 to 0.478.
- **Where the wrong hits sat.** The best wrong hit for each name sat at 0.059 to 0.258. It ranked first for 27 names and lower for the other 6.
- **What a threshold would do.** A threshold that admitted the nearest lexical node, at 0.247, would also admit a wrong Entity for 32 of the 33 names, all except `electron cyclotron heating system`.
- **One example.** For `mpa`, `energy confinement` ranked first at 0.078, and `magnetic probe array (mpa)` ranked 30th at 0.351.

### The view

| Run | Nodes | Projected edges | Overlay edges | Project (s) | Overlay (s) | Clone (s) |
|---|---|---|---|---|---|---|
| hint-1 | 78 | 163 | 11 | 0.0049 | 0.0001 | 0.0053 |
| hint-2 | 63 | 134 | 7 | 0.005 | 0.0001 | 0.0039 |
| hint-3 | 68 | 162 | 24 | 0.0051 | 0.0003 | 0.0051 |
| nohint-1 | 73 | 162 | 21 | 0.0037 | 0.0001 | 0.0029 |
| nohint-2 | 69 | 158 | 17 | 0.0066 | 0.0002 | 0.0048 |
| nohint-3 | 68 | 145 | 19 | 0.0037 | 0.0002 | 0.0038 |

Projection, overlay copy and clone together take under 15 ms on graphs of 63 to 78 nodes. The overlay copies only the nodes each name aligned to. The `checks` root is left out, because its view was timed before that rule was fixed and its graph can no longer be re-measured. The ownership filter is not timed, and these graphs are far smaller than a real dataset. So the numbers show the route works, not what it costs at scale.

### The Cognee behaviour checks

| Behaviour | Observed | Matches the design |
|---|---|---|
| CB11. A cognify right after one add processes only the new document. | DOC02's cognify made 4 calls, for its 2 chunks only, in every root. | Yes |
| CB20. The custom prompt goes with every extraction call and no summary call. | 2 of the 4 calls per document were hinted, and 2 were `KnowledgeGraph` extractions. The harness counts the two separately, so that the hinted calls are the extractions is inferred, consistent with the source. | Yes |
| CB20. A hinted update takes the full rebuild. | `status: full_rebuild`, `fallback.reason: custom_extraction_config`. Data ID kept, `raw_content_hash` changed. 4 calls, 2 of them hinted. | Yes |
| CB17. A memory-only forget keeps the Data row and clears its mark. | Row kept and its mark cleared. DOC02's document node gone, DOC01's kept. A plain cognify made 4 calls and restored DOC02's node and mark. | Yes |
| CB16. The default prune keeps Data rows and their marks. | 2 rows kept, both still marked processed, graph empty. A plain cognify then made 0 calls and the graph stayed at 0 nodes. | Yes |

## What it means for the design

1. **Replace vector similarity with the lexical pass.** With this embedding model, a vector pass would serve a wrong Entity's facts for 27 of 33 names that did not align exactly, and no threshold separates right from wrong. The lexical pass is deterministic, needs no threshold, and aligned every `Name (ABBR)` node cognify made in these runs.
2. **The spelling hint does not earn its place here.** With exact and lexical alignment, the runs without the hint left no group without a node. On this corpus the hint linked names to chunks that do not name them in every run, and in one run those were a name's only links. It also costs:
   - a copy of Cognee's prompt to maintain;
   - one cognify per document;
   - a writer policy.

   The recommendation is to build without it. This rests on two documents and one variant pattern, `Name (ABBR)`.
3. **A vector fallback for the seed is unsupported by this data.** The measured queries were the described names themselves, and their nearest hit was usually wrong. Queries outside the described names were not run, so the framework drops the fallback until a project measures one on its own queries.
4. **The in-memory view route is cheap at this size.** It needs timing with the ownership filter on a real dataset.
5. **CB11, CB16, CB17 and CB20 hold in practice.**

## Limits

- **A small corpus.** Two documents, four chunks, one extraction model, one embedding model and one rule describer.
- **Thin repetition.** Three hinted and four unhinted runs show the effects, but cannot estimate rates tightly.
- **The vector verdict is specific to these models.** It holds for the configured embedding model and these short technical names.
- **Facts are unmeasured.** Nobody checked whether the model extracted facts on planted links.
- **The `checks` root.** Its graph was pruned by the checks after its measurement, so its Entity names cannot be inspected afterwards.

## The full `report` output

`uv run python scripts/align_experiment.py report outputs/minimal-align-20261031-1256` prints the tables above and these details. The random `data_id`, `dataset_id` and `pipeline_run_id` values are left out of the checks output here.

| Run | Hint | exact | lexical | unsupported | unaligned | Planted links (names) | Entities | LLM calls (hinted) |
|---|---|---|---|---|---|---|---|---|
| checks | no | 13 | 0 | 0 | 7 | 0 (0) | 42 | 9 (0) |
| hint-1 | yes | 20 | 0 | 0 | 0 | 7 (7) | 50 | 9 (4) |
| hint-2 | yes | 20 | 0 | 0 | 0 | 8 (7) | 38 | 9 (4) |
| hint-3 | yes | 17 | 0 | 3 | 0 | 7 (7) | 40 | 9 (4) |
| nohint-1 | no | 15 | 0 | 0 | 5 | 0 (0) | 43 | 9 (0) |
| nohint-2 | no | 14 | 0 | 0 | 6 | 0 (0) | 42 | 9 (0) |
| nohint-3 | no | 8 | 11 | 0 | 1 | 0 (0) | 38 | 9 (0) |

Names not aligned `exact`, by run.

| Run | Name | Outcome | Lexical node | Its vector rank and distance | Top hit (kind) | Best wrong hit | Best in-group hit |
|---|---|---|---|---|---|---|---|
| checks | afrl | unaligned | - | - | - | rcm, rank 1 at 0.0947 | aurora fusion research laboratory, rank 15 at 0.2253 |
| checks | ech | unaligned | - | - | - | rcm, rank 1 at 0.0782 | electron cyclotron heating, rank 16 at 0.2306 |
| checks | edc | unaligned | - | - | - | rcm, rank 1 at 0.1247 | edge density controller, rank 10 at 0.2113 |
| checks | mpa | unaligned | - | - | - | energy confinement, rank 1 at 0.0784 | magnetic probe array, rank 14 at 0.1909 |
| checks | nbi | unaligned | - | - | - | energy confinement, rank 1 at 0.0908 | neutral beam injection, rank 9 at 0.1394 |
| checks | pcps | unaligned | - | - | - | rcm, rank 1 at 0.0926 | plasma current power supply, rank 11 at 0.1873 |
| checks | vcs | unaligned | - | - | - | energy confinement, rank 1 at 0.0848 | vertical control system, rank 6 at 0.1257 |
| hint-3 | mpa | unsupported | - | - | mpa, rank 1 at 0.0 (exact) | vcs, rank 2 at 0.0589 | magnetic probe array, rank 19 at 0.1909 |
| hint-3 | pcps | unsupported | - | - | pcps, rank 1 at -0.0 (exact) | rcm, rank 2 at 0.0926 | plasma current power supply, rank 15 at 0.1873 |
| hint-3 | rcm | unsupported | - | - | rcm, rank 1 at -0.0 (exact) | ech, rank 2 at 0.0782 | rogowski current monitor, rank 21 at 0.1969 |
| nohint-1 | afrl | unaligned | - | - | vcs, rank 1 at 0.086 (wrong) | vcs, rank 1 at 0.086 | aurora fusion research laboratory, rank 17 at 0.2253 |
| nohint-1 | ech | unaligned | - | - | rcm, rank 1 at 0.0782 (wrong) | rcm, rank 1 at 0.0782 | electron cyclotron heating, rank 18 at 0.2306 |
| nohint-1 | mpa | unaligned | - | - | vcs, rank 1 at 0.0589 (wrong) | vcs, rank 1 at 0.0589 | magnetic probe array, rank 16 at 0.1909 |
| nohint-1 | nbi | unaligned | - | - | vcs, rank 1 at 0.0661 (wrong) | vcs, rank 1 at 0.0661 | neutral beam injection, rank 10 at 0.1394 |
| nohint-1 | pcps | unaligned | - | - | rcm, rank 1 at 0.0926 (wrong) | rcm, rank 1 at 0.0926 | plasma current power supply, rank 12 at 0.1873 |
| nohint-2 | afrl | unaligned | - | - | vcs, rank 1 at 0.086 (wrong) | vcs, rank 1 at 0.086 | aurora fusion research laboratory, rank 15 at 0.2253 |
| nohint-2 | ech | unaligned | - | - | vcs, rank 1 at 0.086 (wrong) | vcs, rank 1 at 0.086 | electron cyclotron heating, rank 16 at 0.2306 |
| nohint-2 | mpa | unaligned | - | - | vcs, rank 1 at 0.0589 (wrong) | vcs, rank 1 at 0.0589 | magnetic probe array, rank 13 at 0.1909 |
| nohint-2 | nbi | unaligned | - | - | vcs, rank 1 at 0.0661 (wrong) | vcs, rank 1 at 0.0661 | neutral beam injection, rank 8 at 0.1394 |
| nohint-2 | pcps | unaligned | - | - | vcs, rank 1 at 0.1019 (wrong) | vcs, rank 1 at 0.1019 | plasma current power supply, rank 10 at 0.1873 |
| nohint-2 | rcm | unaligned | - | - | edge reflectometer, rank 1 at 0.0875 (wrong) | edge reflectometer, rank 1 at 0.0875 | rogowski current monitor, rank 14 at 0.1969 |
| nohint-3 | afrl | unaligned | - | - | rcm, rank 1 at 0.0947 (wrong) | rcm, rank 1 at 0.0947 | aurora fusion research laboratory, rank 11 at 0.2253 |
| nohint-3 | ech | lexical | electron cyclotron heating system (ech) (supported) | 27 at 0.3566 | rcm, rank 1 at 0.0782 (wrong) | rcm, rank 1 at 0.0782 | electron cyclotron heating, rank 11 at 0.2306 |
| nohint-3 | edc | lexical | edge density controller (edc) (supported) | 34 at 0.423 | rcm, rank 1 at 0.1247 (wrong) | rcm, rank 1 at 0.1247 | edge density controller, rank 9 at 0.2113 |
| nohint-3 | electron cyclotron heating system | lexical | electron cyclotron heating system (ech) (supported) | 2 at 0.2467 | electron cyclotron heating, rank 1 at 0.0618 (group) | energy confinement, rank 3 at 0.2584 | electron cyclotron heating, rank 1 at 0.0618 |
| nohint-3 | magnetic probe array | lexical | magnetic probe array (mpa) (supported) | 11 at 0.2703 | aurora magnetic reconstruction, rank 1 at 0.1654 (wrong) | aurora magnetic reconstruction, rank 1 at 0.1654 | - |
| nohint-3 | mpa | lexical | magnetic probe array (mpa) (supported) | 30 at 0.3508 | energy confinement, rank 1 at 0.0784 (wrong) | energy confinement, rank 1 at 0.0784 | - |
| nohint-3 | nbi | lexical | neutral beam injection system (nbi) (supported) | 33 at 0.401 | energy confinement, rank 1 at 0.0908 (wrong) | energy confinement, rank 1 at 0.0908 | neutral beam injection, rank 8 at 0.1394 |
| nohint-3 | neutral beam injection system | lexical | neutral beam injection system (nbi) (supported) | 22 at 0.3619 | neutral beam injection, rank 1 at 0.0379 (group) | vertical control system, rank 2 at 0.1469 | neutral beam injection, rank 1 at 0.0379 |
| nohint-3 | pcps | lexical | plasma current power supply (pcps) (supported) | 33 at 0.3876 | rcm, rank 1 at 0.0926 (wrong) | rcm, rank 1 at 0.0926 | - |
| nohint-3 | plasma current power supply | lexical | plasma current power supply (pcps) (supported) | 19 at 0.3253 | rcm, rank 1 at 0.1604 (wrong) | rcm, rank 1 at 0.1604 | - |
| nohint-3 | rogowski current monitor | lexical | rogowski current monitor (rcm) (supported) | 25 at 0.3846 | rcm, rank 1 at 0.1969 (group) | energy confinement, rank 2 at 0.2022 | rcm, rank 1 at 0.1969 |
| nohint-3 | vcs | lexical | vertical control system (vcs) (supported) | 37 at 0.4784 | energy confinement, rank 1 at 0.0848 (wrong) | energy confinement, rank 1 at 0.0848 | vertical control system, rank 6 at 0.1257 |

Planted links: a chunk linked to an exact node of a described name whose text holds no name of its group.

| Run | Name | Document | Chunk index |
|---|---|---|---|
| hint-1 | aurora reconstruction suite | doc01 | 1 |
| hint-1 | magnetic probe array | doc01 | 1 |
| hint-1 | mpa | doc01 | 1 |
| hint-1 | pcps | doc01 | 1 |
| hint-1 | plasma current power supply | doc01 | 1 |
| hint-1 | rcm | doc01 | 1 |
| hint-1 | rogowski current monitor | doc01 | 1 |
| hint-2 | aurora reconstruction suite | doc01 | 1 |
| hint-2 | aurora reconstruction suite | doc02 | 1 |
| hint-2 | magnetic probe array | doc01 | 1 |
| hint-2 | mpa | doc01 | 1 |
| hint-2 | pcps | doc01 | 1 |
| hint-2 | plasma current power supply | doc01 | 1 |
| hint-2 | rcm | doc01 | 1 |
| hint-2 | rogowski current monitor | doc01 | 1 |
| hint-3 | aurora reconstruction suite | doc01 | 1 |
| hint-3 | magnetic probe array | doc01 | 1 |
| hint-3 | mpa | doc01 | 1 |
| hint-3 | pcps | doc01 | 1 |
| hint-3 | plasma current power supply | doc01 | 1 |
| hint-3 | rcm | doc01 | 1 |
| hint-3 | rogowski current monitor | doc01 | 1 |

| Run | Nodes | Projected edges | Overlay edges | Project (s) | Overlay (s) | Clone (s) |
|---|---|---|---|---|---|---|
| hint-1 | 78 | 163 | 11 | 0.0049 | 0.0001 | 0.0053 |
| hint-2 | 63 | 134 | 7 | 0.005 | 0.0001 | 0.0039 |
| hint-3 | 68 | 162 | 24 | 0.0051 | 0.0003 | 0.0051 |
| nohint-1 | 73 | 162 | 21 | 0.0037 | 0.0001 | 0.0029 |
| nohint-2 | 69 | 158 | 17 | 0.0066 | 0.0002 | 0.0048 |
| nohint-3 | 68 | 145 | 19 | 0.0037 | 0.0002 | 0.0038 |

Behaviour checks in checks.

```
{
 "hinted_update": {
  "result": {
   "status": "full_rebuild",
   "regions": null,
   "deleted_chunks": null,
   "added_chunks": null,
   "reused_chunks": null,
   "kept_chunks": null,
   "reindexed_chunks": null,
   "total_chunks": null,
   "duration_seconds": 16.404,
   "fallback": {
    "reason": "custom_extraction_config",
    "detail": "chunk-level update supports only the default graph model and prompt"
   },
   "error": null
  },
  "data_id_kept": true,
  "hash_changed": true,
  "calls": {
   "total": 4,
   "by_model": {
    "KnowledgeGraph": 2,
    "SummarizedContent": 2
   },
   "hinted": 2,
   "distinct_prompts": 2
  }
 },
 "memory_only_forget": {
  "data_row_kept": true,
  "processed_after": false,
  "doc02_node_after_forget": false,
  "doc01_node_after_forget": true,
  "recognify_calls": {
   "total": 4,
   "by_model": {
    "KnowledgeGraph": 2,
    "SummarizedContent": 2
   },
   "hinted": 0,
   "distinct_prompts": 2
  },
  "doc02_node_after_recognify": true,
  "processed_after_recognify": true
 },
 "default_prune": {
  "data_rows": 2,
  "processed_after": [
   true,
   true
  ],
  "graph_nodes_after_prune": 0,
  "recognify_calls": {
   "total": 0,
   "by_model": {},
   "hinted": 0,
   "distinct_prompts": 0
  },
  "graph_nodes_after_recognify": 0
 }
}
```
