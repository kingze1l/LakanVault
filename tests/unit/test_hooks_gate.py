# hooks gate api — off/tag/on from status ui
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import lakanvault.app.server as server_mod
from lakanvault.orchestration import hooks_gate


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(hooks_gate, "_persist_path", lambda: tmp_path / "hooks_mode.txt")
    hooks_gate._mode = "tag"
    hooks_gate._loaded = True
    monkeypatch.setattr(server_mod, "assert_loopback_client", lambda client: None)
    with TestClient(server_mod.app) as c:
        yield c


def test_hooks_mode_get_and_set(client: TestClient, tmp_path: Path) -> None:
    got = client.get("/api/hooks/mode")
    assert got.status_code == 200
    assert got.json()["mode"] in {"off", "tag", "on"}

    bad = client.post("/api/hooks/mode", json={"mode": "nope"})
    assert bad.status_code == 400

    set_off = client.post("/api/hooks/mode", json={"mode": "off"})
    assert set_off.status_code == 200
    assert set_off.json()["mode"] == "off"
    assert (tmp_path / "hooks_mode.txt").read_text(encoding="utf-8").strip().startswith("off")

    set_tag = client.post("/api/hooks/mode", json={"mode": "tag"})
    assert set_tag.status_code == 200
    assert set_tag.json()["mode"] == "tag"


def test_dictionary_api_and_dashboard_page(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lakanvault.orchestration import word_dictionary as wd

    monkeypatch.setattr(wd, "_path", lambda: tmp_path / "word_dictionary.json")
    got = client.get("/api/dictionary")
    assert got.status_code == 200
    assert got.json() == {"overlook": [], "flag": []}

    put = client.put(
        "/api/dictionary",
        json={"overlook": ["Alpha"], "flag": ["ProjectX"]},
    )
    assert put.status_code == 200
    assert put.json() == {"overlook": ["Alpha"], "flag": ["ProjectX"]}
    assert client.get("/api/dictionary").json()["flag"] == ["ProjectX"]

    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert b"Lakan" in dash.content
    assert b"Word dictionary" in dash.content
