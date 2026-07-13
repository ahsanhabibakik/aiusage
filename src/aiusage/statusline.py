"""Renders live Claude usage for Claude Code's own status bar.

Bundled into the package (not a separately-fetched shell script) so the
statusLine command in ~/.claude/settings.json never drifts out of sync with
the installed version, and works offline. Reads from aiusage's own local
cache (127.0.0.1:8737) -- never calls api.anthropic.com directly, so this
is safe to run on every status bar render with no rate-limit risk.

Deliberately does NOT check for updates here: this path runs on every
render, and a network call would stall the status bar. Update checks live
in cli.py's status/serve/tray commands instead.
"""
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from .config import DEFAULT_PORT

SESSION_HUES = [(100, 200, 255), (255, 190, 90), (255, 110, 110)]
WEEKLY_HUES = [(190, 150, 255), (255, 150, 80), (255, 90, 130)]
BAR_WIDTH = 10
RESET = "\033[0m"
DIM = "\033[2m"


def _color(pct, hues, verdict=None):
    if pct is None:
        return (150, 150, 150)
    if verdict == "over" or pct >= 90:
        return hues[2]
    if verdict == "tight" or pct >= 70:
        return hues[1]
    return hues[0]


def _fg(rgb):
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m"


def _bar(pct, hues, verdict=None):
    filled = round(min(pct, 100) / 100 * BAR_WIDTH)
    c = _fg(_color(pct, hues, verdict))
    return f"{c}{'█' * filled}{DIM}{'░' * (BAR_WIDTH - filled)}{RESET}"


def _duration(resets_at):
    if not resets_at:
        return None
    try:
        target = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    seconds = (target - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        return "soon"
    mins = round(seconds / 60)
    if mins < 60:
        return f"{mins}m"
    hrs, mins = divmod(mins, 60)
    if hrs < 24:
        return f"{hrs}h {mins}m"
    days, hrs = divmod(hrs, 24)
    return f"{days}d {hrs}h"


def _metric(label, pct, hues, resets_at, verdict=None):
    c = _fg(_color(pct, hues, verdict))
    d = _duration(resets_at)
    flame = " ⚠" if verdict == "over" else ""
    reset_text = f"{DIM} ({d}){RESET}" if d else ""
    return f"{c}{label} {_bar(pct, hues, verdict)} {round(pct)}%{flame}{RESET}{reset_text}"


CODEX_HUES = [(70, 200, 160), (255, 180, 60), (255, 110, 110)]


def _fetch(port):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/usage")
    with urllib.request.urlopen(req, timeout=1) as resp:
        return json.loads(resp.read().decode())


def _provider_parts(snapshot, session_hues, weekly_hues, include_today=True):
    lines = {l.get("label"): l for l in snapshot.get("lines", [])}
    parts = []
    s = lines.get("Session")
    if s and s.get("type") == "progress":
        parts.append(_metric("5h", s.get("used", 0), session_hues, s.get("resets_at"),
                             (s.get("pace") or {}).get("verdict")))
    w = lines.get("Weekly")
    if w and w.get("type") == "progress":
        parts.append(_metric("7d", w.get("used", 0), weekly_hues, w.get("resets_at"),
                             (w.get("pace") or {}).get("verdict")))
    today = lines.get("Today")
    if include_today and today and today.get("type") == "text" and today.get("value") and today["value"] != "No data":
        parts.append(f"{DIM}today {today['value']}{RESET}")
    return parts


def render(port=DEFAULT_PORT):
    try:
        data = _fetch(port)
    except (urllib.error.URLError, OSError):
        return f"{DIM}Claude usage: aiusage not running (aiusage tray){RESET}"
    except Exception:
        return f"{DIM}Claude usage: error reading data{RESET}"

    try:
        by_id = {p.get("providerId"): p for p in data}
        segments = []

        claude = by_id.get("claude")
        if claude:
            parts = _provider_parts(claude, SESSION_HUES, WEEKLY_HUES)
            if parts:
                segments.append(f"{DIM}Claude{RESET} " + f"{DIM}|{RESET} ".join(parts))

        codex = by_id.get("codex")
        if codex:
            # Compact: bars only, no spend -- keeps the line from overflowing.
            parts = _provider_parts(codex, CODEX_HUES, CODEX_HUES, include_today=False)
            if parts:
                segments.append(f"{DIM}Codex{RESET} " + f"{DIM}|{RESET} ".join(parts))

        if segments:
            return f"  {DIM}‖{RESET}  ".join(segments)
        return f"{DIM}Claude usage: no data yet{RESET}"
    except Exception:
        return f"{DIM}Claude usage: error reading data{RESET}"
