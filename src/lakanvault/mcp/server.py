"""MCP stdio surface — tools only; no cloud forward. Stdio loop is ticket 1.3."""
from __future__ import annotations

from pathlib import Path

from lakanvault.contracts.mcp import ClassifyResponse
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
