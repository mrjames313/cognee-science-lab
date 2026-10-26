"""The search request and `retrieve_settled`, the one entry the CLI `retrieve`
and the IDENTITY SearchType (search.py) share. Importing this module changes
nothing in Cognee."""

from dataclasses import dataclass
from enum import StrEnum

from .retrieve import LIMIT, retrieve
from .validation import IntentError


class SearchScope(StrEnum):
    """What a search returns: identity-anchored facts only (the default), or
    also native hits no saved source attributes, which is not built yet."""

    IDENTITY = "identity"
    IDENTITY_AND_UNATTRIBUTED = "identity_and_unattributed"


class SearchMode(StrEnum):
    """How facts are found: from the saved decisions (`semantic`), or by
    source as well (`source_aware`), which is not built yet."""

    SEMANTIC = "semantic"
    SOURCE_AWARE = "source_aware"


class SearchRefused(IntentError):
    """A search the lab refuses before it reads the ledger. Through
    `cognee.search` it fails the whole search, before Cognee logs the query."""


NOT_BUILT = {
    SearchScope.IDENTITY_AND_UNATTRIBUTED: (
        "scope_not_built",
        "Scope identity_and_unattributed is not built; search with scope identity",
    ),
    SearchMode.SOURCE_AWARE: (
        "mode_not_built",
        "Mode source_aware is not built; search with mode semantic",
    ),
}
# A writer changed the ledger during the read: a source's row moved
# (`retrieval_changed`), or a writer began on a source that retrieval was
# failing (`stale_attempt` from RecordStore.fail). A second read sees the new
# rows.
UNSETTLED = {"retrieval_changed", "stale_attempt"}


@dataclass(frozen=True)
class SearchRequest:
    """A scope and a mode that are built. Make one with `parse`."""

    scope: SearchScope
    mode: SearchMode

    @classmethod
    def parse(cls, scope=None, mode=None) -> "SearchRequest":
        """None takes the default. A value neither enum knows is
        `config_invalid`; a value not built yet is refused with its code."""
        try:
            request = cls(
                SearchScope.IDENTITY if scope is None else SearchScope(scope),
                SearchMode.SEMANTIC if mode is None else SearchMode(mode),
            )
        except ValueError as exc:
            raise SearchRefused("config_invalid", str(exc)) from None
        for value in (request.scope, request.mode):
            if value in NOT_BUILT:
                raise SearchRefused(*NOT_BUILT[value])
        return request


async def retrieve_settled(publisher, dataset_id, query, request, *, limit=LIMIT):
    """`retrieve`, read once more if a writer changed the ledger during the
    first read, with the scope, the mode and the dataset beside the facts."""
    try:
        found = await retrieve(publisher, dataset_id, query, limit=limit)
    except IntentError as exc:
        if exc.code not in UNSETTLED:
            raise
        found = await retrieve(publisher, dataset_id, query, limit=limit)
    return dict(
        mode=request.mode.value,
        scope=request.scope.value,
        dataset_id=str(dataset_id),
        **found,
    )
