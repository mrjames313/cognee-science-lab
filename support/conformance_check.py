"""The conformance check of the IDENTITY search on a conformance-fixture root.

It scores `cognee.search` with the lab's IDENTITY search type against the
Stage 5.3 traversal and query-resolution benchmarks and the Helios manifest
in data/hidden, and it is the only reader of data/hidden.
docs/stage6_conformance_check.md states the describer, the measures, the
baseline and the gate.

    uv run python support/conformance_check.py [--root DIR] [--json]
    uv run python support/conformance_check.py --write-baseline
"""

import argparse
import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ANSWERS = REPO / "data" / "hidden"
BASELINE = Path(__file__).with_name("conformance_baseline.json")
RUNS = REPO / "outputs" / "conformance"
RECALL_TOP_K = 5
CLOSURE_TOP_K = 100
GATED_COUNTS = ("repeated_edge_ids", "attribution_violations", "leakage_violations")


class Outcome(StrEnum):
    """A case's outcome, worst first: a case that passes outranks an
    unobserved one (the search showed nothing that decides it), which
    outranks a failure."""

    FAILED = "failed"
    UNOBSERVED = "unobserved"
    PASSED = "passed"

    @property
    def rank(self) -> int:
        return list(Outcome).index(self)

    @classmethod
    def of(cls, passed: bool) -> "Outcome":
        return cls.PASSED if passed else cls.FAILED


def load(name):
    return yaml.safe_load((ANSWERS / name).read_text())


def words(text):
    return f" {' '.join(re.findall(r'[a-z0-9]+(?:\.[0-9]+)?', text.casefold()))} "


def holds_value(text, unit, low, high):
    for match in re.finditer(
        rf"(\d+(?:\.\d+)?)(?:\s*[–-]\s*(\d+(?:\.\d+)?))?\s*{re.escape(unit)}(?!\w)",
        text,
    ):
        found = (float(match[1]), float(match[2] or match[1]))
        if found == (float(low), float(high)):
            return True
    return False


class Fixture:
    """The conformance root's saved description, by name and identity group."""

    def __init__(self, root):
        from cognee_lab.identity.conformance_fixture import identity_groups
        from cognee_lab.identity.models import IdentitySource

        self.source = IdentitySource.model_validate_json(
            (root / "identity.json").read_text()
        )
        source = self.source
        doc = source.inputs[source.original_input_ref]
        self.text = next(root.glob("DOC01_*.md")).read_text()
        self.original = str(doc.data_id)
        chunks = sorted(
            (i for i in source.inputs.values() if i.kind == "chunk"),
            key=lambda i: i.start,
        )
        self.chunks = [(i.start, i.end) for i in chunks]
        self.chunk_ids = {str(i.chunk_id) for i in chunks}
        self.mentions = {str(g.entity_id) for g in source.mention_groups.values()}
        self.group = {str(e): str(g) for e, g in identity_groups(source).items()}
        self.names = {
            str(e): r.name
            for e, r in source.entity_constructions.items()
            if str(e) not in self.mentions
        }

    def groups_named(self, names) -> set[str]:
        wanted = {n.casefold() for n in names}
        return {self.group[e] for e, n in self.names.items() if n.casefold() in wanted}

    def label(self, group) -> str:
        return min(n for e, n in self.names.items() if self.group[e] == group)

    def resolved(self, result) -> set[str]:
        """The identity groups a search resolved: its seeds' and its fact
        subjects'."""
        ids = set(result["seed_entity_ids"]) | {f["source_id"] for f in result["facts"]}
        return {self.group[e] for e in ids if e in self.group}


def manifest_names(manifest, key):
    entity = manifest["entities"][key]
    return [entity["canonical_name"], *entity.get("aliases", [])]


class Check:
    def __init__(self, fixture, search, node_type):
        self.fixture, self.search, self.node_type = fixture, search, node_type
        self.cases = {}
        self.counts = dict.fromkeys((*GATED_COUNTS, "logical_duplicates"), 0)
        self.searches = 0

    async def query(self, text, top_k):
        result = await self.search(text, top_k)
        self.searches += 1
        await self.inspect(result)
        return result

    def case(self, case_id, metric, outcome: Outcome, **detail):
        self.cases[case_id] = dict(metric=metric, outcome=outcome, detail=detail)

    def control(self, subject, wrong, outcome: Outcome, **detail):
        """A negative control: `subject` is never served or resolved under
        the `wrong` referent."""
        self.case(f"{subject}:not:{wrong}", "negative_controls", outcome, **detail)

    async def inspect(self, result):
        """The counts every result adds to: repeated edge IDs, attribution
        outside DOC01's own chunks, endpoint leakage and logical duplicates."""
        fixture = self.fixture
        ids = [f["edge_id"] for f in result["facts"]]
        self.counts["repeated_edge_ids"] += len(ids) - len(set(ids))
        logical = {}
        for fact in result["facts"]:
            for e in fact["evidence"]:
                if (
                    e["data_id"] != fixture.original
                    or e["chunk_id"] not in fixture.chunk_ids
                ):
                    self.counts["attribution_violations"] += 1
            identity = fact.get("identity")
            if identity and identity["identity_data_id"] != str(
                fixture.source.identity_data_id
            ):
                self.counts["attribution_violations"] += 1
            for endpoint in (fact["source_id"], fact["target_id"]):
                if await self.node_type(endpoint) != "Entity":
                    self.counts["leakage_violations"] += 1
            if fact["target_id"] in fixture.mentions or (
                fact["source_id"] in fixture.mentions and not identity
            ):
                self.counts["leakage_violations"] += 1
            subject = fixture.group.get(fact["source_id"], fact["source_id"])
            target = fixture.group.get(fact["target_id"], fact["target_id"])
            logical.setdefault((subject, fact["relationship"], target), set()).add(
                fact["source_id"]
            )
        self.counts["logical_duplicates"] += sum(len(s) - 1 for s in logical.values())

    async def fact_recall(self, manifest):
        facts = manifest["facts"] + manifest["temporal_facts"]
        for fact in [f for f in facts if "DOC01" in f["expected_sources"]]:
            subject = manifest["entities"][fact["subject"]]["canonical_name"]
            query = f"{subject} {fact['predicate'].replace('_', ' ')}"
            result = await self.query(query, RECALL_TOP_K)
            if "object" in fact:
                objects = (
                    manifest_names(manifest, fact["object"])
                    if fact["object"] in manifest["entities"]
                    else [fact["object"]]
                )

                def holds(text):
                    return any(words(o) in words(text) for o in objects)

            else:
                low = fact.get("value", fact.get("value_min"))
                high = fact.get("value", fact.get("value_max"))

                def holds(text):
                    return holds_value(text, fact["unit"], low, high)

            hits = [f for f in result["facts"] if holds(f["text"])]
            subjects = self.fixture.groups_named(
                manifest_names(manifest, fact["subject"])
            )
            self.case(
                f"recall:{fact['id']}",
                "fact_recall",
                Outcome.of(bool(hits)),
                query=query,
                subject_matched=any(
                    self.fixture.group.get(f["source_id"]) in subjects for f in hits
                ),
            )

    async def closure(self, traversal):
        for case in traversal["identity_cases"]:
            seen = {}
            for member in case["members"]:
                result = await self.query(member["name"], CLOSURE_TOP_K)
                seen[member["name"]] = dict(
                    present=bool(self.fixture.groups_named([member["name"]])),
                    edges=sorted(f["edge_id"] for f in result["facts"]),
                    groups=sorted(
                        self.fixture.label(g) for g in self.fixture.resolved(result)
                    ),
                )
            edge_sets = {tuple(s["edges"]) for s in seen.values()}
            if not all(s["present"] for s in seen.values()):
                outcome = Outcome.FAILED
            elif edge_sets == {()}:
                outcome = Outcome.UNOBSERVED
            else:
                outcome = Outcome.of(len(edge_sets) == 1)
            self.case(
                f"closure:{case['id']}",
                "closure_symmetry",
                outcome,
                members={
                    m: dict(
                        present=s["present"], facts=len(s["edges"]), groups=s["groups"]
                    )
                    for m, s in seen.items()
                },
            )

    async def served_under(self, span, query):
        """The referent groups under which the search serves a fact anchored
        at `span`, for `query`."""
        start, end = span
        result = await self.query(query, CLOSURE_TOP_K)
        return {
            self.fixture.group[f["identity"]["target_entity_id"]]
            for f in result["facts"]
            if "identity" in f
            and any(
                o["start"] < end and start < o["end"]
                for o in f["identity"]["occurrences"]
            )
        }

    async def mention(self, case_id, span, expected, wrong):
        """A mention served under `expected` (None: under no group), and
        never under the `wrong` group, a negative control."""
        fixture = self.fixture
        if expected is not None:
            group = fixture.groups_named([expected])
            served = await self.served_under(span, expected)
            self.case(
                case_id,
                "mentions",
                (
                    Outcome.of(len(group) == 1 and served == group)
                    if served
                    else Outcome.UNOBSERVED
                ),
                expected=expected,
                served=sorted(fixture.label(g) for g in served),
            )
        if wrong is not None:
            groups = fixture.groups_named([wrong])
            served = await self.served_under(span, wrong)
            observed = (
                expected is None
                or self.cases[case_id]["outcome"] is not Outcome.UNOBSERVED
            )
            self.control(
                case_id,
                wrong,
                (
                    Outcome.of(not served & groups)
                    if observed or served
                    else Outcome.UNOBSERVED
                ),
                served=sorted(fixture.label(g) for g in served),
            )

    async def mentions(self, traversal, manifest):
        text = self.fixture.text
        cases = traversal["mention_cases"]

        def place(case):
            return case["source_chunk_index"], case["surface_text"].casefold()

        # An unresolved mention case must not take the referent of the
        # resolved case at the same surface in the same chunk (TRV08 against
        # TRV07's VCS).
        referents = {
            place(c): c["expected_canonical"] for c in cases if c["expected_canonical"]
        }
        for case in cases:
            expected = case["expected_canonical"]
            wrong = None if expected else referents.get(place(case))
            start, end = self.fixture.chunks[case["source_chunk_index"]]
            surface = case["surface_text"].casefold()
            at = [
                start + m.start()
                for m in re.finditer(re.escape(surface), text[start:end].casefold())
            ]
            if case["occurrence_index"] >= len(at):
                reason = (
                    f"chunk {case['source_chunk_index']} of the fixture holds "
                    f"{len(at)} occurrence(s) of {case['surface_text']!r}"
                )
                self.case(case["id"], "mentions", Outcome.UNOBSERVED, reason=reason)
                if wrong:
                    self.control(case["id"], wrong, Outcome.UNOBSERVED, reason=reason)
                continue
            at = at[case["occurrence_index"]]
            if not expected:
                self.case(
                    case["id"],
                    "mentions",
                    Outcome.UNOBSERVED,
                    reason="nothing to serve",
                )
            await self.mention(case["id"], (at, at + len(surface)), expected, wrong)
        for er in manifest["entity_resolution_ground_truth"]:
            if er["document"] != "DOC01":
                continue
            context = er["context"].removesuffix("...").strip()
            at = text.find(context)
            inner = context.casefold().find(er["mention"].casefold())
            if at < 0 or inner < 0:
                self.case(
                    er["id"],
                    "mentions",
                    Outcome.UNOBSERVED,
                    reason="context not in DOC01",
                )
                continue
            span = (at + inner, at + inner + len(er["mention"]))
            target = manifest["entities"][er["resolve_to"]]["canonical_name"]
            wrong = er.get("hard_negative_for")
            await self.mention(
                er["id"],
                span,
                target,
                manifest["entities"][wrong]["canonical_name"] if wrong else None,
            )

    async def negative_controls(self, traversal):
        fixture = self.fixture
        for case in traversal["identity_cases"]:
            for excluded in case.get("must_not_include", []):
                groups = fixture.groups_named([excluded])
                members = fixture.groups_named([m["name"] for m in case["members"]])
                for member in case["members"]:
                    result = await self.query(member["name"], CLOSURE_TOP_K)
                    self.control(
                        f"{case['id']}:{member['name']}",
                        excluded,
                        Outcome.of(
                            bool(groups) and not fixture.resolved(result) & groups
                        ),
                    )
                result = await self.query(excluded, CLOSURE_TOP_K)
                self.control(
                    f"{case['id']}:{excluded}",
                    case["canonical"],
                    Outcome.of(bool(groups) and not fixture.resolved(result) & members),
                )

    async def query_resolution(self, queries):
        fixture = self.fixture
        for case in queries["cases"]:
            result = await self.query(case["context"], RECALL_TOP_K)
            resolved = fixture.resolved(result)
            expected = (
                fixture.groups_named([case["expected"]]) if case["expected"] else set()
            )
            if case["expected_status"] == "ambiguous":
                metric, passed = "negative_controls", not resolved
            elif case["mechanism"] == "contextual":
                metric, passed = "query_resolution", resolved <= expected
            else:
                metric, passed = "query_resolution", bool(expected & resolved)
            self.case(
                f"query:{case['id']}",
                metric,
                Outcome.of(passed),
                resolved=sorted(fixture.label(g) for g in resolved),
            )


async def measure(root):
    import cognee
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.infrastructure.databases.vector import get_vector_engine_async

    from cognee_lab.identity.environment import DATASET_NAME, close_stores
    from cognee_lab.identity.search import IDENTITY

    graph = await get_graph_engine()
    types = {}

    async def node_type(node_id):
        if node_id not in types:
            node = await graph.get_node(node_id)
            types[node_id] = node.get("type") if node else None
        return types[node_id]

    async def search(query, top_k):
        (result,) = await cognee.search(
            query, query_type=IDENTITY, datasets=[DATASET_NAME], top_k=top_k
        )
        return result

    traversal = load("stage5_traversal_benchmark_v0.1.yaml")
    manifest = load("helios_hidden_manifest_v0.2.yaml")
    check = Check(Fixture(root), search, node_type)
    try:
        await check.fact_recall(manifest)
        await check.closure(traversal)
        await check.mentions(traversal, manifest)
        await check.negative_controls(traversal)
        await check.query_resolution(
            load("stage5_query_resolution_benchmark_v0.1.yaml")
        )
    finally:
        await close_stores(await get_vector_engine_async(), graph)
    return check, sorted({str(t) for t in types.values() if t != "Entity"})


def make_root(root):
    made = subprocess.run(
        [
            sys.executable,
            "-m",
            "cognee_lab.identity",
            "conformance-fixture",
            "--root",
            str(root),
            "--embedding",
            "loopback",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if made.returncode != 0:
        tail = "\n".join(
            (made.stdout.strip().splitlines()[-1:] or [])
            + made.stderr.strip().splitlines()[-40:]
        )
        raise SystemExit(
            f"conformance-fixture exited {made.returncode} for {root}:\n{tail}"
        )


def metrics(cases):
    table = {}
    for case in cases.values():
        row = table.setdefault(case["metric"], dict(passed=0, failed=0, unobserved=0))
        row[case["outcome"].value] += 1
    return table


def compare(cases, counts, baseline):
    """How this run moved from `baseline`: regressions (a case that does
    worse, appears or disappears, or a gated count that grew) and
    improvements. Either one fails the check."""
    recorded = {c: v for c, v in baseline["cases"].items() if "outcome" in v}
    regressions, improvements = [], []
    for case_id, then in recorded.items():
        now = cases.get(case_id)
        if now is None:
            regressions.append(f"{case_id}: missing from this run")
            continue
        was, outcome = Outcome(then["outcome"]), now["outcome"]
        moved = f"{case_id}: {was} on the baseline, now {outcome}"
        if outcome.rank < was.rank:
            regressions.append(moved)
        elif outcome.rank > was.rank:
            improvements.append(moved)
    regressions += [
        f"{case_id}: new case, not on the baseline"
        for case_id in sorted(set(cases) - set(recorded))
    ]
    regressions += [
        f"{name}: {counts[name]} (baseline {baseline['counts'].get(name, 0)})"
        for name in GATED_COUNTS
        if counts[name] > baseline["counts"].get(name, 0)
    ]
    return regressions, improvements


def baseline_of(cases, counts, old):
    """The baseline for this run, each case that does not pass with its gap
    (the reason it does not pass) carried from `old`, and the problems that
    refuse it: a case that does not pass with no gap, a gap on a case that
    passes, and a gated count that is not 0. The baseline file is the only
    record of the gaps; edit a gap there, then write the baseline again."""
    written, problems = {}, []
    for case_id, case in sorted(cases.items()):
        outcome = case["outcome"]
        gap = old["cases"].get(case_id, {}).get("gap")
        entry = dict(metric=case["metric"], outcome=outcome.value)
        if outcome is Outcome.PASSED:
            if gap:
                problems.append(f"{case_id} passes; delete its gap from the baseline")
        elif gap:
            entry["gap"] = gap
        else:
            problems.append(f"{case_id} is {outcome}; record its gap in the baseline")
        written[case_id] = entry
    problems += [
        f"{name} is {counts[name]}; a gated count must be 0"
        for name in GATED_COUNTS
        if counts[name]
    ]
    return dict(cases=written, counts=counts), problems


def report_lines(report):
    lines = [f"conformance check on {report['root']} ({report['searches']} searches)"]
    lines.append(f"{'measure':<20}{'passed':>8}{'failed':>8}{'unobserved':>12}")
    for name, row in sorted(report["metrics"].items()):
        lines.append(
            f"{name:<20}{row['passed']:>8}{row['failed']:>8}{row['unobserved']:>12}"
        )
    for name, value in report["counts"].items():
        gate = "gated, must be 0" if name in GATED_COUNTS else "reported only"
        lines.append(f"{name}: {value} ({gate})")
    lines.append(f"cases that do not pass: {len(report['gaps'])}")
    lines += [f"  {g['case']} [{g['outcome']}]: {g['gap']}" for g in report["gaps"]]
    for title in ("regressions", "improvements"):
        lines.append(f"{title}: {len(report[title])}")
        lines += [f"  {item}" for item in report[title]]
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root",
        type=Path,
        help="a conformance-fixture root to search, made here if missing "
        "(default: a new root under outputs/conformance/)",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="write support/conformance_baseline.json from a new root, keeping "
        "each gap it records",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the report as JSON only"
    )
    args = parser.parse_args()
    if args.write_baseline and args.root:
        parser.error("--write-baseline searches a root it makes; drop --root")
    root = (
        args.root
        or RUNS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") / "root"
    ).resolve()
    if not root.exists():
        make_root(root)
    from cognee_lab.identity.environment import fixture_environment, read_fixture

    if read_fixture(root) != "conformance-fixture":
        parser.error(f"{root} is not a conformance-fixture root")
    with fixture_environment(root):
        check, leaking = asyncio.run(measure(root))
    counts = check.counts
    old = (
        json.loads(BASELINE.read_text())
        if BASELINE.exists()
        else dict(cases={}, counts={})
    )
    if args.write_baseline:
        regressions, improvements = compare(check.cases, counts, old)
        print(f"moved from {BASELINE.name}:", file=sys.stderr)
        for item in regressions + improvements or ["nothing"]:
            print(f"  {item}", file=sys.stderr)
        old, problems = baseline_of(check.cases, counts, old)
        if problems:
            parser.error(f"{BASELINE.name} not written: " + "; ".join(problems))
        BASELINE.write_text(json.dumps(old, indent=2) + "\n")
        print(f"wrote {BASELINE.name}", file=sys.stderr)
    if not old["cases"]:
        parser.error(f"{BASELINE.name} is missing; write it with --write-baseline")
    regressions, improvements = compare(check.cases, counts, old)
    report = dict(
        root=str(root),
        searches=check.searches,
        metrics=metrics(check.cases),
        counts=counts,
        leaking_node_types=leaking,
        cases=check.cases,
        gaps=[
            dict(
                case=case_id,
                outcome=case["outcome"],
                gap=old["cases"].get(case_id, {}).get("gap", "NO GAP RECORDED"),
            )
            for case_id, case in sorted(check.cases.items())
            if case["outcome"] is not Outcome.PASSED
        ],
        regressions=regressions,
        improvements=improvements,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n".join(report_lines(report)))
    if improvements:
        print("baseline is stale, rerun with --write-baseline", file=sys.stderr)
    raise SystemExit(1 if regressions or improvements else 0)


if __name__ == "__main__":
    main()
