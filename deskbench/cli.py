"""The agent's interface: every verb is a subcommand, every result is shell-consumable."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import engine, flavours, lock, sessions, term
from .engine import EngineError

PROGRAM = "deskbench"
VERSION = "0.1.0"

# Verbs that need PyGObject (GTK, AppIndicator, the notification service).
GUI_VERBS = {"tray", "ask"}

SYSTEM_PYTHONS = ("/usr/bin/python3", "/usr/local/bin/python3")

ASK_DONE = 0
ASK_TIMEOUT = 4
ASK_CLOSED = 5


def _gi_available() -> bool:
    try:
        import gi  # noqa: F401
    except ImportError:
        return False
    return True


def _system_python() -> str | None:
    for candidate in SYSTEM_PYTHONS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _use_gi_interpreter(arguments: list[str]) -> None:
    """Re-exec a GUI verb under an interpreter that can import PyGObject.

    PyGObject is a system package and cannot be installed into a virtualenv casually, so a console
    script living in an isolated environment (uv tool, pipx) has no ``gi``. Rather than failing with
    "No module named 'gi'", hand the verb to the system interpreter, which does.
    """
    if _gi_available():
        return
    python = _system_python()
    if python is None:
        return
    package_root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = package_root + (os.pathsep + existing if existing else "")
    os.execve(python, [python, "-m", PROGRAM, *arguments], env)


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
    image_choice = new.add_mutually_exclusive_group()
    image_choice.add_argument(
        "--flavour",
        default=None,
        metavar="NAME",
        help="built-in or user flavour (see `deskbench images`; default: base)",
    )
    image_choice.add_argument(
        "--image",
        metavar="REF",
        help="fully qualified OCI image reference carrying a tag or digest",
    )
    new.add_argument(
        "--pull",
        choices=("missing", "always", "never"),
        default="missing",
        help="image pull policy: missing uses a local image and pulls only when absent, "
             "always refreshes it, never fails when absent (default: missing)",
    )
    new.add_argument("--bind", action="append", default=[], metavar="SRC[:DST][:ro]",
                     help="make a host path visible inside the desktop (repeatable)")
    new.set_defaults(handler=cmd_new)

    images = subparsers.add_parser("images", help="list the built-in and user image flavours")
    images.add_argument("--json", action="store_true", help="machine-readable output")
    images.set_defaults(handler=cmd_images)

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
    shot.add_argument("--settle", type=int, default=250,
                      metavar="MS", help="how long the screen must stay still (default 250)")
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

    capabilities = subparsers.add_parser(
        "capabilities", help="report what a desktop can do right now (shell, tmux, package managers)"
    )
    capabilities.add_argument("name")
    capabilities.add_argument("--json", action="store_true", help="machine-readable output")
    capabilities.set_defaults(handler=cmd_capabilities)

    terminal = subparsers.add_parser("term", help="tmux sessions inside a desktop")
    term_verbs = terminal.add_subparsers(dest="term_verb", required=True)

    term_start_parser = term_verbs.add_parser("start", help="start a session at a fixed grid")
    term_start_parser.add_argument("name")
    term_start_parser.add_argument("--cells", required=True, metavar="WxH",
                                   help="grid in character cells, columns x rows (required)")
    term_start_parser.add_argument("--session", default=term.DEFAULT_SESSION, help="session name")
    term_start_parser.set_defaults(handler=cmd_term_start)

    term_screen_parser = term_verbs.add_parser("screen", help="print a session's visible screen")
    term_screen_parser.add_argument("name")
    term_screen_parser.add_argument("--session", default=term.DEFAULT_SESSION, help="session name")
    term_screen_parser.add_argument("--history", type=int, default=0, metavar="N",
                                    help="also print up to N lines of scrollback")
    term_screen_parser.set_defaults(handler=cmd_term_screen)

    term_send_parser = term_verbs.add_parser("send", help="type text, or one key, into a session")
    term_send_parser.add_argument("name")
    term_send_parser.add_argument("--session", default=term.DEFAULT_SESSION, help="session name")
    term_send_parser.add_argument("--key", metavar="KEY", help="send one named key, such as C-c")
    term_send_parser.add_argument("text", nargs="?", help="-- TEXT, typed then followed by Enter")
    term_send_parser.set_defaults(handler=cmd_term_send)

    term_list_parser = term_verbs.add_parser("list", help="list a desktop's sessions")
    term_list_parser.add_argument("name")
    term_list_parser.add_argument("--json", action="store_true", help="machine-readable output")
    term_list_parser.set_defaults(handler=cmd_term_list)

    term_stop_parser = term_verbs.add_parser("stop", help="end one session")
    term_stop_parser.add_argument("name")
    term_stop_parser.add_argument("--session", default=term.DEFAULT_SESSION, help="session name")
    term_stop_parser.set_defaults(handler=cmd_term_stop)

    tray = subparsers.add_parser("tray", help=argparse.SUPPRESS)
    tray.set_defaults(handler=cmd_tray)

    return parser


def _spawn_tray() -> None:
    """Start the tray unless one is already alive.

    ``DESKBENCH_NO_TRAY=1`` suppresses it, which is how the test suite keeps a GUI out of
    headless runs. The child's output goes to a log next to the lock: a tray that dies on
    start-up must not be invisible.
    """
    if os.environ.get("DESKBENCH_NO_TRAY") == "1":
        return
    if lock.is_held():
        return
    package_root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(package_root) + (os.pathsep + existing if existing else "")
    with open(lock.state_dir() / "tray.log", "ab", buffering=0) as log:
        subprocess.Popen(
            [sys.executable, "-m", PROGRAM, "tray"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
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
    binds = [sessions.parse_bind(value) for value in args.bind]
    if args.image:
        flavour = flavours.adhoc(args.image)
    else:
        flavour = flavours.get(args.flavour or "base")
    desktop = engine.create(name, size, flavour, binds, args.pull)
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


def cmd_images(args: argparse.Namespace) -> int:
    discovery = flavours.discover()
    for problem in discovery.problems:
        print(f"{PROGRAM}: ignoring {problem.path}: {problem.message}", file=sys.stderr)
    rows = [
        {
            "name": flavour.name,
            "source": flavour.source,
            "image": flavour.image,
            "present": engine.image_exists(flavour.image),
            "summary": flavour.summary,
        }
        for flavour in discovery.flavours
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    name_width = max(len(row["name"]) for row in rows)
    source_width = max(len(row["source"]) for row in rows)
    image_width = max(len(row["image"]) for row in rows)
    for row in rows:
        state = "yes" if row["present"] else "no"
        print(f"{row['name']:<{name_width}}  {row['source']:<{source_width}}  "
              f"{state:<3}  {row['image']:<{image_width}}  {row['summary']}")
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
    engine.shot(args.name, destination, args.settle)
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


def cmd_capabilities(args: argparse.Namespace) -> int:
    report = engine.capabilities_of(args.name)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    for tool in ("shell", "screenshot", "tmux", "sudo"):
        print(f"{tool}: {report[tool] or 'absent'}")
    for manager, path in report["package_managers"].items():
        print(f"{manager}: {path or 'absent'}")
    write = report["privileged_write"]
    print(f"privileged write: {'yes' if write['possible'] else 'no'} "
          f"(measured with {write['measured_with']})")
    return 0


def cmd_term_start(args: argparse.Namespace) -> int:
    cols, rows = term.validate_cells(args.cells)
    session = sessions.validate_name(args.session)
    engine.term_start(args.name, cols, rows, session)
    return 0


def cmd_term_screen(args: argparse.Namespace) -> int:
    if args.history < 0:
        raise sessions.SessionError("--history must be zero or more lines")
    session = sessions.validate_name(args.session)
    print(engine.term_screen(args.name, session, args.history), end="")
    return 0


def cmd_term_send(args: argparse.Namespace) -> int:
    if (args.text is None) == (args.key is None):
        raise sessions.SessionError("give either TEXT or --key KEY, not both and not neither")
    session = sessions.validate_name(args.session)
    engine.term_send(args.name, session, args.text, args.key)
    return 0


def cmd_term_list(args: argparse.Namespace) -> int:
    listed = engine.term_list(args.name)
    if args.json:
        print(json.dumps([entry.as_dict() for entry in listed], indent=2))
        return 0
    if not listed:
        print("no term sessions")
        return 0
    width = max(len(entry.name) for entry in listed)
    for entry in listed:
        print(f"{entry.name:<{width}}  {entry.grid:<9}  attached {entry.attached}")
    return 0


def cmd_term_stop(args: argparse.Namespace) -> int:
    session = sessions.validate_name(args.session)
    engine.term_stop(args.name, session)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from . import notify

    return notify.ask(args.name, args.message, args.timeout)


def cmd_tray(_: argparse.Namespace) -> int:
    from . import tray

    return tray.main()


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(arguments)
    if args.verb in GUI_VERBS:
        _use_gi_interpreter(arguments)  # may replace this process
    try:
        return args.handler(args)
    except (
        EngineError,
        sessions.SessionError,
        flavours.UnknownFlavour,
        flavours.InvalidImage,
        flavours.FlavourConfigError,
        flavours.ManifestError,
    ) as exc:
        print(f"{PROGRAM}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
