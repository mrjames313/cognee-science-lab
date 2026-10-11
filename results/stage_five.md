# Stage 5.1 — Identity Benchmark and Fragmentation Inventory

## Objective

Stage 5.1 examined how Cognee's default semantic graph handles identity, aliases, acronyms, contextual references, and potentially confusable entities.

The goal was diagnostic rather than corrective:

> Determine where identity resolution already works, where semantic entities become fragmented, where source meaning survives despite representation changes, and what information is available to support a future non-destructive resolution layer.

The tests use the existing DOC01 graph together with the source-linked `AbbreviationObservation` overlay created in Stage 4.

The benchmark intentionally distinguishes several different failure modes:

- multiple graph nodes representing the same semantic entity;
- failure to materialize a semantic entity at all;
- failure to resolve a contextual reference;
- successful reference resolution but failure to extract the associated assertion;
- inappropriate merging of distinct but lexically similar entities;
- preservation of source meaning using a representation different from the source wording.

These should not all be treated as the same "entity resolution" problem.

---

## Benchmark categories

### Entity identity

The benchmark tested whether known aliases and naming variants were represented as one semantic entity.

Cases:

- `ID01_VCS`
- `ID02_AFRL`
- `ID03_H1`
- `ID04_NBI`
- `ID05_ECH`
- `ID06_EDC`

### Contextual references
5.2
These test source phrases such as:

```text
"the controller"
```

where the correct referent must be inferred from nearby context.

Cases:

- `REF01_VCS_CONTROLLER`
- `REF02_EDC_CONTROLLER`

The benchmark evaluates whether the semantic assertion associated with the reference survives; it does not require Cognee to create an `Entity("controller")`.

### Negative identity controls

These test cases where lexically related concepts must remain distinct.

Cases:

- `NEG01_AURORA`
- `NEG02_HELIOS`

---

# Results

## ID01 — VCS / Vertical Control System

Expected identity:

```text
VCS
Vertical Control System
vertical-control system
```

The generic graph contains a single semantic representation:

```text
vertical control system
```

with facts distributed across several chunks.

The typed observation layer contains:

```text
chunk 1: VCS -> Vertical Control System
chunk 2: VCS -> unresolved
chunk 3: VCS -> unresolved
chunk 4: VCS -> Vertical Control System
```

This reveals an important distinction.

The generic graph successfully consolidated VCS globally even when some local typed observations could not independently resolve the abbreviation.

### Chunk 3 special case

Chunk 3 contains the source fact:

```text
VCS update rate | 10 kHz
```

but the generic `vertical control system` entity is not associated with that chunk.

Instead, Cognee extracted:

```text
Helios-1 --has_vcs_update_rate--> 10 kHz
```

with provenance pointing to chunk 3.

Thus the semantic information was preserved even though the local VCS mention was not represented as a reference to the canonical VCS entity.

### Assessment

```text
identity ground truth:          unambiguous
generic consolidation:          PASS
fact preservation:              PASS
mention-level attribution:      incomplete
representation fidelity:        transformed
```

This is an important example of semantic preservation without faithful preservation of the source-level entity structure.

---

## ID02 — AFRL / Aurora Fusion Research Laboratory

Expected identity:

```text
AFRL
Aurora Fusion Research Laboratory
```

The generic graph contains two separate entities:

```text
aurora fusion research laboratory
afrl
```

The typed observations show:

```text
chunk 0: AFRL -> Aurora Fusion Research Laboratory
chunk 4: AFRL -> unresolved
```

Facts associated with the laboratory and facts associated with the acronym are therefore divided between different generic nodes.

### Assessment

```text
identity ground truth:          unambiguous
typed evidence available:       YES
generic consolidation:          FAIL
fact preservation:              PASS
fact concentration:             FAIL
canonical naming:               fragmented
```

This is a strong example of document-level identity information being available but not reused consistently across chunks.

It provides a good motivation for document-level semantic context such as a future `DefinitionSummary`.

---

## ID03 — H-1 / Helios-1

Expected identity:

```text
H-1
Helios 1
Helios-1
```

The generic graph contains only:

```text
helios-1
```

and this node accumulates facts from throughout the document.

The typed layer contains:

```text
H-1 -> Helios 1
```

There is no independent `H-1` or `Helios 1` generic entity.

### Assessment

```text
identity ground truth:          unambiguous
typed evidence available:       YES
generic consolidation:          PASS
fact preservation:              PASS
fact concentration:             PASS
canonical naming:               PASS
```

This is a useful positive control.

However, because `Helios-1` appears extensively elsewhere in the document, this test alone does not prove exactly how Cognee resolved the individual `H-1` occurrence.

The important result is that no visible fragmentation remains in the final semantic graph.

A future resolution layer should therefore avoid creating redundant structures around cases Cognee has already resolved successfully.

---

## ID04 — NBI / Neutral Beam Injection

Expected identity includes:

```text
NBI
Neutral Beam Injection
neutral beam injection
Neutral Beam Injection System
```

The generic graph contains three representations:

```text
neutral beam injection
neutral beam injection system
nbi
```

The typed observations contain:

```text
chunk 0: NBI -> neutral beam injection
chunk 1: NBI -> Neutral Beam Injection
chunk 4: NBI -> unresolved
```

Semantic facts are divided between all three generic nodes.

For example, different representations carry information about:

- auxiliary heating;
- Campaign A operation;
- authorized power;
- installed capacity.

### Assessment

```text
identity ground truth:          unambiguous
typed evidence available:       YES
generic consolidation:          FAIL
fact preservation:              PASS
fact concentration:             FAIL
canonical naming:               fragmented
```

Unlike AFRL, this is not simply acronym-vs-full-name fragmentation.

The variants include:

```text
neutral beam injection
neutral beam injection system
NBI
```

so purely lexical normalization is insufficient.

### Additional structural clue

All of these representations also have compatible type information, such as:

```text
is_a -> heating system
```

or:

```text
is_a -> system
```

That provides another potentially useful identity-resolution signal.

For example:

```text
neutral beam injection --is_a--> heating system
```

is semantically compatible with an entity named:

```text
neutral beam injection system
```

This should not be treated as a hard rule, but type compatibility can contribute evidence to a future resolver.

---

## ID05 — ECH / Electron Cyclotron Heating

ECH exhibits essentially the same pattern as NBI.

Generic entities:

```text
electron cyclotron heating
electron cyclotron heating system
ech
```

Typed observations:

```text
chunk 0: ECH -> electron cyclotron heating
chunk 1: ECH -> Electron Cyclotron Heating
chunk 4: ECH -> unresolved
```

Again, facts are distributed across the three generic nodes.

### Assessment

```text
identity ground truth:          unambiguous
typed evidence available:       YES
generic consolidation:          FAIL
fact preservation:              PASS
fact concentration:             FAIL
canonical naming:               fragmented
```

NBI and ECH together suggest a systematic pattern:

> A technical process name, a "... system" variant, and its acronym can be represented as separate entities across chunks even when the document provides explicit abbreviation evidence.

As with NBI, compatible `is_a` relationships provide potentially useful supporting evidence:

```text
electron cyclotron heating
    --is_a--> heating system

electron cyclotron heating system
    --is_a--> system
```

This is potentially meaningful for resolution, but blindly stripping words such as `system` would be unsafe because the process and its implementation may legitimately be distinct in other domains.

---

## ID06 — EDC / Edge Density Controller

Expected identity:

```text
EDC
Edge Density Controller
```

The generic graph contains only:

```text
edge density controller
```

across chunks 2 and 4.

Typed observations are also consistently resolved:

```text
chunk 2: EDC -> Edge Density Controller
chunk 4: EDC -> Edge Density Controller
```

No separate `EDC` generic entity was created.

### Assessment

```text
identity ground truth:          unambiguous
typed evidence available:       YES
generic consolidation:          PASS
fact preservation:              PASS
fact concentration:             PASS
canonical naming:               PASS
```

EDC is another useful positive control.

The entity identity results now divide roughly into:

```text
successful consolidation:
    VCS
    H-1 / Helios-1
    EDC

fragmentation:
    AFRL
    NBI
    ECH
```

Therefore the important question is not simply:

```text
Can Cognee resolve acronyms?
```

It clearly can in some circumstances.

The more interesting question is what evidence distinguishes successful and unsuccessful resolution.

Candidate factors include:

- explicit local expansion;
- prior document-level definitions;
- acronym-only later mentions;
- semantic variants such as "... system";
- `is_a` compatibility;
- shared neighbors and relations;
- strength of the existing entity representation;
- document context.

---

# Contextual-reference tests

## REF01 — "the controller" -> Vertical Control System

Source context includes:

```text
During one VCS tuning sequence ...
"the controller reduced vertical motion during the current ramp."
```

The semantic graph contains:

```text
vertical control system
    --reduces_vertical_motion_in-->
helios-1
```

The extracted edge text is:

```text
The Vertical Control System controller reduced vertical motion
during the current ramp in Helios-1 commissioning.
```

Most importantly, provenance confirms that this exact semantic edge came from chunk 2:

```text
relationship:
    reduces_vertical_motion_in

source:
    vertical control system

destination:
    helios-1

provenance:
    chunk_index = 2
    source_task = extract_chunks_from_documents
    evidence_kind = extracted
```

### Assessment

```text
source reference recognized:        PASS
correct canonical referent:         PASS
specific semantic assertion:        PASS
source-chunk provenance:             PASS
structural fidelity of assertion:    PARTIAL
```

Cognee successfully interpreted:

```text
"the controller"
```

as the Vertical Control System.

However, the resulting graph does not preserve the source statement in a fully decomposed representation.

The source concept is approximately:

```text
subject:
    Vertical Control System

action:
    reduce

object:
    vertical motion

during:
    current ramp

context:
    Helios-1 commissioning
```

while the graph produces:

```text
Vertical Control System
    --reduces_vertical_motion_in-->
Helios-1
```

The qualifier `"during the current ramp"` survives in `edge_text`, but is not represented as a first-class semantic qualifier.

This suggests that default Cognee edges preserve some semantic detail textually but do not provide a general structured representation for qualifiers such as:

- during;
- before / after;
- under condition X;
- at configuration Y;
- with confidence Z.

That issue is relevant to later scientific claim modeling, but does not need to be solved during identity work.

---

## Source-level mentions and canonical identity

REF01 also exposes a potentially important missing representation.

The source contains:

```text
"the controller"
```

while the graph correctly resolves this to:

```text
Vertical Control System
```

But the current graph does not appear to preserve the explicit correspondence:

```text
this particular source occurrence of "the controller"
    -> Vertical Control System
```

Instead, what survives is approximately:

```text
DocumentChunk
    -> semantic entity

semantic edge
    -> provenance back to DocumentChunk
```

This is sufficient to identify the supporting chunk, but not the exact source mention or character span.

A future non-destructive representation could preserve:

```text
Mention
    surface_text = "the controller"
    source_chunk = chunk 2
    start_char = ...
    end_char = ...
    resolution_status = resolved

Mention
    --resolves_to-->
Vertical Control System
```

This would be useful even for text-oriented retrieval.

For example, retrieval could return the authentic source:

```text
"...the controller reduced vertical motion..."
```

together with an annotation:

```text
"the controller" -> Vertical Control System
```

so downstream reasoning does not have to redo the coreference resolution.

This is distinct from a `DefinitionSummary`:

```text
DefinitionSummary
    -> reusable document-level vocabulary/context

Mention
    -> interpretation of a particular source occurrence
```

Both may ultimately be useful.

---

## REF02 — "the controller" -> Edge Density Controller

Source context includes:

```text
"the controller increased gas flow as the edge density fell"
```

After correcting the benchmark phrase to include the source's second `"the"`, the benchmark correctly identifies chunk 2.

The generic graph contains the canonical:

```text
edge density controller
```

and preserves its general behavior:

```text
edge density controller
    --adjusts-->
gas injection
```

with edge text similar to:

```text
The Edge Density Controller adjusts commanded gas flow
for Gas injection using density feedback and selected edge diagnostics.
```

The chunk also contains the EDC entity using:

```text
Document chunk mentions edge density controller:
Controller that adjusts commanded gas flow using density
measurements and selected edge diagnostics.
```

However, a direct search of edge text and relation names found no representation of the specific source event:

```text
the controller increased gas flow as the edge density fell
```

### Assessment

```text
source phrase found:               PASS
canonical EDC entity exists:       PASS
general EDC semantics captured:    PASS
specific contextual assertion:     FAIL
mention-resolution outcome:        INDETERMINATE
```

This distinction is important.

The missing event does not prove that Cognee incorrectly resolved `"the controller"`.

Possible internal behavior includes:

```text
"the controller" -> EDC
```

followed by failure to retain the specific assertion.

Alternatively, reference resolution itself may have failed.

The final graph does not contain enough intermediate information to distinguish those cases.

This is another argument for preserving mention resolution separately from relation extraction:

```text
Mention("the controller")
    --resolves_to--> EDC

Event/assertion extraction
    -> independent result
```

REF01 and REF02 therefore form a useful comparison:

```text
REF01:
    contextual reference resolved
    specific event retained
    event has source provenance

REF02:
    canonical entity exists
    general behavior retained
    specific event omitted
    reference-resolution result cannot be observed independently
```

REF02 should remain as a useful negative extraction case rather than being repaired specifically.

---

# Negative identity controls

## NEG01 — Aurora organization vs Aurora Reconstruction Suite

Expected distinction:

```text
Aurora Fusion Research Laboratory / AFRL
!=
Aurora Reconstruction Suite
```

The graph preserves this distinction.

Organization-side entities include:

```text
aurora fusion research laboratory
afrl
```

while the software is represented separately as:

```text
aurora reconstruction suite
```

Thus there is no evidence of an incorrect merge.

### Assessment

```text
negative identity control:      PASS
organization/software split:    preserved
internal AFRL fragmentation:    still present
```

This provides an important constraint for future resolution:

> Shared lexical tokens are weak evidence of identity.

A resolver should not merge entities merely because both contain `"Aurora"`.

Other evidence such as type compatibility, explicit abbreviation relationships, graph neighborhoods, and document context should outweigh superficial lexical overlap.

---

## Semantic document entity vs ingestion document

The Aurora case also exposed another potentially confusing representation.

The generic semantic graph contains an entity resembling:

```text
Aurora Fusion Research Laboratory
Technical Note AFRL-H1-2026-04
```

typed as a document.

This is distinct from Cognee's infrastructure representation of the ingested source:

```text
TextDocument(
    DOC01_helios1_technical_overview_v2
)
```

These represent different graph roles:

```text
TextDocument
    ingestion / storage / provenance object

semantic document Entity
    real-world document that can participate
    in semantic relationships
```

They may refer to the same underlying real-world document, but they should not necessarily be merged.

A future system might instead express:

```text
SemanticDocumentEntity
    --represented_by-->
TextDocument
```

or an equivalent provenance relationship.

This also introduces another useful negative-resolution pattern:

```text
Aurora Fusion Research Laboratory
```

must remain distinct from:

```text
Aurora Fusion Research Laboratory Technical Note AFRL-H1-2026-04
```

even though one name contains the other.

Name containment should therefore not be treated as strong identity evidence.

---

## NEG02 — Helios program vs Helios-1

Expected distinction:

```text
Helios program
!=
Helios-1
```

The graph contains a strong:

```text
helios-1
```

entity but does not materialize a separate:

```text
helios program
```

entity.

Therefore this is not a clean identity test.

### Assessment

```text
expected distinction:          valid
Helios-1 represented:          PASS
Helios program represented:    FAIL / absent
accidental merge:              no direct evidence
identity evaluation:           INCONCLUSIVE
```

Some relations attached to `Helios-1`, such as research or investigation-oriented relationships, appear semantically closer to statements in the source concerning the broader Helios program.

This raises the possibility of subject substitution:

```text
source:
    Helios program investigates X

graph:
    Helios-1 investigates X
```

However, one example is not enough evidence to design a specialized mechanism around.

### Type/relation plausibility

The graph's existing `is_a` relationships could provide a weak consistency signal.

For example, if:

```text
Helios-1 --is_a--> device/tokamak
```

while another relation says:

```text
Helios-1 --investigates--> confinement physics
```

the subject/predicate combination may be less plausible than:

```text
Helios program --investigates--> confinement physics
```

This suggests a possible future signal:

```text
relation/type compatibility
```

or:

```text
relation plausibility
```

However, this should be treated as soft evidence only.

Scientific writing often assigns agency metaphorically:

```text
the experiment investigates...
the instrument observes...
the reactor demonstrates...
```

so hard ontology constraints would likely overcorrect.

For Stage 5 this case should therefore remain:

```text
interesting possible subject substitution
weak evidence from relation/type semantics
not sufficient to design around
```

---

# Cross-case observations

## 1. Identity resolution is not uniformly failing

The current graph contains both successful and unsuccessful cases.

Successful:

```text
VCS
H-1 / Helios-1
EDC
```

Fragmented:

```text
AFRL
NBI
ECH
```

Therefore a future resolver should augment the existing graph rather than assume all identity must be rebuilt.

---

## 2. Identity is not merely a string-normalization problem

NBI and ECH demonstrate variants such as:

```text
electron cyclotron heating
electron cyclotron heating system
ECH
```

Acronym expansion plus case/hyphen normalization is not sufficient.

Useful evidence may include:

```text
explicit abbreviation observations
lexical similarity
is_a / type compatibility
shared relations and neighbors
document-level definitions
source context
embedding similarity
LLM semantic judgment
```

No single signal should necessarily be authoritative.

---

## 3. `is_a` relationships may provide useful resolution evidence

Compatible type information appeared across fragmented nodes.

Examples include:

```text
electron cyclotron heating --is_a--> heating system
electron cyclotron heating system --is_a--> system
```

and analogous NBI cases.

This can provide positive evidence for equivalence.

Likewise, incompatible types can provide negative evidence:

```text
Aurora Fusion Research Laboratory -> organization
Aurora Reconstruction Suite       -> software/system
```

Type information should therefore probably contribute to a weighted resolution decision.

---

## 4. Existing graph neighborhoods are potentially valuable identity evidence

Fragmented nodes often have semantically compatible relation neighborhoods.

A resolver could potentially compare:

```text
types
neighbor entities
relationship concepts
descriptions
source locations
```

rather than relying only on names.

This is especially relevant for variants such as:

```text
NBI
neutral beam injection
neutral beam injection system
```

---

## 5. Fact preservation and identity preservation are different questions

Several cases preserve the fact even when the expected entity representation is absent or fragmented.

Examples:

```text
VCS update rate
```

became:

```text
Helios-1 --has_vcs_update_rate--> 10 kHz
```

even though the local VCS mention was not attached to the generic VCS entity.

Likewise, some Helios-program semantics may survive on `Helios-1`.

Evaluation should therefore distinguish:

```text
Was the information preserved?
```

from:

```text
Was the source semantic structure preserved?
```

---

## 6. Mention resolution and assertion extraction should be independently observable

REF02 shows why these should not be conflated.

Currently:

```text
source mention
    ↓
internal interpretation
    ↓
final extracted graph
```

Only the final result is visible.

If an assertion disappears, it becomes impossible to determine whether:

```text
reference resolution failed
```

or:

```text
reference resolution succeeded,
but relation extraction failed
```

A future mention layer could preserve this distinction.

---

## 7. Source spans are likely valuable

Chunk-level provenance is already useful, but it is relatively coarse.

A future representation could preserve:

```text
source_chunk_id
start_char
end_char
surface_text
resolution state
canonical target
```

For example:

```text
Mention:
    "the controller"

source:
    chunk 2, chars N:M

resolves_to:
    Vertical Control System
```

This would support both graph-oriented and text-oriented recall.

---

## 8. Structured qualifiers are not first-class in the default semantic graph

REF01 preserves:

```text
during the current ramp
```

inside `edge_text`, but not as an explicit structured qualifier.

For future scientific assertions, a richer representation may eventually be useful:

```text
subject
predicate
object
time/context/condition qualifiers
evidence
```

Potential approaches include:

- properties on semantic relationships;
- typed relation objects;
- reified assertion/claim nodes.

This belongs more naturally in later scientific claim modeling than in Stage 5 identity work.

---

## 9. Semantic entities and infrastructure entities can represent the same real-world object at different levels

The semantic technical-note entity and the Cognee `TextDocument` illustrate this.

These should not necessarily be merged.

Instead the graph may need relationships expressing:

```text
semantic identity / real-world object
          ↕
source/provenance representation
```

This is closely related to the distinction between:

```text
Mention
```

and:

```text
CanonicalEntity
```

---

# Emerging resolution evidence model

The Stage 5.1 results suggest that identity resolution should eventually combine several kinds of evidence:

```text
explicit alias / abbreviation evidence
        +
lexical similarity
        +
type / is_a compatibility
        +
graph-neighborhood similarity
        +
document context
        +
relation/type plausibility
        +
embedding or LLM semantic evidence
```

Negative evidence is equally important:

```text
incompatible entity types
different semantic roles
name containment without equivalence
different source contexts
explicit contradiction
```

The objective should not be aggressive merging.

The system should be able to represent:

```text
resolved
likely equivalent
ambiguous
unresolved
explicitly distinct
```

without destroying the original graph or source evidence.

---

# Implications for Stage 5.2

Stage 5.1 supports moving toward a non-destructive semantic identity layer rather than physically merging existing graph nodes.

A provisional structure is:

```text
source text
    |
    v
Mention / AliasObservation
    |
    | resolves_to
    v
Canonical semantic entity
```

with source evidence preserved on the mention:

```text
surface_text
source_chunk
source_span
resolution_status
confidence / evidence
```

Existing Cognee entities can remain intact and be reconciled through this additional structure.

Separately, a document-level semantic context such as:

```text
DefinitionSummary
```

can hold reusable vocabulary and definitions:

```text
AFRL — Aurora Fusion Research Laboratory
VCS — Vertical Control System
EDC — Edge Density Controller
NBI — neutral beam injection
ECH — electron cyclotron heating
H-1 — Helios-1
```

The two mechanisms serve different purposes:

```text
DefinitionSummary
    document-level vocabulary and semantic context

Mention
    interpretation of a specific source occurrence

Canonical entity
    identity used for semantic reasoning
```

The next Stage 5 work should focus on defining these representations and their semantics, without yet attempting to solve every extraction or ontology issue uncovered during Stage 5.1.

---

# Stage 5.1 conclusion

The default Cognee graph already performs meaningful identity and contextual reasoning, but its behavior is inconsistent across otherwise similar cases.

It can:

- consolidate some aliases and acronyms;
- resolve contextual references;
- preserve many facts despite representation changes;
- preserve source provenance at the chunk level;
- avoid some obvious false merges.

It can also:

- fragment semantically identical entities;
- fail to reuse known abbreviations across chunks;
- omit semantic entities entirely;
- lose individual source assertions;
- obscure whether reference resolution succeeded when relation extraction fails;
- transform source-level semantic structure while retaining the underlying information.

The strongest architectural conclusion from Stage 5.1 is therefore not that Cognee needs to be replaced with a stricter canonical graph.

Instead, the existing open semantic graph appears useful as a base layer, while identity-sensitive applications would benefit from an additional non-destructive layer that preserves source mentions, explicit resolution evidence, document-level definitions, and canonical semantic relationships.


## Stage 5.2 — Non-Destructive Identity Representation

### Objective

Stage 5.1 showed that Cognee's default semantic extraction performs identity consolidation inconsistently. Some aliases and abbreviations were successfully consolidated into a single generic `Entity`, while others remained fragmented across multiple entities. It also showed that contextual references such as `"the controller"` can sometimes be resolved correctly even when that resolution is not independently observable from the final semantic relation graph.

The objective of Stage 5.2 was therefore to test whether an explicit identity layer could be added **without rewriting, merging, or deleting Cognee's original semantic graph**.

The desired representation needed to support several different kinds of information:

1. reconciliation between fragmented semantic entities;
2. explicit recording of identity mappings that Cognee already resolved correctly;
3. source-specific contextual mentions;
4. document-scoped vocabulary and definitions;
5. source-grounded evidence supporting an identity decision;
6. preservation of unresolved evidence without incorrectly promoting it into a resolved identity.

The resulting design separates three concepts:

```text
Mention
    what does this particular source occurrence mean?

IdentityResolution
    how does a source form or semantic representation map to
    a canonical semantic entity?

DefinitionSummary
    what vocabulary and identity context should be remembered
    for this document?
```

---

## 5.2.1 IdentityResolution

A new `IdentityResolution` DataPoint was introduced to represent identity mappings explicitly.

Conceptually:

```text
source representation
        ↓
IdentityResolution
        ↓
canonical Entity
```

The important design choice was that `source_entity_id` is optional.

This supports both fragmented cases:

```text
Entity("nbi")
       ↑
       | source_representation
IdentityResolution("NBI")
       |
       | canonicalizes_to
       ↓
Entity("neutral beam injection")
```

and cases where Cognee already consolidated the source form:

```text
IdentityResolution("VCS")
       |
       | canonicalizes_to
       ↓
Entity("vertical control system")
```

In the latter case:

```text
source_entity_id = None
```

because there is no separate generic `Entity("vcs")`.

This means that `IdentityResolution` is not merely a repair mechanism for extraction failures. It also serves as an explicit representation of known document vocabulary that may be useful during future retrieval and encoding.

The initial identity overlay contained nine mappings:

```text
AFRL
    --abbreviation-->
Aurora Fusion Research Laboratory

VCS
    --abbreviation-->
Vertical Control System

EDC
    --abbreviation-->
Edge Density Controller

H-1
    --alias-->
Helios-1

Helios 1
    --alias-->
Helios-1

NBI
    --abbreviation-->
neutral beam injection

neutral beam injection system
    --semantic_variant-->
neutral beam injection

ECH
    --abbreviation-->
electron cyclotron heating

electron cyclotron heating system
    --semantic_variant-->
electron cyclotron heating
```

The persisted representation correctly retained `source_entity_id=None` for VCS, EDC, H-1, and Helios 1 rather than dropping the field. The resolution nodes retained the expected `resolution_kind`, document scope, canonical entity UUID, and evidence list.

The final graph contained nine `IdentityResolution` nodes.

---

## 5.2.2 Identity evidence vocabulary

The initial models deliberately used ordinary strings rather than enforced enums, but a controlled intended vocabulary was documented.

Resolution kinds include:

```text
abbreviation
alias
semantic_variant
contextual_reference
```

Identity evidence keywords include:

```text
explicit_abbreviation
explicit_alias
typed_observation
lexical_normalization
lexical_semantic_variant
compatible_type
shared_neighbors
shared_relations
source_context
document_context
definition_summary
generic_graph_consolidation
embedding_similarity
llm_semantic_judgment
```

The last two are reserved for later experiments.

Examples from the current overlay include:

```text
VCS -> vertical control system

evidence:
    explicit_abbreviation
    typed_observation
    generic_graph_consolidation
    document_context
```

and:

```text
neutral beam injection system
    -> neutral beam injection

evidence:
    lexical_semantic_variant
    compatible_type
    shared_relations
    document_context
```

This vocabulary is not yet enforced in code, but it establishes a stable semantic contract for later pipeline work.

---

## 5.2.3 Mention

A separate `Mention` DataPoint was introduced for source-specific references.

This is deliberately distinct from entity identity.

For example:

```text
source text:
    "...the controller reduced vertical motion..."

Mention:
    surface_text = "the controller"
    resolution_status = resolved

        ↓ resolves_to

Entity("vertical control system")
```

This allows mention resolution to remain observable even if later semantic assertion extraction fails.

Two mentions were created for the two occurrences of `"the controller"` in chunk 2.

Because both have the same surface text in the same chunk, `occurrence_index` was included in the temporary identity:

```text
source_chunk_id
surface_text
occurrence_index
```

This avoids collapsing the two occurrences before exact source character spans are introduced.

The VCS occurrence was represented as:

```text
resolution_status = resolved
canonical = vertical control system
```

with resolution basis including:

```text
source_context
semantic_edge
edge_text
chunk_provenance
generic_graph_consolidation
```

The EDC occurrence was intentionally represented as:

```text
resolution_status = indeterminate
canonical = None
```

rather than assigning the benchmark-ground-truth answer.

This preserves the distinction discovered in Stage 5.1:

> The source tells us that the second `"the controller"` refers to EDC, but the persisted Cognee graph does not tell us whether coreference resolution itself succeeded before the contextual assertion was dropped.

The final graph contained two `Mention` nodes.

Exact `start_char` / `end_char` source spans remain deferred to Stage 6.

---

## 5.2.4 DefinitionSummary

A document-level `DefinitionSummary` DataPoint was added as a semantic-context materialized view.

Its purpose is different from canonical identity resolution.

`IdentityResolution` records a specific identity decision.

`DefinitionSummary` retains vocabulary that may be useful when interpreting later chunks.

The initial summary was:

```text
AFRL — Aurora Fusion Research Laboratory.

VCS — Vertical Control System; controls vertical plasma position.

EDC — Edge Density Controller; adjusts commanded gas flow using density feedback.

NBI — neutral beam injection; also appears as
      "neutral beam injection system"; auxiliary heating system.

ECH — electron cyclotron heating; also appears as
      "electron cyclotron heating system"; auxiliary heating system.

H-1 and Helios 1 — aliases for Helios-1.
```

An important design decision was to preserve significant naming variants rather than making this text purely canonical.

For example:

```text
NBI — neutral beam injection;
      also appears as "neutral beam injection system"
```

is more useful as extraction context than retaining only:

```text
NBI — neutral beam injection
```

The `DefinitionSummary` therefore acts as a reusable document vocabulary/context representation rather than an ontology or canonical source of truth.

The persisted summary retained the complete definitions text and was linked to the source `TextDocument`.

---

## 5.2.5 Graph relationships

The initial DataPoints were deliberately persisted using UUID properties only:

```text
IdentityResolution.canonical_entity_id
IdentityResolution.source_entity_id
IdentityResolution.scope_document_id

Mention.canonical_entity_id
Mention.source_chunk_id

DefinitionSummary.source_document_id
```

As expected, this initially produced isolated nodes.

A second experiment added graph-native relationships between those existing nodes without recreating the underlying Cognee entities.

The following relationships were added:

```text
IdentityResolution
    --canonicalizes_to--> Entity

IdentityResolution
    --source_representation--> Entity
        # only when a separate fragmented Entity exists

IdentityResolution
    --scoped_to--> TextDocument

Mention
    --observed_in--> DocumentChunk

Mention
    --resolves_to--> Entity
        # only when resolution_status == resolved

DefinitionSummary
    --summarizes_definitions_for--> TextDocument
```

The graph changed from:

```text
154 nodes
328 edges
```

to:

```text
154 nodes
355 edges
```

giving exactly the expected 27 new relationships and zero new nodes.

The relationship breakdown was:

```text
9  IdentityResolution --canonicalizes_to--> Entity
5  IdentityResolution --source_representation--> Entity
9  IdentityResolution --scoped_to--> TextDocument

2  Mention --observed_in--> DocumentChunk
1  Mention --resolves_to--> Entity

1  DefinitionSummary --summarizes_definitions_for--> TextDocument
---------------------------------------------------------------
27
```

The topology therefore supports both already-consolidated and fragmented cases without introducing synthetic duplicate entities.

---

## 5.2.6 AbbreviationObservation as source evidence

The 23 `AbbreviationObservation` nodes created during Stage 4 were intentionally retained.

These already provide source-grounded extraction evidence:

```text
AbbreviationObservation
    --observed_in-->
DocumentChunk
```

For example:

```text
VCS -> Vertical Control System
NBI -> Neutral Beam Injection
ECH -> Electron Cyclotron Heating
H-1 -> Helios 1
```

as well as unresolved observations such as:

```text
VCS -> ""
NBI -> ""
ECH -> ""
AFRL -> ""
```

The final step in Stage 5.2 connected **positive resolved observations** to the identity decisions they support:

```text
AbbreviationObservation
    --supports-->
IdentityResolution
```

This creates an explicit evidence chain:

```text
DocumentChunk
      ↑ observed_in
AbbreviationObservation
      ↓ supports
IdentityResolution
      ↓ canonicalizes_to
Entity
```

Ten `supports` relationships were added:

```text
AFRL chunk 0  -> AFRL resolution

VCS chunk 1   -> VCS resolution
VCS chunk 4   -> VCS resolution

EDC chunk 2   -> EDC resolution
EDC chunk 4   -> EDC resolution

NBI chunk 0   -> NBI resolution
NBI chunk 1   -> NBI resolution

ECH chunk 0   -> ECH resolution
ECH chunk 1   -> ECH resolution

H-1 chunk 1   -> H-1 resolution
```

The graph therefore moved from:

```text
154 nodes / 355 edges
```

to:

```text
154 nodes / 365 edges
```

while the node inventory remained:

```text
AbbreviationObservation  23
IdentityResolution        9
Mention                   2
DefinitionSummary         1
```



Exactly ten `supports` edges were present in the final graph.

Resolved observations correctly supported the appropriate identity nodes. For example:

```text
AFRL -> Aurora Fusion Research Laboratory
    --supports-->
AFRL -> aurora fusion research laboratory
```



Normalization also allowed mappings such as:

```text
NBI -> Neutral Beam Injection
```

to support:

```text
NBI -> neutral beam injection
```

and:

```text
H-1 -> Helios 1
```

to support:

```text
H-1 -> helios-1
```

without requiring exact case or hyphenation equivalence.

Unresolved observations such as:

```text
VCS -> ""
```

were intentionally **not** connected with `supports`.

They remain available as source-grounded evidence but do not establish the identity mapping.

Similarly, abbreviation observations were not incorrectly used as evidence for separate semantic-variant resolutions:

```text
neutral beam injection system
    -> neutral beam injection

electron cyclotron heating system
    -> electron cyclotron heating
```

Those resolutions instead retain evidence such as:

```text
lexical_semantic_variant
compatible_type
shared_relations
document_context
```

This establishes a useful distinction between:

```text
evidence that a source form occurred
```

and:

```text
evidence that positively supports an identity decision
```

---

## 5.2.7 Final representation

The completed Stage 5.2 overlay can be summarized as:

```text
                     TextDocument
                       ↑       ↑
             scoped_to |       | summarizes_definitions_for
                       |       |
              IdentityResolution     DefinitionSummary
                  ↑          |
         supports |          | canonicalizes_to
                  |          v
AbbreviationObservation     Entity
          ↑
          | observed_in
          |
    DocumentChunk
```

with contextual references represented separately:

```text
DocumentChunk
      ↑
      | observed_in
      |
    Mention
      |
      | resolves_to
      v
    Entity
```

For fragmented entities:

```text
Fragmented Entity
       ↑
       | source_representation
       |
IdentityResolution
       |
       | canonicalizes_to
       v
Canonical Entity
```

For successfully consolidated aliases:

```text
IdentityResolution("VCS")
       |
       | canonicalizes_to
       v
Entity("vertical control system")
```

with no artificial `Entity("VCS")` created.

---

## 5.2.8 Key findings

### 1. Identity can be represented non-destructively

It is not necessary to merge or rewrite Cognee's generic semantic graph in order to represent semantic equivalence.

The original graph can remain intact while an explicit identity layer records how its representations should be interpreted.

---

### 2. Successful native resolution is still useful knowledge

Identity records should not be limited to repairing failures.

Mappings such as:

```text
VCS -> Vertical Control System
EDC -> Edge Density Controller
H-1 -> Helios-1
```

are useful for retrieval and later extraction even when Cognee already consolidated them successfully.

---

### 3. Mention resolution and entity reconciliation are different operations

The representations now distinguish:

```text
Mention("the controller")
    -> Vertical Control System
```

from:

```text
Entity("nbi")
    -> Entity("neutral beam injection")
```

The former interprets a particular source occurrence.

The latter reconciles semantic representations.

---

### 4. Document context deserves its own representation

`DefinitionSummary` provides a compact reusable semantic context for later processing.

It is neither:

```text
raw source text
```

nor:

```text
canonical ontology
```

but rather a document-scoped materialized vocabulary/context view.

---

### 5. Source evidence can be separated from derived identity

`AbbreviationObservation` represents what was extracted from a particular chunk.

`IdentityResolution` represents a derived semantic decision.

The relationship:

```text
AbbreviationObservation --supports--> IdentityResolution
```

makes that dependency explicit.

This is useful for:

```text
provenance
explanation
retrieval
future update/invalidation logic
```

---

### 6. Unresolved evidence should be retained without being promoted

An observation such as:

```text
VCS -> ""
```

is meaningful.

It says that the source contains an abbreviation-like form that the local extraction did not resolve.

That information should be retained, but it should not be interpreted as positive support for:

```text
VCS -> Vertical Control System
```

unless some other evidence establishes the mapping.

---

### 7. Manual graph edges differ from Cognee-native DataPoint edges

The manually added Stage 5.2 graph relationships persisted correctly, but their edge properties contain primarily:

```text
edge_text
```

whereas Cognee-generated DataPoint relationships such as Stage-4 `observed_in` edges include a richer metadata envelope:

```text
edge_object_id
edge_text
feedback_weight
relationship_name
relationship_type
source_node_id
target_node_id
updated_at
...
```

This is not a problem for the Stage 5.2 representation experiment, but it suggests that a production implementation should probably create these relationships through Cognee's normal DataPoint/pipeline lifecycle rather than patching them into the graph afterward.

That integration question is deferred to Stage 6.

---

## Stage 5.2 conclusion

Stage 5.2 demonstrated that Cognee's open semantic graph can be augmented with a **non-destructive, source-grounded identity layer**.

The representation now supports:

```text
source observations
contextual mentions
document vocabulary
identity decisions
fragmented source entities
canonical semantic entities
document scope
explicit evidence relationships
```

without modifying the original generic semantic extraction.

The core evidence path is:

```text
DocumentChunk
      ↑ observed_in
AbbreviationObservation
      ↓ supports
IdentityResolution
      ↓ canonicalizes_to
Entity
```

while contextual references use:

```text
DocumentChunk
      ↑ observed_in
Mention
      ↓ resolves_to
Entity
```

and document-level reusable context is represented through:

```text
DefinitionSummary
      ↓ summarizes_definitions_for
TextDocument
```

This establishes the representation needed for the next questions.

**Stage 5.3** will test how these identity relationships should affect graph traversal and retrieval—for example, whether the fragmented NBI representations can behave as one logical semantic neighborhood without physically merging their nodes.

**Stage 5.4** will investigate resolution timing, document versus corpus scope, and graph evolution as documents are added, updated, or removed.

**Stage 6** will then move these manually demonstrated structures into an actual processing pipeline with explicit source spans, automatic evidence extraction, identity reconciliation, hierarchical context, and lifecycle-aware graph updates.




## Stage 5.3 — Unified Entity Roles and Identity-Aware Recall

### Objective

Stage 5.3 tested whether identity reconciliation could be moved into the semantic layer itself, while preserving the non-destructive support/provenance structures introduced in Stage 5.2.

The goals were to:

- represent canonical entities, reusable variants, and source-specific mentions using a unified `Entity` abstraction;
- add direct semantic `resolves_to` relationships between Entity representations;
- preserve Stage-5.2 `IdentityResolution`, `AbbreviationObservation`, and mention helper objects as a separate support/provenance layer;
- perform identity-aware semantic recall without physically merging Entity nodes;
- test query-time resolution of reusable shorthand and context-dependent references;
- verify that ambiguous references do not trigger broad or incorrect recall.

The design intentionally avoids treating identity reconciliation as destructive graph normalization. Original extracted representations and relationships remain in place.

---

### 5.3.0 — Unified Entity Representation

The working semantic representation uses a single `Entity` class with three roles:

```text
canonical
variant
mention
```

The intended semantics are:

```text
canonical
    Preferred semantic representation within some applicable scope.

variant
    Reusable non-canonical representation whose interpretation can
    apply throughout an applicable scope.

mention
    A particular source occurrence whose interpretation depends on
    the context of that occurrence.
```

Role and scope are independent.

All three Entity roles may participate in ordinary semantic relationships. No role-specific restriction is placed on which semantic edges an Entity may carry.

Identity navigation is represented directly in the semantic layer:

```text
variant --resolves_to--> canonical

mention --resolves_to--> canonical
```

The relationship is stored directionally, but an already-established identity relationship can be traversed bidirectionally during semantic recall.

This is distinct from query-time resolution: a historical mention such as `"the controller"` resolving to VCS does not make `"the controller"` a reusable global alias.

---

### Scope and Source Location

The design discussion separated two concepts that had previously been partially conflated:

```text
semantic scope
    where a representation's interpretation is applicable

source location
    where a particular occurrence appeared
```

The current intended Entity fields are therefore conceptually:

```python
class Entity(CogneeEntity):
    entity_role: str | None = None
    graph_layer: str = "semantic"

    scope_kind: str | None = None
    scope_anchor_id: str | None = None

    source_document_id: str | None = None
    source_chunk_id: str | None = None
    source_chunk_index: int | None = None

    start_char: int | None = None
    end_char: int | None = None
    occurrence_index: int | None = None
```

Current scope kinds under consideration are:

```text
global
corpus
document
subdocument
chunk
occurrence
```

The current graph still contains some earlier experimental scope field names. Those were not migrated merely for this experiment; the cleaner field separation is intended for subsequent pipeline work.

---

### Representation Overlay

The Stage-5.3 representation experiment added direct semantic identity structure on top of the Stage-5.2 graph.

Starting graph:

```text
154 nodes
365 edges
```

After applying the Entity-layer changes:

```text
160 nodes
377 edges
```

The delta consisted of:

- four previously absent reusable variant Entity nodes;
- two semantic mention Entity nodes;
- nine variant-to-canonical `resolves_to` edges;
- one resolved mention-to-canonical `resolves_to` edge;
- two temporary `materializes_as` links from Stage-5.2 mention-support records to semantic mention Entities.

The graph inventory after the overlay included:

```text
Entity                  87
EntityType              25
AbbreviationObservation 23
IdentityResolution       9
TextSummary              6
DocumentChunk            6
Mention                  2
TextDocument             1
DefinitionSummary        1
```

and:

```text
10 Entity --resolves_to--> Entity
2  Mention --materializes_as--> Entity
1  Mention --resolves_to--> Entity
```

The final `Mention --resolves_to--> Entity` edge above belongs to the older Stage-5.2 support representation and is not part of the semantic identity graph.

---

### Logical Graph Layers

Stage 5.3 reinforced the usefulness of distinguishing logical graph layers.

```text
SEMANTIC LAYER
    Entity
    ordinary semantic relationships
    resolves_to

SUPPORT / PROVENANCE LAYER
    IdentityResolution
    AbbreviationObservation
    current Mention helper records
    later MentionResolution / evidence structures

SOURCE / CONTEXT LAYER
    TextDocument
    DocumentChunk
    TextSummary
    DefinitionSummary
```

Semantic recall should operate primarily on the semantic layer.

Support and source layers remain available for explanation, maintenance, invalidation, debugging, and provenance queries.

The current `materializes_as` edge is transitional glue between the Stage-5.2 mention helper and the semantic `Entity(role=mention)`. It is not intended as a long-term domain identity relationship.

---

## 5.3.1 — Identity-Aware Semantic Recall

The first recall experiment assumed that a query had already been resolved to a known semantic Entity.

The retrieval procedure was:

```text
seed Entity
    ↓
semantic resolves_to closure
    ↓
union semantic neighborhoods across all representations
    ↓
canonicalize Entity endpoints
    ↓
group equivalent logical facts
    ↓
retain original raw graph edges as support
```

Only semantic:

```text
Entity --resolves_to--> Entity
```

edges participate in identity closure.

The older support-layer:

```text
Mention --resolves_to--> Entity
```

relationship is deliberately excluded.

This prevents support/provenance helper nodes from leaking into semantic retrieval.

---

### NBI Identity Component

The NBI component contained:

```text
canonical  neutral beam injection
variant    nbi
variant    neutral beam injection system
```

Identity closure was consistent regardless of the starting representation.

The component contained:

```text
8 raw semantic incident edges
7 logical semantic facts after identity normalization
```

The resulting logical neighborhood included:

```text
helios-1 --has_auxiliary_heating--> neutral beam injection

helios-1 --has_installed_capacity--> neutral beam injection
    raw source:
        helios-1 --has_installed_capacity--> nbi

helios-1 --uses--> neutral beam injection
    raw source:
        helios-1 --uses--> neutral beam injection system

neutral beam injection --authorized_for--> campaign a

neutral beam injection --is_a--> heating system

neutral beam injection --is_a--> system
    raw sources:
        nbi --is_a--> system
        neutral beam injection system --is_a--> system

neutral beam injection --provided_power_during--> campaign a
```

This demonstrates two important behaviors.

First, facts attached to different equivalent Entity representations become available through one logical identity neighborhood without rewriting the original graph.

Second, duplicate logical facts can be suppressed while retaining multiple raw supports.

For example:

```text
nbi --is_a--> system
neutral beam injection system --is_a--> system
```

becomes one logical:

```text
neutral beam injection --is_a--> system
```

with both underlying assertions retained.

---

### VCS Identity Component

After excluding the Stage-5.2 helper node from semantic closure, the VCS component contained:

```text
canonical  vertical control system
variant    VCS
mention    the controller
```

The resolved mention therefore participates in the same semantic identity component as the canonical Entity and reusable abbreviation.

The logical semantic neighborhood contained 15 facts, including:

```text
vertical control system --commands--> vertical-control coils
vertical control system --receives_estimates_from--> magnetic probe array
vertical control system --reduces_vertical_motion_in--> helios-1
vertical control system --uses_gain_schedule_for--> current ramp
vertical control system --uses_gain_schedule_for--> flat-top operation
vertical control system --uses_gain_schedule_for--> startup
```

In the current corpus the mention Entity does not carry a unique semantic relation of its own. Cognee had already attached the relevant source assertion directly to the canonical VCS Entity.

Therefore this experiment validates mention participation in identity closure, but does not yet demonstrate recovery of a fact that exists only on a mention node.

That behavior is deferred until later pipeline experiments provide naturally occurrence-attached semantic assertions.

---

### Recall Result

Stage 5.3.1 demonstrated that a semantic identity component can act as a non-destructive recall view:

```text
multiple stored representations
        ↓
identity closure
        ↓
one logical semantic neighborhood
```

without physically merging the graph.

This supports the architecture in which identity reconciliation is represented explicitly rather than implemented as graph rewriting.

---

## 5.3.2 — Query-Time Entity Resolution

The next experiment addressed a separate problem:

> How should conversational or query-time shorthand be resolved before semantic recall?

This is particularly important because conversational input is likely to contain more shorthand and contextual references than structured scientific documents.

The key design principle is:

```text
canonical / variant representation
    may define reusable identity mappings

historical mention representation
    does not automatically define a reusable mapping
```

For example:

```text
NBI
    reusable variant
    -> neutral beam injection
```

while:

```text
the controller
```

must be resolved from the current context even if an earlier occurrence of `"the controller"` resolved to VCS.

---

### Query Resolution Pipeline

The tested pipeline was:

```text
query mention
    ↓
exact reusable lookup over canonical + variant Entities
    ↓
if unique:
    resolve immediately

otherwise:
    ↓
build contextual candidate scores
    ↓
resolved / ambiguous
    ↓
semantic recall only after successful resolution
```

Historical mention Entity names are excluded from reusable surface-form lookup.

---

### Candidate Profiles

A lightweight lexical-semantic profile was constructed for each explicitly marked canonical Entity using:

- canonical name and description;
- reusable variant names and descriptions;
- semantic relationship names;
- neighboring semantic Entity names and descriptions;
- semantic facts attached anywhere in the resolved identity component.

Historical mention surface strings are intentionally excluded from reusable vocabulary.

A simple TF-IDF-like overlap score was then used as an interpretable baseline for contextual disambiguation.

This was intended as a mechanism test rather than a production-quality resolver.

---

### Query-Time Resolution Benchmark

Five cases were tested.

#### QRY01 — reusable abbreviation

```text
mention:
    NBI

context:
    How much auxiliary heating power can NBI provide?
```

Result:

```text
resolved -> neutral beam injection
mechanism -> reusable_variant
PASS
```

---

#### QRY02 — reusable alias

```text
mention:
    H-1

context:
    What is the nominal toroidal field of H-1?
```

Result:

```text
resolved -> helios-1
mechanism -> reusable_variant
PASS
```

---

#### QRY03 — contextual controller reference: VCS

```text
mention:
    the controller

context:
    During the current ramp, the controller reduced vertical motion
    and used magnetic estimates to command the coils.
```

Top candidates:

```text
vertical control system     18.330
helios-1                    13.825
edge density controller      5.569
electron cyclotron heating   5.387
```

Result:

```text
resolved -> vertical control system
mechanism -> contextual
PASS
```

---

#### QRY04 — contextual controller reference: EDC

```text
mention:
    the controller

context:
    As edge density fell, the controller increased commanded gas flow.
```

Top candidates:

```text
edge density controller     10.691
helios-1                     8.438
vertical control system      2.896
electron cyclotron heating   1.336
```

Result:

```text
resolved -> edge density controller
mechanism -> contextual
PASS
```

---

#### QRY05 — insufficient context

```text
mention:
    the controller

context:
    What does the controller do?
```

The top four candidates all matched only the generic `control` concept with identical score:

```text
vertical control system      1.336
electron cyclotron heating   1.336
helios-1                     1.336
edge density controller      1.336
```

Result:

```text
status -> ambiguous
canonical entity -> none
PASS
```

Critically, the existing historical:

```text
the controller -> vertical control system
```

mention resolution did not incorrectly cause the new query occurrence to resolve to VCS.

Overall result:

```text
5 / 5 PASS
```

---

### Observed Candidate Centrality Bias

The contextual tests revealed one likely future resolver issue.

`helios-1` ranked second in both controller-resolution cases despite not being the intended referent.

This appears to result from the entity's broad semantic neighborhood:

```text
high-degree / central Entity
    -> broad lexical profile
    -> increased chance of contextual overlap
```

Possible future mitigations include degree normalization, relation weighting, narrower candidate generation, embeddings, or an LLM resolver.

No correction was introduced at this stage because the benchmark passed and there is not yet evidence that the bias causes practical failures.

This is recorded as a deferred resolver refinement.

---

## 5.3.3 — End-to-End Resolution and Recall

The final Stage-5.3 experiment composed the two independently tested mechanisms:

```text
query-time entity resolution
        +
identity-aware semantic recall
```

The resulting end-to-end path is:

```text
query mention
    ↓
reusable-name lookup or contextual resolution
    ↓
canonical Entity
    ↓
bidirectional semantic identity closure
    ↓
union semantic neighborhoods
    ↓
canonicalize Entity endpoints
    ↓
logical facts + retained raw support
```

Semantic recall is explicitly blocked if query-time resolution remains ambiguous.

---

### End-to-End NBI Recall

Query:

```text
How much auxiliary heating power can NBI provide?
```

Resolution:

```text
NBI
    -> neutral beam injection
    mechanism: reusable_variant
```

Identity component:

```text
neutral beam injection
nbi
neutral beam injection system
```

Recall:

```text
8 raw semantic edges
7 logical semantic facts
```

Facts stored on `nbi` and `neutral beam injection system` were successfully surfaced as facts about the canonical `neutral beam injection` Entity while retaining their original raw edge support.

---

### End-to-End Contextual VCS Recall

Query context:

```text
During the current ramp, the controller reduced vertical motion
and used magnetic estimates to command the coils.
```

Resolution:

```text
the controller
    -> vertical control system
```

Identity component:

```text
vertical control system
VCS
the controller [resolved occurrence]
```

Recall produced 15 logical semantic facts, including:

```text
vertical control system --commands--> vertical-control coils
vertical control system --receives_estimates_from--> magnetic probe array
vertical control system --reduces_vertical_motion_in--> helios-1
vertical control system --uses_gain_schedule_for--> current ramp
```

---

### End-to-End Contextual EDC Recall

Query context:

```text
As edge density fell, the controller increased commanded gas flow.
```

The same surface form:

```text
the controller
```

resolved instead to:

```text
edge density controller
```

The resulting EDC identity component contained:

```text
edge density controller
EDC
```

and recall returned nine semantic facts, including:

```text
edge density controller --adjusts--> gas injection
edge density controller --commissioned_before--> campaign a
edge density controller --enabled_after--> march
edge density controller --is_a--> system
```

This demonstrates that the current query occurrence is resolved before graph activation rather than activating all historical nodes with the same surface string.

---

### Ambiguous Query Behavior

Query:

```text
What does the controller do?
```

Resolution remained:

```text
ambiguous
```

and the pipeline explicitly stopped:

```text
RECALL SKIPPED:
query mention was not resolved to a canonical Entity
```

This is an important architectural result.

The system does not:

```text
find every historical "the controller" mention
    -> activate all associated Entities
    -> attempt to resolve ambiguity afterward
```

Instead:

```text
resolve current mention first
    -> activate semantic memory only after resolution
```

This ordering is likely important for conversational recall, where shorthand and contextual references may be more frequent than in curated scientific documents.

---

## Mention Clustering Investigation

During Stage 5.3, a possible future optimization was considered for cases where large numbers of occurrence-level mention Entities resolve to the same canonical Entity.

A candidate representation would cluster mentions using approximately:

```text
(normalized surface form, resolved canonical Entity)
```

for example:

```text
"the controller" + VCS
```

rather than materializing a separate semantic mention node for every occurrence.

The design was intentionally deferred.

The key problem is that semantic relationships currently attached to individual mention occurrences implicitly preserve occurrence-level provenance.

If relationships are moved onto a shared cluster node:

```text
cluster --relation--> object
```

the system must independently retain which source occurrence or occurrences supported that relation.

If relationships remain attached to individual mention nodes, clustering does not substantially reduce semantic retrieval fan-out.

Therefore meaningful mention clustering appears to depend on a stronger relation/assertion provenance abstraction, for example:

```text
semantic assertion
    +
supporting source occurrences
```

or equivalent provenance-bearing semantic edges.

No clustering changes were made in Stage 5.3.

If mention fan-out becomes a practical problem before richer assertion provenance exists, retrieval indexing/filtering should be preferred over premature graph-model changes.

---

## Stage 5.3 Conclusions

Stage 5.3 supports the following architecture:

```text
QUERY / SOURCE EXPRESSION
        ↓
contextual or reusable identity resolution
        ↓
SEMANTIC ENTITY
        ↓
identity closure
        ↓
logical semantic recall
        ↓
raw provenance retained underneath
```

Key findings:

1. A unified semantic `Entity` representation with `canonical`, `variant`, and `mention` roles is workable.

2. Entity role and semantic scope should remain separate concepts.

3. Canonical and variant representations may define reusable mappings within an applicable scope.

4. Mention resolution is occurrence-dependent and should not automatically create a reusable alias.

5. Direct semantic:

```text
Entity --resolves_to--> Entity
```

relationships provide a useful identity-navigation layer without physically merging original Entities.

6. Identity closure can be traversed bidirectionally during recall after resolution has already been established.

7. Facts distributed across multiple equivalent Entity representations can be recalled as one logical neighborhood.

8. Duplicate logical facts can be suppressed while preserving multiple raw graph assertions as support.

9. Support/provenance nodes must be explicitly excluded from ordinary semantic identity traversal.

10. Query-time resolution should occur before semantic recall.

11. An ambiguous query reference should not activate all historical mentions sharing the same surface text.

12. A simple graph-derived lexical contextual resolver was sufficient for the current benchmark, producing:

```text
5 / 5 PASS
```

13. Highly central Entities may receive artificially high contextual scores because of broad semantic neighborhoods. Degree/centrality normalization is recorded as a future refinement but was not required in the current benchmark.

14. Mention clustering is deferred until relation/assertion-level provenance is represented well enough that semantic facts can be compacted without losing source attribution.

15. The current Stage-5.2 `Mention` helper and `materializes_as` relationship should be treated as transitional support-layer structures. The longer-term model should make the semantic `Entity(role=mention)` the source occurrence and represent resolution justification separately, likely through a `MentionResolution` or equivalent support object.

Overall, Stage 5.3 demonstrates that **query-time contextual resolution and non-destructive identity-aware recall can be composed into a coherent semantic-memory path without rewriting Cognee's original graph.**

The next stage should evaluate how these mechanisms behave when knowledge evolves across documents and time, beginning with ingestion of DOC02 and inspection of the resulting graph delta before applying custom reconciliation.

# Cognee Science Lab — Stage 5.4 Investigation Results

**Project:** `cognee-science-lab`  
**Results consolidated:** 2026-10-11  
**Primary code baseline:** Cognee 1.6.2  
**Experimental backends:** Ladybug graph; LanceDB vector  
**Status:** 5.4.1–5.4.4 complete enough for architecture selection; 5.4.5 investigation planned.

This note consolidates the completed experiments, source inspections, and architectural decisions from Stage 5.4. It does not report a new run of the experiments. Graph counts and benchmark scores refer to recorded experimental snapshots, not the current live database.

## 1. Purpose and revised investigation structure

Stage 5.4 began with questions about identity-resolution timing, scope, and graph evolution. It was reframed around Cognee's operational semantics because a durable identity representation cannot be selected independently of construction, maintenance, retrieval, update, and deletion behavior.

The refined sequence is:

| Phase | Investigation | Status |
|---|---|---|
| 5.4.1 | Incremental / overlapping-ingest baseline | Complete |
| 5.4.2 | Operational and extension map | Complete enough to proceed |
| 5.4.3 | Retrieval semantics and extensions | Complete enough to proceed |
| 5.4.4 | Lifecycle and persistence integration | Complete enough for architecture selection |
| 5.4.5 | Mutation characterization, ownership, architecture, and operational invariants | Planned; current next work |

“Complete enough” means the investigation supports the next architectural step. It does not mean all relevant behavior has been experimentally characterized or production code implemented.

Three kinds of conclusions are distinguished below:

- **Measured:** observed in controlled project runs.
- **Source-inspected:** established through review of implementation or extension contracts.
- **Design decision:** the preferred project approach derived from those findings.

## 2. Stage 5.4.1 — Overlapping-ingest baseline

### Question

What happens to the existing semantic graph and Stage-5.3 identity overlay when another document with overlapping entities is processed through ordinary Cognify?

### Experiment

DOC02 was added and Cognified over the existing DOC01 / Stage-5.3 graph.

This was a test of overlapping ingestion through Cognify. It was **not** a test of the native incremental `update()` engine.

The existing graph contained experimental canonical/variant/mention roles, direct `resolves_to` links, and support structures such as `IdentityResolution` and `AbbreviationObservation`.

### Measured results

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Nodes | 160 | 281 | +121 |
| Edges | 377 | 761 | +384 |
| Stage-5.3 query-resolution benchmark | 5/5 | 0/5 | All five cases regressed |

Additional diff findings:

- No pre-existing edges were removed or modified in the recorded comparison.
- Properties on **30 pre-existing Entity nodes** were rewritten.
- Rewritten properties included project annotations such as `entity_role` / `graph_layer`, as well as some names and descriptions.
- The direct `resolves_to` identity topology survived.
- The query resolver nevertheless failed because it depended on the overwritten annotations.

The earlier successful behavior included reusable NBI alias resolution, contextual resolution of “the controller” to VCS or EDC, and preservation of ambiguity when context was insufficient.

### Interpretation

Cognify is additive in some respects, but it is **not append-only for existing node properties**.

The failure separated two concerns:

1. The identity relationships remained in the graph.
2. The metadata needed to interpret and select those relationships was no longer reliable.

A graph can therefore retain its identity topology while losing operational identity behavior.

### Architectural constraint

Important project state must not depend on arbitrary properties on Cognee-owned Entity nodes remaining intact across later Cognify runs.

Possible responses include separately owned metadata, dedicated identity structures, or a hybrid representation. The experiment did not select among those options.

The observed survival of existing edges is limited to this run; it is not a general persistence guarantee for Cognify, Improve, Update, or Forget.

## 3. Stage 5.4.2 — Operational and extension map

### Question

Which Cognee mechanisms can support custom identity and scientific-memory behavior while preserving useful native behavior and minimizing dependence on private internals?

### Source-inspected operational map

| Operation | Relevant behavior | Extension implications |
|---|---|---|
| Add / Remember | Source ingestion; standard permanent Remember proceeds through Add and Cognify | Preserve native ingestion and lifecycle bookkeeping |
| Cognify | Task-based construction and persistence | Configure extraction and customize construction sequencing |
| Improve | Ordered built-in maintenance stages | Understand the full orchestrator before assuming mutation isolation |
| Memify | Task-based extraction/enrichment over existing data or graph state | Suitable for replayable reconciliation and graph maintenance |
| Recall / Search | Retrieval routing and registered retrievers | Put project retrieval semantics behind a custom Retriever/SearchType |
| Update | Separate incremental and full-rebuild paths | Customized construction must have compatible update behavior |
| Forget | Fixed deletion and cleanup orchestration | Custom artifact cleanup depends on compatible ownership/provenance or explicit repair |

### Preferred extension surfaces

| Surface | Finding / intended use |
|---|---|
| `DataPoint` | Custom persisted structures; deterministic identity and nested relationships |
| `graph_model` | Extraction configuration; Stage 4 showed that a custom top-level model replaces normal semantic extraction rather than automatically augmenting it |
| `Task` and custom pipelines | Explicit extraction/construction sequencing |
| Custom Memify Tasks | Reconciliation, normalization, consolidation, and derived-state maintenance |
| Registered `Retriever` / `SearchType` | Identity-aware and domain-specific retrieval |
| `GraphDBInterface` and vector interfaces | Backend-independent graph/index access |

Importability alone does not make a function a stable extension contract.

Private Hybrid methods, dependence on `brute_force_triplet_search` as a public interface, direct Ladybug manipulation, and patching `recall()` / `search()` were judged fragile approaches.

### Improve / Memify findings

In pinned 1.6.2, Improve has a fixed ordered stage registry:

1. Feedback weights.
2. Session QA persistence.
3. Agent trace persistence.
4. Agent context extraction.
5. Session distillation.
6. User preference updates.
7. Truth-subspace construction.
8. Triplet enrichment.
9. Global-context indexing.

There is no public dynamic stage-registration hook in that reviewed implementation.

The triplet-enrichment stage exposes the intended custom Memify seam through arguments including `extraction_tasks`, `enrichment_tasks`, `data`, and `node_type`. Supplying custom Tasks bypasses the normal graph-change watermark shortcut for that work.

A custom Task can read and write graph structures selected by its own logic, including reconciliation/support objects. Logical membership in the support layer does not itself prevent mutation.

**Not yet established:** which arbitrary project structures the built-in Improve stages actually select, traverse, modify, or re-index. Custom Task capability must not be mistaken for evidence about default Improve behavior.

### Representation candidates retained

| Candidate | Physical organization |
|---|---|
| A | Augment Cognee's semantic graph |
| B | Separate identity subgraph |
| C | Auxiliary identity structures/store |
| D | Hybrid |

These are representation alternatives. They are distinct from the lifecycle A/B alternatives in Section 5.

No final physical representation was selected. The project intends to preserve useful native Cognee identity behavior while adding explicit resolution and provenance where needed.

## 4. Stage 5.4.3 — Retrieval semantics and extensions

### Question

Do native retrieval modes interpret identity links in the way required by the Stage-5.3 model?

### Native retrieval characterization

| Retrieval mode | Relevant behavior |
|---|---|
| `RAG_COMPLETION` | Primarily source/chunk-vector retrieval |
| `GRAPH_COMPLETION` | Vector-selected graph evidence, graph projection/neighborhood work, ranked edges/triplets, and context rendering |
| `HYBRID_COMPLETION` | Passage retrieval combined with entity/fact neighborhoods |

Native graph retrieval does **not** give `resolves_to` special identity semantics merely because a relationship has that name.

Some apparent native alias-resolution success was attributable to lexical redundancy rather than an explicit identity operation. The presence of an identity edge is therefore insufficient to guarantee identity-aware recall.

### Design direction

Use a registered custom Retriever/SearchType for project identity semantics:

```text
query
    -> query-time entity/mention resolution
    -> scope-aware canonical / identity expansion
    -> union of semantic neighborhoods
    -> logical fact deduplication
    -> source-attributed retrieval context
```

Required behavior:

- Resolve conversational shorthand before broad semantic activation.
- Preserve ambiguity when context does not justify one interpretation.
- Treat identity traversal differently from ordinary semantic distance.
- Retrieve relevant facts attached to equivalent representations without physically merging original nodes.
- Exclude support/reconciliation objects from ordinary semantic recall.
- Retain raw edges and supporting sources when logically deduplicating facts.
- Allow explanation/provenance retrieval to inspect support structures when requested.

Identity is logically navigable in both directions, but that does not justify activating every reverse-linked mention indiscriminately.

### Extension boundary

Use Cognee's retriever registry and graph/vector interfaces. A custom retrieval type is preferable to silently changing the semantics of built-in Graph or Hybrid retrieval.

Keep native RAG as a reference and fallback. Source chunks remain valuable when the semantic graph omits, fragments, or misrepresents information.

The Stage-5.3 script demonstrates the intended behavior; packaging it as the production custom Retriever remains Stage-6 work.

## 5. Stage 5.4.4 — Lifecycle and persistence integration

### Question

How can custom extraction/construction Tasks participate in native Remember and Update without creating a parallel lifecycle implementation?

### Source lifecycle versus derived maintenance

Two kinds of customization need different homes:

| Kind of work | Appropriate location |
|---|---|
| Changes to extraction, intermediate outputs, or construction order | Inside the Cognify Task sequence |
| Reconciliation, normalization, and suitable derived materialization | Replayable Memify/Improve Tasks |

The custom graph-model experiments already demonstrated that some project behavior affects extraction itself. It would therefore be too restrictive to require every customization to run after ordinary Cognify.

Conversely, adding a Cognify hook is not a reason to put all derived maintenance inside construction.

### Native Update findings

Cognee 1.6.2 has separate incremental and full-rebuild paths.

The incremental path uses a chunk-oriented diff/replacement mechanism. It can preserve unchanged chunk identities, replace affected chunks and summaries, remove affected graph/index state according to native ownership/orphan rules, and extract replacement chunks.

Its eligibility is constrained by extraction configuration; custom graph-model/prompt cases do not use the ordinary incremental route in the reviewed implementation.

The full-rebuild path uses native lifecycle machinery:

```text
resolve existing data_id
    -> forget(memory_only=True)
    -> reset appropriate pipeline status
    -> add replacement with pinned data_id
    -> cognify()
```

The incremental path does **not** call Cognify.

These findings describe native mechanics. Correct handling of arbitrary custom support structures under those mechanics remains unverified.

### Lifecycle alternatives compared

| Criterion | A — project lifecycle wrappers | B — Cognify task-transform extension |
|---|---|---|
| Cognee source changes | None | Small patch |
| Construction ordering | Project controls custom pipeline | Transform native construction Tasks |
| Remember lifecycle | Wrapper reproduces/composes behavior | Native lifecycle retained |
| Update bookkeeping | Project must track/reproduce relevant internals | Native lifecycle retained |
| Upgrade burden | Wrapper tracks changing lifecycle semantics | Patch tracks Task-list seam |
| Main risk | Divergence from native lifecycle | Maintaining a small extension patch |
| Decision | Viable fallback | **Preferred direction** |

Wrapper duplication would include data-ID resolution, pinned replacement, status handling, route checks, chunk-budget behavior, results, and error/rollback semantics.

### Preferred B proposal

Conceptual API:

```python
cognify_task_transform: Callable[[list[Task]], list[Task]] | None = None
```

Core placement:

```text
cognify()
    -> build native STANDARD Tasks
    -> apply optional task-list transform
    -> build tasks_by_route
    -> calculate pipeline needs, including needs_llm
    -> execute native cognify_pipeline
```

The transform receives already-configured native Tasks and can insert, replace, remove, or append project Tasks. This retains upstream default sequencing changes where the transform leaves them intact.

Proposed changes:

- **Cognify:** expose and apply the transform before route-task mapping and pipeline-needs calculation.
- **Remember:** forward the argument through the normal permanent-memory Cognify kwargs path.
- **Update:** a non-null transform forces the native full-rebuild path; forward the same transform into the rebuild's Cognify call.

The full-rebuild rule is semantic: Cognee's separate incremental updater cannot assume that its native chunk processing is equivalent to an arbitrary customized construction sequence.

**Implementation status:** B is preferred and specified, but the patch has not been implemented or validated in these investigations.

### Scope and limitations

- Local Python first; Python callables are not serializable through the HTTP API.
- Transform only `CognifyRoute.STANDARD` initially.
- Leave DLT/code/special routes native unless deliberately supported later.
- Define unsupported combinations explicitly.
- Reject custom-transform dry runs initially, or clearly state that native estimates exclude custom costs.
- Custom Tasks must obey Task-chain input/output contracts.
- Preserve native pipeline naming, runtime/routing, data-ID/status handling, and result construction.
- Native rollback for native artifacts does not guarantee cleanup of arbitrary custom side effects.
- Define idempotence, replay, and cleanup for project writes separately.
- The patch does not automatically arrange post-update reconciliation.

### Cognify call-path review

The reviewed architecturally relevant call paths were:

| Entry point | Reaches core Cognify? | Implication |
|---|---|---|
| Direct local SDK Cognify | Yes | Core seam supports direct construction |
| Standard permanent-memory Remember | Yes, after Add | Forward transform argument |
| Full-rebuild Update | Yes | Forward transform; retain bookkeeping |
| Incremental Update | No | Disable this branch when transform supplied |
| HTTP POST `/api/v1/cognify` | Yes, on server | Requires server-side extension configuration |
| Remote SDK Cognify | Forwards to server before local Task construction | Client-side callable cannot implement server customization |

Not every Remember mode goes through STANDARD Cognify. Sessions, typed memories, and specialized code/import paths require separate treatment.

No additional comparable top-level production lifecycle caller was identified in that review. This was a scoped call-path finding, not a claim that examples or tests never invoke Cognify.

### Upgrade-resilience assessment

The reviewed 1.6.2 code and then-current main both constructed route-specific Task lists before executing the Cognify pipeline. This made the Task-list boundary a promising conceptual patch anchor.

That is evidence for a relatively small maintenance surface, not a guarantee of future compatibility. Recheck it when changing the project pin.

## 6. Persistence, provenance, and deletion constraints

The lifecycle review also identified concerns that remain relevant to the final architecture:

- Native Cognify uses the stable `cognify_pipeline` name for completion tracking.
- A separate custom pipeline name has independent status semantics.
- Native single-data `forget(memory_only=True)` resets Cognify status; it does not understand arbitrary project pipeline names.
- Native Forget coordinates graph/vector cleanup, session invalidation, relational edge-evidence removal, and pipeline-status handling.
- Graph interfaces expose source-ref and pipeline-run provenance mechanisms, but custom writes must use them deliberately and compatibly.
- Manual graph-engine edges observed earlier had a thinner metadata envelope than normal DataPoint relationships.
- `add_data_points()` is graph persistence plus indexing, not merely isolated object creation; reuse of IDs can interact with existing objects.

None of these mechanisms establishes that custom `IdentityResolution`, observations, definitions, or future Claim/Evidence structures will survive, update, or delete correctly by default.

Forget remains a compatibility/repair concern with lower architectural priority than construction, maintenance, retrieval, and Update. A documented small cleanup/replay path may be acceptable where native deletion is insufficient.

## 7. Conclusions established so far

1. **Mutable Cognee Entity properties are not a safe home for durable project state.** The overlapping-ingest experiment demonstrated the failure directly.
2. **Identity topology and operational identity behavior are separate.** Surviving links did not prevent the benchmark regression.
3. **Native retrieval does not supply the required identity semantics.** A registered custom Retriever is the preferred extension.
4. **Extraction customization and derived maintenance need separate extension seams.** Use transformed Cognify for the former and replayable Memify/Improve Tasks for the latter.
5. **Prefer lifecycle B:** a small Cognify task-transform patch with native Remember/Update orchestration.
6. **Customized Update initially requires full rebuild.** Incremental compatibility needs a future explicit contract.
7. **Physical identity representation remains open.** The lifecycle decision does not settle representation A/B/C/D.
8. **Logical graph layers are not established native mutation boundaries.** Ownership policy must be grounded in actual operation selection and write behavior.

## 8. Remaining investigation — Stage 5.4.5

No new 5.4.5 experiment results are reported here.

The next work is to characterize actual mutation/persistence behavior across:

- Cognee semantic nodes and edges;
- project identity representations and `resolves_to`;
- reconciliation/support objects;
- source/context structures;
- provenance, source refs, and pipeline-run metadata;
- graph/vector indexes;
- representative future scientific structures.

Test persistence, overlapping Cognify, default Improve, direct/custom Memify, incremental and full-rebuild Update, Forget, and deletion. Treat Recall/Search as a read-path control while distinguishing graph/index mutations from session or other bookkeeping writes.

Use isolated/reset fixtures and before/after snapshots. Record write path, operation eligibility, selectors, property/edge changes, source/run metadata, evidence/status, and index changes.

The particularly important unresolved question is:

> Which built-in Improve stages can select, traverse, modify, or re-index reconciliation/support structures, and by what mechanism?

A custom no-op Task does not imply that its enclosing Improve run is a no-op.

Only after this characterization should we finalize ownership, choose the physical representation, specify lifecycle orchestration, and turn the resulting invariants into Stage-6 requirements.

The agreed architecture check-in remains **after Stage 6**.

## 9. Reference anchors

Companion project documents:

- `cognee_science_lab_ROADMAP.md` — revised 2026-10-11.
- `cognee_extension_architecture_reference_v1.6.2.md` — detailed extension/lifecycle reference.

Primary implementation anchors used in the earlier investigations:

- [Cognify — v1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/cognify/cognify.py)
- [Remember — v1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/remember/remember.py)
- [Update — v1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/update/update.py)
- [Forget — v1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/forget/forget.py)
- [Improve — v1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/improve/improve.py)
- [Improve registry — v1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/registry.py)
- [Improve stages — v1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/improve/stages.py)

Main-branch documentation and design materials are context, not substitutes for the pinned runtime:

- [Custom Tasks and pipelines example](https://github.com/topoteretes/cognee/blob/main/examples/guides/custom_tasks_and_pipelines.py)
- [Memify design discussion](https://github.com/topoteretes/cognee/issues/3389)