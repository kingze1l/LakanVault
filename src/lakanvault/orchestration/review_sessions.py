# holds original + sanitized text a bit so toast View can open Prompt Review
"""Short-lived in-memory review sessions for toast View → Prompt Review.

Stores original/sanitized text in process memory only (TTL). Never written to audit/disk.
Public /api/protect/recent stays metadata-only; fetch full payload via event id (loopback).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


DEFAULT_TTL_S = 15 * 60
DEFAULT_CAPACITY = 50


@dataclass
class ReviewSession:
    event_id: int
    session_id: str
    original: str
    sanitized: str
    action: str
    source: str
    entity_types: tuple[str, ...]
    findings: list[dict[str, Any]]
    ts: float
    override_used: bool = False


@dataclass
class ReviewSessionStore:
    capacity: int = DEFAULT_CAPACITY
    ttl_s: float = DEFAULT_TTL_S
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _by_event: dict[int, ReviewSession] = field(default_factory=dict, repr=False)
    _by_session: dict[str, int] = field(default_factory=dict, repr=False)

    # save a session keyed by event id n session id
    def put(
        self,
        *,
        event_id: int,
        session_id: str,
        original: str,
        sanitized: str,
        action: str,
        source: str,
        entity_types: list[str] | tuple[str, ...] | None = None,
        findings: list[dict[str, Any]] | None = None,
    ) -> ReviewSession:
        sess = ReviewSession(
            event_id=int(event_id),
            session_id=str(session_id),
            original=original or "",
            sanitized=sanitized or "",
            action=str(action or "").lower(),
            source=str(source or "unknown")[:32],
            entity_types=tuple(str(t) for t in (entity_types or ()) if t)[:12],
            findings=list(findings or []),
            ts=time.time(),
        )
        with self._lock:
            self._purge_unlocked()
            self._by_event[sess.event_id] = sess
            self._by_session[sess.session_id] = sess.event_id
            while len(self._by_event) > self.capacity:
                oldest_id = min(self._by_event, key=lambda i: self._by_event[i].ts)
                self._drop_unlocked(oldest_id)
        return sess

    # look up by protect event id
    def get_by_event(self, event_id: int) -> ReviewSession | None:
        with self._lock:
            self._purge_unlocked()
            return self._by_event.get(int(event_id))

    # look up by protect session id
    def get_by_session(self, session_id: str) -> ReviewSession | None:
        with self._lock:
            self._purge_unlocked()
            eid = self._by_session.get(str(session_id))
            if eid is None:
                return None
            return self._by_event.get(eid)

    # mark that they already used the override send once
    def mark_override_used(self, session_id: str) -> bool:
        with self._lock:
            self._purge_unlocked()
            eid = self._by_session.get(str(session_id))
            if eid is None:
                return False
            sess = self._by_event.get(eid)
            if sess is None:
                return False
            if sess.override_used:
                return False
            sess.override_used = True
            return True

    # shape it for the review ui (loopback only)
    def to_public_dict(self, sess: ReviewSession) -> dict[str, Any]:
        """Full payload for Review UI (loopback only)."""
        return {
            "event_id": sess.event_id,
            "session_id": sess.session_id,
            "original": sess.original,
            "sanitized": sess.sanitized,
            "final_action": sess.action,
            "source": sess.source,
            "entity_types": list(sess.entity_types),
            "findings": list(sess.findings),
            "ts": sess.ts,
            "allow_send": sess.action != "block",
            "override_used": sess.override_used,
        }

    # drop expired sessions (caller already holds the lock)
    def _purge_unlocked(self) -> None:
        now = time.time()
        expired = [eid for eid, s in self._by_event.items() if now - s.ts > self.ttl_s]
        for eid in expired:
            self._drop_unlocked(eid)

    # yank one session out of both maps
    def _drop_unlocked(self, event_id: int) -> None:
        sess = self._by_event.pop(event_id, None)
        if sess is not None:
            self._by_session.pop(sess.session_id, None)


_STORE = ReviewSessionStore()
_STORE_LOCK = threading.Lock()


# shared store for the whole process
def get_review_sessions() -> ReviewSessionStore:
    return _STORE


# fresh store for unit tests
def reset_review_sessions_for_tests() -> ReviewSessionStore:
    global _STORE
    with _STORE_LOCK:
        _STORE = ReviewSessionStore()
        return _STORE
