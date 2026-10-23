"""Export the implementation schema; cross-record/runtime checks remain Python checks."""

import json
from pathlib import Path

from .models import IdentitySource


def schema():
    result = IdentitySource.model_json_schema()
    result["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    result["title"] = "Cognee identity source — implementation draft 0.1"
    result["description"] = (
        "Schema generated from runtime models. Cross-reference, exact text/range, "
        "dependency, UUID-use and publication checks also run in Python."
    )
    result["properties"]["entity_constructions"]["description"] = (
        "Each entry declares an Entity this source intends to retain, including supported "
        "singletons and existing endpoints, and supplies minimal creation values. All required "
        "endpoints need entries. Existing nodes bypass property writes; a recipe does not "
        "authorize reconstructing a missing reasoning input or retired intent."
    )
    result["properties"]["variant_assignments"][
        "description"
    ] = "Relationships independently established by this source, not a cached identity-graph walk."
    result["properties"]["inputs"][
        "description"
    ] = "Shared inputs/locators. Per-record input_refs declare actual reasoning dependencies."
    definitions = result["$defs"]
    definitions["SourceTextInput"]["properties"]["text_sha256"][
        "description"
    ] = "SHA-256 lowercase hex of exact extracted document string encoded as UTF-8, without normalization."
    definitions["TextSpanInput"]["properties"]["text_sha256"][
        "description"
    ] = "SHA-256 lowercase hex of UTF-8 document_text[start:end], excluding offsets and parent digest."
    definitions["CorpusObjectInput"]["properties"]["content_sha256"][
        "description"
    ] = "SHA-256 lowercase hex of RFC 8785 JCS UTF-8 of selected supplied field/value object; missing fields fail."
    definitions["SavedRecordInput"]["properties"]["content_sha256"]["description"] = (
        "SHA-256 lowercase hex of RFC 8785 JCS UTF-8 of the record's fingerprint: its "
        "record_type and reviewed fields, without producer_ref, input_refs and "
        "explanation; a mention resolution adds its group's entity_id."
    )
    return result


if __name__ == "__main__":
    target = Path("schemas/cognee_identity_source_schema_draft.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema(), indent=2, ensure_ascii=False) + "\n")
