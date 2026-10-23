# Agent instructions for cognee-science-lab

## Start here

Read [docs/SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) first. It gives the current baseline, the next task, the code map and the commands. [ROADMAP.md](ROADMAP.md) is the stage overview.

## Hard rules

- Do not change, move or delete anything in `.cognee_data/`, `.cognee_system/` or `.env`. These are the user's lab stores and settings.
- Never print a value from `.env`. A key name, an embedding model name or a dimension count is not a secret.
- Do not run commands on, change or delete the reviewed roots under `outputs/stage6_*`. Make a new root for each new fixture.
- The repository is public. Do not commit a secret or a value from `.env`.
- A user auto-mode rule allows deletion under `outputs/`. The user also allows removing a branch's worktree and deleting the branch after the branch is merged into `main` (see "Land a change"). Ask the user before any other deletion.

## Embedding profiles

- Fixture creation takes `--embedding env|loopback`. The CLI default is `env`, which calls the NVIDIA embedding API that `.env` names.
- Use `env` only for a real fixture run that the user wants. Use `loopback` for everything else.
- pytest and the verify journeys use `loopback` already.

## Verify a change

The user agreed this routine on 2026-10-21.

1. On every commit, run `uv run pytest -q -m 'not integration'`. CI runs the same command on every push, then the occurrence check and the chain check at their default bounds (the unit suite covers only small worlds).
2. For a change that touches `RecordStore` or its callers, run `uv run python support/ledger_check.py`. Read `.claude/skills/identity-ledger/SKILL.md` first. For a change to `src/cognee_lab/identity/admission.py`, run `uv run python support/occurrence_check.py` and `uv run python support/occurrence_check.py --mutants`. For a change to `admission.py`, `records.py`, `chains.py` (the citation rules and the withholding closure) or `erasure.py`, also run `uv run python support/chain_check.py` and `uv run python support/chain_check.py --mutants`.
3. For each feature change, run the changed feature's journeys with `.claude/skills/verify/scripts/verify.py journey <ID>`. The feature files in `.claude/skills/verify/features/` list the journeys. Read `.claude/skills/verify/SKILL.md` first.
4. Once per checkpoint, before the merge to `main`, run `.claude/skills/verify/scripts/verify.py journey all`.
5. Run the integration suite, `uv run pytest -q -m integration`, only on a local machine. It takes about 10 minutes.

## Land a change

Follow [.agents/playbooks/landing-on-main.md](.agents/playbooks/landing-on-main.md). In short:

1. Work on a branch off `main`.
2. Review the branch with `/pstack:thermos`. Fix each finding, or dismiss it with a reason.
3. Run the unit tests on the branch. At a checkpoint, also run `verify.py journey all`.
4. Merge with `git merge --ff-only <branch>`. Do not open a pull request.
5. Push `main` only when the user asks.
6. After the merge, remove the branch's worktree with `git worktree remove <path>` and delete the branch with `git branch -d <branch>`. Do the same for a harness `worktree-agent-*` branch whose commits are on `main`. Never pass `--force` or `-D`. If either command refuses, or an agent still works in the worktree, ask the user.

## Update the docs after each checkpoint

- `docs/SESSION_HANDOFF.md`: baseline, status, evidence and next task.
- `ROADMAP.md`: "Last revised", "Progress at a glance" and a dated revision entry.
- The fixture guide for the checkpoint under `docs/`.
- `results/cognee_knowledge_integration_playbook.md`: a dated evidence section. Add a lesson to the register only if it transfers to other integrations.

Keep dated history. Say who ran each result and where: the user, or the assistant on the user's Mac.
