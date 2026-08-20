"""URL policy — local AI endpoints must stay on localhost."""
from __future__ import annotations

from urllib.parse import urlparse

_ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def assert_localhost_url(url: str) -> str:
    """Validate and normalize a local-only base URL. Raises ValueError if not localhost."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must use http or https: {url}")
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise ValueError(
            f"Only localhost URLs are allowed (got host={host!r}). "
            "Use http://localhost:PORT or http://127.0.0.1:PORT"
        )
    return url.strip().rstrip("/")


def normalize_origin(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must use http or https: {url}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError(f"URL missing host: {url}")
    port = parsed.port
    origin = f"{parsed.scheme}://{host}"
    if port:
        origin = f"{origin}:{port}"
    return origin


def assert_allowed_upstream(url: str, allowlist: list[str]) -> str:
    """Exact origin allowlist. Does not trust Host headers or arbitrary URLs."""
    origin = normalize_origin(url)
    allowed = {normalize_origin(item) for item in allowlist}
    if origin not in allowed:
        raise ValueError(f"Upstream origin not allowlisted: {origin}")
    return url.strip().rstrip("/")
