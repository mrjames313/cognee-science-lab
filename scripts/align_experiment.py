"""The alignment experiment of docs/minimal_identity_framework.md, open question 7.

Cognifies DOC01 and DOC02 in a fresh isolated root, with or without the
spelling hint. Then it aligns each described name with Cognee's Entities by
the framework's rules (exact, then lexical, each support-checked), ranks the
right nodes in the `Entity_name` vector index, and times Shape 1v's in-memory
view. With --checks it also exercises five Cognee behaviours the design reads
from source.

    uv run --with anthropic==2.3.0 python scripts/align_experiment.py run ROOT --hint|--no-hint [--checks]
    uv run python scripts/align_experiment.py analyze ROOT
    uv run python scripts/align_experiment.py dry-run ROOT
    uv run python scripts/align_experiment.py report BASE

`run` spends LLM calls. `analyze` re-measures an existing root and spends
embedding calls only. `report` prints the tables of
results/minimal_identity_alignment_experiment.md from the roots under BASE.

`run` uses the real LLM and embedding settings that .env names, read into this
process only. Every value stays in memory and none is written to the root.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from cognee_lab.identity import environment  # noqa: E402  (imports no cognee)

DOCS = {
    "doc01": REPO / "data" / "DOC01_helios1_technical_overview.md",
    "doc02": REPO / "data" / "DOC02_campaign_A_high_current.md",
}
DOC01_V2 = REPO / "data" / "DOC01_helios1_technical_overview_v2.md"
HINT_MARKER = "Naming guidance for this document."
# About twice what one root with --checks spends, so a runaway retry loop stops early.
CALL_CAP = 40
VECTOR_DEPTH = 100
# Retrieve step 4's structural edges, plus `made_from` (a chunk summary to its
# chunk), which never touches an Entity and so never reaches step 4.
STRUCTURAL = {"contains", "is_a", "is_part_of", "belongs_to_set", "made_from"}
PAREN = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")


def make_root(root: Path) -> None:
    # Not environment.create_root: this root is no lab fixture kind, and a lab
    # command must not route into it. The marker carries the non-secret
    # embedding record only.
    embedding = environment._env_record(environment._operator_embedding())
    root.mkdir(parents=True, exist_ok=False)
    (root / environment.MARKER).write_text(
        json.dumps({"kind": environment.MARKER_KIND, "embedding": embedding})
    )


def operator_llm() -> dict[str, str]:
    # Read before fixture_environment, which points COGNEE_ENV_FILE elsewhere.
    values = dotenv_values(environment._operator_file())
    keys = ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY")
    if missing := [k for k in keys if not values.get(k)]:
        raise SystemExit(f".env does not set {', '.join(missing)}")
    return {k: values[k] for k in keys}


def real_llm_environment(settings: dict[str, str]) -> None:
    os.environ.update(settings)
    # fixture_environment points the LLM at a closed port so a stray call
    # fails. This experiment calls the provider on purpose, at its default endpoint.
    os.environ.pop("LLM_ENDPOINT", None)


class Calls:
    """Every structured LLM call this process makes, by response model."""

    def __init__(self):
        self.log = []

    def install(self):
        from cognee.infrastructure.llm.LLMGateway import LLMGateway

        original = LLMGateway.acreate_structured_output

        def counted(text_input, system_prompt, response_model, **kwargs):
            if len(self.log) >= CALL_CAP:
                raise RuntimeError(f"LLM call cap {CALL_CAP} reached")
            self.log.append(
                dict(
                    model=getattr(response_model, "__name__", str(response_model)),
                    hinted=HINT_MARKER in system_prompt,
                    prompt_sha=hashlib.sha256(system_prompt.encode()).hexdigest()[:12],
                )
            )
            return original(text_input, system_prompt, response_model, **kwargs)

        LLMGateway.acreate_structured_output = staticmethod(counted)

    def mark(self):
        return len(self.log)

    def since(self, mark):
        part = self.log[mark:]
        return dict(
            total=len(part),
            by_model=dict(Counter(c["model"] for c in part)),
            hinted=sum(c["hinted"] for c in part),
            distinct_prompts=len({c["prompt_sha"] for c in part}),
        )


def norm(text: str) -> str:
    from cognee.modules.engine.utils import generate_node_name

    return generate_node_name(text)


def whole_word(term: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def hint_prompt(names: list[str]) -> str:
    from cognee.infrastructure.llm.config import get_llm_config
    from cognee.infrastructure.llm.prompts import render_prompt

    path = get_llm_config().graph_prompt_path
    base = os.path.dirname(path) if os.path.isabs(path) else None
    prompt = render_prompt(os.path.basename(path) if base else path, {}, base_directory=base)
    listed = "\n".join(f"- {name}" for name in sorted(names))
    return (
        f"{prompt}\n\n{HINT_MARKER} The document's author uses the entity names "
        "listed below. When the text in front of you refers to one of these "
        "entities, name its node with the listed spelling exactly. Do not add a "
        "listed entity unless the text in front of you refers to it.\n"
        f"{listed}\n"
    )


async def dataset_and_rows():
    from cognee.modules.data.methods import get_dataset_data, get_datasets_by_name
    from cognee.modules.users.methods import get_default_user

    user = await get_default_user()
    dataset = (await get_datasets_by_name(environment.DATASET_NAME, user.id))[0]
    return dataset.id, await get_dataset_data(dataset.id)


async def stored_text(row) -> str:
    from cognee.infrastructure.files.utils.open_data_file import open_data_file

    async with open_data_file(row.raw_data_location, mode="r", encoding="utf-8") as f:
        return f.read()


def describe(text):
    """Names and variant pairs from the lab's rule describer. Its author read
    the conformance answers, so this is a fixed description, not a test of
    Describe."""
    from cognee_lab.identity.conformance_fixture import reusable_names

    names, variants = reusable_names(text)
    return sorted({norm(n) for n in names.values()}), [
        (norm(a), norm(b)) for a, b in variants
    ]


def groups_of(described):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for names, variants in described.values():
        for n in names:
            find(n)
        for a, b in variants:
            parent[find(a)] = find(b)
    groups = {}
    for n in parent:
        groups.setdefault(find(n), set()).add(n)
    return {n: frozenset(g) for g in groups.values() for n in g}


def other_end(edge, node_id):
    a, rel, b = edge
    return rel, (b if str(a.get("id")) == node_id else a)


async def read_corpus(graph, data_ids):
    """Each chunk of the corpus with its document, normalised text and the
    Entities it `contains`."""
    chunks = {}
    for doc, data_id in data_ids.items():
        for edge in await graph.get_edges(str(data_id)):
            rel, other = other_end(edge, str(data_id))
            if rel != "is_part_of" or other.get("type") != "DocumentChunk":
                continue
            chunk_id = str(other["id"])
            node = await graph.get_node(chunk_id)
            entities = {}
            for inner in await graph.get_edges(chunk_id):
                rel2, ent = other_end(inner, chunk_id)
                if rel2 == "contains" and ent.get("type") == "Entity":
                    entities[str(ent["id"])] = ent.get("name", "")
            chunks[chunk_id] = dict(
                doc=doc,
                index=node.get("chunk_index"),
                text=norm(node.get("text") or ""),
                entities=entities,
            )
    return chunks


def support(node_id, terms, chunks):
    """The chunks that contain the node, split by whether their text holds
    one of the terms as a whole word."""
    supported, unsupported = [], []
    for chunk_id, chunk in chunks.items():
        if node_id in chunk["entities"]:
            hit = any(whole_word(t, chunk["text"]) for t in terms)
            (supported if hit else unsupported).append(chunk_id)
    return supported, unsupported


def lexical_match(candidate_name, closure):
    if candidate_name in closure:
        return True
    m = PAREN.match(candidate_name)
    return bool(m) and (m.group(1) in closure or m.group(2) in closure)


async def align(graph, vector, described, chunks):
    from cognee.modules.engine.models import Entity

    group = groups_of(described)
    listed_by = {}
    for doc, (names, _) in described.items():
        for n in names:
            listed_by.setdefault(n, set()).add(doc)
    all_listed = set(group)
    records = []
    for name in sorted(group):
        closure = group[name]
        docs = set().union(*(listed_by.get(n, set()) for n in closure))
        exact_id = str(Entity.id_for(name))
        record = dict(name=name, group=sorted(closure), exact=None, lexical=[])
        if await graph.get_node(exact_id) is not None:
            ok, bad = support(exact_id, closure, chunks)
            record["exact"] = dict(id=exact_id, supported=len(ok), unsupported=len(bad))
        seen = {}
        for chunk in chunks.values():
            if chunk["doc"] in docs:
                seen.update(chunk["entities"])
        # A group member's own exact node aligns under that member's name, so
        # only a node that sits at no member's exact ID can be a lexical match.
        member_ids = {str(Entity.id_for(n)) for n in closure}
        record["member_ids"] = sorted(member_ids)
        for node_id, cand in sorted(seen.items(), key=lambda kv: kv[1]):
            if node_id in member_ids or not lexical_match(cand, closure):
                continue
            m = PAREN.match(cand)
            parts = {cand, m.group(1), m.group(2)} if m else {cand}
            if any(x in all_listed and x not in closure for x in parts):
                continue
            terms = set(closure) | ({m.group(1), m.group(2)} if m else {cand})
            ok, bad = support(node_id, terms, chunks)
            record["lexical"].append(
                dict(id=node_id, name=cand, supported=len(ok), unsupported=len(bad))
            )
        if record["exact"] and record["exact"]["supported"]:
            record["outcome"] = "exact"
        elif any(c["supported"] for c in record["lexical"]):
            record["outcome"] = "lexical"
        elif record["exact"] or record["lexical"]:
            record["outcome"] = "unsupported"
        else:
            record["outcome"] = "unaligned"
        record["vector"] = await vector_ranks(graph, vector, name, closure, record)
        records.append(record)
    return records


async def vector_ranks(graph, vector, name, closure, record):
    """Where the right nodes rank among `Entity_name` hits for the name, and
    the best hit that is none of them."""
    right = {c["id"] for c in record["lexical"]}
    ranked = []
    for hit in await vector.search("Entity_name", query_text=name, limit=VECTOR_DEPTH):
        node = await graph.get_node(str(hit.id))
        if node is not None and node.get("type") == "Entity":
            ranked.append((str(hit.id), node.get("name", ""), round(float(hit.score), 4)))
    exact_id = record["exact"]["id"] if record["exact"] else None

    members = set(record["member_ids"])

    def kind(node_id, node_name):
        if node_id == exact_id:
            return "exact"
        if node_id in right:
            return "lexical"
        if node_id in members or node_name in closure:
            return "group"
        return "wrong"

    out = dict(depth=len(ranked), top=None, exact=None, right=[], best_group=None, best_wrong=None)
    for rank, (node_id, node_name, distance) in enumerate(ranked, start=1):
        k = kind(node_id, node_name)
        entry = dict(rank=rank, name=node_name, distance=distance)
        if out["top"] is None:
            out["top"] = dict(entry, kind=k)
        if k == "exact":
            out["exact"] = entry
        elif k == "lexical":
            out["right"].append(entry)
        elif k == "group" and out["best_group"] is None:
            out["best_group"] = entry
        elif k == "wrong" and out["best_wrong"] is None:
            out["best_wrong"] = entry
    return out


def planted(records, chunks):
    """Links from a chunk to an exact node of a described name whose text holds
    no name of its group. A whole-word test, so a paraphrase such as "the
    reconstruction" counts as planted too."""
    links = []
    for r in records:
        if not r["exact"]:
            continue
        _, bad = support(r["exact"]["id"], set(r["group"]), chunks)
        links += [
            dict(name=r["name"], doc=chunks[c]["doc"], chunk_index=chunks[c]["index"])
            for c in bad
        ]
    return links


async def graph_stats(graph):
    nodes, edges = await graph.get_graph_data()
    entities = [p for _, p in nodes if p.get("type") == "Entity"]
    return dict(nodes=len(nodes), edges=len(edges), entities=len(entities))


async def view_timing(records):
    """Shape 1v's in-memory route without the ownership filter: project the
    whole graph, copy each admitted member's own non-structural edges onto the
    other members of its group once, and clone the result as each query would."""
    from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge
    from cognee.modules.retrieval.utils.brute_force_triplet_search import get_memory_fragment

    t0 = time.perf_counter()
    fragment = await get_memory_fragment()
    t1 = time.perf_counter()
    projected = len(fragment.edges)
    members = {}
    for r in records:
        if r["outcome"] == "exact":
            ids = [r["exact"]["id"]]
        elif r["outcome"] == "lexical":
            ids = [c["id"] for c in r["lexical"] if c["supported"]]
        else:
            ids = []
        for node_id in ids:
            members.setdefault(frozenset(r["group"]), set()).add(node_id)
    originals = {
        node_id: [
            e for e in fragment.nodes[node_id].skeleton_edges
            if e.attributes.get("relationship_name") not in STRUCTURAL
        ]
        for ids in members.values()
        for node_id in ids
        if node_id in fragment.nodes
    }
    added = 0
    for ids in members.values():
        present = [i for i in ids if i in originals]
        for source in present:
            for edge in originals[source]:
                far = edge.node2 if edge.node1.id == source else edge.node1
                for member in present:
                    if member == source or far.id == member:
                        continue
                    fragment.add_edge(
                        Edge(fragment.nodes[member], far, attributes=dict(edge.attributes))
                    )
                    added += 1
    t2 = time.perf_counter()
    copy.deepcopy(fragment)
    t3 = time.perf_counter()
    return dict(
        nodes=len(fragment.nodes),
        projected_edges=projected,
        overlay_edges=added,
        project_s=round(t1 - t0, 4),
        overlay_s=round(t2 - t1, 4),
        clone_s=round(t3 - t2, 4),
    )


async def measure(data_ids):
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.infrastructure.databases.vector import get_vector_engine

    _, rows = await dataset_and_rows()
    by_id = {r.id: r for r in rows}
    described = {d: describe(await stored_text(by_id[i])) for d, i in data_ids.items()}
    graph = await get_graph_engine()
    vector = get_vector_engine()
    chunks = await read_corpus(graph, data_ids)
    records = await align(graph, vector, described, chunks)
    return dict(
        described={d: dict(names=len(n), variants=len(v)) for d, (n, v) in described.items()},
        chunks={d: sum(c["doc"] == d for c in chunks.values()) for d in data_ids},
        graph=await graph_stats(graph),
        alignment=records,
        planted=planted(records, chunks),
        view=await view_timing(records),
    ), (graph, vector)


async def corpus_ids():
    _, rows = await dataset_and_rows()
    return {d: next(r.id for r in rows if r.name == p.stem) for d, p in DOCS.items()}


async def run(root, hint: bool, checks: bool) -> dict:
    import cognee

    calls = Calls()
    calls.install()
    result = dict(hint=hint, cognifies={})
    for doc, path in DOCS.items():
        await cognee.add(str(path), dataset_name=environment.DATASET_NAME)
        _, rows = await dataset_and_rows()
        row = next(r for r in rows if r.name == path.stem)
        prompt = hint_prompt(describe(await stored_text(row))[0]) if hint else None
        mark = calls.mark()
        t0 = time.perf_counter()
        await cognee.cognify(datasets=[environment.DATASET_NAME], custom_prompt=prompt)
        result["cognifies"][doc] = dict(
            calls=calls.since(mark), seconds=round(time.perf_counter() - t0, 1)
        )
    data_ids = await corpus_ids()
    measured, engines = await measure(data_ids)
    try:
        result |= measured
        result["llm_calls_total"] = len(calls.log)
        write(root, result)
        if checks:
            result["checks"] = await behaviour_checks(cognee, calls, data_ids)
            result["llm_calls_total"] = len(calls.log)
    finally:
        await environment.close_stores(*engines)
    return result


async def behaviour_checks(cognee, calls, data_ids):
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee_lab.identity.registered import stamped

    out = {}
    dataset_id, rows = await dataset_and_rows()
    before = {r.id: r for r in rows}
    mark = calls.mark()
    update = await cognee.update(
        data_id=data_ids["doc01"],
        data=str(DOC01_V2),
        dataset_id=dataset_id,
        custom_prompt=hint_prompt(describe(DOC01_V2.read_text())[0]),
    )
    _, rows = await dataset_and_rows()
    after = {r.id: r for r in rows}
    out["hinted_update"] = dict(
        result=json.loads(json.dumps(update, default=str)),
        data_id_kept=data_ids["doc01"] in after,
        hash_changed=after[data_ids["doc01"]].raw_content_hash
        != before[data_ids["doc01"]].raw_content_hash,
        calls=calls.since(mark),
    )

    graph = await get_graph_engine()
    doc01, doc02 = str(data_ids["doc01"]), str(data_ids["doc02"])
    await cognee.forget(data_id=data_ids["doc02"], dataset_id=dataset_id, memory_only=True)
    _, rows = await dataset_and_rows()
    out["memory_only_forget"] = dict(
        data_row_kept=any(r.id == data_ids["doc02"] for r in rows),
        processed_after=await stamped(data_ids["doc02"], dataset_id),
        doc02_node_after_forget=await graph.get_node(doc02) is not None,
        doc01_node_after_forget=await graph.get_node(doc01) is not None,
    )
    mark = calls.mark()
    await cognee.cognify(datasets=[environment.DATASET_NAME])
    out["memory_only_forget"] |= dict(
        recognify_calls=calls.since(mark),
        doc02_node_after_recognify=await graph.get_node(doc02) is not None,
        processed_after_recognify=await stamped(data_ids["doc02"], dataset_id),
    )

    await cognee.prune.prune_system()
    _, rows = await dataset_and_rows()
    graph = await get_graph_engine()
    nodes, _ = await graph.get_graph_data()
    out["default_prune"] = dict(
        data_rows=len(rows),
        processed_after=[await stamped(r.id, dataset_id) for r in rows],
        graph_nodes_after_prune=len(nodes),
    )
    mark = calls.mark()
    await cognee.cognify(datasets=[environment.DATASET_NAME])
    nodes, _ = await graph.get_graph_data()
    out["default_prune"] |= dict(
        recognify_calls=calls.since(mark), graph_nodes_after_recognify=len(nodes)
    )
    return out


async def analyze(root) -> dict:
    result = json.loads((root / "result.json").read_text())
    if "checks" in result:
        raise SystemExit("The checks pruned this root's graph after its measurement; analyze would overwrite it")
    measured, engines = await measure(await corpus_ids())
    await environment.close_stores(*engines)
    return {k: v for k, v in result.items() if k in ("hint", "cognifies", "llm_calls_total", "checks")} | measured


async def dry_run() -> dict:
    import cognee

    for path in DOCS.values():
        await cognee.add(str(path), dataset_name=environment.DATASET_NAME)
    return await cognee.cognify(datasets=[environment.DATASET_NAME], dry_run=True)


def write(root, result):
    (root / "result.json").write_text(json.dumps(result, indent=2, default=str))


def report(base: Path) -> str:
    runs = []
    for path in sorted(base.glob("*/result.json")):
        r = json.loads(path.read_text())
        if isinstance(r, dict) and "planted" in r:
            runs.append((path.parent.name, r))
    out = [
        "| Run | Hint | exact | lexical | unsupported | unaligned | Planted links (names) | Entities | LLM calls (hinted) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, r in runs:
        outcomes = Counter(a["outcome"] for a in r["alignment"])
        extraction = [c["calls"] for c in r["cognifies"].values()]
        out.append(
            f"| {name} | {'yes' if r['hint'] else 'no'} | {outcomes['exact']} | {outcomes['lexical']} | "
            f"{outcomes['unsupported']} | {outcomes['unaligned']} | {len(r['planted'])} "
            f"({len({p['name'] for p in r['planted']})}) | {r['graph']['entities']} | "
            f"{sum(c['total'] for c in extraction)} ({sum(c['hinted'] for c in extraction)}) |"
        )
    out += [
        "",
        "Names not aligned `exact`, by run.",
        "",
        "| Run | Name | Outcome | Lexical node | Its vector rank and distance | Top hit (kind) | Best wrong hit | Best in-group hit |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, r in runs:
        for a in r["alignment"]:
            if a["outcome"] == "exact":
                continue
            lex = ", ".join(f"{c['name']} ({'supported' if c['supported'] else 'unsupported'})" for c in a["lexical"]) or "-"
            v = a["vector"]
            right = ", ".join(f"{x['rank']} at {x['distance']}" for x in v["right"]) or (
                "-" if not a["lexical"] else f"not in top {v['depth']}"
            )
            fmt = lambda e: f"{e['name']}, rank {e['rank']} at {e['distance']}" if e else "-"
            top = f"{fmt(v['top'])} ({v['top']['kind']})" if v.get("top") else "-"
            out.append(
                f"| {name} | {a['name']} | {a['outcome']} | {lex} | {right} | {top} | "
                f"{fmt(v['best_wrong'])} | {fmt(v['best_group'])} |"
            )
    out += [
        "",
        "Planted links: a chunk linked to an exact node of a described name whose text holds no name of its group.",
        "",
        "| Run | Name | Document | Chunk index |",
        "|---|---|---|---|",
    ]
    for name, r in runs:
        for p in r["planted"]:
            out.append(f"| {name} | {p['name']} | {p['doc']} | {p['chunk_index']} |")
    out += [
        "",
        "| Run | Nodes | Projected edges | Overlay edges | Project (s) | Overlay (s) | Clone (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, r in runs:
        if "checks" in r:
            continue
        v = r["view"]
        out.append(
            f"| {name} | {v['nodes']} | {v['projected_edges']} | {v['overlay_edges']} | "
            f"{v['project_s']} | {v['overlay_s']} | {v['clone_s']} |"
        )
    for name, r in runs:
        if "checks" in r:
            out += ["", f"Behaviour checks in {name}.", "", "```", json.dumps(r["checks"], indent=1, default=str), "```"]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run")
    one.add_argument("root", type=Path)
    one.add_argument("--hint", action=argparse.BooleanOptionalAction, required=True)
    one.add_argument("--checks", action="store_true")
    for command in ("analyze", "dry-run"):
        sub.add_parser(command).add_argument("root", type=Path)
    sub.add_parser("report").add_argument("base", type=Path)
    args = parser.parse_args()
    if args.command == "report":
        print(report(args.base))
        return

    root = args.root.resolve()
    outputs = REPO / "outputs"
    if outputs not in root.parents or any(p.name.startswith("stage6_") for p in (root, *root.parents)):
        raise SystemExit("ROOT must be under outputs/ and outside every reviewed stage6_* root")
    if args.command == "analyze":
        with environment.fixture_environment(root):
            result = asyncio.run(analyze(root))
    else:
        llm = operator_llm() if args.command == "run" else None
        make_root(root)
        with environment.fixture_environment(root):
            if llm:
                real_llm_environment(llm)
            if args.command == "run":
                result = asyncio.run(run(root, args.hint, args.checks))
            else:
                result = asyncio.run(dry_run())
    write(root, result)
    if isinstance(result, dict):
        result = {k: v for k, v in result.items() if k not in ("alignment", "planted")}
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
