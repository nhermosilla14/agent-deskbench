"""Single-instance and liveness for the tray, using a lifetime-held flock.

The lock file *is* the answer to "is a tray running?": whoever holds it is the tray. No PID
files, no socket probes, no registry.
"""

from __future__ import annotations

import fcntl
import os
import signal
from pathlib import Path


def state_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = Path(base) / "deskbench"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def lock_path() -> Path:
    return state_dir() / "tray.lock"


def attention_path() -> Path:
    return state_dir() / "attention"


def acquire(path: Path | None = None) -> object | None:
    """Take the tray lock without waiting.

    Returns the open file (keep it alive) or ``None`` when another tray already holds it.
    """
    handle = open(path or lock_path(), "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def is_held(path: Path | None = None) -> bool:
    """True when some live process holds the tray lock."""
    handle = open(path or lock_path(), "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(handle, fcntl.LOCK_UN)
        return False
    finally:
        handle.close()


def tray_pid(path: Path | None = None) -> int | None:
    """PID recorded by the tray, if it looks like ours."""
    try:
        text = (path or lock_path()).read_text().strip()
        pid = int(text)
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, ValueError):
        return None
    return pid if b"deskbench" in cmdline else None


def poke(path: Path | None = None) -> None:
    """Ask a running tray to refresh now instead of on its next tick."""
    pid = tray_pid(path)
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGUSR1)
    except OSError:
        pass
