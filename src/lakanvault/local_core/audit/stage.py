"""Audit stage — writes pipeline outcomes to disk.
Per data-classification.md: no raw prompts, no model bytes, no full paths.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from lakanvault.contracts.events import PipelineEvent, StageResult, StageStatus
from lakanvault.contracts.ports import AuditWriter, PipelineStage

logger = logging.getLogger(__name__)


class AuditStage(PipelineStage, AuditWriter):
    """
    Final stage. Writes a JSON audit record to audit_dir.
    Only stage outcomes and redacted metadata are stored.
    """

    def __init__(self, audit_dir: str | Path = "./data/audit"):
        self._audit_dir = Path(audit_dir)

    @property
    def name(self) -> str:
        return "audit"

    def run(self, event: PipelineEvent) -> StageResult:
        try:
            self.write(event)
            return StageResult(
                stage=self.name,
                status=StageStatus.PASS,
                message=f"Audit written for run {event.run_id}",
                metadata={"run_id": event.run_id},
            )
        except Exception as exc:
            return StageResult(
                stage=self.name,
                status=StageStatus.ERROR,
                message=f"Audit write failed: {exc}",
            )

    def write(self, event: PipelineEvent) -> None:
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "run_id": event.run_id,
            "overall_status": event.overall_status.value,
            "started_at": event.started_at.isoformat(),
            "written_at": datetime.now(timezone.utc).isoformat(),
            # Store file name only, never full path (privacy)
            "target_name": Path(event.target_path).name,
            "stages": [
                {
                    "stage": s.stage,
                    "status": s.status.value,
                    "message": s.message,
                    # Metadata is already sanitised by each stage
                    "metadata": {
                        k: v for k, v in s.metadata.items()
                        if k not in ("prompt_text", "raw_bytes", "full_path")
                    },
                }
                for s in event.stages
            ],
        }
        out = self._audit_dir / f"{event.run_id}.json"
        out.write_text(json.dumps(record, indent=2))
        logger.info("Audit record written: %s", out)
