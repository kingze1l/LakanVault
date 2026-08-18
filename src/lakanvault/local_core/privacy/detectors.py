"""PII span detection — regex + optional local spaCy NER (en_core_web_sm)."""
from __future__ import annotations

import logging
import os
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
    r"(?i)\b(?:my name is|i am|i'm|call me|this is)\s+([A-Za-z][A-Za-z0-9_'-]{1,30})\b",
)
NAME_CONTEXT_RE = re.compile(
    r"(?i)\b(?:for|dear|telling|regarding|attention)\s+([A-Za-z][A-Za-z0-9_'-]{2,30})\b",
)
NAME_TO_RE = re.compile(
    r"\bto\s+([A-Z][a-z][A-Za-z0-9_'-]{1,29})\b",
)
NAME_SIGNED_RE = re.compile(
    r"(?i)(?:^|\n)\s*(?:thanks|regards|sincerely|cheers),?\s*\n?\s*([A-Z][a-z]{2,30})\b",
)

_NAME_BLOCKLIST = frozenset({
    "the", "a", "an", "my", "your", "his", "her", "their", "our", "this", "that",
    "today", "tomorrow", "yesterday", "class", "school", "work", "me", "you",
    "him", "her", "them", "us", "it", "all", "any", "some", "every", "each",
    "he", "she", "they", "we", "i", "cant", "can't", "cannot", "make", "write",
    "email", "tutor", "teacher", "student", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday", "morning", "afternoon", "please",
    "thanks", "hello", "dear", "sir", "madam", "team", "everyone", "anyone",
})

NAME_AFTER_INTRO_PATTERNS = [
    r"(?i)(?<=my name is )[A-Za-z][A-Za-z0-9_'-]{1,30}\b",
    r"(?i)(?<=call me )[A-Za-z][A-Za-z0-9_'-]{1,30}\b",
    r"(?i)(?<=i am )[A-Za-z][A-Za-z0-9_'-]{1,30}\b",
    r"(?i)(?<=i'm )[A-Za-z][A-Za-z0-9_'-]{1,30}\b",
    r"(?i)(?<=this is )[A-Za-z][A-Za-z0-9_'-]{1,30}\b",
]
NAME_CONTEXT_PATTERNS = [
    r"(?i)(?<=for )[A-Za-z][A-Za-z0-9_'-]{2,30}\b",
    r"(?<=to )[A-Z][a-z][A-Za-z0-9_'-]{1,29}\b",
    r"(?i)(?<=dear )[A-Za-z][A-Za-z0-9_'-]{2,30}\b",
    r"(?i)(?<=telling )[A-Za-z][A-Za-z0-9_'-]{2,30}\b",
    r"(?i)(?<=hey )[A-Za-z][A-Za-z0-9_'-]{2,30}\b",
    r"(?i)(?<=hi )[A-Za-z][A-Za-z0-9_'-]{2,30}\b",
    r"(?i)(?<=hello )[A-Za-z][A-Za-z0-9_'-]{2,30}\b",
]


@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    entity_type: str
    text: str


def _is_plausible_name(token: str) -> bool:
    low = token.lower().strip("'")
    if low in _NAME_BLOCKLIST:
        return False
    if len(low) < 2:
        return False
    if low.isdigit():
        return False
    return True


def _name_span(m: re.Match, group: int = 1) -> PiiSpan | None:
    name = m.group(group)
    if not _is_plausible_name(name):
        return None
    start = m.start(group)
    return PiiSpan(start, start + len(name), "PERSON", name)


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


def _regex_spans(text: str) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    for m in EMAIL_RE.finditer(text):
        spans.append(PiiSpan(m.start(), m.end(), "EMAIL_ADDRESS", m.group()))
    for m in PHONE_RE.finditer(text):
        spans.append(PiiSpan(m.start(), m.end(), "PHONE_NUMBER", m.group()))
    for m in NAME_INTRO_RE.finditer(text):
        s = _name_span(m)
        if s:
            spans.append(s)
    for m in NAME_CONTEXT_RE.finditer(text):
        s = _name_span(m)
        if s:
            spans.append(s)
    for m in NAME_TO_RE.finditer(text):
        s = _name_span(m)
        if s:
            spans.append(s)
    for m in NAME_SIGNED_RE.finditer(text):
        s = _name_span(m)
        if s:
            spans.append(s)
    return _dedupe_spans(spans)


def _engine_mode() -> str:
    env = os.environ.get("LAKANVAULT_PRIVACY_ENGINE", "").strip().lower()
    if env:
        return env
    try:
        from lakanvault.shared.config import load_config

        return str(load_config().get("privacy", {}).get("engine", "auto")).lower()
    except Exception:
        return "auto"


def _try_pattern_analyzer():
    # AnalyzerEngine(nlp_engine=None) makes Presidio create a default spaCy
    # engine and download en_core_web_lg — that breaks air-gap and GitHub
    # Actions. Regex in _regex_spans already covers the same entities.
    return None


def _try_spacy_analyzer():
    try:
        import spacy
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import SpacyNlpEngine

        if not spacy.util.is_package("en_core_web_sm"):
            logger.info(
                "Local NER model not installed. Run: python -m spacy download en_core_web_sm"
            )
            return None

        nlp_engine = SpacyNlpEngine(
            models=[{"lang_code": "en", "model_name": "en_core_web_sm"}],
        )
        return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    except ImportError:
        return None
    except (Exception, SystemExit) as exc:
        logger.warning("SpaCy NER analyzer unavailable: %s", exc)
        return None


_PATTERN_ANALYZER: object | None = None
_PATTERN_READY = False
_SPACY_ANALYZER: object | None = None
_SPACY_READY = False


def _get_pattern_analyzer():
    global _PATTERN_ANALYZER, _PATTERN_READY
    if not _PATTERN_READY:
        _PATTERN_ANALYZER = _try_pattern_analyzer()
        _PATTERN_READY = True
    return _PATTERN_ANALYZER


def _get_spacy_analyzer():
    global _SPACY_ANALYZER, _SPACY_READY
    if not _SPACY_READY:
        _SPACY_ANALYZER = _try_spacy_analyzer()
        _SPACY_READY = True
    return _SPACY_ANALYZER


def reset_analyzer_cache() -> None:
    """For tests — clear lazy singletons."""
    global _PATTERN_ANALYZER, _PATTERN_READY, _SPACY_ANALYZER, _SPACY_READY
    _PATTERN_ANALYZER = None
    _PATTERN_READY = False
    _SPACY_ANALYZER = None
    _SPACY_READY = False


def _presidio_spans(text: str, analyzer) -> list[PiiSpan]:
    results = analyzer.analyze(text=text, language="en")
    spans: list[PiiSpan] = []
    for r in results:
        if r.entity_type not in {"PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"}:
            continue
        fragment = text[r.start : r.end]
        if r.entity_type == "PERSON" and not _is_plausible_name(fragment):
            continue
        spans.append(PiiSpan(r.start, r.end, r.entity_type, fragment))
    return spans


def find_pii_spans(text: str, engine: str | None = None) -> tuple[list[PiiSpan], str]:
    """Return (spans, engine_label). engine config: auto | regex | spacy | pattern."""
    if not text:
        return [], "none"

    mode = (engine or _engine_mode()).lower()
    regex_hits = _regex_spans(text)

    if mode == "regex":
        return regex_hits, "regex"

    merged = list(regex_hits)
    used_engines: list[str] = []

    if mode in ("auto", "spacy"):
        spacy_a = _get_spacy_analyzer()
        if spacy_a is not None:
            try:
                merged = _dedupe_spans(merged + _presidio_spans(text, spacy_a))
                used_engines.append("spacy")
            except (Exception, SystemExit) as exc:
                logger.warning("SpaCy analyze failed: %s", exc)

    if mode in ("auto", "pattern") and not used_engines:
        pat_a = _get_pattern_analyzer()
        if pat_a is not None:
            try:
                merged = _dedupe_spans(merged + _presidio_spans(text, pat_a))
                used_engines.append("presidio")
            except (Exception, SystemExit) as exc:
                logger.warning("Presidio analyze failed: %s", exc)

    if not merged and regex_hits:
        merged = regex_hits
        used_engines = ["regex"]
    elif regex_hits and used_engines:
        merged = _dedupe_spans(merged + regex_hits)
        if "regex" not in used_engines:
            used_engines.append("regex")

    if not merged:
        return [], used_engines[0] if used_engines else "none"

    label = "+".join(dict.fromkeys(used_engines)) if used_engines else "regex"
    return merged, label
