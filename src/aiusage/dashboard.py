DASHBOARD_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>aiusage</title>
<style>
body{font:14px -apple-system,Segoe UI,Roboto,sans-serif;background:#0b0b0f;color:#eaeaf0;margin:0;padding:24px}
.card{background:#16161d;border-radius:12px;padding:16px 20px;margin-bottom:16px;max-width:480px}
.card h2{margin:0 0 12px;font-size:15px;color:#9d9dff}
.line{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #24242c}
.line:last-child{border-bottom:none}
.bar{height:6px;border-radius:3px;background:#26263a;margin-top:4px;overflow:hidden}
.bar > div{height:100%;background:linear-gradient(90deg,#7c7cff,#9d9dff)}
.muted{color:#8888a0;font-size:12px}
</style></head>
<body>
<div id="root">Loading…</div>
<script>
async function load() {
  const res = await fetch('/v1/usage');
  const data = await res.json();
  const root = document.getElementById('root');
  root.innerHTML = '';
  if (!data.length) { root.textContent = 'No providers enabled yet.'; return; }
  for (const p of data) {
    const card = document.createElement('div');
    card.className = 'card';
    let html = `<h2>${p.displayName}</h2>`;
    for (const l of p.lines) {
      if (l.type === 'progress') {
        const pct = l.limit ? Math.round((l.used / l.limit) * 100) : 0;
        html += `<div class="line"><div>${l.label}</div><div>${pct}%</div></div>
                 <div class="bar"><div style="width:${pct}%"></div></div>`;
      } else {
        html += `<div class="line"><div>${l.label}</div><div>${l.value || l.text || ''}</div></div>`;
      }
    }
    html += `<div class="muted">Fetched ${new Date(p.fetchedAt).toLocaleTimeString()}</div>`;
    card.innerHTML = html;
    root.appendChild(card);
  }
}
load();
setInterval(load, 30000);
</script>
</body></html>
"""
