from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "lakanvault"

FORBIDDEN_IMPORTS: tuple[tuple[str, str], ...] = (
    ("local_core", "cloud_intelligence"),
    ("cloud_intelligence", "local_core"),
    ("app", "local_core"),
    ("app", "cloud_intelligence"),
    ("orchestration", "cloud_intelligence"),
)


def _layer_modules(layer: str) -> list[Path]:
    base = SRC / layer
    if not base.exists():
        return []
    return sorted(base.rglob("*.py"))


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def _module_imports_layer(module_text: str, forbidden_layer: str) -> bool:
    needle = f"lakanvault.{forbidden_layer}"
    return needle in module_text or forbidden_layer in module_text


def verify() -> list[str]:
    errors: list[str] = []
    for source_layer, forbidden_layer in FORBIDDEN_IMPORTS:
        for path in _layer_modules(source_layer):
            text = path.read_text(encoding="utf-8")
            if _module_imports_layer(text, forbidden_layer):
                errors.append(
                    f"{path.relative_to(ROOT)} must not import {forbidden_layer}"
                )
    return errors


def main() -> int:
    errors = verify()
    if errors:
        for err in errors:
            print(f"BOUNDARY VIOLATION: {err}", file=sys.stderr)
        return 1
    print("Boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
