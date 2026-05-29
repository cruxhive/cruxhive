# @cruxhive/cli

The CLI for [CruxHive](https://cruxhive.com) — a team AI knowledge governance layer that gives Claude Code, OpenCode, Cursor, Windsurf, and Gemini CLI a shared, human-approved knowledge base.

## Quick start

```bash
npm install -g @cruxhive/cli
cd your-project
cruxhive init
cruxhive index
```

That's it. Your AI tools now share a single approved knowledge base for this project.

## What `init` does

1. Creates `~/.cruxhive/personal/` (one-time bootstrap, machine-wide)
2. Creates `.llm/` structure in the current project (`CONTEXT.md`, `plans/`, `pending/`, `context/`, `memory/`)
3. Installs `cruxhive-mcp` via `uv tool install` (or `pip` as fallback)
4. Wires `.mcp.json` so any MCP client can call CruxHive tools
5. Symlinks `CLAUDE.md`, `AGENT.md`, `GEMINI.md`, `.windsurfRules`, `.cursor/rules/cruxhive.mdc` → `.llm/CONTEXT.md`
6. Patches `.gitignore` so `.llm/cruxhive.db` (your local index + usage log) is never committed

## Commands

| Command | What it does |
|---|---|
| `cruxhive init` | Bootstrap a project (see above) |
| `cruxhive index` | (Re)build SQLite knowledge index from `.llm/` + `~/.cruxhive/personal/` |
| `cruxhive propose` | Interactive: pick type → topic → opens `$EDITOR` → writes to `.llm/pending/` |
| `cruxhive review` | Terminal loop: approve / reject / skip each pending entry |
| `cruxhive health` | Status of Personal · Org · Project tiers + counts + stale files + MCP wiring |
| `cruxhive stats` | Usage observability — searches, hit rate, gaps, per-AI-tool breakdown |
| `cruxhive sync` | Pull org-layer context from workspace memory or git remote |
| `cruxhive ui` | Web dashboard at <http://localhost:3847> (requires `cruxhive-mcp[ui]`) |

`cruxhive stats` flags: `--days N`, `--by tool`, `--gaps`, `--stale`, `--export csv|json`, `--clear`, `--json`.

## Three-tier context model

| Tier | Lives at | Contents |
|---|---|---|
| **Personal** | `~/.cruxhive/personal/` | Developer preferences. Indexed into every project on this machine. Never committed. |
| **Project** | `.llm/` | Plans, patterns, constraints. Lives in your project repo. |
| **Org** | `.llm/memory/platform_refs.md` | Cross-project facts auto-synced from workspace or a shared git remote. |

All three are visible to every MCP-compatible AI tool. Switch from Claude Code to OpenCode mid-session — same context, same constraints, same approvals.

## Requirements

- Node.js ≥ 18 (for this CLI)
- Python ≥ 3.11 (for the MCP server, installed automatically)
- [`uv`](https://docs.astral.sh/uv/) is recommended (cleaner installs); `pip` works as a fallback

## Observability

Every MCP tool call is logged locally. No data leaves your machine. Opt out with `CRUXHIVE_ANALYTICS=0`.

```bash
cruxhive stats
# shows: total calls, searches, hit rate, per-AI-tool breakdown,
# top zero-result queries (= what to document next), daily sparkline
```

## Links

- Site: <https://cruxhive.com>
- Guide: <https://cruxhive.com/guide.html>
- Source: <https://github.com/cruxhive/cruxhive>
- PyPI server: [`cruxhive-mcp`](https://pypi.org/project/cruxhive-mcp/)

## License

MIT.
