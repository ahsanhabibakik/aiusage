#!/usr/bin/env bash
# Prints live Claude usage into Claude Code's own status line.
# Reads from aiusage's local cache (already refreshed every 5 min) --
# never calls api.anthropic.com directly, so this is safe to run on
# every status line render with no rate-limit risk.
set -o pipefail

resp=$(curl -s -m 1 http://127.0.0.1:8737/v1/usage/claude 2>/dev/null)
[ -z "$resp" ] && exit 0

python3 -c "
import json, sys

# Same hue families as the tray icons: session=blue family, weekly=purple
# family, so the two windows read as visually distinct at a glance, with
# severity (green/amber/red) layered on top.
SESSION_HUES = [(100,200,255), (255,190,90), (255,110,110)]
WEEKLY_HUES  = [(190,150,255), (255,150,80), (255,90,130)]

def color(pct, hues):
    if pct is None:
        return (150, 150, 150)
    if pct >= 90:
        return hues[2]
    if pct >= 70:
        return hues[1]
    return hues[0]

def paint(text, rgb):
    r, g, b = rgb
    return f'\033[1;38;2;{r};{g};{b}m{text}\033[0m'

try:
    d = json.loads(sys.argv[1])
    lines = {l.get('label'): l for l in d.get('lines', [])}
    parts = []
    s = lines.get('Session')
    if s and s.get('type') == 'progress':
        pct = round(s.get('used', 0))
        parts.append(paint(f'5h {pct}%', color(pct, SESSION_HUES)))
    w = lines.get('Weekly')
    if w and w.get('type') == 'progress':
        pct = round(w.get('used', 0))
        parts.append(paint(f'7d {pct}%', color(pct, WEEKLY_HUES)))
    if parts:
        print('\033[2mClaude\033[0m ' + '  '.join(parts))
except Exception:
    pass
" "$resp" 2>/dev/null

exit 0
