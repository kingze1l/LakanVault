"""PII span detection — pattern-only Presidio + regex fallback (no spaCy download)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}(?!\d)",
)
NAME_INTRO_RE = re.compile(
    r"(?i)\b(?:my name is|i am|i'm|call me|this is)\s+([A-Za-z][A-Za-z0-9_-]{1,30})\b",
)
# Presidio matches the full regex span — use lookbehind so only the name token is tagged.
NAME_AFTER_INTRO_PATTERNS = [
    r"(?i)(?<=my name is )[A-Za-z][A-Za-z0-9_-]{1,30}\b",
    r"(?i)(?<=call me )[A-Za-z][A-Za-z0-9_-]{1,30}\b",
    r"(?i)(?<=i am )[A-Za-z][A-Za-z0-9_-]{1,30}\b",
    r"(?i)(?<=i'm )[A-Za-z][A-Za-z0-9_-]{1,30}\b",
    r"(?i)(?<=this is )[A-Za-z][A-Za-z0-9_-]{1,30}\b",
]


@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    entity_type: str
    text: str


def _regex_spans(text: str) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    for m in EMAIL_RE.finditer(text):
        spans.append(PiiSpan(m.start(), m.end(), "EMAIL_ADDRESS", m.group()))
    for m in PHONE_RE.finditer(text):
        spans.append(PiiSpan(m.start(), m.end(), "PHONE_NUMBER", m.group()))
    for m in NAME_INTRO_RE.finditer(text):
        name = m.group(1)
        start = m.start(1)
        spans.append(PiiSpan(start, start + len(name), "PERSON", name))
    return _dedupe_spans(spans)


def _dedupe_spans(spans: list[PiiSpan]) -> list[PiiSpan]:
    if not spans:
        return []
    spans = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    kept: list[PiiSpan] = []
    for span in spans:
        if any(span.start >= k.start and span.end <= k.end for k in kept):
            continue
        kept.append(span)
    return sorted(kept, key=lambda s: s.start)


def _try_pattern_analyzer():
    try:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry

        registry = RecognizerRegistry()
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="EMAIL_ADDRESS",
                patterns=[Pattern("email", EMAIL_RE.pattern, 0.9)],
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="PHONE_NUMBER",
                patterns=[Pattern("phone", PHONE_RE.pattern, 0.75)],
            )
        )
        person_patterns = [
            Pattern(f"name_intro_{i}", pat, 0.85)
            for i, pat in enumerate(NAME_AFTER_INTRO_PATTERNS)
        ]
        registry.add_recognizer(
            PatternRecognizer(supported_entity="PERSON", patterns=person_patterns)
        )
        return AnalyzerEngine(registry=registry, supported_languages=["en"], nlp_engine=None)
    except ImportError:
        logger.warning("presidio-analyzer not installed — using regex fallback only")
        return None
    except (Exception, SystemExit) as exc:
        logger.warning("Presidio pattern analyzer unavailable: %s", exc)
        return None


_ANALYZER: object | None = None
_ANALYZER_READY = False


def _get_analyzer():
    """Lazy singleton — Presidio init is expensive; cache across requests."""
    global _ANALYZER, _ANALYZER_READY
    if not _ANALYZER_READY:
        _ANALYZER = _try_pattern_analyzer()
        _ANALYZER_READY = True
    return _ANALYZER


def _presidio_spans(text: str, analyzer) -> list[PiiSpan]:
    results = analyzer.analyze(text=text, language="en")
    return [
        PiiSpan(r.start, r.end, r.entity_type, text[r.start : r.end])
        for r in results
    ]


def find_pii_spans(text: str) -> tuple[list[PiiSpan], str]:
    """Return (spans, engine_label) where engine_label is presidio|regex|none."""
    if not text:
        return [], "none"

    analyzer = _get_analyzer()
    if analyzer is not None:
        try:
            return _dedupe_spans(_presidio_spans(text, analyzer)), "presidio"
        except (Exception, SystemExit) as exc:
            logger.warning("Presidio analyze failed, falling back to regex: %s", exc)

    return _regex_spans(text), "regex"
