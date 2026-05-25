from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IntegrityVerified(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    sha256: str = Field(min_length=64, max_length=64)
    verified: bool
    timestamp: datetime


class ThreatFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    severity: str
    finding_type: str
    timestamp: datetime


class PIIMasked(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    entity_count: int = Field(ge=0)
    timestamp: datetime


class AuditRecorded(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    stage: str
    timestamp: datetime
