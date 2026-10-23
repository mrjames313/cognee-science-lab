"""Rule 5 of the occurrence check's decision choices: other documents' inputs.

Each builder layers a glossary document's text or span, a corpus input or a
re-confirm on an admitted world from occurrence_worlds.py; the rows state the
outcomes as `DECISIONS` there does.
"""

from uuid import UUID, uuid5

from cognee_lab.identity.validation import text_digest
from occurrence_worlds import (
    ADMIT,
    CONTINUING,
    DOCUMENT,
    HC,
    HELIOS,
    attest,
    continuing_rid,
    decision,
    refuse,
    retarget_continuing_to_hc,
    retarget_document_variant,
    variant,
)

GLOSSARY_TEXT = "HC: Helios controller.\n"
GLOSSARY_ENTRY = "HC: Helios controller."


def add_glossary(payload, key="gloss", *, dataset=None, data_id=None):
    """Another document of the dataset, as a text input."""
    payload["inputs"][key] = dict(
        kind="source_text",
        dataset_id=dataset or payload["dataset_id"],
        data_id=data_id or str(uuid5(UUID(payload["dataset_id"]), key)),
        text_sha256=text_digest(GLOSSARY_TEXT),
    )


def glossary_span(
    payload, key="gloss_hc", *, start=0, entry=GLOSSARY_ENTRY, document="gloss"
):
    payload["inputs"][key] = dict(
        kind="text_span",
        document_ref=document,
        start=start,
        end=start + len(entry),
        text_sha256=text_digest(entry),
    )


def cite(payload, record, key):
    payload["variant_assignments"].get(
        record, payload["mention_resolutions"].get(record)
    )["input_refs"] = ["doc01", key]


def v01_reads_glossary(old, new, ctx):
    for payload in (old, new):
        add_glossary(payload)
        glossary_span(payload)
        cite(payload, "v01", "gloss_hc")


def move_foreign_span(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    glossary_span(new, start=7)


def change_foreign_span(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    glossary_span(new, entry="HC: Helios regulator.")


def move_foreign_span_to_another_document(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    add_glossary(new, "gloss2")
    glossary_span(new, document="gloss2")


def change_foreign_text(old, new, ctx):
    v01_reads_glossary(old, new, ctx)
    new["inputs"]["gloss"]["text_sha256"] = text_digest("changed\n")


def change_corpus_input(old, new, ctx):
    new["inputs"]["existing_A"]["content_sha256"] = text_digest("changed")


def reconfirm(record, *, producer):
    def change(old, new, ctx):
        for payload in (old, new):
            add_glossary(payload)
            glossary_span(payload)
        rid = record(ctx) if callable(record) else record
        cite(old, rid, "gloss_hc")
        new["inputs"].pop("gloss_hc")
        glossary_span(new, "gloss_hc_r2", entry="HC: Helios regulator.")
        cite(new, rid, "gloss_hc_r2")
        if producer:
            attest(new, rid)

    return change


def drop_foreign_input(*, producer):
    """The continuing resolution and its group read the glossary entry; the
    new revision drops that input from both, reviewed fields unchanged."""

    def change(old, new, ctx):
        rid, group = continuing_rid(ctx), ctx["continuing"]
        add_glossary(old)
        glossary_span(old)
        old["mention_resolutions"][rid]["input_refs"].append("gloss_hc")
        old["mention_groups"][group]["input_refs"].append("gloss_hc")
        if producer:
            attest(new, rid)

    return change


def move_group_to_new_input(*, producer):
    """Only the continuing group reads the glossary entry; the new revision
    points the group at a new input key, the resolution unchanged."""

    def change(old, new, ctx):
        group = ctx["continuing"]
        for payload in (old, new):
            add_glossary(payload)
        glossary_span(old)
        old["mention_groups"][group]["input_refs"].append("gloss_hc")
        glossary_span(new, "gloss_hc_r2", entry="HC: Helios regulator.")
        new["mention_groups"][group]["input_refs"].append("gloss_hc_r2")
        if producer:
            attest(new, continuing_rid(ctx))

    return change


def add_variant_reading_new_span(*, producer):
    def change(old, new, ctx):
        add_glossary(new)
        glossary_span(new)
        new["variant_assignments"]["v02"] = variant(HELIOS, HC, DOCUMENT)
        cite(new, "v02", "gloss_hc")
        if producer:
            attest(new, "v02")

    return change


def rename_variant_onto_new_span(*, producer):
    """v01 reads the glossary entry; the new revision renames it v01b and
    points it at the changed entry under a new key."""

    def change(old, new, ctx):
        reconfirm("v01", producer=False)(old, new, ctx)
        new["variant_assignments"]["v01b"] = new["variant_assignments"].pop("v01")
        if producer:
            attest(new, "v01b")

    return change


def retarget_resolution_onto_new_span(*, producer):
    """The continuing resolution reads the glossary entry; the new revision
    retargets it and points it at the changed entry under a new key."""

    def change(old, new, ctx):
        reconfirm(continuing_rid, producer=producer)(old, new, ctx)
        retarget_continuing_to_hc(old, new, ctx)

    return change


def sibling_reconfirmed(old, new, ctx):
    """The old revision's continuing resolution was re-confirmed on the
    changed glossary entry under its own producer; v01 still reads the old
    entry, and the corpus input a fresh resolution cites, under the
    fixture's."""
    rid = continuing_rid(ctx)
    for payload in (old, new):
        add_glossary(payload)
        glossary_span(payload, "gloss_hc_r2", entry="HC: Helios regulator.")
        cite(payload, rid, "gloss_hc_r2")
        attest(payload, rid)
    glossary_span(old)
    old["variant_assignments"]["v01"]["input_refs"].append("gloss_hc")


def rename_variant_onto_siblings_input(*, producer):
    """The new revision renames v01 v01b and points it at the entry the
    continuing resolution's producer re-confirmed."""

    def change(old, new, ctx):
        sibling_reconfirmed(old, new, ctx)
        new["variant_assignments"]["v01b"] = new["variant_assignments"].pop("v01")
        cite(new, "v01b", "gloss_hc_r2")
        if producer:
            attest(new, "v01b", "reconfirm_v01b")

    return change


def retarget_variant_onto_siblings_input(old, new, ctx):
    sibling_reconfirmed(old, new, ctx)
    retarget_document_variant(old, new, ctx)
    cite(new, "v01", "gloss_hc_r2")


def add_text_of_another_dataset(old, new, ctx):
    add_glossary(new, dataset=str(uuid5(UUID(new["dataset_id"]), "other")))


def add_second_own_text(old, new, ctx):
    add_glossary(new, data_id=new["inputs"]["doc01"]["data_id"])


def cited_source(payload):
    return str(uuid5(UUID(payload["dataset_id"]), "cited-source"))


def saved_record(
    payload, key="rec", *, identity=None, dataset=None, revision=1, digest="record"
):
    """A citation of resolution r1 of another source of the dataset."""
    payload["inputs"][key] = dict(
        kind="saved_record",
        dataset_id=dataset or payload["dataset_id"],
        identity_data_id=identity or cited_source(payload),
        record_type="mention_resolution",
        record_id="r1",
        representation_revision=revision,
        content_sha256=text_digest(digest),
    )


def cite_own_record(old, new, ctx):
    saved_record(new, identity=new["identity_data_id"])


def cite_record_of_another_dataset(old, new, ctx):
    saved_record(new, dataset=str(uuid5(UUID(new["dataset_id"]), "other")))


def cite_record(*, producer):
    """v01 cites a saved record the old revision did not cite."""

    def change(old, new, ctx):
        saved_record(new)
        cite(new, "v01", "rec")
        if producer:
            attest(new, "v01")

    return change


def drop_record_citation(*, producer):
    """v01 stops citing a saved record, its reviewed fields unchanged."""

    def change(old, new, ctx):
        saved_record(old)
        cite(old, "v01", "rec")
        cite(new, "v01", "existing_A")
        if producer:
            attest(new, "v01")

    return change


def change_cited_record(**pinned):
    """v01 cites a saved record whose pin changes under its old key."""

    def change(old, new, ctx):
        saved_record(old)
        saved_record(new, **pinned)
        for payload in (old, new):
            cite(payload, "v01", "rec")
        attest(new, "v01")

    return change


def group_cites_record(old, new, ctx):
    """A continuing group cites a saved record in both revisions; its
    resolution cites it through the group."""
    for payload in (old, new):
        saved_record(payload)
        payload["mention_groups"][ctx["continuing"]]["input_refs"].append("rec")


DEPENDENCY_DECISIONS = [
    decision(
        "foreign span moved with its digest unchanged",
        "rule 5",
        [],
        move_foreign_span,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "foreign span changed under its old key",
        "rule 5",
        [],
        change_foreign_span,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "foreign span moved to another document under its old key",
        "rule 5",
        [],
        move_foreign_span_to_another_document,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "foreign text changed under its old key",
        "rule 5",
        [],
        change_foreign_text,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "corpus input changed under its old key",
        "rule 5",
        [],
        change_corpus_input,
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "variant re-confirmed on a new span under a new producer",
        "rule 5",
        [],
        reconfirm("v01", producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "variant cites a new span under its old producer",
        "rule 5",
        [],
        reconfirm("v01", producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution re-confirmed on a new span under a new producer",
        "rule 5",
        [CONTINUING],
        reconfirm(continuing_rid, producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "continuing resolution cites a new span under its old producer",
        "rule 5",
        [CONTINUING],
        reconfirm(continuing_rid, producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution drops a foreign input under its old producer",
        "rule 5",
        [CONTINUING],
        drop_foreign_input(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution drops a foreign input under a new producer",
        "rule 5",
        [CONTINUING],
        drop_foreign_input(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "continuing group moves to a new foreign input under its old producer",
        "rule 5",
        [CONTINUING],
        move_group_to_new_input(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing group moves to a new foreign input under a new producer",
        "rule 5",
        [CONTINUING],
        move_group_to_new_input(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "new variant reads a new span under its old producer",
        "rule 5",
        [],
        add_variant_reading_new_span(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "new variant reads a new span under a new producer",
        "rule 5",
        [],
        add_variant_reading_new_span(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "document variant renamed onto a new span under its old producer",
        "rule 5",
        [],
        rename_variant_onto_new_span(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "document variant renamed onto a new span under a new producer",
        "rule 5",
        [],
        rename_variant_onto_new_span(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "continuing resolution retargeted onto a new span under its old producer",
        "rule 5",
        [CONTINUING],
        retarget_resolution_onto_new_span(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "continuing resolution retargeted onto a new span under a new producer",
        "rule 5",
        [CONTINUING],
        retarget_resolution_onto_new_span(producer=True),
        text_edit=refuse("continuing_decision_changed"),
        same_text=ADMIT,
    ),
    decision(
        "document variant renamed onto a sibling's re-confirmed span under its old producer",
        "rule 5",
        [CONTINUING],
        rename_variant_onto_siblings_input(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "document variant renamed onto a sibling's re-confirmed span under a new producer",
        "rule 5",
        [CONTINUING],
        rename_variant_onto_siblings_input(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "document variant retargeted onto a sibling's re-confirmed span under its old producer",
        "rule 5",
        [CONTINUING],
        retarget_variant_onto_siblings_input,
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "text of another dataset",
        "rule 5",
        [],
        add_text_of_another_dataset,
        text_edit=refuse("not_admitted"),
        same_text=refuse("not_admitted"),
    ),
    decision(
        "second text of the own document",
        "rule 5",
        [],
        add_second_own_text,
        text_edit=refuse("not_admitted"),
        same_text=refuse("not_admitted"),
    ),
    decision(
        "saved record of the citing source itself",
        "rule 5",
        [],
        cite_own_record,
        text_edit=refuse("self_citation"),
        same_text=refuse("self_citation"),
    ),
    decision(
        "saved record of another dataset",
        "rule 5",
        [],
        cite_record_of_another_dataset,
        text_edit=refuse("not_admitted"),
        same_text=refuse("not_admitted"),
    ),
    decision(
        "new saved-record citation under a new producer",
        "rule 5",
        [],
        cite_record(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "new saved-record citation under the old producer",
        "rule 5",
        [],
        cite_record(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "saved-record citation dropped under the old producer",
        "rule 5",
        [],
        drop_record_citation(producer=False),
        text_edit=refuse("reconfirm_unattested"),
        same_text=refuse("reconfirm_unattested"),
    ),
    decision(
        "saved-record citation dropped under a new producer",
        "rule 5",
        [],
        drop_record_citation(producer=True),
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
    decision(
        "saved record's digest changed under its old key",
        "rule 5",
        [],
        change_cited_record(digest="changed"),
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "saved record's pinned revision changed under its old key",
        "rule 5",
        [],
        change_cited_record(revision=2),
        text_edit=refuse("foreign_input_changed"),
        same_text=refuse("foreign_input_changed"),
    ),
    decision(
        "continuing group cites a saved record",
        "rule 5",
        [CONTINUING],
        group_cites_record,
        text_edit=ADMIT,
        same_text=ADMIT,
    ),
]
