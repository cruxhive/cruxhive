"""Workspace-level rollup across multiple CruxHive projects.

Reads ~/.cruxhive/config.yaml (or scans a default directory) for project
paths, then aggregates KPIs across all of them. Used by the
`cruxhive workspace` CLI and the workspace mode of the web UI.

No new metrics collected — this just sums up per-project snapshots.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


DEFAULT_SCAN = Path.home() / "Projects_Local" / "Development"


def _parse_simple_yaml(text: str) -> dict:
    """Minimal YAML parser for the keys we actually use.

    Supports flat `key: value` and `key: \\n  - item` lists. Good enough for
    a config that holds a scan path and a project list, without dragging in
    PyYAML as a runtime dependency.
    """
    out: dict = {}
    current_list_key: str | None = None
    section: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith(" "):
            # Top-level key
            current_list_key = None
            if ":" in raw:
                k, _, v = raw.partition(":")
                k = k.strip()
                v = v.strip()
                if not v:
                    section = k
                    out[k] = {}
                else:
                    section = None
                    out[k] = _coerce(v)
        else:
            # Indented under section
            stripped = raw.strip()
            if section is None:
                continue
            if stripped.startswith("- "):
                key = current_list_key or "_items"
                out[section].setdefault(key, [])
                out[section][key].append(stripped[2:].strip())
            elif ":" in stripped:
                k, _, v = stripped.partition(":")
                k = k.strip()
                v = v.strip()
                if not v:
                    current_list_key = k
                    out[section][k] = []
                else:
                    current_list_key = None
                    out[section][k] = _coerce(v)
    return out


def _coerce(v: str):
    v = v.strip()
    if v.lower() in {"true", "yes"}: return True
    if v.lower() in {"false", "no"}: return False
    try:
        if "." in v: return float(v)
        return int(v)
    except ValueError:
        return v.strip('"\'')


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def load_config() -> dict:
    """Return the workspace config dict, or {} if no config file present."""
    cfg_path = Path.home() / ".cruxhive" / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        return _parse_simple_yaml(cfg_path.read_text())
    except Exception:
        return {}


def list_projects(scan: Path | None = None) -> list[Path]:
    """Return absolute paths of CruxHive-initialized projects.

    Priority order:
      1. config.yaml `workspace.projects:` list
      2. config.yaml `workspace.scan:` directory
      3. `scan` argument
      4. DEFAULT_SCAN (~/Projects_Local/Development)
    """
    cfg = load_config().get("workspace", {})
    if isinstance(cfg.get("projects"), list) and cfg["projects"]:
        paths = [_expand(p) for p in cfg["projects"]]
        return [p for p in paths if (p / ".llm" / "cruxhive.db").exists()]

    scan_path: Path
    if cfg.get("scan"):
        scan_path = _expand(cfg["scan"])
    elif scan:
        scan_path = scan
    else:
        scan_path = DEFAULT_SCAN

    if not scan_path.exists():
        return []

    out: list[Path] = []
    for child in sorted(scan_path.iterdir()):
        if child.is_dir() and (child / ".llm" / "cruxhive.db").exists():
            out.append(child)
    return out


def collect_all(days: int = 7) -> list[dict]:
    """Run _collect_snapshot for every workspace project. Returns list of snapshots."""
    from . import cli as _cli

    out: list[dict] = []
    for root in list_projects():
        try:
            snap = _cli._collect_snapshot(str(root), days=days)
            out.append(snap)
        except Exception as e:
            out.append({
                "date": "",
                "project": root.name,
                "root": str(root),
                "error": str(e),
            })
    return out


def aggregate(snapshots: list[dict]) -> dict:
    """Sum KPIs across all per-project snapshots into a workspace-wide view."""
    total = {
        "projects": len(snapshots),
        "total_entries": 0,
        "constraints": 0,
        "pending_count": 0,
        "decayed_count": 0,
        "searches": 0,
        "hits": 0,
        "total_calls": 0,
        "proposals": 0,
    }
    for s in snapshots:
        k = s.get("kpis") or {}
        ev = s.get("events") or {}
        total["total_entries"] += k.get("total_entries", 0)
        total["constraints"] += k.get("constraints", 0)
        total["pending_count"] += k.get("pending_count", 0)
        total["decayed_count"] += k.get("decayed_count", 0)
        total["searches"] += k.get("searches", 0)
        total["hits"] += ev.get("hits", 0)
        total["total_calls"] += k.get("total_calls", 0)
        total["proposals"] += k.get("proposals", 0)
    total["hit_rate"] = (total["hits"] / total["searches"]) if total["searches"] else 0.0
    total["decay_ratio"] = (total["decayed_count"] / total["total_entries"]) if total["total_entries"] else 0.0
    return total
