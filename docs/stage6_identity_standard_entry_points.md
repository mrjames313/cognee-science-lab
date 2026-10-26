# Stage 6: the lab's add, cognify and remember

**Guide scope:** what the lab's entry points over Cognee's own pipeline do, which fixture uses them, and what a plain Cognee call outside them does to a lab source. For project status, read [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

Built on 2026-10-26 against Cognee 1.6.2 (step 5, units S3a, S3b and S4). Every creation command and `readd` registers and publishes its documents through the entry points ("Which commands use them"). Since S4 every text edit goes through the lab's `update` ("The lab's update").

## Warning: a plain Cognee call bypasses the identity layer

`cognee.cognify`, `cognee.remember` and `cognee.update` know nothing of the lab's saved descriptions. Run on a lab document, they extract it with the LLM and write graph content that no ledger row governs. The lab protects its files in one way only: it stamps each file it manages as cognified, so a plain `cognee.cognify` with its defaults skips the file and makes no LLM call. That protection has gaps:

- **Before chunking.** `add` stamps the description at once, but the original only once `cognify` has chunked it. A plain `cognee.cognify` between the two extracts the original.
- **`cognee.cognify(incremental_loading=False)`** ignores every stamp and extracts every file.
- **A dataset `cognee.forget(memory_only=True)`** clears every stamp in the dataset.
- **A per-item `cognee.forget(memory_only=True)`** clears that item's stamp.
- **`cognee.update`** on its full-rebuild path cognifies the whole dataset. Stamped files still skip, but the updated file is ingested with changed text, which clears its stamp.
- **Ingesting changed text** clears every stamp of that item. The lab's own text writes (`registered.write_text`) and its per-item forget in a text change stamp the item again at once.
- **A hard kill inside a text change between its per-item forget and the stamp after it.** The forget has cleared the original's chunks and its stamp, and the row stays `pending`. A plain `cognee.cognify` then extracts the previous text with the LLM. Resuming the text change forgets and stamps the original again.
- **Roots made before S3b** carry no stamp on the files their creation command registered by hand (before S3a for `fixture`), or on the files of a source re-added before S3b, until something the lab writes stamps them.

The fixture environment points the LLM at a closed loopback port (`http://127.0.0.1:9/v1`), so a plain call that does reach the LLM fails at once with a connection error. It never sends the fixture's fake key to a provider.

## What the entry points do

`src/cognee_lab/identity/entry.py` holds four functions for a new source (since S4 `entry_update.py` holds `update` and `replace_text`, "The lab's update"):

- **`add`** registers the original through `cognee.add`, chunks it in memory with Cognee's chunker, asks the caller's describer for the identity description, writes the description to a file, registers that file through `cognee.add` and stamps it.
- **`cognify`** runs Cognee's `run_pipeline` under the pipeline name `cognify_pipeline` over one source's original. Cognee's standard Tasks run first: `classify_documents`, `extract_chunks_from_documents` and `add_data_points`. Then one lab Task, `identity_publish`, runs once per document over the whole chunk set. It stamps the original, then publishes the description: a first publication when the source has no row, a re-add at the expected revision when its row is forgotten, else a reconcile. A source with no captured facts (the glossary, doc03) publishes with no semantic writer.
- **One source per run.** `cognify` takes one source. Cognee runs the data items of one run concurrently, up to 20 at a time (`run_tasks.py`, `asyncio.gather`), and a root's sources must publish in order: doc03 cites doc01's published decisions, so doc01 must be current first.
- **`remember`** is `add`, then `cognify`. It never runs Cognee's improve step.
- **`remember_in_order`** runs `add`, then `cognify`, for each source of a root in publication order. A failure stops it before the next source is added.

The run uses captured decisions only. Cognee's `extract_graph_and_summarize` Task does not run; a native extractor waits for step 6. Every Task declares `needs_llm=False`, so the run skips Cognee's LLM connection probe.

### Which commands use them

| Command | Sources, in publication order | Through |
| --- | --- | --- |
| `fixture` | doc01 | `remember_in_order` |
| `multi-fixture`, `chunked-fixture` | doc01, doc02 | `remember_in_order`: `add`, then `cognify`, for each |
| `glossary-fixture [--chain]` | glossary, doc01 [, doc03] | `remember_in_order`: `add`, then `cognify`, for each |
| `readd` | the forgotten source | `add`, then `cognify` at `--expected-revision` |

Each describer reads only the descriptions of the sources before it: doc02's derives from doc01's, and doc03's cites doc01's decisions. doc01's description on a glossary root holds the glossary's text as the fixture writes it, not the registered copy. Admission reads the registered glossary when doc01 publishes, so doc01 is added after the glossary is registered. With `--fault-stage` and `--source`, the selected source's publication fails and the sources after it are never added: no original is left registered without a stamp. The root's manifest still names them, and a command that selects one refuses it (`source_missing`). A source that was added but whose first `cognify` never began has no publication; `reconcile` and the glossary root's report refuse it (`not_published`). `readd` admits the re-add on the in-memory text and chunks before `add` writes anything, as before, and `add` refuses (`chunk_mapping`) if Cognee's chunks differ from the admitted ones.

`reconcile` of a failed first publication runs `cognify` again on every root kind. Any other row is reconciled over the chunks Cognee holds, which the lab chunks again in memory without writing them (`fixture.load_chunks`). The hand-built creation route (chunk in memory, `add_data_points`, then a publish Task in `run_tasks_base`) is gone.

### The lab Task never writes with the pipeline's context

Cognee tags what a Task writes with the pipeline's context by its run ID. The lab Task builds contexts of its own, from the identity Data item for the identity writes and from the original for the captured facts and their evidence. None carries a run ID. Cognee's rollback of a run, and its recovery at API startup of a run abandoned for more than an hour, find a run's writes by that ID, so they can only ever reach the native document node and chunks.

This protects the lab's nodes only. A rollback that removes a chunk also removes every edge that ends at it, the lab's mention markers and fact edges among them. The run passes no rollback handler, so a failed run removes nothing. Startup recovery keeps an item that is stamped, and the lab Task stamps the original before it publishes.

With `ENABLE_BACKEND_ACCESS_CONTROL=true`, each nested Cognee call inside an item Task asks for a fresh dataset-queue slot. A queue of one slot could then block. The fixtures run with access control off, and this case is untested.

### A failure

A failure in the lab Task is recorded in the ledger as a failed attempt with its recovery event, as before. The run still completes, so Cognee keeps the native chunks and the stamp, and the entry point then raises the same error. The CLI exits 1 and prints it with its `recovery_event_id`, exactly as the [first slice guide](stage6_identity_first_slice.md) describes. Cognee's own dataset status (`cognee.datasets.get_status`, or the run record) still shows `cognify_pipeline` completed for the run. Read the ledger (`status`) for the lab's outcome, not Cognee's run status.

`reconcile` of a failed first publication runs the lab's `cognify` again. Cognee's Tasks chunk the original again with the same chunk IDs and the chunk budget the chunks record. Then the lab Task finishes the saved plan.

`status` compares a failed first publication with Cognee's copy like any other row. The lab never rolls its own chunks back, and Cognee's startup recovery keeps them because the original is stamped. So if they are gone, something outside the lab removed them, for example a `cognee.forget(memory_only=True)` of the original or a `cognee.update` that changed its text. `status` lists the row under `native_deleted`, and `reconcile` refuses it ([forget guide](stage6_identity_forget.md#deletes-outside-the-lab)).

## The lab's update

A text edit changes the original document of a published source and publishes the next revision of its identity description. Since S4 every edit command goes through `entry_update.update`:

```python
await update(
    publisher,
    source,          # the current description
    text,            # the new text of the original
    occurrence_map,  # old occurrences to new, which admission checks
    describe_edit=describe,
    expected_revision=1,
    semantics=None,  # or the captured facts to rebuild
)
```

1. `update` refuses a source whose native copy is gone or changed outside the lab with `native_deleted` and the forget hint, as `reconcile` does. Then it reads the registered text, chunks the new text in memory with the chunk budget the native chunks record, and calls `describe_edit` with an `EditDraft` (the current description, the registered text, the new text and its chunks). The describer returns the next revision. The occurrence map is the caller's, since it never depends on the new chunks.
2. `update` builds the `TextChange` from the occurrence map and runs Cognee's `run_pipeline` under the pipeline name `cognify_pipeline` over the original, with one lab Task, `identity_update`. As in `cognify`, the run passes no rollback handler and `incremental_loading=False`, and every Task declares `needs_llm=False`.
3. The lab Task calls the publisher's `replace` with the text change and the identity Data item's context, which carries no run ID. `replace` begins the attempt, withholds the dependents' affected decisions, forgets the original's memory (`cognee.forget(memory_only=True)` on the one Data item), stamps the original again at once, registers the new text and then runs Cognee's standard Tasks (`classify_documents`, `extract_chunks_from_documents`, `add_data_points`) nested, outside any run, with the lab's own context. Then it registers the description and publishes it.

Cognee rebuilds the whole document, so every chunk of the original is new. The identity revision is incremental: admission checks the occurrence map against the previous revision, and the Entities, markers and facts that the map keeps keep their IDs.

**No describer, no update.** `describe_edit` is a required argument of `update`, so the lab never guesses an edited description (the user's decision U-e, made by the assistant on 2026-10-26 and awaiting confirmation). Until fix round 1 of S4 a describer of None was refused at run time with `describer_missing`.

**The nested Tasks write with the lab's context.** The standard Tasks inside `replace` run with a context that has no pipeline run ID, so Cognee's rollback or startup recovery of the update run never finds the rebuilt chunks. Had they carried the run's ID, a recovery could remove chunks that a completed revision cites.

**Which commands use it.**

| Command | Through |
| --- | --- |
| `edit-text` | `update`, with the captured facts (`text_fixture.RebuiltSemantics`) |
| `remove-occurrences`, `retire-resolved-group`, `add-occurrences`, `split-group`, `combine-groups`, `reinterpret-new-entity`, `reinterpret-unresolved`, `change-kind-to-mention`, `change-kind-to-reusable` | `update`, with the captured facts |
| `edit-glossary` | `update`, with no captured facts |
| `reconcile` of a failed text change, and a forget's erasure retry of one | `replace_text`, with the text change the plan saved |

The hand-built edit route (a lab Task in `run_tasks_base` over the identity Data item, then the in-memory chunker and a direct `add_data_points`) is gone.

**A failure.** A failure in the lab Task is recorded in the ledger as a failed replacement with its recovery event. The run still completes and `update` raises the same error, so the CLI exits 1 with `recovery_event_id`, as before. The original stays stamped at every replacement stage, `text_removed` included: the memory-only forget clears the original's mark, and the lab stamps it again before the stage ends. `reconcile` runs `replace_text` again with the saved text change.

## Commands

```bash
uv run python -m cognee_lab.identity fixture --root outputs/stage6_entry --embedding loopback
uv run python -m cognee_lab.identity native-cognify --root outputs/stage6_entry
uv run python -m cognee_lab.identity retrieve --root outputs/stage6_entry
```

- `fixture` builds doc01 through `add`, then `cognify` (`remember_in_order`). Its output adds `cognify_stamps`: `original`, `identity` and `seed` are each `true`.
- `native-cognify` is a stand-in for a plain `cognee.cognify()` outside the lab, with Cognee's defaults. It prints `native_cognify.items`, the run result of each Data item. On a `fixture` root each of the three items is `PipelineRunAlreadyCompleted`, and `retrieve` then returns the same fact as before.
- `multi-fixture`, `chunked-fixture` and `glossary-fixture --chain` stamp every file they register too: `native-cognify` skips the five Data items of a two-source root and the seven of a chain root.
- `edit-text --source doc01 --expected-revision 1` on a `multi-fixture` root edits doc01 through the lab's `update`. doc01 reaches revision 2, and `native-cognify` then skips all five Data items.
- `fixture --fault-stage nodes|identity_edges|verification` fails the first publication at that stage. The command exits 1 with `recovery_event_id`. The stamps stay, so `native-cognify` still skips every item. `reconcile` restores the fact and resolves the incident with outcome `restored`.

Captured decisions prove lifecycle mechanics only. They do not prove extraction or search quality.
