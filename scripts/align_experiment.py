"""The alignment experiment of docs/minimal_identity_framework.md, open question 7.

Cognifies DOC01 and DOC02 in a fresh isolated root, with or without the
spelling hint, then measures how each described name aligns with Cognee's
Entities, how long Shape 1v's in-memory view takes to build, and, with
--checks, five Cognee behaviours the design reads from source.

    uv run python scripts/align_experiment.py run ROOT --hint|--no-hint [--checks]
    uv run python scripts/align_experiment.py dry-run ROOT
    uv run python scripts/align_experiment.py report BASE

`run` uses the real LLM and embedding settings that .env names, read into
this process only. Every value stays in memory and none is written to the root.
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
CALL_CAP = 160
STRUCTURAL = {"contains", "is_a", "is_part_of", "belongs_to_set", "made_from"}


def make_root(root: Path) -> None:
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
        by_model = {}
        for call in part:
            by_model[call["model"]] = by_model.get(call["model"], 0) + 1
        return dict(
            total=len(part),
            by_model=by_model,
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


async def dataset_and_rows(name):
    from cognee.modules.data.methods import get_dataset_data, get_datasets_by_name
    from cognee.modules.users.methods import get_default_user

    user = await get_default_user()
    datasets = await get_datasets_by_name(name, user.id)
    dataset = datasets[0]
    return dataset.id, await get_dataset_data(dataset.id)


async def stored_text(row) -> str:
    from cognee.infrastructure.files.utils.open_data_file import open_data_file

    async with open_data_file(row.raw_data_location, mode="r", encoding="utf-8") as f:
        return f.read()


def processed(row, dataset_id) -> bool:
    from cognee.modules.pipelines.models.DataItemStatus import is_data_item_completed

    status = (row.pipeline_status or {}).get("cognify_pipeline") or {}
    return is_data_item_completed(status.get(str(dataset_id)))


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


async def chunk_index(graph, data_ids):
    chunks = {}
    for doc, data_id in data_ids.items():
        for a, rel, b in await graph.get_edges(str(data_id)):
            other = b if str(a.get("id")) == str(data_id) else a
            if rel == "is_part_of" and other.get("type") == "DocumentChunk":
                node = await graph.get_node(str(other["id"]))
                chunks[str(other["id"])] = dict(doc=doc, text=norm(node.get("text") or ""))
    return chunks


async def support(graph, node_id, terms, chunks):
    supported, unsupported = [], []
    for a, rel, b in await graph.get_edges(node_id):
        if rel != "contains":
            continue
        other = b if str(a.get("id")) == node_id else a
        chunk = chunks.get(str(other.get("id")))
        if chunk is None:
            continue
        hit = any(whole_word(t, chunk["text"]) for t in terms)
        (supported if hit else unsupported).append(str(other["id"]))
    return supported, unsupported


async def align(graph, vector, described, chunks):
    from cognee.modules.engine.models import Entity

    group = groups_of(described)
    listed_by = {}
    for doc, (names, _) in described.items():
        for n in names:
            listed_by.setdefault(n, []).append(doc)
    all_listed = set(group)
    records = []
    for name in sorted(group):
        closure = group[name]
        exact_id = str(Entity.id_for(name))
        exact = await graph.get_node(exact_id)
        record = dict(name=name, group=sorted(closure), listed_by=listed_by.get(name, []))
        if exact is not None:
            ok, bad = await support(graph, exact_id, {name, *closure}, chunks)
            record["exact"] = dict(supported_chunks=len(ok), unsupported_chunks=len(bad))
        else:
            record["exact"] = None
        hits = []
        for hit in await vector.search("Entity_name", query_text=name, limit=10):
            node = await graph.get_node(str(hit.id))
            if node is None or node.get("type") != "Entity":
                continue
            hit_name = node.get("name", "")
            ok, bad = await support(graph, str(hit.id), {hit_name}, chunks)
            hits.append(
                dict(
                    name=hit_name,
                    distance=round(float(hit.score), 4),
                    is_exact=str(hit.id) == exact_id,
                    in_closure=hit_name in closure,
                    excluded=hit_name in all_listed and hit_name not in closure,
                    supported_chunks=len(ok),
                    unsupported_chunks=len(bad),
                )
            )
        record["similar_hits"] = hits
        records.append(record)
    return records


async def graph_stats(graph, described):
    nodes, edges = await graph.get_graph_data()
    entities = [p for _, p in nodes if p.get("type") == "Entity"]
    listed = {n for names, _ in described.values() for n in names}
    entity_names = {p.get("name") for p in entities}
    return dict(
        nodes=len(nodes),
        edges=len(edges),
        entities=len(entities),
        entities_listed_by_describe=len(entity_names & listed),
        entities_not_listed=len(entity_names - listed),
        entity_names=sorted(n for n in entity_names if n),
    )


async def view_timing(described, admitted):
    """Shape 1v's in-memory route: project the whole graph, add the overlay,
    clone it once as each query would."""
    from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge
    from cognee.modules.retrieval.utils.brute_force_triplet_search import get_memory_fragment

    t0 = time.perf_counter()
    fragment = await get_memory_fragment()
    t1 = time.perf_counter()
    added = 0
    for members in {frozenset(g) for g in groups_of(described).values() if len(g) > 1}:
        nodes = [fragment.nodes[i] for n in members if (i := admitted.get(n)) in fragment.nodes]
        for source in nodes:
            for edge in list(source.skeleton_edges):
                if edge.attributes.get("relationship_name") in STRUCTURAL:
                    continue
                far = edge.node2 if edge.node1 is source else edge.node1
                for member in nodes:
                    if member is source:
                        continue
                    fragment.add_edge(Edge(member, far, attributes=dict(edge.attributes)))
                    added += 1
    t2 = time.perf_counter()
    copy.deepcopy(fragment)
    t3 = time.perf_counter()
    return dict(
        nodes=len(fragment.nodes),
        edges=len(fragment.edges),
        overlay_edges=added,
        project_s=round(t1 - t0, 3),
        overlay_s=round(t2 - t1, 4),
        clone_s=round(t3 - t2, 3),
    )


async def run(root: Path, hint: bool, checks: bool) -> dict:
    import cognee
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.infrastructure.databases.vector import get_vector_engine
    from cognee.modules.engine.models import Entity

    calls = Calls()
    calls.install()
    result = dict(hint=hint, cognifies={}, described={})
    name = environment.DATASET_NAME
    data_ids, described = {}, {}
    for doc, path in DOCS.items():
        await cognee.add(str(path), dataset_name=name)
        dataset_id, rows = await dataset_and_rows(name)
        row = next(r for r in rows if r.name == path.stem)
        data_ids[doc] = row.id
        described[doc] = describe(await stored_text(row))
        prompt = hint_prompt(described[doc][0]) if hint else None
        mark = calls.mark()
        t0 = time.perf_counter()
        await cognee.cognify(datasets=[name], custom_prompt=prompt)
        result["cognifies"][doc] = dict(
            calls=calls.since(mark), seconds=round(time.perf_counter() - t0, 1)
        )
    result["described"] = {
        d: dict(names=len(n), variants=len(v)) for d, (n, v) in described.items()
    }
    graph = await get_graph_engine()
    vector = get_vector_engine()
    chunks = await chunk_index(graph, data_ids)
    result["chunks"] = {d: sum(c["doc"] == d for c in chunks.values()) for d in DOCS}
    result["graph"] = await graph_stats(graph, described)
    records = await align(graph, vector, described, chunks)
    result["alignment"] = records
    admitted = {
        r["name"]: str(Entity.id_for(r["name"]))
        for r in records
        if r["exact"] and r["exact"]["supported_chunks"]
    }
    result["view"] = await view_timing(described, admitted)
    if checks:
        result["checks"] = await behaviour_checks(cognee, calls, data_ids, described)
    result["llm_calls_total"] = len(calls.log)
    return result


async def behaviour_checks(cognee, calls, data_ids, described):
    from cognee.infrastructure.databases.graph import get_graph_engine

    name = environment.DATASET_NAME
    out = {}
    graph = await get_graph_engine()

    dataset_id, rows = await dataset_and_rows(name)
    before = {r.id: r for r in rows}
    v2_text = DOC01_V2.read_text()
    v2_names, _ = describe(v2_text)
    mark = calls.mark()
    update = await cognee.update(
        data_id=data_ids["doc01"],
        data=str(DOC01_V2),
        dataset_id=dataset_id,
        custom_prompt=hint_prompt(v2_names),
    )
    _, rows = await dataset_and_rows(name)
    after = {r.id: r for r in rows}
    out["hinted_update"] = dict(
        result=json.loads(json.dumps(update, default=str)),
        data_id_kept=data_ids["doc01"] in after,
        hash_changed=after[data_ids["doc01"]].raw_content_hash
        != before[data_ids["doc01"]].raw_content_hash,
        calls=calls.since(mark),
    )

    await cognee.forget(data_id=data_ids["doc02"], dataset_id=dataset_id, memory_only=True)
    _, rows = await dataset_and_rows(name)
    row = next((r for r in rows if r.id == data_ids["doc02"]), None)
    out["memory_only_forget"] = dict(
        data_row_kept=row is not None,
        processed_after=processed(row, dataset_id) if row else None,
        document_node_present=await graph.get_node(str(data_ids["doc02"])) is not None,
    )
    mark = calls.mark()
    await cognee.cognify(datasets=[name])
    out["memory_only_forget"]["recognify_calls"] = calls.since(mark)

    await cognee.prune.prune_system()
    _, rows = await dataset_and_rows(name)
    graph = await get_graph_engine()
    nodes, _ = await graph.get_graph_data()
    out["default_prune"] = dict(
        data_rows=len(rows),
        processed_after=[processed(r, dataset_id) for r in rows],
        graph_nodes_after=len(nodes),
    )
    mark = calls.mark()
    await cognee.cognify(datasets=[name])
    out["default_prune"]["recognify_calls"] = calls.since(mark)
    return out


def best_similar(record):
    """The best hit the similar pass could admit: not the exact node, not a
    name another group lists, and supported by a chunk's text."""
    hits = [
        h for h in record["similar_hits"]
        if not h["is_exact"] and not h["excluded"] and h["supported_chunks"]
    ]
    return min(hits, key=lambda h: h["distance"], default=None)


def report(base: Path) -> str:
    rows, similar, lines = [], [], []
    for result_file in sorted(base.glob("*/result.json")):
        run_name = result_file.parent.name
        r = json.loads(result_file.read_text())
        if not isinstance(r, dict) or "alignment" not in r:
            continue
        a = r["alignment"]
        exact = [x for x in a if x["exact"] and x["exact"]["supported_chunks"]]
        unsupported = [x for x in a if x["exact"] and not x["exact"]["supported_chunks"]]
        planted = sum(x["exact"]["unsupported_chunks"] for x in a if x["exact"])
        extraction = [c["calls"] for c in r["cognifies"].values()]
        rows.append(
            f"| {run_name} | {len(a)} | {len(exact)} | {len(unsupported)} | "
            f"{len(a) - len(exact) - len(unsupported)} | {planted} | "
            f"{r['graph']['entities']} | {sum(c['total'] for c in extraction)} | "
            f"{sum(c['hinted'] for c in extraction)} | {r['view']['project_s']} | "
            f"{r['view']['overlay_edges']} |"
        )
        for x in a:
            if x in exact:
                continue
            best = best_similar(x)
            closure_hits = [h["distance"] for h in x["similar_hits"] if h["in_closure"] and not h["is_exact"]]
            similar.append(
                f"| {run_name} | {x['name']} | "
                f"{best['name'] if best else '-'} | {best['distance'] if best else '-'} | "
                f"{min(closure_hits) if closure_hits else '-'} |"
            )
    lines += [
        "| run | names | exact | exact unsupported | no exact | contains edges without text | entities | LLM calls | hinted calls | view project s | overlay edges |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "Names with no supported exact node, and the best hit the similar pass could admit.",
        "",
        "| run | name | best admissible hit | distance | nearest hit in its own group |",
        "|---|---|---|---|---|",
        *similar,
    ]
    return "\n".join(lines)


async def dry_run(root: Path) -> dict:
    import cognee

    for path in DOCS.values():
        await cognee.add(str(path), dataset_name=environment.DATASET_NAME)
    estimate = await cognee.cognify(datasets=[environment.DATASET_NAME], dry_run=True)
    return json.loads(json.dumps(estimate, default=str))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run")
    one.add_argument("root", type=Path)
    one.add_argument("--hint", action=argparse.BooleanOptionalAction, required=True)
    one.add_argument("--checks", action="store_true")
    dry = sub.add_parser("dry-run")
    dry.add_argument("root", type=Path)
    rep = sub.add_parser("report")
    rep.add_argument("base", type=Path)
    args = parser.parse_args()
    if args.command == "report":
        print(report(args.base))
        return

    root = args.root.resolve()
    if REPO / "outputs" not in root.parents:
        raise SystemExit("ROOT must be a new directory under outputs/")
    llm = operator_llm() if args.command == "run" else None
    make_root(root)
    with environment.fixture_environment(root):
        if llm:
            real_llm_environment(llm)
        if args.command == "run":
            result = asyncio.run(run(root, args.hint, args.checks))
        else:
            result = asyncio.run(dry_run(root))
    (root / "result.json").write_text(json.dumps(result, indent=2, default=str))
    if isinstance(result, dict):
        result = {k: v for k, v in result.items() if k != "alignment"}
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
