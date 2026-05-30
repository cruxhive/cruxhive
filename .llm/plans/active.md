# Active — CruxHive

**Updated**: 2026-05-30
**Mode**: local single-user

## How to see metrics

- **Per-project terminal**: `cruxhive stats` · `cruxhive digest` · `cruxhive status`
- **Per-project web UI**: `cruxhive ui` → http://localhost:3847 (4 tabs + KPI banner)
- **Workspace terminal**: `cruxhive workspace`
- **Workspace web UI**: `cruxhive ui --workspace` → http://localhost:3847
- **Setup audit**: `cruxhive doctor`
- **Week-over-week**: `cruxhive digest --compare`

## Pending

### Low (not blocking daily use)
- [ ] cruxhive.com live — make repo public + enable GitHub Pages
- [ ] Show HN post (after repo public)
- [ ] Phase 5 — Mozbridge operational context feed (deploy telemetry → auto entries)
- [ ] `cruxhive bootstrap --from-git-history` — auto-seed empty projects
- [ ] Vector search default model swap (smaller model so hybrid is on for everyone)
- [ ] Background conflict scanner across all approved entries

### Deferred
- GitHub Actions publish — manual is fine while local-only
- Personal layer cross-machine sync — single machine, no divergence
- UI polish (bulk approve, visual diff, audit trail)
- Smarter `/extract` prompt — no telemetry yet to train on

## Done

- [x] Phases 1–4 (context layer, MCP, search, approval, NLI, web UI)
- [x] All 6 workspace projects wired (Claude Code, OpenCode, Cursor, Windsurf, Gemini)
- [x] Three tiers (Personal · Project · Org) reach every AI tool
- [x] Observability — usage logging, `cruxhive stats`, 4-tab web dashboard
- [x] Cross-tool slash command parity (Claude + OpenCode) — six slashes
- [x] `/extract` — auto-extract from conversation with approval gate intact
- [x] Memory intelligence wave — conflict detection, decay, dedup warning, digest
- [x] Test suite — 23 pytest tests on hot paths, all passing
- [x] Automation wave — status, doctor, post-commit hook, SessionStart hook, decay markers
- [x] **Trend tracking** — `cruxhive digest` auto-saves `.llm/digests/{date}.json` + .md
- [x] **`--compare` flag** — week-over-week deltas in digest output
- [x] **`cruxhive workspace`** — cross-project KPI rollup in terminal
- [x] **`cruxhive ui --workspace`** — web dashboard for all projects aggregated
- [x] **KPI banner in per-project UI** — sticky strip with 5 color-coded KPIs
- [x] `cruxhive-mcp@0.7.1` (PyPI) · `@cruxhive/cli@0.8.0` (npm)
