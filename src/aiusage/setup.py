"""Wires aiusage into Claude Code's statusLine and the OS's login autostart.

Only ever runs when explicitly invoked (`aiusage setup`, or once at the end
of the installer). Never runs unattended in the background -- rewriting a
shared config file like ~/.claude/settings.json without being asked is
exactly the kind of thing this deliberately avoids. If something else (e.g.
Claude Code's own `/statusline` wizard) overwrites the statusLine field
later, re-running `aiusage setup` puts it back; nothing does that silently.
"""
import json
import os
import platform
import shutil
import sys
from pathlib import Path


def claude_settings_path():
    return Path.home() / ".claude" / "settings.json"


def aiusage_statusline_command():
    exe = sys.argv[0]
    if not os.path.isabs(exe):
        found = shutil.which("aiusage")
        exe = found or exe
    return f"{exe} statusline"


def wire_statusline(force=False):
    """Returns (changed: bool, message: str)."""
    path = claude_settings_path()
    our_command = aiusage_statusline_command()

    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return False, f"{path} is invalid JSON -- not touching it, fix manually"

    existing = data.get("statusLine")
    if existing and existing.get("command") != our_command and not force:
        return False, (
            f"a different statusLine is already set ({existing.get('command')!r}). "
            f"Re-run with --force to replace it, or add this yourself:\n"
            f'  "statusLine": {{"type": "command", "command": "{our_command}"}}'
        )
    if existing and existing.get("command") == our_command:
        return False, "statusLine already wired up, nothing to do"

    path.parent.mkdir(parents=True, exist_ok=True)
    backed_up = path.exists()
    if backed_up:
        shutil.copy(path, path.with_suffix(".json.bak"))
    data["statusLine"] = {"type": "command", "command": our_command}
    path.write_text(json.dumps(data, indent=2) + "\n")
    suffix = f" (backup of previous file saved as {path.name}.bak)" if backed_up else ""
    return True, f"wired into {path}{suffix}"


def _linux_autostart_path():
    return Path.home() / ".config" / "autostart" / "aiusage-tracker.desktop"


def _macos_agent_path():
    return Path.home() / "Library" / "LaunchAgents" / "dev.aiusage.tracker.plist"


def write_autostart():
    """Returns (path_or_none, message)."""
    exe = shutil.which("aiusage") or sys.argv[0]
    system = platform.system()

    if system == "Linux":
        path = _linux_autostart_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=aiusage\n"
            "Comment=AI coding subscription usage tracker (tray icon)\n"
            f"Exec={exe} tray\n"
            "Icon=utilities-system-monitor\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        return path, f"autostart entry added ({path})"

    if system == "Darwin":
        path = _macos_agent_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            "  <key>Label</key><string>dev.aiusage.tracker</string>\n"
            "  <key>ProgramArguments</key>\n"
            f"  <array><string>{exe}</string><string>tray</string></array>\n"
            "  <key>RunAtLoad</key><true/>\n"
            "</dict>\n</plist>\n"
        )
        os.system(f'launchctl load "{path}" 2>/dev/null')
        return path, f"autostart agent added and loaded ({path})"

    return None, f"no autostart support for {system} yet -- run `aiusage tray` manually after login"


def run_setup(force=False):
    changed, msg = wire_statusline(force=force)
    print(f"statusLine: {msg}")
    path, msg = write_autostart()
    print(f"autostart: {msg}")
