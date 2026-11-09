"""Prompt Review HTTP API: loopback protect/send + page."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lakanvault.app import server as server_mod
from lakanvault.local_core.findings import Finding, Tier


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
    # Starlette TestClient uses host "testclient"; treat as loopback for these tests.
    monkeypatch.setattr(server_mod, "assert_loopback_client", lambda client: None)
    server_mod.reset_gateway()

    with TestClient(server_mod.app) as c:
        yield c
    server_mod.reset_gateway()


def test_review_page_served(client: TestClient) -> None:
    resp = client.get("/review")
    assert resp.status_code == 200
    assert "Prompt Review" in resp.text


def test_review_masks_email_and_allows_send(client: TestClient) -> None:
    resp = client.post(
        "/api/review",
        json={"text": f"please email {EMAIL}", "session_id": "rev1", "llm": "never"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "rev1"
    assert data["final_action"] == "mask"
    assert data["allow_send"] is True
    assert EMAIL not in data["sanitized"]
    assert data["finding_count"] >= 1
    assert "text" not in data["findings"][0]


def test_review_blocks_secret(client: TestClient) -> None:
    resp = client.post(
        "/api/review",
        json={"text": SECRET_PROMPT, "session_id": "rev-block", "llm": "never"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["final_action"] == "block"
    assert data["allow_send"] is False
    assert data["sanitized"] == ""
    assert "SuperSecret99" not in resp.text


def test_review_send_unknown_session(client: TestClient) -> None:
    resp = client.post(
        "/api/review/send",
        json={"session_id": "missing", "sanitized": "hello"},
    )
    assert resp.status_code == 404


def test_review_send_blocked_empty(client: TestClient) -> None:
    client.post(
        "/api/review",
        json={"text": SECRET_PROMPT, "session_id": "empty-send", "llm": "never"},
    )
    resp = client.post(
        "/api/review/send",
        json={"session_id": "empty-send", "sanitized": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is True


def test_review_rejects_non_loopback(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(client_tuple):
        raise PermissionError("internal endpoint: loopback only")

    monkeypatch.setattr(server_mod, "assert_loopback_client", boom)
    resp = client.post("/api/review", json={"text": "hello world", "llm": "never"})
    assert resp.status_code == 403
