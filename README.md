# CruxHive

**The hive mind for your team's AI context — approved, versioned, trusted.**

> Your coding AI forgets everything between sessions. Your teammates' AIs forget everything too. CruxHive fixes that — with a human approval gate, hybrid semantic search, and a knowledge base that compounds over time.

```bash
npm install -g @cruxhive/cli && cruxhive init
```

One human-curated knowledge base. Every AI tool reads from it — Claude Code, OpenCode, Cursor, Windsurf, Gemini CLI. Local SQLite, MIT licensed, zero cloud dependency.

---

## Install

```bash
npm install -g @cruxhive/cli
cruxhive init
```

`npm install -g` leaves `cruxhive` on PATH, so every command below (`cruxhive review`, `cruxhive ui`, ...) works from any project directory afterward. `init` itself installs the MCP server (via `uv`) and wires up the current project.

Prefer a one-off, no-install run? `npx @cruxhive/cli init` also works — `init` will detect that `cruxhive` isn't left on PATH afterward and print the exact `npx @cruxhive/cli <command>` form to use instead of the short form shown throughout this README.

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

## Installing this for a user (for AI coding agents)

If you're an AI agent asked to set this up in a project, run this sequence — don't skip the verification steps, and don't guess at commands that aren't listed here.

**Claude Code users:** get this as a real Skill instead of relying on your agent to read and follow this section correctly — it auto-loads and triggers on "set up cruxhive" without needing to fetch this page first:
```bash
curl --create-dirs -o ~/.claude/skills/install-cruxhive/SKILL.md \
  https://raw.githubusercontent.com/cruxhive/cruxhive/main/skills/install-cruxhive/SKILL.md
```
Installed once, globally — works from any project afterward.

1. **Check prerequisites.** `node --version` (need 18+) and `uv --version` (need `uv`; if missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`).
2. **Install globally, not via `npx`:** `npm install -g @cruxhive/cli`. This matters — `npx` doesn't leave `cruxhive` on PATH, so every command after this one would fail with `command not found` unless you re-prefix each one with `npx @cruxhive/cli`.
3. **Verify the install before continuing:** `cruxhive --help` should print usage, not an error. If it doesn't, stop and report the actual error — don't fall back to guessing at differently-named commands (in particular, the hyphenated `cruxhive-*` Python entry points that `init` installs are *not* a drop-in replacement for every `cruxhive` subcommand — `cruxhive review`'s interactive/bulk approval flow, for one, only exists in the `cruxhive` CLI itself).
4. **Initialize, from the project's git root:** `cruxhive init`.
5. **Confirm it's healthy:** `cruxhive doctor` — should report no failures.
6. **Describe the project:** edit `.llm/CONTEXT.md` with a few sentences on what this project is, its stack, and its conventions. This is what makes retrieval useful — don't skip it or leave the placeholder text.
7. **Build the index:** `cruxhive index`.
8. **Prove the loop actually works before telling the user it's done** — this is the whole point of the tool, so confirm it rather than assuming:
   - Propose one real fact you've learned about the project so far (via the `context_propose` MCP tool if your client already sees it, otherwise `cruxhive propose` interactively).
   - Confirm it's **not** yet retrievable: search for it (`context_search` / `cruxhive search "<topic>"`) and confirm it does **not** come back. This is the approval gate working correctly, not a bug — don't "fix" it.
   - Tell the user it's waiting: *"N proposal(s) pending your review — run `cruxhive review` to approve or reject."* **Do not approve it yourself** unless the user has explicitly told you they've enabled `cruxhive solo --enable` (single-approver projects only). Approval is meant to be a human action; this is the core guarantee the tool exists to provide, and silently bypassing it defeats the point of installing it.
9. **Report back to the user** what got installed, where `.llm/` lives, and that a human needs to run `cruxhive review` (or `cruxhive ui` for a browser dashboard) to start approving what gets learned.

If any step fails, run `cruxhive doctor` and report its exact output rather than retrying blindly or silently skipping ahead.

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
skills      Sync a canonical skills dir to every AI-tool dialect
            (cruxhive skills sync [--from <dir>], default source .llm/skills/)
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
