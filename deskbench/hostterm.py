"""Open a host terminal on a desktop: the human's way in, never the agent's.

The emulator is found on the host. ``DESKBENCH_TERMINAL`` (which may carry arguments) wins and
must be installed; ``$TERMINAL`` is tried next and skipped when stale; then the candidates below
in order.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys

from . import engine
from .engine import EngineError

TERMINAL_ENV = "DESKBENCH_TERMINAL"
CANDIDATES = (
    "xdg-terminal-exec",
    "x-terminal-emulator",
    "konsole",
    "gnome-terminal",
    "xfce4-terminal",
    "alacritty",
    "kitty",
    "foot",
    "wezterm",
    "xterm",
)
# Arguments that come between the emulator and the command, since emulators disagree.
_SEPARATORS = {
    "gnome-terminal": ("--",),
    "xfce4-terminal": ("-x",),
    "wezterm": ("start", "--"),
    "kitty": (),
    "foot": (),
    "xdg-terminal-exec": (),
}
_DEFAULT_SEPARATOR = ("-e",)


def _usable(value: str) -> list[str] | None:
    """The emulator argv from ``value`` if its program is installed, else ``None``."""
    try:
        argv = shlex.split(value)
    except ValueError:
        return None
    if argv and shutil.which(argv[0]):
        return argv
    return None


def emulator() -> list[str]:
    """The emulator's argv (program and its own arguments), before the command is appended."""
    explicit = os.environ.get(TERMINAL_ENV, "").strip()
    if explicit:
        argv = _usable(explicit)
        if argv is None:
            raise EngineError(f"{TERMINAL_ENV} is set to {explicit!r}, which is not installed")
        return argv
    for value in (os.environ.get("TERMINAL", ""), *CANDIDATES):
        argv = _usable(value)
        if argv:
            return argv
    raise EngineError(
        f"no terminal emulator found; looked for ${TERMINAL_ENV}, $TERMINAL, then "
        f"{', '.join(CANDIDATES)}. Set {TERMINAL_ENV} to one of them"
    )


def _in_terminal(command: list[str]) -> list[str]:
    program = emulator()
    separator = _SEPARATORS.get(os.path.basename(program[0]), _DEFAULT_SEPARATOR)
    return [*program, *separator, *command]


def attach_argv(name: str, session: str) -> list[str]:
    """The host command that opens ``session`` in a terminal window, without running it.

    ``deskbench term attach --print`` shows this. It is a debugging surface, not an interface.
    """
    return _in_terminal(engine.term_attach_command(name, session))


def attach(name: str, session: str) -> None:
    """Open ``session`` in a new terminal window and return without waiting for it."""
    argv = attach_argv(name, session)
    if sys.stdout.isatty():
        _warn_if_smaller(name, session)
    _spawn(argv)


def open_shell(name: str) -> None:
    """Open a private ``sh -l`` in a new terminal window; it is not a session."""
    _spawn(_in_terminal(engine.shell_command(name)))


def _warn_if_smaller(name: str, session: str) -> None:
    entry = next((item for item in engine.term_list(name) if item.name == session), None)
    if entry is None:
        return
    size = shutil.get_terminal_size()
    if size.columns < entry.cols or size.lines < entry.rows:
        print(
            f"deskbench: this terminal is {size.columns}x{size.lines}, smaller than session "
            f"{session!r} ({entry.grid}); the session keeps its size and parts may be cut off",
            file=sys.stderr,
        )


def _spawn(argv: list[str]) -> None:
    try:
        subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise EngineError(f"could not start {argv[0]}: {exc}") from exc
