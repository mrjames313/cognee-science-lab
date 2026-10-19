# Step 4 / M3: unchanged-text identity revision replacement

Implemented against pinned Cognee 1.6.2 on 2026-10-19. This is the first portion of accepted step 4, following the publication and multi-source withdrawal fixtures. It is not completion of document edits, rechunking, dependency maintenance or the full lifecycle.

## Run the captured correction

Apply this incremental checkpoint after the initial Stage 6, seed-selection and multi-source withdrawal patches. Use a new root:

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/stage6_revisions
uv run python -m cognee_lab.identity revise --root outputs/stage6_revisions --source doc01 --expected-revision 1
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_revisions --source doc01
```

The correction is deliberately supplied as captured test input, not inferred from the text. It retargets doc01's accepted mention and document-scoped HC variant to an exact new Entity UUID, named Revised controller. It retires doc01's obsolete controller declaration and private singleton. Doc02 retains its original interpretation, contribution and singleton support. Shared singleton support remains. Both original documents, extracted text, chunk mappings, mention UUIDs/ranges, ordinary fact endpoints/IDs and evidence remain unchanged.

The revised assignments have a separate captured correction producer. Existing mention groups keep their original producer attribution.

The expected revision is mandatory for the fixture correction. A stale caller is rejected before changing native Data or graph state. Repeating revise with expected revision 1 after success is a stale request; use reconcile to check/rebuild the saved current revision.

| Observation | doc01 | doc02 |
|---|---|---|
| Saved / verified / registered revision after correction | 2 / 2 / 2 | 1 / 1 / 1 |
| Mention resolution target | Revised controller | Original Helios controller |
| Ordinary fact source | Same local mention UUID as revision 1 | Unchanged |
| Original evidence and occurrence positions | Unchanged | Unchanged |
| Contribution to the old shared variant edge | Removed | Preserved, including scope and native owner |
| Private singleton | Removed from graph and name index | Preserved |

The default HC query returns both local facts with their respective document-scoped interpretations. The correction command also queries Revised controller and returns doc01's fact alone. Healthy same-revision reconciliation preserves the corrected result.

The correction command prints its summary and writes revision_result.json. The captured input is available in identity_doc01_revision2.json. Subsequent reconciliation writes multisource_result.json. Source summaries include saved_revision, verified_revision, registered_revision and registered_matches_saved. The project relational description is the authoritative saved record; the original fixture input files remain initial fixtures, and current fixture operations load saved intent from the ledger.

## Replacement API and write order

Publisher.replace(source, texts=..., chunks=..., ctx=..., expected_revision=..., verify_semantics=...) accepts the intended next IdentitySource under the existing dataset/generated-Data ID. It uses the same backend-neutral writer/revision guard and the same graph publisher as first publication. No new permanent role registry or graph support nodes are introduced.

1. Verify the previous publication is current; require exactly the next revision and unchanged original text inputs, chunk mapping and mention groups. Validate the intended record, actual input fingerprints, UUID uses, native context and existing semantic output.
2. Persist the new authoritative description as pending, with its intended revision and a durable plan containing the previous description, old/new edge identities and retired declarations. The prior verified revision remains recorded.
3. Update the registered generated Data snapshot through Cognee's ingestion Task using an explicit existing data_id. Preserve that ID, update native managed files/content metadata and refresh the Task context. The generated snapshot is managed from saved intent; its previous external file source_uri is not retained as a reload source.
4. Publish required new Entities and intended identity links through the common publisher. Existing compatible Entity fields are referenced without ordinary-property writes.
5. Remove obsolete source-specific contributions and native retention. Use Cognee's source-ref removal planner for the selected retired nodes/edges, preserving unrelated owners and payloads. A surviving contribution without its native owner is an error rather than permission to delete its edge.
6. Verify intended graph/ownership/indexes, obsolete-output retirement, registered JSON/content metadata, unchanged required semantic output and actual reasoning inputs. Only then acknowledge the matching attempt as current at revision 2.

The native high-level Add operation refuses changed existing documents in this baseline. The lower-level ingest_data Task supports updating the generated Data row under its explicit ID without running graph extraction or deleting original facts. The integration uses that Task with a checked real PipelineContext, rather than writing provider-specific SQL, changing source files in place, or invoking general document Update. The native Task maintains Data locations, hashes and sizes. Project SHA-256/JCS input-fingerprint rules are unchanged.

Identity helper edges remain graph-only. Newly created Entities receive their native name indexes; retired declarations lose only this source's native retention, with graph/vector deletion for objects left unowned. Original semantic facts retain their original chunk ownership/evidence.

## Interrupted replacement and explicit recovery

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/stage6_revision_failure
uv run python -m cognee_lab.identity revise --root outputs/stage6_revision_failure --expected-revision 1 --fault-stage replace_saved
# Expected injected failure.
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_revision_failure
uv run python -m cognee_lab.identity status --root outputs/stage6_revision_failure
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_revision_failure --source doc01
```

Injection boundaries are replace_saved, replace_registered, replace_published, replace_retired and replace_verification. The native tests cover the first four, spanning saved-record, registered-Data, additive graph and destructive retirement writes.

| Failure point | Saved intent | Registered snapshot | Graph |
|---|---|---|---|
| replace_saved | Revision 2, failed; last verified 1 | Revision 1 | Previous output |
| replace_registered | Revision 2, failed; last verified 1 | Revision 2 | Previous output |
| replace_published | Revision 2, failed; last verified 1 | Revision 2 | New output written; old output may remain |
| replace_retired | Revision 2, failed; last verified 1 | Revision 2 | New output with retirement performed; not acknowledged current |

These failures do not roll back. The integration retriever withholds doc01 while components may disagree and continues using doc02's independently valid publication. Native readers that do not consult the integration's ledger do not gain this eligibility behavior automatically.

Explicit reconcile loads the exact saved revision-2 intent and its retirement plan, accepts only a registered snapshot matching the previous or intended revision, and finishes replacement without another identity/model decision. It does not restore revision 1 or invent a new revision. The original incident receives the verified recovery attempt, resolving revision 2 and outcome restored. A missing/incompatible retirement plan or a changed reasoning input is a diagnostic requiring an explicit further recovery/reconsideration choice.

Retrieval also compares current saved intent with the registered snapshot and native raw-content hash. An unexpected mismatch is withheld and recorded instead of serving the mismatched publication.

## Evidence and remaining scope

Pure checks cover captured correction structure, unchanged-occurrence admission, native-owner preservation, expected-revision/pending-intent guards and exact saved-plan reuse. Native tests cover stale callers, coordinated revision/currentness, both query routes, exact local fact/evidence preservation, original borrowed-field preservation, doc02 survival, obsolete singleton/vector removal, reopen/reconcile, and explicit recovery at four write boundaries. Previous publication/withdrawal fixtures remain regression checks.

This fixture establishes neither the quality of the supplied identity correction nor a guarantee that arbitrary previously extracted facts remain valid after a real identity change. The supplied semantic verifier checks the captured unchanged local fact; semantic regeneration and its selection policy remain later work.

Text, group membership, occurrence ranges, chunk boundaries, new context selection and dependent-source maintenance are not admitted by this replacement slice. Standard Cognify/Remember/Update wiring, coordinated native Data removal, hard-crash writer abandonment, public SearchType, complete corpus traversal and all-backend validation remain incomplete. There is no A/B copy, rollback, automatic retry, LLM Describe or comprehensive replay framework.
