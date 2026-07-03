"""Write-time reconciliation: ADD / UPDATE / DUPLICATE verdicts at propose time."""
from __future__ import annotations

from pathlib import Path

from cruxhive_mcp import reconcile, store


def _write(p: Path, body: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _entry(topic: str, content: str, etype: str = "fact") -> str:
    return (
        f"---\ntype: {etype}\nscope: project\ntopic: {topic}\n"
        f"valid_at: 2026-06-01\nconfidence: high\nsource: human\n"
        f"approved_by: tester\n---\n\n{content}\n"
    )


def test_reconcile_add_for_unrelated_content(project):
    _write(project / ".llm" / "context" / "auth.md",
           _entry("auth", "Logto OIDC handles all user-facing authentication flows."))
    store.index(str(project))
    conn = store.connect(str(project))
    v = reconcile.reconcile(conn, "billing", "decision",
                            "Stripe webhooks drive invoice reconciliation nightly.")
    conn.close()
    assert v["verdict"] == "add"
    assert v["target"] is None


def test_reconcile_duplicate_for_near_identical(project):
    body = "The API server runs on port 8000 behind traefik with logto oidc auth."
    _write(project / ".llm" / "context" / "api.md", _entry("api-server", body))
    store.index(str(project))
    conn = store.connect(str(project))
    v = reconcile.reconcile(conn, "api-server", "fact", body)
    conn.close()
    assert v["verdict"] == "duplicate"
    assert v["target"] == ".llm/context/api.md"
    assert v["score"] >= reconcile.DUP_THRESHOLD


def test_reconcile_update_for_refinement(project):
    _write(project / ".llm" / "context" / "api.md",
           _entry("api-server",
                  "The API server runs on port 8000 behind traefik with logto oidc auth."))
    store.index(str(project))
    conn = store.connect(str(project))
    v = reconcile.reconcile(
        conn, "api-server", "fact",
        "The API server runs on port 8000 behind traefik, and now also exposes "
        "a websocket endpoint for realtime updates streaming metrics.",
    )
    conn.close()
    assert v["verdict"] == "update"
    assert v["target"] == ".llm/context/api.md"


def test_reconcile_catches_duplicate_in_pending_queue(project):
    """Queue-dups must be caught even though pending proposals are invisible to
    search (the approval gate) — this is the repeated-/extract scenario."""
    body = "Celery beat fires the wallet engine scan every 300 seconds via redis."
    _write(project / ".llm" / "pending" / "fact_wallet-scan.md",
           "---\ntype: fact\nscope: project\ntopic: wallet-scan\n"
           "valid_at: 2026-07-01\ninvalid_at: ~\nconfidence: medium\n"
           f"source: ai-proposed\napproved_by: ~\n---\n\n{body}\n")
    store.index(str(project))
    conn = store.connect(str(project))
    # Sanity: the gate hides it from search…
    assert all("wallet-scan" not in h["path"]
               for h in store.search_bm25(conn, "wallet engine scan", 5))
    # …but reconcile still sees it.
    v = reconcile.reconcile(conn, "wallet-scan", "fact", body)
    conn.close()
    assert v["verdict"] == "duplicate"
    assert v["target"] == ".llm/pending/fact_wallet-scan.md"


def test_frontmatter_lines_shape():
    assert reconcile.frontmatter_lines({"verdict": "add", "target": None, "score": 0.0}) == ""
    lines = reconcile.frontmatter_lines(
        {"verdict": "update", "target": ".llm/context/api.md", "score": 0.4})
    assert "reconcile: update\n" in lines
    assert "reconcile_target: .llm/context/api.md\n" in lines
    assert "reconcile_score: 0.40\n" in lines


def test_list_pending_exposes_reconcile_verdict(project):
    """The stamped verdict must reach reviewers via list_pending."""
    _write(project / ".llm" / "pending" / "fact_dup-thing.md",
           "---\ntype: fact\nscope: project\ntopic: dup-thing\n"
           "valid_at: 2026-07-02\ninvalid_at: ~\nconfidence: medium\n"
           "source: ai-proposed\napproved_by: ~\n"
           "reconcile: duplicate\nreconcile_target: .llm/context/orig.md\n"
           "reconcile_score: 0.71\n---\n\nSame old thing, restated.\n")
    store.index(str(project))
    conn = store.connect(str(project))
    pend = store.list_pending(conn)
    conn.close()
    match = [p for p in pend if "dup-thing" in p["path"]]
    assert len(match) == 1
    assert match[0]["reconcile"] == "duplicate"
    assert match[0]["reconcile_target"] == ".llm/context/orig.md"
    assert match[0]["reconcile_score"] == "0.71"
    # Preview shows the body, not raw frontmatter.
    assert match[0]["preview"].startswith("Same old thing")
