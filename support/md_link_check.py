"""Check that every relative Markdown link and anchor in the repository resolves.

Reads each Markdown file that git tracks, skips fenced code blocks and inline
code, and checks each relative link target: the file or directory must exist,
and a #anchor must match a heading slug in the target file, computed the way
GitHub computes it. External links (http, https, mailto) are not fetched.

    uv run python support/md_link_check.py
    uv run python support/md_link_check.py docs/SESSION_HANDOFF.md ROADMAP.md

Exits 1 and prints one line per broken link, or exits 0 with a count.
"""

import re
import subprocess
import sys
from functools import cache
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"(?<!!)\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r"""<a\s+(?:name|id)=["']([^"']+)["']""")


def prose_lines(path: Path):
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield number, line


def slug(heading: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


@cache
def anchors(path: Path) -> frozenset[str]:
    seen: dict[str, int] = {}
    found = set()
    for _, line in prose_lines(path):
        found.update(HTML_ANCHOR.findall(line))
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return frozenset(found)


def broken_links(path: Path):
    for number, line in prose_lines(path):
        text = INLINE_CODE.sub("", line)
        for target in LINK.findall(text) + IMAGE.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            file_part, _, anchor = target.partition("#")
            resolved = (path.parent / unquote(file_part)).resolve() if file_part else path
            if not resolved.exists():
                yield number, target, "missing file"
            elif anchor and resolved.suffix == ".md" and unquote(anchor) not in anchors(resolved):
                yield number, target, "missing anchor"


def tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [ROOT / name for name in out.splitlines() if (ROOT / name).exists()]


def main(argv: list[str]) -> int:
    files = [Path(name).resolve() for name in argv] if argv else tracked_markdown()
    problems = 0
    links = 0
    for path in files:
        for number, line in prose_lines(path):
            text = INLINE_CODE.sub("", line)
            links += len(LINK.findall(text)) + len(IMAGE.findall(text))
        for number, target, reason in broken_links(path):
            problems += 1
            print(f"{path.relative_to(ROOT)}:{number}: {reason}: {target}")
    if problems:
        print(f"FAIL: {problems} broken of {links} links in {len(files)} files")
        return 1
    print(f"PASS: {links} links in {len(files)} files resolve (external links not fetched)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
