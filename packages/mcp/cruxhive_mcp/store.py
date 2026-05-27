"""SQLite knowledge store: FTS5 BM25 + optional sqlite-vec hybrid search.

Schema lives at .llm/cruxhive.db — one DB per project root.
"""
from __future__ import annotations

import datetime
import os
import re
import sqlite3
from pathlib import Path

from .frontmatter import parse as _parse_fm, set_field as _set_field

DB_PATH = ".llm/cruxhive.db"
_SKIP_DIRS = {"__pycache__", ".git", "node_modules", "dist", "vendor"}
# Null-ish YAML values treated as empty
_NULL_VALUES = {"~", "null", "none", "", "~\n"}


def _is_null(v: str | None) -> bool:
    return v is None or v.strip().lower() in _NULL_VALUES


def _db_path(root: str) -> Path:
    return Path(root) / DB_PATH


def connect(root: str) -> sqlite3.Connection:
    p = _db_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    _try_load_vec(conn)
    _init_schema(conn)
    return conn


def _try_load_vec(conn: sqlite3.Connection) -> None:
    try:
        import sqlite_vec  # type: ignore[import]
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception:
        pass


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            path        TEXT    UNIQUE NOT NULL,
            type        TEXT,
            scope       TEXT,
            topic       TEXT,
            valid_at    TEXT,
            invalid_at  TEXT,
            confidence  TEXT,
            source      TEXT,
            approved_by TEXT,
            content     TEXT NOT NULL DEFAULT '',
            mtime       REAL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
            topic, content,
            content=entries, content_rowid=id,
            tokenize='porter ascii'
        );
        CREATE TRIGGER IF NOT EXISTS _fts_ai AFTER INSERT ON entries BEGIN
            INSERT INTO entries_fts(rowid, topic, content)
            VALUES (new.id, COALESCE(new.topic,''), new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS _fts_ad AFTER DELETE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, topic, content)
            VALUES ('delete', old.id, COALESCE(old.topic,''), old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS _fts_au AFTER UPDATE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, topic, content)
            VALUES ('delete', old.id, COALESCE(old.topic,''), old.content);
            INSERT INTO entries_fts(rowid, topic, content)
            VALUES (new.id, COALESCE(new.topic,''), new.content);
        END;
    """)
    # sqlite-vec virtual table — only if extension loaded
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entry_vecs
            USING vec0(id INTEGER PRIMARY KEY, vec FLOAT[768])
        """)
    except Exception:
        pass
    conn.commit()


# ── Indexing ──────────────────────────────────────────────────────────────────

def _scan_md_files(root: str) -> list[Path]:
    base = Path(root) / ".llm"
    if not base.exists():
        return []
    result = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for f in filenames:
            if f.endswith(".md"):
                result.append(Path(dirpath) / f)
    return result


def index(root: str, embedder=None) -> int:
    """Scan .llm/ tree and upsert changed .md files. Returns count of updated entries."""
    conn = connect(root)
    files = _scan_md_files(root)
    count = 0
    for fpath in files:
        mtime = fpath.stat().st_mtime
        rel = str(fpath.relative_to(root))
        row = conn.execute("SELECT mtime FROM entries WHERE path=?", (rel,)).fetchone()
        if row and row["mtime"] == mtime:
            continue
        text = fpath.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_fm(text)
        if not _is_null(meta.get("invalid_at")):
            # Deprecated entry — remove from index
            conn.execute("DELETE FROM entries WHERE path=?", (rel,))
            count += 1
            continue
        vec_bytes = None
        if embedder is not None:
            try:
                embed_text = f"{meta.get('topic', '')} {body[:512]}"
                vec_bytes = embedder.encode_bytes(embed_text)
            except Exception:
                pass
        conn.execute("""
            INSERT INTO entries
                (path, type, scope, topic, valid_at, invalid_at,
                 confidence, source, approved_by, content, mtime)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                type=excluded.type, scope=excluded.scope, topic=excluded.topic,
                valid_at=excluded.valid_at, invalid_at=excluded.invalid_at,
                confidence=excluded.confidence, source=excluded.source,
                approved_by=excluded.approved_by, content=excluded.content,
                mtime=excluded.mtime
        """, (
            rel,
            meta.get("type"), meta.get("scope"), meta.get("topic"),
            meta.get("valid_at"), meta.get("invalid_at"),
            meta.get("confidence"), meta.get("source"), meta.get("approved_by"),
            text, mtime,
        ))
        if vec_bytes is not None:
            try:
                row_id = conn.execute(
                    "SELECT id FROM entries WHERE path=?", (rel,)
                ).fetchone()["id"]
                conn.execute(
                    "INSERT OR REPLACE INTO entry_vecs(id, vec) VALUES (?,?)",
                    (row_id, vec_bytes),
                )
            except Exception:
                pass
        count += 1
    conn.commit()
    conn.close()
    return count


# ── Search ────────────────────────────────────────────────────────────────────

def search_bm25(conn: sqlite3.Connection, query: str, n: int = 10) -> list[dict]:
    try:
        rows = conn.execute("""
            SELECT e.path, e.type, e.scope, e.topic, e.confidence,
                   e.source, e.approved_by, e.valid_at,
                   snippet(entries_fts, 1, '[', ']', '...', 24) AS snippet,
                   rank
            FROM entries_fts
            JOIN entries e ON e.id = entries_fts.rowid
            WHERE entries_fts MATCH ?
              AND (e.invalid_at IS NULL OR e.invalid_at IN ('~','null','none',''))
            ORDER BY rank
            LIMIT ?
        """, (query, n)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def search_vec(conn: sqlite3.Connection, query_vec_bytes: bytes, n: int = 10) -> list[dict]:
    try:
        rows = conn.execute("""
            SELECT e.path, e.type, e.scope, e.topic, e.confidence,
                   e.source, e.approved_by, e.valid_at,
                   '' AS snippet, v.distance AS rank
            FROM entry_vecs v
            JOIN entries e ON e.id = v.id
            WHERE v.vec MATCH ?
              AND (e.invalid_at IS NULL OR e.invalid_at IN ('~','null','none',''))
            ORDER BY v.distance
            LIMIT ?
        """, (query_vec_bytes, n)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def rrf_fuse(bm25: list[dict], vec: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion. k=60 is the research-validated default."""
    scores: dict[str, float] = {}
    by_path: dict[str, dict] = {}
    for rank, item in enumerate(bm25):
        p = item["path"]
        scores[p] = scores.get(p, 0.0) + 1.0 / (k + rank + 1)
        by_path[p] = item
    for rank, item in enumerate(vec):
        p = item["path"]
        scores[p] = scores.get(p, 0.0) + 1.0 / (k + rank + 1)
        by_path.setdefault(p, item)
    return [by_path[p] for p in sorted(scores, key=lambda x: -scores[x])]


# ── Proposals ─────────────────────────────────────────────────────────────────

def list_pending(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT path, type, scope, topic, confidence, source,
               approved_by, valid_at,
               substr(content, 1, 300) AS preview
        FROM entries
        WHERE source = 'ai-proposed'
          AND (approved_by IS NULL OR approved_by IN ('~','null','none',''))
        ORDER BY valid_at DESC
    """).fetchall()
    return [dict(r) for r in rows]


def approve(conn: sqlite3.Connection, path: str, approver: str, root: str) -> bool:
    fpath = Path(root) / path
    if not fpath.exists():
        return False
    text = fpath.read_text(encoding="utf-8")
    text = _set_field(text, "source", "human")
    text = _set_field(text, "approved_by", approver)
    fpath.write_text(text, encoding="utf-8")
    conn.execute(
        "UPDATE entries SET source='human', approved_by=? WHERE path=?",
        (approver, path),
    )
    conn.commit()
    return True


def reject(conn: sqlite3.Connection, path: str, root: str) -> bool:
    fpath = Path(root) / path
    if not fpath.exists():
        return False
    today = datetime.date.today().isoformat()
    text = fpath.read_text(encoding="utf-8")
    text = _set_field(text, "invalid_at", today)
    fpath.write_text(text, encoding="utf-8")
    conn.execute("DELETE FROM entries WHERE path=?", (path,))
    conn.commit()
    return True


# ── Stats ─────────────────────────────────────────────────────────────────────

def stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE source='ai-proposed' "
        "AND (approved_by IS NULL OR approved_by IN ('~','null','none',''))"
    ).fetchone()[0]
    constraints = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE type='constraint'"
    ).fetchone()[0]
    by_type = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT type, COUNT(*) FROM entries WHERE type IS NOT NULL GROUP BY type"
        ).fetchall()
    }
    return {
        "total": total,
        "pending": pending,
        "constraints": constraints,
        "by_type": by_type,
    }
