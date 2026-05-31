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

# Path to bundled docs/guide.html (force-included by hatchling at wheel build).
# Falls back to repo path when running editable from source.
_BUNDLED_DOCS = Path(__file__).parent.parent / "static" / "guide.html"
_REPO_DOCS = Path(__file__).resolve().parents[4] / "docs" / "guide.html"


def _docs_html() -> str:
    """Return the guide.html contents, preferring the bundled copy."""
    for candidate in (_BUNDLED_DOCS, _REPO_DOCS):
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except Exception:
                continue
    return (
        "<!doctype html><html><body style='font-family:sans-serif;padding:2rem;background:#0a0a0a;color:#e2e8f0'>"
        "<h1>Docs not bundled</h1>"
        "<p>This CruxHive build doesn't include <code>guide.html</code>. "
        "See <a href='https://github.com/cruxhive/cruxhive/blob/main/docs/guide.html' style='color:#f5a524'>the GitHub source</a>.</p>"
        "</body></html>"
    )

_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>CruxHive</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' fill='none'><rect width='64' height='64' rx='12' fill='%230a0a0a'/><path d='M32 8 L55 19.5 L55 44.5 L32 56 L9 44.5 L9 19.5 Z' stroke='%23f5a524' stroke-width='3' stroke-linejoin='round'/><circle cx='32' cy='32' r='6' fill='%23f5a524'/></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'IBM Plex Sans',system-ui,-apple-system,sans-serif;
      background:#0a0a0a;color:#e2e8f0;min-height:100vh}
    header{padding:1.25rem 2rem;border-bottom:1px solid #1d1d1d;
      display:flex;align-items:center;gap:1rem}
    header h1{font-size:1.1rem;font-weight:700;color:#f8fafc;letter-spacing:-.02em}
    header h1 span{color:#f5a524}
    .stats{display:flex;gap:1.5rem;margin-left:auto;margin-right:1rem}
    .stat{font-size:.75rem;color:#94a3b8}
    .stat strong{color:#e2e8f0;font-size:.9rem;display:block}
    nav.tabs{display:flex;gap:0;border-bottom:1px solid #1d1d1d;
      padding:0 2rem;background:#0d0d0d}
    nav.tabs button{background:none;border:none;color:#64748b;
      padding:.85rem 1.25rem;font-size:.85rem;font-weight:500;cursor:pointer;
      border-bottom:2px solid transparent;transition:all .15s}
    nav.tabs button:hover{color:#e2e8f0}
    nav.tabs button.active{color:#f5a524;border-bottom-color:#f5a524}
    main{max-width:960px;margin:2rem auto;padding:0 1.5rem}
    h2{font-size:.85rem;font-weight:600;text-transform:uppercase;
      letter-spacing:.06em;color:#64748b;margin-bottom:1rem}
    h3{font-size:.95rem;font-weight:600;color:#e2e8f0;margin:1.5rem 0 .5rem}
    .empty{padding:2rem;text-align:center;color:#64748b;
      border:1px dashed #1d1d1d;border-radius:.5rem}
    .card{background:#131313;border:1px solid #1d1d1d;border-radius:.5rem;
      padding:1.25rem;margin-bottom:.75rem}
    .card-header{display:flex;align-items:flex-start;gap:.75rem;margin-bottom:.5rem}
    .badge{font-size:.7rem;font-weight:600;padding:.2rem .5rem;border-radius:.25rem;
      text-transform:uppercase;white-space:nowrap}
    .badge-fact{background:#1e3a5f;color:#60a5fa}
    .badge-constraint{background:#3b1414;color:#f87171}
    .badge-decision{background:#1e3b2d;color:#4ade80}
    .badge-pattern{background:#2d2b1e;color:#fbbf24}
    .badge-plan{background:#2d1e3b;color:#f5a524}
    .badge-research{background:#1e2d3b;color:#38bdf8}
    .badge-outcome{background:#1e2e1e;color:#86efac}
    .badge-other{background:#1d1d1d;color:#94a3b8}
    .path{font-size:.78rem;color:#94a3b8;font-family:"IBM Plex Mono","SF Mono",Menlo,monospace;flex:1;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .meta{font-size:.75rem;color:#64748b;margin-bottom:.75rem}
    .preview{font-size:.8rem;color:#94a3b8;line-height:1.5;
      background:#0a0a0a;border-left:2px solid #1d1d1d;
      padding:.5rem .75rem;border-radius:0 .25rem .25rem 0;
      margin-bottom:.875rem;white-space:pre-wrap;max-height:120px;overflow:hidden}
    .conflict-box{background:#3b1414;border-left:2px solid #f87171;
      padding:.55rem .75rem;border-radius:0 .25rem .25rem 0;
      margin-bottom:.875rem;font-size:.78rem;color:#fca5a5}
    .conflict-box .conflict-title{font-weight:600;margin-bottom:.3rem;color:#fecaca}
    .conflict-box .conflict-item{font-family:"IBM Plex Mono","SF Mono",Menlo,monospace;font-size:.72rem;
      color:#fda4af;margin-top:.25rem;opacity:.85}
    .actions{display:flex;gap:.5rem}
    button{cursor:pointer;font-size:.78rem;font-weight:600;padding:.4rem .9rem;
      border-radius:.3rem;border:none;transition:opacity .15s}
    .btn-approve{background:#22c55e;color:#0a0a0a}
    .btn-reject{background:#1d1d1d;color:#94a3b8;border:1px solid #2a2a2a}
    button:hover{opacity:.85}
    button:disabled{opacity:.4;cursor:not-allowed}
    .toast{position:fixed;bottom:1.5rem;right:1.5rem;padding:.75rem 1.25rem;
      border-radius:.4rem;font-size:.82rem;font-weight:600;opacity:0;
      transition:opacity .2s;pointer-events:none}
    .toast.show{opacity:1}
    .toast-ok{background:#22c55e;color:#0a0a0a}
    .toast-err{background:#ef4444;color:#fff}
    input.approver{background:#0a0a0a;border:1px solid #2a2a2a;color:#e2e8f0;
      padding:.35rem .65rem;border-radius:.3rem;font-size:.78rem;width:130px}
    .view{display:none}
    .view.active{display:block}
    .kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1.5rem}
    .kpi{background:#131313;border:1px solid #1d1d1d;border-radius:.5rem;padding:1rem}
    .kpi-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
      color:#64748b;margin-bottom:.4rem}
    .kpi-value{font-size:1.5rem;font-weight:700;color:#e2e8f0}
    .kpi-sub{font-size:.7rem;color:#94a3b8;margin-top:.25rem}
    table{width:100%;border-collapse:collapse;font-size:.82rem}
    table thead{background:#131313;color:#94a3b8;text-align:left}
    table th, table td{padding:.65rem .85rem;border-bottom:1px solid #1d1d1d}
    table th{font-weight:500;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}
    table tbody tr:hover{background:#131313}
    .num{text-align:right;font-variant-numeric:tabular-nums}
    .pill{display:inline-block;font-size:.7rem;padding:.15rem .5rem;border-radius:1rem;
      background:#1d1d1d;color:#94a3b8}
    .gap-row{background:#131313;border:1px solid #1d1d1d;border-radius:.5rem;
      padding:.75rem 1rem;margin-bottom:.4rem;display:flex;align-items:center;gap:.75rem}
    .gap-q{flex:1;font-family:"IBM Plex Mono","SF Mono",Menlo,monospace;font-size:.82rem;color:#fbbf24}
    .spark{font-family:"IBM Plex Mono","SF Mono",Menlo,monospace;letter-spacing:.05em;color:#f5a524;font-size:1.1rem}
    .filter-bar{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;
      font-size:.8rem;color:#94a3b8}
    select{background:#0a0a0a;border:1px solid #2a2a2a;color:#e2e8f0;
      padding:.35rem .65rem;border-radius:.3rem;font-size:.78rem}
    .kpi-strip{display:flex;gap:.4rem;padding:.5rem 2rem;background:#0d0d0d;
      border-bottom:1px solid #1d1d1d;overflow-x:auto}
    .kpi-chip{flex:0 0 auto;background:#131313;border:1px solid #1d1d1d;
      border-radius:.4rem;padding:.4rem .75rem;font-size:.72rem;color:#94a3b8;
      display:flex;flex-direction:column;line-height:1.2}
    .kpi-chip strong{font-size:.95rem;font-weight:700;color:#e2e8f0}
    .kpi-chip.good strong{color:#86efac}
    .kpi-chip.warn strong{color:#fbbf24}
    .kpi-chip.bad strong{color:#f87171}
    .kpi-chip .label{font-size:.62rem;text-transform:uppercase;
      letter-spacing:.05em;color:#64748b;margin-top:.15rem}
    [data-tip]{position:relative}
    [data-tip]:hover::after{
      content:attr(data-tip);position:absolute;left:50%;top:100%;transform:translateX(-50%);
      margin-top:.4rem;background:#0d0d0d;border:1px solid #2a2a2a;
      border-radius:.35rem;padding:.55rem .75rem;font-size:.72rem;
      font-weight:400;color:#cbd5e1;line-height:1.4;
      white-space:pre-wrap;width:260px;text-align:left;z-index:100;
      box-shadow:0 4px 16px #000c;text-transform:none;letter-spacing:0;
      pointer-events:none}
    [data-tip]:hover::before{
      content:'';position:absolute;left:50%;top:100%;transform:translateX(-50%);
      margin-top:.05rem;border:5px solid transparent;border-bottom-color:#2a2a2a;
      z-index:101;pointer-events:none}
  </style>
</head>
<body>
<header>
  <a href="/" style="display:flex;align-items:center;gap:.5rem;text-decoration:none">
    <svg viewBox="0 0 64 64" width="22" height="22" fill="none" style="color:#f5a524">
      <path d="M32 4 L57 18.5 L57 45.5 L32 60 L7 45.5 L7 18.5 Z" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round"/>
      <g stroke="currentColor" stroke-width="1" opacity="0.45">
        <line x1="32" y1="32" x2="32" y2="15"/><line x1="32" y1="32" x2="47" y2="23"/>
        <line x1="32" y1="32" x2="47" y2="41"/><line x1="32" y1="32" x2="32" y2="49"/>
        <line x1="32" y1="32" x2="17" y2="41"/><line x1="32" y1="32" x2="17" y2="23"/>
      </g>
      <circle cx="32" cy="15" r="2.5" fill="currentColor"/><circle cx="47" cy="23" r="2.5" fill="currentColor"/>
      <circle cx="47" cy="41" r="2.5" fill="currentColor"/><circle cx="32" cy="49" r="2.5" fill="currentColor"/>
      <circle cx="17" cy="41" r="2.5" fill="currentColor"/><circle cx="17" cy="23" r="2.5" fill="currentColor"/>
      <circle cx="32" cy="32" r="4.5" fill="currentColor"/>
    </svg>
    <h1>crux<span>hive</span></h1>
  </a>
  <div class="stats" id="stats"></div>
  <a href="/docs" target="_blank" rel="noopener" title="Open the CruxHive guide in a new tab"
     style="color:#94a3b8;font-size:.78rem;text-decoration:none;
            padding:.35rem .7rem;border:1px solid #2a2a2a;border-radius:.3rem">Docs ↗</a>
</header>
<div class="kpi-strip" id="kpi-strip"></div>
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

function kpiClass(value, thresholds, lowerIsBetter=false) {
  // thresholds.good: value is good when >= (or <= if lowerIsBetter)
  // thresholds.warn: value is warning when >= (or <= if lowerIsBetter)
  if (lowerIsBetter) {
    if (value <= thresholds.good) return 'good';
    if (value <= thresholds.warn) return 'warn';
    return 'bad';
  }
  if (value >= thresholds.good) return 'good';
  if (value >= thresholds.warn) return 'warn';
  return 'bad';
}

async function loadKpiStrip() {
  const r = await fetch('/api/kpis');
  if (!r.ok) return;
  const k = await r.json();
  const hitRate = k.searches ? Math.round((k.hits / k.searches) * 100) : null;
  const decayPct = k.total_entries ? Math.round((k.decayed_count / k.total_entries) * 100) : 0;

  const TIPS = {
    sessions: 'AI tool sessions started in the last 7 days. Auto-logged by the SessionStart hook. Distinct from Searches — sessions count up automatically, searches only when AI calls context_search.',
    hitRate: 'Percentage of context_search calls that returned ≥1 result. Green ≥70% · Yellow ≥50% · Red <50%. Low = KB too thin or wrong topics.',
    gaps: 'Distinct zero-result queries in the last 30 days. Each one is a candidate to document. Green ≤2 · Yellow ≤5 · Red >5.',
    pending: 'AI-proposed entries waiting for human approval. Color reflects age of the oldest entry: green ≤3d · yellow ≤14d · red >14d.',
    decayed: 'High-confidence entries that decayed by age (not revalidated). Color reflects ratio: green ≤5% · yellow ≤15% · red >15%.',
    entries: 'Total markdown knowledge entries indexed for this project (.llm/ + ~/.cruxhive/personal/).',
    constraints: 'Approved "constraint"-type entries — the rules the AI is checked against via NLI faithfulness.',
  };

  const chips = [];
  chips.push(`<div class="kpi-chip ${(k.sessions || 0) > 0 ? 'good' : ''}" data-tip="${TIPS.sessions}">
    <strong>${k.sessions || 0}</strong><span class="label">Sessions (7d)</span></div>`);
  if (hitRate !== null) {
    chips.push(`<div class="kpi-chip ${kpiClass(hitRate, {good:70, warn:50})}" data-tip="${TIPS.hitRate}">
      <strong>${hitRate}%</strong><span class="label">Hit rate</span></div>`);
  } else {
    chips.push(`<div class="kpi-chip" data-tip="${TIPS.hitRate}">
      <strong>—</strong><span class="label">Hit rate</span></div>`);
  }
  chips.push(`<div class="kpi-chip ${kpiClass(k.gaps_30d, {good:2, warn:5}, true)}" data-tip="${TIPS.gaps}">
    <strong>${k.gaps_30d}</strong><span class="label">Gaps (30d)</span></div>`);
  chips.push(`<div class="kpi-chip ${kpiClass(k.pending_oldest_days || 0, {good:3, warn:14}, true)}" data-tip="${TIPS.pending}">
    <strong>${k.pending_count}</strong><span class="label">Pending${k.pending_count ? ` · ${k.pending_oldest_days}d` : ''}</span></div>`);
  chips.push(`<div class="kpi-chip ${kpiClass(decayPct, {good:5, warn:15}, true)}" data-tip="${TIPS.decayed}">
    <strong>${k.decayed_count}</strong><span class="label">Decayed · ${decayPct}%</span></div>`);
  chips.push(`<div class="kpi-chip" data-tip="${TIPS.entries}">
    <strong>${k.total_entries}</strong><span class="label">Entries</span></div>`);
  chips.push(`<div class="kpi-chip" data-tip="${TIPS.constraints}">
    <strong>${k.constraints}</strong><span class="label">Constraints</span></div>`);

  document.getElementById('kpi-strip').innerHTML = chips.join('');
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
  list.innerHTML = pending.map(p => {
    const conflictsHtml = (p.conflicts && p.conflicts.length)
      ? `<div class="conflict-box">
           <div class="conflict-title">⚠ ${p.conflicts.length} potential conflict(s) with approved constraint(s)</div>
           ${p.conflicts.slice(0,3).map(c =>
             `<div class="conflict-item">· [${c.severity}] ${c.path} (score: ${c.score}) — ${c.preview || ''}</div>`
           ).join('')}
         </div>`
      : '';
    return `
    <div class="card" id="card-${btoa(p.path)}">
      <div class="card-header">
        ${badge(p.type)}
        <span class="path">${p.path}</span>
      </div>
      <div class="meta">${p.topic ? `topic: ${p.topic} · ` : ''}proposed: ${p.valid_at||'?'}</div>
      <div class="preview">${p.preview || ''}</div>
      ${conflictsHtml}
      <div class="actions">
        <button class="btn-approve" onclick="approve('${p.path}')">✓ Approve</button>
        <button class="btn-reject" onclick="reject('${p.path}')">✗ Reject</button>
      </div>
    </div>
  `;
  }).join('');
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

loadKpiStrip();
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

    @app.get("/docs", response_class=HTMLResponse)
    def docs():
        return _docs_html()

    @app.get("/api/pending")
    def api_pending():
        conn = _store.connect(root)
        data = _store.list_pending(conn)
        data = _store.annotate_pending_conflicts(conn, data)
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

    @app.get("/api/kpis")
    def api_kpis(days: int = 7):
        """Compact KPI strip data — same shape used by the top banner."""
        conn = _store.connect(root)
        s = _events.summary(conn, days=days)
        gaps = _events.top_gaps(conn, days=max(days, 30), limit=50)
        pa = _events.pending_age(conn)
        decayed = _store.stale_high_confidence(conn)
        kb = _store.stats(conn)
        conn.close()
        return {
            "hit_rate": s["hit_rate"],
            "searches": s["searches"],
            "hits": s["hits"],
            "sessions": s.get("sessions", 0),
            "gaps_30d": len(gaps),
            "pending_count": pa["count"],
            "pending_oldest_days": pa["oldest_days"],
            "decayed_count": len(decayed),
            "total_entries": kb["total"],
            "constraints": kb["constraints"],
        }

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
    """Uvicorn factory entry point. Uses CRUXHIVE_ROOT env var for project root.

    If CRUXHIVE_WORKSPACE=1 is set, returns the workspace-mode UI instead.
    """
    if os.environ.get("CRUXHIVE_WORKSPACE", "0") not in {"0", "", "false", "no"}:
        return make_workspace_app()
    root = os.environ.get("CRUXHIVE_ROOT") or os.getcwd()
    return make_app(root)


# ── Workspace mode ────────────────────────────────────────────────────────────

_WORKSPACE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CruxHive · Workspace</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' fill='none'><rect width='64' height='64' rx='12' fill='%230a0a0a'/><path d='M32 8 L55 19.5 L55 44.5 L32 56 L9 44.5 L9 19.5 Z' stroke='%23f5a524' stroke-width='3' stroke-linejoin='round'/><circle cx='32' cy='32' r='6' fill='%23f5a524'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'IBM Plex Sans',system-ui,-apple-system,sans-serif;
  background:#0a0a0a;color:#e2e8f0;min-height:100vh}
header{padding:1.25rem 2rem;border-bottom:1px solid #1d1d1d;
  display:flex;align-items:center;gap:1rem;position:sticky;top:0;
  background:#0a0a0aee;backdrop-filter:blur(8px);z-index:10}
header h1{font-size:1.1rem;font-weight:700;color:#f8fafc;letter-spacing:-.02em}
header h1 span{color:#f5a524}
header .mode{font-size:.7rem;color:#f5a524;
  background:#3d2710;border:1px solid #f5a52444;padding:.25rem .65rem;border-radius:1rem}
header .filler{flex:1}
header select{background:#0a0a0a;border:1px solid #2a2a2a;color:#e2e8f0;
  padding:.4rem .65rem;border-radius:.3rem;font-size:.78rem;cursor:pointer}
header a.docs-link{color:#94a3b8;font-size:.78rem;text-decoration:none;
  padding:.4rem .75rem;border:1px solid #2a2a2a;border-radius:.3rem;
  transition:all .15s}
header a.docs-link:hover{color:#e2e8f0;border-color:#475569;background:#131313}
main{max-width:1180px;margin:1.5rem auto;padding:0 1.5rem}
h2{font-size:.78rem;font-weight:600;text-transform:uppercase;
  letter-spacing:.06em;color:#64748b;margin:1.5rem 0 .75rem;
  display:flex;align-items:center;gap:.5rem}
h2 .count{font-size:.7rem;color:#475569;font-weight:400;
  background:#1d1d1d;padding:.1rem .5rem;border-radius:.75rem}

/* ── Empty state callout ───────────────────────────────────────── */
.callout{background:linear-gradient(135deg,#1a1410 0%,#0a0a0a 100%);
  border:1px solid #4338ca44;border-radius:.6rem;padding:1.4rem 1.6rem;
  margin-bottom:1.5rem}
.callout h3{font-size:1rem;color:#e2e8f0;margin-bottom:.5rem;font-weight:600}
.callout p{font-size:.85rem;color:#94a3b8;line-height:1.55;margin-bottom:.6rem}
.callout code{background:#0a0a0a;color:#f5a524;padding:.1rem .4rem;
  border-radius:.25rem;font-size:.78rem;font-family:'IBM Plex Mono','SF Mono',Menlo,monospace}
.callout .actions{margin-top:.75rem;display:flex;gap:.5rem;flex-wrap:wrap}
.callout .pill{background:#1d1d1d;border:1px solid #2a2a2a;color:#cbd5e1;
  padding:.35rem .7rem;border-radius:.3rem;font-size:.75rem;
  font-family:'IBM Plex Mono','SF Mono',Menlo,monospace}

/* ── KPI strip (aggregate) ─────────────────────────────────────── */
.kpi-row{display:grid;grid-template-columns:repeat(7,1fr);gap:.5rem;margin-bottom:1.25rem}
.kpi{background:#131313;border:1px solid #1d1d1d;border-radius:.45rem;
  padding:.75rem .9rem;display:flex;flex-direction:column;line-height:1.2}
.kpi-label{font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;
  color:#64748b;margin-bottom:.3rem;font-weight:600}
.kpi-value{font-size:1.35rem;font-weight:700;color:#e2e8f0;
  font-variant-numeric:tabular-nums}
.kpi-value.muted{color:#475569}
.kpi-value.good{color:#86efac}
.kpi-value.warn{color:#fbbf24}
.kpi-value.bad{color:#f87171}
.kpi-sub{font-size:.66rem;color:#64748b;margin-top:.15rem}

/* ── Custom hover tooltip ──────────────────────────────────────── */
[data-tip]{position:relative}
[data-tip]:hover::after{
  content:attr(data-tip);
  position:absolute;left:50%;top:100%;transform:translateX(-50%);
  margin-top:.4rem;background:#0d0d0d;border:1px solid #2a2a2a;
  border-radius:.35rem;padding:.55rem .75rem;font-size:.72rem;
  font-weight:400;color:#cbd5e1;line-height:1.4;
  white-space:pre-wrap;width:260px;text-align:left;z-index:100;
  box-shadow:0 4px 16px #000c;text-transform:none;letter-spacing:0;
  pointer-events:none}
[data-tip]:hover::before{
  content:'';position:absolute;left:50%;top:100%;transform:translateX(-50%);
  margin-top:.05rem;border:5px solid transparent;border-bottom-color:#2a2a2a;
  z-index:101;pointer-events:none}
.kpi-delta{font-size:.65rem;font-weight:600;margin-left:.3rem}
.kpi-delta.up{color:#86efac}
.kpi-delta.down{color:#f87171}
.kpi-delta.flat{color:#475569}

/* ── Gaps panel ────────────────────────────────────────────────── */
.gaps-panel{background:#131313;border:1px solid #1d1d1d;border-radius:.5rem;
  padding:1rem 1.2rem;margin-bottom:1.25rem}
.gap-row{display:flex;align-items:center;gap:.6rem;padding:.4rem 0;
  border-bottom:1px solid #1d1d1d;font-size:.8rem}
.gap-row:last-child{border-bottom:none}
.gap-row .q{flex:1;font-family:'IBM Plex Mono','SF Mono',Menlo,monospace;color:#fbbf24;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gap-row .meta{color:#64748b;font-size:.7rem}
.gap-empty{color:#64748b;font-size:.8rem;text-align:center;padding:.5rem 0}

/* ── Project cards ─────────────────────────────────────────────── */
.project-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));
  gap:.7rem;margin-bottom:1rem}
.project-card{background:#131313;border:1px solid #1d1d1d;border-radius:.5rem;
  padding:.9rem 1rem;cursor:pointer;transition:all .15s;text-align:left;
  font-family:inherit;color:inherit;display:flex;flex-direction:column;gap:.45rem;
  width:100%}
.project-card:hover{border-color:#f5a524;background:#1a2138;transform:translateY(-1px)}
.project-card.active{border-left:3px solid #f5a524;padding-left:.85rem}
.project-card-header{display:flex;align-items:baseline;justify-content:space-between;
  gap:.5rem}
.project-name{font-size:1.05rem;font-weight:700;color:#f8fafc;letter-spacing:-.01em}
.project-badge{font-size:.62rem;text-transform:uppercase;letter-spacing:.05em;
  padding:.15rem .45rem;border-radius:.25rem;font-weight:600}
.project-badge.active{background:#1e3a5f;color:#60a5fa}
.project-badge.quiet{background:#1d1d1d;color:#64748b}
.project-stats{display:grid;grid-template-columns:repeat(auto-fit, minmax(60px, 1fr));gap:.5rem;margin-top:.2rem}
.project-stat{display:flex;flex-direction:column;gap:.15rem}
.project-stat-label{font-size:.62rem;color:#64748b;text-transform:uppercase;
  letter-spacing:.05em}
.project-stat-value{font-size:1rem;font-weight:600;color:#e2e8f0;
  font-variant-numeric:tabular-nums}
.project-stat-value.warn{color:#fbbf24}
.project-stat-value.bad{color:#f87171}
.project-stat-value.muted{color:#475569}

/* ── Collapsed (quiet) cards ───────────────────────────────────── */
.quiet-section{margin-top:.5rem}
.quiet-toggle{background:none;border:1px dashed #1d1d1d;color:#94a3b8;
  font-size:.78rem;padding:.5rem 1rem;border-radius:.4rem;cursor:pointer;
  width:100%;text-align:left;font-family:inherit;
  display:flex;align-items:center;justify-content:space-between}
.quiet-toggle:hover{border-color:#475569;color:#e2e8f0}
.quiet-toggle .chevron{transition:transform .15s}
.quiet-toggle.open .chevron{transform:rotate(90deg)}
.quiet-list{display:none;margin-top:.6rem}
.quiet-list.open{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));
  gap:.7rem}

/* ── Drilldown drawer ──────────────────────────────────────────── */
.drawer-overlay{position:fixed;inset:0;background:#000c;z-index:50;
  display:none;align-items:center;justify-content:center;padding:2rem}
.drawer-overlay.open{display:flex}
.drawer{background:#0a0a0a;border:1px solid #2a2a2a;border-radius:.6rem;
  width:100%;max-width:680px;max-height:88vh;overflow:hidden;
  display:flex;flex-direction:column}
.drawer-header{padding:1.1rem 1.4rem;border-bottom:1px solid #1d1d1d;
  display:flex;align-items:center;gap:1rem}
.drawer-header h3{font-size:1.05rem;font-weight:700;color:#f8fafc}
.drawer-header .close{margin-left:auto;background:none;border:none;color:#94a3b8;
  font-size:1.3rem;cursor:pointer;line-height:1;padding:.25rem .5rem;border-radius:.3rem}
.drawer-header .close:hover{background:#1d1d1d;color:#f8fafc}
.drawer-body{padding:1rem 1.4rem;overflow-y:auto;font-size:.85rem;color:#cbd5e1}
.drawer-section{margin-bottom:1.25rem}
.drawer-section h4{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
  color:#64748b;font-weight:600;margin-bottom:.5rem}
.drawer-path{font-family:'IBM Plex Mono','SF Mono',Menlo,monospace;font-size:.72rem;color:#475569;
  word-break:break-all;margin-top:.25rem}
.drawer-cmd{background:#131313;border:1px solid #1d1d1d;border-radius:.35rem;
  padding:.55rem .8rem;font-family:'IBM Plex Mono','SF Mono',Menlo,monospace;font-size:.78rem;
  color:#f5a524;margin-top:.4rem}
.drawer-list li{padding:.3rem 0;border-bottom:1px solid #1d1d1d;
  display:flex;justify-content:space-between;gap:.5rem;font-size:.78rem}
.drawer-list li:last-child{border-bottom:none}
.drawer-list code{font-family:'IBM Plex Mono','SF Mono',Menlo,monospace;color:#94a3b8;font-size:.72rem}
.kbd{font-family:'IBM Plex Mono','SF Mono',Menlo,monospace;font-size:.7rem;color:#cbd5e1;
  background:#1d1d1d;border:1px solid #2a2a2a;padding:.05rem .3rem;border-radius:.2rem}
</style>
</head>
<body>
<header>
  <a href="/" style="display:flex;align-items:center;gap:.5rem;text-decoration:none">
    <svg viewBox="0 0 64 64" width="22" height="22" fill="none" style="color:#f5a524">
      <path d="M32 4 L57 18.5 L57 45.5 L32 60 L7 45.5 L7 18.5 Z" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round"/>
      <g stroke="currentColor" stroke-width="1" opacity="0.45">
        <line x1="32" y1="32" x2="32" y2="15"/><line x1="32" y1="32" x2="47" y2="23"/>
        <line x1="32" y1="32" x2="47" y2="41"/><line x1="32" y1="32" x2="32" y2="49"/>
        <line x1="32" y1="32" x2="17" y2="41"/><line x1="32" y1="32" x2="17" y2="23"/>
      </g>
      <circle cx="32" cy="15" r="2.5" fill="currentColor"/><circle cx="47" cy="23" r="2.5" fill="currentColor"/>
      <circle cx="47" cy="41" r="2.5" fill="currentColor"/><circle cx="32" cy="49" r="2.5" fill="currentColor"/>
      <circle cx="17" cy="41" r="2.5" fill="currentColor"/><circle cx="17" cy="23" r="2.5" fill="currentColor"/>
      <circle cx="32" cy="32" r="4.5" fill="currentColor"/>
    </svg>
    <h1>crux<span>hive</span></h1>
  </a>
  <span class="mode">Workspace</span>
  <span class="filler"></span>
  <a class="docs-link" href="/docs" target="_blank" rel="noopener" title="Open the CruxHive guide in a new tab">Docs ↗</a>
  <label style="font-size:.7rem;color:#64748b">window:</label>
  <select id="window" onchange="load()">
    <option value="7" selected>Last 7 days</option>
    <option value="30">Last 30 days</option>
    <option value="90">Last 90 days</option>
  </select>
</header>
<main>
  <div id="callout-slot"></div>
  <h2>Aggregate <span class="count" id="agg-count"></span></h2>
  <div class="kpi-row" id="kpis"></div>

  <h2>Top knowledge gaps <span class="count">cross-project</span></h2>
  <div class="gaps-panel" id="gaps-panel"></div>

  <h2>Active projects <span class="count" id="active-count"></span></h2>
  <div class="project-grid" id="active-projects"></div>

  <div class="quiet-section" id="quiet-section"></div>
</main>

<div class="drawer-overlay" id="drawer-overlay" onclick="if(event.target===this)closeDrawer()">
  <div class="drawer">
    <div class="drawer-header">
      <h3 id="drawer-title">Project</h3>
      <button class="close" onclick="closeDrawer()">×</button>
    </div>
    <div class="drawer-body" id="drawer-body"></div>
  </div>
</div>

<script>
const fmtPct = (p) => p === null ? '—' : (p * 100).toFixed(0) + '%';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function colorClass(value, thresholds, lowerIsBetter = false) {
  if (lowerIsBetter) {
    if (value <= thresholds.good) return 'good';
    if (value <= thresholds.warn) return 'warn';
    return 'bad';
  }
  if (value >= thresholds.good) return 'good';
  if (value >= thresholds.warn) return 'warn';
  return 'bad';
}

function isActive(s) {
  if (!s.kpis) return false;
  const k = s.kpis;
  return (k.sessions > 0) || (k.searches > 0) || (k.pending_count > 0) ||
         (k.proposals > 0) || (k.decayed_count > 0) || (k.gaps_30d > 0);
}

async function load() {
  const days = document.getElementById('window').value;
  const r = await fetch(`/api/workspace?days=${days}`);
  const data = await r.json();
  const agg = data.aggregate || {};
  const snaps = (data.projects || []).filter(s => !s.error);
  const errored = (data.projects || []).filter(s => s.error);

  document.getElementById('agg-count').textContent = `last ${days} days · ${snaps.length} project(s)`;

  // ── Empty-state callout ─────────────────────────────────────────
  const slot = document.getElementById('callout-slot');
  const totallyIdle = (agg.searches || 0) === 0 && (agg.pending_count || 0) === 0
                   && (agg.proposals || 0) === 0 && (agg.sessions || 0) === 0;
  if (totallyIdle && agg.total_entries > 0) {
    slot.innerHTML = `
      <div class="callout">
        <h3>🐝 CruxHive is wired but no AI session has been recorded yet</h3>
        <p>You have <strong>${agg.total_entries}</strong> indexed entries across <strong>${agg.projects}</strong> projects, but no SessionStart event has fired in the last ${days} days. This usually means your existing AI sessions started before the hook was wired — open a new Claude Code or OpenCode session in any project and the sessions counter will start moving.</p>
        <p><strong>If sessions count up but searches stay at 0:</strong> the AI tool is loading <code>.llm/CONTEXT.md</code> as static context but never invoking the MCP <code>context_*</code> tools. Use slash commands (<code>/radar</code>, <code>/extract</code>, <code>/review</code>) or ask the AI explicitly to search the CruxHive knowledge base.</p>
        <div class="actions">
          <span class="pill">cd your-project && claude</span>
          <span class="pill">/radar  · /next-slice  · /extract</span>
        </div>
      </div>`;
  } else if (snaps.length === 0) {
    slot.innerHTML = `
      <div class="callout">
        <h3>No projects discovered</h3>
        <p>Configure <code>~/.cruxhive/config.yaml</code> with a <code>workspace.projects</code> list, or place your projects as siblings inside <code>~/Projects_Local/Development/</code>.</p>
      </div>`;
  } else {
    slot.innerHTML = '';
  }

  // ── KPI strip ───────────────────────────────────────────────────
  const hitRate = agg.searches ? agg.hit_rate : null;
  const decayPct = agg.total_entries ? (agg.decayed_count / agg.total_entries) : 0;

  const kpis = [
    {label: 'Projects', value: agg.projects || 0,
     sub: errored.length ? `${errored.length} error(s)` : `${agg.active_projects || 0} active`,
     tip: 'Total CruxHive-initialized projects discovered. "Active" = had ≥1 session_start event in the window.'},
    {label: 'Sessions', value: agg.sessions || 0,
     sub: agg.sessions ? `last ${days}d` : 'no sessions yet',
     cls: (agg.sessions || 0) > 0 ? 'good' : 'muted',
     tip: 'Number of AI tool sessions started (Claude Code, OpenCode, etc.). Auto-logged by the SessionStart hook. >0 means CruxHive is being loaded. Distinct from "Searches".'},
    {label: 'Entries', value: agg.total_entries || 0,
     tip: 'Markdown knowledge entries indexed across all projects. Includes project, org, and personal layers.'},
    {label: 'Pending', value: agg.pending_count || 0,
     cls: agg.pending_count > 5 ? 'warn' : (agg.pending_count > 0 ? '' : 'muted'),
     tip: 'AI-proposed entries waiting for human approval. 0 = clean. 1-5 = normal. >5 = review backlog forming.'},
    {label: 'Hit rate', value: hitRate === null ? '—' : fmtPct(hitRate),
     sub: agg.searches ? `${agg.searches} searches` : 'no searches yet',
     cls: hitRate === null ? 'muted' : colorClass(hitRate * 100, {good: 70, warn: 50}),
     tip: '% of context_search calls that returned ≥1 result. Green ≥70% · Yellow ≥50% · Red <50%. Low = KB too thin or wrong topics — see Top Gaps.'},
    {label: 'Constraints', value: agg.constraints || 0,
     cls: (agg.constraints || 0) === 0 ? 'muted' : '',
     tip: 'Approved "constraint"-type entries — the rules that AI faithfulness checks are run against. The most important entry type.'},
    {label: 'Decayed', value: agg.decayed_count || 0,
     sub: agg.total_entries ? fmtPct(decayPct) + ' of total' : '',
     cls: decayPct > 0.15 ? 'warn' : (agg.decayed_count > 0 ? '' : 'muted'),
     tip: 'High-confidence entries auto-downgraded because they haven\\'t been revalidated. >15% of total = audit time. Update valid_at: or set invalid_at: to deprecate.'},
  ];

  document.getElementById('kpis').innerHTML = kpis.map(k => `
    <div class="kpi" data-tip="${esc(k.tip || '')}">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value ${k.cls || ''}">${k.value}</div>
      ${k.sub ? `<div class="kpi-sub">${k.sub}</div>` : ''}
    </div>
  `).join('');

  // ── Cross-project Top Gaps ───────────────────────────────────────
  const allGaps = {};
  snaps.forEach(s => (s.gaps || []).forEach(g => {
    const key = g.query;
    if (!allGaps[key]) allGaps[key] = {query: g.query, times: 0, projects: new Set()};
    allGaps[key].times += g.times || 0;
    allGaps[key].projects.add(s.project);
  }));
  const topGaps = Object.values(allGaps)
    .sort((a, b) => b.times - a.times)
    .slice(0, 6);

  const gp = document.getElementById('gaps-panel');
  if (topGaps.length === 0) {
    gp.innerHTML = '<div class="gap-empty">No zero-result queries — every recent search found something.</div>';
  } else {
    gp.innerHTML = topGaps.map(g => `
      <div class="gap-row">
        <span class="q">${esc(g.query)}</span>
        <span class="meta">${g.times}× · ${[...g.projects].join(', ')}</span>
      </div>
    `).join('');
  }

  // ── Sort + split projects ────────────────────────────────────────
  const active = snaps.filter(isActive).sort((a, b) =>
    (b.kpis.searches + b.kpis.pending_count) - (a.kpis.searches + a.kpis.pending_count));
  const quiet = snaps.filter(s => !isActive(s)).sort((a, b) =>
    (b.kpis.total_entries || 0) - (a.kpis.total_entries || 0));

  document.getElementById('active-count').textContent =
    active.length ? `${active.length}` : 'none in this window';

  document.getElementById('active-projects').innerHTML = active.length
    ? active.map(s => renderCard(s, true)).join('')
    : '<div class="gap-empty">No projects with recent activity. The cards below have entries but no MCP calls yet.</div>';

  const qs = document.getElementById('quiet-section');
  if (quiet.length === 0) {
    qs.innerHTML = '';
  } else {
    qs.innerHTML = `
      <button class="quiet-toggle" onclick="toggleQuiet(event)">
        <span><span class="chevron">▸</span>&nbsp; ${quiet.length} quiet project(s) — no MCP activity in last ${days} days</span>
        <span style="font-size:.7rem;color:#64748b">click to expand</span>
      </button>
      <div class="quiet-list" id="quiet-list">
        ${quiet.map(s => renderCard(s, false)).join('')}
      </div>`;
  }

  // Stash for drilldown
  window.__snaps = Object.fromEntries(snaps.map(s => [s.project, s]));
}

function toggleQuiet(e) {
  const btn = e.currentTarget;
  btn.classList.toggle('open');
  document.getElementById('quiet-list').classList.toggle('open');
}

function renderCard(s, isActiveCard) {
  const k = s.kpis;
  const ev = s.events || {};
  const hits = ev.hits || 0;
  const pct = k.searches ? fmtPct(hits / k.searches) : null;

  const statClass = (val, lowerIsBetter, thresholds) => {
    if (val === 0 || val === null) return 'muted';
    if (lowerIsBetter) return val > thresholds.bad ? 'bad' : (val > thresholds.warn ? 'warn' : '');
    return '';
  };

  // Four most relevant stats per card
  const stats = isActiveCard
    ? [
        {label: 'sessions', value: k.sessions || 0, cls: (k.sessions || 0) > 0 ? '' : 'muted'},
        {label: 'searches', value: k.searches, cls: statClass(k.searches, false, {})},
        {label: 'hit rate', value: pct === null ? '—' : pct, cls: pct === null ? 'muted' : ''},
        {label: 'pending', value: k.pending_count + (k.pending_count ? ` · ${k.pending_oldest_days}d` : ''),
         cls: statClass(k.pending_count, true, {warn: 3, bad: 10})},
      ]
    : [
        {label: 'entries', value: k.total_entries, cls: k.total_entries === 0 ? 'muted' : ''},
        {label: 'gaps', value: k.gaps_30d, cls: statClass(k.gaps_30d, true, {warn: 3, bad: 10})},
        {label: 'decayed', value: k.decayed_count, cls: statClass(k.decayed_count, true, {warn: 5, bad: 20})},
      ];

  return `
    <button class="project-card ${isActiveCard ? 'active' : ''}" onclick="openDrawer('${esc(s.project)}')">
      <div class="project-card-header">
        <span class="project-name">${esc(s.project)}</span>
        <span class="project-badge ${isActiveCard ? 'active' : 'quiet'}">${isActiveCard ? 'active' : `${k.total_entries} entries`}</span>
      </div>
      <div class="project-stats">
        ${stats.map(st => `
          <div class="project-stat">
            <span class="project-stat-label">${st.label}</span>
            <span class="project-stat-value ${st.cls}">${st.value}</span>
          </div>`).join('')}
      </div>
    </button>`;
}

function openDrawer(name) {
  const s = window.__snaps[name];
  if (!s) return;
  const k = s.kpis;

  document.getElementById('drawer-title').textContent = name;

  const sections = [];

  // Path + open command
  sections.push(`
    <div class="drawer-section">
      <h4>Path</h4>
      <div class="drawer-path">${esc(s.root || '?')}</div>
      <div class="drawer-cmd">cd ${esc(s.root || '?')} &amp;&amp; cruxhive ui</div>
      <div class="kpi-sub" style="margin-top:.35rem">Opens this project's dedicated UI with Approvals · Usage · By AI Tool · Gaps tabs.</div>
    </div>`);

  // KPI summary
  const hits = (s.events || {}).hits || 0;
  const pct = k.searches ? fmtPct(hits / k.searches) : 'no searches yet';
  sections.push(`
    <div class="drawer-section">
      <h4>Last ${s.window_days || 7} days</h4>
      <ul class="drawer-list">
        <li><span>Tool calls</span><strong>${k.total_calls}</strong></li>
        <li><span>Searches</span><strong>${k.searches}</strong></li>
        <li><span>Hit rate</span><strong>${pct}</strong></li>
        <li><span>Proposals</span><strong>${k.proposals}</strong></li>
        <li><span>Total entries</span><strong>${k.total_entries}</strong></li>
        <li><span>Constraints</span><strong>${k.constraints}</strong></li>
      </ul>
    </div>`);

  // Top gaps for this project
  if ((s.gaps || []).length) {
    sections.push(`
      <div class="drawer-section">
        <h4>Top gaps for this project</h4>
        <ul class="drawer-list">
          ${s.gaps.slice(0, 5).map(g => `
            <li><span>${esc(g.query)}</span><strong>${g.times}×</strong></li>
          `).join('')}
        </ul>
      </div>`);
  }

  // Decayed
  if ((s.decayed || []).length) {
    sections.push(`
      <div class="drawer-section">
        <h4>Decayed entries (${s.decayed.length})</h4>
        <ul class="drawer-list">
          ${s.decayed.slice(0, 5).map(d => `
            <li><code>${esc(d.path)}</code><strong>${d.age_days}d · ${esc(d.effective_confidence)}</strong></li>
          `).join('')}
        </ul>
      </div>`);
  }

  // Pending
  if (k.pending_count > 0) {
    sections.push(`
      <div class="drawer-section">
        <h4>Pending approval</h4>
        <ul class="drawer-list">
          <li><span>Count</span><strong>${k.pending_count}</strong></li>
          <li><span>Oldest</span><strong>${k.pending_oldest_days}d</strong></li>
          <li><span>Average age</span><strong>${k.pending_avg_days}d</strong></li>
        </ul>
        <div class="drawer-cmd" style="margin-top:.5rem">cruxhive review</div>
      </div>`);
  }

  document.getElementById('drawer-body').innerHTML = sections.join('');
  document.getElementById('drawer-overlay').classList.add('open');
}

function closeDrawer() {
  document.getElementById('drawer-overlay').classList.remove('open');
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeDrawer();
});

load();
</script>
</body>
</html>"""


def make_workspace_app() -> "FastAPI":  # type: ignore[name-defined]
    if not _FASTAPI_AVAILABLE:
        raise ImportError("fastapi not installed. Run: uv tool install 'cruxhive-mcp[ui]'")

    from .. import workspace as _ws

    app = FastAPI(title="CruxHive Workspace", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _WORKSPACE_HTML

    @app.get("/docs", response_class=HTMLResponse)
    def docs():
        return _docs_html()

    @app.get("/api/workspace")
    def api_workspace(days: int = 7):
        snaps = _ws.collect_all(days=days)
        agg = _ws.aggregate([s for s in snaps if not s.get("error")])
        return {"aggregate": agg, "projects": snaps}

    return app
