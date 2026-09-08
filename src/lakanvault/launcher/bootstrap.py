"""Shared bootstrap for LakanVault — bundled runtime, gateway server, tray."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

# Windows: hide console window for child daemon under a windowed parent.
_CREATE_NO_WINDOW = 0x08000000


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def seed_bundled_config(root: Path) -> None:
    """Copy read-only default.yaml from the freeze bundle into writable config/.

    PyInstaller packs ``config/`` under ``_MEIPASS``. The tray creates an empty
    ``exe/config/`` for local.yaml; without this seed, lifespan fails on missing
    default.yaml.
    """
    dest_dir = root / "config"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "default.yaml"
    if dest.is_file():
        return
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "config" / "default.yaml")
        candidates.append(Path(sys.executable).resolve().parent / "_internal" / "config" / "default.yaml")
    else:
        candidates.append(Path(__file__).resolve().parents[3] / "config" / "default.yaml")
    for src in candidates:
        if src.is_file():
            shutil.copy2(src, dest)
            return


def ensure_data_dirs(root: Path) -> None:
    (root / "data" / "models").mkdir(parents=True, exist_ok=True)
    (root / "data" / "audit").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)
    seed_bundled_config(root)


def daemon_log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "lakanvault-daemon.log"
    return Path("lakanvault-daemon.log")


def _append_log(msg: str) -> None:
    try:
        path = daemon_log_path()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(msg if msg.endswith("\n") else msg + "\n")
    except OSError:
        pass


def _ensure_stdio() -> None:
    """Windowed PyInstaller builds set stdout/stderr to None; uvicorn calls isatty()."""
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


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
    """Block forever serving the FastAPI app (call on the main thread when frozen)."""
    import asyncio
    import traceback

    try:
        _ensure_stdio()
        _append_log("starting gateway…")

        # Windowed frozen apps on Windows: ProactorEventLoop can fail to bind sockets.
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        import uvicorn

        from lakanvault.app.server import app

        _append_log("app imported; creating uvicorn server")
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            log_config=None,
            http="h11",
            lifespan="on",
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        # Windowed frozen processes hang/exit if uvicorn installs signal handlers.
        server.install_signal_handlers = False
        _append_log(f"binding uvicorn on {host}:{port}")
        asyncio.run(server.serve())
        _append_log(
            f"uvicorn stopped started={server.started} should_exit={server.should_exit}"
        )
    except Exception:
        _append_log(traceback.format_exc())
        raise


def start_gateway_thread(host: str, port: int) -> threading.Thread:
    thread = threading.Thread(target=run_gateway_server, args=(host, port), daemon=True)
    thread.start()
    return thread


def frozen_daemon_command(host: str, port: int) -> list[str]:
    """Child process argv for a frozen tray parent."""
    return [
        sys.executable,
        "--daemon-only",
        "--host",
        host,
        "--port",
        str(port),
        "--no-runtime",
    ]


def start_frozen_daemon_process(host: str, port: int) -> subprocess.Popen:
    """Spawn a sibling copy of this exe that runs uvicorn on its main thread."""
    env = os.environ.copy()
    # Keep frozen DLP on regex path — avoids optional spaCy pull at runtime.
    env.setdefault("LAKANVAULT_PRIVACY_ENGINE", "regex")
    root = Path(sys.executable).resolve().parent
    _append_log(f"spawning daemon child on {host}:{port}")
    return subprocess.Popen(
        frozen_daemon_command(host, port),
        cwd=str(root),
        env=env,
        creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        close_fds=True,
    )


def wait_for_url(url: str, attempts: int = 40, delay: float = 0.15) -> bool:
    for _ in range(attempts):
        time.sleep(delay)
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except OSError:
            continue
    return False


def wait_for_url_ready(url: str) -> bool:
    """Frozen onedir cold-starts can take longer than a normal import."""
    if getattr(sys, "frozen", False):
        return wait_for_url(url, attempts=120, delay=0.5)
    return wait_for_url(url)


def open_browser(url: str) -> None:
    webbrowser.open(url)


def run_daemon_only(*, host: str = "127.0.0.1", port: int = 8080) -> int:
    """Foreground API only — used by frozen child processes (no tray)."""
    root_dir = repo_root()
    os.chdir(root_dir)
    ensure_data_dirs(root_dir)
    run_gateway_server(host, port)
    return 0


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

    start_gateway_thread(host, port)
    wait_for_url_ready(url)

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
    """Show system tray; start gateway in-process (dev) or as child exe (frozen)."""
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

    child: subprocess.Popen | None = None
    if getattr(sys, "frozen", False):
        child = start_frozen_daemon_process(host, port)
    else:
        start_gateway_thread(host, port)

    ready = wait_for_url_ready(url)

    controller = TrayController(host=host, port=port)
    controller.set_status(TrayStatus.RUNNING if ready else TrayStatus.ERROR)

    def on_quit() -> None:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
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
    parser.add_argument(
        "--daemon-only",
        action="store_true",
        help="Foreground API only (used by frozen tray child process)",
    )
    args = parser.parse_args(argv)

    if args.daemon_only:
        return run_daemon_only(host=args.host, port=args.port)

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
