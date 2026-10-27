"""The search request and `retrieve_settled`, the one entry the CLI `retrieve`
and the IDENTITY SearchType (search.py) share. Importing this module changes
nothing in Cognee."""

from dataclasses import dataclass, fields
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
    """A scope and a mode that are built. Constructing one with a value that
    neither enum knows is `config_invalid`; with a value not built yet, it is
    refused with that value's code."""

    scope: SearchScope = SearchScope.IDENTITY
    mode: SearchMode = SearchMode.SEMANTIC

    def __post_init__(self):
        try:
            object.__setattr__(self, "scope", SearchScope(self.scope))
            object.__setattr__(self, "mode", SearchMode(self.mode))
        except ValueError as exc:
            raise SearchRefused("config_invalid", str(exc)) from None
        for value in (self.scope, self.mode):
            if value in NOT_BUILT:
                raise SearchRefused(*NOT_BUILT[value])

    @classmethod
    def parse(cls, scope=None, mode=None) -> "SearchRequest":
        """None takes the default."""
        given = dict(scope=scope, mode=mode)
        return cls(**{key: value for key, value in given.items() if value is not None})

    @classmethod
    def from_config(cls, config) -> "SearchRequest":
        """A request from `retriever_specific_config`, which takes only the
        request's fields."""
        config = config or {}
        known = {f.name for f in fields(cls)}
        if unknown := sorted(set(config) - known):
            raise SearchRefused(
                "config_invalid",
                f"Unknown retriever_specific_config keys {unknown}; "
                f"IDENTITY takes {sorted(known)}",
            )
        return cls.parse(**config)


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
