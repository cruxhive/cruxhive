"""Shared test fixtures."""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal CruxHive project root with .llm/ scaffolding."""
    (tmp_path / ".llm" / "plans").mkdir(parents=True)
    (tmp_path / ".llm" / "context").mkdir()
    (tmp_path / ".llm" / "memory").mkdir()
    (tmp_path / ".llm" / "pending").mkdir()
    # A simple CONTEXT.md so index has something to find. valid_at is relative:
    # a hardcoded date ages past store._DECAY_HIGH_DAYS and starts failing
    # decay-sensitive tests on a calendar rather than on a code change.
    (tmp_path / ".llm" / "CONTEXT.md").write_text(
        "---\n"
        "type: fact\n"
        "scope: project\n"
        "topic: project-context\n"
        f"valid_at: {_dt.date.today().isoformat()}\n"
        "confidence: high\n"
        "source: human\n"
        "approved_by: tester\n"
        "---\n\n"
        "# Test project\n\nA tiny fixture.\n"
    )
    return tmp_path


@pytest.fixture
def no_analytics(monkeypatch):
    """Disable event logging during tests by default."""
    monkeypatch.setenv("CRUXHIVE_ANALYTICS", "0")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME so the personal layer doesn't pollute the user's machine.

    Autouse: store._personal_root() is resolved from Path.home() on every
    call (not cached), so this is enough to isolate it — but without
    autouse, a test's exact-match assertion only fails on a machine that
    already has a real ~/.cruxhive/personal/ (silently green in CI, silently
    red on a real dev machine). Applies to every test, not just ones that
    opt in, since any test with an exact-match assertion is at risk.

    Deliberately does NOT mkdir fake_home: several tests create
    tmp_path/"_home" themselves (directly or via `project`, which is
    tmp_path) before writing under it — pre-creating it here would collide
    with their own `.mkdir()`. Path.home() doesn't require the path to
    exist, and store._personal_root().exists() already treats a missing
    personal tier as "nothing to scan", which is exactly what we want here.
    """
    fake_home = tmp_path / "_home"
    monkeypatch.setenv("HOME", str(fake_home))
    return fake_home
