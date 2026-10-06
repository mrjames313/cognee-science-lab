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


---

## Stage 3B — Direct retrieval comparison

Five baseline probes were used to compare semantic chunk retrieval, lexical chunk retrieval, and semantic retrieval over Cognee-generated summaries.

| Query | CHUNKS | CHUNKS_LEXICAL | SUMMARIES |
|---|---|---|---|
| Campaign A current limit | Mediocre ranking; most direct source chunk only #4 | Strong; direct/table-bearing chunks near top | Strong; relevant operating-envelope summary #1 |
| Installed NBI capacity | Good; directly relevant chunk #1 | Reasonable; tends toward table/specification material | Strong; relevant power-system summary #1 |
| Tritium | Strong; explicit source chunk #1 | Strong; explicit source chunk #1 | Weaker ranking; most directly useful device summary lower |
| Vertical motion | Weak/mixed; EDC/coreference chunk #1, explicit VCS section #2 | Best; VCS section #1 | Weak; EDC-oriented summary #1, VCS material lower |
| AFRL → tokamak | Strong; introductory AFRL/Helios-1 chunk #1 | Strong; same source chunk #1 | Strong; AFRL/Helios-1 summary #1 |

### Campaign A current limit

Semantic chunk retrieval found relevant material, but its ranking was surprisingly weak: the chunk containing the direct Campaign A current-limit statement appeared only fourth. Lexical retrieval did better because terms such as “Campaign A,” “plasma-current,” and “limit” occur close together in the operating-envelope/table material. Summary retrieval also performed well because the generated summary normalized the configuration-dependent current-limit fact into a compact representation.

This is an early indication that semantic similarity is not automatically the best ranking mechanism for precise engineering facts. Parameter names and campaign labels can be sufficiently distinctive that lexical matching is highly effective.

### Installed NBI capacity

All three approaches retrieved useful evidence. Semantic chunk retrieval placed the relevant magnetic/power-system chunk first. Summary retrieval was especially clean because the generated system summary explicitly consolidated installed actuator capacities. Lexical retrieval also worked, but behaved more like a specification/table lookup.

This is a case where summarization appears beneficial: a scattered technical passage is converted into a compact fact-oriented representation without materially losing the information needed for the query.

### Tritium

Raw semantic and lexical retrieval were both strong because the source contains a direct negative statement: Helios-1 does not use tritium.

Summary retrieval was weaker. The summary most directly describing Helios-1 and its deuterium-only operation did not rank first. This illustrates an important compression tradeoff: summaries can normalize facts, but salience decisions made during summarization can make an explicit negative fact less retrievable than it was in the original text.

### Vertical-motion control

This was the most useful discriminator among the baseline queries.

Semantic chunk retrieval ranked the EDC/coreference section ahead of the section explicitly defining the Vertical Control System. This makes semantic sense—both passages discuss controllers, control behavior, and plasma operation—but it is less useful for the precise question.

Lexical retrieval ranked the VCS section first and was clearly the strongest method for this query.

Summary retrieval behaved similarly to semantic chunk retrieval: an EDC-oriented summary ranked first, while the more directly useful VCS/system summary appeared lower.

This is a concrete example of **semantic neighborhood confusion**. Embedding retrieval recognizes the broad concept “controller affecting plasma behavior,” but does not reliably preserve the distinction between nearby control subsystems. Precise technical terminology gives lexical retrieval an advantage.

### AFRL → Helios-1

All three retrieval methods performed well.

This query is architecturally interesting because Stage 2 did not produce a standalone `afrl` semantic entity, yet the raw source explicitly contains “Aurora Fusion Research Laboratory (AFRL).” Document retrieval therefore bridges an entity-resolution weakness in the extracted graph.

This gives an important distinction:

```text
poor semantic-graph canonicalization
        ≠
poor document retrieval
```

A multi-representation system can remain robust even when one representation fails to canonicalize an alias correctly.

### Stage 3B conclusions

The three retrieval mechanisms have genuinely complementary failure modes:

#### CHUNKS

`CHUNKS` performs semantic/vector retrieval over the original document chunks.

It successfully retrieved useful source material for all five probes. In particular, the query using `AFRL` retrieved the document introduction containing the expansion "Aurora Fusion Research Laboratory (AFRL)" even though the semantic graph did not contain a standalone `afrl` entity. This demonstrates that document retrieval can compensate for some graph entity-resolution failures.

Ranking was not uniformly precise. For the Campaign A current-limit query, the chunk containing the most direct current-limit statement ranked fourth. For the vertical-motion query, the highest-ranked chunk was the section containing the ambiguous controller log, while the section explicitly describing the Vertical Control System ranked second. 

Thus semantic retrieval provides useful paraphrase and alias tolerance, but similarity can also pull in a broad semantic neighborhood rather than the most precise source passage.

#### CHUNKS_LEXICAL

`CHUNKS_LEXICAL` performs lexical/keyword retrieval over the original document chunks.

For terminology-heavy technical questions it was often competitive with or better than semantic retrieval. The vertical-motion query placed the VCS section first, and the AFRL query placed the introductory AFRL/Helios-1 passage first. 

This suggests that lexical retrieval remains useful in scientific and engineering corpora where system names, acronyms, parameter names, and specialized terminology carry unusually high information content.

#### SUMMARIES

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

---

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

---

## Stage 3D — Discriminating retrieval and completion probes

Stage 3D reduced retrieval to `top_k=2` and deliberately targeted representation weaknesses observed during Stage 2.

| Probe | RAG | Graph | Hybrid | Main observation |
|---|---|---|---|---|
| Early engineering field | **FAIL — 6.2 T** | **FAIL — 6.2 T** | **FAIL — 6.2 T** | Correct 5.0 evidence missed by all completion contexts |
| NBI checkout power | **PASS — 8 MW** | **PASS — 8 MW** | **PASS — 8 MW** | Omitted unit successfully recovered |
| 1.20 MA intrinsic limit? | PASS | **Strong pass** | Strong pass | Graph preserves authorized-vs-intrinsic semantics well |
| VCS “controller” | PASS | **Strong pass** | PASS | Graph contains resolved VCS relation |
| Density-checkout “controller” | PASS | **FAIL — VCS** | PASS | Graph enters wrong controller neighborhood |
| Improved confinement? | PASS | PASS | PASS | Negative/epistemic claim survives |
| H-1 installed NBI capacity | PASS | PASS | PASS | Correct, but weak test of alias resolution |

### Early engineering field: a retrieval-induced hallucination

The source states that early engineering pulses were run at `5.0` before returning to 6.2 T operation. The unit is omitted locally and must be inferred from context.

Lexical retrieval successfully finds the source chunk containing this sentence. Semantic chunk retrieval at `top_k=2` does not. Summary retrieval also fails to surface the summary in which Stage 2 had inferred the value as 5.0 T.

The consequence is striking: none of the RAG, graph, or hybrid completion contexts contains the 5.0 value. Instead, they contain the nearby and much more frequently represented nominal value of 6.2 T.

All three completion modes then confidently answer **6.2 T**.

This gives a clean causal chain:

```text
source contains correct fact
        ↓
retrieval misses correct evidence
        ↓
retrieved context contains nearby wrong value
        ↓
LLM confidently answers with wrong value
```

This is not primarily a reasoning failure. The completion model follows the context it was given.

It also demonstrates why retrieval evaluation cannot be reduced to whether some broadly relevant passage was found: a context can be topically relevant while still lacking the exact evidence needed to distinguish two plausible values.

### NBI actuator-checkout power: successful contextual unit inference

The source says that normal high-current operation used 4–6 MW, followed by:

```text
Brief operation at 8 was authorized during actuator checkout
```

All three completion modes correctly answer **8 MW**.

This provides an especially useful contrast with the 5.0-T case. Both involve locally omitted units, but the NBI fact survived extraction/retrieval while the commissioning-field fact did not.

Thus unit inference is not simply “supported” or “unsupported.” It is **representation- and retrieval-dependent**.

### 1.20 MA: operational authorization versus intrinsic limit

All three methods correctly reject the proposition that 1.20 MA was an intrinsic plasma-stability limit.

Graph completion gives the cleanest semantic formulation: it identifies the value as an authorized Campaign A operating limit associated with power-supply, vertical-control, and machine-protection constraints.

RAG also answers correctly, but adds calibration/measurement considerations. Those are relevant to the measured current value, but are conceptually distinct from why the authorization limit existed.

This suggests one real advantage for a structured representation: graph retrieval can sometimes preserve the **type of fact** better than broad text retrieval—here, operational authorization versus physical stability versus measurement uncertainty.

### VCS controller coreference: successful semantic materialization

For the VCS tuning-sequence quote, graph retrieval performs particularly well.

The semantic representation includes a relationship equivalent to:

```text
VCS
   --reduces_vertical_motion_during-->
current ramp
```

Graph completion therefore identifies “the controller” as the Vertical Control System and correctly ties it to the observed behavior.

This is stronger evidence than simply finding the raw sentence: Cognee successfully converted a local ambiguous reference into a reusable semantic relation.

### Density-control controller coreference: graph-induced error

The superficially parallel density-control query behaves very differently.

The raw passage clearly implies that “the controller” is the Edge Density Controller, because it increased gas flow as edge density fell.

RAG retrieves this passage and answers EDC correctly.

Hybrid also answers correctly because the raw-document evidence remains available.

Graph retrieval, however, enters a VCS-oriented graph neighborhood and supplies the completion model with Vertical Control System material rather than the EDC relation. Graph completion consequently answers **VCS**, incorrectly.

This is the clearest example in Stage 3 of a graph representation making the result worse:

```text
raw text
    → correct local interpretation: EDC

semantic graph retrieval
    → wrong neighborhood: VCS

graph completion
    → confidently wrong answer: VCS

hybrid retrieval
    → raw evidence rescues graph error
```

The two controller probes together are more informative than either alone. Cognee is capable of resolving local controller coreference, but that resolution is inconsistent rather than systematic.

### Improved-confinement claim

All three completion methods correctly reject the claim that Campaign A demonstrated improved confinement caused by the density controller.

This requires preserving more than a simple negated triple. The source distinguishes:

- operational use of the EDC,
- absence of controlled experimental variation,
- and absence of a statistically meaningful confinement claim.

The result suggests that both text and graph representations preserve enough epistemic context to avoid turning an operational correlation into a causal scientific conclusion.

This is encouraging for scientific-memory applications, where distinctions such as “observed,” “tested,” “inferred,” and “not established” are often as important as the numerical facts themselves.

### H-1 alias query

All three methods answer 8 MW correctly.

However, this should **not** be counted as strong evidence for alias resolution. The query also contains the highly discriminating phrase “installed neutral-beam capacity,” which can retrieve the correct table or capacity node without successfully resolving `H-1 → Helios-1`.

A stronger alias test should later use a query in which successful retrieval genuinely depends on the alias mapping.

### Context-volume behavior

Reducing `top_k` from five to two substantially reduces RAG context size, but the experiment also shows that graph structure does not automatically produce compact prompts.

Typical context sizes were approximately:

```text
RAG
    ~1,030–1,040 tokens

GRAPH
    ~700–1,600 tokens

HYBRID
    ~1,170–1,220 tokens
```

Graph context size is particularly variable. A query can select only three or four graph nodes yet still generate more than 1,500 tokens because `DocumentChunk` and `TextSummary` nodes carry large textual payloads.

Therefore:

```text
few graph nodes
    ≠
small LLM context
```

This will become increasingly important as the corpus and graph grow.


### Stage 3D conclusions

Stage 3D establishes several stronger results than the baseline completion experiment:

1. **Retrieval errors propagate into confident generation errors.**  
   The 5.0-T query demonstrates this directly.

2. **Different representations fail differently.**  
   Lexical retrieval found evidence that semantic retrieval, summaries, graph retrieval, and hybrid retrieval all missed.

3. **Semantic extraction can create real value.**  
   The VCS coreference and operational-vs-intrinsic current-limit examples show information being represented in a form useful for reasoning.

4. **Semantic extraction can also create new failure modes.**  
   The EDC/VCS error is not merely missing information; the graph steers retrieval toward the wrong interpretation.

5. **Hybrid retrieval provides fault tolerance.**  
   It rescued the EDC coreference failure by retaining source-text evidence, although it did not rescue the 5.0-T failure when its own document retrieval also missed the relevant chunk.

6. **Generated summaries are another lossy representation.**  
   They sometimes improve normalization, but they should not be assumed to preserve every scientifically relevant detail.

7. **Prompt growth is already nontrivial.**  
   Graph and hybrid retrieval can generate contexts comparable to or larger than RAG despite operating over a very small corpus.

The broader architectural implication is that Cognee should be viewed less as a single knowledge representation and more as a collection of interacting representations:

```text
raw document chunks
        +
generated summaries
        +
semantic entities/relations
        +
graph topology
        +
retrieval heuristics
        ↓
assembled LLM context
```

The strength of the system comes from those representations being able to compensate for one another. The risk is that every transformation also introduces its own information-loss and retrieval-failure modes.


