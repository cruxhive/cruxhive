"""Shared test fixtures."""
from __future__ import annotations

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
    # A simple CONTEXT.md so index has something to find
    (tmp_path / ".llm" / "CONTEXT.md").write_text(
        "---\n"
        "type: fact\n"
        "scope: project\n"
        "topic: project-context\n"
        "valid_at: 2026-05-01\n"
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


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME so the personal layer doesn't pollute the user's machine."""
    fake_home = tmp_path / "_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    # Some libs read Path.home(), which uses pwd not HOME on macOS. Reload module.
    return fake_home
