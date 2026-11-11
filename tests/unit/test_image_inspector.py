# sprint 3 image inspect block-first no ocr text in results
from __future__ import annotations

import base64

from lakanvault.contracts.mcp import PolicyAction
from lakanvault.contracts.proxy import TransformResult
from lakanvault.local_core.dlp import image_inspector as mod
from lakanvault.local_core.dlp.image_inspector import ImageInspector, OcrEngine

# tiny fake png as a data url
def _png_data_url(payload: bytes | None = None) -> str:
    raw = payload if payload is not None else (b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

# chat payload with one image_url
def _payload(url: str) -> dict:
    return {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": url}}],
            }
        ]
    }

# ocr stub that just returns fixed text
class FakeOcr(OcrEngine):
    def __init__(self, text: str) -> None:
        self._text = text

    def extract(self, image_bytes: bytes, mime: str) -> str:
        return self._text

# transform stub that always allows
def _allow(_text: str) -> TransformResult:
    return TransformResult(text=_text, action=PolicyAction.ALLOW)


def test_remote_url_blocked_in_strict() -> None:
    inspector = ImageInspector(FakeOcr("hello"))
    result = inspector.inspect(_payload("https://cdn.example/a.png"), _allow, strict=True)
    assert result.blocked is True
    assert "remote" in result.reason


def test_bad_magic_blocked() -> None:
    inspector = ImageInspector(FakeOcr("hello"))
    url = "data:image/png;base64," + base64.b64encode(b"not-a-png").decode()
    result = inspector.inspect(_payload(url), _allow, strict=True)
    assert result.blocked is True


def test_oversized_blocked(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_MAX_DECODED", 8)
    inspector = ImageInspector(FakeOcr("hello"))
    result = inspector.inspect(_payload(_png_data_url()), _allow, strict=True)
    assert result.blocked is True


def test_ocr_secret_blocks_whole_request() -> None:
    inspector = ImageInspector(FakeOcr("My key is sk-9f8e7d6c5b4a3210fedcba0987654321zz"))

    def tx(text: str) -> TransformResult:
        if "sk-" in text:
            return TransformResult(text="", blocked=True, action=PolicyAction.BLOCK)
        return TransformResult(text=text, action=PolicyAction.ALLOW)

    result = inspector.inspect(_payload(_png_data_url()), tx, strict=True)
    assert result.blocked is True
    assert "request blocked" in result.reason


def test_ocr_email_redact_still_blocks_request() -> None:
    inspector = ImageInspector(FakeOcr("mail jane.doe@example.com"))

    def tx(text: str) -> TransformResult:
        return TransformResult(
            text="mail [LV_AAAAAAAAAAAAAAAAAAAAAAAAAA]",
            action=PolicyAction.REDACT,
        )

    result = inspector.inspect(_payload(_png_data_url()), tx, strict=True)
    assert result.blocked is True


def test_ocr_unavailable_blocks_in_strict() -> None:
    inspector = ImageInspector()  # default engine raises OcrUnavailable
    result = inspector.inspect(_payload(_png_data_url()), _allow, strict=True)
    assert result.blocked is True
    assert "OCR" in result.reason


def test_inspect_result_has_no_ocr_text() -> None:
    inspector = ImageInspector(FakeOcr("ssn 123-45-6789"))
    result = inspector.inspect(_payload(_png_data_url()), _allow, strict=True)
    dumped = result.__dict__
    assert "ocr_text" not in dumped
    assert "123-45-6789" not in str(dumped)
