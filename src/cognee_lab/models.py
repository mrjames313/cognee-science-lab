from typing import Literal, ClassVar
from pydantic import BaseModel, Field, model_validator

from cognee.infrastructure.engine import DataPoint
from cognee.modules.chunking.models import DocumentChunk
from cognee.shared.data_models import KnowledgeGraph


# ---------------------------------------------------------------------------
# Stage 5 identity vocabulary
#
# These are currently DOCUMENTED vocabularies, not enforced enums.
#
# Keeping the fields as strings makes the experiments easy to evolve while
# giving us a stable intended vocabulary to use consistently in scripts,
# output, evaluation, and later schemas.
# ---------------------------------------------------------------------------


IDENTITY_RESOLUTION_KINDS = (
    # Short form explicitly expands to the canonical name.
    # Example: AFRL -> Aurora Fusion Research Laboratory
    "abbreviation",

    # Alternate name for the same semantic object.
    # Example: H-1 -> Helios-1
    "alias",

    # Semantically equivalent naming variant that is not simply an alias.
    # Example:
    #   electron cyclotron heating system
    #       -> electron cyclotron heating
    "semantic_variant",

    # Context-dependent reference to an entity.
    # Normally used for Mention rather than IdentityResolution, but retained
    # here because future identity representations may need it.
    # Example: "the machine" -> Helios-1
    "contextual_reference",
)


IDENTITY_EVIDENCE_KEYWORDS = (
    # The source explicitly defines an abbreviation.
    # Example: "Vertical Control System (VCS)"
    "explicit_abbreviation",

    # The source explicitly indicates two names refer to the same object.
    "explicit_alias",

    # A Stage 4 typed/source-grounded observation supports the mapping.
    "typed_observation",

    # Simple lexical normalization supports equivalence:
    # case, punctuation, hyphenation, etc.
    "lexical_normalization",

    # The names are semantically related variants rather than simple
    # orthographic variants.
    # Example: "neutral beam injection system" vs
    #          "neutral beam injection"
    "lexical_semantic_variant",

    # is_a/type information is compatible between the representations.
    "compatible_type",

    # Their graph neighborhoods contain compatible/shared entities.
    "shared_neighbors",

    # They participate in compatible/shared semantic relationships.
    "shared_relations",

    # Nearby source text supports the identity relationship.
    "source_context",

    # Earlier/later material within the same document supports the identity.
    # This is stronger than merely saying that both entities occur somewhere
    # in the same document.
    "document_context",

    # A DefinitionSummary or equivalent document vocabulary supports it.
    "definition_summary",

    # The existing generic Cognee graph already consolidated the variants
    # into one semantic entity.
    "generic_graph_consolidation",

    # Embedding similarity supports equivalence.
    # Reserved for later experiments.
    "embedding_similarity",

    # An LLM semantic-resolution step supports equivalence.
    # Reserved for later experiments.
    "llm_semantic_judgment",
)


MENTION_RESOLUTION_STATUSES = (
    # The pipeline provides enough observable evidence to assign a target.
    "resolved",

    # The pipeline provides evidence that the mention is currently unresolved.
    "unresolved",

    # We cannot determine from persisted pipeline output whether resolution
    # succeeded or failed.
    "indeterminate",

    # More than one plausible referent remains.
    "ambiguous",
)


MENTION_RESOLUTION_BASIS_KEYWORDS = (
    # The surrounding source text itself makes the referent clear.
    "source_context",

    # An explicit abbreviation/alias definition resolves the mention.
    "explicit_definition",

    # A typed Stage 4 observation resolves the surface form.
    "typed_observation",

    # A DefinitionSummary provides the relevant document-scoped mapping.
    "definition_summary",

    # A semantic relation in the generic graph demonstrates the resolved
    # referent.
    "semantic_edge",

    # Natural-language edge_text demonstrates the resolved referent.
    "edge_text",

    # Provenance connects the resolved semantic assertion back to the
    # source chunk containing this mention.
    "chunk_provenance",

    # Existing generic-graph consolidation provides the target identity.
    "generic_graph_consolidation",

    # The source occurrence exists, but no resolved semantic assertion
    # corresponding to it was materialized.
    "specific_assertion_not_materialized",

    # Reserved for future resolution mechanisms.
    "embedding_similarity",
    "llm_semantic_judgment",
)


class IdentityResolution(DataPoint):
    """
    A non-destructive identity assertion.

    This records that a source form or semantic representation resolves to
    an existing canonical semantic entity within some scope.

    Importantly, source_entity_id is optional.

    This allows us to represent BOTH:

        Entity("nbi") -> Entity("neutral beam injection")

    where both generic Entity nodes exist, AND:

        surface form "VCS" -> Entity("vertical control system")

    where Cognee already consolidated VCS and therefore never created a
    separate Entity("vcs") node.

    IdentityResolution is informational and auditable. It does not merge,
    delete, or rewrite generic Cognee entities.
    """

    # The form being resolved.
    #
    # Examples:
    #   "AFRL"
    #   "neutral beam injection system"
    #   "VCS"
    #   "H-1"
    source_name: str

    # Optional existing generic Entity corresponding to source_name.
    #
    # None is valid and meaningful: it means the surface/semantic form is
    # known even though Cognee did not materialize it as a separate generic
    # entity.
    source_entity_id: str | None = None

    # Existing generic Entity selected as the canonical target.
    canonical_entity_id: str
    canonical_name: str

    # Intended vocabulary: IDENTITY_RESOLUTION_KINDS
    resolution_kind: str

    # Initially "document". Later possibilities may include corpus/domain.
    scope: str
    scope_document_id: str

    # Intended vocabulary: IDENTITY_EVIDENCE_KEYWORDS
    evidence: list[str] = []

    metadata: dict = {
        "index_fields": [
            "source_name",
            "canonical_name",
        ],
        "identity_fields": [
            "source_name",
            "canonical_entity_id",
            "scope",
            "scope_document_id",
        ],
    }


class Mention(DataPoint):
    """
    A particular occurrence of a surface form in source text.

    Mention preserves source-level identity independently of semantic
    relation extraction.

    Example:

        source:
            "...the controller reduced vertical motion..."

        Mention("the controller")
            -> resolves to Vertical Control System

    A Mention may remain unresolved, ambiguous, or indeterminate.
    """

    source_chunk_id: str
    source_chunk_index: int

    surface_text: str

    # Zero-based among occurrences of the same surface_text in the chunk.
    #
    # This is useful before exact source spans are available. Eventually
    # start_char/end_char should become the stronger source locator.
    occurrence_index: int

    start_char: int | None = None
    end_char: int | None = None

    # Intended vocabulary: MENTION_RESOLUTION_STATUSES
    resolution_status: str

    # Canonical target when observable from the pipeline.
    canonical_entity_id: str | None = None
    canonical_name: str | None = None

    # Intended vocabulary: MENTION_RESOLUTION_BASIS_KEYWORDS
    resolution_basis: list[str] = []

    metadata: dict = {
        "index_fields": [
            "surface_text",
        ],
        "identity_fields": [
            "source_chunk_id",
            "surface_text",
            "occurrence_index",
        ],
    }


class DefinitionSummary(DataPoint):
    """
    Document-scoped semantic vocabulary/context.

    This is a materialized contextual summary, not the canonical source of
    identity truth.

    Unlike canonical identity resolution, DefinitionSummary should retain
    important source vocabulary and semantic variants that later chunks may
    actually use.

    Example:

        NBI — neutral beam injection; also appears as
              "neutral beam injection system".

    Its initial consumer is expected to be later extraction/resolution
    stages rather than direct canonical graph traversal.
    """

    source_document_id: str
    definitions_text: str

    metadata: dict = {
        "index_fields": [
            "definitions_text",
        ],
        "identity_fields": [
            "source_document_id",
        ],
    }

    
class Abbreviation(DataPoint):
    short_form: str = Field(
        description="Abberviation or acronym exactly as used in the text, e.g. VCS."
    )
    full_form: str = Field(
        description="Expanded form explicitly associated with the abbreviation."
    )

    metadata: dict = {
        "index_fields": ["short_form", "full_form"],
        "identity_fields": ["short_form"],
    }

class AbbreviationGraph(DataPoint):
    name: Literal["abbreviation_graph"] = "abbreviation_graph"

    abbreviations: list[Abbreviation] = Field(
        default_factory=list,
        description=(
            "Abbreviations or acronyms whose expanded forms are supported "
            "by the source text."
        ),
    )

    metadata: dict = {
        "index_fields": [],
        "identity_fields": ["name"],
    }

    
class AbbreviationExtraction(BaseModel):
    short_form: str = Field(
        description=(
            "An abbreviation or acronym exactly as it appears in the source text, "
            "for example VCS, EDC, NBI, or AFRL."
        )
    )

    full_form: str = Field(
        description=(
            "The full expanded name explicitly associated with the abbreviation "
            "in the source text, for example 'Vertical Control System' for 'VCS'."
            "If the abbreviation is recognized but the expansion cannot be "
            "established from this chunk, leave this empty."
        )
    )

# This corresponds to an extracted abbreviation
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

class MixedKnowledgeGraph(KnowledgeGraph):
    abbreviations: list[AbbreviationExtraction] = Field(
        default_factory=list,
        description=(
            "Abbreviations, acronyms or shorthand recognized in this source "
            "chunk.  Include unresolved cases with an empty full_form."
        ),
    )

#    captured_abbreviations: ClassVar[
#        list[AbbreviationExtraction]
#    ] = []

#    @model_validator(mode="after")
#    def capture_abbreviations(self):
#        type(self).captured_abbreviations.extend(
#            self.abbreviations
#        )
#        return self

#    @classmethod
#    def clear_capture(cls):
#        cls.captured_abbreviations.clear()



# In-depth analysis of extraction
    # @model_validator(mode="after")
    # def capture_abbreviations(self):
    #     print("\n[MIXED EXTRACTION]")
    #     print(f"  generic nodes: {len(self.nodes)}")
    #     print(f"  generic edges: {len(self.edges)}")
        
    #     print(
    #         "  abbreviations:",
    #         [
    #             (a.short_form, a.full_form)
    #             for a in self.abbreviations
    #         ],
    #     )

    #     node_names = {
    #         node.id: node.name
    #         for node in self.nodes
    #     }

    #     abbreviation_terms = {
    #         term.casefold()
    #         for a in self.abbreviations
    #         for term in (a.short_form, a.full_form)
    #     }

    #     print("  generic edges involving abbreviation-like nodes:")

    #     found = False

    #     for edge in self.edges:
    #         source_name = node_names.get(edge.source_node_id, "")
    #         target_name = node_names.get(edge.target_node_id, "")
            
    #         if (
    #                 source_name.casefold() in abbreviation_terms
    #                 or target_name.casefold() in abbreviation_terms
    #         ):
    #             found = True
    #             print(
    #                 f"    {source_name!r}"
    #                 f" --{edge.relationship_name}--> "
    #             f"{target_name!r}"
    #         )

    #     if not found:
    #         print("    none")

    #     type(self).captured_abbreviations.extend(
    #         self.abbreviations
    #     )

    #     return self

# In depth analysis of extraction and edges    
    # @model_validator(mode="after")
    # def debug_mixed_extraction(self):
    #     print("\n[MIXED EXTRACTION]")

    #     nodes_by_id = {
    #         node.id: node
    #         for node in self.nodes
    #     }

    #     print(f"  generic nodes: {len(self.nodes)}")
    #     print(f"  generic edges: {len(self.edges)}")

    #     print(
    #         "  abbreviations:",
    #         [
    #             (a.short_form, a.full_form)
    #             for a in self.abbreviations
    #         ],
    #     )

    #     def norm(s: str) -> str:
    #         return " ".join(
    #             s.casefold()
    #             .replace("-", " ")
    #             .split()
    #         )

    #     # --------------------------------------------------
    #     # Structural sanity: do all edges resolve to nodes?
    #     # --------------------------------------------------

    #     dangling = []
        
    #     for edge in self.edges:
    #         missing = []

    #         if edge.source_node_id not in nodes_by_id:
    #             missing.append("source")

    #         if edge.target_node_id not in nodes_by_id:
    #             missing.append("target")

    #         if missing:
    #             dangling.append((edge, missing))

    #     print(f"  dangling generic edges: {len(dangling)}")

    #     for edge, missing in dangling:
    #         print(
    #             "    ",
    #             missing,
    #             edge.source_node_id,
    #             f"--{edge.relationship_name}-->",
    #             edge.target_node_id,
    #         )

    #     # --------------------------------------------------
    #     # For each typed abbreviation, locate matching
    #     # generic nodes and show their generic relationships.
    #     # --------------------------------------------------

    #     for abbreviation in self.abbreviations:
    #         terms = {
    #             norm(abbreviation.short_form),
    #             norm(abbreviation.full_form),
    #         }

    #         matching_ids = {
    #             node.id
    #             for node in self.nodes
    #             if norm(node.name) in terms
    #         }

    #         print(
    #             f"\n  ABBREVIATION "
    #             f"{abbreviation.short_form!r}"
    #             f" -> {abbreviation.full_form!r}"
    #         )

    #         if not matching_ids:
    #             print("    generic node: NONE")
    #             continue

    #         for node_id in matching_ids:
    #             node = nodes_by_id[node_id]

    #             print(
    #                 f"    generic node: "
    #                 f"{node.name!r} "
    #                 f"(id={node.id}, type={node.type!r})"
    #             )

    #         incident_edges = [
    #             edge
    #             for edge in self.edges
    #             if (
    #                     edge.source_node_id in matching_ids
    #                     or edge.target_node_id in matching_ids
    #             )
    #         ]

    #         if not incident_edges:
    #             print("    incident generic edges: NONE")
    #             continue

    #         print("    incident generic edges:")

    #         for edge in incident_edges:
    #             source = nodes_by_id.get(edge.source_node_id)
    #             target = nodes_by_id.get(edge.target_node_id)

    #             source_name = (
    #                 source.name
    #                 if source is not None
    #                 else f"<missing:{edge.source_node_id}>"
    #             )

    #             target_name = (
    #                 target.name
    #                 if target is not None
    #                 else f"<missing:{edge.target_node_id}>"
    #             )

    #             print(
    #                 f"      {source_name!r}"
    #                 f" --{edge.relationship_name}--> "
    #                 f"{target_name!r}"
    #             )

    #     type(self).captured_abbreviations.extend(
    #         self.abbreviations
    #     )

    #     # TEMP
    #     print("\n  VCS / vertical-motion related generic edges:")

    #     for edge in self.edges:
    #         source = nodes_by_id.get(edge.source_node_id)
    #         target = nodes_by_id.get(edge.target_node_id)

    #         source_name = source.name if source else ""
    #         target_name = target.name if target else ""

    #         haystack = " ".join([
    #             source_name,
    #             target_name,
    #             edge.relationship_name,
    #             edge.description or "",
    #         ]).casefold()

    #         if any(
    #                 term in haystack
    #                 for term in (
    #                         "vcs",
    #                         "vertical control",
    #                         "vertical-control",
    #                         "vertical motion",
    #                 )
    #         ):
    #             print(
    #                 f"    {source_name!r}"
    #                 f" --{edge.relationship_name}--> "
    #                 f"{target_name!r}"
    #             )
    #     # END TEMP
    #     return self

## Simple analysis of extraction       
#    @model_validator(mode="after")
#    def debug_mixed_extraction(self):
#        print("\n[MIXED EXTRACTION]")
#        print(f"  generic nodes: {len(self.nodes)}")
#        print(f"  generic edges: {len(self.edges)}")
#        print(
#            "  abbreviations:",
#            [
#                (a.short_form, a.full_form)
#                for a in self.abbreviations
#            ],
#        )
#        return self

# Old experiments from phase 1
class HeatingSystem(DataPoint):
    name: str
    heating_type: str

    metadata: dict = {
        "index_fields": ["name"],
        "identity_fields": ["name"],
    }


class Organization(DataPoint):
    name: str

    metadata: dict = {
        "index_fields": ["name"],
        "identity_fields": ["name"],
    }

    
class Facility(DataPoint):
    name: str
    description: str | None = None
    operator: Organization
    heating_systems: list[HeatingSystem]
    
    metadata: dict = {
        "index_fields": ["name"],
        "identity_fields": ["name"],
    }
