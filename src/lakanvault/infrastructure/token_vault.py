"""In-memory SQLite token map — never writes a database file."""
from __future__ import annotations

import base64
import secrets
import sqlite3
import threading
import time

from lakanvault.contracts.proxy import (
    OPAQUE_TOKEN_BODY_LEN,
    OPAQUE_TOKEN_PREFIX,
    TokenVaultPort,
)


class VaultCapacityError(RuntimeError):
    """Hard cap reached after expired-row cleanup."""


def generate_opaque_token() -> str:
    raw = secrets.token_bytes(16)
    body = base64.b32encode(raw).decode("ascii").rstrip("=")
    if len(body) != OPAQUE_TOKEN_BODY_LEN:
        body = (body + "A" * OPAQUE_TOKEN_BODY_LEN)[:OPAQUE_TOKEN_BODY_LEN]
    return f"{OPAQUE_TOKEN_PREFIX}{body}]"


class InMemoryTokenVault(TokenVaultPort):
    def __init__(
        self,
        *,
        max_entries: int = 10_000,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.execute("PRAGMA temp_store=MEMORY")
        self._conn.execute("PRAGMA journal_mode=OFF")
        self._conn.execute(
            """
            CREATE TABLE tokens (
                token TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                request_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                value_bytes INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE UNIQUE INDEX idx_req_val ON tokens(request_id, value)"
        )
        self._conn.execute("CREATE INDEX idx_expires ON tokens(expires_at)")
        self._conn.execute("CREATE INDEX idx_request ON tokens(request_id)")

    def mint(self, value: str, *, request_id: str, ttl_seconds: float) -> str:
        now = time.time()
        expires = now + max(float(ttl_seconds), 0.0)
        nbytes = len(value.encode("utf-8"))
        with self._lock:
            self._cleanup_expired_unlocked(now)
            row = self._conn.execute(
                "SELECT token FROM tokens WHERE request_id = ? AND value = ?",
                (request_id, value),
            ).fetchone()
            if row:
                self._conn.execute(
                    "UPDATE tokens SET expires_at = ? WHERE token = ?",
                    (expires, row[0]),
                )
                self._conn.commit()
                return row[0]
            self._enforce_cap_unlocked(nbytes)
            token = generate_opaque_token()
            for _ in range(5):
                try:
                    self._conn.execute(
                        "INSERT INTO tokens "
                        "(token, value, request_id, created_at, expires_at, value_bytes) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (token, value, request_id, now, expires, nbytes),
                    )
                    self._conn.commit()
                    return token
                except sqlite3.IntegrityError:
                    token = generate_opaque_token()
            raise RuntimeError("opaque token collision after retries")

    def get(self, token: str) -> str | None:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT value, expires_at FROM tokens WHERE token = ?",
                (token,),
            ).fetchone()
            if not row:
                return None
            value, expires_at = row
            if expires_at <= now:
                self._conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
                self._conn.commit()
                return None
            return value

    def delete_request(self, request_id: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM tokens WHERE request_id = ?", (request_id,)
            )
            self._conn.commit()
            return int(cur.rowcount)

    def cleanup_expired(self) -> int:
        with self._lock:
            return self._cleanup_expired_unlocked(time.time())

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.execute("DELETE FROM tokens")
                self._conn.commit()
            finally:
                self._conn.close()

    def _cleanup_expired_unlocked(self, now: float) -> int:
        cur = self._conn.execute("DELETE FROM tokens WHERE expires_at <= ?", (now,))
        self._conn.commit()
        return int(cur.rowcount)

    def _enforce_cap_unlocked(self, incoming_bytes: int) -> None:
        count = self._conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
        total = self._conn.execute(
            "SELECT COALESCE(SUM(value_bytes), 0) FROM tokens"
        ).fetchone()[0]
        if count + 1 > self._max_entries or total + incoming_bytes > self._max_bytes:
            raise VaultCapacityError("in-memory token vault cap exceeded")
