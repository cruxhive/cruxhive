# Active — CruxHive

**Updated**: 2026-05-29
**Mode**: local single-user

## Pending

### Low (not blocking daily use)
- [ ] cruxhive.com live — make repo public + enable GitHub Pages
- [ ] Show HN post (after repo public)
- [ ] Phase 5 — Mozbridge operational context feed (deploy telemetry → auto entries)
- [ ] Vector search default model swap (smaller model so hybrid is on for everyone)
- [ ] `cruxhive doctor` diagnostic command
- [ ] Background conflict scanner across all approved entries

### Deferred
- GitHub Actions publish — manual is fine while local-only
- Personal layer cross-machine sync — single machine, no divergence

## Done

- [x] Phase 1 — Canonical context + MCP skill layer
- [x] Phase 2 — Multi-tool bootstrap (Cursor, Windsurf, Gemini, OpenCode)
- [x] Phase 3 — OSS extraction
- [x] Phase 4 — SQLite FTS5 + approval workflow + NLI + web UI
- [x] All 6 workspace projects bootstrapped
- [x] Three tiers (Personal · Project · Org) reach every AI tool
- [x] Real MCP `clientInfo` capture · gitignored DB · published READMEs
- [x] Observability — usage logging, `cruxhive stats`, 4-tab web dashboard
- [x] Cross-tool slash command parity (Claude + OpenCode)
- [x] `/extract` — auto-extract from conversation with approval gate intact
- [x] **Conflict detection at review** — NLI flags contradictions in pending entries
- [x] **Confidence decay** — high → medium → low based on age, computed not stored
- [x] **Dedup warning on `cruxhive propose`** — search similar entries, confirm before file
- [x] **`cruxhive digest`** — weekly markdown report of gaps, decay, queue, divergence
- [x] **Test suite** — 23 pytest tests covering frontmatter, store, events, decay
- [x] `cruxhive-mcp@0.5.0` on PyPI · `@cruxhive/cli@0.6.0` on npm
