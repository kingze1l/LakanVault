"""Gateway — pure Python entry point for all pipeline runs."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lakanvault.contracts.dtos import ScanRequest, ScanResponse
from lakanvault.local_core.audit.stage import AuditStage
from lakanvault.local_core.integrity.stage import IntegrityStage
from lakanvault.local_core.privacy.stage import PrivacyStage
from lakanvault.local_core.threat_scanner.stage import ThreatScannerStage
from lakanvault.orchestration.bus import EventBus
from lakanvault.orchestration.pipeline import Pipeline
from lakanvault.shared.config import load_config

logger = logging.getLogger(__name__)


class Gateway:
    def __init__(self, config_dir: str | Path = "./config"):
        self._cfg = load_config(config_dir)
        self._pipeline = self._build_pipeline()
        self._bus = self._build_bus()

    def get_config_snapshot(self) -> dict[str, Any]:
        return self._cfg

    def _build_pipeline(self) -> Pipeline:
        local = self._cfg.get("local", {})
        privacy = self._cfg.get("privacy", {})
        chunk_size = local.get("chunk_size_bytes", 1_048_576)
        audit_dir = local.get("audit_dir", "./data/audit")

        stage_map = {
            "integrity": IntegrityStage(chunk_size=chunk_size),
            "threat_scanner": ThreatScannerStage(),
            "privacy": PrivacyStage(
                enabled=privacy.get("enabled", True),
                spacy_model_path=privacy.get("spacy_model_path"),
            ),
            "audit": AuditStage(audit_dir=audit_dir),
        }
        order = self._cfg.get("pipeline", {}).get(
            "order", ["integrity", "threat_scanner", "privacy", "audit"]
        )
        stages = [stage_map[name] for name in order if name in stage_map]
        return Pipeline(stages)

    def _build_bus(self) -> EventBus:
        cloud = self._cfg.get("cloud", {})
        return EventBus(
            cloud_enabled=cloud.get("enabled", False),
            analytics_endpoint=cloud.get("analytics_endpoint", ""),
        )

    def receive(self, request: ScanRequest) -> ScanResponse:
        logger.info("Gateway received scan request: %s", request.target_path)

        event, duration_ms = self._pipeline.run(request)
        cloud_forwarded = self._bus.publish(event, duration_ms)

        stages_out = [
            {"stage": s.stage, "status": s.status.value, "message": s.message}
            for s in event.stages
        ]

        hash_short = ""
        pii_count = 0
        for s in event.stages:
            if s.stage == "integrity":
                hash_short = s.metadata.get("hash_short", "")
            if s.stage == "privacy":
                pii_count = s.metadata.get("pii_span_count", 0)

        return ScanResponse(
            run_id=event.run_id,
            overall_status=event.overall_status.value,
            stages=stages_out,
            hash_summary=hash_short,
            pii_span_count=pii_count,
            cloud_forwarded=cloud_forwarded,
        )
