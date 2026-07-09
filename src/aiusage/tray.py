"""Cross-platform menu bar / system tray icons (Windows, macOS, Linux via pystray).

Two icons run side by side: one for the 5-hour session window, one for the
7-day weekly window. Each bakes its live percentage into the icon itself
(battery-badge style) so it reads at a glance without opening a menu.
"""
import threading
import time
import webbrowser

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


def _severity_color(percent, palette):
    if percent is None:
        return (120, 120, 130)
    if percent >= 90:
        return palette[2]
    if percent >= 70:
        return palette[1]
    return palette[0]


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow < 10 has no `size` kwarg on load_default(); text will just
        # render at its one fixed built-in size instead of scaling.
        return ImageFont.load_default()


def _make_badge(percent, shape="circle"):
    palette = SESSION_COLORS if shape == "circle" else WEEKLY_COLORS
    color = _severity_color(percent, palette) + (255,)
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


def _fetch_percents():
    """One live API call, both metrics -- never fetch the same snapshot twice."""
    percents = {"Session": None, "Weekly": None}
    try:
        snap = claude_provider.fetch_snapshot()
        for line in snap.lines:
            if line.type == "progress" and line.label in percents:
                percents[line.label] = round(line.used or 0)
    except Exception:
        pass
    return percents


def _open_dashboard(icon, item):
    webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}")


def run_tray():
    import pystray

    percents = _fetch_percents()

    def make(label, shape):
        pct = percents[label]
        icon = pystray.Icon(
            f"aiusage-{label.lower()}",
            _make_badge(pct, shape),
            f"aiusage - Claude {label} {pct if pct is not None else '?'}%",
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
            percents = _fetch_percents()
            for lbl, shape, icon in (("Session", "circle", session_icon), ("Weekly", "square", weekly_icon)):
                pct = percents[lbl]
                icon.icon = _make_badge(pct, shape)
                icon.title = f"aiusage - Claude {lbl} {pct if pct is not None else '?'}%"

    threading.Thread(target=_loop, daemon=True).start()
    weekly_icon.run_detached()
    session_icon.run()
