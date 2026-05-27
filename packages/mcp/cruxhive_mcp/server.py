"""CruxHive MCP server entry point.

Exposes four context tools callable from Claude Code, OpenCode, Cursor,
Windsurf, Gemini CLI, or any MCP-compatible client:

  context_radar         — git commit coverage report
  context_next_slice    — find next unblocked work slice
  context_write_plan    — write/update a .llm/plans/ file
  context_sync_memory   — sync org-layer context across projects
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import register_all

mcp = FastMCP("cruxhive")
register_all(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
