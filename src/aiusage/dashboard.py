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
  .metric-resets { font-size: 12px; color: #7a7a8c; }
  .bar-track {
    height: 7px;
    border-radius: 4px;
    background: #232330;
    overflow: hidden;
  }
  .bar-fill { height: 100%; border-radius: 4px; transition: width .3s ease; }
  .metric-bottom {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    font-size: 12.5px;
    color: #9d9dae;
  }
  .divider { height: 1px; background: #232330; margin: 18px 0 14px; }
  .row {
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    font-size: 13px;
  }
  .row .label { color: #9d9dae; }
  .row .value { color: #e5e5ee; font-variant-numeric: tabular-nums; }
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

function barColor(usedPct) {
  if (usedPct >= 90) return RED;
  if (usedPct >= 70) return AMBER;
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

function renderMetric(line) {
  const usedPct = line.limit ? Math.round((line.used / line.limit) * 100) : 0;
  const leftPct = 100 - usedPct;
  const color = barColor(usedPct);
  let resetsText = '';
  if (line.resets_at) {
    const ms = new Date(line.resets_at).getTime() - Date.now();
    resetsText = `Resets in ${fmtDuration(ms)}`;
  }
  return `
    <div class="metric">
      <div class="metric-top">
        <span class="metric-label">${line.label}</span>
        <span class="metric-resets">${resetsText}</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${usedPct}%;background:${color}"></div></div>
      <div class="metric-bottom"><span>${leftPct}% left</span><span></span></div>
    </div>`;
}

function renderRow(line) {
  return `<div class="row"><span class="label">${line.label}</span><span class="value">${line.value ?? line.text ?? ''}</span></div>`;
}

async function load() {
  let data;
  try {
    const res = await fetch('/v1/usage');
    data = await res.json();
  } catch (e) {
    document.getElementById('root').innerHTML = '<div class="empty">Can\\'t reach the local aiusage server.</div>';
    return;
  }
  const root = document.getElementById('root');
  if (!data.length) { root.innerHTML = '<div class="empty">No providers enabled yet.</div>'; return; }

  root.innerHTML = data.map(p => {
    const progressLines = p.lines.filter(l => l.type === 'progress');
    const textLines = p.lines.filter(l => l.type === 'text' && l.label !== 'Live data');
    const staleLine = p.lines.find(l => l.label === 'Live data');
    let html = `<div class="card">
      <div class="card-head"><h2>${p.displayName}</h2>${p.plan ? `<span class="plan-pill">${p.plan}</span>` : ''}</div>`;
    if (staleLine) html += `<div class="error-row">${staleLine.value}</div>`;
    html += progressLines.map(renderMetric).join('');
    if (progressLines.length && textLines.length) html += '<div class="divider"></div>';
    html += textLines.map(renderRow).join('');
    html += `<div class="footer-time">Updated ${new Date(p.fetchedAt).toLocaleTimeString()}</div>`;
    html += '</div>';
    return html;
  }).join('');
}

load();
setInterval(load, 30000);
</script>
</body></html>
"""
