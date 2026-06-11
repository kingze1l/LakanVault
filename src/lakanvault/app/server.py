"""HTTP API + static HTML dashboard (ADR-004: thin UI shell, logic in Gateway)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lakanvault.app.picker import list_model_files, pick_model_file, pick_models_folder
from lakanvault.contracts.dtos import ScanRequest, ScanResponse
from lakanvault.orchestration.gateway import Gateway

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3],
        Path.cwd(),
        Path.cwd().parent,
    ]
    for candidate in candidates:
        if (candidate / "config" / "default.yaml").exists():
            return candidate.resolve()
    return here.parents[3].resolve()


REPO_ROOT = _find_repo_root()
CONFIG_DIR = REPO_ROOT / "config"

app = FastAPI(title="LakanVault", version="0.1.0")
_gateway: Gateway | None = None


def get_gateway() -> Gateway:
    global _gateway
    if _gateway is None:
        cfg = CONFIG_DIR if CONFIG_DIR.exists() else Path("./config")
        _gateway = Gateway(config_dir=cfg)
    return _gateway


def _resolve_models_dir(custom_dir: str | None = None) -> Path:
    if custom_dir:
        path = Path(custom_dir)
        return path if path.is_absolute() else REPO_ROOT / path
    cfg = get_gateway().get_config_snapshot()
    models_dir = cfg.get("local", {}).get("models_dir", "./data/models")
    path = Path(models_dir)
    return path if path.is_absolute() else REPO_ROOT / path


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def api_config() -> dict:
    return get_gateway().get_config_snapshot()


@app.get("/api/models")
def api_models(dir: str | None = Query(default=None)) -> dict:
    models_dir = _resolve_models_dir(dir)
    models = list_model_files(models_dir)
    return {
        "models_dir": str(models_dir),
        "exists": models_dir.exists(),
        "count": len(models),
        "models": models,
        "default_path": models[0]["path"] if models else None,
    }


@app.get("/api/pick-file")
def api_pick_file() -> dict:
    models_dir = _resolve_models_dir()
    path = pick_model_file(models_dir if models_dir.exists() else REPO_ROOT)
    if not path:
        return {"path": None, "cancelled": True}
    return {"path": path, "cancelled": False}


@app.get("/api/pick-folder")
def api_pick_folder() -> dict:
    models_dir = _resolve_models_dir()
    path = pick_models_folder(models_dir if models_dir.exists() else REPO_ROOT)
    if not path:
        return {"path": None, "cancelled": True}
    models = list_model_files(path) if path else []
    return {
        "path": path,
        "cancelled": False,
        "models": models,
        "default_path": models[0]["path"] if models else None,
    }


@app.post("/api/scan")
def api_scan(request: ScanRequest) -> ScanResponse:
    if not request.target_path.strip():
        raise HTTPException(status_code=400, detail="target_path is required")
    target = Path(request.target_path)
    if not target.is_absolute():
        candidate = REPO_ROOT / target
        if candidate.exists():
            request = ScanRequest(
                target_path=str(candidate.resolve()),
                prompt_text=request.prompt_text,
            )
    if not Path(request.target_path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.target_path}")
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
