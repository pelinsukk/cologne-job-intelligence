"""Small immutable records; source claims are not independently verified facts."""

from dataclasses import dataclass
from enum import StrEnum


class AuthorizationState(StrEnum):
    PERMITTED = "PERMITTED"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Employer:
    external_id: str
    name: str
    source_url: str
    website: str | None = None
    aliases: tuple[str, ...] = ()
    industry: str | None = None
    location_evidence: str = "unknown"
    confidence: str = "source_claim"


class CollectionError(Exception):
    """Safe, user-readable failure without secrets or response bodies."""
