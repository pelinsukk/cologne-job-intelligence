import hashlib
import json
from datetime import UTC, datetime

import pytest

from cologne_jobs.authorization import Source
from cologne_jobs.models import AuthorizationState
from cologne_jobs.storage import Store


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    import httpx

    def fail(*args, **kwargs):
        raise AssertionError("Unit tests must not perform live network requests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fail)


@pytest.fixture
def store(tmp_path):
    instance = Store(tmp_path / "test.sqlite3")
    yield instance
    instance.close()


@pytest.fixture
def permitted(store):
    # Synthetic authorization used ONLY with MockTransport; never a live permission claim.
    source = Source(
        id="local-json",
        name="Synthetic test source",
        official_url="https://fixture.example/",
        method="local JSON file",
        state=AuthorizationState.PERMITTED,
        enabled=True,
        documentation=("synthetic fixture permission",),
        license="test-only",
        robots_assessment="synthetic runtime check required",
        fields=("name",),
        rate_limits="test: one request per 5 seconds",
        restrictions="Synthetic fixture only; never a real collection grant",
        confidence="high",
        assessed_on=datetime.now(UTC).date().isoformat(),
        endpoint="https://fixture.example/employers",
        robots_url="https://fixture.example/robots.txt",
    )
    store.save_source(source)
    return source


@pytest.fixture
def dataset(tmp_path, store, permitted):
    from dataclasses import replace

    payload = {
        "employers": [
            {
                "external_id": "synthetic-1",
                "name": "Synthetic Research GmbH",
                "website": "https://synthetic.example/",
                "source_url": "https://fixture.example/1",
                "aliases": ["Synthetic Research"],
                "location_evidence": "synthetic Cologne claim",
            },
            {
                "external_id": "synthetic-2",
                "name": "Synthetic Research GmbH",
                "website": "https://SYNTHETIC.example",
                "source_url": "https://fixture.example/2",
            },
        ]
    }
    path = tmp_path / "employers.json"
    path.write_text(json.dumps(payload))
    source = replace(
        permitted,
        endpoint=None,
        robots_url=None,
        documentation=(
            "synthetic rights fixture",
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        ),
    )
    store.save_source(source)
    return path
