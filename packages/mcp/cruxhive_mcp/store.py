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
    _migrate(conn)
    # Also initialize the events log schema so stats queries work
    # against any store connection.
    try:
        from . import events as _events
        _events._init(conn)
    except Exception:
        pass
    return conn


# ── Schema migrations ────────────────────────────────────────────────────────
#
# Append-only registry. Each migration runs exactly once per DB and is recorded
# in the `schema_migrations` table. NEVER reorder or remove a migration that
# has shipped — add a new one that undoes the old behavior instead. Idempotent
# DDL (CREATE TABLE IF NOT EXISTS …) lives in `_init_schema`; column adds and
# data-shape changes belong here.
#
# To add a migration:
#   _MIGRATIONS.append((
#       "002-add-rejected-by",
#       "ALTER TABLE entries ADD COLUMN rejected_by TEXT",
#   ))

_MIGRATIONS: list[tuple[str, str]] = [
    # No migrations yet — schema_migrations table is created on first connect,
    # tracking begins from this revision (cruxhive-mcp >= 0.7).
]


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations idempotently. Failures are logged, not fatal —
    a failed migration is retried on the next connect() so a transient SQLite
    error (locked DB, etc.) doesn't permanently brick the store."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id         TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    conn.commit()
    applied = {
        row["id"]
        for row in conn.execute("SELECT id FROM schema_migrations").fetchall()
    }
    for mid, sql in _MIGRATIONS:
        if mid in applied:
            continue
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(id, applied_at) VALUES (?, ?)",
                (mid, datetime.datetime.now(datetime.timezone.utc).isoformat()),
            )
            conn.commit()
        except sqlite3.Error as e:
            import sys
            print(f"cruxhive: migration {mid} failed: {e}", file=sys.stderr)
            conn.rollback()


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
        CREATE TABLE IF NOT EXISTS entry_entities (
            entry_id INTEGER NOT NULL,
            entity   TEXT    NOT NULL,
            PRIMARY KEY (entry_id, entity)
        );
        CREATE INDEX IF NOT EXISTS idx_entry_entities_entity
            ON entry_entities(entity);
        CREATE TRIGGER IF NOT EXISTS _entities_ad AFTER DELETE ON entries BEGIN
            DELETE FROM entry_entities WHERE entry_id = old.id;
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

PERSONAL_ROOT = Path.home() / ".cruxhive" / "personal"


def _scan_dir(base: Path) -> list[Path]:
    if not base.exists():
        return []
    result = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for f in filenames:
            if f.endswith(".md"):
                result.append(Path(dirpath) / f)
    return result


def _scan_md_files(root: str) -> list[tuple[Path, str]]:
    """Return (absolute_path, db_path) tuples.

    db_path is what we store in the `path` column — relative for project files,
    `personal:<filename>` for files under ~/.cruxhive/personal/.
    """
    result: list[tuple[Path, str]] = []
    base = Path(root) / ".llm"
    for f in _scan_dir(base):
        result.append((f, str(f.relative_to(root))))
    # Also include personal layer — visible from every project
    if PERSONAL_ROOT.exists():
        for f in _scan_dir(PERSONAL_ROOT):
            rel = f.relative_to(PERSONAL_ROOT).as_posix()
            result.append((f, f"personal:{rel}"))
    return result


EPHEMERAL_TTL_DAYS = 7  # source: ephemeral entries auto-expire after this many days


# ── Entity extraction ────────────────────────────────────────────────────────
#
# Cheap regex-based entity tagging. Used at index time to populate
# entry_entities, then at search time to boost results that share entities
# with the query. No NER models, no new dependencies.

_ENTITY_PATTERNS = [
    re.compile(r"\b[a-z][a-z0-9]+(?:_[a-z0-9]+){1,5}\b"),   # snake_case (function/var names)
    re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b"),                   # ALL_CAPS constants / env vars
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),              # IPv4
    re.compile(r"\b[a-z0-9-]+\.[a-z0-9-]+(?:\.[a-z0-9-]+)+\b"),  # hostnames (a.b.c)
    re.compile(r"\b[\w-]+\.(?:py|js|ts|tsx|jsx|md|sh|sql|yml|yaml|toml|json|html|css)\b"),  # files w/ extension
]
_ENTITY_STOPWORDS = frozenset({
    # noise-y snake_case from common words
    "should_be", "could_be", "must_be", "would_be",
    "to_do", "to_be",
})


def extract_entities(text: str, max_entities: int = 40) -> set[str]:
    """Pull a bounded set of canonical entities from a piece of text."""
    out: set[str] = set()
    for pat in _ENTITY_PATTERNS:
        for m in pat.finditer(text or ""):
            tok = m.group(0)
            if tok.lower() in _ENTITY_STOPWORDS:
                continue
            out.add(tok)
            if len(out) >= max_entities:
                return out
    return out


def _ephemeral_expired(meta: dict) -> bool:
    """Return True if this is an ephemeral entry past its TTL."""
    if (meta.get("source") or "").strip().lower() != "ephemeral":
        return False
    try:
        d = datetime.date.fromisoformat((meta.get("valid_at") or "")[:10])
        return (datetime.date.today() - d).days > EPHEMERAL_TTL_DAYS
    except Exception:
        return False


def index(root: str, embedder=None) -> int:
    """Scan .llm/ tree + ~/.cruxhive/personal/ and upsert changed .md files.

    Side-effect: entries with `source: ephemeral` and `valid_at` older than
    EPHEMERAL_TTL_DAYS get their on-disk frontmatter stamped with
    `invalid_at: <today>`, which removes them from the index on this pass.
    """
    conn = connect(root)
    files = _scan_md_files(root)
    count = 0
    for fpath, rel in files:
        mtime = fpath.stat().st_mtime
        row = conn.execute("SELECT mtime FROM entries WHERE path=?", (rel,)).fetchone()
        if row and row["mtime"] == mtime:
            continue
        text = fpath.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_fm(text)
        # Auto-expire ephemeral entries past their TTL — stamp invalid_at on disk
        if _ephemeral_expired(meta) and rel.startswith(".llm/"):
            today = datetime.date.today().isoformat()
            new_text = _set_field(text, "invalid_at", today)
            try:
                fpath.write_text(new_text, encoding="utf-8")
                meta["invalid_at"] = today  # so the next branch fires
            except Exception:
                pass  # readonly fs / personal layer — skip
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
        # Resolve the row id once — used for both vector + entity updates
        try:
            row_id = conn.execute(
                "SELECT id FROM entries WHERE path=?", (rel,)
            ).fetchone()["id"]
        except Exception:
            row_id = None

        if vec_bytes is not None and row_id is not None:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO entry_vecs(id, vec) VALUES (?,?)",
                    (row_id, vec_bytes),
                )
            except Exception:
                pass

        # Refresh entity tags for this entry — wipe + reinsert is simplest
        if row_id is not None:
            try:
                conn.execute("DELETE FROM entry_entities WHERE entry_id=?", (row_id,))
                # Scan topic + body. Cap body slice to keep cost bounded.
                entities = extract_entities(
                    f"{meta.get('topic','')} {body[:4096]}"
                )
                if entities:
                    conn.executemany(
                        "INSERT OR IGNORE INTO entry_entities(entry_id, entity) VALUES (?,?)",
                        [(row_id, e) for e in entities],
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


def _recency_boost(mtime: float | None, now: float | None = None) -> float:
    """Banded recency multiplier added on top of search score.

    ≤7d → +0.20, ≤30d → +0.10, ≤90d → +0.05, else 0.
    """
    if not mtime:
        return 0.0
    import time as _t
    n = now if now is not None else _t.time()
    age_days = (n - mtime) / 86400
    if age_days <= 7:   return 0.20
    if age_days <= 30:  return 0.10
    if age_days <= 90:  return 0.05
    return 0.0


def _entity_boost_paths(conn: sqlite3.Connection, query: str) -> dict[str, int]:
    """Return {path: shared_entity_count} for entries that share entities with query."""
    query_entities = extract_entities(query)
    if not query_entities:
        return {}
    placeholders = ",".join("?" * len(query_entities))
    rows = conn.execute(f"""
        SELECT e.path, COUNT(*) AS shared
        FROM entry_entities ee
        JOIN entries e ON e.id = ee.entry_id
        WHERE ee.entity IN ({placeholders})
          AND (e.invalid_at IS NULL OR e.invalid_at IN ('~','null','none',''))
        GROUP BY e.path
    """, tuple(query_entities)).fetchall()
    return {r["path"]: r["shared"] for r in rows}


def rrf_fuse(
    bm25: list[dict], vec: list[dict], k: int = 60,
    conn: sqlite3.Connection | None = None, query: str = "",
) -> list[dict]:
    """Reciprocal Rank Fusion with optional entity + recency boost.

    Base: research-validated RRF with k=60.
    Entity boost: +0.10 per shared entity between query and entry (cap 0.30).
    Recency boost: banded +0.05/+0.10/+0.20 by age — see _recency_boost.

    Boosts only apply if `conn` is provided (entity lookup needs the DB).
    """
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

    # Entity + recency boosts
    if conn is not None:
        entity_hits = _entity_boost_paths(conn, query) if query else {}

        # Pull entity-only matches in as new candidates if BM25/vec missed them.
        # This lets a query like "91.99.212.250" surface entries about that IP
        # even if the literal token wasn't tokenized by FTS5.
        missing = [p for p in entity_hits if p not in by_path]
        if missing:
            ph = ",".join("?" * len(missing))
            new_rows = conn.execute(f"""
                SELECT path, type, scope, topic, confidence, source,
                       approved_by, valid_at,
                       substr(content, 1, 200) AS snippet, 0.0 AS rank
                FROM entries WHERE path IN ({ph})
            """, tuple(missing)).fetchall()
            for r in new_rows:
                d = dict(r)
                p = d["path"]
                by_path[p] = d
                # Start with a small base score so entity boost still dominates
                # rank but the entry shows up at all.
                scores[p] = scores.get(p, 0.0) + 1.0 / (k + 200)

        # Pull mtimes for all candidate paths in one query
        paths = list(by_path.keys())
        if paths:
            ph2 = ",".join("?" * len(paths))
            mtime_rows = conn.execute(
                f"SELECT path, mtime FROM entries WHERE path IN ({ph2})",
                tuple(paths),
            ).fetchall()
            mtimes = {r["path"]: r["mtime"] for r in mtime_rows}
            for p, item in by_path.items():
                shared = entity_hits.get(p, 0)
                if shared:
                    scores[p] += min(0.30, shared * 0.10)
                    item["_entity_match"] = shared
                scores[p] += _recency_boost(mtimes.get(p))

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


def list_approved_constraints(conn: sqlite3.Connection) -> list[dict]:
    """All approved (non-deprecated) constraints — used for conflict checks."""
    rows = conn.execute("""
        SELECT path, topic, content
        FROM entries
        WHERE type = 'constraint'
          AND source = 'human'
          AND (invalid_at IS NULL OR invalid_at IN ('~','null','none',''))
    """).fetchall()
    return [dict(r) for r in rows]


def annotate_pending_conflicts(conn: sqlite3.Connection, pending: list[dict]) -> list[dict]:
    """Add a `conflicts` list to each pending entry.

    Reads full content for each pending entry, then runs an NLI check against
    every approved constraint. Silent no-op if NLI model isn't installed.
    """
    try:
        from . import nli
        if not nli.is_available():
            return pending
    except Exception:
        return pending

    constraints = list_approved_constraints(conn)
    if not constraints:
        return pending

    for p in pending:
        row = conn.execute("SELECT content FROM entries WHERE path=?", (p["path"],)).fetchone()
        if not row:
            p["conflicts"] = []
            continue
        body = row["content"]
        p["conflicts"] = nli.check_conflicts(body, constraints)
    return pending


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


# ── Confidence decay ──────────────────────────────────────────────────────────

# Days an entry can sit at its stored level before decay kicks in.
_DECAY_HIGH_DAYS = 60   # high → medium after this
_DECAY_MED_DAYS = 120   # medium → low after this
_DECAY_ORDER = ("low", "medium", "high")


def _age_days(valid_at: str | None, mtime: float | None) -> int | None:
    """Days since the entry was last (re)validated."""
    if valid_at:
        try:
            d = datetime.date.fromisoformat(valid_at[:10])
            return (datetime.date.today() - d).days
        except Exception:
            pass
    if mtime:
        import time as _t
        return int((_t.time() - mtime) / 86400)
    return None


def effective_confidence(stored: str | None, valid_at: str | None,
                         mtime: float | None) -> tuple[str, int]:
    """Compute effective confidence given age. Returns (effective, age_days).

    Decay rules:
        high   stays high until {DECAY_HIGH_DAYS}d, then → medium
        medium stays medium until {DECAY_MED_DAYS}d (from valid_at), then → low
        low    stays low

    Never increases confidence. Returns the stored value unchanged if
    valid_at/mtime are unavailable.
    """
    age = _age_days(valid_at, mtime)
    s = (stored or "").strip().lower()
    if s not in _DECAY_ORDER or age is None:
        return (stored or "", age or 0)
    if s == "high" and age >= _DECAY_HIGH_DAYS:
        return ("medium" if age < _DECAY_MED_DAYS else "low", age)
    if s == "medium" and age >= _DECAY_MED_DAYS:
        return ("low", age)
    return (s, age)


def annotate_decay(conn: sqlite3.Connection, rows: list[dict]) -> list[dict]:
    """Add `effective_confidence` and `age_days` fields to each row."""
    for r in rows:
        eff, age = effective_confidence(r.get("confidence"), r.get("valid_at"), r.get("mtime"))
        r["effective_confidence"] = eff
        r["age_days"] = age
        r["decayed"] = (
            eff != (r.get("confidence") or "").strip().lower()
            and bool(r.get("confidence"))
        )
    return rows


def stale_high_confidence(conn: sqlite3.Connection) -> list[dict]:
    """Entries stored as high but decayed by age."""
    rows = conn.execute("""
        SELECT path, type, topic, confidence, valid_at, mtime
        FROM entries
        WHERE LOWER(COALESCE(confidence,'')) = 'high'
          AND (invalid_at IS NULL OR invalid_at IN ('~','null','none',''))
    """).fetchall()
    out = []
    for r in rows:
        eff, age = effective_confidence(r["confidence"], r["valid_at"], r["mtime"])
        if eff != "high":
            d = dict(r)
            d["effective_confidence"] = eff
            d["age_days"] = age
            out.append(d)
    return sorted(out, key=lambda x: -x["age_days"])


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
