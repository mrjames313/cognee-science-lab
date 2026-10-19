# Stage 6: first identity publication/retrieval slice

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
- `publish.py` uses configured Cognee engines and native persistence/reference APIs. It writes only missing Entities, retains compatible existing Entities without overwriting ordinary fields, creates original-chunk-owned markers, and aggregates source-specific contribution payloads on graph-only identity edges.
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

Remaining work includes multi-document lifecycle/withdrawal, revision replacement, full original/generated source removal, dependent-source maintenance, standard entry-point transformation, registered public SearchType, comprehensive context-sensitive traversal across sources, span-applicable variant traversal, unresolved/ambiguous passage delivery, full grouped evidence delivery and offline diagnostics. The first retriever intentionally declines span-applicable variant expansion and only searches facts supported by the current source document; this is an internal fixture boundary, not a new public fact-source filtering feature. It is not the final corpus-wide retriever. Complex saved-record reasoning inputs require an input-reader adapter and currently fail explicitly.

The saved authoritative JSON is serialized in the project relational row; the initial registered generated Data item contains the matching JSON snapshot. This slice rejects description revision replacement rather than allowing those representations to diverge. A later maintenance milestone must implement the coordinated saved-source update path.

No live lab corpus was changed, no native dependency source was patched, and no backend-specific query/storage implementation was added. Comprehensive replay, whole-store A/B copies, model-driven Describe, automatic repair and size/density tooling remain deferred.
