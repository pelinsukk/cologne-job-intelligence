import json
import subprocess
import sys
from dataclasses import replace

import pytest

from cologne_jobs.cli import main
from cologne_jobs.discovery import discover
from cologne_jobs.models import CollectionError, Employer
from cologne_jobs.normalization import normalize_name, normalize_url
from cologne_jobs.storage import Store


def test_normalization():
    assert normalize_name("  ＡCME  Köln GmbH ") == "acme köln gmbh"
    assert normalize_url("HTTPS://EXAMPLE.COM:443/path/#fragment") == "https://example.com/path"
    assert normalize_url("example.com/") == "https://example.com"
    assert normalize_url("https://example.com/path?a=1") != normalize_url(
        "https://example.com/path"
    )


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "ftp://example.com",
        "https://u:p@example.com",
        "https://example.com/a\nb",
        "https://localhost",
        "https://[::1]",
    ],
)
def test_bad_urls(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_repeat_discovery_deduplicates_persists_and_preserves_provenance(store, dataset, tmp_path):
    first = discover(store, "local-json", dataset)
    assert first == {"fetched": 2, "created": 1, "updated": 1}
    first_seen = store.db.execute("SELECT first_seen FROM employers").fetchone()[0]
    second = discover(store, "local-json", dataset)
    assert second == {"fetched": 2, "created": 0, "updated": 2}
    assert store.db.execute("SELECT first_seen FROM employers").fetchone()[0] == first_seen
    assert store.db.execute("SELECT COUNT(*) FROM provenance").fetchone()[0] == 2
    assert store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2
    reopened = Store(tmp_path / "test.sqlite3")
    assert reopened.db.execute("SELECT COUNT(*) FROM employers").fetchone()[0] == 1
    reopened.close()


def test_same_name_different_websites_and_no_website_are_not_blindly_merged(store, permitted):
    records = [
        Employer(str(i), "Synthetic Same Name", f"https://fixture.example/{i}", website=url)
        for i, url in enumerate(["https://one.example", "https://two.example", None, None])
    ]
    assert store.persist(permitted.id, records) == (4, 0)


def test_same_domain_different_organizations_not_merged(store, permitted):
    records = [
        Employer(str(i), name, f"https://fixture.example/{i}", website="https://shared.example")
        for i, name in enumerate(["Synthetic A", "Synthetic B"])
    ]
    assert store.persist(permitted.id, records) == (2, 0)


def test_changed_source_claim_retained_in_history(store, permitted):
    employer = Employer(
        "1", "Synthetic Employer", "https://fixture.example/1", website="https://old.example"
    )
    store.persist(permitted.id, [employer])
    assert store.persist(permitted.id, [replace(employer, website="https://new.example")]) == (0, 1)
    assert store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2
    assert store.db.execute("SELECT website FROM employers").fetchone()[0] == "https://new.example"


def test_atomic_batch_rollback(store, permitted):
    with pytest.raises(ValueError):
        store.persist(
            permitted.id,
            [
                Employer("1", "Synthetic", "https://fixture.example/1"),
                Employer("2", "", "https://fixture.example/2"),
            ],
        )
    assert store.db.execute("SELECT COUNT(*) FROM employers").fetchone()[0] == 0


def test_unknown_source_cannot_read_local_dataset(store, tmp_path):
    with pytest.raises(CollectionError, match="UNKNOWN"):
        discover(store, "local-json", tmp_path / "nonexistent.json")
    assert store.db.execute("SELECT status FROM discovery_runs").fetchone()[0] == "failed"


def test_assessment_hash_binds_exact_dataset(store, dataset):
    dataset.write_text('{"employers": []}')
    with pytest.raises(CollectionError, match="hash"):
        discover(store, "local-json", dataset)


def test_cli_discover_and_inspect(store, dataset, tmp_path, capsys):
    args = ["--db", str(tmp_path / "test.sqlite3")]
    assert main([*args, "discover", "--file", str(dataset)]) == 0
    assert json.loads(capsys.readouterr().out)["created"] == 1
    assert main([*args, "employers", "1"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["provenance"]) == 2
    assert result["confidence"] == "source_claim"


@pytest.mark.parametrize("command", ["status", "doctor", "sources", "audit", "employers"])
def test_cli_documented_commands_in_separate_processes(tmp_path, command):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cologne_jobs.cli",
            "--db",
            str(tmp_path / "process.sqlite3"),
            command,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) is not None


def test_cli_disable_persists_and_blocks_discovery(store, dataset, tmp_path, capsys):
    args = ["--db", str(tmp_path / "test.sqlite3")]
    assert main([*args, "sources", "disable", "local-json"]) == 0
    capsys.readouterr()
    assert main([*args, "discover", "--file", str(dataset)]) == 1
    assert "enabled=False" in capsys.readouterr().err
    assert not store.source("local-json").enabled


def test_cli_cannot_enable_blocked_source(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "test.sqlite3"), "sources", "enable", "osm-overpass"]) == 1
    assert "BLOCKED" in capsys.readouterr().err


def test_no_future_milestone_commands_exposed():
    from cologne_jobs.cli import parser

    for command in ("update", "scan", "match", "dashboard"):
        with pytest.raises(SystemExit) as exc:
            parser().parse_args([command])
        assert exc.value.code == 2


def test_cli_assessment_import_is_explicit_and_cannot_enable_network(
    store, dataset, tmp_path, capsys
):
    path = tmp_path / "assessment.json"
    source = store.source("local-json")
    path.write_text(json.dumps(source.to_dict()))
    args = ["--db", str(tmp_path / "test.sqlite3")]
    assert main([*args, "sources", "assess", str(path)]) == 0
    capsys.readouterr()
    source = replace(source, endpoint="https://fixture.example/collection")
    path.write_text(json.dumps(source.to_dict()))
    assert main([*args, "sources", "assess", str(path)]) == 1
    assert "may not define network" in capsys.readouterr().err


def test_secrets_not_embedded_and_local_files_ignored():
    import re
    from pathlib import Path

    root = Path(__file__).parents[1]
    patterns = [
        r"gh[pousr]_[A-Za-z0-9]{20,}",
        r"sk-[A-Za-z0-9]{20,}",
        r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b",
    ]
    for path in (root / "src").rglob("*.py"):
        for pattern in patterns:
            assert re.search(pattern, path.read_text()) is None
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "data/test.json",
            ".env",
            "local.sqlite3",
            "local.sqlite3-wal",
            "local.log",
        ],
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )
    assert ignored.returncode == 0
    assert len(ignored.stdout.splitlines()) == 5
