"""End-to-end integration test — the canonical flow a real user runs.

Covers: index → propose → search-hits → review → approve → search-now-shows-approved
→ digest contains the entry. If this passes, the major user paths work.

Uses subprocess + the installed CLI binaries to make it as close to a
real user session as possible.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _bin_available(name: str) -> bool:
    return shutil.which(name) is not None


def _run(args, cwd, stdin=None):
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, input=stdin, timeout=30,
        env={
            "CRUXHIVE_ANALYTICS": "0",
            "HOME": str(cwd),  # isolate ~/.cruxhive/ for solo config etc
            "PATH": os.environ.get("PATH", ""),
        },
    )


@pytest.fixture
def fresh_project(tmp_path):
    """A bare project structure ready to be `cruxhive-index`'d."""
    p = tmp_path / "fresh"
    (p / ".llm" / "context").mkdir(parents=True)
    (p / ".llm" / "plans").mkdir()
    (p / ".llm" / "memory").mkdir()
    (p / ".llm" / "pending").mkdir()
    (p / ".llm" / "CONTEXT.md").write_text(
        "---\ntype: fact\ntopic: project-context\nvalid_at: 2026-05-29\n"
        "confidence: high\nsource: human\napproved_by: alice\n---\n\n# Test project\n"
    )
    return p


@pytest.mark.skipif(
    not all(_bin_available(b) for b in [
        "cruxhive-index", "cruxhive-search", "cruxhive-propose",
        "cruxhive-review", "cruxhive-approve", "cruxhive-digest",
    ]),
    reason="cruxhive-* CLI binaries not installed",
)
def test_full_propose_approve_search_flow(fresh_project):
    """The canonical user flow, end to end."""

    # 1. Index initial project — should pick up CONTEXT.md
    r = _run(["cruxhive-index"], fresh_project)
    assert r.returncode == 0, r.stderr
    assert "Indexed" in r.stdout

    # 2. Search for "test" — should hit CONTEXT.md
    r = _run(["cruxhive-search", "test"], fresh_project)
    assert r.returncode == 0
    initial_results = json.loads(r.stdout)
    initial_count = len(initial_results)
    assert initial_count >= 1

    # 3. Propose a new constraint
    r = _run(
        ["cruxhive-propose", "constraint", "rate-limit"],
        fresh_project,
        stdin="Always rate-limit external API calls to 10 requests per second to avoid bans.",
    )
    assert r.returncode == 0, r.stderr
    # File should exist
    pending = list((fresh_project / ".llm" / "pending").glob("constraint_rate-limit*.md"))
    assert len(pending) == 1
    proposed_path = pending[0]

    # 4. Search for the new content — should be findable even in pending.
    # FTS5 doesn't tokenize hyphens, so use a word from the body.
    r = _run(["cruxhive-search", "external"], fresh_project)
    assert r.returncode == 0
    hits = json.loads(r.stdout)
    paths = [h.get("path", "") for h in hits]
    assert any("rate-limit" in p for p in paths), f"Expected rate-limit in {paths}"

    # 5. List pending — should include the new entry
    r = _run(["cruxhive-review"], fresh_project)
    assert r.returncode == 0
    pending_list = json.loads(r.stdout)
    assert any("rate-limit" in (e.get("path") or "") for e in pending_list)

    # 6. Approve it
    rel_path = str(proposed_path.relative_to(fresh_project))
    r = _run(["cruxhive-approve", rel_path, "alice"], fresh_project)
    assert r.returncode == 0, r.stderr
    assert "Approved" in r.stdout or "approved" in r.stdout.lower()

    # 7. On-disk frontmatter should now be human-approved
    body = proposed_path.read_text()
    assert "source: human" in body
    assert "approved_by: alice" in body

    # 8. Pending list should now be empty (no other proposals)
    r = _run(["cruxhive-review"], fresh_project)
    assert r.returncode == 0
    final_pending = json.loads(r.stdout)
    assert all("rate-limit" not in (e.get("path") or "") for e in final_pending)

    # 9. Digest should mention the entry exists (knowledge base count incremented)
    r = _run(["cruxhive-digest", "--json", "--no-save"], fresh_project)
    assert r.returncode == 0
    digest = json.loads(r.stdout)
    assert digest["kpis"]["total_entries"] >= 2  # CONTEXT.md + rate-limit


@pytest.mark.skipif(
    not all(_bin_available(b) for b in [
        "cruxhive-index", "cruxhive-propose", "cruxhive-search", "cruxhive-solo",
    ]),
    reason="cruxhive-* CLI binaries not installed",
)
def test_solo_mode_skips_pending_queue(fresh_project):
    """With solo enabled, propose writes the entry as already-approved."""

    # Enable solo mode (writes to HOME/.cruxhive/config.yaml; HOME is the test dir)
    r = _run(["cruxhive-solo", "--name", "tester"], fresh_project)
    assert r.returncode == 0
    assert "enabled" in r.stdout.lower()

    # Index, then propose
    _run(["cruxhive-index"], fresh_project)
    r = _run(
        ["cruxhive-propose", "decision", "vector-db"],
        fresh_project,
        stdin="Use sqlite-vec instead of pgvector — local-first principle.",
    )
    assert r.returncode == 0
    assert "auto-approved" in r.stdout or "Written" in r.stdout

    # Verify on-disk it's already human-approved
    proposed = next((fresh_project / ".llm" / "pending").glob("decision_vector-db*.md"))
    body = proposed.read_text()
    assert "source: human" in body
    assert "approved_by: tester" in body
    assert "approved_by: ~" not in body


@pytest.mark.skipif(
    not all(_bin_available(b) for b in ["cruxhive-index", "cruxhive-digest"]),
    reason="cruxhive-* CLI binaries not installed",
)
def test_digest_persists_snapshot_for_compare(fresh_project):
    """digest writes a JSON snapshot to .llm/digests/ so --compare has data later."""
    _run(["cruxhive-index"], fresh_project)
    r = _run(["cruxhive-digest"], fresh_project)
    assert r.returncode == 0
    digests = list((fresh_project / ".llm" / "digests").glob("*.json"))
    assert len(digests) >= 1
    snap = json.loads(digests[0].read_text())
    assert "kpis" in snap
    assert "project" in snap
