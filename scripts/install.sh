#!/usr/bin/env bash
# One-line installer for aiusage-tracker.
#   curl -fsSL https://raw.githubusercontent.com/ahsanhabibakik/aiusage/main/scripts/install.sh | bash
#
# Creates an isolated venv under ~/.local/share/aiusage-tracker so it never
# touches system Python packages, then symlinks the `aiusage` command into
# ~/.local/bin. Safe to re-run any time -- idempotent.
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
    "$VENV_DIR/bin/pip" install --quiet --upgrade "git+https://github.com/ahsanhabibakik/aiusage.git"
fi

ln -sf "$VENV_DIR/bin/aiusage" "$BIN_DIR/aiusage"

echo
echo "Installed. Run:  aiusage status"
echo "Or:               aiusage tray     (system tray icon)"
echo "Or:               aiusage serve    (local dashboard at http://127.0.0.1:8737)"
echo

# Statusline + autostart wiring is bundled in the package itself (`aiusage
# setup`) so it's always in sync with whatever version just got installed --
# never overwrites a different statusLine you already have without --force.
"$BIN_DIR/aiusage" setup

# Launch it right now -- no login/restart needed to see it working.
if ! pgrep -f "$BIN_DIR/aiusage tray" >/dev/null 2>&1 && ! pgrep -f "$VENV_DIR/bin/aiusage tray" >/dev/null 2>&1; then
    nohup "$BIN_DIR/aiusage" tray >/tmp/aiusage-tracker.log 2>&1 &
    disown
    echo "aiusage-tracker: tray launched now (PID $!)"
fi

echo
echo "To see it in Claude Code: open a NEW terminal/session (don't run"
echo "/statusline -- that's Claude Code's own config wizard and will"
echo "overwrite this with its sample statusline instead of reloading it)."

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo
        echo "Note: $BIN_DIR is not on your PATH. Add this to your shell profile:"
        echo "  export PATH=\"$BIN_DIR:\$PATH\""
        ;;
esac

case "$(uname -s)" in
    Linux)
        echo
        echo "Linux tray icon: needs python-gobject + libappindicator system packages"
        echo "to actually render in modern panels (Plasma 6, GNOME)."
        echo "  Arch:          sudo pacman -S python-gobject libappindicator"
        echo "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-appindicator3-0.1"
        echo "Without these, use 'aiusage serve' + http://127.0.0.1:8737 instead."
        ;;
esac

echo
echo "Update any time with:  aiusage update"
