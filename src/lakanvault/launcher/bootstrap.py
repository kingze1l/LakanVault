"""Shared bootstrap for LakanVault — bundled runtime, gateway server, browser."""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def ensure_data_dirs(root: Path) -> None:
    (root / "data" / "models").mkdir(parents=True, exist_ok=True)
    (root / "data" / "audit").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)


def start_bundled_runtime(root_dir: Path):
    """Auto-start llama.cpp sidecar when runtime/ ships with the build."""
    try:
        from lakanvault.local_core.runtime import LlamaRuntime, set_runtime
        from lakanvault.shared.config import RUNTIME_BASE_URL_ENV, load_config
    except Exception:
        return None
    try:
        config = load_config(root_dir / "config")
    except Exception:
        config = {}
    runtime = LlamaRuntime(root_dir, config)
    set_runtime(runtime)
    if not runtime.available():
        return None
    if runtime.start() and runtime.wait_until_ready():
        os.environ[RUNTIME_BASE_URL_ENV] = runtime.base_url
        return runtime
    return None


def run_gateway_server(host: str, port: int) -> None:
    import uvicorn

    from lakanvault.app.server import app

    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_gateway_server(host: str, port: int) -> threading.Thread:
    thread = threading.Thread(target=run_gateway_server, args=(host, port), daemon=True)
    thread.start()
    return thread


def wait_for_url(url: str, attempts: int = 40, delay: float = 0.15) -> bool:
    for _ in range(attempts):
        time.sleep(delay)
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except OSError:
            continue
    return False


def open_browser(url: str) -> None:
    webbrowser.open(url)


def run_daemon(
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser_flag: bool = False,
    start_runtime: bool = True,
) -> int:
    """Start optional bundled runtime + gateway API; block until Ctrl+C."""
    root_dir = repo_root()
    os.chdir(root_dir)
    src = root_dir / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    ensure_data_dirs(root_dir)

    runtime = start_bundled_runtime(root_dir) if start_runtime else None
    url = f"http://{host}:{port}"

    start_gateway_server(host, port)
    wait_for_url(url)

    if runtime is not None:
        print(f"  Bundled model server: {runtime.base_url} ({runtime.active_model})")
        print("  Chat: ready (offline bundled model)")
    else:
        print("  Chat: connect LM Studio or Ollama via /api/settings (local_ai.base_url).")

    print(f"\n  LakanVault API at {url}\n  Press Ctrl+C to stop.\n")
    if open_browser_flag:
        open_browser(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        if runtime is not None:
            runtime.stop()
    return 0


def run_tray_daemon(
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    start_runtime: bool = True,
) -> int:
    """Start gateway in a background thread and show the system tray icon."""
    from lakanvault.tray.app import run_tray_loop
    from lakanvault.tray.state import TrayController, TrayStatus

    root_dir = repo_root()
    os.chdir(root_dir)
    src = root_dir / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    ensure_data_dirs(root_dir)
    runtime = start_bundled_runtime(root_dir) if start_runtime else None
    url = f"http://{host}:{port}"
    start_gateway_server(host, port)
    ready = wait_for_url(url)

    controller = TrayController(host=host, port=port)
    controller.set_status(TrayStatus.RUNNING if ready else TrayStatus.ERROR)

    def on_quit() -> None:
        if runtime is not None:
            runtime.stop()

    run_tray_loop(controller, on_quit=on_quit)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start LakanVault gateway daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--browser", action="store_true", help="Open API root URL in browser")
    parser.add_argument("--no-runtime", action="store_true", help="Skip bundled llama.cpp startup")
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Show system tray icon (default when frozen as .exe)",
    )
    args = parser.parse_args(argv)
    use_tray = args.tray or getattr(sys, "frozen", False)
    if use_tray:
        return run_tray_daemon(
            host=args.host,
            port=args.port,
            start_runtime=not args.no_runtime,
        )
    return run_daemon(
        host=args.host,
        port=args.port,
        open_browser_flag=args.browser,
        start_runtime=not args.no_runtime,
    )


if __name__ == "__main__":
    raise SystemExit(main())
