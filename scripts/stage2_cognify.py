import asyncio

import cognee

DATASET = "helios_stage2"


async def main():
    print("LLM provider:", cognee.config.get("llm_provider"))
    print("LLM model:", cognee.config.get("llm_model"))
    print("Embedding provider:", cognee.config.get("embedding_provider"))
    print("Embedding model:", cognee.config.get("embedding_model"))
    print("Embedding dimensions:", cognee.config.get("embedding_dimensions"))

    result = await cognee.cognify(
        datasets=DATASET,
        chunk_size=1000,
    )

    print("cognify() result:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())

    
