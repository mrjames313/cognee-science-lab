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
    read_fixture,
)
from .chain_fixture import CITATIONS
from .entity_edit import ENTITY_CASES
from .forget import FAULT_STAGES as FORGET_STAGES
from .glossary_fixture import CASES as GLOSSARY_CASES
from .glossary_fixture import COMMANDS as GLOSSARY_COMMANDS
from .glossary_fixture import REFRESH_FAULT
from .glossary_fixture import REVIEW_COMMANDS as REVIEWS
from .glossary_fixture import SHARED_COMMANDS as GLOSSARY_SHARED
from .occurrence_fixture import COMMANDS as OCCURRENCE_COMMANDS
from .replace import FAULT_STAGES as REPLACE_STAGES
from .replace import TEXT_FAULT_STAGES
from .withdraw import FAULT_STAGES as WITHDRAW_STAGES

PUBLISH_STAGES = ("nodes", "identity_edges", "verification")
UNCHANGED_TEXT_STAGES = tuple(s for s in REPLACE_STAGES if s not in TEXT_FAULT_STAGES)
# The fault stages of the operation each command runs. A command not listed
# here publishes.
COMMAND_FAULT_STAGES = {
    "revise": UNCHANGED_TEXT_STAGES,
    "reconfirm": UNCHANGED_TEXT_STAGES,
    "replace-decision": UNCHANGED_TEXT_STAGES,
    "cite-record": UNCHANGED_TEXT_STAGES,
    "replace-citation": UNCHANGED_TEXT_STAGES,
    "edit-text": REPLACE_STAGES,
    **dict.fromkeys(OCCURRENCE_COMMANDS, REPLACE_STAGES),
    "edit-glossary": (*REPLACE_STAGES, REFRESH_FAULT),
    "edit-entity": (),
    "refresh-dependents": (REFRESH_FAULT,),
    "withdraw": WITHDRAW_STAGES,
    "forget": FORGET_STAGES,
}
REVISION_COMMANDS = {
    "revise",
    "edit-text",
    "forget",
    "readd",
    "edit-glossary",
    "reconfirm",
    "replace-decision",
    "cite-record",
    "replace-citation",
    *OCCURRENCE_COMMANDS,
}


def cited_record(value):
    """`--cite SOURCE:RECORD`: a fixture source label and a record key."""
    label, _, record = value.partition(":")
    if not label or not record:
        raise argparse.ArgumentTypeError("use SOURCE:RECORD, for example doc01:v02")
    return label, record


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
            *GLOSSARY_COMMANDS,
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
        choices=["doc01", "doc02", "glossary", "doc03"],
        default="doc01",
        help="Selected original document in the isolated fixture",
    )
    parser.add_argument(
        "--case",
        choices=[*sorted(GLOSSARY_CASES), *ENTITY_CASES],
        help="edit-glossary: which captured glossary edit to make "
        f"({', '.join(sorted(GLOSSARY_CASES))}); edit-entity: which outside "
        f"edit of the Entity doc01 reads ({', '.join(ENTITY_CASES)})",
    )
    parser.add_argument(
        "--decision",
        help="reconfirm, replace-decision and replace-citation only: the withheld "
        "decision of doc01 or doc03",
    )
    answer = parser.add_mutually_exclusive_group()
    answer.add_argument(
        "--cite",
        type=cited_record,
        metavar="SOURCE:RECORD",
        help="replace-citation only: cite this record as it is now instead",
    )
    answer.add_argument(
        "--drop",
        action="store_true",
        help="replace-citation only: remove the decision instead",
    )
    parser.add_argument(
        "--citation",
        choices=CITATIONS,
        help="cite-record only: which refused saved-record citation to try",
    )
    parser.add_argument(
        "--chain",
        action="store_true",
        help="glossary-fixture only: add doc03, whose decisions cite doc01's",
    )
    parser.add_argument(
        "--fault-stage",
        choices=[
            *PUBLISH_STAGES,
            *WITHDRAW_STAGES,
            *FORGET_STAGES,
            *REPLACE_STAGES,
            REFRESH_FAULT,
        ],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="forget only: report what the forget would remove, with the token "
        "to confirm, and write nothing",
    )
    parser.add_argument(
        "--confirm",
        metavar="TOKEN",
        help="forget only: the dry run's token, required when the forget "
        "removes other sources' decisions",
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
    if args.command in REVISION_COMMANDS and args.expected_revision is None:
        parser.error(f"{args.command} requires --expected-revision")
    cases = {"edit-glossary": GLOSSARY_CASES, "edit-entity": ENTITY_CASES}
    if args.command in cases and args.case not in cases[args.command]:
        parser.error(
            f"{args.command} requires --case, one of "
            f"{', '.join(sorted(cases[args.command]))}"
        )
    if args.case is not None and args.command not in cases:
        parser.error("--case applies to edit-glossary and edit-entity only")
    if args.command in REVIEWS and args.decision is None:
        parser.error(f"{args.command} requires --decision")
    if (args.command == "replace-citation") != bool(args.cite or args.drop):
        parser.error(
            "replace-citation requires --cite or --drop, which apply to it only"
        )
    if (args.command == "cite-record") != (args.citation is not None):
        parser.error("cite-record requires --citation, which applies to it only")
    if args.chain and args.command != "glossary-fixture":
        parser.error("--chain applies to glossary-fixture only")
    allowed = COMMAND_FAULT_STAGES.get(args.command, PUBLISH_STAGES)
    if args.fault_stage and args.fault_stage not in allowed:
        parser.error(
            f"Fault stage {args.fault_stage} is not a stage of {args.command}; "
            f"its stages are {', '.join(allowed)}"
        )
    if args.dependent and args.command != "multi-fixture":
        parser.error("--dependent applies to multi-fixture only")
    if (args.dry_run or args.confirm) and args.command != "forget":
        parser.error("--dry-run and --confirm apply to forget only")
    if args.dry_run and (args.confirm or args.fault_stage):
        parser.error("A dry run takes neither --confirm nor --fault-stage")
    creating = args.command in CREATION_COMMANDS
    if creating and root.exists():
        parser.error("Fixture root already exists; choose a new directory")
    if not creating and not (root / MARKER).exists():
        parser.error("Root is not an isolated Stage 6 fixture directory")
    environment = ExitStack()
    made = False
    try:
        if creating:
            create_root(root, args.embedding or "env", args.command)
            made = True
        elif error := _reopen_error(args, root):
            parser.error(error)
        kind = args.command if creating else read_fixture(root)
        if kind is None and args.command in {"reconcile", "forget", "readd"}:
            parser.error("Root predates fixture kinds; regenerate it")
        environment.enter_context(fixture_environment(root))
    except ValueError as exc:
        if made:
            (root / MARKER).unlink()
            root.rmdir()
        parser.error(str(exc))
    with environment:
        if args.command in GLOSSARY_COMMANDS or (
            args.command in GLOSSARY_SHARED and kind == "glossary-fixture"
        ):
            from .glossary_fixture import run
        elif args.command in OCCURRENCE_COMMANDS:
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
            args.command == "reconcile" and kind in {"multi-fixture", "chunked-fixture"}
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
        # A forget that completed but left a dependent unrevised.
        if result.get("dependents_failed"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
