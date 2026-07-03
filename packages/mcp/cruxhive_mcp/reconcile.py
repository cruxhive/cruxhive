"""Write-time reconciliation: classify a new proposal against existing knowledge.

mem0-style ADD / UPDATE / DUPLICATE verdicts, adapted to CruxHive's human gate:
nothing is auto-applied — the verdict is stamped into the proposal's frontmatter
so the reviewer approves a *reconciled* decision ("this updates X", "this
duplicates Y") instead of an ever-growing pile of near-identical entries.

Deterministic and dependency-free: BM25 candidates + token-set Jaccard on entry
bodies. NLI contradiction checking stays a separate layer (nli.py).
"""
from __future__ import annotations

import re
import sqlite3

from . import store as _store
from .frontmatter import parse as _parse_fm

# Verdict thresholds (Jaccard on body token sets).
DUP_THRESHOLD = 0.60      # near-identical content → duplicate
UPDATE_THRESHOLD = 0.25   # substantial overlap → refines/updates the target
# Weaker overlap still counts as an update when topic AND type both match —
# same subject re-documented usually means new info about the same thing.
TOPIC_MATCH_THRESHOLD = 0.12

_STOP = {
    "the", "and", "for", "with", "that", "this", "are", "was", "not",
    "its", "has", "have", "from", "when", "into", "via", "per", "use",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]{3,}", text.lower()) if t not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _body_of(content: str) -> str:
    _, body = _parse_fm(content)
    return body


def reconcile(
    conn: sqlite3.Connection,
    topic: str,
    etype: str,
    content: str,
) -> dict:
    """Return {"verdict": add|update|duplicate, "target": path|None,
    "score": float, "similar": [{path, score}, ...]}.

    Candidates come from two pools: BM25 over retrievable knowledge, plus the
    pending queue itself (invisible to search by design — the approval gate —
    but exactly where duplicate proposals pile up). Fails open to "add".
    """
    new_tokens = _tokens(f"{topic} {content}")
    scored: dict[str, dict] = {}

    def _consider(path: str, row_topic: str | None, row_type: str | None, full: str):
        body_tokens = _tokens(f"{row_topic or ''} {_body_of(full)}")
        score = _jaccard(new_tokens, body_tokens)
        if score <= 0.0:
            return
        prev = scored.get(path)
        if prev is None or score > prev["score"]:
            scored[path] = {
                "path": path, "score": score,
                "topic_match": bool(row_topic and topic
                                    and row_topic.strip().lower() == topic.strip().lower()),
                "type_match": bool(row_type and row_type == etype),
            }

    try:
        # Pool 1 — retrievable (approved/active) knowledge via BM25.
        hits = _store.search_bm25(conn, f"{topic} {content[:300]}", 8)
        paths = [h["path"] for h in hits]
        if paths:
            ph = ",".join("?" * len(paths))
            for r in conn.execute(
                f"SELECT path, topic, type, content FROM entries WHERE path IN ({ph})",
                tuple(paths),
            ).fetchall():
                _consider(r["path"], r["topic"], r["type"], r["content"])

        # Pool 2 — the pending queue (unapproved proposals never surface in
        # search, so queue-dups must be checked directly).
        for r in conn.execute(
            "SELECT path, topic, type, content FROM entries "
            "WHERE path LIKE '.llm/pending/%'"
        ).fetchall():
            _consider(r["path"], r["topic"], r["type"], r["content"])
    except Exception:
        return {"verdict": "add", "target": None, "score": 0.0, "similar": []}

    ranked = sorted(scored.values(), key=lambda x: -x["score"])
    similar = [{"path": s["path"], "score": round(s["score"], 2)} for s in ranked[:3]]
    if not ranked:
        return {"verdict": "add", "target": None, "score": 0.0, "similar": []}

    best = ranked[0]
    if best["score"] >= DUP_THRESHOLD:
        verdict = "duplicate"
    elif best["score"] >= UPDATE_THRESHOLD or (
        best["topic_match"] and best["type_match"]
        and best["score"] >= TOPIC_MATCH_THRESHOLD
    ):
        verdict = "update"
    else:
        return {"verdict": "add", "target": None, "score": round(best["score"], 2),
                "similar": similar}
    return {"verdict": verdict, "target": best["path"],
            "score": round(best["score"], 2), "similar": similar}


def frontmatter_lines(verdict: dict) -> str:
    """Extra frontmatter lines to stamp a non-add verdict into a proposal
    (empty string for add). Reviewers see these via list_pending/UI."""
    if verdict.get("verdict") in ("update", "duplicate") and verdict.get("target"):
        return (
            f"reconcile: {verdict['verdict']}\n"
            f"reconcile_target: {verdict['target']}\n"
            f"reconcile_score: {verdict['score']:.2f}\n"
        )
    return ""


def verdict_message(verdict: dict) -> str | None:
    """Human/AI-facing warning line for a non-add verdict (None for add)."""
    v = verdict.get("verdict")
    if v == "duplicate":
        return (
            f"⚠ **Likely DUPLICATE** of `{verdict['target']}` "
            f"(similarity {verdict['score']:.2f}). Filed for review anyway — "
            f"consider rejecting one of the two."
        )
    if v == "update":
        return (
            f"ℹ This proposal likely **UPDATES** `{verdict['target']}` "
            f"(similarity {verdict['score']:.2f}). The reviewer will see both — "
            f"on approval, consider retiring the older entry."
        )
    return None
