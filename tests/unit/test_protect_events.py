"""Protect event ring + HTTP API shape (metadata only)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lakanvault.app import server as server_mod
from lakanvault.local_core.findings import Finding, Tier
from lakanvault.orchestration.protect_events import (
    ProtectEventRing,
    get_protect_ring,
    record_protect_event,
    reset_protect_ring_for_tests,
)


FORBIDDEN_KEYS = {"text", "sanitized", "prompt", "raw", "value", "secret"}


@pytest.fixture(autouse=True)
def _fresh_ring() -> None:
    reset_protect_ring_for_tests()
    yield
    reset_protect_ring_for_tests()


def test_ring_records_warn_mask_block_only() -> None:
    ring = ProtectEventRing(capacity=5)
    assert ring.record("allow", source="review") is None
    assert ring.record("MASK", source="review", entity_types=["EMAIL_ADDRESS"]) is not None
    assert ring.record("block", source="proxy", entity_types=["SECRET"]) is not None
    assert ring.record("warn", source="chat") is not None
    stats = ring.stats()
    assert stats["masked"] == 1
    assert stats["blocked"] == 1
    assert stats["warned"] == 1
    assert stats["paused"] is False


def test_ring_caps_and_since_id() -> None:
    ring = ProtectEventRing(capacity=3)
    for i in range(5):
        ring.record("warn", source="t", entity_types=[f"E{i}"])
    recent = ring.recent(since_id=0, limit=10)
    assert len(recent) == 3
    assert recent[0]["id"] == 3
    since = ring.recent(since_id=4, limit=10)
    assert [e["id"] for e in since] == [5]


def test_ring_events_are_metadata_only() -> None:
    record_protect_event(
        "block",
        source="review",
        entity_types=["API_KEY"],
    )
    for ev in get_protect_ring().recent():
        assert set(ev.keys()) == {"id", "ts", "action", "source", "entity_types"}
        assert not FORBIDDEN_KEYS.intersection(ev.keys())
        assert "sk-" not in str(ev)
        assert isinstance(ev["entity_types"], list)


EMAIL = "jane.doe@example.com"
SECRET_PROMPT = "connect with postgres://admin:SuperSecret99@db.example.com/app"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "default.yaml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    def fake_pii(text: str, layers=("names",)):
        start = text.find(EMAIL)
        if start < 0:
            return []
        return [
            Finding(
                "EMAIL_ADDRESS",
                EMAIL,
                start,
                start + len(EMAIL),
                0.95,
                Tier.PII_MODERATE,
                "presidio",
            )
        ]

    monkeypatch.setattr("lakanvault.local_core.scan.detect_pii", fake_pii)
    monkeypatch.setattr(server_mod, "CONFIG_DIR", cfg)
    monkeypatch.setattr(server_mod, "assert_loopback_client", lambda client: None)
    server_mod.reset_gateway()
    reset_protect_ring_for_tests()

    with TestClient(server_mod.app) as c:
        yield c
    server_mod.reset_gateway()
    reset_protect_ring_for_tests()


def test_status_page_served(client: TestClient) -> None:
    resp = client.get("/status")
    assert resp.status_code == 200
    assert "Protection" in resp.text
    assert "BLOCKED" in resp.text


def test_protect_api_from_review_mask(client: TestClient) -> None:
    resp = client.post(
        "/api/review",
        json={"text": f"please email {EMAIL}", "session_id": "ev1", "llm": "never"},
    )
    assert resp.status_code == 200
    assert resp.json()["final_action"] == "mask"

    recent = client.get("/api/protect/recent").json()
    assert len(recent["events"]) >= 1
    ev = recent["events"][-1]
    assert ev["action"] == "mask"
    assert ev["source"] == "review"
    assert "EMAIL_ADDRESS" in ev["entity_types"]
    for key in FORBIDDEN_KEYS:
        assert key not in ev
    assert EMAIL not in str(recent)

    stats = client.get("/api/protect/stats").json()
    assert stats["masked"] >= 1
    assert "activity" in stats


def test_protect_api_block_and_pause(client: TestClient) -> None:
    client.post(
        "/api/review",
        json={"text": SECRET_PROMPT, "session_id": "ev-block", "llm": "never"},
    )
    stats = client.get("/api/protect/stats").json()
    assert stats["blocked"] >= 1
    assert stats["paused"] is False

    pause = client.post("/api/protect/pause", json={"paused": True})
    assert pause.status_code == 200
    assert pause.json()["paused"] is True
    assert client.get("/api/protect/stats").json()["paused"] is True

    client.post("/api/protect/pause", json={"paused": False})
    assert client.get("/api/protect/stats").json()["paused"] is False
