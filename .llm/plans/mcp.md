---
type: plan
scope: project
topic: mcp
valid_at: 2026-05-27
confidence: high
source: human
approved_by: jessin
---

# cruxhive-mcp — Package Plan

PyPI package (`cruxhive-mcp`). FastMCP server exposing the CruxHive knowledge layer as MCP tools.

## Shipped

- [x] `server.py` — FastMCP entry point (`cruxhive-mcp` CLI)
- [x] `tools/context.py` — context_radar, context_next_slice, context_write_plan, context_sync_memory
- [x] `frontmatter.py` — minimal YAML frontmatter parser + in-place field setter
- [x] `store.py` — SQLite FTS5 BM25 + optional sqlite-vec hybrid search, RRF k=60
- [x] `embedder.py` — optional Nomic Embed v1.5 (graceful no-op without `[full]`)
- [x] `nli.py` — optional cross-encoder/nli-deberta-v3-small faithfulness checker
- [x] `tools/knowledge.py` — context_index, context_search, context_propose, context_review, context_approve, context_reject, context_check_faithfulness
- [x] `ui/__init__.py` — FastAPI approval queue at localhost:3847
- [x] Optional extras: `[full]` (sentence-transformers + sqlite-vec), `[ui]` (fastapi + uvicorn)

## Pending

- [ ] Publish v0.2.0 to PyPI (`uv publish`)
- [ ] `context_propose` auto-capture hook — fires during AI sessions to surface drift
- [ ] Phase 5: Mozbridge operational context feed (`source: mozbridge-feed`)
- [ ] Phase 6: Cloud sync + Permify RBAC (Mozbridge-integrated only)

## Install tiers

```bash
uvx cruxhive-mcp                  # base — FTS5 search, propose/review workflow
pip install cruxhive-mcp[full]    # + Nomic Embed + sqlite-vec hybrid search
pip install cruxhive-mcp[ui]      # + approval queue web dashboard
pip install cruxhive-mcp[all]     # everything
```
