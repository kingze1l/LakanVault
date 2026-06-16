"""Gateway — pure Python entry point for all pipeline runs.
Zero Streamlit imports. Can be wrapped as a background .exe in Phase 2 (ADR-004).
UI calls Gateway.receive(); gateway calls Pipeline; gateway returns ScanResponse.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from time import monotonic

from lakanvault.contracts.dtos import ScanRequest, ScanResponse
from lakanvault.local_core.adapters.local_llm_client import LocalLLMClient
from lakanvault.local_core.audit.stage import AuditStage
from lakanvault.local_core.integrity.registry import ModelRegistry
from lakanvault.local_core.integrity.stage import IntegrityStage
from lakanvault.local_core.privacy.anonymizer import ReversibleAnonymizer
from lakanvault.local_core.privacy.stage import PrivacyStage
from lakanvault.local_core.threat_scanner.stage import ThreatScannerStage
from lakanvault.orchestration.bus import EventBus
from lakanvault.orchestration.pipeline import Pipeline
from lakanvault.shared.config import load_config
from lakanvault.shared.url_policy import assert_localhost_url

logger = logging.getLogger(__name__)


class Gateway:
    """
    Wires config → stages → pipeline → bus.
    Returns plain DTOs. Knows nothing about Streamlit or any UI.
    """

    def __init__(self, config_dir: str | Path = "./config"):
        self._config_dir = Path(config_dir)
        self._cfg = load_config(config_dir)
        self._pipeline = self._build_pipeline()
        self._bus = self._build_bus()
        self._anonymizer = ReversibleAnonymizer()
        self._local_llm = self._build_local_llm()
        local = self._cfg.get("local", {})
        models_dir = self._resolve_path(local.get("models_dir", "./data/models"), self._config_dir)
        self._registry = ModelRegistry(models_dir=models_dir)

    def _build_local_llm(self) -> LocalLLMClient:
        ai = self._cfg.get("local_ai", {})
        return LocalLLMClient(
            base_url=ai.get("base_url", "http://localhost:1234"),
            model=ai.get("model", ""),
            timeout_seconds=float(ai.get("timeout_seconds", 120)),
            temperature=float(ai.get("temperature", 0.7)),
            max_tokens=int(ai.get("max_tokens", 256)),
            stream=bool(ai.get("stream", True)),
        )

    def get_config_snapshot(self) -> dict[str, object]:
        return self._cfg

    def get_settings(self) -> dict:
        ai = self._cfg.get("local_ai", {})
        local = self._cfg.get("local", {})
        cloud = self._cfg.get("cloud", {})
        privacy = self._cfg.get("privacy", {})
        return {
            "local_ai": {
                "base_url": ai.get("base_url", "http://localhost:1234"),
                "model": ai.get("model", ""),
                "provider": ai.get("provider", "lm_studio"),
                "timeout_seconds": ai.get("timeout_seconds", 120),
                "temperature": ai.get("temperature", 0.7),
                "max_tokens": ai.get("max_tokens", 256),
                "stream": ai.get("stream", True),
                "presets": ai.get("presets", {}),
            },
            "local": {
                "models_dir": local.get("models_dir", "./data/models"),
                "audit_dir": local.get("audit_dir", "./data/audit"),
                "chunk_size_bytes": local.get("chunk_size_bytes", 1_048_576),
            },
            "privacy": {"enabled": privacy.get("enabled", True)},
            "cloud": {"enabled": cloud.get("enabled", False)},
        }

    def apply_settings(self, partial: dict) -> None:
        self._cfg = load_config(self._config_dir)
        if "local_ai" in partial:
            ai = partial["local_ai"]
            if "base_url" in ai:
                assert_localhost_url(ai["base_url"])
            self._local_llm.configure(
                base_url=ai.get("base_url"),
                model=ai.get("model"),
                timeout_seconds=ai.get("timeout_seconds"),
                temperature=ai.get("temperature"),
                max_tokens=ai.get("max_tokens"),
                stream=ai.get("stream"),
            )
        if "local" in partial:
            local = partial["local"]
            if "models_dir" in local:
                models_dir = self._resolve_path(local["models_dir"], self._config_dir)
                self._registry = ModelRegistry(models_dir=models_dir)
            self._pipeline = self._build_pipeline()
        if "cloud" in partial:
            self._bus = self._build_bus()

    @staticmethod
    def _resolve_path(path: str | Path, anchor: Path) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        for base in (anchor.parent, anchor, Path.cwd()):
            candidate = (base / p).resolve()
            if candidate.exists() or base == anchor.parent:
                return candidate
        return (Path.cwd() / p).resolve()

    def _build_pipeline(self) -> Pipeline:
        local = self._cfg.get("local", {})
        chunk_size = local.get("chunk_size_bytes", 1_048_576)
        audit_dir = local.get("audit_dir", "./data/audit")

        stage_map = {
            "integrity": IntegrityStage(chunk_size=chunk_size),
            "threat_scanner": ThreatScannerStage(),
            "privacy": PrivacyStage(),
            "audit": AuditStage(audit_dir=audit_dir),
        }
        order = self._cfg.get("pipeline", {}).get(
            "order", ["integrity", "threat_scanner", "privacy", "audit"]
        )
        stages = [stage_map[name] for name in order if name in stage_map]
        return Pipeline(stages)

    def _build_bus(self) -> EventBus:
        cloud = self._cfg.get("cloud", {})
        return EventBus(
            cloud_enabled=cloud.get("enabled", False),
            analytics_endpoint=cloud.get("analytics_endpoint", ""),
        )

    def receive(self, request: ScanRequest) -> ScanResponse:
        logger.info("Gateway received scan request: %s", request.target_path)

        event, duration_ms = self._pipeline.run(request)
        self._bus.publish(event, duration_ms)

        stages_out = []
        for s in event.stages:
            stages_out.append({
                "stage": s.stage,
                "status": s.status.value,
                "message": s.message,
            })

        hash_short = ""
        pii_count = 0
        for s in event.stages:
            if s.stage == "integrity":
                hash_short = s.metadata.get("hash_short", "")
            if s.stage == "privacy":
                pii_count = s.metadata.get("pii_span_count", 0)

        return ScanResponse(
            run_id=event.run_id,
            overall_status=event.overall_status.value,
            stages=stages_out,
            hash_summary=hash_short,
            pii_span_count=pii_count,
            cloud_forwarded=self._cfg.get("cloud", {}).get("enabled", False),
        )

    def local_llm_status(self, base_url: str | None = None) -> dict:
        url = base_url or self._local_llm.base_url
        models = self._local_llm.list_models(base_url=url)
        return {
            "reachable": bool(models),
            "models": models,
            "base_url": url,
        }

    def lmstudio_models(self) -> list[str]:
        return self._local_llm.list_models()

    def lmstudio_reachable(self) -> bool:
        return bool(self._local_llm.list_models())

    def chat(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict:
        t0 = monotonic()
        sanitized, mapping = self._anonymizer.anonymize(prompt)
        sanitize_ms = round((monotonic() - t0) * 1000, 1)

        try:
            result = self._local_llm.chat(
                sanitized, model=model, base_url=base_url
            )
        except (ConnectionError, ValueError) as exc:
            return {
                "sanitized_prompt": sanitized,
                "mapping": mapping,
                "raw_response": "",
                "restored_response": "",
                "pii_span_count": len(mapping),
                "model_used": model or self._cfg.get("local_ai", {}).get("model", ""),
                "provider_url": base_url or self._local_llm.base_url,
                "latency_ms": 0.0,
                "sanitize_ms": sanitize_ms,
                "error": str(exc),
            }

        restored = ReversibleAnonymizer.restore(result.content, mapping)

        return {
            "sanitized_prompt": sanitized,
            "mapping": mapping,
            "raw_response": result.content,
            "restored_response": restored,
            "pii_span_count": len(mapping),
            "model_used": result.model_used,
            "provider_url": result.provider_url,
            "latency_ms": result.latency_ms,
            "sanitize_ms": sanitize_ms,
            "error": None,
        }

    def chat_stream_events(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
    ):
        """Yield SSE-friendly dict events: meta, token, done, error."""
        t0 = monotonic()
        sanitized, mapping = self._anonymizer.anonymize(prompt)
        sanitize_ms = round((monotonic() - t0) * 1000, 1)

        yield {
            "type": "meta",
            "sanitized_prompt": sanitized,
            "pii_span_count": len(mapping),
            "placeholders": sorted(mapping.keys()),
            "sanitize_ms": sanitize_ms,
        }

        try:
            parts: list[str] = []
            model_used = model or ""
            provider_url = base_url or self._local_llm.base_url
            llm_start = monotonic()

            for chunk in self._local_llm.chat_stream(
                sanitized, model=model, base_url=base_url
            ):
                if chunk.model_used:
                    model_used = chunk.model_used
                if chunk.provider_url:
                    provider_url = chunk.provider_url
                if chunk.delta:
                    parts.append(chunk.delta)
                    yield {"type": "token", "delta": chunk.delta}
                if chunk.done:
                    raw = chunk.full_content or "".join(parts)
                    restored = ReversibleAnonymizer.restore(raw, mapping)
                    llm_ms = round((monotonic() - llm_start) * 1000, 1)
                    yield {
                        "type": "done",
                        "raw_response": raw,
                        "restored_response": restored,
                        "model_used": model_used,
                        "provider_url": provider_url,
                        "latency_ms": llm_ms,
                        "sanitize_ms": sanitize_ms,
                    }
                    return

            raw = "".join(parts)
            restored = ReversibleAnonymizer.restore(raw, mapping)
            llm_ms = round((monotonic() - llm_start) * 1000, 1)
            yield {
                "type": "done",
                "raw_response": raw,
                "restored_response": restored,
                "model_used": model_used,
                "provider_url": provider_url,
                "latency_ms": llm_ms,
                "sanitize_ms": sanitize_ms,
            }
        except (ConnectionError, ValueError) as exc:
            yield {"type": "error", "error": str(exc)}

    def scan_models(self) -> list[dict]:
        return [asdict(e) for e in self._registry.scan()]

    def eject_model(self, model_name: str) -> bool:
        return self._registry.quarantine(model_name)

    def set_model_baseline(self, model_name: str, sha256_hex: str) -> None:
        self._registry.set_baseline(model_name, sha256_hex)
