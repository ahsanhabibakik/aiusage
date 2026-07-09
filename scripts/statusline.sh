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
try:
    d = json.loads(sys.argv[1])
    lines = {l.get('label'): l for l in d.get('lines', [])}
    parts = []
    s = lines.get('Session')
    if s and s.get('type') == 'progress':
        parts.append(f\"5h:{round(s.get('used', 0))}%\")
    w = lines.get('Weekly')
    if w and w.get('type') == 'progress':
        parts.append(f\"7d:{round(w.get('used', 0))}%\")
    if parts:
        print('Claude ' + ' '.join(parts))
except Exception:
    pass
" "$resp" 2>/dev/null

exit 0
