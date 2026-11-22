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


def _is_tray_process(pid: int) -> bool:
    """True only for ``python3 -m deskbench tray``, never for a bystander mentioning the name."""
    try:
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    return b"-m" in argv and b"deskbench" in argv and b"tray" in argv


def tray_pid(path: Path | None = None) -> int | None:
    """PID recorded by the tray, if the process still looks like ours."""
    try:
        pid = int((path or lock_path()).read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if _is_tray_process(pid) else None


def poke(path: Path | None = None) -> bool:
    """Ask a running tray to refresh now. Never signals a process we cannot identify."""
    if not is_held(path):
        return False
    pid = tray_pid(path)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGUSR1)
    except OSError:
        return False
    return True


def attention_dir() -> Path:
    path = state_dir() / "attention"
    path.mkdir(mode=0o700, exist_ok=True)
    return path


def attention_mark(name: str, pid: int) -> Path:
    """Record that the process ``pid`` is waiting for a human on ``name``."""
    marker = attention_dir() / f"{name}.{pid}"
    marker.touch()
    return marker


def attention_live() -> bool:
    """Any pending request whose asker is still alive; dead askers are pruned."""
    live = False
    for marker in attention_dir().iterdir():
        try:
            pid = int(marker.name.rsplit(".", 1)[1])
        except (IndexError, ValueError):
            marker.unlink(missing_ok=True)
            continue
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            marker.unlink(missing_ok=True)
            continue
        except PermissionError:
            pass
        live = True
    return live
