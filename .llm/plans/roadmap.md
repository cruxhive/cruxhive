---
type: plan
scope: project
topic: roadmap
valid_at: 2026-05-27
confidence: high
source: human
approved_by: jessin
---

# CruxHive — Phase Roadmap

Full architecture in `docs/PLAN.md`. This file tracks phase-level status for radar.

## Phases

- [x] Phase 1 — Internal dogfooding + MCP skill layer (mozbridge)
- [x] Phase 2 — Multi-tool support + bootstrap.sh (Cursor, Windsurf, Gemini, OpenCode)
- [x] Phase 3 — OSS extraction (`packages/mcp/` + `packages/cli/`)
- [x] Phase 4 — SQLite semantic layer, approval workflow, NLI faithfulness, web UI
- [ ] Phase 5 — Mozbridge operational context feed (deploy telemetry → knowledge entries)
- [ ] Phase 6 — Cloud sync + Permify RBAC (Mozbridge commercial)

## Key decisions

- Storage: SQLite FTS5 + sqlite-vec + Nomic Embed v1.5 + RRF k=60
- Approval gate: humans always approve — AI only proposes, never writes directly
- Packaging: npm thin wrapper → PyPI server via uv
- Faithfulness: cross-encoder/nli-deberta-v3-small post-session async
- Tiers: Personal (~/.cruxhive/) → Project (.llm/) → Org (shared git remote)
- Open-core: OSS (Phases 1–4) + Mozbridge commercial (Phases 5–6)
