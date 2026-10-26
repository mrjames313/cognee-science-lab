"""Erasure retries through real configured stores in fresh subprocesses: a
dependent's failed attempt finishes with the removal of what a forget took
away, and nothing its superseded description wrote is left behind."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_identity_native import command

REPO = Path(__file__).parents[1]
HC = "9b2b4cb5-1b07-5380-8aa5-cf0f11b8db88"

LEFTOVERS = r"""
import asyncio,json,sys
from pathlib import Path
from cognee_lab.identity.environment import fixture_environment
root=Path(sys.argv[1]);source=sys.argv[2];dropped=json.loads(sys.argv[3])
with fixture_environment(root):
 from cognee_lab.identity.models import IdentitySource
 from cognee_lab.identity.native import edge_metadata
 from cognee_lab.identity.publish import Publisher,contributions,identity_edges
 async def check():
  p=await Publisher.configured()
  row=next(r for r in await p.records.rows() if r.source==source)
  superseded=[IdentitySource.model_validate_json(d) for d in row.plan["erased_from"]]
  kept={tuple(e[:3]) for e in identity_edges(row.description)}
  gone=sorted({tuple(e[:3]) for s in superseded for e in identity_edges(s)}-kept)
  edges=[]
  for triple in gone:
   edge=await edge_metadata(p.graph,*triple)
   if edge and any(c.get("identity_data_id")==source for c in contributions(edge.edge_properties)):
    edges.append(triple)
  print(json.dumps(dict(
   superseded_edges=len(gone),
   nodes=[e for e in dropped if await p.graph.get_node(e) is not None],
   vectors=[e for e in dropped if await p.vector.retrieve("Entity_name",[e])],
   edges=edges)))
 asyncio.run(check())
"""


def run_script(script, *args):
    completed = subprocess.run(
        [sys.executable, "-c", script, *map(str, args)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert completed.returncode == 0, (
        completed.stdout[-4000:] + completed.stderr[-4000:]
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def leftovers(root, source, dropped):
    """What the dependent's superseded descriptions wrote that is still in
    the graph: a dropped Entity's node or name vector, and an identity edge
    the removal no longer wants that still holds this source's
    contribution."""
    return run_script(LEFTOVERS, root, source, json.dumps(dropped))


@pytest.mark.integration
def test_native_an_erasure_retry_of_a_failed_publication_retires_what_it_wrote(
    tmp_path,
):
    """doc01's first publication failed after its nodes and identity edges
    were written, while v01 reads the glossary's HC entry. Forgetting the
    glossary finishes doc01's publication with the removal: HC, which only
    v01 named, leaves the graph and the name index with the edge v01 wrote,
    as the dry run said, and no query seeds it."""
    root = tmp_path / "glossary"
    command(
        root,
        "glossary-fixture",
        "--source",
        "doc01",
        "--fault-stage",
        "identity_edges",
        expect=1,
    )
    forget = ("forget", "--source", "glossary", "--expected-revision", "1")
    report = json.loads(command(root, *forget, "--dry-run").stdout)
    (dependent,) = report["dependents"]
    assert (dependent["state"], dependent["blocked"]) == ("failed", False)
    assert dependent["dropped_entities"] == [HC]
    command(root, *forget, "--confirm", report["token"])
    final = json.loads((root / "glossary_result.json").read_text())
    assert final["dependents_failed"] is None
    doc01 = final["sources"]["doc01"]
    assert (doc01["state"], doc01["saved_revision"]) == ("current", 1)
    assert list(doc01["decisions"]) == ["r01"]
    assert HC not in final["result"]["seed_entity_ids"]
    assert final["result"]["unavailable_sources"] == []
    found = leftovers(root, doc01["identity_data_id"], dependent["dropped_entities"])
    assert found["superseded_edges"] > 0
    assert (found["nodes"], found["vectors"], found["edges"]) == ([], [], [])


FAILED_TEXT_CHANGE = r"""
import asyncio,json,sys
from pathlib import Path
from cognee_lab.identity.environment import fixture_environment
root=Path(sys.argv[1]);fault=sys.argv[2]
with fixture_environment(root):
 from cognee_lab.identity.admission import identity_map
 from cognee_lab.identity.captured_chunks import recorded_budget
 from cognee_lab.identity.registered import context_for
 from cognee_lab.identity.forget import forget, preview
 from cognee_lab.identity.multisource import current_sources
 from cognee_lab.identity.publish import Publisher
 from cognee_lab.identity.text_changes import TextChange,chunk_text,original_context,read_original
 from cognee_lab.identity.text_fixture import PREFIX,describe_prefix_edit,rebuild
 async def check():
  p=await Publisher.configured()
  sources=await current_sources(root,p)
  old=sources["doc02"]
  ctx=await context_for(old.identity_data_id)
  before=await read_original(old,ctx)
  change=TextChange(previous_text=before,text=PREFIX+before,occurrence_map=identity_map(old),chunk_budget=await recorded_budget(old,p.graph))
  chunks=await chunk_text(change.text,await original_context(old,ctx),change.chunk_budget)
  intended=describe_prefix_edit(old,change.text,chunks)
  try:
   await rebuild(p,intended,change,expected_revision=1,fault_stage=fault)
   raise SystemExit("the injected failure did not fail the text change")
  except SystemExit: raise
  except Exception: pass
  row=await p.records.row(old)
  assert (row.state,row.revision,row.resumed_by)==("failed",2,"replace"),row
  doc01=sources["doc01"]
  report=await preview(p,doc01,expected_revision=1)
  (dependent,)=report["dependents"]
  assert (dependent["state"],dependent["blocked"])==("failed",False),report
  outcome=await forget(p,doc01,expected_revision=1,confirm=report["token"])
  assert outcome["dependents_failed"] is None,outcome
  row=await p.records.row(old)
  assert (row.state,row.revision)==("current",2),row
  assert row.description.inputs[row.description.original_input_ref].text_sha256==intended.inputs[intended.original_input_ref].text_sha256
  doc01_data=doc01.inputs[doc01.original_input_ref].data_id
  assert not any(getattr(i,"data_id",None)==doc01_data for i in row.description.inputs.values()),row.description.inputs
  assert any(k.startswith("forget_") for k in row.description.producers)
  print(json.dumps(dict(source=row.source,dropped=dependent["dropped_entities"])))
 asyncio.run(check())
"""


@pytest.mark.integration
@pytest.mark.parametrize("fault", ["replace_saved", "replace_verification"])
def test_native_a_failed_text_change_takes_the_removal(tmp_path, fault):
    """doc02's own text change failed while it reads doc01's text, which no
    command can produce: before anything was written, or after its writes
    and before acknowledgement. Forgetting doc01 finishes the text change
    with the removal applied to its saved revision, and nothing the saved
    revision wrote for the removed decision is left."""
    root = tmp_path / "failed_text_change"
    command(root, "multi-fixture", "--dependent")
    done = run_script(FAILED_TEXT_CHANGE, root, fault)
    found = leftovers(root, done["source"], done["dropped"])
    assert found["superseded_edges"] > 0
    assert (found["nodes"], found["vectors"], found["edges"]) == ([], [], [])
