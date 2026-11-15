"""Shared Home Assistant support for Sequent Microsystems cards."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Card:
    """Card-specific configuration and hardware API."""

    domain: str
    legacy_domain: str
    name_prefix: str
    full_name: str
    entity_map: dict[str, Any]
    api: Any
