"""Conservative normalization. Never merge employers on name/domain alone."""

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


def normalize_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def clean_name(value: str) -> str:
    name = " ".join(unicodedata.normalize("NFKC", value).split())
    if not name or len(name) > 500 or any(unicodedata.category(c) == "Cc" for c in name):
        raise ValueError("Invalid organization name")
    return name


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.search(r"[\s\\\x00-\x1f]", value):
        raise ValueError("Invalid website URL")
    if "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Only HTTP(S) website URLs are supported")
    if parts.username or parts.password:
        raise ValueError("Website URLs must not contain credentials")
    host = parts.hostname.encode("idna").decode().lower()
    if ":" in host or "." not in host:
        raise ValueError("Website requires a public domain name")
    port = parts.port
    if port and (parts.scheme.lower(), port) not in {("https", 443), ("http", 80)}:
        host += f":{port}"
    # Scheme, path and non-root query differences may be meaningful. Preserve them.
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), parts.query, ""))
