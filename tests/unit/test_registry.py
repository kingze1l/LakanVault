"""Tests for model registry poisoned detection and quarantine."""
from pathlib import Path

from lakanvault.local_core.integrity.registry import ModelRegistry


def test_poisoned_when_baseline_mismatch(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    model = models_dir / "demo-poisoned.gguf"
    model.write_bytes(b"GGUF" + b"x" * 100)

    registry = ModelRegistry(models_dir)
    entries = registry.scan()
    assert len(entries) == 1
    assert entries[0].status == "UNVERIFIED"

    registry.set_baseline("demo-poisoned.gguf", "0" * 64)
    entries = registry.scan()
    assert entries[0].status == "POISONED"


def test_quarantine_moves_file(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    model = models_dir / "bad.gguf"
    model.write_bytes(b"GGUF")

    registry = ModelRegistry(models_dir)
    assert registry.quarantine("bad.gguf") is True
    assert not model.exists()
    assert list(registry.quarantine_dir.glob("*bad.gguf"))
