"""Event log for observability.

Single append-only table inside .llm/cruxhive.db. Tracks every MCP tool call
with the calling AI tool, query, result count, and latency. All local — no
network calls, no telemetry leaving the machine.

Disable with: CRUXHIVE_ANALYTICS=0
"""
from __future__ import annotations

import contextvars
import datetime
import json
import os
import sqlite3
import time
import uuid
from functools import wraps
from pathlib import Path
from typing import Any, Callable

# Per-session client info, set on MCP initialize. ContextVar is async-safe.
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_cruxhive_session_id", default=""
)
_client_name: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_cruxhive_client_name", default=""
)
_client_ver: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_cruxhive_client_ver", default=""
)

# Optional reference to the FastMCP instance for MCP-protocol clientInfo lookup.
# Set by server.py at startup. Falls back to env-var detection if missing.
_mcp_ref: list = []

DB_PATH = ".llm/cruxhive.db"
MAX_ROWS = 100_000  # cap log size, trim oldest beyond this


def attach_mcp(mcp_instance) -> None:
    """Register the FastMCP instance so we can read clientInfo via the protocol."""
    _mcp_ref.clear()
    _mcp_ref.append(mcp_instance)


def _client_from_mcp() -> tuple[str, str]:
    """Read clientInfo from the active MCP session, if available.

    FastMCP exposes the InitializeRequestParams via session.client_params, which
    carries clientInfo.name / clientInfo.version. Returns ('', '') outside a
    request or if the MCP ref isn't set.
    """
    if not _mcp_ref:
        return ("", "")
    try:
        ctx = _mcp_ref[0].get_context()
        params = ctx.session.client_params
        if params and params.clientInfo:
            return (
                params.clientInfo.name or "",
                params.clientInfo.version or "",
            )
    except Exception:
        pass
    return ("", "")


def _enabled() -> bool:
    return os.environ.get("CRUXHIVE_ANALYTICS", "1") not in {"0", "false", "no"}


def _infer_client_from_env() -> tuple[str, str]:
    """Best-effort client detection when MCP clientInfo is unavailable.

    Returns (name, version). Returns ('', '') if unknown.
    """
    # Claude Code sets these
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION"):
        return ("claude-code", os.environ.get("CLAUDE_CODE_VERSION", ""))
    # OpenCode
    if os.environ.get("OPENCODE_SESSION") or os.environ.get("OPENCODE_VERSION"):
        return ("opencode", os.environ.get("OPENCODE_VERSION", ""))
    # Cursor
    if os.environ.get("CURSOR_SESSION") or "Cursor" in os.environ.get("TERM_PROGRAM", ""):
        return ("cursor", "")
    # Windsurf
    if os.environ.get("WINDSURF_SESSION") or "Windsurf" in os.environ.get("TERM_PROGRAM", ""):
        return ("windsurf", "")
    return ("", "")


def set_client(name: str, version: str = "") -> str:
    """Record client identity for the current session. Returns session id."""
    sid = uuid.uuid4().hex[:12]
    _session_id.set(sid)
    if not name:
        # Prefer real MCP clientInfo, then env-var inference
        name, version = _client_from_mcp()
    if not name:
        name, version = _infer_client_from_env()
    _client_name.set(name or "unknown")
    _client_ver.set(version or "")
    return sid


def _ensure_session() -> tuple[str, str, str]:
    """Return (session_id, client_name, client_ver), refreshing client info
    from MCP clientInfo on each call so a long-lived process re-tags events
    correctly when the client changes (e.g. server reused across connections).
    """
    sid = _session_id.get()
    cname = _client_name.get()
    if not sid:
        sid = set_client("")
        return sid, _client_name.get(), _client_ver.get()
    # On every call, try a fresh read of MCP clientInfo so the tag tracks the
    # real caller. Only overwrite if we got a non-empty result.
    mcp_name, mcp_ver = _client_from_mcp()
    if mcp_name and mcp_name != cname:
        _client_name.set(mcp_name)
        _client_ver.set(mcp_ver)
        cname = mcp_name
    return sid, cname, _client_ver.get()


def _db(root: str) -> sqlite3.Connection:
    p = Path(root) / DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    _init(conn)
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            session_id  TEXT    NOT NULL,
            client_name TEXT,
            client_ver  TEXT,
            tool        TEXT    NOT NULL,
            query       TEXT,
            result_n    INTEGER,
            ms          INTEGER,
            meta        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_events_tool ON events(tool, ts);
        CREATE INDEX IF NOT EXISTS idx_events_client ON events(client_name, ts);
    """)


def log(
    root: str,
    tool: str,
    query: str = "",
    result_n: int | None = None,
    ms: int | None = None,
    meta: dict | None = None,
) -> None:
    """Write one row. Silent on failure — observability must never break MCP."""
    if not _enabled():
        return
    try:
        sid, cname, cver = _ensure_session()
        conn = _db(root)
        conn.execute(
            "INSERT INTO events (ts, session_id, client_name, client_ver, "
            "tool, query, result_n, ms, meta) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                sid, cname, cver, tool,
                (query or "")[:500],
                result_n,
                ms,
                json.dumps(meta) if meta else None,
            ),
        )
        # Cheap log rotation: every ~1000 inserts, trim oldest beyond MAX_ROWS
        if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] > MAX_ROWS:
            conn.execute(
                "DELETE FROM events WHERE id IN "
                "(SELECT id FROM events ORDER BY id LIMIT ?)",
                (MAX_ROWS // 10,),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


def trace(tool_name: str, query_kw: str | None = None):
    """Decorator: log a tool call with latency. result_n inferred from int returns or list len.

    query_kw: name of the kwarg to record as the 'query' field (e.g. 'query', 'topic', 'path').
    """
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            root = kwargs.get("project_root") or os.getcwd()
            q = ""
            if query_kw and query_kw in kwargs:
                q = str(kwargs.get(query_kw) or "")
            result_n: int | None = None
            try:
                rv = fn(*args, **kwargs)
                # Heuristic: count result lines from the canonical "## Results" format
                if isinstance(rv, str):
                    if "No results" in rv or "empty" in rv.lower():
                        result_n = 0
                    elif "## Results" in rv:
                        result_n = rv.count("\n**") // 1  # crude but consistent
                return rv
            finally:
                ms = int((time.perf_counter() - t0) * 1000)
                log(root, tool_name, query=q, result_n=result_n, ms=ms)
        return wrapper
    return deco


# ── Aggregation queries (used by CLI + UI) ─────────────────────────────────────

def summary(conn: sqlite3.Connection, days: int = 7) -> dict:
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    total = conn.execute(
        "SELECT COUNT(*) FROM events WHERE ts >= ?", (cutoff,)
    ).fetchone()[0]
    searches = conn.execute(
        "SELECT COUNT(*) FROM events WHERE tool='context_search' AND ts >= ?",
        (cutoff,),
    ).fetchone()[0]
    hits = conn.execute(
        "SELECT COUNT(*) FROM events WHERE tool='context_search' AND ts >= ? "
        "AND result_n IS NOT NULL AND result_n > 0",
        (cutoff,),
    ).fetchone()[0]
    proposals = conn.execute(
        "SELECT COUNT(*) FROM events WHERE tool='context_propose' AND ts >= ?",
        (cutoff,),
    ).fetchone()[0]
    sessions = conn.execute(
        "SELECT COUNT(*) FROM events WHERE tool='session_start' AND ts >= ?",
        (cutoff,),
    ).fetchone()[0]
    return {
        "days": days,
        "total_calls": total,
        "searches": searches,
        "hits": hits,
        "hit_rate": (hits / searches) if searches else 0.0,
        "proposals": proposals,
        "sessions": sessions,
    }


def by_tool(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    """Per-AI-tool breakdown."""
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute("""
        SELECT
            COALESCE(NULLIF(client_name,''), 'unknown') AS client,
            COUNT(*) AS calls,
            SUM(CASE WHEN tool='context_search' THEN 1 ELSE 0 END) AS searches,
            SUM(CASE WHEN tool='context_search' AND result_n > 0 THEN 1 ELSE 0 END) AS hits,
            SUM(CASE WHEN tool='context_search' AND (result_n = 0 OR result_n IS NULL)
                THEN 1 ELSE 0 END) AS zero_results,
            SUM(CASE WHEN tool='context_propose' THEN 1 ELSE 0 END) AS proposals,
            COUNT(DISTINCT session_id) AS sessions
        FROM events
        WHERE ts >= ?
        GROUP BY client
        ORDER BY calls DESC
    """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def top_gaps(conn: sqlite3.Connection, days: int = 30, limit: int = 10) -> list[dict]:
    """Zero-result queries — what the AI looked for but didn't find."""
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute("""
        SELECT
            query,
            COUNT(*) AS times,
            COUNT(DISTINCT client_name) AS distinct_clients,
            GROUP_CONCAT(DISTINCT client_name) AS clients
        FROM events
        WHERE tool='context_search'
          AND (result_n = 0 OR result_n IS NULL)
          AND query != ''
          AND ts >= ?
        GROUP BY query
        ORDER BY times DESC, query
        LIMIT ?
    """, (cutoff, limit)).fetchall()
    return [dict(r) for r in rows]


def daily_counts(conn: sqlite3.Connection, days: int = 30) -> list[dict]:
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute("""
        SELECT substr(ts, 1, 10) AS day, COUNT(*) AS n
        FROM events
        WHERE ts >= ?
        GROUP BY day
        ORDER BY day
    """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def stale_entries(conn: sqlite3.Connection, days: int = 60) -> list[dict]:
    """Entries that have not appeared in any search result snippet in N days.

    Approximation: entries with no search-tool event mentioning their path.
    Cheap proxy — we don't actually log per-result paths yet, so this falls
    back to indexed-but-old by mtime.
    """
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).timestamp()
    rows = conn.execute("""
        SELECT path, type, topic, mtime
        FROM entries
        WHERE mtime < ?
          AND (invalid_at IS NULL OR invalid_at IN ('~','null','none',''))
        ORDER BY mtime ASC
        LIMIT 25
    """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def pending_age(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT path, valid_at
        FROM entries
        WHERE source = 'ai-proposed'
          AND (approved_by IS NULL OR approved_by IN ('~','null','none',''))
    """).fetchall()
    if not rows:
        return {"count": 0, "oldest_days": 0, "avg_days": 0.0}
    today = datetime.date.today()
    ages: list[int] = []
    for r in rows:
        try:
            d = datetime.date.fromisoformat((r["valid_at"] or "")[:10])
            ages.append((today - d).days)
        except Exception:
            pass
    if not ages:
        return {"count": len(rows), "oldest_days": 0, "avg_days": 0.0}
    return {
        "count": len(rows),
        "oldest_days": max(ages),
        "avg_days": round(sum(ages) / len(ages), 1),
    }


def clear(conn: sqlite3.Connection) -> int:
    n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.execute("DELETE FROM events")
    conn.commit()
    return n
