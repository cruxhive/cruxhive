# Active — CruxHive

**Updated**: 2026-05-30
**Mode**: local single-user

## Pending

### Low (not blocking daily use)
- [ ] cruxhive.com live — make repo public + enable GitHub Pages
- [ ] Show HN post (after repo public)
- [ ] Phase 5 — Mozbridge operational context feed (deploy telemetry → auto entries)
- [ ] `cruxhive bootstrap --from-git-history` — auto-seed empty projects from past commits
- [ ] Vector search default model swap (smaller model so hybrid is on for everyone)
- [ ] Background conflict scanner across all approved entries

### Deferred
- GitHub Actions publish — manual is fine while local-only
- Personal layer cross-machine sync — single machine, no divergence
- UI polish (bulk approve, visual diff, audit trail) — no usage data yet
- Smarter `/extract` prompt — no approval telemetry yet to train on

## Done

- [x] Phases 1–4 (context layer, MCP, search, approval, NLI, web UI)
- [x] All 6 workspace projects wired (Claude Code, OpenCode, Cursor, Windsurf, Gemini)
- [x] Three tiers (Personal · Project · Org) reach every AI tool
- [x] `.gitignore` patched, READMEs published, real MCP `clientInfo` capture
- [x] Observability — usage logging, `cruxhive stats`, 4-tab web dashboard
- [x] Cross-tool slash command parity (Claude + OpenCode)
- [x] `/extract` — auto-extract from conversation with approval gate intact
- [x] Conflict detection at review — NLI flags contradictions
- [x] Confidence decay — high → medium → low based on age (computed, not stored)
- [x] Dedup warning on `cruxhive propose`
- [x] `cruxhive digest` — weekly markdown report
- [x] Test suite — 23 pytest tests on hot paths, all passing
- [x] **`cruxhive status`** — one-line health summary for hooks
- [x] **`cruxhive doctor`** — setup audit with fix suggestions
- [x] **Git post-commit auto-index** — closes manual-refresh hole
- [x] **SessionStart nudge** — Claude Code + OpenCode show pending/gaps at session start
- [x] **Auto-decay markers in search results** — surfaces stale entries inline
- [x] `cruxhive-mcp@0.6.0` (PyPI) · `@cruxhive/cli@0.7.0` (npm)
