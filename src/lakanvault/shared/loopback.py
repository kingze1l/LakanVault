"""Inbound client checks for daemon-internal HTTP endpoints."""
from __future__ import annotations

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.lower().strip("[]")
    if normalized.startswith("::ffff:"):
        normalized = normalized.removeprefix("::ffff:")
    return normalized in _LOOPBACK_HOSTS


def assert_loopback_client(client: tuple | None) -> None:
    """Allow only loopback ASGI clients. Host headers are not trusted."""
    host = None if client is None else str(client[0])
    if not is_loopback_host(host):
        raise PermissionError("internal endpoint: loopback only")
