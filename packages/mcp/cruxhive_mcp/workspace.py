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


def config_path() -> Path:
    return Path.home() / ".cruxhive" / "config.yaml"


def load_config() -> dict:
    """Return the cruxhive config dict, or {} if no config file present."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        return _parse_simple_yaml(p.read_text())
    except Exception:
        return {}


def _format_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "~"
    s = str(v)
    # Quote if contains chars that need it
    if any(c in s for c in ":#"):
        return f'"{s}"'
    return s


def save_config(cfg: dict) -> None:
    """Write a config dict back to ~/.cruxhive/config.yaml in simple YAML."""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for section, body in cfg.items():
        if isinstance(body, dict):
            lines.append(f"{section}:")
            for k, v in body.items():
                if isinstance(v, list):
                    lines.append(f"  {k}:")
                    for item in v:
                        lines.append(f"    - {item}")
                else:
                    lines.append(f"  {k}: {_format_value(v)}")
            lines.append("")
        else:
            lines.append(f"{section}: {_format_value(body)}")
    p.write_text("\n".join(lines).rstrip() + "\n")


def is_solo(approver_hint: str = "") -> tuple[bool, str]:
    """Return (enabled, approver) for solo mode.

    Solo mode is enabled when:
      - CRUXHIVE_SOLO=1 env var is set, OR
      - ~/.cruxhive/config.yaml has solo.enabled: true

    Approver resolves from:
      1. approver_hint argument (if given)
      2. CRUXHIVE_APPROVER env var
      3. config.yaml solo.approver
      4. `git config user.name` (best-effort)
      5. literal "self"
    """
    env_solo = os.environ.get("CRUXHIVE_SOLO", "").lower() in {"1", "true", "yes"}
    cfg = load_config().get("solo") or {}
    enabled = env_solo or bool(cfg.get("enabled"))
    if not enabled:
        return (False, "")
    approver = (
        approver_hint
        or os.environ.get("CRUXHIVE_APPROVER", "")
        or cfg.get("approver", "")
    )
    if not approver:
        try:
            import subprocess
            r = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True, text=True, timeout=2,
            )
            approver = r.stdout.strip() or "self"
        except Exception:
            approver = "self"
    return (True, approver)


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


def search_all(query: str, n: int = 10) -> list[dict]:
    """Search every configured project's index, merge results.

    Returns a flat list of result dicts, each with a `project` key naming
    the project the entry lives in. Sorted by descending fused score
    (BM25 + entity + recency).
    """
    from . import store as _store

    all_results: list[dict] = []
    for root in list_projects():
        db = root / ".llm" / "cruxhive.db"
        if not db.exists():
            continue
        try:
            conn = _store.connect(str(root))
            bm25 = _store.search_bm25(conn, query, n * 2)
            fused = _store.rrf_fuse(bm25, [], conn=conn, query=query)
            for r in fused[:n]:
                r["project"] = root.name
                all_results.append(r)
            conn.close()
        except Exception:
            continue

    # Re-sort merged set. Entries with entity matches go first.
    all_results.sort(
        key=lambda r: (-(r.get("_entity_match") or 0), r.get("rank") or 0)
    )
    return all_results[:n]


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
        "sessions": 0,
        "active_projects": 0,  # projects with any session in window
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
        total["sessions"] += k.get("sessions", 0)
        if k.get("sessions", 0) > 0:
            total["active_projects"] += 1
    total["hit_rate"] = (total["hits"] / total["searches"]) if total["searches"] else 0.0
    total["decay_ratio"] = (total["decayed_count"] / total["total_entries"]) if total["total_entries"] else 0.0
    return total
