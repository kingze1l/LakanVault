# main entry for scans chat protect etc — ui talks to this not local_core directly
"""Gateway — pure Python entry point for all pipeline runs.
Zero Streamlit imports. Can be wrapped as a background .exe in Phase 2 (ADR-004).
UI calls Gateway.receive(); gateway calls Pipeline; gateway returns ScanResponse.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from pathlib import Path
from time import monotonic

from lakanvault.contracts.dtos import ScanRequest, ScanResponse
from lakanvault.contracts.mcp import (
    ClassifyRequest,
    ClassifyResponse,
    DataTier,
    FindingSummary,
    PolicyAction,
    ProtectRequest,
    ProtectResponse,
    RestoreRequest,
    RestoreResponse,
    ReviewSendRequest,
    ReviewSendResponse,
)
from lakanvault.local_core.adapters.local_llm_client import LocalLLMClient
from lakanvault.local_core.audit.stage import AuditStage
from lakanvault.local_core.integrity.registry import ModelRegistry
from lakanvault.local_core.integrity.stage import IntegrityStage
from lakanvault.local_core.policy.engine import Action
from lakanvault.local_core.privacy.anonymizer import ReversibleAnonymizer
from lakanvault.local_core.privacy.classifier import classify_content
from lakanvault.local_core.scan import process_input, process_output
from lakanvault.local_core.security.prompt_guard import (
    BLOCKED_USER_MESSAGE,
    detect_prompt_injection,
    wrap_user_message,
)
from lakanvault.local_core.privacy.stage import PrivacyStage
from lakanvault.local_core.threat_scanner.stage import ThreatScannerStage
from lakanvault.orchestration.bus import EventBus
from lakanvault.orchestration.pipeline import Pipeline
from lakanvault.shared.config import load_config, resolve_config_dir
from lakanvault.shared.system_prompt import build_chat_system_prompt
from lakanvault.shared.url_policy import assert_localhost_url

logger = logging.getLogger(__name__)


class Gateway:
    """
    Wires config → stages → pipeline → bus.
    Returns plain DTOs. Knows nothing about Streamlit or any UI.
    """

    # load config n wire up pipeline bus llm registry
    def __init__(self, config_dir: str | Path = "./config"):
        self._config_dir = resolve_config_dir(config_dir)
        self._cfg = load_config(self._config_dir)
        self._pipeline = self._build_pipeline()
        self._bus = self._build_bus()
        self._anonymizer = ReversibleAnonymizer()
        self._local_llm = self._build_local_llm()
        # Joan scan sessions: session_id -> Vault (:memory:, workspace=session_id)
        self._protect_vaults: dict[str, object] = {}
        local = self._cfg.get("local", {})
        models_dir = self._resolve_path(local.get("models_dir", "./data/models"), self._config_dir)
        self._registry = ModelRegistry(models_dir=models_dir)

    # build the local llm client from config
    def _build_local_llm(self) -> LocalLLMClient:
        ai = self._cfg.get("local_ai", {})
        return LocalLLMClient(
            base_url=ai.get("base_url", "http://localhost:1234"),
            model=ai.get("model", ""),
            timeout_seconds=float(ai.get("timeout_seconds", 120)),
            temperature=float(ai.get("temperature", 0.2)),
            max_tokens=int(ai.get("max_tokens", 120)),
            stream=bool(ai.get("stream", True)),
        )

    # raw config dict for callers
    def get_config_snapshot(self) -> dict[str, object]:
        return self._cfg

    # settings shape the ui cares about
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

    # apply partial settings live (reload cfg bits)
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

    # turn relative paths into absolute ones
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

    # wire stages from config order
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

    # bus for optional cloud forward
    def _build_bus(self) -> EventBus:
        cloud = self._cfg.get("cloud", {})
        return EventBus(
            cloud_enabled=cloud.get("enabled", False),
            analytics_endpoint=cloud.get("analytics_endpoint", ""),
        )

    # run a file scan thru the pipeline
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
                "metadata": s.metadata,
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
            duration_ms=duration_ms,
        )

    # classify text for mcp / ide (no raw pii back)
    def classify_text(
        self,
        text: str,
        source: str = "unknown",
    ) -> ClassifyResponse:
        """Classify content for MCP/IDE integrations. No raw PII in response."""
        _ = ClassifyRequest(text=text, source=source)  # validate bounds
        result = classify_content(text)
        return ClassifyResponse(
            tier=DataTier(result.tier),
            action=PolicyAction(result.action),
            reason=result.reason,
            pii_span_count=result.pii_span_count,
            entity_types=result.entity_types,
            injection_blocked=result.injection_blocked,
            injection_category=result.injection_category,
        )

    # get or make a joan vault for this session id
    def _vault_for_session(self, session_id: str):
        from lakanvault.local_core.anonymizer.anonymizer import Vault

        vault = self._protect_vaults.get(session_id)
        if vault is None:
            key_path = self._config_dir.parent / "data" / "vault.key"
            key_path.parent.mkdir(parents=True, exist_ok=True)
            vault = Vault(":memory:", workspace=session_id, key_path=str(key_path))
            self._protect_vaults[session_id] = vault
        return vault

    # scan + sanitize a prompt (review / hooks / mcp)
    def protect_prompt(
        self,
        text: str,
        session_id: str = "",
        llm: str = "unsure",
        *,
        source: str = "review",
    ) -> ProtectResponse:
        """Joan scan + dictionary apply + Vault sanitize. Findings metadata only."""
        from lakanvault.local_core.policy.engine import Action, action_for, decide
        from lakanvault.local_core.scan import process_input
        from lakanvault.orchestration.protect_events import record_protect_event
        from lakanvault.orchestration.word_dictionary import apply_dictionary

        req = ProtectRequest(text=text, session_id=session_id or "", llm=llm)
        sid = req.session_id or uuid.uuid4().hex[:12]
        vault = self._vault_for_session(sid)
        protected = process_input(req.text, vault, llm=req.llm)  # type: ignore[arg-type]
        # Sami dictionary layer: overlook Joan hits / force CUSTOM_FLAG masks.
        findings = apply_dictionary(req.text, list(protected.findings))
        final, per = decide(findings)
        if final == Action.BLOCK:
            sanitized = ""
        elif final == Action.MASK:
            mask_findings = [f for f, action in per if action == Action.MASK]
            sanitized = vault.sanitize(req.text, mask_findings)
        else:
            sanitized = req.text
        summaries = [
            FindingSummary(
                entity_type=f.entity_type,
                tier=f.tier.value if hasattr(f.tier, "value") else str(f.tier),
                confidence=float(f.confidence),
                start=int(f.start),
                end=int(f.end),
                source=str(f.source),
                needs_escalation=bool(f.needs_escalation),
                action=action_for(f).value,
            )
            for f in findings
        ]
        from lakanvault.orchestration.review_sessions import get_review_sessions

        action_s = final.value if hasattr(final, "value") else str(final)
        event_id: int | None = None
        if action_s in ("warn", "mask", "block"):
            ev = record_protect_event(
                action_s,
                source=source,
                entity_types=[s.entity_type for s in summaries],
            )
            if ev is not None:
                event_id = ev.id
                get_review_sessions().put(
                    event_id=ev.id,
                    session_id=sid,
                    original=req.text,
                    sanitized=sanitized,
                    action=action_s,
                    source=source,
                    entity_types=[s.entity_type for s in summaries],
                    findings=[s.model_dump() for s in summaries],
                )
        return ProtectResponse(
            session_id=sid,
            sanitized=sanitized,
            findings=summaries,
            finding_count=len(summaries),
            final_action=action_s,
            allow_send=final != Action.BLOCK,
            event_id=event_id,
        )

    # put real values back from a prior protect session
    def restore_prompt(self, text: str, session_id: str) -> RestoreResponse:
        """Restore surrogates from Joan Vault for a prior protect session."""
        from lakanvault.local_core.scan import process_output

        req = RestoreRequest(text=text, session_id=session_id)
        vault = self._protect_vaults.get(req.session_id)
        if vault is None:
            raise KeyError(f"unknown protect session: {req.session_id}")
        return RestoreResponse(
            session_id=req.session_id,
            text=process_output(req.text, vault),
        )

    # send reviewed text to local llm (maybe override original once)
    def send_reviewed(
        self,
        session_id: str,
        sanitized: str,
        model: str | None = None,
        base_url: str | None = None,
        *,
        override: bool = False,
    ) -> ReviewSendResponse:
        """Send reviewed text to the local LLM; restore with the review session vault.

        ``override=True`` does **not** call the local LLM. It trusts the stored
        original once for Cursor paste (FR8-style handoff) so a blocked/confidential
        prompt can go through after explicit confirm.
        """
        from lakanvault.local_core.scan import process_output
        from lakanvault.orchestration.hooks_gate import remember_trusted_paste
        from lakanvault.orchestration.review_sessions import get_review_sessions

        req = ReviewSendRequest(
            session_id=session_id,
            sanitized=sanitized,
            model=model,
            base_url=base_url,
            override=override,
        )
        vault = self._protect_vaults.get(req.session_id)
        outbound = (req.sanitized or "").strip()
        used_override = False
        if req.override:
            store = get_review_sessions()
            sess = store.get_by_session(req.session_id)
            if sess is None or not (sess.original or "").strip():
                return ReviewSendResponse(
                    session_id=req.session_id,
                    blocked=True,
                    block_reason="override unavailable (session expired or unknown)",
                )
            if not store.mark_override_used(req.session_id):
                return ReviewSendResponse(
                    session_id=req.session_id,
                    blocked=True,
                    block_reason="override already used for this session",
                )
            outbound = sess.original
            used_override = True
            logger = __import__("logging").getLogger(__name__)
            logger.warning(
                "review override (no LLM) session=%s action=%s entities=%s",
                req.session_id,
                sess.action,
                list(sess.entity_types),
            )
            remember_trusted_paste(outbound)
            return ReviewSendResponse(
                session_id=req.session_id,
                raw_response=(
                    "Override accepted (no local LLM). "
                    "Paste the Original text into Cursor as a new message — "
                    "exact paste is trusted once."
                ),
                restored_response=outbound,
                model_used="(override — paste into Cursor)",
                provider_url="",
                override_used=True,
            )
        else:
            if vault is None:
                raise KeyError(f"unknown protect session: {req.session_id}")
            if not outbound:
                return ReviewSendResponse(
                    session_id=req.session_id,
                    blocked=True,
                    block_reason="nothing to send (blocked or empty sanitized prompt)",
                )
        if base_url:
            assert_localhost_url(base_url)
        system_hint = build_chat_system_prompt(None)
        try:
            result = self._local_llm.chat(
                wrap_user_message(outbound),
                model=req.model,
                base_url=req.base_url,
                system=system_hint,
                stream=False,
            )
        except (ConnectionError, ValueError) as exc:
            return ReviewSendResponse(
                session_id=req.session_id,
                error=str(exc),
                model_used=req.model or self._cfg.get("local_ai", {}).get("model", ""),
                provider_url=req.base_url or self._local_llm.base_url,
                override_used=used_override,
            )
        restored = process_output(result.content, vault)
        return ReviewSendResponse(
            session_id=req.session_id,
            raw_response=result.content,
            restored_response=restored,
            model_used=result.model_used,
            provider_url=result.provider_url,
            latency_ms=result.latency_ms,
            override_used=used_override,
        )

    # check if local llm is up
    def local_llm_status(self, base_url: str | None = None) -> dict:
        url = base_url or self._local_llm.base_url
        models = self._local_llm.list_models(base_url=url)
        return {
            "reachable": bool(models),
            "models": models,
            "base_url": url,
        }

    # list lm studio models (legacy name)
    def lmstudio_models(self) -> list[str]:
        return self._local_llm.list_models()

    # is lm studio reachable (legacy name)
    def lmstudio_reachable(self) -> bool:
        return bool(self._local_llm.list_models())

    # sanitize prompt before chat (joan process_input)
    def _prepare_chat(self, prompt: str) -> dict:
        t0 = monotonic()
        req_id = uuid.uuid4().hex[:12]
        vault = self._vault_for_session(f"chat-{req_id}")
        from lakanvault.orchestration.protect_events import record_protect_event

        try:
            protected = process_input(prompt, vault, llm="never")
        except Exception as exc:
            sanitize_ms = round((monotonic() - t0) * 1000, 1)
            record_protect_event("block", source="chat", entity_types=[])
            return {
                "block_reason": f"detector failure: {type(exc).__name__}",
                "sanitized": "",
                "mapping": {},
                "vault": None,
                "detection_engine": "joan",
                "sanitize_ms": sanitize_ms,
                "system_hint": build_chat_system_prompt(None),
                "llm_prompt": wrap_user_message(""),
                "request_id": req_id,
            }
        if protected.final_action == Action.BLOCK:
            mapping: dict[str, str] = {}
            sanitized = ""
            block_reason = "API key or credential pattern detected"
        else:
            block_reason = detect_prompt_injection(prompt)
            sanitized = protected.sanitized
            mapping = vault.mapping()
        action_s = (
            protected.final_action.value
            if hasattr(protected.final_action, "value")
            else str(protected.final_action)
        )
        if action_s in ("warn", "mask", "block"):
            record_protect_event(
                action_s,
                source="chat",
                entity_types=[f.entity_type for f in protected.findings],
            )
        sanitize_ms = round((monotonic() - t0) * 1000, 1)
        system_hint = build_chat_system_prompt(
            ReversibleAnonymizer.placeholder_system_hint(mapping)
            if mapping and any(k.startswith("NAME_") for k in mapping)
            else None
        )
        return {
            "block_reason": block_reason,
            "sanitized": sanitized,
            "mapping": mapping,
            "vault": vault,
            "detection_engine": "joan",
            "sanitize_ms": sanitize_ms,
            "system_hint": system_hint,
            "llm_prompt": wrap_user_message(sanitized),
            "request_id": req_id,
        }

    # restore placeholders in chat reply
    def _restore_chat_text(self, text: str, prep: dict) -> str:
        vault = prep.get("vault")
        if vault is None:
            return text
        return process_output(text, vault)

    # canned blocked chat response
    def _blocked_chat_result(self, prep: dict, model: str | None, base_url: str | None) -> dict:
        reason = prep["block_reason"] or "prompt injection"
        message = BLOCKED_USER_MESSAGE.format(reason=reason)
        return {
            "sanitized_prompt": prep["sanitized"],
            "mapping": prep["mapping"],
            "raw_response": message,
            "restored_response": message,
            "pii_span_count": len(prep["mapping"]),
            "detection_engine": prep["detection_engine"],
            "model_used": model or self._cfg.get("local_ai", {}).get("model", ""),
            "provider_url": base_url or self._local_llm.base_url,
            "latency_ms": 0.0,
            "sanitize_ms": prep["sanitize_ms"],
            "error": None,
            "blocked": True,
            "block_reason": reason,
        }

    # full chat: sanitize → llm → restore
    def chat(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict:
        prep = self._prepare_chat(prompt)
        if prep["block_reason"]:
            return self._blocked_chat_result(prep, model, base_url)

        try:
            result = self._local_llm.chat(
                prep["llm_prompt"],
                model=model,
                base_url=base_url,
                system=prep["system_hint"],
            )
        except (ConnectionError, ValueError) as exc:
            return {
                "sanitized_prompt": prep["sanitized"],
                "mapping": prep["mapping"],
                "raw_response": "",
                "restored_response": "",
                "pii_span_count": len(prep["mapping"]),
                "detection_engine": prep["detection_engine"],
                "model_used": model or self._cfg.get("local_ai", {}).get("model", ""),
                "provider_url": base_url or self._local_llm.base_url,
                "latency_ms": 0.0,
                "sanitize_ms": prep["sanitize_ms"],
                "error": str(exc),
                "blocked": False,
                "block_reason": "",
            }

        restored = self._restore_chat_text(result.content, prep)

        return {
            "sanitized_prompt": prep["sanitized"],
            "mapping": prep["mapping"],
            "raw_response": result.content,
            "restored_response": restored,
            "pii_span_count": len(prep["mapping"]),
            "detection_engine": prep["detection_engine"],
            "model_used": result.model_used,
            "provider_url": result.provider_url,
            "latency_ms": result.latency_ms,
            "sanitize_ms": prep["sanitize_ms"],
            "error": None,
            "blocked": False,
            "block_reason": "",
        }

    # streaming chat events (meta / token / done / error)
    def chat_stream_events(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
    ):
        """Yield SSE-friendly dict events: meta, token, done, error."""
        prep = self._prepare_chat(prompt)

        yield {
            "type": "meta",
            "sanitized_prompt": prep["sanitized"],
            "pii_span_count": len(prep["mapping"]),
            "placeholders": sorted(prep["mapping"].keys()),
            "sanitize_ms": prep["sanitize_ms"],
            "detection_engine": prep["detection_engine"],
            "blocked": bool(prep["block_reason"]),
            "block_reason": prep["block_reason"] or "",
        }

        if prep["block_reason"]:
            message = BLOCKED_USER_MESSAGE.format(reason=prep["block_reason"])
            yield {
                "type": "done",
                "raw_response": message,
                "restored_response": message,
                "model_used": model or "",
                "provider_url": base_url or self._local_llm.base_url,
                "latency_ms": 0.0,
                "sanitize_ms": prep["sanitize_ms"],
                "blocked": True,
            }
            return

        try:
            parts: list[str] = []
            model_used = model or ""
            provider_url = base_url or self._local_llm.base_url
            llm_start = monotonic()

            for chunk in self._local_llm.chat_stream(
                prep["llm_prompt"],
                model=model,
                base_url=base_url,
                system=prep["system_hint"],
            ):
                if chunk.model_used:
                    model_used = chunk.model_used
                if chunk.provider_url:
                    provider_url = chunk.provider_url
                if chunk.delta:
                    parts.append(chunk.delta)
                    raw_so_far = "".join(parts)
                    restored_so_far = self._restore_chat_text(raw_so_far, prep)
                    yield {
                        "type": "token",
                        "delta": chunk.delta,
                        "restored": restored_so_far,
                    }
                if chunk.done:
                    raw = chunk.full_content or "".join(parts)
                    restored = self._restore_chat_text(raw, prep)
                    llm_ms = round((monotonic() - llm_start) * 1000, 1)
                    yield {
                        "type": "done",
                        "raw_response": raw,
                        "restored_response": restored,
                        "model_used": model_used,
                        "provider_url": provider_url,
                        "latency_ms": llm_ms,
                        "sanitize_ms": prep["sanitize_ms"],
                    }
                    return

            raw = "".join(parts)
            restored = self._restore_chat_text(raw, prep)
            llm_ms = round((monotonic() - llm_start) * 1000, 1)
            yield {
                "type": "done",
                "raw_response": raw,
                "restored_response": restored,
                "model_used": model_used,
                "provider_url": provider_url,
                "latency_ms": llm_ms,
                "sanitize_ms": prep["sanitize_ms"],
            }
        except (ConnectionError, ValueError) as exc:
            yield {"type": "error", "error": str(exc)}

    # scan models dir integrity
    def scan_models(self) -> list[dict]:
        return [asdict(e) for e in self._registry.scan()]

    # quarantine a model file
    def eject_model(self, model_name: str) -> bool:
        return self._registry.quarantine(model_name)

    # pin a hash baseline for a model
    def set_model_baseline(self, model_name: str, sha256_hex: str) -> None:
        self._registry.set_baseline(model_name, sha256_hex)

    # bundled runtime status if we have one
    def runtime_status(self) -> dict:
        from lakanvault.local_core.runtime import get_runtime

        runtime = get_runtime()
        if runtime is None:
            return {"available": False, "running": False, "models": [], "active_model": ""}
        return runtime.status()

    # switch the bundled runtime model
    def runtime_select(self, model: str) -> dict:
        from lakanvault.local_core.runtime import get_runtime

        runtime = get_runtime()
        if runtime is None or not runtime.available():
            raise ValueError("No bundled runtime available")
        if not model or model not in runtime.list_models():
            raise ValueError("Unknown bundled model")
        if not runtime.restart(model):
            raise RuntimeError("Failed to switch model")
        return runtime.status()
