import asyncio
import cognee

async def main():
    await cognee.prune.prune_data()

    await cognee.prune.prune_system(
        graph=True,
        vector=True,
        metadata=True,
        cache=True,
    )

if __name__ == "__main__":
    asyncio.run(main())
    
