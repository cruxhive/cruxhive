---
type: plan
scope: project
topic: cli
valid_at: 2026-05-27
confidence: high
source: human
approved_by: jessin
---

# @cruxhive/cli — Package Plan

npm package (`@cruxhive/cli`). Thin Node.js wrapper — entry point for any developer regardless of Python setup.

## Shipped

- [x] `bin/cruxhive.js` — CLI router (init, sync, health, ui)
- [x] `lib/init.js` — scaffold .llm/, install cruxhive-mcp via uv/pip, wire .mcp.json + CLAUDE.md
- [x] `lib/sync.js` — workspace sync script or git org_remote pull
- [x] `lib/health.js` — knowledge base audit (typed entries, pending, stale >90d)
- [x] `lib/ui.js` — spawn uvicorn + open browser at localhost:3847

## Pending

- [ ] Publish v0.2.0 to npm (`npm publish --access=public`)
- [ ] `cruxhive index` command — explicit re-index trigger (currently via MCP tool only)
- [ ] `cruxhive propose` command — CLI path to propose without opening an AI tool
- [ ] Interactive `cruxhive review` — approve/reject in terminal without opening the web UI
