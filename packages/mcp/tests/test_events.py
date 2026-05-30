"""Observability log: schema, summary, by_tool, gaps, opt-out."""
import os
from pathlib import Path

import pytest

from cruxhive_mcp import events, store


@pytest.fixture(autouse=True)
def force_enable(monkeypatch):
    # Tests must opt in to logging — default fixture turns it on
    monkeypatch.setenv("CRUXHIVE_ANALYTICS", "1")


def test_log_writes_row(project):
    events.set_client("test-client", "1.0")
    events.log(str(project), "context_search", query="hetzner", result_n=3, ms=12)
    conn = store.connect(str(project))
    n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()
    assert n == 1


def test_log_respects_opt_out(project, monkeypatch):
    monkeypatch.setenv("CRUXHIVE_ANALYTICS", "0")
    events.log(str(project), "context_search", query="nope", result_n=0, ms=5)
    conn = store.connect(str(project))
    n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()
    assert n == 0


def test_summary_computes_hit_rate(project):
    events.set_client("claude-code", "1.0")
    events.log(str(project), "context_search", query="a", result_n=2, ms=10)
    events.log(str(project), "context_search", query="b", result_n=0, ms=8)
    events.log(str(project), "context_search", query="c", result_n=5, ms=12)
    events.log(str(project), "context_propose", query="topic", ms=20)

    conn = store.connect(str(project))
    s = events.summary(conn, days=7)
    conn.close()
    assert s["searches"] == 3
    assert s["hits"] == 2
    assert s["proposals"] == 1
    assert 0.66 < s["hit_rate"] < 0.67


def test_by_tool_groups_distinct_clients(project):
    events.set_client("claude-code", "1.0")
    events.log(str(project), "context_search", query="x", result_n=1, ms=8)

    events.set_client("opencode", "0.1")
    events.log(str(project), "context_search", query="y", result_n=0, ms=10)
    events.log(str(project), "context_search", query="z", result_n=2, ms=9)

    conn = store.connect(str(project))
    rows = events.by_tool(conn, days=7)
    conn.close()
    clients = {r["client"]: r for r in rows}
    assert "claude-code" in clients
    assert "opencode" in clients
    assert clients["opencode"]["searches"] == 2
    assert clients["opencode"]["zero_results"] == 1


def test_top_gaps_only_returns_zero_result_queries(project):
    events.set_client("claude-code", "1.0")
    events.log(str(project), "context_search", query="hetzner ip", result_n=0, ms=5)
    events.log(str(project), "context_search", query="hetzner ip", result_n=0, ms=5)
    events.log(str(project), "context_search", query="found this", result_n=3, ms=5)

    conn = store.connect(str(project))
    gaps = events.top_gaps(conn, days=30)
    conn.close()
    queries = [g["query"] for g in gaps]
    assert "hetzner ip" in queries
    assert "found this" not in queries
    miss = next(g for g in gaps if g["query"] == "hetzner ip")
    assert miss["times"] == 2


def test_pending_age_returns_zero_when_no_pending(project):
    store.index(str(project))
    conn = store.connect(str(project))
    p = events.pending_age(conn)
    conn.close()
    assert p["count"] == 0
    assert p["oldest_days"] == 0
