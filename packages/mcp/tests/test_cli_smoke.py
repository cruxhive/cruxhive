"""CLI entry point smoke tests — invoke each `cruxhive-*` binary via subprocess.

These don't replace the deeper unit tests; they verify the CLI surface
hasn't broken: exit codes, output shape, basic flag parsing.

Some commands require `cruxhive-mcp` to be installed (uv tool install).
If the binary isn't on PATH we skip — these tests are most useful in CI
where the package is freshly installed before running.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _bin_available(name: str) -> bool:
    return shutil.which(name) is not None


def _run(args: list[str], cwd: Path | None = None, stdin: str | None = None) -> tuple[int, str, str]:
    """Run a CLI and return (returncode, stdout, stderr)."""
    r = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True,
        input=stdin, timeout=30,
        env={"CRUXHIVE_ANALYTICS": "0", "HOME": str(cwd) if cwd else None, "PATH": __import__("os").environ.get("PATH", "")},
    )
    return r.returncode, r.stdout, r.stderr


@pytest.fixture
def initialized_project(tmp_path):
    """A bare CruxHive project structure (skip cruxhive-init, just create the layout)."""
    (tmp_path / ".llm" / "context").mkdir(parents=True)
    (tmp_path / ".llm" / "plans").mkdir()
    (tmp_path / ".llm" / "memory").mkdir()
    (tmp_path / ".llm" / "pending").mkdir()
    (tmp_path / ".llm" / "CONTEXT.md").write_text(
        "---\ntype: fact\ntopic: project-context\nvalid_at: 2026-05-29\n"
        "confidence: high\nsource: human\napproved_by: alice\n---\n\nA test project.\n"
    )
    return tmp_path


# ── cruxhive-index ────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-index"), reason="cruxhive-index not on PATH")
def test_cruxhive_index_runs_clean(initialized_project):
    code, out, err = _run(["cruxhive-index"], cwd=initialized_project)
    assert code == 0, f"stdout: {out}\nstderr: {err}"
    assert "Indexed" in out


@pytest.mark.skipif(not _bin_available("cruxhive-index"), reason="cruxhive-index not on PATH")
def test_cruxhive_index_rebuild_flag(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)  # first pass
    code, out, _ = _run(["cruxhive-index", "--rebuild"], cwd=initialized_project)
    assert code == 0
    assert "rebuild" in out.lower() or "Indexed" in out


# ── cruxhive-search ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-search"), reason="cruxhive-search not on PATH")
def test_cruxhive_search_returns_json(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)
    code, out, _ = _run(["cruxhive-search", "test"], cwd=initialized_project)
    assert code == 0
    # Output must be valid JSON
    data = json.loads(out)
    assert isinstance(data, list)


@pytest.mark.skipif(not _bin_available("cruxhive-search"), reason="cruxhive-search not on PATH")
def test_cruxhive_search_usage_on_no_args(initialized_project):
    code, _, err = _run(["cruxhive-search"], cwd=initialized_project)
    assert code != 0
    assert "Usage" in err or "usage" in err.lower()


# ── cruxhive-propose ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-propose"), reason="cruxhive-propose not on PATH")
def test_cruxhive_propose_writes_file(initialized_project):
    code, out, _ = _run(
        ["cruxhive-propose", "fact", "test-topic"],
        cwd=initialized_project,
        stdin="A simple test fact.",
    )
    assert code == 0
    files = list((initialized_project / ".llm" / "pending").glob("fact_test-topic*.md"))
    assert len(files) == 1


@pytest.mark.skipif(not _bin_available("cruxhive-propose"), reason="cruxhive-propose not on PATH")
def test_cruxhive_propose_rejects_invalid_type(initialized_project):
    code, _, err = _run(
        ["cruxhive-propose", "bogus", "topic"],
        cwd=initialized_project,
        stdin="content",
    )
    assert code != 0
    assert "Invalid" in err or "invalid" in err.lower()


# ── cruxhive-review (lists pending as JSON) ──────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-review"), reason="cruxhive-review not on PATH")
def test_cruxhive_review_returns_json(initialized_project):
    # File a proposal first
    _run(["cruxhive-propose", "fact", "review-test"],
         cwd=initialized_project, stdin="content")
    code, out, _ = _run(["cruxhive-review"], cwd=initialized_project)
    assert code == 0
    data = json.loads(out)
    assert isinstance(data, list)
    assert any("review-test" in (e.get("path") or "") for e in data)


# ── cruxhive-stats ────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-stats"), reason="cruxhive-stats not on PATH")
def test_cruxhive_stats_runs(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)
    code, out, _ = _run(["cruxhive-stats"], cwd=initialized_project)
    assert code == 0
    assert "CruxHive stats" in out or "cruxhive stats" in out.lower()


@pytest.mark.skipif(not _bin_available("cruxhive-stats"), reason="cruxhive-stats not on PATH")
def test_cruxhive_stats_json_mode(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)
    code, out, _ = _run(["cruxhive-stats", "--json"], cwd=initialized_project)
    assert code == 0
    data = json.loads(out)
    assert "summary" in data or "knowledge_base" in data


# ── cruxhive-status ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-status"), reason="cruxhive-status not on PATH")
def test_cruxhive_status_quiet_silent_when_clean(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)
    code, out, _ = _run(["cruxhive-status", "--quiet"], cwd=initialized_project)
    assert code == 0
    # No output expected when nothing is actionable
    assert out.strip() == ""


@pytest.mark.skipif(not _bin_available("cruxhive-status"), reason="cruxhive-status not on PATH")
def test_cruxhive_status_json_mode(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)
    code, out, _ = _run(["cruxhive-status", "--json"], cwd=initialized_project)
    assert code == 0
    data = json.loads(out)
    assert "pending" in data
    assert "gaps_30d" in data


# ── cruxhive-doctor ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-doctor"), reason="cruxhive-doctor not on PATH")
def test_cruxhive_doctor_reports_findings(initialized_project):
    code, out, _ = _run(["cruxhive-doctor"], cwd=initialized_project)
    # Exit code can be 0 (all green) or 1 (problems found); both legitimate.
    assert code in (0, 1)
    assert "CruxHive doctor" in out


# ── cruxhive-digest ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-digest"), reason="cruxhive-digest not on PATH")
def test_cruxhive_digest_produces_markdown(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)
    code, out, _ = _run(["cruxhive-digest"], cwd=initialized_project)
    assert code == 0
    assert "# CruxHive digest" in out
    assert "## Key indicators" in out or "## Snapshot" in out


@pytest.mark.skipif(not _bin_available("cruxhive-digest"), reason="cruxhive-digest not on PATH")
def test_cruxhive_digest_json_mode(initialized_project):
    _run(["cruxhive-index"], cwd=initialized_project)
    code, out, _ = _run(["cruxhive-digest", "--json", "--no-save"], cwd=initialized_project)
    assert code == 0
    data = json.loads(out)
    assert "kpis" in data
    assert "project" in data


# ── cruxhive-solo ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-solo"), reason="cruxhive-solo not on PATH")
def test_cruxhive_solo_status_runs(tmp_path):
    """--status should never modify state; exit clean."""
    code, out, _ = _run(["cruxhive-solo", "--status"], cwd=tmp_path)
    assert code == 0
    assert "Solo mode" in out


# ── cruxhive-direnv ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-direnv"), reason="cruxhive-direnv not on PATH")
def test_cruxhive_direnv_writes_envrc(tmp_path):
    code, out, _ = _run(["cruxhive-direnv", "--client", "cursor"], cwd=tmp_path)
    assert code == 0
    envrc = tmp_path / ".envrc"
    assert envrc.exists()
    body = envrc.read_text()
    assert "CRUXHIVE_CLIENT" in body
    assert "cursor" in body


# ── cruxhive-workspace ────────────────────────────────────────────────────────

@pytest.mark.skipif(not _bin_available("cruxhive-workspace"), reason="cruxhive-workspace not on PATH")
def test_cruxhive_workspace_handles_no_projects(tmp_path):
    """When there are no discoverable projects, exit cleanly with a message."""
    code, out, _ = _run(["cruxhive-workspace"], cwd=tmp_path)
    assert code == 0
    # Either "No CruxHive projects found" or the regular table with 0 projects.
    assert "No CruxHive projects" in out or "Aggregate" in out


@pytest.mark.skipif(not _bin_available("cruxhive-workspace"), reason="cruxhive-workspace not on PATH")
def test_cruxhive_workspace_json_mode(tmp_path):
    code, out, _ = _run(["cruxhive-workspace", "--json"], cwd=tmp_path)
    assert code == 0
    data = json.loads(out)
    assert "aggregate" in data
    assert "projects" in data
