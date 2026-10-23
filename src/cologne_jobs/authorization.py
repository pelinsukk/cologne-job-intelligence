"""Fail-closed assessment policy and bundled, evidence-linked source registry."""

import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

from cologne_jobs.models import AuthorizationState, CollectionError

ASSESSMENT_MAX_DAYS = 90


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    official_url: str
    method: str
    state: AuthorizationState = AuthorizationState.UNKNOWN
    enabled: bool = False
    documentation: tuple[str, ...] = ()
    license: str = "unknown"
    robots_assessment: str = "not assessed"
    fields: tuple[str, ...] = ()
    rate_limits: str = "not assessed"
    restrictions: str = "Not authorized"
    assessed_on: str | None = None
    confidence: str = "unknown"
    min_interval: float = 5.0
    refresh_seconds: int = 86400
    endpoint: str | None = None
    robots_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "Source":
        value = dict(value)
        value["state"] = AuthorizationState(value.get("state", "UNKNOWN"))
        for key in ("documentation", "fields"):
            value[key] = tuple(value.get(key, ()))
        return cls(**value)


def authorize(source: Source, today: date | None = None) -> None:
    if source.state != AuthorizationState.PERMITTED or source.enabled is not True:
        raise CollectionError(f"Source {source.id}: {source.state}, enabled={source.enabled}")
    today = today or datetime.now(UTC).date()
    try:
        age = (today - date.fromisoformat(source.assessed_on or "")).days
    except ValueError:
        age = -1
    if not 0 <= age <= ASSESSMENT_MAX_DAYS:
        raise CollectionError(f"Source {source.id}: assessment missing, future-dated or expired")

    def meaningful(value: object) -> bool:
        return isinstance(value, str) and value.strip().casefold() not in {
            "",
            "unknown",
            "not assessed",
            "not authorized",
        }

    if not (
        source.documentation
        and all(meaningful(item) for item in source.documentation)
        and source.fields
        and all(meaningful(item) for item in source.fields)
        and meaningful(source.license)
        and source.confidence == "high"
        and meaningful(source.robots_assessment)
        and meaningful(source.rate_limits)
        and meaningful(source.restrictions)
    ):
        raise CollectionError(f"Source {source.id}: insufficient authorization evidence")
    if (
        not isinstance(source.min_interval, int | float)
        or not math.isfinite(source.min_interval)
        or source.min_interval < 1
        or not isinstance(source.refresh_seconds, int)
        or source.refresh_seconds < 60
    ):
        raise CollectionError(f"Source {source.id}: unsafe rate configuration")


def initial_sources() -> list[Source]:
    return [
        Source(
            id="wikidata-sparql",
            name="Wikidata Query Service",
            official_url="https://query.wikidata.org/",
            method="SPARQL GET",
            state=AuthorizationState.BLOCKED,
            documentation=(
                "https://www.wikidata.org/wiki/Wikidata:Data_access",
                "https://www.wikidata.org/wiki/Wikidata:Licensing",
                "https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual",
                "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
                "https://query.wikidata.org/robots.txt",
            ),
            license="CC0-1.0 (structured data only)",
            robots_assessment="2026-10-24: HTTP 200; User-agent: *; Disallow: /sparql, /bigdata",
            fields=("organization name", "entity ID", "website", "headquarters claim"),
            rate_limits="60 query seconds/60 seconds; 30 error queries/min; max 5 parallel",
            restrictions="Project policy respects robots.txt: /sparql prohibited. No query sent.",
            assessed_on="2026-10-24",
            confidence="high",
        ),
        Source(
            id="osm-overpass",
            name="OpenStreetMap via FOSSGIS Overpass",
            official_url="https://overpass-api.de/",
            method="Overpass QL GET",
            state=AuthorizationState.BLOCKED,
            documentation=(
                "https://dev.overpass-api.de/overpass-doc/en/preface/commons.html",
                "https://www.openstreetmap.org/copyright",
                "https://overpass-api.de/robots.txt",
            ),
            license="ODbL-1.0; attribution and share-alike obligations on distribution",
            robots_assessment="2026-10-24: HTTP 200; User-agent: *; Disallow: /api/, /munin/",
            fields=("organization name", "OSM ID", "website", "location"),
            rate_limits="Guideline: under 10000 queries/day and 1 GB/day; server slot quotas",
            restrictions="Project policy respects robots.txt: /api/ prohibited. No query sent.",
            assessed_on="2026-10-24",
            confidence="high",
        ),
        Source(
            id="local-json",
            name="User supplied employer JSON",
            official_url="local-file",
            method="local JSON file",
            restrictions="Requires explicit dataset-specific rights assessment before import",
            robots_assessment="Not applicable: local file only; no network access",
        ),
        *[
            Source(
                id=key,
                name=name,
                official_url=url,
                method="unimplemented",
                restrictions="No automated access permission established; never collected",
            )
            for key, name, url in (
                ("ihk-koeln", "IHK Köln", "https://www.ihk.de/koeln/"),
                ("koelnbusiness", "KölnBusiness", "https://koeln.business/"),
                ("linkedin", "LinkedIn", "https://www.linkedin.com/"),
                ("indeed", "Indeed", "https://de.indeed.com/"),
                ("stepstone", "StepStone", "https://www.stepstone.de/"),
                ("xing", "XING", "https://www.xing.com/"),
            )
        ],
    ]
