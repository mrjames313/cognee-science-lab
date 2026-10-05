import inspect
import cognee
from cognee import SearchType

def main():
    print("cognee.search signature:")
    print(inspect.signature(cognee.search))

    print("\nAvailable SearchType values:")

    for search_type in SearchType:
        print(
            f"  {search_type.name:40} "
            f"value={search_type.value!r}"
        )

if __name__ == "__main__":
    main()
