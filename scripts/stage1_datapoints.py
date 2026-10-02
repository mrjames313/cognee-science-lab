import asyncio
import cognee

import cognee_lab.models as md
from cognee.modules.engine.operations.setup import setup
from cognee.tasks.storage import add_data_points

from pathlib import Path


async def main():
    # Get the cognee database set up
    await setup()

    aurora = md.Organization(
        name="Aurora Fusion Research Laboratory",
    )

    nbi = md.HeatingSystem(
        name="Helios-1 Neutral Beam Injection System",
        heating_type="neutral beam injection",
    )

    ech = md.HeatingSystem(
        name="Helios-1 Electron Cyclotron Heating System",
        heating_type="electron cyclotron heating",
    )
    
    helios = md.Facility(
        name="Helios-1",
        description="Compact high-field tokamak",
        operator=aurora,
        heating_systems=[nbi, ech],
    )

    print("\nAurora:")
    print(aurora.model_dump())
#    print("Python object:")
#    print(helios)

    print("\nHelios:")
    print(helios.model_dump())

    await add_data_points([helios])

    output_path = Path("outputs/stage1_one_node.html").resolve()

    await cognee.visualize_graph(
        str(output_path),
        full=True,
    )

    print("Python object ID:", helios.id)
    
    print(f"\nGraph written to: {output_path}")

    
if __name__ == "__main__":
    asyncio.run(main())
