"""CruxHive approval queue web UI.

Requires: pip install cruxhive-mcp[ui]
Start:    cruxhive ui   (from project root)
URL:      http://localhost:3847
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

from .. import store as _store

_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>CruxHive</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#0f1117;color:#e2e8f0;min-height:100vh}
    header{padding:1.25rem 2rem;border-bottom:1px solid #1e2636;
      display:flex;align-items:center;gap:1rem}
    header h1{font-size:1.1rem;font-weight:700;color:#f8fafc;letter-spacing:-.02em}
    header h1 span{color:#6366f1}
    .stats{display:flex;gap:1.5rem;margin-left:auto}
    .stat{font-size:.75rem;color:#94a3b8}
    .stat strong{color:#e2e8f0;font-size:.9rem;display:block}
    main{max-width:860px;margin:2rem auto;padding:0 1.5rem}
    h2{font-size:.85rem;font-weight:600;text-transform:uppercase;
      letter-spacing:.06em;color:#64748b;margin-bottom:1rem}
    .empty{padding:2rem;text-align:center;color:#64748b;
      border:1px dashed #1e2636;border-radius:.5rem}
    .card{background:#161c2d;border:1px solid #1e2636;border-radius:.5rem;
      padding:1.25rem;margin-bottom:.75rem}
    .card-header{display:flex;align-items:flex-start;gap:.75rem;margin-bottom:.5rem}
    .badge{font-size:.7rem;font-weight:600;padding:.2rem .5rem;border-radius:.25rem;
      text-transform:uppercase;white-space:nowrap}
    .badge-fact{background:#1e3a5f;color:#60a5fa}
    .badge-constraint{background:#3b1414;color:#f87171}
    .badge-decision{background:#1e3b2d;color:#4ade80}
    .badge-pattern{background:#2d2b1e;color:#fbbf24}
    .badge-plan{background:#2d1e3b;color:#c084fc}
    .badge-research{background:#1e2d3b;color:#38bdf8}
    .badge-outcome{background:#1e2e1e;color:#86efac}
    .badge-other{background:#1e2636;color:#94a3b8}
    .path{font-size:.78rem;color:#94a3b8;font-family:monospace;flex:1;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .meta{font-size:.75rem;color:#64748b;margin-bottom:.75rem}
    .preview{font-size:.8rem;color:#94a3b8;line-height:1.5;
      background:#0f1117;border-left:2px solid #1e2636;
      padding:.5rem .75rem;border-radius:0 .25rem .25rem 0;
      margin-bottom:.875rem;white-space:pre-wrap;max-height:120px;overflow:hidden}
    .actions{display:flex;gap:.5rem}
    button{cursor:pointer;font-size:.78rem;font-weight:600;padding:.4rem .9rem;
      border-radius:.3rem;border:none;transition:opacity .15s}
    .btn-approve{background:#22c55e;color:#0f1117}
    .btn-reject{background:#1e2636;color:#94a3b8;border:1px solid #2d3748}
    button:hover{opacity:.85}
    button:disabled{opacity:.4;cursor:not-allowed}
    .toast{position:fixed;bottom:1.5rem;right:1.5rem;padding:.75rem 1.25rem;
      border-radius:.4rem;font-size:.82rem;font-weight:600;opacity:0;
      transition:opacity .2s;pointer-events:none}
    .toast.show{opacity:1}
    .toast-ok{background:#22c55e;color:#0f1117}
    .toast-err{background:#ef4444;color:#fff}
    input.approver{background:#0f1117;border:1px solid #2d3748;color:#e2e8f0;
      padding:.35rem .65rem;border-radius:.3rem;font-size:.78rem;width:130px}
  </style>
</head>
<body>
<header>
  <h1>Crux<span>Hive</span></h1>
  <div class="stats" id="stats"></div>
</header>
<main>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
    <h2>Pending Proposals</h2>
    <label style="font-size:.78rem;color:#94a3b8">
      Your name:
      <input class="approver" id="approver-input" placeholder="your-username">
    </label>
  </div>
  <div id="pending-list"></div>
</main>
<div class="toast" id="toast"></div>
<script>
const ROOT = '';
let approver = localStorage.getItem('cruxhive-approver') || '';

document.getElementById('approver-input').value = approver;
document.getElementById('approver-input').addEventListener('input', e => {
  approver = e.target.value.trim();
  localStorage.setItem('cruxhive-approver', approver);
});

function badge(type) {
  const cls = ['fact','constraint','decision','pattern','plan','research','outcome']
    .includes(type) ? type : 'other';
  return `<span class="badge badge-${cls}">${type||'?'}</span>`;
}

function toast(msg, ok=true) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${ok?'toast-ok':'toast-err'} show`;
  setTimeout(() => el.className = 'toast', 2200);
}

async function load() {
  const [pRes, sRes] = await Promise.all([
    fetch('/api/pending'),
    fetch('/api/stats'),
  ]);
  const pending = await pRes.json();
  const stats = await sRes.json();

  document.getElementById('stats').innerHTML = `
    <div class="stat"><strong>${stats.total}</strong>total</div>
    <div class="stat"><strong>${stats.pending}</strong>pending</div>
    <div class="stat"><strong>${stats.constraints}</strong>constraints</div>
  `;

  const list = document.getElementById('pending-list');
  if (!pending.length) {
    list.innerHTML = '<div class="empty">No pending proposals — knowledge base is fully reviewed ✓</div>';
    return;
  }
  list.innerHTML = pending.map(p => `
    <div class="card" id="card-${btoa(p.path)}">
      <div class="card-header">
        ${badge(p.type)}
        <span class="path">${p.path}</span>
      </div>
      <div class="meta">${p.topic ? `topic: ${p.topic} · ` : ''}proposed: ${p.valid_at||'?'}</div>
      <div class="preview">${p.preview || ''}</div>
      <div class="actions">
        <button class="btn-approve" onclick="approve('${p.path}')">✓ Approve</button>
        <button class="btn-reject" onclick="reject('${p.path}')">✗ Reject</button>
      </div>
    </div>
  `).join('');
}

async function approve(path) {
  if (!approver) { toast('Enter your name first', false); return; }
  const res = await fetch('/api/approve', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({path, approver}),
  });
  if (res.ok) {
    toast(`Approved: ${path.split('/').pop()}`);
    const id = 'card-' + btoa(path);
    document.getElementById(id)?.remove();
    const stats = await (await fetch('/api/stats')).json();
    document.querySelector('#stats').innerHTML = `
      <div class="stat"><strong>${stats.total}</strong>total</div>
      <div class="stat"><strong>${stats.pending}</strong>pending</div>
      <div class="stat"><strong>${stats.constraints}</strong>constraints</div>
    `;
  } else {
    toast('Approve failed', false);
  }
}

async function reject(path) {
  const res = await fetch('/api/reject', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({path}),
  });
  if (res.ok) {
    toast(`Rejected: ${path.split('/').pop()}`);
    document.getElementById('card-' + btoa(path))?.remove();
  } else {
    toast('Reject failed', false);
  }
}

load();
</script>
</body>
</html>"""


def make_app(project_root: str | None = None) -> "FastAPI":  # type: ignore[name-defined]
    if not _FASTAPI_AVAILABLE:
        raise ImportError(
            "fastapi not installed. Run: pip install cruxhive-mcp[ui]"
        )

    root = project_root or os.getcwd()
    app = FastAPI(title="CruxHive", docs_url=None, redoc_url=None)

    class ApproveReq(BaseModel):
        path: str
        approver: str

    class RejectReq(BaseModel):
        path: str

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _HTML

    @app.get("/api/pending")
    def api_pending():
        conn = _store.connect(root)
        data = _store.list_pending(conn)
        conn.close()
        return data

    @app.get("/api/stats")
    def api_stats():
        conn = _store.connect(root)
        data = _store.stats(conn)
        conn.close()
        return data

    @app.post("/api/approve")
    def api_approve(req: ApproveReq):
        conn = _store.connect(root)
        ok = _store.approve(conn, req.path, req.approver, root)
        conn.close()
        if not ok:
            raise HTTPException(404, detail="entry not found")
        return {"ok": True}

    @app.post("/api/reject")
    def api_reject(req: RejectReq):
        conn = _store.connect(root)
        ok = _store.reject(conn, req.path, root)
        conn.close()
        if not ok:
            raise HTTPException(404, detail="entry not found")
        return {"ok": True}

    return app


def app():
    """Uvicorn factory entry point. Uses CRUXHIVE_ROOT env var for project root."""
    root = os.environ.get("CRUXHIVE_ROOT") or os.getcwd()
    return make_app(root)
