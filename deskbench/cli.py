"""The agent's interface: every verb is a subcommand, every result is shell-consumable."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import engine, lock, sessions
from .engine import EngineError

PROGRAM = "deskbench"
VERSION = "0.1.0"

ASK_DONE = 0
ASK_TIMEOUT = 4
ASK_CLOSED = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Disposable graphical desktops for coding agents.",
    )
    parser.add_argument("--version", action="version", version=f"{PROGRAM} {VERSION}")
    subparsers = parser.add_subparsers(dest="verb", required=True)

    new = subparsers.add_parser("new", help="start a desktop and print its URL as JSON")
    new.add_argument("--name", help="desktop name (default: first free deskN)")
    new.add_argument("--size", default=sessions.DEFAULT_SIZE, help="screen geometry, WxH")
    new.add_argument("--image", help=f"override the container image (default {engine.IMAGE})")
    new.set_defaults(handler=cmd_new)

    listing = subparsers.add_parser("ls", help="list desktops")
    listing.add_argument("--json", action="store_true", help="machine-readable output")
    listing.set_defaults(handler=cmd_ls)

    url = subparsers.add_parser("url", help="print a desktop's viewer URL")
    url.add_argument("name")
    url.set_defaults(handler=cmd_url)

    run = subparsers.add_parser("exec", help="run a command inside a desktop")
    run.add_argument("name")
    run.add_argument("command", nargs=argparse.REMAINDER, help="-- command and arguments")
    run.set_defaults(handler=cmd_exec)

    shot = subparsers.add_parser("shot", help="capture the desktop to a PNG")
    shot.add_argument("name")
    shot.add_argument("-o", "--output", help="destination path (default: a temp file)")
    shot.set_defaults(handler=cmd_shot)

    logs = subparsers.add_parser("logs", help="print the desktop's log")
    logs.add_argument("name")
    logs.add_argument("-n", "--tail", type=int, default=40, help="number of lines")
    logs.set_defaults(handler=cmd_logs)

    stop = subparsers.add_parser("stop", help="stop a desktop")
    stop.add_argument("name")
    stop.set_defaults(handler=cmd_stop)

    ask = subparsers.add_parser("ask", help="ask a human to look at a desktop, and block")
    ask.add_argument("name")
    ask.add_argument("message")
    ask.add_argument("-t", "--timeout", type=int, default=600, help="seconds to wait")
    ask.set_defaults(handler=cmd_ask)

    tray = subparsers.add_parser("tray", help=argparse.SUPPRESS)
    tray.set_defaults(handler=cmd_tray)

    return parser


def _spawn_tray() -> None:
    """Start the tray unless one is already alive.

    ``DESKBENCH_NO_TRAY=1`` suppresses it, which is how the test suite keeps a GUI out of
    headless runs.
    """
    if os.environ.get("DESKBENCH_NO_TRAY") == "1":
        return
    if lock.is_held():
        return
    package_root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(package_root) + (os.pathsep + existing if existing else "")
    subprocess.Popen(
        [sys.executable, "-m", PROGRAM, "tray"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(package_root),
        env=env,
        start_new_session=True,
        close_fds=True,
    )


def cmd_new(args: argparse.Namespace) -> int:
    existing = [desktop.name for desktop in engine.list_desktops()]
    name = sessions.validate_name(args.name) if args.name else sessions.next_free_name(existing)
    if name in existing:
        raise EngineError(f"desktop {name!r} already exists; pick another name or stop it")
    size = sessions.validate_size(args.size)
    desktop = engine.create(name, size, args.image or engine.IMAGE)
    try:
        _spawn_tray()
    except OSError as exc:
        # The desktop is running and the caller needs to hear about it, even if the tray is not.
        print(f"{PROGRAM}: desktop started, but the tray could not be spawned: {exc}",
              file=sys.stderr)
    print(json.dumps(desktop.as_dict()))
    print(f"{PROGRAM}: {desktop.name} is up; viewer at {desktop.url}", file=sys.stderr)
    return 0


def cmd_ls(args: argparse.Namespace) -> int:
    desktops = engine.list_desktops()
    if args.json:
        print(json.dumps([desktop.as_dict() for desktop in desktops], indent=2))
        return 0
    if not desktops:
        print("no desktops")
        return 0
    width = max(len(desktop.name) for desktop in desktops)
    for desktop in desktops:
        print(f"{desktop.name:<{width}}  {desktop.state:<8}  {desktop.url}")
    return 0


def cmd_url(args: argparse.Namespace) -> int:
    desktop = engine.get(args.name)
    if not desktop.url:
        raise EngineError(f"desktop {args.name!r} is not publishing a viewer port")
    print(desktop.url)
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise EngineError("exec needs a command after `--`")
    return engine.exec_in(args.name, command)


def cmd_shot(args: argparse.Namespace) -> int:
    if args.output:
        destination = Path(args.output).expanduser()
    else:
        handle, path = tempfile.mkstemp(prefix=f"deskbench-{args.name}-", suffix=".png")
        os.close(handle)
        destination = Path(path)
    engine.shot(args.name, destination)
    print(destination)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    print(engine.logs(args.name, args.tail), end="")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    engine.stop(args.name)
    lock.poke()
    print(f"{PROGRAM}: stopped {args.name}", file=sys.stderr)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from . import notify

    return notify.ask(args.name, args.message, args.timeout)


def cmd_tray(_: argparse.Namespace) -> int:
    from . import tray

    return tray.main()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (EngineError, sessions.SessionError) as exc:
        print(f"{PROGRAM}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
