"""OpenAI payload walk — restore assistant text only."""
from lakanvault.infrastructure.token_vault import generate_opaque_token
from lakanvault.local_core.dlp.openai_payload import (
    UninspectedPayloadError,
    restore_chat_response,
    sanitize_chat_request,
)
from lakanvault.contracts.proxy import TransformResult


def test_sanitize_user_and_tool_text() -> None:
    hits = []

    def tx(text: str) -> TransformResult:
        hits.append(text)
        return TransformResult(text=text.replace("jane.doe@example.com", "[T]"))

    payload = {
        "model": "gpt-4o-mini",
        "unknown_future_field": True,
        "messages": [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "mail jane.doe@example.com"},
            {"role": "tool", "content": "jane.doe@example.com"},
            {"role": "assistant", "content": "ok"},
        ],
    }
    out, findings, uninspected = sanitize_chat_request(payload, tx, strict=True)
    assert out["unknown_future_field"] is True
    assert "jane.doe@example.com" not in out["messages"][1]["content"]
    assert out["messages"][3]["content"] == "ok"
    assert uninspected == 0
    assert findings


def test_strict_mode_blocks_images() -> None:
    def tx(text: str) -> TransformResult:
        return TransformResult(text=text)

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "see"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/a.png"}},
                ],
            }
        ]
    }
    try:
        sanitize_chat_request(payload, tx, strict=True, allow_images=False)
    except UninspectedPayloadError:
        return
    raise AssertionError("expected UninspectedPayloadError")


def test_restore_skips_tool_call_arguments() -> None:
    token = generate_opaque_token()
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"use {token}",
                    "tool_calls": [
                        {"function": {"name": "send", "arguments": f'{{"secret":"{token}"}}'}}
                    ],
                }
            }
        ]
    }
    out = restore_chat_response(payload, lambda text: text.replace(token, "SECRET"))
    assert "SECRET" in out["choices"][0]["message"]["content"]
    assert token in out["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    assert "SECRET" not in out["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
