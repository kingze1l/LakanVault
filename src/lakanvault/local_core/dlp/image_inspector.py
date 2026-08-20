"""Local inline-image inspection. OCR text is never logged; secrets block the request."""
from __future__ import annotations

import base64
import re
from collections.abc import Callable
from dataclasses import dataclass

from lakanvault.contracts.mcp import PolicyAction
from lakanvault.contracts.proxy import TransformResult

_DATA_URL = re.compile(
    r"^data:(image/(png|jpeg|jpg|webp));base64,([A-Za-z0-9+/=\s]+)$",
    re.IGNORECASE | re.DOTALL,
)
_MAX_IMAGES = 4
_MAX_B64_CHARS = 2_800_000  # ~2 MiB decoded
_MAX_DECODED = 2_000_000
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_WEBP = b"RIFF"


class OcrUnavailable(RuntimeError):
    pass


class OcrEngine:
    def extract(self, image_bytes: bytes, mime: str) -> str:
        raise OcrUnavailable("no local OCR engine configured")


@dataclass
class ImageInspectResult:
    blocked: bool
    reason: str = ""
    inspected: int = 0


def _iter_image_urls(payload: dict) -> list[str]:
    urls: list[str] = []
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        return urls
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            image = part.get("image_url")
            if isinstance(image, dict) and isinstance(image.get("url"), str):
                urls.append(image["url"])
            elif part.get("type") == "image_url" and isinstance(part.get("url"), str):
                urls.append(part["url"])
    return urls


def _decode_data_url(url: str) -> tuple[str, bytes]:
    match = _DATA_URL.match(url.strip())
    if not match:
        raise ValueError("unsupported image encoding")
    mime = f"image/{match.group(2).lower()}"
    if mime == "image/jpg":
        mime = "image/jpeg"
    b64 = re.sub(r"\s+", "", match.group(3))
    if len(b64) > _MAX_B64_CHARS:
        raise ValueError("image payload too large")
    # estimate before allocate
    est = (len(b64) * 3) // 4
    if est > _MAX_DECODED:
        raise ValueError("image payload too large")
    raw = base64.b64decode(b64, validate=False)
    if len(raw) > _MAX_DECODED:
        raise ValueError("image payload too large")
    if mime == "image/png" and not raw.startswith(_PNG):
        raise ValueError("image magic mismatch")
    if mime == "image/jpeg" and not raw.startswith(_JPEG):
        raise ValueError("image magic mismatch")
    if mime == "image/webp" and not raw.startswith(_WEBP):
        raise ValueError("image magic mismatch")
    return mime, raw


class ImageInspector:
    def __init__(self, engine: OcrEngine | None = None) -> None:
        self._engine = engine or OcrEngine()

    def inspect(
        self,
        payload: dict,
        transform: Callable[[str], TransformResult],
        *,
        strict: bool = True,
    ) -> ImageInspectResult:
        urls = _iter_image_urls(payload)
        if not urls:
            return ImageInspectResult(blocked=False, inspected=0)
        if len(urls) > _MAX_IMAGES:
            return ImageInspectResult(True, "too many images", len(urls))
        inspected = 0
        for url in urls:
            if url.lower().startswith("http://") or url.lower().startswith("https://"):
                if strict:
                    return ImageInspectResult(True, "remote image URL is uninspected", inspected)
                continue
            try:
                mime, raw = _decode_data_url(url)
                text = self._engine.extract(raw, mime)
            except OcrUnavailable:
                if strict:
                    return ImageInspectResult(True, "OCR unavailable", inspected)
                continue
            except Exception:
                if strict:
                    return ImageInspectResult(True, "image inspection failed", inspected)
                continue
            inspected += 1
            result = transform(text or "")
            if result.blocked or result.action in {
                PolicyAction.BLOCK,
                PolicyAction.REDACT,
                PolicyAction.WARN,
            }:
                return ImageInspectResult(
                    True,
                    "sensitive content in image — request blocked",
                    inspected,
                )
        return ImageInspectResult(False, inspected=inspected)
