# review session store + event api + override send
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from lakanvault.app import server as server_mod
from lakanvault.local_core.findings import Finding, Tier
from lakanvault.orchestration.protect_events import reset_protect_ring_for_tests
from lakanvault.orchestration.review_sessions import (
    ReviewSessionStore,
    reset_review_sessions_for_tests,
)


EMAIL = "jane.doe@example.com"
SECRET_PROMPT = "connect with postgres://admin:SuperSecret99@db.example.com/app"

# clear rings n session store between tests
@pytest.fixture(autouse=True)
def _fresh() -> None:
    reset_protect_ring_for_tests()
    reset_review_sessions_for_tests()
    yield
    reset_protect_ring_for_tests()
    reset_review_sessions_for_tests()


def test_store_put_get_and_ttl_cap() -> None:
    store = ReviewSessionStore(capacity=2, ttl_s=60)
    store.put(
        event_id=1,
        session_id="s1",
        original="a",
        sanitized="A",
        action="mask",
        source="review",
    )
    store.put(
        event_id=2,
        session_id="s2",
        original="b",
        sanitized="B",
        action="block",
        source="proxy",
    )
    store.put(
        event_id=3,
        session_id="s3",
        original="c",
        sanitized="C",
        action="warn",
        source="mcp",
    )
    assert store.get_by_event(1) is None  # evicted
    assert store.get_by_event(3) is not None
    assert store.get_by_session("s3") is not None


def test_override_once() -> None:
    store = ReviewSessionStore()
    store.put(
        event_id=9,
        session_id="ov",
        original="secret",
        sanitized="",
        action="block",
        source="review",
    )
    assert store.mark_override_used("ov") is True
    assert store.mark_override_used("ov") is False

# fastapi client + stub email finder
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
    reset_review_sessions_for_tests()

    with TestClient(server_mod.app) as c:
        yield c
    server_mod.reset_gateway()

# event api can show original but recent list stays clean
def test_event_api_returns_original_recent_stays_clean(client: TestClient) -> None:
    resp = client.post(
        "/api/review",
        json={"text": f"please email {EMAIL}", "session_id": "rv1", "llm": "never"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["final_action"] == "mask"
    assert data["event_id"] is not None

    recent = client.get("/api/protect/recent").json()
    for ev in recent["events"]:
        assert "original" not in ev
        assert "text" not in ev
        assert "sanitized" not in ev

    detail = client.get(f"/api/protect/event/{data['event_id']}").json()
    assert detail["original"] == f"please email {EMAIL}"
    assert EMAIL not in detail["sanitized"]
    assert detail["session_id"] == "rv1"


def test_toast_page_served(client: TestClient) -> None:
    assert client.get("/toast").status_code == 200


def test_override_send_blocked_without_flag_and_works_with_flag(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = client.post(
        "/api/review",
        json={"text": SECRET_PROMPT, "session_id": "blk1", "llm": "never"},
    )
    assert resp.json()["final_action"] == "block"
    assert resp.json()["allow_send"] is False

    no_ov = client.post(
        "/api/review/send",
        json={"session_id": "blk1", "sanitized": "", "override": False},
    )
    assert no_ov.status_code == 200
    assert no_ov.json()["blocked"] is True

    fake = MagicMock()
    fake.content = "ok"
    fake.model_used = "mock"
    fake.provider_url = "http://127.0.0.1:1234"
    fake.latency_ms = 1.0
    monkeypatch.setattr(
        server_mod.get_gateway()._local_llm,
        "chat",
        lambda *a, **k: fake,
    )

    ov = client.post(
        "/api/review/send",
        json={"session_id": "blk1", "sanitized": "", "override": True},
    )
    assert ov.status_code == 200
    body = ov.json()
    assert body["blocked"] is False
    assert body["override_used"] is True
    assert body["raw_response"] == "ok"

    again = client.post(
        "/api/review/send",
        json={"session_id": "blk1", "sanitized": "", "override": True},
    )
    assert again.json()["blocked"] is True


def test_show_toast_sets_visible_flag() -> None:
    from lakanvault.tray.panel import FlyoutHost

    host = FlyoutHost()
    class W:
        def __init__(self) -> None:
            self.urls: list[str] = []
            self.shown = False
            self.moved = []

        def load_url(self, url: str) -> None:
            self.urls.append(url)

        def move(self, x: int, y: int) -> None:
            self.moved.append((x, y))

        def show(self) -> None:
            self.shown = True

        def hide(self) -> None:
            self.shown = False

    fake = W()
    host._prepared = True  # noqa: SLF001
    host._ready.set()
    host._toast_window = fake  # noqa: SLF001
    host._base_url = "http://127.0.0.1:8080"  # noqa: SLF001
    host.show_toast(event_id=7, action="block", source="review", entity_types=["SECRET"])
    assert fake.shown is True
    assert "event=7" in fake.urls[-1]
    assert "action=block" in fake.urls[-1]
    host.hide_toast()
    assert fake.shown is False
