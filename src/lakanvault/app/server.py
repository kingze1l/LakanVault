"""HTTP API + static HTML dashboard (ADR-004: thin UI shell, logic in Gateway)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lakanvault.contracts.dtos import ScanRequest, ScanResponse
from lakanvault.orchestration.gateway import Gateway

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"

app = FastAPI(title="LakanVault", version="0.1.0")
_gateway: Gateway | None = None


def get_gateway() -> Gateway:
    global _gateway
    if _gateway is None:
        cfg = CONFIG_DIR if CONFIG_DIR.exists() else Path("./config")
        _gateway = Gateway(config_dir=cfg)
    return _gateway


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def api_config() -> dict:
    return get_gateway().get_config_snapshot()


@app.post("/api/scan")
def api_scan(request: ScanRequest) -> ScanResponse:
    if not request.target_path.strip():
        raise HTTPException(status_code=400, detail="target_path is required")
    return get_gateway().receive(request)


@app.get("/api/audit")
def api_audit() -> list[dict]:
    audit_dir = Path(get_gateway().get_config_snapshot().get("local", {}).get("audit_dir", "./data/audit"))
    if not audit_dir.is_absolute():
        audit_dir = REPO_ROOT / audit_dir
    if not audit_dir.exists():
        return []

    rows: list[dict] = []
    for path in sorted(audit_dir.glob("*.json"), reverse=True)[:30]:
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return rows


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
