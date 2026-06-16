"""Shared config loader — merges default.yaml with optional local.yaml overrides."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_dir: str | Path = "./config") -> dict[str, Any]:
    config_dir = Path(config_dir)
    default_path = config_dir / "default.yaml"
    local_path = config_dir / "local.yaml"

    with open(default_path) as f:
        config = yaml.safe_load(f)

    if local_path.exists():
        with open(local_path) as f:
            local = yaml.safe_load(f) or {}
        config = _deep_merge(config, local)

    return config


def save_local_config(config_dir: str | Path, partial: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge partial settings into config/local.yaml and return full merged config."""
    config_dir = Path(config_dir)
    local_path = config_dir / "local.yaml"
    existing: dict[str, Any] = {}
    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    merged_local = _deep_merge(existing, partial)
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged_local, f, default_flow_style=False, sort_keys=False)
    return load_config(config_dir)


def clear_local_config_keys(config_dir: str | Path, keys: list[str]) -> dict[str, Any]:
    """Remove top-level keys from local.yaml (reset to defaults)."""
    config_dir = Path(config_dir)
    local_path = config_dir / "local.yaml"
    if not local_path.exists():
        return load_config(config_dir)
    with open(local_path, encoding="utf-8") as f:
        existing = yaml.safe_load(f) or {}
    for key in keys:
        existing.pop(key, None)
    if existing:
        with open(local_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(existing, f, default_flow_style=False, sort_keys=False)
    else:
        local_path.unlink(missing_ok=True)
    return load_config(config_dir)
