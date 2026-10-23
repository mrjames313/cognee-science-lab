"""Census of what the identity integration's code, tests and history are for.

Attributes every line of src/cognee_lab/identity to one primary purpose, then
counts tests, verify journeys and git churn by the same split. The method is
in docs/integration_design_snapshot_2026-10-23.md, "Purpose census". The
labels are judgments from each function's docstring and callers; edit
DEFAULT, OVERRIDE and the scenario sets when the code changes. A module
missing from them is reported as unclassified, never guessed.

Run from the repository root: uv run python scripts/purpose_census.py [-v]
"""

import ast
import collections
import pathlib
import re
import subprocess
import sys

PACKAGE = pathlib.Path("src/cognee_lab/identity")

CATEGORIES = {
    "P": "provenance checks: record or check what a record came from",
    "C.own": "change: retirement by native ownership (withdraw, forget, re-add)",
    "C.dep": "change: dependency on recorded inputs (withholding, refresh)",
    "C.cont": "change: revision continuity rules and replace orchestration",
    "C.text": "change: native rebuild for a new text",
    "L": "ledger and crash recovery",
    "B": "publish: compile, write and verify one revision's overlay",
    "Q": "retrieval probe",
    "M": "record model and self-consistency",
    "F": "CLI, environment, schema export",
    "S.first": "scenario fixtures: first publication",
    "S.change": "scenario fixtures: a change after publication",
}
CORE = ("P", "C.own", "C.dep", "C.cont", "C.text", "L", "B", "Q", "M")

DEFAULT = {
    "admission": "C.cont", "publish": "B", "storage": "L", "retrieve": "Q",
    "replace": "C.cont", "withholding": "C.dep", "forget": "C.own",
    "validation": "P", "text_changes": "C.text", "retirement": "C.own",
    "models": "M", "revisions": "C.cont", "withdraw": "C.own",
    "registered": "P", "stages": "L", "native": "B", "schema": "F",
    "environment": "F", "__main__": "F", "fixture_embeddings": "F",
    "__init__": "F",
}
SCENARIO_FIRST = {"fixture", "captured_chunks", "captured_text"}
SCENARIO_CHANGE = {
    "multisource", "glossary_fixture", "text_fixture", "occurrence_fixture",
    "forget_fixture", "kind_change", "resolved_retirement", "reinterpretation",
    "group_regrouping", "captured_revision", "occurrence_addition",
}
# Dotted names reach methods and nested functions, e.g. "replace.withhold".
OVERRIDE = {
    "admission": {
        "check_input_kinds": "P", "check_corpus_inputs_exist": "P",
        "check_absent_from_graph": "B", "entity_ids_named": "B",
        "check_source_identity": "M",
        "check_foreign_inputs": "C.dep", "foreign_citations": "C.dep",
        "attested_inputs": "C.dep", "check_reconfirmations": "C.dep",
        "without_range": "C.dep",
        "check_removed_entity_ids": "C.own", "replacement_entity_id": "C.own",
        "check_readd_entity_ids": "C.own", "admit_readd": "C.own",
    },
    "publish": {
        "Publisher.withheld_for": "C.dep", "Publisher.withdraw": "C.own",
        "Publisher.forget": "C.own", "Publisher.replace": "C.cont",
        "Publisher.admit_inputs": "P", "Publisher.preflight": "P",
        "Publisher.refuse_owned_retry": "L", "Publisher.reconcile": "L",
        "Publisher._publish": "L", "Publisher.forgotten_row": "C.own",
        "Publisher.admit_readd": "C.own", "Publisher.readd": "C.own",
    },
    "retrieve": {
        "live_drift": "P", "valid_sources": "P", "is_served": "L",
        "held_by": "C.dep", "live_held": "C.dep", "withheld_now": "C.dep",
        "withholding_status": "C.dep",
    },
    "replace": {
        "replace.retire_and_verify": "C.own", "replace.withhold": "C.dep",
        "replace.clean_withholdings": "C.dep",
    },
    "revisions": {
        "next_revision": "C.dep", "remapped": "C.dep", "written_ranges": "C.dep",
        "refresh_dependents": "C.dep", "reconfirmed": "C.dep",
    },
    "text_changes": {
        "reject_sole_owned_readers": "C.dep", "reject_unsafe_cascades": "C.own",
    },
    "validation": {
        "IntentError": "M", "fresh_mention_id": "M", "fresh_entity_id": "M",
        "validate_uses": "M", "Reason": "C.dep", "stronger": "C.dep",
        "is_foreign": "C.dep", "withheld_by": "C.dep",
    },
    "models": {
        name: "P"
        for name in (
            "Range", "Occurrence", "SourceTextInput", "ChunkInput",
            "TextSpanInput", "CorpusObjectInput", "SavedRecordInput", "Producer",
        )
    },
    "registered": {"write_registered": "B", "write_text": "C.text"},
    "native": {"mention_fact": "Q", "MentionFact": "Q"},
}
# Tests and journeys that exercise no change after publication.
FIRST_TESTS = {
    "test_identity_native", "test_identity_storage", "test_identity_environment",
    "test_identity_records", "test_identity_retrieval", "test_identity_ledger_check",
    "test_identity_chunks", "test_identity_chunks_native",
}
FIRST_JOURNEY_FEATURES = {"publication-and-retrieval"}


def module_category(stem):
    if stem in SCENARIO_FIRST:
        return "S.first"
    if stem in SCENARIO_CHANGE:
        return "S.change"
    return DEFAULT.get(stem)


def line_labels(path, default):
    text = path.read_text()
    labels = [default] * (len(text.splitlines()) + 1)
    overrides = OVERRIDE.get(path.stem, {})

    def walk(nodes, prefix):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                if name in overrides:
                    labels[node.lineno : node.end_lineno + 1] = [overrides[name]] * (
                        node.end_lineno - node.lineno + 1
                    )
                walk(node.body, name + ".")

    walk(ast.parse(text).body, "")
    return labels[1:]


def code_census():
    lines, per_module, unclassified = collections.Counter(), {}, []
    for path in sorted(PACKAGE.glob("*.py")):
        default = module_category(path.stem)
        if default is None:
            unclassified.append(path.stem)
            continue
        counts = collections.Counter(line_labels(path, default))
        lines.update(counts)
        per_module[path.stem] = counts
    return lines, per_module, unclassified


def test_census():
    counts = collections.Counter()
    for path in pathlib.Path("tests").glob("test_*.py"):
        n = len(re.findall(r"^(?:async )?def test_", path.read_text(), re.M))
        counts["first" if path.stem in FIRST_TESTS else "change"] += n
    return counts


def journey_census():
    counts, fault = collections.Counter(), 0
    for path in pathlib.Path(".claude/skills/verify/features").glob("*.md"):
        text = path.read_text()
        n = len(re.findall(r"^```bash journey", text, re.M))
        counts["first" if path.stem in FIRST_JOURNEY_FEATURES else "change"] += n
        titles = re.findall(r"^\*\*[A-Z]+[0-9]+ ([^.*]*)", text, re.M)
        fault += sum(bool(re.search(r"fault|fail|interrupt", t)) for t in titles)
    return counts, fault


def churn_census():
    log = subprocess.run(
        ["git", "log", "--numstat", "--format=", "HEAD", "--", str(PACKAGE)],
        capture_output=True, text=True, check=True,
    ).stdout
    counts = collections.Counter()
    for row in log.splitlines():
        parts = row.split("\t")
        if len(parts) == 3 and parts[0] != "-":
            category = module_category(pathlib.Path(parts[2]).stem) or "unclassified"
            counts[category] += int(parts[0]) + int(parts[1])
    return counts


def main():
    lines, per_module, unclassified = code_census()
    core = sum(lines[c] for c in CORE)
    print(f"Code lines by purpose (core = {core}):")
    for category, meaning in CATEGORIES.items():
        share = f"{100 * lines[category] / core:5.1f}%" if category in CORE else "      "
        print(f"  {category:8} {lines[category]:6} {share}  {meaning}")
    if unclassified:
        print("Unclassified modules:", ", ".join(unclassified))
    print("Tests:", dict(test_census()))
    journeys, fault = journey_census()
    print("Journeys:", dict(journeys), f"of which fault or recovery: {fault}")
    print("Churn by module default category:", dict(churn_census()))
    if "-v" in sys.argv:
        for stem, counts in per_module.items():
            print(f"  {stem}: {dict(counts)}")


if __name__ == "__main__":
    main()
