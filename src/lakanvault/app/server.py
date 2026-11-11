# fastapi http shell — thin routes that call into Gateway (logic lives there)
"""HTTP API daemon (ADR-004: thin shell; logic in Gateway). UI shell TBD."""
from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lakanvault.app.picker import list_model_files, pick_model_file, pick_models_folder
from lakanvault.app.proxy_routes import internal_router, router as proxy_router
from lakanvault.contracts.dtos import (
    BaselineRequest,
    ChatRequest,
    ChatResponse,
    IntegrityEjectRequest,
    ScanRequest,
    ScanResponse,
    SettingsUpdate,
)
from lakanvault.contracts.mcp import ProtectRequest, ProtectResponse, ReviewSendRequest, ReviewSendResponse
from lakanvault.orchestration.gateway import Gateway
from lakanvault.orchestration.protect_events import get_protect_ring
from lakanvault.orchestration.proxy_gateway import ProxyGateway
from lakanvault.orchestration.review_sessions import get_review_sessions
from lakanvault.infrastructure.token_vault import InMemoryTokenVault
from lakanvault.infrastructure.upstream.openai import OpenAIUpstream
from lakanvault.shared.config import clear_local_config_keys, load_config, save_local_config
from lakanvault.shared.loopback import assert_loopback_client
from lakanvault.shared.paths import resource_path, writable_data_root
from lakanvault.shared.url_policy import assert_localhost_url


# find repo root (or exe folder when frozen)
def _find_repo_root() -> Path:
    from lakanvault.shared.paths import bundle_root, is_frozen

    if is_frozen():
        # Writable root beside the exe (local.yaml / data). default.yaml is seeded
        # from _MEIPASS by launcher.ensure_data_dirs before uvicorn starts.
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve()
    candidates = [
        bundle_root(),
        here.parents[3],
        Path.cwd(),
        Path.cwd().parent,
    ]
    for candidate in candidates:
        if (candidate / "config" / "default.yaml").exists():
            return candidate.resolve()
    return here.parents[3].resolve()


# pick a config dir that actually has default.yaml
def _config_dir_with_defaults() -> Path:
    """Prefer CONFIG_DIR when default.yaml is present; else bundled read-only config."""
    if (CONFIG_DIR / "default.yaml").is_file():
        return CONFIG_DIR
    from lakanvault.shared.paths import bundle_root

    bundled = bundle_root() / "config"
    if (bundled / "default.yaml").is_file():
        return bundled
    return CONFIG_DIR if CONFIG_DIR.exists() else Path("./config")


# where the static html lives
def _resolve_static_dir() -> Path:
    bundled = resource_path("lakanvault", "app", "static")
    if bundled.is_dir():
        return bundled
    local = Path(__file__).resolve().parent / "static"
    if local.is_dir():
        return local
    return bundled


REPO_ROOT = _find_repo_root()
CONFIG_DIR = REPO_ROOT / "config"
STATIC_DIR = _resolve_static_dir()
_gateway: Gateway | None = None


# startup/shutdown — wire vault proxy client then clean up
@asynccontextmanager
async def lifespan(app: FastAPI):
    import httpx
    import traceback

    # frozen builds write a tiny log next to the exe
    def _flog(msg: str) -> None:
        if not getattr(sys, "frozen", False):
            return
        try:
            path = Path(sys.executable).resolve().parent / "lakanvault-daemon.log"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(msg if msg.endswith("\n") else msg + "\n")
        except OSError:
            pass

    try:
        from lakanvault.launcher.bootstrap import seed_bundled_config

        seed_bundled_config(REPO_ROOT)
    except Exception as exc:  # pragma: no cover - best-effort before load
        _flog(f"lifespan: seed_bundled_config skipped: {exc}")

    cfg_dir = _config_dir_with_defaults()
    _flog(f"lifespan: CONFIG_DIR={cfg_dir} default={(cfg_dir / 'default.yaml').is_file()}")
    try:
        cfg = load_config(cfg_dir)
        proxy_cfg = cfg.get("proxy") or {}
        vault = InMemoryTokenVault(
            max_entries=int(proxy_cfg.get("vault_max_entries", 10_000)),
            max_bytes=int(proxy_cfg.get("vault_max_bytes", 10 * 1024 * 1024)),
        )
        client = httpx.AsyncClient()
        allowlist = list(proxy_cfg.get("allowlist") or ["https://api.openai.com"])
        openai_base = str(proxy_cfg.get("openai_base_url") or "https://api.openai.com")
        try:
            upstream = OpenAIUpstream(
                client,
                openai_base,
                allowlist,
                timeout_seconds=float(proxy_cfg.get("timeout_seconds", 120)),
            )
        except ValueError:
            upstream = None
        app.state.token_vault = vault
        app.state.httpx = client
        app.state.proxy_max_body = int(proxy_cfg.get("max_body_bytes", 1_048_576))
        app.state.proxy_gateway = ProxyGateway(
            vault,
            upstream,
            strict=bool(proxy_cfg.get("strict_mode", True)),
            ttl_seconds=float(proxy_cfg.get("vault_ttl_seconds", 3600)),
            allow_images=bool(proxy_cfg.get("allow_images", False)),
        )
        writable_data_root().mkdir(parents=True, exist_ok=True)
        _flog("lifespan: startup ok")
    except Exception:
        _flog("lifespan: startup FAILED\n" + traceback.format_exc())
        raise
    try:
        yield
    finally:
        client = getattr(app.state, "httpx", None)
        vault = getattr(app.state, "token_vault", None)
        if client is not None:
            await client.aclose()
        if vault is not None:
            vault.close()


app = FastAPI(title="LakanVault", version="0.1.0", lifespan=lifespan)
app.include_router(proxy_router)
app.include_router(internal_router)


# lazy singleton gateway
def get_gateway() -> Gateway:
    global _gateway
    if _gateway is None:
        _gateway = Gateway(config_dir=_config_dir_with_defaults())
    return _gateway


# drop gateway so next call reloads config
def reset_gateway() -> None:
    global _gateway
    _gateway = None


# resolve models dir from settings or custom path
def _resolve_models_dir(custom_dir: str | None = None) -> Path:
    if custom_dir:
        path = Path(custom_dir)
        return path if path.is_absolute() else REPO_ROOT / path
    cfg = get_gateway().get_config_snapshot()
    models_dir = cfg.get("local", {}).get("models_dir", "./data/models")
    path = Path(models_dir)
    return path if path.is_absolute() else REPO_ROOT / path


# review endpoints are loopback only
def _require_loopback(request: Request) -> None:
    try:
        assert_loopback_client(request.client)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="review endpoint: loopback only") from exc


class ProtectPauseBody(BaseModel):
    paused: bool = Field(..., description="When true, tray toasts skip new protect events")


# root health-ish info
@app.get("/")
def index() -> dict:
    return {
        "service": "LakanVault",
        "version": "0.1.0",
        "status": "ok",
        "message": "Status at /status — Prompt Review at /review — use /api/* and /v1/* endpoints.",
        "status_page": "/status",
        "review": "/review",
    }


# serve status.html
@app.get("/status")
def status_page() -> FileResponse:
    path = STATIC_DIR / "status.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="status.html not found")
    return FileResponse(path, media_type="text/html")


# serve review.html
@app.get("/review")
def review_page() -> FileResponse:
    path = STATIC_DIR / "review.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="review.html not found")
    return FileResponse(path, media_type="text/html")


# serve toast.html
@app.get("/toast")
def toast_page() -> FileResponse:
    path = STATIC_DIR / "toast.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="toast.html not found")
    return FileResponse(path, media_type="text/html")


# recent protect events for tray poll (meta only)
@app.get("/api/protect/recent")
def api_protect_recent(
    since_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """Metadata-only protect events for tray poll / status UI."""
    return {"events": get_protect_ring().recent(since_id=since_id, limit=limit)}


# protect counts for the status ui
@app.get("/api/protect/stats")
def api_protect_stats() -> dict:
    return get_protect_ring().stats()


# full review session by event id (loopback — has original text)
@app.get("/api/protect/event/{event_id}")
def api_protect_event(request: Request, event_id: int) -> dict:
    """Full review session for View → Prompt Review. Loopback only; includes original text."""
    _require_loopback(request)
    sess = get_review_sessions().get_by_event(event_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="event expired or unknown")
    return get_review_sessions().to_public_dict(sess)


# pause / unpause tray toasts
@app.post("/api/protect/pause")
def api_protect_pause(body: ProtectPauseBody) -> dict:
    ring = get_protect_ring()
    ring.set_paused(body.paused)
    return {"paused": ring.is_paused()}


# prompt review / cursor hooks — joan protect
@app.post("/api/review", response_model=ProtectResponse)
def api_review(request: Request, body: ProtectRequest) -> ProtectResponse:
    """Joan protect for Prompt Review UI and Cursor hooks. Loopback only."""
    _require_loopback(request)
    try:
        return get_gateway().protect_prompt(
            body.text, session_id=body.session_id, llm=body.llm, source="review"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"review failed: {type(exc).__name__}: {exc}",
        ) from exc


# send reviewed text to local llm
@app.post("/api/review/send", response_model=ReviewSendResponse)
def api_review_send(request: Request, body: ReviewSendRequest) -> ReviewSendResponse:
    """Send sanitized (or override original) text from a prior /api/review session. Loopback only."""
    _require_loopback(request)
    if body.base_url:
        try:
            assert_localhost_url(body.base_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return get_gateway().send_reviewed(
            body.session_id,
            body.sanitized,
            model=body.model,
            base_url=body.base_url,
            override=body.override,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# dump config snapshot
@app.get("/api/config")
def api_config() -> dict:
    return get_gateway().get_config_snapshot()


# get settings for the ui
@app.get("/api/settings")
def api_get_settings() -> dict:
    return get_gateway().get_settings()


# save settings to local.yaml n reload gateway
@app.put("/api/settings")
def api_put_settings(body: SettingsUpdate) -> dict:
    partial = body.model_dump(exclude_none=True)
    if "local_ai" in partial and partial["local_ai"].get("base_url"):
        try:
            assert_localhost_url(partial["local_ai"]["base_url"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    save_local_config(CONFIG_DIR, partial)
    reset_gateway()
    gw = get_gateway()
    gw.apply_settings(partial)
    return {"saved": True, "settings": gw.get_settings()}


# wipe local settings keys back to defaults
@app.post("/api/settings/reset")
def api_reset_settings() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    clear_local_config_keys(CONFIG_DIR, ["local_ai", "local", "privacy", "cloud"])
    reset_gateway()
    return {"reset": True, "settings": get_gateway().get_settings()}


# list model files in models dir
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


# native file picker for a model
@app.get("/api/pick-file")
def api_pick_file() -> dict:
    models_dir = _resolve_models_dir()
    path = pick_model_file(models_dir if models_dir.exists() else REPO_ROOT)
    if not path:
        return {"path": None, "cancelled": True}
    return {"path": path, "cancelled": False}


# native folder picker for models
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


# run the integrity→threat→privacy→audit scan pipeline
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


# is local llm reachable + list models
@app.get("/api/local-llm/status")
def api_local_llm_status(base_url: str | None = Query(default=None)) -> dict:
    if base_url:
        try:
            assert_localhost_url(base_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_gateway().local_llm_status(base_url=base_url)


# old lmstudio path (same as local-llm)
@app.get("/api/lmstudio/status")
def api_lmstudio_status(base_url: str | None = Query(default=None)) -> dict:
    return api_local_llm_status(base_url=base_url)


# bundled runtime status
@app.get("/api/runtime/status")
def api_runtime_status() -> dict:
    return get_gateway().runtime_status()


# switch bundled runtime model
@app.post("/api/runtime/select")
def api_runtime_select(body: dict) -> dict:
    model = (body or {}).get("model", "")
    try:
        return get_gateway().runtime_select(model)
    except ValueError as exc:
        raise HTTPException(status_code=400 if "Unknown" in str(exc) else 409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# chat with sanitize → local llm → restore
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
        blocked=bool(result.get("blocked")),
        block_reason=result.get("block_reason") or "",
    )


# streaming chat (sse)
@app.post("/api/chat/stream")
def api_chat_stream(request: ChatRequest) -> StreamingResponse:
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    if request.base_url:
        try:
            assert_localhost_url(request.base_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # yield sse data lines from gateway
    def event_gen():
        for event in get_gateway().chat_stream_events(
            request.prompt, model=request.model, base_url=request.base_url
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# integrity scan over models dir
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


# quarantine a bad model
@app.post("/api/integrity/eject")
def api_integrity_eject(request: IntegrityEjectRequest) -> dict:
    if not request.model_name.strip():
        raise HTTPException(status_code=400, detail="model_name is required")
    ok = get_gateway().eject_model(request.model_name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Model not found: {request.model_name}")
    return {"quarantined": True, "model_name": request.model_name}


# pin a model hash as baseline
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


# recent audit jsons (meta only)
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


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
