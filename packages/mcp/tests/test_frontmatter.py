"""Frontmatter parser must round-trip and handle the edge cases that real entries hit."""
from cruxhive_mcp.frontmatter import parse, set_field


SAMPLE = """\
---
type: constraint
scope: project
topic: auth
valid_at: 2026-05-29
invalid_at: ~
confidence: high
source: human
approved_by: jane
---

# Body

Real content here.
"""


def test_parse_basic_fields():
    meta, body = parse(SAMPLE)
    assert meta["type"] == "constraint"
    assert meta["scope"] == "project"
    assert meta["topic"] == "auth"
    assert meta["approved_by"] == "jane"
    assert "# Body" in body
    assert "Real content here." in body


def test_parse_no_frontmatter():
    meta, body = parse("Just a body with no frontmatter.\n")
    assert meta == {}
    assert body.startswith("Just a body")


def test_set_field_replaces_existing():
    new = set_field(SAMPLE, "approved_by", "rob")
    meta, _ = parse(new)
    assert meta["approved_by"] == "rob"


def test_set_field_adds_missing_field():
    src = """---
type: fact
---

body
"""
    new = set_field(src, "topic", "hello")
    meta, _ = parse(new)
    assert meta["topic"] == "hello"
    # Existing field still present
    assert meta["type"] == "fact"


def test_invalid_at_null_marker_preserved():
    meta, _ = parse(SAMPLE)
    assert meta["invalid_at"] == "~"


def test_set_field_roundtrip():
    new = set_field(SAMPLE, "invalid_at", "2026-12-01")
    meta, body = parse(new)
    assert meta["invalid_at"] == "2026-12-01"
    assert "# Body" in body
