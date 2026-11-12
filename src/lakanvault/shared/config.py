# shared yaml config merge (default + runtime env + local)
# local.yaml wins when the user saved settings
"""Shared config loader — merges default.yaml with optional local.yaml overrides."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml

from lakanvault.shared.paths import is_frozen, resource_path

# Set by the standalone launcher when a bundled llama.cpp runtime is started.
# Precedence: default.yaml < this runtime URL < local.yaml (explicit user save wins).
RUNTIME_BASE_URL_ENV = "LAKANVAULT_RUNTIME_BASE_URL"


# find a folder that actually has default.yaml (cwd, frozen bundle, or repo)
def resolve_config_dir(explicit: str | Path | None = None) -> Path:
    """Locate config/ for source + frozen MCP/tray (Cursor often cwd=demo-workspace)."""
    explicit_path = Path(explicit) if explicit is not None else None
    # Real/custom dirs (tests, --config-dir) win immediately.
    if explicit_path is not None:
        if (explicit_path / "default.yaml").is_file():
            return explicit_path.resolve()
        norm = str(explicit_path).replace("\\", "/").strip()
        if norm not in {"./config", "config"}:
            return explicit_path.resolve()

    # Default "./config" when missing (frozen MCP cwd is often demo-workspace).
    candidates: list[Path] = [Path.cwd() / "config"]
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                resource_path("config"),
                exe_dir / "_internal" / "config",
                exe_dir / "config",
                # MVP layout: mcp.exe under .../mcp/, tray under root
                exe_dir.parent / "_internal" / "config",
                exe_dir.parent / "config",
            ]
        )
    # src/lakanvault/shared/config.py → repo/config
    candidates.append(Path(__file__).resolve().parents[3] / "config")

    seen: set[str] = set()
    for cand in candidates:
        try:
            key = str(cand.resolve())
        except OSError:
            key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        if (cand / "default.yaml").is_file():
            return cand.resolve()

    return (Path.cwd() / "config").resolve()


# deep merge dicts override wins on leaves
def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# load default then maybe stamp runtime url then merge local.yaml
def load_config(config_dir: str | Path = "./config") -> dict[str, Any]:
    config_dir = resolve_config_dir(config_dir)
    default_path = config_dir / "default.yaml"
    local_path = config_dir / "local.yaml"

    with open(default_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    runtime_url = os.environ.get(RUNTIME_BASE_URL_ENV)
    if runtime_url:
        ai = config.setdefault("local_ai", {})
        ai["base_url"] = runtime_url
        ai["provider"] = "llama_cpp"

    if local_path.exists():
        with open(local_path) as f:
            local = yaml.safe_load(f) or {}
        config = _deep_merge(config, local)

    return config


# write partial into local.yaml n return full merged config
def save_local_config(config_dir: str | Path, partial: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge partial settings into config/local.yaml and return full merged config."""
    # writes stay next to resolved defaults when possible; fall back to explicit path
    resolved = resolve_config_dir(config_dir)
    config_dir = resolved if (resolved / "default.yaml").is_file() else Path(config_dir)
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


# drop top-level keys from local.yaml (reset to defaults)
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
