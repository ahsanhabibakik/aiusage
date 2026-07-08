"""Cross-platform menu bar / system tray icon (Windows, macOS, Linux via pystray)."""
import threading
import time
import webbrowser

from PIL import Image, ImageDraw

from .config import DEFAULT_PORT
from .providers import claude as claude_provider

REFRESH_SECONDS = 60


def _make_icon(percent):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (124, 124, 255, 255)
    if percent is not None and percent >= 90:
        color = (255, 90, 90, 255)
    elif percent is not None and percent >= 70:
        color = (255, 180, 60, 255)
    draw.ellipse((4, 4, size - 4, size - 4), outline=color, width=6)
    if percent is not None:
        extent = 360 * min(percent, 100) / 100
        draw.pieslice((4, 4, size - 4, size - 4), -90, -90 + extent, fill=color)
    return img


def _session_percent():
    try:
        snap = claude_provider.fetch_snapshot()
        for line in snap.lines:
            if line.type == "progress" and line.label == "Session":
                return round(line.used or 0)
    except Exception:
        pass
    return None


def _open_dashboard(icon, item):
    webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}")


def _quit(icon, item):
    icon.stop()


def run_tray():
    import pystray

    pct = _session_percent()
    icon = pystray.Icon(
        "aiusage",
        _make_icon(pct),
        f"aiusage — Claude session {pct if pct is not None else '?'}%",
        menu=pystray.Menu(
            pystray.MenuItem("Open dashboard", _open_dashboard),
            pystray.MenuItem("Quit", _quit),
        ),
    )

    def _loop():
        while True:
            time.sleep(REFRESH_SECONDS)
            pct = _session_percent()
            icon.icon = _make_icon(pct)
            icon.title = f"aiusage — Claude session {pct if pct is not None else '?'}%"

    threading.Thread(target=_loop, daemon=True).start()
    icon.run()
