"""M1 offline connector. No public employer dataset is enabled for collection."""

import hashlib
import json
import time
from pathlib import Path

from cologne_jobs.authorization import authorize
from cologne_jobs.models import CollectionError, Employer
from cologne_jobs.storage import Store


def discover(store: Store, source_id: str, path: Path | None = None) -> dict:
    run_id = store.db.execute(
        "INSERT INTO discovery_runs(source_id,started,status) VALUES (?,?,'running')",
        (source_id, time.time()),
    ).lastrowid
    store.db.commit()
    try:
        source = store.source(source_id)
        authorize(source)
        store.check_runtime(source_id, time.time())
        if source_id != "local-json":
            raise CollectionError("No live discovery adapter enabled in M0/M1")
        if path is None:
            raise CollectionError("local-json requires --file PATH")
        with store.discovery_lease(source_id):
            # Authorization precedes even reading the dataset. Exact bytes bind the
            # local rights assessment to this file, not every file the user may select.
            if path.stat().st_size > 2_000_000:
                raise CollectionError("Local dataset exceeds 2 MB")
            with path.open("rb") as handle:
                content = handle.read(2_000_001)
            if len(content) > 2_000_000:
                raise CollectionError("Local dataset exceeds 2 MB")
            digest = hashlib.sha256(content).hexdigest()
            if f"sha256:{digest}" not in source.documentation:
                raise CollectionError("Dataset hash does not match the assessed local file")
            store.audit(source_id, "local_read", f"sha256:{digest}")
            payload = json.loads(content)
            if not isinstance(payload, dict) or set(payload) != {"employers"}:
                raise CollectionError("Expected an object containing only employers")
            records = payload["employers"]
            if not isinstance(records, list) or len(records) > 10000:
                raise CollectionError("employers must be a list of at most 10000 records")
            employers = []
            allowed = {
                "external_id",
                "name",
                "source_url",
                "website",
                "aliases",
                "industry",
                "location_evidence",
                "confidence",
            }
            for record in records:
                if not isinstance(record, dict) or set(record) - allowed:
                    raise CollectionError(
                        "Invalid employer fields (personal/contact fields forbidden)"
                    )
                for key in ("external_id", "name", "source_url"):
                    if not isinstance(record.get(key), str) or not record[key].strip():
                        raise CollectionError(f"Employer requires string {key}")
                for key in ("website", "industry"):
                    if record.get(key) is not None and not isinstance(record[key], str):
                        raise CollectionError(f"Invalid {key}")
                if not isinstance(record.get("location_evidence", "unknown"), str):
                    raise CollectionError("location_evidence must be a string source claim")
                aliases = record.get("aliases", [])
                if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
                    raise CollectionError("aliases must be a string list")
                # Import never upgrades unverified source claims to verified local facts.
                record = dict(record, aliases=tuple(aliases), confidence="source_claim")
                employers.append(Employer(**record))
            created, updated = store.persist(source_id, employers)
            result = {"fetched": len(employers), "created": created, "updated": updated}
            with store.db:
                store.db.execute(
                    "UPDATE discovery_runs SET finished=?,status='success',fetched=?,"
                    "created=?,updated=? WHERE id=?",
                    (time.time(), len(employers), created, updated, run_id),
                )
            store.audit(source_id, "discovery_success", json.dumps(result))
            return result
    except (CollectionError, OSError, ValueError, TypeError) as exc:
        # Do not expose arbitrary dataset content or filesystem details in persistent logs.
        detail = str(exc) if isinstance(exc, CollectionError) else type(exc).__name__
        with store.db:
            store.db.execute(
                "UPDATE discovery_runs SET finished=?,status='failed',error=? WHERE id=?",
                (time.time(), detail, run_id),
            )
        store.audit(source_id, "discovery_failed", detail)
        raise CollectionError(detail) from None
