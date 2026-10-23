"""Rule 6 of the occurrence check's decision choices: erasure removals.

A dependent of a forgotten glossary loses the decisions that cite it. Each
builder makes the old revision cite the glossary's entry, or an Entity the
forget removed, and the new revision the removal, whole, partial or
overreaching, under the removal producer the forget names. The rows state
the outcomes as `DECISIONS` does. A removal changes nothing else, so its
rows need a steady world, where every group continues and nothing is new.
"""

from uuid import UUID, uuid5

from cognee_lab.identity.erasure_rules import ERASURE_IMPLEMENTATION, Erasures
from dependency_worlds import add_glossary, cite, glossary_span, saved_record
from occurrence_worlds import (
    ADMIT,
    CONTINUING,
    CORPUS,
    DOCUMENT,
    HC,
    HELIOS,
    add_recipe,
    continuing_rid,
    decision,
    refuse,
    variant,
)

STEADY = "steady"
ERASER = "forget_gloss_r2"
UNRELATED = refuse("erasure_unrelated")
INCOMPLETE = refuse("erasure_incomplete")
UNBOUND = refuse("erasure_unbound")


def glossary_id(payload):
    return str(uuid5(UUID(payload["dataset_id"]), "gloss"))


def removed_entity(identity):
    return str(uuid5(UUID(str(identity)), "removed:entity"))


def read_entity(identity):
    return str(uuid5(UUID(str(identity)), "read:entity"))


def forgotten(old) -> Erasures:
    """What the ledger lets every world's removal claim: the glossary is
    forgotten and its forget removed one Entity; another saved source reads
    one Entity as a corpus input. The glossary's identity source is
    dependency_worlds.cited_source, whose resolution r1 a world may cite."""
    return Erasures(
        {
            uuid5(old.dataset_id, "gloss"): frozenset(
                {UUID(removed_entity(old.identity_data_id))}
            )
        },
        frozenset({UUID(read_entity(old.identity_data_id))}),
        {uuid5(old.dataset_id, "gloss"): uuid5(old.dataset_id, "cited-source")},
    )


def eraser(payload, *, document=None, removed=None):
    """The removal producer, naming the forgotten document and Entities: by
    default the glossary and the one Entity its forget removed."""
    if removed is None:
        removed = [removed_entity(payload["identity_data_id"])]
    payload["producers"][ERASER] = dict(
        method="captured_fixture",
        implementation=ERASURE_IMPLEMENTATION,
        version="0.1",
        configuration=dict(
            forgotten_document_id=document or glossary_id(payload),
            removed_entity_ids=list(removed),
        ),
        run_id=None,
    )


def reads_glossary(payload, *records):
    add_glossary(payload)
    glossary_span(payload)
    for record in records:
        cite(payload, record, "gloss_hc")


def unresolved(payload, rid, *, producer=ERASER, refs=("doc01",)):
    group = payload["mention_resolutions"][rid]["group_ref"]
    payload["mention_resolutions"][rid] = dict(
        group_ref=group,
        status="unresolved",
        input_refs=list(refs),
        producer_ref=producer,
    )


def unresolve_reader(old, new, ctx):
    rid = continuing_rid(ctx)
    reads_glossary(old, rid)
    unresolved(new, rid)
    eraser(new)


def drop_reading_variant(*, scope=None, producer=True):
    """v01 reads the glossary entry and goes, with HC, which only it named."""

    def change(old, new, ctx):
        if scope:
            for payload in (old, new):
                payload["variant_assignments"]["v01"]["applicability"] = scope
        reads_glossary(old, "v01")
        new["variant_assignments"].pop("v01")
        new["entity_constructions"].pop(HC)
        if producer:
            eraser(new)

    return change


def keep_reading_variant(old, new, ctx):
    reads_glossary(old, "v01")
    reads_glossary(new, "v01")
    eraser(new)


def keep_reader_accepted(old, new, ctx):
    rid = continuing_rid(ctx)
    reads_glossary(old, rid)
    reads_glossary(new, rid)
    eraser(new)


def unresolve_under_old_producer(old, new, ctx):
    rid = continuing_rid(ctx)
    reads_glossary(old, rid)
    unresolved(new, rid, producer="fixture")
    eraser(new)


def unresolve_a_bystander(old, new, ctx):
    """Only v01 reads the glossary; the removal also unresolves the
    continuing resolution, which cites nothing forgotten."""
    drop_reading_variant()(old, new, ctx)
    unresolved(new, continuing_rid(ctx), refs=("doc01", "existing_A"))


def drop_an_unnamed_recipe(old, new, ctx):
    spare = str(uuid5(ctx["identity"], "spare"))
    add_recipe(old, spare)
    drop_reading_variant()(old, new, ctx)


def keep_an_erased_input(old, new, ctx):
    drop_reading_variant()(old, new, ctx)
    glossary_span(new)
    add_glossary(new)


def add_a_decision(old, new, ctx):
    drop_reading_variant()(old, new, ctx)
    new["variant_assignments"]["v02"] = variant(HELIOS, HC, DOCUMENT)
    new["entity_constructions"][HC] = old["entity_constructions"][HC]
    new["variant_assignments"]["v02"]["producer_ref"] = ERASER


def erase_another_document(old, new, ctx):
    drop_reading_variant(producer=False)(old, new, ctx)
    eraser(new, document=str(uuid5(UUID(new["dataset_id"]), "other")))


def claim_an_entity(old, new, ctx):
    """The producer names an Entity the glossary's forget did not remove."""
    drop_reading_variant(producer=False)(old, new, ctx)
    eraser(new, removed=[HELIOS])


def name_part_of_the_removed(old, new, ctx):
    """The producer names none of the Entities the glossary's forget
    removed, so a decision citing one could survive the removal."""
    drop_reading_variant(producer=False)(old, new, ctx)
    eraser(new, removed=[])


def remove_nothing(old, new, ctx):
    """The producer names the glossary, which the old revision never cites."""
    eraser(new)


def read_recipe(*, drop):
    """v01 reads the glossary entry and names an Entity that only it
    declares and another saved source reads as a corpus input."""

    def change(old, new, ctx):
        read = read_entity(ctx["identity"])
        for payload in (old, new):
            add_recipe(payload, read)
            payload["variant_assignments"]["v01"]["target_entity_id"] = read
        reads_glossary(old, "v01")
        new["variant_assignments"].pop("v01")
        if drop:
            new["entity_constructions"].pop(read)
        eraser(new)

    return change


def removed_entity_input(old, new, ctx):
    """The continuing resolution reads an Entity the forget removed."""
    rid = continuing_rid(ctx)
    entity = removed_entity(ctx["identity"])
    old["inputs"]["existing_Z"] = dict(old["inputs"]["existing_A"], entity_id=entity)
    cite(old, rid, "existing_Z")
    unresolved(new, rid)
    eraser(new, removed=[entity])


def strip_the_group(*, keep):
    """The continuing group reads the glossary entry too."""

    def change(old, new, ctx):
        unresolve_reader(old, new, ctx)
        old["mention_groups"][ctx["continuing"]]["input_refs"].append("gloss_hc")
        if keep:
            new["mention_groups"][ctx["continuing"]]["input_refs"].append("gloss_hc")
            reads_glossary(new)

    return change


def unresolve_record_citer(old, new, ctx):
    """The continuing resolution cites the forgotten source's saved record."""
    rid = continuing_rid(ctx)
    saved_record(old)
    cite(old, rid, "rec")
    unresolved(new, rid)
    eraser(new)


def keep_record_citer(old, new, ctx):
    rid = continuing_rid(ctx)
    for payload in (old, new):
        saved_record(payload)
        cite(payload, rid, "rec")
    eraser(new)


def drop_record_citing_variant(old, new, ctx):
    saved_record(old)
    cite(old, "v01", "rec")
    new["variant_assignments"].pop("v01")
    new["entity_constructions"].pop(HC)
    eraser(new)


# A removal is an unchanged-text revision: with changed text its groups
# differ, so the rule refuses it before the text-edit rules would.
ERASURE_DECISIONS = [
    decision(
        "erasure unresolves the continuing resolution citing the forgotten source's record",
        "rule 6",
        [CONTINUING, STEADY],
        unresolve_record_citer,
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "erasure drops the document variant citing the forgotten source's record",
        "rule 6",
        [STEADY],
        drop_record_citing_variant,
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "erasure keeps the resolution citing the forgotten source's record",
        "rule 6",
        [CONTINUING, STEADY],
        keep_record_citer,
        text_edit=INCOMPLETE,
        same_text=INCOMPLETE,
    ),
    decision(
        "erasure unresolves the continuing resolution citing the forgotten span",
        "rule 6",
        [CONTINUING, STEADY],
        unresolve_reader,
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "erasure drops the document variant citing the forgotten span",
        "rule 6",
        [STEADY],
        drop_reading_variant(),
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "erasure drops a corpus-scoped variant citing the forgotten span",
        "rule 6",
        [STEADY],
        drop_reading_variant(scope=CORPUS),
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "corpus-scoped variant citing a forgotten span dropped without a removal producer",
        "rule 6",
        [STEADY],
        drop_reading_variant(scope=CORPUS, producer=False),
        text_edit=refuse("variant_changed"),
        same_text=refuse("variant_changed"),
    ),
    decision(
        "erasure keeps the variant citing the forgotten span",
        "rule 6",
        [STEADY],
        keep_reading_variant,
        text_edit=INCOMPLETE,
        same_text=INCOMPLETE,
    ),
    decision(
        "erasure keeps the continuing resolution citing the forgotten span",
        "rule 6",
        [CONTINUING, STEADY],
        keep_reader_accepted,
        text_edit=INCOMPLETE,
        same_text=INCOMPLETE,
    ),
    decision(
        "erasure unresolves under the old producer",
        "rule 6",
        [CONTINUING, STEADY],
        unresolve_under_old_producer,
        text_edit=INCOMPLETE,
        same_text=INCOMPLETE,
    ),
    decision(
        "erasure unresolves a resolution that cites nothing forgotten",
        "rule 6",
        [CONTINUING, STEADY],
        unresolve_a_bystander,
        text_edit=UNRELATED,
        same_text=UNRELATED,
    ),
    decision(
        "erasure drops a recipe no removed decision named",
        "rule 6",
        [STEADY],
        drop_an_unnamed_recipe,
        text_edit=UNRELATED,
        same_text=UNRELATED,
    ),
    decision(
        "erasure keeps a forgotten input nothing cites",
        "rule 6",
        [STEADY],
        keep_an_erased_input,
        text_edit=INCOMPLETE,
        same_text=INCOMPLETE,
    ),
    decision(
        "erasure adds a decision",
        "rule 6",
        [STEADY],
        add_a_decision,
        text_edit=UNRELATED,
        same_text=UNRELATED,
    ),
    decision(
        "erasure configured for a document no forgotten source held drops a variant",
        "rule 6",
        [STEADY],
        erase_another_document,
        text_edit=UNBOUND,
        same_text=UNBOUND,
    ),
    decision(
        "erasure names an Entity its forget did not remove",
        "rule 6",
        [STEADY],
        claim_an_entity,
        text_edit=UNBOUND,
        same_text=UNBOUND,
    ),
    decision(
        "erasure names only part of what its forget removed",
        "rule 6",
        [STEADY],
        name_part_of_the_removed,
        text_edit=UNBOUND,
        same_text=UNBOUND,
    ),
    decision(
        "erasure removes nothing the old revision cites",
        "rule 6",
        [STEADY],
        remove_nothing,
        text_edit=refuse("erasure_empty"),
        same_text=refuse("erasure_empty"),
    ),
    decision(
        "erasure drops a recipe another saved source reads",
        "rule 6",
        [STEADY],
        read_recipe(drop=True),
        text_edit=UNRELATED,
        same_text=UNRELATED,
    ),
    decision(
        "erasure keeps a recipe another saved source reads",
        "rule 6",
        [STEADY],
        read_recipe(drop=False),
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "erasure unresolves the continuing resolution citing a removed Entity",
        "rule 6",
        [CONTINUING, STEADY],
        removed_entity_input,
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "erasure strips the forgotten span from the continuing group",
        "rule 6",
        [CONTINUING, STEADY],
        strip_the_group(keep=False),
        text_edit=UNRELATED,
        same_text=ADMIT,
    ),
    decision(
        "erasure leaves the forgotten span in the continuing group",
        "rule 6",
        [CONTINUING, STEADY],
        strip_the_group(keep=True),
        text_edit=INCOMPLETE,
        same_text=INCOMPLETE,
    ),
]
