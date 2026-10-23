"""The decisions digest changes with every reviewed decision and with
nothing a re-add must rename or that records how a decision was made."""

import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cognee_lab.identity.decisions import decisions_digest
from cognee_lab.identity.forget_fixture import describe_readd
from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.validation import IntentError
from test_identity_forget import HC, TEXT, chunks_of, tomb

A = "8b4bff50-907b-56b6-bc80-3b0a7018714a"


def copied(payload):
    return json.loads(json.dumps(payload))


def accepted(source_payload):
    return copied(source_payload)


def open_candidates(source_payload):
    """r01 is unresolved between A and an Entity of the corpus."""
    p = copied(source_payload)
    r01 = p["mention_resolutions"]["r01"]
    del r01["target_entity_id"]
    r01.update(status="unresolved", candidate_entity_ids=[A, str(uuid4())])
    return p


def three_groups(source_payload):
    """g02 holds `HC` and is ambiguous between HC and an unnamed singleton;
    g03 holds `Helios controller` and has no resolution."""
    p = copied(source_payload)
    singleton = str(uuid4())
    p["entity_constructions"][singleton] = dict(name="X", description="Unnamed.")
    for key, start, end, text in (("g02", 19, 21, "HC"), ("g03", 0, 17, None)):
        entity = str(uuid4())
        p["mention_groups"][key] = dict(
            p["mention_groups"]["g01"],
            entity_id=entity,
            occurrences=[dict(start=start, end=end, text=TEXT[start:end])],
        )
        p["entity_constructions"][entity] = dict(name=key, description="A group.")
    p["mention_resolutions"]["r02"] = dict(
        p["mention_resolutions"]["r01"],
        group_ref="g02",
        status="ambiguous",
        candidate_entity_ids=[str(HC), singleton],
    )
    del p["mention_resolutions"]["r02"]["target_entity_id"]
    return p


BASES = (accepted, open_candidates, three_groups)


def reusable(p):
    groups = {g["entity_id"] for g in p["mention_groups"].values()}
    return sorted(set(p["entity_constructions"]) - groups)


def outcomes(p, r):
    """Every outcome resolution `r` may take over this source's Entities,
    including its own candidates with one of them exchanged for another."""
    entities = reusable(p)
    for e in entities:
        yield dict(status="accepted", target_entity_id=e)
    own = r.get("candidate_entity_ids") or []
    exchanged = [
        own[:n] + [e] + own[n + 1 :] for n in range(len(own)) for e in entities
    ]
    for status in ("unresolved", "ambiguous"):
        for candidates in (None, [], *([e] for e in entities), entities, *exchanged):
            yield dict(status=status, candidate_entity_ids=candidates)


def decision_changes(p):
    """(kind, edit) for each single change to a reviewed decision."""
    for k, r in p["mention_resolutions"].items():
        for outcome in outcomes(p, r):

            def edit(q, k=k, outcome=outcome):
                r = q["mention_resolutions"][k]
                for field in ("target_entity_id", "candidate_entity_ids"):
                    r.pop(field, None)
                r.update({f: v for f, v in outcome.items() if v is not None})
                if outcome.get("candidate_entity_ids") is None:
                    r.pop("candidate_entity_ids", None)

            yield "outcome", edit
        for g in p["mention_groups"]:
            yield "regroup", lambda q, k=k, g=g: q["mention_resolutions"][k].update(
                group_ref=g
            )
        yield "drop", lambda q, k=k: q["mention_resolutions"].pop(k)
    for k in p["variant_assignments"]:

        def swap(q, k=k):
            v = q["variant_assignments"][k]
            v["source_entity_id"], v["target_entity_id"] = (
                v["target_entity_id"],
                v["source_entity_id"],
            )

        yield "variant swap", swap
        for end in ("source_entity_id", "target_entity_id"):
            for e in reusable(p):
                yield "retarget", lambda q, k=k, end=end, e=e: q["variant_assignments"][
                    k
                ].update({end: e})
        for scope in (
            dict(kind="corpus"),
            dict(kind="document", document_ref="doc01"),
            dict(
                kind="text_spans", document_ref="doc01", ranges=[dict(start=0, end=5)]
            ),
        ):
            yield "applicability", lambda q, k=k, scope=scope: q["variant_assignments"][
                k
            ].update(applicability=scope)
        yield "drop", lambda q, k=k: q["variant_assignments"].pop(k)
    for e in p["entity_constructions"]:
        for field in ("name", "description"):
            yield "recipe", lambda q, e=e, field=field: q["entity_constructions"][
                e
            ].update({field: q["entity_constructions"][e][field] + " (edited)"})
    for kind in ("mention_resolutions", "variant_assignments", "mention_groups"):
        for k in p[kind]:

            def rename(q, kind=kind, k=k):
                q[kind][f"{k}_renamed"] = q[kind].pop(k)
                for r in q["mention_resolutions"].values():
                    if kind == "mention_groups" and r["group_ref"] == k:
                        r["group_ref"] = f"{k}_renamed"

            yield "key rename", rename
    for g, group in p["mention_groups"].items():
        for n in range(len(group["occurrences"])):
            yield "occurrence drop", lambda q, g=g, n=n: q["mention_groups"][g][
                "occurrences"
            ].pop(n)
            for other in p["mention_groups"]:

                def move(q, g=g, n=n, other=other):
                    o = q["mention_groups"][g]["occurrences"].pop(n)
                    into = q["mention_groups"][other]["occurrences"]
                    into.append(o)
                    into.sort(key=lambda o: o["start"])

                yield "occurrence move", move


def admitted(p, edit):
    q = copied(p)
    edit(q)
    try:
        return IdentitySource.model_validate_json(json.dumps(q))
    except ValidationError:
        return None


@pytest.mark.parametrize("base", BASES)
def test_every_decision_change_changes_the_digest(source_payload, base):
    p = base(source_payload)
    digest = decisions_digest(IdentitySource.model_validate_json(json.dumps(p)))
    kinds, same = set(), []
    for n, (kind, edit) in enumerate(decision_changes(p)):
        changed = admitted(p, edit)
        if changed is None or changed == admitted(p, lambda q: None):
            continue
        kinds.add(kind)
        if decisions_digest(changed) == digest:
            same.append((n, kind))
    assert same == []
    assert {"outcome", "drop", "recipe", "key rename"} <= kinds
    if p["variant_assignments"]:
        assert {"variant swap", "applicability"} <= kinds
    if len(reusable(p)) > 2:
        assert "retarget" in kinds
    if any(len(g["occurrences"]) > 1 for g in p["mention_groups"].values()):
        assert "occurrence drop" in kinds
    if len(p["mention_groups"]) > 1:
        assert {"occurrence move", "regroup"} <= kinds


def renamed_everywhere(p):
    """Every Entity of the source under another UUID, in every role."""
    text = json.dumps(p)
    for old in p["entity_constructions"]:
        text = text.replace(old, str(uuid4()))
    return json.loads(text)


def ignored_changes(p):
    def revision(q):
        q["revision"] += 1

    def producers(q):
        q["producers"]["fixture"]["version"] = "0.2"
        q["producers"]["again"] = dict(q["producers"]["fixture"], run_id="2")
        for kind in ("mention_groups", "mention_resolutions", "variant_assignments"):
            for record in q[kind].values():
                record["producer_ref"] = "again"

    def inputs(q):
        q["inputs"]["chunk01"]["chunk_id"] = str(uuid4())
        q["inputs"]["more"] = dict(q["inputs"]["existing_A"], entity_id=str(uuid4()))
        for kind in ("mention_groups", "mention_resolutions", "variant_assignments"):
            for record in q[kind].values():
                record["input_refs"].append("more")

    def explanations(q):
        for kind in ("mention_resolutions", "variant_assignments"):
            for record in q[kind].values():
                record["explanation"] = "Reviewed again."

    def text_shift(q):
        q["inputs"]["chunk01"]["end"] += 3
        for group in q["mention_groups"].values():
            for o in group["occurrences"]:
                o["start"], o["end"] = o["start"] + 3, o["end"] + 3

    def uuids(q):
        q.clear()
        q.update(renamed_everywhere(p))

    return (revision, producers, inputs, explanations, text_shift, uuids)


@pytest.mark.parametrize("base", BASES)
def test_nothing_a_readd_renames_or_how_a_decision_was_made_changes_it(
    source_payload, base
):
    p = base(source_payload)
    source = IdentitySource.model_validate_json(json.dumps(p))
    digest = decisions_digest(source)
    for edit in ignored_changes(p):
        changed = admitted(p, edit)
        assert changed is not None, edit.__name__
        assert decisions_digest(changed) == digest, edit.__name__

    readds = 0
    for removed in (set(), {HC}, {UUID(A)}, {HC, UUID(A)}, set(map(UUID, reusable(p)))):
        try:
            readded = describe_readd(
                source, tomb(source), removed, TEXT, chunks_of(source, TEXT)
            )
        except IntentError:
            continue
        readds += 1
        assert decisions_digest(readded) == digest, removed
    assert readds >= 3
