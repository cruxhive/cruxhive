# Active — CruxHive

**Updated**: 2026-05-27

## Now

**Publish** — packages are built, credentials needed:
- [ ] `UV_PUBLISH_TOKEN=pypi-xxx uv publish` in `packages/mcp/`
- [ ] `npm login` + `npm publish --access=public` in `packages/cli/`
- [ ] cruxhive.com live (make repo public + GitHub Pages, or Vercel)
- [ ] HN Show HN post

## Next

**Phase 5 — Mozbridge operational context feed**
- Deploy telemetry → automatic `source: mozbridge-feed` knowledge entries
- Build flakiness, secret expiry → surfaced as context without manual proposal
- See: `docs/PLAN.md` Phase 5

## Done

- [x] Phase 1 — Canonical context + MCP skill layer (mozbridge internal)
- [x] Phase 2 — Multi-tool bootstrap (Cursor, Windsurf, Gemini, OpenCode)
- [x] Phase 3 — OSS extraction (`packages/mcp/`, `packages/cli/`)
- [x] Phase 4 — SQLite FTS5 search, approval workflow, NLI faithfulness, web UI
- [x] All 6 workspace projects bootstrapped (Claude Code, OpenCode, Cursor, Windsurf, Gemini)
