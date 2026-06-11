"""
Boundary checker — catches import violations per ADR-001.
Run after P1b: python scripts/verify_boundaries.py

Rules (from docs/architecture/001-hybrid-boundary.md):
  app          → must NOT import local_core or cloud_intelligence
  orchestration → must NOT import cloud_intelligence directly
  local_core   → must NOT import cloud_intelligence or app
  cloud_intelligence → must NOT import local_core or app
  contracts    → must NOT import local_core, cloud_intelligence, app, orchestration
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "lakanvault"

# (package, forbidden_imports)
RULES: list[tuple[str, list[str]]] = [
    ("app",               ["local_core", "cloud_intelligence"]),
    ("orchestration",     ["cloud_intelligence"]),
    ("local_core",        ["cloud_intelligence", "app"]),
    ("cloud_intelligence",["local_core", "app"]),
    ("contracts",         ["local_core", "cloud_intelligence", "app", "orchestration"]),
]


def get_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def check() -> int:
    violations = 0
    for package, forbidden in RULES:
        pkg_dir = SRC / package
        if not pkg_dir.exists():
            continue
        for py_file in pkg_dir.rglob("*.py"):
            imports = get_imports(py_file)
            for imp in imports:
                for bad in forbidden:
                    full_bad = f"lakanvault.{bad}"
                    if imp == full_bad or imp.startswith(full_bad + "."):
                        rel = py_file.relative_to(SRC.parent.parent)
                        print(f"VIOLATION: {rel} imports {imp!r} (forbidden for {package})")
                        violations += 1

    if violations == 0:
        print("OK: all boundary checks passed.")
    else:
        print(f"\n{violations} violation(s) found.")
    return violations


if __name__ == "__main__":
    sys.exit(check())
