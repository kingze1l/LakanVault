"""Walk OpenAI Chat Completions JSON without dropping unknown fields."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lakanvault.contracts.proxy import RestoreAllowSet, TransformResult


class UninspectedPayloadError(ValueError):
    """Strict mode: image/audio/file block cannot be scanned as text."""


def _transform_content(
    content: Any,
    transform: Callable[[str], TransformResult],
    *,
    strict: bool,
    allow_images: bool = False,
) -> tuple[Any, list[TransformResult], int]:
    findings: list[TransformResult] = []
    uninspected = 0
    if content is None:
        return content, findings, 0
    if isinstance(content, str):
        result = transform(content)
        findings.append(result)
        return result.text if not result.blocked else "", findings, 0
    if isinstance(content, list):
        out: list[Any] = []
        for part in content:
            if not isinstance(part, dict):
                out.append(part)
                continue
            kind = part.get("type")
            if kind in (None, "text") and "text" in part:
                clone = dict(part)
                result = transform(str(clone.get("text") or ""))
                findings.append(result)
                clone["text"] = result.text if not result.blocked else ""
                out.append(clone)
            elif kind in {"image_url", "image"} or "image_url" in part:
                if allow_images:
                    out.append(part)
                elif strict:
                    raise UninspectedPayloadError("image content is uninspected")
                else:
                    uninspected += 1
                    out.append(part)
            elif kind in {"input_audio", "file", "input_file"}:
                if strict:
                    raise UninspectedPayloadError(f"{kind} content is uninspected")
                uninspected += 1
                out.append(part)
            else:
                out.append(part)
        return out, findings, uninspected
    return content, findings, 0


def sanitize_chat_request(
    payload: dict[str, Any],
    transform: Callable[[str], TransformResult],
    *,
    strict: bool = True,
    allow_images: bool = False,
) -> tuple[dict[str, Any], list[TransformResult], int]:
    """Sanitize user/system/developer/tool text. Preserve unknown keys."""
    out = dict(payload)
    findings: list[TransformResult] = []
    uninspected = 0
    messages = out.get("messages")
    if isinstance(messages, list):
        new_messages = []
        for msg in messages:
            if not isinstance(msg, dict):
                new_messages.append(msg)
                continue
            clone = dict(msg)
            role = clone.get("role")
            if role in {"system", "developer", "user", "tool"}:
                content, hits, skip = _transform_content(
                    clone.get("content"),
                    transform,
                    strict=strict,
                    allow_images=allow_images,
                )
                clone["content"] = content
                findings.extend(hits)
                uninspected += skip
            new_messages.append(clone)
        out["messages"] = new_messages
    return out, findings, uninspected


def restore_chat_response(
    payload: dict[str, Any],
    restore: Callable[[str], str],
) -> dict[str, Any]:
    """Restore opaque tokens in assistant message text only — never tool_calls."""
    out = dict(payload)
    choices = out.get("choices")
    if not isinstance(choices, list):
        return out
    new_choices = []
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        clone = dict(choice)
        message = clone.get("message")
        if isinstance(message, dict):
            msg = dict(message)
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = restore(content)
            elif isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") in (None, "text") and "text" in part:
                        p = dict(part)
                        p["text"] = restore(str(p.get("text") or ""))
                        parts.append(p)
                    else:
                        parts.append(part)
                msg["content"] = parts
            clone["message"] = msg
        new_choices.append(clone)
    out["choices"] = new_choices
    return out


def collect_existing_tokens(payload: dict[str, Any], finder: Callable[[str], list[str]]) -> RestoreAllowSet:
    allow = RestoreAllowSet()

    def walk(node: Any) -> None:
        if isinstance(node, str):
            for token in finder(node):
                allow.add(token)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload.get("messages"))
    return allow
