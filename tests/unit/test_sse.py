"""SSE parse/serialize and sliding-tail opaque token restore."""
from __future__ import annotations

import json

from lakanvault.infrastructure.token_vault import generate_opaque_token
from lakanvault.infrastructure.upstream.sse import (
    SlidingTokenRestorer,
    iter_restored_sse,
    parse_sse_chunk,
    restore_sse_data_json,
    serialize_sse,
)


def test_parse_preserves_comment_event_and_id() -> None:
    raw = ": keep-alive\nevent: delta\nid: 7\ndata: hello\n\n"
    events = parse_sse_chunk(raw)
    assert len(events) == 1
    fields, data = events[0]
    assert fields["comment"] == "keep-alive"
    assert fields["event"] == "delta"
    assert fields["id"] == "7"
    assert data == "hello"
    assert "event: delta" in serialize_sse(fields, data)
    assert "id: 7" in serialize_sse(fields, data)


def test_done_event_round_trip() -> None:
    raw = "data: [DONE]\n\n"
    fields, data = parse_sse_chunk(raw)[0]
    assert data == "[DONE]"
    assert serialize_sse(fields, data) == "data: [DONE]\n\n"


def test_restore_every_character_boundary() -> None:
    token = generate_opaque_token()
    mapping = {token: "SECRET"}
    restorer = SlidingTokenRestorer(mapping)
    source = f"hi {token} café"
    pieces = [restorer.feed(ch) for ch in source]
    pieces.append(restorer.flush())
    assert "".join(pieces) == "hi SECRET café"


def test_unfinished_token_at_eof_is_emitted() -> None:
    token = generate_opaque_token()
    restorer = SlidingTokenRestorer({token: "SECRET"})
    partial = token[:10]
    assert restorer.feed(partial) == ""
    assert restorer.flush() == partial


def test_utf8_multibyte_not_corrupted() -> None:
    token = generate_opaque_token()
    restorer = SlidingTokenRestorer({token: "密钥"})
    text = f"你好 {token}"
    out = "".join(restorer.feed(ch) for ch in text) + restorer.flush()
    assert out == "你好 密钥"


def test_sse_json_restores_delta_content_only() -> None:
    token = generate_opaque_token()
    restorer = SlidingTokenRestorer({token: "SECRET"})
    payload = {
        "choices": [
            {
                "index": 0,
                "delta": {
                    "content": token,
                    "tool_calls": [{"function": {"arguments": token}}],
                },
            }
        ]
    }
    out = json.loads(restore_sse_data_json(json.dumps(payload), restorer, flush=True))
    assert out["choices"][0]["delta"]["content"] == "SECRET"
    assert out["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == token


def test_iter_restored_sse_split_across_events() -> None:
    token = generate_opaque_token()
    mid = len(token) // 2
    events = [
        f'data: {{"choices":[{{"delta":{{"content":"{token[:mid]}"}}}}]}}\n\n',
        f'data: {{"choices":[{{"delta":{{"content":"{token[mid:]}"}}}}]}}\n\n',
        "data: [DONE]\n\n",
    ]
    restored = "".join(iter_restored_sse(events, {token: "SECRET"}))
    assert "SECRET" in restored
    assert token not in restored
    assert "[DONE]" in restored
