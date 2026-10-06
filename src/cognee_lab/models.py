from typing import Literal, ClassVar
from pydantic import BaseModel, Field, model_validator

from cognee.infrastructure.engine import DataPoint
from cognee.modules.chunking.models import DocumentChunk
from cognee.shared.data_models import KnowledgeGraph


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
