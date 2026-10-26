"""Step 5 S1 commit-0 probes E1, E2 and E5 (.audit/step5-s1-spec.md).

Each run makes a new directory outputs/s1_probes/<UTC stamp>/, builds loopback
fixture roots in it through the identity CLI, then opens each root in a child
process that enters fixture_environment before importing cognee. Every LLM call
is refused unless a probe installs a stub, and each call is recorded.

    uv run python support/s1_probes.py
    uv run python support/s1_probes.py --probes e1
    uv run python support/s1_probes.py --stages text_chunks,replace_published

E1  IDENTITY added to cognee's SearchType: lookups, pickle, payloads, history,
    cognee.search versus the lab retrieve, FEELING_LUCKY, recall.
E2  What CHUNKS, GRAPH_COMPLETION and TRIPLET_COMPLETION (only_context) serve
    on a chain root after a cosmetic glossary edit and after a failed insert.
E5  A second dataset by plain cognee.add, then cognify with a stub extractor:
    the dataset kwarg the retriever receives and foreign Entity_name seeds.

The probe retriever is not the S1 retriever; it only calls retrieve.
"""

import argparse
import asyncio
import copy
import json
import os
import pickle
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "cognee_lab.identity"]
FAILED_STAGES = ("text_chunks", "replace_published")
QUERIES = (
    "What does HC limit?",
    "What does Helios controller limit?",
    "What does the controller limit?",
)
FOREIGN_DATASET = "s1_probe_foreign"
FOREIGN_TEXT = "Aurora controller limits vibrations in the cryostat."
FOREIGN_QUERY = "What does Aurora controller limit?"
STRUCTURAL = {
    "resolves_to",
    "has_identity_mention",
    "contains",
    "is_a",
    "is_part_of",
    "belongs_to_set",
}


def lab_stores() -> list[Path]:
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    roots = {REPO, Path(common).parent}
    return [
        r / name for r in sorted(roots) for name in (".cognee_system", ".cognee_data")
    ]


def fingerprint() -> dict:
    found = {}
    for store in lab_stores():
        files = [p for p in store.rglob("*") if p.is_file()]
        found[str(store)] = dict(
            files=len(files),
            newest_mtime_ns=max((p.stat().st_mtime_ns for p in files), default=None),
        )
    return found


def extract_json(stdout: str):
    start = 0 if stdout.startswith("{") else stdout.find("\n{") + 1
    if start == 0 and not stdout.startswith("{"):
        return None
    try:
        return json.loads(stdout[start:])
    except ValueError:
        return None


def run_cli(base: Path, root: str, label: str, *args: str) -> dict:
    command = [*CLI, *args, "--root", str(base / root)]
    if args[0].endswith("fixture"):
        command += ["--embedding", "loopback"]
    done = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    (base / f"{root}.{label}.stdout").write_text(done.stdout)
    (base / f"{root}.{label}.stderr").write_text(done.stderr)
    print(f"cli {root} {label}: exit {done.returncode}", flush=True)
    return dict(
        command=" ".join(command[2:]),
        exit=done.returncode,
        json=extract_json(done.stdout),
    )


def run_inner(base: Path, root: str, probe: str) -> dict:
    out = base / f"{root}.{probe}.json"
    done = subprocess.run(
        [sys.executable, __file__, "--inner", probe, "--root", str(base / root)]
        + ["--out", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    (base / f"{root}.{probe}.stderr").write_text(done.stderr)
    print(f"probe {probe} on {root}: exit {done.returncode}", flush=True)
    if done.returncode != 0 or not out.exists():
        return dict(error=f"exit {done.returncode}", stderr_tail=done.stderr[-2000:])
    return json.loads(out.read_text())


def orchestrate(args) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = REPO / "outputs" / "s1_probes" / stamp
    base.mkdir(parents=True, exist_ok=False)
    before = fingerprint()
    probes = set(args.probes.split(","))
    summary = dict(base=str(base.relative_to(REPO)), steps={}, probes={})
    steps = summary["steps"]
    if probes & {"e1", "e2"}:
        steps["e1_chain"] = [
            run_cli(base, "e1_chain", "fixture", "glossary-fixture", "--chain")
        ]
    if "e1" in probes:
        summary["probes"]["e1"] = run_inner(base, "e1_chain", "e1")
    if "e2" in probes:
        summary["probes"]["e2_healthy"] = run_inner(base, "e1_chain", "e2")
        steps["e2_cosmetic"] = [
            run_cli(base, "e2_cosmetic", "fixture", "glossary-fixture", "--chain"),
            run_cli(
                base,
                "e2_cosmetic",
                "edit",
                "edit-glossary",
                "--source",
                "glossary",
                "--case",
                "cosmetic",
                "--expected-revision",
                "1",
            ),
        ]
        summary["probes"]["e2_cosmetic"] = run_inner(base, "e2_cosmetic", "e2")
        for stage in args.stages.split(","):
            root = f"e2_failed_{stage}"
            steps[root] = [
                run_cli(base, root, "fixture", "glossary-fixture", "--chain"),
                run_cli(
                    base,
                    root,
                    "fail",
                    "edit-glossary",
                    "--source",
                    "glossary",
                    "--case",
                    "insert",
                    "--expected-revision",
                    "1",
                    "--fault-stage",
                    stage,
                ),
            ]
            summary["probes"][root] = run_inner(base, root, "e2")
    if "e5" in probes:
        steps["e5_two_datasets"] = [
            run_cli(base, "e5_two_datasets", "fixture", "fixture")
        ]
        summary["probes"]["e5"] = run_inner(base, "e5_two_datasets", "e5")
    for root_steps in steps.values():
        for step in root_steps:
            step["json_keys"] = sorted(step.pop("json") or {})
    summary["lab_store_unchanged"] = fingerprint() == before
    (base / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    digest = dict(
        base=summary["base"],
        lab_store_unchanged=summary["lab_store_unchanged"],
        steps={
            root: [[s["command"], s["exit"]] for s in root_steps]
            for root, root_steps in steps.items()
        },
        probe_errors={k: v.get("error") for k, v in summary["probes"].items()},
    )
    print(json.dumps(digest, indent=2))


def install_llm(calls: list, answers: dict):
    """Replace LLMGateway.acreate_structured_output. `answers` maps a
    response-model name to a factory; any other call raises."""
    from cognee.infrastructure.llm.LLMGateway import LLMGateway

    async def fake(text_input, system_prompt, response_model, **kwargs):
        name = getattr(response_model, "__name__", str(response_model))
        answer = answers.get(name)
        calls.append(dict(model=name, answered=answer is not None))
        if answer is None:
            raise RuntimeError(f"s1 probe: LLM call refused ({name})")
        return answer(response_model)

    LLMGateway.acreate_structured_output = staticmethod(fake)


def add_member(enum_cls, name: str):
    """Add `name` to a str Enum through its stdlib internals, idempotently."""
    if name in enum_cls._member_map_:
        return enum_cls._member_map_[name]
    member = str.__new__(enum_cls, name)
    member._name_ = name
    member._value_ = name
    member._sort_order_ = len(enum_cls._member_names_)
    member.__objclass__ = enum_cls
    type.__setattr__(enum_cls, name, member)
    enum_cls._member_map_[name] = member
    enum_cls._value2member_map_[name] = member
    enum_cls._member_names_.append(name)
    return member


def plain(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def attempt(fn):
    try:
        return dict(ok=True, value=fn())
    except Exception as exc:
        return dict(ok=False, error=type(exc).__name__, message=str(exc)[:400])


async def attempt_async(coro):
    try:
        return dict(ok=True, value=await coro)
    except Exception as exc:
        return dict(ok=False, error=type(exc).__name__, message=str(exc)[:400])


def make_retriever(calls: list):
    from cognee.modules.retrieval.base_retriever import BaseRetriever
    from cognee_lab.identity.publish import Publisher
    from cognee_lab.identity.retrieve import retrieve

    class ProbeIdentityRetriever(BaseRetriever):
        supports_session_turn_preparation = False
        supports_prompt_preview = False

        def __init__(self, **kwargs):
            dataset = kwargs.get("dataset")
            calls.append(
                dict(
                    kwargs=sorted(kwargs),
                    dataset=(
                        None
                        if dataset is None
                        else dict(id=str(dataset.id), name=dataset.name)
                    ),
                    top_k=kwargs.get("top_k"),
                    only_context=kwargs.get("only_context"),
                    retriever_specific_config=kwargs.get("retriever_specific_config"),
                )
            )
            self.dataset = dataset
            self.session_id = kwargs.get("session_id")

        async def get_retrieved_objects(self, query, query_batch=None):
            if self.dataset is None:
                return dict(refused="dataset_required")
            publisher = await Publisher.configured()
            return plain(await retrieve(publisher, self.dataset.id, query))

        async def get_context_from_objects(
            self, query=None, query_batch=None, retrieved_objects=None
        ):
            return json.dumps(retrieved_objects, sort_keys=True)

        async def get_completion_from_context(
            self, query=None, query_batch=None, retrieved_objects=None, context=None
        ):
            return [retrieved_objects]

    return ProbeIdentityRetriever


async def lab_dataset():
    from cognee.modules.data.methods.get_datasets_by_name import (
        get_datasets_by_name,
    )
    from cognee.modules.users.methods import get_default_user
    from cognee_lab.identity.environment import DATASET_NAME

    user = await get_default_user()
    (dataset,) = await get_datasets_by_name(DATASET_NAME, user.id)
    return user, dataset


async def history() -> list:
    from cognee.infrastructure.databases.relational import get_relational_engine
    from cognee.modules.search.models.Query import Query
    from cognee.modules.search.models.Result import Result
    from sqlalchemy import select

    engine = get_relational_engine()
    async with engine.get_async_session() as session:
        found = await session.execute(
            select(Query.query_type, Query.text, Query.dataset_id, Result.value)
            .join(Result, Result.query_id == Query.id, isouter=True)
            .order_by(Query.created_at)
        )
        return [
            dict(
                query_type=t,
                text=q,
                dataset_id=str(d) if d else None,
                result_prefix=(v or "")[:120],
            )
            for t, q, d, v in found.all()
        ]


def fresh_process_lookup() -> dict:
    env = dict(os.environ)
    env["COGNEE_ENV_FILE"] = str(REPO / "src/cognee_lab/identity/fixture.env")
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cognee.modules.search.types import SearchType\n"
            "try:\n    SearchType['IDENTITY']; print('found')\n"
            "except KeyError as e:\n    print('KeyError', e)",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    return dict(exit=done.returncode, stdout=done.stdout.strip()[-200:])


def enum_selftest(SearchType, member, builtin_names) -> dict:
    from cognee.modules.retrieval.registered_community_retrievers import (
        registered_community_retrievers,
    )

    builtin = SearchType.CHUNKS
    return dict(
        getitem=attempt(lambda: SearchType["IDENTITY"] is member),
        call=attempt(lambda: SearchType("IDENTITY") is member),
        attribute=attempt(lambda: SearchType.IDENTITY is member),
        class_dict_holds_member=attempt(
            lambda: SearchType.__dict__.get("IDENTITY") is member
        ),
        in_members=attempt(lambda: "IDENTITY" in SearchType.__members__),
        in_iteration=attempt(lambda: member in list(SearchType)),
        contains=attempt(lambda: member in SearchType),
        contains_value=attempt(lambda: "IDENTITY" in SearchType),
        length=attempt(lambda: [len(builtin_names), len(SearchType)]),
        equals_str=attempt(lambda: member == "IDENTITY"),
        isinstance_str=attempt(lambda: isinstance(member, str)),
        name_value=attempt(lambda: [member.name, member.value]),
        str_format=attempt(lambda: [str(member), f"{member}", repr(member)]),
        hashable=attempt(lambda: {member: 1}[SearchType("IDENTITY")]),
        vars_like_builtin=attempt(
            lambda: dict(
                builtin=sorted(vars(builtin)),
                added=sorted(vars(member)),
            )
        ),
        pickle=attempt(lambda: pickle.loads(pickle.dumps(member)) is member),
        deepcopy=attempt(lambda: copy.deepcopy(member) is member),
        copy=attempt(lambda: copy.copy(member) is member),
        idempotent=attempt(
            lambda: add_member(SearchType, "IDENTITY") is member
            and SearchType._member_names_.count("IDENTITY") == 1
        ),
        registry_entry=attempt(
            lambda: registered_community_retrievers.get(member).__name__
        ),
        not_builtin=attempt(lambda: "IDENTITY" not in builtin_names),
        fresh_process_getitem=attempt(fresh_process_lookup),
    )


def payload_checks(SearchType, member, EarlyModel) -> dict:
    """`EarlyModel` and the search router were defined before the extension,
    as in a server that imported its routers first."""
    from pydantic import BaseModel
    from cognee.api.v1.search.routers.get_search_router import SearchPayloadDTO
    from cognee.modules.search.models.SearchResultPayload import (
        SearchResultPayload,
    )

    def build():
        return SearchResultPayload(
            result_object={"facts": []},
            context=json.dumps({"facts": []}),
            completion=[{"facts": []}],
            search_type=member,
        )

    def dumped_json():
        return build().model_dump_json()

    class LateModel(BaseModel):
        search_type: SearchType

    def router_dto(raw: str):
        return SearchPayloadDTO.model_validate_json(raw).search_type.value

    return dict(
        build=attempt(lambda: build().search_type is member),
        dump_python=attempt(lambda: build().model_dump()["search_type"] is member),
        dump_json_mode=attempt(lambda: build().model_dump(mode="json")["search_type"]),
        dump_json=attempt(lambda: json.loads(dumped_json())["search_type"]),
        dump_json_by_alias=attempt(
            lambda: json.loads(build().model_dump_json(by_alias=True))["searchType"]
        ),
        validate_json=attempt(
            lambda: SearchResultPayload.model_validate_json(dumped_json()).search_type
        ),
        validate_python_str=attempt(
            lambda: SearchResultPayload.model_validate(
                {"search_type": "IDENTITY"}
            ).search_type
            is member
        ),
        validate_python_member=attempt(
            lambda: SearchResultPayload.model_validate(
                {"search_type": member}
            ).search_type
            is member
        ),
        builtin_validate_json=attempt(
            lambda: SearchResultPayload.model_validate_json(
                '{"searchType": "CHUNKS"}'
            ).search_type.value
        ),
        model_defined_after_extension_validate_json=attempt(
            lambda: LateModel.model_validate_json(
                '{"search_type": "IDENTITY"}'
            ).search_type
            is member
        ),
        model_defined_before_extension_validate_json=attempt(
            lambda: EarlyModel.model_validate_json(
                '{"search_type": "IDENTITY"}'
            ).search_type
            is member
        ),
        model_defined_before_extension_validate_python=attempt(
            lambda: EarlyModel.model_validate({"search_type": "IDENTITY"}).search_type
            is member
        ),
        router_dto_identity=attempt(
            lambda: router_dto('{"search_type": "IDENTITY", "query": "q"}')
        ),
        router_dto_builtin=attempt(
            lambda: router_dto('{"search_type": "CHUNKS", "query": "q"}')
        ),
    )


async def probe_e1(root: Path) -> dict:
    import cognee
    from cognee.modules.retrieval.register_retriever import use_retriever
    from cognee.modules.search.types import SearchType
    from cognee.infrastructure.llm.prompts import read_query_prompt
    from cognee_lab.identity.environment import DATASET_NAME
    from cognee_lab.identity.publish import Publisher
    from cognee_lab.identity.retrieve import retrieve

    from pydantic import BaseModel
    import cognee.api.v1.search.routers.get_search_router  # noqa: F401

    class EarlyModel(BaseModel):
        search_type: SearchType

    llm_calls, retriever_calls = [], []
    install_llm(llm_calls, {})
    builtin_names = list(SearchType.__members__)
    member = add_member(SearchType, "IDENTITY")
    use_retriever(member, make_retriever(retriever_calls))
    result = dict(
        environment=dict(
            cognee=cognee.__version__,
            python=sys.version.split()[0],
        ),
        selftest=enum_selftest(SearchType, member, builtin_names),
        payload=payload_checks(SearchType, member, EarlyModel),
        selector_prompt_names_identity=attempt(
            lambda: "IDENTITY" in read_query_prompt("search_type_selector_prompt.txt")
        ),
    )
    publisher = await Publisher.configured()
    user, dataset = await lab_dataset()
    queries = {}
    for query in QUERIES:
        direct = plain(await retrieve(publisher, dataset.id, query))
        named = await attempt_async(
            cognee.search(query, query_type=member, datasets=[DATASET_NAME])
        )
        unscoped = await attempt_async(cognee.search(query, query_type=member))
        by_name_str = await attempt_async(
            cognee.search(
                query, query_type=SearchType["IDENTITY"], datasets=[DATASET_NAME]
            )
        )
        verbose = await attempt_async(
            cognee.search(
                query, query_type=member, datasets=[DATASET_NAME], verbose=True
            )
        )
        only_context = await attempt_async(
            cognee.search(
                query, query_type=member, datasets=[DATASET_NAME], only_context=True
            )
        )
        queries[query] = dict(
            direct_facts=[f["edge_id"] for f in direct["facts"]],
            direct_unavailable=direct["unavailable_sources"],
            named_equals_retrieve=named.get("value") == [direct],
            unscoped_equals_retrieve=unscoped.get("value") == [direct],
            getitem_equals_retrieve=by_name_str.get("value") == [direct],
            named=named if named.get("value") != [direct] else "equal",
            unscoped=unscoped if unscoped.get("value") != [direct] else "equal",
            verbose_keys=(
                sorted(verbose["value"][0]) if verbose.get("ok") else verbose
            ),
            verbose_text_equals=(
                verbose.get("ok") and verbose["value"][0]["text_result"] == [direct]
            ),
            only_context_type=(
                type(only_context["value"]).__name__
                if only_context.get("ok")
                else only_context
            ),
            only_context_is_json_of_retrieve=(
                only_context.get("ok")
                and json.loads(
                    only_context["value"]
                    if isinstance(only_context["value"], str)
                    else only_context["value"][0]
                )
                == direct
            ),
        )
    result["queries"] = queries
    query = QUERIES[0]
    direct = plain(await retrieve(publisher, dataset.id, query))
    install_llm(llm_calls, {"str": lambda _: "IDENTITY"})
    before = len(retriever_calls)
    lucky = await attempt_async(
        cognee.search(
            query, query_type=SearchType.FEELING_LUCKY, datasets=[DATASET_NAME]
        )
    )
    result["feeling_lucky"] = dict(
        identity_retriever_ran=len(retriever_calls) > before,
        equals_retrieve=lucky.get("value") == [direct],
        outcome=lucky if lucky.get("value") != [direct] else "equal",
    )
    install_llm(llm_calls, {})
    before = len(retriever_calls)
    recalled = await attempt_async(
        cognee.recall(query, query_type=member, datasets=[DATASET_NAME])
    )
    items = recalled.get("value") or []
    result["recall"] = dict(
        identity_retriever_ran=len(retriever_calls) > before,
        items=len(items),
        item_type=[type(i).__name__ for i in items],
        item_fields=[
            dict(
                kind=getattr(i, "kind", None),
                search_type=str(getattr(i, "search_type", None)),
                source=getattr(i, "source", None),
                dataset_name=getattr(i, "dataset_name", None),
            )
            for i in items
        ],
        raw_equals_retrieve=[plain(getattr(i, "raw", None)) == direct for i in items],
        text_is_json_of_retrieve=[
            attempt(lambda: json.loads(getattr(i, "text", "")) == direct) for i in items
        ],
        error=None if recalled["ok"] else recalled,
    )
    result["history"] = await history()
    result["retriever_calls"] = retriever_calls
    result["llm_calls"] = llm_calls
    return result


async def graph_index(publisher):
    nodes, edges = await publisher.graph.get_graph_data()
    return {str(i): p for i, p in nodes}, edges


async def classify(publisher, rows):
    from cognee_lab.identity.retrieve import withheld_now

    held = await withheld_now(publisher, rows)
    mentions, withheld_mentions, failed_docs = {}, set(), set()
    for row in rows:
        description = row.description
        if description is None:
            continue
        original = description.inputs[description.original_input_ref]
        if row.state != "current":
            failed_docs.add(str(original.data_id))
        for key, group in description.mention_groups.items():
            mentions[str(group.entity_id)] = dict(source=row.source, group=key)
        for key in held.get(row.source, {}):
            decision = description.mention_resolutions.get(key)
            if decision is not None:
                group = description.mention_groups[decision.group_ref]
                withheld_mentions.add(str(group.entity_id))
    return held, mentions, withheld_mentions, failed_docs


def node_id(node) -> str:
    return str(getattr(node, "id", node))


async def probe_e2(root: Path) -> dict:
    import cognee
    from cognee.modules.search.types import SearchType
    from cognee_lab.identity.environment import DATASET_NAME
    from cognee_lab.identity.publish import Publisher
    from cognee_lab.identity.retrieve import retrieve

    llm_calls = []
    install_llm(llm_calls, {})
    publisher = await Publisher.configured()
    user, dataset = await lab_dataset()
    rows = await publisher.records.rows(dataset.id)
    held, mentions, withheld_mentions, failed_docs = await classify(publisher, rows)
    nodes, edges = await graph_index(publisher)
    labels = {
        str(r.description.inputs[r.description.original_input_ref].data_id): (
            r.description.original_input_ref
        )
        for r in rows
        if r.description is not None
    }
    doc_data = {str(a): str(b) for a, b, rel, _ in edges if rel == "is_part_of"}
    chunk_doc = {c: labels.get(d, nodes[d].get("name")) for c, d in doc_data.items()}
    chunk_text = {c: nodes[c].get("text", "") for c in doc_data}
    failed_chunks = {c for c, d in doc_data.items() if d in failed_docs}
    facts = {(str(a), rel, str(b)) for a, b, rel, _ in edges if rel not in STRUCTURAL}
    withheld_facts = {f for f in facts if f[0] in withheld_mentions}
    failed_facts = {
        f
        for f in facts
        if any(
            str(c) in failed_chunks and str(e) == f[0]
            for c, e, rel, _ in edges
            if rel == "contains"
        )
    }
    mention_names = {i: nodes[i].get("name") for i in mentions if i in nodes}
    result = dict(
        rows=[dict(source=r.source, state=r.state, revision=r.revision) for r in rows],
        withheld_decisions={s: sorted(v) for s, v in held.items()},
        mention_nodes=mention_names,
        withheld_mention_nodes=sorted(withheld_mentions),
        fact_edges=sorted(map(list, facts)),
        withheld_fact_edges=sorted(map(list, withheld_facts)),
        failed_doc_chunks=sorted(failed_chunks),
        failed_row_fact_edges=sorted(map(list, failed_facts)),
        chunk_documents=chunk_doc,
        queries={},
    )
    for query in QUERIES:
        entry = {}
        identity = plain(await retrieve(publisher, dataset.id, query))
        entry["identity"] = dict(
            facts=[f["text"] for f in identity["facts"]],
            unavailable=[
                [u["assignment_id"], u["reason"]]
                for u in identity["unavailable_sources"]
            ],
        )
        chunks = await attempt_async(
            cognee.search(
                query,
                query_type=SearchType.CHUNKS,
                datasets=[DATASET_NAME],
                verbose=True,
            )
        )
        if chunks["ok"]:
            found = chunks["value"][0]["objects_result"] or []
            served = [str(c.id) for c in found]
            texts = [c.payload.get("text", "") for c in found]
            entry["CHUNKS"] = dict(
                chunks=len(served),
                by_document=[chunk_doc.get(c) for c in served],
                failed_row_chunks=sum(c in failed_chunks for c in served),
                chunks_with_edited_text=sum(
                    "ECRH" in t or "plasma-heating" in t for t in texts
                ),
                glossary_texts=[
                    t for c, t in zip(served, texts) if chunk_doc.get(c) == "glossary"
                ],
            )
        else:
            entry["CHUNKS"] = chunks
        for name in ("GRAPH_COMPLETION", "TRIPLET_COMPLETION"):
            served = await attempt_async(
                cognee.search(
                    query,
                    query_type=SearchType[name],
                    datasets=[DATASET_NAME],
                    only_context=True,
                    verbose=True,
                )
            )
            if not served["ok"]:
                entry[name] = served
                continue
            payload = served["value"][0]
            objects = payload["objects_result"] or []
            context = payload["context_result"]
            context_text = context if isinstance(context, str) else json.dumps(context)
            triples = []
            for edge in objects:
                a = node_id(getattr(edge, "node1", None))
                b = node_id(getattr(edge, "node2", None))
                attributes = getattr(edge, "attributes", {}) or {}
                rel = attributes.get("relationship_name") or attributes.get(
                    "relationship_type"
                )
                triples.append((a, rel, b))
            entry[name] = dict(
                edges=len(triples),
                edges_touching_mentions=sum(
                    t[0] in mentions or t[2] in mentions for t in triples
                ),
                mention_nodes_reached=sorted(
                    {t[0] for t in triples if t[0] in mentions}
                    | {t[2] for t in triples if t[2] in mentions}
                ),
                mention_label_lines={
                    label: mention_lines(context_text, label)
                    for label in mention_names.values()
                },
                withheld_facts_served=sum(t in withheld_facts for t in triples),
                withheld_mention_edges_served=sum(
                    t[0] in withheld_mentions or t[2] in withheld_mentions
                    for t in triples
                ),
                failed_row_facts_served=sum(t in failed_facts for t in triples),
                failed_row_chunk_nodes_served=sum(
                    t[0] in failed_chunks or t[2] in failed_chunks for t in triples
                ),
                relations=sorted({str(t[1]) for t in triples}),
                context_chars=len(context_text),
                context_head=context_text[:600],
            )
        result["queries"][query] = entry
    from cognee.memify_pipelines.create_triplet_embeddings import (
        create_triplet_embeddings,
    )

    install_llm(llm_calls, {"str": lambda _: "test"})
    memified = await attempt_async(
        create_triplet_embeddings(user, dataset=DATASET_NAME)
    )
    install_llm(llm_calls, {})
    result["triplet_embeddings"] = dict(
        ok=memified["ok"], error=memified.get("error"), message=memified.get("message")
    )
    for query in QUERIES:
        served = await attempt_async(
            cognee.search(
                query,
                query_type=SearchType.TRIPLET_COMPLETION,
                datasets=[DATASET_NAME],
                only_context=True,
                verbose=True,
            )
        )
        identity = plain(await retrieve(publisher, dataset.id, query))
        entry = result["queries"][query]
        entry["identity_after_triplet_embeddings"] = [
            f["text"] for f in identity["facts"]
        ]
        if not served["ok"]:
            entry["TRIPLET_COMPLETION_after_embeddings"] = served
            continue
        payload = served["value"][0]
        texts = [
            (getattr(o, "payload", None) or {}).get("text", "")
            for o in payload["objects_result"] or []
        ]
        entry["TRIPLET_COMPLETION_after_embeddings"] = dict(
            triplets=len(texts),
            texts=texts,
            mention_label_triplets={
                label: sum(label in triplet_ends(t) for t in texts)
                for label in mention_names.values()
            },
            withheld_facts_served=sum(
                any(serves_fact(t, nodes, f) for f in withheld_facts) for t in texts
            ),
            failed_row_facts_served=sum(
                any(serves_fact(t, nodes, f) for f in failed_facts) for t in texts
            ),
            failed_row_chunk_texts_served=sum(
                any(
                    triplet_ends(t)[0].strip() == chunk_text[c].strip()
                    for c in failed_chunks
                )
                for t in texts
            ),
            context_chars=len(str(payload["context_result"])),
        )
    result["llm_calls"] = llm_calls
    return result


def mention_lines(context: str, label: str) -> int:
    """Lines of a GRAPH_COMPLETION context that name `label` as a node: its
    node entry and each connection it is an endpoint of."""
    return sum(
        line == f"Node: {label}"
        or line.startswith(f"{label} --[")
        or f"]--> {label}  (" in line
        for line in context.splitlines()
    )


ARROW = "-›"


def triplet_ends(text: str) -> tuple[str, str]:
    """A Triplet_text payload is `subject-›edge text-›object`."""
    parts = text.split(ARROW)
    return parts[0], parts[-1]


def serves_fact(text: str, nodes: dict, fact: tuple) -> bool:
    a, rel, b = fact
    return triplet_ends(text) == (nodes[a].get("name"), nodes[b].get("name"))


def knowledge_graph(model):
    from cognee.shared.data_models import Edge, Node

    return model(
        summary="Aurora controller limits vibrations.",
        description="Aurora controller limits vibrations.",
        nodes=[
            Node(
                id="aurora controller",
                name="Aurora controller",
                type="Device",
                description="A cryostat controller.",
            ),
            Node(
                id="vibrations",
                name="vibrations",
                type="Phenomenon",
                description="Mechanical vibrations.",
            ),
        ],
        edges=[
            Edge(
                source_node_id="aurora controller",
                target_node_id="vibrations",
                relationship_name="limits",
            )
        ],
    )


async def seeds_for(publisher, dataset_id, lab_entities) -> dict:
    from cognee_lab.identity.retrieve import retrieve

    found = {}
    for query in (*QUERIES, FOREIGN_QUERY):
        result = plain(await retrieve(publisher, dataset_id, query))
        found[query] = dict(
            seeds=result["seed_entity_ids"],
            foreign_seeds=[
                s for s in result["seed_entity_ids"] if s not in lab_entities
            ],
            facts=[f["text"] for f in result["facts"]],
        )
    return found


async def search_scopes(member, calls) -> dict:
    import cognee
    from cognee_lab.identity.environment import DATASET_NAME

    found = {}
    for label, datasets in (("none", None), ("lab", [DATASET_NAME])):
        before = len(calls)
        outcome = await attempt_async(
            cognee.search(QUERIES[0], query_type=member, datasets=datasets)
        )
        found[label] = dict(
            retriever_dataset=[c["dataset"] for c in calls[before:]],
            outcome=outcome,
        )
    return found


async def probe_e5(root: Path) -> dict:
    import cognee
    from cognee.modules.engine.utils import generate_node_id
    from cognee.modules.retrieval.register_retriever import use_retriever
    from cognee.modules.search.types import SearchType
    from cognee.modules.data.methods import get_datasets
    from cognee_lab.identity.publish import Publisher

    llm_calls, retriever_calls = [], []
    install_llm(llm_calls, {})
    member = add_member(SearchType, "IDENTITY")
    use_retriever(member, make_retriever(retriever_calls))
    publisher = await Publisher.configured()
    user, dataset = await lab_dataset()
    nodes, _ = await graph_index(publisher)
    lab_entities = {i for i, p in nodes.items() if p.get("type") == "Entity"}

    async def datasets():
        return [dict(id=str(d.id), name=d.name) for d in await get_datasets(user.id)]

    result = dict(
        lab_entity_ids={i: nodes[i].get("name") for i in sorted(lab_entities)},
        cognee_node_id_collisions={
            name: str(generate_node_id(name)) in lab_entities
            for name in ("HC", "Helios controller", "oscillations")
        },
        baseline=dict(
            datasets=await datasets(),
            scopes=await search_scopes(member, retriever_calls),
            seeds=await seeds_for(publisher, dataset.id, lab_entities),
        ),
    )
    added = await attempt_async(cognee.add(FOREIGN_TEXT, dataset_name=FOREIGN_DATASET))
    result["after_plain_add"] = dict(
        add=dict(
            ok=added["ok"], error=added.get("error"), message=added.get("message")
        ),
        datasets=await datasets(),
        scopes=await search_scopes(member, retriever_calls),
        seeds=await seeds_for(publisher, dataset.id, lab_entities),
    )
    install_llm(
        llm_calls,
        {
            "str": lambda _: "test",
            "KnowledgeGraph": knowledge_graph,
            "SummarizedContent": lambda model: model(
                summary="Aurora controller limits vibrations."
            ),
        },
    )
    cognified = await attempt_async(cognee.cognify(datasets=[FOREIGN_DATASET]))
    install_llm(llm_calls, {})
    nodes_after, _ = await graph_index(publisher)
    result["after_foreign_cognify"] = dict(
        cognify=dict(
            ok=cognified["ok"],
            error=cognified.get("error"),
            message=cognified.get("message"),
        ),
        foreign_entities={
            i: p.get("name")
            for i, p in nodes_after.items()
            if p.get("type") == "Entity" and i not in lab_entities
        },
        lab_entities_unchanged={
            i: nodes_after.get(i, {}).get("name") == nodes[i].get("name")
            for i in sorted(lab_entities)
        },
        entity_name_hits={
            query: [
                str(c.id)
                for c in await publisher.vector.search(
                    "Entity_name",
                    query_text=query,
                    query_vector=None,
                    limit=10,
                    include_payload=False,
                )
            ]
            for query in (*QUERIES, FOREIGN_QUERY)
        },
        datasets=await datasets(),
        scopes=await search_scopes(member, retriever_calls),
        seeds=await seeds_for(publisher, dataset.id, lab_entities),
    )
    result["retriever_calls"] = retriever_calls
    result["llm_calls"] = llm_calls
    return result


PROBES = dict(e1=probe_e1, e2=probe_e2, e5=probe_e5)


def inner(args) -> None:
    from cognee_lab.identity.environment import fixture_environment

    root = Path(args.root).resolve()
    with fixture_environment(root):
        result = asyncio.run(PROBES[args.inner](root))
    Path(args.out).write_text(json.dumps(result, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--probes", default="e1,e2,e5")
    parser.add_argument("--stages", default=",".join(FAILED_STAGES))
    parser.add_argument("--inner", choices=sorted(PROBES), help=argparse.SUPPRESS)
    parser.add_argument("--root", help=argparse.SUPPRESS)
    parser.add_argument("--out", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inner:
        inner(args)
    else:
        orchestrate(args)


if __name__ == "__main__":
    main()
