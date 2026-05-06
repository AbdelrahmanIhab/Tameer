"""
Tameer — Developer Debug Dashboard
====================================
GET /debug        → single-page HTML dashboard
GET /debug/stream → SSE stream of pipeline events
"""

from __future__ import annotations
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse

from backend.services import debug_bus

router = APIRouter(prefix="/debug", tags=["Debug"])


# ── SSE stream ────────────────────────────────────────────────────────────────

@router.get("/stream")
async def debug_stream():
    async def _generator():
        cursor = len(debug_bus.get_all_events())
        ticks_since_ping = 0
        while True:
            events = debug_bus.get_events_since(cursor)
            if events:
                for e in events:
                    yield f"data: {json.dumps(e)}\n\n"
                cursor += len(events)
                ticks_since_ping = 0
            else:
                ticks_since_ping += 1
                if ticks_since_ping >= 50:   # 50 × 0.5 s = 25 s
                    yield ": ping\n\n"
                    ticks_since_ping = 0
            await asyncio.sleep(0.5)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── HTML dashboard ────────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Tameer Debug</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Courier New', monospace; background: #0f172a; color: #e2e8f0; font-size: 13px; }

header {
  padding: 10px 16px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex; align-items: center; gap: 12px;
}
h1 { font-size: 13px; font-weight: bold; letter-spacing: 1px; color: #94a3b8; }
#dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: #ef4444; flex-shrink: 0;
  transition: background 0.3s;
}
#dot.on { background: #10b981; box-shadow: 0 0 6px #10b981; }
#slabel { font-size: 11px; color: #475569; }

.bar {
  padding: 7px 16px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
}
button {
  padding: 3px 10px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #94a3b8;
  border-radius: 3px;
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
  transition: all 0.15s;
}
button:hover { background: #1e293b; color: #e2e8f0; }
button.active { background: #334155; color: #f1f5f9; border-color: #64748b; }
button.danger { border-color: #4b1a1a; color: #f87171; }
button.danger:hover { background: #4b1a1a; }

#aslabel { color: #475569; font-size: 11px; display: flex; align-items: center; gap: 4px; cursor: pointer; margin-left: 4px; }
#cnt { margin-left: auto; color: #475569; font-size: 11px; }

.wrap { overflow: auto; height: calc(100vh - 85px); }

table { width: 100%; border-collapse: collapse; }
thead th {
  position: sticky; top: 0;
  background: #1e293b;
  padding: 7px 10px;
  text-align: left;
  color: #475569;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #334155;
  white-space: nowrap;
  user-select: none;
}
tbody tr { border-bottom: 1px solid #172033; }
tbody tr.erow:hover { background: #1e293b; }
tbody tr.hidden { display: none; }
td { padding: 5px 10px; white-space: nowrap; vertical-align: middle; }

.badge {
  display: inline-block; padding: 1px 7px;
  border-radius: 3px; font-size: 10px; font-weight: bold; letter-spacing: 0.3px;
}
.m { background: #172554; color: #60a5fa; }
.p { background: #2d1f00; color: #fbbf24; }
.i { background: #022c22; color: #34d399; }
.a { background: #2d1400; color: #fb923c; }
.ok   { color: #34d399; font-size: 11px; }
.err  { color: #f87171; font-size: 11px; }

.tid  { color: #7c3aed; font-size: 11px; font-family: monospace; cursor: pointer; }
.tid:hover { text-decoration: underline; color: #a78bfa; }
.tid.hi { color: #a78bfa; background: #2e1065; border-radius: 2px; padding: 0 2px; }
.ts   { color: #475569; font-size: 11px; }
.zid  { color: #60a5fa; }
.det  { color: #cbd5e1; max-width: 420px; overflow: hidden; text-overflow: ellipsis; }

.xtog { cursor: pointer; color: #475569; font-size: 10px; }
.xtog:hover { color: #94a3b8; }
.xrow td {
  background: #080d14;
  color: #64748b;
  font-size: 11px;
  padding: 3px 10px 4px 28px;
  border-bottom: 1px solid #172033;
}
pre { margin: 0; white-space: pre-wrap; word-break: break-all; }
</style>
</head>
<body>

<header>
  <div id="dot"></div>
  <h1>TAMEER&nbsp;&nbsp;DEBUG&nbsp;&nbsp;DASHBOARD</h1>
  <span id="slabel">disconnected</span>
</header>

<div class="bar">
  <button class="active" onclick="setFilter('all',this)">All</button>
  <button onclick="setFilter('mqtt_received',this)">MQTT</button>
  <button onclick="setFilter('processing',this)">Processing</button>
  <button onclick="setFilter('influx_write',this)">InfluxDB</button>
  <button onclick="setFilter('automation',this)">Automation</button>
  <button class="danger" onclick="clearAll()" style="margin-left:6px">Clear</button>
  <label id="aslabel"><input type="checkbox" id="asc" checked> Auto-scroll</label>
  <span id="cnt">0 events</span>
</div>

<div class="wrap" id="wrap">
  <table>
    <thead>
      <tr>
        <th>Trace&nbsp;ID</th>
        <th>Time</th>
        <th>Stage</th>
        <th>Zone</th>
        <th>Type</th>
        <th>Inst</th>
        <th>Detail</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody id="tb"></tbody>
  </table>
</div>

<script>
let filter = 'all', n = 0, highlighted = null;

const BADGE = {
  mqtt_received: ['m','MQTT'],
  processing:    ['p','PROCESSING'],
  influx_write:  ['i','INFLUXDB'],
  automation:    ['a','AUTOMATION'],
};

function fmt(iso) {
  try { return iso.replace('T',' ').slice(0,23); } catch { return iso; }
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function setFilter(f, btn) {
  filter = f;
  document.querySelectorAll('.bar button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#tb tr.erow').forEach(r => applyFilter(r));
  document.querySelectorAll('#tb tr.xrow').forEach(r => {
    const prev = r.previousElementSibling;
    r.classList.toggle('hidden', prev && prev.classList.contains('hidden'));
  });
}

function applyFilter(row) {
  row.classList.toggle('hidden', filter !== 'all' && row.dataset.stage !== filter);
}

function clearAll() {
  document.getElementById('tb').innerHTML = '';
  n = 0; highlighted = null;
  document.getElementById('cnt').textContent = '0 events';
}

function highlightTrace(tid) {
  if (highlighted === tid) {
    highlighted = null;
    document.querySelectorAll('.tid').forEach(el => el.classList.remove('hi'));
  } else {
    highlighted = tid;
    document.querySelectorAll('.tid').forEach(el =>
      el.classList.toggle('hi', el.textContent === tid));
  }
}

function addEvent(e) {
  const tb = document.getElementById('tb');
  const id = ++n;
  const [bc, bl] = BADGE[e.stage] || ['m', e.stage.toUpperCase()];
  const hasX = e.extra && Object.keys(e.extra).length > 0;

  const tr = document.createElement('tr');
  tr.className = 'erow';
  tr.dataset.stage = e.stage;
  applyFilter(tr);

  tr.innerHTML =
    `<td><span class="tid" onclick="highlightTrace('${esc(e.trace_id||'')}')">${esc(e.trace_id||'—')}</span></td>` +
    `<td><span class="ts">${esc(fmt(e.ts))}</span></td>` +
    `<td><span class="badge ${bc}">${bl}</span></td>` +
    `<td><span class="zid">${e.zone_id??'—'}</span></td>` +
    `<td>${esc(e.node_type||'—')}</td>` +
    `<td>${e.node_instance??'—'}</td>` +
    `<td class="det" title="${esc(e.detail||'')}">` +
      (hasX ? `<span class="xtog" onclick="toggleX(${id})">▶</span> ` : '') +
      esc(e.detail||'') +
    `</td>` +
    `<td><span class="${e.status==='error'?'err':'ok'}">${esc(e.status||'ok')}</span></td>`;
  tb.appendChild(tr);

  if (hasX) {
    const xr = document.createElement('tr');
    xr.className = 'xrow'; xr.id = 'x'+id;
    if (tr.classList.contains('hidden')) xr.classList.add('hidden');
    xr.innerHTML = `<td colspan="8"><pre>${esc(JSON.stringify(e.extra,null,2))}</pre></td>`;
    tb.appendChild(xr);
  }

  document.getElementById('cnt').textContent = `${n} event${n!==1?'s':''}`;

  if (highlighted) {
    tr.querySelectorAll('.tid').forEach(el =>
      el.classList.toggle('hi', el.textContent === highlighted));
  }

  if (document.getElementById('asc').checked) {
    const w = document.getElementById('wrap');
    w.scrollTop = w.scrollHeight;
  }
}

function toggleX(id) {
  const el = document.getElementById('x'+id);
  if (el) el.style.display = el.style.display === 'table-row' ? 'none' : 'table-row';
}

// SSE
const dot = document.getElementById('dot');
const sl  = document.getElementById('slabel');

function connect() {
  const es = new EventSource('/debug/stream');
  es.onopen = () => { dot.className='on'; sl.textContent='connected'; };
  es.onmessage = ev => { try { addEvent(JSON.parse(ev.data)); } catch(e) { console.error(e); } };
  es.onerror = () => { dot.className=''; sl.textContent='reconnecting…'; es.close(); setTimeout(connect,3000); };
}
connect();
</script>
</body>
</html>"""


@router.get("", response_class=HTMLResponse)
async def debug_dashboard():
    return HTMLResponse(content=_HTML)
