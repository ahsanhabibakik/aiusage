#!/usr/bin/env bash
# Prints live Claude usage into Claude Code's own status line.
# Reads from aiusage's local cache (already refreshed every 5 min) --
# never calls api.anthropic.com directly, so this is safe to run on
# every status line render with no rate-limit risk. The token/spend
# figures are computed entirely from local session logs and stay
# available even when the live session/weekly % can't be fetched
# (e.g. rate limited).
set -o pipefail

resp=$(curl -s -m 1 http://127.0.0.1:8737/v1/usage/claude 2>/dev/null)
if [ -z "$resp" ]; then
    printf '\033[2mClaude usage: aiusage not running (aiusage tray)\033[0m\n'
    exit 0
fi

python3 -c "
import json, sys
from datetime import datetime, timezone

SESSION_HUES = [(100,200,255), (255,190,90), (255,110,110)]
WEEKLY_HUES  = [(190,150,255), (255,150,80), (255,90,130)]
BAR_WIDTH = 10

def color(pct, hues):
    if pct is None:
        return (150, 150, 150)
    if pct >= 90:
        return hues[2]
    if pct >= 70:
        return hues[1]
    return hues[0]

def fg(rgb):
    r, g, b = rgb
    return f'\033[38;2;{r};{g};{b}m'

RESET = '\033[0m'
DIM = '\033[2m'

def bar(pct, hues):
    filled = round(min(pct, 100) / 100 * BAR_WIDTH)
    c = fg(color(pct, hues))
    return f\"{c}{'█' * filled}{DIM}{'░' * (BAR_WIDTH - filled)}{RESET}\"

def duration(resets_at):
    if not resets_at:
        return None
    try:
        target = datetime.fromisoformat(resets_at.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
    seconds = (target - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        return 'soon'
    mins = round(seconds / 60)
    if mins < 60:
        return f'{mins}m'
    hrs, mins = divmod(mins, 60)
    if hrs < 24:
        return f'{hrs}h {mins}m'
    days, hrs = divmod(hrs, 24)
    return f'{days}d {hrs}h'

def metric(label, pct, hues, resets_at):
    c = fg(color(pct, hues))
    d = duration(resets_at)
    reset_text = f'{DIM} ({d}){RESET}' if d else ''
    return f'{c}{label} {bar(pct, hues)} {round(pct)}%{RESET}{reset_text}'

try:
    d = json.loads(sys.argv[1])
    lines = {l.get('label'): l for l in d.get('lines', [])}
    parts = []

    s = lines.get('Session')
    if s and s.get('type') == 'progress':
        parts.append(metric('5h', s.get('used', 0), SESSION_HUES, s.get('resets_at')))

    w = lines.get('Weekly')
    if w and w.get('type') == 'progress':
        parts.append(metric('7d', w.get('used', 0), WEEKLY_HUES, w.get('resets_at')))

    today = lines.get('Today')
    if today and today.get('type') == 'text' and today.get('value') and today['value'] != 'No data':
        parts.append(f\"{DIM}today {today['value']}{RESET}\")

    if parts:
        print(f'{DIM}Claude{RESET} ' + f'{DIM}|{RESET} '.join(parts))
    else:
        print(f'{DIM}Claude usage: no data yet{RESET}')
except Exception:
    print(f'\033[2mClaude usage: error reading data\033[0m')
" "$resp" 2>/dev/null

exit 0
