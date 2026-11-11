# boundary checker http/mcp must not import core/vault impls
from pathlib import Path
import importlib.util

# scripts/verify_boundaries should exit 0
def test_verify_boundaries_passes() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "verify_boundaries.py"
    spec = importlib.util.spec_from_file_location("verify_boundaries", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.check() == 0
