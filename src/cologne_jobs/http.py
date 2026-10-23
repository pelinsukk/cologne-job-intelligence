"""Permission-gated future connector transport; no enabled live adapter in M1."""

import hashlib
import json
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from cologne_jobs.authorization import Source, authorize
from cologne_jobs.models import CollectionError
from cologne_jobs.storage import Store

USER_AGENT = "CologneJobIntelligenceBot/0.1 (https://github.com/pelinsukk/cologne-job-intelligence)"
LOGGER = logging.getLogger(__name__)
MAX_BYTES = 2_000_000


def retry_after(value: str | None, now: float) -> float:
    try:
        delay = float(value or "")
        if math.isfinite(delay) and delay >= 0:
            return max(60.0, delay)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value or "")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(60.0, parsed.timestamp() - now)
    except (ValueError, TypeError, OverflowError):
        return 300.0


class AuthorizedHTTP:
    def __init__(
        self,
        store: Store,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ):
        self.store = store
        self.sleep = sleep
        self.clock = clock
        self.client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(30, connect=10),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
        )

    def close(self) -> None:
        self.client.close()

    def gate(self, source_id: str) -> Source:
        try:
            source = self.store.source(source_id)
            authorize(source, datetime.fromtimestamp(self.clock(), UTC).date())
            self.store.check_runtime(source_id, self.clock())
            return source
        except CollectionError as exc:
            self.store.audit(source_id, "denied", str(exc))
            raise

    def _request(
        self, source_id: str, url: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        for attempt in range(2):
            source = self.gate(source_id)
            if url not in {source.endpoint, source.robots_url}:
                self.store.audit(source_id, "denied", "URL outside assessed allowlist")
                raise CollectionError("URL outside assessed allowlist")
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.username or parts.password or parts.query:
                raise CollectionError("Assessed endpoints require credential-free HTTPS")
            wait = self.store.reserve_request(source_id, source.min_interval, self.clock())
            self.sleep(wait)
            self.gate(source_id)  # Recheck if source changed while waiting.
            fingerprint = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
            self.store.audit(source_id, "request", f"{url} request_sha256={fingerprint}")
            LOGGER.info(json.dumps({"event": "request", "source": source_id, "url": url}))
            try:
                with self.client.stream("GET", url, params=params) as stream:
                    body = bytearray()
                    for chunk in stream.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise CollectionError("Response exceeds 2 MB limit")
                    response = httpx.Response(
                        stream.status_code,
                        headers=stream.headers,
                        content=bytes(body),
                        request=stream.request,
                    )
            except httpx.TransportError:
                self.store.audit(source_id, "network_error", "Transport failure")
                if attempt == 0:
                    self.sleep(source.min_interval)
                    continue
                raise CollectionError(
                    f"Source {source_id}: network failure after 2 attempts"
                ) from None
            code = response.status_code
            self.store.audit(source_id, "response", url, code)
            text = response.text[:10000].lower()
            captcha = any(
                marker in text for marker in ("captcha", "verify you are human", "cf-chl-")
            )
            if code in (401, 403) or captcha:
                reason = f"Access denied (HTTP {code})" if not captcha else "CAPTCHA/challenge"
                self.store.deny(source_id, reason)
                self.store.audit(source_id, "blocked", reason, code)
                raise CollectionError(f"Source {source_id}: {reason}; no retry or alternate route")
            if code == 429 or (code == 503 and "retry-after" in response.headers):
                delay = retry_after(response.headers.get("retry-after"), self.clock())
                self.store.cooldown(source_id, self.clock() + delay)
                self.store.audit(source_id, "cooldown", f"Wait at least {delay:.0f} seconds", code)
                raise CollectionError(f"Source {source_id}: HTTP {code}; cooldown saved, no retry")
            if code in (502, 503, 504) and attempt == 0:
                self.sleep(source.min_interval)
                continue
            if code != 200:
                raise CollectionError(f"Source {source_id}: HTTP {code}; redirects not followed")
            return response
        raise AssertionError("unreachable")

    def get_json(self, source_id: str, params: dict[str, str]) -> dict:
        source = self.gate(source_id)
        if not source.endpoint or not source.robots_url:
            raise CollectionError("No assessed endpoint and robots URL")
        endpoint = urlsplit(source.endpoint)
        robots = urlsplit(source.robots_url)
        if (endpoint.scheme, endpoint.netloc) != (robots.scheme, robots.netloc):
            raise CollectionError("Robots URL must have the endpoint origin")
        response = self._request(source_id, source.robots_url)
        text = response.text
        if "text/plain" not in response.headers.get("content-type", ""):
            raise CollectionError("Robots response is not text/plain; collection stopped")
        if "<html" in text.lower() or "user-agent:" not in text.lower():
            raise CollectionError("Robots response unrecognized; collection stopped")
        parser = RobotFileParser()
        parser.parse(text.splitlines())
        target = str(httpx.URL(source.endpoint, params=params))
        if not parser.can_fetch(USER_AGENT, target):
            self.store.deny(source_id, "robots.txt disallows collection")
            self.store.audit(source_id, "blocked", "robots.txt disallows collection")
            raise CollectionError("robots.txt disallows collection")
        interval = max(parser.crawl_delay(USER_AGENT) or 0, source.min_interval)
        request_rate = parser.request_rate(USER_AGENT)
        if request_rate:
            interval = max(interval, request_rate.seconds / request_rate.requests)
        if interval > source.min_interval:
            # Persist robots pacing, including across later command invocations.
            with self.store.db:
                self.store.db.execute(
                    "UPDATE source_runtime SET next_request=MAX(next_request,?) WHERE source_id=?",
                    (self.clock() + interval, source_id),
                )
        self.store.audit(
            source_id, "robots_allowed", "Current robots rules allow assessed endpoint"
        )
        response = self._request(source_id, source.endpoint, params)
        if "json" not in response.headers.get("content-type", ""):
            raise CollectionError("Expected JSON response")
        try:
            value = response.json()
        except ValueError:
            raise CollectionError("Invalid JSON response") from None
        if not isinstance(value, dict):
            raise CollectionError("Expected a JSON object")
        return value
