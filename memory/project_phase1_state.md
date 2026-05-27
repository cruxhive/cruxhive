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

**Completed 2026-05-27:**
- All 5 workspace projects bootstrapped: orphimusev2, OranjeBudget, Pratios, traderdeck, vueauto
  - .llm/CONTEXT.md seeded for each
  - bootstrap.sh ran: Cursor, Windsurf, Gemini CLI, Claude Code wired per project
  - .claude/settings.json patched with sync-platform-memory.sh SessionStart hook
- mozbridge committed (d6e0c311): Phase 1+2 changes
- cruxhive committed (ac065f7): Phase 3 + landing page
- cruxhive-mcp wheel built: packages/mcp/dist/cruxhive_mcp-0.1.0-py3-none-any.whl

**Remaining manual steps:**
1. `git push` cruxhive repo → github.com/cruxhive/cruxhive
2. `git push` mozbridge repo → github.com/jessin01/mozbridge
3. Enable GitHub Pages (Settings → Pages → source: main/docs) at cruxhive.com
4. PyPI: `cd packages/mcp && UV_PUBLISH_TOKEN=<token> uv publish` (need PyPI API token)
5. npm: `npm login` then `cd packages/cli && npm publish --access=public`
6. HN Show HN post once packages are live

**Why:** Build inside mozbridge first, extract at Phase 3. Packages are ready; publication is a manual deploy step requiring credentials.

**How to apply:** Next session: push both repos, enable GH Pages, then publish packages with credentials.
