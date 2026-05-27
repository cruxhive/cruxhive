"""Minimal YAML frontmatter parser — no external deps."""
from __future__ import annotations

import re


def parse(text: str) -> tuple[dict[str, str], str]:
    """Return (metadata_dict, body). Keys are lowercased, values stripped."""
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip()
    return meta, text[m.end():]


def set_field(text: str, key: str, value: str) -> str:
    """Set or add a frontmatter field in-place. Returns updated text."""
    pattern = rf"(^---\n.*?)(^{re.escape(key)}\s*:.*?\n)(.*?---\n)"
    replacement = rf"\g<1>{key}: {value}\n\g<3>"
    updated = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL | re.MULTILINE)
    if updated == text:
        # Field not present — insert before closing ---
        updated = re.sub(r"(^---\n)(.*?)(^---\n)", rf"\1\2{key}: {value}\n\3", text, count=1, flags=re.DOTALL | re.MULTILINE)
    return updated
