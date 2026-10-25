"""A captured stand-in for a delete outside the lab.

`native-forget` calls Cognee's own delete as a user would, with no ledger
row and no writer reservation, so nothing in the lab records it. `status`
then lists each saved source whose native copy is gone
(`native_copy.natively_deleted`), `reconcile` refuses it, and `forget` erases
the lab's copy.

- `data`: `cognee.forget(data_id=..., dataset_id=...)` on the selected
  source's original document.
- `dataset`: `cognee.forget(dataset=...)` on the root's dataset.
- `prune`: `cognee.prune.prune_data()`, then `cognee.prune.prune_system()`
  with its defaults, which keep the relational database and so the ledger.
"""

CASES = ("data", "dataset", "prune")


async def run(args, root):
    import cognee

    from .environment import DATASET_NAME
    from .multisource import root_files
    from .publish import Publisher
    from .validation import IntentError

    publisher = await Publisher.configured()
    args._fixture_publisher = publisher
    files = root_files(root)
    if args.source not in files:
        raise IntentError("source_missing", "Selected document is not in this fixture")
    source = files[args.source]
    deleted = dict(case=args.case)
    if args.case == "data":
        doc = source.inputs[source.original_input_ref]
        await cognee.forget(data_id=doc.data_id, dataset_id=source.dataset_id)
        deleted.update(source=args.source, data_id=str(doc.data_id))
    elif args.case == "dataset":
        await cognee.forget(dataset=DATASET_NAME)
        deleted.update(dataset_id=str(source.dataset_id))
    else:
        await cognee.prune.prune_data()
        await cognee.prune.prune_system()
    return dict(native_forget=deleted)
