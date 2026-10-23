from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from cologne_jobs.authorization import authorize
from cologne_jobs.http import AuthorizedHTTP, retry_after
from cologne_jobs.models import AuthorizationState, CollectionError


def gateway(store, handler):
    now = [datetime.now(UTC).timestamp()]

    def sleep(seconds):
        now[0] += seconds

    return AuthorizedHTTP(
        store, transport=httpx.MockTransport(handler), sleep=sleep, clock=lambda: now[0]
    )


@pytest.mark.parametrize(
    "state", [AuthorizationState.UNKNOWN, AuthorizationState.RESTRICTED, AuthorizationState.BLOCKED]
)
def test_nonpermitted_never_touches_network(store, permitted, state):
    store.save_source(replace(permitted, state=state))
    calls = []
    client = gateway(store, lambda request: calls.append(request))
    with pytest.raises(CollectionError):
        client.get_json(permitted.id, {})
    client.close()
    assert calls == []
    assert store.db.execute("SELECT event FROM audit ORDER BY id DESC").fetchone()[0] == "denied"


@pytest.mark.parametrize(
    "change",
    [
        {"enabled": False},
        {"assessed_on": "2020-01-01"},
        {"assessed_on": None},
        {"assessed_on": "2099-01-01"},
        {"confidence": "unknown"},
        {"documentation": ()},
        {"license": "unknown"},
        {"min_interval": 0},
        {"refresh_seconds": 0},
        {"license": ""},
        {"documentation": ("",)},
        {"restrictions": "unknown"},
        {"min_interval": float("nan")},
    ],
)
def test_incomplete_or_stale_assessment_fails(permitted, change):
    with pytest.raises(CollectionError):
        authorize(replace(permitted, **change))


def test_permitted_collection_and_rate_spacing(store, permitted):
    calls = []

    def handler(request):
        calls.append(request)
        assert "CologneJobIntelligenceBot" in request.headers["user-agent"]
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
            )
        return httpx.Response(200, json={"employers": []})

    client = gateway(store, handler)
    start = client.clock()
    assert client.get_json(permitted.id, {"q": "small"}) == {"employers": []}
    assert client.clock() - start >= permitted.min_interval
    assert len(calls) == 2
    client.close()


@pytest.mark.parametrize(
    "status,body",
    [(403, "Forbidden"), (401, "Denied"), (200, "Please verify you are human captcha")],
)
def test_denial_latches_across_new_clients_no_retry_or_alternate_route(
    store, permitted, status, body
):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(status, text=body)

    for _ in range(2):
        client = gateway(store, handler)
        with pytest.raises(CollectionError):
            client.get_json(permitted.id, {})
        client.close()
    assert calls == [permitted.robots_url]
    assert store.runtime(permitted.id)["denied_reason"]


def test_429_saves_retry_after_and_does_not_retry(store, permitted):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3600"})

    client = gateway(store, handler)
    now = client.clock()
    with pytest.raises(CollectionError, match="cooldown"):
        client.get_json(permitted.id, {})
    assert store.runtime(permitted.id)["cooldown_until"] == now + 3600
    with pytest.raises(CollectionError, match="cooldown"):
        client.get_json(permitted.id, {})
    assert len(calls) == 1
    client.close()


def test_retry_after_http_date_and_bad_headers():
    now = datetime.now(UTC).replace(microsecond=0)
    assert retry_after(format_datetime(now + timedelta(hours=2)), now.timestamp()) == 7200
    assert retry_after("nonsense", now.timestamp()) == 300
    assert retry_after("nan", now.timestamp()) == 300
    assert retry_after("-2", now.timestamp()) == 300


@pytest.mark.parametrize(
    "body,content_type",
    [
        ("User-agent: *\nDisallow: /employers", "text/plain"),
        ("<html>not robots</html>", "text/html"),
        ("", "text/plain"),
    ],
)
def test_robots_denied_or_unavailable_blocks_collection(store, permitted, body, content_type):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=body, headers={"content-type": content_type})

    client = gateway(store, handler)
    with pytest.raises(CollectionError):
        client.get_json(permitted.id, {})
    assert len(calls) == 1
    client.close()


@pytest.mark.parametrize("status", [302, 404])
def test_redirect_and_missing_robots_not_followed(store, permitted, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"location": "https://alternate.example/"})

    client = gateway(store, handler)
    with pytest.raises(CollectionError):
        client.get_json(permitted.id, {})
    assert len(calls) == 1
    client.close()


def test_network_failure_reported_bounded_and_audited(store, permitted):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("sensitive transport detail", request=request)

    client = gateway(store, handler)
    with pytest.raises(CollectionError, match="network failure after 2 attempts"):
        client.get_json(permitted.id, {})
    assert len(calls) == 2
    assert (
        store.db.execute("SELECT COUNT(*) FROM audit WHERE event='network_error'").fetchone()[0]
        == 2
    )
    client.close()


def test_gateway_rejects_unassessed_url_without_network(store, permitted):
    calls = []
    client = gateway(store, lambda request: calls.append(request))
    with pytest.raises(CollectionError, match="allowlist"):
        client._request(permitted.id, "https://alternate.example/")
    assert not calls
    client.close()


def test_request_reservation_persists_across_store_reopen(tmp_path):
    from cologne_jobs.storage import Store

    path = tmp_path / "persist.sqlite3"
    first = Store(path)
    assert first.reserve_request("local-json", 5, 100) == 0
    first.close()
    second = Store(path)
    assert second.reserve_request("local-json", 5, 101) == 4
    second.close()


def test_403_at_collection_endpoint_does_not_try_another_route(store, permitted):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
            )
        return httpx.Response(403)

    client = gateway(store, handler)
    with pytest.raises(CollectionError, match="Access denied"):
        client.get_json(permitted.id, {})
    with pytest.raises(CollectionError, match="latched denial"):
        client.get_json(permitted.id, {})
    assert calls == ["/robots.txt", "/employers"]
    client.close()


def test_transient_failure_retries_only_same_endpoint_once(store, permitted):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(503)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
            )
        return httpx.Response(200, json={"employers": []})

    client = gateway(store, handler)
    assert client.get_json(permitted.id, {}) == {"employers": []}
    assert calls == ["/robots.txt", "/robots.txt", "/employers"]
    client.close()
