from cognee.infrastructure.engine import DataPoint


class HeatingSystem(DataPoint):
    name: str
    heating_type: str

    metadata: dict = {
        "index_fields": ["name"],
        "identity_fields": ["name"],
    }


class Organization(DataPoint):
    name: str

    metadata: dict = {
        "index_fields": ["name"],
        "identity_fields": ["name"],
    }

    
class Facility(DataPoint):
    name: str
    description: str | None = None
    operator: Organization
    heating_systems: list[HeatingSystem]
    
    metadata: dict = {
        "index_fields": ["name"],
        "identity_fields": ["name"],
    }
