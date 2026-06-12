# CruxHive — Claude Guide

## What this is

CruxHive is a team AI knowledge governance layer. One human-curated knowledge base, every AI tool reads from it: Claude Code, OpenCode, Cursor, Windsurf, Gemini CLI. Local SQLite, MIT licensed, zero cloud dependency.

**Status**: Published. `cruxhive-mcp@0.18.0` on PyPI · `@cruxhive/cli@0.18.0` on npm.

**Enforcement & retrieval** (0.13–0.18): `cruxhive-inject` (UserPromptSubmit hook — forces retrieval-as-context) · `cruxhive-guardrails` (PreToolUse hook — denies secret commits / force-push / merged-migration edits; `--list` to inspect; extend via `.llm/guardrails.toml`). `cruxhive init` wires both by default. Search uses keyword-OR FTS (`store.fts_or_query`) so natural-language queries match.

**Human gate** (UI): `cruxhive-ui --workspace` serves a unified app — workspace rollup at `/`, each project mounted at `/p/{name}/` with its dashboard + a `/manage` page (search · create entries/constraints/rules · approve/retire · audit Activity tab).

## Repo layout

```
cruxhive/
├── docs/
│   ├── index.html     — landing page (cruxhive.com via GitHub Pages)
│   ├── guide.html     — full user-facing guide (also bundled in wheel)
│   ├── logo.svg       — brand mark
│   └── favicon.svg
├── packages/
│   ├── cli/           — @cruxhive/cli npm package (thin wrapper)
│   │   ├── package.json
│   │   ├── bin/cruxhive.js
│   │   └── lib/{init,sync,health,...}.js
│   └── mcp/           — cruxhive-mcp PyPI package (the real engine)
│       ├── pyproject.toml
│       ├── cruxhive_mcp/server.py
│       ├── cruxhive_mcp/store.py            — SQLite + FTS5 + entity boost
│       ├── cruxhive_mcp/events.py           — observability log
│       ├── cruxhive_mcp/workspace.py        — cross-project rollup
│       ├── cruxhive_mcp/tools/knowledge.py  — context_search/propose/...
│       ├── cruxhive_mcp/ui/__init__.py      — FastAPI dashboard
│       └── tests/                           — 32 pytest tests
├── scripts/
│   └── sync-docs.sh   — copy docs/guide.html into the wheel before publish
├── .llm/              — this repo's own knowledge base (eats own dog food)
├── README.md
└── CLAUDE.md          — this file
```

## Key architecture decisions

- **Storage**: SQLite FTS5 BM25 + optional sqlite-vec (Nomic Embed v1.5) + RRF k=60 hybrid search, plus entity-aware boost (regex extraction at index time) and recency banding.
- **Approval gate**: AI tools never write directly. They call `context_propose` → entry lands in `.llm/pending/` → human runs `cruxhive review`. Solo developers can run `cruxhive solo` to auto-approve own proposals.
- **Packaging**: npm thin wrapper (`@cruxhive/cli`) drives the Python server (`cruxhive-mcp`). `cruxhive init` installs the server via `uv tool install`.
- **Faithfulness**: optional `cross-encoder/nli-deberta-v3-small` for post-session contradiction detection.
- **Three tiers**: Personal (`~/.cruxhive/personal/`) → Project (`.llm/`) → Org (shared git remote or auto-synced from a workspace memory dir).

## Common dev tasks

| Task | Command |
|------|---------|
| Run tests | `cd packages/mcp && uv run --with pytest --with mcp pytest -q` |
| Build wheel | `cd packages/mcp && rm -rf dist/ && uv build` |
| Publish to PyPI | `uv publish --token "$(awk '/password/{print $3}' ~/.pypirc)"` |
| Build + publish npm | `cd packages/cli && npm publish --access=public` |
| Sync docs into wheel | `scripts/sync-docs.sh` (runs before each `uv build`) |
| Reinstall locally | `uv tool install --editable "packages/mcp[ui]" --force` |
| Smoke test UI | `cruxhive-ui --workspace --port 3847` |

## Versioning

`cruxhive-mcp` (Python) and `@cruxhive/cli` (Node) are versioned independently. Either can be bumped without touching the other. The npm CLI is a thin shell over the Python entry points — if a function moves Python-side, the npm CLI usually doesn't need a release.

## Links

- Site: https://cruxhive.github.io/cruxhive/ (cruxhive.com once DNS is wired)
- Repo: https://github.com/cruxhive/cruxhive
- PyPI: https://pypi.org/project/cruxhive-mcp/
- npm:  https://www.npmjs.com/package/@cruxhive/cli
