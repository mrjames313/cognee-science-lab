import asyncio
import cognee
import uuid

from cognee import SearchType
from litellm import token_counter

DATASET = "helios_stage2"

QUERIES = [
    "What was the Campaign A plasma current limit?",
    "What is the installed NBI capacity?",
    "Does Helios-1 use tritium?",
    "What system controlled vertical motion?",
    "What tokamak does AFRL operate?",
]

QUERIES_3D = [
    # Unit inference that appeared in summaries but not semantic graph
    "What toroidal field was used during the early engineering pulses?",

    # Unit inference that DID survive into the semantic graph
    "What NBI power was authorized during actuator checkout?",

    # Operational/configuration fact vs intrinsic physical limit
    "Was 1.20 MA an intrinsic plasma stability limit for Helios-1?",

    # Ambiguous local coreference — VCS
    "In the VCS tuning sequence, what did 'the controller' refer to?",

    # Ambiguous local coreference — EDC
    "In the density-control checkout, what did 'the controller' refer to?",

    # Negative scientific claim
    "Did Campaign A demonstrate improved confinement caused by the density controller?",

    # Alias resolution
    "How much installed neutral-beam capacity did H-1 have?",
]

# Third argument is whether to use only_context in returning results
SEARCH_MODES = [
    (
        SearchType.CHUNKS,
        "Semantic/vector similarity search over document chunks.",
        False,
    ),
    (
        SearchType.CHUNKS_LEXICAL,
        "Lexical/keyword search over document chunks.",
        False,
    ),
    (
        SearchType.SUMMARIES,
        "Semantic search over precomputed chunk/document summaries.",
        False,
    ),
    # Stage 3C: answer generation
    (
        SearchType.RAG_COMPLETION,
        "Rag + completion: Answer generated from retrieved document context.",
        False,
    ),
    (
        SearchType.GRAPH_COMPLETION,
        "Graph + completion: Answer generated from graph-derived context.",
        False,
    ),
    (
        SearchType.HYBRID_COMPLETION,
        "Hybrid + completion: Answer generated from combined graph and document retrieval.",
        False,
    ),
]

RUN_ID = uuid.uuid4().hex

COMPLETION_MODEL = "openai/gpt-5.6-luna"

def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def preview(text: str, max_chars: int = 40000) -> str:
    text = normalize_whitespace(text)

    if len(text) <= max_chars:
        return text

    return text[: max_chars - 3] + "..."

def as_data(result):
    if hasattr(result, "model_dump"):
        return result.model_dump()

    if hasattr(result, "__dict__"):
        return vars(result)

    return result

def text_stats(text: str):
    chars = len(text)
    words = len(text.split())

    try:
        tokens = token_counter(
            model=COMPLETION_MODEL,
            text=text,
        )
    except Exception as e:
        tokens = None
        token_error = str(e)
    else:
        token_error = None

    return chars, words, tokens, token_error


def print_text_stats(text: str):
    chars, words, tokens, token_error = text_stats(text)

    print(f"     chars:  {chars:,}")
    print(f"     words:  {words:,}")

    if tokens is not None:
        print(f"     tokens: {tokens:,}")
    else:
        print("     tokens: unavailable")
        print(f"     token error: {token_error}")


def print_result(rank: int, result):
    if hasattr(result, "model_dump"):
        result = result.model_dump()

    elif hasattr(result, "__dict__"):
        result = vars(result)

    if isinstance(result, str):
        print(f"  {rank}")
        print_text_stats(result)
        print(f"    {preview(result)}")
        return

    if not isinstance(result, dict):
        text = str(result)
        print(f"  {rank}")
        print_text_stats(text)
        print(f"    {preview(text)}")
        return

    print(f"  {rank}.")

    score = result.get("score")
    if score is not None:
        print(f"     score: {score:.4f}")

    chunk_index = result.get("chunk_index")
    source_chunk_id = result.get("source_chunk_id")

    if chunk_index is not None:
        print(f"     chunk: {chunk_index}")
    elif source_chunk_id is not None:
        print(f"     source_chunk_id: {source_chunk_id}")

    for key in ("answer", "text", "content", "result"):
        if key in result and result[key] is not None:
            text = str(result[key])
            print_text_stats(text)
            print(f"     {preview(str(result[key]))}")
            return

async def main():

    # Set the relevant params here
    queries = QUERIES_3D
    top_k = 2
    
    for search_type, description,only_context in SEARCH_MODES:
        print("\n" + "=" * 80)
        print(search_type.value)
        print(description)
        print(f"only_context={only_context}")
        print("=" * 80)

        for query_index, query in enumerate(queries):
            session_id = (
                f"stage3-{RUN_ID}-"
                f"{search_type.value}-{query_index}"
            )
            print(f"\nQUERY: {query}")

            results = await cognee.search(
                query_text=query,
                query_type=search_type,
                datasets=DATASET,
                top_k=top_k,
                session_id=session_id,
                only_context=only_context,  # True argument skips the LLM interpretation step
            )

            # Normalize just in case a search type returns a single object.
            if not isinstance(results, (list, tuple)):
                results = [results]

            print(f"    results: {len(results)}")

            for i, result in enumerate(results, start=1):
                print_result(i, result)

            print()

            
if __name__ == "__main__":
    asyncio.run(main())
    
 
