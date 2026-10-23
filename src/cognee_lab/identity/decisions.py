"""Queries over a description's reviewed decisions that models.Tombstone and
the erasure rules share. It reads descriptions by their fields and the
`status` discriminator alone, so models.py can import it."""

from hashlib import sha256

import rfc8785


def naming_keys(source, entity_id) -> set[str]:
    """Keys of the resolutions and variants that name an Entity."""
    return {
        k
        for k, r in source.mention_resolutions.items()
        if r.status == "accepted" and r.target_entity_id == entity_id
    } | {
        k
        for k, v in source.variant_assignments.items()
        if entity_id in (v.source_entity_id, v.target_entity_id)
    }


def roles(source, entity_id) -> list[list[str]]:
    """Each decision that names an Entity, by key, with the part the Entity
    plays in it: an accepted resolution's target or an open resolution's
    candidate, a variant's source or target. Unlike `naming_keys`, which
    leaves out candidates and asks only whether a key names the Entity,
    the role tells a variant's two endpoints apart."""
    found = set()
    for k, r in source.mention_resolutions.items():
        match r.status:
            case "accepted":
                if r.target_entity_id == entity_id:
                    found.add((k, "target"))
            case "unresolved" | "ambiguous":
                if entity_id in (r.candidate_entity_ids or ()):
                    found.add((k, "candidate"))
    for k, v in source.variant_assignments.items():
        if v.source_entity_id == entity_id:
            found.add((k, "source"))
        if v.target_entity_id == entity_id:
            found.add((k, "target"))
    return [list(pair) for pair in sorted(found)]


def decisions_digest(source) -> str:
    """A digest of a description's reviewed decisions that a re-add of the
    same decisions repeats: each resolution by key with its group, status
    and the Entities it names, each variant by key with its endpoints and
    applicability, and each recipe under the name of its Entity. A re-add
    renames the source's own Entities and moves to the next revision, so
    an Entity is named by its group key, or by its `roles`, never by its
    UUID. Each group's occurrences count by their surface text and their
    place in the order of all the source's occurrences, which a text shift
    keeps and a regrouping does not. A span-scoped variant's ranges count
    as offsets: the description holds no surface text for them, and a text edit does not remap them
    either (`admission.check_no_span_variants`), so a shifted range is
    another scope. Producers, inputs and explanations are left out: they
    record how a decision was made and where it reads, which other text or
    a removal changes."""
    groups = {g.entity_id: k for k, g in source.mention_groups.items()}
    spans = sorted(
        (o.start, o.end, k)
        for k, g in source.mention_groups.items()
        for o in g.occurrences
    )
    place = {span: n for n, span in enumerate(spans)}

    def name(entity_id):
        if entity_id in groups:
            return ["group", groups[entity_id]]
        if entity_id in source.entity_constructions:
            return ["roles", roles(source, entity_id)]
        return ["entity", str(entity_id)]

    def names(entity_ids):
        if entity_ids is None:
            return None
        return sorted((name(e) for e in entity_ids), key=rfc8785.dumps)

    def outcome(r):
        match r.status:
            case "accepted":
                return dict(target=name(r.target_entity_id), candidates=None)
            case "unresolved" | "ambiguous":
                return dict(target=None, candidates=names(r.candidate_entity_ids))

    decisions = dict(
        groups={
            k: [[place[o.start, o.end, k], o.text] for o in g.occurrences]
            for k, g in source.mention_groups.items()
        },
        resolutions={
            k: dict(group=r.group_ref, status=r.status, **outcome(r))
            for k, r in source.mention_resolutions.items()
        },
        variants={
            k: dict(
                source=name(v.source_entity_id),
                target=name(v.target_entity_id),
                applicability=v.applicability.model_dump(mode="json"),
            )
            for k, v in source.variant_assignments.items()
        },
        recipes=sorted(
            (
                [name(e), r.name, r.description]
                for e, r in source.entity_constructions.items()
            ),
            key=rfc8785.dumps,
        ),
    )
    return sha256(rfc8785.dumps(decisions)).hexdigest()
