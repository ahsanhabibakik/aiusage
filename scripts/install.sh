#!/usr/bin/env bash
# One-line installer for aiusage-tracker (macOS / Linux / WSL).
#   curl -fsSL https://raw.githubusercontent.com/ahsanhabibakik/aiusage/main/scripts/install.sh | bash
# Windows (PowerShell):
#   irm https://raw.githubusercontent.com/ahsanhabibakik/aiusage/main/scripts/install.ps1 | iex
#
# Tiered: with Python 3.9+ it installs into an isolated venv (lightest, and
# on Linux the only way the tray icon can use the system's AppIndicator
# libs). Without Python it downloads a self-contained binary from GitHub
# Releases -- no runtime needed at all. Safe to re-run any time; idempotent.
set -euo pipefail

INSTALL_DIR="$HOME/.local/share/aiusage-tracker"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_DIR/venv"
REPO="ahsanhabibakik/aiusage"

have_python() {
    command -v python3 >/dev/null 2>&1 || return 1
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null
}

binary_target() {
    case "$(uname -s)" in
        Linux)  echo "linux-x86_64" ;;
        # Apple Silicon only -- no Intel macOS binary (GitHub retired the
        # Intel runners). Intel Macs use the Python path below instead.
        Darwin) [ "$(uname -m)" = "arm64" ] && echo "macos-arm64" || echo "" ;;
        *)      echo "" ;;
    esac
}

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

if have_python; then
    echo "aiusage-tracker: Python found -- installing to venv at $INSTALL_DIR"
    # --system-site-packages: on Linux, lets the tray icon see the system's
    # gi/AppIndicator3 libraries (python-gobject + libappindicator). Without
    # this the tray silently falls back to a protocol modern DEs (Plasma 6,
    # GNOME) don't render. Harmless no-op on macOS.
    python3 -m venv --system-site-packages "$VENV_DIR"
    if "$VENV_DIR/bin/pip" install --quiet --upgrade aiusage-tracker 2>/dev/null; then
        echo "aiusage-tracker: installed from PyPI"
    else
        echo "aiusage-tracker: PyPI install failed, falling back to GitHub source"
        "$VENV_DIR/bin/pip" install --quiet --upgrade "git+https://github.com/$REPO.git"
    fi
    ln -sf "$VENV_DIR/bin/aiusage" "$BIN_DIR/aiusage"
else
    target=$(binary_target)
    if [ -z "$target" ]; then
        echo "error: no Python 3.9+ and no prebuilt binary for $(uname -s). Install Python first." >&2
        exit 1
    fi
    echo "aiusage-tracker: no Python 3.9+ found -- downloading standalone binary ($target)"
    url="https://github.com/$REPO/releases/latest/download/aiusage-$target"
    if ! curl -fsSL "$url" -o "$BIN_DIR/aiusage.tmp"; then
        echo "error: binary download failed ($url). Install Python 3.9+ and re-run instead." >&2
        exit 1
    fi
    chmod +x "$BIN_DIR/aiusage.tmp"
    mv "$BIN_DIR/aiusage.tmp" "$BIN_DIR/aiusage"
    if [ "$(uname -s)" = "Linux" ]; then
        echo "note: the standalone Linux binary can't bundle the system AppIndicator"
        echo "      libs, so the tray icon may not render on Plasma 6/GNOME."
        echo "      'aiusage serve' + http://127.0.0.1:8737 works fully; for the"
        echo "      tray, install python3 and re-run this installer."
    fi
fi

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
