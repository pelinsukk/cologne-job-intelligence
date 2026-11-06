import json

from cologne_jobs.cli import main


def test_manual_workflow_persists_and_deduplicates(tmp_path, capsys):
    db = tmp_path / "jobs.sqlite3"

    def invoke(*args):
        assert main(["--db", str(db), "jobs", *args]) == 0
        return json.loads(capsys.readouterr().out)

    options = (
        "--employer",
        "Example",
        "--title",
        "Python analyst",
        "--url",
        "https://example.invalid/job",
        "--location",
        "Cologne",
    )
    job = invoke("add", *options)
    assert invoke("add", *options)["id"] == job["id"]
    assert (
        invoke("list", "--term", "PYTHON", "--term", "python", "--term", "analyst")[0]["score"] == 2
    )
    invoke("stage", str(job["id"]), "interview")
    invoke("stage", str(job["id"]), "interview")
    assert invoke("list", "--stage", "saved") == []
    assert [e["stage"] for e in invoke("history", str(job["id"]))] == ["saved", "interview"]


def test_demo_never_creates_real_database(tmp_path, capsys):
    db = tmp_path / "real.sqlite3"
    assert main(["--db", str(db), "jobs", "demo"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["synthetic"] and not result["persistent"]
    assert result["jobs"][0]["score"] == 2
    assert not db.exists()
