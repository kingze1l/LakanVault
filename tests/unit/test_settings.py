"""Tests for settings save/load."""
from pathlib import Path

from lakanvault.shared.config import clear_local_config_keys, load_config, save_local_config


def test_save_local_config_roundtrip(tmp_path: Path) -> None:
    default = tmp_path / "default.yaml"
    default.write_text(
        "local_ai:\n  base_url: http://localhost:1234\n  model: ''\n"
        "local:\n  models_dir: ./data/models\n",
        encoding="utf-8",
    )
    save_local_config(tmp_path, {"local_ai": {"base_url": "http://127.0.0.1:11434", "provider": "ollama"}})
    cfg = load_config(tmp_path)
    assert cfg["local_ai"]["base_url"] == "http://127.0.0.1:11434"
    assert cfg["local_ai"]["provider"] == "ollama"


def test_clear_local_config_keys(tmp_path: Path) -> None:
    default = tmp_path / "default.yaml"
    default.write_text("local_ai:\n  base_url: http://localhost:1234\n", encoding="utf-8")
    save_local_config(tmp_path, {"local_ai": {"model": "test-model"}})
    clear_local_config_keys(tmp_path, ["local_ai"])
    cfg = load_config(tmp_path)
    assert cfg["local_ai"]["base_url"] == "http://localhost:1234"
    assert cfg["local_ai"].get("model") is None
