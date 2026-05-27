---
name: project-phase1-state
description: CruxHive Phase 1 current progress — what's shipped in mozbridge, what remains
metadata:
  type: project
---

Phase 1 Slice 1 shipped 2026-05-27:

**Shipped:**
- `mozbridge/.llm/CONTEXT.md` — canonical tool-agnostic context file with CruxHive frontmatter. This is the single file any AI tool reads. CLAUDE.md remains for Claude Code-specific instructions (code-review-graph section).
- `mozbridge/mcp/mozbridge_mcp/tools/context.py` — four MCP tools registered in the FastMCP server: `context_radar`, `context_next_slice`, `context_write_plan`, `context_sync_memory`. No new dependencies (stdlib tomllib only).
- `ai-toolkit/skills/core/radar.md` and `write-plan.md` — copied from .claude/commands/ into the skills directory.
- `ai-toolkit/manifest.json` — updated to v1.1.0, added radar and write-plan entries.
- `ai-toolkit/README.md` — added three-tier model section and MCP tools table.
- `cruxhive/docs/index.html` — full landing page at cruxhive.com root. Updated with pre-release status badge, early adopter section (MCP manual setup), and release roadmap.
- `cruxhive/docs/CNAME` and `.nojekyll` — ready for GitHub Pages deployment at cruxhive.com.

**Phase 2 shipped 2026-05-27:**
- `mozbridge/ai-toolkit/bootstrap.sh` — detects + wires all AI tools (Claude Code, Cursor, Windsurf, Gemini, OpenCode)
- `ai-toolkit/adapters/opencode-cruxhive.js` — OpenCode plugin (session.created, session.compacted, file.edited hooks)
- `ai-toolkit/MULTI_TOOL.md` — how to add a new tool in ~5 lines
- Tested live in mozbridge: Cursor + Windsurf + Gemini CLI wired, CLAUDE.md patched

**Phase 3 shipped 2026-05-27:**
- `cruxhive/packages/mcp/` — standalone `cruxhive-mcp` Python package (FastMCP, stdlib only)
- `cruxhive/packages/cli/` — `@cruxhive/cli` npm package (init/sync/health commands)
- README updated with install instructions
- CLAUDE.md updated with new repo layout

**Remaining for actual launch:**
- `uv publish packages/mcp` — publish cruxhive-mcp to PyPI
- `npm publish packages/cli --access=public` — publish @cruxhive/cli
- Push cruxhive repo to github.com/cruxhive/cruxhive
- Enable GitHub Pages (Settings → Pages → source: main/docs) for cruxhive.com
- HN Show HN post once packages are live

**Why:** Build inside mozbridge first, extract at Phase 3. Packages are ready; publication is a manual deploy step.

**How to apply:** Next session start in cruxhive/ repo for publishing work, or mozbridge/ for Phase 4 (semantic search).
