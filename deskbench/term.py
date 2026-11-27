"""tmux argument builders, the grid rules and the ``list-windows`` parser for terminal sessions.

Pure functions, no I/O, so the grammar is tested without a container. Session targets are
prefixed with ``=`` so that ``main`` never resolves to a session such as ``mainline``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .sessions import SessionError

DEFAULT_SESSION = "main"
MIN_COLS, MAX_COLS = 20, 500
MIN_ROWS, MAX_ROWS = 5, 200
_CELLS = re.compile(r"^(\d{1,4})x(\d{1,4})$")
_LIST_FORMAT = (
    "#{session_name}\t#{session_attached}\t#{window_width}\t#{window_height}\t#{window_active}"
)


@dataclass(frozen=True)
class TermSession:
    name: str
    cols: int
    rows: int
    attached: int

    @property
    def grid(self) -> str:
        return f"{self.cols}x{self.rows}"

    def as_dict(self) -> dict[str, str | int]:
        return {"name": self.name, "grid": self.grid, "attached": self.attached}


def validate_cells(value: str) -> tuple[int, int]:
    """Return ``(columns, rows)`` if the grid is within bounds, else raise."""
    match = _CELLS.match(value)
    if not match:
        raise SessionError(f"invalid grid {value!r}: expected COLSxROWS, for example 120x40")
    cols, rows = int(match.group(1)), int(match.group(2))
    if not (MIN_COLS <= cols <= MAX_COLS and MIN_ROWS <= rows <= MAX_ROWS):
        raise SessionError(
            f"grid {value!r} is out of range: columns {MIN_COLS}-{MAX_COLS}, "
            f"rows {MIN_ROWS}-{MAX_ROWS}"
        )
    return cols, rows


def ended_message(session: str, desktop: str) -> str:
    return (
        f"there is no session {session!r} in desktop {desktop!r}: it has ended (its shell "
        "exited) or was never started. Run `deskbench term list` to see what exists, or "
        "`deskbench term start` to start one"
    )


def _target(session: str) -> str:
    """Exact session name, for session-level commands."""
    return f"={session}"


def _pane_target(session: str) -> str:
    """Exact session name plus ``:``, which tmux resolves to its current window and pane."""
    return f"={session}:"


def new_session_args(session: str, cols: int, rows: int) -> list[str]:
    return ["new-session", "-d", "-s", session, "-x", str(cols), "-y", str(rows), "sh", "-l"]


def has_session_args(session: str) -> list[str]:
    return ["has-session", "-t", _target(session)]


def kill_session_args(session: str) -> list[str]:
    return ["kill-session", "-t", _target(session)]


def pin_args(session: str) -> list[str]:
    return ["set-option", "-w", "-t", _pane_target(session), "window-size", "manual"]


def read_pin_args(session: str) -> list[str]:
    return ["show-options", "-w", "-v", "-t", _pane_target(session), "window-size"]


def capture_args(session: str, history: int) -> list[str]:
    """``capture-pane`` of the visible area, with ``history`` scrollback lines above it when set."""
    args = ["capture-pane", "-p", "-J", "-t", _pane_target(session)]
    if history:
        args.extend(["-S", f"-{history}"])
    return args


def send_text_args(session: str, text: str) -> list[str]:
    return ["send-keys", "-t", _pane_target(session), "-l", "--", text]


def send_enter_args(session: str) -> list[str]:
    return ["send-keys", "-t", _pane_target(session), "Enter"]


def send_key_args(session: str, key: str) -> list[str]:
    return ["send-keys", "-t", _pane_target(session), "--", key]


def list_args() -> list[str]:
    return ["list-windows", "-a", "-F", _LIST_FORMAT]


def parse_list(text: str) -> list[TermSession]:
    """Sessions from ``list_args`` output; only each session's active window carries its grid."""
    sessions = []
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) != 5 or fields[4] != "1":
            continue
        name, attached, cols, rows, _ = fields
        sessions.append(TermSession(name, int(cols), int(rows), int(attached)))
    return sessions
