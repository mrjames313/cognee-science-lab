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