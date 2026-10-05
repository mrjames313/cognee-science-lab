# Cognee science lab

The project runs through a series of Cognee experiments against an artificial scientific corpus,
in order to determine Cognee's ability to process, encode, represent, and recall precise
technical information. 

There are multiple experiment stages, each building on the previous.

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
Status: next
Goal: understand how Cognee retrieves knowledge from the graph/vector/chunk layers, and whether retrieval compensates for the fragmentation we observed.
We planned to test queries

### Stage 4 — Custom graph model
Status: planned
Goal: replace the generic Entity / EntityType / arbitrary relation model with a domain-specific Cognee graph model.

### Stage 5 — Identity, relation semantics, and schema evolution
Status: planned
Goal: tackle the problems Stage 2 exposed directly.

### Stage 6 — Custom pipeline and intermediate representations
Status: planned, major checkpoint
Goal: stop treating cognify() as a black box and construct a custom processing pipeline from Cognee tasks.


## Setup and running the code

Will run in a single-user mode and use local storage for Cognee.

LLMs for processing inputs, and creating embeddings are API calls and require
authentication.

Install dependencies:

```bash
uv sync

cp .env.example .env
```

# Within .env, add your API keys (and possibly change configuration if not using those providers)
# Then edit the three root-directory paths to use the absolute repo path as shown




### Model configuration

Stage 1 experiments are all local.

Stage 2 uses OpenAI GPT-5.6 Luna for Cognee's LLM-based graph extraction.

It also uses Nvidia's (free) embedding API, which should provide better
performance than the local embeddings, and affects chunking as well.


