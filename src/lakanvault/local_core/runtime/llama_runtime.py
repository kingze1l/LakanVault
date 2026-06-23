"""Manage an optional bundled llama.cpp server (sidecar) for zero-setup demos."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_CREATE_NO_WINDOW = 0x08000000


class LlamaRuntime:
    def __init__(self, base_dir: Path, config: dict[str, Any] | None = None) -> None:
        self.base_dir = Path(base_dir)
        rt = (config or {}).get("local_runtime", {}) if isinstance(config, dict) else {}
        self.enabled: bool = bool(rt.get("enabled", True))
        self.host: str = rt.get("host", "127.0.0.1")
        self.port: int = int(rt.get("port", 8081))
        self.server_exe: Path = self._resolve(rt.get("server_exe", "runtime/llama-server.exe"))
        self.models_dir: Path = self._resolve(rt.get("models_dir", "runtime/models"))
        self.model: str = rt.get("model", "") or ""
        self.context_size: int = int(rt.get("context_size", 2048))
        self.threads: int = int(rt.get("threads", 0))
        self.extra_args: list[str] = list(rt.get("extra_args", []) or [])
        self._proc: subprocess.Popen | None = None
        self._active_model: str = ""

    def _resolve(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else self.base_dir / p

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def active_model(self) -> str:
        return self._active_model

    def list_models(self) -> list[str]:
        if not self.models_dir.is_dir():
            return []
        return sorted(p.name for p in self.models_dir.glob("*.gguf"))

    def _resolve_model(self, name: str | None = None) -> Path | None:
        wanted = name or self.model
        if wanted:
            p = self.models_dir / wanted
            if p.is_file():
                return p
        models = self.list_models()
        return (self.models_dir / models[0]) if models else None

    def available(self) -> bool:
        return self.enabled and self.server_exe.is_file() and self._resolve_model() is not None

    def _port_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            return s.connect_ex((self.host, self.port)) == 0

    def is_running(self) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return True
        return self._port_open()

    def start(self, model: str | None = None) -> bool:
        if not self.available():
            return False
        model_path = self._resolve_model(model)
        if model_path is None:
            return False
        if self._port_open() and self._proc is None:
            self._active_model = model_path.name
            return True
        args = [
            str(self.server_exe),
            "-m", str(model_path),
            "--host", self.host,
            "--port", str(self.port),
            "-c", str(self.context_size),
        ]
        if self.threads > 0:
            args += ["-t", str(self.threads)]
        args += self.extra_args
        creationflags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        self._active_model = model_path.name
        return True

    def wait_until_ready(self, timeout: float = 90.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._port_open():
                return True
            if self._proc is not None and self._proc.poll() is not None:
                return False
            time.sleep(0.5)
        return False

    def restart(self, model: str) -> bool:
        self.stop()
        if self.start(model):
            return self.wait_until_ready()
        return False

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available(),
            "running": self.is_running(),
            "base_url": self.base_url,
            "models": self.list_models(),
            "active_model": self._active_model,
            "models_dir": str(self.models_dir),
        }


_RUNTIME: "LlamaRuntime | None" = None


def set_runtime(runtime: LlamaRuntime | None) -> None:
    global _RUNTIME
    _RUNTIME = runtime


def get_runtime() -> LlamaRuntime | None:
    return _RUNTIME
