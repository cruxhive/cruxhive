"""Index → search → approve → reject lifecycle, plus confidence decay."""
import datetime
from pathlib import Path

import pytest

from cruxhive_mcp import store


def _write(p: Path, body: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_index_picks_up_files(project):
    n = store.index(str(project))
    assert n >= 1
    conn = store.connect(str(project))
    rows = conn.execute("SELECT path FROM entries").fetchall()
    conn.close()
    paths = {r["path"] for r in rows}
    assert ".llm/CONTEXT.md" in paths


def test_bm25_search_returns_matching_entry(project):
    _write(project / ".llm" / "plans" / "auth-rewrite.md",
           "---\ntype: plan\ntopic: auth\nvalid_at: 2026-05-01\n"
           "confidence: high\nsource: human\n---\n\nReplace Logto with WorkOS.\n")
    store.index(str(project))
    conn = store.connect(str(project))
    hits = store.search_bm25(conn, "auth", 5)
    conn.close()
    paths = [h["path"] for h in hits]
    assert any("auth-rewrite" in p for p in paths)


def test_search_excludes_invalidated_entries(project):
    _write(project / ".llm" / "context" / "old.md",
           "---\ntype: fact\ntopic: deprecated-thing\nvalid_at: 2025-01-01\n"
           "invalid_at: 2026-04-01\nconfidence: high\nsource: human\n---\n\nDo not use.\n")
    store.index(str(project))
    conn = store.connect(str(project))
    hits = store.search_bm25(conn, "deprecated-thing", 5)
    conn.close()
    assert hits == [] or all("deprecated-thing" not in (h.get("topic") or "") for h in hits)


def test_pending_lifecycle(project):
    pending = project / ".llm" / "pending" / "constraint_auth.md"
    _write(pending,
           "---\ntype: constraint\nscope: project\ntopic: auth\n"
           "valid_at: 2026-05-29\nconfidence: medium\nsource: ai-proposed\n"
           "approved_by: ~\n---\n\nNever log raw tokens.\n")
    store.index(str(project))
    conn = store.connect(str(project))

    listed = store.list_pending(conn)
    assert len(listed) == 1
    assert listed[0]["path"] == ".llm/pending/constraint_auth.md"

    ok = store.approve(conn, listed[0]["path"], "tester", str(project))
    assert ok is True
    assert store.list_pending(conn) == []

    on_disk = pending.read_text()
    assert "approved_by: tester" in on_disk
    assert "source: human" in on_disk
    conn.close()


def test_reject_sets_invalid_at_and_removes_from_index(project):
    pending = project / ".llm" / "pending" / "fact_bad.md"
    _write(pending,
           "---\ntype: fact\nscope: project\ntopic: bad\n"
           "valid_at: 2026-05-29\nconfidence: low\nsource: ai-proposed\n"
           "approved_by: ~\n---\n\nWrong thing.\n")
    store.index(str(project))
    conn = store.connect(str(project))

    ok = store.reject(conn, ".llm/pending/fact_bad.md", str(project))
    assert ok is True
    on_disk = pending.read_text()
    assert "invalid_at:" in on_disk
    assert "invalid_at: ~" not in on_disk

    rows = conn.execute("SELECT path FROM entries WHERE path=?",
                        (".llm/pending/fact_bad.md",)).fetchall()
    assert rows == []
    conn.close()


def test_stats_aggregates(project):
    _write(project / ".llm" / "context" / "c1.md",
           "---\ntype: constraint\nvalid_at: 2026-05-01\nconfidence: high\n"
           "source: human\napproved_by: jess\n---\n\nNo secrets in env.\n")
    _write(project / ".llm" / "pending" / "p1.md",
           "---\ntype: fact\nvalid_at: 2026-05-29\nconfidence: medium\n"
           "source: ai-proposed\napproved_by: ~\n---\n\nNew claim.\n")
    store.index(str(project))
    conn = store.connect(str(project))
    s = store.stats(conn)
    conn.close()
    assert s["total"] >= 2
    assert s["pending"] == 1
    assert s["constraints"] >= 1
    assert "fact" in s["by_type"] or "constraint" in s["by_type"]


# ── Confidence decay ──────────────────────────────────────────────────────────

def test_effective_confidence_high_stays_high_when_fresh():
    today = datetime.date.today().isoformat()
    eff, age = store.effective_confidence("high", today, None)
    assert eff == "high"
    assert age == 0


def test_effective_confidence_high_decays_to_medium():
    long_ago = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
    eff, age = store.effective_confidence("high", long_ago, None)
    assert eff == "medium"
    assert age == 90


def test_effective_confidence_high_decays_to_low_after_long_period():
    very_old = (datetime.date.today() - datetime.timedelta(days=200)).isoformat()
    eff, _ = store.effective_confidence("high", very_old, None)
    assert eff == "low"


def test_effective_confidence_low_stays_low():
    very_old = (datetime.date.today() - datetime.timedelta(days=300)).isoformat()
    eff, _ = store.effective_confidence("low", very_old, None)
    assert eff == "low"


def test_stale_high_confidence_lists_decayed(project):
    long_ago = (datetime.date.today() - datetime.timedelta(days=200)).isoformat()
    _write(project / ".llm" / "context" / "old_high.md",
           f"---\ntype: fact\ntopic: old\nvalid_at: {long_ago}\nconfidence: high\n"
           "source: human\napproved_by: jess\n---\n\nWas true once.\n")
    store.index(str(project))
    conn = store.connect(str(project))
    decayed = store.stale_high_confidence(conn)
    conn.close()
    paths = [d["path"] for d in decayed]
    assert ".llm/context/old_high.md" in paths
