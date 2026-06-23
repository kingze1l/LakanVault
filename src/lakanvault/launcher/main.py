"""LakanVault standalone launcher — splash screen, gateway server, open browser."""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    _root = Path(sys.executable).resolve().parent
else:
    _root = Path(__file__).resolve().parents[3]
    if str(_root / "src") not in sys.path:
        sys.path.insert(0, str(_root / "src"))

os.chdir(_root)

from lakanvault.launcher.bootstrap import (
    ensure_data_dirs,
    repo_root,
    run_gateway_server,
    start_bundled_runtime,
    wait_for_url,
)


def _show_splash(logo_path: Path) -> object | None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        return None

    root = tk.Tk()
    root.title("LakanVault")
    root.configure(bg="#0B0E14")
    root.overrideredirect(True)
    w, h = 360, 320
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    frame = tk.Frame(root, bg="#0B0E14", padx=24, pady=24)
    frame.pack(fill="both", expand=True)

    if logo_path.is_file():
        try:
            img = tk.PhotoImage(file=str(logo_path))
            max_side = 120
            if img.width() > max_side or img.height() > max_side:
                scale = max(img.width(), img.height()) // max_side
                if scale > 1:
                    img = img.subsample(scale, scale)
            lbl = tk.Label(frame, image=img, bg="#0B0E14")
            lbl.image = img
            lbl.pack(pady=(8, 12))
        except tk.TclError:
            pass

    tk.Label(
        frame,
        text="LakanVault",
        fg="#E8EAED",
        bg="#0B0E14",
        font=("Segoe UI", 18, "bold"),
    ).pack()
    tk.Label(
        frame,
        text="Security Gateway",
        fg="#5A9E6F",
        bg="#0B0E14",
        font=("Segoe UI", 10),
    ).pack(pady=(4, 16))
    tk.Label(
        frame,
        text="Starting local gateway…",
        fg="#8B92A5",
        bg="#0B0E14",
        font=("Consolas", 9),
    ).pack()
    ttk.Progressbar(frame, mode="indeterminate", length=240).pack(pady=16)
    for child in frame.winfo_children():
        if isinstance(child, ttk.Progressbar):
            child.start(10)
            break

    root.update()
    return root


def main() -> None:
    root_dir = repo_root()
    if str(root_dir / "src") not in sys.path:
        sys.path.insert(0, str(root_dir / "src"))

    ensure_data_dirs(root_dir)

    logo = root_dir / "src" / "lakanvault" / "app" / "static" / "logo.png"
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", root_dir)) / "lakanvault" / "app" / "static" / "logo.png"
        if bundled.is_file():
            logo = bundled

    splash = _show_splash(logo)
    host, port = "127.0.0.1", 8080
    runtime = start_bundled_runtime(root_dir)
    url = f"http://{host}:{port}"

    threading.Thread(target=run_gateway_server, args=(host, port), daemon=True).start()
    wait_for_url(url)

    if splash is not None:
        try:
            splash.destroy()
        except Exception:
            pass

    if runtime is not None:
        print(f"  Bundled model server: {runtime.base_url} ({runtime.active_model})")
    print(f"\n  LakanVault running at {url}\n  Press Ctrl+C to stop.\n")
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        if runtime is not None:
            runtime.stop()


if __name__ == "__main__":
    main()
