# Overlook / Flag word dictionary — Sami layer on top of Joan findings.
"""Persist + apply custom overlook/flag terms without rewriting Joan detectors."""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from lakanvault.local_core.findings import Finding, Tier, resolve_overlaps
from lakanvault.shared.paths import writable_data_root

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_DEFAULT: dict[str, list[str]] = {"overlook": [], "flag": []}


def _path() -> Path:
    return writable_data_root() / "word_dictionary.json"


def _normalize_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        term = str(item or "").strip()
        if not term:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
    return out


def _normalize_payload(data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        return {"overlook": [], "flag": []}
    return {
        "overlook": _normalize_list(data.get("overlook")),
        "flag": _normalize_list(data.get("flag")),
    }


def load_dictionary() -> dict[str, list[str]]:
    path = _path()
    with _LOCK:
        if not path.is_file():
            return {"overlook": [], "flag": []}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("word_dictionary load failed: %s", exc)
            return {"overlook": [], "flag": []}
        return _normalize_payload(raw)


def save_dictionary(payload: dict[str, Any]) -> dict[str, list[str]]:
    cleaned = _normalize_payload(payload)
    path = _path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return cleaned


def _overlook_set(terms: list[str]) -> set[str]:
    return {t.casefold() for t in terms}


def _drop_overlooked(findings: list[Finding], overlook: set[str]) -> list[Finding]:
    if not overlook:
        return findings
    kept: list[Finding] = []
    for f in findings:
        if f.text.casefold() in overlook:
            continue
        # Also overlook when the finding span is exactly an overlook term match.
        span = f.text.strip().casefold()
        if span in overlook:
            continue
        kept.append(f)
    return kept


def _flag_findings(text: str, terms: list[str], covered: list[Finding]) -> list[Finding]:
    if not terms or not text:
        return []
    added: list[Finding] = []
    for term in terms:
        if not term:
            continue
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            if any(not (end <= c.start or start >= c.end) for c in covered + added):
                continue
            added.append(
                Finding(
                    entity_type="CUSTOM_FLAG",
                    text=text[start:end],
                    start=start,
                    end=end,
                    confidence=0.95,
                    tier=Tier.PII_MODERATE,
                    source="dictionary",
                )
            )
    return added


def apply_dictionary(text: str, findings: list[Finding]) -> list[Finding]:
    """Overlook matching Joan spans; Flag uncovered custom terms as CUSTOM_FLAG."""
    data = load_dictionary()
    overlook = _overlook_set(data["overlook"])
    trimmed = _drop_overlooked(list(findings), overlook)
    flagged = _flag_findings(text, data["flag"], trimmed)
    return resolve_overlaps(trimmed + flagged)
