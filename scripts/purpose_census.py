"""Census of what the identity integration's code, tests and history are for.

Attributes every line of src/cognee_lab/identity to one primary purpose, then
counts tests, verify journeys and git churn by the same split. The method is
in docs/integration_design_snapshot_2026-10-23.md, "Purpose census". The
labels are judgments from each function's docstring and callers; edit
MODULES, OVERRIDE, TESTS and JOURNEY_FEATURES when the code changes. A
module, test file or feature file missing from them is reported as
unclassified, never guessed, and an entry or override that names no file,
function or class is reported as stale.

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
    "Q": "retrieval and the public IDENTITY search",
    "M": "record model and self-consistency",
    "F": "CLI, environment, schema export",
    "S.first": "scenario fixtures: first publication",
    "S.change": "scenario fixtures: a change after publication",
}
CORE = ("P", "C.own", "C.dep", "C.cont", "C.text", "L", "B", "Q", "M")

# Each module's default label. A module listed twice is an error.
MODULES = {
    "P": ("validation", "registered", "digests", "native_copy"),
    "C.own": (
        "forget", "retirement", "withdraw", "erasure", "erasure_rules",
        "dataset_forget", "removal_record",
    ),
    "C.dep": ("withholding", "chains", "dependency", "outside_deletion", "review"),
    "C.cont": ("admission", "replace", "revisions"),
    "C.text": ("text_changes", "entry_update"),
    "L": ("storage", "stages"),
    "B": ("publish", "native", "entry", "native_chunks"),
    "Q": ("retrieve", "delivery", "settled", "search"),
    "M": ("models", "records", "decisions"),
    "F": ("schema", "environment", "__main__", "fixture_embeddings", "__init__"),
    "S.first": (
        "fixture", "captured_chunks", "captured_text", "conformance_fixture",
        "native_search",
    ),
    "S.change": (
        "multisource", "glossary_fixture", "text_fixture", "occurrence_fixture",
        "forget_fixture", "kind_change", "resolved_retirement", "reinterpretation",
        "group_regrouping", "captured_revision", "occurrence_addition",
        "chain_fixture", "chain_kind_change", "entity_edit", "native_cognify",
        "native_forget",
    ),
}
# Dotted names reach methods and nested functions, e.g. "replace.withhold".
OVERRIDE = {
    "admission": {
        "check_input_kinds": "P", "check_corpus_inputs_exist": "P",
        "check_absent_from_graph": "B", "check_source_identity": "M",
        "check_foreign_inputs": "C.dep", "foreign_citations": "C.dep",
        "attested_inputs": "C.dep", "check_reconfirmations": "C.dep",
        "without_range": "C.dep",
    },
    "erasure_rules": {"entity_ids_named": "B"},
    "outside_deletion": {
        "check_readd": "C.own", "orphan_name_points": "C.own",
        "sweep_orphans": "C.own",
    },
    "review": {"replaced_variant": "S.change"},
    "publish": {
        "Publisher.withheld_for": "C.dep", "Publisher.withdraw": "C.own",
        "Publisher.forget": "C.own", "Publisher.replace": "C.cont",
        "Publisher.admit_inputs": "P", "Publisher.preflight": "P",
        "Publisher.refuse_owned_retry": "L", "Publisher.reconcile": "L",
        "Publisher._publish": "L", "Publisher.forgotten_row": "C.own",
        "Publisher.admit_readd": "C.own", "Publisher.readd": "C.own",
    },
    "retrieve": {
        "live_drift": "P", "valid_sources": "P", "withheld_now": "C.dep",
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
        "is_foreign": "C.dep",
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
# Tests and journeys by whether they exercise a change after publication.
# "mixed" files cover both and are counted apart, not split by guess.
TESTS = {
    "first": (
        "test_identity_native", "test_identity_storage", "test_identity_environment",
        "test_identity_records", "test_identity_retrieval",
        "test_identity_ledger_check", "test_identity_chunks",
        "test_identity_chunks_native",
        "test_conformance_check", "test_identity_conformance",
        "test_identity_conformance_native", "test_identity_delivery",
        "test_identity_search",
    ),
    "mixed": (
        "test_identity_entry", "test_identity_entry_native",
        "test_identity_search_native",
    ),
    "change": (
        "test_identity_additions", "test_identity_additions_native",
        "test_identity_cascade", "test_identity_chain_kind_change",
        "test_identity_chains", "test_identity_chains_native",
        "test_identity_combination_native", "test_identity_dataset_forget",
        "test_identity_dataset_forget_native", "test_identity_decisions",
        "test_identity_dependencies", "test_identity_dependencies_native",
        "test_identity_entity_edits", "test_identity_erasure",
        "test_identity_erasure_retry_native", "test_identity_forget",
        "test_identity_forget_native", "test_identity_general_map",
        "test_identity_kind_change", "test_identity_kind_change_native",
        "test_identity_mixed", "test_identity_mixed_native",
        "test_identity_native_deletes", "test_identity_native_deletes_native",
        "test_identity_occurrences", "test_identity_occurrences_native",
        "test_identity_outside_deletion", "test_identity_outside_deletion_native",
        "test_identity_readd_outside_deletion", "test_identity_regrouping",
        "test_identity_reinterpretation", "test_identity_reinterpretation_native",
        "test_identity_removal_record", "test_identity_removal_record_native",
        "test_identity_removal_wiring", "test_identity_removed_uuid",
        "test_identity_resolved_retirement",
        "test_identity_resolved_retirement_native", "test_identity_revisions",
        "test_identity_split_native", "test_identity_text_changes",
        "test_identity_text_native", "test_occurrence_check",
    ),
}
JOURNEY_FEATURES = {
    "first": ("publication-and-retrieval",),
    "mixed": ("standard-entry-points", "public-search"),
    "change": (
        "dependencies", "group-regrouping", "multi-source-withdrawal",
        "occurrence-changes", "reinterpretation", "revision-and-text-edits",
        "source-lifecycle",
    ),
}
FEATURES = pathlib.Path(".claude/skills/verify/features")


def by_member(table):
    """Invert a {group: members} table; a member in two groups is an error."""
    inverted = {m: group for group, members in table.items() for m in members}
    assert len(inverted) == sum(map(len, table.values())), f"duplicate in {table}"
    return inverted


DEFAULT = by_member(MODULES)
TEST_GROUP = by_member(TESTS)
FEATURE_GROUP = by_member(JOURNEY_FEATURES)
assert {*MODULES, *CORE, *(v for o in OVERRIDE.values() for v in o.values())} <= set(
    CATEGORIES
), "a label is not in CATEGORIES"


def table_problems():
    """Files no table classifies, and table entries with no file."""
    files = {
        "module": ({p.stem for p in PACKAGE.glob("*.py")}, DEFAULT),
        "test": ({p.stem for p in pathlib.Path("tests").glob("test_*.py")}, TEST_GROUP),
        "feature": (
            {p.stem for p in FEATURES.glob("*.md")} - {"README"},
            FEATURE_GROUP,
        ),
    }
    unclassified, stale = [], []
    for kind, (found, table) in files.items():
        unclassified += [f"{kind} {name}" for name in sorted(found - table.keys())]
        stale += [f"{kind} {name}" for name in sorted(table.keys() - found)]
    stale += [f"override {stem}.*" for stem in OVERRIDE if stem not in DEFAULT]
    return unclassified, stale


def line_labels(path, default):
    """The label of each line, and the overrides that matched no node."""
    text = path.read_text()
    labels = [default] * (len(text.splitlines()) + 1)
    overrides = OVERRIDE.get(path.stem, {})
    unmatched = set(overrides)

    def walk(nodes, prefix):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                if name in overrides:
                    unmatched.discard(name)
                    labels[node.lineno : node.end_lineno + 1] = [overrides[name]] * (
                        node.end_lineno - node.lineno + 1
                    )
                walk(node.body, name + ".")

    walk(ast.parse(text).body, "")
    return labels[1:], unmatched


def code_census():
    lines, per_module, stale = collections.Counter(), {}, []
    for path in sorted(PACKAGE.glob("*.py")):
        if path.stem not in DEFAULT:
            continue
        labels, unmatched = line_labels(path, DEFAULT[path.stem])
        stale += sorted(f"override {path.stem}.{name}" for name in unmatched)
        counts = collections.Counter(labels)
        lines.update(counts)
        per_module[path.stem] = counts
    return lines, per_module, stale


def test_census():
    counts = collections.Counter()
    for path in pathlib.Path("tests").glob("test_*.py"):
        n = len(re.findall(r"^(?:async )?def test_", path.read_text(), re.M))
        counts[TEST_GROUP.get(path.stem, "unclassified")] += n
    return counts


def journey_census():
    counts, fault = collections.Counter(), 0
    for path in FEATURES.glob("*.md"):
        if path.stem == "README":
            continue
        text = path.read_text()
        n = len(re.findall(r"^```bash journey", text, re.M))
        counts[FEATURE_GROUP.get(path.stem, "unclassified")] += n
        titles = re.findall(r"^\*\*[A-Z]+[0-9]+ ([^.*]*)", text, re.M)
        fault += sum(bool(re.search(r"fault|fail|interrupt|crash", t)) for t in titles)
    return counts, fault


def churn_census():
    log = subprocess.run(
        ["git", "log", "--numstat", "--format=", "HEAD", "--", str(PACKAGE)],
        capture_output=True, text=True, check=True,
    ).stdout
    counts = collections.Counter()
    for row in log.splitlines():
        parts = row.split("\t")
        if len(parts) == 3 and parts[0] != "-" and parts[2].endswith(".py"):
            category = DEFAULT.get(pathlib.Path(parts[2]).stem, "unclassified")
            counts[category] += int(parts[0]) + int(parts[1])
    return counts


def main():
    lines, per_module, stale = code_census()
    unclassified, stale_entries = table_problems()
    stale = stale_entries + stale
    core = sum(lines[c] for c in CORE)
    print(f"Code lines by purpose (core = {core}):")
    for category, meaning in CATEGORIES.items():
        share = f"{100 * lines[category] / core:5.1f}%" if category in CORE else "      "
        print(f"  {category:8} {lines[category]:6} {share}  {meaning}")
    if unclassified:
        print("Unclassified:", ", ".join(unclassified))
    if stale:
        print("Stale entries:", ", ".join(stale))
    print("Tests:", dict(test_census()))
    journeys, fault = journey_census()
    print("Journeys:", dict(journeys), f"of which fault or recovery: {fault}")
    print("Churn by module default category:", dict(churn_census()))
    if "-v" in sys.argv:
        for stem, counts in per_module.items():
            print(f"  {stem}: {dict(counts)}")


if __name__ == "__main__":
    main()
