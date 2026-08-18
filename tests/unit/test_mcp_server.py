"""MCP tool list + classify round-trip (stdio loop is ticket 1.3)."""
from pathlib import Path

from lakanvault.contracts.mcp import DataTier, PolicyAction
from lakanvault.mcp.server import classify, list_tools


def test_lists_classify_and_audit_tools() -> None:
    tools = list_tools()
    assert "lakanvault_classify" in tools
    assert "lakanvault_audit_recent" in tools
    assert len(tools) == 2


def test_classify_clean_text_allows(tmp_path: Path) -> None:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    resp = classify("hello world", config_dir=config_dir)
    assert resp.tier == DataTier.PUBLIC
    assert resp.action == PolicyAction.ALLOW
    assert "prompt_text" not in resp.model_dump()
