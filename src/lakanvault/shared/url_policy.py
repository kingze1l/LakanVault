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
