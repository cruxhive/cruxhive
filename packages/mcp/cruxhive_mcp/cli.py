"""Thin CLI entry points called by @cruxhive/cli shell commands."""
from __future__ import annotations

import os
import sys


def index() -> None:
    """cruxhive-index: index .llm/ into SQLite."""
    from . import store as _store
    from . import embedder as _emb

    root = os.getcwd()
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

    fpath.write_text(
        f"---\ntype: {entry_type}\nscope: {scope}\ntopic: {topic}\n"
        f"valid_at: {date}\ninvalid_at: ~\nconfidence: medium\n"
        f"source: ai-proposed\napproved_by: ~\n---\n\n{content}\n",
        encoding="utf-8",
    )
    try:
        _store.index(root)
    except Exception:
        pass

    rel = str(fpath.relative_to(root))
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


def digest() -> None:
    """cruxhive-digest: weekly markdown report of gaps, staleness, queue health."""
    from datetime import date
    from pathlib import Path
    from . import events as _events
    from . import store as _store

    days = 7
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a in ("--days", "-d") and i + 1 < len(args) and args[i + 1].isdigit():
            days = int(args[i + 1])

    root = os.getcwd()
    proj = Path(root).name
    if not (Path(root) / ".llm" / "cruxhive.db").exists():
        print(f"# CruxHive digest — {proj}\n\n_No knowledge base yet. Run `cruxhive init` then `cruxhive index`._")
        sys.exit(1)

    conn = _store.connect(root)
    summary = _events.summary(conn, days=days)
    by_tool = _events.by_tool(conn, days=days)
    gaps = _events.top_gaps(conn, days=max(days, 30), limit=10)
    pend = _events.pending_age(conn)
    decayed = _store.stale_high_confidence(conn)
    kb = _store.stats(conn)
    conn.close()

    today = date.today().isoformat()
    out = []
    out.append(f"# CruxHive digest — {proj}")
    out.append(f"_Generated {today} · window: last {days} days_\n")

    # Headline
    hit_pct = f"{summary['hit_rate']*100:.0f}%" if summary["searches"] else "—"
    out.append(f"## Snapshot")
    out.append(f"- **{kb['total']}** entries · **{kb['pending']}** pending · **{kb['constraints']}** constraints")
    out.append(f"- **{summary['total_calls']}** tool calls · **{summary['searches']}** searches · **{hit_pct}** hit rate")
    out.append(f"- **{summary['proposals']}** new proposals\n")

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
    if decayed:
        out.append(f"## High-confidence entries that have decayed")
        out.append(f"_These were marked `confidence: high` but haven't been revalidated. Effective confidence has been auto-downgraded for search ranking._\n")
        for d in decayed[:8]:
            out.append(f"- `{d['path']}` — {d['age_days']}d old, now **{d['effective_confidence']}** (was high)")
        if len(decayed) > 8:
            out.append(f"- … and {len(decayed) - 8} more")
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
    if decayed:
        suggestions.append(f"Revalidate the {len(decayed)} decayed high-confidence entr{'ies' if len(decayed) != 1 else 'y'}")
    if pend["count"] and pend["oldest_days"] > 7:
        suggestions.append("Drain the pending review queue")
    if not suggestions:
        suggestions.append("Knowledge base is healthy. Carry on.")
    for s in suggestions:
        out.append(f"- {s}")

    print("\n".join(out))


def search() -> None:
    """cruxhive-search: BM25 search. Prints JSON. Args: <query> [n]"""
    import json
    args = sys.argv[1:]
    if not args:
        print("Usage: cruxhive-search <query> [n]", file=sys.stderr)
        sys.exit(1)
    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
    from . import store as _store
    root = os.getcwd()
    try:
        conn = _store.connect(root)
        hits = _store.search_bm25(conn, args[0], n)
        conn.close()
        # Trim to fields the CLI cares about
        out = [
            {"path": h.get("path"), "topic": h.get("topic"),
             "type": h.get("type"), "snippet": (h.get("snippet") or "")[:160]}
            for h in hits
        ]
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


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
