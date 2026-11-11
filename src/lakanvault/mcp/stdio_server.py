# native mcp stdio server so cursor can call classify/protect/restore/audit
"""Native MCP stdio server — classify, protect/restore, and audit tools for Cursor.

Uses the official MCP Python SDK (newline-delimited JSON-RPC on stdin/stdout).
Does not import local_core or infrastructure; handlers go through Gateway.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mcp.server import MCPServer

from lakanvault.mcp.server import audit_recent, classify, protect, restore, shared_gateway


# figure out where config/ lives
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


# build the mcp server with our tools wired up
def build_server(config_dir: str | Path | None = None) -> MCPServer:
    cfg = resolve_config_dir(config_dir)
    # Warm shared Gateway so protect/restore sessions stick for this process.
    shared_gateway(cfg)
    server = MCPServer(
        "lakanvault",
        instructions=(
            "Local DLP tools for LakanVault. "
            "Call lakanvault_protect before sending user text to a cloud model; "
            "call lakanvault_restore on the model reply with the same session_id. "
            "These tools do not see the final cloud prompt unless the agent calls them."
        ),
        version="0.1.0",
    )

    # classify tool — meta only
    @server.tool(
        name="lakanvault_classify",
        description="Classify text for secrets/PII before AI submission. Returns metadata only.",
    )
    def lakanvault_classify(text: str, source: str = "mcp") -> dict:
        return classify(text, config_dir=cfg).model_dump(mode="json")

    # protect tool — sanitize before cloud send
    @server.tool(
        name="lakanvault_protect",
        description=(
            "Scan and sanitize text before sending to an external LLM. "
            "Returns sanitized prompt, session_id, and finding metadata "
            "(entity_type/tier/offsets only — never the raw matched values). "
            "Pass the same session_id to lakanvault_restore after the model replies."
        ),
    )
    def lakanvault_protect(
        text: str,
        session_id: str = "",
        llm: str = "unsure",
    ) -> dict:
        return protect(text, session_id=session_id, llm=llm, config_dir=cfg).model_dump(mode="json")

    # restore tool — put real values back in the reply
    @server.tool(
        name="lakanvault_restore",
        description=(
            "Restore original secret/PII values in an external LLM reply "
            "using session_id from a prior lakanvault_protect call."
        ),
    )
    def lakanvault_restore(text: str, session_id: str) -> dict:
        try:
            return restore(text, session_id=session_id, config_dir=cfg).model_dump(mode="json")
        except KeyError as exc:
            return {"error": str(exc), "session_id": session_id, "text": text}

    # audit tool — recent run meta
    @server.tool(
        name="lakanvault_audit_recent",
        description="Return recent audit run metadata (no prompt text).",
    )
    def lakanvault_audit_recent(limit: int = 10) -> dict:
        return audit_recent(limit=limit, config_dir=cfg).model_dump(mode="json")

    return server


# cli entry — parse args n run stdio loop
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
