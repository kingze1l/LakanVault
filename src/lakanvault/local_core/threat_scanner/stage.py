"""Threat scanner — checks host and env for misconfigurations.
Per ADR-002: does NOT see raw prompts; runs before privacy stage.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from lakanvault.contracts.events import PipelineEvent, StageResult, StageStatus
from lakanvault.contracts.ports import PipelineStage


_RISKY_ENV_VARS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "HUGGINGFACE_TOKEN",
]


class ThreatScannerStage(PipelineStage):
    """
    Checks for env misconfigurations: leaked API keys in env,
    world-writable model directories, running as root.
    Does NOT read prompt text — that's the privacy stage's job.
    """

    @property
    def name(self) -> str:
        return "threat_scanner"

    def run(self, event: PipelineEvent) -> StageResult:
        warnings: list[str] = []

        # Check for leaked secrets in environment
        leaked = [k for k in _RISKY_ENV_VARS if os.environ.get(k)]
        if leaked:
            warnings.append(f"API keys in environment: {', '.join(leaked)}")

        # Check if running as root (Linux/Mac)
        if hasattr(os, "getuid") and os.getuid() == 0:
            warnings.append("Running as root — not recommended for inference workloads")

        # Check model directory permissions
        model_dir = Path(event.target_path).parent
        if model_dir.exists():
            stat = model_dir.stat()
            # World-writable directory
            if stat.st_mode & 0o002:
                warnings.append(f"Model directory is world-writable: {model_dir}")

        if warnings:
            return StageResult(
                stage=self.name,
                status=StageStatus.WARN,
                message="; ".join(warnings),
                metadata={"finding_count": len(warnings)},
                # NOTE: we only log finding_type + severity to cloud, never hostnames/ports
            )

        return StageResult(
            stage=self.name,
            status=StageStatus.PASS,
            message="No host misconfiguration detected",
            metadata={"finding_count": 0},
        )
