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
        """Hybrid BM25 + vector search over the knowledge base.

        query: natural language or keyword query
        n: max results (default 8)
        type: optional filter — fact|decision|plan|pattern|constraint|research|outcome

        Run context_index first if no results appear.
        """
        import time as _time
        root = project_root or os.getcwd()
        t0 = _time.perf_counter()
        result_n = 0
        result_paths: list[str] = []
        try:
            conn = _store.connect(root)
            bm25 = _store.search_bm25(conn, query, n * 2)
            results = bm25

            from .. import embedder as _emb
            if _emb.is_available():
                qvec = _emb.encode_bytes(query)
                if qvec:
                    vec_results = _store.search_vec(conn, qvec, n * 2)
                    results = _store.rrf_fuse(bm25, vec_results)

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

            lines = [f"## Results for `{query}`\n"]
            for i, r in enumerate(results, 1):
                approved = r.get("approved_by") or "⏳ pending"
                lines.append(
                    f"**{i}. {r['path']}**  "
                    f"[{r.get('type','?')}] [{r.get('confidence','?')}] · {approved}"
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
        project_root: str | None = None,
    ) -> str:
        """Propose a new knowledge entry for human review.

        type: fact|decision|plan|pattern|constraint|research|outcome
        topic: one-to-three word tag (e.g. "auth", "database-schema", "cicd")
        content: the knowledge body in markdown (include context, rationale, and why it matters)
        scope: personal|project|org (default: project)

        Writes to .llm/pending/ with source:ai-proposed.
        Use context_review to list pending proposals.
        Confidence is capped at medium until a human approves.
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

        entry = (
            f"---\n"
            f"type: {type}\n"
            f"scope: {scope}\n"
            f"topic: {topic}\n"
            f"valid_at: {date}\n"
            f"invalid_at: ~\n"
            f"confidence: medium\n"
            f"source: ai-proposed\n"
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
        return (
            f"Proposed: `{rel}`\n\n"
            f"Run `context_review` to see all pending proposals, "
            f"or `context_approve` to approve this one directly.\n"
            f"Open the approval dashboard: `cruxhive ui`"
        )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @_events.trace("context_review")
    def context_review(project_root: str | None = None) -> str:
        """List all pending AI-proposed knowledge entries awaiting human approval.

        If cruxhive-mcp[full] is installed, each entry is also scanned via NLI
        for conflicts with existing approved constraints, surfaced inline.
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
