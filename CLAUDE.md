# CruxHive — Claude Guide

## What this is

CruxHive is a team AI knowledge governance layer — an OSS tool being extracted from Mozbridge's internal `ai-toolkit/` after Phase 1+2 are proven.

**Status**: Pre-release. Dogfooding inside `Development/mozbridge/` across 6 workspace projects before extraction.

## Repo layout

```
cruxhive/
├── docs/
│   ├── index.html     — landing page (cruxhive.com via GitHub Pages)
│   ├── landing.html   — same content (canonical source)
│   ├── CNAME          — cruxhive.com
│   └── PLAN.md        — full architecture + phase plan
├── packages/
│   ├── cli/           — @cruxhive/cli npm package
│   │   ├── package.json
│   │   ├── bin/cruxhive.js
│   │   └── lib/{init,sync,health}.js
│   └── mcp/           — cruxhive-mcp PyPI package
│       ├── pyproject.toml
│       ├── cruxhive_mcp/server.py
│       └── cruxhive_mcp/tools/context.py
├── memory/            — CruxHive session memory
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

Phase 1+2 (complete):
- `Development/mozbridge/ai-toolkit/` — skill manifest, bootstrap.sh, adapters, MCP tools (source of truth)
- `Development/memory/` — org-layer context prototype
- `Development/mozbridge/.llm/plans/agentfile.md` — authoritative plan (mirrored here as docs/PLAN.md)

Phase 3+ (this repo is now the primary workspace):
- `packages/mcp/` — standalone `cruxhive-mcp` Python package (extracted from mozbridge MCP)
- `packages/cli/` — `@cruxhive/cli` npm thin wrapper
- Publishing: `uv publish packages/mcp` (PyPI) + `npm publish packages/cli` (npm)

## Links

- cruxhive.com
- github.com/cruxhive/cruxhive
- npm: @cruxhive/cli (not yet published)
- PyPI: cruxhive-mcp (not yet published)
