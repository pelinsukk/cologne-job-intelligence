"""Local, user-entered vacancy and application tracker. Never makes network requests."""

import argparse
import re
import sqlite3
from collections.abc import Sequence

from cologne_jobs.models import CollectionError
from cologne_jobs.normalization import clean_name, normalize_name, normalize_url

STAGES = ("saved", "applied", "interview", "offer", "rejected", "withdrawn")
SCHEMA = """
CREATE TABLE IF NOT EXISTS manual_jobs (
    id INTEGER PRIMARY KEY,
    employer TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL,
    notes TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'saved',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS manual_job_events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES manual_jobs(id),
    stage TEXT NOT NULL,
    at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def configure(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="jobs_action", required=True)
    add = commands.add_parser("add", help="Record a listing manually")
    for key in ("employer", "title", "url"):
        add.add_argument(f"--{key}", required=True)
    add.add_argument("--location", default="")
    add.add_argument(
        "--notes", default="", help="Short personal summary; do not paste contact data"
    )
    listing = commands.add_parser("list", help="List tracked jobs, optionally ranked by terms")
    listing.add_argument("--term", action="append", default=[])
    listing.add_argument("--stage", choices=STAGES)
    stage = commands.add_parser("stage", help="Record a manually performed application step")
    stage.add_argument("id", type=int)
    stage.add_argument("stage", choices=STAGES)
    history = commands.add_parser("history", help="Show application stage history")
    history.add_argument("id", type=int)
    commands.add_parser(
        "demo", help="Run a labelled synthetic example without opening your database"
    )


def _matches(row: dict, terms: Sequence[str]) -> list[str]:
    content = normalize_name(" ".join(row[k] for k in ("title", "location", "notes")))
    normalized = dict.fromkeys(normalize_name(term) for term in terms if term.strip())
    return [
        term for term in normalized if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", content)
    ]


def run(db: sqlite3.Connection, args: argparse.Namespace) -> object:
    db.executescript(SCHEMA)
    if args.jobs_action == "add":
        url = normalize_url(args.url)
        if not url:
            raise CollectionError("A listing URL is required")
        if len(args.notes) > 2000 or len(args.location) > 200:
            raise CollectionError("Use at most 2000 characters for notes and 200 for location")
        with db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO manual_jobs(employer,title,url,location,notes) "
                "VALUES (?,?,?,?,?)",
                (clean_name(args.employer), clean_name(args.title), url, args.location, args.notes),
            )
            row = db.execute("SELECT * FROM manual_jobs WHERE url=?", (url,)).fetchone()
            if cursor.rowcount:
                db.execute(
                    "INSERT INTO manual_job_events(job_id,stage) VALUES (?, 'saved')", (row["id"],)
                )
        return dict(row)
    if args.jobs_action == "list":
        rows = db.execute(
            "SELECT * FROM manual_jobs WHERE ? IS NULL OR stage=? ORDER BY id",
            (args.stage, args.stage),
        )
        result = [dict(row) for row in rows]
        for row in result:
            row["matched_terms"] = _matches(row, args.term)
            row["score"] = len(row["matched_terms"])
        return sorted(result, key=lambda row: (-row["score"], row["id"]))
    with db:
        row = db.execute("SELECT * FROM manual_jobs WHERE id=?", (args.id,)).fetchone()
        if row is None:
            raise CollectionError("Job ID not found")
        if args.jobs_action == "history":
            return [
                dict(event)
                for event in db.execute(
                    "SELECT stage,at FROM manual_job_events WHERE job_id=? ORDER BY id", (args.id,)
                )
            ]
        if row["stage"] != args.stage:
            db.execute(
                "UPDATE manual_jobs SET stage=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (args.stage, args.id),
            )
            db.execute(
                "INSERT INTO manual_job_events(job_id,stage) VALUES (?,?)", (args.id, args.stage)
            )
        return dict(db.execute("SELECT * FROM manual_jobs WHERE id=?", (args.id,)).fetchone())


def demo() -> dict:
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        for title, path, notes in (
            ("Climate data analyst", "analyst", "Python and climate data"),
            ("Field research assistant", "field", "Field instrumentation"),
        ):
            run(
                db,
                argparse.Namespace(
                    jobs_action="add",
                    employer="Synthetic Example Employer",
                    title=title,
                    url=f"https://example.invalid/{path}",
                    location="Cologne",
                    notes=notes,
                ),
            )
        run(db, argparse.Namespace(jobs_action="stage", id=1, stage="applied"))
        jobs = run(
            db, argparse.Namespace(jobs_action="list", stage=None, term=["Python", "climate"])
        )
        history = run(db, argparse.Namespace(jobs_action="history", id=1))
    db.close()
    return {"synthetic": True, "persistent": False, "jobs": jobs, "example_history": history}
