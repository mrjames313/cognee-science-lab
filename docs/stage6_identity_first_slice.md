# Stage 6: identity publication, retrieval and lifecycle fixtures

Implemented on 2026-10-17 against Cognee 1.6.2. This is the agreed first checkpoint (record validation and a deterministic end-to-end fixture), not the complete Stage 6 integration. The reviewed handoff remains the design authority for later milestones.

## Run it

From the repository root:

```bash
uv sync --group dev
uv run python -m cognee_lab.identity fixture --root outputs/stage6_first
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_first --query 'What does HC limit?'
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_first
uv run python -m cognee_lab.identity status --root outputs/stage6_first
uv run pytest -q
```

Use a new root for `fixture`; an existing directory is rejected. The other commands require the fixture marker. These commands configure a fresh, isolated test profile before importing Cognee; they do not reset or use the lab's configured corpus. The first tested configuration is Ladybug/LanceDB/SQLite. Providers and paths here are fixture configuration, not direct backend access in the integration.

The fixture uses a loopback OpenAI-compatible service with deterministic token-hash embeddings. Graph, vector and relational storage are real; no extraction/answer LLM or external embedding API is called. Hugging Face offline mode prevents a tokenizer download; this tiny fixture does not evaluate chunk token-budget precision or embedding quality. Environments whose injected HTTP proxy requires optional SOCKS support may need `uv pip install 'httpx[socks]' pysocks` for Cognee startup; this is an environment dependency, not an integration backend dependency.

Expected result: the query seeds the HC Entity, traverses the document-applicable variant relationship to the reusable controller, then finds the accepted local mention and its `limits -> oscillations` fact. Output includes the original document/chunk evidence, exact occurrence positions and accepted identity annotation. The source passage is not replaced with generated identity prose.

## What the code does

- `models.py` validates the saved forms, references, required construction entries, sorted occurrences and local role consistency. `validation.py` checks exact document/span digests, RFC 8785 structured input signatures, native chunk mapping, actual supplied dependencies and cross-source UUID use.
- `publish.py` uses configured Cognee engines and native persistence/reference APIs. It writes only missing Entities, retains compatible existing Entities without overwriting ordinary fields, creates original-chunk-owned markers, and aggregates source-specific contribution payloads on graph-only identity edges. Each occurrence chunk explicitly retains its marked mention endpoint, including unresolved mentions without facts.
- `fixture.py` routes captured semantic output through native chunk ownership, index helpers and evidence buffering/lookup, under the original source context. It avoids populated nested existing Entities. A native custom Task invokes the publisher; completing the standard Cognify Task-transform hook remains later work.
- `storage.py` stores serialized descriptions, minimal intent, publication status and recovery events through Cognee's configured relational session facility with backend-neutral SQLAlchemy operations. It creates only namespaced project tables. A portable conditional update reserves one project writer across the shared stores; it does not coordinate arbitrary native writers.
- `retrieve.py` is a small document-context fixture retriever. It consumes Entity-name candidates, current validated saved assignments, actual physical contribution payloads, bounded native fact neighborhoods and native original-source evidence. Helper links are excluded from subject-matter facts. It rechecks publication tokens before delivery.

The example/schema/source fixture live in `tests/fixtures/identity/` and `schemas/`. The runtime schema is generated from the models:

```bash
uv run python -m cognee_lab.identity.schema
```

The schema test verifies generation stays synchronized and validates the example with a JSON Schema engine. Cross-record/runtime validity still needs the Python checks.

## Failure visibility and recovery

```bash
uv run python -m cognee_lab.identity fixture --root outputs/stage6_failure --fault-stage identity_edges
# Expected nonzero exit and a recovery_event_id.
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_failure
# No facts from the unfinished source.
uv run python -m cognee_lab.identity status --root outputs/stage6_failure
uv run python -m cognee_lab.identity reconcile --root outputs/stage6_failure
```

The injected failure happens after deterministic semantic output exists, so identity-only reconciliation can verify that output and restore publication without another model decision. Reconciliation is explicit and gets a new attempt; repeated graph/contribution publication is idempotent. The original event remains linked to the verified recovery. Deliberate injections are labeled separately from runtime incidents.

`--fault-stage nodes` and `--fault-stage verification` exercise other boundaries. If required semantic output is absent after a node-stage failure, identity-only reconciliation refuses to declare success. Actual document reconsideration/rebuild will be a later milestone; there is no hidden extraction call.

Detected changed reasoning inputs are withheld and recorded as recovery-required incidents. Event writes that themselves fail are surfaced, leaving publication unavailable. Abrupt-process-death inspection/reservation abandonment and further recovery outcomes remain incomplete: a hard crash can leave the project writer reserved, so do not treat this slice as general restart recovery.

## Verified behavior and limits

Focused tests cover invalid records, UUID-use conflict, repeated Unicode chunks, JCS signatures, missing/changed corpus inputs, saved revision/attempt guards, event deduplication, native publication/ownership/index/evidence verification, reopening the actual stores, idempotent reconciliation, injected failure withholding/recovery and dependency-change detection. Test code also rejects concrete backend imports and raw query calls in the application package. These checks do not establish compatibility with untested backends.

The native run exposed a mismatch between `get_edges`' interface annotation and its actual legacy return shape/direction on this path. The integration uses `get_edge_delete_data` for exact edge/provenance reads and `iter_bounded_neighborhood` for uniform directed EdgeData, without an adapter-specific workaround. Default neighborhood implementations on some backends can read more than the returned cap; actual backend work bounds need separate admission tests.

Remaining work includes text/occurrence-changing revision replacement, coordinated original/generated Data removal and full document lifecycle, dependent-source maintenance, standard entry-point transformation, registered public SearchType, comprehensive context-sensitive traversal across sources, span-applicable variant traversal, unresolved/ambiguous passage delivery, full grouped evidence delivery and offline diagnostics. The first retriever intentionally declines span-applicable variant expansion and only searches facts supported by the current source document; this is an internal fixture boundary, not a new public fact-source filtering feature. It is not the final corpus-wide retriever. Complex saved-record reasoning inputs require an input-reader adapter and currently fail explicitly.

The saved authoritative JSON is serialized in the project relational row, with a matching snapshot in the registered generated Data item. The [unchanged-text replacement checkpoint](stage6_identity_revision_replacement.md) coordinates advancing those representations and the graph. Pending/failed replacements are withheld until verified; text/occurrence changes remain unsupported.

No live lab corpus was changed, no native dependency source was patched, and no backend-specific query/storage implementation was added. Comprehensive replay, whole-store A/B copies, model-driven Describe, automatic repair and size/density tooling remain deferred.

## Two-source lifecycle fixture

Apply this checkpoint after the initial Stage 6 patch and seed-selection fix.

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/stage6_shared
uv run python -m cognee_lab.identity withdraw --root outputs/stage6_shared --source doc01
uv run python -m cognee_lab.identity withdraw --root outputs/stage6_shared --source doc02
```

The new fixture creates two original documents and two registered identity descriptions in one dataset. Both descriptions independently support the same physical HC-to-controller variant edge and a shared singleton. Each description also declares a private singleton and distinct accepted and unresolved mention groups. Captured ordinary facts remain attached to their local mention and original producing chunk; both documents independently produce a limits-to-oscillations fact. No LLM is used.

The command writes `multisource_result.json` and prints the result plus a compact graph/ownership summary. Expect:

| Point | Shared variant contributions/owners | Shared singleton | Query facts |
|---|---|---|---|
| Both published | 2 / 2 | Present and indexed | Two local mention facts, with their own evidence |
| Withdraw doc01 | 1 / 1, belonging to doc02 | Present and indexed | Only doc02's interpreted fact |
| Withdraw doc02 | No remaining physical variant edge | Absent from graph and name index | None |

After each withdrawal, original-chunk markers, mention nodes, ordinary facts, original ownership and native edge evidence remain. A private singleton is removed, including its name vector, when its one identity owner withdraws. The borrowed controller's ordinary fields and independent native ownership survive. Unresolved mention endpoints survive through original occurrence-chunk ownership even though they have no facts.

This operation withdraws the selected generated source's graph contributions and Entity retention. It keeps the registered Data items and saved description for inspection/history. It does not delete or update original text, retract ordinary facts, implement original-document Forget, or replace a saved-description revision. The fixture retriever excludes withdrawn descriptions, so retained original facts cease receiving that description's identity interpretation.

Use a fresh root to try the reverse removal order. Repeating withdrawal is supported, including after the other source was withdrawn. `reconcile --source doc02` can check the still-current second document before retirement; reconciliation cannot silently reactivate a withdrawn source.

### Withdrawal implementation and failures

`Publisher.withdraw(source, expected_revision=..., ...)` uses the existing portable writer/revision guards. It saves retirement keys, previous owner refs and contribution properties in a minimal plan before destructive writes. It marks the source pending, removes only that source's contribution payloads, then uses Cognee's `UnifiedStoreEngine.delete_by_source_ref` with the configured graph/vector engines. Native provenance deletion detaches shared ownership and removes unowned graph/vector output. Verification checks retired ownership/contributions and surviving native owners/indexes before acknowledging `withdrawn`. Historical survivor expectations are adjusted for other sources explicitly retired between retries.

The ledger adds an explicit `withdrawn` completion state; the revision and description are retained. Withdrawal preserves the last successfully published revision, including zero for a publication that never completed. This is an operation state, not a second role or eligibility registry. Interrupted withdrawal becomes failed/unavailable with a recovery event. Explicitly retry `withdraw`; publication reconciliation is rejected while withdrawal is incomplete. Successful recovery records `outcome: withdrawn` on the original event.

```bash
uv run python -m cognee_lab.identity multi-fixture --root outputs/stage6_shared_failure
uv run python -m cognee_lab.identity withdraw --root outputs/stage6_shared_failure --source doc01 --fault-stage withdraw_contributions
# Expected injected error and recovery-event identifier.
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_shared_failure
# Only doc02's interpreted fact; doc01 appears in unavailable_sources.
uv run python -m cognee_lab.identity withdraw --root outputs/stage6_shared_failure --source doc01
```

Other injection boundaries are `withdraw_owners` and `withdraw_verification`. Deliberate retirement is absent from `unavailable_sources`; failed/pending publication is now reported there with any unresolved recovery-event identifier. The isolated CLI closes supported engine lifecycle handles before interpreter teardown, including handled operation failures. Existing-root fixture errors now give an argparse message instead of a raw traceback.

The native test matrix covers both removal orders, repeated withdrawal before/after another retirement, shared payload/native owner survival, independent singleton retention, private/last-owner graph and vector cleanup, unresolved-marker retention, original fact ownership/evidence preservation, and caught failures after payload mutation and native deletion. Tests also retire the independent source between a failure and its retry. Hard process crashes, arbitrary native writes during a project mutation, coordinated native Data deletion, all-backend admission and corpus-wide identity traversal remain outside this checkpoint.

## Step 4: identity revision replacement

See [the revision replacement guide](stage6_identity_revision_replacement.md) for a captured doc01 correction from revision 1 to 2, native registered-Data updates, stale-revision guards and explicit recovery. This is the first part of M3 / accepted step 4. Original text, chunk mappings and mention groups remain unchanged.
