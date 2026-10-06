import asyncio
from pathlib import Path

import cognee

from cognee.infrastructure.llm.extraction import extract_content_graph
from cognee.tasks.storage import add_data_points

from cognee_lab.models import (
    AbbreviationObservation,
    MixedKnowledgeGraph,
)


DATASET = "helios_stage4_source_linked"

DOCUMENT = Path(
    "data/DOC01_helios1_technical_overview_v2.md"
)


captured_chunk_graphs = []


async def calculate_chunk_graphs(
    data_chunks,
    graph_model,
    custom_prompt,
    **kwargs,
):
    # Cognee passes this callback itself through kwargs.
    # Do not send it onward to the LLM extraction function.
    extraction_kwargs = dict(kwargs)
    extraction_kwargs.pop("calculate_chunk_graphs", None)

    graphs = await asyncio.gather(
        *[
            extract_content_graph(
                chunk.text,
                graph_model,
                custom_prompt=custom_prompt,
                **extraction_kwargs,
            )
            for chunk in data_chunks
        ]
    )

    # asyncio.gather returns results in input order, so these pairs
    # are deterministic even though calls execute concurrently.
    captured_chunk_graphs.extend(
        zip(data_chunks, graphs)
    )

    return graphs


async def main():
    captured_chunk_graphs.clear()

    await cognee.add(
        str(DOCUMENT),
        dataset_name=DATASET,
    )

    await cognee.cognify(
        datasets=DATASET,
        graph_model=MixedKnowledgeGraph,
        chunk_size=1000,
        calculate_chunk_graphs=calculate_chunk_graphs,
    )

    observations = []

    print("\nCaptured source-linked abbreviations:")

    for chunk, graph in captured_chunk_graphs:
        print(
            f"\nchunk {chunk.chunk_index} "
            f"id={chunk.id}"
        )

        for abbreviation in graph.abbreviations:
            short_form = abbreviation.short_form.strip()
            full_form = abbreviation.full_form.strip()

            print(
                f"  {short_form!r}"
                f" -> {full_form!r}"
            )

            observations.append(
                AbbreviationObservation(
                    short_form=short_form,
                    full_form=full_form,
                    source_chunk_id=str(chunk.id),
                    source_chunk_index=chunk.chunk_index,
                    observed_in=chunk,
                )
            )

    # Deduplicate only identical observations from the SAME chunk.
    unique = {
        (
            observation.short_form,
            observation.full_form,
            observation.source_chunk_id,
        ): observation
        for observation in observations
    }

    observations = list(unique.values())

    print(
        f"\nCaptured {len(observations)} "
        "distinct source-linked observations."
    )

    await add_data_points(observations)

    print(
        f"Persisted {len(observations)} "
        "AbbreviationObservation nodes."
    )


if __name__ == "__main__":
    asyncio.run(main())
