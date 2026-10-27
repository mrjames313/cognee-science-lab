"""The conformance fixture: DOC01 of the Helios corpus, described by rules over
its text and one hand-read table of references, and published through the
lab's `add` and `cognify`.

The describer reads only DOC01's text and its native chunks. Its rules and
its table were written by an author who had read the answers that
`support/conformance_check.py` scores, so that check measures retrieval over
a fixed description. It is a conformance check, not an evaluation of
Describe. docs/stage6_conformance_check.md ("The describer") states the
rules.
"""

import json
import re
from enum import Enum
from pathlib import Path
from typing import NamedTuple
from uuid import NAMESPACE_URL, UUID, uuid5

from . import entry
from .captured_chunks import bind_chunks
from .environment import DATASET_NAME, read_embedding
from .fixture import (
    ChunkFact,
    FactTarget,
    check_chunk_vectors,
    check_fact_edge,
    require_inspected_cognee,
    write_chunk_facts,
)
from .models import Accepted, IdentitySource
from .publish import Publisher
from .validation import IntentError, fresh_mention_id, map_chunks, text_digest

DOC01 = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "DOC01_helios1_technical_overview_v2.md"
)
ORIGINAL_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:conformance:doc01")
IDENTITY_DATA_ID = uuid5(NAMESPACE_URL, "cognee-lab:conformance:doc01:identity")
RELATION = "stated_with"
RULES = "rules"
READING = "reading"
# The commands a conformance-fixture root takes: its description has no
# captured fixture edits, so it is created, read and searched only.
COMMANDS = frozenset({"conformance-fixture", "status", "retrieve", "search"})

ABBREVIATION = re.compile(r"((?:[A-Za-z][\w-]*\s+){1,6})\(([A-Z]{2,5})\)")
TITLE_NAME = re.compile(r"\b[A-Z][\w-]*(?:\s+[A-Z][\w-]*)+")
ALIAS_STATEMENT = re.compile(r"generally uses “(?P<name>[^”]+?)\.?”\s+(?P<rest>.*)")
QUOTED = re.compile(r"“([^”]+?)[,.]?”")
QUANTITY = re.compile(
    r"(?<![\w.])\d+(?:\.\d+)?(?:[–-]\d+(?:\.\d+)?)?(?:%|\s(?:m|s|T|MW|kHz|MA)\b)"
)
# A sentence ends at its punctuation; the whitespace after it is consumed.
SENTENCE_END = re.compile(r"[.!?]”?(\s+)(?=[A-Z“])")
TABLE_RULE = re.compile(r"^\|[-:| ]+\|$")


class Reference(NamedTuple):
    """A hand-read reference group: each occurrence as its surface form and
    a passage DOC01 holds once, whose first instance of the surface form it
    is, and the reusable name the group refers to."""

    occurrences: tuple[tuple[str, str], ...]
    target: str


# Read from DOC01: each group refers to the Entity its paragraph names, or,
# inside a quotation, the one the sentence that introduces it names.
REFERENCES = {
    "g01": Reference(
        (
            ("The controller", "The controller receives fast magnetic"),
            ("It", "It has separate gain schedules"),
        ),
        "Vertical Control System",
    ),
    "g02": Reference(
        (
            ("The density controller", "The density controller was commissioned"),
            ("The controller", "The controller has proportional"),
            ("It", "It can be disabled"),
            ("It", "It was not used as an experimental variable"),
        ),
        "Edge Density Controller",
    ),
    "g03": Reference(
        (("the controller", "the controller reduced vertical motion"),),
        "Vertical Control System",
    ),
    "g04": Reference(
        (("the controller", "the controller increased gas flow"),),
        "Edge Density Controller",
    ),
    "g05": Reference(
        (
            ("Aurora", "Aurora combines calibrated"),
            ("The suite", "The suite is maintained"),
            ("The suite", "The suite was used to reconstruct"),
            ("It", "It also provides the common equilibrium"),
        ),
        "Aurora Reconstruction Suite",
    ),
    "g06": Reference(
        (("The device", "The device was constructed"),),
        "Helios-1",
    ),
    "g07": Reference(
        (
            ("The machine", "The machine is a conventional"),
            ("the machine", "the machine was returned to 6.2"),
        ),
        "Helios-1",
    ),
    "g08": Reference(
        (("It", "It was not the dominant heating actuator"),),
        "Electron Cyclotron Heating System",
    ),
    "g09": Reference(
        (("the probe array", "the probe array is not treated"),),
        "Magnetic Probe Array",
    ),
    "g10": Reference(
        (("The density controller", "The density controller was introduced"),),
        "Edge Density Controller",
    ),
    "g11": Reference(
        (("The machine", "The machine combines high-field"),),
        "Helios-1",
    ),
}


class Fact(NamedTuple):
    """One stated fact: a subject Entity, the Entity or quantity stated with
    it, and the sentence of DOC01 that states both, as `[start, end)`."""

    subject_id: UUID
    target: FactTarget
    text: str
    start: int
    end: int


def entity_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"cognee-lab:conformance:entity:{name.casefold()}")


def body_lines(text):
    """Each line of DOC01's body with its offset: no heading, no bold
    front matter, no table rule, and nothing from the references on."""
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == "## References":
            return
        if stripped and not stripped.startswith(("#", "**")):
            if not TABLE_RULE.match(stripped):
                yield offset, line.rstrip("\n")
        offset += len(line)


def sentence_start(line, position) -> bool:
    before = line[:position].rstrip()
    return not before or before[-1] in ".:!?“"


def reusable_names(text) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """The reusable names in DOC01 by casefold, as first written, and the
    variant pairs (alias, name) among them, from four rules:

    1. An abbreviation definition `long form (ABBR)`, where ABBR is the
       initials of the last words: both names, ABBR a variant of the long form.
    2. A defined long form followed by "System": a variant of the long form.
    3. A run of two or more capitalized words, not at a sentence start.
    4. An alias statement `generally uses “N.”` followed by quoted names
       before any `, where` qualifier: each quoted name a variant of N.
    """
    names: dict[str, str] = {}
    variants: list[tuple[str, str]] = []

    def add(name):
        return names.setdefault(name.casefold(), name)

    lines = list(body_lines(text))
    for _, line in lines:
        for match in ABBREVIATION.finditer(line):
            words, abbreviation = match.group(1).split(), match.group(2)
            last = words[-len(abbreviation) :]
            if (
                len(last) == len(abbreviation)
                and abbreviation == "".join(w[0] for w in last).upper()
            ):
                variants.append((add(abbreviation), add(" ".join(last))))
    for long_form in [t for _, t in variants]:
        if long_form.casefold().endswith(" system"):
            continue
        found = re.search(
            rf"(?<![\w-]){re.escape(long_form)} System\b", text, re.IGNORECASE
        )
        if found:
            variants.append((add(found.group(0)), long_form))
    for _, line in lines:
        if line.startswith("|"):
            continue
        for match in TITLE_NAME.finditer(line):
            if not sentence_start(line, match.start()):
                add(match.group(0))
        if statement := ALIAS_STATEMENT.search(line):
            name = add(statement["name"])
            listed = statement["rest"].split(", where", 1)[0]
            for alias in QUOTED.findall(listed):
                variants.append((add(alias), name))
    return names, list(dict.fromkeys(variants))


def locate(text, surface, passage) -> tuple[int, int]:
    """The offsets of `surface` within the one occurrence of `passage`."""
    at = text.find(passage)
    if at < 0 or text.find(passage, at + 1) >= 0:
        raise IntentError(
            "fixture_shape", f"DOC01 must hold the passage {passage!r} once"
        )
    inner = passage.find(surface)
    if inner < 0:
        raise IntentError("fixture_shape", f"{surface!r} is not in {passage!r}")
    return at + inner, at + inner + len(surface)


def describe(text, chunks, dataset_id) -> IdentitySource:
    """DOC01's description from its text and native chunks alone."""
    names, variants = reusable_names(text)
    constructions = {
        str(entity_id(n)): dict(name=n, description="A reusable name in DOC01.")
        for n in names.values()
    }
    groups, resolutions = {}, {}
    for number, (key, reference) in enumerate(REFERENCES.items(), 1):
        if reference.target.casefold() not in names:
            raise IntentError(
                "fixture_shape", f"No reusable name {reference.target!r} in DOC01"
            )
        occurrences = sorted(
            locate(text, surface, passage) for surface, passage in reference.occurrences
        )
        mention = fresh_mention_id(IDENTITY_DATA_ID, 1, key)
        surfaces = dict.fromkeys(text[s:e] for s, e in occurrences)
        constructions[str(mention)] = dict(
            name="; ".join(surfaces), description=f"Reference group {key} in DOC01."
        )
        groups[key] = dict(
            entity_id=str(mention),
            document_ref="doc01",
            occurrences=[dict(start=s, end=e, text=text[s:e]) for s, e in occurrences],
            chunk_refs=[],
            input_refs=["doc01"],
            producer_ref=READING,
        )
        resolutions[f"r{number:02}"] = dict(
            group_ref=key,
            input_refs=["doc01"],
            producer_ref=READING,
            status="accepted",
            target_entity_id=str(entity_id(reference.target)),
        )
    payload = dict(
        kind="cognee_identity_source",
        schema_version="0.1-draft",
        dataset_id=str(dataset_id),
        identity_data_id=str(IDENTITY_DATA_ID),
        revision=1,
        original_input_ref="doc01",
        inputs=dict(
            doc01=dict(
                kind="source_text",
                dataset_id=str(dataset_id),
                data_id=str(ORIGINAL_DATA_ID),
                text_sha256=text_digest(text),
            )
        ),
        producers={
            RULES: dict(
                method="rules",
                implementation="conformance-describer-rules",
                version="1",
                configuration={},
            ),
            READING: dict(
                method="captured_fixture",
                implementation="conformance-describer-reading",
                version="1",
                configuration={},
            ),
        },
        entity_constructions=constructions,
        mention_groups=groups,
        mention_resolutions=resolutions,
        variant_assignments={
            f"v{number:02}": dict(
                status="accepted",
                source_entity_id=str(entity_id(alias)),
                target_entity_id=str(entity_id(name)),
                applicability=dict(kind="document", document_ref="doc01"),
                input_refs=["doc01"],
                producer_ref=RULES,
            )
            for number, (alias, name) in enumerate(variants, 1)
        },
    )
    bind_chunks(payload, text, chunks)
    return IdentitySource.model_validate_json(json.dumps(payload))


def sentences(text):
    """Each sentence of DOC01's body as `[start, end)`; a table row is one."""
    for offset, line in body_lines(text):
        if line.startswith("|"):
            inner = line.strip("| ")
            start = offset + line.index(inner)
            yield start, start + len(inner)
            continue
        start = 0
        for end in SENTENCE_END.finditer(line):
            yield offset + start, offset + end.start(1)
            start = end.end()
        yield offset + start, offset + len(line.rstrip())


def identity_groups(source) -> dict[UUID, UUID]:
    """Each reusable Entity, and each mention group with an accepted
    resolution, to one representative of its identity group: variants join
    groups, and a mention joins its referent's."""
    mentions = {g.entity_id for g in source.mention_groups.values()}
    parent = {e: e for e in source.entity_constructions if e not in mentions}

    def root(e):
        while parent[e] != e:
            e = parent[e]
        return e

    for variant in source.variant_assignments.values():
        parent[root(variant.source_entity_id)] = root(variant.target_entity_id)
    groups = {e: root(e) for e in parent}
    for decision in source.mention_resolutions.values():
        if isinstance(decision, Accepted):
            mention = source.mention_groups[decision.group_ref].entity_id
            groups[mention] = groups[decision.target_entity_id]
    return groups


class SpanKind(Enum):
    """What a named span of DOC01 is: a reusable Entity's name, an
    occurrence of a reference group, or a quantity with a unit."""

    ENTITY = "entity"
    MENTION = "mention"
    QUANTITY = "quantity"


class Span(NamedTuple):
    start: int
    end: int
    kind: SpanKind
    target: FactTarget


def named_spans(source, text) -> list[Span]:
    """The named spans of DOC01, in text order, with no overlap. Names match
    whole words, abbreviations by case; a longer span wins an overlap."""
    mentions = {g.entity_id for g in source.mention_groups.values()}
    found = []
    for entity, recipe in source.entity_constructions.items():
        if entity in mentions:
            continue
        target = FactTarget(entity, recipe.name, recipe.description)
        flags = 0 if recipe.name == recipe.name.upper() else re.IGNORECASE
        pattern = rf"(?<![\w-]){re.escape(recipe.name)}(?![\w-])"
        found += [
            Span(m.start(), m.end(), SpanKind.ENTITY, target)
            for m in re.finditer(pattern, text, flags)
        ]
    for group in source.mention_groups.values():
        recipe = source.entity_constructions[group.entity_id]
        target = FactTarget(group.entity_id, recipe.name, recipe.description)
        found += [
            Span(o.start, o.end, SpanKind.MENTION, target) for o in group.occurrences
        ]
    for match in QUANTITY.finditer(text):
        name = " ".join(match.group(0).split())
        quantity = uuid5(NAMESPACE_URL, f"cognee-lab:conformance:quantity:{name}")
        target = FactTarget(quantity, name, "A quantity stated in DOC01.")
        found.append(Span(match.start(), match.end(), SpanKind.QUANTITY, target))
    spans, cursor = [], -1
    for span in sorted(found, key=lambda s: (s.start, -s.end)):
        if span.start >= cursor:
            spans.append(span)
            cursor = span.end
    return spans


def facts_of(source, text) -> list[Fact]:
    """The sentence rule: in each sentence the first named reusable Entity or
    reference group is the subject, stated with each other named Entity
    outside its identity group and each quantity. A subject and target pair
    keeps its first sentence."""
    groups = identity_groups(source)
    spans = named_spans(source, text)
    facts, seen = [], set()
    for start, end in sentences(text):
        inside = [s for s in spans if start <= s.start and s.end <= end]
        subject = next(
            (s.target.id for s in inside if s.kind is not SpanKind.QUANTITY), None
        )
        if subject is None:
            continue
        groups_seen, targets = {groups[subject]}, []
        for span in inside:
            if span.kind is SpanKind.QUANTITY:
                targets.append(span.target)
            elif (
                span.kind is SpanKind.ENTITY
                and groups[span.target.id] not in groups_seen
            ):
                groups_seen.add(groups[span.target.id])
                targets.append(span.target)
        for target in targets:
            if (subject, target.id) not in seen:
                seen.add((subject, target.id))
                facts.append(Fact(subject, target, text[start:end], start, end))
    return facts


def fact_evidence(source, chunks):
    """Each fact with the chunks its sentence overlaps, over the checked
    native chunk mapping."""
    ordered = sorted(chunks, key=lambda c: c.chunk_index)
    text = "".join(c.text for c in ordered)
    mapping = map_chunks(text, ordered)
    return [
        (
            fact,
            [
                c
                for c in ordered
                if mapping[str(c.id)][0] < fact.end
                and fact.start < mapping[str(c.id)][1]
            ],
        )
        for fact in facts_of(source, text)
    ]


async def write_facts(publisher, source, chunks, ctx):
    from cognee.modules.provenance.edge_evidence.persistence import (
        flush_context_provenance,
    )

    owned = {c.id: [] for c in chunks}
    for fact, selected in fact_evidence(source, chunks):
        for chunk in selected:
            owned[chunk.id].append(
                ChunkFact(fact.subject_id, fact.target, RELATION, fact.text)
            )
    for chunk in chunks:
        if owned[chunk.id]:
            await write_chunk_facts(publisher, source, chunk, ctx, owned[chunk.id])
    await flush_context_provenance(ctx)


async def verify_facts(publisher, source, chunks, ctx):
    for fact, selected in fact_evidence(source, chunks):
        await check_fact_edge(
            publisher,
            source,
            ctx,
            subject_id=fact.subject_id,
            target_id=fact.target.id,
            relation=RELATION,
            expected=selected,
        )
    await check_chunk_vectors(publisher, chunks)


class StatedFacts:
    """The sentence rule's facts, as the lab's cognify writes and checks
    them (`entry.Semantics`)."""

    write = staticmethod(write_facts)
    verify = staticmethod(verify_facts)


def summary(source, text) -> dict:
    mentions = {g.entity_id for g in source.mention_groups.values()}
    return dict(
        reusable_entities=len(set(source.entity_constructions) - mentions),
        variant_assignments=len(source.variant_assignments),
        mention_groups=len(source.mention_groups),
        accepted_resolutions=sum(
            isinstance(d, Accepted) for d in source.mention_resolutions.values()
        ),
        facts=len(facts_of(source, text)),
        chunks=sum(i.kind == "chunk" for i in source.inputs.values()),
    )


async def run(args, root):
    """`conformance-fixture`: register DOC01 and its description through the
    lab's `add`, then publish it and its stated facts through `cognify`."""
    import cognee

    require_inspected_cognee()
    original = entry.Original(root / DOC01.name, ORIGINAL_DATA_ID)
    text = DOC01.read_text()
    original.path.write_text(text)
    source = await entry.add(
        DATASET_NAME,
        original,
        describe=lambda draft: describe(draft.text, draft.chunks, draft.dataset_id),
        identity_path=root / "identity.json",
    )
    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    await entry.cognify(publisher, source, semantics=StatedFacts(), origin="test")
    result = dict(
        cognee_version=cognee.__version__,
        fixture_root=str(root),
        profile="native configured stores; no LLM",
        embedding=read_embedding(root),
        description=summary(source, text),
        publications=[
            dict(
                state=r.state,
                revision=r.revision,
                verified_revision=r.verified_revision,
            )
            for r in await publisher.records.rows(source.dataset_id)
        ],
        recovery_events=await publisher.records.events(source.dataset_id),
    )
    (root / "result.json").write_text(json.dumps(result, indent=2))
    return result
