# CruxHive — Claude Guide

## What this is

CruxHive is a team AI knowledge governance layer — an OSS tool being extracted from Mozbridge's internal `ai-toolkit/` after Phase 1+2 are proven.

**Status**: Pre-release. Dogfooding inside `Development/mozbridge/` across 6 workspace projects before extraction.

## Repo layout (target, not yet built)

```
cruxhive/
├── docs/
│   ├── PLAN.md        — full architecture + phase plan
│   └── landing.html   — marketing landing page
├── packages/
│   ├── cli/           — npm @cruxhive/cli (thin Node wrapper)
│   └── mcp/           — PyPI cruxhive-mcp (FastAPI MCP server)
├── README.md
└── CLAUDE.md
```

## Key decisions (from docs/PLAN.md)

- **Storage**: SQLite FTS5 (BM25) + sqlite-vec (Nomic Embed v1.5) + RRF k=60 hybrid search
- **Approval gate**: Humans always approve AI-proposed entries — AI only proposes, never writes directly
- **Packaging**: npm thin wrapper (`npx cruxhive init`) installs PyPI server via `uv`
- **Faithfulness**: `cross-encoder/nli-deberta-v3-small` post-session async contradiction detection
- **Tiers**: Personal (`~/.cruxhive/`) → Project (`.llm/`) → Org (shared git remote)

## Where the active work lives

Phase 1+2 build inside:
- `Development/mozbridge/ai-toolkit/` — skill manifest + MCP tools
- `Development/memory/` — org-layer context (the prototype)
- `Development/mozbridge/.llm/plans/agentfile.md` — authoritative plan (mirrored here as docs/PLAN.md)

This repo becomes the primary workspace at Phase 3 (OSS extraction).

## Links

- cruxhive.com
- github.com/cruxhive/cruxhive
- npm: @cruxhive/cli (not yet published)
- PyPI: cruxhive-mcp (not yet published)
