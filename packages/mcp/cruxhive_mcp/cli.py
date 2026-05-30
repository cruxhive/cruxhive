"""Thin CLI entry points called by @cruxhive/cli shell commands."""
from __future__ import annotations

import os
import sys


def ui() -> None:
    """cruxhive-ui: launch the local approval/dashboard web UI.

    Reads .llm/cruxhive.db from the current working directory.
    Default port 3847; override with --port. Pass --workspace for the
    cross-project workspace view (requires multiple .llm/ dirs nearby).

    Install requires the [ui] extra:
        uv tool install --reinstall --from <path> 'cruxhive-mcp[ui]'
    """
    try:
        import uvicorn
    except ImportError:
        print(
            "  \033[31m✗\033[0m  uvicorn not installed.\n"
            "  Reinstall with the [ui] extra:\n"
            "     uv tool install --reinstall --from "
            "/path/to/cruxhive/packages/mcp 'cruxhive-mcp[ui]'",
            file=sys.stderr,
        )
        sys.exit(1)

    args = sys.argv[1:]
    port = 3847
    host = "127.0.0.1"
    workspace = False
    while args:
        a = args.pop(0)
        if a == "--port" and args:
            port = int(args.pop(0))
        elif a == "--host" and args:
            host = args.pop(0)
        elif a in ("--workspace", "-w"):
            workspace = True
        elif a in ("--help", "-h"):
            print(ui.__doc__)
            return

    from .ui import make_app, make_workspace_app  # type: ignore[attr-defined]

    app = make_workspace_app() if workspace else make_app()
    print(f"  \033[32m✓\033[0m  CruxHive UI → http://{host}:{port}"
          f"{'  (workspace mode)' if workspace else ''}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def index() -> None:
    """cruxhive-index: index .llm/ into SQLite.

    Flags:
      --rebuild   force full re-index (drops existing entries first). Use after
                  upgrading cruxhive-mcp to a version with new schema features
                  (entity tags, etc.) that need backfilling on existing files.
    """
    from . import store as _store
    from . import embedder as _emb

    args = sys.argv[1:]
    rebuild = "--rebuild" in args

    root = os.getcwd()

    if rebuild:
        conn = _store.connect(root)
        before = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.execute("DELETE FROM entries")
        conn.commit()
        conn.close()
        print(f"  \033[36m·\033[0m  --rebuild: dropped {before} entries; reindexing fresh")

    embedder = _emb if _emb.is_available() else None
    try:
        n = _store.index(root, embedder=embedder)
        vec = " (+ vectors)" if embedder else ""
        print(f"  \033[32m✓\033[0m  Indexed {n} file(s){vec} → .llm/cruxhive.db")
    except Exception as e:
        print(f"  \033[31m✗\033[0m  {e}", file=sys.stderr)
        sys.exit(1)


def propose() -> None:
    """cruxhive-propose: write a pending knowledge entry from stdin args."""
    # Usage: cruxhive-propose <type> <topic> [scope]
    # Content is read from stdin.
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: cruxhive-propose <type> <topic> [scope]", file=sys.stderr)
        print("Content is read from stdin.", file=sys.stderr)
        sys.exit(1)

    entry_type = args[0]
    topic = args[1]
    scope = args[2] if len(args) > 2 else "project"
    content = sys.stdin.read().strip()

    if not content:
        print("  \033[31m✗\033[0m  No content provided on stdin.", file=sys.stderr)
        sys.exit(1)

    import datetime
    from pathlib import Path
    from . import store as _store

    root = os.getcwd()
    valid_types = {"fact", "decision", "plan", "pattern", "constraint", "research", "outcome"}
    if entry_type not in valid_types:
        print(f"  \033[31m✗\033[0m  Invalid type '{entry_type}'. Use: {', '.join(sorted(valid_types))}", file=sys.stderr)
        sys.exit(1)

    date = datetime.date.today().isoformat()
    slug = topic.lower().replace(" ", "-").replace("/", "-")[:40]
    pending_dir = Path(root) / ".llm" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    fpath = pending_dir / f"{entry_type}_{slug}.md"
    i = 1
    while fpath.exists():
        fpath = pending_dir / f"{entry_type}_{slug}_{i}.md"
        i += 1

    from . import workspace as _ws
    solo_enabled, solo_approver = _ws.is_solo()
    if solo_enabled:
        source_val, approved_by = "human", solo_approver
    else:
        source_val, approved_by = "ai-proposed", "~"

    fpath.write_text(
        f"---\ntype: {entry_type}\nscope: {scope}\ntopic: {topic}\n"
        f"valid_at: {date}\ninvalid_at: ~\nconfidence: medium\n"
        f"source: {source_val}\napproved_by: {approved_by}\n---\n\n{content}\n",
        encoding="utf-8",
    )
    try:
        _store.index(root)
    except Exception:
        pass

    rel = str(fpath.relative_to(root))
    if solo_enabled:
        print(f"  \033[32m✓\033[0m  Written: {rel}  (solo mode — auto-approved as {solo_approver})")
    else:
        print(f"  \033[32m✓\033[0m  Proposed: {rel}")
        print(f"       Run \033[36mcruxhive review\033[0m to approve or reject.")


def review() -> None:
    """cruxhive-review-list: print pending proposals as JSON for the JS CLI."""
    import json
    from . import store as _store

    root = os.getcwd()
    try:
        conn = _store.connect(root)
        pending = _store.list_pending(conn)
        conn.close()
        print(json.dumps(pending))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


def approve() -> None:
    """cruxhive-approve: approve a pending entry. Args: <path> <approver>"""
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: cruxhive-approve <path> <approver>", file=sys.stderr)
        sys.exit(1)
    path, approver = args[0], args[1]
    from . import store as _store
    root = os.getcwd()
    conn = _store.connect(root)
    ok = _store.approve(conn, path, approver, root)
    conn.close()
    if ok:
        print(f"  \033[32m✓\033[0m  Approved: {path}")
    else:
        print(f"  \033[31m✗\033[0m  Not found: {path}", file=sys.stderr)
        sys.exit(1)


def _collect_snapshot(root: str, days: int = 7) -> dict:
    """Build a structured digest snapshot. Used by `digest` and `workspace`."""
    from datetime import date
    from pathlib import Path
    from . import events as _events
    from . import store as _store

    proj = Path(root).name
    conn = _store.connect(root)
    summary = _events.summary(conn, days=days)
    by_tool = _events.by_tool(conn, days=days)
    gaps = _events.top_gaps(conn, days=max(days, 30), limit=10)
    pend = _events.pending_age(conn)
    decayed = _store.stale_high_confidence(conn)
    kb = _store.stats(conn)
    conn.close()

    decay_ratio = (len(decayed) / kb["total"]) if kb["total"] else 0.0
    kpis = {
        "hit_rate": round(summary["hit_rate"], 4),
        "gaps_30d": len(gaps),
        "pending_count": pend["count"],
        "pending_oldest_days": pend["oldest_days"],
        "pending_avg_days": pend["avg_days"],
        "decayed_count": len(decayed),
        "decay_ratio": round(decay_ratio, 4),
        "total_entries": kb["total"],
        "constraints": kb["constraints"],
        "searches": summary["searches"],
        "total_calls": summary["total_calls"],
        "proposals": summary["proposals"],
        "sessions": summary.get("sessions", 0),
    }

    return {
        "date": date.today().isoformat(),
        "project": proj,
        "root": str(root),
        "window_days": days,
        "kpis": kpis,
        "kb": kb,
        "events": summary,
        "by_tool": by_tool,
        "gaps": gaps[:10],
        "decayed": [
            {"path": d["path"], "age_days": d["age_days"],
             "effective_confidence": d["effective_confidence"]}
            for d in decayed[:25]
        ],
        "pending_age": pend,
    }


def _find_prior_snapshot(root: str, target_days_ago: int = 7) -> dict | None:
    """Return the snapshot closest to N days before today, or None."""
    import json
    import datetime
    from pathlib import Path

    d = Path(root) / ".llm" / "digests"
    if not d.exists():
        return None
    target = datetime.date.today() - datetime.timedelta(days=target_days_ago)
    best: tuple[int, dict] | None = None
    for f in d.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            ds = data.get("date")
            if not ds:
                continue
            fdate = datetime.date.fromisoformat(ds)
            if fdate >= datetime.date.today():
                continue  # skip today's snapshot
            diff = abs((fdate - target).days)
            if best is None or diff < best[0]:
                best = (diff, data)
        except Exception:
            continue
    return best[1] if best else None


def _delta(curr: float | int, prev: float | int, lower_is_better: bool = False) -> str:
    """Format a delta arrow + sign. lower_is_better flips the color logic."""
    if prev is None:
        return ""
    diff = curr - prev
    if diff == 0:
        return " →"
    sign = "+" if diff > 0 else ""
    arrow = "↑" if diff > 0 else "↓"
    # Color heuristic (used only when stdout is a TTY)
    good = (diff < 0) if lower_is_better else (diff > 0)
    color = "32" if good else "31"
    if not sys.stdout.isatty():
        return f" {arrow}{sign}{diff}"
    return f" \033[{color}m{arrow}{sign}{diff}\033[0m"


def digest() -> None:
    """cruxhive-digest: weekly markdown report of gaps, staleness, queue health.

    Flags:
      --days N        window in days (default 7)
      --compare       diff against the snapshot closest to 7 days ago
      --json          emit JSON snapshot instead of markdown
      --no-save       don't persist to .llm/digests/
    """
    import json as _json
    from datetime import date
    from pathlib import Path

    days = 7
    args = sys.argv[1:]
    compare = "--compare" in args
    as_json = "--json" in args
    no_save = "--no-save" in args
    for i, a in enumerate(args):
        if a in ("--days", "-d") and i + 1 < len(args) and args[i + 1].isdigit():
            days = int(args[i + 1])

    root = os.getcwd()
    proj = Path(root).name
    if not (Path(root) / ".llm" / "cruxhive.db").exists():
        print(f"# CruxHive digest — {proj}\n\n_No knowledge base yet. Run `cruxhive init` then `cruxhive index`._")
        sys.exit(1)

    snap = _collect_snapshot(root, days=days)
    summary = snap["events"]
    by_tool = snap["by_tool"]
    gaps = snap["gaps"]
    pend = snap["pending_age"]
    decayed_list = snap["decayed"]
    kb = snap["kb"]
    kpis = snap["kpis"]

    today = snap["date"]

    # JSON mode short-circuits everything else
    if as_json:
        print(_json.dumps(snap, indent=2, default=str))
        # Still persist
        if not no_save:
            _save_snapshot(root, today, snap, markdown=None)
        return
    prior = _find_prior_snapshot(root) if compare else None
    prior_kpis = (prior or {}).get("kpis", {})

    def delta(field, lower_is_better=False):
        if not compare or field not in prior_kpis:
            return ""
        return _delta(kpis[field], prior_kpis[field], lower_is_better=lower_is_better)

    out: list[str] = []
    out.append(f"# CruxHive digest — {proj}")
    if compare and prior:
        out.append(f"_Generated {today} · window: last {days} days · vs {prior.get('date','?')}_\n")
    else:
        out.append(f"_Generated {today} · window: last {days} days_\n")

    # KPI table — the headline view
    hit_pct = f"{summary['hit_rate']*100:.0f}%" if summary["searches"] else "—"
    out.append(f"## Key indicators")
    out.append(f"- **Hit rate**: {hit_pct}{delta('hit_rate')}")
    out.append(f"- **Gaps (30d)**: {kpis['gaps_30d']}{delta('gaps_30d', lower_is_better=True)}")
    out.append(f"- **Pending queue**: {kpis['pending_count']}{delta('pending_count', lower_is_better=True)}"
               + (f" (oldest {kpis['pending_oldest_days']}d)" if kpis['pending_count'] else ""))
    out.append(f"- **Decayed entries**: {kpis['decayed_count']}{delta('decayed_count', lower_is_better=True)}"
               + f" ({kpis['decay_ratio']*100:.0f}% of total)")
    out.append(f"- **Total entries**: {kpis['total_entries']}{delta('total_entries')}")
    out.append(f"- **Constraints**: {kpis['constraints']}{delta('constraints')}\n")

    out.append(f"## Activity")
    out.append(f"- **{kpis.get('sessions',0)}** AI sessions{delta('sessions')} · "
               f"**{summary['total_calls']}** tool calls{delta('total_calls')} · "
               f"**{summary['searches']}** searches{delta('searches')}")
    out.append(f"- **{summary['proposals']}** new proposals{delta('proposals')}\n")

    # Gaps — most actionable
    if gaps:
        out.append(f"## Top knowledge gaps")
        out.append(f"_Zero-result queries from your AI tools — most actionable list to document next._\n")
        for i, g in enumerate(gaps, 1):
            clients = g["clients"] or "?"
            out.append(f"{i}. **{g['query']}** — searched {g['times']}× by {clients}")
        out.append("")
        out.append("→ Use `/propose` (or `cruxhive propose`) to capture entries for these.\n")
    else:
        out.append(f"## Top knowledge gaps\n_None — every recent search found something._\n")

    # Stale high-confidence entries
    if decayed_list:
        out.append(f"## High-confidence entries that have decayed")
        out.append(f"_These were marked `confidence: high` but haven't been revalidated. Effective confidence has been auto-downgraded for search ranking._\n")
        for d in decayed_list[:8]:
            out.append(f"- `{d['path']}` — {d['age_days']}d old, now **{d['effective_confidence']}** (was high)")
        if len(decayed_list) > 8:
            out.append(f"- … and {len(decayed_list) - 8} more")
        out.append("")
        out.append("→ Re-read each, update `valid_at:` to today, or set `invalid_at:` to deprecate.\n")

    # Per-AI-tool divergence
    if len(by_tool) > 1:
        out.append(f"## Per-AI-tool divergence")
        out.append(f"| Tool | Calls | Hit rate | Zero-results | Proposals |")
        out.append(f"|------|------:|---------:|-------------:|----------:|")
        for r in by_tool:
            hits = r.get("hits") or 0
            searches = r.get("searches") or 0
            pct = f"{hits/searches*100:.0f}%" if searches else "—"
            out.append(f"| {r['client']} | {r['calls']} | {pct} | {r.get('zero_results') or 0} | {r.get('proposals') or 0} |")
        out.append("")
        out.append("→ A tool with low hit rate may need better prompts that mention CruxHive; high zero-result count signals missing knowledge for that tool's workflow.\n")
    elif by_tool:
        out.append(f"## AI tool usage")
        r = by_tool[0]
        hits = r.get("hits") or 0
        searches = r.get("searches") or 0
        pct = f"{hits/searches*100:.0f}%" if searches else "—"
        out.append(f"Single tool active: **{r['client']}** ({r['calls']} calls, {pct} hit rate). Add another (OpenCode, Cursor, ...) to compare.\n")

    # Pending queue
    if pend["count"]:
        out.append(f"## Pending approval queue")
        out.append(f"- **{pend['count']}** proposals waiting")
        out.append(f"- Oldest: **{pend['oldest_days']}d** · Avg age: **{pend['avg_days']}d**")
        if pend["oldest_days"] > 14:
            out.append(f"- ⚠ Queue is stale — review backlog before adding more.")
        out.append("")
        out.append("→ Run `/review`, `cruxhive review`, or open `cruxhive ui`.\n")

    # Suggested actions
    out.append(f"## Suggested next actions")
    suggestions = []
    if gaps:
        suggestions.append(f"Document the top {min(3, len(gaps))} gap{'s' if len(gaps) > 1 else ''}")
    if decayed_list:
        suggestions.append(f"Revalidate the {len(decayed_list)} decayed high-confidence entr{'ies' if len(decayed_list) != 1 else 'y'}")
    if pend["count"] and pend["oldest_days"] > 7:
        suggestions.append("Drain the pending review queue")
    if not suggestions:
        suggestions.append("Knowledge base is healthy. Carry on.")
    for s in suggestions:
        out.append(f"- {s}")

    markdown = "\n".join(out)
    print(markdown)

    if not no_save:
        _save_snapshot(root, today, snap, markdown=markdown)


def _save_snapshot(root: str, date_iso: str, snap: dict, markdown: str | None) -> None:
    """Persist a digest snapshot (.json always, .md if provided)."""
    import json
    from pathlib import Path
    d = Path(root) / ".llm" / "digests"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{date_iso}.json").write_text(json.dumps(snap, indent=2, default=str))
    if markdown is not None:
        (d / f"{date_iso}.md").write_text(markdown)


def doctor() -> None:
    """cruxhive-doctor: diagnose CruxHive setup in the current project.

    Verifies all the things `cruxhive init` should have wired:
    .llm/CONTEXT.md, .mcp.json, .gitignore entries, AI tool symlinks,
    slash command files, .llm/memory/platform_refs.md, personal layer,
    git post-commit hook, session hooks. Reports problems with fix
    suggestions. Exit code: 0 if all green, 1 if any problem.
    """
    from pathlib import Path
    import json

    root = Path(os.getcwd())
    proj = root.name

    problems: list[str] = []
    warnings: list[str] = []
    oks: list[str] = []

    def ok(msg: str) -> None:
        oks.append(msg)

    def warn(msg: str) -> None:
        warnings.append(msg)

    def fail(msg: str) -> None:
        problems.append(msg)

    # .llm/CONTEXT.md
    ctx = root / ".llm" / "CONTEXT.md"
    if not ctx.exists():
        fail(f".llm/CONTEXT.md missing — run `cruxhive init`")
    else:
        ok(".llm/CONTEXT.md present")

    # .mcp.json
    mcp = root / ".mcp.json"
    if not mcp.exists():
        fail(".mcp.json missing — run `cruxhive init`")
    else:
        try:
            cfg = json.loads(mcp.read_text())
            if cfg.get("mcpServers", {}).get("cruxhive"):
                ok(".mcp.json registers cruxhive-mcp")
            else:
                fail(".mcp.json present but missing cruxhive entry")
        except Exception as e:
            fail(f".mcp.json is malformed: {e}")

    # AI tool wirings
    tool_files = [
        ("CLAUDE.md", "Claude Code"),
        ("AGENT.md", "OpenCode"),
        (".cursor/rules/cruxhive.mdc", "Cursor"),
        (".windsurfRules", "Windsurf"),
        ("GEMINI.md", "Gemini CLI"),
    ]
    missing_tools = []
    for fname, tname in tool_files:
        p = root / fname
        if not (p.exists() or p.is_symlink()):
            missing_tools.append(f"{tname} ({fname})")
    if missing_tools:
        warn(f"AI tool wirings missing for: {', '.join(missing_tools)}")
    else:
        ok("All 5 AI tool wirings present")

    # .gitignore
    gi = root / ".gitignore"
    if gi.exists() and "cruxhive.db" in gi.read_text():
        ok(".gitignore excludes cruxhive.db")
    elif gi.exists():
        warn(".gitignore exists but doesn't exclude .llm/cruxhive.db")
    else:
        warn(".gitignore missing — index/log will land in git unless added")

    # Slash commands
    expected = {"radar", "next-slice", "review", "propose", "write-plan", "extract"}
    for dialect_dir, dialect_name in [
        (".claude/commands", "Claude Code"),
        (".opencode/commands", "OpenCode"),
    ]:
        d = root / dialect_dir
        if not d.exists():
            warn(f"{dialect_dir}/ missing — slash commands not wired for {dialect_name}")
            continue
        present = {f.stem for f in d.glob("*.md")}
        missing = expected - present
        if missing:
            warn(f"{dialect_dir}/ missing commands: {', '.join(sorted(missing))}")
        else:
            ok(f"{dialect_dir}/ has all 6 slash commands")

    # platform_refs.md
    refs = root / ".llm" / "memory" / "platform_refs.md"
    if refs.exists():
        ok(".llm/memory/platform_refs.md present (org layer)")
    else:
        warn(".llm/memory/platform_refs.md missing — run `cruxhive sync` to populate org layer")

    # Personal layer
    from pathlib import Path as _P
    personal = _P.home() / ".cruxhive" / "personal"
    if personal.exists() and any(personal.glob("*.md")):
        ok(f"Personal layer present (~/.cruxhive/personal/, {len(list(personal.glob('*.md')))} file(s))")
    else:
        warn("Personal layer empty — `cruxhive init` will seed it")

    # Git post-commit hook
    hook = root / ".git" / "hooks" / "post-commit"
    if hook.exists():
        body = hook.read_text()
        if "cruxhive" in body.lower():
            ok("Git post-commit hook installed (auto-index)")
        else:
            warn("Git post-commit exists but doesn't run cruxhive-index")
    else:
        warn("Git post-commit hook not installed — run `cruxhive init` to add auto-index")

    # .envrc (direnv) for non-hook AI tools (Cursor/Windsurf/Gemini)
    envrc = root / ".envrc"
    if envrc.exists() and "CruxHive .envrc" in envrc.read_text():
        from shutil import which
        if which("direnv"):
            ok(".envrc CruxHive section present + direnv installed (Cursor/Windsurf coverage)")
        else:
            warn(".envrc CruxHive section present but `direnv` binary missing — install: brew install direnv")
    else:
        warn(".envrc not wired — Cursor/Windsurf/Gemini sessions won't log. Run `cruxhive direnv`")

    # SQLite db sanity
    db = root / ".llm" / "cruxhive.db"
    if db.exists():
        import sqlite3
        try:
            c = sqlite3.connect(str(db))
            n = c.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            e = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            c.close()
            ok(f"SQLite knowledge base healthy ({n} entries, {e} events)")
        except Exception as ex:
            fail(f"SQLite knowledge base corrupt: {ex}")
    else:
        warn(".llm/cruxhive.db missing — run `cruxhive index`")

    # ── Output ──────────────────────────────────────────────────────────────
    def c(s: str, code: str) -> str:
        if not sys.stdout.isatty():
            return s
        return f"\033[{code}m{s}\033[0m"

    print()
    print(f"  {c('CruxHive doctor', '1')} — {proj}")
    print()
    for m in oks:
        print(f"  {c('✓', '32')}  {m}")
    for m in warnings:
        print(f"  {c('!', '33')}  {m}")
    for m in problems:
        print(f"  {c('✗', '31')}  {m}")
    print()
    if problems:
        print(f"  {c('Summary', '1')}: {len(problems)} problem(s), {len(warnings)} warning(s)")
        print(f"  → Fix: \033[36mcruxhive init\033[0m  (idempotent, won't clobber existing files)\n")
        sys.exit(1)
    elif warnings:
        print(f"  {c('Summary', '1')}: {len(warnings)} warning(s)")
        print(f"  → Optional fixes: \033[36mcruxhive init\033[0m or \033[36mcruxhive sync\033[0m\n")
        sys.exit(0)
    else:
        print(f"  {c('Summary', '1')}: all green ({len(oks)} checks passed)\n")
        sys.exit(0)


def _digest_age_days(root: str) -> int | None:
    """Days since the last digest was written. None if never."""
    from pathlib import Path
    import datetime
    digests = Path(root) / ".llm" / "digests"
    if not digests.exists():
        return None
    files = sorted(digests.glob("*.md"))
    if not files:
        return None
    latest = max(f.stat().st_mtime for f in files)
    return int((datetime.datetime.now().timestamp() - latest) / 86400)


def solo() -> None:
    """cruxhive-solo: enable/disable auto-approve-own-proposals mode.

    Use this when you're the only approver — turns CruxHive's pending queue
    into a no-op so `context_propose` writes entries as already-approved.

    Flags:
      --enable          turn solo mode on (default)
      --disable         turn solo mode off — back to normal approval queue
      --name NAME       approver name to stamp on entries (default: `git config user.name`)
      --status          just print current state, change nothing
    """
    from . import workspace as _ws

    args = sys.argv[1:]
    disable = "--disable" in args
    status_only = "--status" in args
    name = ""
    for i, a in enumerate(args):
        if a == "--name" and i + 1 < len(args):
            name = args[i + 1]

    cfg = _ws.load_config()

    def c(s, code):
        return s if not sys.stdout.isatty() else f"\033[{code}m{s}\033[0m"

    if status_only:
        enabled, approver = _ws.is_solo(name)
        print()
        if enabled:
            print(f"  {c('Solo mode: ON', '32')}")
            print(f"  Approver: {c(approver, '36')}")
            print(f"  Source: {'CRUXHIVE_SOLO env' if os.environ.get('CRUXHIVE_SOLO') else 'config.yaml'}")
        else:
            print(f"  {c('Solo mode: OFF', '90')}")
            print(f"  Proposals will land in .llm/pending/ and need explicit approval.")
        print()
        return

    if disable:
        if "solo" in cfg:
            cfg["solo"]["enabled"] = False
            _ws.save_config(cfg)
        print(f"  {c('✓', '32')}  Solo mode disabled. Proposals will require explicit approval.")
        return

    # Enable
    if not name:
        try:
            import subprocess
            r = subprocess.run(
                ["git", "config", "user.name"], capture_output=True, text=True, timeout=2
            )
            name = r.stdout.strip()
        except Exception:
            pass
    if not name:
        print(f"  {c('!', '33')}  No --name given and `git config user.name` is unset.")
        print(f"  Pass --name 'Your Name' or set git user.name first.")
        sys.exit(1)

    cfg.setdefault("solo", {})
    cfg["solo"]["enabled"] = True
    cfg["solo"]["approver"] = name
    _ws.save_config(cfg)
    print()
    print(f"  {c('✓', '32')}  Solo mode enabled.")
    print(f"  Approver: {c(name, '36')}")
    print(f"  Config: {c(str(_ws.config_path()), '90')}")
    print()
    print(f"  From now on, `context_propose` writes entries directly as approved.")
    print(f"  Override per-project: \033[36mCRUXHIVE_SOLO=0 cruxhive propose\033[0m")
    print(f"  Disable: \033[36mcruxhive solo --disable\033[0m")
    print()


def workspace() -> None:
    """cruxhive-workspace: aggregate KPIs across all configured projects.

    Reads ~/.cruxhive/config.yaml (or scans ~/Projects_Local/Development/)
    for projects with an initialized .llm/cruxhive.db, then prints a
    workspace-wide rollup and per-project breakdown.

    Flags:
      --days N    window in days (default 7)
      --json      structured output
    """
    import json
    from . import workspace as _workspace

    args = sys.argv[1:]
    days = 7
    as_json = "--json" in args
    for i, a in enumerate(args):
        if a in ("--days", "-d") and i + 1 < len(args) and args[i + 1].isdigit():
            days = int(args[i + 1])

    snaps = _workspace.collect_all(days=days)
    agg = _workspace.aggregate([s for s in snaps if not s.get("error")])

    if as_json:
        print(json.dumps({"aggregate": agg, "projects": snaps}, indent=2, default=str))
        return

    if not snaps:
        print()
        print("  No CruxHive projects found.")
        print("  Configure paths in ~/.cruxhive/config.yaml or scan a different directory.")
        print()
        return

    def c(s: str, code: str) -> str:
        if not sys.stdout.isatty():
            return s
        return f"\033[{code}m{s}\033[0m"

    hit_pct = f"{agg['hit_rate']*100:.0f}%" if agg["searches"] else "—"
    decay_pct = f"{agg['decay_ratio']*100:.0f}%" if agg["total_entries"] else "—"

    print()
    print(f"  {c('CruxHive workspace', '1')} · last {days} days · "
          f"{agg['projects']} project(s)")
    print()
    print(f"  {c('Aggregate', '36')}")
    print(f"    {agg['total_entries']:>5}  entries")
    print(f"    {agg['constraints']:>5}  constraints")
    print(f"    {agg['pending_count']:>5}  pending approval")
    print(f"    {agg['decayed_count']:>5}  decayed ({decay_pct} of total)")
    print(f"    {agg.get('sessions', 0):>5}  AI sessions · {agg.get('active_projects', 0)} active project(s)")
    print(f"    {agg['total_calls']:>5}  tool calls · {agg['searches']} searches · {hit_pct} hit rate")
    print(f"    {agg['proposals']:>5}  proposals")
    print()
    print(f"  {c('Per project', '36')}")
    print(f"    {'project':<16} {'entries':>8} {'pending':>8} {'searches':>9} "
          f"{'hits%':>7} {'decayed':>8} {'gaps':>6}")
    for s in snaps:
        if s.get("error"):
            print(f"    {s['project'][:16]:<16} {c('error: ' + s['error'][:50], '31')}")
            continue
        k = s["kpis"]
        searches = k["searches"]
        hits = (s.get("events") or {}).get("hits", 0)
        pct = f"{hits/searches*100:.0f}%" if searches else "—"
        print(f"    {s['project'][:16]:<16} {k['total_entries']:>8} "
              f"{k['pending_count']:>8} {searches:>9} {pct:>7} "
              f"{k['decayed_count']:>8} {k['gaps_30d']:>6}")
    print()


_ENVRC_TEMPLATE = '''# CruxHive .envrc — auto-logs a session_start event when you cd into this project.
# Generated by `cruxhive direnv`. Requires direnv (https://direnv.net) installed
# and `direnv allow` run once per project.
#
# Coverage: this fires for any shell session in this directory, so AI tools
# without their own SessionStart hook (Cursor, Windsurf, Gemini CLI) get
# tagged correctly via the CRUXHIVE_CLIENT hint below.
#
# Rate-limited inside cruxhive-status: only one session per (project, client)
# is logged per 20 minutes, so repeated direnv reloads are safe.

# Tell CruxHive which AI tool you use here. Override per-session as needed:
# CRUXHIVE_CLIENT=cursor claude   (forces "cursor" tag even when launching claude)
export CRUXHIVE_CLIENT="${{CRUXHIVE_CLIENT:-{client}}}"

# Fire the session_start event. Silent on failure (e.g. CruxHive not installed).
cruxhive-status --quiet --session-start 2>/dev/null || true
'''


def direnv() -> None:
    """cruxhive-direnv: write a .envrc that logs a session_start when you cd in.

    Useful for AI tools that don't have their own session lifecycle hook
    (Cursor, Windsurf, Gemini CLI). Requires direnv installed:
        brew install direnv     # macOS
        apt install direnv      # Debian/Ubuntu
    Plus the eval line added to your shell rc (see https://direnv.net).

    Flags:
      --client NAME   default CRUXHIVE_CLIENT value (default: cursor)
      --force         overwrite existing .envrc
      --uninstall     remove the .envrc CruxHive section
    """
    from pathlib import Path

    args = sys.argv[1:]
    client = "cursor"
    force = "--force" in args
    uninstall = "--uninstall" in args
    for i, a in enumerate(args):
        if a == "--client" and i + 1 < len(args):
            client = args[i + 1]

    root = Path(os.getcwd())
    envrc = root / ".envrc"

    if uninstall:
        if envrc.exists():
            envrc.unlink()
            print(f"  \033[32m✓\033[0m  Removed {envrc}")
        else:
            print(f"  \033[36m·\033[0m  No .envrc in {root}")
        return

    if envrc.exists() and not force:
        existing = envrc.read_text()
        if "CruxHive .envrc" in existing:
            print(f"  \033[36m·\033[0m  .envrc already contains CruxHive section "
                  f"(use --force to overwrite)")
            return
        print(f"  \033[31m✗\033[0m  .envrc exists but is not CruxHive-managed. "
              f"Refusing to overwrite without --force.", file=sys.stderr)
        sys.exit(1)

    envrc.write_text(_ENVRC_TEMPLATE.format(client=client))
    print(f"  \033[32m✓\033[0m  Wrote {envrc}")
    print()
    print(f"  Next:")
    print(f"    1. \033[36mdirenv allow\033[0m   (one-time, per project)")
    print(f"    2. \033[36mcd ..\033[0m && \033[36mcd {root.name}\033[0m   (re-enter to trigger)")
    print()
    print(f"  Tag your AI tool: edit \033[36m.envrc\033[0m and change "
          f"CRUXHIVE_CLIENT=\"{client}\" if needed.")
    print(f"  Uninstall: \033[36mcruxhive direnv --uninstall\033[0m")


def status() -> None:
    """cruxhive-status: one-line health summary for hooks and nudges.

    Flags:
      --quiet           print nothing if everything is clean (for SessionStart hooks)
      --json            structured output
      --session-start   ALSO log a session_start event before printing — used by
                        SessionStart hooks to record that an AI session began,
                        even if no MCP search ever happens in that session
    """
    import json
    from pathlib import Path
    from . import events as _events
    from . import store as _store

    args = sys.argv[1:]
    quiet = "--quiet" in args or "-q" in args
    as_json = "--json" in args
    session_start = "--session-start" in args

    root = os.getcwd()
    db = Path(root) / ".llm" / "cruxhive.db"
    if not db.exists():
        if as_json:
            print(json.dumps({"setup": False}))
        elif not quiet:
            print("CruxHive: not initialized (run `cruxhive init`)")
        return

    # Record session start before any other work so we capture even broken sessions.
    # Rate-limit: skip if another session_start for the same client landed in the
    # last 20 minutes — otherwise repeated cd / direnv reloads spam the log.
    if session_start:
        try:
            import sqlite3 as _sql
            import datetime as _dt
            _events.set_client("", "")  # forces env-var detection
            cname = _events._client_name.get() or "unknown"
            conn_rl = _sql.connect(str(db))
            cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=20)).isoformat(timespec="seconds")
            recent = conn_rl.execute(
                "SELECT COUNT(*) FROM events WHERE tool='session_start' "
                "AND client_name=? AND ts >= ?", (cname, cutoff)
            ).fetchone()[0]
            conn_rl.close()
            if recent == 0:
                _events.log(root, "session_start", query="", result_n=None, ms=None)
        except Exception:
            pass

    conn = _store.connect(root)
    pending = _store.list_pending(conn)
    decayed = _store.stale_high_confidence(conn)
    gaps = _events.top_gaps(conn, days=30, limit=50)
    conn.close()

    digest_age = _digest_age_days(root)
    summary = {
        "pending": len(pending),
        "gaps_30d": len(gaps),
        "decayed": len(decayed),
        "digest_age_days": digest_age,
    }

    if as_json:
        print(json.dumps(summary))
        return

    # Anything actionable?
    actionable = (
        summary["pending"] > 0
        or summary["gaps_30d"] >= 3
        or summary["decayed"] > 0
        or (digest_age is not None and digest_age >= 7)
    )

    if quiet and not actionable:
        return

    parts: list[str] = []
    if summary["pending"]:
        parts.append(f"{summary['pending']} pending")
    if summary["gaps_30d"] >= 3:
        parts.append(f"{summary['gaps_30d']} gaps (30d)")
    if summary["decayed"]:
        parts.append(f"{summary['decayed']} decayed entries")
    if digest_age is not None and digest_age >= 7:
        parts.append(f"digest {digest_age}d old")

    body = " · ".join(parts) if parts else "all clear"
    suffix = "  →  run `cruxhive digest` for details" if actionable else ""
    print(f"🐝 CruxHive: {body}{suffix}")


def search() -> None:
    """cruxhive-search: BM25 + entity + recency search.

    Usage:
      cruxhive-search <query> [n]               # search current project
      cruxhive-search --workspace <query> [n]   # search ALL configured projects

    Prints JSON. Logs to the events table (client_name='cli').
    """
    import json
    import time as _time
    raw = sys.argv[1:]
    if not raw:
        print("Usage: cruxhive-search [--workspace] <query> [n]", file=sys.stderr)
        sys.exit(1)

    workspace_mode = False
    args = []
    for a in raw:
        if a in ("--workspace", "-w"):
            workspace_mode = True
        else:
            args.append(a)
    if not args:
        print("Usage: cruxhive-search [--workspace] <query> [n]", file=sys.stderr)
        sys.exit(1)

    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
    from . import events as _events
    from . import store as _store
    root = os.getcwd()
    t0 = _time.perf_counter()
    result_n = 0
    try:
        if workspace_mode:
            from . import workspace as _ws
            hits = _ws.search_all(args[0], n=n)
            out = [
                {"project": h.get("project"), "path": h.get("path"),
                 "topic": h.get("topic"), "type": h.get("type"),
                 "snippet": (h.get("snippet") or "")[:160],
                 "entity_match": h.get("_entity_match", 0)}
                for h in hits
            ]
        else:
            conn = _store.connect(root)
            bm25 = _store.search_bm25(conn, args[0], n * 2)
            hits = _store.rrf_fuse(bm25, [], conn=conn, query=args[0])[:n]
            conn.close()
            out = [
                {"path": h.get("path"), "topic": h.get("topic"),
                 "type": h.get("type"), "snippet": (h.get("snippet") or "")[:160],
                 "entity_match": h.get("_entity_match", 0)}
                for h in hits
            ]
        result_n = len(out)
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        ms = int((_time.perf_counter() - t0) * 1000)
        _events.set_client("cli", "")
        _events.log(
            root,
            "context_workspace_search" if workspace_mode else "context_search",
            query=args[0], result_n=result_n, ms=ms,
        )


def reject() -> None:
    """cruxhive-reject: reject a pending entry. Args: <path>"""
    args = sys.argv[1:]
    if not args:
        print("Usage: cruxhive-reject <path>", file=sys.stderr)
        sys.exit(1)
    from . import store as _store
    root = os.getcwd()
    conn = _store.connect(root)
    ok = _store.reject(conn, args[0], root)
    conn.close()
    if ok:
        print(f"  \033[32m✓\033[0m  Rejected: {args[0]}")
    else:
        print(f"  \033[31m✗\033[0m  Not found: {args[0]}", file=sys.stderr)
        sys.exit(1)


# ── Stats / observability ─────────────────────────────────────────────────────

def _c(s: str, code: str) -> str:
    if not sys.stdout.isatty():
        return s
    return f"\033[{code}m{s}\033[0m"


def _bar(value: float, max_value: float, width: int = 20) -> str:
    if max_value <= 0:
        return " " * width
    filled = int(round(width * value / max_value))
    return "█" * filled + "·" * (width - filled)


def _parse_flags(argv: list[str]) -> dict:
    out: dict = {
        "days": 7, "by": None, "gaps": False, "stale": False,
        "export": None, "clear": False, "json": False,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--days", "-d") and i + 1 < len(argv):
            try: out["days"] = int(argv[i + 1])
            except ValueError: pass
            i += 2
        elif a == "--by" and i + 1 < len(argv):
            out["by"] = argv[i + 1]
            i += 2
        elif a == "--gaps":   out["gaps"] = True;  i += 1
        elif a == "--stale":  out["stale"] = True; i += 1
        elif a == "--clear":  out["clear"] = True; i += 1
        elif a == "--json":   out["json"] = True;  i += 1
        elif a == "--export" and i + 1 < len(argv):
            out["export"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return out


def stats() -> None:
    """cruxhive-stats: usage & knowledge-base observability dashboard."""
    import json as _json
    from pathlib import Path
    from . import events as _events
    from . import store as _store

    flags = _parse_flags(sys.argv[1:])
    root = os.getcwd()
    db_path = Path(root) / ".llm" / "cruxhive.db"

    if not db_path.exists():
        print(f"  {_c('!', '33')}  No knowledge base found at .llm/cruxhive.db")
        print(f"       Run \033[36mcruxhive init\033[0m then \033[36mcruxhive index\033[0m")
        sys.exit(1)

    conn = _store.connect(root)

    # Clear log
    if flags["clear"]:
        n = _events.clear(conn)
        conn.close()
        print(f"  {_c('✓', '32')}  Cleared {n} event(s) from log.")
        return

    # Export CSV / JSON
    if flags["export"]:
        rows = conn.execute(
            "SELECT ts, session_id, client_name, client_ver, tool, "
            "query, result_n, ms, meta FROM events ORDER BY id"
        ).fetchall()
        if flags["export"] == "csv":
            import csv
            w = csv.writer(sys.stdout)
            w.writerow(["ts", "session_id", "client_name", "client_ver",
                        "tool", "query", "result_n", "ms", "meta"])
            for r in rows:
                w.writerow([r[k] for k in
                            ("ts", "session_id", "client_name", "client_ver",
                             "tool", "query", "result_n", "ms", "meta")])
        else:
            print(_json.dumps([dict(r) for r in rows], indent=2, default=str))
        conn.close()
        return

    days = flags["days"]
    sum_ = _events.summary(conn, days=days)
    kb_stats = _store.stats(conn)
    pend = _events.pending_age(conn)

    if flags["json"]:
        out = {
            "days": days,
            "summary": sum_,
            "knowledge_base": kb_stats,
            "pending": pend,
            "by_tool": _events.by_tool(conn, days=days),
            "gaps": _events.top_gaps(conn, days=max(days, 30)),
            "stale": _events.stale_entries(conn, days=60),
        }
        print(_json.dumps(out, indent=2, default=str))
        conn.close()
        return

    proj = Path(root).name
    print()
    print(f"  {_c('CruxHive stats', '1')} · last {days} days · {proj}")
    print()

    # Headline counters
    hit_pct = f"{sum_['hit_rate']*100:.0f}%" if sum_["searches"] else "—"
    print(f"  {_c('Activity', '36')}")
    print(f"    {sum_['total_calls']:>5}  total tool calls")
    print(f"    {sum_['searches']:>5}  searches · {hit_pct} hit rate")
    print(f"    {sum_['proposals']:>5}  proposals")
    print()

    # Knowledge base health
    decayed = _store.stale_high_confidence(conn)
    print(f"  {_c('Knowledge base', '36')}")
    print(f"    {kb_stats['total']:>5}  entries indexed")
    print(f"    {kb_stats['pending']:>5}  pending approval"
          + (f" (oldest {pend['oldest_days']}d, avg {pend['avg_days']}d)"
             if pend["count"] else ""))
    print(f"    {kb_stats['constraints']:>5}  constraints")
    if decayed:
        print(f"    {len(decayed):>5}  high-confidence entries decayed (need revalidation)")
    if kb_stats["by_type"]:
        types = " · ".join(f"{t}:{n}" for t, n in sorted(kb_stats["by_type"].items()))
        print(f"           {_c(types, '90')}")
    print()

    # By tool
    tool_rows = _events.by_tool(conn, days=days)
    if tool_rows:
        print(f"  {_c('By AI tool', '36')}")
        print(f"    {'client':<14} {'calls':>6} {'search':>7} {'hits%':>7} "
              f"{'gaps':>5} {'props':>6} {'sess':>5}")
        for r in tool_rows:
            hits = r["hits"] or 0
            searches = r["searches"] or 0
            pct = f"{hits/searches*100:.0f}%" if searches else "—"
            print(f"    {r['client'][:14]:<14} {r['calls']:>6} {searches:>7} "
                  f"{pct:>7} {r['zero_results'] or 0:>5} "
                  f"{r['proposals'] or 0:>6} {r['sessions']:>5}")
        print()

    # Daily sparkline
    daily = _events.daily_counts(conn, days=days)
    if daily:
        max_n = max(d["n"] for d in daily) or 1
        ticks = "▁▂▃▄▅▆▇█"
        spark = "".join(ticks[min(len(ticks) - 1, int((d["n"] / max_n) * (len(ticks) - 1)))]
                        for d in daily)
        print(f"  {_c('Daily activity', '36')}  {spark}  (peak {max_n})")
        print()

    # Gaps
    if flags["gaps"] or flags["by"] is None:
        gaps = _events.top_gaps(conn, days=max(days, 30), limit=10)
        if gaps:
            print(f"  {_c('Top gaps', '36')}  (zero-result queries — what to document)")
            for i, g in enumerate(gaps, 1):
                clients = g["clients"] or ""
                times_str = f"{g['times']}×"
                print(f"    {i}. {_c(g['query'][:60], '33')}  "
                      f"{_c(times_str, '90')}  "
                      f"{_c(clients, '90')}")
            print()

    # Stale entries
    if flags["stale"]:
        stale = _events.stale_entries(conn, days=60)
        if stale:
            print(f"  {_c('Stale entries', '36')}  (mtime > 60 days)")
            for s in stale[:10]:
                from datetime import datetime as _dt
                d = _dt.fromtimestamp(s["mtime"]).date().isoformat()
                print(f"    {d}  [{s.get('type','?')}]  {s['path']}")
            print()

    conn.close()
