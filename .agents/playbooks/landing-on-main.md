---
extends: opening-a-pr
when: Landing finished work in cognee-science-lab, where reviewed branches merge into main locally and no pull request is opened.
---

# Landing on main

This repository has one maintainer and no pull requests. A branch lands on `main` by a local merge, after an independent review.

- **Replace** "Work from a git worktree off main." with: Work on a branch off `main`. A worktree has no `.env`, because git ignores it, so fixture runs with `--embedding env` must run in the main checkout.
- **Replace** "Conventional Commits `type(scope): subject`, no trailing period." with: Use this repository's style, a short plain sentence with no type prefix.
- **In** "Run `/deslop` over the diff before commit and `/no-comments` before review." add: The review is `/pstack:thermos` over `main..<branch>`. Also run `/pstack:interrogate` when the design is contested. Fix each finding, or dismiss it with a concrete reason, before the merge. If no independent reviewer can run, the merge waits.
- **Replace** "Open every PR ready, never as a draft." with: Do not open a pull request. After the review passes, run `uv run pytest -q -m 'not integration'` on the branch. If the branch ends a checkpoint, also run `.claude/skills/verify/scripts/verify.py journey all`. Then merge into `main` with `git merge --ff-only <branch>`. After a checkpoint merges, push `main` and check CI; push at other times only when the operator asks.
- **Replace** "Post the URL and keep building." with: Report the merged commit hash in place of a URL. Then remove the branch's worktree with `git worktree remove <path>` and delete the branch with `git branch -d <branch>`, never forced. A harness lock (`claude agent <name> (pid ...)`) on a finished agent's clean worktree is released with `git worktree unlock <path>` first; a branch merged into `main` but not into the checkout's HEAD takes `git branch -u main <branch>` first. Otherwise, if either refuses, ask the operator.
