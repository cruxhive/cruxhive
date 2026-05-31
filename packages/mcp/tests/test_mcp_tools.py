"""MCP tools — the AI-facing surface.

Tests the registered MCP tools by reaching into FastMCP's tool manager
and invoking the function directly. This is the closest we get to
testing what an actual AI client would see when calling these tools.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mcp.server.fastmcp import FastMCP

from cruxhive_mcp import events as _events
from cruxhive_mcp import store as _store
from cruxhive_mcp.tools.knowledge import register as register_knowledge


@pytest.fixture
def tools(project, monkeypatch):
    """A FastMCP instance with all knowledge tools registered.

    Returns dict {tool_name: callable} so tests can do `tools['context_search'](...)`.
    """
    # Pin the cwd inside tools' os.getcwd() calls
    monkeypatch.chdir(project)
    # Reset events client state so tests are independent
    monkeypatch.setenv("CRUXHIVE_ANALYTICS", "0")
    _events._session_id.set("")
    _events._client_name.set("")
    _events._client_ver.set("")

    m = FastMCP("test")
    register_knowledge(m)
    return {name: t.fn for name, t in m._tool_manager._tools.items()}


@pytest.fixture
def seeded_project(project):
    """A project with a few approved entries already indexed."""
    (project / ".llm" / "context").mkdir(exist_ok=True)
    (project / ".llm" / "context" / "auth.md").write_text(
        "---\ntype: decision\nscope: project\ntopic: auth\n"
        "valid_at: 2026-05-29\nconfidence: high\nsource: human\napproved_by: alice\n---\n\n"
        "We use Logto for OIDC. Tokens are validated server-side."
    )
    (project / ".llm" / "context" / "database.md").write_text(
        "---\ntype: constraint\nscope: project\ntopic: database\n"
        "valid_at: 2026-05-29\nconfidence: high\nsource: human\napproved_by: alice\n---\n\n"
        "Never use raw SQL strings — always parameterized queries."
    )
    _store.index(str(project))
    return project


# ── context_index ─────────────────────────────────────────────────────────────

def test_context_index_returns_count(tools, project):
    (project / ".llm" / "context" / "thing.md").write_text(
        "---\ntype: fact\ntopic: x\nvalid_at: 2026-05-29\n"
        "confidence: high\nsource: human\napproved_by: alice\n---\n\nA fact."
    )
    result = tools["context_index"](project_root=str(project))
    assert "Indexed" in result
    assert "→ .llm/cruxhive.db" in result


# ── context_search ─────────────────────────────────────────────────────────────

def test_context_search_returns_matching_entry(tools, seeded_project):
    result = tools["context_search"](query="auth", n=5, project_root=str(seeded_project))
    assert "auth.md" in result
    assert "Results for" in result


def test_context_search_filters_by_type(tools, seeded_project):
    result = tools["context_search"](
        query="database", n=5, type="constraint", project_root=str(seeded_project)
    )
    # Only constraint should match
    assert "database.md" in result
    # auth.md is a decision, not a constraint — should be filtered out
    assert "auth.md" not in result


def test_context_search_empty_kb_message(tools, project):
    result = tools["context_search"](query="anything", n=5, project_root=str(project))
    # Project fixture has one entry (CONTEXT.md) but not indexed yet
    # Either we get "empty" or "no results", both acceptable
    assert "empty" in result.lower() or "no results" in result.lower() or "results for" in result.lower()


def test_context_search_decay_markers_in_output(tools, project):
    import datetime
    long_ago = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
    (project / ".llm" / "context" / "old.md").write_text(
        f"---\ntype: fact\ntopic: legacy\nvalid_at: {long_ago}\n"
        "confidence: high\nsource: human\napproved_by: alice\n---\n\nlegacy fact that is now old and stale."
    )
    _store.index(str(project))
    result = tools["context_search"](query="legacy", n=5, project_root=str(project))
    # Old high-confidence entries should be marked as stale/decayed
    assert "stale" in result or "high→medium" in result or "high→low" in result


# ── context_propose ───────────────────────────────────────────────────────────

def test_context_propose_writes_pending_file(tools, project, monkeypatch):
    # Make sure solo mode is OFF — proposals should land in pending
    monkeypatch.delenv("CRUXHIVE_SOLO", raising=False)
    monkeypatch.delenv("CRUXHIVE_APPROVER", raising=False)
    fake_home = project / "_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    result = tools["context_propose"](
        type="constraint",
        topic="rate-limit",
        content="Always rate-limit external API calls to 10/sec.",
        project_root=str(project),
    )
    assert "Proposed:" in result or "Written:" in result
    # File should exist
    pending = project / ".llm" / "pending"
    assert pending.exists()
    files = list(pending.glob("constraint_rate-limit*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "source: ai-proposed" in content
    assert "approved_by: ~" in content


def test_context_propose_solo_mode_auto_approves(tools, project, monkeypatch):
    monkeypatch.setenv("CRUXHIVE_SOLO", "1")
    monkeypatch.setenv("CRUXHIVE_APPROVER", "tester")
    result = tools["context_propose"](
        type="fact",
        topic="solo-test",
        content="Some fact established in a solo session.",
        project_root=str(project),
    )
    assert "Written:" in result or "auto-approved" in result
    files = list((project / ".llm" / "pending").glob("fact_solo-test*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "source: human" in content
    assert "approved_by: tester" in content


def test_context_propose_ephemeral_sets_correct_source(tools, project, monkeypatch):
    monkeypatch.delenv("CRUXHIVE_SOLO", raising=False)
    result = tools["context_propose"](
        type="research",
        topic="quick-note",
        content="Brief observation that will auto-expire.",
        ephemeral=True,
        project_root=str(project),
    )
    assert "ephemeral" in result.lower() or "Filed" in result
    files = list((project / ".llm" / "pending").glob("research_quick-note*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "source: ephemeral" in content
    assert "confidence: low" in content


def test_context_propose_rejects_invalid_type(tools, project):
    result = tools["context_propose"](
        type="bogus-type",
        topic="anything",
        content="...",
        project_root=str(project),
    )
    assert "Invalid type" in result


# ── context_review ────────────────────────────────────────────────────────────

def test_context_review_lists_pending(tools, project, monkeypatch):
    monkeypatch.delenv("CRUXHIVE_SOLO", raising=False)
    monkeypatch.setenv("HOME", str(project / "_home"))
    (project / "_home").mkdir(exist_ok=True)
    # File a proposal so there's something to review
    tools["context_propose"](
        type="pattern", topic="error-handling",
        content="Always wrap external calls in retry-with-backoff.",
        project_root=str(project),
    )
    result = tools["context_review"](project_root=str(project))
    assert "pending proposal" in result.lower()
    assert "error-handling" in result or "pattern_error-handling" in result


def test_context_review_empty_when_clean(tools, seeded_project):
    result = tools["context_review"](project_root=str(seeded_project))
    assert "No pending" in result or "fully reviewed" in result.lower()


# ── context_approve / reject ─────────────────────────────────────────────────

def test_context_approve_flips_source_to_human(tools, project, monkeypatch):
    monkeypatch.delenv("CRUXHIVE_SOLO", raising=False)
    monkeypatch.setenv("HOME", str(project / "_home"))
    (project / "_home").mkdir(exist_ok=True)
    tools["context_propose"](
        type="fact", topic="approve-test",
        content="A claim to be approved.",
        project_root=str(project),
    )
    pending_files = list((project / ".llm" / "pending").glob("fact_approve-test*.md"))
    assert len(pending_files) == 1
    rel_path = str(pending_files[0].relative_to(project))

    result = tools["context_approve"](
        path=rel_path, approver="alice", project_root=str(project),
    )
    assert "Approved" in result or "approved" in result
    on_disk = pending_files[0].read_text()
    assert "source: human" in on_disk
    assert "approved_by: alice" in on_disk


def test_context_reject_marks_invalid(tools, project, monkeypatch):
    monkeypatch.delenv("CRUXHIVE_SOLO", raising=False)
    monkeypatch.setenv("HOME", str(project / "_home"))
    (project / "_home").mkdir(exist_ok=True)
    tools["context_propose"](
        type="fact", topic="reject-test",
        content="A claim to be rejected.",
        project_root=str(project),
    )
    pending_files = list((project / ".llm" / "pending").glob("fact_reject-test*.md"))
    rel_path = str(pending_files[0].relative_to(project))

    result = tools["context_reject"](path=rel_path, project_root=str(project))
    assert "Rejected" in result or "rejected" in result
    on_disk = pending_files[0].read_text()
    assert "invalid_at:" in on_disk
    assert "invalid_at: ~" not in on_disk


def test_context_approve_returns_not_found_for_bogus_path(tools, project):
    result = tools["context_approve"](
        path=".llm/pending/does-not-exist.md",
        approver="alice",
        project_root=str(project),
    )
    assert "Not found" in result or "not found" in result.lower()


# ── context_workspace_search ──────────────────────────────────────────────────

def test_context_workspace_search_aggregates_across_projects(tools, tmp_path, monkeypatch):
    """Two project dirs, each with one indexed entry; workspace search hits both."""
    fake_home = tmp_path / "_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    # Set up workspace config pointing at our two test projects
    proj_a = tmp_path / "alpha"
    proj_b = tmp_path / "beta"
    for p in (proj_a, proj_b):
        (p / ".llm" / "context").mkdir(parents=True)
    (proj_a / ".llm" / "context" / "alpha-auth.md").write_text(
        "---\ntype: decision\ntopic: auth-alpha\nvalid_at: 2026-05-29\n"
        "confidence: high\nsource: human\napproved_by: jess\n---\n\n"
        "Alpha uses Logto for auth-alpha topic."
    )
    (proj_b / ".llm" / "context" / "beta-auth.md").write_text(
        "---\ntype: decision\ntopic: auth-beta\nvalid_at: 2026-05-29\n"
        "confidence: high\nsource: human\napproved_by: jess\n---\n\n"
        "Beta uses Auth0 for auth-beta topic."
    )
    _store.index(str(proj_a))
    _store.index(str(proj_b))

    cfg_path = fake_home / ".cruxhive" / "config.yaml"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        f"workspace:\n  projects:\n    - {proj_a}\n    - {proj_b}\n"
    )

    result = tools["context_workspace_search"](query="auth", n=8)
    # Both project results should appear, tagged with project name
    assert "alpha" in result
    assert "beta" in result


def test_context_workspace_search_empty_message_when_no_results(tools, tmp_path, monkeypatch):
    fake_home = tmp_path / "_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    cfg_path = fake_home / ".cruxhive" / "config.yaml"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text("workspace:\n  projects: []\n")

    result = tools["context_workspace_search"](query="anything-at-all", n=5)
    assert "No results" in result or "no results" in result.lower()


# ── context_check_faithfulness ────────────────────────────────────────────────

def test_check_faithfulness_returns_message_when_no_constraints(tools, project):
    """With no approved constraints, the tool should say so cleanly."""
    result = tools["context_check_faithfulness"](
        response="The auth system uses cookies.",
        project_root=str(project),
    )
    assert "No approved constraints" in result or "no approved constraints" in result.lower()


def test_check_faithfulness_graceful_when_nli_missing(tools, seeded_project):
    """When NLI model isn't installed, fall back to listing constraints for manual check."""
    # seeded_project has 1 constraint (the "never use raw SQL" one)
    result = tools["context_check_faithfulness"](
        response="We will execute the user's query as raw SQL for speed.",
        project_root=str(seeded_project),
    )
    # Either NLI ran (full extra installed) or it gave the manual-check fallback message
    assert (
        "violation" in result.lower()
        or "no faithfulness" in result.lower()
        or "NLI checker not installed" in result
        or "Constraints to check manually" in result
    )
