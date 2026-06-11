"""Privacy stage — PII detection via local patterns (no runtime SpaCy download)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from lakanvault.contracts.events import PipelineEvent, StageResult, StageStatus
from lakanvault.contracts.ports import PipelineStage

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


def _regex_pii_scan(text: str) -> tuple[int, list[str]]:
    entity_types: list[str] = []
    emails = _EMAIL.findall(text)
    phones = _PHONE.findall(text)
    if emails:
        entity_types.append("EMAIL")
    if phones:
        entity_types.append("PHONE")
    return len(emails) + len(phones), entity_types


def _build_pattern_analyzer():
    try:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
        from presidio_analyzer.recognizer_registry import RecognizerRegistry

        registry = RecognizerRegistry()
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="EMAIL_ADDRESS",
                patterns=[Pattern(name="email_pattern", regex=_EMAIL.pattern, score=0.85)],
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="PHONE_NUMBER",
                patterns=[Pattern(name="phone_pattern", regex=_PHONE.pattern, score=0.75)],
            )
        )
        return AnalyzerEngine(registry=registry, supported_languages=["en"])
    except Exception as exc:
        logger.warning("Pattern-based Presidio unavailable: %s", exc)
        return None


class PrivacyStage(PipelineStage):
    def __init__(
        self,
        enabled: bool = True,
        spacy_model_path: str | None = None,
        use_regex_fallback: bool = True,
    ):
        self._enabled = enabled
        self._use_regex_fallback = use_regex_fallback
        path = Path(spacy_model_path) if spacy_model_path else None
        if path and path.exists():
            logger.info("SpaCy sideload path present at %s — using pattern scan for now", path)
        self._analyzer = _build_pattern_analyzer() if enabled else None

    @property
    def name(self) -> str:
        return "privacy"

    def run(self, event: PipelineEvent) -> StageResult:
        if not self._enabled:
            return StageResult(
                stage=self.name,
                status=StageStatus.SKIPPED,
                message="Privacy scanning disabled in config",
                metadata={"pii_span_count": 0},
            )

        prompt_text = event.prompt_text.strip()
        if not prompt_text:
            return StageResult(
                stage=self.name,
                status=StageStatus.PASS,
                message="No prompt text provided — nothing to scan",
                metadata={"pii_span_count": 0},
            )

        if self._analyzer is not None:
            try:
                results = self._analyzer.analyze(text=prompt_text, language="en")
                count = len(results)
                entity_types = list({r.entity_type for r in results})
                if count > 0:
                    return StageResult(
                        stage=self.name,
                        status=StageStatus.WARN,
                        message=f"{count} PII span(s) detected ({', '.join(entity_types)})",
                        metadata={"pii_span_count": count, "entity_types": entity_types},
                    )
                return StageResult(
                    stage=self.name,
                    status=StageStatus.PASS,
                    message="No PII detected",
                    metadata={"pii_span_count": 0},
                )
            except Exception as exc:
                logger.warning("Presidio scan failed, falling back to regex: %s", exc)

        if self._use_regex_fallback:
            count, entity_types = _regex_pii_scan(prompt_text)
            if count > 0:
                return StageResult(
                    stage=self.name,
                    status=StageStatus.WARN,
                    message=f"{count} PII pattern(s) detected ({', '.join(entity_types)})",
                    metadata={"pii_span_count": count, "entity_types": entity_types},
                )
            return StageResult(
                stage=self.name,
                status=StageStatus.PASS,
                message="No PII patterns detected",
                metadata={"pii_span_count": 0},
            )

        return StageResult(
            stage=self.name,
            status=StageStatus.WARN,
            message="PII scanner unavailable",
            metadata={"pii_span_count": 0},
        )
