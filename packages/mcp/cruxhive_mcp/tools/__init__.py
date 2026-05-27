"""CruxHive tool modules. Each exposes `register(mcp)`."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import context, knowledge


def register_all(mcp: FastMCP) -> None:
    context.register(mcp)
    knowledge.register(mcp)
