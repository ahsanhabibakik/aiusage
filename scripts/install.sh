#!/usr/bin/env bash
# One-line installer for aiusage-tracker.
#   curl -fsSL https://raw.githubusercontent.com/ahsanhabibakik/aiusage/main/scripts/install.sh | bash
#
# Creates an isolated venv under ~/.local/share/aiusage-tracker so it never
# touches system Python packages, then symlinks the `aiusage` command into
# ~/.local/bin.
set -euo pipefail

INSTALL_DIR="$HOME/.local/share/aiusage-tracker"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_DIR/venv"

if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 not found. Install Python 3.9+ first." >&2
    exit 1
fi

py_ver=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
py_major=${py_ver%%.*}
py_minor=${py_ver##*.}
if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 9 ]; }; then
    echo "error: python3 is $py_ver, need 3.9+." >&2
    exit 1
fi

echo "aiusage-tracker: installing to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

# --system-site-packages: on Linux, lets the tray icon see the system's
# gi/AppIndicator3 libraries (python-gobject + libappindicator). Without this
# the tray silently falls back to a protocol modern DEs (Plasma 6, GNOME)
# don't render. Harmless no-op on macOS/Windows.
python3 -m venv --system-site-packages "$VENV_DIR"

if "$VENV_DIR/bin/pip" install --quiet --upgrade aiusage-tracker 2>/dev/null; then
    echo "aiusage-tracker: installed from PyPI"
else
    echo "aiusage-tracker: PyPI install failed, falling back to GitHub source"
    "$VENV_DIR/bin/pip" install --quiet "git+https://github.com/ahsanhabibakik/aiusage.git"
fi

ln -sf "$VENV_DIR/bin/aiusage" "$BIN_DIR/aiusage"

STATUSLINE_PATH="$INSTALL_DIR/statusline.sh"
curl -fsSL "https://raw.githubusercontent.com/ahsanhabibakik/aiusage/main/scripts/statusline.sh" -o "$STATUSLINE_PATH"
chmod +x "$STATUSLINE_PATH"

echo
echo "Installed. Run:  aiusage status"
echo "Or:               aiusage tray     (system tray icon)"
echo "Or:               aiusage serve    (local dashboard at http://127.0.0.1:8737)"

# --- Wire into Claude Code's status bar -------------------------------
# Merges statusLine in, never overwrites a DIFFERENT one you already set.
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
python3 - "$CLAUDE_SETTINGS" "$STATUSLINE_PATH" <<'PYEOF'
import json, os, sys

settings_path, statusline_path = sys.argv[1], sys.argv[2]
our_command = f"bash {statusline_path}"

data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        print("aiusage-tracker: existing settings.json is invalid JSON, leaving statusLine setup to you")
        sys.exit(0)

existing = data.get("statusLine")
if existing and existing.get("command") != our_command:
    print(f"aiusage-tracker: you already have a different statusLine set ({existing.get('command')!r}) -- not touching it.")
    print(f"  To use aiusage's instead: \"statusLine\": {{\"type\": \"command\", \"command\": \"{our_command}\"}}")
    sys.exit(0)
if existing:
    print("aiusage-tracker: statusLine already wired up, nothing to do")
    sys.exit(0)

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
if os.path.exists(settings_path):
    import shutil
    shutil.copy(settings_path, settings_path + ".bak")

data["statusLine"] = {"type": "command", "command": our_command}
with open(settings_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"aiusage-tracker: wired into {settings_path} (backup saved as .bak)")
PYEOF

# --- Autostart the tray at login ---------------------------------------
OS_NAME="$(uname -s)"
if [ "$OS_NAME" = "Linux" ]; then
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/aiusage-tracker.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=aiusage
Comment=AI coding subscription usage tracker (tray icon)
Exec=$BIN_DIR/aiusage tray
Icon=utilities-system-monitor
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
    echo "aiusage-tracker: autostart entry added ($AUTOSTART_DIR/aiusage-tracker.desktop)"
elif [ "$OS_NAME" = "Darwin" ]; then
    AGENT_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$AGENT_DIR"
    PLIST="$AGENT_DIR/dev.aiusage.tracker.plist"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>dev.aiusage.tracker</string>
    <key>ProgramArguments</key>
    <array><string>$BIN_DIR/aiusage</string><string>tray</string></array>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
EOF
    launchctl load "$PLIST" 2>/dev/null || true
    echo "aiusage-tracker: autostart agent added and loaded ($PLIST)"
fi

# --- Launch it right now, no login/restart needed -----------------------
if ! pgrep -f "$BIN_DIR/aiusage tray" >/dev/null 2>&1 && ! pgrep -f "$VENV_DIR/bin/aiusage tray" >/dev/null 2>&1; then
    nohup "$BIN_DIR/aiusage" tray >/tmp/aiusage-tracker.log 2>&1 &
    disown
    echo "aiusage-tracker: tray launched now (PID $!)"
fi

echo
echo "Everything's wired up: tray running, autostart set, statusLine active."
echo "Open a new Claude Code session (or run /statusline once) to see it there."

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo
        echo "Note: $BIN_DIR is not on your PATH. Add this to your shell profile:"
        echo "  export PATH=\"$BIN_DIR:\$PATH\""
        ;;
esac

case "$OS_NAME" in
    Linux)
        echo
        echo "Linux tray icon: needs python-gobject + libappindicator system packages"
        echo "to actually render in modern panels (Plasma 6, GNOME)."
        echo "  Arch:          sudo pacman -S python-gobject libappindicator"
        echo "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-appindicator3-0.1"
        echo "Without these, use 'aiusage serve' + http://127.0.0.1:8737 instead."
        ;;
esac
