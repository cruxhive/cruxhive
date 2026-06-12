# CruxHive

**The hive mind for your team's AI context — approved, versioned, trusted.**

> Your coding AI forgets everything between sessions. Your teammates' AIs forget everything too. CruxHive fixes that — with a human approval gate, hybrid semantic search, and a knowledge base that compounds over time.

```bash
npx cruxhive init
```

One human-curated knowledge base. Every AI tool reads from it — Claude Code, OpenCode, Cursor, Windsurf, Gemini CLI. Local SQLite, MIT licensed, zero cloud dependency.

---

## Install

```bash
# One command — installs the MCP server (via uv) and wires up your project
npx cruxhive init
```

Or install the engine directly:

```bash
uv tool install cruxhive-mcp      # Python 3.11+
```

Wire into any MCP client — add to `.mcp.json`:
```json
{
  "mcpServers": {
    "cruxhive": { "command": "uvx", "args": ["cruxhive-mcp"], "type": "stdio" }
  }
}
```

## How it works

AI tools **never write to your knowledge base directly.** They propose; a human approves.

1. Your AI calls `context_propose` → the entry lands in `.llm/pending/`.
2. You run `cruxhive review` → approve or reject, with full git history.
3. Approved entries get indexed and become searchable by every AI tool, every session.

Solo developer? `cruxhive solo` auto-approves your own proposals.

## CLI

```
init        Bootstrap CruxHive in the current project
index       Index .llm/ markdown files into the local knowledge base
propose     Propose a new knowledge entry for human review
review      Interactively approve or reject pending proposals
sync        Sync org-layer context from the configured remote
health      Knowledge base health summary
stats       Usage observability — searches, hit rate, gaps, by AI tool
digest      Weekly markdown digest — gaps, decayed entries, queue health
status      One-line health summary (use --quiet for hooks)
doctor      Diagnose setup — symlinks, hooks, slash commands
workspace   Cross-project rollup — aggregate KPIs across all projects
direnv      Write a .envrc that auto-logs sessions for Cursor/Windsurf/Gemini
solo        Enable/disable solo mode — auto-approve your own proposals
ui          Open the approval-queue dashboard (localhost:3847)
```

## MCP tools

| Tool | What it does |
|------|--------------|
| `context_search` | Hybrid search (FTS5 BM25 + optional sqlite-vec, RRF fusion, entity boost) |
| `context_workspace_search` | Same, across every configured project |
| `context_propose` | Submit a knowledge entry for human review |
| `context_review` / `context_approve` / `context_reject` | The approval gate |
| `context_index` | (Re)index `.llm/` markdown into the local store |
| `context_check_faithfulness` | NLI-based contradiction detection on captured context |
| `context_radar` | Scan recent commits, map to plan areas, surface uncovered work |
| `context_next_slice` · `context_write_plan` · `context_sync_memory` | Planning + org-layer sync |

## Status

**Published.** `cruxhive-mcp` on [PyPI](https://pypi.org/project/cruxhive-mcp/) · `@cruxhive/cli` on [npm](https://www.npmjs.com/package/@cruxhive/cli). MIT, 0 cloud dependencies.

- [x] Phase 1 — Internal dogfooding + MCP skill layer
- [x] Phase 2 — Multi-tool support + bootstrap script
- [x] Phase 3 — OSS extraction + public release
- [x] Phase 4 — Cross-project org layer + hybrid semantic search

## Why

Engineering work has 7 stages. Every AI tool covers stages 1–6. Stage 7 — **Capture** — has no tooling. That's where the value leaks out: hard-won context dies at the end of every session.

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

## Links

- Site: https://cruxhive.github.io/cruxhive/
- PyPI: https://pypi.org/project/cruxhive-mcp/
- npm:  https://www.npmjs.com/package/@cruxhive/cli

## License

MIT
