"""Cross-platform menu bar / system tray icons (Windows, macOS, Linux via pystray).

Two icons run side by side: one for the 5-hour session window, one for the
7-day weekly window. Each bakes its live percentage into the icon itself
(battery-badge style) so it reads at a glance without opening a menu.
"""
import threading
import time
import webbrowser
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

from .config import DEFAULT_PORT
from .providers import claude as claude_provider

# Matches OpenUsage's own default poll interval -- no reason to hit
# api.anthropic.com's usage endpoint any harder than the reference
# implementation does; a tighter interval risks 429s / provider throttling.
REFRESH_SECONDS = 300

# (r, g, b) at low / medium / high severity, per metric family so the two
# icons stay visually distinct even at a glance, before reading the number.
SESSION_COLORS = [(90, 140, 255), (255, 180, 60), (255, 90, 90)]   # blue -> amber -> red
WEEKLY_COLORS = [(150, 100, 230), (255, 140, 40), (230, 60, 90)]   # purple -> orange -> crimson


def _severity_color(percent, palette, pace_verdict=None):
    """Level-based severity, upgraded by the burn-rate verdict: a half-full
    window burning too fast is already red; a nearly-drained one coasting to
    the reset keeps its calmer color unless the level itself is critical."""
    if percent is None:
        return (120, 120, 130)
    if pace_verdict == "over" or percent >= 90:
        return palette[2]
    if pace_verdict == "tight" or percent >= 70:
        return palette[1]
    return palette[0]


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow < 10 has no `size` kwarg on load_default(); text will just
        # render at its one fixed built-in size instead of scaling.
        return ImageFont.load_default()


def _make_badge(percent, shape="circle", pace_verdict=None):
    palette = SESSION_COLORS if shape == "circle" else WEEKLY_COLORS
    color = _severity_color(percent, palette, pace_verdict) + (255,)
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if shape == "circle":
        draw.ellipse((2, 2, size - 2, size - 2), fill=color)
    else:
        # rounded square / diamond-ish badge so the weekly icon reads as a
        # different shape from the session circle even in black & white.
        draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=16, fill=color)

    label = "?" if percent is None else str(int(round(percent)))
    font_size = 34 if len(label) <= 2 else 26
    font = _font(font_size)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), label, fill=(255, 255, 255, 255), font=font)
    return img


def _format_duration(resets_at):
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


def _fetch_metrics():
    """One live API call, both metrics -- never fetch the same snapshot twice.
    Also runs the notification check on the same snapshot (no extra call)."""
    metrics = {"Session": (None, None, None), "Weekly": (None, None, None)}
    try:
        snap = claude_provider.fetch_snapshot()
        for line in snap.lines:
            if line.type == "progress" and line.label in metrics:
                verdict = (line.pace or {}).get("verdict")
                metrics[line.label] = (round(line.used or 0), line.resets_at, verdict)
        from .notify import check_and_notify
        check_and_notify(snap.lines)
    except Exception:
        pass
    return metrics


def _open_dashboard(icon, item):
    webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}")


def _tooltip(label, pct, resets_at):
    pct_text = f"{pct}%" if pct is not None else "?"
    duration = _format_duration(resets_at)
    reset_text = f" (resets in {duration})" if duration else ""
    return f"aiusage - Claude {label} {pct_text}{reset_text}"


def run_tray():
    import pystray

    metrics = _fetch_metrics()

    def make(label, shape):
        pct, resets_at, verdict = metrics[label]
        icon = pystray.Icon(
            f"aiusage-{label.lower()}",
            _make_badge(pct, shape, verdict),
            _tooltip(label, pct, resets_at),
        )
        return icon

    session_icon = make("Session", "circle")
    weekly_icon = make("Weekly", "square")

    def quit_both(icon, item):
        session_icon.stop()
        weekly_icon.stop()

    session_icon.menu = pystray.Menu(
        pystray.MenuItem("Open dashboard", _open_dashboard),
        pystray.MenuItem("Quit", quit_both),
    )
    weekly_icon.menu = pystray.Menu(
        pystray.MenuItem("Open dashboard", _open_dashboard),
        pystray.MenuItem("Quit", quit_both),
    )

    def _loop():
        while True:
            time.sleep(REFRESH_SECONDS)
            metrics = _fetch_metrics()
            for lbl, shape, icon in (("Session", "circle", session_icon), ("Weekly", "square", weekly_icon)):
                pct, resets_at, verdict = metrics[lbl]
                icon.icon = _make_badge(pct, shape, verdict)
                icon.title = _tooltip(lbl, pct, resets_at)

    threading.Thread(target=_loop, daemon=True).start()
    weekly_icon.run_detached()
    session_icon.run()
