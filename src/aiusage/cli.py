import argparse
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request

from . import __version__
from .config import DEFAULT_PORT
from .providers import claude as claude_provider
from .server import run_server

PYPI_PROJECT = "aiusage-tracker"


def _notify_if_outdated():
    """Best-effort, non-blocking. Never raises, never delays startup by more
    than ~1.5s -- this only runs once at command startup, not on the
    statusline render path."""
    try:
        req = urllib.request.Request(f"https://pypi.org/pypi/{PYPI_PROJECT}/json")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            latest = json.loads(resp.read().decode())["info"]["version"]
        if latest != __version__:
            print(f"aiusage: v{latest} available (you have v{__version__}) -- run `aiusage update`", file=sys.stderr)
    except Exception:
        pass


def cmd_status(args):
    _notify_if_outdated()
    snap = claude_provider.fetch_snapshot().to_dict()
    print(json.dumps(snap, indent=2))


def cmd_serve(args):
    _notify_if_outdated()
    run_server(port=args.port)


def cmd_tray(args):
    _notify_if_outdated()
    threading.Thread(target=run_server, kwargs={"port": args.port}, daemon=True).start()
    from .tray import run_tray
    run_tray()


def cmd_statusline(args):
    from .statusline import render
    print(render(port=args.port))


def cmd_setup(args):
    from .setup import run_setup
    run_setup(force=args.force)


def cmd_update(args):
    print(f"aiusage: currently v{__version__}, checking for updates...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", PYPI_PROJECT])
        source = "PyPI"
    except subprocess.CalledProcessError:
        print("aiusage: PyPI upgrade failed, trying GitHub source...")
        # --force-reinstall: the git source's version string doesn't bump on
        # every commit, so a plain --upgrade silently no-ops here (pip sees
        # "already satisfied" and skips it) even when main has moved on.
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "--force-reinstall", "--no-deps",
            "git+https://github.com/ahsanhabibakik/aiusage.git",
        ])
        source = "GitHub source"
    new_version = subprocess.check_output(
        [sys.executable, "-c", "import aiusage; print(aiusage.__version__)"]
    ).decode().strip()
    print(f"aiusage: updated via {source}, now v{new_version}")
    if new_version != __version__:
        print("Restart any running 'aiusage tray'/'aiusage serve' to use the new version.")


def main():
    parser = argparse.ArgumentParser(prog="aiusage", description="Track your AI coding subscription usage from the terminal, a local API, or the system tray.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="print current Claude usage as JSON and exit")
    p_status.set_defaults(func=cmd_status)

    p_serve = sub.add_parser("serve", help="run the local HTTP API + dashboard (no tray icon)")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.set_defaults(func=cmd_serve)

    p_tray = sub.add_parser("tray", help="run the system tray icon + local HTTP API (default)")
    p_tray.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_tray.set_defaults(func=cmd_tray)

    p_statusline = sub.add_parser("statusline", help="print one line of live usage for Claude Code's status bar")
    p_statusline.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_statusline.set_defaults(func=cmd_statusline)

    p_setup = sub.add_parser("setup", help="wire up Claude Code's statusLine + login autostart")
    p_setup.add_argument("--force", action="store_true", help="overwrite an existing different statusLine")
    p_setup.set_defaults(func=cmd_setup)

    p_update = sub.add_parser("update", help="upgrade aiusage to the latest version")
    p_update.set_defaults(func=cmd_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
