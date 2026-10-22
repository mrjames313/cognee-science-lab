"""Isolated initial fixture commands. Never reset or open the user's lab store."""

import argparse
import asyncio
import json
import inspect
from contextlib import ExitStack
from pathlib import Path

from .environment import (
    CREATION_COMMANDS,
    MARKER,
    create_root,
    fixture_environment,
    read_embedding,
)
from .forget import STAGES as FORGET_STAGES
from .occurrence_fixture import COMMANDS as OCCURRENCE_COMMANDS

TEXT_COMMANDS = {"edit-text", *OCCURRENCE_COMMANDS}


def _reopen_error(args, root: Path) -> str | None:
    recorded = read_embedding(root)
    if recorded is None:
        if args.command not in {"status", "retrieve"}:
            return "Root predates embedding profiles; only status and retrieve open it"
        if args.embedding == "loopback":
            return "Root predates embedding profiles; its vectors use .env embeddings"
        return None
    if args.embedding not in (None, recorded["profile"]):
        return f"Root was created with --embedding {recorded['profile']}"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "fixture",
            "multi-fixture",
            "chunked-fixture",
            "revise",
            "edit-text",
            *OCCURRENCE_COMMANDS,
            "withdraw",
            "forget",
            "readd",
            "retrieve",
            "status",
            "reconcile",
        ],
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--query", default="What does HC limit?")
    parser.add_argument(
        "--expected-revision",
        type=int,
        help="Required saved revision guard for revision-changing commands",
    )
    parser.add_argument(
        "--source",
        choices=["doc01", "doc02"],
        default="doc01",
        help="Selected original document in the isolated fixture",
    )
    parser.add_argument(
        "--fault-stage",
        choices=[
            "nodes",
            "identity_edges",
            "verification",
            "withdraw_contributions",
            "withdraw_owners",
            "withdraw_verification",
            *FORGET_STAGES,
            "replace_saved",
            "replace_registered",
            "replace_published",
            "replace_retired",
            "replace_verification",
            "text_removed",
            "text_registered",
            "text_chunks",
        ],
    )
    parser.add_argument(
        "--dependent",
        action="store_true",
        help="multi-fixture only: doc02 lists doc01's text and private singleton "
        "as inputs of its resolution, so doc01 has a dependent",
    )
    parser.add_argument(
        "--embedding",
        choices=["env", "loopback"],
        help="Embedding profile. Creation records it (default env: EMBEDDING_* from "
        "the repo .env or COGNEE_ENV_FILE); reopening refuses a different one.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if (
        args.command in {"revise", "edit-text", "forget", "readd", *OCCURRENCE_COMMANDS}
        and args.expected_revision is None
    ):
        parser.error(f"{args.command} requires --expected-revision")
    if args.fault_stage:
        if args.command in TEXT_COMMANDS:
            if not args.fault_stage.startswith(("text_", "replace_")):
                parser.error("Fault stage does not match the selected operation")
        elif args.fault_stage.startswith("text_"):
            parser.error("Text failure boundaries require a text-changing command")
        prefix = {
            "withdraw": "withdraw_",
            "forget": "forget_",
            "revise": "replace_",
        }.get(args.command)
        if (prefix and not args.fault_stage.startswith(prefix)) or (
            not prefix
            and args.command not in TEXT_COMMANDS
            and args.fault_stage.startswith(("withdraw_", "replace_", "forget_"))
        ):
            parser.error("Fault stage does not match the selected operation")
    if args.dependent and args.command != "multi-fixture":
        parser.error("--dependent applies to multi-fixture only")
    creating = args.command in CREATION_COMMANDS
    if creating and root.exists():
        parser.error("Fixture root already exists; choose a new directory")
    if not creating and not (root / MARKER).exists():
        parser.error("Root is not an isolated Stage 6 fixture directory")
    environment = ExitStack()
    made = False
    try:
        if creating:
            create_root(root, args.embedding or "env")
            made = True
        elif error := _reopen_error(args, root):
            parser.error(error)
        environment.enter_context(fixture_environment(root))
    except ValueError as exc:
        if made:
            (root / MARKER).unlink()
            root.rmdir()
        parser.error(str(exc))
    with environment:
        if args.command in OCCURRENCE_COMMANDS:
            from .occurrence_fixture import run
        elif args.command == "edit-text":
            from .text_fixture import run
        elif args.command == "revise":
            from .revisions import run
        elif args.command in {
            "multi-fixture",
            "chunked-fixture",
            "withdraw",
            "forget",
            "readd",
        } or (
            args.command == "reconcile" and (root / "multi-fixture-info.json").exists()
        ):
            from .multisource import run
        else:
            from .fixture import run

        async def execute():
            try:
                return await run(args, root)
            finally:
                publisher = getattr(args, "_fixture_publisher", None)
                if publisher is not None:
                    # This CLI owns the isolated stores. Close before interpreter
                    # teardown; never rely on object-finalizer order for durability.
                    for engine in (publisher.vector, publisher.graph):
                        close = getattr(engine, "close", None)
                        if close is not None:
                            closing = close()
                            if inspect.isawaitable(closing):
                                await closing

        try:
            result = asyncio.run(execute())
        except Exception as exc:
            report = {"error": type(exc).__name__, "message": str(exc)}
            if getattr(exc, "details", None) is not None:
                report["details"] = exc.details
            print(json.dumps(report, default=str))
            raise SystemExit(1) from exc
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
