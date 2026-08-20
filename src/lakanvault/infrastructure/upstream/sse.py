"""Protocol-correct SSE parse/serialize + sliding-tail opaque token restore."""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from typing import Any

from lakanvault.contracts.proxy import OPAQUE_TOKEN_REGEX

_TOKEN_RE = re.compile(OPAQUE_TOKEN_REGEX)
_DONE = "[DONE]"


def parse_sse_chunk(raw: str) -> list[tuple[dict[str, str], str]]:
    """Split a buffer fragment into (fields, data_payload) events.

    fields may include event, id, comment (':'). data_payload is the joined data.
    """
    events: list[tuple[dict[str, str], str]] = []
    for block in re.split(r"\n\n+", raw.replace("\r\n", "\n")):
        if not block.strip():
            continue
        fields: dict[str, str] = {}
        data_lines: list[str] = []
        for line in block.split("\n"):
            if not line:
                continue
            if line.startswith(":"):
                fields["comment"] = line[1:].lstrip()
                continue
            if ":" in line:
                name, value = line.split(":", 1)
                value = value[1:] if value.startswith(" ") else value
                if name == "data":
                    data_lines.append(value)
                else:
                    fields[name] = value
        events.append((fields, "\n".join(data_lines)))
    return events


def serialize_sse(fields: dict[str, str], data: str) -> str:
    lines: list[str] = []
    if comment := fields.get("comment"):
        lines.append(f": {comment}")
    if event := fields.get("event"):
        lines.append(f"event: {event}")
    if eid := fields.get("id"):
        lines.append(f"id: {eid}")
    if data == "":
        if not lines:
            return "\n"
    else:
        for part in data.split("\n"):
            lines.append(f"data: {part}")
    return "\n".join(lines) + "\n\n"


class SlidingTokenRestorer:
    """Restore complete [LV_…] tokens; hold a possible incomplete suffix."""

    _INCOMPLETE = re.compile(
        r"(?:\[(?:L(?:V(?:_(?:[A-Z2-7]{0,26})?)?)?)?)?$"
    )

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = dict(mapping)
        self._buf = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        if not self._mapping:
            return chunk
        self._buf += chunk
        hold = 0
        match = self._INCOMPLETE.search(self._buf)
        if match and match.group(0):
            hold = len(match.group(0))
        emit, self._buf = self._buf[: len(self._buf) - hold], self._buf[len(self._buf) - hold :]
        return self._restore_complete(emit)

    def flush(self) -> str:
        out = self._restore_complete(self._buf)
        self._buf = ""
        return out

    def _restore_complete(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            token = match.group(0)
            return self._mapping.get(token, token)

        return _TOKEN_RE.sub(repl, text)


def restore_sse_data_json(
    data: str,
    restorer: SlidingTokenRestorer,
    *,
    flush: bool = False,
) -> str:
    if data == _DONE:
        return _DONE
    try:
        obj: dict[str, Any] = json.loads(data)
    except json.JSONDecodeError:
        out = restorer.feed(data)
        return out + (restorer.flush() if flush else "")
    choices = obj.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                delta = dict(delta)
                content = restorer.feed(delta["content"])
                if flush:
                    content += restorer.flush()
                delta["content"] = content
                choice["delta"] = delta
            # tool_calls / function.arguments are never restored
    return json.dumps(obj, separators=(",", ":"))


def iter_restored_sse(
    chunks: Iterator[str],
    mapping: dict[str, str],
    lookup_delta: Callable[[dict[str, Any]], None] | None = None,
) -> Iterator[str]:
    restorer = SlidingTokenRestorer(mapping)
    pending = ""
    for chunk in chunks:
        pending += chunk.replace("\r\n", "\n")
        while "\n\n" in pending:
            block, pending = pending.split("\n\n", 1)
            events = parse_sse_chunk(block + "\n\n")
            for fields, data in events:
                if data == _DONE:
                    leftover = restorer.flush()
                    if leftover:
                        extra = json.dumps(
                            {"choices": [{"index": 0, "delta": {"content": leftover}}]},
                            separators=(",", ":"),
                        )
                        yield serialize_sse({}, extra)
                    yield serialize_sse(fields, _DONE)
                    continue
                yield serialize_sse(fields, restore_sse_data_json(data, restorer))
    if pending.strip():
        events = parse_sse_chunk(pending + "\n\n")
        for i, (fields, data) in enumerate(events):
            last = i == len(events) - 1
            yield serialize_sse(
                fields,
                restore_sse_data_json(data, restorer, flush=last and data != _DONE),
            )
    leftover = restorer.flush()
    if leftover:
        extra = json.dumps(
            {"choices": [{"index": 0, "delta": {"content": leftover}}]},
            separators=(",", ":"),
        )
        yield serialize_sse({}, extra)
