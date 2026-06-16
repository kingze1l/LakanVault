"""Model registry — tracks trusted baseline hashes for local models.

Per ADR-003: baselines come out-of-band (USB / tutor JSON), never from cloud.
A model whose live hash doesn't match its recorded baseline is flagged
POISONED and can be quarantined (moved to data/quarantine/, removed from
the active models directory).
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1_048_576  # 1 MB, matches config/default.yaml


@dataclass
class ModelEntry:
    name: str
    path: str
    size_bytes: int
    current_hash: str
    baseline_hash: str | None
    status: str  # "TRUSTED" | "POISONED" | "UNVERIFIED" | "QUARANTINED"


def _sha256_file(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha.update(chunk)
    return sha.hexdigest()


class ModelRegistry:
    """
    baselines.json format:
        { "model-file-name.gguf": "sha256-hex..." }

    Lives at <models_dir>/baselines.json — loaded out-of-band by the user.
    """

    def __init__(self, models_dir: str | Path, quarantine_dir: str | Path | None = None):
        self.models_dir = Path(models_dir)
        self.quarantine_dir = Path(quarantine_dir) if quarantine_dir else self.models_dir / "_quarantine"
        self.baselines_path = self.models_dir / "baselines.json"

    def _load_baselines(self) -> dict[str, str]:
        if self.baselines_path.exists():
            try:
                return json.loads(self.baselines_path.read_text())
            except Exception as exc:
                logger.warning("Failed to read baselines.json: %s", exc)
        return {}

    def scan(self) -> list[ModelEntry]:
        """Hash every model file and compare against baselines."""
        if not self.models_dir.exists():
            return []

        baselines = self._load_baselines()
        entries: list[ModelEntry] = []

        for f in sorted(self.models_dir.iterdir()):
            if not f.is_file():
                continue
            if f.name in ("baselines.json",):
                continue
            if f.suffix.lower() not in (".gguf", ".bin", ".safetensors", ".pt", ".onnx"):
                continue

            try:
                current_hash = _sha256_file(f)
            except OSError as exc:
                logger.warning("Could not hash %s: %s", f, exc)
                continue

            baseline = baselines.get(f.name)
            if baseline is None:
                status = "UNVERIFIED"
            elif baseline == current_hash:
                status = "TRUSTED"
            else:
                status = "POISONED"

            entries.append(ModelEntry(
                name=f.name,
                path=str(f),
                size_bytes=f.stat().st_size,
                current_hash=current_hash,
                baseline_hash=baseline,
                status=status,
            ))

        return entries

    def quarantine(self, model_name: str) -> bool:
        """Move a poisoned/unverified model out of the active models dir."""
        src = self.models_dir / model_name
        if not src.exists():
            return False

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = self.quarantine_dir / f"{ts}__{model_name}"
        shutil.move(str(src), str(dest))

        # Log the ejection — metadata only, no model bytes
        log_path = self.quarantine_dir / "ejection_log.jsonl"
        record = {
            "model": model_name,
            "quarantined_at": ts,
            "quarantined_to": str(dest.name),
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(record) + "\n")

        logger.warning("Model quarantined: %s -> %s", model_name, dest)
        return True

    def set_baseline(self, model_name: str, sha256_hex: str) -> None:
        """Record a trusted baseline hash (out-of-band trust, ADR-003)."""
        baselines = self._load_baselines()
        baselines[model_name] = sha256_hex
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.baselines_path.write_text(json.dumps(baselines, indent=2))
