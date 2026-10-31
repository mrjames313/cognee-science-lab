# Minimal identity framework: the alignment experiment

Run by the assistant on the user's Mac on 2026-10-31, at the user's request, with Cognee 1.6.2, Claude Haiku 5.5 (`claude-haiku-5-5`) for extraction and the embedding model that `.env` names. It answers open question 7 of [the minimal identity framework](../docs/minimal_identity_framework.md): does the spelling hint earn its place, and what threshold should alignment's similar pass use? It also times Shape 1v's in-memory view and checks five Cognee behaviours the design had read in the source but never run.

The harness is [`scripts/align_experiment.py`](../scripts/align_experiment.py). The raw results are under `outputs/minimal-align-20261031-1256/`, which is not committed.

## Method

- **Corpus.** DOC01 and DOC02 of the Helios corpus (`data/DOC01_helios1_technical_overview.md`, `data/DOC02_campaign_A_high_current.md`). Cognee's chunker made 2 chunks of each.
- **Describe.** The lab's rule describer (`reusable_names` in `src/cognee_lab/identity/conformance_fixture.py`) over each document's stored text. It gives 20 distinct names in 10 variant groups across the two documents. Its author had read the conformance answers, so it is a fixed description, not a test of Describe.
- **Conditions.** Six fresh isolated roots, three with the spelling hint and three without. Each root runs add DOC01, Describe, cognify, then the same for DOC02. With the hint, cognify gets Cognee's configured graph prompt plus a section listing that document's names.
- **Alignment.** Each of the 20 names is checked for an exact node at `Entity.id_for(name)`. That node is then support-checked against the text of its `contains` chunks: whole words, using the name or another name in its group. The top 10 `Entity_name` vector hits are recorded with their distances and their own support.
- **The view.** Cognee's `get_memory_fragment` projects the whole graph. Each admitted group member's non-structural edges are copied onto the other members. The result is deep-copied once, standing in for the per-query clone.
- **Checks.** On the last hinted root, after measurement:
  1. A hinted `cognee.update` of DOC01 to its v2 text.
  2. `cognee.forget(memory_only=True)` of DOC02, then a plain cognify.
  3. The default `cognee.prune.prune_system()`, then a plain cognify.
- **Cost.** 80 LLM calls in total, counted at Cognee's `LLMGateway`:
  - 9 per root (one connectivity call, then 2 graph extractions and 2 summaries per document);
  - 8 more for the checks;
  - a 9-call smoke run;
  - a 9-call first attempt at the checks root that failed in the update check.

## Results

### The hint

| Run | Names aligned `exact` | No exact node | `contains` edges whose chunk lacks the name | Entities |
|---|---|---|---|---|
| hint-1 | 20 of 20 | 0 | 7 | 50 |
| hint-2 | 20 of 20 | 0 | 8 | 38 |
| hint-3 | 20 of 20 | 0 | 8 | 44 |
| nohint-1 | 15 of 20 | 5 | 0 | 43 |
| nohint-2 | 14 of 20 | 6 | 0 | 42 |
| nohint-3 | 8 of 20 | 12 | 0 | 38 |

- **Effect on exact alignment.** With the hint, every described name had an exact, supported node in all three runs. Without it, 8 to 15 of the 20 did, with wide run-to-run variation (CB3).
- **What the hint plants.** It sends the whole document's list with every chunk, and the model links names to chunks that never mention them. In hint-1, DOC01's second chunk was linked to `mpa`, `pcps`, `rcm`, `magnetic probe array`, `plasma current power supply` and `rogowski current monitor`, and DOC02's second chunk to `rogowski current monitor`. None of those chunks contains the name or any variant of it. Every hinted run planted 7 or 8 such links. The support check rejected each one, and every planted node still had a real supporting chunk.
- **Not measured.** Whether the model also extracted facts on those planted links.

### Why the no-hint names missed

Every miss without the hint was one of two kinds:
- **Never extracted.** In nohint-1 and nohint-2, cognify made no node for `afrl`, `ech`, `mpa`, `nbi`, `pcps` or `rcm`. Their long forms were exact and supported, so each group still had a node, and no native fact was lost.
- **Extracted with the abbreviation in parentheses.** In nohint-3, cognify named 11 of its 12 missing names this way, for example `magnetic probe array (mpa)`, `vertical control system (vcs)` and `rogowski current monitor (rcm)`.

A lexical rule finds every such node. It strips one trailing parenthetical, then checks whether the base or the parenthetical equals a name in the group. It recovered all 11 in nohint-3 and admitted nothing wrong in any run.

### The vector similar pass

It does not work with this embedding model, at any threshold.
- **For the 12 nohint-3 misses.** The right node ranked 2nd to 37th among `Entity_name` hits, at distances 0.247 to 0.478. A wrong Entity ranked above it every time, at distances 0.078 to 0.258. For example:
  - for `mpa`, `energy confinement` scored 0.078, and `magnetic probe array (mpa)` ranked 30th at 0.351;
  - for `magnetic probe array`, `aurora magnetic reconstruction` scored 0.165, and the right node ranked 11th at 0.270.
- **For names with no node at all.** The best hit the pass could admit was always wrong, at distances of about 0.06 to 0.13.
- **Where it scored well.** Only on long-form pairs such as `neutral beam injection` and `neutral beam injection system` (0.038), and those are already in the same group.

### The view

| Run | Graph nodes | Graph edges | Overlay edges | Project (s) | Overlay (s) | Clone (s) |
|---|---|---|---|---|---|---|
| hint-1 | 78 | 190 | 27 | 0.003 | 0.0002 | 0.003 |
| hint-2 | 63 | 143 | 9 | 0.007 | 0.0002 | 0.005 |
| hint-3 | 70 | 230 | 59 | 0.004 | 0.0003 | 0.004 |
| nohint-1 | 73 | 195 | 33 | 0.003 | 0.0002 | 0.003 |
| nohint-2 | 69 | 182 | 24 | 0.003 | 0.0001 | 0.003 |
| nohint-3 | 68 | 145 | 0 | 0.003 | 0.0000 | 0.002 |

At this size, building and cloning the view costs milliseconds. The graphs are far smaller than a real dataset. These numbers show the route works, not how it scales.

### The Cognee behaviour checks

| Behaviour | Observed | Matches the design |
|---|---|---|
| A cognify right after one add processes only that document (CB11) | DOC02's cognify made 4 calls, for its 2 chunks only, in every run | Yes |
| The custom prompt goes with every extraction call and no summary call (CB20) | 2 of 4 calls hinted per document, both of them `KnowledgeGraph` extractions | Yes |
| A hinted update takes the full rebuild (CB20) | `status: full_rebuild`, `fallback.reason: custom_extraction_config`. Data ID kept, `raw_content_hash` changed. 4 calls, 2 of them hinted. | Yes |
| A memory-only forget keeps the Data row and clears its mark (CB17) | Row kept, processed mark cleared, document node gone. A plain cognify re-extracted DOC02 alone in 4 calls. | Yes |
| The default prune keeps Data rows and their marks (CB16) | 2 rows kept, both still marked processed, graph empty. A plain cognify then made 0 calls and left the graph empty. | Yes |

One harness finding: `cognee.update` rejects an open file handle (`IngestionError: Data type not supported: BufferedReader`, status 415). It takes an absolute path or an upload object.

## What it means for the design

1. **The vector similar pass should go.** With this embedding model it would serve wrong Entities' facts as `similar` matches, and no threshold separates right from wrong. The lexical pass above replaces it. It is deterministic, needs no threshold and no vector search, and caught every variant node in these runs.
2. **With the lexical pass, the hint bought nothing here.** Exact plus lexical aligned every node that existed in all three no-hint runs. Each name it left unaligned had no node, and its group still had one. Meanwhile the hint planted 7 or 8 false chunk links per run. That makes it optional at best, and it carries real costs:
   - a copy of Cognee's prompt to maintain;
   - one cognify per document;
   - a full rebuild on every update;
   - a writer policy;
   - links that may carry false facts.

   This rests on two documents and one naming pattern, `Name (ABBR)`. A corpus with other variant patterns could change it.
3. **Shape 1v's in-memory view is cheap at this size.** A scaling measurement needs a larger graph.
4. **Four design claims read from source now hold in practice:** CB11, CB16, CB17 and CB20.

## Limits

- **A small corpus.** Two documents, four chunks, one extraction model, one embedding model and one rule describer.
- **Thin repetition.** Three runs per condition is enough to see the hint's effect and the vector pass's failure, but not to estimate rates tightly.
- **The similar-pass verdict is specific to these models.** It holds for the configured embedding model and these short technical names. Another embedding model might separate them.
- **Facts on planted links are unmeasured.**
