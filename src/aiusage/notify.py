"""Desktop notifications for usage alerts, once per metric per reset period.

Three alert kinds, mirroring the reference OpenUsage behavior:
- almost_out: a metric drops under 10% remaining
- will_run_out: burn-rate projection says it runs out before the reset
- limit_reached: the window is fully spent

Each fires at most once per (metric, resets_at) pair -- the resets_at
timestamp IS the period identity, so a new window automatically re-arms the
alert without any timer bookkeeping. State persists in the app config dir
so restarting the tray doesn't re-fire old alerts.
"""
import json
import platform
import subprocess

from .config import app_config_dir

_STATE_FILE = "notified.json"


def _load_state():
    path = app_config_dir() / _STATE_FILE
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def _save_state(state):
    d = app_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    # Keep only the most recent 100 keys so the file can't grow forever.
    if len(state) > 100:
        state = dict(list(state.items())[-100:])
    (d / _STATE_FILE).write_text(json.dumps(state))


def send_notification(title, body):
    """Best-effort, never raises."""
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(["notify-send", "--app-name=aiusage", title, body],
                           timeout=5, capture_output=True)
        elif system == "Darwin":
            script = f'display notification "{body}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
        elif system == "Windows":
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
                "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('ToastText02');"
                f"$t.GetElementsByTagName('text')[0].AppendChild($t.CreateTextNode('{title}')) > $null;"
                f"$t.GetElementsByTagName('text')[1].AppendChild($t.CreateTextNode('{body}')) > $null;"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('aiusage').Show("
                "[Windows.UI.Notifications.ToastNotification]::new($t))"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=10, capture_output=True)
    except Exception:
        pass


def check_and_notify(snapshot):
    """Walk a snapshot dict's progress lines, fire any newly-crossed alerts.
    Called after each tray refresh; cheap no-op when nothing has changed."""
    state = _load_state()
    changed = False
    provider = snapshot.get("displayName") or snapshot.get("providerId", "")

    for line in snapshot.get("lines", []):
        if line.get("type") != "progress" or line.get("used") is None or not line.get("resets_at"):
            continue
        name = f"{provider} {line.get('label')}".strip()
        left = (line.get("limit") or 100) - line["used"]
        pace = line.get("pace") or {}
        period_key = f"{snapshot.get('providerId')}|{line.get('label')}|{line['resets_at']}"

        alerts = []
        if left <= 0:
            alerts.append(("limit_reached", f"{name} limit reached",
                           f"Your {name} window is fully used. Resets soon."))
        elif left < 10:
            alerts.append(("almost_out", f"{name} almost out",
                           f"Under {round(left)}% left in your {name} window."))
        if pace.get("verdict") == "over" and left > 0:
            alerts.append(("will_run_out", f"{name} on pace to run out",
                           f"At the current rate your {name} window runs out before it resets "
                           f"(projected {pace['projected_used_pct']}% used)."))

        for kind, title, body in alerts:
            key = f"{period_key}|{kind}"
            if key not in state:
                send_notification(title, body)
                state[key] = True
                changed = True

    if changed:
        _save_state(state)
