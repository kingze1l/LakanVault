"""MCP tool list + classify round-trip (stdio loop is ticket 1.3)."""
from pathlib import Path

from lakanvault.contracts.mcp import DataTier, PolicyAction
from lakanvault.mcp.server import audit_recent, classify, list_tools


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


def test_audit_recent_returns_metadata_only(tmp_path: Path) -> None:
    src_cfg = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_dir.joinpath("default.yaml").write_text(src_cfg.read_text(encoding="utf-8"), encoding="utf-8")
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    config_dir.joinpath("local.yaml").write_text(
        f"local:\n  audit_dir: {audit_dir.as_posix()}\n",
        encoding="utf-8",
    )
    (audit_dir / "run1.json").write_text(
        '{"run_id":"abc","overall_status":"PASS","written_at":"t",'
        '"target_name":"m.gguf","pii_span_count":2,"prompt_text":"secret"}',
        encoding="utf-8",
    )
    resp = audit_recent(limit=5, config_dir=config_dir)
    assert resp.total_returned == 1
    dumped = resp.model_dump()
    assert "prompt_text" not in dumped
    assert "secret" not in str(dumped)
    assert resp.entries[0].run_id == "abc"
