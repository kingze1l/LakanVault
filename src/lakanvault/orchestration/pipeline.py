"""Pipeline runner — wires stages together, enforces fail-closed order.
Stage order comes from config, not hard-coded here (ADR-002).
"""
from __future__ import annotations

import logging
import uuid
from time import monotonic

from lakanvault.contracts.dtos import ScanRequest, ScanResponse
from lakanvault.contracts.events import PipelineEvent, StageStatus
from lakanvault.contracts.ports import PipelineStage

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Runs stages in the order provided.
    Stops immediately on FAIL or ERROR (fail-closed).
    Cloud forward is handled by the bus, not here.
    """

    def __init__(self, stages: list[PipelineStage]):
        self._stages = stages

    def run(self, request: ScanRequest) -> tuple[PipelineEvent, float]:
        run_id = str(uuid.uuid4())[:8]
        event = PipelineEvent(
            run_id=run_id,
            target_path=request.target_path,
            prompt_text=request.prompt_text,
        )
        start = monotonic()

        for stage in self._stages:
            if not event.should_continue():
                logger.warning(
                    "Pipeline halted before %s — fail-closed (run_id=%s)",
                    stage.name, run_id,
                )
                break

            logger.info("Running stage: %s (run_id=%s)", stage.name, run_id)
            try:
                result = stage.run(event)
            except Exception as exc:
                from lakanvault.contracts.events import StageResult
                result = StageResult(
                    stage=stage.name,
                    status=StageStatus.ERROR,
                    message=f"Unhandled exception: {exc}",
                )

            event.add_stage(result)
            logger.info(
                "Stage %s → %s: %s", stage.name, result.status.value, result.message
            )

        duration_ms = (monotonic() - start) * 1000
        return event, duration_ms
