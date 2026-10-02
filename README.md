The project runs through a series of Cognee experiments against an artificial scientific corpus.

There are multiple experiment stages, growing in sophistication.


### Model configuration

Stage 1 experiments are all local.

Stage 2 uses OpenAI GPT-5.6 Luna for Cognee's LLM-based graph extraction,
while embeddings remain local using BAAI/bge-small-en-v1.5 via FastEmbed.

It also uses Nvidia's (free) embedding API, which should provide better
performance than the local embeddings, and affects chunking as well.


## Local setup

Will run in a single-user mode and use local storage.

Install dependencies:

```bash
uv sync

cp .env.example .env

# Then edit the three root-directory paths to use the absolute repo path.
