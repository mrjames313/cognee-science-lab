## Stage 3A — Search-mode inventory

The first step was to inventory Cognee's available `SearchType` modes and identify which were useful for examining retrieval behavior directly.

Cognee 1.6.2 exposes the following search types:

```text
SUMMARIES
CHUNKS
RAG_COMPLETION
HYBRID_COMPLETION
TRIPLET_COMPLETION
GRAPH_COMPLETION
GRAPH_COMPLETION_DECOMPOSITION
GRAPH_SUMMARY_COMPLETION
CYPHER
NATURAL_LANGUAGE
GRAPH_COMPLETION_COT
GRAPH_COMPLETION_CONTEXT_EXTENSION
FEELING_LUCKY
TEMPORAL
CODING_RULES
CHUNKS_LEXICAL
AGENTIC_COMPLETION
CODE
GRAPH_REPORT
SKILLS
```

For the initial experiments these were divided into three useful groups:

- **Direct retrieval:** `CHUNKS`, `CHUNKS_LEXICAL`, `SUMMARIES`
- **Answer-generation / completion:** `RAG_COMPLETION`, `GRAPH_COMPLETION`, `HYBRID_COMPLETION`
- **Specialized or higher-level modes:** Cypher, temporal retrieval, agentic completion, graph decomposition, chain-of-thought variants, and others

The experiments use the lower-level `cognee.search()` interface rather than `recall()`. This keeps the retrieval strategy explicit and makes it possible to inspect intermediate results instead of allowing Cognee to choose a routing strategy automatically.

A useful distinction established here is that the `*_COMPLETION` modes are not simply alternate retrieval result formats. They retrieve or construct context and then pass that context to an LLM to generate an answer. Later experiments therefore inspect both the generated answer and, using `only_context=True`, the actual context supplied to the completion model.

## Stage 3B — Direct retrieval

Three direct retrieval modes were compared against the same five diagnostic questions:

```text
CHUNKS
CHUNKS_LEXICAL
SUMMARIES
```

The queries tested configuration-dependent numerical facts, installed hardware capacity, negation, controller/coreference semantics, and acronym resolution.

### CHUNKS

`CHUNKS` performs semantic/vector retrieval over the original document chunks.

It successfully retrieved useful source material for all five probes. In particular, the query using `AFRL` retrieved the document introduction containing the expansion "Aurora Fusion Research Laboratory (AFRL)" even though the semantic graph did not contain a standalone `afrl` entity. This demonstrates that document retrieval can compensate for some graph entity-resolution failures.

Ranking was not uniformly precise. For the Campaign A current-limit query, the chunk containing the most direct current-limit statement ranked fourth. For the vertical-motion query, the highest-ranked chunk was the section containing the ambiguous controller log, while the section explicitly describing the Vertical Control System ranked second. 

Thus semantic retrieval provides useful paraphrase and alias tolerance, but similarity can also pull in a broad semantic neighborhood rather than the most precise source passage.

### CHUNKS_LEXICAL

`CHUNKS_LEXICAL` performs lexical/keyword retrieval over the original document chunks.

For terminology-heavy technical questions it was often competitive with or better than semantic retrieval. The vertical-motion query placed the VCS section first, and the AFRL query placed the introductory AFRL/Helios-1 passage first. 

This suggests that lexical retrieval remains useful in scientific and engineering corpora where system names, acronyms, parameter names, and specialized terminology carry unusually high information content.

### SUMMARIES

`SUMMARIES` performs semantic/vector retrieval over LLM-generated summaries associated with source chunks. Returned objects contain a `source_chunk_id`, preserving a link from the generated summary to its originating document chunk.

The summaries often normalize information into an easier-to-retrieve factual representation. For example, the AFRL query ranked the summary explicitly stating that AFRL operates Helios-1 first, and the installed-NBI query ranked the magnetic/power-system summary first. 

However, summarization can also blur nearby concepts. For the vertical-motion query, the highest-ranked summary concerned the Edge Density Controller rather than the more directly relevant VCS material. The tritium query similarly did not rank the summary containing the most direct device description first. 

The three direct retrieval modes therefore provide complementary behavior:

```text
CHUNKS
    semantic retrieval over original evidence
    good alias/paraphrase tolerance
    sometimes broad ranking

CHUNKS_LEXICAL
    term-oriented retrieval over original evidence
    strong when scientific/engineering terminology is distinctive

SUMMARIES
    semantic retrieval over compressed LLM representations
    can normalize useful facts and aliases
    can also lose distinctions or blur nearby concepts
```

### Stage 3B limitation

The current corpus contains only six chunks and the experiments use `top_k=5`. Consequently, nearly the entire corpus is returned for each query. These experiments are therefore useful for understanding retrieval mechanics and ranking behavior but should not be interpreted as a meaningful retrieval-accuracy benchmark.

## Stage 3C — Completion strategies

Three completion modes were compared:

```text
RAG_COMPLETION
GRAPH_COMPLETION
HYBRID_COMPLETION
```

An initial run revealed that Cognee maintains search-session conversation history and supplies previous question/answer pairs to subsequent completion calls. Because the three search modes had been run sequentially in the same default session, later graph and hybrid completions could see answers produced by earlier searches. Those initial answer-quality results were therefore considered contaminated.

The experiment was repeated with a new unique `session_id` for every query. Inspection using `only_context=True` confirmed that the previous-conversation block was absent in the clean run.

### RAG completion

`RAG_COMPLETION` retrieves source chunks and constructs a prompt from their text before asking the LLM to answer.

All five baseline questions were answered correctly in the clean run.

However, `top_k=5` against a six-chunk corpus means that the LLM receives most of the document. The clean context dump contained approximately **13,000 characters and 1,875 words per query**. Thus RAG success on these probes says relatively little about precision: the answer is usually present somewhere in a large fraction of the available source.

### Graph completion

`GRAPH_COMPLETION` first performs vector-based relevance retrieval, projects the corresponding graph, selects a smaller set of nodes and connections, renders that material into text, and passes it to the completion model.

For the baseline questions, the final graph contexts contained approximately 5–8 selected nodes and five connections, and all five answers were correct. The current-limit response also preserved the useful qualification that 1.20 MA was the **authorized** limit.

However, graph completion should not be interpreted as retrieval from semantic triples alone. The projected graph contains `DocumentChunk` and `TextSummary` nodes whose node contents can include substantial source text. Graph-completion success therefore shows that the Cognee graph representation contained sufficient evidence, but not necessarily that the extracted entity/relation layer alone contained sufficient evidence.

The clean graph-completion prompts ranged from approximately **7,250 to 13,500 characters**, or roughly **1,000–1,860 words**, with an average near **9,900 characters / 1,350 words**.

### Hybrid completion

`HYBRID_COMPLETION` explicitly combines multiple types of evidence into sections such as:

```text
Relevant passages
Relevant entities
Related facts
```

All five baseline questions were again answered correctly.

Hybrid retrieval generated the largest contexts. The five clean prompts ranged from approximately **14,850 to 16,060 characters**, corresponding to about **2,160–2,310 words**, with an average near **15,400 characters / 2,230 words**.

Graph neighborhood expansion can also fan out rapidly. Most baseline queries produced neighborhoods of roughly 15–20 nodes and 23–42 edges, but the tritium query expanded one hop around the highly connected Helios-1 region to **65 nodes and 160 edges**.

### Context-growth finding

A significant Stage 3C finding is therefore not merely that `top_k=5` retrieves a large *fraction* of this small corpus, but that Cognee rapidly constructs substantial absolute amounts of text for the completion model.

For a single short technical document divided into only six approximately 1,000-token chunks:

```text
RAG_COMPLETION
    ~13.0k characters
    ~1,875 words / query

GRAPH_COMPLETION
    ~7.3k–13.5k characters
    ~1,000–1,860 words / query

HYBRID_COMPLETION
    ~14.8k–16.1k characters
    ~2,160–2,310 words / query
```

These values measure the dumped prompt text rather than model-specific token counts.

This suggests that context-volume management may become important quickly as the knowledge base grows. Graph and hybrid retrieval do not inherently imply a compact context: graph nodes can carry large chunk/summary payloads, and graph neighborhood expansion can add substantial redundant or indirectly related material.

### Stage 3C conclusion

The three default completion strategies all succeed on the current baseline probes, but the corpus and questions are too small and explicit to discriminate answer quality meaningfully.

More useful distinctions emerge from their retrieval behavior:

- raw RAG can compensate for imperfect graph extraction but currently supplies most of the corpus;
- graph completion retrieves relevant semantic structure but can also reintroduce large amounts of source text through chunk and summary nodes;
- hybrid retrieval combines useful evidence types but can generate the largest contexts and suffer from high-degree graph fan-out.

The next experiments therefore use harder questions specifically selected to expose representation differences discovered during Stage 2.

## Stage 3D — discriminating retrieval/completion probes

Results:
                         RAG     Graph   Hybrid
Early field 5.0 T        FAIL    FAIL    FAIL
NBI checkout 8 MW        PASS    PASS    PASS
1.20 MA intrinsic?       PASS    PASS    PASS
VCS "controller"         PASS    PASS    PASS
EDC "controller"         PASS    FAIL    PASS
Confinement claim        PASS    PASS    PASS
H-1 NBI capacity         PASS    PASS    PASS

### Key findings:

1. Retrieval failure propagates directly into confident wrong answers.
   The 5.0-T commissioning fact was absent from all three completion
   contexts; all three answered with the nearby nominal 6.2-T value.

2. Graph retrieval can improve semantic precision.
   It cleanly represented the authorized-vs-intrinsic current-limit
   distinction and correctly resolved the VCS controller reference.

3. Graph retrieval can also introduce semantic errors.
   The density-control coreference query entered the VCS neighborhood
   instead of the EDC neighborhood, producing the wrong answer.

4. Hybrid retrieval corrected that graph failure because the raw
   source passage remained available.

5. Omitted-unit inference is representation-dependent.
   "8" → 8 MW survived retrieval and completion.
   "5.0" → 5.0 T did not.

6. Answer generation mostly followed the supplied context.
   The major errors are best understood as retrieval/context failures
   rather than failures of downstream reasoning.