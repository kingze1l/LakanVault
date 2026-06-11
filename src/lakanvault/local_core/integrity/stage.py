"""Integrity stage — SHA-256 chunked hashing of model files."""
from __future__ import annotations

import hashlib
from pathlib import Path

from lakanvault.contracts.events import PipelineEvent, StageResult, StageStatus
from lakanvault.contracts.ports import PipelineStage


class IntegrityStage(PipelineStage):
    """
    Hashes target file in configurable chunks (default 1 MB).
    Compares against a trusted baseline if one is provided.
    Per ADR-003: baseline comes out-of-band, never from cloud.
    """

    def __init__(self, chunk_size: int = 1_048_576, baseline_hash: str | None = None):
        self._chunk_size = chunk_size
        self._baseline_hash = baseline_hash

    @property
    def name(self) -> str:
        return "integrity"

    def run(self, event: PipelineEvent) -> StageResult:
        path = Path(event.target_path)

        if not path.exists():
            return StageResult(
                stage=self.name,
                status=StageStatus.FAIL,
                message=f"Path not found: {path}",
            )

        try:
            sha = hashlib.sha256()
            bytes_processed = 0
            with open(path, "rb") as f:
                while chunk := f.read(self._chunk_size):
                    sha.update(chunk)
                    bytes_processed += len(chunk)

            digest = sha.hexdigest()
            short = f"{digest[:8]}…{digest[-4:]}"

            if self._baseline_hash and digest != self._baseline_hash:
                return StageResult(
                    stage=self.name,
                    status=StageStatus.FAIL,
                    message=f"Hash mismatch. Got {short}, expected baseline.",
                    metadata={"hash": digest, "bytes_processed": bytes_processed},
                )

            return StageResult(
                stage=self.name,
                status=StageStatus.PASS,
                message=f"SHA-256 verified: {short}",
                metadata={
                    "hash": digest,
                    "hash_short": short,
                    "bytes_processed": bytes_processed,
                    "baseline_checked": self._baseline_hash is not None,
                },
            )

        except OSError as exc:
            return StageResult(
                stage=self.name,
                status=StageStatus.ERROR,
                message=f"IO error during hash: {exc}",
            )
