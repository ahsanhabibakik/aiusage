DASHBOARD_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>aiusage</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    font: 14px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0a0a0f;
    color: #f0f0f5;
    margin: 0;
    padding: 32px 16px;
  }
  #root { max-width: 420px; margin: 0 auto; }
  .card {
    background: #17171f;
    border: 1px solid #24242f;
    border-radius: 16px;
    padding: 20px 22px;
    margin-bottom: 18px;
  }
  .card-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .card-head h2 { margin: 0; font-size: 17px; font-weight: 600; }
  .plan-pill {
    font-size: 11px;
    color: #a8a8ba;
    background: #232330;
    padding: 3px 9px;
    border-radius: 999px;
  }
  .metric { margin-bottom: 18px; }
  .metric:last-child { margin-bottom: 0; }
  .metric-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 7px;
  }
  .metric-label { font-size: 13.5px; font-weight: 600; color: #f0f0f5; }
  .metric-flame { font-size: 12px; color: #e05c5c; font-weight: 500; }
  .metric-spare { font-size: 12px; color: #e0a840; }
  .metric-resets { font-size: 12px; color: #7a7a8c; cursor: pointer; }
  .bar-track {
    height: 7px;
    border-radius: 4px;
    background: #232330;
    overflow: hidden;
    position: relative;
  }
  .bar-fill { height: 100%; border-radius: 4px; transition: width .3s ease; }
  .pace-tick {
    position: absolute;
    top: -2px;
    width: 2px;
    height: 11px;
    background: #f0f0f5aa;
    border-radius: 1px;
  }
  .metric-bottom {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    font-size: 12.5px;
    color: #9d9dae;
  }
  .metric-bottom .headline { cursor: pointer; }
  .divider { height: 1px; background: #232330; margin: 18px 0 14px; }
  .row {
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    font-size: 13px;
  }
  .row .label { color: #9d9dae; }
  .row .value { color: #e5e5ee; font-variant-numeric: tabular-nums; }
  .row .value.has-models { cursor: pointer; border-bottom: 1px dotted #55556a; }
  .models {
    background: #1d1d27;
    border-radius: 10px;
    padding: 10px 14px;
    margin: 4px 0 8px;
    font-size: 12px;
  }
  .model-row { display: flex; justify-content: space-between; padding: 3px 0; }
  .model-row .m-name { color: #b8b8c8; }
  .model-row .m-val { color: #e5e5ee; font-variant-numeric: tabular-nums; }
  .model-bar { height: 3px; border-radius: 2px; background: #5b8def; margin: 1px 0 4px; }
  .trend {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 56px;
    margin: 8px 0 4px;
  }
  .trend-bar {
    flex: 1;
    background: #5b8def88;
    border-radius: 2px 2px 0 0;
    min-height: 2px;
  }
  .trend-bar:hover { background: #5b8def; }
  .trend-note { font-size: 11px; color: #55556a; margin-bottom: 8px; }
  .error-row {
    font-size: 12.5px;
    color: #d0a050;
    background: #262018;
    padding: 8px 12px;
    border-radius: 8px;
    margin-bottom: 14px;
  }
  .empty { color: #7a7a8c; text-align: center; padding: 60px 0; }
  .footer-time { color: #55556a; font-size: 11px; text-align: center; margin-top: 4px; }
</style></head>
<body>
<div id="root">Loading…</div>
<script>
const BLUE = '#5b8def';
const AMBER = '#e0a840';
const RED = '#e05c5c';

// Persisted display toggles (click any headline / reset label to flip).
let showLeft = localStorage.getItem('aiusage.showLeft') !== 'false';
let exactTimes = localStorage.getItem('aiusage.exactTimes') === 'true';
const openModels = new Set();

function barColor(usedPct, verdict) {
  if (verdict === 'over' || usedPct >= 90) return RED;
  if (verdict === 'tight' || usedPct >= 70) return AMBER;
  return BLUE;
}

function fmtDuration(ms) {
  if (ms <= 0) return 'soon';
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ${mins % 60}m`;
  const days = Math.floor(hrs / 24);
  return `${days}d ${hrs % 24}h`;
}

function fmtTokens(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(n);
}

function renderMetric(line) {
  const usedPct = line.limit ? Math.round((line.used / line.limit) * 100) : 0;
  const leftPct = 100 - usedPct;
  const pace = line.pace || null;
  const verdict = pace ? pace.verdict : null;
  const color = barColor(usedPct, verdict);

  let resetsText = '';
  if (line.resets_at) {
    const t = new Date(line.resets_at);
    resetsText = exactTimes
      ? `Resets ${t.toLocaleString([], {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'})}`
      : `Resets in ${fmtDuration(t.getTime() - Date.now())}`;
  }

  // Even-pace tick: where usage would sit now if burned evenly.
  let tick = '';
  if (pace && line.resets_at && line.period_duration_ms) {
    const remaining = new Date(line.resets_at).getTime() - Date.now();
    const elapsedFrac = 1 - remaining / line.period_duration_ms;
    if (elapsedFrac > 0 && elapsedFrac < 1) {
      tick = `<div class="pace-tick" style="left:${(elapsedFrac * 100).toFixed(1)}%"></div>`;
    }
  }

  let paceNote = '';
  if (verdict === 'over') {
    paceNote = `<span class="metric-flame">On pace to run out (~${pace.projected_used_pct}% at reset)</span>`;
  } else if (verdict === 'tight') {
    paceNote = `<span class="metric-spare">~${Math.max(1, 100 - pace.projected_used_pct)}% spare at reset</span>`;
  }

  const headline = showLeft ? `${leftPct}% left` : `${usedPct}% used`;

  return `
    <div class="metric">
      <div class="metric-top">
        <span class="metric-label">${line.label}</span>
        ${paceNote}
        <span class="metric-resets" onclick="flipTimes()" title="Click to toggle exact/countdown">${resetsText}</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${usedPct}%;background:${color}"></div>${tick}</div>
      <div class="metric-bottom">
        <span class="headline" onclick="flipUsedLeft()" title="Click to toggle used/left">${headline}</span>
        <span></span>
      </div>
    </div>`;
}

function renderRow(line, idx) {
  const hasModels = Array.isArray(line.models) && line.models.length;
  const cls = hasModels ? 'value has-models' : 'value';
  const click = hasModels ? `onclick="toggleModels('${idx}')" title="Click for model breakdown"` : '';
  let html = `<div class="row"><span class="label">${line.label}</span><span class="${cls}" ${click}>${line.value ?? line.text ?? ''}</span></div>`;
  if (hasModels && openModels.has(String(idx))) {
    const maxCost = Math.max(...line.models.map(m => m.cost));
    html += '<div class="models">' + line.models.map(m => `
      <div class="model-row"><span class="m-name">${m.model}</span><span class="m-val">$${m.cost.toFixed(2)} · ${fmtTokens(m.tokens)} tok</span></div>
      <div class="model-bar" style="width:${maxCost ? (m.cost / maxCost * 100).toFixed(0) : 0}%"></div>
    `).join('') + '</div>';
  }
  return html;
}

function renderTrend(line) {
  if (!line.points || !line.points.length) return '';
  const maxVal = Math.max(...line.points.map(p => p.value));
  const bars = line.points.map(p =>
    `<div class="trend-bar" style="height:${maxVal ? Math.max(3, p.value / maxVal * 100) : 3}%" title="${p.label}: ${p.valueLabel || p.value}"></div>`
  ).join('');
  return `
    <div class="divider"></div>
    <div class="row"><span class="label">${line.label}</span><span></span></div>
    <div class="trend">${bars}</div>
    ${line.note ? `<div class="trend-note">${line.note}</div>` : ''}`;
}

function flipUsedLeft() {
  showLeft = !showLeft;
  localStorage.setItem('aiusage.showLeft', showLeft);
  load();
}
function flipTimes() {
  exactTimes = !exactTimes;
  localStorage.setItem('aiusage.exactTimes', exactTimes);
  load();
}
function toggleModels(idx) {
  openModels.has(idx) ? openModels.delete(idx) : openModels.add(idx);
  load();
}

let lastData = null;
async function load(refetch = true) {
  if (refetch || !lastData) {
    try {
      const res = await fetch('/v1/usage');
      lastData = await res.json();
    } catch (e) {
      document.getElementById('root').innerHTML = '<div class="empty">Can\\'t reach the local aiusage server.</div>';
      return;
    }
  }
  const data = lastData;
  const root = document.getElementById('root');
  if (!data.length) { root.innerHTML = '<div class="empty">No providers enabled yet.</div>'; return; }

  root.innerHTML = data.map(p => {
    const progressLines = p.lines.filter(l => l.type === 'progress');
    const textLines = p.lines.filter(l => l.type === 'text' && l.label !== 'Live data');
    const trendLine = p.lines.find(l => l.type === 'barChart');
    const staleLine = p.lines.find(l => l.label === 'Live data');
    let html = `<div class="card">
      <div class="card-head"><h2>${p.displayName}</h2>${p.plan ? `<span class="plan-pill">${p.plan}</span>` : ''}</div>`;
    if (staleLine) html += `<div class="error-row">${staleLine.value}</div>`;
    html += progressLines.map(renderMetric).join('');
    if (progressLines.length && textLines.length) html += '<div class="divider"></div>';
    html += textLines.map((l, i) => renderRow(l, `${p.providerId}-${i}`)).join('');
    if (trendLine) html += renderTrend(trendLine);
    html += `<div class="footer-time">Updated ${new Date(p.fetchedAt).toLocaleTimeString()}</div>`;
    html += '</div>';
    return html;
  }).join('');
}

load();
setInterval(load, 30000);
// Tick countdowns between refreshes without refetching.
setInterval(() => load(false), 30000 / 2);
</script>
</body></html>
"""
