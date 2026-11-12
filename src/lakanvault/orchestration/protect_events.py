# little ring buffer of protect events for the tray (no raw pii just meta)
"""In-memory protect event ring for tray status/toasts. Metadata only — no PII."""
from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProtectEvent:
    id: int
    ts: float
    action: str  # warn | mask | block
    source: str  # review | proxy | mcp | chat
    entity_types: tuple[str, ...] = ()


@dataclass
class ProtectEventRing:
    capacity: int = 100
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _seq: Any = field(default_factory=lambda: itertools.count(1), repr=False)
    _events: list[ProtectEvent] = field(default_factory=list, repr=False)
    _paused: bool = False
    _counts: dict[str, int] = field(
        default_factory=lambda: {"block": 0, "mask": 0, "warn": 0}
    )

    # flip the pause flag so tray can hush toasts
    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = bool(paused)

    # are we paused rn
    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    # stash a warn/mask/block event if its one of those
    def record(
        self,
        action: str,
        *,
        source: str,
        entity_types: list[str] | tuple[str, ...] | None = None,
    ) -> ProtectEvent | None:
        act = (action or "").strip().lower()
        if act not in {"warn", "mask", "block"}:
            return None
        types = tuple(
            str(t) for t in (entity_types or ()) if t
        )[:12]
        with self._lock:
            ev = ProtectEvent(
                id=next(self._seq),
                ts=time.time(),
                action=act,
                source=str(source or "unknown")[:32],
                entity_types=types,
            )
            self._events.append(ev)
            if len(self._events) > self.capacity:
                self._events = self._events[-self.capacity :]
            self._counts[act] = self._counts.get(act, 0) + 1
            return ev

    # grab events newer than since_id for the tray poll
    def recent(self, *, since_id: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._lock:
            rows = [e for e in self._events if e.id > int(since_id)]
            rows = rows[-limit:]
            return [
                {
                    "id": e.id,
                    "ts": e.ts,
                    "action": e.action,
                    "source": e.source,
                    "entity_types": list(e.entity_types),
                }
                for e in rows
            ]

    # counts + recent activity for the status ui
    def stats(self) -> dict[str, Any]:
        with self._lock:
            activity = [
                {
                    "id": e.id,
                    "ts": e.ts,
                    "action": e.action,
                    "source": e.source,
                    "entity_types": list(e.entity_types),
                }
                for e in self._events[-20:]
            ]
            return {
                "paused": self._paused,
                "blocked": self._counts.get("block", 0),
                "warned": self._counts.get("warn", 0),
                "masked": self._counts.get("mask", 0),
                "activity": list(reversed(activity)),
            }


_RING = ProtectEventRing()
_RING_LOCK = threading.Lock()


# process-wide ring so everyone shares the same feed
def get_protect_ring() -> ProtectEventRing:
    return _RING


# wipe n make a fresh ring (tests only)
def reset_protect_ring_for_tests() -> ProtectEventRing:
    """Replace the process-wide ring (unit tests only)."""
    global _RING
    with _RING_LOCK:
        _RING = ProtectEventRing()
        return _RING


# shorthand so callers dont dig into the ring object
def record_protect_event(
    action: str,
    *,
    source: str,
    entity_types: list[str] | tuple[str, ...] | None = None,
) -> ProtectEvent | None:
    return _RING.record(action, source=source, entity_types=entity_types)
