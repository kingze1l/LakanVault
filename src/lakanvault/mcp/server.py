"""MCP stdio surface — tools only; no cloud forward. Stdio loop is ticket 1.3."""
from __future__ import annotations

from pathlib import Path

from lakanvault.contracts.mcp import AuditQueryRequest, AuditQueryResponse, ClassifyResponse
from lakanvault.orchestration.gateway import Gateway

TOOLS: tuple[str, ...] = (
    "lakanvault_classify",
    "lakanvault_audit_recent",
)


def list_tools() -> tuple[str, ...]:
    return TOOLS


def classify(text: str, config_dir: str | Path = "./config") -> ClassifyResponse:
    """Classify via gateway. Read-only; does not forward prompts to cloud."""
    return Gateway(config_dir=config_dir).classify_text(text)


def audit_recent(
    limit: int = 10,
    config_dir: str | Path = "./config",
) -> AuditQueryResponse:
    req = AuditQueryRequest(limit=limit)
    gw = Gateway(config_dir=config_dir)
    audit_dir = Path(gw.get_config_snapshot().get("local", {}).get("audit_dir", "./data/audit"))
    if not audit_dir.is_absolute():
        audit_dir = Path(config_dir).resolve().parent / audit_dir
    entries = []
    if audit_dir.exists():
        import json

        from lakanvault.contracts.mcp import AuditEntrySummary

        for path in sorted(audit_dir.glob("*.json"), reverse=True)[: req.limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            entries.append(
                AuditEntrySummary(
                    run_id=str(data.get("run_id", path.stem)),
                    overall_status=str(data.get("overall_status", "")),
                    timestamp=str(data.get("written_at", "")),
                    model_filename=str(data.get("target_name", "")),
                    pii_span_count=int(data.get("pii_span_count") or 0),
                )
            )
    return AuditQueryResponse(entries=entries, total_returned=len(entries))
