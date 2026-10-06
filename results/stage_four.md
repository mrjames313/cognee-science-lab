# Stage 4 — Mixed Semantic Structure and Annotation

Stage 4 explores whether Cognee can support a heterogeneous knowledge representation in which some parts of the graph remain open-ended, as in the default `KnowledgeGraph`, while selected semantic categories receive stronger structure. The long-term target is not a fully rigid ontology. Instead, the goal is to preserve open-world extraction while introducing strongly modeled “semantic islands” for concepts where precision materially improves retrieval, reasoning, provenance, or maintenance—for example abbreviations and aliases, physical quantities, time, relation senses, and source-linked mention annotations.

A second motivation is the retrieval behavior observed in Stage 3. Raw/source-preserving `DocumentChunk` retrieval, summaries, and the semantic graph can rescue one another, but they also fail differently. Stage 4 therefore asks whether stronger semantic structure can be added without losing the flexibility and source evidence that make the default graph useful.

## 4.1 — `graph_model` boundary probe

### Question

What exactly does a custom `graph_model` replace, and which parts of Cognee’s normal document/chunk/summary/provenance infrastructure remain?

### Experimental model

A deliberately narrow custom model was used so that the experiment tested the `graph_model` boundary rather than a broader domain schema.

```python
class Abbreviation(DataPoint):
    short_form: str
    full_form: str

    metadata: dict = {
        "index_fields": ["short_form", "full_form"],
        "identity_fields": ["short_form"],
    }


class AbbreviationGraph(DataPoint):
    name: Literal["abbreviation_graph"] = "abbreviation_graph"
    abbreviations: list[Abbreviation]

    metadata: dict = {
        "index_fields": [],
        "identity_fields": ["name"],
    }
```

The same revised DOC01 and the same `chunk_size=1000` used in Stages 2–3 were used here so that chunking behavior remained controlled.

### Resulting graph

The custom run produced:

```text
Nodes: 17

TextSummary          6
DocumentChunk        6
Abbreviation         3
TextDocument         1
AbbreviationGraph    1

Edges: 21

6  TextSummary       --made_from-->      DocumentChunk
6  DocumentChunk     --is_part_of-->     TextDocument
6  DocumentChunk     --contains-->       AbbreviationGraph
3  AbbreviationGraph --abbreviations-->  Abbreviation
```

The six `DocumentChunk` boundaries were unchanged from the baseline DOC01 v2 run.

### Extracted abbreviations

The three persisted typed objects were:

```text
AFRL -> Aurora Fusion Research Laboratory
NBI  -> neutral beam injection
ECH  -> electron cyclotron heating
```

Other explicit abbreviation definitions present in the document, such as VCS, PCPS, EDC, RCM, and MPA, did not appear as persisted `Abbreviation` nodes in this run.

### Finding 1 — custom `graph_model` replaces the default semantic layer

The default graph normally contains `Entity`, `EntityType`, and a large collection of open-vocabulary semantic relationships. None of those appeared in the 4.1 graph.

The result is therefore not:

```text
default open graph
        +
typed abbreviation nodes
```

but rather:

```text
Cognee document/chunk/summary infrastructure
        +
custom abbreviation graph
```

This establishes that the ordinary `graph_model` hook is a replacement mechanism for semantic extraction, not an additive augmentation mechanism.

### Finding 2 — document infrastructure survives

The following remained intact:

- `TextDocument`
- `DocumentChunk`
- `TextSummary`
- `DocumentChunk --is_part_of--> TextDocument`
- `TextSummary --made_from--> DocumentChunk`
- the same six chunk boundaries

Thus semantic graph extraction is downstream from, and separable from, Cognee’s basic document/chunk/summary representations.

### Finding 3 — a single persisted root is not inherent

The custom graph contained one `AbbreviationGraph` root because the top-level model itself inherited from `DataPoint` and used a constant identity field:

```text
name = "abbreviation_graph"
```

All six chunks therefore pointed to the same persisted root:

```text
DocumentChunk --contains--> AbbreviationGraph
```

and that root pointed to typed abbreviation objects:

```text
AbbreviationGraph --abbreviations--> Abbreviation
```

Later introspection showed that Cognee’s default `KnowledgeGraph` is instead a plain Pydantic model:

```python
class KnowledgeGraph(BaseModel):
    nodes: list[Node]
    edges: list[Edge]
```

with `Node` and `Edge` also plain Pydantic records rather than `DataPoint`s. Therefore a persisted graph root is a consequence of the custom model design, not a general requirement of Cognee graph extraction.

### Finding 4 — visible topology is coarse, but edge source references retain chunk provenance

Because every chunk points to the shared root, graph topology alone does not reveal which chunk introduced or supported each abbreviation. However, `get_edge_delete_data()` exposed chunk-specific `source_ref_keys` on the custom semantic edges.

Observed support included:

```text
AFRL -> chunk 0
NBI  -> chunks 0, 1
ECH  -> chunks 0, 1
```

The chunk IDs in the source references matched the actual `DocumentChunk` IDs.

Thus the more accurate interpretation is:

> The shared-root topology loses chunk specificity visually, but Cognee retains chunk-level source provenance on the custom semantic edges.

This is adequate for coarse provenance, although it is still less precise than the later target of source-span annotations such as `chunk_id + start_char + end_char`.

### Finding 5 — `provenance_edge_evidence` is not a universal edge ledger

The relational table `provenance_edge_evidence` contained 12 rows:

```text
6  is_part_of
6  contains
```

It contained no `abbreviations` rows, even though those custom semantic edges had valid chunk-specific `source_ref_keys`. `made_from` was also absent.

Therefore Cognee currently exposes at least two provenance mechanisms with different coverage:

```text
edge source references / source_ref_keys
    -> custom abbreviation edges included

provenance_edge_evidence
    -> selective subset of infrastructure edges in this run
```

Absence from `provenance_edge_evidence` should not be interpreted as absence of provenance.

### Finding 6 — typed extraction constrains representation, not recall

The custom `Abbreviation` schema guaranteed the shape of objects that were returned, but only three abbreviation objects were persisted despite several other explicit acronym expansions in the source.

A strongly typed output therefore gives a guarantee like:

```text
if an item is returned as Abbreviation:
    it has short_form + full_form
```

but does not guarantee:

```text
every abbreviation present in the source is returned
```

This distinction will be even more important for physical quantities, temporal expressions, measurements, and scientific claims.

### Finding 7 — relationship namespace collision is real

Cognee used:

```text
DocumentChunk --contains--> AbbreviationGraph
```

as an infrastructure relationship.

The same surface predicate is entirely plausible as a domain relationship, for example:

```text
VacuumVessel --contains--> Plasma
```

The graph therefore has a real namespace/semantic-sense ambiguity in `relationship_name`, not merely a hypothetical one. Future work should distinguish infrastructure relations from domain relations and eventually distinguish multiple domain senses of the same surface verb.

### 4.1 conclusion

`graph_model` gives strong control over the semantic representation, but it does so by replacing the default open semantic graph. Cognee’s document/chunk/summary infrastructure remains intact, and custom semantic edges retain useful chunk-level source references. However, a custom `DataPoint` graph is not automatically exhaustive, and its topology can be coarser than the provenance data attached to the edges.

These results motivate an architecture in which typed semantic structures augment rather than replace the default graph.

---

## 4.2 — Mixed open + typed extraction

### Question

Can a single Cognee extraction preserve the default open-world `KnowledgeGraph` while also extracting a strongly typed semantic side channel?

Cognee’s default extraction structures were first inspected:

```python
class KnowledgeGraph(BaseModel):
    nodes: list[Node]
    edges: list[Edge]
```

where:

```python
class Node(BaseModel):
    id: str
    name: str
    type: str
    description: str


class Edge(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_name: str
    description: str | None
```

These are extraction DTOs, not persisted `DataPoint`s. `relationship_name` is an unconstrained string.

### 4.2a — embedding a `DataPoint` inside `KnowledgeGraph`

The first mixed model attempted to extend the default graph with typed abbreviation objects:

```python
class MixedKnowledgeGraph(KnowledgeGraph):
    abbreviations: list[Abbreviation]
```

where `Abbreviation` was the `DataPoint` class used in 4.1.

#### Structured-output failures

The model reached the LLM, but the generated response schema exposed inherited `DataPoint` persistence fields such as `id` and `metadata`.

OpenAI strict structured output rejected the schema because the inherited open-ended `metadata: dict` did not satisfy strict-schema requirements, causing Cognee/LiteLLM to demote the call to non-strict JSON schema.

More importantly, the LLM attempted to populate `Abbreviation.id` with semantic identifiers such as:

```text
PCPS
VCS
NBI
ECH
AFRL
EDC
RCM
MPA
```

Pydantic then rejected these because the inherited `DataPoint.id` requires a UUID.

The key architectural mismatch is:

```text
KnowledgeGraph / Node / Edge
    = extraction representation

DataPoint
    = persistent graph representation
```

Embedding persistent `DataPoint`s directly inside the generic extraction DTO caused storage-level fields to leak into the LLM schema.

#### Despite the errors, the generic graph persisted

The run ultimately produced a healthy-looking generic graph:

```text
Nodes: 133
  Entity        93
  EntityType    27
  TextSummary    6
  DocumentChunk  6
  TextDocument   1

Edges: 331
```

No `Abbreviation` nodes persisted.

The error log nevertheless showed that the mixed schema was affecting extraction: the LLM attempted to populate abbreviation records for a much broader set than had been persisted in 4.1.

This implies that the extra typed field was not simply ignored. Instead, mixed extraction occurred, but validation/persistence of the typed channel failed.

### 4.2b — plain Pydantic extraction DTO

To isolate extraction from persistence, the typed side channel was changed to a plain Pydantic model:

```python
class AbbreviationExtraction(BaseModel):
    short_form: str = Field(...)
    full_form: str = Field(...)


class MixedKnowledgeGraph(KnowledgeGraph):
    abbreviations: list[AbbreviationExtraction] = Field(...)
```

The field descriptions retained explicit guidance defining abbreviations/acronyms and requiring source-supported full forms.

This removes UUIDs, metadata, timestamps, and other storage concerns from the LLM-facing schema.

#### Persisted graph

The final graph was again the normal open semantic graph:

```text
Nodes: 124
  Entity        88
  EntityType    23
  TextSummary    6
  DocumentChunk  6
  TextDocument   1

Edges: 309
```

No typed abbreviation objects appeared in the persisted graph.

The graph was somewhat smaller than earlier DOC01 runs. In particular, it contained no `abbreviated_as` relation. This raised the possibility that the dedicated abbreviation field might be competing with the generic node/edge channel, but the persisted graph alone could not establish that.

### Direct observation of the parsed mixed extraction

A temporary Pydantic `model_validator(mode="after")` was added to print the fully parsed `MixedKnowledgeGraph` object for each extraction call.

The six calls produced:

```text
generic nodes: 4
 generic edges: 3
 abbreviations: []

generic nodes: 20
 generic edges: 21
 abbreviations:
   EDC -> Edge Density Controller
   VCS -> vertical-control system

generic nodes: 17
 generic edges: 19
 abbreviations:
   PCPS -> Plasma Current Power Supply
   VCS  -> Vertical Control System
   NBI  -> Neutral Beam Injection System
   ECH  -> Electron Cyclotron Heating System

generic nodes: 21
 generic edges: 24
 abbreviations: []

generic nodes: 18
 generic edges: 18
 abbreviations:
   AFRL -> Aurora Fusion Research Laboratory
   NBI  -> neutral beam injection
   ECH  -> electron cyclotron heating

generic nodes: 26
 generic edges: 26
 abbreviations:
   EDC -> Edge Density Controller
   RCM -> Rogowski Current Monitor
   MPA -> Magnetic Probe Array
```

Because extraction may run concurrently, print order should not be assumed to correspond directly to chunk index without explicitly carrying the chunk ID into the diagnostic.

### Finding 1 — mixed open + typed extraction works in one LLM call

This is the central Stage 4.2 result.

The parsed `MixedKnowledgeGraph` simultaneously contained:

```text
generic nodes / generic edges
        +
typed abbreviation DTOs
```

The LLM therefore can produce a heterogeneous extraction representation in a single call.

### Finding 2 — standard Cognee persistence consumes the generic channel but not the added typed DTO field

The final graph contained the generic `Entity` / `EntityType` semantic graph, while the successfully parsed `abbreviations` field did not appear as graph objects.

The effective pipeline is therefore:

```text
DocumentChunk
    ↓
LLM
    ↓
MixedKnowledgeGraph
   ├── nodes / edges      -> consumed by normal Cognee persistence
   └── abbreviations      -> successfully parsed, but not persisted
```

This is a much more favorable result than requiring two independent semantic extraction passes: the typed and open representations can be produced from the same chunk, same model call, and same interpretation.

### Finding 3 — extraction DTOs and persistent graph objects should be separate classes

Stage 4.2a demonstrated that a `DataPoint` is a poor LLM-facing extraction DTO because persistence fields leak into structured output. Stage 4.2b demonstrated that a plain Pydantic DTO works cleanly.

The emerging design principle is:

```text
LLM extraction representation
    plain Pydantic DTOs
        ↓ deterministic conversion
persistent representation
    Cognee DataPoints / graph objects
```

This separation is architectural rather than merely a workaround.

### Finding 4 — typed extraction has substantially better abbreviation recall than 4.1 persistence suggested

Across the mixed extraction calls, the LLM identified eight distinct abbreviations:

```text
AFRL
PCPS
VCS
NBI
ECH
EDC
RCM
MPA
```

This is much broader than the three `Abbreviation` nodes persisted in 4.1.

Therefore the 4.1 result should not be interpreted simply as an LLM inability to recognize the missing abbreviations. The representation/validation/persistence path materially affects what survives into the graph.

### Finding 5 — strong typing does not solve canonical identity

The typed side channel itself produced normalization variants:

```text
VCS -> "vertical-control system"
VCS -> "Vertical Control System"

NBI -> "Neutral Beam Injection System"
NBI -> "neutral beam injection"

ECH -> "Electron Cyclotron Heating System"
ECH -> "electron cyclotron heating"
```

Thus strong typing answers “what kind of object is this?” but not necessarily “which canonical object is this?”

This foreshadows Stage 5 identity work and suggests that typed semantic islands will still require normalization/entity-resolution mechanisms.

### Finding 6 — the generic graph may compete with the typed side channel

The 4.2b generic graph contained 88 entities versus 93 in earlier DOC01 runs and had no `abbreviated_as` edges. One plausible explanation is that abbreviation facts were routed into the dedicated `abbreviations` field rather than redundantly represented in generic `nodes`/`edges`.

However, graph extraction is stochastic enough that this cannot yet be treated as proven. The important established result is that the typed side channel was populated even though it did not persist.

### 4.2c — Relational integrity, chunk-local identity, and unresolved aliases

The mixed extraction result raised a more important question than whether typed abbreviations were persisted:

> Does adding a typed abbreviation side channel interfere with Cognee's generic `nodes` / `edges` extraction, particularly when an abbreviation is used to express important relational facts?

This matters because Cognee's downstream generic graph construction assumes that relational facts required by the open graph are represented through the ordinary `KnowledgeGraph.nodes` and `KnowledgeGraph.edges` fields. The additional `abbreviations` field cannot itself serve as an endpoint for a generic `Edge`.

A diagnostic validator was therefore added to inspect each parsed `MixedKnowledgeGraph` before persistence. For each extraction it reported:

- generic node and edge counts;
- typed abbreviation records;
- any generic edges whose endpoints were absent from `nodes`;
- generic nodes corresponding to typed abbreviations;
- edges incident on those nodes;
- selected VCS / vertical-motion relations independent of the typed abbreviation list.

#### Structural result: generic graph integrity was preserved

Across repeated runs:

```text
dangling generic edges: 0
```

for every extraction.

Thus the added typed field did not cause generic `Edge` objects to reference entities that existed only in `abbreviations[]`.

The structural contract remained:

```text
generic Edge endpoints
        ↓
generic Node IDs
```

rather than:

```text
generic Edge
        ↓
typed side-channel object
```

This is an important pass condition for mixed extraction.

### Relations expressed through abbreviations were still extracted

The stronger test was whether relational facts survived when the source used only an abbreviation rather than repeating the full entity name.

Several cases showed that they did.

#### VCS

The source first introduces:

```text
Vertical Control System (VCS)
```

and later asserts facts using the short form and contextual references such as:

```text
the VCS operated ...
the controller receives ...
[the controller] applies corrective commands ...
```

One extraction produced:

```text
VCS -> Vertical Control System
```

in the typed channel, while the generic channel contained:

```text
Vertical Control System
    --receives_estimates_from--> Magnetic Probe Array

Vertical Control System
    --commands--> Vertical-control coils

Vertical Control System
    --operated_during--> Campaign A
```

Thus abbreviation- and coreference-mediated facts remained available to generic relation extraction.

#### PCPS

The full form is introduced earlier as:

```text
Plasma Current Power Supply (PCPS)
```

while a later sentence uses only `PCPS` to describe the operating-current limitation.

The generic extraction attached the resulting facts to:

```text
Plasma Current Power Supply
```

rather than requiring the expanded form to appear again in the same sentence.

#### EDC

Similarly, after:

```text
Edge Density Controller (EDC)
```

the source uses combinations of:

```text
EDC
it
the controller
```

to describe later behavior.

Generic extraction successfully produced relations such as:

```text
Edge Density Controller
    --adjusts--> gas flow

Edge Density Controller
    --was_not_an_experimental_variable_in--> H1-1854

Edge Density Controller
    --increases_when_edge_density_falls--> gas flow
```

#### RCM and MPA

A particularly useful example occurs after introducing:

```text
Rogowski Current Monitor (RCM)
Magnetic Probe Array (MPA)
```

The source later uses the abbreviations themselves to compare the two diagnostics.

The generic graph successfully represented relationships between the expanded concepts, demonstrating that both endpoints of a relation can depend on abbreviation interpretation without the relation being lost.

### Cross-chunk behavior exposed a different problem

Repeated extraction of the chunk containing the control-room shorthand produced a more revealing set of outcomes.

That chunk contains local definitions for EDC, RCM, and MPA, but uses `VCS` without containing the earlier expansion `Vertical Control System (VCS)`.

One run produced:

```text
abbreviations:
    EDC -> Edge Density Controller
    VCS -> VCS
    RCM -> Rogowski Current Monitor
    MPA -> Magnetic Probe Array

generic:
    VCS --reduced--> Vertical motion
    VCS --was_tuned_during--> Current ramp
```

A later run produced:

```text
abbreviations:
    EDC -> Edge Density Controller
    RCM -> Rogowski Current Monitor
    MPA -> Magnetic Probe Array
```

with no VCS abbreviation record at all, while still producing:

```text
VCS --reduces--> vertical motion
VCS --operated_during--> current ramp
```

This second behavior is arguably more semantically correct given the current typed-field instruction. The local chunk provides evidence that `VCS` is an entity participating in the event, but does not itself provide evidence for what `VCS` expands to.

The extractor therefore effectively distinguishes:

```text
I can identify this local entity:
    VCS

I can extract facts about it:
    VCS --reduces--> vertical motion

but I cannot locally establish:
    VCS == Vertical Control System
```

This is an important distinction.

### Much apparent variability is explained by chunk-local evidence

Initial runs appeared to show substantial stochastic variation in how VCS was represented:

```text
Vertical Control System
vertical-control system
VCS
```

Some true LLM variability remains possible, but the experiments show that chunk boundaries explain an important portion of the behavior.

A chunk containing the explicit definition:

```text
Vertical Control System (VCS)
```

can naturally produce:

```text
VCS -> Vertical Control System
```

and attach generic relations to the expanded node.

A later chunk containing only:

```text
VCS
```

cannot establish that expansion from its own source text, even though it can still correctly extract local relations involving `VCS`.

The current extraction behavior is therefore better characterized as:

```text
chunk-local semantic interpretation
        ↓
local entity naming / resolution
        ↓
local relation extraction
        ↓
later graph integration
```

rather than:

```text
document-wide identity resolution
        ↓
all chunk relations use canonical entity IDs
```

The ordering of diagnostic printouts should also not be interpreted as a sequential knowledge-building process. Extraction calls may complete in a different order from document order, and observations from one completed chunk are not automatically evidence that a later extraction call was given those observations as context.

### Important finding: relation extraction can succeed before identity resolution

The VCS control-room example is especially useful:

```text
During one VCS tuning sequence ...
"the controller reduced vertical motion during the current ramp."
```

Even without locally knowing that `VCS` expands to `Vertical Control System`, the extractor can infer:

```text
"the controller"
       ↓
VCS
```

and produce:

```text
VCS --reduces--> vertical motion
```

Thus the unresolved identity does not prevent extraction of the underlying relational fact.

This suggests that a provisional entity such as `VCS` is not necessarily an extraction failure. It can act as a locally meaningful object to which valid facts are attached before canonical identity is known.

### “Known unknowns” may be a useful semantic state

The current abbreviation schema represents resolved abbreviations:

```text
VCS -> Vertical Control System
```

but does not explicitly represent:

```text
encountered abbreviation-like token: VCS
resolution status: unresolved
```

The experiments suggest that this intermediate state could be valuable.

A richer representation might eventually distinguish:

```text
resolved alias
    VCS -> Vertical Control System

unresolved alias / mention
    VCS -> UNKNOWN

ordinary entity
    VCS
    + locally extracted relations
```

This would permit the system to retain both:

1. the fact that resolution is incomplete; and
2. useful relational knowledge already attached to the unresolved entity.

Later evidence could then resolve:

```text
VCS == Vertical Control System
```

and reconcile or redirect the existing facts without necessarily repeating the original relation extraction.

This is potentially useful beyond abbreviations. The same principle applies to:

- pronouns and contextual references;
- unfamiliar identifiers;
- equipment tags;
- experiment IDs;
- aliases;
- partial names;
- ambiguous terminology;
- relation senses whose canonical meaning is not yet known.

The ability to explicitly represent **“I have evidence about this object, but I do not yet know exactly what canonical object it is”** may be an important property of a scientific memory system.

### No resolution architecture selected yet

Several possible approaches now exist, and Stage 4 does not yet choose among them.

One option is a document-context pass that discovers aliases and identities before relation extraction:

```text
document
    ↓
identity / alias discovery
    ↓
chunk extraction with shared context
```

Another is sequential extraction with an evolving symbol table:

```text
chunk 0 → learned identities
             ↓
chunk 1 → updated identities
             ↓
...
```

A third is to preserve unresolved entities and resolve only those that require later reconciliation:

```text
local extraction
    ↓
resolved entities + unresolved entities
    ↓
targeted later resolution
    ↓
relink / merge existing facts
```

The last approach may require fewer additional passes and explicitly preserves useful uncertainty, but the experiments so far do not establish which architecture is preferable.

This should remain an open design question for the later identity-resolution and custom-pipeline stages.

### Updated Stage 4.2 conclusions

The mixed extraction experiments now support the following stronger conclusions:

1. **Typed side-channel extraction does not inherently break generic relation extraction.** Generic edges remained structurally valid, with no dangling endpoints observed.

2. **Facts expressed using abbreviations are still captured by the generic graph.** This includes cases in which one or both relation endpoints require abbreviation interpretation.

3. **Local coreference resolution can succeed even when global identity resolution does not.** For example, `"the controller"` can resolve to local `VCS`, allowing the underlying relation to be extracted.

4. **Typed abbreviation extraction is not a canonicalization stage.** `abbreviations[]` and generic `nodes[]` / `edges[]` are sibling outputs from the same LLM interpretation rather than a deterministic pipeline in which abbreviation resolution precedes graph construction.

5. **Chunk-local evidence materially affects entity naming.** A chunk containing an explicit expansion may emit `Vertical Control System`; another chunk containing only `VCS` may retain `VCS` as the relational endpoint.

6. **Unresolved identity does not imply lost knowledge.** Useful relational facts can accumulate against a provisional entity and potentially be reconciled later.

7. **Representing unresolved semantic objects explicitly may be valuable.** A future system may benefit from knowing not only what has been resolved, but also what remains unresolved and why.

The central Stage 4.2 picture is therefore:

```text
source chunk
    ↓
local semantic interpretation
    ├── generic nodes + relations
    └── typed semantic observations
            ↓
some identities resolved
some identities provisional
            ↓
later persistence / reconciliation / canonicalization
```

This moves the primary concern from **whether mixed extraction loses relational facts** to **how locally extracted facts and typed semantic evidence should later participate in identity resolution and canonical graph construction**.

### 4.2 conclusion

Cognee’s current structured-output machinery can support a heterogeneous extraction envelope containing both:

```text
open-world generic semantics
        +
strongly typed semantic side channels
```

in a single model call.

The limitation is downstream: Cognee’s standard `KnowledgeGraph` persistence path processes the generic `nodes`/`edges` fields but does not automatically persist additional typed DTO fields.

This suggests a promising architecture for the next experiment:

```text
one mixed extraction call
        ↓
MixedKnowledgeGraph
   ├── generic nodes/edges -> normal Cognee graph persistence
   └── typed DTOs          -> custom deterministic persistence
```

Stage 4.3 therefore tests whether typed DTOs extracted in the same call can be converted to `DataPoint`s and persisted as an overlay alongside the ordinary Cognee semantic graph.

## 4.3 — Persistent typed-observation overlay

### Question

Stage 4.2 established that a single LLM call can produce both:

```text
generic KnowledgeGraph nodes / edges
        +
typed abbreviation DTOs
```

but Cognee's normal persistence path consumes only the generic `nodes` and `edges`. The typed side channel is successfully parsed but otherwise discarded.

Stage 4.3 therefore asked:

> Can typed observations produced during the same extraction call be converted to persistent `DataPoint`s and stored alongside Cognee's normal open semantic graph without replacing or disrupting it?

The purpose was deliberately limited. This stage did **not** attempt to canonicalize aliases, merge generic entities, attach observations to source chunks, or resolve unknown abbreviations.

### Persistent observation model

The extraction representation remained a plain Pydantic DTO:

```python
class AbbreviationExtraction(BaseModel):
    short_form: str
    full_form: str
```

A separate persistent model was introduced:

```python
class AbbreviationObservation(DataPoint):
    short_form: str
    full_form: str

    metadata: dict = {
        "index_fields": ["short_form", "full_form"],
        "identity_fields": ["short_form", "full_form"],
    }
```

The distinction is intentional:

```text
AbbreviationExtraction
    = LLM-facing extraction record

AbbreviationObservation
    = persistent semantic observation
```

Typed results were captured from the mixed extraction and, after normal Cognee `cognify()` completed, deterministically converted to `AbbreviationObservation` objects and persisted with `add_data_points()`.

### Extraction result

One run produced 17 captured records:

```text
PCPS -> Plasma Current Power Supply
VCS  -> Vertical Control System
NBI  -> Neutral Beam Injection System
ECH  -> Electron Cyclotron Heating System
H-1  -> Helios 1
AFRL -> Aurora Fusion Research Laboratory
NBI  -> neutral beam injection
ECH  -> electron cyclotron heating
NBI  -> ""
ECH  -> ""
VCS  -> Vertical Control System
EDC  -> Edge Density Controller
AFRL -> ""
EDC  -> Edge Density Controller
VCS  -> ""
RCM  -> Rogowski Current Monitor
MPA  -> Magnetic Probe Array
```

After exact `(short_form, full_form)` deduplication:

```text
17 captured records
15 distinct observations
15 persisted AbbreviationObservation nodes
```

### Finding 1 — typed observations can coexist with the ordinary Cognee graph

The resulting graph contained:

```text
Entity                     76
EntityType                 23
AbbreviationObservation    15
TextSummary                 6
DocumentChunk               6
TextDocument                1
```

Thus typed observations can be added as an overlay without replacing the normal open-world semantic graph.

The resulting architecture was:

```text
normal Cognee graph
    Entity
    EntityType
    generic relationships

        +

typed persistent observations
    AbbreviationObservation
```

This establishes the main Stage 4.3 result:

> Additional strongly typed semantic objects can be persisted alongside Cognee's normal semantic graph even though Cognee's standard mixed-extraction persistence does not create those objects automatically.

### Finding 2 — persistence should preserve observations rather than prematurely canonicalize them

Several short forms appeared with multiple interpretations:

```text
NBI -> Neutral Beam Injection System
NBI -> neutral beam injection
NBI -> ""

ECH -> Electron Cyclotron Heating System
ECH -> electron cyclotron heating
ECH -> ""

VCS -> Vertical Control System
VCS -> ""
```

These were intentionally preserved as separate observations rather than normalized during persistence.

At this stage, an observation means:

```text
the extraction produced this semantic interpretation
```

not:

```text
this is the final canonical identity of this symbol
```

That distinction leaves normalization, equivalence, and canonical identity for later stages.

### Finding 3 — unresolved observations emerged naturally

The empty expansions were especially interesting:

```text
NBI  -> ""
ECH  -> ""
AFRL -> ""
VCS  -> ""
```

Although the initial schema had not explicitly modeled an unresolved state, these outputs effectively represented:

```text
this token appears to be abbreviation-like or shorthand,
but its expansion cannot be established from the local context
```

This provided an early example of a potentially useful **known-unknown** state.

Rather than discarding these records, Stage 4.3 retained them for later investigation.

### Finding 4 — the overlay was initially disconnected

`add_data_points()` successfully persisted the 15 observation nodes, but no graph relationships connected them to:

- the source `DocumentChunk`;
- corresponding generic `Entity` nodes;
- canonical entities;
- other abbreviation observations.

Thus Stage 4.3 produced:

```text
AbbreviationObservation
        [isolated]
```

rather than:

```text
DocumentChunk
      |
      v
AbbreviationObservation
      |
      v
Entity
```

No abbreviation-specific entries appeared in the relational provenance evidence table either.

This cleanly identified the next missing capability: **source association**.

### Finding 5 — the overlay does not canonicalize the generic graph

The generic semantic graph remained independently extracted.

Manual graph inspection showed that some generic `Entity` nodes still used abbreviation/acronym names such as:

```text
afrl
ech
```

even though typed observations elsewhere contained expanded forms.

This is important because it confirms that:

```text
typed abbreviation extraction
```

does **not** currently feed back into:

```text
generic Entity identity / naming
```

The overlay therefore augments the generic graph rather than cleaning, merging, or canonicalizing it.

This is not considered a failure of Stage 4.3; canonical identity is explicitly deferred to Stage 5.

### 4.3 conclusion

Stage 4.3 demonstrated that typed semantic results obtained during mixed extraction can be deterministically converted to persistent `DataPoint`s and stored alongside Cognee's normal graph.

However, these observations initially lacked source provenance and were not connected to or used to canonicalize generic entities.

The resulting representation was therefore:

```text
open semantic graph
        +
persistent typed observations
```

with reconciliation between those representations still unresolved.

---

## 4.4 — Source-linked typed observations

### Question

Once typed observations could be persisted, the next requirement was to preserve **where each observation came from**.

This became particularly important after observing cases such as:

```text
VCS -> Vertical Control System
VCS -> ""
```

Without source context, these can look contradictory.

With source context, they may instead mean:

```text
chunk A:
    enough local evidence exists to resolve VCS

chunk B:
    VCS is recognized and participates in useful facts,
    but its expansion is not locally available
```

Stage 4.4 therefore asked:

> Can each typed semantic observation be associated directly with the `DocumentChunk` whose extraction produced it?

No attempt was made yet to perform cross-chunk resolution, canonicalization, source-span annotation, or graph merging.

### Capturing extraction together with its input chunk

The earlier diagnostic approach captured typed results inside a Pydantic validator. This made it difficult to reliably associate results with their source chunks because chunk extraction is concurrent.

Stage 4.4 instead intercepted extraction at the chunk-processing boundary and retained:

```text
(DocumentChunk, MixedKnowledgeGraph)
```

pairs.

Conceptually:

```text
DocumentChunk 0
      ↓
MixedKnowledgeGraph 0

DocumentChunk 1
      ↓
MixedKnowledgeGraph 1

...
```

Extraction remained parallel; the experiment merely preserved the association between each input chunk and its corresponding structured result.

### Source-specific persistent model

The persistent observation was extended with source identity:

```python
class AbbreviationObservation(DataPoint):
    short_form: str
    full_form: str

    source_chunk_id: str
    source_chunk_index: int

    observed_in: DocumentChunk

    metadata: dict = {
        "index_fields": [
            "short_form",
            "full_form",
            "source_chunk_id",
        ],
        "identity_fields": [
            "short_form",
            "full_form",
            "source_chunk_id",
        ],
    }
```

Including `source_chunk_id` in identity intentionally changes the semantics from Stage 4.3.

Two identical observations from two different chunks are now distinct evidence objects:

```text
chunk 1: VCS -> Vertical Control System

chunk 4: VCS -> Vertical Control System
```

rather than being globally deduplicated into one record.

The nested `observed_in: DocumentChunk` field also creates an explicit graph relationship:

```text
AbbreviationObservation
        --observed_in-->
DocumentChunk
```

### Extraction result

The run produced 23 source-linked observations.

#### Chunk 0

```text
AFRL -> Aurora Fusion Research Laboratory
NBI  -> neutral beam injection
ECH  -> electron cyclotron heating
```

#### Chunk 1

```text
PCPS -> Plasma Current Power Supply
VCS  -> Vertical Control System
NBI  -> Neutral Beam Injection
ECH  -> Electron Cyclotron Heating
H-1  -> Helios 1
MA   -> ""
MW   -> ""
kHz  -> ""
T    -> ""
```

#### Chunk 2

```text
EDC -> Edge Density Controller
VCS -> ""
RCM -> Rogowski Current Monitor
MPA -> Magnetic Probe Array
```

#### Chunk 3

```text
VCS -> ""
```

#### Chunk 4

```text
EDC  -> Edge Density Controller
VCS  -> Vertical Control System
NBI  -> ""
ECH  -> ""
AFRL -> ""
MA   -> ""
```

#### Chunk 5

```text
no observations
```

All 23 observations persisted.

### Finding 1 — source-linked overlay persistence works

The resulting graph contained:

```text
Entity                     81
EntityType                 25
AbbreviationObservation    23
TextSummary                 6
DocumentChunk               6
TextDocument                1
```

and exactly:

```text
23 AbbreviationObservation --observed_in--> DocumentChunk
```

relationships.

This satisfies the primary Stage 4.4 success criterion.

The graph now contains two parallel but source-grounded semantic representations:

```text
DocumentChunk
      |
      | contains
      v
generic Entity graph

and

AbbreviationObservation
      |
      | observed_in
      v
DocumentChunk
```

### Finding 2 — resolved and unresolved observations can coexist without contradiction

VCS provides the clearest example:

```text
chunk 1:
    VCS -> Vertical Control System

chunk 2:
    VCS -> ""

chunk 3:
    VCS -> ""

chunk 4:
    VCS -> Vertical Control System
```

The source links change the meaning of these records.

They need not be interpreted as four competing global assertions. Instead, they represent four local extraction states:

```text
chunk 1:
    locally resolved

chunk 2:
    recognized but locally unresolved

chunk 3:
    recognized but locally unresolved

chunk 4:
    locally resolved
```

This is a substantially more useful representation than a document-level abbreviation table that discards where each assertion originated.

It also provides evidence for a later resolution process:

```text
multiple local observations
        ↓
cross-chunk / document-level reconciliation
        ↓
possible canonical identity
```

without requiring that reconciliation during initial extraction.

### Finding 3 — unresolved knowledge can coexist with useful generic relations

Earlier Stage 4.2 experiments showed that chunks containing unresolved `VCS` mentions could nevertheless extract useful relations involving `VCS`, including vertical-motion-control facts.

Stage 4.4 now gives those unresolved typed observations explicit source context.

Conceptually:

```text
chunk 2
  |
  +-- AbbreviationObservation:
  |      VCS -> unresolved
  |
  +-- generic semantic facts involving VCS
```

This supports the idea that identity resolution and relation extraction do not necessarily need to happen in strict sequence.

A provisional entity can accumulate meaningful local facts before its global identity has been resolved.

### Finding 4 — broader wording reveals that "abbreviation" is too narrow a semantic category

The revised extraction wording produced several additional forms:

```text
H-1 -> Helios 1

MA  -> ""
MW  -> ""
kHz -> ""
T   -> ""
```

These expose multiple semantic categories currently being represented by the same `AbbreviationObservation` type.

For example:

```text
VCS -> Vertical Control System
    acronym / abbreviation

H-1 -> Helios 1
    alias / shorthand

MW -> ""
kHz -> ""
T -> ""
    unit symbols

VCS -> ""
    unresolved abbreviation / shorthand
```

The extraction is therefore identifying a useful broader class of compact or alternate surface forms, but `AbbreviationObservation` is not yet a sufficiently precise ontology for them.

This is recorded as a finding rather than corrected in Stage 4.

### Finding 5 — source linkage is independent of Cognee's relational provenance ledger

All 23 `observed_in` relationships were present in the graph.

However, `observed_in` did not appear among the relationships recorded in Cognee's `provenance_edge_evidence` table.

This reinforces an earlier Stage 4 result:

```text
graph relationship persistence
```

and:

```text
relational provenance_edge_evidence
```

are distinct mechanisms with different coverage.

The explicit graph edge is therefore currently the authoritative representation of the observation-to-source association created by this experiment.

### Finding 6 — source-linked observations still do not canonicalize generic entities

Even with source-linked typed evidence, generic graph extraction remains independent.

Manual inspection still found some ordinary `Entity` nodes represented by acronym or abbreviation names such as:

```text
afrl
ech
```

rather than being automatically reconciled with the corresponding expanded names.

Thus the current system can contain simultaneously:

```text
generic Entity("afrl")

AbbreviationObservation(
    short_form="AFRL",
    full_form="Aurora Fusion Research Laboratory"
)
```

without any explicit identity relationship between them.

Likewise, source-linked abbreviation evidence does not imply that generic relations have been rewritten to use a canonical entity.

This is an important Stage 4 boundary:

> Mixed typed observations provide evidence that can later support canonicalization, but they do not themselves perform canonicalization.

That problem belongs to Stage 5.

### 4.4 conclusion

Stage 4.4 successfully extended the mixed semantic overlay with source-level provenance.

Each typed observation can now retain the identity of the source chunk from which it was extracted, while the normal Cognee semantic graph continues to be generated independently.

The resulting architecture is:

```text
                    DocumentChunk
                    /           \
                   /             \
          generic semantic      source of
             extraction        typed observation
                |                    |
                v                    v
             Entity      AbbreviationObservation
```

The typed side can represent both locally resolved and locally unresolved knowledge:

```text
VCS -> Vertical Control System
```

or:

```text
VCS -> unresolved
```

while preserving the chunk in which each observation occurred.

No attempt is yet made to:

- merge aliases;
- create canonical entities;
- resolve unknown abbreviations from other chunks;
- rewrite generic graph endpoints;
- distinguish acronyms from aliases, units, and other shorthand;
- attach exact character spans;
- reconcile contradictory or competing observations.

Those are intentionally deferred.

---

## Stage 4 overall conclusion

Stage 4 began with the question of whether stronger semantic structure could be introduced without sacrificing Cognee's open-ended semantic graph.

The experiments established four increasingly strong results:

```text
4.1
custom graph_model
    -> strong typing is possible
    -> but replaces the default semantic graph

4.2
mixed extraction DTO
    -> generic + typed semantics can be produced
       in the same LLM call

4.3
persistent overlay
    -> typed observations can coexist with
       the normal generic graph

4.4
source-linked overlay
    -> typed observations can retain the
       DocumentChunk that produced them
```

The resulting prototype architecture is therefore:

```text
source document
      ↓
DocumentChunk
      ↓
single mixed extraction
      ├───────────────────────────────┐
      ↓                               ↓
generic open semantics       typed semantic observations
Entity / EntityType          abbreviation / alias evidence
generic relations            resolved or unresolved
      │                               │
      │                               └── observed_in ──> DocumentChunk
      │
      └── normal Cognee integration
```

This preserves three useful properties simultaneously:

1. **Open-world extraction** remains available for semantic information not anticipated by a fixed schema.
2. **Selected semantic concepts can receive stronger structure.**
3. **Typed interpretations can retain source context and uncertainty rather than immediately becoming canonical facts.**

The experiments also expose the next class of problems clearly.

The generic graph may still contain fragmented or abbreviation-named entities such as `afrl` and `ech`; typed observations may contain multiple expansions or unresolved forms for the same short form; and compact surface forms currently mix acronyms, aliases, unit symbols, and other shorthand.

Stage 4 therefore stops before attempting to solve identity.

The next stage asks:

> Given generic entities plus source-grounded semantic observations, how should identity, aliasing, unresolved references, and eventual canonicalization be represented and reconciled?

That becomes the central problem of **Stage 5 — identity, resolution, and semantic reconciliation**.