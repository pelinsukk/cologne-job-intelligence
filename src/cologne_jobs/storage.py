"""SQLite v1. Upserts preserve first-seen, previous claims and source provenance."""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from cologne_jobs.authorization import Source, initial_sources
from cologne_jobs.models import CollectionError, Employer
from cologne_jobs.normalization import clean_name, normalize_name, normalize_url

SCHEMA = """
CREATE TABLE sources(id TEXT PRIMARY KEY, assessment TEXT NOT NULL);
CREATE TABLE source_runtime(
 source_id TEXT PRIMARY KEY REFERENCES sources(id),
 denied_reason TEXT, cooldown_until REAL NOT NULL DEFAULT 0,
 next_request REAL NOT NULL DEFAULT 0, last_success REAL,
 lease_until REAL NOT NULL DEFAULT 0
);
CREATE TABLE audit(
 id INTEGER PRIMARY KEY, at REAL NOT NULL, source_id TEXT NOT NULL,
 event TEXT NOT NULL, detail TEXT NOT NULL, status INTEGER,
 assessment TEXT NOT NULL
);
CREATE TABLE employers(
 id INTEGER PRIMARY KEY, canonical_name TEXT NOT NULL, normalized_name TEXT NOT NULL,
 website TEXT, industry TEXT, cologne_presence TEXT NOT NULL DEFAULT 'source_claim',
 confidence TEXT NOT NULL, monitoring_status TEXT NOT NULL DEFAULT 'not_started',
 careers_url TEXT, ats_provider TEXT, last_successful_scan REAL,
 first_seen REAL NOT NULL, last_seen REAL NOT NULL
);
CREATE TABLE aliases(
 employer_id INTEGER NOT NULL REFERENCES employers(id), alias TEXT NOT NULL,
 UNIQUE(employer_id, alias)
);
CREATE TABLE provenance(
 source_id TEXT NOT NULL REFERENCES sources(id), external_id TEXT NOT NULL,
 employer_id INTEGER NOT NULL REFERENCES employers(id), source_url TEXT NOT NULL,
 first_seen REAL NOT NULL, last_seen REAL NOT NULL,
 PRIMARY KEY(source_id, external_id)
);
CREATE TABLE observations(
 id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, external_id TEXT NOT NULL,
 employer_id INTEGER NOT NULL REFERENCES employers(id), payload TEXT NOT NULL,
 first_seen REAL NOT NULL, last_seen REAL NOT NULL,
 UNIQUE(source_id, external_id, payload)
);
CREATE TABLE discovery_runs(
 id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, started REAL NOT NULL, finished REAL,
 status TEXT NOT NULL, fetched INTEGER NOT NULL DEFAULT 0,
 created INTEGER NOT NULL DEFAULT 0, updated INTEGER NOT NULL DEFAULT 0,
 error TEXT
);
CREATE INDEX employers_name ON employers(normalized_name);
PRAGMA user_version=1;
"""


class Store:
    def __init__(self, path: Path | str):
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self.db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "COMMIT;")
        elif version != 1:
            self.db.close()
            raise CollectionError(f"Unsupported database schema: {version}")
        with self.db:
            for source in initial_sources():
                self.db.execute(
                    "INSERT OR IGNORE INTO sources VALUES (?,?)",
                    (source.id, json.dumps(source.to_dict())),
                )
                self.db.execute(
                    "INSERT OR IGNORE INTO source_runtime(source_id) VALUES (?)", (source.id,)
                )

    def close(self) -> None:
        self.db.close()

    def source(self, source_id: str) -> Source:
        row = self.db.execute("SELECT assessment FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise CollectionError(f"Unregistered source: {source_id}")
        return Source.from_dict(json.loads(row[0]))

    def save_source(self, source: Source) -> None:
        with self.db:
            self.db.execute(
                "UPDATE sources SET assessment=? WHERE id=?",
                (json.dumps(source.to_dict()), source.id),
            )
            self.audit(source.id, "assessment_changed", "Explicit local assessment/control change")

    def audit(self, source_id: str, event: str, detail: str, status: int | None = None) -> None:
        source = self.db.execute(
            "SELECT assessment FROM sources WHERE id=?", (source_id,)
        ).fetchone()
        with self.db:
            self.db.execute(
                "INSERT INTO audit(at,source_id,event,detail,status,assessment) "
                "VALUES (?,?,?,?,?,?)",
                (time.time(), source_id, event, detail, status, source[0] if source else "{}"),
            )

    def runtime(self, source_id: str) -> sqlite3.Row:
        return self.db.execute(
            "SELECT * FROM source_runtime WHERE source_id=?", (source_id,)
        ).fetchone()

    def check_runtime(self, source_id: str, now: float) -> None:
        row = self.runtime(source_id)
        if row["denied_reason"]:
            raise CollectionError(f"Source {source_id}: latched denial: {row['denied_reason']}")
        if now < row["cooldown_until"]:
            raise CollectionError(f"Source {source_id}: cooldown until {row['cooldown_until']:.0f}")

    def deny(self, source_id: str, reason: str) -> None:
        with self.db:
            self.db.execute(
                "UPDATE source_runtime SET denied_reason=? WHERE source_id=?", (reason, source_id)
            )

    def cooldown(self, source_id: str, until: float) -> None:
        with self.db:
            self.db.execute(
                "UPDATE source_runtime SET cooldown_until=MAX(cooldown_until,?) WHERE source_id=?",
                (until, source_id),
            )

    def reserve_request(self, source_id: str, interval: float, now: float) -> float:
        # Atomic reservation makes throttling persist across processes and manual runs.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.check_runtime(source_id, now)
            scheduled = max(now, self.runtime(source_id)["next_request"])
            self.db.execute(
                "UPDATE source_runtime SET next_request=? WHERE source_id=?",
                (scheduled + interval, source_id),
            )
        return scheduled - now

    @contextmanager
    def discovery_lease(self, source_id: str):
        now = time.time()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.runtime(source_id)["lease_until"] > now:
                raise CollectionError("Another discovery is running; try again later")
            self.db.execute(
                "UPDATE source_runtime SET lease_until=? WHERE source_id=?", (now + 600, source_id)
            )
        try:
            yield
        finally:
            with self.db:
                self.db.execute(
                    "UPDATE source_runtime SET lease_until=0 WHERE source_id=?", (source_id,)
                )

    def persist(self, source_id: str, employers: list[Employer]) -> tuple[int, int]:
        created = updated = 0
        now = time.time()
        # Entire batch rolls back if any record is invalid.
        with self.db:
            for employer in employers:
                name = clean_name(employer.name)
                website = normalize_url(employer.website)
                aliases = {clean_name(a) for a in (*employer.aliases, name)}
                if not employer.external_id or not employer.source_url:
                    raise ValueError("Every employer requires an external ID and provenance URL")
                row = self.db.execute(
                    "SELECT employer_id FROM provenance WHERE source_id=? AND external_id=?",
                    (source_id, employer.external_id),
                ).fetchone()
                stable_identity = row is not None
                # Cross-source matches require both exact normalized name and exact URL.
                # Ambiguous matches remain distinct; shared corporate domains are not identity.
                if not row and website:
                    matches = self.db.execute(
                        "SELECT id FROM employers WHERE normalized_name=? AND website=?",
                        (normalize_name(name), website),
                    ).fetchall()
                    if len(matches) == 1:
                        row = matches[0]
                if row:
                    employer_id = row[0]
                    self.db.execute(
                        "UPDATE employers SET last_seen=? WHERE id=?", (now, employer_id)
                    )
                    if stable_identity:
                        self.db.execute(
                            "UPDATE employers SET canonical_name=?,normalized_name=?,"
                            "website=COALESCE(?,website),industry=COALESCE(?,industry) WHERE id=?",
                            (name, normalize_name(name), website, employer.industry, employer_id),
                        )
                    updated += 1
                else:
                    cursor = self.db.execute(
                        "INSERT INTO employers(canonical_name,normalized_name,website,industry,"
                        "cologne_presence,confidence,first_seen,last_seen) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (
                            name,
                            normalize_name(name),
                            website,
                            employer.industry,
                            employer.location_evidence,
                            employer.confidence,
                            now,
                            now,
                        ),
                    )
                    employer_id = cursor.lastrowid
                    created += 1
                for alias in aliases:
                    self.db.execute(
                        "INSERT OR IGNORE INTO aliases VALUES (?,?)", (employer_id, alias)
                    )
                self.db.execute(
                    "INSERT INTO provenance VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(source_id,external_id) "
                    "DO UPDATE SET last_seen=excluded.last_seen,source_url=excluded.source_url",
                    (source_id, employer.external_id, employer_id, employer.source_url, now, now),
                )
                payload = json.dumps(
                    {
                        "name": name,
                        "website": website,
                        "industry": employer.industry,
                        "location_evidence": employer.location_evidence,
                        "confidence": employer.confidence,
                    },
                    sort_keys=True,
                )
                self.db.execute(
                    "INSERT INTO observations(source_id,external_id,employer_id,payload,first_seen,"
                    "last_seen) VALUES (?,?,?,?,?,?) ON CONFLICT(source_id,external_id,payload) "
                    "DO UPDATE SET last_seen=excluded.last_seen",
                    (source_id, employer.external_id, employer_id, payload, now, now),
                )
            self.db.execute(
                "UPDATE source_runtime SET last_success=? WHERE source_id=?", (now, source_id)
            )
        return created, updated
