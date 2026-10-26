"""The IDENTITY SearchType: `cognee.search(query, query_type=SearchType.IDENTITY,
datasets=[name])` returns what the lab's `retrieve_settled` returns, with no LLM.

Importing this module adds IDENTITY to Cognee's closed SearchType enum and
registers `IdentityRetriever` for it, or fails the import (`register`). It
imports cognee, so configure the process first. A model that validates
SearchType from JSON and was built before this import, such as Cognee's HTTP
router DTOs, rejects IDENTITY, and the `cognee search` CLI never imports the
lab, so neither can name it.

The first search in a process opens the configured stores through
`Publisher.configured`, which creates the lab's ledger tables in Cognee's
relational database when they are missing.
"""

import json
import pickle
import sys

import cognee
from cognee.modules.retrieval.base_retriever import BaseRetriever
from cognee.modules.retrieval.register_retriever import use_retriever
from cognee.modules.retrieval.registered_community_retrievers import (
    registered_community_retrievers,
)
from cognee.modules.search.types import SearchType

from .retrieve import (
    LIMIT,
    SearchMode,
    SearchRefused,
    SearchScope,
    refuse_unbuilt,
    retrieve_settled,
)

NAME = "IDENTITY"
# The enum internals `add_member` writes are those of Python 3.12's enum
# module, and Cognee 1.6.2 is the version whose search path was inspected.
COGNEE_VERSION = "1.6.2"
PYTHON = (3, 12)
CONFIG_KEYS = {"scope", "mode"}


class RegistrationError(RuntimeError):
    """IDENTITY cannot join SearchType safely in this process."""


def parse_config(config) -> tuple[SearchScope, SearchMode]:
    """`retriever_specific_config`: an optional `scope` and `mode`."""
    config = dict(config or {})
    if unknown := sorted(set(config) - CONFIG_KEYS):
        raise SearchRefused(
            "config_invalid",
            f"Unknown retriever_specific_config keys {unknown}; "
            f"IDENTITY takes {sorted(CONFIG_KEYS)}",
        )
    try:
        return (
            SearchScope(config.get("scope", SearchScope.IDENTITY)),
            SearchMode(config.get("mode", SearchMode.SEMANTIC)),
        )
    except ValueError as exc:
        raise SearchRefused("config_invalid", str(exc)) from None


class IdentityRetriever(BaseRetriever):
    """Serves the identity-anchored facts of one dataset's served sources.

    Every refusal raises in the constructor, which Cognee calls before it
    reads anything or logs the query. Context is the result as JSON text and
    the completion is `[result]`, so no LLM runs."""

    supports_session_turn_preparation = False
    supports_prompt_preview = False

    def __init__(self, dataset=None, top_k=LIMIT, retriever_specific_config=None, **_):
        from cognee.context_global_variables import backend_access_control_enabled

        if backend_access_control_enabled():
            raise SearchRefused(
                "access_control_on",
                "IDENTITY runs only with ENABLE_BACKEND_ACCESS_CONTROL=false; "
                "the lab's ledger lives in the one shared relational database",
            )
        if dataset is None:
            raise SearchRefused(
                "dataset_required",
                "IDENTITY searches one dataset; pass datasets=[name] when the "
                "user can read more than one",
            )
        self.scope, self.mode = parse_config(retriever_specific_config)
        refuse_unbuilt(self.scope, self.mode)
        self.dataset, self.top_k = dataset, top_k

    async def get_retrieved_objects(self, query, query_batch=None):
        from .publish import Publisher

        return await retrieve_settled(
            await Publisher.configured(),
            self.dataset.id,
            query,
            limit=self.top_k,
            scope=self.scope,
            mode=self.mode,
        )

    async def get_context_from_objects(
        self, query=None, query_batch=None, retrieved_objects=None
    ):
        return json.dumps(retrieved_objects, ensure_ascii=False)

    async def get_completion_from_context(
        self, query=None, query_batch=None, retrieved_objects=None, context=None
    ):
        return [retrieved_objects]

    def get_context_evidence(self, retrieved_objects, dataset_id=None):
        """Each fact as a triplet and each of its checked chunks as a segment
        that supports it. No `graph_edge`: Cognee would resolve one through
        the edge sidecar, which lists every document's chunks, served or not."""
        from cognee.modules.search.models.EvidenceReference import (
            EvidenceReference,
        )

        references = []
        for rank, fact in enumerate(retrieved_objects["facts"]):
            references.append(
                EvidenceReference(
                    kind="triplet",
                    artifact_id=fact["edge_id"],
                    dataset_id=retrieved_objects["dataset_id"],
                    source_node_id=fact["source_id"],
                    target_node_id=fact["target_id"],
                    relationship_name=fact["relationship"],
                    label=fact["text"],
                    rank=rank,
                    score=fact["score"],
                )
            )
            references += [
                EvidenceReference(
                    kind="segment",
                    artifact_id=chunk["chunk_id"],
                    role="supports_assertion",
                    assertion_id=fact["edge_id"],
                    dataset_id=retrieved_objects["dataset_id"],
                    data_id=chunk["data_id"],
                    chunk_id=chunk["chunk_id"],
                    chunk_index=chunk["chunk_index"],
                    rank=rank,
                )
                for chunk in fact["evidence"]
            ]
        return references


def add_member(enum_cls, name):
    """Add `name` to a str Enum through Python 3.12's enum internals. Filling
    the member maps does not set the class attribute, so set it as well."""
    member = str.__new__(enum_cls, name)
    member._name_ = name
    member._value_ = name
    member._sort_order_ = len(enum_cls._member_names_)
    member.__objclass__ = enum_cls
    type.__setattr__(enum_cls, name, member)
    enum_cls._member_map_[name] = member
    enum_cls._value2member_map_[name] = member
    enum_cls._member_names_.append(name)
    return member


def self_test(member):
    """The uses of IDENTITY that `cognee.search` and its results rely on."""
    from cognee.modules.search.models.SearchResultPayload import SearchResultPayload

    def payload():
        return SearchResultPayload(
            result_object={}, context="{}", completion=[{}], search_type=member
        )

    checks = dict(
        getitem=lambda: SearchType[NAME] is member,
        call=lambda: SearchType(NAME) is member,
        attribute=lambda: getattr(SearchType, NAME) is member,
        members=lambda: SearchType.__members__.get(NAME) is member,
        iteration=lambda: [m for m in SearchType if m.value == NAME] == [member],
        pickle=lambda: pickle.loads(pickle.dumps(member)) is member,
        payload=lambda: payload().model_dump()["search_type"] is member,
        payload_by_value=lambda: SearchResultPayload.model_validate(
            {"search_type": NAME}
        ).search_type
        is member,
        registry=lambda: registered_community_retrievers.get(member)
        is IdentityRetriever,
    )
    failed = []
    for name, check in checks.items():
        try:
            passed = check()
        except Exception:
            passed = False
        if not passed:
            failed.append(name)
    if failed:
        raise RegistrationError(f"IDENTITY failed its self-test: {failed}")


def register():
    """Add IDENTITY to SearchType and register `IdentityRetriever` for it.
    Idempotent. Refuses another Cognee or Python version, and an IDENTITY
    member it did not add, since registering a retriever under an existing
    member silently replaces that member's retriever."""
    if cognee.__version__ != COGNEE_VERSION:
        raise RegistrationError(
            f"IDENTITY was built against cognee {COGNEE_VERSION}, "
            f"found {cognee.__version__}"
        )
    if tuple(sys.version_info[:2]) != PYTHON:
        raise RegistrationError(
            "IDENTITY extends SearchType through Python 3.12's enum internals, "
            f"found Python {sys.version_info[0]}.{sys.version_info[1]}"
        )
    member = SearchType._member_map_.get(NAME)
    if member is None:
        member = add_member(SearchType, NAME)
        use_retriever(member, IdentityRetriever)
    elif registered_community_retrievers.get(member) is not IdentityRetriever:
        raise RegistrationError(
            f"SearchType already has {NAME}, which the lab did not add; "
            "registering would replace its retriever"
        )
    self_test(member)
    return member


IDENTITY = register()
