# Stage 2 — Default `add → cognify` Pipeline

## Objective

Stage 2 explored Cognee's default ingestion and graph-construction pipeline using a single synthetic technical document describing the fictional Helios-1 fusion research program.

The goals were to understand:

- what `cognee.add()` persists before graph construction
- how `cognee.cognify()` chunks and transforms a document
- what graph objects are created by the default pipeline
- how entities are identified and merged across chunks
- how relationships are represented
- how aliases, acronyms, coreferences, negation, and contextual quantities are handled
- what provenance is retained for extracted semantic relationships

The corpus was intentionally designed to include repeated facts, aliases, acronyms, pronouns, omitted units, temporal/configuration-dependent statements, negative statements, and scientific caveats.

---

## 1. `add()` performs ingestion, not semantic graph construction

Calling:

```python
await cognee.add(path, dataset_name="helios_stage2")
```

created the dataset and data-item metadata but left the graph empty.

Observed after `add()`:

```text
graph nodes: 0
graph edges: 0
```

The original Markdown document was also materialized into Cognee's data directory as normalized text. Cognee retained metadata including:

- original source path
- normalized data location
- dataset ID
- data ID
- content hash
- MIME/original MIME types
- pipeline status

This establishes a useful separation:

```text
source file
    ↓
add()
    ↓
dataset + data item + normalized content
    ↓
cognify()
    ↓
semantic graph
```

`add()` should therefore be understood primarily as ingestion/cataloguing rather than knowledge extraction.

---

## 2. The default `cognify()` pipeline materializes document structure

Using an explicit:

```python
chunk_size=1000
```

on DOC01 produced:

```text
1  TextDocument
6  DocumentChunk
6  TextSummary
98 Entity
31 EntityType
```

The document/chunk structure is approximately:

```text
TextDocument
    ↑ is_part_of
DocumentChunk
    ↑ made_from
TextSummary
```

Semantic entities are also associated with source chunks through:

```text
DocumentChunk --contains--> Entity
```

The pipeline therefore preserves more than a final entity graph: document, chunk, summary, and semantic layers coexist.

---

## 3. Chunking respects semantic boundaries

The six chunks were:

```text
chunk 0: 979 tokens, cut=sentence_end
chunk 1: 995 tokens, cut=sentence_end
chunk 2: 998 tokens, cut=paragraph_end
chunk 3: 982 tokens, cut=paragraph_end
chunk 4: 968 tokens, cut=sentence_end
chunk 5: 430 tokens, cut=paragraph_end
```

The explicit 1000-token maximum acted as an upper bound rather than a hard slicing point. Cognee backed up to sentence or paragraph boundaries.

Each `DocumentChunk` retained useful provenance and chunk metadata, including:

- `document_id`
- `document_name`
- `chunk_index`
- `chunk_size`
- `max_chunk_tokens`
- `cut_type`
- `chunker_id`
- source URI/content hash
- original chunk text

This makes the chunk representation usable for later source tracing.

---

## 4. The default semantic graph is schema-light

The dominant semantic structure is:

```text
Entity --is_a--> EntityType
```

There were exactly:

```text
98 Entity nodes
98 is_a edges
```

and every entity had exactly one `is_a` relationship:

```text
Counter({1: 98})
```

Entity identity uses the entity's normalized `name`, consistent with the `identity_fields=["name"]` behavior studied in Stage 1.

By contrast, relationship vocabulary is highly open-ended. Examples included:

```text
uses
equipped_with
has_parameter
has_configuration_setting
operated_at
authorized_current_for
receives_estimates_from
was_not_experimental_variable_in
provides_control_system_context_for
describes_analysis_dependent_quantity_for
```

Many relationships appeared only once.

The default model is therefore closer to an LLM-generated/OpenIE-style semantic graph than to an ontology-constrained property graph:

```text
entities:      moderately canonicalized
entity types:  explicitly represented
relationships: largely free-form
```

---

## 5. Relationship names are not globally schema-constrained

Most `contains` edges represented:

```text
DocumentChunk --contains--> Entity
```

but Cognee also created a semantic relationship:

```text
Helios-1 --contains--> vacuum vessel
```

Thus the same predicate name can be used for both pipeline structure and domain semantics.

Relationship meaning depends on endpoint types and context rather than a globally enforced domain/range schema.

This is flexible, but it limits schema-level guarantees and makes global reasoning about predicates more difficult.

---

## 6. Cross-chunk entity merging works well when names canonicalize identically

The graph contained:

```text
98 unique Entity nodes
121 DocumentChunk --contains--> Entity edges
```

Several entities appeared in multiple chunks:

```text
helios-1                         [0,1,2,3,4,5]
campaign a                       [0,1,2,3,4]
aurora fusion research laboratory [0,3,5]
edge density controller          [1,2,4]
h1-1854                          [0,2]
neutral beam injection           [0,2]
vertical control system          [1,2]
```

This demonstrates that Cognee does not create independent entity copies for every chunk. When extraction produces the same canonical entity name, deterministic identity collapses those occurrences into one node.

The working model is:

```text
text mention
    ↓
LLM extraction / partial normalization
    ↓
Entity(name=...)
    ↓
identity_fields=["name"]
    ↓
deterministic cross-chunk identity
```

---

## 7. The extraction LLM performs some genuine coreference/canonicalization

The source explicitly stated that Helios-1 may be called:

```text
Helios-1
Helios 1
H-1
Helios
the machine
```

Yet Cognee produced a single `helios-1` node rather than separate `h-1`, `helios`, or `machine` entities.

The `helios-1` node also appeared in all six chunks.

This suggests that default extraction performs some contextual mention normalization/coreference resolution before `identity_fields` are applied.

This behavior is useful but inconsistent, as described below.

---

## 8. Alias and acronym resolution are incomplete

Several clear aliases were represented as separate entities.

### Organization alias

```text
afrl
aurora fusion research laboratory
```

Both were typed as `organization`, but remained separate nodes.

### Vertical Control System

```text
vertical control system
vertical-control system
```

Both were typed as `system`, but their facts were divided across two entities.

The main node contained information about:

- 10 kHz operation
- magnetic probe input
- vertical-control coils
- distinction from EDC

while the hyphenated node alone contained:

- reduced actuator-rate margin at high current

This is more serious than cosmetic duplication because knowledge becomes fragmented across aliases.

### NBI

Cognee created:

```text
nbi
neutral beam injection
neutral beam injection system
```

All three effectively described the same physical heating subsystem but had different types and relation neighborhoods.

A similar pattern occurred for ECH:

```text
ech
electron cyclotron heating
electron cyclotron heating system
```

### Discharge identifier

Cognee created both:

```text
h1-1854
discharge h1-1854
```

Both were typed as `discharge`, but different facts were attached to each.

This is a clean example of entity-resolution failure causing factual fragmentation.

---

## 9. Entity granularity is not consistently normalized

Some apparent duplicates could theoretically represent distinct concepts, for example:

```text
electron cyclotron heating
electron cyclotron heating system
electron cyclotron heating capacity
```

A well-designed ontology might intentionally distinguish:

```text
process
physical subsystem
capacity/property
```

However, the default graph does not apply such distinctions consistently enough to infer that this was intentional modeling.

The default extractor appears to decide entity granularity locally rather than according to a stable domain model.

This suggests that entity resolution in a scientific system cannot be reduced to string normalization alone; ontology/type semantics are also needed to determine when two mentions refer to the same thing versus related but distinct concepts.

---

## 10. Contextual unit inference partially worked

Two different versions of the source text were used, leading to slightly
different outcomes.

The source contained:

```text
the field was lowered to 5.0 ... and later returned to 6.2
```

without repeating the unit in that sentence.

In both cases, Cognee extracted:

```text
5.0 t
6.2 t
```

and in the first case, both semantic relationships:

```text
Helios-1 --operated_at_during_commissioning--> 5.0 t
Helios-1 --operated_at--> 6.2 t
```

In the second case, the 5.0T value did not generate a graph entity or semantic edge.

The surrounding chunk had previously established the nominal field as 6.2 T, so this demonstrates successful local contextual unit inference in some cases.

Contextual unit inference can occur during cognify,
but successful inference does not guarantee that the
inferred quantity is materialized as a graph fact.

It does not demonstrate cross-chunk inference: sufficient unit context was available within the same chunk.

---

## 11. Negation is preserved, but encoded lexically

Cognee successfully preserved negative information rather than silently dropping or reversing it.

Examples included:

```text
does_not_use
not_configured_for
did_not_independently_exercise
was_not_experimental_variable_in
was_not_dominant_heating_actuator
```

For example:

```text
Helios-1 --does_not_use--> tritium
```

and:

```text
Edge Density Controller
    --was_not_experimental_variable_in-->
H1-1854
```

This is good extraction behavior.

However, polarity is encoded in the predicate name itself rather than represented structurally as something like:

```text
subject
predicate
object
polarity = negative
```

This makes systematic reasoning over positive and negative versions of the same predicate harder.

---

## 12. Temporal/configuration semantics are also represented lexically

The source deliberately distinguished stable machine facts from time/configuration-dependent values.

Cognee represented these using relations such as:

```text
has_configuration_setting
requires_date_context
describes_configuration_dependent_quantity_for
describes_analysis_dependent_quantity_for
operated_at_during_commissioning
completed_campaign_by
occurred_on
```

This retains much of the source semantics, but temporal meaning is distributed across many relation types and related entities rather than represented with a uniform valid-time model.

This will matter when later documents revise values.

---

## 13. Graph edges are first-class objects

The low-level graph engine returned edges as:

```python
(
    source_node_id,
    target_node_id,
    relationship_name,
    edge_properties,
)
```

Every edge had properties including:

```text
source_node_id
target_node_id
relationship_name
relationship_type
edge_object_id
updated_at
feedback_weight
edge_text
```

`edge_text` is a natural-language rendering of the semantic relationship.

Example:

```text
Helios-1 had an authorized plasma-current limit of 1.20 MA
in the Campaign A configuration.
```

The unique `edge_object_id` is particularly important because provenance can refer directly to a specific graph edge.

---

## 14. Cognee preserves two distinct forms of edge provenance

The ordinary graph representation does not expose all provenance information.

### Graph/run provenance

Using:

```python
get_edge_delete_data(...)
```

revealed fields such as:

```text
source_ref_keys
source_dataset_ids
source_run_ids
source_run_refs
```

These track ownership/contribution of graph artifacts at the data/dataset and pipeline-run level.

### Chunk-level edge evidence

Cognee's relational metadata database also contains:

```text
provenance_edge_evidence
```

with columns including:

```text
dataset_id
data_id
pipeline_run_id
chunk_id
chunk_index
edge_id
source_node_id
destination_node_id
relationship_name
evidence_kind
source_task
confidence
```

This directly connects a semantic graph edge to one or more source chunks.

The `edge_id` in this table was exactly the graph's `edge_object_id`, confirming that evidence is attached to the actual graph edge rather than reconstructed later from subject/predicate/object matching.

---

## 15. One graph edge can accumulate evidence from multiple chunks

One semantic edge:

```text
Campaign A --conducted_on--> Helios-1
```

had two evidence rows:

```text
chunk 3
chunk 4
```

Both chunks independently provided enough context for the extractor to infer the same canonical graph relationship.

Therefore Cognee supports:

```text
          chunk 3
             \
semantic edge
             /
          chunk 4
```

This is a significant capability.

However, only one of the 356 graph edges in this document had multiple evidence rows.

---

## 16. Edge evidence is extraction provenance, not exhaustive evidence discovery

The distinction became clear with the Campaign-A current-limit fact.

Chunk 1 explicitly stated:

```text
During Campaign A the authorized plasma-current limit was 1.20 MA
```

Chunk 3 also stated the 1.20 MA setting in a table and supporting text.

The semantic edge:

```text
Helios-1
    --has_configuration_setting-->
authorized plasma-current limit
```

was linked only to chunk 3.

Thus Cognee does not appear to perform a later semantic search for every source passage that supports a proposition.

Instead:

> Evidence rows identify chunks that independently produced the same canonical graph edge during extraction.

For evidence to accumulate automatically, extraction must converge on the same:

```text
source entity
relationship
destination entity
```

Entity-resolution or predicate-normalization failures therefore also fragment provenance.

---

## 17. "Evidence" may be contextual rather than an exact quotation

The multi-evidence `Campaign A --conducted_on--> Helios-1` relation illustrates this.

Neither supporting chunk necessarily contained the exact sentence:

```text
Campaign A was conducted on Helios-1.
```

Instead, each chunk contained enough surrounding context to infer that relationship.

Thus `provenance_edge_evidence` means approximately:

> this chunk caused/supports this extracted graph relationship

rather than:

> this chunk contains an exact textual statement matching the edge.

Currently observed evidence metadata was:

```text
evidence_kind = extracted
confidence = None
```

No distinction was observed between:

- directly stated
- contextually inferred
- strongly implied
- derived from another claim

---

## 18. Overall default pipeline model

The Stage 2 observations support the following mental model:

```text
Source file
    ↓
add()
    ↓
Data / dataset metadata
    ↓
normalized text
    ↓
cognify()
    ↓
TextDocument
    ↓
DocumentChunk
    ↓
TextSummary
    ↓
LLM semantic extraction
    ↓
Entity + EntityType
    ↓
open-vocabulary Entity→Entity relationships
    ↓
graph edge identity
    ↓
provenance_edge_evidence
    ↓
one or more source chunks
```

---

## Capabilities observed

Cognee's default pipeline showed several strong capabilities:

- clean separation of ingestion from semantic processing
- semantically sensible chunking near explicit token limits
- persistent document and chunk structure
- deterministic cross-chunk entity identity when names align
- some real contextual/coreference normalization
- strong extraction of many technical relationships
- contextual unit inference
- preservation of negative statements
- explicit entity typing
- first-class semantic edge identity
- document/run provenance
- explicit chunk-level provenance for semantic edges
- ability for one semantic edge to accumulate evidence from multiple chunks

---

## Gaps and limitations observed

The most important weaknesses were:

- inconsistent alias/acronym resolution
- entity fragmentation caused by punctuation or naming differences
- inconsistent conceptual granularity
- exactly one type per extracted entity in this experiment
- unconstrained/free-form relationship vocabulary
- semantically similar predicates may be generated independently
- negation encoded in relationship names rather than structured polarity
- temporal/configuration semantics encoded through heterogeneous predicates
- entity-resolution failures fragment both knowledge and provenance
- relation-resolution failures likewise prevent evidence consolidation
- edge evidence records extraction provenance rather than exhaustively discovering every supporting passage
- no explicit first-class scientific `Claim` object
- no observed structured distinction between direct assertion, inference, measurement, interpretation, or derived evidence
- no observed confidence value for extracted evidence

---

## Corpus v2 removed benchmark-explanatory language.

Major Stage 2 conclusions survived:
- partial entity/coreference normalization
- persistent alias/granularity fragmentation
- open-vocabulary predicates
- preservation of negation and configuration context
- edge identity and provenance infrastructure

Refined finding:
- contextual unit inference is representation-dependent.
  The 5.0 T commissioning value was inferred in the summary
  but not materialized in the graph, while the isolated NBI
  value 8 was inferred as 8 MW and represented semantically.
The default graph is more capable than a simple entity/relation extraction graph. In particular, Cognee already provides useful machinery for:

---

## Important architectural takeaway

```text
document → chunk → semantic edge → source evidence
```

This makes it a potentially useful substrate for an evolving knowledge system.

However, the graph remains fundamentally **entity-and-edge oriented**, while a scientific knowledge system may need a more explicit model such as:

```text
Claim
    subject
    predicate
    object/value
    polarity
    valid time
    assertion time
    confidence/status
    evidence[]
```

along with explicit models for:

```text
Measurement
Evidence
Source
Entity aliases
Canonical relations
Temporal validity
Revision/supersession
```

Stage 2 therefore suggests that later customization may not require replacing Cognee's underlying graph/provenance infrastructure. Instead, the likely opportunity is to impose stronger identity, relation, claim, temporal, and evidence semantics on top of that substrate.

---

## Questions carried forward

Stage 3 will examine whether Cognee's retrieval layer compensates for some of the graph fragmentation observed here.

Important questions include:

- Can semantic retrieval bridge aliases such as `AFRL` and `Aurora Fusion Research Laboratory`?
- Can retrieval find facts split across `NBI`, `Neutral Beam Injection`, and `Neutral Beam Injection System`?
- How do different search modes use entities, graph relationships, chunks, summaries, and embeddings?
- Does retrieval exploit `edge_text` or provenance evidence?
- How well does retrieval handle negative statements?
- Can it retrieve configuration-dependent facts with the necessary temporal context?
- Does graph fragmentation materially reduce answer quality, or does semantic retrieval hide much of it?