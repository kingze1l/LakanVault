"""Domain events — immutable records of what happened in the pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class StageResult(BaseModel):
    stage: str
    status: StageStatus
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineEvent(BaseModel):
    run_id: str
    target_path: str
    prompt_text: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stages: list[StageResult] = Field(default_factory=list)
    overall_status: StageStatus = StageStatus.PASS

    def add_stage(self, result: StageResult) -> None:
        self.stages.append(result)
        if result.status in (StageStatus.FAIL, StageStatus.ERROR):
            self.overall_status = StageStatus.FAIL
        elif result.status == StageStatus.WARN and self.overall_status == StageStatus.PASS:
            self.overall_status = StageStatus.WARN

    def should_continue(self) -> bool:
        return self.overall_status not in (StageStatus.FAIL, StageStatus.ERROR)
