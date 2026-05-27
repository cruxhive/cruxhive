# CruxHive — Team AI Knowledge Layer

**Status**: Planning (Phase 1 starts after Mozbridge GTM sprint; OSS extraction after Phase 1+2 proven internally — not gated on user count)
**Last updated**: 2026-05-27
**Owner**: Jessin Palackal
**Depends on**: ai-toolkit.md (internal dogfooding layer), cicd-fleet-architecture.md (Mozbridge operational data source), security.md (RBAC primitives via Permify)
**OSS repo (future)**: github.com/cruxhive/cruxhive
**Domain**: cruxhive.com (registered 2026-05-27)
**npm**: npx cruxhive init · **PyPI**: cruxhive-mcp · **Open-core**: OSS (Phases 1–4) + Mozbridge commercial (Phases 5–6)

## Context

Engineering work has seven stages. Every AI coding tool covers stages 1–6. Stage 7 has no tooling — and it's where all value is lost.

```
1. Observe     → 2. Define     → 3. Research   → 4. Reason
5. Decide      → 6. Implement  → 7. Capture ← nothing exists here
```

When a session closes, everything the AI learned about your codebase — every constraint discovered, every decision made, every failed approach — evaporates. The next session starts from zero. So does every teammate's session. And the one after that.

This is the **Externalization gap** — the missing quadrant in the GRAI framework (2025 extension of Nonaka's SECI model). AI tools operate entirely in Socialization (developer + AI work together) and Internalization (AI applies context). Nobody has built infrastructure for **Externalization** — converting session-generated tacit knowledge into explicit, persistent, team-shared knowledge.

**80% of organisational knowledge is tacit.** Without Externalization infrastructure, 80% of what your team learns through AI-assisted work is lost every session.

**The problem, precisely:** AI coding tools have no institutional memory. Every session, every teammate, every tool starts from scratch. Teams cannot get compounding value from AI — knowledge earned on Monday doesn't exist on Tuesday.

**The solution:** CruxHive is the governance layer for team AI context. Not just "shared context" — every tool now ships a steering file (AGENTS.md, .kiro/steering/, .cursor/rules/). What nobody has is: human approval before knowledge enters the shared base, audit trail, cross-tool org layer, and live operational intelligence from the deployment platform.

**Positioning:** "The hive mind for your team's AI context — approved, versioned, trusted."

**Build strategy: Dogfood → Extract → Amplify**
Build inside Mozbridge's `ai-toolkit/` first. Prove across 6 workspace projects. Extract as standalone OSS after Phase 1+2 proven internally (not gated on Mozbridge user count — competitive window is 6–12 months). The OSS tool drives Mozbridge adoption — developers find CruxHive, discover Mozbridge's operational context feed (the moat no competitor can replicate).

**Open-core model:** OSS covers everything through Phase 4 (local MCP server, approval workflow, hybrid search, NLI faithfulness). Mozbridge commercial covers Phases 5–6 (operational context feed, cloud sync, managed RBAC via Permify).

## Current State

**Proven in production across 6 workspace projects** (mozbridge, orphimusev2, OranjeBudget, Pratios, traderdeck, vueauto):
- `Development/memory/` — org-level shared context, auto-synced via `scripts/sync-platform-memory.sh` (5 platform fact files, 2 cross-project guardrails)
- `~/.claude/projects/.../memory/` — per-project AI memory (Claude-specific path); 10+ memory files per project with feedback, project state, references
- `.llm/plans/` — versioned plan system; active plans live across 4 areas (cicd, uiux, analytics, security)
- `.llm/memory/` — cross-project platform conventions readable by any AI tool
- PostToolUse hooks — auto-sync on every Write/Edit, auto-update code-review-graph on every file change
- SessionStart hook — memory sync fires on every session open; code-review-graph status loaded
- `ai-toolkit/` — skills manifest with radar, next-slice, write-plan, audit, sync-memory skills
- `mozbridge` MCP server — exposes 30+ platform operations as MCP tools

**What works now:** three-tier context (personal/project/org), org-sync via shell scripts, hook-driven auto-sync, versioned plans, skill distribution. All Claude Code-specific. Organic 4-type taxonomy emerged (platform_* = facts, feedback_* = constraints, project_* = plans/state, reference_* = pointers).

**What's missing vs the target architecture:** tool-agnosticism (currently Claude Code only), semantic search, team approval workflow, confidence scores and expiry, formal seven-type taxonomy, multi-tool adapter layer.

## Architecture Decisions

**Decision**: Three-tier context model — Personal / Project / Org.
**Why**: Mirrors git's local/remote/fork. Personal = per-developer preferences (style, shortcuts). Project = plans, memory, patterns in the repo. Org = cross-project standards, architectural decisions, security rules. Each tier has independent access control and different consumers.
**Trade-off**: Three tiers adds indirection. Single-tier is simpler but can't support team sharing without leaking personal context into org knowledge.

**Decision**: Git as the storage and versioning layer; semantic layer on top.
**Why**: Git gives versioning, history, provenance, collaboration (PRs for context changes), and diffability — "what changed in team knowledge this week?" The semantic layer (relevance ranking, confidence scores, expiry, graph relations) is what git cannot provide. Both are needed.
**Trade-off**: Rejected git-only (no semantic retrieval) and database-only (loses versioning and human collaboration workflow).

**Decision**: MCP as the universal interface — not tool-specific adapters.
**Why**: MCP is already supported by Claude Code, OpenCode, Cursor, Windsurf, VS Code Copilot, and Gemini CLI. Skills and automation live in the MCP server, not per-tool hook configs. One MCP server update propagates to all tools simultaneously. Near-zero maintenance.
**Trade-off**: Rejected per-tool adapter approach (N adapters to maintain per new tool). Only thin symlinks needed per tool for the context filename (`CLAUDE.md`, `AGENT.md`, `.cursorrules`, etc.).

**Decision**: One canonical `CONTEXT.md` symlinked to each tool's expected filename.
**Why**: Content is identical across tools. Only the filename differs. Symlinks = zero sync cost, zero drift.
**Trade-off**: Tools that don't support symlinks need a copy. Currently all major tools support symlinks on macOS/Linux.

**Decision**: Humans always approve AI-proposed knowledge. AI only proposes, never writes directly to approved context.
**Why**: Trust. AI-discovered facts can be wrong, outdated, or misscoped. Human approval is the quality gate. Without it, the shared knowledge base degrades over time via AI hallucination accumulation.
**Trade-off**: Adds friction to knowledge capture. Mitigated by one-keystroke approve UX and confidence-score surfacing (low-confidence entries are flagged, not hidden).

**Decision**: Mozbridge operational context auto-feeds the knowledge base without human proposal.
**Why**: Mozbridge already knows things no static file can capture — deploy failure patterns, build flakiness, secret expiry timelines, maintenance windows. This data is structured, machine-generated, and high-confidence. It becomes automatic context for any AI tool working on a project.
**Trade-off**: Mozbridge-sourced context has no human approval gate (it comes from the platform, not an AI session). Mitigated by marking the source clearly and setting auto-expiry on operational facts.

**Decision**: RBAC inherits Mozbridge's org/project/membership structure via Permify.
**Why**: Zero new identity infrastructure. If you're a project member in Mozbridge, you can read that project's context. Org admins manage org-wide knowledge. Same mental model developers already have.
**Trade-off**: CruxHive as a standalone OSS tool won't have Permify built in — standalone version uses file-based scoping. Full RBAC only available in the Mozbridge-integrated version.

**Decision**: Three swappable storage modes — Simple / Graph / Cloud — chosen at `cruxhive init`.
**Why**: Different teams have different constraints. A solo developer wants zero setup. A team with dedicated infra can benefit from embedded graph traversal. A team on Mozbridge gets cloud-hosted context with zero ops. Forcing one mode excludes everyone else.
**Trade-off**: Three modes to maintain and document. Mitigated by a shared MCP interface — each mode implements the same `search_context`, `propose`, `approve` tool surface; the storage backend is one field in `agentfile.config.yaml`.

| Mode | Storage | Infra required | Best for |
|---|---|---|---|
| Simple | SQLite FTS5 + markdown | None (zero setup) | Solo devs, quick start, most teams |
| Graph | Kuzu (embedded) + SQLite | Docker (one compose service) | Teams needing semantic graph traversal |
| Cloud | Mozbridge-hosted | Mozbridge account | Teams on Mozbridge — zero local ops |

Users select mode at `npx cruxhive init` via a short interactive prompt. Default is Simple. Migration path: Simple → Graph is additive (import existing SQLite); Graph → Cloud is a push.

---

**Decision**: SQLite with temporal fields as the Phase 4 semantic layer — not Graphiti, not mem0.
**Why**: Deep research (2026-05-26) ruled out both alternatives. Graphiti requires a graph database (Neo4j/FalkorDB/Kuzu) plus LLM API calls per knowledge entry for fact extraction — this directly contradicts the near-zero-maintenance goal and adds unbounded cost at team scale. mem0 is personal AI memory with user_id filtering, not a team knowledge base; it has an ADD-only model (no deletion, unbounded growth), made breaking API changes in April 2026, and is not designed for structured approval workflows. SQLite FTS5 + temporal fields (`valid_at`, `invalid_at`, `confidence`, `source_session`, `supersedes_id`) delivers 80% of Graphiti's value with zero extra infrastructure — stays inside the git model.
**Trade-off**: SQLite temporal layer is a custom build — no off-shelf fit exists. Graphiti remains an upgrade path if graph traversal becomes necessary at Phase 5+. Rejected Graphiti-now because infra complexity contradicts the "near-zero maintenance" positioning that makes CruxHive adoptable.

**Decision**: OpenCode plugin system is the first-class adapter for OpenCode — not just a symlink.
**Why**: The OpenCode plugin ecosystem (JS/TS, npm packages, `.opencode/plugins/`) is more capable than initially assessed. Four hooks cover all CruxHive integration points: `session.created` (auto-sync), `tool.execute.after` (capture proposals), `file.edited` (drift detection), `session.compacted` (restore state after context compression). The `session.compacted` hook is particularly valuable — it fires exactly when context is lost and state needs rebuilding from the knowledge base. Existing ecosystem plugins (`opencode-dynamic-context-pruning`, `opencode-supermemory`) confirm the plugin model is production-used.
**Trade-off**: The Claude Code adapter uses hooks/skills (already built). The OpenCode adapter uses JS plugins (new build). Both are thin — ~50 lines each. Maintaining two adapters is acceptable given they call the same underlying MCP tools.

**Decision**: Adopt detect-secrets (Yelp) for proposal scanning, not a custom scanner.
**Why**: detect-secrets has a Python API, supports 25+ secret types via regex + entropy detection, runs as a pre-proposal hook with zero network calls, and is already used in pre-commit workflows. Building a custom scanner for Gap 10 is unnecessary.
**Trade-off**: detect-secrets uses heuristics — false positives possible. Mitigated by showing the flagged content to the proposer with an override option.

**Decision**: Hybrid search — BM25 (SQLite FTS5) + vector (sqlite-vec + Nomic Embed v1.5) fused via Reciprocal Rank Fusion at k=60.
**Why**: BM25 alone misses ~35% of relevant entries on paraphrased queries (e.g. query "where to store tokens?" misses entry "never use localStorage — XSS risk"). Nomic Embed v1.5 (137M params, GGUF Q4 ~130MB, MIT license, 8192 token context, ~50ms on CPU) adds semantic recall with zero API cost. sqlite-vec (7.6k stars, pure C, `pip install sqlite-vec`) stores vectors in the same SQLite file as FTS5 — zero extra infrastructure. RRF fuses by rank not score — no normalisation needed, k=60 is the research-validated default.
**Trade-off**: Adds ~212MB model footprint (nomic + NLI models, one-time download). Session query latency increases from ~5ms to ~60ms — imperceptible. New dependency: `sentence-transformers`.

**Decision**: NLI-based faithfulness checking — `cross-encoder/nli-deberta-v3-small` (82MB, CPU, Apache 2.0).
**Why**: Keyword matching misses synonyms, implicit violations, and produces false positives on negation. TOHA (attention topology) requires model internals — incompatible with Claude/GPT/external APIs. LLM-as-judge adds API cost. NLI (Natural Language Inference) classifies premise/hypothesis pairs as entailment/neutral/**contradiction** — exactly the right primitive for "does this AI response contradict this constraint?" Runs post-session async (~400ms for 3–5 constraints, non-blocking). 82MB, zero API calls.
**Trade-off**: Only checks `type: constraint` entries — not all knowledge types. Catches ~70% of faithfulness failures. High-precision approach; low recall is acceptable because the approval gate prevents most bad entries from entering the base.

**Decision**: Optional web UI served from the MCP server (same process, same port).
**Why**: The approval queue needs a web interface for non-developer reviewers (architects, PMs, tech leads). Health metrics (coverage, bus factor, freshness) are visual, not textual. A dashboard screenshot drives OSS adoption — CLI output screenshots do not. FastAPI already runs in the MCP server; adding `/ui` route is 30 lines + one static HTML file. No second process, no daemon.
**Trade-off**: Adds a static HTML file to the package. UI is optional — CLI always works standalone. `cruxhive ui` opens `localhost:3847/ui`; `cruxhive ui --serve` starts a standalone server if MCP is not already running.

**Decision**: Two-layer packaging — npm CLI (`@cruxhive/cli`) as entry point + PyPI (`cruxhive-mcp`) as the server.
**Why**: Not every developer has Python. Every developer has Node. `npx cruxhive init` works anywhere with zero prerequisites. The npm package is a thin wrapper (~100 lines) that installs `cruxhive-mcp` via `uv` and bootstraps the project. The Python package contains the actual MCP server, SQLite logic, embedding model, NLI model. `cruxhive.config.yaml` (checked into the repo) captures the team configuration — every new member runs `npx cruxhive init` and gets the full setup automatically.
**Trade-off**: Two packages to maintain and publish. Mitigated: the npm package is trivially thin; all logic is in Python.

**Decision**: CruxHive is the name. Not "Lore" or "Agentfile."
**Why**: "Lore" is taken — getlore.ai launched with the same tagline and @lorehq/cli on npm. "Agentfile" had autonomous-AI-agent connotations and confused with the AGENTS.md Linux Foundation standard. "CruxHive" = Crux (the essential, decisive point — what every knowledge entry captures) + Hive (collective intelligence that compounds). `cruxhive init`, `cruxhive propose`, `cruxhive review`, `cruxhive health` — reads cleanly. The hive metaphor is the product thesis: knowledge compounds because the hive never forgets.
**Trade-off**: Two syllables vs one for "Lore." Offset by clean namespace: cruxhive.com registered 2026-05-27, npm @cruxhive/cli 404, PyPI cruxhive-mcp 404. Naming is resolved.

**Decision**: Extract OSS after Phase 1+2 internally proven — not gated on Mozbridge user count.
**Why**: Competitive window is 6–12 months. Grov (192 stars, no approval workflow) is actively shipping (13 releases, last Jan 2026). Amazon Kiro ships `.kiro/steering/` — validates the steering file concept AND accelerates commoditisation of single-file approaches. The moat (governance + org layer) must be live before competitors close the gap. Internal proof across 6 workspace projects is sufficient social proof for an HN launch.
**Trade-off**: Shipping before Mozbridge has external users means no tenant case studies. Mitigated by workspace project evidence (6 projects, N months of usage data).

## Information Model

### Seven knowledge types

Every piece of CruxHive context has a declared type. The type determines expiry behaviour, default confidence, and approval routing.

| Type | What it captures | Expires? | Default confidence |
|---|---|---|---|
| **Fact** | Verified truths about the system — versions, IPs, URLs, API contracts | On change | High (human-approved) |
| **Decision** | Architectural choices with rationale + trade-off. Immutable unless superseded | Never (superseded instead) | High |
| **Plan** | Phased implementation intentions — current sprint, upcoming work | On completion | Medium |
| **Pattern** | Reusable solutions, conventions, code idioms the team repeats | Rarely | High |
| **Constraint** | Things the team must NOT do and why — compliance rules, tech bans, guardrails | Never | High |
| **Research** | External findings, competitive intelligence, technology evaluations | After 90 days | Medium |
| **Outcome** | What happened — deploy results, experiment results, post-mortems | Never | High |

The existing organic taxonomy (platform_* / feedback_* / project_* / reference_*) maps to this:
- `platform_*` → Fact
- `feedback_*` → Constraint
- `project_*` → Plan + Outcome
- `reference_*` → pointer (metadata, not a type)

### Frontmatter standard

Every context file (markdown) carries a YAML frontmatter block. AI tools and `agentfile` CLI read this to populate the semantic index.

```yaml
---
type: fact | decision | plan | pattern | constraint | research | outcome
scope: personal | project | org
topic: one-to-three-word tag (e.g. "auth", "cicd", "database-schema")
valid_at: 2026-05-27         # when this became true
invalid_at: ~                # null = still valid; set to deprecate without deleting
confidence: high | medium | low
source: human | ai-proposed | mozbridge-feed
approved_by: jessin          # git username of approver; null = pending
supersedes: filename.md      # link to the entry this replaces
---
```

**Rules**:
- `invalid_at` set → entry stays in git history but excluded from live context queries
- `source: ai-proposed` → confidence capped at medium until human-approved
- `source: mozbridge-feed` → confidence high but auto-expiry via TTL (30 days default)
- `supersedes` chain must terminate — no circular references

### Three scopes

| Scope | Location | Access | Who writes |
|---|---|---|---|
| Personal | `~/.agentfile/personal/` | Owner only | Developer (never shared) |
| Project | `.llm/` in the repo | All contributors | Any project member (approval required) |
| Org | Shared git remote | All members | Architect role (stricter approval) |

---

## Workflow Framing

Engineering work has seven stages. CruxHive is the infrastructure for Stage 7 — the missing stage everywhere else.

```
1. Observe     — what's happening in the system, market, codebase
2. Define      — which problem to solve (scope, success criteria)
3. Research    — gather facts, competitive intelligence, prior art
4. Reason      — synthesize, analyse trade-offs, stress-test assumptions
5. Decide      — make the architectural or product call
6. Implement   — write the code, run the deploy, ship the thing
7. Capture     — record what was learned for future sessions ← CruxHive lives here
```

Stages 1-6 are well-served. Every tool covers thinking → doing. Stage 7 is where knowledge falls off a cliff: the developer closes the session, the session's institutional memory evaporates, and the next session starts from scratch.

**CruxHive's job**: make Stage 7 a first-class operation that takes < 60 seconds and persists knowledge in a form that any AI tool can retrieve in any future session, for any team member.

The seven types map directly to workflow stages:
- Stages 1-2 → Observation notes and Research entries
- Stages 3-4 → Research + Constraint entries (what ruled out, why)
- Stage 5 → Decision entries (the call + rationale)
- Stage 6 → Plan entries (what was built)
- Stage 7 → Outcome entries (what actually happened vs what was planned)

---

## Out of Scope

- Building a custom UI for knowledge management (CLI + MCP tools are the interface)
- Replacing git with a custom VCS (git is the storage layer, not replaced)
- Real-time collaborative editing of context (async approval workflow is sufficient)
- AI-to-AI knowledge sharing without human approval
- Mobile clients
- Enterprise SSO beyond what Logto already provides
- Any implementation before Mozbridge hits 10-20 users

## Metrics

Research-grounded framework across five layers. Layers 1–2 are measurable from day one (git + frontmatter). Layers 3–4 require MCP logging. Layer 5 is the north star — measured quarterly.

### Layer 1 — Mnemonic function health (Stein & Zwass OMIS, 1995)

| Function | Metric | Alarm |
|---|---|---|
| Acquisition | Proposals per session | < 0.5 (nobody capturing) or > 10 (noise flood) |
| Retention | Approval rate % | < 50% sustained |
| Maintenance | Supersede rate per month | Zero for 30+ days = base stagnating |
| Search | Context recall (see Layer 3) | — |
| Retrieval | `search_context()` p99 latency | > 100ms |

### Layer 2 — Knowledge base health (from git + frontmatter, zero infrastructure)

| Metric | Definition | Alarm |
|---|---|---|
| Coverage | % of areas.toml areas with ≥1 entry | < 30% |
| Standard currency | % of entries within type-specific half-life | < 60% |
| **Knowledge bus factor** | Unique contributors per area (git blame on approved_by) | Any area at 1 |
| Pending queue age | Age of oldest unapproved proposal | > 7 days |
| Provenance completeness | % of entries with approved_by set | < 80% |
| Confidence distribution | Ratio high/medium/low | > 40% low |

**Knowledge bus factor** is the most underappreciated metric. An area where one person contributed all entries has bus factor 1 — that person leaving breaks the AI's institutional memory for that area. Measurable from `approved_by` field today.

### Layer 3 — RAG Triad (requires MCP call logging)

| Metric | What it catches | Target |
|---|---|---|
| Context recall | Relevant entry exists but `search_context()` missed it | > 80% |
| Context precision | Right entry exists but ranked below noise | > 75% |
| **Faithfulness** | AI output contradicts a retrieved constraint (NLI-detected) | > 85% non-violation |
| Abstention correctness | AI fabricated knowledge when base had no relevant entry | > 90% |

Faithfulness is the trust metric. A base with perfect recall but poor faithfulness gives developers false confidence.

### Layer 4 — Externalization rate (the compounding signal)

```
Externalization rate = approved entries added per week
                       ─────────────────────────────────
                       sessions × active developers per week
```

A ratio of 100:1 means 99% of session knowledge is evaporating. Target: ratio trending down over time as capture becomes habitual.

### Layer 5 — North star (measured quarterly, requires session observation)

**Baseline reset frequency**: how many times per week does a developer re-explain something to AI that should already be in the base?

When this trends to zero across the team, the system is working. Target by month 6: < 1 re-explanation per developer per week.

### Type-specific knowledge half-lives (drives `invalid_at` defaults)

| Type | Half-life | Review trigger |
|---|---|---|
| Fact (IPs, versions, URLs) | Months | 90 days |
| Decision (architectural) | 2–4 years | 365 days |
| Plan (sprint, upcoming) | Weeks | On completion |
| Pattern (code conventions) | 1–2 years | 180 days |
| Constraint (don't-do rules) | Very long | 730 days |
| Research (competitive intel) | 6–12 months | 90 days |
| Outcome (what happened) | Permanent | Never |

---

## Phases

### Phase 1 — Internal dogfooding (in progress, partially done)
**Goal**: Solidify the `.llm/` structure and MCP skill layer across all workspace projects so the pattern is proven before extraction.
**Scope**:
- `ai-toolkit/` — finalize skill manifest format; ensure radar, next-slice, write-plan, sync-memory work as MCP tools (not just Claude Code skills)
- `.llm/CONTEXT.md` — single canonical context file that replaces per-tool `CLAUDE.md` content (CLAUDE.md becomes a thin loader or symlink)
- `Development/memory/` sync — verify the org-layer sync works across all 6 workspace projects (mozbridge, orphimusev2, OranjeBudget, pratios, traderdeck, vueauto)
- Document the three-tier model in `ai-toolkit/README.md`
**Success criteria**:
1. All workspace projects read from a shared org-layer context without manual copy-paste
2. `scripts/sync-platform-memory.sh` runs cleanly across all 6 projects
3. Core skills (radar, next-slice, write-plan, audit) exposed as MCP tools callable from any MCP client
4. `ai-toolkit/README.md` explains the three-tier model in under 500 words
**Blocked by**: nothing
**Estimated effort**: M

### Phase 2 — Multi-tool support + bootstrap script
**Goal**: Any developer can run one command to wire CruxHive into whichever AI tools they have installed.
**Scope**:
- `ai-toolkit/bootstrap.sh` — detects installed tools (Claude Code, OpenCode, Cursor, Copilot, Windsurf, Gemini CLI), creates symlinks from `.llm/CONTEXT.md` to each tool's expected filename
- Adapter skeletons:
  - Claude Code: `.claude/settings.json` skeleton with SessionStart sync hook
  - OpenCode: `.opencode/plugins/agentfile.js` — JS plugin (~50 lines) handling `session.created` (sync), `tool.execute.after` (propose capture), `file.edited` (drift check), `session.compacted` (state restore)
  - Cursor: `.cursor/rules/agentfile.mdc` symlink
  - Copilot: `.github/copilot-instructions.md` symlink
  - Windsurf: `.windsurfRules` symlink
- Test: verify Claude Code + OpenCode both load the same CONTEXT.md on the same project
- `ai-toolkit/MULTI_TOOL.md` — documents the symlink strategy and how to add a new tool
**Success criteria**:
1. `bash ai-toolkit/bootstrap.sh` on a fresh project creates correct symlinks + adapters for all detected tools
2. Claude Code and OpenCode sessions on the same project show identical project context (verified manually)
3. OpenCode `session.compacted` hook fires and restores context state from `.llm/`
4. Adding a new tool requires one symlink + one adapter file — documented and testable
5. No per-tool maintenance needed after bootstrap runs
**Blocked by**: Phase 1 (CONTEXT.md must exist before symlinking)
**Estimated effort**: S

### Phase 3 — Extract as standalone open-source package
**Goal**: Publish CruxHive as a standalone OSS tool any team can install, independent of Mozbridge.
**Scope**:
- New repo: `agentfile` (or under `mozbridge-packages/`)
- `npx cruxhive init` — bootstraps `.llm/` structure + CONTEXT.md + bootstrap.sh in a project
- `npx cruxhive sync` — pulls latest org context from a configured remote
- Core MCP server: radar, next-slice, write-plan, sync-memory tools (subset of Mozbridge MCP)
- `README.md` with demo GIF showing Claude Code + OpenCode sharing the same context
- MIT license
- Post: HN "Show HN", r/LocalLLaMA, r/programming
**Success criteria**:
1. `npx cruxhive init` runs in under 30 seconds on a fresh project
2. README explains the value proposition in under 200 words
3. Demo GIF shows two tools sharing context on the same project
4. 100+ GitHub stars within 2 weeks of HN post (leading indicator of product-market fit)
**Blocked by**: Phase 2 (multi-tool support must work before publishing), Mozbridge 10-20 users milestone
**Estimated effort**: M

### Phase 4 — Team sharing + semantic layer
**Goal**: Teams share a context layer. AI sessions can propose knowledge for human approval. Semantic search over context.
**Scope**:
- Shared `.llm/` remote: a git repo that team members clone and sync (like a context upstream)
- `cruxhive propose "<fact>"` — creates a pending knowledge entry; runs detect-secrets scan before queuing; records `{author, session_id, task_context, source_file, timestamp}`
- Approval queue: CLI (`cruxhive review`) shows pending entries with related existing context for comparison; one-keystroke approve/reject/edit
- Propagation: approved entries pushed to the shared remote, teammates pull on next session start
- Semantic search: SQLite FTS5 index over `.llm/` files, rebuilt incrementally on file change (not full reindex). MCP tool: `search_context(query)` returns BM25-ranked results
- Temporal fields on every entry: `valid_at`, `invalid_at`, `confidence`, `source_session`, `supersedes_id` — stored in frontmatter + mirrored into SQLite for querying
- Confidence scores: human-written + approved = high; AI-proposed + approved = medium; pending = low
- Rate limiting on `propose()`: max 10 proposals per session via SlowAPI (already in Mozbridge)
- Note: Graphiti and mem0 explicitly ruled out — see Architecture Decisions
**Success criteria**:
1. `cruxhive propose` scans for secrets before queuing; blocked entries show what triggered the flag
2. `cruxhive propose` creates a pending entry with full `{author, session_id, task_context, timestamp}` metadata
3. `cruxhive review` shows the approval queue with related existing entries for comparison
4. Approved entry appears in all team members' context within one `cruxhive sync` cycle
5. `search_context("auth")` returns BM25-ranked results in under 100ms on a 1,000-entry knowledge base
6. Pending entries surfaced to AI tools as low-confidence (flagged, not hidden)
7. Superseded entries retain `invalid_at` timestamp — queryable as history, excluded from live context
**Blocked by**: Phase 3 (needs established user base to validate team-sharing UX)
**Estimated effort**: L

### Phase 5 — RBAC + governance
**Goal**: Different roles have different read/write/approve permissions on different context scopes.
**Scope**:
- Role definitions: contributor (propose + read project), reviewer (approve project), architect (approve + write org), ops (approve + write operational), admin (full control)
- Scope enforcement: personal context readable only by owner; project context readable by project members; org context readable by all
- Audit trail: every knowledge entry records who proposed it, which session it came from, who approved it, when, what it superseded
- Conflict detection: warn when a new entry contradicts an existing high-confidence entry
- Expiry: operational facts (Mozbridge-sourced) auto-expire after configurable TTL; human-approved facts never expire unless explicitly marked
- Standalone (OSS): file-based scoping via directory structure. Mozbridge-integrated: Permify RBAC
**Success criteria**:
1. A contributor cannot approve their own proposed entry
2. An org admin can see and manage all entries; a project reviewer sees only their project's queue
3. Every entry has a full provenance chain traceable to the proposing session
4. Conflicting entries trigger a warning in the approval UI showing both entries side-by-side
5. Operational entries older than their TTL are automatically marked stale and removed from context
**Blocked by**: Phase 4, Permify integration decision for Mozbridge version
**Estimated effort**: L

### Phase 6 — Mozbridge operational context integration (the moat)
**Goal**: Mozbridge automatically feeds live operational facts into the knowledge base — deploy patterns, build flakiness, secret expiry, infrastructure state — without any human proposal step.
**Scope**:
- `backend/app/services/agentfile_feed.py` — writes structured operational facts to the project's `.llm/memory/operational/` on key events: deploy failure (reason + affected services), build flakiness (pipeline + failure rate), CI secret expiry warnings, maintenance mode changes
- Celery task: `agentfile_sync_operational_context` — runs after every deploy op, build op, and on a nightly schedule
- MCP tool: `get_operational_context(project_id)` — returns the latest operational facts for a project, ranked by recency and severity
- Tenant onboarding: provisioning a project in Mozbridge also bootstraps its CruxHive context layer (`.llm/` structure, CONTEXT.md, org context pointer)
- Auto-expiry: operational facts older than 30 days are removed unless reinforced by a new event
**Success criteria**:
1. After a deploy failure, the project's AI tool automatically knows the failure reason on the next session
2. `get_operational_context("orphimuse")` returns structured facts: last deploy status, build flakiness rate, next secret expiry
3. Provisioning a new project in Mozbridge UI creates `.llm/` structure via a PR on the project's repo (like the CI pipeline install PR)
4. Operational facts are marked with source=mozbridge and auto-expire after 30 days
5. No human action required to get operational context into the knowledge base
**Blocked by**: Phase 4 (needs team-sharing layer), Phase 5 (needs operational fact expiry), deploy-reconciler Phase 2 (richer operational state)
**Estimated effort**: L

## Open Questions

1. **Semantic search storage**: SQLite FTS5 confirmed as Phase 4 implementation (zero infra, incremental, already used by Context Mode). pgvector and Graphiti ruled out — see Architecture Decisions. Revisit only if graph traversal becomes a requirement at Phase 5+. (Owner: Jessin — decided 2026-05-26)

2. **Auto-capture UX**: How does an AI tool propose a knowledge entry mid-session? In-session MCP tool call (`propose_knowledge`)? Post-session summary prompt? The UX determines adoption — too much friction and nobody uses it. (Owner: Jessin — needs user testing)

3. **Naming**: RESOLVED — CruxHive. cruxhive.com registered 2026-05-27. npm @cruxhive/cli clean (404). PyPI cruxhive-mcp clean (404). GitHub org github.com/cruxhive claimed 2026-05-27. No conflicts found.

4. **OSS extraction timing**: Extract after Mozbridge 10-20 users OR after Phase 1+2 proven internally, whichever comes first? Users give social proof; internal proof gives confidence. (Owner: Jessin)

5. **Conflict resolution policy**: When two facts contradict, does the higher-confidence entry win automatically, or does every conflict require human resolution? Automatic resolution risks silently overwriting correct facts; manual resolution creates a queue burden. (Owner: Jessin — decide before Phase 5)

6. **OpenCode plugin distribution**: Should the OpenCode adapter ship as an npm package (`opencode-agentfile`) or as a file in the bootstrapped project (`.opencode/plugins/agentfile.js`)? npm package = easier updates, requires npm publish. Local file = zero external dependency, harder to update. (Owner: Jessin — decide before Phase 2)

## Assumptions

Every assumption this idea rests on. High-importance + low-evidence assumptions are what to validate first — they're the ones that kill ideas silently.

| Assumption | Importance | Evidence | Validation |
|---|---|---|---|
| Teams want shared AI context | High | Grov (191★), ContextCache (3★) prove demand exists | Interview 5 team leads before Phase 3 |
| Git workflow is natural for knowledge management | High | arken-shared-config (4★) uses this, but small sample | Ship Phase 1+2 internally, measure if workspace team adopts it |
| No approval workflow = trust breaks down at scale | High | Anecdotal — no data yet | Survey teams using Grov; ask if they've seen hallucinations propagate |
| Tool-agnostic positioning beats tool-specific | High | Assumption — Grov is multi-tool too | Track whether users cite tool-agnosticism as the reason to choose CruxHive |
| Operational context feed (Phase 6) creates a moat | High | Logical but unvalidated | Can only validate after Phase 6 ships; monitor whether Grov adds deploy integration |
| Teams will approve knowledge entries regularly | Medium | None — this is a new behaviour | UX prototype before Phase 4; measure approval queue drain rate |
| Mozbridge users are the right seed market | Medium | Thesis — Mozbridge solves deploy pain, CruxHive solves context pain | Validate when first Mozbridge tenant tries CruxHive |
| SQLite FTS5 is fast enough at team scale | Medium | Context Mode uses it successfully | Benchmark at 1,000 entries before Phase 4 ships |
| "CruxHive" name is unclaimed | Low | **Checked 2026-05-27** — cruxhive.com registered, npm + PyPI clean | Done |

## Pre-mortem

*It's 2028. CruxHive failed. Why?*

**Scenario A — Approval fatigue killed adoption**
Teams installed it, proposals piled up, nobody reviewed them. The approval queue became a graveyard. Developers stopped proposing because nothing got approved. The knowledge base stayed empty. They uninstalled it after 3 weeks.
*What to watch for:* Approval queue age > 7 days. Mitigation: weekly digest email, one-click approve from email, auto-escalation.

**Scenario B — Grov shipped approval workflows first**
Grov added an approval UI and RBAC in Q3 2026. With 191 stars and a head start on distribution, they captured the market before CruxHive launched publicly. CruxHive was the better architecture but arrived too late.
*What to watch for:* Grov's GitHub commits, changelog, and pricing page. Mitigation: ship Phase 3 OSS faster; the architectural moat (git + three tiers + operational feed) must be live before Grov closes the feature gap.

**Scenario C — The problem wasn't big enough**
Teams got along fine with per-developer AI setups. The inconsistency wasn't painful enough to justify the overhead of a shared knowledge base. CruxHive solved a real problem that teams didn't care about enough to change behaviour for.
*What to watch for:* Low install counts, high churn after first week. Mitigation: nail the solo-developer value first (Phase 1-2 works without a team); team features are the upsell, not the entry point.

**Scenario D — Anthropic shipped native team memory in Claude Code**
Anthropic added org-level memory to Claude Code in a product update. Claude Code's distribution (millions of users) made it the default. Tool-agnostic positioning only matters if there's a reason to be tool-agnostic — and most teams picked one tool.
*What to watch for:* Anthropic team memory announcements. Mitigation: the git layer is the differentiator — it works even if every team uses Claude Code, because git-backed knowledge outlasts any single tool.

## Validation Experiments

Minimum experiments to validate the highest-importance assumptions before committing to each phase.

| Before | Experiment | Success signal |
|---|---|---|
| Phase 2 | Run CruxHive internally across all 6 workspace projects for 30 days | All 6 projects actively use `.llm/` for plans and memory; at least 2 non-Mozbridge projects adopt it |
| Phase 3 | Interview 5 engineering team leads about shared AI context pain | 3+ describe the exact problem CruxHive solves without prompting |
| Phase 4 | Build approval queue prototype, test with one team | Average approval time < 24 hours; queue does not accumulate stale entries |
| Phase 5 | Survey 3 teams using Grov | At least 1 reports a hallucination that propagated to the whole team via auto-capture |
| Phase 6 | Deploy operational feed for Orphimuse; measure AI session quality | AI tool references a Mozbridge-sourced fact in a session without being asked |

## References

- `ai-toolkit/` — current internal skill distribution artifact
- `Development/memory/` — org-level context prototype (the shared layer already working)
- `scripts/sync-platform-memory.sh` — the "git pull" for context (Phase 1 prototype)
- [analytics.md](analytics.md) — Langfuse integration (future: AI session traces feed into knowledge proposals)
- [security.md](security.md) — Permify RBAC (reused for Phase 5 Mozbridge-integrated RBAC)
- [cicd-fleet-architecture.md](cicd-fleet-architecture.md) — Mozbridge operational data source for Phase 6
- Research session 2026-05-25: Harness Engineering (martinfowler.com/articles/harness-engineering.html), BMAD Method, Context Mode (github.com/mksglu/context-mode)
- Research session 2026-05-26: competitive landscape + tool evaluation

**Ruled out (with reasons):**
- Graphiti (github.com/getzep/graphiti) — 26.5k stars, powerful temporal knowledge graph, but requires graph DB (Neo4j/FalkorDB/Kuzu) + LLM calls per entry. Too heavy.
- mem0 (github.com/mem0ai/mem0) — 56.7k stars, YC S24, but personal AI memory not team knowledge base. ADD-only model, breaking API changes Apr 2026, LLM cost per operation.
- Official MCP memory server — JSONL file, single-user only. No team features.

**Adopted (with gaps they close):**
- detect-secrets (github.com/Yelp/detect-secrets) — Gap 10: proposal secret scanning, Python API, 25+ detectors
- SlowAPI — Gap 13: rate limiting on propose(), already in Mozbridge
- Langfuse — Gaps 6/7/9: query tracing + health metrics + feedback loop, already deployed
- opencode-dynamic-context-pruning — Gap 12: context budget, native OpenCode npm plugin
- OpenCode plugin system — first-class adapter via `session.created/tool.execute.after/file.edited/session.compacted` hooks

**Competitive intelligence map (updated 2026-05-27):**

| | AGENTS.md | Grov | Kiro | Continue Hub | Copilot scoped | **CruxHive** |
|---|---|---|---|---|---|---|
| Stars / adoption | 60k+ OSS repos | 192★ | Amazon product | OSS | 26M+ users | — |
| Shared team context | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Human approval workflow | ✗ | ✗ | ✗ | partial (enterprise) | partial (enterprise) | ✓ |
| Git versioning + audit trail | partial | ✗ | ✗ | ✗ | ✗ | ✓ |
| Semantic search | ✗ | ✓ (API) | ✗ | ✗ | ✗ | ✓ (local) |
| Org-layer (cross-project) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Tool-agnostic (MCP) | partial | partial | Kiro only | Continue only | Copilot only | ✓ |
| Faithfulness detection | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (local NLI) |
| Operational data feed | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (Mozbridge) |
| Zero cloud / local | ✓ | partial | ✓ | partial | ✗ | ✓ |

**Critical shift (2026-05-27):** Single-file steering is now commoditised. Amazon Kiro ships `.kiro/steering/`, AGENTS.md has Linux Foundation backing (60k+ repos), Copilot has scoped instructions. The positioning must be governance + org layer — not "shared context." That ship has sailed.

**Watch closely:**
- Grov (github.com/TonyStef/Grov) — 192★, proxy-based, no approval gate, last release Jan 2026. Actively shipping. If they add approval workflow before Phase 3, the gap narrows significantly. Monitor weekly.
- Continue Hub / Mission Control — team assistant sharing for Continue.dev only. Moving toward governance but tool-locked.
- ContextCache (github.com/thecontextcache/contextcache) — FastAPI + Postgres, early stage but architecturally sound. Watch.

**Methodology references:**
- Assumption Log framework — David Bland, *Testing Business Ideas*
- Pre-mortem — Gary Klein (1989), *Sources of Power*
- Opportunity Solution Tree — Teresa Torres, *Continuous Discovery Habits*
- Zettelkasten — Niklas Luhmann; the methodology CruxHive is structurally modelled on (atomic linked notes → emergent knowledge)
