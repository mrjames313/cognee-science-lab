"""Small worlds of a forget that cascades down chains of citations.

The worlds reuse chain_worlds.py's sources: each has a resolution `d` and a
variant `v`, and a source that cites another cites its `d` from its `d` and
its `v` from its `v`. Source s0 is forgotten. Every other source is in one
state:

- ok: current and served.
- blocked: its withdrawal failed, so its removal waits for that attempt.
- drifted: current, but its `d` cites each cited source's `d` at a
  fingerprint that record no longer has, so a removal of that record does
  not reach it (review resolution 12); its `v` cites as usual.
- reconciled: served, then a reconcile at the same revision failed, so its
  removal applies in place to a revision its citers pinned (fix round 1).

`cascade_oracle` states the cascade as the user decided it, not as the code
computes it: a decision that cites the forgotten source, or a record a
removal removes as it was, is removed; each dependent has one removal
revision at its longest path from the forgotten source; a removal waits
for a blocked removal above it.
"""

import dataclasses
import json

from chain_worlds import DECISIONS, identity, payload_of, record_key, row_of
from cognee_lab.identity.models import IdentitySource, Tombstone
from cognee_lab.identity.validation import text_digest

FORGOTTEN = "s0"
CASCADE_STATES = ("ok", "blocked", "drifted", "reconciled")
STALE = text_digest("an earlier fingerprint")


def described(label, cites, state="ok") -> IdentitySource:
    """The source's description: a drifted source pins a stale fingerprint
    on each citation of a `d`."""
    payload = payload_of(label, cites=cites)
    if state == "drifted":
        for cited in cites:
            payload["inputs"][record_key(cited, "d")]["content_sha256"] = STALE
    return IdentitySource.model_validate_json(json.dumps(payload))


def source_row(label, cites, state):
    row = row_of(described(label, cites, state), "ok")
    if state == "blocked":
        row = dataclasses.replace(
            row, state="failed", plan=dict(operation="identity_withdraw")
        )
    if state == "reconciled":
        row = dataclasses.replace(
            row, state="failed", plan=dict(operation="identity_publish")
        )
    return row


def forgotten_row(graph):
    source = described(FORGOTTEN, graph[FORGOTTEN])
    tombstone = Tombstone.of(source, forgotten_at="t", removed_entity_ids=())
    return dataclasses.replace(
        row_of(source, "ok"),
        state="forgotten",
        description=None,
        tombstone=tombstone,
        plan=dict(operation="identity_forget"),
    )


def pending_row(graph):
    """s0 while its forget is pending, by its saved plan."""
    source = described(FORGOTTEN, graph[FORGOTTEN])
    doc = source.inputs[source.original_input_ref]
    plan = dict(
        operation="identity_forget",
        entities={},
        revision=source.revision,
        original_data_id=str(doc.data_id),
    )
    return dataclasses.replace(row_of(source, "ok"), state="pending", plan=plan)


def readded(rows):
    """`rows` with s0 re-added after its forget: current at the revision
    after its tombstone's, which the row keeps as its last tombstone."""
    (forgotten,) = [r for r in rows if r.tombstone is not None]
    tomb = forgotten.tombstone
    payload = payload_of(FORGOTTEN, cites=())
    payload["revision"] = tomb.revision + 1
    source = IdentitySource.model_validate_json(json.dumps(payload))
    row = dataclasses.replace(row_of(source, "ok"), tombstone=None, last_tombstone=tomb)
    return [row if r is forgotten else r for r in rows]


def cascade_rows(graph, states, forget=forgotten_row):
    """The rows of one world: s0's, by `forget`, then every other source's
    in its state."""
    return [forget(graph)] + [
        source_row(label, graph[label], states[label])
        for label in sorted(graph)
        if label != FORGOTTEN
    ]


def cascade_oracle(graph, states):
    """Each dependent's level, removed decisions and cited removed records,
    by source identity, as the user decided them, and the sources whose
    removal waits: a blocked one, and each one that cites a record a
    waiting one removes."""
    level, removed, cited = {}, {}, {}
    grew = True
    while grew:
        grew = False
        for label in sorted(graph):
            if label == FORGOTTEN:
                continue
            decisions, depth, records = set(), 0, set()
            for source in graph[label]:
                for d in DECISIONS:
                    if source == FORGOTTEN:
                        decisions.add(d)
                        depth = max(depth, 1)
                    elif d in removed.get(source, ()) and not (
                        d == "d" and states[label] == "drifted"
                    ):
                        decisions.add(d)
                        depth = max(depth, level[source] + 1)
                        records.add((str(identity(source)), d))
            found = (depth, frozenset(decisions), frozenset(records))
            if (
                decisions
                and (level.get(label), removed.get(label), cited.get(label)) != found
            ):
                level[label], removed[label], cited[label] = found
                grew = True
    waiting = {label for label in level if states[label] == "blocked"}
    grew = True
    while grew:
        grew = False
        for label in level:
            behind = {s for s, _ in cited[label]} & {str(identity(w)) for w in waiting}
            if label not in waiting and behind:
                waiting.add(label)
                grew = True
    plan = {
        str(identity(label)): (level[label], removed[label], cited[label])
        for label in level
    }
    return plan, {str(identity(label)) for label in waiting}


def new_citation(source, cited, decision) -> IdentitySource:
    """`source` with one more citation, of `cited`'s record `decision` as it
    is now, from its decision of the same kind, under a new key."""
    from cognee_lab.identity.records import REGISTRY, citation

    payload = source.model_dump(mode="json")
    key = f"new_{decision}_{cited.identity_data_id}"
    payload["inputs"][key] = citation(cited, decision)
    field = REGISTRY[payload["inputs"][key]["record_type"]].field
    for record in payload[field].values():
        record["input_refs"].append(key)
    return IdentitySource.model_validate_json(json.dumps(payload))
