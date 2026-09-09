"""Relevance floor for the UserPromptSubmit hook (`cruxhive-inject`).

`store.fts_or_query` ORs every token in the prompt and nothing downstream
applied a score threshold, so a single stray word match was enough to pull a
document into the injected context of every turn — and the injected block tells
the model to treat decisions/constraints as binding. These tests pin the floor
that stops one-word coincidences without hurting genuine topical retrieval.
"""
from pathlib import Path

from cruxhive_mcp import cli, store


def _write(p: Path, body: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _candidates(conn, query):
    bm25 = store.search_bm25(conn, query, 8)
    return store.rrf_fuse(bm25, [], conn=conn, query=query)[:6]


def _seeded(project):
    _write(project / ".llm" / "context" / "ops.md",
           "---\ntype: constraint\ntopic: ops-resilience\nvalid_at: 2026-05-01\n"
           "confidence: high\nsource: human\napproved_by: tester\n---\n\n"
           "Rollback gates must be green before we proceed with a production change.\n")
    store.index(str(project))
    return store.connect(str(project))


def test_single_token_coincidence_is_dropped(project):
    """'proceed' alone must not drag an ops constraint into an unrelated turn."""
    conn = _seeded(project)
    query = "proceed as instructed"  # 'proceed' matches; 'instructed' does not
    before = _candidates(conn, query)
    assert any(h["path"].endswith("ops.md") for h in before), "fixture no longer reproduces"
    assert cli._relevance_floor(conn, before, query) == []
    conn.close()


def test_genuine_topical_query_survives(project):
    conn = _seeded(project)
    query = "rollback gates before a production change"
    kept = cli._relevance_floor(conn, _candidates(conn, query), query)
    assert [h["path"] for h in kept] == [".llm/context/ops.md"]
    conn.close()


def test_prompt_with_too_few_content_words_retrieves_nothing(project):
    """A prompt carrying one usable word can't clear the bar."""
    conn = _seeded(project)
    query = "proceed"
    assert cli._relevance_floor(conn, _candidates(conn, query), query) == []
    conn.close()


def test_filtering_failure_never_blocks_the_prompt(project):
    """The hook's contract is to never break a turn — degrade to unfiltered."""
    conn = _seeded(project)
    query = "rollback gates before a production change"
    hits = _candidates(conn, query)
    conn.close()  # a closed connection makes the lookup raise
    assert cli._relevance_floor(conn, hits, query) == hits


# ── Pending-queue nudge ────────────────────────────────────────────────────────

def _run_inject(project, prompt, capsys, monkeypatch):
    import io
    import json

    payload = json.dumps({"prompt": prompt, "cwd": str(project)})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    cli.inject()
    return capsys.readouterr().out


def _seed_pending(project, n):
    for i in range(n):
        _write(
            project / ".llm" / "pending" / f"fact_pending-{i}.md",
            f"---\ntype: fact\ntopic: pending-{i}\nvalid_at: 2026-05-29\n"
            "confidence: medium\nsource: ai-proposed\napproved_by: ~\n---\n\n"
            f"Pending claim number {i}.\n",
        )


def test_nudge_appears_when_pending_at_least_three(project, capsys, monkeypatch):
    conn = _seeded(project)
    conn.close()
    _seed_pending(project, 3)
    store.index(str(project))

    out = _run_inject(project, "rollback gates before a production change", capsys, monkeypatch)
    assert "3 proposals pending your review" in out
    assert "cruxhive review" in out


def test_nudge_absent_when_pending_below_three(project, capsys, monkeypatch):
    conn = _seeded(project)
    conn.close()
    _seed_pending(project, 2)
    store.index(str(project))

    out = _run_inject(project, "rollback gates before a production change", capsys, monkeypatch)
    assert "pending your review" not in out
