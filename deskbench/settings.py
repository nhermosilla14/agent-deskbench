"""Host preferences edited by the tray: the default grid for ``New terminal…``.

Stored in ``$XDG_CONFIG_HOME/agent-deskbench/settings.toml`` (``~/.config`` when unset). Only the
tray writes this file, and reads never raise: an absent or corrupt file means the default.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import tomllib

from . import term

DEFAULT_SIZE = "120x40"
FILE_NAME = "settings.toml"


@dataclass(frozen=True)
class Settings:
    default_size: str = DEFAULT_SIZE


def path() -> Path:
    """The settings file. Resolved from the XDG config root only, never from the flavours override."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg.strip()).expanduser() if xdg and xdg.strip() else Path.home() / ".config"
    return base / "agent-deskbench" / FILE_NAME


def load() -> Settings:
    """Return the stored settings, or the default when the file is absent, unreadable or invalid."""
    try:
        data = tomllib.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):  # TOML and UTF-8 errors are ValueErrors
        return Settings()
    table = data.get("term")
    value = table.get("default_size") if isinstance(table, dict) else None
    if not isinstance(value, str):
        return Settings()
    try:
        term.validate_cells(value)
    except ValueError:
        return Settings()
    return Settings(default_size=value)


def save(settings: Settings) -> None:
    """Validate, then replace the file atomically; a refused value never touches the stored one."""
    term.validate_cells(settings.default_size)
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    text = f'[term]\ndefault_size = "{settings.default_size}"\n'
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".settings-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
