import argparse
import json
import sys
import threading

from .config import DEFAULT_PORT
from .providers import claude as claude_provider
from .server import run_server


def cmd_status(args):
    snap = claude_provider.fetch_snapshot().to_dict()
    print(json.dumps(snap, indent=2))


def cmd_serve(args):
    run_server(port=args.port)


def cmd_tray(args):
    threading.Thread(target=run_server, kwargs={"port": args.port}, daemon=True).start()
    from .tray import run_tray
    run_tray()


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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
