from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppSection(BaseModel):
    name: str = "LakanVault"
    log_level: str = "INFO"


class CloudSection(BaseModel):
    enabled: bool = False
    analytics_endpoint: str | None = None
    enrichment_endpoint: str | None = None


class LocalSection(BaseModel):
    chunk_size_bytes: int = 1_048_576
    models_dir: str = "./data/models"
    manifest_db: str = "./data/manifest.db"
    audit_dir: str = "./data/audit"


class PipelineSection(BaseModel):
    order: list[str] = Field(
        default_factory=lambda: ["integrity", "threat_scanner", "privacy", "audit"]
    )


class PrivacySection(BaseModel):
    enabled: bool = True


class AppConfig(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    cloud: CloudSection = Field(default_factory=CloudSection)
    local: LocalSection = Field(default_factory=LocalSection)
    pipeline: PipelineSection = Field(default_factory=PipelineSection)
    privacy: PrivacySection = Field(default_factory=PrivacySection)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def load_config(config_dir: Path | str = "config") -> AppConfig:
    root = Path(config_dir)
    data: dict[str, Any] = {}
    for name in ("default.yaml", "local.yaml"):
        data = _deep_merge(data, load_yaml(root / name))
    cloud_path = root / "cloud.yaml"
    if cloud_path.exists():
        data = _deep_merge(data, load_yaml(cloud_path))
    return AppConfig.model_validate(data)
