# Agent instructions for cognee-science-lab

## Start here

Read [docs/SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md) first. It gives the current baseline, the next task, the code map and the commands. [ROADMAP.md](ROADMAP.md) is the stage overview.

## Hard rules

- Do not change, move or delete anything in `.cognee_data/`, `.cognee_system/` or `.env`. These are the user's lab stores and settings.
- Never print a value from `.env`. A key name, an embedding model name or a dimension count is not a secret.
- Do not run commands on, change or delete the reviewed roots under `outputs/stage6_*`. Make a new root for each new fixture.
- The repository is public. Do not commit a secret or a value from `.env`.
- A user auto-mode rule allows deletion under `outputs/`. Ask the user before any other deletion.

## Embedding profiles

- Fixture creation takes `--embedding env|loopback`. The CLI default is `env`, which calls the NVIDIA embedding API that `.env` names.
- Use `env` only for a real fixture run that the user wants. Use `loopback` for everything else.
- pytest and the verify journeys use `loopback` already.

## Verify a change

1. Run `uv run pytest -q -m 'not integration'`. CI runs the same command on every push.
2. For a change to `src/cognee_lab/identity/`, run `.claude/skills/verify/scripts/verify.py journey all`. Read `.claude/skills/verify/SKILL.md` first.
3. For a change that touches `RecordStore` or its callers, run `uv run python support/ledger_check.py`. Read `.claude/skills/identity-ledger/SKILL.md` first.
4. Run the integration suite, `uv run pytest -q -m integration`, only on a local machine. It takes about 10 minutes.

## Land a change

Follow [.agents/playbooks/landing-on-main.md](.agents/playbooks/landing-on-main.md). In short:

1. Work on a branch off `main`.
2. Review the branch with `/pstack:thermos`. Fix each finding, or dismiss it with a reason.
3. Run the unit tests on the branch.
4. Merge with `git merge --ff-only <branch>`. Do not open a pull request.
5. Push `main` only when the user asks.

## Update the docs after each checkpoint

- `docs/SESSION_HANDOFF.md`: baseline, status, evidence and next task.
- `ROADMAP.md`: "Last revised", "Progress at a glance" and a dated revision entry.
- The fixture guide for the checkpoint under `docs/`.
- `results/cognee_knowledge_integration_playbook.md`: a dated evidence section. Add a lesson to the register only if it transfers to other integrations.

Keep dated history. Say who ran each result and where: the user, or the assistant on the user's Mac.
