"""Refuse a commit that stages an env file or adds a secret value from one.

Install once per checkout as the pre-commit hook:

    printf '#!/bin/sh\nexec python3 support/secret_guard.py\n' > .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

The secrets are the values of every KEY, SECRET, PASSWORD or TOKEN setting in
`.env` and in any copy of it at the repo root (`.env~`, `.env.bak`, `#.env#`
and the like), except `.env.example`. The guard prints the setting's name and
the staged file, never the value. Standard library only, so the hook needs no
environment.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SECRET_NAME = re.compile(r"(KEY|SECRET|PASSWORD|TOKEN)(?!IZER)")
ENV_COPY = re.compile(r"^(\.env.*|#\.env.*#|\.#\.env.*)$")
MIN_LENGTH = 12


def env_copies() -> list[Path]:
    return [
        p for p in REPO.iterdir()
        if p.is_file() and ENV_COPY.match(p.name) and p.name != ".env.example"
    ]


def secrets() -> dict[str, str]:
    found = {}
    for path in env_copies():
        for line in path.read_text(errors="replace").splitlines():
            name, sep, value = line.partition("=")
            name = name.strip().removeprefix("export ").strip()
            value = value.strip().strip("'\"")
            if sep and SECRET_NAME.search(name) and len(value) >= MIN_LENGTH:
                found.setdefault(value, f"{path.name}:{name}")
    return found


def git(*args) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def main() -> int:
    problems = []
    for path in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines():
        name = Path(path).name
        if ENV_COPY.match(name) and name != ".env.example":
            problems.append(f"{path} is an env file")
    added = [
        line[1:]
        for line in git("diff", "--cached", "-U0", "--no-color").splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    staged = "\n".join(added)
    for value, where in secrets().items():
        if value in staged:
            files = git("diff", "--cached", "--name-only", "-G", re.escape(value)).split()
            problems.append(f"the value of {where} is staged in {', '.join(files) or 'a file'}")
    for problem in problems:
        print(f"secret_guard: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
