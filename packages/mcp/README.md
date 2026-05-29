# cruxhive-mcp

The Python MCP server for [CruxHive](https://cruxhive.com) — a team AI knowledge governance layer.

Drop it into any project and any MCP-compatible AI tool (Claude Code, OpenCode, Cursor, Windsurf, Gemini CLI) can search, propose, and review project knowledge with a human-in-the-loop approval gate.

## Why

LLM coding tools all have their own context format (`CLAUDE.md`, `AGENT.md`, `.cursor/rules/`, `.windsurfRules`). When you switch tools, you lose all your accumulated context. When you let the AI write to that context, you lose control of what's true.

CruxHive solves both:

- **Tool-agnostic** — one canonical `.llm/CONTEXT.md`, symlinked into every tool's expected location. Switch LLMs, keep your knowledge.
- **Approval-gated** — AI proposes new knowledge, humans approve. Search and indexing happens locally in SQLite.
- **Three tiers** — personal (`~/.cruxhive/personal/`), project (`.llm/`), org (synced).

## Install

The recommended path is via the npm CLI which installs this server automatically:

```bash
npm install -g @cruxhive/cli
cruxhive init
```

To install just the Python server directly:

```bash
uv tool install cruxhive-mcp                # core
uv tool install "cruxhive-mcp[ui]"          # + web dashboard
uv tool install "cruxhive-mcp[full]"        # + hybrid vector search + NLI
```

## What it exposes

Eleven MCP tools, all operating on local SQLite. Zero network calls.

| Tool | What it does |
|---|---|
| `context_index` | Scan `.llm/` + `~/.cruxhive/personal/` → SQLite FTS5 (+ optional vec) |
| `context_search` | Hybrid BM25 + vector search with RRF fusion (k=60) |
| `context_propose` | Write a pending knowledge entry to `.llm/pending/` |
| `context_review` | List entries awaiting human approval |
| `context_approve` | Approve a pending entry (source → human) |
| `context_reject` | Mark entry invalid (sets `invalid_at`, removes from index) |
| `context_check_faithfulness` | NLI contradiction check against approved constraints |
| `context_radar` | Git commits → classify by plan area → coverage report |
| `context_next_slice` | Read active plan → extract first unblocked work item |
| `context_write_plan` | Write `.llm/plans/{name}.md` + register in `active.md` |
| `context_sync_memory` | Sync workspace-level org context across projects |

## CLI binaries

Each tool also has a standalone CLI entry point, used internally by `@cruxhive/cli`:

```
cruxhive-mcp        # MCP stdio server
cruxhive-index      # build/refresh SQLite index
cruxhive-propose    # write a pending entry (content on stdin)
cruxhive-review     # JSON list of pending entries
cruxhive-approve    # approve an entry
cruxhive-reject     # reject an entry
cruxhive-stats      # usage observability dashboard
```

## Manual `.mcp.json` wiring

If you'd rather skip `cruxhive init`:

```json
{
  "mcpServers": {
    "cruxhive": {
      "command": "cruxhive-mcp",
      "type": "stdio"
    }
  }
}
```

## Observability

Every MCP tool call is logged locally to `.llm/cruxhive.db` (events table) with: timestamp, calling AI tool, query, result count, latency. Inspect with:

```bash
cruxhive stats              # last 7 days summary + by-AI-tool breakdown + top gaps
cruxhive stats --days 30 --gaps
cruxhive stats --export csv > usage.csv
```

Disable logging entirely with `CRUXHIVE_ANALYTICS=0`.

## Knowledge entry format

Every entry is a markdown file under `.llm/` with YAML frontmatter:

```markdown
---
type: constraint        # fact | decision | plan | pattern | constraint | research | outcome
scope: project          # personal | project | org
topic: auth
valid_at: 2026-05-29
invalid_at: ~
confidence: high        # low | medium | high
source: human           # human | ai-proposed | mozbridge-feed
approved_by: jane       # or ~ for pending
---

The body, in markdown. Explain what's true, when, and why.
```

`cruxhive propose` builds this for you interactively.

## Architecture

- **Storage**: SQLite FTS5 (BM25) + optional `sqlite-vec` + Nomic Embed v1.5
- **Fusion**: Reciprocal Rank Fusion, k=60 (research-validated default)
- **Approval**: AI proposes → human approves; constraint writes always require approval
- **Faithfulness**: optional `cross-encoder/nli-deberta-v3-small` (~82MB) for post-session contradiction checks

## Links

- Project site: <https://cruxhive.com>
- Documentation: <https://cruxhive.com/guide.html>
- Source: <https://github.com/cruxhive/cruxhive>
- npm CLI: [`@cruxhive/cli`](https://www.npmjs.com/package/@cruxhive/cli)

## License

MIT.
