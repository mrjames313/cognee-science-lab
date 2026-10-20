# Cognee science lab

The project runs through a series of Cognee experiments against an artificial scientific corpus,
in order to determine Cognee's ability to process, encode, represent, and recall precise
technical information. 

There are multiple experiment stages, each building on the previous.

See the writeups in the `results/` directory for summaries of the current findings and conclusions.

## Continuing this project

**Start with [docs/SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md).** It records the delivered code baseline, implementation and Mac-verification status, code map, original six-step sequence, remaining work and next task. [ROADMAP.md](ROADMAP.md) is the stage overview. Dated investigation/checkpoint writeups retain their historical evidence boundaries.

## Stages

### Stage 1 — DataPoint mechanics
Status: complete
Goal: understand Cognee’s low-level graph data model without involving LLM extraction.
We tested custom DataPoint classes

### Stage 2 — Default add → cognify pipeline
Status: complete
Goal: understand what Cognee does automatically with an actual scientific-style source document.
We created and ingested the synthetic Helios-1 technical corpus, especially DOC01, and examined both ingestion and semantic graph construction.

### Stage 3 — Retrieval methods
Status: complete
Goal: understand how Cognee retrieves knowledge from the graph/vector/chunk layers, and whether retrieval compensates for the fragmentation we observed.
The query experiments and findings are recorded in `results/stage_three.md`.

### Stage 4 — Custom / mixed graph model
Status: exploration complete for the Stage-6 handoff
Goal: investigate how to specify a graph model with a mix of strongly-typed entities / relationships (for example, physical quantites) and open-world graph such as what Cognee generates by default.  The idea is to enforce specificity and precision where it is warranted by the domain, while allowing for the flexibility and extensibility of open-world extraction.

### Stage 5 — Identity, relation semantics, and schema evolution
Status: scoped identity/operational investigation and architecture handoff complete; implementation continues in Stage 6
Goal: tackle the problems Stage 2 exposed directly, using the frameworks developed in stage 4.

### Stage 6 — Custom pipeline and intermediate representations
Status: steps 1–2 and bounded portions of steps 3–4 implemented; captured publication/retrieval, shared-source withdrawal, corrections, native text/chunk rebuilding, occurrence/group retirement and bounded additions implemented; regrouping, changed interpretation, dependencies, full source lifecycle and steps 5–6 remain
Goal: stop treating cognify() as a black box and construct a custom processing pipeline from Cognee tasks.

See [the Stage 6 fixture guide](docs/stage6_identity_first_slice.md) for single/two-source fixtures, selected identity-source withdrawal, focused tests, recovery-event visibility and remaining boundaries. Integration code uses Cognee's graph/vector/relational interfaces; Ladybug/LanceDB/SQLite is the initial test configuration.

Step 4 includes [guarded identity corrections](docs/stage6_identity_revision_replacement.md) and [captured source-text edits](docs/stage6_identity_text_changes.md). The text-edit slice remaps document positions, rebuilds native chunks/facts/evidence, preserves independent sources and explicitly recovers caught failures. The [multi-chunk checkpoint](docs/stage6_identity_multichunk.md) adds split occurrences, complete fact-continuation evidence, changing boundaries and repeated edits. Arbitrary edits, dependency propagation and standard Update wiring remain incomplete.

The [reviewed occurrence-removal checkpoint](docs/stage6_identity_occurrence_removal.md) adds partial-group continuity and empty unresolved-group retirement through the same rebuild/recovery boundary. Its explicit retention map is captured review input, not automatic text matching or interpretation.

The [resolved-group retirement checkpoint](docs/stage6_identity_resolved_retirement.md) removes the final occurrences of a fact-bearing group, verifies actual node/link/fact/evidence/index cleanup, and preserves doc02's distinct fact plus shared endpoints and relationship-text index. It uses the same guarded replace/rebuild/recovery path.


The [occurrence-addition checkpoint](docs/stage6_identity_occurrence_addition.md) preserves a continuing group, introduces a separate same-text local group and produces its original-owned fact/evidence through the common maintenance path. See the handoff for its test evidence and remaining boundaries.

## Setup and running the code

Will run in a single-user mode and use local storage for Cognee.

The historical lab extraction/embedding profile uses external API credentials. The isolated Stage-6 fixtures use captured decisions and a loopback deterministic embedding service; they need no LLM or external embedding API credentials. Follow the handoff and fixture guides before opening or changing lab stores.

Install dependencies:

```bash
uv sync

cp .env.example .env
```

# Within .env, add your API keys (and possibly change configuration if not using those providers)
# Then edit the three root-directory paths to use the absolute repo path as shown




### Historical lab model configuration

Stage 1 experiments are all local.

Stage 2 uses OpenAI GPT-5.6 Luna for Cognee's LLM-based graph extraction.

It also uses Nvidia's (free) embedding API, which should provide better
performance than the local embeddings, and affects chunking as well.
