# soft-parse hook stdin (fail-open on bad JSON)
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_hook(name: str):
    path = Path(__file__).resolve().parents[2] / ".cursor" / "hooks" / name
    spec = importlib.util.spec_from_file_location(f"lv_hook_{name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_prompt_hook_parses_empty_bom_and_noise() -> None:
    mod = _load_hook("lakanvault_prompt.py")
    assert mod._parse_hook_payload("") == ({}, None)
    assert mod._parse_hook_payload("\ufeff") == ({}, None)
    data, err = mod._parse_hook_payload('  {"prompt":"hi"}  ')
    assert err is None and data == {"prompt": "hi"}
    data, err = mod._parse_hook_payload('noise {"prompt":"x"} trailing')
    assert err is None and data == {"prompt": "x"}
    data, err = mod._parse_hook_payload("not-json")
    assert data is None and err == "invalid_json"


def test_read_hook_parses_soft() -> None:
    mod = _load_hook("lakanvault_read.py")
    assert mod._parse_hook_payload("") == ({}, None)
    data, err = mod._parse_hook_payload("<<< {\"file_path\":\"a.py\"} >>>")
    assert err is None and data == {"file_path": "a.py"}
