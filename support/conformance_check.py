"""The conformance check of the IDENTITY search on a conformance-fixture root.

It scores `cognee.search` with the lab's IDENTITY search type against the
Stage 5.3 traversal and query-resolution benchmarks and the Helios manifest
in data/hidden. It is the only reader of data/hidden: the fixture's describer
(src/cognee_lab/identity/conformance_fixture.py) reads DOC01 alone. Its rules
were written by an author who had read these answers, so a pass means the
search serves the fixture's description as the benchmarks expect, not that
Describe found it.

Each measure is a set of cases. A case passes, fails, or is unobserved (the
search shows nothing that decides it):

- fact recall: for each manifest fact DOC01 states, the query "<subject>
  <predicate>" returns, within the default top 5, a fact whose text holds the
  object or the value with its unit.
- closure symmetry: for each traversal identity case, every member's name as
  the query returns the same nonempty set of facts.
- mentions: TRV07 and TRV08 at their chunk coordinates, and the manifest's
  DOC01 entity resolutions, served (or not) under their referent.
- negative controls: AFRL never brings in the Aurora Reconstruction Suite or
  the reverse, TRV08 and each manifest hard negative never served under the
  wrong referent, and QRY05 resolves nothing.
- query resolution: QRY01 and QRY02 resolve to their group; QRY03 and QRY04
  (an accepted gap) only never resolve to a wrong group.

Over every result it also counts repeated edge IDs, facts attributed to
anything but DOC01's own chunks and fact endpoints that are not Entities
(helper, source-context or mention leakage). These counts must stay 0.
Logical duplicates (one fact through two members of an identity group) are
reported, not gated.

The check compares the cases with support/conformance_baseline.json and exits
1 when a case does worse than there (passed, then unobserved, then failed),
a case appears or disappears, or a gated count grows.
`--write-baseline` writes the baseline from this run; every failing case
then needs its reason in KNOWN_GAPS.

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
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ANSWERS = REPO / "data" / "hidden"
BASELINE = Path(__file__).with_name("conformance_baseline.json")
RUNS = REPO / "outputs" / "conformance"
RECALL_TOP_K = 5
CLOSURE_TOP_K = 100
GATED_COUNTS = ("repeated_edge_ids", "attribution_violations", "leakage_violations")

# Why each case that fails on the baseline fails. A known retrieval limit is
# recorded here, never tuned away in this check.
UNNAMED = (
    "is a lowercase common noun in DOC01; no name rule makes it a reusable "
    "Entity, so no fact has it as subject and the query has no seed"
)
ONE_GROUP = (
    "the sentence names only the subject's identity group; the sentence rule "
    "states a fact only with a second Entity or a quantity"
)
TRV08_COORDINATES = (
    "the case's coordinates (chunk 2, second 'the controller') follow DOC01 "
    "v1's Stage-5 chunking; chunk 2 of DOC01 v2 holds one occurrence. The "
    "manifest's ER005 hard negative stands in for it"
)
KNOWN_GAPS = {
    "recall:F008": "no sentence that states deuterium names a reusable Entity, "
    "so the sentence rule writes no fact",
    "recall:F010": "DOC01 never states 'spatial magnetic measurements' (the "
    "words are matched literally), and the MPA's only fact is RCM -> MPA",
    "recall:F011": f"the two-color interferometer {UNNAMED}",
    "recall:F012": f"Thomson scattering {UNNAMED}",
    "recall:F013": f"the edge reflectometer {UNNAMED}",
    "recall:F014": f"the suite's use: {ONE_GROUP}",
    "recall:F015": f"the EDC's gas feedback: {ONE_GROUP}; its words also differ "
    "from the manifest object",
    "recall:F016": "the pulse length is stated only in a table row that names "
    "no Entity",
    "closure:TRV05_AFRL": "no fact has an AFRL-group subject (AFRL is named only "
    "as the target of a Helios-1 fact), so there is nothing to compare",
    "TRV08_CONTROLLER_UNRESOLVED": TRV08_COORDINATES,
    "TRV08_CONTROLLER_UNRESOLVED:not:vertical control system": TRV08_COORDINATES,
    "ER001": "the section-1 group of 'the machine' has no fact: neither of its "
    "sentences names a second Entity or a quantity with a unit",
    "query:QRY05": "retrieval limit: with no name match the search seeds the top "
    "Entity_name vector hit, so the ambiguous query resolves to an arbitrary "
    "group. Seeding is later work, measured against this baseline",
}


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

    def case(self, case_id, metric, passed, **detail):
        self.cases[case_id] = dict(metric=metric, passed=passed, detail=detail)

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
                bool(hits),
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
                passed = False
            elif edge_sets == {()}:
                passed = None
            else:
                passed = len(edge_sets) == 1
            self.case(
                f"closure:{case['id']}",
                "closure_symmetry",
                passed,
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
                (len(group) == 1 and served == group) if served else None,
                expected=expected,
                served=sorted(fixture.label(g) for g in served),
            )
        if wrong is not None:
            groups = fixture.groups_named([wrong])
            served = await self.served_under(span, wrong)
            observed = expected is None or self.cases[case_id]["passed"] is not None
            self.case(
                f"{case_id}:not:{wrong}",
                "negative_controls",
                (not served & groups) if observed or served else None,
                served=sorted(fixture.label(g) for g in served),
            )

    async def mentions(self, traversal, manifest):
        text = self.fixture.text
        cases = traversal["mention_cases"]
        # An unresolved mention case must not take the referent its resolved
        # neighbours at the same surface take (TRV08 against TRV07's VCS).
        resolved = [c["expected_canonical"] for c in cases if c["expected_canonical"]]
        for case in cases:
            expected = case["expected_canonical"]
            wrong = None if expected else resolved[0]
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
                self.case(case["id"], "mentions", None, reason=reason)
                if wrong:
                    self.case(
                        f"{case['id']}:not:{wrong}",
                        "negative_controls",
                        None,
                        reason=reason,
                    )
                continue
            at = at[case["occurrence_index"]]
            if not expected:
                self.case(case["id"], "mentions", None, reason="nothing to serve")
            await self.mention(case["id"], (at, at + len(surface)), expected, wrong)
        for er in manifest["entity_resolution_ground_truth"]:
            if er["document"] != "DOC01":
                continue
            context = er["context"].removesuffix("...").strip()
            at = text.find(context)
            inner = context.casefold().find(er["mention"].casefold())
            if at < 0 or inner < 0:
                self.case(er["id"], "mentions", None, reason="context not in DOC01")
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
                    self.case(
                        f"{case['id']}:{member['name']}:not:{excluded}",
                        "negative_controls",
                        bool(groups) and not fixture.resolved(result) & groups,
                    )
                result = await self.query(excluded, CLOSURE_TOP_K)
                self.case(
                    f"{case['id']}:{excluded}:not:{case['canonical']}",
                    "negative_controls",
                    bool(groups) and not fixture.resolved(result) & members,
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
                passed,
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
    subprocess.run(
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
        check=True,
        capture_output=True,
        text=True,
    )


def metrics(cases):
    table = {}
    for case in cases.values():
        row = table.setdefault(case["metric"], dict(passed=0, failed=0, unobserved=0))
        row[{True: "passed", False: "failed", None: "unobserved"}[case["passed"]]] += 1
    return table


# A case that passes outranks an unobserved one, which outranks a failure.
RANK = {True: 2, None: 1, False: 0}


def compare(cases, counts, baseline):
    regressions, improvements = [], []
    for case_id, then in baseline["cases"].items():
        now = cases.get(case_id)
        if now is None:
            regressions.append(f"{case_id}: missing from this run")
        elif RANK[now["passed"]] < RANK[then["passed"]]:
            regressions.append(
                f"{case_id}: {then['passed']} on the baseline, now {now['passed']}"
            )
        elif RANK[now["passed"]] > RANK[then["passed"]]:
            improvements.append(case_id)
    regressions += [
        f"{case_id}: new case, not on the baseline"
        for case_id in sorted(set(cases) - set(baseline["cases"]))
    ]
    regressions += [
        f"{name}: {counts[name]} (baseline {baseline['counts'][name]})"
        for name in GATED_COUNTS
        if counts[name] > baseline["counts"][name]
    ]
    return regressions, improvements


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
    gaps = {
        case_id: case
        for case_id, case in report["cases"].items()
        if case["passed"] is not True
    }
    lines.append(f"known gaps and unobserved cases: {len(gaps)}")
    for case_id, case in sorted(gaps.items()):
        lines.append(
            f"  {case_id} [{case['passed']}]: {KNOWN_GAPS.get(case_id, 'NO REASON RECORDED')}"
        )
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
        help="write support/conformance_baseline.json from this run",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the report as JSON only"
    )
    args = parser.parse_args()
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
    if args.write_baseline:
        unexplained = sorted(
            c
            for c, case in check.cases.items()
            if case["passed"] is not True and c not in KNOWN_GAPS
        )
        if unexplained:
            parser.error(f"record a reason in KNOWN_GAPS for {unexplained}")
        baseline = dict(
            cases={
                c: dict(
                    metric=case["metric"], passed=case["passed"], gap=KNOWN_GAPS.get(c)
                )
                for c, case in sorted(check.cases.items())
            },
            counts=counts,
        )
        BASELINE.write_text(json.dumps(baseline, indent=2) + "\n")
    if not BASELINE.exists():
        parser.error(f"{BASELINE.name} is missing; write it with --write-baseline")
    regressions, improvements = compare(
        check.cases, counts, json.loads(BASELINE.read_text())
    )
    report = dict(
        root=str(root),
        searches=check.searches,
        metrics=metrics(check.cases),
        counts=counts,
        leaking_node_types=leaking,
        cases=check.cases,
        regressions=regressions,
        improvements=improvements,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n".join(report_lines(report)))
    raise SystemExit(1 if regressions else 0)


if __name__ == "__main__":
    main()
