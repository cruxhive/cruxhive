# cruxhive-mcp

MCP server for the CruxHive knowledge layer. Exposes four tools callable from Claude Code, OpenCode, Cursor, Windsurf, Gemini CLI, or any MCP-compatible client.

## Tools

| Tool | What it does |
|---|---|
| `context_radar` | Scan git history → classify commits by plan area → coverage report |
| `context_next_slice` | Read active plan → extract open items → structured slice proposal |
| `context_write_plan` | Write `.llm/plans/{name}.md` + register in `active.md` |
| `context_sync_memory` | Sync org-layer context to all workspace projects |

All tools operate on the local filesystem (`.llm/` directory). Zero external API calls.

## Install

```bash
uv pip install cruxhive-mcp
# or: pip install cruxhive-mcp
```

## Wire into your project

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "cruxhive": {
      "command": "uvx",
      "args": ["cruxhive-mcp"],
      "type": "stdio"
    }
  }
}
```

Or use `npx cruxhive init` — it does everything automatically.

## Requirements

Python 3.11+. No extra dependencies beyond `mcp`.
