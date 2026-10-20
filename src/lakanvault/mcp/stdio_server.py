"""Native MCP stdio server — classify and audit tools for Cursor.

Uses the official MCP Python SDK (newline-delimited JSON-RPC on stdin/stdout).
Does not import local_core or infrastructure; handlers go through Gateway.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mcp.server import MCPServer

from lakanvault.mcp.server import audit_recent, classify


def resolve_config_dir(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    cwd = Path.cwd() / "config"
    if (cwd / "default.yaml").is_file():
        return cwd
    here = Path(__file__).resolve().parents[3] / "config"
    if (here / "default.yaml").is_file():
        return here
    return Path("config")


def build_server(config_dir: str | Path | None = None) -> MCPServer:
    cfg = resolve_config_dir(config_dir)
    server = MCPServer(
        "lakanvault",
        instructions=(
            "Local DLP tools for LakanVault. "
            "These tools classify or audit text; they do not see the final cloud prompt."
        ),
        version="0.1.0",
    )

    @server.tool(
        name="lakanvault_classify",
        description="Classify text for secrets/PII before AI submission. Returns metadata only.",
    )
    def lakanvault_classify(text: str, source: str = "mcp") -> dict:
        return classify(text, config_dir=cfg).model_dump(mode="json")

    @server.tool(
        name="lakanvault_audit_recent",
        description="Return recent audit run metadata (no prompt text).",
    )
    def lakanvault_audit_recent(limit: int = 10) -> dict:
        return audit_recent(limit=limit, config_dir=cfg).model_dump(mode="json")

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LakanVault MCP stdio server")
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Path to config/ containing default.yaml (defaults to ./config)",
    )
    args = parser.parse_args(argv)
    server = build_server(args.config_dir)
    # Protocol traffic only on stdout; SDK redirects stray fd-1 output.
    print("lakanvault-mcp-server: ready on stdio", file=sys.stderr)
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
