# CruxHive

**The hive mind for your team's AI context — approved, versioned, trusted.**

> Your coding AI forgets everything between sessions. Your teammates' AIs forget everything too. CruxHive fixes that — with a human approval gate, hybrid semantic search, and a knowledge base that compounds over time.

```bash
npx cruxhive init
```

---

## Status

**Pre-release.** Being dogfooded internally across 6 projects before public launch.

- [x] Domain: cruxhive.com
- [ ] Phase 1 — Internal dogfooding + MCP skill layer
- [ ] Phase 2 — Multi-tool support + bootstrap script
- [ ] Phase 3 — OSS extraction + public launch
- [ ] Phase 4 — Team sharing + semantic layer

## Why

Engineering work has 7 stages. Every AI tool covers stages 1–6. Stage 7 — **Capture** — has no tooling. That's where all value is lost.

CruxHive is infrastructure for Stage 7.

## What makes it different

| | AGENTS.md | Grov | Kiro | CruxHive |
|---|---|---|---|---|
| Human approval workflow | ✗ | ✗ | ✗ | ✓ |
| Git versioning + audit trail | partial | ✗ | ✗ | ✓ |
| Semantic search (hybrid, local) | ✗ | ✓ (API) | ✗ | ✓ |
| Org-layer (cross-project) | ✗ | ✗ | ✗ | ✓ |
| Faithfulness detection | ✗ | ✗ | ✗ | ✓ |
| Tool-agnostic via MCP | partial | partial | Kiro only | ✓ |

## License

MIT
