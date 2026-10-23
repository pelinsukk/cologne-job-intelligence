"""Operational M0/M1 commands only. JSON output is safe for local scripting."""

import argparse
import json
import os
import platform
import sqlite3
import sys
import time
from dataclasses import replace
from pathlib import Path

from cologne_jobs.authorization import Source, authorize
from cologne_jobs.discovery import discover
from cologne_jobs.models import CollectionError
from cologne_jobs.storage import Store


def default_db() -> Path:
    if value := os.environ.get("COLOGNE_JOBS_DB"):
        return Path(value).expanduser()
    base = (
        Path.home() / "Library/Application Support"
        if sys.platform == "darwin"
        else Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    )
    return base / "cologne-jobs/employers.sqlite3"


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(description="Local employer registry (M0/M1 only)")
    app.add_argument(
        "--db", type=Path, default=default_db(), help="SQLite file (or COLOGNE_JOBS_DB)"
    )
    commands = app.add_subparsers(dest="command", required=True)
    discovery = commands.add_parser("discover", help="Discover through authorized local JSON only")
    discovery.add_argument("--source", default="local-json")
    discovery.add_argument("--file", type=Path)
    employers = commands.add_parser(
        "employers", help="List employers or inspect ID with provenance"
    )
    employers.add_argument("id", nargs="?", type=int)
    employers.add_argument("--limit", type=int, default=50)
    employers.add_argument("--offset", type=int, default=0)
    sources = commands.add_parser("sources", help="Inspect/control authorization registry")
    source_commands = sources.add_subparsers(dest="action")
    for action in ("enable", "disable"):
        control = source_commands.add_parser(action)
        control.add_argument("id")
    assessment = source_commands.add_parser("assess", help="Load local-json rights assessment")
    assessment.add_argument("file", type=Path)
    commands.add_parser("status", help="Counts, coverage, source freshness and latest runs")
    commands.add_parser("doctor", help="Local diagnostic checks; never sends network requests")
    audit = commands.add_parser("audit", help="Inspect recent collection/control audit records")
    audit.add_argument("--limit", type=int, default=20)
    return app


def source_report(store: Store) -> list[dict]:
    result = []
    for row in store.db.execute("SELECT id FROM sources ORDER BY id").fetchall():
        source = store.source(row[0])
        reason = None
        try:
            authorize(source)
            store.check_runtime(source.id, time.time())
        except CollectionError as exc:
            reason = str(exc)
        result.append(
            dict(
                source.to_dict(),
                effective_collection_allowed=reason is None,
                denial_reason=reason,
                runtime=dict(store.runtime(source.id)),
            )
        )
    return result


def run(args: argparse.Namespace, store: Store) -> None:
    if args.command == "sources":
        if args.action in {"enable", "disable"}:
            source = store.source(args.id)
            source = replace(source, enabled=args.action == "enable")
            if source.enabled:
                authorize(source)
                store.check_runtime(source.id, time.time())
            store.save_source(source)
        elif args.action == "assess":
            source = Source.from_dict(json.loads(args.file.read_text()))
            if source.id != "local-json" or source.method != "local JSON file":
                raise CollectionError("M1 assessments support local-json only")
            if source.endpoint or source.robots_url:
                raise CollectionError("Local imports may not define network endpoints")
            if source.enabled:
                authorize(source)
            if not any(
                value.startswith("sha256:") and len(value) == 71 for value in source.documentation
            ):
                raise CollectionError("Local assessment requires sha256:<64 hex digits> evidence")
            store.save_source(source)
        emit(source_report(store))
    elif args.command == "discover":
        emit(discover(store, args.source, args.file))
    elif args.command == "employers":
        if args.limit < 1 or args.limit > 1000 or args.offset < 0:
            raise CollectionError("Use limit 1..1000 and offset >= 0")
        if args.id is None:
            rows = store.db.execute(
                "SELECT * FROM employers ORDER BY id LIMIT ? OFFSET ?", (args.limit, args.offset)
            ).fetchall()
            emit([dict(row) for row in rows])
        else:
            row = store.db.execute("SELECT * FROM employers WHERE id=?", (args.id,)).fetchone()
            if row is None:
                raise CollectionError("Employer ID not found")
            emit(
                dict(row)
                | {
                    "aliases": [
                        r[0]
                        for r in store.db.execute(
                            "SELECT alias FROM aliases WHERE employer_id=? ORDER BY alias",
                            (args.id,),
                        )
                    ],
                    "provenance": [
                        dict(r)
                        for r in store.db.execute(
                            "SELECT * FROM provenance WHERE employer_id=?", (args.id,)
                        )
                    ],
                    "observations": [
                        dict(r)
                        for r in store.db.execute(
                            "SELECT * FROM observations WHERE employer_id=?", (args.id,)
                        )
                    ],
                }
            )
    elif args.command == "status":
        sources = source_report(store)
        count = store.db.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
        eligible = sum(s["effective_collection_allowed"] for s in sources)
        emit(
            {
                "database": str(args.db.expanduser().resolve()),
                "employers": count,
                "sources_registered": len(sources),
                "sources_effectively_allowed": eligible,
                "sources_disabled_or_denied": len(sources) - eligible,
                "coverage": "Unknown denominator: no claim of exhaustive Cologne coverage",
                "employer_claims": "Source claims; no independent presence/website verification",
                "live_discovery": "Unavailable: assessed API paths disallowed by robots.txt",
                "recent_runs": [
                    dict(r)
                    for r in store.db.execute(
                        "SELECT * FROM discovery_runs ORDER BY id DESC LIMIT 10"
                    )
                ],
                "source_health": [
                    {
                        "id": s["id"],
                        "state": s["state"],
                        "enabled": s["enabled"],
                        "denial_reason": s["denial_reason"],
                        "runtime": s["runtime"],
                    }
                    for s in sources
                ],
            }
        )
    elif args.command == "doctor":
        integrity = store.db.execute("PRAGMA quick_check").fetchone()[0]
        foreign_keys = store.db.execute("PRAGMA foreign_key_check").fetchall()
        emit(
            {
                "python": platform.python_version(),
                "sqlite": sqlite3.sqlite_version,
                "schema_version": store.db.execute("PRAGMA user_version").fetchone()[0],
                "integrity": integrity,
                "foreign_key_errors": len(foreign_keys),
                "database": str(args.db.expanduser().resolve()),
                "network_checked": False,
                "paid_services": False,
                "operational": [
                    "discover (authorized local JSON)",
                    "employers",
                    "sources",
                    "status",
                    "doctor",
                    "audit",
                ],
            }
        )
        if integrity != "ok" or foreign_keys:
            raise CollectionError("Database integrity check failed")
    elif args.command == "audit":
        if not 1 <= args.limit <= 1000:
            raise CollectionError("Use limit 1..1000")
        emit(
            [
                dict(r)
                for r in store.db.execute(
                    "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (args.limit,)
                )
            ]
        )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    store = None
    try:
        store = Store(args.db)
        run(args, store)
        return 0
    except (CollectionError, OSError, sqlite3.Error, ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, CollectionError) else type(exc).__name__
        print(json.dumps({"error": message}), file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
