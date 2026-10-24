"""Small worlds of sources that cite one another's saved records.

Each source has its own document and two decisions: resolution `d` of its
group `g`, accepted to the Helios controller, and variant `v`, HC as the
Helios controller within its document. A source that cites another cites
both of its records, each from its own kind of decision: its `d` cites the
other's `d` and its `v` the other's `v`, each pinned at that source's
revision 1. So the worlds cover both record types and show that
withholding follows the decision, not the source. Each source is in one
state, which decides its ledger row, its current decisions and the
withholding table:

- ok: current and served.
- held: served, and a table row withholds its `d` for review.
- replaced: served, its `d` and `v` changed in place, so their fingerprints
  differ.
- rekeyed: served, its resolution renamed to `e`, so `d` is gone.
- pending: its latest attempt is pending.
- unverified: current, but its verified revision is behind its saved one.
- withdrawn: withdrawn.
- invalid: current, but an own input fails live validation.

`chain_check.py` runs the real admission and withholding code on every such
world and compares it with `oracle`, which is written from the user's
decisions, not from the code.
"""

import json
from functools import cache
from itertools import product
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from cognee_lab.identity.models import IdentitySource
from cognee_lab.identity.records import citation
from cognee_lab.identity.storage import PublicationRow
from cognee_lab.identity.validation import Reason, object_digest, text_digest
from cognee_lab.identity.withholding import Status, Withheld, WithholdingRow

LABELS = ("s0", "s1", "s2", "s3")
STATES = (
    "ok",
    "held",
    "replaced",
    "rekeyed",
    "pending",
    "unverified",
    "withdrawn",
    "invalid",
)
SERVED = frozenset({"ok", "held", "replaced", "rekeyed"})
DATASET = uuid5(NAMESPACE_URL, "cognee-lab:chain-worlds:dataset")
HELIOS = "8b4bff50-907b-56b6-bc80-3b0a7018714a"
HC = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
TEXT = "The controller limits oscillations.\n"
MENTION = "The controller"


def identity(label) -> UUID:
    return uuid5(DATASET, f"{label}:identity")


# Each decision of a source, with the prefix of the input keys under which
# a citing source's decision of the same kind cites it.
DECISIONS = {"d": "rec", "v": "var"}


def record_key(label, decision="d") -> str:
    return f"{DECISIONS[decision]}_{label}"


def producer():
    return dict(
        method="captured_fixture",
        implementation="chain-worlds",
        version="0.1",
        configuration={},
        run_id=None,
    )


def payload_of(label, *, key="d", replaced=False, cites=()) -> dict:
    """One source's description: its document, one chunk, one group, the
    resolution under `key` and variant `v`, each citing the record of the
    same kind of each source in `cites`. `replaced` changes both decisions
    in place."""
    own = identity(label)
    mention = str(uuid5(own, "mention:g"))
    payload = dict(
        kind="cognee_identity_source",
        schema_version="0.1-draft",
        dataset_id=str(DATASET),
        identity_data_id=str(own),
        revision=1,
        original_input_ref="doc",
        inputs=dict(
            doc=dict(
                kind="source_text",
                dataset_id=str(DATASET),
                data_id=str(uuid5(DATASET, f"{label}:document")),
                text_sha256=text_digest(TEXT),
            ),
            chunk01=dict(
                kind="chunk",
                document_ref="doc",
                chunk_id=str(uuid5(own, "chunk01")),
                start=0,
                end=len(TEXT),
            ),
            existing_A=dict(
                kind="corpus_object",
                dataset_id=str(DATASET),
                entity_id=HELIOS,
                selected_fields=["name"],
                content_sha256=object_digest({"name": "Helios controller"}),
            ),
        ),
        producers=dict(fixture=producer()),
        entity_constructions={
            mention: dict(name=MENTION, description="mention"),
            HELIOS: dict(name="Helios controller", description="seed"),
            HC: dict(name="HC", description="seed"),
        },
        mention_groups=dict(
            g=dict(
                entity_id=mention,
                document_ref="doc",
                occurrences=[dict(start=0, end=len(MENTION), text=MENTION)],
                chunk_refs=["chunk01"],
                input_refs=["doc"],
                producer_ref="fixture",
            )
        ),
        mention_resolutions={
            key: dict(
                group_ref="g",
                status="accepted",
                target_entity_id=HC if replaced else HELIOS,
                input_refs=["doc", "existing_A"],
                producer_ref="fixture",
            )
        },
        variant_assignments=dict(
            v=dict(
                status="accepted",
                source_entity_id=HELIOS if replaced else HC,
                target_entity_id=HC if replaced else HELIOS,
                applicability=dict(kind="document", document_ref="doc"),
                input_refs=["doc", "existing_A"],
                producer_ref="fixture",
            )
        ),
    )
    decisions = dict(
        d=payload["mention_resolutions"][key], v=payload["variant_assignments"]["v"]
    )
    for cited in sorted(cites):
        for decision, record in decisions.items():
            ref = record_key(cited, decision)
            payload["inputs"][ref] = citation(original(cited), decision)
            record["input_refs"].append(ref)
    return payload


@cache
def original(label) -> IdentitySource:
    """A source's revision 1 as every citation pins it."""
    return IdentitySource.model_validate_json(json.dumps(payload_of(label)))


@cache
def described(label, cites: frozenset, state="ok") -> IdentitySource:
    """The source's current description in this state, citing `cites`."""
    options = dict(cites=cites, replaced=state == "replaced")
    if state == "rekeyed":
        options["key"] = "e"
    return IdentitySource.model_validate_json(json.dumps(payload_of(label, **options)))


def row_of(source, state) -> PublicationRow:
    ledger = {"pending": "pending", "withdrawn": "withdrawn"}.get(state, "current")
    verified = ledger == "current" and state != "unverified"
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        revision=source.revision,
        verified_revision=source.revision if verified else 0,
        state=ledger,
        attempt=str(uuid4()),
        description=source,
        tombstone=None,
        plan={},
    )


def held_row(label) -> WithholdingRow:
    return WithholdingRow(
        dataset=str(DATASET),
        source=str(identity(label)),
        assignment="d",
        input_ref="existing_A",
        consumed=str(uuid5(DATASET, "edited")),
        edit_revision=2,
        reason=Reason.CHANGED,
        status=Status.REFRESH_NEEDED,
        old_digest=None,
        new_digest=None,
    )


def graphs(labels):
    """Every citation graph on `labels`: each source's set of cited sources,
    never itself."""
    pairs = [(a, b) for a in labels for b in labels if a != b]
    for edges in product((False, True), repeat=len(pairs)):
        graph = {label: set() for label in labels}
        for (a, b), present in zip(pairs, edges):
            if present:
                graph[a].add(b)
        yield {label: frozenset(cited) for label, cited in graph.items()}


def cyclic_from(graph, start) -> bool:
    """Whether a path of citations leads from `start` back to it."""
    seen, todo = set(), list(graph[start])
    while todo:
        node = todo.pop()
        if node == start:
            return True
        if node not in seen:
            seen.add(node)
            todo.extend(graph[node])
    return False


def acyclic(graph) -> bool:
    return not any(cyclic_from(graph, label) for label in graph)


def world_rows(graph, states):
    """The ledger rows and withholding table of one world."""
    rows = [
        row_of(described(label, graph[label], states[label]), states[label])
        for label in graph
    ]
    table = [held_row(label) for label in graph if states[label] == "held"]
    return rows, table


# What each upstream state gives a decision that cites one of its records
# directly, by the kind of the cited decision.
DIRECT = {
    "replaced": dict.fromkeys(DECISIONS, (Reason.CHANGED, Status.REFRESH_NEEDED)),
    "rekeyed": dict(d=(Reason.REMOVED, Status.REFRESH_NEEDED)),
    "pending": dict.fromkeys(DECISIONS, (Reason.CHANGED, Status.EDIT_UNFINISHED)),
    "unverified": dict.fromkeys(DECISIONS, (Reason.CHANGED, Status.EDIT_UNFINISHED)),
    "withdrawn": dict.fromkeys(DECISIONS, (Reason.REMOVED, Status.REFRESH_NEEDED)),
    "invalid": dict.fromkeys(DECISIONS, (Reason.CHANGED, Status.EDIT_UNFINISHED)),
}


def stronger(a, b):
    order = list(type(a))
    return max(a, b, key=order.index)


def oracle(graph, states) -> dict[str, dict[str, Withheld]]:
    """The withheld decisions of every served source that validates, as
    the user decided them: a decision is withheld when its own input
    changed, when a record it cites changed, went or belongs to an
    unfinished source, and, down the whole chain, when a record it cites is
    withheld (`input_changed`, `upstream_withheld`). Keys are source
    identities, as the code reports them."""
    causes = {(label, d): [] for label in graph for d in DECISIONS}
    for label in graph:
        if states[label] == "held":
            causes[label, "d"].append(
                (Reason.CHANGED, Status.REFRESH_NEEDED, "existing_A")
            )
        for cited in graph[label]:
            for d, direct in DIRECT.get(states[cited], {}).items():
                causes[label, d].append((*direct, record_key(cited, d)))
    grew = True
    while grew:
        grew = False
        for label in graph:
            for cited in graph[label]:
                for d in DECISIONS:
                    upstream = (
                        states[cited] in SERVED
                        and not (states[cited] == "rekeyed" and d == "d")
                        and causes[cited, d]
                    )
                    cause = (
                        Reason.CHANGED,
                        Status.UPSTREAM_WITHHELD,
                        record_key(cited, d),
                    )
                    if upstream and cause not in causes[label, d]:
                        causes[label, d].append(cause)
                        grew = True
    found = {}
    for label in graph:
        if states[label] not in SERVED:
            continue
        for d in DECISIONS:
            if not causes[label, d]:
                continue
            reason, status = causes[label, d][0][:2]
            for r, s, _ in causes[label, d][1:]:
                reason, status = stronger(reason, r), stronger(status, s)
            key = "e" if (d, states[label]) == ("d", "rekeyed") else d
            found.setdefault(str(identity(label)), {})[key] = Withheld(
                reason, status, frozenset(c[2] for c in causes[label, d])
            )
    return found
