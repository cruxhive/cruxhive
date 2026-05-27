# CruxHive

**The hive mind for your team's AI context — approved, versioned, trusted.**

> Your coding AI forgets everything between sessions. Your teammates' AIs forget everything too. CruxHive fixes that — with a human approval gate, hybrid semantic search, and a knowledge base that compounds over time.

```bash
npx cruxhive init
```

---

## Install

```bash
# MCP server (Python 3.11+)
uv pip install cruxhive-mcp

# Full CLI — coming soon
npx cruxhive init
```

Wire into any MCP client — add to `.mcp.json`:
```json
{
  "mcpServers": {
    "cruxhive": { "command": "uvx", "args": ["cruxhive-mcp"], "type": "stdio" }
  }
}
```

**MCP tools**: `context_radar` · `context_next_slice` · `context_write_plan` · `context_sync_memory`

## Status

**Pre-release.** Dogfooding internally across 6 projects before public launch.

- [x] Phase 1 — Internal dogfooding + MCP skill layer ✓
- [x] Phase 2 — Multi-tool support + bootstrap script ✓
- [ ] Phase 3 — OSS extraction + public launch ← here
- [ ] Phase 4 — Team sharing + semantic search

## Why

Engineering work has 7 stages. Every AI tool covers stages 1–6. Stage 7 — **Capture** — has no tooling. That's where all value is lost.

CruxHive is infrastructure for Stage 7.

## What makes it different

| | AGENTS.md | Grov | Kiro | CruxHive |
|---|---|---|---|---|
| Human approval workflow | ✗ | ✗ | ✗ | ✓ |
| Git versioning + audit trail | partial | ✗ | ✗ | ✓ |
| Semantic search (hybrid, local) | ✗ | ✓ (API) | ✗ | ✓ |
| Org-layer (cross-project) | ✗ | ✗ | ✗ | ✓ |
| Faithfulness detection | ✗ | ✗ | ✗ | ✓ |
| Tool-agnostic via MCP | partial | partial | Kiro only | ✓ |

## License

MIT
