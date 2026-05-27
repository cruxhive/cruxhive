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
