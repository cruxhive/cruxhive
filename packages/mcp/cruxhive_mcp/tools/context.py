"""CruxHive context tools — knowledge layer MCP tools.

Operates on the local project's .llm/ directory. No external API calls.
Callable from Claude Code, OpenCode, Cursor, Windsurf, Gemini CLI,
or any MCP-compatible client.

Stdlib only — no dependencies beyond `mcp` (tomllib is Python 3.11+ built-in).
"""
from __future__ import annotations

import os
import re
import subprocess
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


# ─── utilities ───────────────────────────────────────────────────────────────


def _root(override: str | None) -> Path:
    return Path(override) if override else Path(os.getcwd())


def _run(args: list[str], cwd: Path) -> tuple[str, str]:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip()


# ─── radar helpers ───────────────────────────────────────────────────────────


def _parse_git_log(raw: str) -> list[tuple[str, list[str]]]:
    commits: list[tuple[str, list[str]]] = []
    msg: str | None = None
    files: list[str] = []
    for line in raw.splitlines():
        if line.startswith("COMMIT:"):
            if msg is not None:
                commits.append((msg, files))
                files = []
            msg = line[7:]
        elif line.strip() and msg is not None:
            files.append(line.strip())
    if msg is not None:
        commits.append((msg, files))
    return commits


def _load_plans(plans_dir: Path) -> dict[str, str]:
    """Returns {area_keyword: filename} for all non-active plans."""
    if not plans_dir.exists():
        return {}
    return {
        f.stem.split("-")[0]: f.name
        for f in plans_dir.glob("*.md")
        if f.name != "active.md"
    }


def _load_areas(areas_toml: Path) -> dict[str, str]:
    """Returns {path_prefix: area_keyword} from areas.toml."""
    if not areas_toml.exists():
        return {}
    with open(areas_toml, "rb") as fh:
        data = tomllib.load(fh)
    return dict(data.get("areas", {}))


_KNOWN_AREAS = frozenset({
    "cicd", "auth", "deploy", "build", "monitoring", "observability",
    "uiux", "security", "infra", "provisioning", "analytics", "maintenance",
    "platform", "openbao", "feedback", "ssh", "ops", "ai",
})


def _classify(
    msg: str,
    files: list[str],
    plans: dict[str, str],
    areas: dict[str, str],
) -> tuple[str, str]:
    """Return (area, COVERED | UNCOVERED | UNCLASSIFIED)."""
    # 1. Conventional commit scope: feat(cicd): …
    m = re.match(r"^\w+\((\w[-\w]*)\):", msg)
    if m:
        area = m.group(1)
        return area, "COVERED" if area in plans else "UNCOVERED"

    # 2. areas.toml — longest prefix match across all changed files
    best: tuple[int, str] | None = None
    for path in files:
        for prefix, kw in areas.items():
            if path.startswith(prefix) and (best is None or len(prefix) > best[0]):
                best = (len(prefix), kw)
    if best:
        kw = best[1]
        return kw, "COVERED" if kw in plans else "UNCOVERED"

    # 3. Directory keyword inference
    for path in files:
        for part in path.split("/")[:-1]:
            if part in plans:
                return part, "COVERED"
            if part in _KNOWN_AREAS:
                return part, "UNCOVERED"

    return "", "UNCLASSIFIED"


# ─── next-slice helpers ───────────────────────────────────────────────────────


def _find_plan_file(area: str, plans_dir: Path) -> Path | None:
    """Find a plan file matching the area keyword."""
    exact = plans_dir / f"{area}.md"
    if exact.exists():
        return exact
    for f in plans_dir.glob("*.md"):
        if f.name == "active.md":
            continue
        if f.stem.startswith(area):
            return f
    return None


def _extract_open_items(content: str) -> list[dict[str, Any]]:
    """Extract unchecked [ ] items from markdown plan content."""
    items: list[dict[str, Any]] = []
    current_phase: str | None = None
    for line in content.splitlines():
        pm = re.match(r"^#{1,4}\s+(Phase\s+\d+[^\n]*)", line)
        if pm:
            current_phase = pm.group(1).strip()
        om = re.match(r"^\s*[-*]\s*\[\s*\]\s*(.*)", line)
        if om:
            text = om.group(1).strip()
            blocked = bool(re.search(r"\bBLOCKED\b|\bDEFERRED\b", text, re.I))
            items.append({"phase": current_phase, "text": text, "blocked": blocked})
    return items


# ─── sync-memory helper ───────────────────────────────────────────────────────


def _find_sync_script(root: Path) -> Path | None:
    """Find sync-platform-memory.sh — workspace level or project scripts/."""
    candidates = [
        root.parent / "scripts" / "sync-platform-memory.sh",
        root / "scripts" / "sync-platform-memory.sh",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ─── tool registration ────────────────────────────────────────────────────────


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def context_radar(days: int = 7, project_root: str | None = None) -> str:
        """Scan recent git commits, classify by plan area, return a coverage report.

        Answers: "does everything I built have a plan behind it?"
        Maps commits to .llm/plans/ files using conventional commit scopes,
        areas.toml prefix matching, and directory keyword inference.

        Args:
            days: How many days of git history to scan. Default 7.
            project_root: Absolute path to the project root. Defaults to cwd.
        """
        root = _root(project_root)
        plans = _load_plans(root / ".llm" / "plans")
        areas = _load_areas(root / ".claude" / "areas.toml")

        if not plans:
            return (
                "No .llm/plans/ directory found. "
                "Run context_write_plan to create the first plan and start tracking."
            )

        raw, _err = _run(
            ["git", "log", f"--since={days} days ago",
             "--name-only", "--pretty=format:COMMIT:%s", "--no-merges"],
            root,
        )
        if not raw:
            return f"No commits in the last {days} days. Try days=30 for a wider window."

        commits = _parse_git_log(raw)
        if not commits:
            return f"No commits in the last {days} days."

        buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"classification": "", "commits": 0, "files": set(), "plan": ""}
        )
        unclassified: list[str] = []

        for msg, files in commits:
            area, cls = _classify(msg, files, plans, areas)
            if cls == "UNCLASSIFIED":
                unclassified.append(msg)
                continue
            b = buckets[area]
            b["classification"] = cls
            b["commits"] += 1
            b["files"].update(files)
            if cls == "COVERED":
                b["plan"] = plans[area]

        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = [
            f"/radar — last {days} days · {date}",
            f"{len(commits)} commits total",
            "",
        ]

        covered = {k: v for k, v in buckets.items() if v["classification"] == "COVERED"}
        uncovered = {k: v for k, v in buckets.items() if v["classification"] == "UNCOVERED"}

        if covered:
            lines.append("COVERED  (plan exists)")
            for area, b in sorted(covered.items()):
                lines.append(
                    f"  {area:<22}{b['commits']} commits · {len(b['files'])} files  →  {b['plan']}"
                )
            lines.append("")

        if uncovered:
            lines.append("UNCOVERED  (no plan)")
            for area, b in sorted(uncovered.items()):
                lines.append(
                    f"  {area:<22}{b['commits']} commits · {len(b['files'])} files"
                    f"  →  context_write_plan('{area}-...')"
                )
            lines.append("")

        if unclassified:
            lines.append("UNCLASSIFIED  (area unclear)")
            for msg in unclassified[:10]:
                lines.append(f"  {msg}")
            if len(unclassified) > 10:
                lines.append(f"  … and {len(unclassified) - 10} more")
            lines.append("")

        lines.append(
            f"{len(covered)} covered · {len(uncovered)} uncovered · {len(unclassified)} unclassified"
        )
        return "\n".join(lines)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def context_next_slice(area: str = "", project_root: str | None = None) -> str:
        """Find the next unblocked implementation slice from the active plan.

        Reads .llm/plans/active.md (or the named plan file) and extracts open
        [ ] items. Returns a structured view so the AI can propose a concrete slice.

        Args:
            area: Plan area keyword (e.g. "cicd", "auth", "agentfile"). Empty = active.md.
            project_root: Absolute path to the project root. Defaults to cwd.
        """
        root = _root(project_root)
        plans_dir = root / ".llm" / "plans"

        if not plans_dir.exists():
            return "No .llm/plans/ directory. Create plans first with context_write_plan."

        plan_path: Path | None = None

        if area:
            plan_path = _find_plan_file(area, plans_dir)
            if not plan_path:
                available = [f.stem for f in plans_dir.glob("*.md") if f.name != "active.md"]
                return (
                    f"No plan file found matching '{area}' in .llm/plans/.\n"
                    f"Available: {', '.join(sorted(available)) or 'none'}"
                )
        else:
            active = plans_dir / "active.md"
            if not active.exists():
                return "No .llm/plans/active.md found. Pass an area keyword explicitly."
            content = active.read_text()
            # Try to extract the current focus area from active.md first line
            for ln in content.splitlines()[:5]:
                m = re.search(r"Focus\*\*.*?:\s*(.+)", ln)
                if m:
                    guessed = m.group(1).strip().lower().split()[0].rstrip(".,;")
                    plan_path = _find_plan_file(guessed, plans_dir)
                    if plan_path:
                        break
            if not plan_path:
                return (
                    "Could not determine current plan area from active.md. "
                    "Pass an explicit area keyword (e.g. context_next_slice('cicd'))."
                )

        content = plan_path.read_text()
        all_items = _extract_open_items(content)
        ready = [i for i in all_items if not i["blocked"]]
        blocked = [i for i in all_items if i["blocked"]]

        # Audit freshness check
        audit_area = plan_path.stem.split("-")[0]
        audit_path = root / ".llm" / "context" / "audits" / f"{audit_area}-latest.md"
        if audit_path.exists():
            import time
            age_days = (time.time() - audit_path.stat().st_mtime) / 86400
            audit_note = f"Audit: {audit_path.name} ({age_days:.0f}d old)"
            if age_days > 3:
                audit_note += " — consider running /audit first"
        else:
            audit_note = f"Audit: none — consider /audit {audit_area} before starting"

        lines = [
            f"Plan: .llm/plans/{plan_path.name}",
            f"Open: {len(ready)} ready · {len(blocked)} blocked",
            audit_note,
            "",
        ]

        if ready:
            lines.append("Ready to start:")
            for i, item in enumerate(ready[:6], 1):
                phase = f"[{item['phase']}] " if item["phase"] else ""
                lines.append(f"  {i}. {phase}{item['text']}")
            if len(ready) > 6:
                lines.append(f"  … and {len(ready) - 6} more")

        if blocked:
            lines.append("")
            lines.append("Blocked / deferred:")
            for item in blocked[:3]:
                phase = f"[{item['phase']}] " if item["phase"] else ""
                lines.append(f"  · {phase}{item['text']}")

        if not ready and not blocked:
            lines.append("No open [ ] items found. Plan may be complete or use a different format.")

        return "\n".join(lines)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def context_write_plan(
        plan_name: str,
        content: str,
        project_root: str | None = None,
    ) -> str:
        """Write a plan file to .llm/plans/ and register it in active.md.

        Creates .llm/plans/{plan_name}.md with the provided content.
        Appends a pointer line to active.md if plan_name is new.

        Args:
            plan_name: Kebab-case plan name (e.g. "cicd-fleet-architecture").
            content: Full markdown content for the plan file.
            project_root: Absolute path to the project root. Defaults to cwd.
        """
        root = _root(project_root)

        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", plan_name):
            return (
                f"Invalid plan name '{plan_name}'. "
                "Use kebab-case only (e.g. 'cicd-fleet-architecture')."
            )

        plans_dir = root / ".llm" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)

        plan_path = plans_dir / f"{plan_name}.md"
        existed = plan_path.exists()
        plan_path.write_text(content)

        active_path = plans_dir / "active.md"
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pointer = f"- Plan: [{plan_name}]({plan_name}.md) — added {date}"

        if active_path.exists():
            active_text = active_path.read_text()
            if plan_name not in active_text:
                active_path.write_text(active_text.rstrip() + "\n" + pointer + "\n")
        else:
            active_path.write_text(f"# Active Plans\n\n{pointer}\n")

        verb = "Updated" if existed else "Created"
        phases = len(re.findall(r"^#{1,4}\s+Phase\s+\d+", content, re.MULTILINE))
        open_q = len(re.findall(r"^#{1,4}\s+Open Questions", content, re.MULTILINE))

        return (
            f"{verb} .llm/plans/{plan_name}.md — "
            f"{phases} phases, {open_q} open-questions section. "
            f"Registered in active.md."
        )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
    def context_sync_memory(project_root: str | None = None) -> str:
        """Sync org-layer context from Development/memory/ to all workspace projects.

        Runs sync-platform-memory.sh and returns the sync report.
        Idempotent — safe to call multiple times per session.

        Args:
            project_root: Absolute path to the mozbridge project root. Defaults to cwd.
        """
        root = _root(project_root)
        script = _find_sync_script(root)

        if script is None:
            return (
                f"Sync script not found. Expected at {root.parent}/scripts/sync-platform-memory.sh "
                f"or {root}/scripts/sync-platform-memory.sh."
            )

        out, err = _run([str(script)], script.parent.parent)
        if err and not out:
            return f"Sync failed:\n{err}"
        if err:
            return f"Sync completed with warnings:\n{out}\n\nSTDERR:\n{err}"
        return out or "Sync completed — all projects up to date."
