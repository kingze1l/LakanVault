"""Thin OpenAI-compatible + internal sanitize routers. Logic lives in ProxyGateway."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from lakanvault.contracts.proxy import SanitizeTextRequest, SanitizeTextResponse
from lakanvault.orchestration.proxy_gateway import ProxyGateway

router = APIRouter()
internal_router = APIRouter()


def _gateway(request: Request) -> ProxyGateway:
    gw = getattr(request.app.state, "proxy_gateway", None)
    if gw is None:
        raise HTTPException(status_code=503, detail="proxy gateway not ready")
    return gw


def _header_map(request: Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items()}


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    gw = _gateway(request)
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid json")
    max_body = int(getattr(request.app.state, "proxy_max_body", 1_048_576))
    raw_len = int(request.headers.get("content-length") or 0)
    if raw_len > max_body:
        raise HTTPException(status_code=413, detail="payload too large")
    rid = uuid.uuid4().hex[:12]
    if payload.get("stream"):
        async def gen():
            async for chunk in gw.iter_sse(payload, _header_map(request), request_id=rid):
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream")
    outcome = await gw.chat_completions(payload, _header_map(request), request_id=rid)
    return JSONResponse(outcome.body, status_code=outcome.status_code)


@router.get("/v1/models")
async def list_models(request: Request) -> JSONResponse:
    gw = _gateway(request)
    upstream = gw._upstream
    if upstream is None:
        raise HTTPException(status_code=503, detail="no upstream configured")
    try:
        resp = await upstream.list_models(_header_map(request))
        data = resp.json()
        status = resp.status_code
        await resp.aclose()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="upstream request failed") from exc
    return JSONResponse(data, status_code=status)


@internal_router.post("/internal/v1/sanitize")
def internal_sanitize(request: Request, body: SanitizeTextRequest) -> SanitizeTextResponse:
    gw = _gateway(request)
    result = gw.sanitize_text(body.text, body.request_id)
    return SanitizeTextResponse(
        text="" if result.blocked else result.text,
        blocked=result.blocked,
        reason=result.reason,
        tokens_minted=list(result.tokens_minted),
        action=result.action,
        tier=result.tier,
    )
