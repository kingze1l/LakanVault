"""HTTP API + static HTML dashboard (ADR-004: thin UI shell, logic in Gateway)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from lakanvault.app.picker import list_model_files, pick_model_file, pick_models_folder
from lakanvault.contracts.dtos import (
    BaselineRequest,
    ChatRequest,
    ChatResponse,
    IntegrityEjectRequest,
    ScanRequest,
    ScanResponse,
    SettingsUpdate,
)
from lakanvault.orchestration.gateway import Gateway
from lakanvault.shared.config import clear_local_config_keys, save_local_config
from lakanvault.shared.url_policy import assert_localhost_url

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


def reset_gateway() -> None:
    global _gateway
    _gateway = None


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


@app.get("/api/settings")
def api_get_settings() -> dict:
    return get_gateway().get_settings()


@app.put("/api/settings")
def api_put_settings(body: SettingsUpdate) -> dict:
    partial = body.model_dump(exclude_none=True)
    if "local_ai" in partial and partial["local_ai"].get("base_url"):
        try:
            assert_localhost_url(partial["local_ai"]["base_url"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    cfg_dir = CONFIG_DIR if CONFIG_DIR.exists() else Path("./config")
    save_local_config(cfg_dir, partial)
    reset_gateway()
    gw = get_gateway()
    gw.apply_settings(partial)
    return {"saved": True, "settings": gw.get_settings()}


@app.post("/api/settings/reset")
def api_reset_settings() -> dict:
    cfg_dir = CONFIG_DIR if CONFIG_DIR.exists() else Path("./config")
    clear_local_config_keys(cfg_dir, ["local_ai", "local", "privacy", "cloud"])
    reset_gateway()
    return {"reset": True, "settings": get_gateway().get_settings()}


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


@app.get("/api/local-llm/status")
def api_local_llm_status(base_url: str | None = Query(default=None)) -> dict:
    if base_url:
        try:
            assert_localhost_url(base_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_gateway().local_llm_status(base_url=base_url)


@app.get("/api/lmstudio/status")
def api_lmstudio_status(base_url: str | None = Query(default=None)) -> dict:
    return api_local_llm_status(base_url=base_url)


@app.post("/api/chat")
def api_chat(request: ChatRequest) -> ChatResponse:
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    if request.base_url:
        try:
            assert_localhost_url(request.base_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = get_gateway().chat(
        request.prompt, model=request.model, base_url=request.base_url
    )
    mapping = result.get("mapping") or {}
    return ChatResponse(
        sanitized_prompt=result.get("sanitized_prompt", ""),
        raw_response=result.get("raw_response", ""),
        restored_response=result.get("restored_response", ""),
        pii_span_count=result.get("pii_span_count", 0),
        placeholders=sorted(mapping.keys()),
        error=result.get("error"),
        model_used=result.get("model_used", ""),
        provider_url=result.get("provider_url", ""),
        latency_ms=result.get("latency_ms", 0.0),
        sanitize_ms=result.get("sanitize_ms", 0.0),
    )


@app.post("/api/chat/stream")
def api_chat_stream(request: ChatRequest) -> StreamingResponse:
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    if request.base_url:
        try:
            assert_localhost_url(request.base_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def event_gen():
        for event in get_gateway().chat_stream_events(
            request.prompt, model=request.model, base_url=request.base_url
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/integrity/scan")
def api_integrity_scan() -> dict:
    entries = get_gateway().scan_models()
    counts = {"TRUSTED": 0, "UNVERIFIED": 0, "POISONED": 0}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    models_dir = _resolve_models_dir()
    return {
        "models_dir": str(models_dir),
        "counts": counts,
        "entries": entries,
    }


@app.post("/api/integrity/eject")
def api_integrity_eject(request: IntegrityEjectRequest) -> dict:
    if not request.model_name.strip():
        raise HTTPException(status_code=400, detail="model_name is required")
    ok = get_gateway().eject_model(request.model_name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Model not found: {request.model_name}")
    return {"quarantined": True, "model_name": request.model_name}


@app.post("/api/integrity/baseline")
def api_integrity_baseline(request: BaselineRequest) -> dict:
    if not request.model_name.strip():
        raise HTTPException(status_code=400, detail="model_name is required")
    gw = get_gateway()
    if request.sha256_hex:
        gw.set_model_baseline(request.model_name, request.sha256_hex)
    else:
        entries = {e["name"]: e for e in gw.scan_models()}
        entry = entries.get(request.model_name)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Model not found: {request.model_name}")
        gw.set_model_baseline(request.model_name, entry["current_hash"])
    return {"pinned": True, "model_name": request.model_name}


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
