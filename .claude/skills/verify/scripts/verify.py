#!/usr/bin/env -S uv run python
"""Drive the Stage 6 identity CLI in isolated roots and keep the evidence.

Run from the repository root:

    V=.claude/skills/verify/scripts/verify.py
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
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RUNS = REPO / "outputs" / "verify"
CLI = [sys.executable, "-m", "cognee_lab.identity"]
EXPECTED_COGNEE = "1.6.2"


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


def new_run(args):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = RUNS / f"{stamp}-{args.name}"
    (run / "roots").mkdir(parents=True)
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
            dict(started=stamp, git_head=head, worktree_dirty=bool(dirty)), indent=2
        )
    )
    print(run.relative_to(REPO))


def doctor(args):
    checks = {}
    checks["repo_root"] = (REPO / "src/cognee_lab/identity/__main__.py").exists()
    checks["python_3_12"] = sys.version_info[:2] == (3, 12)
    try:
        import cognee

        checks["cognee_version"] = cognee.__version__
    except Exception as exc:  # report, don't crash the doctor
        checks["cognee_version"] = f"import failed: {exc}"
    checks["cognee_is_1_6_2"] = checks["cognee_version"] == EXPECTED_COGNEE
    checks["jq_available"] = shutil.which("jq") is not None
    checks["cli_parses"] = (
        subprocess.run(CLI + ["--help"], capture_output=True, cwd=REPO).returncode == 0
    )
    if args.run:
        run = run_dir(args.run)
        checks["run"] = str(run.relative_to(REPO))
        roots = sorted(p for p in (run / "roots").iterdir() if p.is_dir())
        checks["roots"] = {
            p.name: (p / "stage6-fixture.json").exists() for p in roots
        }
        checks["roots_are_fixtures"] = all(checks["roots"].values())
        checks["live_cli_pids"] = live_cli_processes(run)
        checks["no_live_cli"] = not checks["live_cli_pids"]
    ok = all(v for k, v in checks.items() if isinstance(v, bool))
    print(json.dumps(dict(ok=ok, **checks), indent=2))
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


def drive(args):
    run = run_dir(args.run)
    cli_args = args.cli_args[1:] if args.cli_args[:1] == ["--"] else args.cli_args
    if not cli_args:
        fail("give the CLI command after --, e.g. -- chunked-fixture")
    if "--root" in cli_args:
        fail("drive adds --root itself; name the root with the ROOT argument")
    root = run / "roots" / args.root
    command = CLI + cli_args + ["--root", str(root)]
    n = len(evidence_steps(run)) + 1
    stem = run / "evidence" / f"{n:02d}-{args.label}"
    stem.with_suffix(".cmd").write_text(
        " ".join(["uv run python -m cognee_lab.identity", *cli_args, "--root", str(root.relative_to(REPO))])
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
    with open(run / "evidence" / "steps.tsv", "a", newline="") as handle:
        csv.writer(handle, delimiter="\t").writerow(
            [f"{n:02d}", args.label, args.root, status, seconds, payload is not None]
        )
    print(
        f"step {n:02d} {args.label}: exit={status} {seconds}s "
        f"json={'yes' if payload is not None else 'NO'} -> {stem.relative_to(REPO)}.*"
    )
    if payload is not None and "error" in payload:
        print(f"  error: {payload['error']}: {payload.get('message', '')}")
    raise SystemExit(0 if status == "0" else 1)


def check(args):
    run = run_dir(args.run)
    matches = [
        p.with_suffix(".json")
        for p in evidence_steps(run)
        if p.stem.split("-", 1)[1] == args.label
    ]
    if not matches or not matches[-1].exists():
        fail(f"no JSON evidence for step label {args.label!r}")
    target = matches[-1]
    result = subprocess.run(
        ["jq", "-e", args.filter, str(target)], capture_output=True, text=True
    )
    verdict = "PASS" if result.returncode == 0 else "FAIL"
    with open(run / "evidence" / "assertions.tsv", "a", newline="") as handle:
        csv.writer(handle, delimiter="\t").writerow(
            [verdict, target.name, args.filter, args.description or ""]
        )
    shown = (result.stdout or result.stderr).strip().replace("\n", " ")[:200]
    print(f"{verdict} {target.name}: {args.description or args.filter}  [{shown}]")
    raise SystemExit(0 if verdict == "PASS" else 1)


def cleanup(args):
    run = run_dir(args.run)
    live = live_cli_processes(run)
    if live:
        fail(f"identity CLI still running against this run (pids {live}); not deleting")
    kept = run / "evidence" / "root-files"
    roots = run / "roots"
    for root in sorted(p for p in roots.iterdir() if p.is_dir()):
        # Result/review files sit at the root's top level; stores are subdirectories.
        for item in root.iterdir():
            if item.is_file():
                (kept / root.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, kept / root.name / item.name)
    shutil.rmtree(roots)
    steps = len(evidence_steps(run))
    print(f"removed {roots.relative_to(REPO)}; kept {steps} steps of evidence in "
          f"{(run / 'evidence').relative_to(REPO)}")


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

    p = sub.add_parser("cleanup", help="delete fixture stores, keep evidence")
    p.add_argument("run")
    p.set_defaults(func=cleanup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
