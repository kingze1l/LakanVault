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
