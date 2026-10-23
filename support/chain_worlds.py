"""Small worlds of sources that cite one another's saved records.

Each source has its own document and one decision, resolution `d` of its
group `g`, accepted to the Helios controller. `d` may cite `d` of any other
source as a saved record pinned at that source's revision 1. Each source is
in one state, which decides its ledger row, its current decision and the
withholding table:

- ok: current and served.
- held: served, and a table row withholds its `d` for review.
- replaced: served, its `d` retargeted in place, so its fingerprint differs.
- rekeyed: served, its decision renamed to `e`, so `d` is gone.
- pending: its latest attempt is pending.
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
STATES = ("ok", "held", "replaced", "rekeyed", "pending", "withdrawn", "invalid")
SERVED = frozenset({"ok", "held", "replaced", "rekeyed"})
DATASET = uuid5(NAMESPACE_URL, "cognee-lab:chain-worlds:dataset")
HELIOS = "8b4bff50-907b-56b6-bc80-3b0a7018714a"
HC = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"
TEXT = "The controller limits oscillations.\n"
MENTION = "The controller"


def identity(label) -> UUID:
    return uuid5(DATASET, f"{label}:identity")


def record_key(label) -> str:
    return f"rec_{label}"


def producer():
    return dict(
        method="captured_fixture",
        implementation="chain-worlds",
        version="0.1",
        configuration={},
        run_id=None,
    )


def payload_of(label, *, key="d", target=HELIOS, cites=()) -> dict:
    """One source's description: its document, one chunk, one group and
    the decision under `key`, citing `d` of each source in `cites`."""
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
                target_entity_id=target,
                input_refs=["doc", "existing_A"],
                producer_ref="fixture",
            )
        },
        variant_assignments={},
    )
    for cited in sorted(cites):
        payload["inputs"][record_key(cited)] = citation(original(cited), "d")
        payload["mention_resolutions"][key]["input_refs"].append(record_key(cited))
    return payload


@cache
def original(label) -> IdentitySource:
    """A source's revision 1 as every citation pins it."""
    return IdentitySource.model_validate_json(json.dumps(payload_of(label)))


@cache
def described(label, cites: frozenset, state="ok") -> IdentitySource:
    """The source's current description in this state, citing `cites`."""
    options = dict(cites=cites)
    if state == "replaced":
        options["target"] = HC
    if state == "rekeyed":
        options["key"] = "e"
    return IdentitySource.model_validate_json(json.dumps(payload_of(label, **options)))


def row_of(source, state) -> PublicationRow:
    ledger = {"pending": "pending", "withdrawn": "withdrawn"}.get(state, "current")
    return PublicationRow(
        dataset=str(source.dataset_id),
        source=str(source.identity_data_id),
        revision=source.revision,
        verified_revision=source.revision if ledger == "current" else 0,
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


# What each upstream state gives a decision that cites its `d` directly.
DIRECT = {
    "replaced": (Reason.CHANGED, Status.REFRESH_NEEDED),
    "rekeyed": (Reason.REMOVED, Status.REFRESH_NEEDED),
    "pending": (Reason.CHANGED, Status.EDIT_UNFINISHED),
    "withdrawn": (Reason.REMOVED, Status.REFRESH_NEEDED),
    "invalid": (Reason.CHANGED, Status.EDIT_UNFINISHED),
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
    causes = {label: [] for label in graph}
    for label in graph:
        if states[label] == "held":
            causes[label].append((Reason.CHANGED, Status.REFRESH_NEEDED, "existing_A"))
        for cited in graph[label]:
            if states[cited] in DIRECT:
                causes[label].append((*DIRECT[states[cited]], record_key(cited)))
    held = {label for label in graph if causes[label]}
    grew = True
    while grew:
        grew = False
        for label in graph:
            for cited in graph[label]:
                upstream = (
                    states[cited] in SERVED
                    and states[cited] != "rekeyed"
                    and cited in held
                )
                cause = (Reason.CHANGED, Status.UPSTREAM_WITHHELD, record_key(cited))
                if upstream and cause not in causes[label]:
                    causes[label].append(cause)
                    held.add(label)
                    grew = True
    found = {}
    for label in graph:
        if states[label] not in SERVED or not causes[label]:
            continue
        reason, status = causes[label][0][:2]
        for r, s, _ in causes[label][1:]:
            reason, status = stronger(reason, r), stronger(status, s)
        key = "e" if states[label] == "rekeyed" else "d"
        found[str(identity(label))] = {
            key: Withheld(reason, status, frozenset(c[2] for c in causes[label]))
        }
    return found
