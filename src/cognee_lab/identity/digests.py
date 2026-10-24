"""The digest of a JSON value, which records and validation both take,
in a module that imports nothing of the package."""

from hashlib import sha256
from typing import Any

import rfc8785


def object_digest(value: Any) -> str:
    """The SHA-256 of the value's canonical JSON (RFC 8785)."""
    return sha256(rfc8785.dumps(value)).hexdigest()
