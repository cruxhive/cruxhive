"""Phase 4 knowledge tools: index, search, propose, review, approve, reject, check_faithfulness."""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .. import events as _events
from .. import store as _store
from ..frontmatter import parse as _parse_fm

_VALID_TYPES = frozenset(
    {"fact", "decision", "plan", "pattern", "constraint", "research", "outcome"}
)


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
    @_events.trace("context_index")
    def context_index(project_root: str | None = None) -> str:
        """Index (or re-index) all .llm/ markdown files into .llm/cruxhive.db.

        Run after adding new files or first time on a project. Safe to call repeatedly.
        Optional: install cruxhive-mcp[full] to also index vector embeddings.
        """
        root = project_root or os.getcwd()
        embedder = None
        from .. import embedder as _embedder
        if _embedder.is_available():
            embedder = _embedder
        try:
            count = _store.index(root, embedder=embedder)
            vec_note = " (+ vector embeddings)" if embedder else ""
            return f"Indexed {count} file(s){vec_note} → .llm/cruxhive.db"
        except Exception as e:
            return f"Error indexing: {e}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def context_search(
        query: str,
        n: int = 8,
        type: str = "",
        project_root: str | None = None,
    ) -> str:
        """SEARCH the project's CruxHive knowledge base before answering questions or making changes.

        USE THIS WHEN:
        - The user asks "how does X work in this project?" or "what's our pattern for Y?"
        - You're about to make a non-trivial code change and want to check for existing
          constraints, decisions, or patterns
        - You're unsure about a project convention, host IP, secret path, or
          architectural decision
        - The user references something that sounds team- or project-specific

        Returns hybrid BM25 + (optional) vector search results with snippets, marking
        each result with effective confidence (high/medium/low) and age. Decayed entries
        ([type] [high→medium · Nd old · stale]) need revalidation.

        query: natural-language question or keywords
        n: max results (default 8)
        type: optional filter — fact|decision|plan|pattern|constraint|research|outcome

        If results are empty, the gap is logged for the user to fill via `cruxhive
        propose` or /extract. Run context_index first if total entries shows 0.
        """
        import time as _time
        root = project_root or os.getcwd()
        t0 = _time.perf_counter()
        result_n = 0
        result_paths: list[str] = []
        try:
            conn = _store.connect(root)
            bm25 = _store.search_bm25(conn, query, n * 2)
            vec_results: list[dict] = []

            from .. import embedder as _emb
            if _emb.is_available():
                qvec = _emb.encode_bytes(query)
                if qvec:
                    vec_results = _store.search_vec(conn, qvec, n * 2)

            # Always go through rrf_fuse so entity + recency boosts apply,
            # even when no vector results are available.
            results = _store.rrf_fuse(bm25, vec_results, conn=conn, query=query)

            conn.close()

            if type:
                results = [r for r in results if r.get("type") == type]
            results = results[:n]
            result_n = len(results)
            result_paths = [r.get("path", "") for r in results]

            if not results:
                conn2 = _store.connect(root)
                total = _store.stats(conn2)["total"]
                conn2.close()
                if total == 0:
                    return "Knowledge base is empty. Run context_index first."
                return f"No results for {query!r}. Try broader terms. ({total} entries indexed)"

            # Enrich each result with effective_confidence + age_days for the user
            conn3 = _store.connect(root)
            mtime_map = {
                row["path"]: row["mtime"]
                for row in conn3.execute(
                    f"SELECT path, mtime FROM entries WHERE path IN ({','.join(['?']*len(results))})",
                    [r["path"] for r in results],
                ).fetchall()
            } if results else {}
            conn3.close()
            for r in results:
                eff, age = _store.effective_confidence(
                    r.get("confidence"), r.get("valid_at"), mtime_map.get(r["path"]),
                )
                r["_effective_confidence"] = eff
                r["_age_days"] = age
                r["_decayed"] = (
                    eff != (r.get("confidence") or "").strip().lower()
                    and bool(r.get("confidence"))
                )

            lines = [f"## Results for `{query}`\n"]
            for i, r in enumerate(results, 1):
                approved = r.get("approved_by") or "⏳ pending"
                conf = (r.get("confidence") or "?").lower()
                eff = r.get("_effective_confidence") or conf
                age = r.get("_age_days") or 0
                if r.get("_decayed"):
                    conf_str = f"{conf}→{eff} · {age}d old · stale"
                elif age and conf:
                    conf_str = f"{conf} · {age}d old"
                else:
                    conf_str = conf
                lines.append(
                    f"**{i}. {r['path']}**  "
                    f"[{r.get('type','?')}] [{conf_str}] · {approved}"
                )
                if r.get("topic"):
                    lines.append(f"   _Topic: {r['topic']}_")
                snippet = (r.get("snippet") or "").strip()
                if snippet:
                    lines.append(f"   …{snippet}…")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return f"Error searching: {e}"
        finally:
            ms = int((_time.perf_counter() - t0) * 1000)
            _events.log(
                root, "context_search",
                query=query, result_n=result_n, ms=ms,
                meta={"type_filter": type, "paths": result_paths[:5]} if result_paths else None,
            )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    @_events.trace("context_propose", query_kw="topic")
    def context_propose(
        type: str,
        topic: str,
        content: str,
        scope: str = "project",
        ephemeral: bool = False,
        project_root: str | None = None,
    ) -> str:
        """PROPOSE a new project knowledge entry for the human to approve.

        USE THIS WHEN:
        - The user just established a decision, constraint, or pattern that should
          outlive this conversation ("we use Logto for OIDC", "never log raw tokens",
          "for new features, scaffold via stack.sh")
        - You discovered a non-obvious fact about the project that took effort to find
          and would save future sessions time
        - The user confirms a rule, convention, or architectural choice

        DO NOT use for transient session state, half-formed thoughts, or secrets.

        Writes a markdown entry to .llm/pending/ with source:ai-proposed and
        confidence:medium. The entry is searchable immediately but flagged pending
        until a human approves via /review, `cruxhive review`, or `cruxhive ui`.
        Confidence cannot be raised above medium without approval.

        type: fact | decision | plan | pattern | constraint | research | outcome
        topic: 1–3 word tag (e.g. "auth", "database-schema", "cicd-tokens")
        content: full markdown body — include WHAT, WHY, and any context needed for
                 someone to understand it 6 months from now
        scope: personal | project | org (default: project)
        """
        root = project_root or os.getcwd()
        if type not in _VALID_TYPES:
            return (
                f"Invalid type '{type}'. "
                f"Must be one of: {', '.join(sorted(_VALID_TYPES))}"
            )

        date = datetime.date.today().isoformat()
        slug = topic.lower().replace(" ", "-").replace("/", "-")[:40]
        pending_dir = Path(root) / ".llm" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)

        fpath = pending_dir / f"{type}_{slug}.md"
        suffix = 1
        while fpath.exists():
            fpath = pending_dir / f"{type}_{slug}_{suffix}.md"
            suffix += 1

        source_val = "ephemeral" if ephemeral else "ai-proposed"
        entry = (
            f"---\n"
            f"type: {type}\n"
            f"scope: {scope}\n"
            f"topic: {topic}\n"
            f"valid_at: {date}\n"
            f"invalid_at: ~\n"
            f"confidence: {'low' if ephemeral else 'medium'}\n"
            f"source: {source_val}\n"
            f"approved_by: ~\n"
            f"---\n\n"
            f"{content.strip()}\n"
        )
        fpath.write_text(entry, encoding="utf-8")

        try:
            _store.index(root)
        except Exception:
            pass

        rel = str(fpath.relative_to(root))

        # Mem0-style conflict + similarity detection at propose time.
        # Surfaces conflicts immediately so the proposer can decide to merge,
        # replace, or withdraw before the human reviewer ever sees it.
        warnings: list[str] = []
        try:
            conn = _store.connect(root)

            # Tier 1 — BM25 similarity check (always runs, no deps).
            # Find top 3 existing entries similar to the new proposal's topic+content.
            sim_q = f"{topic} {content[:200]}"
            similar = _store.search_bm25(conn, sim_q, 5)
            similar = [s for s in similar if s.get("path") != rel][:3]
            if similar:
                lines = ["⚠ **Similar existing entries** (review for redundancy):"]
                for s in similar:
                    lines.append(
                        f"  · {s['path']} [{s.get('type','?')}] "
                        f"{'approved' if s.get('approved_by') else 'pending'}"
                    )
                warnings.append("\n".join(lines))

            # Tier 2 — NLI-based contradiction check against approved constraints.
            try:
                from .. import nli as _nli
                if _nli.is_available():
                    constraints = _store.list_approved_constraints(conn)
                    if constraints:
                        conflicts = _nli.check_conflicts(content, constraints)
                        if conflicts:
                            lines = [f"⚠ **{len(conflicts)} contradiction(s) with approved constraints:**"]
                            for c in conflicts[:3]:
                                lines.append(
                                    f"  · [{c.get('severity','?')}] {c.get('path','?')} "
                                    f"(score: {c.get('score','?')})"
                                )
                            warnings.append("\n".join(lines))
            except Exception:
                pass

            conn.close()
        except Exception:
            pass

        msg = (
            f"Proposed: `{rel}`\n\n"
            f"Run `context_review` to see all pending proposals, "
            f"or `context_approve` to approve this one directly.\n"
            f"Open the approval dashboard: `cruxhive ui`"
        )
        if warnings:
            msg = "\n\n".join(warnings) + "\n\n" + msg
        return msg

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @_events.trace("context_review")
    def context_review(project_root: str | None = None) -> str:
        """LIST pending knowledge proposals waiting for human approval.

        USE THIS WHEN:
        - The user asks "what's in my approval queue?" or "anything to review?"
        - You've just filed proposals via context_propose / /extract and want to
          show the user what's queued
        - You see a non-empty pending count in a status nudge

        Returns each pending entry with type, topic, preview, and (if NLI is
        installed) any contradictions with existing approved constraints surfaced
        as warnings. For each entry, the response includes the exact
        context_approve / context_reject calls the user can run.
        """
        root = project_root or os.getcwd()
        try:
            conn = _store.connect(root)
            pending = _store.list_pending(conn)
            pending = _store.annotate_pending_conflicts(conn, pending)
            conn.close()

            if not pending:
                return "No pending proposals — knowledge base is fully reviewed."

            lines = [f"## {len(pending)} pending proposal(s)\n"]
            for p in pending:
                lines.append(f"**{p['path']}**")
                lines.append(
                    f"  type: {p.get('type','?')} · "
                    f"topic: {p.get('topic','?')} · "
                    f"proposed: {p.get('valid_at','?')}"
                )
                preview = (p.get("preview") or "").strip()[:120]
                if preview:
                    lines.append(f"  > {preview}…")

                conflicts = p.get("conflicts") or []
                if conflicts:
                    lines.append(f"  ⚠ **{len(conflicts)} potential conflict(s):**")
                    for c in conflicts[:3]:
                        lines.append(
                            f"    · [{c['severity']}] {c['path']} "
                            f"(score: {c['score']}) — {c['preview']}"
                        )

                lines.append(
                    f"  ✓ `context_approve path=\"{p['path']}\" approver=\"<your-name>\"`"
                )
                lines.append(
                    f"  ✗ `context_reject path=\"{p['path']}\"`\n"
                )
            lines.append("Or open the approval dashboard: `cruxhive ui`")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
    @_events.trace("context_approve", query_kw="path")
    def context_approve(
        path: str,
        approver: str,
        project_root: str | None = None,
    ) -> str:
        """Approve a pending knowledge proposal.

        Updates source→human, sets approved_by on disk and in the index.
        path: relative path from project root (e.g. .llm/pending/constraint_auth.md)
        approver: your git username or name
        """
        root = project_root or os.getcwd()
        try:
            conn = _store.connect(root)
            ok = _store.approve(conn, path, approver, root)
            conn.close()
            if ok:
                return f"Approved: `{path}` — approved_by: {approver}"
            return f"Not found: {path}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
    @_events.trace("context_reject", query_kw="path")
    def context_reject(
        path: str,
        project_root: str | None = None,
    ) -> str:
        """Reject a pending knowledge proposal.

        Sets invalid_at to today, removes from the active index. File stays in git history.
        path: relative path from project root
        """
        root = project_root or os.getcwd()
        try:
            conn = _store.connect(root)
            ok = _store.reject(conn, path, root)
            conn.close()
            if ok:
                return f"Rejected: `{path}` — invalid_at set, removed from index"
            return f"Not found: {path}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @_events.trace("context_check_faithfulness")
    def context_check_faithfulness(
        response: str,
        project_root: str | None = None,
    ) -> str:
        """Check if an AI response contradicts any approved constraints in the knowledge base.

        Uses cross-encoder/nli-deberta-v3-small (~82 MB).
        Install: pip install cruxhive-mcp[full]
        Runs in ~400 ms for 3-5 constraints on CPU.

        response: the AI response text to validate
        """
        root = project_root or os.getcwd()
        try:
            conn = _store.connect(root)
            rows = conn.execute("""
                SELECT content FROM entries
                WHERE type = 'constraint'
                  AND source = 'human'
                  AND (invalid_at IS NULL OR invalid_at IN ('~','null','none',''))
            """).fetchall()
            conn.close()

            if not rows:
                return (
                    "No approved constraints in knowledge base. "
                    "Propose constraints with context_propose, then approve them."
                )

            from ..nli import check, is_available
            if not is_available():
                constraint_list = "\n".join(
                    f"- {r['content'][:80]}…" for r in rows[:5]
                )
                return (
                    f"NLI checker not installed. Install: `pip install cruxhive-mcp[full]`\n\n"
                    f"Constraints to check manually ({len(rows)} total):\n{constraint_list}"
                )

            constraints = [r["content"] for r in rows]
            violations = check(response, constraints)
            _events.log(
                root, "faithfulness.result",
                result_n=len(violations),
                meta={"constraints_checked": len(constraints)},
            )

            if not violations:
                return (
                    f"No faithfulness violations detected "
                    f"({len(constraints)} constraint(s) checked)."
                )

            lines = [f"## ⚠ {len(violations)} faithfulness violation(s)\n"]
            for v in violations:
                lines.append(f"**{v['severity'].upper()}** (score: {v['score']})")
                lines.append(f"> {v['constraint']}\n")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"
