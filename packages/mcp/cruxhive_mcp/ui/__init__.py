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

from .. import events as _events
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
    nav.tabs{display:flex;gap:0;border-bottom:1px solid #1e2636;
      padding:0 2rem;background:#0d1018}
    nav.tabs button{background:none;border:none;color:#64748b;
      padding:.85rem 1.25rem;font-size:.85rem;font-weight:500;cursor:pointer;
      border-bottom:2px solid transparent;transition:all .15s}
    nav.tabs button:hover{color:#e2e8f0}
    nav.tabs button.active{color:#a78bfa;border-bottom-color:#6366f1}
    main{max-width:960px;margin:2rem auto;padding:0 1.5rem}
    h2{font-size:.85rem;font-weight:600;text-transform:uppercase;
      letter-spacing:.06em;color:#64748b;margin-bottom:1rem}
    h3{font-size:.95rem;font-weight:600;color:#e2e8f0;margin:1.5rem 0 .5rem}
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
    .view{display:none}
    .view.active{display:block}
    .kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1.5rem}
    .kpi{background:#161c2d;border:1px solid #1e2636;border-radius:.5rem;padding:1rem}
    .kpi-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
      color:#64748b;margin-bottom:.4rem}
    .kpi-value{font-size:1.5rem;font-weight:700;color:#e2e8f0}
    .kpi-sub{font-size:.7rem;color:#94a3b8;margin-top:.25rem}
    table{width:100%;border-collapse:collapse;font-size:.82rem}
    table thead{background:#161c2d;color:#94a3b8;text-align:left}
    table th, table td{padding:.65rem .85rem;border-bottom:1px solid #1e2636}
    table th{font-weight:500;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}
    table tbody tr:hover{background:#161c2d}
    .num{text-align:right;font-variant-numeric:tabular-nums}
    .pill{display:inline-block;font-size:.7rem;padding:.15rem .5rem;border-radius:1rem;
      background:#1e2636;color:#94a3b8}
    .gap-row{background:#161c2d;border:1px solid #1e2636;border-radius:.5rem;
      padding:.75rem 1rem;margin-bottom:.4rem;display:flex;align-items:center;gap:.75rem}
    .gap-q{flex:1;font-family:monospace;font-size:.82rem;color:#fbbf24}
    .spark{font-family:monospace;letter-spacing:.05em;color:#a78bfa;font-size:1.1rem}
    .filter-bar{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;
      font-size:.8rem;color:#94a3b8}
    select{background:#0f1117;border:1px solid #2d3748;color:#e2e8f0;
      padding:.35rem .65rem;border-radius:.3rem;font-size:.78rem}
  </style>
</head>
<body>
<header>
  <h1>Crux<span>Hive</span></h1>
  <div class="stats" id="stats"></div>
</header>
<nav class="tabs">
  <button class="active" data-tab="approvals">Approvals</button>
  <button data-tab="usage">Usage</button>
  <button data-tab="models">By AI Tool</button>
  <button data-tab="gaps">Gaps &amp; Staleness</button>
</nav>
<main>
  <!-- ─── Approvals view (original) ─────────────────────────────────────── -->
  <div class="view active" id="view-approvals">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
      <h2>Pending Proposals</h2>
      <label style="font-size:.78rem;color:#94a3b8">
        Your name:
        <input class="approver" id="approver-input" placeholder="your-username">
      </label>
    </div>
    <div id="pending-list"></div>
  </div>

  <!-- ─── Usage view ────────────────────────────────────────────────────── -->
  <div class="view" id="view-usage">
    <div class="filter-bar">
      <span>Window:</span>
      <select id="usage-days" onchange="loadUsage()">
        <option value="7" selected>Last 7 days</option>
        <option value="30">Last 30 days</option>
        <option value="90">Last 90 days</option>
      </select>
    </div>
    <div class="kpi-row" id="usage-kpis"></div>
    <h3>Daily activity</h3>
    <div class="card"><div class="spark" id="usage-spark"></div></div>
    <h3>Pending queue health</h3>
    <div class="card" id="usage-pending"></div>
  </div>

  <!-- ─── By tool view ──────────────────────────────────────────────────── -->
  <div class="view" id="view-models">
    <div class="filter-bar">
      <span>Window:</span>
      <select id="models-days" onchange="loadModels()">
        <option value="7" selected>Last 7 days</option>
        <option value="30">Last 30 days</option>
        <option value="90">Last 90 days</option>
      </select>
    </div>
    <table>
      <thead><tr>
        <th>AI tool</th>
        <th class="num">Calls</th>
        <th class="num">Searches</th>
        <th class="num">Hit rate</th>
        <th class="num">Zero-result</th>
        <th class="num">Proposals</th>
        <th class="num">Sessions</th>
      </tr></thead>
      <tbody id="models-tbody"></tbody>
    </table>
    <p style="margin-top:1rem;font-size:.75rem;color:#64748b">
      Hit rate compares which model finds what it's looking for. Zero-result
      queries show where its expectations don't match your knowledge base.
    </p>
  </div>

  <!-- ─── Gaps view ─────────────────────────────────────────────────────── -->
  <div class="view" id="view-gaps">
    <h3>Top gaps (zero-result queries)</h3>
    <p style="font-size:.78rem;color:#94a3b8;margin-bottom:1rem">
      What your AI tools searched for but didn't find. These are the next
      things to document.
    </p>
    <div id="gaps-list"></div>

    <h3 style="margin-top:2rem">Stale entries (mtime &gt; 60 days)</h3>
    <p style="font-size:.78rem;color:#94a3b8;margin-bottom:1rem">
      Entries that may need a refresh. Stale knowledge produces confident
      wrong answers.
    </p>
    <div id="stale-list"></div>
  </div>
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

document.querySelectorAll('nav.tabs button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('nav.tabs button').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.view').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    document.getElementById('view-' + b.dataset.tab).classList.add('active');
    if (b.dataset.tab === 'usage')  loadUsage();
    if (b.dataset.tab === 'models') loadModels();
    if (b.dataset.tab === 'gaps')   loadGaps();
  });
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

function renderHeader(stats) {
  document.getElementById('stats').innerHTML = `
    <div class="stat"><strong>${stats.total}</strong>total</div>
    <div class="stat"><strong>${stats.pending}</strong>pending</div>
    <div class="stat"><strong>${stats.constraints}</strong>constraints</div>
  `;
}

async function loadApprovals() {
  const [pRes, sRes] = await Promise.all([
    fetch('/api/pending'),
    fetch('/api/stats'),
  ]);
  const pending = await pRes.json();
  renderHeader(await sRes.json());

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

async function loadUsage() {
  const d = document.getElementById('usage-days').value;
  const data = await (await fetch(`/api/usage?days=${d}`)).json();
  const s = data.summary, p = data.pending;
  const hitPct = s.searches ? (s.hit_rate * 100).toFixed(0) + '%' : '—';
  document.getElementById('usage-kpis').innerHTML = `
    <div class="kpi"><div class="kpi-label">Tool calls</div>
      <div class="kpi-value">${s.total_calls}</div>
      <div class="kpi-sub">in last ${s.days} days</div></div>
    <div class="kpi"><div class="kpi-label">Searches</div>
      <div class="kpi-value">${s.searches}</div>
      <div class="kpi-sub">${hitPct} hit rate</div></div>
    <div class="kpi"><div class="kpi-label">Proposals</div>
      <div class="kpi-value">${s.proposals}</div>
      <div class="kpi-sub">queued for review</div></div>
    <div class="kpi"><div class="kpi-label">Pending queue</div>
      <div class="kpi-value">${p.count}</div>
      <div class="kpi-sub">${p.count ? `oldest ${p.oldest_days}d · avg ${p.avg_days}d` : 'empty'}</div></div>
  `;
  const daily = data.daily || [];
  if (daily.length) {
    const max = Math.max(...daily.map(x => x.n)) || 1;
    const ticks = '▁▂▃▄▅▆▇█';
    const spark = daily.map(x => ticks[Math.min(7, Math.floor((x.n/max)*7))]).join('');
    document.getElementById('usage-spark').textContent = spark + `  (peak ${max}/day)`;
  } else {
    document.getElementById('usage-spark').textContent = 'no activity yet';
  }
  document.getElementById('usage-pending').innerHTML = p.count
    ? `<div style="display:flex;justify-content:space-between">
        <span>${p.count} proposal(s) awaiting review</span>
        <span class="pill">avg ${p.avg_days}d old · oldest ${p.oldest_days}d</span>
       </div>`
    : `<div style="color:#86efac">✓ Queue is empty — knowledge base is fully reviewed.</div>`;
}

async function loadModels() {
  const d = document.getElementById('models-days').value;
  const rows = await (await fetch(`/api/by-tool?days=${d}`)).json();
  const tb = document.getElementById('models-tbody');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="7" class="empty">No tool calls logged yet.</td></tr>';
    return;
  }
  tb.innerHTML = rows.map(r => {
    const pct = r.searches ? (r.hits / r.searches * 100).toFixed(0) + '%' : '—';
    return `<tr>
      <td>${r.client || 'unknown'}</td>
      <td class="num">${r.calls}</td>
      <td class="num">${r.searches}</td>
      <td class="num">${pct}</td>
      <td class="num">${r.zero_results || 0}</td>
      <td class="num">${r.proposals || 0}</td>
      <td class="num">${r.sessions}</td>
    </tr>`;
  }).join('');
}

async function loadGaps() {
  const [g, s] = await Promise.all([
    fetch('/api/gaps').then(r => r.json()),
    fetch('/api/stale').then(r => r.json()),
  ]);
  const gl = document.getElementById('gaps-list');
  gl.innerHTML = g.length
    ? g.map(x => `
        <div class="gap-row">
          <span class="gap-q">${x.query}</span>
          <span class="pill">${x.times}×</span>
          <span class="pill">${x.clients || '?'}</span>
        </div>`).join('')
    : '<div class="empty">No zero-result queries — AI is finding what it needs ✓</div>';

  const sl = document.getElementById('stale-list');
  sl.innerHTML = s.length
    ? s.map(x => {
        const d = new Date(x.mtime * 1000).toISOString().slice(0,10);
        return `<div class="gap-row">
          ${badge(x.type)}
          <span class="path" style="flex:1">${x.path}</span>
          <span class="pill">${d}</span>
        </div>`;
      }).join('')
    : '<div class="empty">No stale entries — knowledge base is fresh ✓</div>';
}

async function approve(path) {
  if (!approver) { toast('Enter your name first', false); return; }
  const res = await fetch('/api/approve', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({path, approver}),
  });
  if (res.ok) {
    toast(`Approved: ${path.split('/').pop()}`);
    document.getElementById('card-' + btoa(path))?.remove();
    renderHeader(await (await fetch('/api/stats')).json());
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

loadApprovals();
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

    @app.get("/api/usage")
    def api_usage(days: int = 7):
        conn = _store.connect(root)
        out = {
            "summary": _events.summary(conn, days=days),
            "daily": _events.daily_counts(conn, days=days),
            "pending": _events.pending_age(conn),
        }
        conn.close()
        return out

    @app.get("/api/by-tool")
    def api_by_tool(days: int = 7):
        conn = _store.connect(root)
        rows = _events.by_tool(conn, days=days)
        conn.close()
        return rows

    @app.get("/api/gaps")
    def api_gaps(days: int = 30, limit: int = 15):
        conn = _store.connect(root)
        rows = _events.top_gaps(conn, days=days, limit=limit)
        conn.close()
        return rows

    @app.get("/api/stale")
    def api_stale(days: int = 60):
        conn = _store.connect(root)
        rows = _events.stale_entries(conn, days=days)
        conn.close()
        return rows

    return app


def app():
    """Uvicorn factory entry point. Uses CRUXHIVE_ROOT env var for project root."""
    root = os.environ.get("CRUXHIVE_ROOT") or os.getcwd()
    return make_app(root)
