#!/usr/bin/env -S uv run python
"""Drive the Stage 6 identity CLI in isolated roots and keep the evidence.

Run from the repository root:

    V=.claude/skills/verify/scripts/verify.py
    $V journey P1
    $V journey all

or by hand:

    RUN=$($V new-run additions)
    $V doctor "$RUN"
    $V drive "$RUN" main fixture -- chunked-fixture
    $V check "$RUN" fixture '.result.facts | length == 2' "fixture returns two facts"
    $V cleanup "$RUN"

Every CLI call gets `--root <run>/roots/<root>`, so this helper never touches the
user-local stores in outputs/stage6_* or the historical lab store.
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from pathlib import Path

from cognee_lab.identity.environment import (
    CREATION_COMMANDS,
    MARKER,
    read_embedding,
    reopen_problem,
)

REPO = Path(__file__).resolve().parents[4]
RUNS = REPO / "outputs" / "verify"
SCRIPT = Path(__file__).resolve().relative_to(REPO)
FEATURES = Path(__file__).resolve().parents[1] / "features"
CLI = [sys.executable, "-m", "cognee_lab.identity"]
EXPECTED_COGNEE = "1.6.2"
TOKENIZER_PATCH = REPO / "patches" / "cognee-1.6.2-openai-compatible-tokenizer.patch"
LAB_SYSTEM = REPO / ".cognee_system"
LAB_DATA = REPO / ".cognee_data"
FENCE = re.compile(r"^```bash journey (?P<id>[A-Z]\d+)(?P<options>( \S+)*)\s*$")
PRELUDE = 'val() { "$V" val "$RUN" "$1" "$2"; }\n'


def fail(message):
    print(f"verify: {message}", file=sys.stderr)
    raise SystemExit(2)


def run_dir(value):
    path = Path(value).resolve()
    if path.parent != RUNS or not (path / "run.json").exists():
        fail(f"{value} is not a run created by new-run under {RUNS}")
    return path


def evidence_steps(run):
    return sorted((run / "evidence").glob("[0-9][0-9]-*.cmd"))


def latest_json(run, label):
    matches = [
        p.with_suffix(".json")
        for p in evidence_steps(run)
        if p.stem.split("-", 1)[1] == label
    ]
    return matches[-1] if matches and matches[-1].exists() else None


def log_assertion(run, verdict, source, expression, description):
    with open(run / "evidence" / "assertions.tsv", "a", newline="") as handle:
        csv.writer(handle, delimiter="\t").writerow(
            [verdict, source, expression, description]
        )


def live_cli_processes(run):
    """PIDs of identity CLI processes whose --root is inside this run."""
    ps = subprocess.run(
        ["ps", "-axo", "pid=,command="], capture_output=True, text=True
    ).stdout
    marker = str(run / "roots")
    return [
        line.split(None, 1)[0]
        for line in ps.splitlines()
        if "cognee_lab.identity" in line and marker in line
    ]


LAB_GUARD = (
    ("system_newest_mtime_ns", "no file in the lab .cognee_system changed"),
    ("system_files", "the lab .cognee_system file count is unchanged"),
    ("cognee_data_files", "the lab .cognee_data file count is unchanged"),
)


def lab_fingerprint():
    """Portable fingerprint of the lab stores that no verify run may touch.

    Covers every file under .cognee_system (relational, graph, vector, and the
    SQLite -wal file a killed writer can leave), not just cognee_db.
    """
    system = [p for p in LAB_SYSTEM.rglob("*") if p.is_file()]
    return dict(
        system_newest_mtime_ns=max(
            (p.stat().st_mtime_ns for p in system), default=None
        ),
        system_files=len(system),
        cognee_data_files=sum(1 for p in LAB_DATA.rglob("*") if p.is_file()),
    )


def make_run(name):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = RUNS / f"{stamp}-{name}"
    for n in range(2, 1000):
        try:
            (run / "roots").mkdir(parents=True)
            break
        except FileExistsError:
            run = RUNS / f"{stamp}-{name}-{n}"
    (run / "evidence").mkdir()
    head = subprocess.run(
        ["git", "-C", str(REPO), "log", "-1", "--format=%h %s"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(REPO), "status", "--short"], capture_output=True, text=True
    ).stdout.strip()
    (run / "run.json").write_text(
        json.dumps(
            dict(
                started=stamp,
                git_head=head,
                worktree_dirty=bool(dirty),
                lab_store=lab_fingerprint(),
            ),
            indent=2,
        )
    )
    return run


def new_run(args):
    print(make_run(args.name).relative_to(REPO))


def root_embedding(root):
    """The marker's embedding record and the reason this root cannot reopen, if any."""
    try:
        record = read_embedding(root)
    except ValueError as exc:
        return None, str(exc)
    if record is None:
        return None, "pre-profile root: no embedding record"
    return record, reopen_problem(root)


def tokenizer_fix_state(site=None):
    """Reverse dry-run of the tokenizer patch; never applies or reverts it."""
    result = subprocess.run(
        ["patch", "-p1", "-R", "-f", "--dry-run", "-i", str(TOKENIZER_PATCH)],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=site or sysconfig.get_paths()["purelib"],
    )
    return "applied" if result.returncode == 0 else "not applied"


def health(run_arg=None):
    """Gates fail the doctor. Info and warnings never do."""
    gates, info, warnings = {}, {}, []
    gates["repo_root"] = (REPO / "src/cognee_lab/identity/__main__.py").exists()
    gates["python_3_12"] = sys.version_info[:2] == (3, 12)
    try:
        # Metadata only: importing cognee would load the lab .env.
        info["cognee_version"] = package_version("cognee")
    except Exception as exc:  # report, don't crash the doctor
        info["cognee_version"] = f"not installed: {exc}"
    gates["cognee_is_1_6_2"] = info["cognee_version"] == EXPECTED_COGNEE
    gates["jq_available"] = shutil.which("jq") is not None
    gates["cli_parses"] = (
        subprocess.run(CLI + ["--help"], capture_output=True, cwd=REPO).returncode == 0
    )
    if run_arg:
        run = run_dir(run_arg)
        info["run"] = str(run.relative_to(REPO))
        roots_dir = run / "roots"
        roots = (
            sorted(p for p in roots_dir.iterdir() if p.is_dir())
            if roots_dir.is_dir()
            else []
        )
        states = {p.name: root_embedding(p) for p in roots}
        info["root_embeddings"] = {name: record for name, (record, _) in states.items()}
        info["root_problems"] = {
            name: problem for name, (_, problem) in states.items() if problem
        }
        gates["roots_reopen"] = not info["root_problems"]
        if any(r and r["profile"] == "env" for r, _ in states.values()):
            info["tokenizer_fix"] = tokenizer_fix_state()
            if info["tokenizer_fix"] != "applied":
                warnings.append(
                    "tokenizer fix is not applied; env roots fall back to an approximate "
                    "tokenizer (see patches/README.md). Loopback runs are unaffected."
                )
        info["live_cli_pids"] = live_cli_processes(run)
        gates["no_live_cli"] = not info["live_cli_pids"]
    return gates, info, warnings


def doctor(args):
    gates, info, warnings = health(args.run)
    ok = all(gates.values())
    print(json.dumps(dict(ok=ok, warnings=warnings, **gates, **info), indent=2))
    raise SystemExit(0 if ok else 1)


def extract_json(stdout):
    """The CLI prints JSON last; Cognee may print log lines before it."""
    lines = stdout.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("{"):
            try:
                return json.loads("\n".join(lines[i:]))
            except json.JSONDecodeError:
                continue
    return None


def supplies_embedding(cli_args):
    """True for --embedding and every abbreviation argparse accepts, with or without =value."""
    return any(
        len(flag) >= 3 and "--embedding".startswith(flag)
        for flag in (arg.split("=", 1)[0] for arg in cli_args)
    )


def next_stem(run, label):
    n = len(evidence_steps(run)) + 1
    return n, run / "evidence" / f"{n:02d}-{label}"


def record_step(run, n, label, root, status, seconds, has_json):
    with open(run / "evidence" / "steps.tsv", "a", newline="") as handle:
        csv.writer(handle, delimiter="\t").writerow(
            [f"{n:02d}", label, root, status, seconds, has_json]
        )


def drive(args):
    run = run_dir(args.run)
    cli_args = args.cli_args[1:] if args.cli_args[:1] == ["--"] else args.cli_args
    if not cli_args:
        fail("give the CLI command after --, e.g. -- chunked-fixture")
    if "--root" in cli_args:
        fail("drive adds --root itself; name the root with the ROOT argument")
    if cli_args[0] in CREATION_COMMANDS and not supplies_embedding(cli_args):
        # The CLI default is env, which calls the embedding API. Verify offline unless asked.
        cli_args = [*cli_args, "--embedding", "loopback"]
    root = run / "roots" / args.root
    command = CLI + cli_args + ["--root", str(root)]
    n, stem = next_stem(run, args.label)
    stem.with_suffix(".cmd").write_text(
        " ".join(
            [
                "uv run python -m cognee_lab.identity",
                *cli_args,
                "--root",
                str(root.relative_to(REPO)),
            ]
        )
        + "\n"
    )
    started = time.monotonic()
    proc = subprocess.Popen(
        command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        stdout, stderr = proc.communicate(timeout=args.timeout)
        status = str(proc.returncode)
    except subprocess.TimeoutExpired:
        proc.kill()  # only the process this helper started
        stdout, stderr = proc.communicate()
        status = "timeout"
    seconds = round(time.monotonic() - started, 1)
    stem.with_suffix(".stdout").write_text(stdout)
    stem.with_suffix(".stderr").write_text(stderr)
    payload = extract_json(stdout)
    if payload is not None:
        stem.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    record_step(run, n, args.label, args.root, status, seconds, payload is not None)
    print(
        f"step {n:02d} {args.label}: exit={status} {seconds}s "
        f"json={'yes' if payload is not None else 'NO'} -> {stem.relative_to(REPO)}.*"
    )
    if payload is not None and "error" in payload:
        print(f"  error: {payload['error']}: {payload.get('message', '')}")
    raise SystemExit(0 if status == "0" else 1)


def check(args):
    run = run_dir(args.run)
    target = latest_json(run, args.label)
    if target is None:
        log_assertion(
            run,
            "FAIL",
            f"no JSON for step {args.label}",
            args.filter,
            args.description or "",
        )
        print(
            f"FAIL no JSON evidence for step label {args.label!r}: {args.description or args.filter}"
        )
        raise SystemExit(1)
    result = subprocess.run(
        ["jq", "-e", args.filter, str(target)], capture_output=True, text=True
    )
    verdict = "PASS" if result.returncode == 0 else "FAIL"
    log_assertion(run, verdict, target.name, args.filter, args.description or "")
    shown = (result.stdout or result.stderr).strip().replace("\n", " ")[:200]
    print(f"{verdict} {target.name}: {args.description or args.filter}  [{shown}]")
    raise SystemExit(0 if verdict == "PASS" else 1)


def val(args):
    run = run_dir(args.run)
    target = latest_json(run, args.label)
    if target is None:
        fail(f"no JSON evidence for step label {args.label!r}")
    result = subprocess.run(
        ["jq", "-r", args.filter, str(target)], capture_output=True, text=True
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)


def probe(args):
    """Evidence about a live root: marker, data files, vector widths, key leakage.

    The key is read the way the CLI reads it and is never printed or written.
    """
    run = run_dir(args.run)
    root = run / "roots" / args.root
    if not (root / MARKER).exists():
        fail(f"{args.root} is not a root of this run")
    import lancedb

    # Private on purpose: a rename should break probe only, not doctor.
    from cognee_lab.identity.environment import _operator_embedding

    db = lancedb.connect(str(root / "vector"))
    record, _ = root_embedding(root)
    try:
        key = _operator_embedding().get("EMBEDDING_API_KEY", "").strip().encode()
    except ValueError:
        key = b""
    scanned = [p for p in root.rglob("*") if p.is_file()] + [
        p for p in (run / "evidence").iterdir() if p.is_file()
    ]
    payload = dict(
        root=args.root,
        marker=record,
        reopen_problem=reopen_problem(root),
        data_dir_files=sum(1 for p in (root / "data").rglob("*") if p.is_file()),
        vector_dims={
            name: db.open_table(name).schema.field("vector").type.list_size
            for name in db.table_names()
        },
        key_scanned=bool(key),
        scanned_files=len(scanned),
        key_leak=bool(key) and any(key in p.read_bytes() for p in scanned),
        tokenizer_fix=tokenizer_fix_state(),
    )
    n, stem = next_stem(run, args.label)
    stem.with_suffix(".cmd").write_text(f"verify probe {args.root}\n")
    stem.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    record_step(run, n, args.label, args.root, "0", 0, True)
    print(f"step {n:02d} {args.label}: probe -> {stem.relative_to(REPO)}.json")


def cleanup_run(run):
    live = live_cli_processes(run)
    if live:
        fail(f"identity CLI still running against this run (pids {live}); not deleting")
    kept = run / "evidence" / "root-files"
    roots = run / "roots"
    if roots.is_dir():
        for root in sorted(p for p in roots.iterdir() if p.is_dir()):
            # Result/review files sit at the root's top level; stores are subdirectories.
            for item in root.iterdir():
                if item.is_file():
                    (kept / root.name).mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, kept / root.name / item.name)
        shutil.rmtree(roots)
    before = json.loads((run / "run.json").read_text()).get("lab_store")
    verdicts = []
    if before:
        after = lab_fingerprint()
        for key, description in LAB_GUARD:
            if key not in before:  # a run made before this guard field existed
                continue
            verdict = "PASS" if before[key] == after[key] else "FAIL"
            verdicts.append(verdict)
            log_assertion(run, verdict, "run.json", f"lab_store.{key}", description)
    return verdicts


def cleanup(args):
    run = run_dir(args.run)
    verdicts = cleanup_run(run)
    print(
        f"removed {(run / 'roots').relative_to(REPO)}; kept {len(evidence_steps(run))} "
        f"steps of evidence in {(run / 'evidence').relative_to(REPO)}; "
        f"lab store guard {verdicts.count('PASS')} PASS {verdicts.count('FAIL')} FAIL"
    )
    raise SystemExit(1 if "FAIL" in verdicts else 0)


def load_journeys():
    """Every ```bash journey ID [stages=a,b] [env]``` block in features/*.md."""
    journeys = {}
    for path in sorted(FEATURES.glob("*.md")):
        lines = path.read_text().splitlines()
        i = 0
        while i < len(lines):
            match = FENCE.match(lines[i])
            i += 1
            if not match:
                continue
            if match["id"] in journeys:
                fail(f"journey {match['id']} is defined twice ({path.name})")
            body = []
            while i < len(lines) and lines[i].rstrip() != "```":
                body.append(lines[i])
                i += 1
            if i == len(lines):
                fail(f"journey {match['id']} in {path.name} has no closing fence")
            options = match["options"].split()
            stages = next(
                (
                    o.removeprefix("stages=").split(",")
                    for o in options
                    if o.startswith("stages=")
                ),
                [],
            )
            journeys[match["id"]] = dict(
                id=match["id"],
                file=path.name,
                stages=stages,
                env="env" in options,
                body="\n".join(body) + "\n",
            )
    return journeys


def run_journey(journey, stage):
    run = make_run(journey["id"].lower() + (f"-{stage}" if stage else ""))
    env = os.environ | {
        "V": str(SCRIPT),
        "RUN": str(run.relative_to(REPO)),
        "STAGE": stage or "",
    }
    log = run / "evidence" / "journey.log"
    try:
        with open(log, "w") as handle:
            status = subprocess.run(
                ["bash", "-c", PRELUDE + journey["body"]],
                cwd=REPO,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
            ).returncode
    finally:
        cleanup_run(run)
    tsv = run / "evidence" / "assertions.tsv"
    rows = list(csv.reader(tsv.open(), delimiter="\t")) if tsv.exists() else []
    # Blocks have no branches, so every `$V check` line must leave exactly one row;
    # fewer means bash stopped early (syntax error, exit) and the rest never ran.
    expected = sum(
        1
        for line in journey["body"].splitlines()
        if line.lstrip().startswith("$V check")
    )
    got = sum(1 for r in rows if r[1] != "run.json")
    if got != expected or status == 2:
        log_assertion(
            run,
            "FAIL",
            "journey.log",
            f"bash exit {status}",
            f"expected {expected} check rows, got {got}; read evidence/journey.log",
        )
        rows = list(csv.reader(tsv.open(), delimiter="\t"))
    passed = sum(1 for r in rows if r[0] == "PASS")
    failed = [r for r in rows if r[0] == "FAIL"]
    return dict(
        journey=journey["id"],
        stage=stage or "",
        passed=passed,
        failed=len(failed),
        failures=failed,
        run=str(run.relative_to(REPO)),
    )


def journey(args):
    journeys = load_journeys()
    wanted = list(journeys) if args.id == "all" else [args.id]
    if args.id != "all" and args.id not in journeys:
        fail(f"no journey {args.id}; known: {', '.join(journeys)}")
    if args.stage and args.id == "all":
        fail("--stage needs one journey ID")
    skipped = [i for i in wanted if journeys[i]["env"] and not args.include_env]
    if args.id != "all" and skipped:
        fail(f"{args.id} calls the embedding API; add --include-env to run it")
    wanted = [i for i in wanted if i not in skipped]
    gates, _, _ = health()
    if not all(gates.values()):
        fail(f"doctor gates failed: {[k for k, v in gates.items() if not v]}")
    plan = []
    for journey_id in wanted:
        entry = journeys[journey_id]
        if args.stage and args.stage not in entry["stages"]:
            fail(
                f"{journey_id} has stages {entry['stages'] or 'none'}, not {args.stage}"
            )
        for stage in [args.stage] if args.stage else entry["stages"] or [None]:
            plan.append((entry, stage))
    if sys.platform == "darwin":
        try:
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        except OSError:
            pass
    results = [None] * len(plan)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(run_journey, entry, stage): i
            for i, (entry, stage) in enumerate(plan)
        }
        for future in as_completed(futures):
            i = futures[future]
            result = results[i] = future.result()
            print(
                f"{result['journey']} {result['stage']}: {result['passed']} PASS {result['failed']} FAIL",
                flush=True,
            )
    print(f"\n{'journey':8}{'stage':26}{'PASS':>6}{'FAIL':>6}  run")
    for r in results:
        print(
            f"{r['journey']:8}{r['stage']:26}{r['passed']:>6}{r['failed']:>6}  {r['run']}"
        )
        for row in r["failures"]:
            print(f"    FAIL {row[1]}: {row[3] or row[2]}")
    total_pass = sum(r["passed"] for r in results)
    total_fail = sum(r["failed"] for r in results)
    print(f"{'total':34}{total_pass:>6}{total_fail:>6}  {len(results)} runs")
    if skipped:
        print(f"skipped (embedding API, add --include-env): {', '.join(skipped)}")
    raise SystemExit(1 if total_fail else 0)


def main():
    os.chdir(REPO)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)

    p = sub.add_parser("new-run", help="create outputs/verify/<stamp>-NAME")
    p.add_argument("name")
    p.set_defaults(func=new_run)

    p = sub.add_parser("doctor", help="read-only: is this checkout/run worth driving?")
    p.add_argument("run", nargs="?")
    p.set_defaults(func=doctor)

    p = sub.add_parser("drive", help="run one CLI command against RUN/roots/ROOT")
    p.add_argument("run")
    p.add_argument("root")
    p.add_argument("label", help="evidence file label, e.g. fixture, add, reconcile")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("cli_args", nargs=argparse.REMAINDER)
    p.set_defaults(func=drive)

    p = sub.add_parser("check", help="jq -e assertion over a step's JSON, logged")
    p.add_argument("run")
    p.add_argument("label")
    p.add_argument("filter")
    p.add_argument("description", nargs="?")
    p.set_defaults(func=check)

    p = sub.add_parser("val", help="print jq -r over a step's JSON, for later checks")
    p.add_argument("run")
    p.add_argument("label")
    p.add_argument("filter")
    p.set_defaults(func=val)

    p = sub.add_parser(
        "probe", help="record marker, data files, vector widths and key leakage"
    )
    p.add_argument("run")
    p.add_argument("root")
    p.add_argument("label")
    p.set_defaults(func=probe)

    p = sub.add_parser(
        "cleanup", help="delete fixture stores, keep evidence, guard the lab store"
    )
    p.add_argument("run")
    p.set_defaults(func=cleanup)

    p = sub.add_parser("journey", help="run journey blocks from features/*.md, or all")
    p.add_argument("id", help="journey ID such as P1, or all")
    p.add_argument("--stage", help="one fault stage of a journey that lists stages")
    p.add_argument(
        "--include-env",
        action="store_true",
        help="also run journeys that call the embedding API",
    )
    p.add_argument(
        "--jobs", type=int, default=4, help="journey runs to execute in parallel"
    )
    p.set_defaults(func=journey)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
