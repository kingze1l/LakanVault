"""Native file/folder picker for local Windows desktop use."""
from __future__ import annotations

from pathlib import Path

MODEL_EXTENSIONS = {".gguf", ".bin", ".safetensors", ".pt", ".onnx", ".pth"}


def pick_model_file(initial_dir: str | Path | None = None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askopenfilename(
            title="Select model file",
            initialdir=str(initial_dir or Path.cwd()),
            filetypes=[
                ("Model files", "*.gguf *.bin *.safetensors *.pt *.pth *.onnx"),
                ("All files", "*.*"),
            ],
        )
    finally:
        root.destroy()
    return path or None


def pick_models_folder(initial_dir: str | Path | None = None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askdirectory(
            title="Select models folder",
            initialdir=str(initial_dir or Path.cwd()),
        )
    finally:
        root.destroy()
    return path or None


def list_model_files(directory: str | Path, max_depth: int = 2) -> list[dict]:
    root = Path(directory)
    if not root.exists():
        return []

    found: list[dict] = []

    def walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for entry in entries:
            if entry.is_file() and entry.suffix.lower() in MODEL_EXTENSIONS:
                stat = entry.stat()
                found.append({
                    "path": str(entry.resolve()),
                    "name": entry.name,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                })
            elif entry.is_dir() and depth < max_depth:
                walk(entry, depth + 1)

    walk(root, 0)
    return sorted(found, key=lambda item: item["name"].lower())
