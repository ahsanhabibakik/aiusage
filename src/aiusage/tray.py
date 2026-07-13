"""Cross-platform menu bar / system tray icons (Windows, macOS, Linux via pystray).

Up to two icons per detected provider (session + weekly window), each baking
its live percentage into the badge itself so it reads at a glance. Reads
through the server module's snapshot cache, so however many icons exist,
each provider's API is polled at most once per refresh interval.
"""
import threading
import time
import webbrowser
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

from .config import DEFAULT_PORT

# Matches OpenUsage's own default poll interval -- no reason to hit any
# provider's usage endpoint harder than the reference implementation does;
# a tighter interval risks 429s / provider throttling.
REFRESH_SECONDS = 300

# (r, g, b) at low / medium / high severity. Distinct hue family per icon so
# they read apart at a glance, before reading the number.
PALETTES = {
    ("claude", "Session"): [(90, 140, 255), (255, 180, 60), (255, 90, 90)],    # blue
    ("claude", "Weekly"): [(150, 100, 230), (255, 140, 40), (230, 60, 90)],    # purple
    ("codex", "Session"): [(70, 200, 160), (255, 180, 60), (255, 90, 90)],     # green
    ("codex", "Weekly"): [(50, 160, 190), (255, 140, 40), (230, 60, 90)],      # teal
}
DEFAULT_PALETTE = [(140, 140, 150), (255, 180, 60), (255, 90, 90)]


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


def _make_badge(percent, palette, shape="circle", pace_verdict=None):
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


def _fetch_all():
    """Snapshot every enabled provider through the server's cache (one real
    API call per provider per cache window) and run notification checks."""
    from .server import PROVIDERS, _get_snapshot
    from .notify import check_and_notify
    snapshots = {}
    for provider_id in PROVIDERS:
        try:
            snap = _get_snapshot(provider_id)
            if snap:
                snapshots[provider_id] = snap
                check_and_notify(snap)
        except Exception:
            continue
    return snapshots


def _icon_specs(snapshots):
    """(provider_id, label, shape) for every icon we want to show: the first
    Session-ish and Weekly-ish progress line of each provider."""
    specs = []
    for provider_id, snap in snapshots.items():
        seen = set()
        for line in snap.get("lines", []):
            if line.get("type") != "progress":
                continue
            label = line.get("label")
            if label in ("Session", "Weekly") and label not in seen:
                seen.add(label)
                specs.append((provider_id, label, "circle" if label == "Session" else "square"))
    return specs


def _metric(snapshots, provider_id, label):
    for line in snapshots.get(provider_id, {}).get("lines", []):
        if line.get("type") == "progress" and line.get("label") == label:
            verdict = (line.get("pace") or {}).get("verdict")
            return round(line.get("used") or 0), line.get("resets_at"), verdict
    return None, None, None


def _open_dashboard(icon, item):
    webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}")


def _tooltip(snapshots, provider_id, label, pct, resets_at):
    name = snapshots.get(provider_id, {}).get("displayName", provider_id.title())
    pct_text = f"{pct}%" if pct is not None else "?"
    duration = _format_duration(resets_at)
    reset_text = f" (resets in {duration})" if duration else ""
    return f"aiusage - {name} {label} {pct_text}{reset_text}"


def run_tray():
    import pystray

    snapshots = _fetch_all()
    specs = _icon_specs(snapshots)
    if not specs:
        # Nothing fetched yet (offline, logged out) -- still show Claude's
        # two icons as unknown rather than exiting with no UI at all.
        specs = [("claude", "Session", "circle"), ("claude", "Weekly", "square")]

    icons = []

    def quit_all(icon, item):
        for ic in icons:
            ic.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open dashboard", _open_dashboard),
        pystray.MenuItem("Quit", quit_all),
    )

    for provider_id, label, shape in specs:
        pct, resets_at, verdict = _metric(snapshots, provider_id, label)
        palette = PALETTES.get((provider_id, label), DEFAULT_PALETTE)
        icon = pystray.Icon(
            f"aiusage-{provider_id}-{label.lower()}",
            _make_badge(pct, palette, shape, verdict),
            _tooltip(snapshots, provider_id, label, pct, resets_at),
            menu=menu,
        )
        icons.append((icon, provider_id, label, shape, palette))

    def _loop():
        while True:
            time.sleep(REFRESH_SECONDS)
            snapshots = _fetch_all()
            for icon, provider_id, label, shape, palette in icons:
                pct, resets_at, verdict = _metric(snapshots, provider_id, label)
                icon.icon = _make_badge(pct, palette, shape, verdict)
                icon.title = _tooltip(snapshots, provider_id, label, pct, resets_at)

    threading.Thread(target=_loop, daemon=True).start()
    for icon, *_ in icons[1:]:
        icon.run_detached()
    icons[0][0].run()
