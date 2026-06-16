"""Privacy stage — PII detection and masking using pattern-only Presidio + regex.
Per ADR-002: runs AFTER threat scanner, so threat never sees PII text.
No spaCy runtime downloads — air-gapped safe.
"""
from __future__ import annotations

import logging

from lakanvault.contracts.events import PipelineEvent, StageResult, StageStatus
from lakanvault.contracts.ports import PipelineStage
from lakanvault.local_core.privacy.detectors import find_pii_spans

logger = logging.getLogger(__name__)


class PrivacyStage(PipelineStage):
    """
    Scans prompt_text for PII using pattern recognizers + regex fallback.
    Only stores the span *count* in metadata — never the text.
    """

    @property
    def name(self) -> str:
        return "privacy"

    def run(self, event: PipelineEvent) -> StageResult:
        prompt_text = event.prompt_text or ""

        if not prompt_text:
            return StageResult(
                stage=self.name,
                status=StageStatus.PASS,
                message="No prompt text provided — nothing to scan",
                metadata={"pii_span_count": 0},
            )

        try:
            spans, engine = find_pii_spans(prompt_text)
            count = len(spans)
            entity_types = sorted({s.entity_type for s in spans})

            if count > 0:
                return StageResult(
                    stage=self.name,
                    status=StageStatus.WARN,
                    message=(
                        f"{count} PII span(s) detected ({', '.join(entity_types)}) "
                        f"via {engine}"
                    ),
                    metadata={
                        "pii_span_count": count,
                        "entity_types": entity_types,
                        "engine": engine,
                    },
                )

            return StageResult(
                stage=self.name,
                status=StageStatus.PASS,
                message=f"No PII detected (engine: {engine})",
                metadata={"pii_span_count": 0, "engine": engine},
            )

        except (Exception, SystemExit) as exc:
            return StageResult(
                stage=self.name,
                status=StageStatus.ERROR,
                message=f"Privacy scan error: {exc}",
                metadata={"pii_span_count": 0},
            )
